# ADR-0005: Ek garanti kaynağı

- Durum: Kabul edildi; entegrasyon ADR-0008 ile güncellendi
- Tarih: 2026-11-20
- İlgili: PRD v0.4 bölüm 3, 9; ADR-0002
- Karar veren: Ürün sahibi + geliştirici

## Bağlam

Ek garanti için iki kaynak var:

1. Statik sayfa /ek-garanti-uygulamalari: 55 satır; adlar "2 Yıl EG Bulaşık Mk. (0-6 Ay)"; rowspan var; SKU yok.
2. /ekgaranti kategorisi: 49 ürün; adlar "2 Yıl Ek Garanti BULAŞIK (0-6 Ay)"; SKU var (ör. GRT323); fiyatlar statik tabloyla aynı.

Bayios ürünleri Ürün Adı ile eşleştiriyor. İki kaynağın adları farklı olduğu için hangisinin kanonik olduğu kritik: yanlış seçim mevcut kayıtları eşleştirmez ve yeni ürünler yaratır.

Ürün sahibi 7. soruda "statik tablo adları kalsın" seçeneğini seçti.

## Karar

1. Ek garanti için kanonik kaynak statik tablodur (/ek-garanti-uygulamalari).
2. Adlar statik tablodaki gibi korunur; kategori sabit "Ek Garanti"dir.
3. Satırlar products çıktısına normal ürün gibi girer (D8); kind = warranty; url = statik sayfa.
4. /ekgaranti kategorisi ek garanti için taranmaz; ileride SKU zenginleştirmesi gerekirse ayrı ADR ile eklenir.
5. rowspan forward-fill korunur; fiyatı olmayan satır atlanır; sıfır satır veya yüksek fiyatsız oranı hatadır.

## Sonuçlar

Olumlu:
- Bayios'taki mevcut ek garanti adlarıyla uyum.
- Statik tablo eksiksiz (55 tanım); kategori sayfasından daha kapsamlı.
- SKU olmadığı için ek eşleme tablosu gerekmez.

Olumsuz / dikkat:
- SKU yok; ileride ürün kodu eşleştirmesi gerekirse kategori sayfası ayrıca taranmalı.
- Bayios'un "Ek Garanti" kategorisi yoksa importer yeni kategori yaratır; kontrol edilmeli.
- Statik tablo adları değişirse Bayios eşleşmesi bozulur; sözleşme testi gerekir.

## Alternatifler

- /ekgaranti kategori ürünleri: SKU ve gerçek ürün sayfası sağlar, ancak adlar farklı; mevcut kayıtlarla uyuşmaz; reddedildi.
- İkisini birleştirmek: statik ad + kategori SKU/fiyat; eşleme tablosu ve bakım gerektirir; v2'ye bırakıldı.
- Ek garanti tamamen ayrı sheet: import edilmezse Bayios ek garanti fiyatlarını güncellemez; mevcut karar products içinde.

## Uygulama notları

- Statik tablo seçicisi: /ek-garanti-uygulamalari; tablo birden fazla olabilir; "Tanım" ve "Fiyat" sütunları başlıktan bulunur.
- rowspan/colspan açılır; hücreler ileri doldurulur.
- Ürün adı = Ek Garanti Tanım; kategori = config warranty_category (varsayılan "Ek Garanti").
- Fiyat parse edilemezse satır atlanır ve sayılır; toplam satır 0 ise hata.
- Aynı ad birden fazla satırda varsa uyarı.
