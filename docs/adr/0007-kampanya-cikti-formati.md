# ADR-0007: Kampanya çıktı formatı (Bayios)

- Durum: Kabul edildi; dosya düzeni ADR-0008 ile güncellendi
- Tarih: 2026-11-21
- İlgili: PRD 9.5, ADR-0004
- Karar veren: Ürün sahibi + geliştirici

## Bağlam

Bayios'un kampanya detay ekranı şu tabloyu kullanıyor:

| Ürün Adı | İlişki Türü | Gerekli Adet |
| --- | --- | --- |
| 07325 A | İlgili ürün | |
| 09325 A | İlgili ürün | |

- Kampanya adı bu tabloda yok; Bayios'ta kampanya oluşturulurken ayrıca giriliyor.
- URL, fiyat, tarih, kampanya ID'si bu ekranda gerekmiyor.
- Kampanyalar web sitesinde olmayabilir (ör. düğün.com); web sitesindeki kampanyalarla aynı formatta elle de eklenebilmeli.
- Mevcut campaign_products referans tablosu fiyat/URL içeriyor; doğrudan içe aktarılamıyor.

## Karar

1. Kampanyalar için referans tablolar korunur:
   - campaigns: kampanya adı, URL, tarih, koşullar, ürün sayısı, dosya eşlemesi.
   - campaign_products: ürün adı, fiyat, URL, kampanya ID (analiz/referans).
2. Her kampanya için ayrı bir Bayios tablosu üretilir:
   - Sütunlar: Ürün Adı, İlişki Türü, Gerekli Adet.
   - İlişki Türü her satırda "İlgili ürün".
   - Gerekli Adet boş.
   - URL/fiyat/tarih/kampanya ID yok.
3. Excel'de her kampanya ayrı sheet; sheet adı kampanya adının temizlenmiş hali + sıra numarası.
   CSV'de her kampanya ayrı dosya; dosya adı sıra + kampanya adı slug'ı.
4. Aynı kampanyada aynı ürün adı tekrarlanırsa tek satıra indirilir.
5. Kampanya adı Bayios'ta elle girilir; campaigns tablosundaki name ve dosya eşlemesi hangi dosyanın hangi kampanya olduğunu gösterir.
6. Ürünü olmayan kampanya için Bayios tablosu üretilmez; product_count = 0 kalır.

## Sonuçlar

Olumlu:
- Her kampanya doğrudan Bayios kampanya detayına kopyalanabilir/import edilebilir.
- Kampanya adı, URL ve fiyat gibi fazladan sütunlar import tablosunu kirletmez.
- Web sitesinde olmayan kampanyalar için aynı 3 sütunlu şablon elle doldurulabilir.

Olumsuz / dikkat:
- Kampanya sayısı kadar sheet/dosya oluşur; Excel'de çok sheet olabilir.
- Sheet adları 31 karaktere sığdırılır; tam ad campaigns tablosunda.
- Ürün adları Bayios'taki ürün adlarıyla birebir eşleşmelidir; farklıysa elle düzeltilir.
- Kampanyanın kendisi (ad, tarih) scraper tarafından Bayios'a yazılmaz; kullanıcı oluşturur.

## Alternatifler

- Tek bir campaign_products_bayios tablosu + Kampanya Adı sütunu: filtreleme gerekir, import şablonunda fazla sütun olur; reddedildi.
- Yalnızca mevcut campaign_products referansını bırakmak: doğrudan import edilemez; reddedildi.
- Kampanya adını her satıra yazmak: kullanıcı zaten Bayios'ta ayrıca girdiği için tekrar; reddedildi.

## Uygulama notları

- Bayios başlıkları: Ürün Adı, İlişki Türü, Gerekli Adet.
- İlişki türü sabiti: İlgili ürün.
- Gerekli Adet: None (CSV'de boş, Excel'de boş hücre).
- Kaynak: campaigns.py içindeki bayios_table yardımcısı.
- Kampanya ürün adları kartlardan alınır; aynı ad tekilleştirilir.
