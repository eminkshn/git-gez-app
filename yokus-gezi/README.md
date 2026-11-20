# Yokuş + gezi modu sürümü (ekip arkadaşının çalışması)

`main` dalındaki rota planlayıcının genişletilmiş hâli:
- Gerçek sokaklar üzerinden, **yokuşa göre** yürüme (Tobler) · 3 profil: Normal / Dik yokuştan kaçın / Engelsiz
- En hızlı + 20 dk'ya kadar **alternatif rotalar**, A* seçeneği
- **🧳 Gezi modu:** backtracking + dal budama, greedy ve brute force karşılaştırması
- Eğim haritası, topoğrafya katmanı, yazarken öneri

## Çalıştırma
- **Veri:** `VERI.md` (Release `veri-v1`, 55 MB)
- **Colab:** `yokus_gezi.ipynb` → Tümünü çalıştır → `gitgez_veri.zip`'i seçin
- **Bilgisayarda:** `pip install -r requirements.txt` → `python app.py` (`gitgez_veri.zip` bu klasörde hazır; ~10 sn'de açılır)
- `app.py` defterden üretilir: `python tools/export_app.py yokus-gezi/yokus_gezi.ipynb yokus-gezi/app.py` — değişiklikleri deftere yapın.

## Durum
- [x] Veri paketi Release'te (`veri-v1`)
- [x] Defter veriyle baştan sona çalıştı (20.11.2026): 38 assert geçti, ~1,3 GB bellek
- [x] `app.py` üretildi ve tarayıcıda denendi (4 sekme açılıyor)
- [ ] `prep_egim.py` (yükseklik/sokak verisini hazırlayan betik) eklenmeli
- [ ] Küçük hatalar ve diğer maddeler: `docs/KARSILASTIRMA_VE_EKSIKLER.md`
