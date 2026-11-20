# 🚇 İstanbul Toplu Taşıma Rota Planlayıcı

Algoritmalar dersi grup projesi. İBB Açık Veri Portalı'nın gerçek verisiyle (14.357 durak, 3.041 hat, 436 şehir tuvaleti)
seçilen gün ve saatte **en hızlı**, **en az aktarmalı** veya **en az yürümeli** rotayı bulur.

## Çalıştırma

### Kendi bilgisayarında (sunum için)
```bash
pip install gradio folium pandas requests
python app.py
```
Tarayıcı kendiliğinden açılır (`http://127.0.0.1:7860`). `istanbul_ag.zip` dosyası `app.py` ile aynı klasörde olmalı.

### Google Colab'da
`istanbul_rota.ipynb` dosyasını Colab'da açın → *Çalışma zamanı → Tümünü çalıştır* → istenince `istanbul_ag.zip` dosyasını seçin.

## Dosyalar

| Dosya | İçerik |
|---|---|
| `app.py` | Gradio arayüzü (🧭 Rota, 🚻 Tuvalet bul). Defterdeki kodun aynısı |
| `istanbul_rota.ipynb` | Colab defteri: tüm algoritmalar, 10 test, ölçümler, arayüz |
| `istanbul_ag.zip` | Temizlenmiş ağ: durak, hat, hat-durak, saatlik sefer sayısı, tuvaletler (1,4 MB) |
| `veri_hazirlama.py` | Ham GTFS (~175 MB) → `istanbul_ag.zip` dönüştürücü |
| `docs/algorithm_design_report.pdf` | Rapor: 6 adım, akış şemaları, sözde kod, analiz |
| `docs/rapor_kaynagi/build_report.py` | Raporu üreten betik |

## Algoritmalar
1. **Yer arama** – hash tablosu (`dict`) + OpenStreetMap adres arama
2. **Yürüme bağlantıları** – ızgara hash'i (2 km), naif O(n²) yerine ≈ O(n)
3. **Saate göre graf** – o saatte çalışmayan hatlar çıkarılır, bekleme = sıklığın yarısı
4. **Dijkstra + Min-Heap** – tek kod, üç kriter (maliyet bir tuple)
5. **En yakın tuvaletler** – `heapq.nsmallest`

## Veri kaynağı
İBB Açık Veri Portalı (data.ibb.gov.tr): İETT GTFS, raylı sistem/vapur GTFS, Şehir Tuvaletleri Veri Seti.
Adres arama: OpenStreetMap Nominatim.

## Ekip çalışması
- Değişiklik yapmadan önce: `git pull`
- Yeni özellik için ayrı dal (branch) açın: `git checkout -b ozellik-adi`
- Bitince Pull Request açın, bir ekip arkadaşı baksın, sonra `main`'e birleştirin.
- Büyük ham veri dosyalarını (`stop_times.txt` vb.) depoya koymayın.
