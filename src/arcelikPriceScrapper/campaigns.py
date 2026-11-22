from __future__ import annotations

import logging
import re
from datetime import date
from urllib.parse import unquote, urlparse

from selectolax.lexbor import LexborHTMLParser as HTMLParser

from .export import Table
from .http import BASE, Http
from .prices import Card, clean, norm_url, parse_cards_tree, parse_price
from .progress import Progress
from .report import Report

log = logging.getLogger("scrapper.campaigns")

MONTHS = {
    "ocak": 1,
    "şubat": 2,
    "mart": 3,
    "nisan": 4,
    "mayıs": 5,
    "haziran": 6,
    "temmuz": 7,
    "ağustos": 8,
    "eylül": 9,
    "ekim": 10,
    "kasım": 11,
    "aralık": 12,
}
_W = r"([^\W\d_]+)"
_D1 = re.compile(
    rf"(\d{{1,2}})\s+{_W}\s*[-–]\s*(\d{{1,2}})\s+{_W}\s+(\d{{4}})"
)
_D2 = re.compile(rf"(\d{{1,2}})\s*[-–]\s*(\d{{1,2}})\s+{_W}\s+(\d{{4}})")

CAMPAIGN_HEADERS = [
    "campaign_id",
    "name",
    "category",
    "url",
    "date_text",
    "start_date",
    "end_date",
    "conditions",
    "product_count",
    "bayios_sheet",
    "scraped_at",
]
BAYIOS_HEADERS = ["Ürün Adı", "İlişki Türü", "Gerekli Adet"]
BAYIOS_RELATION = "İlgili ürün"
CP_HEADERS = [
    "campaign_id",
    "product_name",
    "product_id",
    "regular_price",
    "website_discounted_price",
    "product_url",
    "scraped_at",
]


_TR_SLUG = str.maketrans("çğıöşüÇĞİÖŞÜ", "cgiosuCGIOSU")


def _sheet_name(name: str, index: int) -> str:
    cleaned = re.sub(r"[\[\]:*?/\\]", " ", name)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    base = cleaned[:24].strip() or "Kampanya"
    return f"{base} ~{index:02d}"[:31]


def _file_slug(name: str, index: int) -> str:
    text = name.translate(_TR_SLUG).lower()
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")[:40]
    return f"campaign_{index:02d}_{text or 'kampanya'}"


def bayios_table(
    index: int, campaign_name: str, cards: dict[str, Card]
) -> Table | None:
    """Bayios kampanya detay formati: Urun Adi | Iliski Turu | Gerekli Adet."""
    names: list[str] = []
    seen: set[str] = set()
    for card in cards.values():
        if card.name and card.name not in seen:
            seen.add(card.name)
            names.append(card.name)
    if not names:
        return None
    return Table(
        _file_slug(campaign_name, index),
        _sheet_name(campaign_name, index),
        BAYIOS_HEADERS,
        [[name, BAYIOS_RELATION, None] for name in names],
    )


def find_date_text(text: str) -> str | None:
    m = _D1.search(text) or _D2.search(text)
    return m.group(0) if m else None


def parse_date_range(text: str | None) -> tuple[str, str] | None:
    if not text:
        return None
    m = _D1.search(text)
    if m:
        d1, m1, d2, m2, y = m.groups()
    else:
        m = _D2.search(text)
        if not m:
            return None
        d1, d2, m2, y = m.groups()
        m1 = m2
    mo1, mo2 = MONTHS.get(m1.lower()), MONTHS.get(m2.lower())
    if not mo1 or not mo2:
        return None
    y2 = int(y)
    y1 = y2 if mo1 <= mo2 else y2 - 1
    try:
        return date(y1, mo1, int(d1)).isoformat(), date(
            y2, mo2, int(d2)
        ).isoformat()
    except ValueError:
        return None


def _is_campaign_href(href: str | None) -> bool:
    if not href:
        return False
    parts = urlparse(norm_url(href)).path.strip("/").split("/")
    return (
        len(parts) == 3
        and parts[0] == "kampanyalar"
        and not parts[2].endswith("-kampanyalari")
    )


def discover_campaigns(html: str) -> dict[str, str | None]:
    """/kampanyalar HTML'i -> {kampanya_url: tarih_metni | None}"""
    tree = HTMLParser(html)
    found: dict[str, str | None] = {}
    for a in tree.css("a[href]"):
        href = a.attributes.get("href")
        if not _is_campaign_href(href):
            continue
        url = norm_url(href)
        date_text = found.get(url)
        if date_text is None:
            node = a
            for _ in range(6):
                node = node.parent
                if node is None:
                    break
                dt = find_date_text(
                    clean(node.text(separator=" ", strip=True))
                )
                if dt:
                    urls = {
                        norm_url(x.attributes.get("href"))
                        for x in node.css("a[href]")
                        if _is_campaign_href(x.attributes.get("href"))
                    }
                    if len(urls) == 1:  # tarih sadece bu karta ait
                        date_text = dt
                    break
        found[url] = date_text
    return found


