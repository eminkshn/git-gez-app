# Yokuş + gezi modu sürümü (ekip arkadaşının çalışması)

`main` dalındaki rota planlayıcının genişletilmiş hâli:
- Gerçek sokaklar üzerinden, **yokuşa göre** yürüme (Tobler) · 3 profil: Normal / Dik yokuştan kaçın / Engelsiz
- En hızlı + 20 dk'ya kadar **alternatif rotalar**, A* seçeneği
- **🧳 Gezi modu:** backtracking + dal budama, greedy ve brute force karşılaştırması
- Eğim haritası, topoğrafya katmanı, yazarken öneri

## Eksik (eklenecek)
- [ ] Veri paketi (> 30 MB): `dem.npz`, `sokak.npz`, `yurume.npz`, `gezi_yerleri.csv` + mevcut ağ dosyaları
- [ ] `prep_egim.py` (yükseklik/sokak verisini hazırlayan betik)
- [ ] Defterin veriyle baştan sona çalıştırılıp testlerin geçtiğinin doğrulanması
