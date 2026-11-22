from __future__ import annotations

import io
import json
from collections import Counter
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from arcelikPriceScrapper.campaigns import BAYIOS_HEADERS, bayios_table
from arcelikPriceScrapper.categories import (
    is_blog_url,
    parse_nav,
    write_category_files,
)
from arcelikPriceScrapper.config import Config, load_config
from arcelikPriceScrapper.export import (
    PRODUCT_HEADERS,
    catalog_payload,
    details_json,
    meta_table,
    products_tables,
    write_campaigns_json,
    write_catalog,
    write_tables,
)
from arcelikPriceScrapper.http import AbortRun
from arcelikPriceScrapper.models import ProductRow
from arcelikPriceScrapper.prices import (
    Card,
    merge_product_rows,
    parse_cards,
    parse_pdp_summary,
    scrape_prices,
)
from arcelikPriceScrapper.progress import Progress, default_enabled
from arcelikPriceScrapper.report import Report
from arcelikPriceScrapper.specs import enrich_specs, parse_spec_details

NAV_HTML = """
<nav id="nav-menu-category"><ul class="ul-clear menu-category">
<li class="lv1-li"><a href="/beyaz-esya">Beyaz Eşya</a><div class="sub"><ul class="ul-clear lv-2">
  <li class="lv2-li"><a href="/buzdolabi">Buzdolabı</a><div class="sublv"><ul class="ul-clear lv-3">
    <li><a href="/no-frost-buzdolabi">No Frost Buzdolabı</a></li>
    <li><a href="/alttan-donduruculu-buzdolabi">Alttan Donduruculu Buzdolabı</a></li>
  </ul></div></li>
  <li class="lv2-li"><a href="/kurutma-makinesi">Kurutma Makinesi</a><div class="sublv"><ul class="ul-clear lv-3">
    <li><a href="/10-kg-kurutma-makinesi">10 Kg Kurutma Makinesi</a></li>
  </ul></div></li>
  <li class="lv2-li"><a href="/derin-dondurucu">Derin Dondurucu</a><div class="sublv"><ul class="ul-clear lv-3">
    <li><a href="/cekmeceli-derin-dondurucu">Çekmeceli Derin Dondurucu</a></li>
  </ul></div></li>
</ul></div></li>
<li class="lv1-li"><a href="/elektronik">Elektronik</a><div class="sub"><ul class="ul-clear lv-2">
  <li class="lv2-li"><a href="/cep-telefonu">Cep Telefonu</a><div class="sublv"><ul class="ul-clear lv-3">
    <li><a href="/android-telefon-modelleri">Android Telefon Modelleri</a></li>
  </ul></div></li>
  <li class="lv2-li"><a href="/bilgisayar">Bilgisayar</a><div class="sublv"><ul class="ul-clear lv-3">
    <li><a href="/tablet">Tablet</a></li>
  </ul></div></li>
</ul></div></li>
<li class="lv1-li"><a href="/ankastre">Ankastre</a><div class="sub"><ul class="ul-clear lv-2">
  <li class="lv2-li"><a href="/ankastre-firin">Ankastre Fırın</a><div class="sublv"><ul class="ul-clear lv-3">
    <li><a href="/buhar-destekli-firin">Buhar Destekli Fırın</a></li>
  </ul></div></li>
</ul></div></li>
<li class="lv1-li"><a href="/kucuk-ev-aletleri">Küçük Ev Aletleri</a><div class="sub"><ul class="ul-clear lv-2">
  <li class="lv2-li"><a href="/kahve-makinesi">Kahve Makinesi</a><div class="sublv"><ul class="ul-clear lv-3">
    <li><a href="/turk-kahve-makinesi">Türk Kahve Makinesi</a></li>
  </ul></div></li>
</ul></div></li>
</ul></nav>
"""


def card_html(
    name: str,
    href: str,
    hierarchy: str,
    price: str,
    discounted: str = "",
    code: str = "1",
) -> str:
    return f"""
    <div class="prd-inner">
      <button data-product-code="{code}" data-product-hierarchy="{hierarchy}"></button>
      <div class="prd-detail"><a href="{href}" aria-label="{name} ürün detaylarını incele">x</a></div>
      <div class="prd-name"><span class="t">{name} Uzun Ad</span></div>
      <div class="prd-price"><span class="prc">{price}</span></div>
      <div class="prd-row-price-third"><span class="prc-third">{discounted}</span></div>
    </div>
    """


