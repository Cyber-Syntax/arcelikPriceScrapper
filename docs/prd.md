# PRD: Arçelik Fiyat Scraper (arcelikPriceScrapper)

Durum: Onaylı v0.6 · Tarih: 2026-11-22 · Dil: Türkçe (kod ve kolonlar İngilizce, Excel başlıkları Türkçe)
Önceki sürüm: v0.5 (2026-11-22). Bu sürüm, ürün ID'sini ve blog istisnasını ekler; M1 uygulamasını yansıtır.
İlgili ADR'ler: ADR-0001 (kategori), ADR-0002 (ürün kimliği), ADR-0003 (tarama/listeler), ADR-0004 (çıktı/teslim), ADR-0005 (ek garanti kaynağı), ADR-0006 (özellikler/cache), ADR-0007 (kampanya formatı), ADR-0008 (garanti entegrasyonu/koşullar/dosya düzeni), ADR-0009 (ürün ID/blog istisnası), ADR-0010 (specs/catalog/11. sütun).

## 0. Yönetici özeti

- Çıktı, Bayios'un 11 sütunlu Excel şablonuna uyar (Ürün ID ilk, Ürün Özellikleri JSON son sütun); CSV aynı şemayla üretilir.
- Kategoriler URL'nin ilk segmentinden değil, sitenin sunucu-render kategori menüsünden (nav ağacı) alınır.
- Ürünler seçili kategori sayfalarından ve 10-50 adetlik açık ürün URL listesinden toplanır; tam sitemap taraması varsayılan değildir.
- Eski/fiyatsız ürünler bir kez taranır, özellikleri JSON cache'e yazılır; haftalık koşu bu ürünler için tekrar istek atmaz.
- Ürün anahtarı ID'dir (varsa); ID yoksa kısa ad kullanılır. Site adı kısa model adıdır; Bayios'taki adla uyuşmazsa config'te name override kullanılır.
- Ana ürün sayfası 11 sütundur (Ürün ID, Ürün Adı, Kategori, fiyatlar, boş Bayios kolonları, Ürün Özellikleri JSON); zaman damgası dosya adında, meta sayfasında ve full/specs çıktılarındadır.
- Ek garanti ayrı komut/dosya değildir; ürün koşusunda statik tablodan çekilip products'a eklenir. Kampanya katılım koşulları tek Excel hücresinde sırayla; kampanya dosyaları out/kampanyalar/ altında kampanya başına üretilir.
- Ürün ID'si kart/PDP'den okunur ve ana products sayfasında ilk sütundadır; blog/ ilk segmentli URL'ler ve blog kategori düğümleri config'den bağımsız olarak asla alınmaz.
- Çıktı adları: ürünler urunler_<YYYYMMDD-HHMMSS>, kampanyalar kampanya-<YYYYMMDD-HHMMSS>-<kampanya-adı>.
- Teslim: GitHub Actions (haftalık + manuel dispatch) → artifact + GitHub Release (data-latest).

### 0.1 v0.3'ten değişenler

