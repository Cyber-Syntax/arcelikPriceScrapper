# Ürün Scraper – Çoklu Export / Import Planı

## 1. Ortak Veri Modeli

Scraper ürünleri önce tek bir standart veri modelinde oluştursun.

Ürün alanları:

- `id` – Stabil ve benzersiz ürün kimliği (products.id)
- `product_name` – Ürün adı
- `price` – Normal fiyat
- `discounted_price` – İndirimli fiyat
- `currency` – Para birimi
- `source_url` – Ürün URL'si
- `features` – Ürün özellikleri
- `specifications` – Teknik özellikler
- `scraped_at` – Veri çekim tarihi

Teknik özelliklerde kategori/grup, özellik adı ve değer bilgileri korunsun.

## 2. Scraper Export Formatları

Aynı veri modelinden üç format üret:

**JSON** (her zaman üretilir)

- Tek bir `catalog.json` dosyası.
- Tüm ürünleri ve tüm özellikleri içersin.
- `schema_version` ve `scraped_at` metadata alanları bulunsun.
- İç içe JSON yapısı korunsun.

**Excel**

- Tek sayfa, her ürün bir satır.
- Ana products 11 sütun; son sütun `details_json`.
- Ürün bilgileri ayrı sütunlarda.
- `features` ve `specifications` tek bir `details_json` sütununda JSON olarak saklansın.

**CSV**

- Excel ile aynı sütun yapısını kullansın.
- `details_json` tek hücrede kalsın.
- UTF-8 BOM ve doğru CSV escaping desteklensin.

## 3. FastAPI Uygulaması – Import

Üç formatı da destekle:

- JSON katalog import
- Excel import
- CSV import

Excel/CSV içindeki `details_json` alanı parse edilerek features ve specifications verilerine dönüştürülsün.

JSON import doğrudan aynı ortak veri modeline bağlansın.

## 4. Veri Bütünlüğü

- `id` üzerinden mükerrer kayıt kontrolü yap.
- Ürün güncelleme ve yeni ürün ekleme senaryolarını destekle.
- Fiyatları hassas sayısal formatta sakla (Decimal).
- Eksik özellikler import işlemini bozmamalı.
- Geçersiz JSON için anlaşılır hata raporu oluştur.
- Eski Excel/CSV import şablonları geriye dönük uyumlu kalsın.

## 5. Test Planı

Aynı örnek katalog üzerinden:

1. JSON export → JSON import
2. Excel export → Excel import
3. CSV export → CSV import

Üç senaryoda da ürün sayısı, ürün kodları, fiyatlar ve tüm özellikler karşılaştırılsın. Veri kaybı veya mükerrer kayıt oluşmadığı doğrulansın.

## Temel Mimari Karar

Tek bir ortak ürün veri modeli kullan. JSON, Excel ve CSV birbirinden bağımsız veri kaynakları olmasın; aynı modelin üç farklı dışa aktarma biçimi olsun.

Öncelik: Üç formatı da uçtan uca çalışır hale getir, mevcut import/export işlevlerini bozma ve testleri tamamla.