def listing_html(crumbs: list[str], cards: list[str], total: int = 1) -> str:
    crumb = "".join(f"<li>{c}</li>" for c in crumbs)
    return (
        f'<ol class="breadcrumb">{crumb}</ol>'
        + "".join(cards)
        + f"<p>{total} ürün</p>"
    )


PDP_URL = "https://www.arcelik.com.tr/10-kg-kurutma-makinesi/1001-kmx-kurutma-makinesi"
PDP_HTML = """
<ol class="breadcrumb">
  <li>Ana Sayfa</li><li>Beyaz Eşya</li><li>Kurutma Makinesi</li>
  <li>10 Kg Kurutma Makinesi</li><li>1001 KMX</li>
</ol>
<h1>1001 KMX<br>10 Kg Kurutma Makinesi</h1>
"""

PDP_WITH_PRICE = """
<ol class="breadcrumb">
  <li>Ana Sayfa</li><li>Ankastre</li><li>Ankastre Fırın</li>
  <li>Buhar Destekli Fırın</li><li>AFC 341 G1</li>
</ol>
<script type="application/ld+json">
{"@type":"Product","name":"AFC 341 G1 Buhar Destekli Fırın","sku":"7768270259",
 "offers":{"price":"33999.00","priceCurrency":"TRY",
 "priceSpecification":[{"@type":"UnitPriceSpecification",
 "priceType":"https://schema.org/ListPrice","price":"35499.00"}]}}
</script>
"""


def pages() -> dict[str, str]:
    return {
        "https://www.arcelik.com.tr/": NAV_HTML,
        "https://www.arcelik.com.tr/buzdolabi": listing_html(
            ["Ana Sayfa", "Beyaz Eşya", "Buzdolabı"],
            [
                card_html(
                    "283616 EI",
                    "/alttan-donduruculu-buzdolabi/283616-ei-buzdolabi",
                    "Beyaz Eşya/Buzdolabı/Alttan Donduruculu Buzdolabı",
                    "104.299 TL",
                    "84.799 TL",
                    "111",
                ),
                card_html(
                    "999999 XX",
                    "/buzdolabi/999999-xx-buzdolabi",
                    "Beyaz Eşya/Buzdolabı/No Frost Buzdolabı",
                    "10.000 TL",
                    "",
                    "222",
                ),
                card_html(
                    "2071 MNFB",
                    "/cekmeceli-derin-dondurucu/2071-mnfb-derin-dondurucu",
                    "Beyaz Eşya/Derin Dondurucu/Çekmeceli Derin Dondurucu",
                    "45.199 TL",
                    "",
                    "888",
                ),
            ],
            total=3,
        ),
        "https://www.arcelik.com.tr/kurutma-makinesi": listing_html(
            ["Ana Sayfa", "Beyaz Eşya", "Kurutma Makinesi"],
            [
                card_html(
                    "1002 KMX",
                    "/10-kg-kurutma-makinesi/1002-kmx-kurutma-makinesi",
                    "Beyaz Eşya/10 Kg Kurutma Makinesi/10 Kg Kurutma Makinesi",
                    "42.399 TL",
                    "37.399 TL",
                    "333",
                )
            ],
        ),
        "https://www.arcelik.com.tr/ankastre-firin": listing_html(
            ["Ana Sayfa", "Ankastre", "Ankastre Fırın"],
            [
                card_html(
                    "AFC 341 G1",
                    "/buhar-destekli-firin/afc-341-g1-ankastre-firin",
                    "Ankastre/Ankastre Fırın/Buhar Destekli Fırın",
                    "35.499 TL",
                    "33.999 TL",
                    "666",
                )
            ],
        ),
        "https://www.arcelik.com.tr/turk-kahve-makinesi": listing_html(
            ["Ana Sayfa", "Küçük Ev Aletleri", "Kahve Makinesi", "Türk Kahve Makinesi"],
            [
                card_html(
                    "TM 100",
                    "/turk-kahve-makinesi/tm-100",
                    "Küçük Ev Aletleri/Kahve Makinesi/Türk Kahve Makinesi",
                    "5.000 TL",
                    "",
                    "777",
                )
            ],
        ),
        "https://www.arcelik.com.tr/cep-telefonu": listing_html(
            ["Ana Sayfa", "Elektronik", "Cep Telefonu"],
            [
                card_html(
                    "Samsung A17",
                    "/samsung-galaxy-a17/samsung-a17-8-256-gb-mavi-cep-telefonu",
                    "Elektronik/Android Telefon Modelleri/TECNO",
                    "17.199 TL",
                    "",
                    "444",
                )
            ],
        ),
        "https://www.arcelik.com.tr/tablet": listing_html(
            ["Ana Sayfa", "Elektronik", "Bilgisayar", "Tablet"],
            [
                card_html(
                    "iPad",
                    "/tablet/ipad",
                    "Elektronik/Bilgisayar/Tablet",
                    "20.000 TL",
                    "",
                    "555",
                )
            ],
        ),
        PDP_URL: PDP_HTML,
    }


