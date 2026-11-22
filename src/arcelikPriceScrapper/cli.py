from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse

from .campaigns import scrape_campaigns
from .categories import (
    fetch_category_tree,
    sitemap_category_urls,
    write_category_files,
)
from .config import Config, load_config, parse_list
from .export import (
    Table,
    categories_table,
    meta_table,
    products_tables,
    write_campaigns_json,
    write_catalog,
    write_tables,
)
from .http import AbortRun, Http
from .models import ProductRow
from .prices import listing_total, merge_product_rows, scrape_prices
from .progress import Progress, default_enabled
from .report import Report
from .specs import enrich_specs
from .warranties import scrape_warranties

log = logging.getLogger("scrapper")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="arcelikPriceScrapper", description="Arcelik scraper")
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--config", default="config.toml")
    common.add_argument(
        "--format", choices=["json", "excel", "csv", "both"]
    )
    common.add_argument("--out-dir")
    common.add_argument("--full", action="store_true", help="products_full tablosu da yaz")
    common.add_argument(
        "--with-scraped-at",
        action="store_true",
        help="ana products sayfasina 12. sutun olarak scraped_at ekle",
    )
    common.add_argument(
        "--progress",
        action="store_true",
        help="TTY olmasa da progress bar goster",
    )
    common.add_argument(
        "--no-progress",
        action="store_true",
        help="progress bar kapat",
    )
    common.add_argument("-v", "--verbose", action="store_true")

    sub = p.add_subparsers(dest="command", required=True)
    for name in ("prices", "all"):
        sp = sub.add_parser(name, parents=[common])
        sp.add_argument(
            "--only",
            help="virgullu kategori slug/ad veya urun URL listesi",
        )
        sp.add_argument("--exclude", help="virgullu kategori slug/ad/glob listesi")
        sp.add_argument(
            "--report-missing",
            action="store_true",
            help="sitemap ile karsilastirip missing.txt yaz",
        )
        sp.add_argument(
            "--refresh-explicit",
            action="store_true",
            help="acik urun PDP'lerini yenile ve cache'i guncelle",
        )
        sp.add_argument(
            "--refresh-specs",
            action="store_true",
            help="specs cache'ini yenile",
        )
    specs = sub.add_parser("specs", parents=[common])
    specs.add_argument("--only", help="virgullu kategori slug/ad veya urun URL listesi")
    specs.add_argument("--exclude", help="virgullu kategori slug/ad/glob listesi")
    specs.add_argument(
        "--refresh-specs",
        action="store_true",
        help="specs cache'ini yenile",
    )
    sub.add_parser("campaigns", parents=[common])
    lc = sub.add_parser("list-categories", parents=[common])
    lc.add_argument("--all", action="store_true", help="CATEGORY sitemap farkini da listele")
    lc.add_argument(
        "--with-counts",
        action="store_true",
        help="her kategori icin ilk sayfadan urun sayisini oku (yavas)",
    )
    return p


async def list_categories(
    http: Http,
    cfg: Config,
    fmt: str | None,
    out_dir: Path,
    stamp: str,
    show_all: bool,
    with_counts: bool,
    progress: Progress | None = None,
) -> list[Path]:
    tree = await fetch_category_tree(
        http, cache_path=Path(cfg.cache.categories_file)
    )
    include_slugs = {e.slug for e in cfg.categories.include}
    excluded = cfg.categories.exclude
    rows: list[list[object]] = []
    if with_counts and progress is not None:
        progress.start("kategoriler", len(tree.nodes))
    for node in tree.nodes:
        count: int | None = None
        if with_counts and progress is not None:
            progress.set_detail(node.slug)
        if with_counts and not http.aborted:
            html = await http.get(node.url)
            if html:
                count = listing_total(html)
        if with_counts and progress is not None:
            progress.advance()
        rows.append(
            [
                node.level,
                node.path_names(),
                node.name,
                node.slug,
                node.url,
                "x" if node.slug in include_slugs else "",
                "x" if tree.is_excluded(node, excluded) else "",
                count,
            ]
        )
    if show_all and not http.aborted:
        sitemap = await sitemap_category_urls(http)
        nav_slugs = {n.slug for n in tree.nodes}
        for url in sorted(sitemap):
            slug = urlparse(url).path.strip("/")
            if not slug or slug in nav_slugs:
                continue
            rows.append(["", "", "", slug, url, "", "", None])
    lv1 = sum(1 for r in rows if r[0] == 1)
    lv2 = sum(1 for r in rows if r[0] == 2)
    lv3 = sum(1 for r in rows if r[0] == 3)
    print(f"{lv1} LV1, {lv2} LV2, {lv3} LV3; toplam {len(rows)} kategori")
    print(f"config include: {len(include_slugs)}; kara liste: {len(excluded)}")
    app_categories = {
        entry.slug: entry.app_category for entry in cfg.categories.include
    }
    written = write_category_files(
        tree,
        out_dir,
        include_slugs,
        app_categories,
        excluded,
        rows,
        stamp,
    )
    if fmt and fmt != "json":
        written += write_tables(
            [categories_table(rows)],
            out_dir,
            fmt,
            stamp,
            partial=False,
            prefix="kategoriler",
        )
    return written