def extract_conditions(tree: HTMLParser) -> str:
    for li in tree.css("li"):
        own = clean(li.text(strip=True))
        if own.startswith("Katılım Koşulları"):
            items = [clean(x.text(strip=True)) for x in li.css("li")]
            items = [i for i in items if i]
            if items:
                return "\n".join(items)
            return clean(own.removeprefix("Katılım Koşulları"))
    # yedek: baslik elemani bulup ust elemanin metnini al
    for node in tree.css("a, button, span, div, h2, h3, h4, strong, p, label"):
        if (
            clean(node.text(strip=True)) == "Katılım Koşulları"
            and node.parent is not None
        ):
            lines = [
                clean(t)
                for t in node.parent.text(separator="\n", strip=True).split(
                    "\n"
                )
                if clean(t)
            ]
            lines = [x for x in lines if x != "Katılım Koşulları"]
            return "\n".join(lines[:30])
    return ""


def parse_cards_fallback(tree: HTMLParser) -> dict[str, Card]:
    """div.prd-inner bulunamazsa: h2 > a basligindan urun, kart metninden TL fiyatlari."""
    rows: dict[str, Card] = {}
    for a in tree.css("h2 a[href]"):
        href = a.attributes.get("href")
        if not href:
            continue
        url = norm_url(href)
        if len(urlparse(url).path.strip("/").split("/")) != 2:
            continue
        best = ""
        node = a.parent
        for _ in range(6):
            if node is None or len(node.css("h2 a[href]")) != 1:
                break
            best = clean(node.text(separator=" ", strip=True))
            node = node.parent
        prices = [parse_price(m) for m in re.findall(r"\d[\d.,]*\s*TL", best)]
        prices = [p for p in prices if p is not None]
        name = clean(a.text(strip=True))
        rows[url] = Card(
            name=name,
            title=name,
            code="",
            url=url,
            price=prices[0] if prices else None,
            discounted=prices[1] if len(prices) > 1 else None,
        )
    return rows


async def scrape_campaigns(
    http: Http,
    report: Report,
    scraped_at: str,
    progress: Progress | None = None,
) -> list[Table]:
    idx_html = await http.get(f"{BASE}/kampanyalar")
    if not idx_html:
        report.warn("/kampanyalar alinamadi")
        return []
    discovered = discover_campaigns(idx_html)
    log.info("%d kampanya bulundu", len(discovered))
    report.set("campaigns", len(discovered))
    if progress is not None and discovered:
        progress.start("kampanyalar", len(discovered))

    camp_rows: list[list] = []
    cp_rows: list[list] = []
    bayios_tables: list[Table] = []
    empty = 0
    for url, idx_date in discovered.items():
        if progress is not None:
            progress.set_detail(url.rsplit("/", 1)[-1])
        html = await http.get(url)
        if not html:
            report.warn(f"kampanya sayfasi alinamadi: {url}")
            continue
        tree = HTMLParser(html)
        h1 = tree.css_first("h1")
        if h1 is not None:
            name = clean(h1.text(strip=True))
        else:
            t = tree.css_first("title")
            name = (
                clean(t.text(strip=True)).removesuffix("| Arçelik").strip()
                if t
                else ""
            )
        conditions = extract_conditions(tree)
        date_text = idx_date or find_date_text(conditions)
        rng = parse_date_range(date_text)

        cards = parse_cards_tree(tree)
        if not cards:
            cards = parse_cards_fallback(tree)
            if cards:
                log.warning("yedek kart parser'i kullanildi: %s", url)
        m = re.search(r"(\d+)\s+sonuç bulundu", tree.text(separator=" "))
        if m and int(m.group(1)) != len(cards):
            report.warn(
                f"{url}: sayfa {m.group(1)} sonuc diyor, {len(cards)} urun parse edildi"
            )
        if not cards:
            empty += 1

        parts = urlparse(url).path.strip("/").split("/")
        cid = unquote(parts[-1])
        index = len(camp_rows) + 1
        sheet_name = _sheet_name(name, index)
        camp_rows.append(
            [
                cid,
                name,
                parts[1],
                url,
                date_text,
                rng[0] if rng else None,
                rng[1] if rng else None,
                conditions,
                len(cards),
                sheet_name,
                scraped_at,
            ]
        )
        table = bayios_table(index, name, cards)
        if table is not None:
            bayios_tables.append(table)
        for c in cards.values():
            cp_rows.append(
                [
                    cid,
                    c.name,
                    c.product_id or c.code,
                    c.price,
                    c.discounted,
                    c.url,
                    scraped_at,
                ]
            )
        if progress is not None:
            progress.advance(products=len(cards))

    report.set("campaigns_without_products", empty)
    report.set("campaign_product_rows", len(cp_rows))
    report.set("campaign_bayios_sheets", len(bayios_tables))
    return [
        Table("campaigns", "Kampanyalar", CAMPAIGN_HEADERS, camp_rows),
        Table(
            "campaign_products",
            "Kampanya Ürünleri",
            CP_HEADERS,
            cp_rows,
            money_cols=(3, 4),
        ),
        *bayios_tables,
    ]