class FakeHttp:
    def __init__(self) -> None:
        self.aborted: str | None = None
        self.status: Counter[str] = Counter()
        self.calls: list[str] = []
        self._pages = pages()

    async def get(self, url: str, check_robots: bool = True) -> str | None:
        self.calls.append(url)
        if self.aborted:
            raise AbortRun(self.aborted)
        self.status["200"] += 1
        return self._pages.get(url) or self._pages.get(url.split("?")[0])


def make_config(tmp_path: Path) -> Config:
    cfg = Config.model_validate(
        {
            "categories": {
                "include": [
                    {"slug": "buzdolabi"},
                    {"slug": "kurutma-makinesi"},
                    {"slug": "ankastre-firin"},
                    {
                        "slug": "turk-kahve-makinesi",
                        "app_category": "Türk Kahve Makinesi",
                    },
                ],
                "exclude": ["cep-telefonu", "bilgisayar"],
            },
            "products": {
                "include": [{"url": PDP_URL, "name": "1001 KMX"}]
            },
        }
    )
    cfg.cache.explicit_file = str(tmp_path / "explicit.json")
    return cfg


def test_nav_tree_and_resolution() -> None:
    tree = parse_nav(NAV_HTML)
    assert len(tree.roots) == 4
    assert len(tree.nodes) == 19
    kurutma = tree.resolve_hierarchy(
        "Beyaz Eşya/10 Kg Kurutma Makinesi/10 Kg Kurutma Makinesi"
    )
    assert kurutma is not None
    assert kurutma.name == "10 Kg Kurutma Makinesi"
    assert kurutma.lv2() is not None
    assert kurutma.lv2().name == "Kurutma Makinesi"
    telefon = tree.resolve_hierarchy(
        "Elektronik/Android Telefon Modelleri/TECNO"
    )
    assert telefon is not None
    assert telefon.lv2() is not None
    assert telefon.lv2().name == "Cep Telefonu"
    assert tree.resolve_hierarchy("Ankastre/Ankastre Fırın/Buhar Destekli Fırın").name == "Buhar Destekli Fırın"
    assert tree.is_excluded(tree.find("tablet"), ["bilgisayar"])
    assert tree.is_excluded(tree.find("android-telefon-modelleri"), ["cep-telefonu"])
    assert not tree.is_excluded(tree.find("buzdolabi"), ["bilgisayar"])
    assert tree.is_excluded(tree.find("no-frost-buzdolabi"), ["*buzdolabi"])
    assert tree.is_excluded(tree.find("cep-telefonu"), ["cep-*"])
    assert tree.find("turk-kahve-makinesi").lv2().name == "Kahve Makinesi"


def test_pdp_embedded_json_product_id() -> None:
    html = """
    <h1>P 13 YEB</h1>
    <script>
      var data = {"products": [{"name": "P 13 YEB", "id": "9205971100",
        "price": "", "brand": "ARÇELİK"}]};
    </script>
    """
    summary = parse_pdp_summary(html, "https://www.arcelik.com.tr/a/b")
    assert summary.name == "P 13 YEB"
    assert summary.product_id == "9205971100"


