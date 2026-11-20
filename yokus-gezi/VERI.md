# Veri paketi: `gitgez_veri.zip` (55 MB)

Zip bu klasörde (`yokus-gezi/gitgez_veri.zip`), depoyla birlikte iner. **Açmayın**; defter ve `app.py` kendisi açar
(`gitgez_veri/` klasörüne). Aynı zip Release `veri-v1`'de de var.

- **Bilgisayarda:** hiçbir şey yapmanız gerekmez, `python app.py` zip'i bu klasörde bulur.
- **Colab'da:** `yokus_gezi.ipynb` ve `gitgez_veri.zip` — sadece bu **iki dosya**.

İçerik: `stops.csv`, `lines.csv`, `line_stops.csv`, `line_hours.csv`, `tuvaletler.csv` (İBB GTFS'ten) +
`dem.npz` (yükseklik, Copernicus GLO-30), `sokak.npz` (sokak ağı, Overture Maps / OpenStreetMap ODbL),
`yurume.npz` (durak→durak yürüme, 3 profil), `gezi_yerleri.csv` (57 yer),
`trafik.csv` (İBB saatlik trafik yoğunluğu, Ocak 2025 → bölge/gün/saat çarpanı). Kaynaklar: `KAYNAK.txt`.

Not: GitHub web sitesinden 25 MB üstü yüklenemez, ama `git push` ile 100 MB'a kadar dosya eklenebilir (bu zip öyle eklendi).
