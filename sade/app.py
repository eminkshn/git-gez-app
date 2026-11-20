"""GitGez — İstanbul rota ve gezi planlayıcı, yerel arayüz.
Bu dosya gitgez_sade.ipynb defterinden otomatik üretilir (tools/export_app.py); düzenlemeleri deftere yapın.
Kurulum : pip install -r requirements.txt  (gradio, numpy, scipy, requests ...)
Veri    : gitgez_veri.zip (yokus-gezi/ klasöründe; açmayın)
Çalıştır: python app.py  ->  http://127.0.0.1:7860
"""
import os
os.chdir(os.path.dirname(os.path.abspath(__file__)))


# ----------------------------------------------------------------------

import os, glob, zipfile

DATA_DIR = "gitgez_veri"                                  # zip buraya açılır
GEREKLI = {"stops.csv", "lines.csv", "line_stops.csv", "line_hours.csv", "tuvaletler.csv",
           "sokak.npz", "yurume.npz", "gezi_yerleri.csv"}
ARANACAK = [".", "..", "../yokus-gezi", "/content", "/content/drive/MyDrive"]

def veri_zipi_bul():
    """Adına değil İÇERİĞİNE bakar: gerekli dosyaların hepsi olan en yeni zip."""
    adaylar = {os.path.abspath(z) for d in ARANACAK if os.path.isdir(d) for z in glob.glob(f"{d}/*.zip")}
    for z in sorted(adaylar, key=os.path.getmtime, reverse=True):
        try:
            with zipfile.ZipFile(z) as f:
                if GEREKLI <= {os.path.basename(n) for n in f.namelist()}:
                    return z
        except zipfile.BadZipFile:
            pass                                          # yarım yüklenmiş zip: atla
    return None

veri_zip = veri_zipi_bul()
if veri_zip is None:                                      # Colab'da yükleme penceresi aç
    try:
        from google.colab import files
        print("gitgez_veri.zip dosyasını seçin (~55 MB, 1-2 dk sürebilir)")
        files.upload()
        veri_zip = veri_zipi_bul()
    except ImportError:
        pass
if veri_zip is None:
    raise FileNotFoundError("gitgez_veri.zip bulunamadı: bu defterle aynı klasöre koyun.")

os.makedirs(DATA_DIR, exist_ok=True)
with zipfile.ZipFile(veri_zip) as f:                      # klasör yapısını düzleştirerek aç
    for n in f.namelist():
        if not n.endswith("/"):
            with open(os.path.join(DATA_DIR, os.path.basename(n)), "wb") as out:
                out.write(f.read(n))
print("Veri:", veri_zip)

# ---- Ayarlar (hepsi dakika ya da metre) ----
WALK_MAX_M     = 2000   # başlangıç/varışta en fazla bu kadar uzaktaki duraklara bakılır (kuş uçuşu)
WALK_M_PER_MIN = 75     # düz yolda yürüme hızı ≈ 4,5 km/sa (yokuşta Tobler fonksiyonuyla yavaşlar)
WALK_LIMIT_DK  = 27     # başlangıç/varışta en fazla bu kadar dakika yürünür
BOARD_PENALTY  = 2      # her araca binişte +2 dk "aktarma zahmeti": aynı süredeki rotalardan az aktarmalı olan kazansın
WALK_WEIGHT    = 4      # "Az yürüme" sıralamasında 1 dk yürüme = 4 dk araçta oturmak kadar "maliyetli"
MAX_WAIT       = 30     # çok seyrek hatlarda bekleme en fazla 30 dk sayılır
PLACE_RADIUS_M = 800    # aynı adlı duraklardan birbirine 800 m'den yakın olanlar "aynı yer"
ALT_PAY        = 30     # alternatif rota en iyisinden en fazla 30 dk uzun olabilir
VARSAYILAN_GUN, VARSAYILAN_SAAT = "hi", 8   # hi = hafta içi, cmt = cumartesi, paz = pazar

import csv, math, re
from collections import defaultdict