def test_blog_is_not_a_category(tmp_path: Path) -> None:
    blog_nav = NAV_HTML.replace(
        '<li class="lv1-li"><a href="/beyaz-esya">',
        '<li class="lv1-li"><a href="/blog">Blog</a>'
        '<div class="sub"><ul class="ul-clear lv-2">'
        '<li class="lv2-li"><a href="/blog/su-aritma">Su Arıtma Blog</a></li>'
        "</ul></div></li>"
        '<li class="lv1-li"><a href="/beyaz-esya">',
    )
    tree = parse_nav(blog_nav)
    assert tree.find("blog") is None
    assert tree.find("blog/su-aritma") is None
    assert not any("blog" in n.slug for n in tree.nodes)
    assert is_blog_url("https://www.arcelik.com.tr/blog/su-aritma")
    assert not is_blog_url("https://www.arcelik.com.tr/buzdolabi")
    out = tmp_path / "cats"
    write_category_files(tree, out, set(), {}, [], tree.to_rows(), "test")
    toml = (out / "categories.toml").read_text(encoding="utf-8")
    txt = (out / "categories.txt").read_text(encoding="utf-8")
    assert 'slug = "blog' not in toml
    assert "Su Arıtma Blog" not in toml
    assert "blog/" not in txt


async def test_blog_explicit_is_never_fetched(tmp_path: Path) -> None:
    blog = "https://www.arcelik.com.tr/blog/su-aritma"
    cfg = Config.model_validate(
        {
            "categories": {"include": [{"slug": "buzdolabi"}]},
            "products": {
                "include": [{"url": blog, "name": "Blog Urun", "force": True}]
            },
        }
    )
    cfg.cache.explicit_file = str(tmp_path / "explicit.json")
    report = Report("prices")
    http = FakeHttp()
    await scrape_prices(
        http,
        cfg,
        report,
        "2026-11-20T00:00:00Z",
        tmp_path,
        cache_path=tmp_path / "categories.json",
    )
    assert blog not in http.calls
    assert report.data["explicit_blocked"] == 1


async def test_only_blog_url_is_rejected(tmp_path: Path) -> None:
    cfg = make_config(tmp_path)
    blog = "https://www.arcelik.com.tr/blog/su-aritma"
    with pytest.raises(ValueError, match="blog"):
        await scrape_prices(
            FakeHttp(),
            cfg,
            Report("prices"),
            "2026-11-20T00:00:00Z",
            tmp_path,
            only=[blog],
            cache_path=tmp_path / "categories.json",
        )


def test_card_parsing() -> None:
    html = listing_html(
        ["Ana Sayfa", "Beyaz Eşya", "Buzdolabı"],
        [
            card_html(
                "283616 EI",
                "/alttan-donduruculu-buzdolabi/283616-ei-buzdolabi",
                "Beyaz Eşya/Buzdolabı/Alttan Donduruculu Buzdolabı",
                "104.299 TL",
                "84.799 TL",
                "111",
            )
        ],
    )
    cards = parse_cards(html)
    card = cards["https://www.arcelik.com.tr/alttan-donduruculu-buzdolabi/283616-ei-buzdolabi"]
    assert card.name == "283616 EI"
    assert card.title == "283616 EI Uzun Ad"
    assert card.hierarchy.endswith("Alttan Donduruculu Buzdolabı")
    assert card.price == Decimal("104299")
    assert card.discounted == Decimal("84799")
    assert card.code == "111"
    assert card.product_id == "111"


def test_pdp_summary_without_price() -> None:
    summary = parse_pdp_summary(PDP_HTML, PDP_URL)
    assert summary.name == "1001 KMX"
    assert summary.title == "1001 KMX 10 Kg Kurutma Makinesi"
    assert summary.category_lv2 == "Kurutma Makinesi"
    assert summary.category_lv3 == "10 Kg Kurutma Makinesi"
    assert summary.price is None
    assert summary.discounted_price is None


def test_pdp_summary_with_jsonld() -> None:
    summary = parse_pdp_summary(PDP_WITH_PRICE, "https://www.arcelik.com.tr/a/b")
    assert summary.name == "AFC 341 G1"
    assert summary.price == Decimal("35499.00")
    assert summary.discounted_price == Decimal("33999.00")
    assert summary.code == "7768270259"
    assert summary.product_id == "7768270259"


