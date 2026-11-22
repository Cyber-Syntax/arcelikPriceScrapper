from __future__ import annotations

import hashlib
import json
import logging
import re
from collections import Counter
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from urllib.parse import urljoin, urlparse

from pydantic import ValidationError
from selectolax.lexbor import LexborHTMLParser as HTMLParser

from .categories import (
    CategoryNode,
    CategoryTree,
    fetch_category_tree,
    is_blog_url,
    norm_key,
)
from .config import CategoryEntry, Config, ExplicitProduct
from .http import BASE, AbortRun, Http
from .models import ProductRow
from .progress import Progress
from .report import Report

log = logging.getLogger("scrapper.prices")

SUFFIX = " ürün detaylarını incele"
_NUM = re.compile(r"\d[\d.,]*")
_URL_NUM = re.compile(r"^\d{1,3}(?:\.\d{3})+$")


@dataclass
class Card:
    name: str
    title: str
    code: str
    url: str
    price: Decimal | None
    discounted: Decimal | None
    hierarchy: str = ""
    product_id: str = ""


@dataclass
class ListingResult:
    cards: dict[str, Card]
    crumbs: list[str]
    reported_total: int | None


@dataclass
class PdpSummary:
    url: str
    name: str
    title: str
    code: str
    product_id: str
    category_path: str
    category_lv1: str | None
    category_lv2: str | None
    category_lv3: str | None
    price: Decimal | None
    discounted_price: Decimal | None


def clean(text: str | None) -> str:
    if not text:
        return ""
    return re.sub(r"\s+", " ", text.replace("\xa0", " ")).strip()


def parse_price(text: str | None) -> Decimal | None:
    """'56.399 TL', '₺3.099', '1.234,50', '475.00' -> Decimal."""
    if not text:
        return None
    m = _NUM.search(str(text).replace("\xa0", " "))
    if not m:
        return None
    s = m.group(0).rstrip(".,")
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    elif _URL_NUM.fullmatch(s):
        s = s.replace(".", "")
    try:
        return Decimal(s)
    except InvalidOperation:
        return None


def price_from_value(value: object) -> Decimal | None:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return value
    if isinstance(value, int | float):
        return Decimal(str(value))
    text = clean(str(value))
    if re.fullmatch(r"-?\d+(?:\.\d+)?", text):
        try:
            return Decimal(text)
        except InvalidOperation:
            return None
    return parse_price(text)


def norm_url(href: str) -> str:
    return urljoin(BASE, href).split("?")[0].split("#")[0].rstrip("/")


def leaf_of(url: str) -> str:
    parts = urlparse(url).path.strip("/").split("/")
    return parts[0] if len(parts) == 2 else ""


def leaf_counts(urls: set[str]) -> Counter[str]:
    return Counter(x for x in map(leaf_of, urls) if x)


def _first_price(nodes) -> Decimal | None:
    for node in nodes:
        value = parse_price(node.text(strip=True))
        if value is not None:
            return value
    return None


def parse_cards_tree(tree: HTMLParser) -> dict[str, Card]:
    rows: dict[str, Card] = {}
    for card in tree.css("div.prd-inner"):
        a = card.css_first(".prd-detail a[href]") or card.css_first("a.js-prd-url")
        if a is None:
            continue
        href = a.attributes.get("href")
        if not href:
            continue
        url = norm_url(href)
        label = clean(a.attributes.get("aria-label") or "").removesuffix(SUFFIX)
        t = card.css_first(".prd-name .t")
        title = clean(t.text(strip=True)) if t else ""
        code_node = card.css_first("[data-product-code]")
        id_node = card.css_first("[data-product-id]")
        product_id = clean(
            (id_node.attributes.get("data-product-id") if id_node else "")
            or (code_node.attributes.get("data-product-code") if code_node else "")
            or ""
        )
        hierarchy = ""
        for node in card.css("[data-product-hierarchy]"):
            candidate = clean(node.attributes.get("data-product-hierarchy") or "")
            if candidate:
                hierarchy = candidate
                break
        price = _first_price(card.css(".prd-price .prc"))
        discounted = _first_price(card.css(".prc-third"))
        if price is None and discounted is not None:
            price, discounted = discounted, None
        if price is not None and discounted is not None and price == discounted:
            discounted = None
        rows[url] = Card(
            name=label or title,
            title=title or label,
            code=(code_node.attributes.get("data-product-code") or "")
            if code_node
            else "",
            url=url,
            price=price,
            discounted=discounted,
            hierarchy=hierarchy,
            product_id=product_id,
        )
    return rows


def parse_cards(html: str) -> dict[str, Card]:
    return parse_cards_tree(HTMLParser(html))


def breadcrumb_names(tree: HTMLParser) -> list[str]:
    out: list[str] = []
    for li in tree.css("ol.breadcrumb li"):
        name = clean(li.text(strip=True))
        if name and norm_key(name) not in ("ana sayfa", "anasayfa"):
            out.append(name)
    return out


