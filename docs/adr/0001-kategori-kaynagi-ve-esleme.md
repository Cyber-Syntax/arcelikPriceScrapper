# ADR-0001: Kategori kaynağı ve uygulama kategorisi

- Durum: Kabul edildi
- Tarih: 2026-11-20
- İlgili: PRD v0.4 bölüm 3, 4, 5; ADR-0003
- Karar veren: Ürün sahibi + geliştirici

## Bağlam

v0.3, ürün URL'sinin ilk segmentini yaprak kategori kabul ediyordu. Canlı doğrulama bunu çürüttü:

- /samsung-galaxy-a17/... ilk segmenti bir marka sayfasıdır; kategori değildir.
- list-categories çıktısı "klavye", "samsung-galaxy-a17", "oda-termostati-old" gibi marka/ghost slug'larla doluydu.
- CATEGORY sitemap'inde 799 URL var; bunların bir kısmı marka, ghost veya kampanya sayfasıdır; hiyerarşi vermez.
- Gerçek ağaç her sayfada sunucu-render gelen nav#nav-menu-category içindedir: 14 LV1, ~103 LV2, yüzlerce LV3.
- Ürün kartında data-product-hierarchy (Top/Mid/Leaf) ve PDP'de ol.breadcrumb vardır.
- Bayios v1 alt kategori desteklemiyor; genel kategoriler kullanılıyor (Buzdolabı, Kurutma Makinesi, Çamaşır Makinesi).
- Bazı dallar istisna: /televizyon LV1 sayfası sayfa 0'da 17 ürün der, sayfalama ile 48 tekil verir; tüm TV alt kategorileri için include_children veya LV2/LV3 seçimi gerekir.

## Karar

1. Kategori kaynağı nav ağacıdır. Slug → (LV1, LV2, LV3) haritası tek istekle kurulur ve 24 saat cache'lenir.
2. app_category varsayılan olarak LV2 adıdır (ör. "Buzdolabı", "Kurutma Makinesi", "Cep Telefonu").
3. Ürün kategorisi şu sırayla çözülür:
   - Açık ürün app_category override'ı
   - Kategori girişi app_category override'ı
   - Kart data-product-hierarchy: en derin bilinen düğüm → LV2 atası
   - Listing breadcrumb'ı: son kategori düğümü → LV2 atası
   - PDP breadcrumb'ı (açık ürün): LV2
   - Hiçbiri yoksa boş + rapor
4. [categories.aliases] ile site LV2 adı Bayios'un eski adına eşlenebilir (ör. "Kurutma Makinesi" = "Kurutma"). Varsayılan boştur.
5. TV gibi LV1 çatısı altında toplanması gereken gruplarda kategori girişine app_category override'ı yazılır.
6. list-categories nav ağacını yazar; marka/ghost sayfaları varsayılan çıktıda yoktur. --all ile CATEGORY sitemap farkı denetlenir.

## Sonuçlar

Olumlu:
- Kategoriler gerçek hiyerarşiyle uyumlu olur; marka sayfaları kategori sanılmaz.
- Bayios'un genel kategori yapısına doğrudan oturur.
- Aynı ürün birden fazla listing'de görünse bile kategori tutarlı çözülür.

Olumsuz / dikkat:
- Nav etiketleri bazen tutarsız (ör. /buhar-destekli-firin "Ankastre Standart Fırın" olarak etiketlenmiş). Bu yüzden tam yol eşleşmesi ve PDP breadcrumb fallback gerekir.
- Kart hierarchy'sindeki orta parça LV2 veya LV3 olabilir; düz metin karşılaştırması yanlış sonuç verir. "En derin bilinen düğüm → LV2 atası" kuralı zorunludur.
- Kategori çözülemeyen ürünlerde boş kategori + rapor vardır; tahmin yoktur.
- Bayios'ta "Kurutma" gibi eski adlar varsa alias veya yeniden adlandırma gerekir.

## Alternatifler

- URL ilk segmenti: reddedildi; marka sayfaları ve eksik kapsama nedeniyle yanlış.
- CATEGORY sitemap'ini hiyerarşi sanmak: reddedildi; 799 URL hiyerarşi vermiyor, marka/ghost içeriyor.
- Her ürün için PDP'ye gidip breadcrumb okumak: reddedildi; 5.693 ürün için ağır ve ban riski yüksek. Yalnızca açık ürünlerde kullanılır.
- Kategori adlarını elle eşlemek: kısmen kabul; yalnızca istisnalar (TV, eski ad) için override/alias.

## Uygulama notları

- Nav seçicileri: nav#nav-menu-category, li.lv1-li, li.lv2-li, ul.lv-3 > li > a.
- Kart seçicisi: [data-product-hierarchy]; değer "Top/Mid/Leaf".
- PDP seçicisi: ol.breadcrumb li; "Ana Sayfa" hariç.
- Kategori cache'i fiyat cache'i değildir; yalnızca ağaç yapısı cache'lenir.
- Çözülemeyen kategoriler run_report.json içinde category_unresolved altında listelenir.
- Kategori sayfasındaki kart hierarchy hedefin kendisi/alt/üst kategorisi değilse çapraz satıştır; ürün dışlanır (ADR-0003).
- list-categories out/categories.txt ve out/categories.toml yazar; TOML yorumlu [[categories.include]] bloklarıdır.
