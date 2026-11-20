"""İstanbul Toplu Taşıma Rota Planlayıcı — yerel arayüz.
Kurulum: pip install gradio folium pandas requests
Çalıştırma: istanbul_ag.zip ile aynı klasörde  ->  python app.py  (tarayıcıda açılır)
"""
import os
os.chdir(os.path.dirname(os.path.abspath(__file__)))



# ----------------------------------------------------------------------

import os, glob, shutil, zipfile

DATA_DIR = "istanbul_ag"
GEREKLI = {"stops.csv", "lines.csv", "line_stops.csv", "line_hours.csv", "tuvaletler.csv"}

def uygun_zipler():
    """Klasördeki istanbul_ag*.zip dosyalarından içinde gerekli tüm dosyalar olanlar (en yenisi önce).
    Colab aynı adla ikinci kez yüklenen dosyayı 'istanbul_ag (1).zip' diye kaydeder; onu da bulur."""
    out = []
    for z in sorted(glob.glob("istanbul_ag*.zip"), key=os.path.getmtime, reverse=True):
        try:
            with zipfile.ZipFile(z) as f:
                if GEREKLI <= set(f.namelist()):
                    out.append(z)
        except zipfile.BadZipFile:
            pass
    return out

if not uygun_zipler():
    eski = glob.glob("istanbul_ag*.zip")
    if eski:
        print("⚠ Eski/eksik veri dosyası bulundu (line_hours.csv yok):", eski, "- siliniyor.")
        for z in eski:
            os.remove(z)
    try:
        from google.colab import files          # sadece Colab'da var
        print("Lütfen GÜNCEL istanbul_ag.zip dosyasını seçin...")
        files.upload()
    except ImportError:
        raise FileNotFoundError("Güncel istanbul_ag.zip bu defterle aynı klasörde olmalı")

zipler = uygun_zipler()
if not zipler:
    raise FileNotFoundError("Yüklenen zip'te gerekli dosyalar yok: " + ", ".join(sorted(GEREKLI)))
shutil.rmtree(DATA_DIR, ignore_errors=True)            # eski açılmış klasör kalmasın
with zipfile.ZipFile(zipler[0]) as z:
    z.extractall(DATA_DIR)
print("Kullanılan veri:", zipler[0], "->", sorted(os.listdir(DATA_DIR)))

WALK_MAX_M     = 2000   # aktarmada / başlangıç-varışta en fazla bu kadar metre yürünür
WALK_M_PER_MIN = 75     # yürüme hızı (≈ 4,5 km/sa)
WALK_DETOUR    = 1.3    # kuş uçuşu mesafe -> gerçek yürüme mesafesi
WALK_WEIGHT    = 4      # "en az yürüme" kriterinde 1 dk yürüme = 4 dk araçta
BOARD_PENALTY  = 2      # her araca binişte "aktarma zahmeti" payı (dk)
PLACE_RADIUS_M = 800    # aynı adlı duraklardan birbirine bu kadar yakın olanlar "aynı yer" sayılır
MAX_WAIT       = 30     # bir saatte çok az sefer varsa bekleme en fazla bu kadar (dk)
VARSAYILAN_GUN, VARSAYILAN_SAAT = "hi", 8     # hi = hafta içi, cmt = cumartesi, paz = pazar

import csv, math
from collections import defaultdict