def listing_breadcrumb(html: str) -> list[str]:
    return breadcrumb_names(HTMLParser(html))


def listing_total(html: str) -> int | None:
    tree = HTMLParser(html)
    text = clean(tree.text(separator=" ", strip=True))
    match = re.search(r"(\d[\d.]*)\s+(?:ürün|sonuç)", text)
    if not match:
        return None
    try:
        return int(match.group(1).replace(".", ""))
    except ValueError:
        return None


def _product_ld(tree: HTMLParser) -> dict[str, object]:
    for script in tree.css('script[type="application/ld+json"]'):
        try:
            data = json.loads(script.text(), strict=False)
        except ValueError:
            continue
        items = data if isinstance(data, list) else [data]
        for item in items:
            if not isinstance(item, dict):
                continue
            kind = item.get("@type")
            if kind == "Product" or (isinstance(kind, list) and "Product" in kind):
                return item
    return {}


def _embedded_product_id(html: str) -> str:
    match = re.search(
        r'"products"\s*:\s*\[\s*\{.*?"id"\s*:\s*"([^"]+)"',
        html,
        re.S,
    )
    return clean(match.group(1)) if match else ""


def _list_price(offers: dict[str, object]) -> Decimal | None:
    specs = offers.get("priceSpecification")
    if isinstance(specs, dict):
        specs = [specs]
    if not isinstance(specs, list):
        return None
    for spec in specs:
        if not isinstance(spec, dict):
            continue
        price_type = str(spec.get("priceType") or "")
        if "ListPrice" in price_type:
            return price_from_value(spec.get("price"))
    return None


def parse_pdp_summary(html: str, url: str = "") -> PdpSummary:
    tree = HTMLParser(html)
    crumbs = breadcrumb_names(tree)
    ld = _product_ld(tree)
    ld_name = clean(str(ld.get("name") or ""))
    h1 = tree.css_first("h1")
    h1_text = clean(h1.text(separator=" ", strip=True)) if h1 else ""
    title_node = tree.css_first("title")
    title_text = ""
    if title_node is not None:
        title_text = clean(title_node.text(strip=True)).split("|", 1)[0].strip()
    title = ld_name or h1_text or title_text
    name = crumbs[-1] if crumbs else (ld_name or h1_text or title_text)
    category_names = crumbs[:-1] if crumbs else []
    category_path = " > ".join(category_names)
    lv1 = category_names[0] if len(category_names) >= 1 else None
    lv2 = category_names[1] if len(category_names) >= 2 else None
    lv3 = category_names[2] if len(category_names) >= 3 else None

    offers = ld.get("offers") or {}
    if isinstance(offers, list):
        offers = offers[0] if offers else {}
    if not isinstance(offers, dict):
        offers = {}
    price = price_from_value(offers.get("price"))
    list_price = _list_price(offers)
    if list_price is not None:
        regular = list_price
        discounted = price if price is not None and price != list_price else None
    else:
        regular = price
        discounted = None

    code = clean(str(ld.get("sku") or ld.get("productID") or ""))
    if not code:
        code_node = tree.css_first("[data-product-code]")
        if code_node is not None:
            code = clean(code_node.attributes.get("data-product-code") or "")
    id_node = tree.css_first("[data-product-id]")
    data_id = (
        clean(id_node.attributes.get("data-product-id") or "")
        if id_node is not None
        else ""
    )
    product_id = (
        clean(str(ld.get("productID") or ""))
        or data_id
        or code
        or _embedded_product_id(html)
    )
    return PdpSummary(
        url=url,
        name=name,
        title=title or name,
        code=code,
        product_id=product_id,
        category_path=category_path,
        category_lv1=lv1,
        category_lv2=lv2,
        category_lv3=lv3,
        price=regular,
        discounted_price=discounted,
    )


async def sitemap_product_urls(http: Http) -> set[str]:
    index = await http.get(f"{BASE}/sitemap.xml") or ""
    urls: set[str] = set()
    for loc in re.findall(r"<loc>\s*(.*?)\s*</loc>", index):
        if "PRODUCT" not in loc.upper():
            continue
        xml = await http.get(loc.replace("&amp;", "&")) or ""
        urls |= {
            norm_url(u)
            for u in re.findall(r"<loc>\s*(https://[^<\s]+?)\s*</loc>", xml)
        }
    return {url for url in urls if not is_blog_url(url)}


