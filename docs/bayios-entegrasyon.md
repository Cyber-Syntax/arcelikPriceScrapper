# Bayios Entegrasyon Brief'i — Scraper v0.6

Durum: Scraper tarafı M2 uygulandı · Tarih: 2026-11-22
Amaç: Bu doküman, scraper çıktısındaki ID + JSON değişikliklerini Bayios'a taşımak için tek başına yeterli bir brief'tir.

## 0. Başka chat'e verilecek kısa brief

Bayios'a scraper entegrasyonu iki fazda yapılacak:

1. Önce Excel/CSV import: ana products 11 sütun olacak; ilk sütun Ürün ID, son sütun Ürün Özellikleri (JSON). Eski 9/10 sütunlu dosyalar da okunmaya devam edecek.
2. Sonra catalog.json import: scraper her koşuda out/catalog_<stamp>.json + out/catalog.json üretecek; tüm ürünler, features ve specifications bu dosyada olacak.
3. Kampanyalar için out/kampanyalar/kampanyalar_<stamp>.json + campaigns.json üretilecek; JSON içinde koşullar ve ürünler olacak.

Ortak ürün modeli ID anahtarlıdır; ayrı product_code yoktur. JSON içinde features[] ve specifications[] bulunur. Medya/gif/resim/video yoktur, sadece metin vardır. Excel/CSV, JSON bozulursa kullanılacak yedektir.

## 1. Scraper'dan çıkan dosyalar

- out/catalog_<YYYYMMDD-HHMMSS>.json — her ürün koşusunda üretilir; tarihli JSON.
- out/catalog.json — aynı içeriğin latest kopyası; mevcut entegrasyon için.
- out/kampanyalar/kampanyalar_<YYYYMMDD-HHMMSS>.json — kampanya JSON'u.
- out/kampanyalar/campaigns.json — kampanya JSON'unun latest kopyası.
- out/urunler_<YYYYMMDD-HHMMSS>.xlsx — format excel veya both ise.
- out/urunler_<YYYYMMDD-HHMMSS>_products.csv — format csv veya both ise.
- out/urunler_<YYYYMMDD-HHMMSS>_products_full.csv — --full verilirse referans.
- out/urunler_<YYYYMMDD-HHMMSS>_meta.csv — --format csv/both ise.
- out/run_report.json — koşu raporu.

Format davranışı:

- Varsayılan format json'dur; catalog tarihli + latest yazılır.
- format excel: catalog_<stamp>.json + catalog.json + Excel.
- format csv: catalog_<stamp>.json + catalog.json + CSV.
- format both: catalog_<stamp>.json + catalog.json + Excel + CSV.
- JSON hiçbir zaman kapatılmaz.

Ana products 11 sütundur. --with-scraped-at verilirse 12. sütun scraped_at eklenir.

## 2. Ortak ürün modeli

- id: ürün ID'si; string. products.id / data-product-code. Ayrı product_code yok.
- product_name: görünen ürün adı.
- category: Bayios kategori adı.
- price: perakende fiyat; Decimal, iki ondalık; bilinmiyorsa boş/null.
- discounted_price: Oliz indirimli fiyat; yoksa boş/null.
- currency: TRY.
- source_url: ürün URL'si.
- features: teknoloji metinleri (title, text, note).
- specifications: teknik özellikler (group, name, value).
- kind: product | warranty | explicit.
- scraped_at: ISO UTC.

Kurallar:

- ID string olarak saklanmalı; baştaki sıfırlar korunmalı.
- Fiyat 0 yazılmaz; bilinmeyen fiyat boş/null.
- Aynı ID tek satırdır. Aynı ad farklı ID ise ayrı satırlardır; ada göre birleştirme yapılmaz.
- Garanti satırlarında ID boş olabilir; bunlar legacy olarak adla eşleştirilebilir.
- features/specifications boş liste olabilir; import bozulmaz.

## 3. Faz 1 — Excel/CSV import

### 3.1 Ana products sütunları

| # | Başlık | Tip | Not |
| --- | --- | --- | --- |
| 1 | Ürün ID | string | Birincil anahtar; boş olabilir (garanti) |
| 2 | Ürün Adı | string | Görünen ad |
| 3 | Kategori | string | Bayios kategori adı |
| 4 | Perakende Fiyat | decimal | Boş olabilir; 0 yazılmaz |
| 5 | Oliz İndirimli Fiyat | decimal | Boş olabilir |
| 6 | Fiziksel Stok | boş | Scraper doldurmaz |
| 7 | Alış Fiyatı | boş | Scraper doldurmaz |
| 8 | Kredi Kartı Taban Fiyatı | boş | Scraper doldurmaz |
| 9 | Nakit Taban Fiyatı | boş | Scraper doldurmaz |
| 10 | Aktif Kampanya | boş | Scraper doldurmaz |
| 11 | Ürün Özellikleri (JSON) | JSON string | features + specifications |
| 12 | scraped_at | string | Yalnızca --with-scraped-at ile; opsiyonel |