async def test_scrape_prices_m1(tmp_path: Path) -> None:
    cfg = make_config(tmp_path)
    report = Report("prices")
    http = FakeHttp()
    rows = await scrape_prices(
        http,
        cfg,
        report,
        "2026-11-20T00:00:00Z",
        tmp_path,
        refresh_explicit=True,
        cache_path=tmp_path / "categories.json",
    )
    by_name = {r.name: r for r in rows}
    assert set(by_name) == {
        "283616 EI",
        "999999 XX",
        "1002 KMX",
        "AFC 341 G1",
        "TM 100",
        "1001 KMX",
    }
    assert by_name["283616 EI"].category == "Buzdolabı"
    assert by_name["283616 EI"].price == Decimal("104299")
    assert by_name["283616 EI"].product_id == "111"
    assert by_name["1002 KMX"].category == "Kurutma Makinesi"
    assert by_name["AFC 341 G1"].category == "Ankastre Fırın"
    assert by_name["TM 100"].category == "Türk Kahve Makinesi"
    assert by_name["1001 KMX"].category == "Kurutma Makinesi"
    assert by_name["1001 KMX"].price is None
    assert by_name["1001 KMX"].kind == "explicit"
    assert "Samsung A17" not in by_name
    assert "iPad" not in by_name
    assert "2071 MNFB" not in by_name
    assert report.data["out_of_scope_products"] >= 1
    assert report.data["explicit_products"] == 1
    assert report.data["empty_price_count"] == 0
    assert report.data["explicit_empty_price_count"] == 1
    assert (tmp_path / "explicit.json").exists()

    # Ikinci kosu: explicit PDP'ye tekrar istek atilmamali.
    http2 = FakeHttp()
    await scrape_prices(
        http2,
        cfg,
        Report("prices"),
        "2026-11-20T00:00:00Z",
        tmp_path,
        refresh_explicit=False,
        cache_path=tmp_path / "categories.json",
    )
    assert PDP_URL not in http2.calls


async def test_only_scope_skips_unrelated_explicit(tmp_path: Path) -> None:
    cfg = make_config(tmp_path)
    report = Report("prices")
    rows = await scrape_prices(
        FakeHttp(),
        cfg,
        report,
        "2026-11-20T00:00:00Z",
        tmp_path,
        only=["turk-kahve-makinesi"],
        cache_path=tmp_path / "categories.json",
    )
    assert {r.name for r in rows} == {"TM 100"}
    assert report.data.get("explicit_skipped_out_of_scope") == 1


async def test_only_product_url(tmp_path: Path) -> None:
    cfg = make_config(tmp_path)
    report = Report("prices")
    rows = await scrape_prices(
        FakeHttp(),
        cfg,
        report,
        "2026-11-20T00:00:00Z",
        tmp_path,
        only=[PDP_URL],
        cache_path=tmp_path / "categories.json",
    )
    assert [r.name for r in rows] == ["1001 KMX"]
    assert rows[0].category == "Kurutma Makinesi"
    assert rows[0].kind == "explicit"
    assert report.data["explicit_products"] == 1


async def test_explicit_blacklist_blocks_url(tmp_path: Path) -> None:
    cfg = Config.model_validate(
        {
            "categories": {
                "include": [{"slug": "buzdolabi"}],
                "exclude": ["kurutma-makinesi"],
            },
            "products": {
                "include": [{"url": PDP_URL, "name": "1001 KMX"}]
            },
        }
    )
    cfg.cache.explicit_file = str(tmp_path / "explicit.json")
    report = Report("prices")
    http = FakeHttp()
    rows = await scrape_prices(
        http,
        cfg,
        report,
        "2026-11-20T00:00:00Z",
        tmp_path,
        cache_path=tmp_path / "categories.json",
    )
    assert "1001 KMX" not in {r.name for r in rows}
    assert report.data["explicit_blocked"] == 1
    assert PDP_URL not in http.calls