async def crawl_listing(
    http: Http,
    slug: str,
    max_pages: int,
    progress: Progress | None = None,
) -> ListingResult:
    cards: dict[str, Card] = {}
    crumbs: list[str] = []
    reported_total: int | None = None
    misses = 0
    for page in range(max_pages):
        if progress is not None:
            progress.set_detail(f"{slug} sayfa {page + 1}")
        url = f"{BASE}/{slug}" + (f"?page={page}" if page else "")
        html = await http.get(url)
        if not html:
            break
        if page == 0:
            crumbs = listing_breadcrumb(html)
            reported_total = listing_total(html)
        page_cards = parse_cards(html)
        if not page_cards:
            break
        new = set(page_cards) - set(cards)
        if not new:
            # Site bazi kategori sayfalarinda ayni sayfayi tekrar ediyor
            # (or. /buzdolabi?page=1). Tek tekrarda durma; iki tekrar
            # ust uste gelirse bitti kabul et.
            misses += 1
            if misses >= 2:
                break
            continue
        misses = 0
        cards.update(page_cards)
    return ListingResult(cards=cards, crumbs=crumbs, reported_total=reported_total)


def _read_explicit_cache(path: Path, report: Report) -> dict[str, dict[str, object]]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        report.warn(f"acik urun cache okunamadi: {exc}")
        return {}
    if not isinstance(data, dict):
        report.warn("acik urun cache gecersiz (obje bekleniyordu)")
        return {}
    return {str(k): v for k, v in data.items() if isinstance(v, dict)}


