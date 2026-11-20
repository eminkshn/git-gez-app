"""İBB GTFS (raylı/vapur + İETT) -> istanbul_ag.zip içindeki sıkıştırılmış ağ dosyaları.
Kullanım: python veri_hazirlama.py <diger_klasoru> <iett_klasoru> <iett_stop_times.txt> <cikis_klasoru>
"""
import sys, os, math, re
from collections import Counter
import pandas as pd
import numpy as np

DIGER, IETT, IETT_ST, OUT = sys.argv[1:5]
os.makedirs(OUT, exist_ok=True)

BUS_KMH = 18.0        # İETT ortalama ticari hız (duraklar dahil) - varsayım
BRT_KMH = 32.0        # Metrobüs (ayrı yol) - varsayım
ROAD_FACTOR = 1.25    # kuş uçuşu -> yol mesafesi
MAX_WAIT = 15.0       # ortalama bekleme üst sınırı (dk)
BBOX = (40.70, 41.65, 27.90, 29.95)


def hav(lat1, lon1, lat2, lon2):
    R = 6371000.0
    p1, p2 = np.radians(lat1), np.radians(lat2)
    dp, dl = p2 - p1, np.radians(lon2 - lon1)
    a = np.sin(dp / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dl / 2) ** 2
    return 2 * R * np.arcsin(np.sqrt(a))


def tsec(s):
    if not isinstance(s, str) or not s:
        return np.nan
    h, m, x = s.split(":")
    return int(h) * 3600 + int(m) * 60 + int(x)


def wait_from_headway(h):
    if h is None or not np.isfinite(h) or h <= 0:
        return MAX_WAIT
    return float(min(max(h / 2, 1.0), MAX_WAIT))


stops_out, lines_out, ls_out = [], [], []

# ------------------------------------------------------------ RAYLI + VAPUR
r = pd.read_csv(f"{DIGER}/routes.csv", encoding="cp1254", dtype=str)
t = pd.read_csv(f"{DIGER}/trips.csv", encoding="cp1254", dtype=str)
st = pd.read_csv(f"{DIGER}/stop_times.csv", encoding="cp1254", dtype=str)
fq = pd.read_csv(f"{DIGER}/frequencies.csv", dtype=str)
sp = pd.read_csv(f"{DIGER}/stops.csv", encoding="cp1254", dtype=str)

KEEP_AGENCY = {"11", "4", "6", "48", "33", "20"}   # Metro İst., Marmaray, Şehir Hatları, Turyol, Dentur, İDO
r = r[r.agency_id.isin(KEEP_AGENCY)]
tour = r.route_long_name.str.contains(r"TUR|BOĞAZA GİDİŞ|BOĞAZDAN GELİŞ|FEST", case=False, na=False)
r = r[~tour]

def rail_mode(row):
    if row.agency_id == "4":
        return "Marmaray"
    if row.agency_id in ("6", "48", "33", "20"):
        return "Vapur"
    return {"1": "Metro", "0": "Tramvay", "7": "Füniküler", "6": "Teleferik"}.get(row.route_type, "Raylı")

r["mode"] = r.apply(rail_mode, axis=1)
t = t[t.route_id.isin(r.route_id)]
st = st[st.trip_id.isin(t.trip_id)].copy()
st["seq"] = st.stop_sequence.astype(int)
st["arr"] = st.arrival_time.map(tsec)
st = st.sort_values(["trip_id", "seq"])
trip_seq = st.groupby("trip_id").agg(stops=("stop_id", tuple), arr=("arr", list))
trip_seq = trip_seq.join(t.set_index("trip_id")[["route_id", "direction_id", "service_id"]])

fq["h"] = fq.headway_secs.astype(float) / 60

# ---- saatlik kalkış sayıları: hours_out[(line_id, gün)] = 24 elemanlı liste
DAYS = ("hi", "cmt", "paz")
hours_out = {}
cal = pd.read_csv(f"{DIGER}/calendar.csv", dtype=str)
cal = cal[cal.end_date >= "20230101"]                      # eski (2019) servisleri atla
svc_days = {}
for c in cal.itertuples():
    ds = set()
    if c.monday == "1": ds.add("hi")
    if c.saturday == "1": ds.add("cmt")
    if c.sunday == "1": ds.add("paz")
    svc_days[c.service_id] = ds
fq_win = {}
for f in fq.itertuples():
    fq_win.setdefault(f.trip_id, []).append((tsec(f.start_time), tsec(f.end_time), float(f.headway_secs)))

