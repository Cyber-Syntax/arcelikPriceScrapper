#!/usr/bin/env python3
"""Arcelik price scraper: sitemap -> categories -> listing pages -> cards -> CSV."""

import asyncio
import csv
import random
import re
import sys
from urllib.parse import urljoin, urlparse

from curl_cffi.requests import AsyncSession
from selectolax.lexbor import LexborHTMLParser as HTMLParser

BASE = "https://www.arcelik.com.tr"
SUFFIX = " ürün detaylarını incele"
MAX_PAGES = 200


HEADERS = {"Accept-Language": "tr-TR,tr;q=0.9"}  # no User-Agent here
SEM = asyncio.Semaphore(2)  # keep it low on a bot-protected site


async def get(session, url, retries=4):
    for attempt in range(retries):
        async with SEM:
            await asyncio.sleep(random.uniform(0.5, 1.5))
            try:
                r = await session.get(url)
            except Exception as e:
                print(f"ERR {type(e).__name__} {url[:100]}", file=sys.stderr)
                r = None
        if r is not None:
            if r.status_code == 200:
                return r.text
            print(
                f"HTTP {r.status_code} {url[:100]} (attempt {attempt + 1})",
                file=sys.stderr,
            )
            if r.status_code not in (403, 429) and r.status_code < 500:
                return None
        await asyncio.sleep(2**attempt * 2)
    return None


def money(node):
    if node is None:
        return ""
    t = re.sub(r"\s+", " ", node.text(strip=True).replace("\xa0", " ")).strip()
    return t if re.search(r"\d", t) else ""


def parse_cards(html):
    """-> {product_url: row}"""
    rows = {}
    for card in HTMLParser(html).css("div.prd-inner"):
        a = card.css_first(".prd-detail a[href]") or card.css_first(
            "a.js-prd-url"
        )
        if a is None:
            continue
        url = urljoin(BASE, a.attributes["href"]).split("?")[0]
        label = (
            (a.attributes.get("aria-label") or "").removesuffix(SUFFIX).strip()
        )
        t = card.css_first(".prd-name .t")
        title = t.text(strip=True) if t else ""
        code_node = card.css_first("[data-product-code]")
        rows[url] = {
            "product_name": label or title,
            "price": money(card.css_first(".prd-price > .prc")),
            "discounted_price": money(
                card.css_first(".prd-row-price-third .prc-third")
            ),
            "code": code_node.attributes.get("data-product-code", "")
            if code_node
            else "",
            "title": title,
            "url": url,
        }
    return rows


async def sitemap_product_urls(client):
    idx = await get(client, f"{BASE}/sitemap.xml") or ""
    urls = set()
    for loc in re.findall(r"<loc>\s*(.*?)\s*</loc>", idx):
        if "PRODUCT" in loc:
            xml = await get(client, loc.replace("&amp;", "&")) or ""
            urls |= set(
                re.findall(r"<loc>\s*(https://[^<\s]+?)\s*</loc>", xml)
            )
    return urls


async def crawl_listing(client, slug, found):
    local = set()
    for page in range(MAX_PAGES):
        url = f"{BASE}/{slug}" + (
            f"?page={page}" if page else ""
        )  # ASSUMPTION: verify
        html = await get(client, url)
        if not html:
            break
        cards = parse_cards(html)
        new = set(cards) - local
        if not new:  # empty or repeated page -> done
            break
        local |= new
        found.update(cards)
    print(f"{slug}: {len(local)} products", file=sys.stderr)


async def amain(out: str = "arcelik_prices.csv", full: bool = False):
    found = {}
    async with AsyncSession(
        impersonate="chrome", headers=HEADERS, timeout=20, allow_redirects=True
    ) as client:
        sm_urls = await sitemap_product_urls(client)
        slugs = sorted(
            {
                p[0]
                for u in sm_urls
                if len(p := urlparse(u).path.strip("/").split("/")) == 2
            }
        )
        print(
            f"{len(sm_urls)} sitemap products, {len(slugs)} categories",
            file=sys.stderr,
        )
        await asyncio.gather(*(crawl_listing(client, s, found) for s in slugs))

    missing = sorted(sm_urls - set(found))
    print(
        f"scraped {len(found)}, in sitemap but not scraped: {len(missing)}",
        file=sys.stderr,
    )
    if missing:
        open("missing.txt", "w").write("\n".join(missing))

    cols = ["product_name", "price", "discounted_price"] + (
        ["code", "title", "url"] if full else []
    )
    with open(out, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(sorted(found.values(), key=lambda r: r["product_name"]))


def main():
    full = "--full" in sys.argv
    asyncio.run(amain(full=full))


if __name__ == "__main__":
    main()