Başlık eşlemesi pozisyona göre değil, başlık adına göre yapılmalı. Fazla sütunlar yok sayılmalı; eksik opsiyonel sütunlar boş kabul edilmeli.

### 3.2 11. sütun JSON formatı

Hücrede JSON string bulunur:

    {"features":[{"title":"SuperWash Teknolojisi","text":"Ana açıklama...","note":"small/dipnot..."}],"specifications":[{"group":"Genel Özellikler","name":"Kapasite","value":"10 kg"}]}

Kurallar:

- features: title, text, note.
- specifications: group, name, value.
- HTML etiketi yoktur; br newline'a çevrilir; small/div içeriği note veya text içinde gelir.
- Medya/gif/resim/video alanı yoktur.
- Boş detay: {"features":[],"specifications":[]}.
- JSON hücresi boşsa mevcut detaylar değiştirilmemeli.
- Boş listeler gelirse detaylar temizlenebilir; bunu import kuralı olarak netleştir.
- Bozuk JSON satırı tüm dosyayı düşürmemeli; satır hatası raporlanmalı, ürün alanları ise mümkünse güncellenmeli.

### 3.3 Excel/CSV import akışı

1. Dosya tipini belirle (xlsx/csv).
2. Başlıkları normalize et; 9, 10, 11 veya 12 sütunlu eski/yeni dosyaları kabul et.
3. Satırları doğrula: ID/name, fiyat formatı, JSON parse.
4. Ürünü ID ile upsert et.
5. ID boşsa (garanti) ada göre legacy eşleştir; yeni ID uydurma.
6. JSON detaylarını product_details alanına yaz.
7. Sonuç raporu: eklenen, güncellenen, atlanan, hatalı satır sayıları.

Eski dosya uyumu:

- 9 sütun: ID ve JSON yok; adla eşleştir, detayları değiştirme.
- 10 sütun: ID var, JSON yok; ID ile eşleştir, detayları değiştirme.
- 11 sütun: ID + JSON; tam yeni format.
- 12 sütun: ID + JSON + scraped_at; scraped_at opsiyonel.
- Başlık yoksa pozisyon varsayımı yapma; hata ver veya açık kolon eşlemesi iste.

### 3.4 Fiyat ve boş hücre

- Fiyatlar ondalık; Excel'de sayısal hücre, CSV'de iki ondalık.
- Boş hücre "dokunma" demektir; 0 yazılmaz.
- Fiziksel Stok/Alış/Kredi/Nakit/Aktif Kampanya her zaman boş.
- Para birimi TRY.

## 4. Faz 2 — catalog.json import

### 4.1 Dosya

out/catalog_<YYYYMMDD-HHMMSS>.json (tarihli)
out/catalog.json (latest kopya)

### 4.2 Şema

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
          "kind": "product",
          "scraped_at": "2026-11-22T...Z"
        }
      ]
    }

### 4.3 Import kuralları