async def amain(args: argparse.Namespace, cfg: Config, report: Report) -> int:
    started = datetime.now(UTC).replace(microsecond=0)
    scraped_at = started.strftime("%Y-%m-%dT%H:%M:%SZ")
    stamp = started.strftime("%Y%m%d-%H%M%S")
    fmt = args.format or cfg.output.format
    out_dir = Path(args.out_dir or cfg.output.dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    progress = Progress(
        default_enabled(
            force=bool(getattr(args, "progress", False)),
            no_progress=bool(getattr(args, "no_progress", False)),
        )
    )
    cmd = args.command
    with_scraped_at = bool(args.with_scraped_at or cfg.output.with_scraped_at)

    products: list[ProductRow] = []
    campaign_tables: list[Table] = []
    campaigns_payload: list[dict[str, object]] = []
    code = 0
    try:
        async with Http(cfg.http, report) as http:
            try:
                await http.load_robots()
                if cmd == "list-categories":
                    for path in await list_categories(
                        http,
                        cfg,
                        args.format,
                        out_dir,
                        stamp,
                        show_all=bool(args.all),
                        with_counts=bool(args.with_counts),
                        progress=progress,
                    ):
                        print(f"yazildi: {path}")
                    return 0
                if cmd in ("prices", "all", "specs"):
                    products += await scrape_prices(
                        http,
                        cfg,
                        report,
                        scraped_at,
                        out_dir,
                        only=parse_list(getattr(args, "only", None)),
                        exclude=parse_list(getattr(args, "exclude", None)),
                        report_missing=bool(
                            getattr(args, "report_missing", False)
                        ),
                        refresh_explicit=bool(
                            getattr(args, "refresh_explicit", False)
                        ),
                        progress=progress,
                    )
                    if cmd in ("prices", "all") and cfg.warranties.enabled:
                        warranty_rows = await scrape_warranties(
                            http,
                            cfg.output.warranty_category,
                            scraped_at,
                            report,
                        )
                        products = merge_product_rows(products + warranty_rows)
                    if products:
                        products = await enrich_specs(
                            http,
                            products,
                            cfg,
                            report,
                            scraped_at,
                            refresh=bool(
                                getattr(args, "refresh_specs", False)
                            ),
                            progress=progress,
                        )
                if cmd in ("campaigns", "all") and cfg.campaigns.enabled:
                    campaign_result = await scrape_campaigns(
                        http, report, scraped_at, progress=progress
                    )
                    campaign_tables = campaign_result.tables
                    campaigns_payload = campaign_result.campaigns
                elif cmd == "campaigns":
                    report.warn("kampanyalar config'te kapali")
                if products:
                    report.set("products", len(products))
            except AbortRun as e:
                log.error("DURDURULDU: %s", e)

            partial = http.aborted is not None
            report.set("abort_reason", http.aborted)
            report.set("http_status", dict(http.status))
            code = 2 if partial else 0
            report.mark_finished(code)
            if cmd in ("prices", "all", "specs"):
                catalog = write_catalog(
                    out_dir, products, scraped_at, stamp
                )
                print(f"yazildi: {catalog}")
            if cmd in ("campaigns", "all") and cfg.campaigns.enabled:
                campaign_json = write_campaigns_json(
                    out_dir,
                    campaigns_payload,
                    scraped_at,
                    stamp,
                )
                print(f"yazildi: {campaign_json}")
            tables: list[Table] = []
            if products:
                tables += products_tables(products, args.full, with_scraped_at)
            tables += campaign_tables
            if fmt != "json":
                tables.append(meta_table(report))
                if not products and not campaign_tables:
                    log.warning(
                        "yazilacak urun/kampanya verisi yok; yalnizca meta yazilacak"
                    )
                for path in write_tables(tables, out_dir, fmt, stamp, partial):
                    print(f"yazildi: {path}")
        return code
    except ValueError as e:
        log.error("HATA: %s", e)
        report.set("abort_reason", f"selection: {e}")
        code = 1
        return code
    except Exception as e:  # noqa: BLE001
        log.exception("beklenmeyen hata")
        report.set("abort_reason", f"unexpected: {e!r}")
        code = 1
        return code
    finally:
        progress.close()
        if cmd != "list-categories":
            report.finish(out_dir / "run_report.json", code)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        stream=sys.stderr,
    )
    try:
        cfg = load_config(args.config)
    except Exception as e:  # noqa: BLE001
        log.error("config okunamadi: %s", e)
        return 1
    report = Report(args.command)
    try:
        return asyncio.run(amain(args, cfg, report))
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    sys.exit(main())
