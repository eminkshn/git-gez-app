# `main` ile `yokus-gezi` karşılaştırması ve eksik taraması

*20 Kasım 2026 · `yokus-gezi/yokus_gezi.ipynb` + Release `veri-v1` verisiyle baştan sona çalıştırılarak yapıldı.*

## 1. Özet

`yokus-gezi`, `main`'deki rota planlayıcının **üzerine kurulmuş, onu tamamen kapsayan** bir sürüm.
Veriyle birlikte **baştan sona hatasız çalışıyor, 38 assert'in hepsi geçiyor**, yerel `app.py` ~9 saniyede açılıyor.
Derse en çok katkısı: **gezi modu** (backtracking + dal budama, greedy, brute force — 1. bölümdeki algoritma sınıfları
ve 0-1 Knapsack) ve **engelsiz yürüyüş profili**.

**Öneri:** Aşağıdaki "Birleştirmeden önce" maddeleri yapılınca `yokus-gezi` → `main` birleştirilsin; sunum ve rapor bu sürüme göre güncellensin.

## 2. Özellik karşılaştırması

| Konu | `main` | `yokus-gezi` |
|---|---|---|
| Yürüme | Kuş uçuşu × 1,3, düz yol | Gerçek sokak ağı (462 bin kavşak, 1,28 M yönlü parça), **yokuşa göre** Tobler süresi |
| Yürüyüş profilleri | — | Normal · Dik yokuştan kaçın · **Engelsiz** (%8 üstü ve merdiven yok) |
| Rota sayısı | Kriter başına 1 | En hızlı + 20 dk'ya kadar **alternatifler** (Kadıköy → Taksim: 6 rota) |
| Eşdeğer hatlar | Ayrı ayrı | 34 / 34A / 34AS gibi aynı güzergâh **tek rota**, sefer sıklıkları birleşik (3.041 hat → 2.822 desen) |
| Arama | Dijkstra | Dijkstra + A\* (alt sınır) + yasaklı hat ile alternatif üretimi |
| Yer arama | Enter + liste, Nominatim | Yazdıkça öneri (Photon, olmazsa Nominatim), çok kelimeli önek araması |
| Harita / arayüz | folium + Gradio, 2 sekme | Leaflet tabanlı Google Haritalar benzeri kartlar, **eğim haritası**, topoğrafya, 4 sekme |
| Gezi modu | — | 6 bölge, 57 yer; açılış saatleri, kapalı günler, Cuma namazı arası, Müzekart |
| Testler | 10 test | 38 assert (alternatifler, yasaklı hat, gezi, kesişme…) |
| Kod | ~700 satır | ~2.570 satır |
| Veri | 1,4 MB | 55 MB (Release `veri-v1`) |

## 3. Ölçümler (aynı makinede, hafta içi 08:00)

| Rota | `main` en hızlı | `yokus-gezi` normal | `yokus-gezi` engelsiz |
|---|---|---|---|
| Üsküdar → Beşiktaş | 28 dk · 0,1 s | 29 dk · 1,1 s · 4 rota | 29 dk · 0,5 s |
| Kadıköy → Taksim | 32 dk · 0,2 s | 32 dk · 6 rota | 33 dk · 1,1 s |
| Bakırköy → Kartal | 63 dk · 0,8 s | 63 dk · 2,6 s · 1 rota | 63 dk · 1,0 s |
| Avcılar → Zincirlikuyu | 69 dk · 0,5 s | 69 dk · 3,7 s · 2 rota | 69 dk · 1,3 s |
| Beylikdüzü → Sabiha G. | 177 dk · 4,0 s | 191 dk · 10,1 s | 195 dk · 8,1 s |

- Sonuçlar tutarlı. Beylikdüzü'ndeki fark beklenen: `yokus-gezi` yürüyüşü gerçek sokaklardan ve yokuşla hesaplıyor, `main` kuş uçuşu × 1,3 ile iyimser.
- `yokus-gezi` bir aramada birden çok Dijkstra çalıştırdığı için (alternatifler) 3–10 kat yavaş; en uzun rotada 10 s. Sunum için kabul edilebilir.
- **Bellek:** `yokus-gezi` ~1,3 GB (Colab'ın 12 GB'ı için sorun değil). **Açılış:** ~9 s (`app.py`).
- **Gece 03:00 Kadıköy → Taksim:** 87 dk, metrobüs + 25G gece otobüsü (iki sürüm aynı).
- **Gezi modu (~1 s):** Salı Topkapı'nın kapalı olduğunu yakalıyor; Cuma günü Ayasofya'yı namaz arasından sonra (15:37) koyuyor.

