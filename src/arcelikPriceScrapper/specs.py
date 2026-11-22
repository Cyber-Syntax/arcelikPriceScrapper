from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

from selectolax.lexbor import LexborHTMLParser as HTMLParser

from .config import Config
from .http import Http
from .models import ProductRow
from .progress import Progress
from .report import Report

log = logging.getLogger("scrapper.specs")

# Parser/cache semasi degisince eski bos kayitlarin tekrar cekilmesini saglar.
SPECS_CACHE_VERSION = 2


def clean(text: str | None) -> str:
    if not text:
        return ""
    return re.sub(r"\s+", " ", text.replace("\xa0", " ")).strip()


def _html_text(fragment: str) -> str:
    fragment = re.sub(r"<br\s*/?>", "\n", fragment, flags=re.I)
    fragment = re.sub(
        r"</(?:p|div|li|h[1-6]|small)>", "\n", fragment, flags=re.I
    )
    raw = HTMLParser(fragment).text(separator="\n", strip=True) or ""
    lines = [clean(line) for line in raw.splitlines()]
    return "\n".join(line for line in lines if line)


@dataclass
class SpecDetails:
    features: list[dict[str, str]] = field(default_factory=list)
    specifications: list[dict[str, str]] = field(default_factory=list)

    def to_dict(self) -> dict[str, list[dict[str, str]]]:
        return {
            "features": self.features,
            "specifications": self.specifications,
        }


def parse_spec_details(html: str) -> SpecDetails:
    tree = HTMLParser(html)
    features: list[dict[str, str]] = []
    seen_features: set[tuple[str, str, str]] = set()
    for item in tree.css(".pdp-technologies .ftc-item"):
        title_node = item.css_first(".ftc-title")
        text_node = item.css_first(".ftc-text")
        title = clean(title_node.text(strip=True)) if title_node else ""
        text = ""
        note = ""
        if text_node is not None:
            raw = text_node.html or ""
            notes = [
                clean(node.text(strip=True))
                for node in text_node.css("small")
            ]
            note = "\n".join(n for n in notes if n)
            main_html = re.sub(
                r"<small\b[^>]*>.*?</small>", " ", raw,
                flags=re.S | re.I,
            )
            text = _html_text(main_html)
        if not title and not text and not note:
            continue
        key = (title, text, note)
        if key in seen_features:
            continue
        seen_features.add(key)
        features.append({"title": title, "text": text, "note": note})

    specifications: list[dict[str, str]] = []
    seen_specs: set[tuple[str, str, str]] = set()
    for group in tree.css("#pdp-features-container .feature-item"):
        title_node = group.css_first(".title")
        group_name = clean(title_node.text(strip=True)) if title_node else ""
        for row in group.css("dl .item"):
            name_node = row.css_first("dt")
            value_node = row.css_first("dd")
            name = clean(name_node.text(strip=True)) if name_node else ""
            value = clean(value_node.text(strip=True)) if value_node else ""
            if not name and not value:
                continue
            key = (group_name, name, value)
            if key in seen_specs:
                continue
            seen_specs.add(key)
            specifications.append(
                {"group": group_name, "name": name, "value": value}
            )
    return SpecDetails(features=features, specifications=specifications)


def load_specs_cache(
    path: Path, report: Report
) -> dict[str, dict[str, object]]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        report.warn(f"specs cache okunamadi: {exc}")
        return {}
    if not isinstance(data, dict):
        report.warn("specs cache gecersiz (obje bekleniyordu)")
        return {}
    return {str(k): v for k, v in data.items() if isinstance(v, dict)}


def write_specs_cache(
    path: Path, cache: dict[str, dict[str, object]]
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(
        json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    tmp.replace(path)


def _apply(row: ProductRow, entry: dict[str, object]) -> None:
    features = entry.get("features")
    specifications = entry.get("specifications")
    if isinstance(features, list):
        row.features = [
            {str(k): str(v) for k, v in item.items()}
            for item in features
            if isinstance(item, dict)
        ]
    if isinstance(specifications, list):
        row.specifications = [
            {str(k): str(v) for k, v in item.items()}
            for item in specifications
            if isinstance(item, dict)
        ]
    row.specs_scraped_at = str(entry.get("scraped_at") or "")


def _key(row: ProductRow) -> str:
    return row.product_id or row.url


async def enrich_specs(
    http: Http,
    rows: list[ProductRow],
    cfg: Config,
    report: Report,
    scraped_at: str,
    *,
    refresh: bool = False,
    progress: Progress | None = None,
) -> list[ProductRow]:
    path = Path(cfg.cache.specs_file)
    cache = load_specs_cache(path, report)
    candidates: list[ProductRow] = [
        row for row in rows if row.kind != "warranty" and row.url
    ]
    to_fetch: list[ProductRow] = []
    for row in candidates:
        entry = cache.get(_key(row))
        if (
            entry is not None
            and not refresh
            and entry.get("cache_version") == SPECS_CACHE_VERSION
        ):
            _apply(row, entry)
        else:
            to_fetch.append(row)
    if progress is not None and to_fetch:
        progress.start("specs", len(to_fetch))
    fetched = 0
    failures = 0
    changed = False
    try:
        for row in to_fetch:
            if http.aborted:
                break
            if progress is not None:
                progress.set_detail(row.product_id or row.name)
            html = await http.get(row.url)
            if not html:
                failures += 1
                report.warn(f"spec sayfasi alinamadi: {row.url}")
                if progress is not None:
                    progress.advance()
                continue
            try:
                details = parse_spec_details(html)
            except Exception as exc:  # noqa: BLE001
                failures += 1
                report.warn(f"spec parse hatasi ({row.url}): {exc}")
                if progress is not None:
                    progress.advance()
                continue
            cache[_key(row)] = {
                **details.to_dict(),
                "cache_version": SPECS_CACHE_VERSION,
                "scraped_at": scraped_at,
            }
            _apply(row, cache[_key(row)])
            fetched += 1
            changed = True
            if progress is not None:
                progress.advance(products=1)
    finally:
        if changed:
            try:
                write_specs_cache(path, cache)
            except OSError as exc:
                report.warn(f"specs cache yazilamadi: {exc}")
    report.set("specs_products", len(candidates))
    report.set("specs_fetched", fetched)
    report.set("specs_failures", failures)
    report.set("specs_rows", sum(len(r.specifications) for r in rows))
    report.set("features_rows", sum(len(r.features) for r in rows))
    report.set("specs_cache_entries", len(cache))
    return rows