def load_network(folder):
    stops, lines, line_stops, hours = {}, {}, defaultdict(list), {}
    with open(f"{folder}/stops.csv", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            stops[r["stop_id"]] = {"name": r["name"], "lat": float(r["lat"]), "lon": float(r["lon"]),
                                   "wc": r.get("wheelchair", "")}       # "1" = tekerlekli sandalyeye uygun
    with open(f"{folder}/lines.csv", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            lines[r["line_id"]] = {"short": r["short_name"], "long": r["long_name"],
                                   "mode": r["mode"], "wait": float(r["wait_min"])}
    with open(f"{folder}/line_stops.csv", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            line_stops[r["line_id"]].append((int(r["seq"]), r["stop_id"], float(r["min_from_prev"])))
    with open(f"{folder}/line_hours.csv", encoding="utf-8") as f:     # saatlik kalkış sayıları
        for r in csv.DictReader(f):
            hours.setdefault((r["line_id"], r["day"]), [0.0] * 24)[int(r["hour"])] = float(r["departures"])
    for lid in line_stops:
        line_stops[lid].sort()
    return stops, lines, dict(line_stops), hours

stops, lines, line_stops, hours = load_network(DATA_DIR)

import pandas as pd
ozet = pd.DataFrame(lines.values()).groupby("mode").agg(hat=("short", "count"))
print(f"{len(stops):,} durak, {len(lines):,} hat")
print(ozet.sort_values("hat", ascending=False).T.to_string())

import unicodedata, difflib

TR_MAP = str.maketrans("çğıöşüÇĞİÖŞÜâîû", "cgiosuCGIOSUaiu")

def normalize(text):
    text = text.translate(TR_MAP).lower()
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return " ".join("".join(c if c.isalnum() else " " for c in text).split())

def haversine_m(lat1, lon1, lat2, lon2):
    """İki koordinat arası kuş uçuşu mesafe (metre)"""
    R = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))

class StopIndex:
    def __init__(self, stops):
        self.by_name = defaultdict(list)                 # hash tablosu
        for sid, s in stops.items():
            self.by_name[normalize(s["name"])].append(sid)

    def find(self, query):
        q = normalize(query)
        if q in self.by_name:                            # 1) tam eşleşme: O(1)
            return q, self.by_name[q]
        starts = [n for n in self.by_name if n.startswith(q + " ") or n.startswith(q)]
        if starts:                                       # 2) bu kelimeyle başlayan tüm adlar
            return q, [i for n in starts for i in self.by_name[n]]   # ("Beşiktaş" -> Beşiktaş Meydan, Beşiktaş İDO...)
        close = difflib.get_close_matches(q, self.by_name.keys(), n=1, cutoff=0.6)
        if close:                                        # 3) yazım hatası toleransı
            return close[0], self.by_name[close[0]]
        return None, []

    def suggest(self, query, n=5):
        return difflib.get_close_matches(normalize(query), self.by_name.keys(), n=n, cutoff=0.4)

    def place(self, query, stops, adj):
        name, ids = self.find(query)
        if not ids:
            return name, []
        hub = max(ids, key=lambda i: sum(1 for e in adj.get(i, ()) if e[2] == "board"))
        h = stops[hub]
        return name, [i for i in ids
                      if haversine_m(h["lat"], h["lon"], stops[i]["lat"], stops[i]["lon"]) <= PLACE_RADIUS_M]

index = StopIndex(stops)
for q in ["kadikoy", "TAKSİM", "Besiktas", "üsküdr", "Sabiha"]:
    name, ids = index.find(q)
    print(f"{q!r:<12} -> {name!r:<28} {len(ids)} durak")

class Grid:
    """Kare kenarı >= WALK_MAX_M olmalı; yoksa komşu 8 kare yetmez ve yakın duraklar kaçar.
    1° enlem ≈ 111,3 km; 1° boylam ≈ 111,3 km × cos(enlem) (İstanbul'da ≈ 84 km)."""
    def __init__(self, stops, cell_m=None):
        cell_m = cell_m or WALK_MAX_M
        self.dlat = cell_m / 111_320
        self.dlon = cell_m / (111_320 * math.cos(math.radians(41.0)))
        self.cells = defaultdict(list)
        for sid, s in stops.items():
            self.cells[self.key(s["lat"], s["lon"])].append(sid)

    def key(self, lat, lon):
        return (int(lat / self.dlat), int(lon / self.dlon))

    def near(self, lat, lon):
        i, j = self.key(lat, lon)
        for di in (-1, 0, 1):
            for dj in (-1, 0, 1):
                yield from self.cells.get((i + di, j + dj), ())

grid = Grid(stops)

def build_walks():
    """Yürüme mesafesindeki tüm durak çiftleri. Saate bağlı olmadığı için bir kez hesaplanır."""
    walks = defaultdict(list)
    for sid, s in stops.items():
        for other in grid.near(s["lat"], s["lon"]):
            if other != sid:
                o = stops[other]
                d = haversine_m(s["lat"], s["lon"], o["lat"], o["lon"])
                if d <= WALK_MAX_M:
                    walks[sid].append((other, d * WALK_DETOUR / WALK_M_PER_MIN, "walk", None))
    return dict(walks)

import time
t0 = time.perf_counter()
WALKS = build_walks()
print(f"{sum(map(len, WALKS.values())):,} yürüme bağlantısı ({WALK_MAX_M} m'ye kadar), {time.perf_counter() - t0:.1f} sn")
print(f"{len(grid.cells):,} dolu kare, kare başına ort. {len(stops) / len(grid.cells):.1f} durak")

def wait_at(lid, gun, saat):
    """O gün/saatte hattın ortalama beklemesi (dk). Sefer yoksa None -> hat kullanılmaz."""
    h = hours.get((lid, gun))
    if h is None:
        return None
    n = h[saat]
    if n == 0 and h[saat - 1] == 0:          # bu saatte ve bir önceki saatte kalkış yok
        return None
    n = n or 1                               # önceki saatte kalkan araç hâlâ yolda olabilir
    return min(max(60 / n / 2, 1.0), MAX_WAIT)

def build_graph(gun, saat):
    """Hat kenarları: bin (bekleme), git (yolculuk), in. Yürüme kenarları WALKS'ta, ortak."""
    adj = defaultdict(list)
    aktif = 0
    for lid, seq in line_stops.items():
        wait = wait_at(lid, gun, saat)
        if wait is None:
            continue                         # o saatte çalışmayan hat
        aktif += 1
        for i, (_, sid, _) in enumerate(seq):
            node = (lid, i)
            adj[sid].append((node, wait + BOARD_PENALTY, "board", lid))
            adj[node].append((sid, 0.0, "alight", lid))
            if i + 1 < len(seq):
                adj[node].append(((lid, i + 1), seq[i + 1][2], "ride", lid))
    return dict(adj), aktif

_graph_cache = {}
def get_graph(gun, saat):
    if (gun, saat) not in _graph_cache:
        _graph_cache[(gun, saat)] = build_graph(gun, saat)
    return _graph_cache[(gun, saat)]

adj, aktif = get_graph(VARSAYILAN_GUN, VARSAYILAN_SAAT)
for saat in (3, 8, 13, 23):
    print(f"hafta içi {saat:02d}:00 -> {get_graph('hi', saat)[1]:,} hat çalışıyor")

import heapq, itertools

DEST = ("__VARIŞ__", "end")

def dijkstra(adj, sources, targets, objective="time", walks=None):
    """sources / targets: {durak: o durağa yürüme dakikası} (liste de olabilir -> 0 dk)."""
    walks = WALKS if walks is None else walks
    if not isinstance(sources, dict): sources = {s: 0.0 for s in sources}
    if not isinstance(targets, dict): targets = {t: 0.0 for t in targets}

    def cost_of(minutes, kind):
        if objective == "transfers":
            return (1 if kind == "board" else 0, minutes)
        if objective == "walk" and kind in ("walk", "walk_end"):
            return (minutes * WALK_WEIGHT,)
        return (minutes,)

    def add(a, b):
        return tuple(x + y for x, y in zip(a, b))

    zero = (0, 0.0) if objective == "transfers" else (0.0,)
    best, prev, heap, counter = {}, {}, [], 0
    for s, w in sources.items():
        state = (s, "walk" if w > 0 else "start")
        c = add(zero, cost_of(w, "walk"))
        if state not in best or c < best[state]:
            best[state] = c
            heap.append((c, counter, state)); counter += 1
    heapq.heapify(heap)                                  # Min-Heap
    done = set()
    while heap:
        cost, _, state = heapq.heappop(heap)            # en ucuz durum
        if state in done:
            continue                                     # tembel silme: eski kayıt
        done.add(state)
        if state == DEST:
            return cost, rebuild_path(prev, state), len(done)
        node, last = state
        if node in targets and not (last == "walk" and targets[node] > 0):
            new = add(cost, cost_of(targets[node], "walk_end"))
            if DEST not in best or new < best[DEST]:
                best[DEST] = new
                prev[DEST] = (state, targets[node], "walk_end", None)
                heapq.heappush(heap, (new, counter, DEST)); counter += 1
        edges = adj.get(node, ())
        if isinstance(node, str) and last != "walk":     # iki yürüme üst üste olmaz
            edges = itertools.chain(edges, walks.get(node, ()))
        for nxt, minutes, kind, lid in edges:
            if kind == "alight" and last == "board":
                continue                                 # bin-in hilesi yok
            nstate = (nxt, kind)
            new = add(cost, cost_of(minutes, kind))
            if nstate not in best or new < best[nstate]:
                best[nstate] = new
                prev[nstate] = (state, minutes, kind, lid)
                heapq.heappush(heap, (new, counter, nstate)); counter += 1
    return None, [], len(done)

def rebuild_path(prev, state):
    path = []
    while state in prev:
        p, minutes, kind, lid = prev[state]
        path.append((p[0], state[0], minutes, kind, lid))
        state = p
    return path[::-1]

import requests

lines_at = defaultdict(set)                              # durak -> o duraktan geçen hat numaraları
for lid, seq in line_stops.items():
    for _, sid, _ in seq:
        lines_at[sid].add(lines[lid]["short"])
landmarks = [sid for sid in stops if sid.startswith("R")]   # raylı sistem istasyonları ve iskeleler

def yakin_istasyon(lat, lon):
    sid = min(landmarks, key=lambda i: haversine_m(lat, lon, stops[i]["lat"], stops[i]["lon"]))
    return stops[sid]["name"], haversine_m(lat, lon, stops[sid]["lat"], stops[sid]["lon"]) / 1000

def near_stops(lat, lon, radius=WALK_MAX_M):
    """Noktaya yürüme mesafesindeki duraklar: {durak: yürüme dk}"""
    out = {}
    for sid in grid.near(lat, lon):
        d = haversine_m(lat, lon, stops[sid]["lat"], stops[sid]["lon"])
        if d <= radius:
            out[sid] = d * WALK_DETOUR / WALK_M_PER_MIN
    return out

def durak_yerleri(query, limit=6, benzer=False):
    """Adında sorgu geçen duraklar. benzer=True: yazım hatasına dayanıklı benzerlik araması (difflib)."""
    q = normalize(query)
    if not q:
        return []
    names = index.suggest(query, n=3) if benzer else [n for n in index.by_name if q in n]
    rank = lambda n: (0 if n == q else 1 if n.startswith(q) else 2, len(n))
    places = []
    for n in (names if benzer else sorted(names, key=rank)):     # benzerlik sonuçları zaten en benzer önce
        clusters = []                                    # aynı adlı durakları konuma göre grupla
        for sid in sorted(index.by_name[n], key=lambda i: -len(lines_at[i])):
            s = stops[sid]
            for c in clusters:
                h = stops[c[0]]
                if haversine_m(h["lat"], h["lon"], s["lat"], s["lon"]) <= PLACE_RADIUS_M:
                    c.append(sid); break
            else:
                clusters.append([sid])
        for c in clusters:
            h = stops[c[0]]
            hatlar = sorted(set().union(*(lines_at[i] for i in c)))
            ist, km = yakin_istasyon(h["lat"], h["lon"])
            if c[0].startswith("R"):
                yer = "raylı istasyon / iskele"
            elif km <= 3:
                yer = f"{ist} yakını ({km:.1f} km)"
            else:
                yer = f"en yakın istasyon/iskele {ist}, {km:.0f} km"
            label = f"🚏 {h['name']} — {yer} · hatlar: {', '.join(hatlar[:4])}{'…' if len(hatlar) > 4 else ''}"
            places.append({"label": label, "lat": h["lat"], "lon": h["lon"], "access": {i: 0.0 for i in c}})
        if len(places) >= limit:
            break
    return places[:limit]

def adres_yerleri(query, limit=4):
    """OpenStreetMap Nominatim ile adres/mekân arama (internet gerekir; çalışmazsa boş liste)."""
    if len(query.strip()) < 3:
        return []
    try:
        r = requests.get("https://nominatim.openstreetmap.org/search",
                         params={"q": query, "format": "jsonv2", "addressdetails": 1, "limit": limit,
                                 "countrycodes": "tr", "viewbox": "27.9,41.65,29.95,40.7", "bounded": 1,
                                 "accept-language": "tr"},
                         headers={"User-Agent": "istanbul-rota-ders-projesi/1.0"}, timeout=8)
        r.raise_for_status()
        results = r.json()
    except Exception as e:
        print(f"(adres araması yapılamadı: {type(e).__name__})")
        return []
    places = []
    for x in results:
        lat, lon = float(x["lat"]), float(x["lon"])
        access = near_stops(lat, lon)
        if not access:
            continue
        a = x.get("address", {})
        parts = [x.get("name") or x["display_name"].split(",")[0],
                 a.get("suburb") or a.get("quarter") or a.get("neighbourhood"),
                 a.get("town") or a.get("city_district") or a.get("county")]
        label = "📍 " + ", ".join(dict.fromkeys(p for p in parts if p))
        places.append({"label": label, "lat": lat, "lon": lon, "access": access})
    return places

def yer_ara(query):
    """Önce adında sorgu geçen duraklar, sonra adres/mekân sonuçları.
    İkisi de boşsa yazımı benzeyen duraklar ('kadıkoy' -> 'Kadıköy')."""
    return (durak_yerleri(query) + adres_yerleri(query)) or durak_yerleri(query, benzer=True)

for p in durak_yerleri("Taşköprü"):
    print(p["label"])

import folium, html as _html
try:
    from IPython.display import display
except ImportError:                                      # Jupyter dışında (python app.py)
    display = print

MODE_ICON = {"Metro": "🚇", "Marmaray": "🚆", "Tramvay": "🚊", "Füniküler": "🚞", "Teleferik": "🚡",
             "Vapur": "⛴️", "Metrobüs": "🚌", "Otobüs": "🚌"}
# Hat renkleri: Metro İstanbul harita renklerine yakın değerler (resmi haritaya göre buradan değiştirilebilir)
LINE_COLOR = {"M1A": "#E2231A", "M1B": "#E2231A", "M2": "#009A4D", "M2A": "#009A4D", "M3": "#0098D8",
              "M3A": "#0098D8", "M4": "#E5007E", "M5": "#6F2A91", "M6": "#C49A6C", "M7": "#F49AC1",
              "M8": "#4A90D9", "M9": "#F5C400", "T1": "#0067AC", "T3": "#8B5A2B", "T4": "#F39200",
              "F1": "#8B5A2B", "F2": "#7F7F7F", "F3": "#8DC63F", "TF1": "#A0522D", "TF2": "#A0522D"}
MODE_COLOR = {"Marmaray": "#1F5FAD", "Metrobüs": "#B5121B", "Vapur": "#0B3C5D", "Otobüs": "#00897B",
              "Metro": "#555555", "Tramvay": "#0067AC", "Füniküler": "#8B5A2B", "Teleferik": "#A0522D"}
GUN_ADI = {"hi": "hafta içi", "cmt": "cumartesi", "paz": "pazar"}
KRITER = {"süre": "time", "aktarma": "transfers", "yürüme": "walk"}
PSEUDO = {}                                              # başlangıç/varış noktası (adres) için geçici "durak"

def hat_rengi(lid):
    L = lines[lid]
    if L["mode"] in ("Metro", "Tramvay", "Füniküler", "Teleferik") and L["short"] in LINE_COLOR:
        return LINE_COLOR[L["short"]]
    return MODE_COLOR.get(L["mode"], "#333333")

def info(sid):
    return stops.get(sid) or PSEUDO[sid]

def ad(sid):
    s = info(sid)
    return s["name"] + (" ♿" if s.get("wc") == "1" else "")

def to_legs(path, origin):
    legs = []
    first = path[0][0]
    if origin["access"].get(first, 0) > 0:               # adresten ilk durağa yürüme
        legs.append({"type": "walk", "from": "__O__", "to": first, "min": origin["access"][first],
                     "stops": ["__O__", first]})
    for u, v, minutes, kind, lid in path:
        if kind == "board":
            legs.append({"type": "ride", "line": lid, "from": u, "to": u, "wait": minutes - BOARD_PENALTY,
                         "ride": 0.0, "n": 0, "stops": [u]})
        elif kind == "ride":
            sid = line_stops[lid][v[1]][1]
            legs[-1]["ride"] += minutes; legs[-1]["n"] += 1; legs[-1]["to"] = sid; legs[-1]["stops"].append(sid)
        elif kind in ("walk", "walk_end") and minutes > 0:
            to = "__D__" if kind == "walk_end" else v
            legs.append({"type": "walk", "from": u, "to": to, "min": minutes, "stops": [u, to]})
    return legs

def tarif_satirlari(legs):
    out, total, walk = [], 0.0, 0.0
    for leg in legs:
        a, b = ad(leg["from"]), ad(leg["to"])
        if leg["type"] == "walk":
            total += leg["min"]; walk += leg["min"]
            out.append(f"🚶 Yürü {max(leg['min'], 1):.0f} dk (~{leg['min'] * WALK_M_PER_MIN / WALK_DETOUR:.0f} m kuş uçuşu): {a} → {b}")
        else:
            L = lines[leg["line"]]
            total += leg["wait"] + leg["ride"]
            out.append(f"{MODE_ICON.get(L['mode'], '🚌')} {L['mode']} {L['short']}: {a} → {b}  "
                       f"({leg['n']} durak, ~{leg['wait']:.0f} dk bekleme + {leg['ride']:.0f} dk yolculuk)")
    rides = sum(l["type"] == "ride" for l in legs)
    dk = lambda x: "<1" if 0 < x < 0.5 else f"{x:.0f}"
    ozet = f"⏱ Toplam ≈ {dk(total)} dk · {rides} araç · {max(rides - 1, 0)} aktarma · 🚶 {dk(walk)} dk yürüme"
    return out, ozet

def harita(legs, tuvaletler=(), merkez=None):
    pts = [(info(s)["lat"], info(s)["lon"]) for leg in legs for s in leg["stops"]] or [merkez]
    m = folium.Map(location=pts[0], zoom_start=13, tiles=None, height=520)
    m = folium.Map(location=pts[0], zoom_start=12, tiles=None, height=450)
    # Not: OpenStreetMap'in kendi sunucusu Colab'dan gelen istekleri engelliyor (403), bu yüzden CARTO / Esri altlığı
    folium.TileLayer("https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png",
                     attr="© OpenStreetMap katkıcıları © CARTO", name="Harita").add_to(m)
    folium.TileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}",
                     attr="Tiles © Esri", name="Esri").add_to(m)
    folium.LayerControl().add_to(m)
    for leg in legs:
        coords = [(info(s)["lat"], info(s)["lon"]) for s in leg["stops"]]
        if leg["type"] == "walk":
            folium.PolyLine(coords, color="#555555", weight=4, dash_array="6", tooltip="Yürüme").add_to(m)
            continue
        L = lines[leg["line"]]
        folium.PolyLine(coords, color=hat_rengi(leg["line"]), weight=7, opacity=0.9,
                        tooltip=f"{L['mode']} {L['short']}").add_to(m)
        for s in leg["stops"]:
            folium.CircleMarker((info(s)["lat"], info(s)["lon"]), radius=3, color="#333",
                                fill=True, tooltip=ad(s)).add_to(m)
    for d, t in tuvaletler:
        folium.Marker((t["lat"], t["lon"]), tooltip=f"🚻 {t['ad']} ({t['durum']}, bakım odası: {t['bakim_odasi']})",
                      icon=folium.DivIcon(html='<div style="font-size:22px;line-height:22px">🚻</div>')).add_to(m)
    if legs:
        folium.Marker(pts[0], tooltip="Başlangıç", icon=folium.Icon(color="green")).add_to(m)
        folium.Marker(pts[-1], tooltip="Varış", icon=folium.Icon(color="red")).add_to(m)
    elif merkez:
        folium.Marker(merkez, tooltip="Buradasınız", icon=folium.Icon(color="green")).add_to(m)
    allpts = pts + [(t["lat"], t["lon"]) for _, t in tuvaletler]
    if len(allpts) > 1:
        m.fit_bounds([min(allpts), max(allpts)])
    return m

