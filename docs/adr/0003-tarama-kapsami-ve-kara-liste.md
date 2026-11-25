# ADR-0003: Tarama kapsamı ve kara liste

- Durum: Kabul edildi; blog istisnası ADR-0009 ile eklendi
- Tarih: 2026-11-20
- İlgili: PRD v0.4 bölüm 5, 6; ADR-0001, ADR-0002
- Karar veren: Ürün sahibi + geliştirici

## Bağlam

v0.3'ün "tüm yaprak slug'ları tara" yaklaşımı sahada iki sorun üretti:

- Ürün sitemap'inde 5.693 ürün var; 799 kategori sayfası gezildiğinde 4.110 ürün "missing" kalıyor. Bunların çoğu telefon, tablet, laptop, kulaklık gibi istenmeyen kategoriler.
- Ürün URL'sinin ilk segmenti kategori olmadığı için "tüm yaprak slug'lar" marka sayfalarını da tarıyor; gereksiz istek ve yanlış kategori.
- Tam tarama, Akamai/403 riskini ve koşu süresini gereksiz büyütüyor.

Ürün sahibi 3. soruda "kategori ağacı + istisna ürün listesi" modelini seçti; 10-50 eski ürünü config.toml'da URL ile vermeyi yeterli buldu. 4. soruda kara listenin ağaç-duyarlı olmasını ve açık ürün izin listesinin kara listeyi ezmesini seçti. 5. soruda bayi profillerini istemedi (tek config).

## Karar

1. categories.include zorunludur; boşsa hata verilir. Varsayılan tam sitemap taraması yoktur.
2. Seçilen düğümün kendi listing'i taranır. include_children varsayılan false'tur; LV1 seçilip tüm alt kategoriler isteniyorsa true yapılır.
3. categories.exclude ağaç-duyarlıdır: bir düğüm (LV1/LV2/LV3) eşleşirse kendisi ve tüm alt kategorileri kapsam dışıdır. Ad veya slug, Türkçe normalize, * glob desteklenir.
4. Kategori kara listesi explicit ürün URL'leri için de geçerlidir (D25). force = true olan inline ürün istisnadır; --only URL manuel istisnadır. Ürün en az bir izinli kaynakta varsa dahil edilir.
5. Aynı ürün birden fazla listing'de görünürse kategori ilk izinli kaynaktan, fiyat ilk dolu değerden gelir; çakışma raporlanır.
6. missing.txt yalnızca --report-missing ile üretilir; aday listesidir, KPI değildir. 4.000+ satır olabilir.
7. Arama endpoint'i (/search?text) robots nedeniyle kullanılmaz; istisnalar yalnızca açık URL ile eklenir.
8. Bayi profili yoktur; tek config, tek çıktı. İleride profil gerekirse ayrı ADR yazılır.
9. Sayfalama: 0 kart -> dur; iki ardışık "yeni kart yok" -> dur. ?page=1 bazı sayfalarda 0'ı tekrarlar; tek tekrar durma sebebi değildir.
10. Kategori sayfasındaki kart hierarchy hedefin kendisi/alt/üst kategorisi değilse çapraz satıştır; ürün dışlanır ve out_of_scope_products sayılır.
11. --only açık ürünleri seçili app_category'lerle sınırlar.
12. Toplu açık ürün URL'leri [products] include_file ile okunur; kategori koşusunda yalnızca kapsam içindeki URL'ler çekilir, diğerleri atlanır.

## Sonuçlar

Olumlu:
- İstek sayısı ve süre öngörülebilir; 5 kategori ~dakikalar.
- Telefon/bilgisayar/tablet kara listesi missing gürültüsünü büyük ölçüde keser.
- Eski ürünler bilinçli olarak eklenir; rastgele tam tarama yok.

Olumsuz / dikkat:
- Kapsam dışındaki ürünler otomatik gelmez; açık URL bakımı gerekir.
- include_children yanlış kullanılırsa istek sayısı büyür; LV1 seçerken dikkat.
- Bayi bazlı farklı kategoriler gerekiyorsa tek config yetersiz kalır; v2'de profil eklenebilir.
- missing.txt hâlâ büyük olabilir; kullanıcı içinden seçim yapmalı.

## Alternatifler

- Tam sitemap + her ürün PDP: tam kapsama ama ~5.700 istek/hafta; reddedildi.
- Tüm 799 kategori sayfası: marka/ghost ve gereksiz istek; reddedildi.
- Yalnızca yaprak slug'lar: G1 gibi ürünleri kaçırır; reddedildi.
- Üst kategori (LV1) hub'larını taramak: bazı ürünleri yakalar (G1 /ankastre'de) ama her LV1 için tam kapsama garanti değil ve istek sayısı yüksek; varsayılan değil. İstenirse include_children veya açık URL ile yapılır.
- Bayi profilleri: v1 için gereksiz; ertelendi.

## Uygulama notları

- Kara liste eşleşmesi hem ad hem slug üzerinden yapılır; ör. "Cep Telefonu", "cep-telefonu" aynı düğümü kapatır.
- Bir düğümün alt kategorileri nav ağacından hesaplanır; ayrı liste tutulmaz.
- Explicit ürün URL'leri kara listeye tabidir; raporda explicit_blocked olarak sayılır. force = true istisnası explicit_override olarak işaretlenir.
- Hedef kategori yoksa veya tümü kara listedeyse hata değil, uyarı + boş çıktı.
- Koşu raporunda kategori bazında hedef/elenen/taranan sayıları bulunur.
