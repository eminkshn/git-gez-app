# GitGez — sade sürüm (derste sunulacak olan)

Ayrıntılı sürümün (`../yokus-gezi/`) okunması ve anlatılması kolay hâli: ~800 satır kod, açıklama satırlarıyla.

| | Sade (`sade/`) | Ayrıntılı (`yokus-gezi/`) |
|---|---|---|
| Rota | En iyi + **1 alternatif** (hatları yasakla, Dijkstra'yı tekrar çalıştır) | 6'ya kadar alternatif, A*, baskınlık kuralları |
| Tercihler | Sadece **sıralama**: en hızlı / az aktarma / az yürüme | + yürüyüş profili (normal, yokuştan kaçın, engelsiz), az yokuş, yol üstü tuvalet |
| Yokuş | Rotada kullanılır (Tobler), ayrı harita yok | + yokuş haritası sekmesi, yükseklik profili |
| Hava / trafik | Var | Var |
| Tuvalet | En yakın 5 tuvalet | + filtreler (bakım odası, istasyonda) |
| Gezi | **Beta**: tek plan, backtracking + dal budama | İki plan, kesişme yasağı, yokuş ve gezme sırası cezaları, dönüş noktası, Müzekart, tempo |
| Testler, ölçümler | Yok (sonuçlar sunumda) | 46 otomatik kontrol, naif/heap, ızgara, greedy/brute force karşılaştırmaları |

## Çalıştırma
- **Colab:** `gitgez_sade.ipynb` + `../yokus-gezi/gitgez_veri.zip` (açmadan) → *Tümünü çalıştır* (~20 sn).
- **Bilgisayar:** bu klasörde `python app.py` → `http://127.0.0.1:7860`. Veri zip'ini `../yokus-gezi/` içinde kendisi bulur.

`app.py` defterden üretilir; değişiklikleri **deftere** yapın, sonra:
```bash
python tools/export_app.py sade/gitgez_sade.ipynb sade/app.py
```

## Kurallar (sade sürümde kalanlar)
| Kural | Neden |
|---|---|
| Her binişte +2 dk "aktarma zahmeti" (ekranda gösterilmez) | Aynı sürede az aktarmalı rota kazansın |
| "Az yürüme"de 1 dk yürüme = 4 dk araç | Yürümeyi gerçekten azaltsın |
| Yürüme üstüne yürüme yok · binip hemen inmek yok | Algoritmanın "hile" yapmasını önler (duraktan durağa 40 dk yürüme) |
| Bekleme = sefer aralığının yarısı, en az 1, en çok 30 dk | Saatlik sefer sayısından tahmin |
| Alternatif en iyisinden en fazla 30 dk uzun | Gece 03:00'te 5 saatlik "alternatif" çıkmasın |
| Gezi: müze/cami girişine +10 dk, "geçiş" yerleri (merdiven, meydan) puanın %60'ı, en fazla 12 aday yer | Küçük yerler büyüklerin yerini kapmasın; backtracking'in en kötü durumu O(n!) |

**Ayrıntılı sürümden çıkarılanlar:** alternatif seçimindeki karmaşık eleme kuralları (aynı koridor %80, "baskın rota",
"yürümek daha hızlıysa araçlı rota ancak yokuşu 20 m azaltıyorsa"), gezide "insanların gezme sırası" cezası (ρ),
yokuş cezası (γ), rotanın kendini kesme yasağı, caddenin iki yönü.