def harita_html(m, h=540):
    """folium haritasını Gradio içinde gösterilebilecek bir iframe'e çevirir."""
    return (f'<iframe srcdoc="{_html.escape(m.get_root().render())}" '
            f'style="width:100%;height:{h}px;border:0;border-radius:12px"></iframe>')

def load_tuvaletler(folder):
    with open(f"{folder}/tuvaletler.csv", encoding="utf-8") as f:
        return [dict(r, lat=float(r["lat"]), lon=float(r["lon"])) for r in csv.DictReader(f)]

TUVALETLER = load_tuvaletler(DATA_DIR)

def yakin_tuvaletler(lat, lon, n=5, max_m=None, sadece_aktif=True, bakim_odasi=False, sadece_ulasim=False):
    """En yakın n tuvalet. 436 kayıt için doğrusal tarama yeterli; en küçük n tanesi heapq.nsmallest (Min-Heap) ile."""
    aday = []
    for t in TUVALETLER:
        if sadece_aktif and t["durum"] != "Aktif": continue
        if bakim_odasi and t["bakim_odasi"] != "Var": continue
        if sadece_ulasim and t["hizmet_yeri"] != "Ulaşım": continue
        d = haversine_m(lat, lon, t["lat"], t["lon"])
        if max_m is None or d <= max_m:
            aday.append((d, t))
    return heapq.nsmallest(n, aday, key=lambda x: x[0])

