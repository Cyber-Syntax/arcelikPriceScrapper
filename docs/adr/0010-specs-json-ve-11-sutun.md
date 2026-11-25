# ADR-0010: Specs kapsamı, catalog.json ve 11. sütun

- Durum: Kabul edildi
- Tarih: 2026-11-22
- İlgili: PRD v0.6 bölüm 6.4, 9.1, 9.3, 9.7, 10, 17; ADR-0004, ADR-0006
- Karar veren: Ürün sahibi + geliştirici

## Bağlam

M2 ürün özellikleri kapsamı netleşti:

- Specs yalnızca explicit ürünler değil, seçili tüm ürünler için isteniyor.
- 10122 gibi ürünlerde .pdp-technologies .ftc-item içinde detaylı teknoloji metinleri var; bazı ürünlerde yalnızca #pdp-features-container teknik özellikleri var.
- Bayios JSON support ekleyecek; Excel/CSV yedek kalmalı.
- Ana products 11. sütunda JSON details taşınacak; catalog.json ayrıca tüm katalogu taşıyacak.
- Format varsayılanı json olacak; JSON her zaman üretilecek.

## Karar

1. Kapsam: seçili tüm ürünler (kategoriler + explicit/açık ürünler). Her ürün için bir PDP isteği; cache zorunlu.
2. Ana products 11 sütun: Ürün ID, Ürün Adı, Kategori, Perakende, Oliz İndirimli, Fiziksel Stok, Alış, Kredi, Nakit, Aktif Kampanya, Ürün Özellikleri (JSON). --with-scraped-at 12. sütun.
3. catalog.json: out/catalog_<stamp>.json + out/catalog.json (latest); schema_version, scraped_at, products[]. Her ürün id, product_name, category, price, discounted_price, currency, source_url, features[], specifications[], kind, scraped_at.
4. Ayrı product_code yoktur; products.id kullanılır.
5. features: .pdp-technologies .ftc-item; title .ftc-title, text .ftc-text. br newline; small/div içeriği parse edilir; small note alanına alınır. Medya/gif/resim/video indirilmez.
6. specifications: #pdp-features-container .feature-item; group .title; dt/dd; (group,name,value) tekilleştirilir.
7. Format: json | excel | csv | both; varsayılan json. catalog.json her zaman; Excel/CSV seçilirse 11 sütunla yedek.
8. Cache: data/specs_cache.json; ID veya URL anahtarı; --refresh-specs zorlar.

## Sonuçlar

Olumlu:
- Tüm seçili ürünlerin teknik ve teknoloji metinleri tek modelde.
- Bayios JSON ile zengin veri alır; Excel/CSV geriye dönük yedek kalır.
- Ana products 11. sütun sayesinde import sırasında detaylar ürünle birlikte taşınır.

Olumsuz / dikkat:
- İlk koşu tüm seçili ürünler için PDP isteği atar; uzun sürebilir.
- Bayios importer 11 sütuna ve JSON içeriğine göre güncellenmeli.
- HTML değişirse ftc-text/spec parser kırılabilir; fixture testi gerekir.
- JSON/Excel/CSV üçünde aynı veri korunmalı; test edilmeli.

## Alternatifler

- Yalnızca explicit ürünler: reddedildi; tüm seçili ürünler istendi.
- Ayrı _specs dosyası: reddedildi; 11. sütun + catalog.json tercih edildi.
- Yalnızca JSON: Excel/CSV yedek isteği nedeniyle reddedildi.
- Medya indirmek: gereksiz istek; v1 metin yeterli.

## Uygulama notları

- Main JSON hücresi: {"features":[...], "specifications":[...]}.
- catalog.json fiyatları sayı; boş fiyat null.
- specs cache atomik yazılır; başarısız fetch eski kaydı silmez.
- 1001 KMX 4 feature/6-43; 10122 11 feature (12 karttan 1 boş)/6-42.
