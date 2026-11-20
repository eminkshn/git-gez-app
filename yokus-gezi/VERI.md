# Veri paketi (55 MB)

GitHub'ın web yükleme sınırı 25 MB olduğu için veri depoda değil, **Release** olarak duruyor:

1. Depo sayfasında sağdaki **Releases → "yokus + gezi verisi" (`veri-v1`)** → zip dosyasını indirin.
2. Zip'i **açmadan** bu klasöre (`yokus-gezi/`) ya da Colab'a yükleyin. Adı önemli değil; defter ve `app.py` doğru zip'i içeriğine bakarak bulur.

İçerik: `stops.csv`, `lines.csv`, `line_stops.csv`, `line_hours.csv`, `tuvaletler.csv` (main ile aynı) +
`dem.npz` (yükseklik, Copernicus GLO-30), `sokak.npz` (sokak ağı, Overture Maps / OpenStreetMap ODbL),
`yurume.npz` (durak→durak yürüme, 3 profil), `gezi_yerleri.csv` (57 yer). Kaynaklar: `KAYNAK.txt`.