| Gezi analizi (Taksim'den, Çarşamba 09–15) | Greedy | Backtracking | İncelenen düğüm | Brute force sıra sayısı |
|---|---|---|---|---|
| Fatih (14 yer) | 160 | **244** | 1.975 | 236.975.164.804 |
| Beyoğlu (10) | 170 | **220** | 1.012 | 9.864.100 |
| Balat (7) | −17 | **94** | 558 | 13.699 |

6 yerlik örnekte brute force (1.956 sıra) ile backtracking **aynı sonucu** veriyor → backtracking'in doğruluğu gösterilmiş.

## 4. Eksik ve hata taraması

### Birleştirmeden önce (önemli)
1. **`prep_egim.py` depoda yok.** `KAYNAK.txt` eğim/sokak verisinin bu betikle üretildiğini söylüyor. Betik olmadan veri yeniden üretilemez; hoca "nasıl ürettiniz?" diye sorarsa cevap yok. → Depoya `yokus-gezi/prep_egim.py` olarak eklenmeli.
2. **Sunum ve PDF rapor eski sürümü anlatıyor.** Gezi modu (backtracking akış şeması + sözde kod), sokak/yokuş yürüyüşü, alternatif rotalar eklenmeli.
3. **Veri dağıtımı.** 55 MB'lık zip GitHub'ın web yükleme sınırını (25 MB) aştığı için Release'te; `VERI.md`'de nasıl indirileceği yazıyor.

### Küçük hatalar (arayüzde görüldü)
4. Adres önerilerinde **aynı satır iki kez** çıkabiliyor (ör. "Taksim — Gümüşsuyu, Beyoğlu" ×2). Etiket tekilleştirilmeli.
5. Rota kartlarında **"🚶 0"** gibi 0 dakikalık yürüyüş çipleri görünüyor (aynı istasyonda aktarma). 1 dk altı yürüyüş gizlenebilir ya da "<1" yazılabilir.
6. Defterin başlığı "bölge(**ler**)" diyor, `gezi_planla` ise **tek bölge** alıyor. Ya metin ya kod düzeltilmeli.
7. `gezi_planla(A, bolge, …)`'de `bolge` liste verilirse hata vermeden **boş plan** dönüyor (aday = 0). Tip kontrolü eklenmeli.

### Dikkat edilmesi gerekenler
8. **Photon** (adres önerisi) internet gerektirir; erişilemezse her aramada 3 sn bekleyip Nominatim'e düşüyor. Sunumdan önce internetle deneyin.
9. **Lisans/atıf:** Sokak verisi OpenStreetMap kaynaklı (Overture, ODbL), yükseklik Copernicus. `KAYNAK.txt`'te var; README'ye ve rapora da yazılmalı. Depo gizli olduğu sürece ODbL'nin paylaşım şartı sorun değil; **herkese açık** yapılacaksa türetilmiş sokak verisi için ODbL şartları okunmalı.
10. **Gezi verisi elle derlendi** (57 yer, saatler Kasım 2026). Kaynak sütunu var; sunumda "saatler değişebilir" denmeli.
11. **Ad tercihleri:** "Tanrı İstemezse", `insan_olmezmis.zip`. Ekip içinde sorun değil; akademik sunum için nötr bir ad düşünülebilir (karar ekibin).
12. **Kapsam / süre:** 25 dakikaya hepsi sığmaz. Öneri: gezi modu (backtracking · greedy · brute force) + engelsiz yürüyüş + alternatif rotalar öne çıksın; eğim haritası demoda kısaca.
13. Kod 3,5 kat büyüdü: herkes kendi sunacağı kısmın fonksiyonlarını bilmeli (öneri: kişi başı kısa kod rehberi).

## 5. Karar bekleyen konular (ekip)
- [ ] `yokus-gezi` `main`'e birleştirilsin mi? (önerim: 1–3 bittikten sonra evet)
- [ ] Sunumda hangi özellikler anlatılacak? (öneri madde 12)
- [ ] Proje adı
- [ ] Trafik / hava durumu (plan: `docs/PLAN_TRAFIK_HAVA.md`) sunumdan önce mi, sonra mı?
