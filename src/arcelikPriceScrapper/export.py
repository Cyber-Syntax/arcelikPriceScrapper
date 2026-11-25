from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any

from openpyxl import Workbook
from openpyxl.styles import Font

from .models import ProductRow
from .report import Report

# Bayios Excel sablonu: 10 sutun (Urun ID dahil), scraped_at yok.
PRODUCT_HEADERS = [
    "Ürün ID",
    "Ürün Adı",
    "Kategori",
    "Perakende Fiyat",
    "Oliz İndirimli Fiyat",
    "Fiziksel Stok",
    "Alış Fiyatı",
    "Kredi Kartı Taban Fiyatı",
    "Nakit Taban Fiyatı",
    "Aktif Kampanya",
    "Ürün Özellikleri (JSON)",
]
FULL_HEADERS = [
    "Ürün ID",
    "Ürün Adı",
    "Kategori",
    "Perakende Fiyat",
    "Oliz İndirimli Fiyat",
    "kind",
    "code",
    "title",
    "url",
    "category_path",
    "source",
    "scraped_at",
]
CATEGORY_HEADERS = [
    "level",
    "path",
    "name",
    "slug",
    "url",
    "in_config",
    "excluded",
    "product_count",
]
META_HEADERS = ["key", "value"]


@dataclass
class Table:
    slug: str  # csv dosya eki
    sheet: str  # excel sheet adi
    headers: list[str]
    rows: list[list[Any]]
    money_cols: tuple[int, ...] = ()


def details_json(row: ProductRow) -> str:
    return json.dumps(
        {
            "features": row.features,
            "specifications": row.specifications,
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )


def catalog_payload(rows: list[ProductRow], scraped_at: str) -> dict[str, Any]:
    products: list[dict[str, Any]] = []
    for row in rows:
        products.append(
            {
                "id": row.product_id,
                "product_name": row.name,
                "category": row.category,
                "price": float(row.price) if row.price is not None else None,
                "discounted_price": (
                    float(row.discounted_price)
                    if row.discounted_price is not None
                    else None
                ),
                "currency": "TRY",
                "source_url": row.url,
                "features": row.features,
                "specifications": row.specifications,
                "kind": row.kind,
                "scraped_at": row.scraped_at or scraped_at,
            }
        )
    return {
        "schema_version": "1.0",
        "scraped_at": scraped_at,
        "products": products,
    }


def write_campaigns_json(
    out_dir: Path,
    campaigns: list[dict[str, Any]],
    scraped_at: str,
    stamp: str,
) -> Path:
    target = out_dir / "kampanyalar"
    target.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(
        {
            "schema_version": "1.0",
            "scraped_at": scraped_at,
            "campaigns": campaigns,
        },
        ensure_ascii=False,
        indent=2,
    )
    (target / "campaigns.json").write_text(payload, encoding="utf-8")
    path = target / f"kampanyalar_{stamp}.json"
    path.write_text(payload, encoding="utf-8")
    return path


def write_catalog(
    out_dir: Path,
    rows: list[ProductRow],
    scraped_at: str,
    stamp: str | None = None,
) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(
        catalog_payload(rows, scraped_at),
        ensure_ascii=False,
        indent=2,
    )
    latest = out_dir / "catalog.json"
    latest.write_text(payload, encoding="utf-8")
    if not stamp:
        return latest
    path = out_dir / f"catalog_{stamp}.json"
    path.write_text(payload, encoding="utf-8")
    return path


def _meta_value(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, int | float | bool) or value is None:
        return "" if value is None else str(value)
    return json.dumps(value, ensure_ascii=False, default=str)


def products_tables(
    rows: list[ProductRow],
    full: bool,
    with_scraped_at: bool = False,
) -> list[Table]:
    headers = PRODUCT_HEADERS + (["scraped_at"] if with_scraped_at else [])
    main_rows: list[list[Any]] = []
    for r in rows:
        row: list[Any] = [
            r.product_id,
            r.name,
            r.category,
            r.price,
            r.discounted_price,
            None,
            None,
            None,
            None,
            None,
            details_json(r),
        ]
        if with_scraped_at:
            row.append(r.scraped_at)
        main_rows.append(row)
    tables = [
        Table(
            "products",
            "Ürünler",
            headers,
            main_rows,
            money_cols=(3, 4),
        )
    ]
    if full:
        tables.append(
            Table(
                "products_full",
                "Ürünler (full)",
                FULL_HEADERS,
                [
                    [
                        r.product_id,
                        r.name,
                        r.category,
                        r.price,
                        r.discounted_price,
                        r.kind,
                        r.code,
                        r.title,
                        r.url,
                        r.category_path,
                        r.source,
                        r.scraped_at,
                    ]
                    for r in rows
                ],
                money_cols=(3, 4),
            )
        )
    return tables


def categories_table(rows: list[list[Any]]) -> Table:
    return Table("categories", "Kategoriler", CATEGORY_HEADERS, rows)


def meta_table(report: Report) -> Table:
    return Table(
        "meta",
        "Meta",
        META_HEADERS,
        [[key, _meta_value(value)] for key, value in sorted(report.data.items())],
    )


def _csv_val(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, Decimal):
        return f"{v:.2f}"
    return str(v)


def _xl_val(v: Any) -> Any:
    if isinstance(v, Decimal):
        return float(v)
    return v


def _write_csv(tables: list[Table], out_dir: Path, base: str) -> list[Path]:
    paths: list[Path] = []
    for t in tables:
        p = out_dir / f"{base}_{t.slug}.csv"
        with open(p, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f)
            w.writerow(t.headers)
            for row in t.rows:
                w.writerow([_csv_val(v) for v in row])
        paths.append(p)
    return paths


def _write_excel(tables: list[Table], out_dir: Path, base: str) -> Path:
    wb = Workbook()
    for i, t in enumerate(tables):
        ws = wb.active if i == 0 else wb.create_sheet()
        ws.title = t.sheet[:31]
        ws.append(t.headers)
        for row in t.rows:
            ws.append([_xl_val(v) for v in row])
        for cell in ws[1]:
            cell.font = Font(bold=True)
        ws.freeze_panes = "A2"
        for row in ws.iter_rows(min_row=2):
            for idx in t.money_cols:
                if idx < len(row):
                    row[idx].number_format = "#,##0.00"
        for col_idx, header in enumerate(t.headers):
            width = len(str(header))
            for row in t.rows[:500]:
                if col_idx < len(row) and row[col_idx] is not None:
                    width = max(width, len(str(row[col_idx])))
            ws.column_dimensions[
                ws.cell(row=1, column=col_idx + 1).column_letter
            ].width = min(width + 2, 60)
    p = out_dir / f"{base}.xlsx"
    wb.save(p)
    return p


def write_tables(
    tables: list[Table],
    out_dir: Path,
    fmt: str,
    stamp: str,
    partial: bool,
    prefix: str = "urunler",
) -> list[Path]:
    if fmt not in ("excel", "csv", "both"):
        raise ValueError(f"gecersiz format: {fmt}")
    out_dir.mkdir(parents=True, exist_ok=True)
    base = f"{prefix}_{stamp}" + (".partial" if partial else "")
    paths: list[Path] = []
    if fmt in ("csv", "both"):
        paths += _write_csv(tables, out_dir, base)
    if fmt in ("excel", "both"):
        paths.append(_write_excel(tables, out_dir, base))
    return paths