def add_departures(key_lid, day_set, times, factor=1.0):
    for day in day_set:
        h = hours_out.setdefault((key_lid, day), [0.0] * 24)
        for t in times:
            if np.isfinite(t):
                h[int(t // 3600) % 24] += factor
fq_by_trip = fq.groupby("trip_id").h.median()

used_rail_stops = set()
for (rid, d), grp in trip_seq.groupby(["route_id", "direction_id"], dropna=False):
    common = Counter(grp.stops).most_common(1)[0][0]
    if len(common) < 2:
        continue
    same = grp[grp.stops == common]
    diffs = np.array([np.diff(a) for a in same.arr], dtype=float) / 60.0
    seg = np.nanmedian(diffs, axis=0)
    seg = np.where(np.isfinite(seg) & (seg > 0), seg, 1.0)
    # sıklık: frequencies varsa onu, yoksa en yoğun servis gününde 07-20 arası sefer sayısı
    fh = fq_by_trip.reindex(grp.index).dropna()
    if len(fh):
        headway = float(fh.median())
    else:
        svc = grp.service_id.value_counts().idxmax()
        g2 = grp[grp.service_id == svc]
        starts = np.array([a[0] for a in g2.arr], dtype=float)
        n = np.sum((starts >= 7 * 3600) & (starts < 20 * 3600))
        headway = 13 * 60 / n if n else np.nan
    row = r[r.route_id == rid].iloc[0]
    lid = f"R{rid}_{d}"
    for tid, tr in grp.iterrows():
        days = svc_days.get(tr.service_id, set())
        if tid in fq_win:                                    # sıklıkla tanımlı sefer (ör. Marmaray)
            times = [t for a, b, hw in fq_win[tid] for t in np.arange(a, b, hw)]
        else:
            times = [tr.arr[0]]
        add_departures(lid, days, times)
    lines_out.append((lid, row.route_short_name, row.route_long_name, row["mode"], round(wait_from_headway(headway), 1)))
    for i, s in enumerate(common):
        ls_out.append((lid, i, "R" + s, 0.0 if i == 0 else round(float(seg[i - 1]), 2)))
        used_rail_stops.add(s)

sp = sp[sp.stop_id.isin(used_rail_stops)]
for row in sp.itertuples():
    wb = row.wheelchair_boarding if row.wheelchair_boarding in ("1", "2") else ""   # 1 erişilebilir, 2 değil, boş = bilgi yok
    stops_out.append(("R" + row.stop_id, row.stop_name.strip(), float(row.stop_lat), float(row.stop_lon), wb))
print("raylı/vapur:", len(lines_out), "hat", len(sp), "durak")

# ------------------------------------------------------------ İETT
def fix_moji(x):
    if not isinstance(x, str):
        return x
    # UTF-8 baytları yanlışlıkla cp1252/latin-1 diye okunmuş metni geri çevir
    out = bytearray()
    for ch in x:
        if ord(ch) < 256:
            out.append(ord(ch))
        else:
            try:
                out += ch.encode("cp1252")
            except UnicodeEncodeError:
                return x
    try:
        return out.decode("utf-8")
    except UnicodeDecodeError:
        return x

def fix_coord(x):
    """Excel binlik ayırıcıyla bozulmuş '410.191.700.005.564' -> 41.0191700005564"""
    if not isinstance(x, str):
        return np.nan
    digits = re.sub(r"\D", "", x)
    if len(digits) < 4:
        return np.nan
    return float(digits[:2] + "." + digits[2:])

bs = pd.read_csv(f"{IETT}/stops.csv", sep=";", dtype=str, encoding="utf-8-sig")
bs["lat"] = bs.stop_lat.map(fix_coord)
bs["lon"] = bs.stop_lon.map(fix_coord)
ok = bs.lat.between(BBOX[0], BBOX[1]) & bs.lon.between(BBOX[2], BBOX[3])
print("İETT durak:", len(bs), "koordinatı geçersiz:", int((~ok).sum()))
bs = bs[ok]
bpos = bs.set_index("stop_id")[["lat", "lon"]]

br = pd.read_csv(f"{IETT}/routes.csv", sep=";", dtype=str, encoding="utf-8-sig")
br["route_long_name"] = br.route_long_name.map(fix_moji)
bt = pd.read_csv(f"{IETT}/trips.csv", sep=";", dtype=str, encoding="utf-8-sig")
bst = pd.read_csv(IETT_ST, dtype=str, usecols=["trip_id", "stop_id", "stop_sequence", "arrival_time"])
bst["seq"] = bst.stop_sequence.astype(int)
bst = bst.sort_values(["trip_id", "seq"])
bst = bst[bst.stop_id.isin(bpos.index)]               # koordinatsız durakları çıkar
first = bst.groupby("trip_id").arrival_time.first().map(tsec)
bseq = bst.groupby("trip_id").stop_id.agg(tuple).to_frame("stops")
bseq["start"] = first
bseq = bseq.join(bt.set_index("trip_id")[["route_id", "service_id"]])

# sıklık: aynı hat numarası için (tüm varyantlar birlikte) hafta içi 07-20 arası sefer sayısı
bt2 = bt.merge(br[["route_id", "route_short_name"]], on="route_id")
bt2["start"] = bt2.trip_id.map(first)
wk = bt2[(bt2.service_id == "0") & (bt2.start >= 7 * 3600) & (bt2.start < 20 * 3600)]
cnt = wk.groupby("route_short_name").size() / 2      # iki yönün ortalaması
IETT_DAY = {"0": "hi", "6": "cmt", "7": "paz"}
bt2["hour"] = (bt2.start // 3600 % 24)
hourly = (bt2.dropna(subset=["start"]).assign(day=lambda x: x.service_id.map(IETT_DAY))
          .dropna(subset=["day"]).groupby(["route_short_name", "day", "hour"]).size() / 2)

METROBUS = re.compile(r"^34[A-Z]{0,2}$")
used_bus = set()
nb = 0
for rid, grp in bseq.groupby("route_id"):
    common = Counter(grp.stops).most_common(1)[0][0]
    if len(common) < 2:
        continue
    row = br[br.route_id == rid]
    if row.empty:
        continue
    row = row.iloc[0]
    short = str(row.route_short_name).strip()
    mode = "Metrobüs" if METROBUS.match(short) else "Otobüs"
    kmh = BRT_KMH if mode == "Metrobüs" else BUS_KMH
    if mode == "Metrobüs":
        # metrobüs duraklarında 34, 34AS, 34BZ... hepsi aynı yoldan geçer: gelen ilk araca binilir
        n = sum(v for k, v in cnt.items() if METROBUS.match(str(k)))
    else:
        n = cnt.get(row.route_short_name, 0)
    headway = 13 * 60 / n if n else np.nan
    lat = bpos.loc[list(common), "lat"].values
    lon = bpos.loc[list(common), "lon"].values
    dist = hav(lat[:-1], lon[:-1], lat[1:], lon[1:]) * ROAD_FACTOR
    mins = dist / (kmh * 1000 / 60)
    lid = f"B{rid}"
    keys = [k for k in cnt.index if METROBUS.match(str(k))] if mode == "Metrobüs" else [row.route_short_name]
    for day in DAYS:
        h = [0.0] * 24
        for k in keys:
            sub = hourly.get(k)
            if sub is not None and day in sub.index.get_level_values(0):
                for hr, v in sub.loc[day].items():
                    h[int(hr)] += float(v)
        if any(h):
            hours_out[(lid, day)] = h
    lines_out.append((lid, fix_moji(short), row.route_long_name, mode, round(wait_from_headway(headway), 1)))
    for i, s in enumerate(common):
        ls_out.append((lid, i, "B" + s, 0.0 if i == 0 else round(float(max(mins[i - 1], 0.3)), 2)))
        used_bus.add(s)
    nb += 1

bs = bs[bs.stop_id.isin(used_bus)]
for row in bs.itertuples():
    stops_out.append(("B" + row.stop_id, row.stop_name.strip(), round(row.lat, 7), round(row.lon, 7), ""))
print("İETT:", nb, "hat", len(bs), "durak")

pd.DataFrame(stops_out, columns=["stop_id", "name", "lat", "lon", "wheelchair"]).to_csv(f"{OUT}/stops.csv", index=False)
pd.DataFrame(lines_out, columns=["line_id", "short_name", "long_name", "mode", "wait_min"]).to_csv(f"{OUT}/lines.csv", index=False)
pd.DataFrame(ls_out, columns=["line_id", "seq", "stop_id", "min_from_prev"]).to_csv(f"{OUT}/line_stops.csv", index=False)
rows = [(lid, day, hr, round(v, 2)) for (lid, day), h in hours_out.items() for hr, v in enumerate(h) if v > 0]
pd.DataFrame(rows, columns=["line_id", "day", "hour", "departures"]).to_csv(f"{OUT}/line_hours.csv", index=False)
print("saatlik kayıt:", len(rows), "· saat bilgisi olan hat:", len({r[0] for r in rows}))
print("toplam:", len(stops_out), "durak", len(lines_out), "hat", len(ls_out), "hat-durak")
