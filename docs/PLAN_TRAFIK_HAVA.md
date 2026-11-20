# Plan: Trafik ve hava durumu verisi

*Durum (güncel): **uygulandı.** Hava: Open-Meteo saatlik tahmin/arşiv (internet yoksa etkisiz), arayüzde elle de seçilebilir.
Trafik: `yokus-gezi/hazirlik/prep_trafik.py` İBB saatlik trafik CSV'lerinden `trafik.csv` üretir; dosya yoksa otobüslerde sabit hız.
Yapılmayanlar: gerçek İBB trafik dosyasıyla çarpanların doğrulanması (sütun adları indirilip kontrol edilmeli), eşiklerin ölçümle ayarı.
Canlı veri, mobil uygulama vb. için: `SONRAKI_ADIMLAR.md`.*

## Amaç
Şu an otobüs süreleri sabit hızla (otobüs 18 km/sa, metrobüs 32 km/sa) tahmin ediliyor ve hava hiç hesaba katılmıyor.
Hedef: **seçilen gün ve saatteki trafik** otobüs sürelerini, **o saatteki hava** yürüyüş sürelerini ve vapur seçimini etkilesin.

## Algoritmaya etkisi
Kenar maliyetleri saate bağlı hâle gelir ama **hep pozitif kalır** → Dijkstra'nın doğruluğu değişmez.
Mevcut tasarım buna hazır: graf zaten `get_graph(gun, saat)` ile saat başına kuruluyor ve önbelleğe alınıyor.
Önbellek anahtarı `(gun, saat)` → `(gun, saat, hava_sinifi)` olur. Karmaşıklık değişmez: graf kurulumu O(L + S), arama O((V + E) log V).

## Faz 0 · Veri keşfi ve doğrulama (önce bu)
| Veri | Aday kaynak | Kontrol edilecek |
|---|---|---|
| Saatlik trafik hızı | İBB Açık Veri Portalı'nda "Saatlik Trafik Yoğunluk" veri seti (geohash bazında ortalama / en düşük / en yüksek hız, araç sayısı; aylık dosyalar) | Gerçek adı, sütunlar, hangi aylar, dosya boyutu, geohash hassasiyeti |
| Şehir geneli trafik | İBB "İstanbul Trafik İndeksi" | Yedek: bölge verisi yoksa şehir geneli çarpan |
| Canlı otobüs konumu | İETT açık servisleri (filo/araç konum) | İsteğe bağlı, sonraki aşama; erişim şekli ve sınırlar |
| Hava (saatlik tahmin) | **Open-Meteo** (ücretsiz, anahtar gerekmiyor): yağış, sıcaklık, rüzgâr/hamle, görüş | Colab'dan erişim; geçmiş günler için arşiv uç noktası |

Not: `data.ibb.gov.tr` bulut sunuculardan gelen bağlantıları kesiyor (bu oturumda denendi). Dosyalar ekipten biri tarafından tarayıcıyla indirilip Release'e konmalı.

## Faz 1 · Trafik (çevrimdışı tablo)
1. **Hazırlık betiği** (`veri_hazirlama.py`'ye ek): aylık trafik dosyalarından `hiz[(geohash, gun_tipi, saat)]` = ortanca ortalama hız tablosu (hafta içi / cumartesi / pazar × 24 saat). Çıktı küçük bir CSV/NPZ.
2. **Otobüs segmenti → geohash:** her ardışık durak çifti için orta nokta (uzun segmentlerde birkaç örnek nokta) geohash'i.
3. **Süre:** `dk = mesafe × 1,25 ÷ v_otobüs(gun, saat)`; `v_otobüs = min(k × v_trafik, v_maks)`. Otobüs durakta durduğu için `k < 1` (ör. 0,6); `k` İETT'nin yayımladığı ortalama ticari hızla (~18 km/sa) kalibre edilir.
4. **Etkilenmeyenler:** metrobüs (ayrı yol), raylı sistem, vapur.
5. `get_graph(gun, saat)` içinde otobüs `ride` kenarlarının süresi tablodan okunur. Veri yoksa eski sabit hız (yedek).

## Faz 2 · Hava durumu (canlı + yedek)
`hava(tarih, saat)` → Open-Meteo'dan saatlik değerler; erişilemezse "hava bilgisi yok" ve katsayı 1.

| Durum | Eşik (varsayım, kaynakla gerekçelendirilecek) | Etki |
|---|---|---|
| Yağmur | ≥ 1 mm/sa | Yürüme süresi × 1,15; "en az yürüme"de yürüme ağırlığı 4 → 6 |
| Kar / buzlanma | kar > 0 ya da sıcaklık ≤ 0 °C ve yağış | Yürüme × 1,5; profil önerisi "dik yokuştan kaçın" |
| Sert rüzgâr | hamle ≥ 50 km/sa | Vapur kartında ⚠ "sefer iptali riski" |
| Fırtına | hamle ≥ 70 km/sa | Vapur hatları grafa eklenmez |
| Sis | görüş < 500 m | Vapur ⚠ |
| Sıcak | ≥ 33 °C | Yürüme × 1,1; yol üstü tuvalet/çeşme notu |

Katsayılar başlangıç varsayımıdır; raporda böyle yazılmalı ve literatürle/ölçümle güncellenmeli.

## Faz 3 · Arayüz ve testler
- Rota sonucunun üstünde hava rozeti: "🌧 08:00 yağmurlu — yürüme süreleri %15 uzun hesaplandı".
- Kartta otobüs bacağında "🚦 yoğun trafik" etiketi (o saatte hız serbest akışın %50'sinin altındaysa).
- Testler: (1) hafta içi 08:00'de bir otobüs segmenti 03:00'tekinden yavaş; (2) yağmurda yürüme dakikası artar, araç dakikası değişmez; (3) fırtınada vapur kullanılmaz; (4) Dijkstra = networkx hâlâ eşit; (5) API yokken eski davranış.

## Faz 4 · Sunum ve rapor
- Problem tanımına "saate bağlı kenar maliyeti", analize "trafiksiz / trafikli" rota karşılaştırması (ör. Kadıköy → Mecidiyeköy 08:00 vs 13:00).
- Sınırlılıklardan "trafik yok" maddesi kalkar; yerine "trafik geçmiş ortalamalardan, anlık değil" gelir.

## Riskler
- Trafik verisinin boyutu (aylık dosyalar büyük olabilir) → yalnızca özet tablo depoya girer.
- Kalibrasyon için otobüs başına gerçek süre verisi yok → `k` katsayısı yaklaşık kalır.
- Open-Meteo için ortam ağ izni gerekir (Colab'da sorun beklenmez).
- Süre: sunumdan önce yapılacaksa önce **Faz 2 (hava)** daha hızlı ve görünür; trafik daha çok veri işi.

## Kabaca iş sırası
1. Faz 0 (veri indir, sütunları doğrula) → 2. Faz 2 hava (küçük, görünür) → 3. Faz 1 trafik → 4. Faz 3 testler/arayüz → 5. Faz 4 sunum/rapor.