def yol_ustu_tuvaletler(legs, max_m=300):
    """Biniş/iniş (aktarma) noktalarına max_m metreden yakın aktif tuvaletler."""
    bulunan = {}
    for leg in legs:
        for sid in (leg["from"], leg["to"]):
            s = info(sid)
            for d, t in yakin_tuvaletler(s["lat"], s["lon"], n=3, max_m=max_m):
                if t["id"] not in bulunan or d < bulunan[t["id"]][0]:
                    bulunan[t["id"]] = (d, t, s["name"])
    return sorted(bulunan.values(), key=lambda x: x[0])

def tuvalet_yeri(t):
    """Bir tuvaleti rota hedefi olarak kullanmak için 'yer' sözlüğü."""
    return {"label": f"🚻 {t['ad']} — {t['ilce'].title()}", "lat": t["lat"], "lon": t["lon"],
            "access": near_stops(t["lat"], t["lon"])}

def rota_hesapla(A, B, kriter="süre", gun=VARSAYILAN_GUN, saat=VARSAYILAN_SAAT, tuvalet=True):
    """A, B: yer sözlükleri. Dönüş: (legs, markdown metin, yol üstü tuvaletler)"""
    PSEUDO["__O__"] = {"name": A["label"].split(" — ")[0][2:], "lat": A["lat"], "lon": A["lon"]}
    PSEUDO["__D__"] = {"name": B["label"].split(" — ")[0][2:], "lat": B["lat"], "lon": B["lon"]}
    g_adj, n_aktif = get_graph(gun, saat)
    baslik = (f"🟢 **{A['label']}**  \n🔴 **{B['label']}**  \n"
              f"{GUN_ADI[gun]} {saat:02d}:00 · kriter: {kriter} · {n_aktif:,} hat çalışıyor\n\n")
    t0 = time.perf_counter()
    cost, path, _ = dijkstra(g_adj, A["access"], B["access"], KRITER[kriter])
    # Doğrudan yürümek daha iyi mi? (ör. tuvalet 500 m ötede)
    direkt = haversine_m(A["lat"], A["lon"], B["lat"], B["lon"]) * WALK_DETOUR / WALK_M_PER_MIN
    if direkt * WALK_M_PER_MIN / WALK_DETOUR <= WALK_MAX_M:
        d_cost = {"time": (direkt,), "transfers": (0, direkt), "walk": (direkt * WALK_WEIGHT,)}[KRITER[kriter]]
        if cost is None or d_cost <= cost:
            cost, path = d_cost, None
    if cost is None:
        return [], baslik + "❌ Bu saatte yol bulunamadı.", []
    if path is None:
        legs = [{"type": "walk", "from": "__O__", "to": "__D__", "min": direkt, "stops": ["__O__", "__D__"]}]
    else:
        legs = to_legs(path, A)
    satirlar, ozet = tarif_satirlari(legs)
    metin = baslik + "\n".join(f"- {s}" for s in satirlar) + f"\n\n**{ozet}**"
    if any(info(s).get("wc") == "1" for l in legs for s in l["stops"]):
        metin += "\n\n♿ = veride tekerlekli sandalyeye uygun olarak kayıtlı istasyon (diğerleri için bilgi yok)"
    wc = yol_ustu_tuvaletler(legs) if tuvalet else []
    if tuvalet:
        if wc:
            metin += "\n\n🚻 **Yol üstündeki tuvaletler (≤ 300 m):**\n" + "\n".join(
                f"- {t['ad']} — {yer} durağına {d:.0f} m · bakım odası: {t['bakim_odasi']}" for d, t, yer in wc[:6])
        else:
            metin += "\n\n🚻 Aktarma noktalarına 300 m içinde aktif tuvalet yok."
    metin += f"\n\n<sub>Dijkstra, {(time.perf_counter() - t0) * 1000:.0f} ms</sub>"
    return legs, metin, wc