- schema_version kontrol edilir; desteklenmeyen sürüm açık hata verir.
- Ürünler ID ile upsert edilir.
- Aynı ID birden fazla kez gelirse son kayıt değil, ilk kayıt + uyarı veya son kayıt kuralı netleştirilmeli; öneri: ilk kayıt, çakışma raporu.
- ID boşsa ada göre legacy eşleştir; yeni ID üretme.
- features/specifications her zaman replace edilir (catalog tam snapshot'tır).
- Eksik ürünler silinmez; delist yapılmaz.
- Fiyat null olabilir; 0'a çevrilmez.
- kind product/warranty/explicit olarak saklanır; warranty detayları boş olabilir.
- Import tek transaction veya batch; hatalı ürün diğerlerini düşürmemeli.
- Dry-run/preview ve hata raporu olmalı.

## 5. Kampanya JSON

### 5.1 Dosya

out/kampanyalar/kampanyalar_<YYYYMMDD-HHMMSS>.json
out/kampanyalar/campaigns.json (latest)

### 5.2 Şema

    {
      "schema_version": "1.0",
      "scraped_at": "2026-11-22T...Z",
      "campaigns": [
        {
          "id": "dugun-com",
          "name": "Düğün.com Kampanyası",
          "category": "kampanyalar",
          "url": "https://www.arcelik.com.tr/kampanyalar/...",
          "date_text": "17-20 Kasım 2026",
          "start_date": "2026-11-17",
          "end_date": "2026-11-20",
          "conditions": ["Kampanya ...", "Seçili ..."],
          "product_count": 2,
          "products": [
            {"name": "07325 A", "product_id": "...", "relationship": "İlgili ürün", "required_quantity": null}
          ],
          "scraped_at": "2026-11-22T...Z"
        }
      ]
    }

### 5.3 Import kuralları

- Kampanya id ile upsert edilir; id yoksa url/name fallback.
- conditions liste olarak saklanır; Excel'deki newline metinle aynı içerik.
- products 3 alanlıdır: name, relationship, required_quantity; product_id opsiyonel.
- Kampanya silinmez; eksik kampanya delist edilmez.
- JSON her zaman; Excel/CSV kampanya düzeni M3'te bekliyor.

## 6. Veritabanı / API önerisi

- products tablosunda id string unique.
- features/specifications için JSONB veya ayrı tablolar; JSONB önerilir; okurken parse etme, yazarken string'e çevirme.
- Excel/CSV'deki JSON hücresi ile catalog.json aynı modele parse edilmeli.
- Upsert anahtarı: id; id boşsa name (legacy).
- Aynı ad farklı ID: iki ürün; ada göre merge yok.
- Detay güncelleme: JSON alanı doluysa replace; boşsa dokunma; boş listeler clear.
- Import ekranında dosya tipi otomatik algılanmalı; JSON/Excel/CSV aynı preview modeline dönüşmeli.
- Hata raporu: satır no, ID, alan, mesaj.

## 7. Test / kabul

- 9, 10, 11 ve 12 sütunlu Excel/CSV dosyaları okunur.
- 11. sütundaki JSON doğru parse edilir; bozuk JSON satır hatası verir.
- features/specifications DB'ye doğru yazılır.
- Aynı ID güncellenir, yeni ID eklenir; aynı ad farklı ID ayrı kalır.
- ID'siz garanti satırı adla eşleşir; yeni ID uydurulmaz.
- catalog_<stamp>.json / catalog.json importu Excel/CSV ile aynı sonucu verir.
- Fiyat Decimal/iki ondalık; boş fiyat 0 olmaz.
- Import sonrası ürün detayları JSON'dan okunabilir.
- Eski 9/10 sütunlu dosya detayları silmez.

## 8. Uygulama sırası

1. DB/API modeline JSON detay alanı ekle.
2. Excel/CSV parser'ı 11 sütuna ve başlık eşlemesine güncelle.
3. JSON hücresini parse et; detayları upsert et.
4. Eski 9/10 sütun uyumunu test et.
5. catalog.json parser'ını ekle; aynı modele bağla.
6. Preview/validasyon/hata raporu ekle.
7. Excel/CSV ve JSON aynı veriyi veriyor mu test et.

## 9. Yapılmaması gerekenler

- Ayrı product_code eklemeye çalışma; ID yeterli.
- Medya/gif/resim/video indirmeye çalışma; JSON'da yok.
- JSON hücresini çift encode etme; DB'de JSONB/nesne olarak sakla.
- ID varken ürünü ada göre birleştirme.
- Boş fiyatı 0 yapma.
- Eksik ürünleri import sırasında silme.
- Excel/CSV'yi JSON'a göre ikinci sınıf yapma; yedek olarak koru.

## 10. Açık kararlar

- Detaylar JSONB mi, normalize tablo mu? Öneri: JSONB + gerekirse okuma için view.
- Aynı ID birden fazla kez gelirse ilk mi son mu? Öneri: ilk + çakışma raporu.
- JSON hücresi boşken mevcut detay korunmalı mı? Öneri: evet.
- Boş listeler detayları temizlemeli mi? Öneri: evet; açıkça clear.
- Garanti satırlarında ID boşsa ada göre eşleşme kabul mü? Öneri: evet, legacy.

## 11. Scraper komutları

- Varsayılan: arcelikPriceScrapper prices — catalog_<stamp>.json + catalog.json.
- Excel/CSV dahil: arcelikPriceScrapper prices --format both.
- Tek kategori: arcelikPriceScrapper prices --only buzdolabi --format both.
- Specs yenile: arcelikPriceScrapper specs --refresh-specs --format json.
- Kampanyalar: arcelikPriceScrapper campaigns --format json (kampanya JSON'u).
- Hepsi: arcelikPriceScrapper all --format both.
- Actions: format seçenekleri json/excel/csv/both; varsayılan json.
