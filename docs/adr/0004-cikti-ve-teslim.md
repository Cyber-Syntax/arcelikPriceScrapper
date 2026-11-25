# ADR-0004: Çıktı şeması ve teslim

- Durum: Kabul edildi; dosya adları/düzeni ADR-0008, ID ADR-0009, 11 sütun/JSON ADR-0010 ile güncellendi
- Tarih: 2026-11-20
- İlgili: PRD v0.6 bölüm 9, 13; ADR-0002, ADR-0008, ADR-0009
- Karar veren: Ürün sahibi + geliştirici

## Bağlam

Bayios'un Excel içe aktarma ekranı v0.5'e kadar 9 sütun kullanıyordu:

Ürün Adı, Kategori, Perakende Fiyat, Oliz İndirimli Fiyat, Fiziksel Stok, Alış Fiyatı, Kredi Kartı Taban Fiyatı, Nakit Taban Fiyatı, Aktif Kampanya.

v0.6'da ürün ID'si ilk sütun olarak eklendi; ana products 11 sütun oldu (son sütun Ürün Özellikleri JSON). Bayios importer'ın buna göre güncellenmesi gerekir. v0.3'te scraped_at 10. sütundu; v0.6'da ID + JSON nedeniyle scraped_at opt-in 12. sütundur.

Ürün sahibi 8. soruda şunları istedi: manuel scrape, GitHub Actions, GitHub Release, dosya adında tarih/saat, Excel ve CSV, haftalık çalışma, Actions'tan manuel tetikleme. Repoya commit veya ayrı private repo seçmedi.

## Karar

1. Ana products sayfası tam 11 sütundur: Ürün ID, Ürün Adı, Kategori, Perakende Fiyat, Oliz İndirimli Fiyat, Fiziksel Stok, Alış Fiyatı, Kredi Kartı Taban Fiyatı, Nakit Taban Fiyatı, Aktif Kampanya, Ürün Özellikleri (JSON).
2. scraped_at ana sayfada yoktur. Zaman damgası:
   - dosya adında (urunler_YYYYMMDD-HHMMSS, UTC)
   - meta sayfasında
   - products_full ve catalog.json çıktılarında
   - run_report.json içinde
3. --with-scraped-at opt-in olarak 12. sütunu ekler; yalnızca importer'ın fazla sütunu yok saydığı doğrulandıktan sonra kullanılır.
4. Çıktı formatı json, excel, csv veya both; varsayılan json. catalog.json her zaman yazılır; Excel/CSV seçilirse aynı 11 sütunla yedek. Excel çok sayfa, CSV tablo başına dosya.
5. Ana ürün workbook'u: products, products_full, meta, categories. catalog.json tüm ürün/özellik kataloğunu taşır. Kampanyalar ayrı dosyalarda (ADR-0007/0008); campaign_products referans tablosu kampanya dosyasında veya ayrı referans çıktısında tutulur.
6. Teslim:
   - GitHub Actions artifact (14 gün, hata ayıklama)
   - GitHub Release tag data-latest; tarihli dosya adları; overwrite; yalnızca başarılı koşu
   - Partial çıktı Release'e yüklenmez
7. Zamanlama: haftalık (Pazartesi 03:00 UTC) + workflow_dispatch (command/only/format). Manuel yerel CLI de desteklenir.
8. Repoya veri commit edilmez. (Açık ürün specs cache'i istisnadır; ADR-0006.)
9. Başarısız/abort koşuda çıkış kodu 2; workflow fail olur; Release adımı çalışmaz.

## Sonuçlar

Olumlu:
- Bayios import'u 11 sütuna güncellenince bozulmaz; ID ilk, JSON son sütundadır.
- Zaman damgası dosya adı ve meta ile izlenebilir.
- Excel ve CSV aynı veriyi taşır; Bayios Excel, diğer tüketiciler CSV kullanabilir.
- Release ile Bayios güncel dosyayı çekebilir.

Olumsuz / dikkat:
- Ana import dosyasında satır bazlı zaman damgası yoktur; istenirse opt-in.
- Release public olur; fiyatlar zaten public ama iş verisi sayılıyorsa private repo gerekir.
- data-latest üzerine yazılır; tarihsel release birikmez. Fiyat geçmişi Bayios'ta tutulur.
- Actions IP'lerinde 403 riski; erken test gerekir.

## Alternatifler

- 9/10 sütunlu ana sayfa: özellik JSON'u taşımaz; 11 sütun kabul edildi.
- CSV'yi repoya commit etmek: public veri ve commit gürültüsü; reddedildi.
- Yalnızca artifact: kalıcı ve kolay erişim yok; reddedildi.
- Tarihli Release tag'leri: tarihçe sağlar ama 52 release/yıl; data-latest tercih edildi. Gerekirse sonra eklenir.
- Ayrı private repo: fiyat gizliliği için; ürün sahibi seçmedi, açık soru olarak bırakıldı.

## Uygulama notları

- Excel sayfa sırası: products (11 sütun, Ürün ID ilk, JSON son), products_full, meta, categories. catalog.json ayrıdır. Kampanya dosyaları out/kampanyalar/ altında ayrıdır.
- Ürün CSV adları: urunler_<stamp>_products.csv, _products_full.csv, _meta.csv, _categories.csv. JSON: out/catalog.json. Kampanya CSV'leri ayrı dosyalardadır.
- Para hücreleri Excel'de sayısal, #,##0.00; CSV'de iki ondalık.
- Fiziksel Stok, Alış Fiyatı, Kredi Kartı Taban Fiyatı, Nakit Taban Fiyatı, Aktif Kampanya her zaman boş.
- Abort: dosya adına _partial eklenir; run_report.json abort_reason içerir.