def rota(nereden, nereye, kriter="süre", gun=VARSAYILAN_GUN, saat=VARSAYILAN_SAAT, harita_goster=True, tuvalet=True):
    """Kodla kullanım: rota("Kadıköy", "Taksim", "süre", "hi", 8). Yer adı (metin) ya da yer sözlüğü alır."""
    yerler = []
    for q in (nereden, nereye):
        if isinstance(q, dict):
            yerler.append(q); continue
        bulunan = yer_ara(q)
        if not bulunan:
            print(f"❌ '{q}' bulunamadı."); return None
        yerler.append(bulunan[0])
    legs, metin, wc = rota_hesapla(*yerler, kriter, gun, saat, tuvalet)
    print(re.sub(r"<[^>]+>|\*\*", "", metin))
    if legs and harita_goster:
        display(harita(legs, [(d, t) for d, t, _ in wc]))
    return legs

import re


import gradio as gr

def ara(q):
    yerler = yer_ara(q or "")
    labels = [p["label"] for p in yerler]
    return gr.update(choices=labels, value=labels[0] if labels else None), yerler

def sec(label, yerler):
    return next((p for p in (yerler or []) if p["label"] == label), None)

def rota_ui(a_label, a_yerler, b_label, b_yerler, gun, saat, kriter, tuvalet):
    A, B = sec(a_label, a_yerler), sec(b_label, b_yerler)
    if A is None or B is None:
        return "❌ Önce nereden ve nereye için arayıp listeden bir yer seçin.", ""
    legs, metin, wc = rota_hesapla(A, B, kriter, gun, int(saat), tuvalet)
    return metin, harita_html(harita(legs, [(d, t) for d, t, _ in wc])) if legs else ""

