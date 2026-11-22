# ADR-0009: Ürün ID ve blog istisnası

- Durum: Kabul edildi
- Tarih: 2026-11-22
- İlgili: PRD v0.6 bölüm 3, 4, 9, 17; ADR-0002, ADR-0003, ADR-0004
- Karar veren: Ürün sahibi + geliştirici

## Bağlam

- Ürün adı tek başına Bayios eşleştirmesi için yeterince güvenli değil; aynı/adı benzeyen ürünler karışabiliyor.
- Sitede ürün ID'si birden fazla yerde var:
  - kart ve PDP'de data-product-code
  - JSON-LD içinde sku/productID
  - dataLayer/script içinde "products": [{"name": "...", "id": "..."}]
  - görsel dosya adlarında da görülebiliyor.
- Blog sayfaları fiyat/ürün kaynağı değil; kategori ağacında "Su Arıtma Blog" gibi düğümler çıkabiliyor ve categories.toml'a yazılabiliyor.

## Karar

1. Ürün ID:
   - Kaynak sırası: data-product-id, data-product-code, JSON-LD sku/productID, gömülü JSON products[].id.
   - ID, ürünün kısa adıyla birlikte taşınır; ana products sayfasında ilk sütundur.
   - Ana products 11 sütundur: Ürün ID, Ürün Adı, Kategori, Perakende, Oliz İndirimli, Fiziksel Stok, Alış, Kredi, Nakit, Aktif Kampanya, Ürün Özellikleri (JSON).
   - products_full, explicit cache ve campaign_products referansı product_id taşır.
   - Garanti satırlarında ID yoktur (boş).
   - ID bulunamayan ürün sayısı raporda; aynı adda farklı ID varsa çakışma uyarısı.

2. Blog istisnası:
   - URL yolunun ilk segmenti blog olan hiçbir şey taranmaz.
   - Kategori ağacındaki blog ve altındaki düğümler indexlenmez; list-categories, categories.txt ve categories.toml'da görünmez.
   - Blog kuralı config'teki exclude'dan bağımsızdır; force = true veya --only URL ile de aşılamaz.
   - Sitemap kategori listesinden de ayıklanır.

## Sonuçlar

Olumlu:
- Bayios eşleştirmesi ID ile yapılabilir; ada göre karışma riski azalır.
- Blog sayfalarından yanlış ürün/fiyat çekilmez; kategori listesi temiz kalır.
- ID ve ad birlikte kullanılarak manuel kontrol kolaylaşır.

Olumsuz / dikkat:
- Bayios importer 11 sütuna güncellenene kadar ana products import'u eski 9/10 sütun bekliyorsa kırılabilir; ürün sahibi güncelleyecek.
- ID her üründe bulunmayabilir; garanti satırları bilinçli olarak boş.
- Aynı adda farklı ID görülürse satırlar ayrı kalır ve rapor/uyarı üretilir; elle kontrol.
- ID kaynağı sayfa yapısına bağlı; data-product-code değişirse JSON-LD/gömülü JSON fallback devrede.

## Alternatifler

- ID'yi ana sayfaya koymamak, yalnızca products_full'a eklemek: Bayios import ekranında kullanılamaz; reddedildi.
- ID'yi son veya ikinci sütuna eklemek: ad-ID ilişkisi zayıf/kullanıcı ID'yi başta istiyor; ilk sütun tercih edildi.
- Blog'u config exclude'a bırakmak: kullanıcı unutabilir, categories.toml'da kalır; global kural tercih edildi.
- Blog URL'sini force ile açmak: fiyat kaynağı değil; güvenlik/veri kalitesi nedeniyle reddedildi.

## Uygulama notları

- Card product_id = data-product-id veya data-product-code.
- PDP product_id = JSON-LD sku/productID, data-product-code veya gömülü products[].id.
- categories.ALWAYS_EXCLUDED_SLUGS = {"blog"}; is_blog_url URL'nin ilk segmentini kontrol eder.
- Ana products başlıkları: Ürün ID, Ürün Adı, Kategori, Perakende Fiyat, Oliz İndirimli Fiyat, Fiziksel Stok, Alış Fiyatı, Kredi Kartı Taban Fiyatı, Nakit Taban Fiyatı, Aktif Kampanya, Ürün Özellikleri (JSON).
