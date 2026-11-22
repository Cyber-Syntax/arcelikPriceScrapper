# arcelikPriceScrapper

Kısa kullanım rehberi. Ayrıntılı gereksinimler ve kararlar için docs/prd.md ve docs/adr/ altına bak.

## 0. Ne yapar?

- Seçili kategori sayfalarından ürün adı, kategori, perakende fiyat ve Oliz indirimli fiyatı çeker.
- data/product_urls.txt içindeki açık ürün URL'lerini bir kez çekip data/explicit_products.json cache'ine yazar.
- Bayios'un 11 sütunlu Excel şablonunu (Ürün ID ilk, Ürün Özellikleri JSON son) ve aynı verinin CSV'sini üretir.
- Her koşuda out/catalog.json üretir; JSON varsayılan formattır.
- Ürün anahtarı ID'dir; aynı ID birleşir, aynı ad farklı ID ise ayrı satır kalır ve raporlanır.
- Ek garanti ürün koşusunda ürünlerle birlikte gelir (ayrı komut/dosya yok); kampanyalar out/kampanyalar/ altında kampanya başına dosya üretir.

## 1. Hızlı test (Bayios'a dokunmadan)

Kurulum:

    uv sync

Testler:

    uv run pytest --no-cov

Kategori listesini dosyaya yaz:

    uv run arcelikPriceScrapper list-categories

Bu komut out/categories.txt ve out/categories.toml dosyalarını üretir.

Tek kategoriyi test et:

    uv run arcelikPriceScrapper prices --only buzdolabi --format both --out-dir out-test

Tek ürünü test et:

    uv run arcelikPriceScrapper prices --only https://www.arcelik.com.tr/10-kg-kurutma-makinesi/1001-kmx-kurutma-makinesi --format csv --out-dir out-test

Beklenen çıktı out-test/ altında:

- catalog.json (her zaman)
- urunler_YYYYMMDD-HHMMSS.xlsx (--format excel/both)
- urunler_YYYYMMDD-HHMMSS_products.csv (--format csv/both)
- urunler_YYYYMMDD-HHMMSS_products_full.csv (--full ile)
- urunler_YYYYMMDD-HHMMSS_meta.csv
- run_report.json

Test için out-test kullan; gerçek out/ klasörünü ezme.

## 2. Tüm ürünleri çekip Bayios'ta kullanmak

1. config.toml içindeki [[categories.include]] listesini istediğin kategorilerle düzenle.
   Kategori slug'larını out/categories.toml içinden kopyalayabilirsin.
2. data/product_urls.txt içine özel/eski ürün URL'lerini her satıra bir URL olarak koy.
   # ile başlayan satırlar yorumdur.
3. Tek seferlik cache'i doldur (kategori kategori, güvenli yöntem):

    uv run arcelikPriceScrapper prices --only buzdolabi --refresh-explicit --format csv --out-dir out/test
    uv run arcelikPriceScrapper prices --only kurutma-makinesi --refresh-explicit --format csv --out-dir out/test
    uv run arcelikPriceScrapper prices --only camasir-makinesi --refresh-explicit --format csv --out-dir out/test
    uv run arcelikPriceScrapper prices --only bulasik-makinesi --refresh-explicit --format csv --out-dir out/test
    uv run arcelikPriceScrapper prices --only ankastre-firin --refresh-explicit --format csv --out-dir out/test

   --only kategori verdiğinde yalnızca o kategoriye ait açık ürünler seçilir; diğerleri atlanır.
   Böylece 2296 URL'lik dosya tek seferde istenmez.

4. Tam koşu:

    uv run arcelikPriceScrapper prices --format both --full

   Bu koşu kategori sayfalarını çeker ve cache'teki açık ürünleri kullanır.
   Cache'te olmayan açık ürünler için max_auto_fetch sınırı vardır (config.toml, varsayılan 50).
   Sınır aşılırsa uyarı verir; eksikler atlanır.

