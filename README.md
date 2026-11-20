# 🚇 İstanbul Toplu Taşıma Rota Planlayıcı

Algoritmalar dersi grup projesi. İBB Açık Veri Portalı'nın gerçek verisiyle (14.357 durak, 3.041 hat, 436 şehir tuvaleti)
seçilen gün ve saatte **en hızlı**, **en az aktarmalı** veya **en az yürümeli** rotayı bulur.

## Klasörler

| Klasör | Ne |
|---|---|
| **`yokus-gezi/`** | **Ana uygulama**: rota + yokuşlu yürüyüş + alternatif rotalar + 🧳 gezi modu + tuvalet (4 sekme) |
| `v1-basit/` | İlk sürüm (sadece rota + tuvalet, 1,4 MB veriyle çalışır). Yedek / karşılaştırma için |
| `docs/` | PDF rapor, karşılaştırma ve eksik taraması, trafik/hava planı |
| `tools/` | `export_app.py`: defterden `app.py` üretir |
| `veri_hazirlama.py` | Ham GTFS (~175 MB) → ağ dosyaları |

## Çalıştırma (ana uygulama)

1. **Veriyi indirin:** depo sayfası → **Releases → `veri-v1`** → zip'i `yokus-gezi/` klasörüne koyun (açmayın). Ayrıntı: `yokus-gezi/VERI.md`
2. **Kendi bilgisayarınızda:**
```bash
cd yokus-gezi
pip install -r requirements.txt
python app.py
```
Tarayıcıda `http://127.0.0.1:7860` açılır (~10 sn).

3. **Colab'da:** `yokus-gezi/yokus_gezi.ipynb` → *Tümünü çalıştır* → zip'i seçin. Telefondan açmak için çıktıdaki `gradio.live` bağlantısı.

> `app.py` defterden üretilir; değişiklikleri **deftere** yapın, sonra: `python tools/export_app.py yokus-gezi/yokus_gezi.ipynb yokus-gezi/app.py`

## Algoritmalar
1. **Yer arama** – hash tablosu (`dict`) + OpenStreetMap adres arama
2. **Yürüme bağlantıları** – ızgara hash'i; sokak ağında yokuşa göre (Tobler) Dijkstra, 3 profil
3. **Saate göre graf** – o saatte çalışmayan hatlar çıkarılır, bekleme = sıklığın yarısı
4. **Dijkstra + Min-Heap** – tek kod, üç kriter (maliyet bir tuple); A* seçeneği
5. **Alternatif rotalar** – eşdeğer hatları yasaklayıp yeniden arama
6. **Gezi planı** – backtracking + dal budama (kesirli knapsack üst sınırı), greedy ve brute force ile karşılaştırma
7. **En yakın tuvaletler** – `heapq.nsmallest`

## Veri kaynağı
İBB Açık Veri Portalı (data.ibb.gov.tr): İETT GTFS, raylı sistem/vapur GTFS, Şehir Tuvaletleri Veri Seti.
Sokak ağı: Overture Maps (OpenStreetMap, ODbL) · Yükseklik: Copernicus DEM GLO-30 (© DLR, © Airbus, ESA).
Adres arama: Photon / OpenStreetMap Nominatim.

## Ekip çalışması
- Değişiklik yapmadan önce: `git pull`
- Yeni özellik için ayrı dal (branch) açın: `git checkout -b ozellik-adi`
- Bitince Pull Request açın, bir ekip arkadaşı baksın, sonra `main`'e birleştirin.
- Büyük ham veri dosyalarını (`stop_times.txt` vb.) depoya koymayın.
