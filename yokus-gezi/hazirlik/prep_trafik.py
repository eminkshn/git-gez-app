"""İBB "Saatlik Trafik Yoğunluk Veri Seti" CSV'lerinden trafik.csv üretir.

Kullanım:
    python prep_trafik.py traffic_density_202410.csv [traffic_density_202411.csv ...] -o trafik.csv

Çıktı (uygulama DATA_DIR içinde ya da yanında arar):
    geohash, gun, saat, carpan
    gun   : hi (hafta içi) / cmt / paz
    carpan: o bölgenin TÜM saatlerdeki medyan hızı / o gün tipi ve saatteki medyan hızı
            (1.3 = normalden %30 yavaş -> otobüs o saatte %30 uzun sürer). Uygulama 0.7–2.0 arasına kırpar.

Neden medyan? Tek tük hatalı ölçümler (0 km/sa, 200 km/sa) sonucu bozmasın.
Neden "tüm saatlerin medyanı" referans? Otobüs durak arası süreleri sabit ortalama hızla tahmin edildi;
o ortalama "tipik saat"e karşılık gelir, çarpan da ona göre ölçülür.
"""
import argparse
import csv
import sys
from collections import defaultdict
from datetime import datetime
from statistics import median

ALAN = {  # beklenen sütunlar (büyük/küçük harf fark etmez)
    "zaman": ["DATE_TIME", "DATETIME", "TARIH"],
    "gh": ["GEOHASH"],
    "hiz": ["AVERAGE_SPEED", "ORTALAMA_HIZ"],
    "lat": ["LATITUDE"], "lon": ["LONGITUDE"],
}
_B32 = "0123456789bcdefghjkmnpqrstuvwxyz"


def geohash(lat, lon, n=6):  # uygulamadaki ile aynı
    la, lo, out, bits, ch, even = [-90.0, 90.0], [-180.0, 180.0], [], 0, 0, True
    while len(out) < n:
        rng, v = (lo, lon) if even else (la, lat)
        mid = (rng[0] + rng[1]) / 2
        if v >= mid:
            ch = ch * 2 + 1; rng[0] = mid
        else:
            ch = ch * 2; rng[1] = mid
        even, bits = not even, bits + 1
        if bits == 5:
            out.append(_B32[ch]); bits, ch = 0, 0
    return "".join(out)


def sutun(baslik, ad):
    up = {h.strip().upper(): h for h in baslik}
    for aday in ALAN[ad]:
        if aday in up:
            return up[aday]
    return None


def zaman_oku(s):
    s = s.strip()[:19]
    for f in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M", "%d.%m.%Y %H:%M:%S", "%d.%m.%Y %H:%M"):
        try:
            return datetime.strptime(s, f)
        except ValueError:
            pass
    return None


def gun_tipi(wd):
    return "paz" if wd == 6 else "cmt" if wd == 5 else "hi"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("csvler", nargs="+")
    ap.add_argument("-o", "--out", default="trafik.csv")
    ap.add_argument("--min-olcum", type=int, default=3, help="bir (bölge, gün, saat) için en az ölçüm sayısı")
    a = ap.parse_args()

    hizlar = defaultdict(list)          # (gh, gun, saat) -> hızlar
    okunan = atlanan = 0
    for yol in a.csvler:
        with open(yol, encoding="utf-8-sig", newline="") as f:
            r = csv.DictReader(f)
            c = {k: sutun(r.fieldnames, k) for k in ALAN}
            if not c["zaman"] or not c["hiz"] or not (c["gh"] or (c["lat"] and c["lon"])):
                sys.exit(f"{yol}: beklenen sütunlar yok. Bulunan: {r.fieldnames}")
            for row in r:
                t = zaman_oku(row[c["zaman"]])
                try:
                    v = float(row[c["hiz"]].replace(",", "."))
                    gh = (row[c["gh"]].strip()[:6] if c["gh"] and row[c["gh"]].strip()
                          else geohash(float(row[c["lat"]]), float(row[c["lon"]]), 6))
                except (ValueError, TypeError):
                    t = None
                if t is None or not (1 <= v <= 150):
                    atlanan += 1
                    continue
                hizlar[(gh.lower(), gun_tipi(t.weekday()), t.hour)].append(v)
                okunan += 1
    print(f"{okunan:,} ölçüm okundu, {atlanan:,} atlandı")

    bolge = defaultdict(list)
    for (gh, _, _), vs in hizlar.items():
        bolge[gh].extend(vs)
    ref = {gh: median(vs) for gh, vs in bolge.items()}

    n = 0
    with open(a.out, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["geohash", "gun", "saat", "carpan"])
        for (gh, gun, saat), vs in sorted(hizlar.items()):
            if len(vs) < a.min_olcum:
                continue
            w.writerow([gh, gun, saat, round(ref[gh] / median(vs), 3)])
            n += 1
    print(f"{a.out}: {n:,} satır, {len(ref):,} bölge")


if __name__ == "__main__":
    main()
