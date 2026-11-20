# 🚇 GitGez — İstanbul rota ve gezi planlayıcı (çalışma adı)

Algoritmalar dersi grup projesi — **Muhammed Emin Küçükşahin, Emir Yılmaz, Fatih Mehmet Miçillioğlu**.
İBB Açık Veri Portalı'nın gerçek verisiyle (14.357 durak, 3.041 hat, 436 şehir tuvaleti)
seçilen gün ve saatte **en hızlı**, **en az aktarmalı** veya **en az yürümeli** rotayı bulur.
Seçilen saatin **hava durumu** (Open-Meteo) ve varsa **geçmiş trafik** verisi (İBB saatlik trafik yoğunluğu) süreleri etkiler.

## Klasörler

| Klasör | Ne |
|---|---|
| **`sade/`** | **Derste sunulacak sade sürüm**: rota (en iyi + 1 alternatif), tuvalet, gezi (beta). Ayrıntı: `sade/README.md` |
| `yokus-gezi/` | Ayrıntılı sürüm: yürüyüş profilleri, yokuş haritası, 6 alternatif, testler ve ölçümler (4 sekme) |
| `v1-basit/` | İlk sürüm (sadece rota + tuvalet, 1,4 MB veriyle çalışır). Yedek / karşılaştırma için |
| `yokus-gezi/hazirlik/` | Veri hazırlama betikleri (sokak ağı, eğim, gezi yerleri, **trafik**) |
| `docs/` | PDF rapor (8 algoritma: adımlar, akış şemaları, sözde kod, analiz), karşılaştırma, trafik/hava planı, `SONRAKI_ADIMLAR.md` |
| `tools/` | `export_app.py`: defterden `app.py` üretir · `build_sade.py`: sade defteri üretir · `patch_hava_trafik.py`: hava/trafik eklemesi (bir kez uygulandı) |
| `veri_hazirlama.py` | Ham GTFS (~175 MB) → ağ dosyaları |

## Çalıştırma (ana uygulama)

1. **Veri:** `yokus-gezi/gitgez_veri.zip` depoda hazır (55 MB, trafik dahil; açmayın). Ayrıntı: `yokus-gezi/VERI.md`
2. **Kendi bilgisayarınızda:**
```bash
cd yokus-gezi
pip install -r requirements.txt
python app.py
```
Tarayıcıda `http://127.0.0.1:7860` açılır (~10 sn).

3. **Colab'da:** `yokus-gezi/yokus_gezi.ipynb` → *Tümünü çalıştır* → `gitgez_veri.zip`'i seçin (sadece bu iki dosya). Telefondan açmak için çıktıdaki `gradio.live` bağlantısı.

> `app.py` defterden üretilir; değişiklikleri **deftere** yapın, sonra: `python tools/export_app.py yokus-gezi/yokus_gezi.ipynb yokus-gezi/app.py`

## Algoritmalar
1. **Yer arama** – hash tablosu (`dict`) + OpenStreetMap adres arama
2. **Yürüme bağlantıları** – ızgara hash'i; sokak ağında yokuşa göre (Tobler) Dijkstra, 3 profil
3. **Saate göre graf** – o saatte çalışmayan hatlar çıkarılır, bekleme = sıklığın yarısı
4. **Dijkstra + Min-Heap** – tek kod, üç kriter (maliyet bir tuple); A* seçeneği
5. **Alternatif rotalar** – eşdeğer hatları yasaklayıp yeniden arama
6. **Gezi planı** – backtracking + dal budama (kesirli knapsack üst sınırı), greedy ve brute force ile karşılaştırma
7. **En yakın tuvaletler** – `heapq.nsmallest`
8. **Hava ve trafik** – kenar maliyetleri saate göre çarpılır (hep pozitif → Dijkstra/A* doğru kalır); fırtınada vapur kenarları çıkarılır

### Trafik verisi
`yokus-gezi/trafik.csv` depoda hazır: İBB *Saatlik Trafik Yoğunluk Veri Seti*, **Ocak 2025** (1,76 milyon ölçüm,
2.458 bölge × gün tipi × saat; ham CSV Release `veri-v1` içinde). Yeniden üretmek ya da başka ay eklemek için:
```bash
python yokus-gezi/hazirlik/prep_trafik.py traffic_density_202501.csv [traffic_density_202502.csv ...] -o yokus-gezi/trafik.csv
```
`trafik.csv` ayrıca `gitgez_veri.zip`'in içinde de var; Colab'a ayrıca yüklemek gerekmez.
Örnek: Kadıköy → Ataşehir, hafta içi 18:00 — trafiksiz 36 dk (M4 + 19E); trafikle en hızlı rota M4 + M8 + 10, 41 dk.

## Veri kaynağı
İBB Açık Veri Portalı (data.ibb.gov.tr): İETT GTFS, raylı sistem/vapur GTFS, Şehir Tuvaletleri Veri Seti.
Sokak ağı: Overture Maps (OpenStreetMap, ODbL) · Yükseklik: Copernicus DEM GLO-30 (© DLR, © Airbus, ESA).
Adres arama: Photon / OpenStreetMap Nominatim. Hava: Open-Meteo (CC BY 4.0). Trafik: İBB Saatlik Trafik Yoğunluk Veri Seti.

## Ekip çalışması
- Değişiklik yapmadan önce: `git pull`
- Yeni özellik için ayrı dal (branch) açın: `git checkout -b ozellik-adi`
- Bitince Pull Request açın, bir ekip arkadaşı baksın, sonra `main`'e birleştirin.
- Büyük ham veri dosyalarını (`stop_times.txt` vb.) depoya koymayın.