async def test_explicit_force_overrides_blacklist(tmp_path: Path) -> None:
    cfg = Config.model_validate(
        {
            "categories": {
                "include": [{"slug": "buzdolabi"}],
                "exclude": ["kurutma-makinesi"],
            },
            "products": {
                "include": [
                    {"url": PDP_URL, "name": "1001 KMX", "force": True}
                ]
            },
        }
    )
    cfg.cache.explicit_file = str(tmp_path / "explicit.json")
    report = Report("prices")
    rows = await scrape_prices(
        FakeHttp(),
        cfg,
        report,
        "2026-11-20T00:00:00Z",
        tmp_path,
        cache_path=tmp_path / "categories.json",
    )
    assert "1001 KMX" in {r.name for r in rows}
    assert report.data["explicit_products"] == 1


async def test_empty_include_raises(tmp_path: Path) -> None:
    cfg = Config()
    with pytest.raises(ValueError, match="categories.include"):
        await scrape_prices(
            FakeHttp(),
            cfg,
            Report("prices"),
            "2026-11-20T00:00:00Z",
            tmp_path,
            cache_path=tmp_path / "categories.json",
        )


def test_config_explicit_url() -> None:
    cfg = Config.model_validate(
        {
            "products": {
                "include": [
                    {"url": "https://arcelik.com.tr/a/b?x=1", "name": " X "}
                ]
            }
        }
    )
    assert cfg.products.include[0].url == "https://www.arcelik.com.tr/a/b"
    assert cfg.products.include[0].name == "X"
    with pytest.raises(ValidationError):
        Config.model_validate(
            {"products": {"include": [{"url": "https://example.com/a/b"}]}}
        )