5. out/urunler_<stamp>.xlsx içindeki Ürünler sayfasını Bayios'un içe aktarma ekranına yükle.
   Ana sayfa 11 sütundur: Ürün ID, Ürün Adı, Kategori, 2 fiyat, 5 boş Bayios kolonu ve Ürün Özellikleri (JSON).
   Ürün ID kart/PDP'den gelir; garanti satırlarında boştur. Fiziksel Stok/Alış/Kredi/Nakit/Aktif Kampanya boş bırakılır.
   Özellikler tüm seçili ürünler için PDP'den çekilir; catalog.json ayrıca tüm kataloğu taşır.
   Zaman damgası dosya adında, Meta sayfasında ve products_full çıktısındadır.
   Ek garanti ayrı komut değildir; prices/all koşusunda ürünlerle birlikte gelir.

Önemli: Büyük URL listesinde tüm dosya için tek komutla --refresh-explicit çalıştırma.
Bu, listedeki tüm seçili ürünler için PDP isteği atar. Kategori kategori ilerle.

## 3. GitHub Actions

Mevcut workflow:

- Haftalık: her pazartesi 03:00 UTC, command=prices.
- Manuel: Actions ekranından workflow_dispatch veya gh ile.

Tüm kategorileri manuel çalıştırma:

    gh workflow run scrape.yml -f command=prices -f format=both

Tek kategori:

    gh workflow run scrape.yml -f command=prices -f only=buzdolabi -f format=both

Fiyat + ek garanti + kampanya:

    gh workflow run scrape.yml -f command=all -f format=both

Progress bar Actions/CI ortamında otomatik kapalıdır; loglar temiz kalır. Gerekirse --progress ile zorlanır.

Önemli sınır: Workflow şu an --refresh-explicit parametresini geçmiyor.
Bu yüzden 2296 açık ürünü Actions içinde tek koşuda doldurmak yok.
Yapılacak doğru akış:

1. Cache'i yerelde kategori kategori doldur (yukarıdaki --refresh-explicit komutları).
2. data/explicit_products.json ve data/product_urls.txt dosyalarını commit et.
3. Actions haftalık prices koşusu cache'i kullanır; kategori sayfalarını tazeler.
4. Cache'te olmayan az sayıda açık ürün varsa max_auto_fetch sınırına kadar otomatik çekilir.

Actions içinde de tam refresh istiyorsan workflow'a refresh_explicit girdisi eklenmeli.
Bu bir sonraki iyileştirme; şu an tek seferlik doldurma yerelde yapılmalı.

## 3.1 Kampanya çıktısı

campaigns veya all komutu out/kampanyalar/ altında kampanya başına dosya üretir:

- Dosya: kampanya-<YYYYMMDD-HHMMSS>-<kampanya-slug>.xlsx
- Urunler sayfası: Ürün Adı | İlişki Türü | Gerekli Adet
- İlişki Türü: İlgili ürün; Gerekli Adet boş; URL/fiyat yok.
- Kampanya sayfası: ad, URL, tarih, Katılım Koşulları (tek hücrede sırayla), ürün sayısı.
- Index: out/kampanyalar/kampanyalar_<stamp>.xlsx (ad, dosya, URL, ürün sayısı).
- Kampanya adı Bayios'ta ayrıca girilir; dosya adı/index eşlemesi yol gösterir.
- Aynı ürün adı kampanya içinde tekilleştirilir.

Not: Bu kampanya dosya düzeni ve Katılım Koşulları M3 hedefine taşındı. M2 ürün özellikleri planı (teknik specs + ftc-text, JSON/Excel/CSV) docs/m2-specs-plan.md içinde; M1 ürün tarafı tamamlandı.

## 3.2 Ürün özellikleri (M2)

- Tüm seçili ürünler için PDP'den teknik özellikler + ftc-text teknoloji metinleri çekilir.
- Her koşuda out/catalog.json yazılır; ana products 11. sütununda Ürün Özellikleri (JSON) bulunur.
- Varsayılan format json'dur; Excel/CSV için --format excel|csv|both kullan.
- Specs cache: data/specs_cache.json; yenilemek için --refresh-specs.
- Medya/gif/resim/video indirilmez; sadece metin.

## 4. Kategori kopyalama ve nvim gc

out/categories.toml içinde:

- Başlık/yol satırları ## ile başlar.
- TOML satırları tek # ile başlar.

Bir bloğu seçip config.toml'a yapıştırıp gc ile yorumları açarsan:

- ## başlık satırları # olarak kalır (yorum kalır).
- # [[categories.include]], # slug, # app_category satırları aktif TOML olur.

