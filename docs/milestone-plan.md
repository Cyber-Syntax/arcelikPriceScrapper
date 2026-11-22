# Milestone Plan — arcelikPriceScrapper

Durum: v0.6 · Tarih: 2026-11-22 · M1 kod uygulaması tamam (canlı doğrulama bekliyor)
İlgili: docs/prd.md, docs/adr/0008-garanti-kosullar-dosya-duzeni.md, docs/adr/0009-urun-id-ve-blog-istisnasi.md

## 0. Özet

| Milestone | Durum | Ana kapsam |
| --- | --- | --- |
| M1 (alpha) | Kod uygulandı; canlı doğrulama bekliyor | Kategori ağacı, ürün fiyatları, ürün ID, blog istisnası, ek garanti entegrasyonu, açık ürün cache/kara liste, 10 sütunlu Excel/CSV, progress, Actions iskeleti |
| M2 | Planlandı | Kampanya koşulları, kampanya başına dosya, Bayios 3 sütunlu tablo, ürün specs/cache |
| 1.0.0 | Planlandı | Sözleşme testleri, 10 ardışık Actions koşusu, hata yolu |
| v2 | Ayrı PRD | Tüm ürün specs/görsel, alt kategoriler, SKU eşleştirme, değişiklik tespiti |

## 1. M1 (alpha)

### 1.1 Tamamlananlar

- [x] Nav kategori ağacı (14 LV1 / 100 LV2 / 183 LV3) ve list-categories
- [x] Seçili kategori taraması, sayfalama, çapraz satış filtresi
- [x] Kart/PDP fiyat ayrıştırma, 10 sütunlu Bayios products (Ürün ID ilk sütun)
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
- [x] products 10 sütun; Ürün ID ilk sütun; 0 yazılmaz; ID'siz ürün raporda.
- [x] Aynı ID tek satır; aynı ad farklı ID ayrı satır + uyarı.
- [x] blog/ URL'leri ve blog kategori düğümleri çıktıda/kategorilerde yok.
- [x] Ek garanti 55 satır, kategori "Ek Garanti", ayrı komut/dosya yok.
- [x] Kara liste explicit URL'lerde de geçerli; force yalnızca istisna.
- [x] Ürün dosya adı urunler_<stamp>; meta ve run_report dolu (yerel test).
- [ ] Actions'ta 10 sütunlu Excel ve yeni akış canlı doğrulanır.

## 2. M2

### 2.1 Kampanya koşulları

- [ ] .promo-acc "Katılım Koşulları" akordeonundan .acc-body ul > li maddelerini sırayla ayrıştırma
- [ ] HTML temizleme, boşluk normalizasyonu, boş/tekrar madde eleme
- [ ] 5-10 maddeyi kırpmadan tek Excel hücresinde newline ile yazma
- [ ] Koşullar boşsa uyarı; kampanya yine de dosya/index içinde
- [ ] Fixture testi: örnek HTML'deki 6 madde sırayla ve eksiksiz

### 2.2 Kampanya dosya düzeni

- [ ] out/kampanyalar/ altında kampanya başına dosya
- [ ] Ad: kampanya-<YYYYMMDD-HHMMSS>-<kampanya-slug>.xlsx
- [ ] Urunler sayfası: Ürün Adı, İlişki Türü, Gerekli Adet
- [ ] Kampanya sayfası: ad, URL, tarih, Katılım Koşulları (tek hücre), ürün sayısı
- [ ] Index: kampanyalar_<stamp>.xlsx (ad, dosya, URL, ürün sayısı)
- [ ] CSV: kampanya-<stamp>-<slug>-urunler.csv ve ...-kampanya.csv
- [ ] Ürünü olmayan kampanya da koşullarıyla dosya alır

### 2.3 Ürün özellikleri

- [ ] specs komutu/cache, product_specs sheet
- [ ] 1001 KMX 6 grup/43 satır
- [ ] İkinci koşuda 0 ağ isteği

### 2.4 M2 kabul kriterleri

- [ ] Kampanya ürün tablosu 3 sütun; İlişki Türü "İlgili ürün"; Gerekli Adet boş.
- [ ] Katılım Koşulları 5-10 madde sırayla tek hücrede; HTML etiketi yok.
- [ ] Her kampanya için out/kampanyalar/ altında dosya; index eşlemesi doğru.
- [ ] products'ta kampanya kolonu boş; kampanya verisi ayrı dosyada.
- [ ] Specs ve cache kabul kriterleri sağlanır.

## 3. 1.0.0

- [ ] Üst üste 10 başarılı Actions koşusu
- [ ] Abort/403/429 yolu testli; partial Release'e yüklenmiyor
- [ ] Nav, kart, PDP, koşullar, garanti, kampanya dosyası için fixture testleri
- [ ] Excel, Bayios preview_product_import ve kampanya import sözleşme testleri
- [ ] Tek kategori < 5 dk; tam seçili set < 30 dk

## 4. v2 (ayrı PRD)

- Tüm ürünler için specs/görsel/açıklama
- Bayios alt kategori desteği
- SKU/ürün kodu eşleştirme
- Değişiklik tespiti, cache yönetimi
- Bayi profilleri

## 5. Bu sürümde değişen kararlar

1. Ek garanti ayrı komut/dosya olmaktan çıktı; prices/all içinde ürünlerle birlikte.
2. Kampanya katılım koşulları ayrıştırılacak; tek Excel hücresinde sırayla.
3. Kampanya çıktıları out/kampanyalar/ altında kampanya başına dosya.
4. Ürün dosyaları urunler_<tarih-saat>; kampanya dosyaları kampanya-<tarih-saat>-<kampanya-adı>.
5. ADR-0007'nin 3 sütun formatı korunuyor; dosya düzeni ADR-0008 ile güncellendi.
6. Ürün ID'si ana products ilk sütunu; 10 sütunlu çıktı (ADR-0009).
7. blog/ URL'leri ve blog kategori düğümleri config'den bağımsız dışlanır (ADR-0009).

## 6. Bağımlılıklar ve riskler

- [ ] Koşul HTML'i değişebilir; fixture/gerçek HTML testi gerekir.
- [ ] Kampanya adı slug'u Türkçe karakter/uzunluk; tam ad index ve Kampanya sayfasında.
- [ ] Garanti statik tablosu adları değişirse Bayios eşleşmesi bozulur.
- [ ] Çok kampanya dosyası disk/artifact boyutunu artırır.
- [ ] Actions 403 riski; erken test.
- [ ] ID'siz ürün / aynı adda farklı ID; raporlanıyor, elle kontrol.
- [ ] Bayios importer 10 sütuna güncellenmeli; eski 9 sütun import'u kırılabilir.