def test_config_product_file(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"
    url_file = tmp_path / "urls.txt"
    url_file.write_text(
        "# yorum\n"
        "\n"
        "https://www.arcelik.com.tr/10-kg-kurutma-makinesi/1000-kmx-kurutma-makinesi\n"
        "https://www.arcelik.com.tr/10-kg-kurutma-makinesi/1001-kmx-kurutma-makinesi\n"
        "https://example.com/a/b\n",
        encoding="utf-8",
    )
    config_path.write_text(
        "[products]\n"
        'include_file = "urls.txt"\n'
        "default_specs = false\n"
        'default_fetch = "always"\n'
        "\n"
        "[[products.include]]\n"
        'url = "https://www.arcelik.com.tr/10-kg-kurutma-makinesi/1001-kmx-kurutma-makinesi"\n'
        'name = "1001 KMX"\n',
        encoding="utf-8",
    )
    cfg = load_config(config_path)
    urls = [product.url for product in cfg.products.include]
    assert urls == [
        "https://www.arcelik.com.tr/10-kg-kurutma-makinesi/1001-kmx-kurutma-makinesi",
        "https://www.arcelik.com.tr/10-kg-kurutma-makinesi/1000-kmx-kurutma-makinesi",
    ]
    assert cfg.products.include[0].name == "1001 KMX"
    assert cfg.products.include[0].specs is True
    assert cfg.products.include[1].specs is False
    assert cfg.products.include[1].fetch == "always"


def test_category_files(tmp_path: Path) -> None:
    tree = parse_nav(NAV_HTML)
    rows = tree.to_rows()
    written = write_category_files(
        tree,
        tmp_path,
        {"buzdolabi"},
        {"buzdolabi": "Buzdolabı"},
        ["bilgisayar"],
        rows,
        "20260101-000000",
    )
    names = {path.name for path in written}
    assert names == {"categories.txt", "categories.toml"}
    txt = (tmp_path / "categories.txt").read_text(encoding="utf-8")
    toml = (tmp_path / "categories.toml").read_text(encoding="utf-8")
    assert "url" in txt.splitlines()[1]
    assert "Buzdolabı" in txt
    assert "## [L2] Beyaz Eşya > Buzdolabı [config]" in toml
    assert "## Istediginiz blogu" in toml
    assert "# slug = \"buzdolabi\"" in toml
    assert "# app_category = \"Buzdolabı\"" in toml
    assert "[config]" in toml
    assert "[excluded]" in toml
    assert "include_children = true" in toml


def test_campaign_bayios_table() -> None:
    cards = {
        "u1": Card(
            name="07325 A",
            title="",
            code="",
            url="u1",
            price=None,
            discounted=None,
        ),
        "u2": Card(
            name="09325 A",
            title="",
            code="",
            url="u2",
            price=None,
            discounted=None,
        ),
        "u3": Card(
            name="09325 A",
            title="",
            code="",
            url="u3",
            price=None,
            discounted=None,
        ),
    }
    table = bayios_table(1, "Düğün.com", cards)
    assert table is not None
    assert table.headers == BAYIOS_HEADERS
    assert table.headers == ["Ürün Adı", "İlişki Türü", "Gerekli Adet"]
    assert table.rows == [
        ["07325 A", "İlgili ürün", None],
        ["09325 A", "İlgili ürün", None],
    ]
    assert table.sheet.startswith("Düğün.com")
    assert len(table.sheet) <= 31
    assert bayios_table(2, "Boş", {}) is None


def test_merge_prefers_id_and_keeps_different_ids() -> None:
    def row(name: str, product_id: str, url: str) -> ProductRow:
        return ProductRow(
            name=name,
            product_id=product_id,
            category="Buzdolabı",
            price=Decimal("10"),
            url=url,
            scraped_at="2026-11-20T00:00:00Z",
        )

    merged = merge_product_rows(
        [
            row("A", "1", "u1"),
            row("A", "2", "u2"),
            row("A", "", "u3"),
        ]
    )
    assert len(merged) == 2
    assert {r.product_id for r in merged} == {"1", "2"}

    same = merge_product_rows(
        [row("B", "3", "u1"), row("B", "3", "u2")]
    )
    assert len(same) == 1
    assert same[0].product_id == "3"

    same_id = merge_product_rows([row("A", "4", "u1"), row("B", "4", "u2")])
    assert len(same_id) == 1
    assert same_id[0].product_id == "4"

    warranty = ProductRow(
        name="A",
        kind="warranty",
        category="Ek Garanti",
        price=Decimal("10"),
        scraped_at="2026-11-20T00:00:00Z",
    )
    with_warranty = merge_product_rows([row("A", "1", "u1"), warranty])
    assert len(with_warranty) == 1
    assert with_warranty[0].product_id == "1"


def test_progress_disabled_is_silent() -> None:
    stream = io.StringIO()
    progress = Progress(True, stream)
    progress.start("test", 2)
    progress.advance(products=3, detail="x")
    progress._render(force=True)
    progress.close()
    assert "test" in stream.getvalue()
    assert "1/2" in stream.getvalue()

    silent = io.StringIO()
    disabled = Progress(False, silent)
    disabled.start("test", 2)
    disabled.advance()
    disabled.close()
    assert silent.getvalue() == ""


def test_progress_disabled_in_ci(monkeypatch) -> None:
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    assert default_enabled() is False


def test_specs_parser_on_saved_pdps() -> None:
    base = Path(__file__).resolve().parent.parent / "docs"
    index = parse_spec_details((base / "index.html").read_text(encoding="utf-8"))
    assert len(index.features) == 4
    assert len(index.specifications) == 43
    assert index.features[0]["title"] == "Isı Pompalı Kurutma Teknolojisi"
    assert index.features[0]["text"]
    assert index.specifications[0]["group"] == "Genel Özellikler"

    wash = parse_spec_details((base / "10122.html").read_text(encoding="utf-8"))
    assert len(wash.features) == 11  # 12 karttan 1'i metinsiz
    assert len(wash.specifications) == 42
    assert wash.features[0]["title"] == "SuperWash Teknolojisi"
    assert wash.features[0]["note"]
    assert any(
        item["group"] == "Genel Özellikler" for item in wash.specifications
    )


async def test_enrich_specs_and_cache(tmp_path: Path) -> None:
    base = Path(__file__).resolve().parent.parent / "docs"
    html = (base / "10122.html").read_text(encoding="utf-8")

    class SpecsHttp:
        def __init__(self) -> None:
            self.calls: list[str] = []
            self.aborted: str | None = None

        async def get(self, url: str, check_robots: bool = True) -> str | None:
            self.calls.append(url)
            return html

    cfg = make_config(tmp_path)
    cfg.cache.specs_file = str(tmp_path / "specs.json")
    row = ProductRow(
        name="10122",
        product_id="457100070000",
        category="Çamaşır Makinesi",
        url="https://www.arcelik.com.tr/a/10122",
        price=Decimal("42999"),
        scraped_at="2026-11-22T00:00:00Z",
    )
    report = Report("prices")
    http = SpecsHttp()
    await enrich_specs(
        http,
        [row],
        cfg,
        report,
        "2026-11-22T00:00:00Z",
    )
    assert len(http.calls) == 1
    assert len(row.features) == 11
    assert len(row.specifications) == 42
    assert report.data["specs_products"] == 1

    second_http = SpecsHttp()
    await enrich_specs(
        second_http,
        [row],
        cfg,
        report,
        "2026-11-22T00:00:00Z",
    )
    assert second_http.calls == []


def test_export_eleven_columns_with_json_and_both(tmp_path: Path) -> None:
    report = Report("prices")
    rows = [
        ProductRow(
            name="Test",
            product_id="9205971100",
            category="Buzdolabı",
            price=Decimal("100.00"),
            discounted_price=None,
            features=[{"title": "Tech", "text": "Text", "note": ""}],
            specifications=[
                {"group": "Genel", "name": "Kapasite", "value": "10 kg"}
            ],
            scraped_at="2026-11-20T00:00:00Z",
        )
    ]
    tables = products_tables(rows, full=True)
    assert tables[0].headers == PRODUCT_HEADERS
    assert tables[0].headers[0] == "Ürün ID"
    assert tables[0].headers[1] == "Ürün Adı"
    assert tables[0].headers[-1] == "Ürün Özellikleri (JSON)"
    assert len(tables[0].headers) == 11
    assert len(tables[0].rows[0]) == 11
    assert tables[0].rows[0][0] == "9205971100"
    details = json.loads(tables[0].rows[0][-1])
    assert details["features"][0]["title"] == "Tech"
    assert details["specifications"][0]["name"] == "Kapasite"
    assert json.loads(details_json(rows[0])) == details
    assert tables[1].headers[0] == "Ürün ID"
    assert tables[1].headers[1] == "Ürün Adı"
    assert tables[1].headers[-1] == "scraped_at"
    assert tables[1].rows[0][0] == "9205971100"
    payload = catalog_payload(rows, "2026-11-20T00:00:00Z")
    assert payload["schema_version"] == "1.0"
    assert payload["products"][0]["id"] == "9205971100"
    assert payload["products"][0]["features"][0]["title"] == "Tech"
    catalog_path = write_catalog(tmp_path, rows, "2026-11-20T00:00:00Z")
    assert catalog_path.name == "catalog.json"
    assert json.loads(catalog_path.read_text(encoding="utf-8"))["products"][0][
        "id"
    ] == "9205971100"
    dated_catalog = write_catalog(
        tmp_path, rows, "2026-11-20T00:00:00Z", "20260101-000000"
    )
    assert dated_catalog.name == "catalog_20260101-000000.json"
    assert (tmp_path / "catalog.json").exists()

    campaign_path = write_campaigns_json(
        tmp_path,
        [
            {
                "id": "c1",
                "name": "Kampanya",
                "conditions": ["Bir", "İki"],
                "products": [{"name": "Ürün", "relationship": "İlgili ürün"}],
            }
        ],
        "2026-11-20T00:00:00Z",
        "20260101-000000",
    )
    assert campaign_path.name == "kampanyalar_20260101-000000.json"
    campaign_payload = json.loads(
        campaign_path.read_text(encoding="utf-8")
    )
    assert campaign_payload["schema_version"] == "1.0"
    assert campaign_payload["campaigns"][0]["conditions"] == ["Bir", "İki"]
    paths = write_tables(
        [tables[0], tables[1], meta_table(report)],
        tmp_path,
        "both",
        "20260101-000000",
        partial=False,
    )
    suffixes = {p.suffix for p in paths}
    assert ".xlsx" in suffixes
    assert ".csv" in suffixes
    assert any(p.name.startswith("urunler_") for p in paths)
    assert any(p.name.endswith("_products.csv") for p in paths)
    assert any(p.name.endswith("_meta.csv") for p in paths)
    with_scraped = products_tables(rows, full=False, with_scraped_at=True)
    assert len(with_scraped[0].headers) == 12
    assert with_scraped[0].rows[0][-1] == "2026-11-20T00:00:00Z"
