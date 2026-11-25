# ADR-0006: Ürün özellikleri ve tek seferlik cache

- Durum: Kısmen güncellendi (kapsam/çıktı: ADR-0010)
- Tarih: 2026-11-20
- Not: M2'de kapsam tüm seçili ürünler, çıktı catalog.json + 11. sütun oldu (ADR-0010); aşağıdaki 1/2/5/7 tarihsel karardır.
- İlgili: PRD v0.4 bölüm 6.2, 6.4, 9.3; ADR-0002
- Karar veren: Ürün sahibi + geliştirici

## Bağlam

Ürün sahibi, 10-50 eski/fiyatsız ürünün yalnızca bir kez taranmasını ve özelliklerinin (ör. Kurutma Kapasitesi 10 kg, Akıllı Nem Sensörü, Isı Pompalı Kurutma Teknolojisi) alınmasını istiyor. Bu ürünler eski olduğu için fiyatları ve özellikleri uzun süre değişmiyor; haftalık koşuda tekrar istek atmak gereksiz ve ban riski.

1001 KMX kayıtlı HTML'inde özellikler sunucu tarafında geliyor: #pdp-features-container .feature-item içinde 6 grup, 43 özellik. Aynı container masaüstü/mobil için iki kez basılıyor.

## Karar

1. Özellikler yalnızca açık ürünler ([[products.include]]) için taranır.
2. Yeni specs komutu PDP'leri çeker, özellikleri ayrıştırır ve data/explicit_products.json cache'ine yazar. M1 notu: specs ayrıştırma henüz yok; M1'de cache'te olmayan açık ürünler ilk prices koşusunda bir kez çekilir, --refresh-explicit tümünü zorlar; yalnızca ad/kategori/fiyat özeti cache'lenir.
3. Haftalık prices/all koşusu cache'te olmayan veya fetch = "always" olan açık ürünler için ilk seferde ağ isteği atar; cache'te olanları tekrar çekmez. specs ayrıştırma M2'de; M1 cache'i okur.
4. Cache dosyası repoya commit edilir (küçük JSON; fiyat alanı da taşıyabilir). Böylece CI ve yerel koşular aynı veriyi kullanır.
5. specs komutu seçenekleri: --only URL, --only-new, --refresh, --config, --format.
6. Parse:
   - #pdp-features-container .feature-item
   - grup: .title
   - satır: dl .item içindeki dt/dd
   - (grup, özellik, değer) üçlüsüyle tekilleştir
   - değerler ham; birim dönüşümü yok
7. Çıktı product_specs uzun tablosu: Ürün Adı, code, group, spec, value, url, scraped_at. Bayios'a import edilmez; referans veridir.
8. Parse hatasında eski cache korunur; boş sonuçla üzerine yazılmaz.

## Sonuçlar

Olumlu:
- Eski ürünler için tek seferlik, hızlı tarama.
- Haftalık koşuya ek istek yükü yok.
- Özellikler Excel'de ayrı sayfada; Bayios import şablonu bozulmaz.
- Cache sayesinde CI ve yerel çıktı tutarlı.

Olumsuz / dikkat:
- Cache commit edilmezse CI'da specs kaybolur.
- Site HTML'i değişirse parse kırılır; fixture testi ve eski cache koruması gerekir.
- Özellik değerleri tutarsız olabilir (ör. Boyut (cm) (GxYxD) = 59.8 cm); temizlik yapılmaz, ham yazılır.
- Tüm ürünler için specs v2 kapsamındadır; bu ADR yalnızca açık ürünleri kapsar.

## Alternatifler

- Her hafta tüm PDP'leri taramak: 5.693 istek; reddedildi.
- Özellikleri elle kopyalamak: 10-50 ürün için mümkün ama bakım yükü ve hata riski; reddedildi.
- SQLite cache: D12 ile çelişir; JSON yeterli.
- Özellikleri ana products sayfasına sütun olarak eklemek: kategoriye göre değişen yüzlerce sütun; Bayios import'unu bozar; reddedildi.

## Uygulama notları

- Cache yazımı atomik: temp dosya + rename; yarıda kalan yazma eski kaydı bozmaz.
- content_hash ile değişiklik tespiti opsiyonel; --refresh zorlar.
- Aynı URL iki kez taranmaz; cache anahtarı normalize URL.
- specs çıktısı Excel'de product_specs sayfası, CSV'de ayrı dosya.
- 1001 KMX kabul testi: 6 grup, 43 satır; Kurutma Kapasitesi = 10 kg; Akıllı Nem Sensörü = Eco Sense; Kurutma Teknolojisi = Isı Pompalı.