def _write_explicit_cache(path: Path, cache: dict[str, dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def _explicit_record(
    product: ExplicitProduct,
    summary: PdpSummary,
    scraped_at: str,
    html: str,
) -> dict[str, object]:
    price = product.price if product.price is not None else summary.price
    discounted = (
        product.discounted_price
        if product.discounted_price is not None
        else summary.discounted_price
    )
    app_category = product.app_category or summary.category_lv2
    return {
        "name": product.name or summary.name,
        "product_id": product.product_id or summary.product_id,
        "title": summary.title,
        "url": product.url,
        "category_path": summary.category_path,
        "category_lv1": summary.category_lv1,
        "category_lv2": summary.category_lv2,
        "category_lv3": summary.category_lv3,
        "app_category": app_category,
        "code": summary.code,
        "price": str(price) if price is not None else None,
        "discounted_price": str(discounted) if discounted is not None else None,
        "scraped_at": scraped_at,
        "content_hash": hashlib.sha1(html.encode("utf-8")).hexdigest(),
    }


async def refresh_explicit_products(
    http: Http,
    cfg: Config,
    report: Report,
    scraped_at: str,
    *,
    force: bool = False,
    cache: dict[str, dict[str, object]] | None = None,
    products: list[ExplicitProduct] | None = None,
    progress: Progress | None = None,
) -> dict[str, dict[str, object]]:
    path = Path(cfg.cache.explicit_file)
    if cache is None:
        cache = _read_explicit_cache(path, report)
    changed = False
    items = products if products is not None else cfg.products.include
    to_fetch = [
        product
        for product in items
        if not is_blog_url(product.url)
        and (
            force
            or product.url not in cache
            or product.fetch == "always"
        )
    ]
    if progress is not None and to_fetch:
        progress.start("acik urunler", len(to_fetch))
    try:
        for product in items:
            url = product.url
            if is_blog_url(url):
                report.warn(f"blog URL'si fiyat kaynagi degil, atlandi: {url}")
                continue
            cached = cache.get(url)
            if not force and cached is not None and product.fetch == "once":
                continue
            if http.aborted:
                break
            if progress is not None:
                progress.set_detail(
                    product.name or url.rsplit("/", 1)[-1]
                )
            html = await http.get(url)
            if not html:
                report.warn(f"acik urun alinamadi: {url}")
                if progress is not None:
                    progress.advance()
                continue
            summary = parse_pdp_summary(html, url)
            if not (product.name or summary.name):
                report.warn(f"acik urun adi bulunamadi: {url}")
                if progress is not None:
                    progress.advance()
                continue
            cache[url] = _explicit_record(product, summary, scraped_at, html)
            changed = True
            if progress is not None:
                progress.advance(products=1)
    finally:
        if changed:
            try:
                _write_explicit_cache(path, cache)
            except OSError as exc:
                report.warn(f"acik urun cache yazilamadi: {exc}")
    report.set("explicit_cache", str(path))
    report.set("explicit_cache_entries", len(cache))
    return cache


def _alias(name: str | None, aliases: dict[str, str]) -> str | None:
    if not name:
        return None
    direct = aliases.get(name)
    if direct:
        return direct
    normalized = {norm_key(k): v for k, v in aliases.items()}
    return normalized.get(norm_key(name), name)


def _explicit_blocked(
    product: ExplicitProduct,
    record: dict[str, object] | None,
    tree: CategoryTree | None,
    patterns: list[str],
) -> bool:
    """Kara liste explicit urunler icin de gecerlidir.

    force = true olan urun istisnadir. Kategori bilinmiyorsa guvenli taraf:
    kara liste varsa urunu ele (istenirse force veya app_category verilir).
    """
    if is_blog_url(product.url):
        return True
    if product.force:
        return False
    if not patterns:
        return False
    if tree is None:
        return True
    data = record or {}
    for value in (
        product.app_category,
        data.get("app_category"),
        data.get("category_lv3"),
        data.get("category_lv2"),
        data.get("category_lv1"),
        data.get("category_path"),
    ):
        if not value:
            continue
        text = clean(str(value))
        node = tree.find(text, warn=False)
        if node is None:
            node = tree.resolve_hierarchy(text.replace(" > ", " / "))
        if node is not None:
            return tree.is_excluded(node, patterns)
    slug = urlparse(product.url).path.strip("/").split("/")[0]
    node = tree.find(slug, warn=False)
    if node is not None:
        return tree.is_excluded(node, patterns)
    return True


def _app_category(
    node: CategoryNode | None,
    entry: CategoryEntry,
    aliases: dict[str, str],
) -> str | None:
    if entry.app_category:
        return _alias(entry.app_category, aliases)
    if node is None:
        return None
    lv2 = node.lv2()
    if lv2 is None:
        return None
    return _alias(lv2.name, aliases)


def _related(node: CategoryNode | None, target: CategoryNode) -> bool:
    """Dugum hedefin kendisi, alt kategorisi veya ust kategorisi mi?

    Kategori sayfalari bazen baska LV2 urunlerini (capraz satis) listeler.
    Bunlari hedef kategoriye yazmamak icin kullanilir.
    """
    if node is None:
        return True
    node_path = tuple(n.slug for n in node.path())
    target_path = tuple(n.slug for n in target.path())
    if node_path == target_path:
        return True
    if node_path[: len(target_path)] == target_path:
        return True
    return target_path[: len(node_path)] == node_path


def _resolve_node(
    tree: CategoryTree,
    card: Card,
    crumbs: list[str],
    listing_node: CategoryNode,
) -> CategoryNode | None:
    node = tree.resolve_hierarchy(card.hierarchy)
    if node is None or (node.level == 1 and listing_node.level >= 2):
        # Kart hierarchy'si yalnizca ust kategoriyi ("Elektronik" gibi)
        # cozebildiyse listing breadcrumb'i daha spesifik olabilir.
        crumb_node = (
            tree.resolve_hierarchy(" / ".join(crumbs)) if crumbs else None
        )
        if crumb_node is not None and _related(crumb_node, listing_node):
            node = crumb_node
        elif listing_node.level >= 2:
            node = listing_node
    return node


def _is_product_url(token: str) -> bool:
    parsed = urlparse(token)
    return parsed.scheme in ("http", "https") and parsed.netloc in {
        "www.arcelik.com.tr",
        "arcelik.com.tr",
    }


def _split_only(tokens: list[str]) -> tuple[list[str], list[str]]:
    categories: list[str] = []
    urls: list[str] = []
    for token in tokens:
        if _is_product_url(token):
            if is_blog_url(token):
                log.warning("blog URL'si fiyat kaynagi degil, atlandi: %s", token)
                continue
            urls.append(token)
        else:
            categories.append(token)
    return categories, urls


def _targets(
    tree: CategoryTree,
    cfg: Config,
    only: list[str],
    exclude: list[str],
    report: Report,
) -> list[tuple[CategoryNode, CategoryEntry]]:
    entries: list[CategoryEntry] = []
    if only:
        config_by_slug = {e.slug: e for e in cfg.categories.include}
        for token in only:
            node = tree.find(token)
            if node is None:
                report.warn(f"--only {token}: kategori bulunamadi")
                continue
            entry = config_by_slug.get(node.slug) or CategoryEntry(slug=node.slug)
            entries.append(entry.model_copy(update={"slug": node.slug}))
    else:
        entries = list(cfg.categories.include)
    if not entries:
        if only:
            raise ValueError(
                "--only " + ", ".join(only) + ": gecerli kategori bulunamadi"
            )
        raise ValueError(
            "categories.include bos: taranacak kategori yok. "
            "config.toml'a [[categories.include]] ekleyin."
        )

    patterns = list(cfg.categories.exclude) + list(exclude)
    targets: list[tuple[CategoryNode, CategoryEntry]] = []
    seen: set[str] = set()
    excluded: list[str] = []
    for entry in entries:
        node = tree.find(entry.slug)
        if node is None:
            report.warn(f"kategori bulunamadi: {entry.slug}")
            continue
        candidates = [(node, entry)]
        expand = entry.include_children
        if expand is None:
            expand = cfg.categories.include_children
        if expand:
            for child in tree.descendants(node):
                candidates.append(
                    (
                        child,
                        entry.model_copy(
                            update={
                                "slug": child.slug,
                                "include_children": False,
                            }
                        ),
                    )
                )
        for candidate, candidate_entry in candidates:
            if tree.is_excluded(candidate, patterns):
                excluded.append(candidate.slug)
                continue
            if candidate.slug in seen:
                continue
            seen.add(candidate.slug)
            targets.append((candidate, candidate_entry))
    if excluded:
        report.set("excluded_categories", sorted(set(excluded)))
    report.set("target_categories", [t[0].slug for t in targets])
    return targets


def _allowed_explicit_categories(
    targets: list[tuple[CategoryNode, CategoryEntry]],
    cfg: Config,
    only: list[str],
) -> set[str] | None:
    """--only kosusunda acik urunleri hedef kategorilerle sinirla."""
    if not only:
        return None
    allowed: set[str] = set()
    broad = False
    for node, entry in targets:
        category = _app_category(node, entry, cfg.categories.aliases)
        if category:
            allowed.add(category)
        elif node.level == 1:
            broad = True
    if broad:
        return None
    return allowed


def _explicit_scope_allowed(
    product: ExplicitProduct,
    record: dict[str, object] | None,
    allowed: set[str],
    forced: set[str],
    tree: CategoryTree | None,
    aliases: dict[str, str],
) -> bool:
    if product.url in forced:
        return True
    data = record or {}
    category = (
        product.app_category
        or clean(str(data.get("app_category") or ""))
        or clean(str(data.get("category_lv2") or ""))
    )
    if category:
        return _alias(category, aliases) in allowed
    if tree is not None:
        slug = urlparse(product.url).path.strip("/").split("/")[0]
        node = tree.find(slug, warn=False)
        if node is not None and node.lv2() is not None:
            return _alias(node.lv2().name, aliases) in allowed
    # Kategori kosusunda URL'nin ilk segmenti cozulemiyorsa (marka sayfasi
    # gibi) toplu fetch yapma; kullanici --refresh-explicit ile zorlayabilir.
    return False


def _explicit_rows(
    cfg: Config,
    cache: dict[str, dict[str, object]],
    scraped_at: str,
    report: Report,
    allowed_categories: set[str] | None = None,
    forced_urls: set[str] | None = None,
    products: list[ExplicitProduct] | None = None,
    tree: CategoryTree | None = None,
    exclude_patterns: list[str] | None = None,
) -> list[ProductRow]:
    rows: list[ProductRow] = []
    skipped_out_of_scope = 0
    blocked_rows = 0
    forced = forced_urls or set()
    patterns = exclude_patterns or []
    items = products if products is not None else cfg.products.include
    for product in items:
        if is_blog_url(product.url):
            report.warn(
                f"blog URL'si fiyat kaynagi degil, atlandi: {product.url}"
            )
            continue
        record = cache.get(product.url)
        if record is None and not (product.name or product.app_category):
            report.warn(
                f"acik urun cache yok ve config'te name/app_category yok: {product.url}"
            )
            report.set("explicit_missing_cache", True)
            continue
        record = record or {}
        name = product.name or clean(str(record.get("name") or ""))
        if not name:
            report.warn(f"acik urun adi yok: {product.url}")
            continue
        category = _alias(
            product.app_category
            or clean(str(record.get("app_category") or ""))
            or clean(str(record.get("category_lv2") or "")),
            cfg.categories.aliases,
        )
        if product.url not in forced and _explicit_blocked(
            product, record, tree, patterns
        ):
            blocked_rows += 1
            continue
        if (
            product.url not in forced
            and allowed_categories is not None
            and (not category or category not in allowed_categories)
        ):
            skipped_out_of_scope += 1
            continue
        price = (
            product.price
            if product.price is not None
            else price_from_value(record.get("price"))
        )
        discounted = (
            product.discounted_price
            if product.discounted_price is not None
            else price_from_value(record.get("discounted_price"))
        )
        try:
            rows.append(
                ProductRow(
                    name=name,
                    product_id=clean(
                        str(
                            product.product_id
                            or record.get("product_id")
                            or record.get("code")
                            or ""
                        )
                    ),
                    category=category,
                    price=price,
                    discounted_price=discounted,
                    kind="explicit",
                    code=clean(str(record.get("code") or "")),
                    title=clean(str(record.get("title") or "")),
                    url=product.url,
                    category_path=clean(str(record.get("category_path") or "")),
                    source="explicit",
                    scraped_at=scraped_at,
                )
            )
        except ValidationError:
            report.warn(f"gecersiz acik urun satiri: {product.url}")
    if skipped_out_of_scope:
        report.set("explicit_skipped_out_of_scope", skipped_out_of_scope)
    if blocked_rows:
        report.set("explicit_blocked_rows", blocked_rows)
    return rows


def _merge_rows(
    rows: list[ProductRow],
) -> tuple[list[ProductRow], dict[str, list[str]], dict[str, list[str]]]:
    by_name: dict[str, list[ProductRow]] = {}
    by_id: dict[str, ProductRow] = {}
    sources: dict[str, list[str]] = {}
    conflicts: dict[str, list[str]] = {}
    for row in rows:
        sources.setdefault(row.name, [])
        if row.url and row.url not in sources[row.name]:
            sources[row.name].append(row.url)
        bucket = by_name.setdefault(row.name, [])
        existing = by_id.get(row.product_id) if row.product_id else None
        if existing is None:
            existing = next(
                (
                    candidate
                    for candidate in bucket
                    if not (
                        candidate.product_id
                        and row.product_id
                        and candidate.product_id != row.product_id
                    )
                ),
                None,
            )
        if existing is None:
            bucket.append(row)
            if row.product_id:
                by_id[row.product_id] = row
            continue
        if (
            existing.category
            and row.category
            and existing.category != row.category
        ):
            conflicts[existing.name] = [existing.category, row.category]
        if row.kind == "explicit" and existing.kind != "explicit":
            existing.kind = "explicit"
        existing.category = existing.category or row.category
        existing.category_path = existing.category_path or row.category_path
        existing.price = existing.price if existing.price is not None else row.price
        existing.discounted_price = (
            existing.discounted_price
            if existing.discounted_price is not None
            else row.discounted_price
        )
        existing.product_id = existing.product_id or row.product_id
        existing.code = existing.code or row.code
        existing.title = existing.title or row.title
        existing.url = existing.url or row.url
        if row.kind == "explicit" and row.price is not None:
            existing.price = row.price
        if row.kind == "explicit" and row.discounted_price is not None:
            existing.discounted_price = row.discounted_price
        if row.kind == "explicit" and row.category:
            existing.category = row.category
            existing.category_path = row.category_path or existing.category_path
        existing.source = existing.source or row.source
        if existing.product_id:
            by_id[existing.product_id] = existing
    return [row for bucket in by_name.values() for row in bucket], sources, conflicts


def merge_product_rows(rows: list[ProductRow]) -> list[ProductRow]:
    """Ayni adli satirlari tekillestirir (garanti + kategori + explicit)."""
    merged, _sources, _conflicts = _merge_rows(rows)
    merged.sort(key=lambda row: row.name.lower())
    return merged


async def scrape_prices(
    http: Http,
    cfg: Config,
    report: Report,
    scraped_at: str,
    out_dir: Path,
    only: list[str] | None = None,
    exclude: list[str] | None = None,
    report_missing: bool = False,
    refresh_explicit: bool = False,
    cache_path: Path | None = None,
    progress: Progress | None = None,
) -> list[ProductRow]:
    only_tokens = list(only or [])
    category_tokens, product_urls = _split_only(only_tokens)
    if (
        not category_tokens
        and not product_urls
        and any(is_blog_url(token) for token in only_tokens)
    ):
        raise ValueError(
            "blog/... fiyat kaynagi degil; kategori veya urun URL'si verin"
        )
    run_cfg = cfg
    forced_urls: set[str] = set()
    extras: list[ExplicitProduct] = []
    configured_urls = {product.url for product in cfg.products.include}
    for token in product_urls:
        try:
            product = ExplicitProduct(url=token)
        except ValidationError as exc:
            report.warn(f"gecersiz urun URL: {token}: {exc}")
            continue
        forced_urls.add(product.url)
        if product.url not in configured_urls:
            extras.append(product)
    if product_urls and not forced_urls:
        raise ValueError(
            "gecerli urun URL bulunamadi: " + ", ".join(product_urls)
        )
    if extras:
        run_cfg = cfg.model_copy(deep=True)
        run_cfg.products.include = list(cfg.products.include) + extras

    product_only = bool(only_tokens) and not category_tokens
    tree: CategoryTree | None = None
    if product_only:
        # Sadece urun URL'si verildi: nav agacina ihtiyac yok.
        targets = []
    else:
        tree = await fetch_category_tree(
            http,
            cache_path=cache_path or Path(run_cfg.cache.categories_file),
        )
        report.set("category_tree_nodes", len(tree.nodes))
        if category_tokens or not only_tokens:
            try:
                targets = _targets(
                    tree, run_cfg, category_tokens, exclude or [], report
                )
            except ValueError:
                if not forced_urls:
                    raise
                report.warn(
                    "kategori bulunamadi; yalnizca acik urunler islenecek"
                )
                targets = []
        else:
            targets = []
    if not targets and not run_cfg.products.include:
        report.warn("taranacak kategori/urun yok")
        return []

    if progress is not None and targets:
        progress.start("kategoriler", len(targets))
    patterns = list(cfg.categories.exclude) + list(exclude or [])
    assigned: dict[str, dict[str, object]] = {}
    per_cat: dict[str, int] = {}
    coverage: dict[str, dict[str, int]] = {}
    excluded_products = 0
    out_of_scope = 0
    url_conflicts: dict[str, list[str]] = {}

    for node, entry in targets:
        try:
            result = await crawl_listing(
                http, node.slug, cfg.http.max_pages, progress=progress
            )
        except AbortRun:
            break
        except Exception as exc:  # noqa: BLE001
            report.warn(f"{node.slug}: {exc!r}")
            continue
        per_cat[node.slug] = len(result.cards)
        log.info("%s: %d products", node.slug, len(result.cards))
        if progress is not None:
            progress.advance(
                products=len(result.cards), detail=node.slug
            )
        if result.reported_total is not None:
            coverage[node.slug] = {
                "cards": len(result.cards),
                "reported": result.reported_total,
            }
            if (
                result.reported_total
                and len(result.cards) < result.reported_total * 0.9
            ):
                report.warn(
                    f"{node.slug}: sayfa {result.reported_total} urun diyor, "
                    f"{len(result.cards)} kart parse edildi"
                )
        for url, card in result.cards.items():
            resolved = _resolve_node(tree, card, result.crumbs, node)
            if not _related(resolved, node):
                out_of_scope += 1
                continue
            if tree.is_excluded(resolved, patterns):
                excluded_products += 1
                continue
            category = _app_category(resolved, entry, cfg.categories.aliases)
            category_path = (
                resolved.path_names() if resolved is not None else node.path_names()
            )
            current = assigned.get(url)
            if current is None:
                assigned[url] = {
                    "card": card,
                    "category": category,
                    "category_path": category_path,
                    "node": resolved,
                    "source": node.slug,
                }
                continue
            current_card = current.get("card")
            if isinstance(current_card, Card):
                if current_card.price is None and card.price is not None:
                    current_card.price = card.price
                if (
                    current_card.discounted is None
                    and card.discounted is not None
                ):
                    current_card.discounted = card.discounted
            if not current.get("category") and category:
                current["category"] = category
                current["category_path"] = category_path
                current["node"] = resolved
            elif current.get("category") and category and current["category"] != category:
                url_conflicts[url] = [str(current.get("category")), category]

    report.set("categories", per_cat)
    report.set("category_coverage", coverage)
    report.set("excluded_products", excluded_products)
    report.set("out_of_scope_products", out_of_scope)

    rows: list[ProductRow] = []
    unresolved: list[str] = []
    invalid = 0
    for url, data in assigned.items():
        card = data.get("card")
        if not isinstance(card, Card):
            continue
        category = data.get("category")
        category_str = str(category) if category else None
        try:
            rows.append(
                ProductRow(
                    name=card.name or card.title,
                    product_id=card.product_id or card.code,
                    category=category_str,
                    price=card.price,
                    discounted_price=card.discounted,
                    code=card.code,
                    title=card.title,
                    url=url,
                    category_path=str(data.get("category_path") or ""),
                    source=str(data.get("source") or ""),
                    scraped_at=scraped_at,
                )
            )
        except ValidationError:
            invalid += 1
            log.warning("gecersiz satir atlandi: %s", url)
        if not category_str:
            unresolved.append(url)

    cache = _read_explicit_cache(Path(run_cfg.cache.explicit_file), report)
    allowed_categories = _allowed_explicit_categories(
        targets, run_cfg, only_tokens
    )
    blocked_count = sum(
        1
        for product in run_cfg.products.include
        if product.url not in forced_urls
        and _explicit_blocked(
            product, cache.get(product.url), tree, patterns
        )
    )
    if blocked_count:
        report.set("explicit_blocked", blocked_count)
    if product_only:
        explicit_products = [
            product
            for product in run_cfg.products.include
            if product.url in forced_urls
        ]
    elif allowed_categories is None:
        explicit_products = [
            product
            for product in run_cfg.products.include
            if product.url in forced_urls
            or not _explicit_blocked(
                product, cache.get(product.url), tree, patterns
            )
        ]
    else:
        explicit_products = [
            product
            for product in run_cfg.products.include
            if product.url in forced_urls
            or (
                _explicit_scope_allowed(
                    product,
                    cache.get(product.url),
                    allowed_categories,
                    forced_urls,
                    tree,
                    run_cfg.categories.aliases,
                )
                and not _explicit_blocked(
                    product, cache.get(product.url), tree, patterns
                )
            )
        ]
    if not product_only and allowed_categories is not None:
        skipped_explicit = len(run_cfg.products.include) - len(
            explicit_products
        )
        if skipped_explicit:
            report.set("explicit_skipped_out_of_scope", skipped_explicit)
    missing_list = [
        product
        for product in explicit_products
        if product.url not in cache
    ]
    always_list = [
        product for product in explicit_products if product.fetch == "always"
    ]
    auto_count = len(
        {product.url for product in missing_list + always_list}
    )
    cap = run_cfg.products.max_auto_fetch
    if auto_count > cap and not refresh_explicit:
        report.warn(
            f"{auto_count} acik urun otomatik fetch limitini ({cap}) asiyor; "
            "cache'te olanlar kullanilacak. --only ile daraltin veya "
            "--refresh-explicit kullanin."
        )
        report.set("explicit_auto_fetch_skipped", auto_count)
    elif refresh_explicit or missing_list or always_list:
        if refresh_explicit and auto_count > cap:
            report.warn(
                f"--refresh-explicit ile {auto_count} acik urun cekilecek; "
                "bu buyuk bir istek, siteyi yavaslatmayin."
            )
        cache = await refresh_explicit_products(
            http,
            run_cfg,
            report,
            scraped_at,
            force=refresh_explicit,
            cache=cache,
            products=explicit_products,
            progress=progress,
        )
    explicit = _explicit_rows(
        run_cfg,
        cache,
        scraped_at,
        report,
        allowed_categories=allowed_categories,
        forced_urls=forced_urls,
        products=explicit_products,
        tree=tree,
        exclude_patterns=patterns,
    )
    rows.extend(explicit)
    report.set("explicit_products", len(explicit))
    unresolved.extend(r.url for r in explicit if not r.category)

    ids_by_name: dict[str, set[str]] = {}
    for row in rows:
        if row.product_id:
            ids_by_name.setdefault(row.name, set()).add(row.product_id)
    id_conflicts = {
        name: sorted(ids)
        for name, ids in ids_by_name.items()
        if len(ids) > 1
    }
    if id_conflicts:
        report.set("product_id_conflicts", dict(list(id_conflicts.items())[:50]))
        report.warn(
            f"{len(id_conflicts)} urun adinda birden fazla ID var; "
            "satirlar ID ile ayrilacak, kontrol edin"
        )

    merged, sources, name_conflicts = _merge_rows(rows)
    all_conflicts = {**url_conflicts, **name_conflicts}
    if all_conflicts:
        report.set("category_conflicts", dict(list(all_conflicts.items())[:50]))
    duplicate_names = {
        name: urls for name, urls in sources.items() if len(urls) > 1
    }
    if duplicate_names:
        report.set("duplicate_names", dict(list(duplicate_names.items())[:50]))
        report.warn(
            f"{len(duplicate_names)} urun adi birden fazla URL'de var "
            "(ID varsa ID ile ayrilir; ID yoksa importer son satiri uygular)"
        )
        try:
            duplicate_lines = [
                name + "\t" + "\t".join(urls)
                for name, urls in duplicate_names.items()
            ]
            (out_dir / "duplicates.txt").write_text(
                "\n".join(duplicate_lines), encoding="utf-8"
            )
        except OSError as exc:
            report.warn(f"duplicates.txt yazilamadi: {exc}")

    merged.sort(key=lambda r: r.name.lower())
    priced_rows = [r for r in merged if r.kind != "explicit"]
    empty_price = sum(1 for r in priced_rows if r.price is None)
    explicit_empty = sum(1 for r in merged if r.kind == "explicit" and r.price is None)
    missing_ids = [
        row
        for row in merged
        if row.kind != "warranty" and not row.product_id
    ]
    report.set("missing_product_ids", len(missing_ids))
    if missing_ids:
        report.warn(
            f"{len(missing_ids)} urunda ID bulunamadi; ID'siz satirlar "
            "Bayios'ta karisabilir"
        )
    report.set("products", len(merged))
    report.set("invalid_rows", invalid)
    report.set("empty_price_count", empty_price)
    report.set("explicit_empty_price_count", explicit_empty)
    report.set("category_unresolved_count", len(unresolved))
    if unresolved:
        report.set("category_unresolved", unresolved[:50])
    if priced_rows and empty_price / len(priced_rows) > 0.01:
        report.warn(
            f"bos perakende fiyat orani yuksek: {empty_price}/{len(priced_rows)}"
        )
    if merged and len(unresolved) / len(merged) > 0.01:
        report.warn(
            f"kategori cozulemeyen urun orani yuksek: {len(unresolved)}/{len(merged)}"
        )

    if report_missing and not http.aborted:
        sm_urls = await sitemap_product_urls(http)
        report.set("sitemap_products", len(sm_urls))
        scraped_urls = set(assigned) | {r.url for r in explicit}
        missing = sorted(sm_urls - scraped_urls)
        report.set("missing_count", len(missing))
        if missing:
            try:
                (out_dir / "missing.txt").write_text(
                    "\n".join(missing), encoding="utf-8"
                )
            except OSError as exc:
                report.warn(f"missing.txt yazilamadi: {exc}")
            report.warn(
                f"sitemap'te olup bu kosuda taranmayan {len(missing)} urun "
                "(missing.txt)"
            )
    return merged