def degistir(a_txt, a_dd, a_yer, b_txt, b_dd, b_yer):
    return (b_txt, gr.update(choices=[p["label"] for p in b_yer], value=b_dd), b_yer,
            a_txt, gr.update(choices=[p["label"] for p in a_yer], value=a_dd), a_yer)

def tuvalet_ara(label, yerler, aktif, bakim, ulasim):
    P = sec(label, yerler)
    if P is None:
        return [], "", gr.update(choices=[], value=None), []
    bulunan = yakin_tuvaletler(P["lat"], P["lon"], n=10, sadece_aktif=aktif, bakim_odasi=bakim, sadece_ulasim=ulasim)
    tablo = [[t["ad"], t["ilce"].title(), f"{d:.0f} m", f"{d * WALK_DETOUR / WALK_M_PER_MIN:.0f} dk",
              t["durum"], t["bakim_odasi"], t["hizmet_yeri"]] for d, t in bulunan]
    secenek = [f"{t['ad']} ({d:.0f} m)" for d, t in bulunan]
    m = harita([], bulunan, merkez=(P["lat"], P["lon"]))
    return tablo, harita_html(m), gr.update(choices=secenek, value=secenek[0] if secenek else None), bulunan

def tuvalete_rota(label, yerler, secim, bulunan, gun, saat):
    P = sec(label, yerler)
    if P is None or not secim or not bulunan:
        return "❌ Önce tuvalet arayın.", ""
    d, t = bulunan[[f"{x['ad']} ({dd:.0f} m)" for dd, x in bulunan].index(secim)]
    legs, metin, _ = rota_hesapla(P, tuvalet_yeri(t), "yürüme", gun, int(saat), tuvalet=False)
    return metin, harita_html(harita(legs, [(d, t)])) if legs else ""

