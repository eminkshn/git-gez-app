# Veri hazırlama betikleri (yokuş + gezi verisi)

Release `veri-v1` içindeki `dem.npz`, `sokak.npz`, `yurume.npz` ve `gezi_yerleri.csv` bu betiklerle üretildi.

| Betik | Ne yapar | Girdi → Çıktı |
|---|---|---|
| `fetch_streets.py` | Overture Maps (OpenStreetMap tabanlı, ODbL) yol segmentlerinden İstanbul kutusunu indirir | S3 (anonim) → `streets.parquet` |
| `prep_egim.py` | Yükseklik modelinden (Copernicus GLO-30) zemin yüksekliği; sokak eğimleri; Tobler yürüme süreleri; 3 profil için durak→durak yürüme (Dijkstra) | `streets.parquet`, `dem/*.tif`, durak verisi → `out/dem.npz`, `out/sokak.npz`, `out/yurume.npz` |
| `gezi_veri.py` | 57 gezi noktasının bilgileri (saatler, kapalı günler, puanlar, kaynaklar) | → `gezi_yerleri.csv` |
| `geocode.py` | Gezi noktalarının koordinatlarını Nominatim / Photon ile doğrular | `poi_taslak.py` → `geocode.json` |

Notlar:
- `geocode.py`, depoda olmayan `poi_taslak.py` dosyasını kullanır (taslak nokta listesi); `gezi_veri.py` de onun çıktısı `geocode.json`'u okur. İkisi yoksa `gezi_veri.py` yeniden çalışmaz; sonuç zaten `gezi_yerleri.csv` içinde. (Bu iki dosya ekleyen kişiden istenebilir.)
- Copernicus DEM dosyaları (`Copernicus_DSM_COG_10_N4x_00_E02x_00_DEM.tif`, 6 kare) Copernicus'tan ayrıca indirilmelidir.
- Gerekenler: `pip install numpy scipy pyarrow shapely tifffile s3fs requests`
