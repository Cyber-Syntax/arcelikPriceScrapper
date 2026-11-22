from __future__ import annotations

import logging
import re

from pydantic import ValidationError
from selectolax.lexbor import LexborHTMLParser as HTMLParser

from .http import BASE, Http
from .models import ProductRow
from .prices import clean, parse_price
from .report import Report

log = logging.getLogger("scrapper.warranties")

URL = f"{BASE}/ek-garanti-uygulamalari"


def tr_lower(s: str) -> str:
    return s.replace("İ", "i").replace("I", "ı").lower()


def expand_table(table) -> list[list[str]]:
    """rowspan/colspan'i acarak duz bir grid dondurur."""
    pending: dict[int, tuple[int, str]] = {}
    grid: list[list[str]] = []
    for tr in table.css("tr"):
        cells: list[str] = []
        col = 0
        tds = iter(tr.css("td, th"))
        while True:
            if col in pending:
                remaining, txt = pending[col]
                cells.append(txt)
                if remaining <= 1:
                    del pending[col]
                else:
                    pending[col] = (remaining - 1, txt)
                col += 1
                continue
            td = next(tds, None)
            if td is None:
                break
            txt = clean(td.text(separator=" ", strip=True))
            rs = int(
                re.sub(r"\D", "", td.attributes.get("rowspan") or "") or 1
            )
            cs = int(
                re.sub(r"\D", "", td.attributes.get("colspan") or "") or 1
            )
            for _ in range(cs):
                cells.append(txt)
                if rs > 1:
                    pending[col] = (rs - 1, txt)
                col += 1
        if cells:
            grid.append(cells)
    return grid


def parse_warranty_html(
    html: str, category: str, scraped_at: str, url: str = URL
) -> list[ProductRow]:
    tree = HTMLParser(html)
    out: list[ProductRow] = []
    for table in tree.css("table"):
        grid = expand_table(table)
        hdr_idx = next(
            (
                i
                for i, r in enumerate(grid)
                if any("tanım" in tr_lower(c) for c in r)
            ),
            None,
        )
        if hdr_idx is None:
            continue
        hdr = [tr_lower(c) for c in grid[hdr_idx]]

        def find(*keys: str) -> int | None:
            for i, h in enumerate(hdr):
                if any(k in h for k in keys):
                    return i
            return None

        c_def, c_price = find("tanım"), find("fiyat")
        c_group, c_period = find("grubu"), find("dönem")
        if c_def is None or c_price is None:
            continue
        for r in grid[hdr_idx + 1 :]:
            if len(r) <= max(c_def, c_price):
                continue
            name = r[c_def]
            price = parse_price(r[c_price])
            if not name or price is None:
                continue
            group = (
                r[c_group] if c_group is not None and c_group < len(r) else ""
            )
            period = (
                r[c_period]
                if c_period is not None and c_period < len(r)
                else ""
            )
            try:
                out.append(
                    ProductRow(
                        name=name,
                        category=category,
                        price=price,
                        kind="warranty",
                        title=f"{group} {period}".strip(),
                        url=url,
                        category_path=category,
                        source="warranty",
                        scraped_at=scraped_at,
                    )
                )
            except ValidationError:
                log.warning("gecersiz garanti satiri: %r", r)
    return out


async def scrape_warranties(
    http: Http, category: str, scraped_at: str, report: Report
) -> list[ProductRow]:
    html = await http.get(URL)
    if not html:
        report.warn("ek garanti sayfasi alinamadi")
        return []
    rows = parse_warranty_html(html, category, scraped_at)
    report.set("warranty_rows", len(rows))
    if not rows:
        report.warn(
            "ek garanti tablosundan hic satir cikmadi (yapi degismis olabilir)"
        )
    names = [r.name for r in rows]
    if len(set(names)) != len(names):
        report.warn("ek garanti adlarinda tekrar var")
    return rows