| Konu               | v0.3                                  | v0.4                                                |
| ------------------ | ------------------------------------- | --------------------------------------------------- |
| Kategori kaynağı   | Ürün URL'sinin ilk segmenti           | Site nav ağacı (1./2./3. seviye)                    |
| list-categories    | Sitemap'ten türetilen yanlış slug'lar | Gerçek kategori ağacı, seviye ve yol                |
| Ürün anahtarı      | Belirsiz "site adı"                   | Kısa model adı + name override                      |
| Tarama             | Tüm yaprak slug'lar                   | Seçili kategoriler + açık ürün URL'leri             |
| Fiyatsız/eski ürün | Kapsam dışı                           | Açık URL + boş fiyat + cache                        |
| Ürün özellikleri   | v2 notu                               | Açık ürünler için v1/M2                             |
| Ana çıktı          | 10 sütun (scraped_at)                 | 9 sütun (Bayios; v0.6'da 11) + meta                 |
| Teslim             | Artifact                              | Artifact + GitHub Release                           |
| Ek garanti         | Statik tablo                          | Statik tablo korundu; kategori çelişkisi belgelendi |
| CLI / paket yolu   | scrapper / src/scrapper               | arcelikPriceScrapper / src/arcelikPriceScrapper     |

### 0.2 v0.4'ten değişenler

| Konu | v0.4 | v0.5 |
| --- | --- | --- |
| Ek garanti | Ayrı komut/dosya | prices/all ürün koşusunda, products içinde |
| Kampanya koşulları | Kısmi/opsiyonel | Katılım Koşulları listesi ayrıştırılır; tek Excel hücresinde sırayla |
| Kampanya dosya düzeni | Tek workbook içinde per-kampanya sheet | out/kampanyalar/ altında kampanya başına dosya |
| Dosya adları | arcelik_<stamp>... | urunler_<stamp>, kampanya-<stamp>-<kampanya-adı> |

### 0.3 v0.5'ten değişenler

| Konu | v0.5 | v0.6 |
| --- | --- | --- |
| Ürün ID | Yok | data-product-code / JSON-LD / gömülü JSON products[].id; ana products 11 sütun |
| Blog | Kategori olarak çıkabiliyor | blog/ ilk segmenti ve blog düğümleri her zaman dışlanır; categories.toml'da yok |
| Ana products | 9 sütun | 11 sütun (Ürün ID ilk, özellik JSON son) |
| Ürün anahtarı | Ad | ID (varsa), ad fallback |
| M1 | Plan | Uygulandı: ID, blog, garanti entegrasyonu, urunler_ dosya adı |

## 1. Amaç

arcelik.com.tr üzerindeki ürün fiyatlarını, ek garanti fiyatlarını ve kampanyaları Excel/CSV olarak dışa aktaran; GitHub Actions'ta haftalık ve manuel çalışabilen; çıktısı PostgreSQL kullanan Bayios uygulamasının "Excel içe aktar" ekranına elle yüklenebilen bir araç.

Veri yalnızca sahibinin kendi uygulamasında kullanılır. Scraper, Bayios veritabanına doğrudan yazmaz.

## 2. Kapsam

| Sürüm         | İçerik                                                                                                                        |
| ------------- | ----------------------------------------------------------------------------------------------------------------------------- |
| M1 (alpha)    | Nav kategori ağacı, seçili kategori taraması, fiyatlar, ürün ID, blog istisnası, ek garanti (aynı ürün koşusunda), açık ürün URL'leri, Excel/CSV, logging + run_report, Actions iskeleti |
| M2            | Ürün özellikleri: teknik specs + ftc-text teknoloji metinleri; JSON birincil + Excel/CSV yedek; cache |
| M3            | Kampanyalar: katılım koşulları + Bayios 3 sütun + out/kampanyalar dosyaları |
| 1.0.0         | Hata yönetimi oturmuş, kabul kriterleri sağlanmış (bölüm 17)                                                                  |
| v2 (ayrı PRD) | Tüm ürünler için specs/görsel/açıklama, Bayios alt kategorileri, SKU eşleştirme, değişiklik tespiti, cache yönetimi           |

Kapsam dışı (v1): stok, taksit, görsel, tüm ürünler için spec, fiyat geçmişi (Bayios tutuyor), proxy, checkpoint/resume, Playwright, PDF, veritabanı, Bayios'a doğrudan API gönderimi, bayi profilleri.

## 3. Site gerçekleri (2026-11-20 doğrulaması)

Bu bölüm, PRD kararlarının dayandığı ölçülen gerçeklerdir. Kod ve testler bu davranışa göre yazılır.

| Kaynak             | Gerçek                                                                                                                                               |
| ------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------- |
| sitemap.xml        | 4 alt sitemap: PRODUCT 5.693 ürün, CATEGORY 799 sayfa, CATEGORYLANDING 1, CONTENT/BLOG                                                               |
| Ürün sitemap'i     | Ürün URL evreni; her girişte lastmod ve görsel var. Kategori bilgisi vermez.                                                                         |
| Kategori sitemap'i | 799 URL; marka sayfaları (samsung-galaxy-a17, apple), ghost/kampanya sayfaları ve gerçek kategoriler karışık. Hiyerarşi vermez.                      |
| Nav menüsü         | Her sayfada sunucu-render gelen nav#nav-menu-category: 14 üst kategori, 100 ikinci seviye, 183 üçüncü seviye (toplam 297 düğüm, 279 tekil slug). Gerçek kategori kaynağı budur.   |
| Ürün URL'si        | İlk segment kategori değildir. Örnek: /samsung-galaxy-a17/... bir marka sayfasıdır.                                                                  |
| Kart               | div.prd-inner; fiyat .prd-price .prc ve .prc-third; kategori [data-product-hierarchy] (Top/Mid/Leaf); ID/kod [data-product-code]; gömülü JSON products[].id yedeği. |
| PDP                | ol.breadcrumb ile tam hiyerarşi; JSON-LD Product ile fiyat/sku; data-product-code veya gömülü products[].id; #pdp-features-container .feature-item ile teknik özellikler. |
| Fiyat kaynağı      | Kartta perakende + indirimli; PDP'de JSON-LD offers.price (satış) ve priceSpecification ListPrice (liste). Eski .prc-with-oliz seçicileri artık yok. |
| Arama              | /search?text robots.txt tarafından yasak; arama ile ürün bulma otomatikleştirilemez.                                                                 |
| Sayfalama          | ?page=N çalışıyor; 0'dan başlar; son sayfada 0 kart veya tekrar eden kart gelir. Sonuç sayısı "N ürün" metninde.                                     |
| Kampanya koşulları | .promo-acc içindeki "Katılım Koşulları" akordeonunun .acc-body ul > li maddeleri; sıra korunur; tipik 5-10 madde. |
| Blog               | /blog/... ve blog/su-aritma gibi kategori düğümleri fiyat kaynağı değildir; config'den bağımsız dışlanır. |
| Teknoloji metinleri | .pdp-technologies .ftc-item; başlık .ftc-title, açıklama .ftc-text; 1001 KMX 4, 10122 12 kart (1 metinsiz). |

### 3.1 Kritik saha örnekleri

- AFC 341 G1: /buhar-destekli-firin yalnızca 2 kart (S, B1) gösteriyor; G1 yok. /ankastre (1. seviye) 130 kart içinde G1'i gösteriyor. Yani üst kategori sayfası, alt kategori sayfasından daha eksiksiz olabiliyor. G1 kartında fiyat var; PDP JSON-LD 33.999 / 35.499.
- 1001 KMX: hiçbir listing'de yok; yalnızca PDP var. PDP'de Product JSON-LD ve fiyat yok. Breadcrumb: Beyaz Eşya > Kurutma Makinesi > 10 Kg Kurutma Makinesi > 1001 KMX. Kısa ad breadcrumb son öğesinden "1001 KMX" gelir.
- 1001 KMX özellikleri: docs/index.html kaydında 6 grup, 43 özellik var. Örnekler: Kurutma Kapasitesi 10 kg, Akıllı Nem Sensörü Eco Sense, Kurutma Teknolojisi Isı Pompalı, Enerji Sınıfı E.
- 283616 EI: kart hierarchy Beyaz Eşya/Buzdolabı/Alttan Donduruculu Buzdolabı; kart adı 283616 EI; fiyat 104.299 / 84.799.
- /buzdolabi: sayfa 60 ürün diyor; sayfalama 49 kart, kapsam filtresi 43 buzdolabı veriyor. Sayfa 2'de Derin Dondurucu çapraz satışları var; bunlar hedef kategoriye yazılmaz.
- /televizyon: sayfa 0 "17 ürün" diyor ama sayfalama ile 48 tekil ürün geliyor. Sayfa 0 sayısına güvenilmez; tüm TV alt kategorileri için include_children gerekir.
- Ek garanti: statik tablo 55 satır, adlar "2 Yıl EG Bulaşık Mk. (0-6 Ay)"; /ekgaranti kategorisi 49 SKU, adlar "2 Yıl Ek Garanti BULAŞIK (0-6 Ay)"; fiyatlar aynı.
- missing.txt: 4.110 satır; ağırlıklı telefon/tablet/laptop/aksesuar (android-telefon-modelleri 343, tablet 250, laptop 203, kulaklik 180). Telefon/bilgisayar kara listesi gürültünün çoğunu keser.

## 4. Karar kaydı

| #   | Karar                                                                                                                                                                                                                       |
| --- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| D1  | Fiyatlar Decimal (TRY).                                                                                                                                                                                                     |
| D2  | Zaman damgası koşu başlangıcı UTC'dir. Ana ürün sayfası 11 sütundur (Ürün ID ilk, Ürün Özellikleri JSON son); zaman damgası dosya adında, meta sayfasında ve full/specs çıktılarındadır. --with-scraped-at ile ana sayfaya 12. sütun eklenebilir (varsayılan kapalı). |
| D3  | Çıktı formatı json, excel, csv veya both; varsayılan json. JSON (catalog.json) her zaman yazılır; Excel/CSV seçilirse aynı 11 sütunla yedek. |
| D4  | Ürün anahtarı ID'dir (data-product-code/JSON-LD/gömülü JSON); ID yoksa kısa ad (kart aria-label suffix temizlenir veya PDP breadcrumb son öğesi). name override her zaman kazanır. |
| D5  | Perakende fiyat = liste/üstü çizili fiyat; Oliz indirimli fiyat = satış fiyatı; indirim yoksa boş.                                                                                                                          |
| D6  | Kategori izin/kara listesi config.toml'da; CLI --only/--exclude ile override.                                                                                                                                               |
| D7  | Kategori kaynağı nav ağacıdır. app_category varsayılan 2. seviye adıdır; alias ve açık override desteklenir.                                                                                                                |
| D8  | Ek garanti ayrı komut/dosya değildir; prices/all ürün koşusunda statik tablodan gelir ve products çıktısına kind=warranty olarak girer; kategori sabit "Ek Garanti". |
| D9  | Kampanya metadata'sı referanstır; her kampanya için out/kampanyalar/kampanya-<stamp>-<slug>.xlsx ve 3 sütunlu Bayios tablosu üretilir; katılım koşulları ayrı Kampanya sayfasında tek hücrede sırayla; Aktif Kampanya kolonu boş. |
| D10 | Teslim GitHub Release + artifact'tır; manuel indirme veya Bayios API gönderimi yok.                                                                                                                                         |
| D11 | Delist ürünler için işlem yapılmaz.                                                                                                                                                                                         |
| D12 | SQLite yok; açık ürün özellikleri JSON cache'te tutulur.                                                                                                                                                                    |
| D13 | 403/429 retry'ları tükenirse koşu durur; \*.partial yazılır; çıkış kodu 2; Release'e yüklenmez.                                                                                                                             |
| D14 | Logging stderr; run_report.json + meta sayfası.                                                                                                                                                                             |
| D15 | Tek paket: src/arcelikPriceScrapper/\*.py; CLI adı arcelikPriceScrapper.                                                                                                                                                    |
| D16 | Pydantic v2 yalnızca config ve satır doğrulaması için.                                                                                                                                                                      |
| D17 | Boş hücre "dokunma"dır. Scraper bilmediği kolona asla 0 yazmaz.                                                                                                                                                             |
| D18 | Biten indirim elle temizlenir; scraper "temizle" işareti yazmaz.                                                                                                                                                            |
| D19 | Importer kategoriyi yalnızca yeni üründe veya mevcut kategori boşsa yazar (I2).                                                                                                                                             |
| D20 | Aynı ID'ye sahip ürünler tek satırda birleşir (ilk kategori, ilk dolu fiyat, specs). Aynı ad farklı ID ise ayrı satır üretilir ve product_id_conflicts/duplicate_names raporlanır; ID yoksa ad anahtarı. |
| D21 | Tam sitemap taraması varsayılan değildir. categories.include boşsa hata verilir; istenirse list-categories çıktısından include üretilir.                                                                                    |
| D22 | Arama endpoint'i kullanılmaz (robots). İstisna ürünler yalnızca açık URL ile eklenir.                                                                                                                                       |
| D23 | Ürün özellikleri seçili tüm ürünler için taranır (kategoriler + explicit); catalog.json ve ana products 11. sütun JSON; cache'ten okunur; medya indirilmez. |
| D24 | Ana products sayfası 11 sütundur (Ürün ID, Ürün Adı, Kategori, 2 fiyat, 5 boş Bayios kolonu, Ürün Özellikleri JSON); full/meta ayrı sayfalardadır. |
| D25 | Kategori kara listesi ağaç-duyarlıdır (düğüm + tüm alt kategoriler) ve explicit ürün URL'leri için de geçerlidir. İstisna: inline force = true; CLI --only URL manuel istisna.                                                                                                              |
| D26 | Bayi profili yoktur (v1); tek config ve tek çıktı. |
| D27 | Sayfalama: 0 kart -> dur; iki ardışık "yeni kart yok" -> dur. ?page=1 bazı sayfalarda 0'ı tekrarlar; tek tekrar durma sebebi değildir. |
| D28 | Kart hierarchy hedefin kendisi/alt/üst kategorisi değilse ürün çapraz satıştır; dışlanır ve out_of_scope_products sayılır. |
| D29 | --only açık ürünleri seçili app_category'lerle sınırlar; tam koşuda tüm açık ürünler girer. |
| D30 | Kampanya koşulları .promo-acc içindeki Katılım Koşulları akordeonundan .acc-body ul > li sırasıyla alınır; tek Excel hücresinde newline ile yazılır; kırpılmaz. |
| D31 | Ürün çıktısı out/urunler_<YYYYMMDD-HHMMSS>.xlsx; kampanya çıktıları out/kampanyalar/ altında kampanya-<YYYYMMDD-HHMMSS>-<kampanya-slug>.xlsx. |
| D32 | Her kampanya ayrı dosya: Urunler sayfası (Ürün Adı, İlişki Türü, Gerekli Adet) + Kampanya sayfası (ad, URL, tarih, Katılım Koşulları, ürün sayısı). |
| D33 | warranties komutu ve ayrı garanti çıktısı yoktur; garanti prices/all içinde ürünlerle birlikte çekilir. |
| D34 | Ürün ID kaynağı: data-product-id, data-product-code, JSON-LD sku/productID, gömülü products[].id; ana products 11 sütun, ID ilk; garanti satırlarında boş. |
| D35 | blog/ ilk segmentli URL'ler ve blog kategori düğümleri config'den bağımsız olarak asla taranmaz/listelenmez; force ve --only URL bu kuralı aşamaz. |
| D36 | Specs çıktısı: catalog.json her zaman; ana products 11. sütun JSON; Excel/CSV 11 sütun yedek; ayrı _specs dosyası yok. |
| D37 | Teknoloji metinleri .pdp-technologies .ftc-item içindeki .ftc-title + .ftc-text; br newline, small/div metni note veya text içinde parse edilir; medya/gif/resim/video indirilmez. |

## 5. Kategori modeli

### 5.1 Kaynak ve seviyeler

Gerçek kategori ağacı nav#nav-menu-category içindedir. Üç seviye vardır:

- 1. seviye (LV1): Beyaz Eşya, Ankastre, Küçük Ev Aletleri, Televizyon, Elektronik, Isıtma Soğutma, ...
- 2. seviye (LV2): Buzdolabı, Çamaşır Makinesi, Kurutma Makinesi, Bulaşık Makinesi, Ankastre Fırın, Cep Telefonu, Bilgisayar, ...
- 3. seviye (LV3): No Frost Buzdolabı, 10 Kg Kurutma Makinesi, Tablet, Buhar Destekli Fırın, ...

Bayios v1 alt kategori desteklemediği için varsayılan uygulama kategorisi LV2 adıdır. Örnek: "Buzdolabı", "Kurutma Makinesi", "Çamaşır Makinesi", "Bulaşık Makinesi", "Ankastre Fırın".

### 5.2 app_category belirleme sırası

Bir ürünün Kategori hücresi şu sırayla belirlenir:

1. Açık ürün girişinde app_category varsa o kullanılır.
2. Kategori girişinde app_category varsa o kullanılır (TV grubu veya Bayios eski adı gibi istisnalar).
3. Karttaki data-product-hierarchy ayrıştırılır (Top/Mid/Leaf). En derin bilinen düğüm nav ağacında bulunur; onun LV2 atası kullanılır.
4. Bulunamazsa listing sayfasının kendi breadcrumb'ındaki son kategori düğümünün LV2 atası kullanılır.
5. Açık ürünlerde PDP breadcrumb'ının LV2'si kullanılır.
6. Hâlâ bulunamazsa Kategori boş bırakılır ve rapora "category_unresolved" olarak yazılır. Tahmin yürütülmez.

Örnekler:

| Ürün                | Kaynak hierarchy                                                                | Kategori (LV2)                                       | Ad                        |
| ------------------- | ------------------------------------------------------------------------------- | ---------------------------------------------------- | ------------------------- |
| 283616 EI           | Beyaz Eşya/Buzdolabı/Alttan Donduruculu Buzdolabı                               | Buzdolabı                                            | 283616 EI                 |
| 1001 KMX            | Beyaz Eşya/10 Kg Kurutma Makinesi/10 Kg Kurutma Makinesi (kart) veya breadcrumb | Kurutma Makinesi                                     | 1001 KMX                  |
| AFC 341 G1          | Ankastre/Ankastre Fırın/Buhar Destekli Fırın                                    | Ankastre Fırın                                       | AFC 341 G1                |
| Samsung A17         | Elektronik/Android Telefon Modelleri/TECNO (kart) veya breadcrumb               | Cep Telefonu                                         | Samsung A17 8/256 GB Mavi |
| Tablet              | Elektronik/Bilgisayar/Tablet                                                    | Bilgisayar                                           | ürün adı                  |
| Türk Kahve Makinesi | Küçük Ev Aletleri/Kahve Makinesi/Türk Kahve Makinesi                            | Kahve Makinesi (veya override "Türk Kahve Makinesi") | ürün adı                  |

Not: Kart hierarchy'sindeki orta parça bazen LV3 olur (ör. 10 Kg Kurutma Makinesi, Android Telefon Modelleri). Bu yüzden çözümleme "en derin bilinen düğüm → LV2 atası" şeklindedir; düz metin karşılaştırması yeterli değildir.

### 5.3 İstisnalar ve alias

- Televizyon grubu: /televizyon LV1 sayfası sayfa 0'da "17 ürün" der; sayfalama ile 48 tekil ürün gelir. Tüm TV alt kategorileri için include_children = true veya LV2/LV3 düğümleri seçilir; app_category = "Televizyon" override'ı ile Bayios'ta tek "Televizyon" kategorisi oluşur.
- Bayios eski adları: site "Kurutma Makinesi" derken Bayios'ta "Kurutma" kayıtları varsa [categories.aliases] ile eşlenir. Varsayılan alias tablosu boştur; doldurulmazsa site adı yazılır ve importer yeni kategori yaratabilir.
- Aynı ada sahip iki farklı kategori varsa (ör. Ankastre Buzdolabı hem Beyaz Eşya hem Ankastre altında) tam yol (LV1/LV2/LV3) ile eşleşme tercih edilir; belirsizlik raporda gösterilir.

### 5.4 Kara liste

categories.exclude girdileri LV1/LV2/LV3 adı veya slug'ı olabilir; büyük/küçük harf ve Türkçe karakter normalize edilir; \* glob desteklenir. Bir düğüm eşleşirse kendisi ve tüm alt kategorileri kapsam dışıdır.

Örnek: exclude = ["tablet", "cep-telefonu", "bilgisayar"]:

- tablet → yalnızca Tablet LV3'ü (ve varsa altını) kapatır.
- cep-telefonu → Cep Telefonu LV2'sini, Android/iPhone LV3'lerini kapatır.
- bilgisayar → Bilgisayar LV2'sini, Laptop/Tablet/Masaüstü LV3'lerini kapatır.

Kara liste explicit ürün URL'leri için de geçerlidir (D25). data/product_urls.txt içindeki bir URL kategorisi kara listedeyse çekilmez ve çıktıya girmez. Kategorisi çözülemeyen URL'ler kara liste varken atlanır; istisna için inline app_category veya force = true verilir. --only URL manuel istisnadır.

blog/ ile başlayan URL'ler ve blog kategori düğümleri bu kara listeden bağımsız, her zaman dışlanır (D35). force = true veya --only URL bu kuralı aşamaz; blog fiyat kaynağı değildir.

### 5.5 list-categories

Yeni davranış: nav ağacını okur, tek istek atar. Sonucu konsola dökmez; out/categories.txt (tablo) ve out/categories.toml (yorumlu, kopyalanabilir [[categories.include]] blokları) dosyalarına yazar. TOML'de her blok yorumludur; istenen bloğun başındaki "# " kaldırılıp config.toml'a taşınır. [config] mevcut config girdisini, [excluded] kara listeyi gösterir. Varsayılan çıktıda marka, ghost ve blog sayfaları yoktur. --all ile CATEGORY sitemap'inde olup nav'da olmayan slug'lar "nav dışı" olarak txt'ye eklenir; blog/ burada da filtrelenir. --with-counts her düğümün ilk sayfasını çekip "N ürün" sayısını txt'ye yazar (yavaş, opsiyonel). --format excel|csv|both verilirse ayrıca tablo çıktısı da yazılır.

Örnek dosya satırı (categories.txt):

    2    Beyaz Eşya > Buzdolabı    Buzdolabı    buzdolabi    https://...    x

Örnek config bloğu (categories.toml):

    # [L2] Beyaz Eşya > Buzdolabı [config]
    # [[categories.include]]
    # slug = "buzdolabi"
    # app_category = "Buzdolabı"

## 6. Tarama akışı

1. config.toml okunur ve doğrulanır. categories.include boşsa hata verilir (D21).
2. Nav ağacı bir kez çekilir (herhangi bir sayfa; tercihen ana sayfa) ve slug → (LV1, LV2, LV3) haritası kurulur. Ağaç 24 saatlik yerel cache'ten de okunabilir; fiyatlar cache'lenmez.
3. Hedef kategori düğümleri belirlenir: include listesi, exclude ile ağaç-duyarlı çıkarılır. include_children = true ise düğümün tüm alt kategorileri de eklenir; varsayılan false. blog/ düğümleri her durumda dışlanır.
4. Her hedef düğüm için listing sayfaları gezilir: /slug, ?page=1, ?page=2, ...; yeni kart gelmeyince veya 0 kart gelince durulur; max_pages sınırı uygulanır.
5. Kartlardan ad, başlık, URL, ID/kod, hierarchy ve fiyatlar okunur. ID data-product-code; yoksa gömülü JSON products[].id/JSON-LD sku. Aynı URL birden fazla kaynakta görülürse kaynak listesi birleştirilir.
6. Her ürün için Kategori bölüm 5.2'ye göre çözülür. Kart hierarchy hedef düğümün kendisi, alt kategorisi veya üst kategorisi değilse ürün çapraz satış sayılır ve dışlanır (out_of_scope_products); kara listedeki kaynaklar elenir; en az bir izinli kaynak kaldıysa ürün dahil edilir.
7. Açık ürünler data/explicit_products.json cache'inden okunur. Haftalık koşu bu ürünler için istek atmaz; yalnızca specs komutu veya --refresh-explicit isteği atar.
8. Ek garanti statik tablosu aynı ürün koşusunda eklenir (ayrı komut/dosya yok). Kampanya koşulları ve kampanya dosyaları ayrı campaigns komutunda üretilir.
9. Doğrulama: boş fiyat oranı, ID'siz ürün sayısı, aynı adda farklı ID çakışması, çakışan adlar, çözülemeyen kategoriler, listing sonuç sayısı ile parse edilen kart sayısı farkı.
10. Çıktılar yazılır; run_report.json ve meta üretilir. 403/429 abort ise partial yazılır ve Release yapılmaz.

### 6.1 Sayfalama ve durma

- İlk sayfa /slug; sonraki sayfalar ?page=N (N=1,2,...).
- Sayfada 0 kart varsa dur.
- Site bazı kategori sayfalarında aynı sayfayı tekrar eder (ör. /buzdolabi?page=1, sayfa 0'ın aynısı). Bu yüzden tek tekrar durma sebebi değildir; iki ardışık "yeni kart yok" sayfasından sonra durulur. Yeni kart gelen sayfada sayaç sıfırlanır.
- max_pages config'ten (varsayılan 200) gelir.
- Sonuç sayısı "N ürün" metni ile parse edilen tekil kart sayısı karşılaştırılır; fark %10'dan fazlaysa uyarı yazılır. Sayfa 0'daki sayı bazen eksik olabilir (ör. /televizyon 17 der, sayfalama 48 tekil verir); bu yüzden sayı yalnızca uyarı amaçlıdır.

### 6.2 Açık ürünler (10-50 adet)

- URL'ler iki yolla verilir: (a) config.toml'da [[products.include]] (ad/kategori override için), (b) toplu dosya: [products] include_file = "data/product_urls.txt"; her satır bir URL, # yorum. Aynı URL iki yerde varsa inline kayıt önce gelir.
- Kategori kara listesi explicit URL'ler için de geçerlidir; force = true olan inline ürün istisnadır. Kategorisi bilinmeyen URL'ler kara liste varken atlanır.
- İlk kez prices/all koşusunda (veya specs komutuyla) taranır; sonuç data/explicit_products.json dosyasına yazılır ve commit edilir.
- Haftalık prices/all koşusu cache'te olmayan veya fetch = "always" olan açık ürünler için ilk seferde ağ isteği atar; cache'te olanları tekrar çekmez. --refresh-explicit tümünü zorla yeniler. Fetch başarısızsa uyarı verir; config'teki name/category/price ile satır üretir veya ürünü atlar.
- --only verildiğinde açık ürünler yalnızca seçili app_category kümesindeyse ve kara listede değilse çıktıya girer; tam koşuda (--only yok) kara liste dışındaki tümü girer.
- --only bir ürün URL'si de kabul eder (ör. https://www.arcelik.com.tr/10-kg-kurutma-makinesi/1001-kmx-kurutma-makinesi). Bu durumda kategori taraması atlanır; URL doğrudan açık ürün olarak işlenir ve cache'e yazılır.
- specs komutu: --only URL, --only-new, --refresh, --config, --format. Başarısız fetch eski cache kaydını silmez.
- Cache anahtarı normalize edilmiş URL'dir. Kayıt: name, title, category_lv1/lv2/lv3, app_category, price, discounted_price, specs[], scraped_at, content_hash. M1 notu: specs alanı henüz yok; specs M2'de eklenecek.

### 6.3 missing.txt

missing.txt, PRODUCT sitemap'inde olup bu koşuda taranmayan URL'lerin listesidir; blog/ URL'leri filtrelenir; varsayılan olarak yalnızca --report-missing ile üretilir. Amaç, açık ürün listesine aday bulmaktır; kapsam KPI'sı değildir. Bu liste 4.000+ satır olabilir; telefon/bilgisayar kara listesiyle birlikte anlamlı küçülür.

### 6.4 Ürün özellikleri (specs)

Kapsam açık soru: öneri v1'de açık/explicit ürünler; seçili kategori veya tüm katalog ayrı batch. Her ürün için PDP isteği gerekir; medya indirilmez (docs/m2-specs-plan.md).

- Teknik özellikler: #pdp-features-container .feature-item; grup .title; satırlar dl .item içindeki dt/dd.
- Teknoloji metinleri: .pdp-technologies .ftc-item; başlık .ftc-title, metin .ftc-text; 1001 KMX 4 kart, 10122 12 kart (1 metinsiz atlanır).
- br -> newline; small dipnot ayrı note; HTML etiketi temizlenir; boş kart atlanır.
- Teknik özelliklerde (grup, özellik, değer) üçlüsü, feature'larda (title, text) ikilisi tekilleştirilir.
- Değerler ham tutulur; birim dönüşümü yapılmaz.
- catalog.json her zaman: out/catalog.json; ana products 11. sütun JSON; Excel/CSV aynı 11 sütunla yedek.
- Özellik yoksa uyarı; eski cache korunur; medya/gif/resim/video isteği yok.

### 6.5 Kampanya koşulları

- Kaynak: .promo-acc içindeki .acc-item başlığı "Katılım Koşulları" olan akordeon; .acc-body altındaki doğrudan ul > li maddeleri.
- Maddeler kaynak sırasıyla alınır; boş satırlar atılır; aynı metin tekilleştirilir; 5-10 madde tipiktir, kırpılmaz.
- HTML etiketleri temizlenir; metin düzleştirilir; her madde tek satır olacak şekilde boşluklar normalize edilir.
- Çıktı tek hücrede newline ile birleştirilir; Excel'de "Katılım Koşulları" sütunu, wrap text.
- Koşullar Bayios'un 3 sütunlu ürün tablosuna konmaz; kampanya metadata sayfasına/dosyasına yazılır.
- Excel'de tek hücre; istenirse "Metni Sütunlara Böl" ile maddeler ayrı satırlara açılabilir.

Örnek hücre (tek hücre, newline):

    Kampanya, 17-20 Kasım 2026 tarihleri arasında geçerlidir.
    Seçili televizyon modellerinde geçerlidir.
    Kampanya, Arçelik mağazaları ve arcelik.com.tr web sitelerinde geçerlidir.
    Her tüketici kampanyadan 1 kez yararlanabilir.
    Bu kampanya diğer kampanyalar ile birleştirilemez.
    Arçelik Pazarlama A.Ş. kampanya şartlarını değiştirme hakkını saklı tutar.

## 7. Ürün anahtarı ve birleştirme

### 7.1 Ad kuralı

- Kart: aria-label eksi " ürün detaylarını incele"; yoksa .prd-name .t. Boşluklar tek boşluğa indirilir, NBSP temizlenir.
- PDP (açık ürün): breadcrumb son öğesi (ör. "1001 KMX"); yoksa JSON-LD name; yoksa h1 (separator ile); yoksa title (| öncesi).
- ID: data-product-code; yoksa JSON-LD sku/productID veya gömülü products[].id. ID anahtardır; ID yoksa ad anahtarı (ADR-0009).
- Uzun pazarlama adı (ör. "1001 KMX 10 Kg Kurutma Makinesi") title alanında tutulur; anahtar kısa addır.
- name override varsa her zaman kazanır. Bayios'taki ad farklıysa bu alan zorunludur.

### 7.2 Çakışma ve birleştirme

- Aynı ID iki URL'de görülürse tek satır üretilir: kategori ilk izinli kaynaktan, fiyat ilk dolu değerden, specs açık ürün cache'inden, URL/kod full çıktısında ilk kaynaktan.
- Aynı ad farklı ID'lere sahipse satırlar ayrı kalır; bu birleştirme değil, ID ile ayırma kuralıdır. run_report.json'da product_id_conflicts ve duplicate_names (ilk 50) raporlanır; istenirse duplicates.txt yazılır.
- ID yoksa ad anahtarı kullanılır; ID'siz ürün sayısı raporda missing_product_ids altında görünür (ADR-0009).

## 8. Fiyat kuralları

### 8.1 Kart

- Perakende: .prd-price .prc içindeki ilk boş olmayan değer.
- Oliz indirimli: .prc-third içindeki ilk boş olmayan değer.
- İkisi eşitse indirimli boş bırakılır (sahte indirim yazılmaz).
- Kartta fiyat yoksa boş bırakılır; kategoriden gelen ürünler için PDP'ye gidilmez (istek bütçesi). Önemliyse ürün açık listeye eklenir.

### 8.2 PDP / açık ürün

- JSON-LD Product offers.price = satış fiyatı.
- offers.priceSpecification içindeki ListPrice = perakende.
- ListPrice yoksa perakende = offers.price, indirimli boş.
- Product JSON-LD yoksa fiyatlar boş.
- Manuel price / discounted_price override'ı PDP'yi ezer.

### 8.3 Genel

- TR formatı: "56.399 TL", "₺3.099", "1.234,50", "475.00".
- Para birimi yazılmaz; Decimal; CSV iki ondalık; Excel sayısal hücre ve #,##0.00.
- Bilinmeyen fiyat 0 değil, boştur (D17). 0 yazmak Bayios'ta fiyatı sıfırlar.

## 9. Çıktı şeması

### 9.1 products (ana import sayfası, 11 sütun)

| #   | Kolon                    | Scraper  | Not                       |
| --- | ------------------------ | -------- | ------------------------- |
| 1   | Ürün ID                  | doldurur | data-product-code/JSON; garanti boş |
| 2   | Ürün Adı                 | doldurur | Anahtar; kısa ad          |
| 3   | Kategori                 | doldurur | LV2 veya alias; yoksa boş |
| 4   | Perakende Fiyat          | doldurur | Bilinmiyorsa boş          |
| 5   | Oliz İndirimli Fiyat     | doldurur | İndirim yoksa boş         |
| 6   | Fiziksel Stok            | boş      | Asla 0 yazılmaz           |
| 7   | Alış Fiyatı              | boş      |                           |
| 8   | Kredi Kartı Taban Fiyatı | boş      |                           |
| 9   | Nakit Taban Fiyatı       | boş      |                           |
| 10  | Aktif Kampanya           | boş      |                           |
| 11  | Ürün Özellikleri (JSON)  | doldurur | features + specifications JSON |

--with-scraped-at verilirse 12. sütun scraped_at eklenir; varsayılan kapalıdır.

### 9.2 products_full

Ürün ID, Ürün Adı, Kategori, Perakende Fiyat, Oliz İndirimli Fiyat, kind (product|warranty|explicit), code, title, url, category_path, source, scraped_at.

### 9.3 catalog.json ve 11. sütun JSON

catalog.json: out/catalog.json; her zaman yazılır. Üst düzey schema_version, scraped_at, products[]. Her ürün: id, product_name, category, price, discounted_price, currency, source_url, features[], specifications[], kind, scraped_at. Ayrı product_code yok; products.id kullanılır.

features[]: title, text, note (ftc-text; small/div parse edilir). specifications[]: group, name, value.

Ana products 11. sütun: Ürün Özellikleri (JSON); değer {"features": [...], "specifications": [...]}. Excel/CSV aynı 11 sütunla yedek; ayrı _specs dosyası yok.

### 9.4 categories (list-categories)

list-categories ayrıca out/categories.txt ve out/categories.toml yazar; --format verilirse tablo da üretilir. blog/ düğümleri hiçbir çıktıda yer almaz.

level, path, name, slug, url, in_config, excluded, product_count (yalnızca --with-counts).

### 9.5 Kampanyalar ve Bayios dosyaları

Kampanya çıktısı iki katmanlıdır:

- campaigns metadata: campaign_id, name, category, url, date_text, start_date, end_date, conditions, product_count, file, scraped_at. conditions = Katılım Koşulları; tek hücrede newline ayrılmış maddeler.
- campaign_products referans: campaign_id, product_name, product_id, regular_price, website_discounted_price, product_url, scraped_at.
- Bayios ürün tablosu (kampanya başına): Ürün Adı, İlişki Türü, Gerekli Adet. İlişki Türü = İlgili ürün; Gerekli Adet boş; URL/fiyat yok.
- Her kampanya için dosya: out/kampanyalar/kampanya-<stamp>-<slug>.xlsx. Urunler sayfası 3 sütun; Kampanya sayfası ad, URL, tarih, Katılım Koşulları (tek hücre), ürün sayısı.
- Index: out/kampanyalar/kampanyalar_<stamp>.xlsx (Kampanya Adı, Dosya, URL, Ürün Sayısı). CSV: kampanya-<stamp>-<slug>-urunler.csv, ...-kampanya.csv, kampanyalar_<stamp>.csv.
- Kampanya adı Bayios'ta elle girilir; dosya adı/index eşlemesi yol gösterir. Ayrıntı: ADR-0007 + ADR-0008.

### 9.6 meta

key/value: run_id, started_at, finished_at, duration_s, command, app_version, config_hash, git_commit, products, explicit_products, warranty_rows, campaigns, campaign_files, specs_products, specs_rows, features_rows, specs_fetched, blank_prices, duplicate_names, category_unresolved, missing_product_ids, product_id_conflicts, http_status, abort_reason.

### 9.7 Dosyalar

Dosya adları ASCII-güvenlidir; Türkçe karakterler slug'lanır. stamp = YYYYMMDD-HHMMSS (UTC).

Ürün Excel: out/urunler_<stamp>.xlsx. Sayfalar: products, products_full, meta, categories.
Ürün CSV: out/urunler_<stamp>_products.csv, _products_full.csv, _meta.csv, _categories.csv.
JSON: out/catalog.json (her zaman; schema_version, scraped_at, products[]).
Kampanya Excel: out/kampanyalar/kampanyalar_<stamp>.xlsx (index) ve out/kampanyalar/kampanya-<stamp>-<kampanya-slug>.xlsx (Urunler + Kampanya).
Kampanya CSV: out/kampanyalar/kampanya-<stamp>-<kampanya-slug>-urunler.csv ve ...-kampanya.csv; index CSV.
Kategori: out/categories.txt, out/categories.toml.
Abort: aynı adlara _partial eklenir; Release'e yüklenmez.
Ek: run_report.json, missing.txt (opsiyonel), duplicates.txt (opsiyonel).

## 10. CLI

    arcelikPriceScrapper prices
    arcelikPriceScrapper prices --only kurutma-makinesi,buzdolabi
    arcelikPriceScrapper prices --only https://www.arcelik.com.tr/10-kg-kurutma-makinesi/1001-kmx-kurutma-makinesi
    arcelikPriceScrapper prices --exclude tablet,cep-telefonu
    arcelikPriceScrapper prices --format both --out-dir out
    arcelikPriceScrapper prices --report-missing
    arcelikPriceScrapper specs --only https://www.arcelik.com.tr/10-kg-kurutma-makinesi/1001-kmx-kurutma-makinesi
    arcelikPriceScrapper specs --refresh-specs
    arcelikPriceScrapper campaigns
    arcelikPriceScrapper all --format both
    arcelikPriceScrapper list-categories
    arcelikPriceScrapper list-categories --format excel

Ortak: --config config.toml, --format json|excel|csv|both, --out-dir out, --full, --with-scraped-at, --progress, --no-progress, -v. Varsayılan format json.
prices/all: --only (kategori slug/ad veya ürün URL'si), --exclude, --report-missing, --refresh-specs.
specs: --only, --exclude, --refresh-specs, --format.

Kurallar:

- --only/--exclude config'i ezer; --only slug, ad veya ürün URL'si kabul eder.
- --only boşsa config include kullanılır; ikisi de boşsa hata.
- Açık ürünler için haftalık koşu ağ isteği atmaz; specs komutu atar.
- ID'siz ürünler raporda sayılır; aynı adda farklı ID varsa product_id_conflicts uyarısı yazılır.
- warranties komutu yoktur; ek garanti prices/all içinde ürünlerle birlikte çekilir.
- all = prices (specs dahil) + campaigns. specs komutu ayrıca specs cache'ini yeniler.
- catalog.json her zaman yazılır; Excel/CSV yedeği --format ile üretilir; ana products 11 sütun.
- specs medya indirmez; sadece metin.
- campaigns çıktıları out/kampanyalar/ altında kampanya başına dosya olarak yazılır.

M1 notu: specs ayrıştırma ve specs komutu M2'dedir. M1'de cache'te olmayan açık ürünler ilk prices koşusunda bir kez çekilir; --refresh-explicit tümünü zorlar. M2 kapsamı ve JSON şeması docs/m2-specs-plan.md'de onaylandı ve uygulandı.

## 11. Config

    [http]
    concurrency = 2
    delay_min = 0.5
    delay_max = 1.5
    timeout = 20
    retries = 4
    max_pages = 200

    [output]
    format = "json"              # json | excel | csv | both (json her zaman)
    dir = "out"
    warranty_category = "Ek Garanti"
    with_scraped_at = false      # ana products 11 sütun kalsın; opt-in 12. sütun

    [categories]
    include_children = false     # seçili düğümün alt kategorileri de taransın mı
    exclude = ["tablet", "cep-telefonu", "bilgisayar", "laptop", "kulaklik", "akilli-saat"]

    [categories.aliases]
    # "Kurutma Makinesi" = "Kurutma"   # Bayios eski adı; boşsa site adı yazılır

    [[categories.include]]
    slug = "buzdolabi"
    # app_category = "Buzdolabı"       # varsayılan: LV2 adı

    [[categories.include]]
    slug = "kurutma-makinesi"

    [[categories.include]]
    slug = "camasir-makinesi"

    [[categories.include]]
    slug = "bulasik-makinesi"

    [[categories.include]]
    slug = "ankastre-firin"

    [[categories.include]]
    slug = "turk-kahve-makinesi"
    app_category = "Türk Kahve Makinesi"   # LV2 Kahve Makinesi; Bayios'ta ayrı kategori

    # TV: LV1 sayfası sayfa 0'da 17 der, sayfalama ile 48 tekil verir; alt kategoriler için include_children = true yap
    # [[categories.include]]
    # slug = "televizyon"
    # app_category = "Televizyon"
    # include_children = true

    [cache]
    explicit_file = "data/explicit_products.json"
    specs_file = "data/specs_cache.json"

    [campaigns]
    enabled = true
    dir = "out/kampanyalar"

    [warranties]
    enabled = true               # prices/all icinde; ayri komut yok

    [products]
    include_file = "data/product_urls.txt"   # her satirda bir URL
    default_specs = true
    default_fetch = "once"
    max_auto_fetch = 50               # tek kosuda otomatik eksik acik urun siniri

    # Istisna: ad/kategori override'i gereken tek urun
    [[products.include]]
    url = "https://www.arcelik.com.tr/10-kg-kurutma-makinesi/1001-kmx-kurutma-makinesi"
    name = "1001 KMX"            # Bayios'taki ad; boşsa breadcrumb son öğesi
    # app_category = "Kurutma Makinesi"
    # price = 47500.00                   # manuel fiyat; boşsa PDP'den, yoksa boş
    specs = true
    fetch = "once"               # once | always
    # force = true               # kara listeye ragmen dahil et

Notlar:

- exclude ağaç-duyarlıdır; bilgisayar yazınca Laptop/Tablet/Masaüstü de gider.
- include_children varsayılan false; LV1 seçip tüm altını istiyorsan true yap.
- app_category yalnızca istisnalar için (TV, eski Bayios adı) kullanılır.
- products.include ve include_file cache'te yoksa ilk haftalık koşuda bir kez çekilir; sonra cache'ten okunur. fetch = "always" her koşuda çeker. --only kategori verildiğinde yalnızca o kategoriye ait açık ürünler çekilir; diğerleri atlanır.

## 12. Hata yönetimi, log ve rapor

- Logging standart logging, stderr; seviye -v ile DEBUG.
- Progress bar: TTY'de otomatik açık; GitHub Actions/CI veya TTY olmayan ortamda otomatik kapalı. --progress zorlar, --no-progress kapatır.
- 403/429: üstel backoff; retry tükenirse AbortRun; tüm koşu durur; toplanan veri \_partial yazılır; çıkış kodu 2; Release yapılmaz.
- Tek sayfa 5xx/parse hatası: loglanır, koşu sürer, raporda sayılır.
- Boş perakende fiyat oranı %1'i geçerse uyarı.
- Kategori çözülemeyen ürün oranı %1'i geçerse uyarı; liste rapora.
- Aynı ID birleşir; aynı ad farklı ID ayrı satır + uyarı; duplicates.txt.
- ID'siz ürün: missing_product_ids uyarısı; ID kaynağı sayfa yapısına bağlı.
- Açık ürün cache yok/bozuk: uyarı; fetch yok; config alanlarıyla satır veya atla.
- Spec fetch/parse hatası: uyarı; eski cache korunur; satır JSON'suz devam eder.
- Garanti tablosu alınamazsa uyarı; ürün koşusu sürer; warranty_rows=0.
- Kampanya sayfası hatası: uyarı; koşu sürer.
- Katılım Koşulları parse edilemezse hücre boş + uyarı; kampanya ürün tablosu ve dosya yine yazılır.
- run_report.json: süre, komut, config hash, HTTP durum sayaçları, kategori bazında ürün, missing, boş fiyat, çakışma, abort nedeni, exit code.
- $GITHUB_STEP_SUMMARY özeti.

## 13. GitHub Actions ve teslim

- Tetikleyiciler:
  - schedule: haftalık, Pazartesi 03:00 UTC.
  - workflow_dispatch: command (prices|all|specs|campaigns|list-categories), only, format.
  - issues: labeled scrape:<slug> opsiyonel; yalnızca yazma yetkisi olanlar; issue gövdesi parse edilmez.
- concurrency: tek koşu; cancel-in-progress false.
- permissions: contents: write (Release için), actions: read.
- timeout-minutes: 90; hedef süre < 30 dk.
- Adımlar: checkout → setup-python 3.12 → pip install . → komut → upload-artifact (14 gün) → Release (yalnızca başarılıysa).
- Release: tag data-latest; out/catalog.json, out/urunler_<stamp>* ve out/kampanyalar/** dosyaları, run_report.json, missing/duplicates (varsa); overwrite.
- Manuel: gh workflow run scrape.yml -f command=prices -f only=kurutma-makinesi -f format=both
- Public repo notları:
  - Release ve artifact herkese görünür; fiyatlar zaten sitede public. Yine de iş verisi sayılıyorsa private repo/self-hosted düşünülmeli.
  - 60 gün hareketsizlikte zamanlanmış workflow kapanır; düzenli commit veya elle koşu.
  - Public repolarda Actions dakikası sınırsız; hosted runner 6 saat; hedef < 30 dk.
- Risk: GitHub datacenter IP'leri 403 alabilir; M1'de erken test; sorunda self-hosted runner veya yerel cron.

## 13.1 Bayios importer bağımlılıkları (uygulama tarafı)

| #   | Değişiklik                                                        | v0.6 durumu                                                                                                                                  |
| --- | ----------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------- |
| I1  | scraped_at kolonunu oku; tarih alanlarında now yerine bunu kullan | Ana products 11 sütun (Ürün ID + özellik JSON) olduğu için v1'de zorunlu değil. products_full kullanılırsa opsiyonel. Zaman damgası dosya adı/meta ile de izlenebilir. |
| I2  | Kategoriyi yalnızca yeni üründe veya mevcut kategori boşsa yaz    | Korunur; zorunlu. Aksi halde elle düzeltilen kategori her importta ezilir.                                                                   |
| I3  | else dalındaki cost_price/dealer pricing tekrarını temizle        | Opsiyonel temizlik.                                                                                                                          |
| I4  | Ürün kodu/SKU ile eşleştirme                                      | v1'de products.id kullanılıyor; ayrı SKU eşleştirmesi v2'de değerlendirilecek.                                                                 |

Yayın öncesi kontrol:

- 11 sütunlu Excel (Ürün ID ilk, özellik JSON son), Bayios preview_product_import ekranından hatasız geçiyor mu?
- Çıktıdaki her Kategori adı Bayios'ta mevcut mu, yoksa yeni kategori yaratması kabul ediliyor mu?
- "Kurutma" / "Kurutma Makinesi" gibi eski-yeni ad farkları alias veya yeniden adlandırma ile çözüldü mü?

## 14. Uyum ve etik

- robots.txt: /search?text, /promotions*, /*productList, /_?sort=_, /_?q=_, /\*variant ve benzerleri çağrılmaz; ?page=N serbesttir.
- Arama endpoint'i yasak olduğu için "arama ile bul" otomasyonu yoktur; istisnalar açık URL ile eklenir.
- Tarayıcı taklidi (impersonate=chrome) bot korumasını aşmak anlamına gelebilir; düşük hız, rastgele gecikme ve 403/429'da durma zorunludur.
- Proxy rotasyonu yok. Kullanım şartlarının otomatik erişim hükümleri sahibi tarafından kontrol edilmelidir.

## 15. Riskler ve önlemler

| Risk                                                               | Önlem                                                 |
| ------------------------------------------------------------------ | ----------------------------------------------------- |
| Actions IP'lerinde 403                                             | Erken test, self-hosted/yerel cron, düşük concurrency |
| Nav etiketleri tutarsız (ör. Buhar/Standart fırın yer değiştirmiş) | Tam yol eşleşmesi, PDP breadcrumb fallback, rapor     |
| Kart hierarchy eksik/yanlış                                        | Listing breadcrumb fallback, rapor                    |
| Ürün ID eksik/yanlış                                               | ID fallback + missing_product_ids raporu; name override |
| Bayios kategori adı farklı (Kurutma vs Kurutma Makinesi)           | alias tablosu veya Bayios'ta yeniden adlandırma       |
| Açık ürün URL'si değişir/kaldırılır                                | Cache uyarısı; eski kayıt korunur; config güncellenir |
| missing.txt çok büyük                                              | Opsiyonel rapor; kara listelerle küçült; KPI yapma    |
| Release public                                                     | Fiyatlar public; hassas veri koyma                    |
| Spec HTML değişir                                                  | Fixture testleri; eski cache korunur                  |
| Aynı ad iki ürün                                                   | İlk kayıt + uyarı; SKU v2                             |

## 16. Sorun kaydı ve çözümleri

| #   | Sorun (kaynak)                                          | Çözüm                                             | ADR       |
| --- | ------------------------------------------------------- | ------------------------------------------------- | --------- |
| S1  | list-categories yanlış slug'lar gösteriyor (sorun.md)   | Nav ağacı; marka/ghost sayfaları varsayılan dışı  | 0001      |
| S2  | G1 alt kategoride görünmüyor (sorun.md)                 | Açık ürün URL'si; gerekirse üst kategori taraması | 0002/0003 |
| S3  | 1001 KMX fiyatsız, sadece PDP (sorun.md)                | Boş fiyat + specs cache                           | 0002/0006 |
| S4  | Telefon/bilgisayar istenmiyor (sorun.md)                | Ağaç-duyarlı exclude                              | 0003      |
| S5  | Tablet komple kara liste (sorun.md)                     | exclude tablet                                    | 0003      |
| S6  | Ek garanti statik tablo vs kategori çelişkisi (todo.md) | Statik tablo kanonik                              | 0005      |
| S7  | Zaman damgası (todo.md)                                 | Dosya adı + meta + full                           | 0004      |
| S8  | Bayios'un güncel CSV'yi çekmesi (todo.md)               | GitHub Release data-latest                        | 0004      |
| S9  | 901 KMX gibi eski ürünler (todo.md)                     | Açık URL listesi                                  | 0002      |
| S10 | Tüm ürün kategorileri (todo.md)                         | Nav ağacı + list-categories                       | 0001      |

## 17. Kabul kriterleri

M1 (alpha):

- list-categories varsayılan çıktıda 14 LV1 ve gerçek LV2/LV3 ağacını gösterir; samsung-galaxy-a17 gibi marka sayfaları varsayılan listede yoktur.
- prices, seçili kategorilerle hatasız biter; 403/ban yok; Actions'ta da çalışır.
- Ana products sayfası tam 11 sütundur (Ürün ID ilk, Ürün Özellikleri JSON son); Fiziksel Stok/Alış/Kredi/Nakit/Aktif Kampanya boştur; 0 yazılmaz.
- Kart/PDP ürünlerinde ID dolu; blog/ URL'leri ve blog kategori düğümleri çıktıda/kategorilerde yok; ID'siz ürünler raporda.
- Telefon/tablet/bilgisayar kara listedeyse çıktıda bu kategorilerden ürün yoktur.
- Aynı ID'ye sahip birden fazla satır products sayfasında yoktur; aynı ad farklı ID ayrı satır ve raporda.
- Boş perakende fiyat oranı < %1; kategori çözülemeyen ürün oranı < %1.
- run_report.json ve meta sayfası dolu; exit code 0.
- Ek garanti ayrı komut/dosya olmadan prices/all içinde gelir; 55 satır, kategori "Ek Garanti", statik tablo adlarıyla; products'ta kind=warranty.
- Ürün dosyaları out/urunler_<stamp> adıyla yazılır.

M2 (ürün özellikleri):

- 1001 KMX: 4 teknoloji metni + 6 grup/43 teknik özellik.
- 10122: 12 teknoloji kartı (1 metinsiz atlanır) + 6 grup/42 teknik özellik.
- catalog.json ve ana products 11. sütun JSON aynı veriyi taşır; Excel/CSV 11 sütun yedek.
- ftc-text br -> newline, small -> note; HTML etiketi yok.
- Medya/gif/resim/video indirilmez; ikinci koşu cache'ten gelir.

M3 (kampanyalar):

- Kampanyalar out/kampanyalar/ altında kampanya başına dosya; Bayios ürün tablosu 3 sütun; products'ta kampanya kolonu boş.
- Katılım Koşulları: 5-10 madde sırayla tek Excel hücresinde; HTML etiketleri temiz; kırpılmaz.

  1.0.0:

- Üst üste 10 başarılı Actions koşusu; abort yolu test edilmiş; partial Release'e yüklenmiyor.
- Nav, kart, PDP, teknik spec/feature ve garanti için fixture testleri.
- Üretilen Excel, Bayios preview_product_import'tan hatasız geçer (sözleşme testi).
- Tek kategori koşusu dakikalar içinde biter; tam seçili set < 30 dk.

## 18. Açık sorular ve aksiyonlar

1. Bayios'ta mevcut "Kurutma" kayıtları "Kurutma Makinesi" olarak mı güncellenecek, yoksa [categories.aliases] mi kullanılacak? Karar verilene kadar site adı yazılır; alias boş. Cevap: sitedeki kategori adı neyse onu kullanalım.
2. Ana products sayfasına 12. sütun (scraped_at) eklenmesi Bayios importer tarafından yok sayılıyor mu? Doğrulanana kadar 11 sütun (ID + JSON); --with-scraped-at opt-in. cevap: şu an scraped_at bayios tarafından bilinmiyor, onu şimdilik eklemeyelim.
3. Bayios'un tam kategori listesi paylaşılırsa app_category eşlemesi birebir doğrulanır; paylaşılmazsa alias/override ile yönetilir. cevap: websitesindekileri kullan, bayios'da güncellerim.
4. Televizyon ve Türk Kahve Makinesi kapsamda mı? TV için LV1 + include_children veya LV2/LV3 + app_category = "Televizyon"; Türk kahvesi için app_category = "Türk Kahve Makinesi" gerekir. cevap: direkt Televizyon ve Kahve Makinesi olarak genel kategori olsun, alt kategoriler sonra.
5. Açık ürün listesi (10-50 URL) ve Bayios'taki birebir adları netleşmeli; name override için gerekli. CEVAP: örn olarak 1000 KMX, 901 KMP IG vb. ürün isimleri websitesinden olsun, bayios'ta oradakileri kullanıyor zaten, aynı ürün adı olur.
6. Ek garanti satırları ana products import'una mı girecek, ayrı sheet mi olacak? Karar: ayrı komut/dosya yok; prices/all içinde ana products, kategori "Ek Garanti".
7. GitHub Release public olacak; fiyatların public olması kabul ediliyor mu? Websitesi zaten public, legal olarak sorun yok. Te sorun, alış fiyatı public repo asla commit edilemez!!!! (Şu an zaten hiç öyle bir şey yok)
8. Actions IP'lerinde 403 riski erken test edilmeli; gerekirse self-hosted runner.
9. M2 specs kapsamı: tüm seçili ürünler (kategoriler + explicit). Karar verildi.
10. Specs çıktı düzeni: catalog.json her zaman, ana products 11. sütun JSON, Excel/CSV 11 sütun yedek. Karar verildi.
11. ftc-text small/div: parse edilir; small note alanına alınır. Karar verildi.
12. Format: json|excel|csv|both; varsayılan json; JSON her zaman. Karar verildi.
13. product_code yok; products.id kullanılır. Fiyat JSON'da sayı. Karar verildi.

## 19. Kaynaklar

- docs/prd.md (bu dosya)
- docs/adr/0001-kategori-kaynagi-ve-esleme.md
- docs/adr/0002-urun-kimligi-ve-istisna-urunler.md
- docs/adr/0003-tarama-kapsami-ve-kara-liste.md
- docs/adr/0004-cikti-ve-teslim.md
- docs/adr/0005-ek-garanti-kaynagi.md
- docs/adr/0006-urun-ozellikleri-ve-cache.md
- docs/adr/0007-kampanya-cikti-formati.md
- docs/adr/0008-garanti-kosullar-dosya-duzeni.md
- docs/adr/0009-urun-id-ve-blog-istisnasi.md
- docs/adr/0010-specs-json-ve-11-sutun.md
- docs/spec.md (Bayios çoklu export/import planı)
- docs/m2-specs-plan.md (scraper M2 specs planı)
- docs/milestone-plan.md
- docs/sorun.md, docs/todo.md, docs/whitelist.md, docs/kampanya-cek.md, docs/robots.txt (tarihsel girdi)
- Canlı doğrulama: 2026-11-20, arcelik.com.tr; kayıtlı PDP: docs/index.html
