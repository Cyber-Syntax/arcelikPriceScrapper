from decimal import Decimal

from arcelikPriceScrapper.campaigns import parse_date_range
from arcelikPriceScrapper.http import RobotsRules
from arcelikPriceScrapper.prices import parse_price
from arcelikPriceScrapper.warranties import parse_warranty_html


def test_parse_price():
    assert parse_price("56.399 TL") == Decimal("56399")
    assert parse_price("₺3.099") == Decimal("3099")
    assert parse_price("1.234,50") == Decimal("1234.50")
    assert parse_price("475.00") == Decimal("475.00")
    assert parse_price("Oliz'e Özel") is None
    assert parse_price("") is None


def test_date_range():
    assert parse_date_range("17 Kasım - 20 Kasım 2026") == (
        "2026-11-17",
        "2026-11-20",
    )
    assert parse_date_range("1 Eylül - 30 Nisan 2027") == (
        "2026-09-01",
        "2027-04-30",
    )
    assert parse_date_range("17-20 Kasım 2026") == ("2026-11-17", "2026-11-20")
    assert parse_date_range("yok") is None


def test_robots_wildcards():
    r = RobotsRules(
        "User-agent: *\nDisallow: /ws/v2*\nDisallow: /*?sort=*\nDisallow: /*variant\n\n"
        "User-agent: GPTBot\nAllow: /\n"
    )
    assert not r.allowed("https://www.arcelik.com.tr/ws/v2/x")
    assert not r.allowed("https://www.arcelik.com.tr/buzdolabi?sort=price")
    assert not r.allowed("https://www.arcelik.com.tr/a/b-variant-1")
    assert r.allowed("https://www.arcelik.com.tr/buzdolabi?page=2")
    assert r.allowed("https://www.arcelik.com.tr/kampanyalar")


WARRANTY_HTML = """
<table>
<tr><td>Ürün Grubu</td><td>Satış<br>Dönemi</td><td>Ek Garanti<br>Süresi</td><td>Ek Garanti Tanım</td>
<td>Tavsiye Edilen Perakende Satış Fiyatı (KDV Dahil - Kasım 2026)</td></tr>
<tr><td rowspan="2">Bulaşık Makinesi</td><td>(0-6 Ay)</td><td>2 Yıl</td><td>2 Yıl EG Bulaşık Mk. (0-6 Ay)</td><td>₺3.099</td></tr>
<tr><td>(7-36 Ay)</td><td>2 Yıl</td><td>2 Yıl EG Bulaşık Mk. (7-36 Ay)</td><td>₺3.649</td></tr>
</table>
"""


def test_warranty_rowspan():
    rows = parse_warranty_html(
        WARRANTY_HTML, "Ek Garanti", "2026-11-19T00:00:00Z"
    )
    assert [r.name for r in rows] == [
        "2 Yıl EG Bulaşık Mk. (0-6 Ay)",
        "2 Yıl EG Bulaşık Mk. (7-36 Ay)",
    ]
    assert [r.price for r in rows] == [Decimal("3099"), Decimal("3649")]
    assert all("Bulaşık Makinesi" in r.title for r in rows)
    assert all(
        r.category == "Ek Garanti" and r.kind == "warranty" for r in rows
    )
