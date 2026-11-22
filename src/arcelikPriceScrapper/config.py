from __future__ import annotations

import logging
import re
import tomllib
from decimal import Decimal
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

from pydantic import BaseModel, Field, ValidationError, field_validator

log = logging.getLogger("scrapper.config")

SLUG_RE = re.compile(r"^[a-z0-9-]+$")
BASE_HOSTS = {"www.arcelik.com.tr", "arcelik.com.tr"}


class HttpCfg(BaseModel):
    concurrency: int = Field(2, ge=1, le=4)
    delay_min: float = 0.5
    delay_max: float = 1.5
    timeout: int = 20
    retries: int = Field(4, ge=1)
    max_pages: int = 200


class OutputCfg(BaseModel):
    format: Literal["json", "excel", "csv", "both"] = "json"
    dir: str = "out"
    warranty_category: str = "Ek Garanti"
    with_scraped_at: bool = False


class CategoryEntry(BaseModel):
    slug: str
    app_category: str | None = None
    include_children: bool | None = None

    @field_validator("slug")
    @classmethod
    def _slug(cls, v: str) -> str:
        v = v.strip()
        if not SLUG_RE.fullmatch(v):
            raise ValueError(f"invalid slug: {v!r}")
        return v

    @field_validator("app_category")
    @classmethod
    def _app_category(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = " ".join(v.split())
        return v or None


class CategoriesCfg(BaseModel):
    include: list[CategoryEntry] = Field(default_factory=list)
    exclude: list[str] = Field(default_factory=list)
    aliases: dict[str, str] = Field(default_factory=dict)
    include_children: bool = False


class ExplicitProduct(BaseModel):
    url: str
    name: str | None = None
    product_id: str | None = None
    app_category: str | None = None
    price: Decimal | None = None
    discounted_price: Decimal | None = None
    specs: bool = True
    fetch: Literal["once", "always"] = "once"
    force: bool = False  # kara listeye ragmen dahil et

    @field_validator("url")
    @classmethod
    def _url(cls, v: str) -> str:
        v = v.strip()
        parsed = urlparse(v)
        if parsed.scheme not in ("http", "https"):
            raise ValueError(f"invalid product url: {v!r}")
        if parsed.netloc not in BASE_HOSTS:
            raise ValueError(f"not an arcelik url: {v!r}")
        path = parsed.path.strip("/")
        if len(path.split("/")) < 2:
            raise ValueError(f"product url must have 2 path segments: {v!r}")
        return f"https://www.arcelik.com.tr/{path}"

    @field_validator("name", "app_category", "product_id")
    @classmethod
    def _text(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = " ".join(v.split())
        return v or None


class ProductsCfg(BaseModel):
    include: list[ExplicitProduct] = Field(default_factory=list)
    include_file: str | None = None
    default_specs: bool = True
    default_fetch: Literal["once", "always"] = "once"
    max_auto_fetch: int = Field(50, ge=0)


class CacheCfg(BaseModel):
    categories_file: str = "data/categories.json"
    explicit_file: str = "data/explicit_products.json"
    specs_file: str = "data/specs_cache.json"


class CampaignsCfg(BaseModel):
    enabled: bool = True


class WarrantiesCfg(BaseModel):
    enabled: bool = True


class Config(BaseModel):
    http: HttpCfg = Field(default_factory=HttpCfg)
    output: OutputCfg = Field(default_factory=OutputCfg)
    categories: CategoriesCfg = Field(default_factory=CategoriesCfg)
    products: ProductsCfg = Field(default_factory=ProductsCfg)
    cache: CacheCfg = Field(default_factory=CacheCfg)
    campaigns: CampaignsCfg = Field(default_factory=CampaignsCfg)
    warranties: WarrantiesCfg = Field(default_factory=WarrantiesCfg)


def _load_product_url_file(cfg: Config, config_path: Path) -> None:
    name = cfg.products.include_file
    if not name:
        return
    file_path = Path(name)
    if not file_path.is_absolute():
        file_path = config_path.parent / file_path
    if not file_path.exists():
        log.warning("products.include_file bulunamadi: %s", file_path)
        return
    seen = {product.url for product in cfg.products.include}
    added = 0
    for raw in file_path.read_text(encoding="utf-8-sig").splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        try:
            product = ExplicitProduct(
                url=line,
                specs=cfg.products.default_specs,
                fetch=cfg.products.default_fetch,
            )
        except ValidationError as exc:
            log.warning("gecersiz urun URL %s: %s", line, exc)
            continue
        if product.url in seen:
            continue
        seen.add(product.url)
        cfg.products.include.append(product)
        added += 1
    if added > 100:
        log.warning(
            "products.include_file: %d URL; buyuk liste, kategori kosusunda "
            "filtre uygulanir (max_auto_fetch=%d)",
            added,
            cfg.products.max_auto_fetch,
        )
    log.info("products.include_file: %d URL eklendi (%s)", added, file_path)


def load_config(path: str | Path) -> Config:
    p = Path(path)
    if not p.exists():
        return Config()
    cfg = Config.model_validate(tomllib.loads(p.read_text(encoding="utf-8")))
    _load_product_url_file(cfg, p)
    return cfg


def parse_list(value: str | None) -> list[str]:
    """Virgullu kullanici girdisini listeye cevirir (slug/ad/glob)."""
    if not value:
        return []
    out: list[str] = []
    for item in value.split(","):
        item = item.strip()
        if item:
            out.append(item)
    return out


def parse_slug_list(value: str | None) -> list[str]:
    """Geriye uyumluluk icin: yalnizca slug dogrular."""
    slugs = parse_list(value)
    for slug in slugs:
        if not SLUG_RE.fullmatch(slug):
            raise SystemExit(f"invalid slug: {slug!r}")
    return slugs