Örnek:

    ## [L2] Beyaz Eşya > Kurutma Makinesi [config]
    # [[categories.include]]
    # slug = "kurutma-makinesi"
    # app_category = "Kurutma Makinesi"

Tüm dosyayı config.toml'a yapıştırma; sadece istediğin blokları kopyala.

## 5. Kara liste ve ürün listesi (önemli)

- categories.exclude ağaç-duyarlıdır. Bir kategoriyi kapatınca alt kategorileri de kapanır.
- Kara liste explicit URL'ler için de geçerlidir. data/product_urls.txt içindeki bir URL,
  kategorisi kara listedeyse çekilmez ve çıktıya girmez.
- Kategorisi URL'den veya cache'ten çözülemeyen explicit URL'ler, kara liste varsa
  güvenli tarafta kalır ve atlanır. Bunları almak için inline app_category ver veya force = true kullan.
- İstisna: config.toml içinde inline [[products.include]] bloğunda force = true olan ürün
  kara listeye rağmen dahil edilir.
- --only URL manuel istisnadır; o tek URL kara listede olsa bile işlenir.
- missing.txt'i data/product_urls.txt içine yapıştırıp sadece istemediğin kategorileri
  categories.exclude içine yazabilirsin. Kara liste artık ürün listesinden önce gelir.
- Kara liste boşsa explicit URL'lerin tümü seçilir; yine de max_auto_fetch sınırı vardır.
- blog/ ile başlayan URL'ler ve blog kategori düğümleri config'den bağımsız olarak asla alınmaz; force ve --only URL bu kuralı aşamaz. categories.txt/toml'da blog görünmez.

Örnek inline istisna:

    [[products.include]]
    url = "https://www.arcelik.com.tr/..."
    force = true

## 5.1 Progress bar

- Terminal (TTY) ise otomatik açılır.
- GitHub Actions, CI veya TTY olmayan ortamda otomatik kapalıdır; loglar temiz kalır.
- Zorla açmak için --progress, kapatmak için --no-progress kullan.

Örnek görünüm:

    [##########----------] 3/7 kategoriler | 120 urun | 12s | kurutma-makinesi sayfa 2

## 6. Config hızlı bakış

    [categories]
    include_children = false
    exclude = ["tablet", "cep-telefonu", "bilgisayar", ...]

    [[categories.include]]
    slug = "kurutma-makinesi"
    # app_category = "Kurutma Makinesi"

    [products]
    include_file = "data/product_urls.txt"
    max_auto_fetch = 50

    [cache]
    explicit_file = "data/explicit_products.json"
    specs_file = "data/specs_cache.json"

    [campaigns]
    dir = "out/kampanyalar"

    [warranties]
    enabled = true      # prices/all icinde; ayri komut yok

    [output]
    format = "json"     # json | excel | csv | both (json her zaman)

## 7. Sık kullanılan komutlar

    # Kategori dosyaları
    uv run arcelikPriceScrapper list-categories

    # Tek kategori
    uv run arcelikPriceScrapper prices --only buzdolabi --format both

    # Tek ürün URL'si
    uv run arcelikPriceScrapper prices --only https://www.arcelik.com.tr/...

    # Kategori + o kategorinin açık ürünlerini zorla yenile
    uv run arcelikPriceScrapper prices --only kurutma-makinesi --refresh-explicit

    # Tüm config kategorileri + cache
    uv run arcelikPriceScrapper prices --format both --full

    # Sadece specs yenile (tum secili urunler)
    uv run arcelikPriceScrapper specs --refresh-specs --format json

    # Kampanyalar (out/kampanyalar/ altinda kampanya basina dosya)
    uv run arcelikPriceScrapper campaigns

    # Hepsi: urunler + ek garanti + specs + kampanyalar
    uv run arcelikPriceScrapper all --format both

## 8. Test

    uv run pytest --no-cov

## 9. Belgeler

- docs/prd.md
- docs/milestone-plan.md
- docs/m2-specs-plan.md
- docs/spec.md
- docs/adr/0008-garanti-kosullar-dosya-duzeni.md
- docs/adr/0009-urun-id-ve-blog-istisnasi.md
- docs/adr/0010-specs-json-ve-11-sutun.md
