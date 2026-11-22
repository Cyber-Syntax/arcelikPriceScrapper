# Milestone Plan — arcelikPriceScrapper

Durum: v0.6 · Tarih: 2026-11-22 · M1 kod uygulaması tamam (canlı doğrulama bekliyor)
İlgili: docs/prd.md, docs/adr/0008-garanti-kosullar-dosya-duzeni.md, docs/adr/0009-urun-id-ve-blog-istisnasi.md, docs/adr/0010-specs-json-ve-11-sutun.md

## 0. Özet

| Milestone | Durum | Ana kapsam |
| --- | --- | --- |
| M1 (alpha) | Kod uygulandı; canlı doğrulama bekliyor | Kategori ağacı, ürün fiyatları, ürün ID, blog istisnası, ek garanti entegrasyonu, açık ürün cache/kara liste, 10 sütunlu Excel/CSV (M2'de 11), progress, Actions iskeleti |
| M2 | Kod uygulandı; canlı doğrulama bekliyor | Teknik specs + ftc-text; catalog.json + 11. sütun JSON; Excel/CSV yedek; cache |
| M3 | Ertelendi | Kampanya koşulları, kampanya başına dosya, Bayios 3 sütunlu tablo |
| 1.0.0 | Planlandı | Sözleşme testleri, 10 ardışık Actions koşusu, hata yolu |
| v2 | Ayrı PRD | Tüm katalog specs/medya, alt kategoriler, SKU eşleştirme, değişiklik tespiti |

## 1. M1 (alpha)

### 1.1 Tamamlananlar

- [x] Nav kategori ağacı (14 LV1 / 100 LV2 / 183 LV3) ve list-categories
- [x] Seçili kategori taraması, sayfalama, çapraz satış filtresi
- [x] Kart/PDP fiyat ayrıştırma, 10 sütunlu Bayios products (M2'de 11; Ürün ID ilk sütun)
- [x] Ürün ID ayrıştırma (data-product-code, JSON-LD, gömülü JSON) ve products_full
- [x] ID anahtarı: aynı ID tek satır; aynı ad farklı ID ayrı satır + rapor
- [x] blog/ URL ve blog kategori düğümlerinin her durumda dışlanması
- [x] Açık ürün URL dosyası/cache, kara liste, force istisnası
- [x] Progress bar (TTY açık, CI kapalı)
- [x] GitHub Actions iskeleti, artifact/Release
- [x] Excel/CSV both, meta, run_report

### 1.2 Yeni kararlarla M1'e girenler

- [x] Ek garanti statik tablosunun prices/all içinde çekilmesi; ayrı warranties komutu/sheet'i kaldırılması
- [x] Ürün çıktılarının out/urunler_<YYYYMMDD-HHMMSS> adlandırmasına geçmesi
- [x] Ürün ID'sinin ana products ve products_full çıktısına eklenmesi
- [x] blog/ URL'lerinin ve blog kategori düğümlerinin dışlanması
- [x] Çıktı şeması/CLI/config dokümanlarının yeni adlarla hizalanması

### 1.3 M1 kabul kriterleri

- [ ] list-categories 14 LV1 ve gerçek LV2/LV3 ağacını gösterir; marka/ghost sayfaları varsayılan dışı.
- [ ] prices seçili kategorilerde 403/ban olmadan biter; Actions'ta çalışır (canlı doğrulama bekliyor).
- [x] M1 products 10 sütun; M2'de 11. sütun JSON eklendi; ID ilk; 0 yazılmaz; ID'siz ürün raporda.
- [x] Aynı ID tek satır; aynı ad farklı ID ayrı satır + uyarı.
- [x] blog/ URL'leri ve blog kategori düğümleri çıktıda/kategorilerde yok.
- [x] Ek garanti 55 satır, kategori "Ek Garanti", ayrı komut/dosya yok.
- [x] Kara liste explicit URL'lerde de geçerli; force yalnızca istisna.
- [x] Ürün dosya adı urunler_<stamp>; meta ve run_report dolu (yerel test).
- [ ] Actions'ta 10 sütunlu Excel ve yeni akış canlı doğrulanır.

## 2. M2 — Ürün özellikleri (specs)

Durum: Kod uygulandı; canlı doğrulama bekliyor. Ayrıntı: docs/m2-specs-plan.md.

### 2.1 Kapsam ve ortak veri modeli

- [x] Kapsam: seçili tüm ürünler (kategoriler + explicit/açık ürünler).
- [x] Ortak model: id, product_name, category, price, discounted_price, currency, source_url, features, specifications, scraped_at. Ayrı product_code yok; products.id kullanılır.
- [x] ID anahtarı; ID yoksa normalize URL; para Decimal.
- [x] JSON schema_version, scraped_at, products[]; catalog.json her zaman.
- [x] Medya alanı yok (gif/resim/video indirilmez).

### 2.2 Teknik özellikler

- [x] #pdp-features-container .feature-item içindeki .title ve dl .item dt/dd okunur.
- [x] 1001 KMX: 6 grup / 43 satır; 10122: 6 grup / 42 satır.
- [x] Masaüstü/mobil tekrarı (group, name, value) ile tekilleştirilir.
- [x] Değerler ham tutulur; birim dönüşümü yapılmaz.

### 2.3 Teknoloji metinleri (ftc-text)

- [x] .pdp-technologies .ftc-item içindeki .ftc-title + .ftc-text okunur.
- [x] 1001 KMX: 4 kart; 10122: 12 kart (1 tanesi metinsiz, atlanır).
- [x] br -> newline; small dipnotu note alanına; HTML etiketi temizlenir.
- [x] Aynı title+text tekilleştirilir; boş kart atlanır.
- [x] gif/resim/video indirilmez; metin v1 için yeterli.

### 2.4 Export: catalog.json + 11. sütun JSON

- [x] catalog.json: out/catalog.json; schema_version + scraped_at + products[]; her zaman yazılır.
- [x] Ana products 11 sütun: son sütun Ürün Özellikleri (JSON); features+specifications aynı hücrede.
- [x] --with-scraped-at 12. sütun.
- [x] Excel/CSV, seçilen formatta aynı 11 sütunla yedek.
- [x] output.format: json | excel | csv | both; varsayılan json; JSON her durumda.
- [x] CSV UTF-8 BOM + doğru escaping.

### 2.5 Cache, istek bütçesi ve testler

- [x] Specs cache: ürün ID/URL anahtarı; bir ürün için bir PDP isteği.
- [x] İkinci specs koşusunda 0 PDP isteği; --refresh-specs cache'i zorlar.
- [x] Başarısız fetch eski cache'i silmez; uyarı.
- [x] Fixture: index.html 4 feature/6 grup/43 spec; 10122.html 12 kart (1 boş)/11 feature/6 grup/42 spec.
- [x] JSON round-trip; Excel/CSV details_json aynı veriyi verir.
- [x] Medya isteği 0.

### 2.6 M2 kabul kriterleri

- [x] features ve specifications ayrı; catalog.json ve 11. sütunda iç içe.
- [x] ftc-text metinleri sıralı, dipnotlu (small/div) ve eksiksiz.
- [x] 1001 KMX 4 teknoloji + 6/43 teknik; 10122 11 teknoloji (12 karttan 1 boş) + 6/42.
- [x] catalog.json, Excel/CSV ve 11. sütun aynı veriyi taşır.
- [x] Medya indirilmez; ikinci koşu cache'ten gelir.
- [x] Ana products 11 sütun; --with-scraped-at 12; Bayios yeni şemayı destekler.

## 3. M3 — Kampanyalar

Durum: M2'den taşındı; şimdilik ertelendi. Bayios kampanya detayı hazır olunca uygulanacak.

### 3.1 Katılım koşulları

- [ ] .promo-acc "Katılım Koşulları" akordeonundan .acc-body ul > li maddelerini sırayla ayrıştırma
- [ ] HTML temizleme, boşluk normalizasyonu, boş/tekrar madde eleme
- [ ] 5-10 maddeyi kırpmadan tek Excel hücresinde newline ile yazma
- [ ] Koşullar boşsa uyarı; kampanya yine de dosya/index içinde
- [ ] Fixture testi: örnek HTML'deki 6 madde sırayla ve eksiksiz

### 3.2 Kampanya dosya düzeni

- [ ] out/kampanyalar/ altında kampanya başına dosya
- [ ] Ad: kampanya-<YYYYMMDD-HHMMSS>-<kampanya-slug>.xlsx
- [ ] Urunler sayfası: Ürün Adı, İlişki Türü, Gerekli Adet
- [ ] Kampanya sayfası: ad, URL, tarih, Katılım Koşulları (tek hücre), ürün sayısı
- [ ] Index: kampanyalar_<stamp>.xlsx (ad, dosya, URL, ürün sayısı)
- [ ] CSV: kampanya-<stamp>-<slug>-urunler.csv ve ...-kampanya.csv
- [ ] Ürünü olmayan kampanya da koşullarıyla dosya alır

### 3.3 M3 kabul kriterleri

- [ ] Kampanya ürün tablosu 3 sütun; İlişki Türü "İlgili ürün"; Gerekli Adet boş.
- [ ] Katılım Koşulları 5-10 madde sırayla tek hücrede; HTML etiketi yok.
- [ ] Her kampanya için out/kampanyalar/ altında dosya; index eşlemesi doğru.
- [ ] products'ta kampanya kolonu boş; kampanya verisi ayrı dosyada.

## 4. 1.0.0

- [ ] Üst üste 10 başarılı Actions koşusu
- [ ] Abort/403/429 yolu testli; partial Release'e yüklenmiyor
- [ ] Nav, kart, PDP, specs/features, koşullar, garanti, kampanya dosyası için fixture testleri
- [ ] Excel, JSON specs, Bayios preview_product_import ve kampanya import sözleşme testleri
- [ ] Tek kategori < 5 dk; tam seçili set < 30 dk

## 5. v2 (ayrı PRD)

- Tüm katalog için specs ve medya/görsel/açıklama
- Bayios alt kategori desteği
- SKU/ürün kodu eşleştirme
- Değişiklik tespiti, cache yönetimi
- Bayi profilleri

## 6. Bu sürümde değişen kararlar

1. Ek garanti ayrı komut/dosya olmaktan çıktı; prices/all içinde ürünlerle birlikte.
2. Kampanya katılım koşulları ayrıştırılacak; tek Excel hücresinde sırayla.
3. Kampanya çıktıları out/kampanyalar/ altında kampanya başına dosya.
4. Ürün dosyaları urunler_<tarih-saat>; kampanya dosyaları kampanya-<tarih-saat>-<kampanya-adı>.
5. ADR-0007'nin 3 sütun formatı korunuyor; dosya düzeni ADR-0008 ile güncellendi.
6. Ürün ID'si ana products ilk sütunu; 10 sütunlu çıktı (ADR-0009).
7. blog/ URL'leri ve blog kategori düğümleri config'den bağımsız dışlanır (ADR-0009).
8. M2 ürün özellikleri: catalog.json her zaman; ana products 11. sütun JSON; Excel/CSV yedek; ftc-text metinleri v1'de alınır.
9. Kampanyalar M3'e taşındı; şimdilik ertelendi.

## 7. Bağımlılıklar ve riskler

- [ ] Koşul HTML'i değişebilir; fixture/gerçek HTML testi gerekir.
- [ ] Kampanya adı slug'u Türkçe karakter/uzunluk; tam ad index ve Kampanya sayfasında.
- [ ] Garanti statik tablosu adları değişirse Bayios eşleşmesi bozulur.
- [ ] Çok kampanya dosyası disk/artifact boyutunu artırır.
- [ ] Actions 403 riski; erken test.
- [ ] Specs için PDP isteği ürün başına bir istek; kapsam ve rate-limit netleşmeli.
- [ ] ftc-text HTML'i değişebilir; fixture testi gerekir.
- [ ] JSON şeması Bayios ile hizalanmalı; Excel/CSV details_json yedeği bozulmamalı.
- [ ] ID'siz ürün / aynı adda farklı ID; raporlanıyor, elle kontrol.
- [ ] Bayios importer 10 sütuna güncellenmeli; eski 9 sütun import'u kırılabilir.
