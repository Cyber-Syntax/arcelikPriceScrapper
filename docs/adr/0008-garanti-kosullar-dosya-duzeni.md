# ADR-0008: Garanti entegrasyonu, kampanya koşulları ve dosya düzeni

- Durum: Kabul edildi
- Tarih: 2026-11-22
- İlgili: PRD v0.5 bölüm 2, 6.5, 9.5, 9.7, 10, 13, 17; ADR-0005, ADR-0007
- Karar veren: Ürün sahibi + geliştirici

## Bağlam

Üç yeni ürün kararı var:

1. Ek garanti ayrı bir komut/dosya olmayacak; ürünler çekilirken aynı koşuda alınacak.
2. Kampanya detay sayfasındaki "Katılım Koşulları" listesi ayrıştırılacak ve Excel'de tek sütunda sırayla verilecek. Örnek HTML:
   .promo-acc > ul.accordion > li > .acc-body > ul > li
3. Kampanya çıktıları out/kampanyalar/ altında, kampanya başına ayrı dosya olacak; dosya adı kampanya adını taşıyacak. Ürün dosyaları urunler_<tarih-saat> adını alacak.

ADR-0007 kampanya ürün tablosunun 3 sütununu tanımlıyordu; ancak tek workbook içinde per-kampanya sheet düzeni bu yeni dosya adlandırmasıyla uyuşmuyor.

## Karar

1. Ek garanti:
   - prices ve all komutları, ürün taraması sırasında statik /ek-garanti-uygulamalari tablosunu da çeker.
   - Satırlar products çıktısına normal ürün gibi girer (kind=warranty, kategori "Ek Garanti").
   - Ayrı warranties komutu, ayrı garanti sheet'i veya ayrı garanti dosyası yoktur.
   - Garanti fetch'i başarısız olursa uyarı verilir; ürün koşusu devam eder.

2. Kampanya katılım koşulları:
   - Kaynak: .promo-acc içindeki, başlığı "Katılım Koşulları" olan akordeon.
   - Maddeler: .acc-body altındaki doğrudan ul > li öğeleri.
   - Sıra korunur; boş maddeler atılır; aynı metin tekilleştirilir; 5-10 madde kırpılmaz.
   - HTML etiketleri temizlenir, boşluklar normalize edilir.
   - Çıktı: "Katılım Koşulları" sütununda tek hücre; maddeler newline ile ayrılır; Excel wrap text.
   - Koşullar Bayios'un 3 sütunlu ürün tablosuna konmaz.

3. Dosya düzeni ve adlandırma:
   - Ürün Excel: out/urunler_<YYYYMMDD-HHMMSS>.xlsx
   - Ürün CSV: out/urunler_<stamp>_products.csv, _products_full.csv, _meta.csv, _categories.csv
   - Kampanya index: out/kampanyalar/kampanyalar_<stamp>.xlsx (Kampanya Adı, Dosya, URL, Ürün Sayısı)
   - Her kampanya: out/kampanyalar/kampanya-<stamp>-<kampanya-slug>.xlsx
   - Kampanya CSV: out/kampanyalar/kampanya-<stamp>-<kampanya-slug>-urunler.csv ve ...-kampanya.csv
   - Dosya adları ASCII-güvenli; Türkçe karakterler slug'lanır; tarih-saat UTC.

4. Kampanya dosyası içeriği:
   - Urunler sayfası: Ürün Adı, İlişki Türü, Gerekli Adet (ADR-0007 ile aynı 3 sütun).
   - Kampanya sayfası: Kampanya Adı, URL, Tarih Metni, Başlangıç, Bitiş, Katılım Koşulları (tek hücre), Ürün Sayısı.
   - Ürünü olmayan kampanya da dosya alır; Urunler boş, Kampanya sayfası koşulları taşır.
   - Kampanya adı Bayios'ta elle girilir; dosya adı/index eşlemesi yol gösterir.

5. Referans tablolar:
   - campaigns ve campaign_products referans olarak kalır; campaign_products fiyat/URL içerir.
   - Bayios'a aktarılacak 3 sütunlu tablo per-kampanya dosyadaki Urunler sayfasıdır.

## Sonuçlar

Olumlu:
- Garanti ayrı komut/sheet yükü olmadan ürünlerle birlikte gelir.
- Katılım koşulları tek hücrede düzenli, sıralı ve eksiksiz taşınır.
- Kampanya başına dosya, Bayios'ta kampanya oluşturup ürünleri aktarmayı kolaylaştırır.
- Ürün ve kampanya dosya adları tarih/saat ve kampanya adıyla izlenebilir.

Olumsuz / dikkat:
- Çok kampanya varsa çok dosya oluşur; out/kampanyalar/ büyür.
- Kampanya adı slug'lanır; tam ad dosya içindeki Kampanya sayfasında ve indexte.
- Koşul HTML'i değişirse parser kırılabilir; fixture testi gerekir.
- Garanti tablosu değişirse Bayios eşleşmesi etkilenir; sözleşme testi gerekir.

## Alternatifler

- Garantiyi ayrı komut/sheet tutmak: kullanım yükü; reddedildi.
- Koşulları ayrı satırlara bölmek: kampanya metadata satırını böler; tek hücre newline tercih edildi.
- Tek workbook içinde per-kampanya sheet: dosya adıyla kampanya eşlemesi zayıf; reddedildi (ADR-0007 dosya düzeni güncellendi).
- Kampanya adını her ürün satırına eklemek: Bayios'ta ayrıca giriliyor; tekrar; reddedildi.

## Uygulama notları

- HTML koşul seçicisi: .promo-acc içinde "Katılım Koşulları" başlığı; .acc-body ul > li.
- Koşul maddeleri newline ile birleştirilir; Excel hücresi wrap text.
- Kampanya dosyası yazımı: Urunler + Kampanya sayfaları; CSV'de iki ayrı dosya.
- Ürün dosyaları ana ürün workbook'u; kampanya dosyaları ayrı klasör.
- warranties komutu kaldırılır; geriye uyumluluk için çağrılırsa "prices/all içinde" uyarısı verilebilir.