GUNLER = [("Hafta içi", "hi"), ("Cumartesi", "cmt"), ("Pazar", "paz")]
SAATLER = [(f"{h:02d}:00", h) for h in range(24)]
ilk_a, ilk_b = yer_ara("Kadıköy"), yer_ara("Taksim")

with gr.Blocks(title="İstanbul Rota Planlayıcı") as demo:
    gr.Markdown("# 🚇 İstanbul Toplu Taşıma Rota Planlayıcı\nDurak adı, adres veya mekân yazıp **Enter**'a basın, listeden doğru yeri seçin.")
    with gr.Tab("🧭 Rota"):
        a_yer, b_yer = gr.State(ilk_a), gr.State(ilk_b)
        with gr.Row():
            with gr.Column(scale=2):
                a_txt = gr.Textbox(label="Nereden", value="Kadıköy", placeholder="durak, adres veya mekân")
                a_dd = gr.Dropdown(label="Bulunan yerler", choices=[p["label"] for p in ilk_a], value=ilk_a[0]["label"])
                b_txt = gr.Textbox(label="Nereye", value="Taksim", placeholder="durak, adres veya mekân")
                b_dd = gr.Dropdown(label="Bulunan yerler", choices=[p["label"] for p in ilk_b], value=ilk_b[0]["label"])
                with gr.Row():
                    gun = gr.Dropdown(GUNLER, value="hi", label="Gün")
                    saat = gr.Dropdown(SAATLER, value=8, label="Saat")
                    ters = gr.Button("⇄ Yer değiştir")
                kriter = gr.Radio([("⏱ En hızlı", "süre"), ("🔁 En az aktarma", "aktarma"), ("🚶 En az yürüme", "yürüme")],
                                  value="süre", label="Kriter")
                tuv = gr.Checkbox(value=True, label="🚻 Yol üstündeki tuvaletleri göster")
                bul = gr.Button("Rota bul", variant="primary")
                tarif = gr.Markdown()
            with gr.Column(scale=3):
                harita_out = gr.HTML()
        a_txt.submit(ara, a_txt, [a_dd, a_yer])
        b_txt.submit(ara, b_txt, [b_dd, b_yer])
        ters.click(degistir, [a_txt, a_dd, a_yer, b_txt, b_dd, b_yer], [a_txt, a_dd, a_yer, b_txt, b_dd, b_yer])
        girdiler = [a_dd, a_yer, b_dd, b_yer, gun, saat, kriter, tuv]
        bul.click(rota_ui, girdiler, [tarif, harita_out])
        demo.load(rota_ui, girdiler, [tarif, harita_out])
    with gr.Tab("🚻 Tuvalet bul"):
        t_yer, t_bulunan = gr.State(ilk_a), gr.State([])
        with gr.Row():
            with gr.Column(scale=2):
                t_txt = gr.Textbox(label="Neredesiniz?", value="Kadıköy", placeholder="durak, adres veya mekân")
                t_dd = gr.Dropdown(label="Bulunan yerler", choices=[p["label"] for p in ilk_a], value=ilk_a[0]["label"])
                with gr.Row():
                    aktif = gr.Checkbox(value=True, label="Sadece aktif")
                    bakim = gr.Checkbox(value=False, label="Bakım odası olsun")
                    ulasim = gr.Checkbox(value=False, label="Sadece istasyon / ulaşım noktası")
                t_bul = gr.Button("En yakın tuvaletleri bul", variant="primary")
                tablo = gr.Dataframe(headers=["Tuvalet", "İlçe", "Mesafe", "Yürüme", "Durum", "Bakım odası", "Yer"],
                                     interactive=False, wrap=True)
                with gr.Row():
                    t_hedef = gr.Dropdown(label="Rota çıkarılacak tuvalet", choices=[])
                    t_gun = gr.Dropdown(GUNLER, value="hi", label="Gün")
                    t_saat = gr.Dropdown(SAATLER, value=8, label="Saat")
                t_rota = gr.Button("🚶 Seçili tuvalete en az yürümeli rota")
                t_tarif = gr.Markdown()
            with gr.Column(scale=3):
                t_harita = gr.HTML()
        t_txt.submit(ara, t_txt, [t_dd, t_yer])
        t_bul.click(tuvalet_ara, [t_dd, t_yer, aktif, bakim, ulasim], [tablo, t_harita, t_hedef, t_bulunan])
        t_rota.click(tuvalete_rota, [t_dd, t_yer, t_hedef, t_bulunan, t_gun, t_saat], [t_tarif, t_harita])

demo.launch(inbrowser=True)
