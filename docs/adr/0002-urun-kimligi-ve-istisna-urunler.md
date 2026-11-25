# ADR-0002: Ürün kimliği ve istisna ürünler

- Durum: Kabul edildi; ürün ID kuralı ADR-0009 ile eklendi
- Not: Bu ADR'deki ad kuralı görünen ad ve ID fallback'i için geçerlidir; anahtar artık ID'dir (ADR-0009).
- Tarih: 2026-11-20
- İlgili: PRD v0.4 bölüm 6, 7; ADR-0003, ADR-0006
- Karar veren: Ürün sahibi + geliştirici

## Bağlam

Bayios, Excel'i içe aktarırken ürünleri Ürün Adı ile eşleştiriyor. Ürün sahibi 1. soruda "Sadece Ürün Adı" seçeneğini seçti. Bu nedenle adın site ve Bayios'ta birebir aynı olması kritik.

Sitede ad kaynağı iki farklı yerde:

- Kart aria-label: "283616 EI ürün detaylarını incele" → kısa ad "283616 EI".
- PDP h1: "1001 KMX 10 Kg Kurutma Makinesi" → uzun, pazarlama içeren ad.
- PDP breadcrumb son öğesi: "1001 KMX" → kısa model adı.
- JSON-LD name: bazen uzun, bazen varyant adı.

Bayios'taki mevcut kayıtlar kısa model adlarıdır (ör. "1002 KMX", "1011 KMP I"). Uzun h1 kullanılırsa eşleşme kaybolur ve importer yeni ürün yaratır.

Ayrıca 10-50 eski ürün hiçbir listing'de yok; yalnızca PDP'de ve fiyatsız. Bunların bir kez taranıp özelliklerinin alınması gerekiyor.

## Karar

1. Ürün anahtarı kısa addır:
   - Kategoriden gelen ürün: kart aria-label eksi " ürün detaylarını incele"; yoksa .prd-name .t.
   - Açık ürün: PDP breadcrumb son öğesi; yoksa JSON-LD name; yoksa h1 (separator ile); yoksa title (| öncesi).
2. Uzun ad title alanında tutulur; anahtar değildir.
3. [[products.include]] girişinde name override varsa her zaman kazanır. Bayios adı farklıysa zorunludur.
4. Açık ürünler URL ile tanımlanır; ilk tarama specs komutuyla yapılır; sonuç data/explicit_products.json cache'ine yazılır ve commit edilir.
5. Haftalık prices/all koşusu cache'te olmayan veya fetch = "always" olan açık ürünler için ilk seferde ağ isteği atar; cache'te olanları tekrar çekmez. --refresh-explicit tümünü zorla yeniler. Fetch başarısızsa config alanlarıyla satır üretir veya uyarı verip atlar.
6. Aynı ada sahip birden fazla URL tek satırda birleşir: ilk izinli kategori, ilk dolu fiyat, açık ürün specs. Çakışma raporlanır.
7. SKU eşleştirme v1 kapsamında değildir; v2'de importer değişikliği ile değerlendirilir.
8. --only verildiğinde açık ürünler yalnızca seçili app_category kümesindeyse çıktıya girer; tam koşuda tümü girer.
9. --only bir ürün URL'si de kabul eder; bu durumda kategori taraması atlanır ve URL doğrudan açık ürün olarak işlenir.
10. Toplu URL'ler [products] include_file = "data/product_urls.txt" ile verilir; her satır bir URL. Inline [[products.include]] aynı URL'de önce gelir (ad/kategori override). Kara liste explicit URL'ler için de geçerlidir; force = true istisnadır.

## Sonuçlar

Olumlu:
- Mevcut Bayios kayıtlarıyla eşleşme şansı yüksek.
- Eski/fiyatsız ürünler tek seferlik taranır; haftalık koşuya yük getirmez.
- Ad farklıysa name override ile düzeltilebilir.

Olumsuz / dikkat:
- Ad anahtarı kırılgandır; site adı değişirse veya iki ürün aynı ada sahipse eşleşme bozulur.
- Açık ürün listesi ve birebir adlar elle bakım gerektirir.
- Cache dosyası commit edilmelidir; aksi halde CI her koşuda cache'siz kalır.
- Uzun h1'in kullanılmaması, bazı ürünlerde ayırt edici bilgi kaybına yol açabilir; title alanı bu yüzden tutulur.

## Alternatifler

- SKU/ürün kodu anahtarı: daha sağlam, ancak Bayios importer değişikliği gerektirir (I4). v2'ye bırakıldı.
- URL anahtarı: Bayios desteklemiyor.
- Uzun h1 anahtarı: mevcut kayıtlarla uyuşmaz; reddedildi.
- Her eski ürünü elle Excel'e yazmak: bakım yükü yüksek; specs de gerekiyor.

## Uygulama notları

- Ad normalizasyonu: NBSP temizle, boşlukları tek boşluğa indir, baş/son boşlukları at. Büyük/küçük harf ve noktalama korunur.
- Açık ürün cache anahtarı normalize edilmiş URL'dir.
- Cache kaydı: name, title, category_lv1/lv2/lv3, app_category, price, discounted_price, specs[], scraped_at, content_hash.
- Başarısız fetch eski kaydı silmez.
- duplicate_names raporu ilk 50 kaydı içerir; istenirse duplicates.txt yazılır.
