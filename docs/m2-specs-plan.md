# M2 — Ürün Özellikleri (Specs) Planı

Durum: Onaylandı · Tarih: 2026-11-22
İlgili: docs/spec.md, docs/prd.md, docs/milestone-plan.md

## 1. Kaynak bulguları

| Dosya | pdp-technologies .ftc-item | #pdp-features-container grup | Teknik satır |
| --- | --- | --- | --- |
| docs/index.html (1001 KMX) | 4 | 6 | 43 |
| docs/10122.html | 12 (1 metinsiz) | 6 | 42 |

- Teknoloji metinleri: .pdp-technologies .ftc-item; başlık .ftc-title, metin .ftc-text.
- Teknik özellikler: #pdp-features-container .feature-item; grup .title, satırlar dl .item dt/dd.
- .ftc-text içinde br ve small/div olabilir; br newline, small içeriği note alanına alınır; HTML etiketi temizlenir.
- 10122'de bir ftc-item başlıksız/metinsiz; boş kayıt atlanır.
- Medya öğeleri video/img; gif/resim/video indirilmez.

## 2. Kapsam (onaylandı)

- Specs, seçili tüm ürünler için çekilir: seçili kategorilerdeki ürünler + explicit/açık ürünler.
- Her ürün için bir PDP isteği gerekir; ilk koşu uzun olabilir, cache zorunlu.
- Tüm katalog ayrı bir bilinçli batch; M2 kapsamı seçili ürünler.
- Medya indirme yok; sadece metin.

## 3. Veri modeli (onaylandı)

- id: ürün ID (data-product-code / gömülü products.id). Ayrı product_code yok.
- product_name
- category
- price
- discounted_price
- currency: TRY
- source_url
- features: teknoloji kartları
- specifications: teknik özellikler
- scraped_at

features öğesi:

    {"title": "...", "text": "Ana açıklama...", "note": "small/dipnot..."}

specifications öğesi:

    {"group": "Genel Özellikler", "name": "Kapasite", "value": "10 kg"}

- Aynı (group, name, value) tekilleştirilir.
- Aynı (title, text, note) tekilleştirilir.
- Boş title+text olan ftc-item atlanır.
- Değerler ham tutulur.

## 4. JSON (birincil ve her zaman)

Dosya: out/catalog_<YYYYMMDD-HHMMSS>.json + out/catalog.json (latest)

    {
      "schema_version": "1.0",
      "scraped_at": "2026-11-22T...Z",
      "products": [
        {
          "id": "457100070000",
          "product_name": "10122 SuperWash Teknolojili",
          "category": "Çamaşır Makinesi",
          "price": 42999.00,
          "discounted_price": null,
          "currency": "TRY",
          "source_url": "https://www.arcelik.com.tr/...",
          "features": [{"title": "...", "text": "...", "note": "..."}],
          "specifications": [{"group": "...", "name": "...", "value": "..."}],
          "scraped_at": "2026-11-22T...Z"
        }
      ]
    }

- catalog_<stamp>.json + catalog.json (latest) her ürün koşusunda yazılır; format json olsa da.
- schema_version ve scraped_at zorunlu.
- Eksik features/specifications boş liste; import bozulmaz.
- Fiyat JSON'da sayı; iki ondalık.

## 5. Ana products 11. sütun

Ana products 11 sütundur:

| # | Kolon |
| --- | --- |
| 1 | Ürün ID |
| 2 | Ürün Adı |
| 3 | Kategori |
| 4 | Perakende Fiyat |
| 5 | Oliz İndirimli Fiyat |
| 6 | Fiziksel Stok |
| 7 | Alış Fiyatı |
| 8 | Kredi Kartı Taban Fiyatı |
| 9 | Nakit Taban Fiyatı |
| 10 | Aktif Kampanya |
| 11 | Ürün Özellikleri (JSON) |

- 11. hücre: {"features": [...], "specifications": [...]} JSON string'i.
- --with-scraped-at opt-in 12. sütun.
- Excel/CSV bu 11 sütunla üretilir; catalog.json ayrıca tam katalogdur.

## 6. Parser kuralları

- Teknik: .feature-item .title; .item dt.t / dd.v; sıra korunur; (group, name, value) tekilleştirilir.
- Teknoloji: .ftc-item .ftc-title; .ftc-text:
  - br -> newline
  - small -> note
  - div/p -> metin
  - HTML etiketi yok; boşluk normalize.
- 10122 item 9 (başlıksız/metinsiz) atlanır.
- Medya/gif/resim/video alanı yok.

## 7. Format / config

- output.format: json | excel | csv | both; varsayılan json.
- json: yalnızca catalog_<stamp>.json + catalog.json (Excel/CSV yok).
- excel: catalog_<stamp>.json + catalog.json + Excel (11 sütun).
- csv: catalog_<stamp>.json + catalog.json + CSV (11 sütun).
- both: catalog_<stamp>.json + catalog.json + Excel + CSV.
- JSON her durumda yazılır.
- --with-scraped-at ana products 12. sütun; varsayılan kapalı.

## 8. Cache ve istek bütçesi

- Cache: data/specs_cache.json; anahtar ürün ID, yoksa normalize URL.
- Bir ürün için bir PDP isteği; başarılı kayıt cache'e yazılır.
- İkinci koşu cache'ten; --refresh-specs zorlar.
- Başarısız fetch eski cache'i silmez; uyarı.
- Tüm seçili ürünler için ilk koşu uzun; progress ve abort/partial gerekir.
- Medya isteği 0.

## 9. CLI

- specs komutu: --only, --exclude, --refresh-specs, --format.
- prices/all: specs'i tüm seçili ürünler için zenginleştirir.
- all: ayrıca campaigns (M3).
- catalog.json her zaman.

## 10. Test/kabul

- 1001 KMX: 4 feature + 6 grup/43 spec.
- 10122: 12 feature (1 boş atlanır) + 6 grup/42 spec.
- 11. sütun JSON'u catalog.json ile aynı features/specifications.
- JSON/Excel/CSV aynı veriyi taşır.
- İkinci koşu 0 PDP; medya 0.
- Ana products 11 sütun; --with-scraped-at 12.
- Resolved: kapsam, 11. sütun, catalog, format, small, product_code yok.

## 11. M2.3 tanımı

M2.3 = teknoloji metinleri (ftc-text). M2.2 = teknik özellikler; M2.4 = JSON/Excel/CSV çıktı; M3 = kampanyalar.