def load_network(folder):
    """Duraklar, hatlar, hat durak dizileri ve saatlik sefer sayıları (İBB GTFS'ten hazırlandı)."""
    stops, lines, line_stops, hours = {}, {}, defaultdict(list), {}
    with open(f"{folder}/stops.csv", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            stops[r["stop_id"]] = {"name": r["name"], "lat": float(r["lat"]), "lon": float(r["lon"])}
    with open(f"{folder}/lines.csv", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            lines[r["line_id"]] = {"short": r["short_name"], "mode": r["mode"]}
    with open(f"{folder}/line_stops.csv", encoding="utf-8") as f:
        for r in csv.DictReader(f):     # min_from_prev: önceki duraktan bu durağa yolculuk dakikası
            line_stops[r["line_id"]].append((int(r["seq"]), r["stop_id"], float(r["min_from_prev"])))
    with open(f"{folder}/line_hours.csv", encoding="utf-8") as f:
        for r in csv.DictReader(f):     # her hat, gün tipi ve saat için kalkış sayısı
            hours.setdefault((r["line_id"], r["day"]), [0.0] * 24)[int(r["hour"])] = float(r["departures"])
    for lid in line_stops:
        line_stops[lid].sort()
    return stops, lines, dict(line_stops), hours

stops, lines, line_stops, hours = load_network(DATA_DIR)

# Aynı durakları aynı sırayla izleyen hatlar (ör. 34A / 34AS) tek "desen" sayılır:
# grafa bir kez girer, sefer sayıları toplanır (= daha sık araç, daha kısa bekleme).
def hat_desenleri():
    by_seq = defaultdict(list)
    for lid, seq in line_stops.items():
        by_seq[(lines[lid]["mode"], tuple(s for _, s, _ in seq))].append(lid)
    temsil, uyeler = {}, {}
    for lids in by_seq.values():
        lids.sort(key=lambda l: (-sum(sum(hours.get((l, g), [0])) for g in ("hi", "cmt", "paz")), lines[l]["short"]))
        uyeler[lids[0]] = lids                           # ilk hat desenin temsilcisi
        for l in lids:
            temsil[l] = lids[0]
    return temsil, uyeler

TEMSIL, UYELER = hat_desenleri()
print(f"{len(stops):,} durak, {len(lines):,} hat -> {len(UYELER):,} farklı desen")

import unicodedata, difflib

TR_MAP = str.maketrans("çğıöşüÇĞİÖŞÜâîû", "cgiosuCGIOSUaiu")

def normalize(text):
    """'KADIKÖY İskele' -> 'kadikoy iskele' (Türkçe harf, büyük/küçük harf ve noktalama farkı kalkar)"""
    text = unicodedata.normalize("NFKD", text.translate(TR_MAP).lower()).encode("ascii", "ignore").decode()
    return " ".join("".join(c if c.isalnum() else " " for c in text).split())

def haversine_m(lat1, lon1, lat2, lon2):
    """İki koordinat arası kuş uçuşu mesafe (metre)"""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2
    return 2 * 6371000 * math.asin(math.sqrt(a))

class StopIndex:
    """Hash tablosu (dict): normalize ad -> durak listesi. Tam ad araması O(1)."""
    def __init__(self, stops):
        self.by_name = defaultdict(list)
        self.by_word = defaultdict(set)                  # kelime -> adlar (çok kelimeli arama için)
        for sid, s in stops.items():
            n = normalize(s["name"])
            self.by_name[n].append(sid)
            for w in n.split():
                self.by_word[w].add(n)

    def search(self, query):
        """Sıralı ad listesi: tam eşleşme > bununla başlayan > kelimeleri eşleşen > içinde geçen."""
        q = normalize(query)
        if not q:
            return []
        words = q.split()
        aday = None
        for w in words:                                  # her kelime bir ad kelimesinin başı olmalı
            hit = {n for k, ns in self.by_word.items() if k.startswith(w) for n in ns}
            aday = hit if aday is None else aday & hit
        aday = set(aday or ())
        if len(q) >= 3:
            aday |= {n for n in self.by_name if q in n}
        sira = lambda n: (0 if n == q else 1 if n.startswith(q) else 2, -len(self.by_name[n]), len(n))
        return sorted(aday, key=sira)

    def suggest(self, query, n=3):
        """Yazım hatası toleransı: 'üsküdr' -> 'uskudar' (difflib benzerlik)"""
        return difflib.get_close_matches(normalize(query), self.by_name.keys(), n=n, cutoff=0.6)

index = StopIndex(stops)
print(index.search("kadıköy")[:3], index.suggest("üsküdr"))

import numpy as np
from scipy import sparse
from scipy.sparse.csgraph import dijkstra as sp_dijkstra, connected_components
from scipy.spatial import cKDTree

KX, KY = 111_320 * math.cos(math.radians(41.0)), 110_950        # derece -> metre (İstanbul için)

_s = np.load(f"{DATA_DIR}/sokak.npz")
N_LAT, N_LON = _s["node_lat"].astype(float), _s["node_lon"].astype(float)   # kavşaklar
N_X, N_Y = N_LON * KX, N_LAT * KY
E_PTR, E_TO, E_GID = _s["indptr"].astype(np.int64), _s["to"].astype(np.int64), _s["gid"].astype(np.int64)
E_FROM = np.repeat(np.arange(len(N_LAT)), np.diff(E_PTR))       # sokak parçası: E_FROM -> E_TO
E_T = _s["t_norm"]                                               # yürüme süresi (dk, eğime göre)
E_CLIMB = _s["climb"] / 10                                       # bu yönde tırmanış (m)
G_PTR, G_LAT, G_LON, G_LEN = _s["g_ptr"], _s["g_lat"], _s["g_lon"], _s["g_len"]   # çizim için geometri
STOP_IDS = _s["stop_ids"].tolist()
STOP_NODE = dict(zip(STOP_IDS, _s["stop_node"].tolist()))        # durak -> en yakın kavşak
STOP_SNAP = dict(zip(STOP_IDS, _s["stop_snap"].tolist()))        # durak ile kavşak arası (m)
# Ağdan kopuk küçük parçalara bağlanan nokta hiçbir yere yürüyemez: sadece büyük (ana) bileşen kullanılır.
_, _lab = connected_components(sparse.csr_matrix((np.ones(len(E_TO)), (E_FROM, E_TO)),
                                                 shape=(len(N_LAT),) * 2), directed=False)
NODE_ANA = np.nonzero(np.bincount(_lab)[_lab] >= 1000)[0]
NODE_TREE = cKDTree(np.c_[N_X[NODE_ANA], N_Y[NODE_ANA]])        # en yakın kavşak araması
print(f"Sokak ağı: {len(N_LAT):,} kavşak, {len(E_TO):,} yönlü parça")

class Yurume:
    """Durak -> durak yürüme bağlantıları. Dijkstra 'walks.get(durak)' ile ister; liste ilk istendiğinde kurulur.
    Hava kötüyse (yağmur, kar) süreler KOSUL['K'] ile çarpılır."""
    def __init__(self, z):
        self.ptr, self.to, self.cost = z["normal_ptr"], z["normal_to"], z["normal_cost"].astype(np.float32)
        self.idx = {sid: i for i, sid in enumerate(STOP_IDS)}
        self.cache = {}
    def get(self, sid, default=()):
        k = KOSUL["K"]
        if (sid, k) not in self.cache:
            i = self.idx.get(sid)
            if i is None:
                return default
            a, b = int(self.ptr[i]), int(self.ptr[i + 1])
            self.cache[(sid, k)] = [(STOP_IDS[t], c * k, "walk", None)
                                    for t, c in zip(self.to[a:b].tolist(), self.cost[a:b].tolist())]
        return self.cache[(sid, k)]

WALKS = Yurume(np.load(f"{DATA_DIR}/yurume.npz"))
print(f"{len(WALKS.to):,} durak→durak yürüme bağlantısı")

def _altgraf(x0, x1, y0, y1):
    """Kutudaki sokakların alt grafı (scipy seyrek matris). Bütün şehir yerine sadece çevre aranır."""
    sel = np.nonzero((N_X >= x0) & (N_X <= x1) & (N_Y >= y0) & (N_Y <= y1))[0]
    loc = np.full(len(N_X), -1); loc[sel] = np.arange(len(sel))
    m = (loc[E_FROM] >= 0) & (loc[E_TO] >= 0)
    ei = np.nonzero(m)[0]
    ru, rv, rw = loc[E_FROM[ei]], loc[E_TO[ei]], E_T[ei] + 1e-6
    o = np.lexsort((rw, rv, ru)); ru, rv, rw, ei = ru[o], rv[o], rw[o], ei[o]
    ilk = np.r_[True, (ru[1:] != ru[:-1]) | (rv[1:] != rv[:-1])]     # iki kavşak arası birden çok yol: en kısası
    n = len(sel)
    A = sparse.csr_matrix((rw[ilk], (ru[ilk], rv[ilk])), shape=(n, n))
    EID = sparse.csr_matrix((ei[ilk] + 1, (ru[ilk], rv[ilk])), shape=(n, n))   # yolu geri kurmak için kenar no
    return A, EID, loc

def yakin_dugumler(lat, lon, k=4, r=250):
    """Noktaya en yakın kavşaklar [(düğüm, mesafe m)]"""
    d, i = NODE_TREE.query([lon * KX, lat * KY], k=k, distance_upper_bound=r)
    out = [(int(NODE_ANA[n]), float(dd)) for dd, n in zip(np.atleast_1d(d), np.atleast_1d(i)) if np.isfinite(dd)]
    if not out:
        dd, n = NODE_TREE.query([lon * KX, lat * KY])
        out = [(int(NODE_ANA[n]), float(dd))]
    return out

def _kaynakli_dijkstra(A, starts, limit, ters=False):
    """scipy Dijkstra'ya birden çok başlangıç noktası (her birinin kendi başlangıç süresiyle):
    sanal bir 'süper kaynak' düğümü eklenir, ondan her başlangıca bir kenar."""
    n = A.shape[0]
    if ters:
        A = A.T.tocsr()                                  # varış için: kenarları ters çevir
    row = sparse.csr_matrix(([c + 1e-6 for c in starts.values()], ([0] * len(starts), list(starts))), shape=(1, n))
    B = sparse.hstack([sparse.vstack([A, row]), sparse.csr_matrix((n + 1, 1))], format="csr")
    dist, pred = sp_dijkstra(B, directed=True, indices=n, limit=limit, return_predecessors=True)
    return dist[:n], pred[:n], n

def nokta_erisim(lat, lon, yon="cikis"):
    """Bir noktadan (çıkış) ya da noktaya (varış) sokaklardan yürüyerek ulaşılan duraklar: {durak: dk}"""
    r = WALK_MAX_M + 400
    x, y = lon * KX, lat * KY
    A, _, loc = _altgraf(x - r, x + r, y - r, y + r)
    starts = {}
    for n, d in yakin_dugumler(lat, lon):
        if loc[n] >= 0:
            starts[loc[n]] = min(starts.get(loc[n], 1e9), d / WALK_M_PER_MIN)
    if not starts:
        return {}
    dist, _, _ = _kaynakli_dijkstra(A, starts, WALK_LIMIT_DK, ters=(yon == "varis"))
    out = {}
    for sid in grid.near(lat, lon):
        n = STOP_NODE.get(sid)
        if n is not None and loc[n] >= 0 and np.isfinite(dist[loc[n]]):
            c = float(dist[loc[n]]) + STOP_SNAP[sid] / WALK_M_PER_MIN
            if c <= WALK_LIMIT_DK:
                out[sid] = c * KOSUL["K"]
    return out

_yol_cache = {}
def yol_bul(lat1, lon1, lat2, lon2):
    """İki nokta arası sokaklardan yürüyüş: {coords, tmin (dk), len (m), climb (m)}.
    Sokak bulunamazsa kuş uçuşu × 1,3 tahmin edilir."""
    key = (round(lat1, 6), round(lon1, 6), round(lat2, 6), round(lon2, 6))
    if key not in _yol_cache:
        crow = haversine_m(lat1, lon1, lat2, lon2)
        m = max(500, 0.6 * crow)                         # arama kutusu: iki noktayı + biraz pay
        x0, x1 = sorted((lon1 * KX, lon2 * KX)); y0, y1 = sorted((lat1 * KY, lat2 * KY))
        A, EID, loc = _altgraf(x0 - m, x1 + m, y0 - m, y1 + m)
        starts = {loc[n]: d / WALK_M_PER_MIN for n, d in yakin_dugumler(lat1, lon1) if loc[n] >= 0}
        sonuc = None
        if starts:
            dist, pred, N = _kaynakli_dijkstra(A, starts, np.inf)
            best = min(((float(dist[loc[n]]) + d / WALK_M_PER_MIN, n) for n, d in yakin_dugumler(lat2, lon2)
                        if loc[n] >= 0 and np.isfinite(dist[loc[n]])), default=None)
            if best is not None:
                eids, cur = [], loc[best[1]]             # yolu sondan başa geri kur (predecessor dizisi)
                while 0 <= cur != N and 0 <= pred[cur] != N:
                    eids.append(int(EID[pred[cur], cur]) - 1)
                    cur = pred[cur]
                sonuc = _yol_ozet(eids[::-1], lat1, lon1, lat2, lon2)
        if sonuc is None:
            sonuc = {"coords": [(lat1, lon1), (lat2, lon2)], "tmin": crow * 1.3 / WALK_M_PER_MIN,
                     "len": crow * 1.3, "climb": 0.0, "yedek": True}
        _yol_cache[key] = sonuc
    s = _yol_cache[key]
    return dict(s, tmin=s["tmin"] * KOSUL["K"])         # hava çarpanı (önbellek değişmez)

def _yol_ozet(eids, lat1, lon1, lat2, lon2):
    coords, tmin, length, climb = [(lat1, lon1)], 0.0, 0.0, 0.0
    for e in eids:
        g = int(E_GID[e]); ileri = g >= 0; g = g if ileri else -g - 1
        a, b = int(G_PTR[g]), int(G_PTR[g + 1])
        pts = list(zip(G_LAT[a:b].astype(float).tolist(), G_LON[a:b].astype(float).tolist()))
        coords.extend(pts if ileri else pts[::-1])
        tmin += float(E_T[e]); length += float(G_LEN[g]); climb += float(E_CLIMB[e])
    coords.append((lat2, lon2))
    uc = haversine_m(*coords[0], *coords[1]) + haversine_m(*coords[-2], *coords[-1])   # noktadan sokağa
    return {"coords": coords, "tmin": tmin + uc / WALK_M_PER_MIN, "len": length + uc, "climb": climb, "yedek": False}

class Grid:
    """Şehri 2 km'lik karelere böler: kare -> içindeki duraklar (hash tablosu).
    Bir noktaya yakın duraklar = kendi karesi + 8 komşu kare. 14 bin durağı tek tek gezmek gerekmez."""
    def __init__(self, stops, cell_m=WALK_MAX_M):
        self.dlat = cell_m / 111_320
        self.dlon = cell_m / (111_320 * math.cos(math.radians(41.0)))   # boylamda 1° daha kısa
        self.cells = defaultdict(list)
        for sid, s in stops.items():
            self.cells[self.key(s["lat"], s["lon"])].append(sid)

    def key(self, lat, lon):
        return int(lat / self.dlat), int(lon / self.dlon)

    def near(self, lat, lon):
        i, j = self.key(lat, lon)
        for di in (-1, 0, 1):
            for dj in (-1, 0, 1):
                yield from self.cells.get((i + di, j + dj), ())

grid = Grid(stops)
print(f"{len(grid.cells):,} dolu kare")

import requests, time
from datetime import date, datetime, timedelta, timezone

IST = timezone(timedelta(hours=3))
YURUME_K = {"acik": 1.0, "yagmur": 1.15, "kar": 1.5}     # yürüme süresi çarpanı (başlangıç varsayımı)
KOSUL = {"sinif": "acik", "K": 1.0, "vapur_kapali": False, "trafik": False, "etiket": "", "uyari": ""}

def gun_tipi(wd):
    """haftanın günü (0 = pazartesi) -> tarife tipi"""
    return "paz" if wd == 6 else "cmt" if wd == 5 else "hi"

_hava_cache = {}
def hava_tahmini(tarih, saat):
    """Open-Meteo'dan o saatin değerleri ya da None (internet yok / tarih çok uzak)."""
    if (tarih, saat) not in _hava_cache:
        try:
            r = requests.get("https://api.open-meteo.com/v1/forecast", timeout=4, params={
                "latitude": 41.015, "longitude": 28.98, "timezone": "Europe/Istanbul",
                "hourly": "temperature_2m,precipitation,snowfall,wind_gusts_10m",
                "start_date": tarih.isoformat(), "end_date": tarih.isoformat()})
            r.raise_for_status()
            h = r.json()["hourly"]
            _hava_cache[(tarih, saat)] = {k: h[k][saat] for k in h if k != "time"}
        except Exception:
            _hava_cache[(tarih, saat)] = None
    return _hava_cache[(tarih, saat)]

def kosul_ayarla(gun, saat, hava="oto", tarih=None, trafik=True):
    """Aramadan önce hava ve trafik durumunu KOSUL'a yazar. hava: 'oto' (tahmin) ya da elle seçilen sınıf."""
    global KOSUL
    firtina, etiket, bilgi_yok = hava == "firtina", "", False
    sinif = "acik" if hava in ("oto", "firtina") else hava
    if hava == "oto":
        bugun = datetime.now(IST).date()
        tarih = tarih or next(bugun + timedelta(days=k) for k in range(7)       # o gün tipine uyan en yakın tarih
                              if gun_tipi((bugun + timedelta(days=k)).weekday()) == gun)
        v = hava_tahmini(tarih, saat)
        if v:
            yag, kar, ruzgar = v.get("precipitation") or 0, v.get("snowfall") or 0, v.get("wind_gusts_10m") or 0
            sinif = "kar" if kar > 0 else "yagmur" if yag >= 0.5 else "acik"
            firtina = ruzgar >= 70                       # rüzgâr hamlesi ≥ 70 km/sa: vapur seferleri iptal
            etiket = f"{v.get('temperature_2m', 0):.0f}°C"
        else:
            bilgi_yok = True                             # internet yok: hava etkisi yok sayılır
    ad = {"acik": "☀️ Açık", "yagmur": "🌧 Yağmurlu", "kar": "❄️ Karlı"}[sinif]
    if firtina:
        ad = "🌬 Fırtınalı"
    if bilgi_yok:
        ad = "🌤 Hava bilgisi yok"
    KOSUL = {"sinif": sinif, "K": YURUME_K[sinif], "vapur_kapali": firtina, "trafik": bool(trafik and TRAFIK),
             "etiket": f"{ad} {etiket}".strip(),
             "uyari": "Fırtına: vapurlar kullanılmıyor" if firtina else
                      f"{ad.split()[1]} hava: yürüme süreleri %{(YURUME_K[sinif] - 1) * 100:.0f} uzun" if sinif != "acik" else ""}
    return KOSUL

# ---- Trafik: geohash bölgesi (≈ 1,2 km × 0,6 km) + gün tipi + saat -> otobüs süresi çarpanı
_B32 = "0123456789bcdefghjkmnpqrstuvwxyz"
def geohash(lat, lon, n=6):
    """Koordinatı bölge koduna çevirir (İBB trafik verisi bu kodu kullanır)."""
    la, lo, out, bits, ch, cift = [-90.0, 90.0], [-180.0, 180.0], "", 0, 0, True
    while len(out) < n:
        aralik, v = (lo, lon) if cift else (la, lat)     # sırayla boylamı ve enlemi ikiye böl
        orta = (aralik[0] + aralik[1]) / 2
        ch = ch * 2 + (v >= orta)
        aralik[0 if v >= orta else 1] = orta
        cift, bits = not cift, bits + 1
        if bits == 5:
            out += _B32[ch]; bits, ch = 0, 0
    return out

TRAFIK, TRAFIK_SEHIR = {}, defaultdict(list)
for yol in (f"{DATA_DIR}/trafik.csv", "trafik.csv"):
    if os.path.exists(yol):
        with open(yol, encoding="utf-8") as f:
            for r in csv.DictReader(f):
                TRAFIK[(r["geohash"], r["gun"], int(r["saat"]))] = float(r["carpan"])
                TRAFIK_SEHIR[(r["gun"], int(r["saat"]))].append(float(r["carpan"]))
        break
TRAFIK_SEHIR = {k: float(np.median(v)) for k, v in TRAFIK_SEHIR.items()}   # bölge verisi yoksa şehir ortalaması

def trafik_carpani(lid, i, gun, saat):
    """Otobüs hattının i -> i+1 durak arası için çarpan (metro, metrobüs, vapur: 1). 0,7–2,0 arası."""
    if lines[lid]["mode"] != "Otobüs" or not TRAFIK:
        return 1.0
    a, b = stops[line_stops[lid][i][1]], stops[line_stops[lid][i + 1][1]]
    gh = geohash((a["lat"] + b["lat"]) / 2, (a["lon"] + b["lon"]) / 2)
    k = TRAFIK.get((gh, gun, saat), TRAFIK_SEHIR.get((gun, saat), 1.0))
    return min(max(k, 0.7), 2.0)

kosul_ayarla("hi", 8, "acik", trafik=False)              # başlangıç: nötr
print(f"Trafik tablosu: {len(TRAFIK):,} kayıt" if TRAFIK else "trafik.csv yok: otobüslerde sabit hız")

def wait_at(lid, gun, saat):
    """Desenin o saatteki ortalama beklemesi (dk) ya da None (o saatte çalışmıyor)."""
    n = onceki = 0.0
    for m in UYELER.get(TEMSIL.get(lid, lid), [lid]):    # aynı desendeki tüm hatların seferleri toplanır
        h = hours.get((m, gun))
        if h:
            n += h[saat]; onceki += h[saat - 1]
    if n == 0 and onceki == 0:
        return None
    n = n or 1                                           # bu saatte kalkış yok ama önceki saatte çıkan araç yolda
    return min(max(60 / n / 2, 1.0), MAX_WAIT)           # saatte n sefer -> ortalama bekleme 60/n/2

def build_graph(gun, saat):
    adj = defaultdict(list)                              # komşuluk listesi: düğüm -> [(komşu, dk, tür, hat)]
    aktif = 0
    for lid in UYELER:                                   # her desen bir kez
        if KOSUL["vapur_kapali"] and lines[lid]["mode"] == "Vapur":
            continue                                     # fırtına: vapur yok
        wait = wait_at(lid, gun, saat)
        if wait is None:
            continue                                     # o saatte çalışmıyor
        aktif += len(UYELER[lid])
        seq = line_stops[lid]
        for i, (_, sid, _) in enumerate(seq):
            node = (lid, i)
            adj[sid].append((node, wait + BOARD_PENALTY, "board", lid))
            adj[node].append((sid, 0.0, "alight", lid))
            if i + 1 < len(seq):
                dk = seq[i + 1][2] * (trafik_carpani(lid, i, gun, saat) if KOSUL["trafik"] else 1.0)
                adj[node].append(((lid, i + 1), dk, "ride", lid))
    return dict(adj), aktif

_graph_cache = {}
def get_graph(gun, saat):
    """Her (gün, saat, fırtına, trafik) için graf bir kez kurulur, sonra önbellekten gelir."""
    k = (gun, saat, KOSUL["vapur_kapali"], KOSUL["trafik"])
    if k not in _graph_cache:
        _graph_cache[k] = build_graph(gun, saat)
    return _graph_cache[k]

# Alternatif rota için: bir yolculuk parçasıyla AYNI durakları izleyen diğer desenler (34 / 34AS / 34BZ…)
desen_at = defaultdict(set)
for lid in UYELER:
    for _, sid, _ in line_stops[lid]:
        desen_at[sid].add(lid)

def esdeger_desenler(lid, i, j):
    seg = [line_stops[lid][k][1] for k in range(i, j + 1)]
    out = []
    for c in desen_at[seg[0]] & desen_at[seg[-1]]:
        cs = [s for _, s, _ in line_stops[c]]
        for p in (k for k, s in enumerate(cs) if s == seg[0]):
            if cs[p:p + len(seg)] == seg:
                out.append(c); break
    return out

for s in (3, 8, 23):
    print(f"hafta içi {s:02d}:00 -> {get_graph('hi', s)[1]:,} hat çalışıyor")

import heapq, itertools

VARIS = ("__VARIŞ__", "end")                              # sanal varış durumu

def dijkstra(adj, sources, targets, objective="time", walks=None, banned=frozenset()):
    """sources / targets: {durak: o durağa yürüme dk}. banned: kullanılmayacak hatlar (alternatif için).
    Dönüş: (maliyet, yol, açılan durum sayısı) — yol bulunamazsa (None, [], n)."""
    walks = WALKS if walks is None else walks

    def cost_of(minutes, kind):                          # bir kenarın maliyeti, seçilen kritere göre
        if objective == "transfers":
            return (1 if kind == "board" else 0, minutes)
        if objective == "walk" and kind in ("walk", "walk_end"):
            return (minutes * WALK_WEIGHT,)
        return (minutes,)

    def add(a, b):
        return tuple(x + y for x, y in zip(a, b))

    zero = (0, 0.0) if objective == "transfers" else (0.0,)
    best, prev, heap, sayac = {}, {}, [], itertools.count()
    for s, w in sources.items():                         # tüm başlangıç durakları heap'e (yürüme süresiyle)
        state = (s, "walk" if w > 0 else "start")
        best[state] = add(zero, cost_of(w, "walk"))
        heapq.heappush(heap, (best[state], next(sayac), state))
    done = set()
    while heap:
        cost, _, state = heapq.heappop(heap)             # en ucuz durum
        if state in done:
            continue                                     # tembel silme: eski kayıt
        done.add(state)
        if state == VARIS:
            return cost, rebuild_path(prev, state), len(done)
        node, last = state
        if node in targets and not (last == "walk" and targets[node] > 0):    # buradan hedefe yürüyebilir miyim?
            new = add(cost, cost_of(targets[node], "walk_end"))
            if VARIS not in best or new < best[VARIS]:
                best[VARIS] = new
                prev[VARIS] = (state, targets[node], "walk_end", None)
                heapq.heappush(heap, (new, next(sayac), VARIS))
        edges = adj.get(node, ())
        if isinstance(node, str) and last != "walk":     # kural 1: yürüme üstüne yürüme yok
            edges = itertools.chain(edges, walks.get(node, ()))
        for nxt, minutes, kind, lid in edges:
            if kind == "alight" and last == "board":
                continue                                 # kural 2: binip hemen inmek yok
            if kind == "board" and lid in banned:
                continue
            nstate = (nxt, kind)
            new = add(cost, cost_of(minutes, kind))
            if nstate not in best or new < best[nstate]: # daha ucuz yol bulundu: güncelle
                best[nstate] = new
                prev[nstate] = (state, minutes, kind, lid)
                heapq.heappush(heap, (new, next(sayac), nstate))
    return None, [], len(done)

def rebuild_path(prev, state):
    """prev zincirini sondan başa izleyerek yolu kurar: [(nereden, nereye, dk, tür, hat)]"""
    path = []
    while state in prev:
        p, minutes, kind, lid = prev[state]
        path.append((p[0], state[0], minutes, kind, lid))
        state = p
    return path[::-1]

lines_at, modes_at = defaultdict(set), defaultdict(set)  # durak -> geçen hat numaraları / araç türleri
for lid, seq in line_stops.items():
    for _, sid, _ in seq:
        lines_at[sid].add(lines[lid]["short"]); modes_at[sid].add(lines[lid]["mode"])
ISTASYONLAR = [sid for sid in stops if sid.startswith("R")]   # raylı sistem istasyonları ve iskeleler
_ist_tree = cKDTree([(stops[s]["lon"] * KX, stops[s]["lat"] * KY) for s in ISTASYONLAR])

def yakin_istasyon(lat, lon):
    """Aynı adlı durakları ayırt etmek için: en yakın istasyonun adı ve uzaklığı (km)."""
    d, i = _ist_tree.query((lon * KX, lat * KY))
    return stops[ISTASYONLAR[i]]["name"], d / 1000

IKON = {"Marmaray": "🚆", "Metro": "🚇", "Tramvay": "🚊", "Füniküler": "🚞", "Teleferik": "🚡",
        "Vapur": "⛴️", "Metrobüs": "🚍", "Otobüs": "🚌"}

def durak_yerleri(query, limit=5):
    """Adında sorgu geçen duraklar; aynı adlı ama birbirinden uzak duraklar ayrı seçenek olur (ör. 4 ayrı Taşköprü)."""
    names = index.search(query) or index.suggest(query)
    yerler = []
    for n in names:
        gruplar = []                                     # aynı adlı durakları konuma göre grupla
        for sid in sorted(index.by_name[n], key=lambda i: -len(lines_at[i])):
            s = stops[sid]
            for g in gruplar:
                if haversine_m(stops[g[0]]["lat"], stops[g[0]]["lon"], s["lat"], s["lon"]) <= PLACE_RADIUS_M:
                    g.append(sid); break
            else:
                gruplar.append([sid])
        for g in gruplar:
            h = stops[g[0]]
            modlar = set().union(*(modes_at[i] for i in g))
            ikon = next((IKON[m] for m in IKON if m in modlar and m != "Otobüs"), "🚏")
            ist, km = yakin_istasyon(h["lat"], h["lon"])
            yer = "istasyon / iskele" if g[0].startswith("R") else f"{ist} yakını" if km <= 3 else f"{ist} ({km:.0f} km)"
            hatlar = sorted(set().union(*(lines_at[i] for i in g)))
            alt = f"{yer} · {', '.join(hatlar[:4])}{'…' if len(hatlar) > 4 else ''}"
            yerler.append({"label": f"{ikon} {h['name']} — {alt}", "name": h["name"], "lat": h["lat"], "lon": h["lon"],
                           "stops": {i: 0.0 for i in g}})
        if len(yerler) >= limit:
            break
    return yerler[:limit]

_geo_cache = {}
def adres_yerleri(query, limit=3):
    """Adres / mekân arama (Photon, OpenStreetMap). İnternet yoksa boş liste."""
    q = query.strip()
    if len(q) < 3:
        return []
    if q not in _geo_cache:
        try:
            r = requests.get("https://photon.komoot.io/api/", timeout=3,
                             params={"q": q, "limit": limit, "lat": 41.02, "lon": 28.98, "bbox": "27.9,40.7,29.95,41.65"},
                             headers={"User-Agent": "gitgez-ders-projesi/1.0"})
            r.raise_for_status()
            _geo_cache[q] = [(f["properties"], f["geometry"]["coordinates"]) for f in r.json().get("features", [])]
        except Exception:
            _geo_cache[q] = []
    out = []
    for p, (lon, lat) in _geo_cache[q]:
        ad = p.get("name") or p.get("street")
        if ad and 40.75 < lat < 41.52 and 27.95 < lon < 29.92:
            alt = ", ".join(dict.fromkeys(x for x in (p.get("district"), p.get("city")) if x))
            out.append({"label": f"📍 {ad} — {alt}" if alt else f"📍 {ad}", "name": ad, "lat": lat, "lon": lon,
                        "stops": None})
    return out

def yer_ara(query):
    """Önce adı birebir tutan durak, sonra adresler, sonra diğer duraklar (en fazla 6 seçenek)."""
    d, a = durak_yerleri(query), adres_yerleri(query)
    tam = [p for p in d if normalize(p["name"]) == normalize(query)]
    return (tam + a[:2] + [p for p in d if p not in tam] + a[2:])[:6]

def erisim(P, yon="cikis"):
    """Yerden (çıkış) / yere (varış) yürüyerek ulaşılan duraklar {durak: dk}. Durak seçildiyse kendi durakları 0 dk."""
    key = ("_acc", yon, KOSUL["K"])
    if key not in P:
        acc = dict(P["stops"] or {})
        for sid, c in nokta_erisim(P["lat"], P["lon"], yon).items():
            if not P["stops"]:
                acc[sid] = c
        P[key] = acc
    return P[key]

for p in durak_yerleri("Taşköprü"):
    print(p["label"])

PSEUDO = {}                                              # başlangıç/varış adresi için geçici "durak"

def info(sid):
    return stops.get(sid) or PSEUDO[sid]

def to_legs(path, accA):
    """Dijkstra yolunu (kenar listesi) okunabilir parçalara çevirir: yürü / araçla git."""
    legs = []
    first = path[0][0]
    if accA.get(first, 0) > 0:                           # başlangıçtan ilk durağa yürüme
        legs.append({"type": "walk", "from": "__O__", "to": first, "min": accA[first]})
    for u, v, minutes, kind, lid in path:
        if kind == "board":
            legs.append({"type": "ride", "line": lid, "i": v[1], "j": v[1], "from": u, "to": u,
                         "wait": minutes - BOARD_PENALTY, "ride": 0.0, "stops": [u]})
        elif kind == "ride":
            sid = line_stops[lid][v[1]][1]
            L = legs[-1]
            L["ride"] += minutes; L["to"] = sid; L["stops"].append(sid); L["j"] = v[1]
        elif kind in ("walk", "walk_end") and minutes > 0:
            legs.append({"type": "walk", "from": u, "to": "__D__" if kind == "walk_end" else v, "min": minutes})
    return legs

def zenginlestir(legs, gun, saat):
    """Yürümelere sokak yolu; araç parçalarına aynı güzergâhtaki diğer hatlar (birleşik, daha kısa bekleme)."""
    for L in legs:
        if L["type"] == "walk":
            a, b = info(L["from"]), info(L["to"])
            L["yol"] = yol_bul(a["lat"], a["lon"], b["lat"], b["lon"])
            L["min"] = L["yol"]["tmin"]
        else:
            es = [c for c in esdeger_desenler(L["line"], L["i"], L["j"]) if wait_at(c, gun, saat) is not None]
            es = sorted(set(es) | {L["line"]}, key=lambda c: c != L["line"])
            L["hatlar"] = list(dict.fromkeys("Marmaray" if lines[m]["mode"] == "Marmaray" else lines[m]["short"]
                                             for c in es for m in UYELER[c]))
            n = sum(hours.get((m, gun), [0] * 24)[saat] for c in es for m in UYELER[c])
            if n > 0:                                    # hangisi önce gelirse ona binilir
                L["wait"] = min(L["wait"], min(max(60 / n / 2, 1.0), MAX_WAIT))
    return legs

def ozetle(legs):
    walk = sum(L["min"] for L in legs if L["type"] == "walk")
    rides = [L for L in legs if L["type"] == "ride"]
    return {"total": walk + sum(L["wait"] + L["ride"] for L in rides), "walk": walk,
            "transfers": max(len(rides) - 1, 0), "climb": sum(L["yol"]["climb"] for L in legs if L["type"] == "walk"),
            "walk_m": sum(L["yol"]["len"] for L in legs if L["type"] == "walk")}

KRITER = {"süre": "time", "aktarma": "transfers", "yürüme": "walk"}
SIRALA = {"süre": lambda r: (round(r["oz"]["total"]),),
          "aktarma": lambda r: (r["oz"]["transfers"], round(r["oz"]["total"])),
          "yürüme": lambda r: (round(r["oz"]["walk"]), round(r["oz"]["total"]))}

_rota_cache = {}
def rota_bul(A, B, gun=VARSAYILAN_GUN, saat=VARSAYILAN_SAAT, kriter="süre", hava="oto"):
    """A, B: yer sözlükleri (yer_ara'dan). Dönüş: en fazla 2 rota [{legs, oz, ad}], kriterine göre sıralı."""
    kosul_ayarla(gun, saat, hava)
    PSEUDO["__O__"], PSEUDO["__D__"] = A, B
    key = (A["label"], B["label"], gun, saat, kriter, KOSUL["etiket"], KOSUL["trafik"])
    if key in _rota_cache:
        return _rota_cache[key]
    adj, _ = get_graph(gun, saat)
    accA, accB = erisim(A, "cikis"), erisim(B, "varis")
    adaylar = []
    _, yol1, _ = dijkstra(adj, accA, accB, KRITER[kriter])           # 1) en iyi rota
    if yol1:
        adaylar.append(to_legs(yol1, accA))
        yasak = set()                                                 # 2) hatlarını yasakla, tekrar ara
        for L in adaylar[0]:
            if L["type"] == "ride":
                yasak |= set(esdeger_desenler(L["line"], L["i"], L["j"])) | {L["line"]}
        if yasak:                                                     # (rota hiç araç kullanmıyorsa alternatif aranmaz)
            _, yol2, _ = dijkstra(adj, accA, accB, KRITER[kriter], banned=frozenset(yasak))
            if yol2:
                adaylar.append(to_legs(yol2, accA))
    if haversine_m(A["lat"], A["lon"], B["lat"], B["lon"]) <= 2400:  # 3) yürüme seçeneği
        y = yol_bul(A["lat"], A["lon"], B["lat"], B["lon"])
        if not y["yedek"]:
            adaylar.append([{"type": "walk", "from": "__O__", "to": "__D__", "min": y["tmin"]}])
    rotalar = []
    for legs in adaylar:
        zenginlestir(legs, gun, saat)
        rotalar.append({"legs": legs, "oz": ozetle(legs)})
    rotalar.sort(key=SIRALA[kriter])
    rotalar = [r for r in rotalar[:2]                                 # en iyi + 1 alternatif
               if r["oz"]["total"] <= rotalar[0]["oz"]["total"] + ALT_PAY]   # çok uzun alternatif gösterilmez
    for r, ad in zip(rotalar, ("Önerilen", "Alternatif")):
        r["ad"] = ad
    _rota_cache[key] = rotalar
    return rotalar

def rota(nereden, nereye, gun="hi", saat=8, kriter="süre", hava="oto"):
    """Kodla kullanım: rota("Kadıköy", "Taksim", "hi", 8)"""
    A, B = yer_ara(nereden)[0], yer_ara(nereye)[0]
    for r in rota_bul(A, B, gun, saat, kriter, hava):
        parca = " › ".join(f"🚶{L['min']:.0f}" if L["type"] == "walk" else
                           f"{IKON.get(lines[L['line']]['mode'], '🚌')} {'/'.join(L['hatlar'][:3])}" for L in r["legs"])
        print(f"{r['ad']}: {r['oz']['total']:.0f} dk · {parca} · 🚶 {r['oz']['walk']:.0f} dk · {r['oz']['transfers']} aktarma")

rota("Kadıköy", "Taksim")

import json, html as _html

LINE_COLOR = {"M1A": "#E2231A", "M1B": "#E2231A", "M2": "#009A4D", "M3": "#0098D8", "M4": "#E5007E", "M5": "#6F2A91",
              "M6": "#C49A6C", "M7": "#F49AC1", "M8": "#4A90D9", "M9": "#F5C400", "M10": "#8DC63F", "M11": "#8B6DB0",
              "M12": "#00A3A1", "T1": "#0067AC", "T3": "#8B5A2B", "T4": "#F39200", "T5": "#7B4A9E", "F1": "#8B5A2B"}
MODE_COLOR = {"Marmaray": "#00B5AD", "Metrobüs": "#D0101B", "Vapur": "#0B4F8A", "Otobüs": "#1A73E8"}
GUN_ADI = {"hi": "Hafta içi", "cmt": "Cumartesi", "paz": "Pazar"}

def _e(s):
    return _html.escape(str(s))

def hat_rengi(lid):
    L = lines[lid]
    return MODE_COLOR.get(L["mode"]) or LINE_COLOR.get(L["short"], "#5F6368")

def dk(x):
    return "<1" if 0 < x < 0.5 else f"{x:.0f}"

def saat_yaz(m):
    m = int(round(m))
    return f"{m // 60 % 24:02d}:{m % 60:02d}"

def harita(cizgiler, noktalar, h=430):
    """Leaflet haritası (iframe). cizgiler: [{c: [[lat, lon]...], renk, kesikli, kalin}], noktalar: [{lat, lon, ad, ikon}]"""
    doc = f"""<!doctype html><html><head><meta charset="utf-8">
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/leaflet@1.9.4/dist/leaflet.css">
<script src="https://cdn.jsdelivr.net/npm/leaflet@1.9.4/dist/leaflet.js"></script>
<style>html,body,#m{{margin:0;height:100%}}</style></head><body><div id="m"></div><script>
const C = {json.dumps(cizgiler)}, N = {json.dumps(noktalar, ensure_ascii=False)};
const map = L.map('m');
L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Light_Gray_Base/MapServer/tile/{{z}}/{{y}}/{{x}}',
  {{attribution: 'Tiles © Esri', maxZoom: 19, maxNativeZoom: 16}}).addTo(map);
const tum = [];
C.forEach(c => {{ tum.push(...c.c);
  if (!c.kesikli) L.polyline(c.c, {{color: '#fff', weight: c.kalin + 4}}).addTo(map);
  L.polyline(c.c, {{color: c.renk, weight: c.kalin, opacity: c.soluk ? .5 : 1, dashArray: c.kesikli ? '1 8' : null,
                    lineCap: 'round'}}).addTo(map); }});
N.forEach(n => {{ tum.push([n.lat, n.lon]);
  L.marker([n.lat, n.lon], {{icon: L.divIcon({{className: '', iconSize: [26, 26], iconAnchor: [13, 13],
    html: '<div style="font-size:20px;text-align:center">' + n.ikon + '</div>'}})}}).bindTooltip(n.ad).addTo(map); }});
if (tum.length) map.fitBounds(L.latLngBounds(tum), {{padding: [30, 30], maxZoom: 16}}); else map.setView([41.01, 28.98], 12);
</script></body></html>"""
    return (f'<iframe srcdoc="{_html.escape(doc)}" style="width:100%;height:{h}px;border:0;border-radius:14px"></iframe>')

def cip(lid, hatlar=None):
    """Renkli hat etiketi: 🚇 M2 (aynı güzergâhta başka hat varsa +n)"""
    L = lines[lid]
    ad_ = "Marmaray" if L["mode"] == "Marmaray" else L["short"]
    ek = f" +{len(hatlar) - 1}" if hatlar and len(hatlar) > 1 else ""
    return (f'<span style="background:{hat_rengi(lid)};color:#fff;border-radius:6px;padding:1px 7px;'
            f'font-weight:600;white-space:nowrap">{IKON.get(L["mode"], "🚌")} {_e(ad_)}{ek}</span>')

def rota_cizgileri(r, ana):
    out = []
    for L in r["legs"]:
        if L["type"] == "walk":
            out.append({"c": L["yol"]["coords"], "renk": "#5f6368" if ana else "#9aa0a6", "kesikli": True, "kalin": 5})
        else:
            out.append({"c": [[info(s)["lat"], info(s)["lon"]] for s in L["stops"]],
                        "renk": hat_rengi(L["line"]) if ana else "#9aa0a6", "kalin": 7 if ana else 5, "soluk": not ana})
    return out

def rota_karti(r, saat):
    """Bir rotanın kartı: üstte özet, altta adım adım tarif (hep açık)."""
    oz, t = r["oz"], saat * 60
    ozet = " › ".join(f"🚶 {dk(L['min'])}" if L["type"] == "walk" else cip(L["line"], L["hatlar"]) for L in r["legs"])
    adimlar = []
    for L in r["legs"]:
        if L["type"] == "walk":
            y = L["yol"]
            yokus = f" · ↗ {y['climb']:.0f} m yokuş" if y["climb"] >= 5 else ""
            adimlar.append(f'<li><b>{saat_yaz(t)}</b> 🚶 {_e(info(L["to"])["name"])}\'a yürü '
                           f'<span class="mu">· {dk(L["min"])} dk, {y["len"]:.0f} m{yokus}</span></li>')
            t += L["min"]
        else:
            n = len(L["stops"]) - 1
            yon = stops[line_stops[L["line"]][-1][1]]["name"]
            diger = f'<br><span class="mu">Aynı yoldan: {_e(", ".join(L["hatlar"][1:6]))}</span>' if len(L["hatlar"]) > 1 else ""
            adimlar.append(f'<li><b>{saat_yaz(t)}</b> {_e(info(L["from"])["name"])} {cip(L["line"])} '
                           f'<span class="mu">{_e(yon)} yönü · ~{dk(L["wait"])} dk bekleme</span>{diger}<br>'
                           f'<b>{saat_yaz(t + L["wait"] + L["ride"])}</b> {_e(info(L["to"])["name"])}\'da in '
                           f'<span class="mu">· {n} durak, {dk(L["ride"])} dk</span></li>')
            t += L["wait"] + L["ride"]
    aktarma = f"{oz['transfers']} aktarma" if any(L["type"] == "ride" for L in r["legs"]) else "sadece yürüyüş"
    return (f'<div class="kart"><div class="ust"><span class="rad">{r["ad"]}</span>'
            f'<span class="sure">{oz["total"]:.0f} dk</span></div>'
            f'<div class="ozet">{ozet}</div>'
            f'<div class="mu">{saat_yaz(saat * 60)} – {saat_yaz(saat * 60 + oz["total"])} · 🚶 {oz["walk"]:.0f} dk yürüyüş · {aktarma}</div>'
            f'<ol class="adim">{"".join(adimlar)}<li><b>{saat_yaz(t)}</b> 🏁 Varış</li></ol></div>')

STIL = """<style>
.kart{border:1px solid var(--border-color-primary);border-radius:14px;padding:14px 16px;margin:10px 0}
.kart .ust{display:flex;justify-content:space-between;align-items:baseline}
.kart .rad{font-weight:700;font-size:15px}.kart .sure{font-size:22px;font-weight:700}
.kart .ozet{margin:8px 0;line-height:2}.mu{color:var(--body-text-color-subdued);font-size:13px}
.adim{margin:10px 0 0;padding-left:20px;line-height:1.6}.adim li{margin-bottom:8px}
.bilgi{font-size:14px;margin:4px 0}.uyari{color:#b06000;font-weight:600;font-size:14px}
</style>"""

def rota_sonucu(A, B, rotalar, gun, saat):
    """Arayüz için: (harita HTML, ayrıntı HTML)"""
    noktalar = [{"lat": A["lat"], "lon": A["lon"], "ad": A["name"], "ikon": "🟢"},
                {"lat": B["lat"], "lon": B["lon"], "ad": B["name"], "ikon": "🔴"}]
    cizgiler = [c for k, r in reversed(list(enumerate(rotalar))) for c in rota_cizgileri(r, k == 0)]   # önerilen en üstte
    bilgi = (f'<div class="bilgi"><b>{_e(A["name"])} → {_e(B["name"])}</b> · {GUN_ADI[gun]} {saat:02d}:00 · '
             f'{_e(KOSUL["etiket"])}</div>' + (f'<div class="uyari">⚠ {_e(KOSUL["uyari"])}</div>' if KOSUL["uyari"] else ""))
    if not rotalar:
        return harita([], noktalar), STIL + bilgi + "<p>Bu saatte rota bulunamadı. Başka bir saat deneyin.</p>"
    return harita(cizgiler, noktalar), STIL + bilgi + "".join(rota_karti(r, saat) for r in rotalar)

with open(f"{DATA_DIR}/tuvaletler.csv", encoding="utf-8") as f:
    TUVALETLER = [dict(r, lat=float(r["lat"]), lon=float(r["lon"])) for r in csv.DictReader(f) if r["durum"] == "Aktif"]

def yakin_tuvaletler(lat, lon, n=5):
    """En yakın n tuvalet: hepsinin uzaklığı hesaplanır, en küçük n tanesi heapq.nsmallest (Min-Heap) ile seçilir.
    O(N log n); 436 kayıt için ızgaraya gerek yok."""
    return heapq.nsmallest(n, ((haversine_m(lat, lon, t["lat"], t["lon"]), t) for t in TUVALETLER), key=lambda x: x[0])

def tuvalet_sonucu(P):
    kosul_ayarla("hi", 12, "acik", trafik=False)
    bulunan = yakin_tuvaletler(P["lat"], P["lon"])
    satir, noktalar, cizgi = [], [{"lat": P["lat"], "lon": P["lon"], "ad": P["name"], "ikon": "🟢"}], []
    for k, (d, t) in enumerate(bulunan):
        noktalar.append({"lat": t["lat"], "lon": t["lon"], "ad": t["ad"].title(), "ikon": "🚻"})
        if d <= 2500:                                    # yürüme mesafesindeyse sokaktan yol
            y = yol_bul(P["lat"], P["lon"], t["lat"], t["lon"])
            yol = f"🚶 {y['tmin']:.0f} dk ({y['len']:.0f} m)"
            if k == 0:
                cizgi.append({"c": y["coords"], "renk": "#1a73e8", "kesikli": True, "kalin": 5})
        else:
            yol = f"{d / 1000:.1f} km — Rota sekmesinden gidebilirsiniz"
        bakim = " · bebek bakım odası var" if t["bakim_odasi"] == "Var" else ""
        satir.append(f'<li><b>{_e(t["ad"].title())}</b> <span class="mu">({_e(t["ilce"].title())})</span><br>{yol}'
                     f'<span class="mu">{bakim}</span></li>')
    return harita(cizgi, noktalar), STIL + f'<div class="bilgi"><b>🚻 {_e(P["name"])} yakınındaki tuvaletler</b></div>' \
        f'<ol class="adim">{"".join(satir)}</ol>'

BOLGELER = ["Fatih", "Balat", "Beyoğlu", "Beşiktaş", "Kadıköy", "Üsküdar"]
GUN_ADLARI = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]
GIRIS_PAYI = 10            # müze/cami girişinde güvenlik, bilet, ayakkabı payı (dk)
GEZI_MAKS_ADAY = 12        # en yüksek puanlı 12 yer (backtracking'in en kötü durumu O(n!) olduğu için)
CUMA_ARASI = (12 * 60, 14 * 60 + 30)

def _dk(s):
    h, m = map(int, s.split(":")); return h * 60 + m

with open(f"{DATA_DIR}/gezi_yerleri.csv", encoding="utf-8") as f:
    YERLER = []
    for r in csv.DictReader(f):
        y = {"ad": r["ad"], "bolge": r["bolge"], "tur": r["tur"], "lat": float(r["lat"]), "lon": float(r["lon"]),
             "sure": int(r["sure_dk"]) + int(r["kuyruk_dk"]) + (GIRIS_PAYI if r["tur"] == "yer" else 0),
             "saat": {m: tuple(map(_dk, r[m].split("-"))) for m in ("yaz", "kis")}, "gise": int(r["gise_dk"]),
             "kapali": {int(g) for g in r["kapali_gun"].split(",") if g}, "cuma": r["cuma_ogle"] == "1"}
        p = {k: int(r[k]) for k in ("populerlik", "tarih", "manzara", "eglence", "kultur")}
        y["puan"] = 3 * p["populerlik"] ** 2 + 2 * (p["tarih"] + p["manzara"] + p["eglence"] + p["kultur"])
        if y["tur"] == "gecis":
            y["puan"] = round(y["puan"] * 0.6)   # yol üstünde bakılıp geçilen yerler (merdiven, meydan) daha az puan
        YERLER.append(y)

def acik_yerler(bolge, tarih):
    """O tarihte açık olan yerler: açılış, kapanış, son giriş (dk)."""
    mev = "kis" if tarih.month in (11, 12, 1, 2, 3) else "yaz"
    out = []
    for y in YERLER:
        if y["bolge"] == bolge and tarih.weekday() not in y["kapali"]:
            a, k = y["saat"][mev]
            out.append(dict(y, acilis=a, kapanis=k, son_giris=k - y["gise"],
                            ara=CUMA_ARASI if y["cuma"] and tarih.weekday() == 4 else None))
    return out

def ziyaret(y, varis):
    """Yere `varis` dakikasında varınca (giriş, çıkış) ya da None (kapalı / sığmıyor).
    Erken varılırsa açılış beklenir; Cuma namazına denk gelirse namazın bitişi beklenir."""
    giris = max(varis, y["acilis"])
    if y["ara"] and giris < y["ara"][1] and giris + y["sure"] > y["ara"][0]:
        giris = y["ara"][1]
    if giris > y["son_giris"] or giris + y["sure"] > y["kapanis"]:
        return None
    return giris, giris + y["sure"]

def tek_kaynak(adj, sources, limit, hedefler):
    """Hedefsiz Dijkstra: kaynaktan her hedef durağa en kısa toplu taşıma + yürüme süresi {durak: dk}.
    Bütün hedeflere ulaşınca ya da süre `limit`i geçince durur."""
    best, heap, done, out, sayac = {}, [], set(), {}, itertools.count()
    kalan = set(hedefler)
    for s, w in sources.items():
        heapq.heappush(heap, (w, next(sayac), (s, "walk" if w > 0 else "start")))
    while heap and kalan:
        c, _, st = heapq.heappop(heap)
        if c > limit:
            break
        if st in done:
            continue
        done.add(st)
        node, last = st
        if isinstance(node, str) and last != "board" and node not in out:
            out[node] = c
            kalan.discard(node)
        edges = adj.get(node, ())
        if isinstance(node, str) and last != "walk":
            edges = itertools.chain(edges, WALKS.get(node, ()))
        for nxt, m, kind, _ in edges:
            if not (kind == "alight" and last == "board") and c + m < best.get((nxt, kind), 1e18):
                best[(nxt, kind)] = c + m
                heapq.heappush(heap, (c + m, next(sayac), (nxt, kind)))
    return out

def _nokta(y):
    return {"label": y["ad"], "name": y["ad"], "lat": y["lat"], "lon": y["lon"], "stops": None}

def sure_matrisi(A, aday, gun, saat):
    """T[i][j]: i'den j'ye en kısa süre (sokaktan yürüme ya da toplu taşıma); bas[j]: başlangıç noktasından."""
    n = len(aday)
    # 1) Yürüme: bütün yerleri kapsayan TEK sokak alt grafında, tüm yerlerden birden scipy Dijkstra
    xs, ys = [y["lon"] * KX for y in aday], [y["lat"] * KY for y in aday]
    G, _, loc = _altgraf(min(xs) - 900, max(xs) + 900, min(ys) - 900, max(ys) + 900)
    dug = []
    for y in aday:                                       # her yerin en yakın kavşağı (+ oraya yürüme dk)
        n_, d_ = next(((loc[k], d) for k, d in yakin_dugumler(y["lat"], y["lon"], k=6, r=400) if loc[k] >= 0), (0, 1e9))
        dug.append((n_, d_ / WALK_M_PER_MIN))
    dist = sp_dijkstra(G, directed=True, indices=[d[0] for d in dug], limit=90)
    T = [[0.0 if i == j else (float(dist[i, dug[j][0]]) + dug[i][1] + dug[j][1]) * KOSUL["K"]
          for j in range(n)] for i in range(n)]          # ulaşılamayan: inf
    # 2) Toplu taşıma: yürümesi 20 dk'dan uzun çiftler için (ör. Üsküdar → Çamlıca)
    adj, _ = get_graph(gun, saat)
    varis = [erisim(_nokta(y), "varis") for y in aday]
    def toplu(acc, hedef_j):
        d = tek_kaynak(adj, acc, 120, {s for j in hedef_j for s in varis[j]})
        return {j: min((d[s] + w for s, w in varis[j].items() if s in d), default=1e9) for j in hedef_j}
    for i in range(n):
        uzak = [j for j in range(n) if T[i][j] > 20]
        if uzak:
            for j, t in toplu(erisim(_nokta(aday[i]), "cikis"), uzak).items():
                T[i][j] = min(T[i][j], t)
    bas = list(toplu(erisim(A, "cikis"), range(n)).values())
    for j, y in enumerate(aday):
        if haversine_m(A["lat"], A["lon"], y["lat"], y["lon"]) < 2500:
            bas[j] = min(bas[j], yol_bul(A["lat"], A["lon"], y["lat"], y["lon"])["tmin"])
    return T, bas

def gezi_backtracking(aday, T, bas, t0, bitis):
    """En iyi sıra (liste) ve sayaçlar. Değer = Σ puan − (yol + bekleme dk)."""
    n = len(aday)
    en_az_gelis = [min([bas[j]] + [T[i][j] for i in range(n) if i != j]) for j in range(n)]
    maliyet = [en_az_gelis[j] + aday[j]["sure"] for j in range(n)]            # bir yerin en az süresi
    oran_sirasi = sorted(range(n), key=lambda j: -aday[j]["puan"] / maliyet[j])
    en_iyi = {"deger": 0.0, "sira": []}
    sayac = {"dugum": 0, "budama": 0}

    def ust_sinir(kalan_sure, kalan):
        """Kesirli knapsack (greedy): en iyi oranlı yerlerle doldur, son yerin bir kısmını al. İyimser tahmin."""
        toplam = 0.0
        for j in oran_sirasi:
            if j in kalan:
                if maliyet[j] <= kalan_sure:
                    toplam += aday[j]["puan"]; kalan_sure -= maliyet[j]
                else:
                    return toplam + aday[j]["puan"] * max(kalan_sure, 0) / maliyet[j]
        return toplam

    def ara(onceki, t, sira, kalan, deger):
        sayac["dugum"] += 1
        if deger > en_iyi["deger"]:
            en_iyi.update(deger=deger, sira=list(sira))  # şimdiye kadarki en iyi plan
        if deger + ust_sinir(bitis - t, kalan) <= en_iyi["deger"]:
            sayac["budama"] += 1                         # bu daldan daha iyisi çıkamaz: geri dön
            return
        for j in oran_sirasi:                            # umut verici yerler önce: iyi plan erken bulunur
            if j not in kalan:
                continue
            git = bas[j] if onceki is None else T[onceki][j]
            z = ziyaret(aday[j], t + git)
            if z is None or z[1] > bitis:
                continue                                 # kapalı ya da süreye sığmıyor
            sira.append(j); kalan.remove(j)
            ara(j, z[1], sira, kalan, deger + aday[j]["puan"] - (z[0] - t))   # özyineleme (derine in)
            sira.pop(); kalan.add(j)                     # geri al (backtrack)

    ara(None, t0, [], set(range(n)), 0.0)
    return en_iyi["sira"], sayac

def gezi_planla(A, bolge, tarih, bas_dk, sure_saat):
    """Dönüş: (çizelge [(yer, varış, giriş, çıkış)], sayaçlar, kapalı yerler)"""
    gun, saat = gun_tipi(tarih.weekday()), min(bas_dk // 60, 23)
    kosul_ayarla(gun, saat, "oto", tarih=tarih)
    acik = acik_yerler(bolge, tarih)
    kapali = sorted({y["ad"] for y in YERLER if y["bolge"] == bolge} - {y["ad"] for y in acik})
    aday = heapq.nlargest(GEZI_MAKS_ADAY, acik, key=lambda y: y["puan"])     # en yüksek puanlı 12 yer
    if not aday:
        return [], {}, kapali
    T, bas = sure_matrisi(A, aday, gun, saat)
    bitis = bas_dk + sure_saat * 60
    sira, sayac = gezi_backtracking(aday, T, bas, bas_dk, bitis)
    cizelge, t, onceki = [], bas_dk, None
    for j in sira:                                       # seçilen sırayı saatlere dök
        varis = t + (bas[j] if onceki is None else T[onceki][j])
        g, c = ziyaret(aday[j], varis)
        cizelge.append((aday[j], varis, g, c))
        t, onceki = c, j
    return cizelge, sayac, kapali

def gezi_sonucu(A, bolge, tarih, bas_dk, sure_saat):
    cizelge, sayac, kapali = gezi_planla(A, bolge, tarih, bas_dk, sure_saat)
    noktalar = [{"lat": A["lat"], "lon": A["lon"], "ad": A["name"], "ikon": "🟢"}]
    cizgi, satir, onceki = [], [], A
    for no, (y, varis, g, c) in enumerate(cizelge, 1):
        noktalar.append({"lat": y["lat"], "lon": y["lon"], "ad": f"{no}. {y['ad']}", "ikon": f"<b>{no}</b>"})
        cizgi.append({"c": [[onceki["lat"], onceki["lon"]], [y["lat"], y["lon"]]], "renk": "#1a73e8", "kesikli": True, "kalin": 4})
        bekle = f" · {g - varis:.0f} dk açılışı bekle" if g - varis >= 5 else ""
        satir.append(f'<li><b>{saat_yaz(g)}–{saat_yaz(c)}</b> {_e(y["ad"])}'
                     f'<span class="mu"> · yol {varis - (cizelge[no - 2][3] if no > 1 else bas_dk):.0f} dk{bekle}</span></li>')
        onceki = y
    bilgi = (f'<div class="bilgi"><b>🧳 {_e(bolge)}</b> · {tarih.day}.{tarih.month:02d} {GUN_ADLARI[tarih.weekday()]} · '
             f'{saat_yaz(bas_dk)}\'dan {sure_saat:g} saat · {_e(KOSUL["etiket"])}</div>'
             + (f'<div class="mu">Bugün kapalı: {_e(", ".join(kapali))}</div>' if kapali else ""))
    if not cizelge:
        return harita([], noktalar), STIL + bilgi + "<p>Bu sürede gezilecek yer çıkmadı. Süreyi uzatmayı deneyin.</p>"
    alt = (f'<div class="mu">Backtracking {sayac["dugum"]:,} düğüm açtı, {sayac["budama"]:,} dalı budadı. '
           f'(Beta: saatler ve süreler tahminidir; gitmeden kontrol edin.)</div>')
    return harita(cizgi, noktalar), STIL + bilgi + f'<ol class="adim">{"".join(satir)}</ol>' + alt

import gradio as gr

_YER_KAYDI = {}                                          # gösterilen her seçenek: etiket -> yer (hash tablosu)

def ara(q):
    """Kutuya yazdıkça çalışır: sonuçlar açılır listeye gelir, ilki seçili olur."""
    yerler = yer_ara(q) if (q or "").strip() else []
    for p in yerler:
        _YER_KAYDI[p["label"]] = p
    etiketler = [p["label"] for p in yerler]
    return gr.update(choices=etiketler, value=etiketler[0] if etiketler else None,
                     label="Bulunan yer" if etiketler else "Sonuç yok — farklı yazmayı deneyin")

def rota_ui(a, b, gun, saat, kriter, hava):
    A, B = _YER_KAYDI.get(a), _YER_KAYDI.get(b)
    if A is None or B is None:
        return "", "Nereden ve nereye için bir yer yazıp listeden seçin."
    rotalar = rota_bul(A, B, gun, int(saat), kriter, hava)
    return rota_sonucu(A, B, rotalar, gun, int(saat))

def tuvalet_ui(p):
    P = _YER_KAYDI.get(p)
    return tuvalet_sonucu(P) if P else ("", "Bulunduğunuz yeri yazıp seçin.")

def gezi_ui(p, bolge, tarih_s, bas, sure):
    A = _YER_KAYDI.get(p)
    if A is None:
        return "", "Nereden çıkacağınızı yazıp seçin."
    return gezi_sonucu(A, bolge, date.fromisoformat(tarih_s), int(bas), float(sure))

def yer_kutusu(etiket, deger):
    """Yazma kutusu + seçili yer (açılır liste: sadece seçili olan görünür, tıklayınca diğerleri)"""
    ilk = yer_ara(deger)
    for p in ilk:
        _YER_KAYDI[p["label"]] = p
    txt = gr.Textbox(label=etiket, value=deger, placeholder="Durak, adres veya mekân…")
    sec = gr.Dropdown([p["label"] for p in ilk], value=ilk[0]["label"] if ilk else None, label="Bulunan yer")
    txt.input(ara, txt, sec, trigger_mode="always_last", show_progress="hidden")
    txt.submit(ara, txt, sec)
    return sec

_simdi = datetime.now(IST)
GUNLER = [("Hafta içi", "hi"), ("Cumartesi", "cmt"), ("Pazar", "paz")]
SAATLER = [(f"{h:02d}:00", h) for h in range(24)]
SIRALAMA = [("⏱ En hızlı", "süre"), ("🔁 Az aktarma", "aktarma"), ("🚶 Az yürüme", "yürüme")]
HAVALAR = [("🌤 Tahmin (otomatik)", "oto"), ("☀️ Açık", "acik"), ("🌧 Yağmurlu", "yagmur"), ("❄️ Karlı", "kar"),
           ("🌬 Fırtınalı", "firtina")]
TARIHLER = [((_simdi.date() + timedelta(days=i)).strftime("%d.%m") + " " + GUN_ADLARI[(_simdi.date() + timedelta(days=i)).weekday()],
             (_simdi.date() + timedelta(days=i)).isoformat()) for i in range(14)]

with gr.Blocks(title="GitGez") as demo:
    gr.Markdown("# 🚇 GitGez — İstanbul rota ve gezi planlayıcı")
    with gr.Tab("🧭 Rota"):
        with gr.Row(equal_height=False):
            with gr.Column(scale=4, min_width=300):
                a = yer_kutusu("Nereden", "Kadıköy")
                b = yer_kutusu("Nereye", "Taksim")
                with gr.Row():
                    gun = gr.Dropdown(GUNLER, value=gun_tipi(_simdi.weekday()), label="Gün")
                    saat = gr.Dropdown(SAATLER, value=_simdi.hour, label="Saat")
                hava = gr.Dropdown(HAVALAR, value="oto", label="Hava")
                with gr.Accordion("Tercihler", open=False):
                    kriter = gr.Radio(SIRALAMA, value="süre", label="Sıralama")
                bul = gr.Button("Rota bul", variant="primary")
            with gr.Column(scale=8):
                r_harita = gr.HTML()
                r_detay = gr.HTML()
        girdi = [a, b, gun, saat, kriter, hava]
        bul.click(rota_ui, girdi, [r_harita, r_detay])
        kriter.change(rota_ui, girdi, [r_harita, r_detay])
    with gr.Tab("🚻 Tuvalet"):
        with gr.Row(equal_height=False):
            with gr.Column(scale=4, min_width=300):
                t = yer_kutusu("Neredesiniz?", "Kadıköy")
                t_bul = gr.Button("En yakın tuvaletler", variant="primary")
            with gr.Column(scale=8):
                t_harita, t_detay = gr.HTML(), gr.HTML()
        t_bul.click(tuvalet_ui, t, [t_harita, t_detay])
    with gr.Tab("🧳 Gezi (beta)"):
        with gr.Row(equal_height=False):
            with gr.Column(scale=4, min_width=300):
                g = yer_kutusu("Nereden çıkacaksınız?", "Eminönü")
                bolge = gr.Dropdown(BOLGELER, value="Fatih", label="Gezilecek bölge")
                with gr.Row():
                    g_tarih = gr.Dropdown(TARIHLER, value=TARIHLER[0][1], label="Gün")
                    g_bas = gr.Dropdown([(f"{h:02d}:00", h * 60) for h in range(8, 20)], value=10 * 60, label="Başlangıç")
                g_sure = gr.Slider(2, 10, value=5, step=0.5, label="Kaç saatiniz var?")
                g_bul = gr.Button("Gezi planı yap", variant="primary")
            with gr.Column(scale=8):
                g_harita, g_detay = gr.HTML(), gr.HTML()
        g_bul.click(gezi_ui, [g, bolge, g_tarih, g_bas, g_sure], [g_harita, g_detay])
    demo.load(rota_ui, girdi, [r_harita, r_detay])        # açılışta örnek rota

if __name__ == "__main__" and os.environ.get("ROTA_NO_LAUNCH") != "1":
    try:
        import google.colab  # noqa: F401
        colabda = True
    except ImportError:
        colabda = False
    demo.launch(share=colabda)                           # Colab'da herkese açık geçici bağlantı (72 saat)
