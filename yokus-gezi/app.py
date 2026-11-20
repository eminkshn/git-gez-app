"""İstanbul Toplu Taşıma Rota Planlayıcı — yokuş + gezi sürümü, yerel arayüz.
Bu dosya yokus_gezi.ipynb defterinden otomatik üretilir (tools/export_app.py); düzenlemeleri deftere yapın.
Kurulum : pip install "gradio>=6,<7" folium pandas requests numpy scipy
Veri    : GitHub Releases > veri-v1 > zip dosyası, bu dosyayla aynı klasöre
Çalıştır: python app.py
"""
import os
os.chdir(os.path.dirname(os.path.abspath(__file__)))


# ----------------------------------------------------------------------

import os, glob, shutil, zipfile

DATA_DIR = "insan_olmezmis"
GEREKLI = {"stops.csv", "lines.csv", "line_stops.csv", "line_hours.csv", "tuvaletler.csv",
           "dem.npz", "sokak.npz", "yurume.npz", "gezi_yerleri.csv"}
VERI_ZIP = "insan_olmezmis.zip"                          # veri paketi (adı farklı olsa da içeriğine bakılarak bulunur)
ARANACAK = [".", "/content", "/content/drive/MyDrive"]       # Colab'da Drive bağlıysa oradan da bulur

def zip_icerik(z):
    """Zip içindeki dosya adları (klasör içine konmuşsa da: 'istanbul_ag/stops.csv' -> 'stops.csv')."""
    with zipfile.ZipFile(z) as f:
        return {os.path.basename(n): n for n in f.namelist() if not n.endswith("/")}

def uygun_zipler():
    """Adı ne olursa olsun (istanbul_ag (1).zip, 5828…-istanbul_ag.zip …) içinde gerekli tüm dosyalar olan zip'ler,
    en yenisi önce. Uygun olmayanların neden olmadığını da raporlar."""
    iyi, rapor = [], []
    adaylar = {os.path.abspath(z) for d in ARANACAK if os.path.isdir(d) for z in glob.glob(f"{d}/*.zip")}
    for z in sorted(adaylar, key=os.path.getmtime, reverse=True):
        try:
            eksik = GEREKLI - set(zip_icerik(z))
        except zipfile.BadZipFile:
            rapor.append(f"  ✗ {z}: bozuk/yarım zip (yükleme tamamlanmamış olabilir, {os.path.getsize(z) / 1e6:.1f} MB)")
            continue
        if eksik:
            rapor.append(f"  ✗ {z}: eksik dosyalar {sorted(eksik)}" +
                         (" — bu ESKİ veri paketi, güncel insan_olmezmis.zip gerekli" if eksik & {"dem.npz", "gezi_yerleri.csv"} else ""))
        else:
            iyi.append(z)
    return iyi, rapor

def acik_klasor():
    """Zip yerine dosyalar tek tek / açılmış klasör olarak yüklendiyse onu kullan."""
    for d in [DATA_DIR, ".", "/content", "/content/insan_olmezmis"]:
        if os.path.isdir(d) and GEREKLI <= set(os.listdir(d)):
            return d
    return None

zipler, rapor = uygun_zipler()
if not zipler and not acik_klasor():
    if rapor:
        print("Bulunan zip dosyaları uygun değil:\n" + "\n".join(rapor))
    try:
        from google.colab import files          # sadece Colab'da var
        print(f"Lütfen {VERI_ZIP} dosyasını seçin (~55 MB; yükleme 1-2 dk sürebilir).\n"
              "Yükleme takılırsa: soldaki 📁 Dosyalar paneline zip'i sürükleyip bu hücreyi tekrar çalıştırın.")
        files.upload()
    except ImportError:
        raise FileNotFoundError(f"{VERI_ZIP} bu defterle aynı klasörde olmalı")
    zipler, rapor = uygun_zipler()

if zipler:
    shutil.rmtree(DATA_DIR, ignore_errors=True)            # eski açılmış klasör kalmasın
    os.makedirs(DATA_DIR)
    ad_map = zip_icerik(zipler[0])
    with zipfile.ZipFile(zipler[0]) as z:
        for ad, yol in ad_map.items():
            with z.open(yol) as src, open(os.path.join(DATA_DIR, ad), "wb") as dst:
                shutil.copyfileobj(src, dst)
    print("Kullanılan veri:", zipler[0], "->", sorted(os.listdir(DATA_DIR)))
elif acik_klasor():
    DATA_DIR = acik_klasor()
    print("Kullanılan veri klasörü:", os.path.abspath(DATA_DIR))
else:
    raise FileNotFoundError("Uygun veri bulunamadı.\n" + "\n".join(rapor) +
                            "\nGerekli dosyalar: " + ", ".join(sorted(GEREKLI)))

WALK_MAX_M     = 2000   # başlangıç/varışta en fazla bu kadar metre (kuş uçuşu) uzaktaki duraklara bakılır
WALK_M_PER_MIN = 75     # düz yolda yürüme hızı (≈ 4,5 km/sa); yokuşta Tobler fonksiyonuyla değişir
WALK_DETOUR    = 1.3    # kuş uçuşu -> gerçek mesafe (sadece sokak ağı bulunamazsa yedek tahmin)
WALK_LIMIT_DK  = 27     # başlangıç/varışta en fazla bu kadar dakikalık yürüme
WALK_WEIGHT    = 4      # "en az yürüme" kriterinde 1 dk yürüme = 4 dk araçta
BOARD_PENALTY  = 2      # her araca binişte "aktarma zahmeti" payı (dk)
PLACE_RADIUS_M = 800    # aynı adlı duraklardan birbirine bu kadar yakın olanlar "aynı yer" sayılır
MAX_WAIT       = 30     # bir saatte çok az sefer varsa bekleme en fazla bu kadar (dk)
ALT_PENCERE    = 20     # en hızlı rotadan en fazla bu kadar dk uzun alternatifler gösterilir
ALT_MAKS       = 6      # en fazla kaç alternatif
DIK, COK_DIK   = 10, 15 # % eğim: "dik yokuş" ve "çok dik yokuş" uyarı eşikleri
VARSAYILAN_GUN, VARSAYILAN_SAAT = "hi", 8     # hi = hafta içi, cmt = cumartesi, paz = pazar
# Hava ve trafik (docs/PLAN_TRAFIK_HAVA.md) — eşik ve katsayılar başlangıç VARSAYIMIDIR, ölçümle güncellenmeli
HAVA_ESIK = {"yagmur_mm": 0.5, "sicak_c": 33, "ruzgar_kmh": 50, "firtina_kmh": 70, "sis_m": 500}
HAVA_YURUME_K = {"acik": 1.0, "yagmur": 1.15, "kar": 1.5, "sicak": 1.1}     # yürüme süresi çarpanı
HAVA_AGIRLIK_K = {"acik": 1.0, "yagmur": 1.5, "kar": 2.0, "sicak": 1.25}    # "en az yürüme"de yürümenin ek ağırlığı
TRAFIK_SINIR = (0.7, 2.0)                    # otobüs süresi çarpanı en az / en çok
KOSUL = {"sinif": "acik", "K": 1.0, "agirlik": 1.0, "vapur_kapali": False, "trafik": False,
         "anahtar": ("acik", False, False), "etiket": ""}          # şu anki hava/trafik durumu (arama başında ayarlanır)
PROFILLER = {"normal": "Normal", "kacin": "Dik yokuştan kaçın", "engel": "Engelsiz (♿ / bebek arabası)"}

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

# Aynı durak dizisini izleyen hatlar tek "desen": graf bir kez kurulur, sefer sayıları toplanır.
# (ör. aynı güzergâhtaki iki otobüs numarası -> iki ayrı rota değil, daha sık gelen tek rota)
def hat_desenleri():
    by_seq = defaultdict(list)
    for lid, seq in line_stops.items():
        by_seq[(lines[lid]["mode"], tuple(s for _, s, _ in seq))].append(lid)
    temsil, uyeler = {}, {}
    for lids in by_seq.values():
        lids.sort(key=lambda l: (-sum(sum(hours.get((l, g), [0])) for g in ("hi", "cmt", "paz")), lines[l]["short"]))
        uyeler[lids[0]] = lids
        for l in lids:
            temsil[l] = lids[0]
    return temsil, uyeler

TEMSIL, UYELER = hat_desenleri()

import pandas as pd
ozet = pd.DataFrame(lines.values()).groupby("mode").agg(hat=("short", "count"))
print(f"{len(stops):,} durak, {len(lines):,} hat -> {len(UYELER):,} farklı durak dizisi (desen)")
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
        self.by_name = defaultdict(list)                 # hash tablosu: normalize ad -> duraklar
        self.by_word = defaultdict(set)                  # kelime -> adlar (çok kelimeli arama için)
        for sid, s in stops.items():
            n = normalize(s["name"])
            self.by_name[n].append(sid)
            for w in n.split():
                self.by_word[w].add(n)

    def find(self, query):
        q = normalize(query)
        if q in self.by_name:                            # 1) tam eşleşme: O(1)
            return q, self.by_name[q]
        starts = [n for n in self.by_name if n.startswith(q)]
        if starts:                                       # 2) bu kelimeyle başlayan tüm adlar
            return q, [i for n in starts for i in self.by_name[n]]
        close = difflib.get_close_matches(q, self.by_name.keys(), n=1, cutoff=0.6)
        if close:                                        # 3) yazım hatası toleransı
            return close[0], self.by_name[close[0]]
        return None, []

    def search(self, query):
        """Sıralı ad listesi: tam > baştan > tüm kelimeler (önek) > içinde geçen."""
        q = normalize(query)
        if not q:
            return []
        words = q.split()
        aday = None
        for w in words:                                  # her sorgu kelimesi bir ad kelimesinin öneki olmalı
            hit = {n for k, ns in self.by_word.items() if k.startswith(w) for n in ns}
            aday = hit if aday is None else aday & hit
        aday = set(aday or ())
        if len(q) >= 3:
            aday |= {n for n in self.by_name if q in n}
        rank = lambda n: (0 if n == q else 1 if n.startswith(q) else 2 if n.split()[0].startswith(words[0]) else 3,
                          -len(self.by_name[n]), len(n))
        return sorted(aday, key=rank)

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
for q in ["kadikoy", "TAKSİM", "Besiktas", "üsküdr", "Sabiha", "kadikoy isk"]:
    name, ids = index.find(q)
    print(f"{q!r:<14} -> {name!r:<28} {len(ids)} durak   | arama: {index.search(q)[:2]}")

import numpy as np
from scipy import sparse
from scipy.sparse.csgraph import dijkstra as sp_dijkstra
from scipy.spatial import cKDTree

KX, KY = 111_320 * math.cos(math.radians(41.0)), 110_950        # derece -> metre (yerel düzlem)

_dem = np.load(f"{DATA_DIR}/dem.npz")
DEM, DEM_TOP, DEM_LEFT, DEM_RES = _dem["z_dm"].astype(np.float32) / 10, float(_dem["top"]), float(_dem["left"]), float(_dem["res"])

def yukseklik(lat, lon):
    """Bilineer enterpolasyonla zemin yüksekliği (m). Dizi de alır."""
    lat, lon = np.asarray(lat, float), np.asarray(lon, float)
    fr = (DEM_TOP - lat) / DEM_RES - 0.5
    fc = (lon - DEM_LEFT) / DEM_RES - 0.5
    i = np.clip(np.floor(fr).astype(int), 0, DEM.shape[0] - 2)
    j = np.clip(np.floor(fc).astype(int), 0, DEM.shape[1] - 2)
    di, dj = np.clip(fr - i, 0, 1), np.clip(fc - j, 0, 1)
    return (DEM[i, j] * (1 - di) * (1 - dj) + DEM[i, j + 1] * (1 - di) * dj
            + DEM[i + 1, j] * di * (1 - dj) + DEM[i + 1, j + 1] * di * dj)

_s = np.load(f"{DATA_DIR}/sokak.npz")   # pickle yok: her numpy sürümünde açılır
N_LAT, N_LON = _s["node_lat"].astype(float), _s["node_lon"].astype(float)
N_X, N_Y = N_LON * KX, N_LAT * KY
E_PTR, E_TO, E_GID = _s["indptr"].astype(np.int64), _s["to"].astype(np.int64), _s["gid"].astype(np.int64)
E_FROM = np.repeat(np.arange(len(N_LAT)), np.diff(E_PTR))
E_W = {"normal": _s["t_norm"], "kacin": _s["c_kacin"], "engel": _s["c_engel"]}
E_T = _s["t_norm"]                                    # gerçek yürüme süresi (dk)
E_CLIMB = _s["climb"] / 10                            # bu yönde toplam tırmanış (m)
E_MAXUP = _s["maxup"]                                 # bu yönde en dik yokuş (%)
G_PTR, G_LAT, G_LON = _s["g_ptr"], _s["g_lat"], _s["g_lon"]
G_LEN, G_GRADE, G_GMAX, G_NAME, G_STEPS = _s["g_len"], _s["g_grade"], _s["g_gmax"], _s["g_name"], _s["g_steps"]
SOKAK_ADI = _s["names"]
STOP_NODE = dict(zip(_s["stop_ids"].tolist(), _s["stop_node"].tolist()))
STOP_SNAP = dict(zip(_s["stop_ids"].tolist(), _s["stop_snap"].tolist()))
STOP_IDS = _s["stop_ids"].tolist()
E_KEY = E_FROM * len(N_LAT) + E_TO                    # (u, v) -> kenar araması (sıralı)
# Konumlar yalnızca ANA sokak ağına bağlanır (OSM'de ağdan kopuk küçük yaya parçaları var: oraya bağlanan nokta
# hiçbir yere yürüyemez). Bağlı bileşenler bir kez bulunur (scipy, BFS mantığı).
_ncomp, _lab = sparse.csgraph.connected_components(
    sparse.csr_matrix((np.ones(len(E_TO)), (E_FROM, E_TO)), shape=(len(N_LAT), len(N_LAT))), directed=False)
NODE_ANA = np.nonzero(np.bincount(_lab)[_lab] >= 1000)[0]
NODE_TREE = cKDTree(np.c_[N_X[NODE_ANA], N_Y[NODE_ANA]])
print(f"Sokak ağı: {len(N_LAT):,} kavşak, {len(E_TO):,} yönlü sokak parçası, "
      f"DEM {DEM.shape[1]}×{DEM.shape[0]} ({DEM_RES * 3600:.0f}\")")
print(f"Eğim dağılımı: %8 üstü {np.mean(G_GMAX > 8):.0%}, %{COK_DIK} üstü {np.mean(G_GMAX > COK_DIK):.0%} sokak parçası")

class Yurume:
    """Durak -> durak yürüme bağlantıları (sıkıştırılmış diziler). Dijkstra'nın beklediği
    walks.get(durak) arayüzünü verir; listeyi ilk istendiğinde kurar (bellek dostu)."""
    def __init__(self, z, profil):
        self.ptr = z[f"{profil}_ptr"]; self.to = z[f"{profil}_to"]
        self.cost = z[f"{profil}_cost"].astype(np.float32); self.tmin = z[f"{profil}_tmin"].astype(np.float32)
        self.climb = z[f"{profil}_climb"]; self.maxup = z[f"{profil}_maxup"]; self.len = z[f"{profil}_len"]
        self.idx = {sid: i for i, sid in enumerate(STOP_IDS)}
        self.cache = {}
        self.cache_k = {}                                # hava çarpanlı kopyalar: (durak, K) -> liste
    def get(self, sid, default=()):
        r = self.cache.get(sid)
        if r is None:
            i = self.idx.get(sid)
            if i is None:
                return default
            a, b = int(self.ptr[i]), int(self.ptr[i + 1])
            r = self.cache[sid] = [(STOP_IDS[t], c, "walk", k) for k, t, c in
                                   zip(range(a, b), self.to[a:b].tolist(), self.cost[a:b].tolist())]
        k = KOSUL["K"]
        if k == 1.0:
            return r
        rk = self.cache_k.get((sid, k))
        if rk is None:                                   # yağmur/kar: yürüme süreleri uzar
            rk = self.cache_k[(sid, k)] = [(t, c * k, kind, x) for t, c, kind, x in r]
        return rk
    def __len__(self):
        return len(self.to)

_yz = np.load(f"{DATA_DIR}/yurume.npz")
WALKS_P = {p: Yurume(_yz, p) for p in PROFILLER}
WALKS = WALKS_P["normal"]
for p, w in WALKS_P.items():
    print(f"{PROFILLER[p]:<32} {len(w):>9,} durak→durak yürüme bağlantısı")

def _altgraf(x0, x1, y0, y1, profil):
    """Kutudaki düğümlerin alt grafı (scipy CSR). Paralel kenarlardan en ucuzu kalır."""
    sel = np.nonzero((N_X >= x0) & (N_X <= x1) & (N_Y >= y0) & (N_Y <= y1))[0]
    loc = np.full(len(N_X), -1); loc[sel] = np.arange(len(sel))
    w = E_W[profil]
    m = (loc[E_FROM] >= 0) & (loc[E_TO] >= 0) & np.isfinite(w)
    ei = np.nonzero(m)[0]
    ru, rv, rw = loc[E_FROM[ei]], loc[E_TO[ei]], w[ei] + 1e-6
    o = np.lexsort((rw, rv, ru)); ru, rv, rw, ei = ru[o], rv[o], rw[o], ei[o]
    first = np.r_[True, (ru[1:] != ru[:-1]) | (rv[1:] != rv[:-1])]
    n = len(sel)
    A = sparse.csr_matrix((rw[first], (ru[first], rv[first])), shape=(n, n))
    EID = sparse.csr_matrix((ei[first] + 1, (ru[first], rv[first])), shape=(n, n))
    return A, EID, sel, loc

def yakin_dugumler(lat, lon, k=4, r=250):
    d, i = NODE_TREE.query([lon * KX, lat * KY], k=k, distance_upper_bound=r)
    out = [(int(NODE_ANA[n]), float(dd)) for dd, n in zip(np.atleast_1d(d), np.atleast_1d(i)) if np.isfinite(dd)]
    if not out:                                          # sokak uzaksa en yakın tek düğüm
        dd, n = NODE_TREE.query([lon * KX, lat * KY])
        out = [(int(NODE_ANA[n]), float(dd))]
    return out

def _kaynakli_dijkstra(A, starts, limit, ters=False):
    """starts: {yerel düğüm: başlangıç maliyeti}. Sanal süper-kaynak düğümü eklenir (scipy başlangıç maliyeti almaz)."""
    n = A.shape[0]
    if ters:
        A = A.T.tocsr()
    rows = [n] * len(starts); cols = list(starts); vals = [c + 1e-6 for c in starts.values()]
    row = sparse.csr_matrix((vals, (np.zeros(len(rows), int), cols)), shape=(1, n))
    B = sparse.hstack([sparse.vstack([A, row]), sparse.csr_matrix((n + 1, 1))], format="csr")
    dist, pred = sp_dijkstra(B, directed=True, indices=n, limit=limit, return_predecessors=True)
    return dist[:n], pred[:n], n

def nokta_erisim(lat, lon, profil="normal", yon="cikis", limit=WALK_LIMIT_DK):
    """Bir noktadan (çıkış) ya da noktaya (varış) sokaklardan yürüyerek ulaşılan duraklar: {durak: maliyet dk}"""
    r = WALK_MAX_M + 400
    x, y = lon * KX, lat * KY
    A, EID, sel, loc = _altgraf(x - r, x + r, y - r, y + r, profil)
    starts = {}
    for n, d in yakin_dugumler(lat, lon):
        if loc[n] >= 0:
            starts[loc[n]] = min(starts.get(loc[n], 1e9), d / WALK_M_PER_MIN)
    out = {}
    if not starts:
        return out
    dist, _, _ = _kaynakli_dijkstra(A, starts, limit, ters=(yon == "varis"))
    for sid in grid.near(lat, lon):
        n = STOP_NODE.get(sid)
        if n is not None and loc[n] >= 0 and np.isfinite(dist[loc[n]]):
            c = float(dist[loc[n]]) + STOP_SNAP[sid] / WALK_M_PER_MIN
            if c <= limit:
                out[sid] = c * KOSUL["K"]
    return out

_yol_cache = {}
def yol_bul(lat1, lon1, lat2, lon2, profil="normal", n1=None, n2=None):
    """İki nokta arası sokaklardan yürüyüş: geometri + süre, mesafe, tırmanış, en dik yokuş, dik bölümler, profil."""
    key = (round(lat1, 6), round(lon1, 6), round(lat2, 6), round(lon2, 6), profil, n1, n2)
    if key in _yol_cache:
        return _hava_yol(_yol_cache[key])
    crow = haversine_m(lat1, lon1, lat2, lon2)
    m = max(500, 0.6 * crow)
    x0, x1 = sorted((lon1 * KX, lon2 * KX)); y0, y1 = sorted((lat1 * KY, lat2 * KY))
    sonuc = None
    for prof in dict.fromkeys((profil, "normal")):       # profil yol bulamazsa (ör. engelsiz) normal ile dene
        A, EID, sel, loc = _altgraf(x0 - m, x1 + m, y0 - m, y1 + m, prof)
        s_list = [(n1, 0.0)] if n1 is not None else yakin_dugumler(lat1, lon1)
        t_list = [(n2, 0.0)] if n2 is not None else yakin_dugumler(lat2, lon2)
        starts = {loc[n]: d / WALK_M_PER_MIN for n, d in s_list if loc[n] >= 0}
        if not starts:
            continue
        dist, pred, N = _kaynakli_dijkstra(A, starts, np.inf)
        best = min(((float(dist[loc[n]]) + d / WALK_M_PER_MIN, n) for n, d in t_list
                    if loc[n] >= 0 and np.isfinite(dist[loc[n]])), default=None)
        if best is None:
            continue
        # yolu geri kur
        path, cur = [], loc[best[1]]
        while cur != N and cur >= 0:
            p = pred[cur]
            if p == N or p < 0:
                break
            path.append(int(EID[p, cur]) - 1)
            cur = p
        sonuc = _yol_ozet(path[::-1], lat1, lon1, lat2, lon2, prof != profil)
        break
    if sonuc is None:                                    # sokak bulunamadı: kuş uçuşu yedek
        sonuc = {"coords": [(lat1, lon1), (lat2, lon2)], "tmin": crow * WALK_DETOUR / WALK_M_PER_MIN,
                 "len": crow * WALK_DETOUR, "climb": 0.0, "descent": 0.0, "maxup": 0, "dik": [], "profil": [],
                 "parcalar": [], "yedek": True, "profil_disi": False}
    _yol_cache[key] = sonuc
    return _hava_yol(sonuc)

def _hava_yol(s):
    """Önbellekteki yürüyüş sonucu hava çarpanıyla (önbellek değişmez)."""
    return s if KOSUL["K"] == 1.0 else dict(s, tmin=s["tmin"] * KOSUL["K"])

def _yol_ozet(eids, lat1, lon1, lat2, lon2, profil_disi):
    coords = [(lat1, lon1)]
    tmin = climb = descent = length = 0.0
    maxup, dik, parcalar = 0, [], []
    for e in eids:
        g = int(E_GID[e]); fwd = g >= 0; g = g if fwd else -g - 1
        a, b = int(G_PTR[g]), int(G_PTR[g + 1])
        la, lo = G_LAT[a:b].astype(float), G_LON[a:b].astype(float)
        if not fwd:
            la, lo = la[::-1], lo[::-1]
        pts = list(zip(la.tolist(), lo.tolist()))
        grade = int(G_GRADE[g]) * (1 if fwd else -1)
        parcalar.append({"c": pts, "g": grade, "s": bool(G_STEPS[g])})
        coords.extend(pts)
        tmin += float(E_T[e]); length += float(G_LEN[g]); climb += float(E_CLIMB[e])
        descent += max(0.0, -grade / 100 * float(G_LEN[g]))
        if G_LEN[g] >= 30:
            maxup = max(maxup, grade)                    # en dik yokuş: ≥30 m'lik sokak parçasının ortalaması (gürültüye dayanıklı)
        if grade >= DIK and G_LEN[g] >= 25:
            ad = str(SOKAK_ADI[G_NAME[g]]) or ("merdiven" if G_STEPS[g] else "isimsiz sokak")
            if dik and dik[-1]["ad"] == ad:
                dik[-1]["len"] += float(G_LEN[g]); dik[-1]["g"] = max(dik[-1]["g"], grade)
            else:
                dik.append({"ad": ad, "len": float(G_LEN[g]), "g": grade})
    coords.append((lat2, lon2))
    snap = haversine_m(lat1, lon1, *coords[1]) + haversine_m(*coords[-2], lat2, lon2) if len(coords) > 2 else haversine_m(lat1, lon1, lat2, lon2)
    tmin += snap / WALK_M_PER_MIN; length += snap
    # yükseklik profili (~20 m aralıkla)
    c = np.array(coords)
    seg = np.hypot(np.diff(c[:, 1]) * KX, np.diff(c[:, 0]) * KY)
    cum = np.r_[0, np.cumsum(seg)]
    n = int(min(120, max(2, cum[-1] // 20)))
    dd = np.linspace(0, cum[-1], n)
    zz = yukseklik(np.interp(dd, cum, c[:, 0]), np.interp(dd, cum, c[:, 1]))
    return {"coords": coords, "tmin": tmin, "len": length, "climb": climb, "descent": descent, "maxup": maxup,
            "dik": [d for d in dik if d["len"] >= 40 or d["g"] >= COK_DIK], "parcalar": parcalar,
            "profil": list(zip(dd.round(0).tolist(), np.round(zz, 1).tolist())), "yedek": False,
            "profil_disi": profil_disi}

def egim_sinifi(g):
    g = abs(g)
    if g < 5:  return "düz", "#34a853"
    if g < 8:  return "hafif eğimli", "#a3c644"
    if g < DIK: return "eğimli", "#fbbc04"
    if g < COK_DIK: return "dik", "#f57c00"
    return "çok dik", "#d93025"

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
print(f"{len(grid.cells):,} dolu kare, kare başına ort. {len(stops) / len(grid.cells):.1f} durak")

import time
t0 = time.perf_counter()
_k = next(s for s in stops if stops[s]["name"].startswith("Taksim"))
_t = nokta_erisim(stops[_k]["lat"], stops[_k]["lon"])
print(f"Taksim'den sokaklarla {WALK_LIMIT_DK} dk içinde {len(_t)} durak ({(time.perf_counter() - t0) * 1000:.0f} ms)")

import requests, time
from datetime import date, datetime, timedelta, timezone

IST = timezone(timedelta(hours=3))
_UA = {"User-Agent": "gitgez-ders-projesi/1.0"}

def gun_tipi_idx(wd):
    return "paz" if wd == 6 else "cmt" if wd == 5 else "hi"

def hedef_tarih(gun, bugun=None):
    """Seçilen gün tipine (hi/cmt/paz) uyan en yakın tarih (bugün uyuyorsa bugün)."""
    bugun = bugun or datetime.now(IST).date()
    return next(bugun + timedelta(days=k) for k in range(8) if gun_tipi_idx((bugun + timedelta(days=k)).weekday()) == gun)

_hava_cache = {}
_hava_hata = [0.0]                                       # son hata zamanı: 5 dk boyunca tekrar denenmez (arayüz yavaşlamasın)
def hava_tahmini(tarih, saat):
    """Open-Meteo saatlik değerler (İstanbul merkez) ya da None. Geçmiş günler arşivden."""
    key = (tarih, saat)
    if key not in _hava_cache:
        if time.time() - _hava_hata[0] < 300:
            return None
        gecmis = tarih < datetime.now(IST).date()
        url = "https://archive-api.open-meteo.com/v1/archive" if gecmis else "https://api.open-meteo.com/v1/forecast"
        alanlar = ["temperature_2m", "precipitation", "snowfall", "wind_gusts_10m"] + ([] if gecmis else ["visibility"])
        try:
            r = requests.get(url, params={"latitude": 41.015, "longitude": 28.98, "hourly": ",".join(alanlar),
                                          "timezone": "Europe/Istanbul", "start_date": tarih.isoformat(),
                                          "end_date": tarih.isoformat()}, headers=_UA, timeout=4)
            r.raise_for_status()
            h = r.json()["hourly"]
            _hava_cache[key] = {a: h[a][saat] for a in alanlar if h.get(a) and h[a][saat] is not None}
        except Exception as e:
            print(f"(hava bilgisi alınamadı: {type(e).__name__})")
            _hava_hata[0] = time.time()
            return None
    return _hava_cache[key]

def hava_sinifi(v):
    """Ölçümlerden: (sınıf, vapur kapalı mı, uyarılar)"""
    e, uyar = HAVA_ESIK, []
    yag, kar, sic = v.get("precipitation", 0), v.get("snowfall", 0), v.get("temperature_2m", 15)
    hamle, gor = v.get("wind_gusts_10m", 0), v.get("visibility", 1e9)
    sinif = ("kar" if kar > 0 or (sic <= 0 and yag > 0) else "yagmur" if yag >= e["yagmur_mm"]
             else "sicak" if sic >= e["sicak_c"] else "acik")
    firtina = hamle >= e["firtina_kmh"]
    if firtina:
        uyar.append(f"⛴ Fırtına (hamle {hamle:.0f} km/sa): vapurlar kullanılmıyor")
    elif hamle >= e["ruzgar_kmh"]:
        uyar.append(f"⛴ Sert rüzgâr (hamle {hamle:.0f} km/sa): vapur seferleri iptal olabilir")
    if gor < e["sis_m"]:
        uyar.append(f"🌫 Sis (görüş {gor:.0f} m): vapur seferleri gecikebilir")
    return sinif, firtina, uyar

HAVA_SECENEK = [("🌤 Tahmin (otomatik)", "oto"), ("☀️ Açık", "acik"), ("🌧 Yağmurlu", "yagmur"), ("❄️ Karlı", "kar"),
                ("🌬 Fırtınalı", "firtina"), ("🔥 Çok sıcak", "sicak")]
HAVA_AD = {"acik": "☀️ açık", "yagmur": "🌧 yağmurlu", "kar": "❄️ karlı", "sicak": "🔥 çok sıcak"}

def kosul_ayarla(gun, saat, hava="oto", tarih=None, trafik=True):
    """Aramadan önce hava ve trafik durumunu ayarlar (KOSUL). hava: 'oto' = tahmin, ya da elle bir sınıf."""
    global KOSUL
    uyar, olcum = [], ""
    if hava == "oto":
        tarih = tarih or hedef_tarih(gun)
        v = hava_tahmini(tarih, saat)
        if v:
            sinif, firtina, uyar = hava_sinifi(v)
            olcum = (f"{v.get('temperature_2m', 0):.0f}°C, yağış {v.get('precipitation', 0):.1f} mm, "
                     f"hamle {v.get('wind_gusts_10m', 0):.0f} km/sa · Open-Meteo {tarih:%d.%m} {saat:02d}:00")
        else:
            sinif, firtina, olcum = "acik", False, None
    else:
        sinif, firtina = ("acik", True) if hava == "firtina" else (hava, False)
        olcum = "elle seçildi"
        if firtina:
            uyar.append("⛴ Fırtına: vapurlar kullanılmıyor")
    K = HAVA_YURUME_K[sinif]
    trafik = bool(trafik and TRAFIK)
    ad = "🌬 fırtınalı" if firtina and sinif == "acik" else HAVA_AD[sinif]
    parca = [f"{ad} ({olcum})" if olcum else "🌤 hava bilgisi yok (internet yok ya da tarih 16 günden uzak)"]
    if K != 1.0:
        parca.append(f"yürüme süreleri %{(K - 1) * 100:.0f} uzun")
    parca.append("🚦 saatlik trafik (İBB)" if trafik else "🚦 trafik verisi yok")
    KOSUL = {"sinif": sinif, "K": K, "agirlik": HAVA_AGIRLIK_K[sinif], "vapur_kapali": firtina, "trafik": trafik,
             "anahtar": (sinif, firtina, trafik), "uyarilar": uyar, "etiket": " · ".join(parca)}
    return KOSUL

# ---- Trafik: (geohash, gün, saat) -> otobüs süresi çarpanı
_B32 = "0123456789bcdefghjkmnpqrstuvwxyz"
def geohash(lat, lon, n=6):
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

def load_trafik(folder):
    """trafik.csv: geohash, gun, saat, carpan. Yoksa boş sözlük (trafik etkisi yok)."""
    tablo, sehir = {}, defaultdict(list)
    for yol in (f"{folder}/trafik.csv", "trafik.csv", "yokus-gezi/trafik.csv", "/content/trafik.csv"):
        if os.path.exists(yol):
            with open(yol, encoding="utf-8") as f:
                for r in csv.DictReader(f):
                    k = float(r["carpan"])
                    tablo[(r["geohash"], r["gun"], int(r["saat"]))] = k
                    sehir[(r["gun"], int(r["saat"]))].append(k)
            break
    return tablo, {k: float(np.median(v)) for k, v in sehir.items()}

TRAFIK, TRAFIK_SEHIR = load_trafik(DATA_DIR)
_seg_gh = {}
def trafik_carpani(lid, i, gun, saat):
    """Otobüs deseni lid'in i -> i+1 parçası için çarpan (yoksa şehir geneli, o da yoksa 1)."""
    if lines[lid]["mode"] != "Otobüs" or not TRAFIK:
        return 1.0
    gh = _seg_gh.get((lid, i))
    if gh is None:
        a, b = stops[line_stops[lid][i][1]], stops[line_stops[lid][i + 1][1]]
        gh = _seg_gh[(lid, i)] = geohash((a["lat"] + b["lat"]) / 2, (a["lon"] + b["lon"]) / 2, 6)
    k = TRAFIK.get((gh, gun, saat), TRAFIK_SEHIR.get((gun, saat), 1.0))
    return min(max(k, TRAFIK_SINIR[0]), TRAFIK_SINIR[1])

print(f"Trafik tablosu: {len(TRAFIK):,} kayıt" if TRAFIK else "Trafik tablosu yok (trafik.csv): otobüslerde sabit hız")
print("Hava (bugün 08:00):", kosul_ayarla("hi", 8, "oto", tarih=datetime.now(IST).date())["etiket"])
kosul_ayarla("hi", 8, "acik", trafik=False)              # varsayılan: nötr


def wait_at(lid, gun, saat):
    """O gün/saatte desenin (aynı durak dizisindeki tüm hatlar) ortalama beklemesi (dk). Sefer yoksa None."""
    n = prev = 0.0
    for m in UYELER.get(TEMSIL.get(lid, lid), [lid]):
        h = hours.get((m, gun))
        if h:
            n += h[saat]; prev += h[saat - 1]
    if n == 0 and prev == 0:                 # bu saatte ve bir önceki saatte kalkış yok
        return None
    n = n or 1                               # önceki saatte kalkan araç hâlâ yolda olabilir
    return min(max(60 / n / 2, 1.0), MAX_WAIT)

def build_graph(gun, saat):
    """Hat kenarları: bin (bekleme), git (yolculuk), in. Yürüme kenarları WALKS'ta, ortak."""
    adj = defaultdict(list)
    aktif = 0
    for lid in UYELER:                       # her desen bir kez
        seq = line_stops[lid]
        if KOSUL["vapur_kapali"] and lines[lid]["mode"] == "Vapur":
            continue                         # fırtına: vapur yok
        wait = wait_at(lid, gun, saat)
        if wait is None:
            continue                         # o saatte çalışmayan hat
        aktif += len(UYELER[lid])
        for i, (_, sid, _) in enumerate(seq):
            node = (lid, i)
            adj[sid].append((node, wait + BOARD_PENALTY, "board", lid))
            adj[node].append((sid, 0.0, "alight", lid))
            if i + 1 < len(seq):
                dk = seq[i + 1][2] * (trafik_carpani(lid, i, gun, saat) if KOSUL["trafik"] else 1.0)
                adj[node].append(((lid, i + 1), dk, "ride", lid))
    return dict(adj), aktif

_graph_cache = {}
def graf_anahtari(gun, saat):
    return (gun, saat, KOSUL["vapur_kapali"], KOSUL["trafik"])

def get_graph(gun, saat):
    k = graf_anahtari(gun, saat)
    if k not in _graph_cache:
        _graph_cache[k] = build_graph(gun, saat)
    return _graph_cache[k]

adj, aktif = get_graph(VARSAYILAN_GUN, VARSAYILAN_SAAT)
for saat in (3, 8, 13, 23):
    print(f"hafta içi {saat:02d}:00 -> {get_graph('hi', saat)[1]:,} hat çalışıyor")

# Bir yolculuk parçasında aynı durakları aynı sırayla izleyen diğer desenler (kısmi örtüşme: 34 / 34AS / 34BZ…)
desen_at = defaultdict(set)
desen_pos = defaultdict(lambda: defaultdict(list))
for lid in UYELER:
    for i, (_, sid, _) in enumerate(line_stops[lid]):
        desen_at[sid].add(lid); desen_pos[lid][sid].append(i)

def esdeger_desenler(lid, i, j):
    seg = [line_stops[lid][k][1] for k in range(i, j + 1)]
    out = []
    for c in desen_at[seg[0]] & desen_at[seg[-1]]:
        cs = line_stops[c]
        for p in desen_pos[c][seg[0]]:
            if p + len(seg) <= len(cs) and all(cs[p + k][1] == seg[k] for k in range(len(seg))):
                out.append(c); break
    return out

import heapq, itertools

DEST = ("__VARIŞ__", "end")

def dijkstra(adj, sources, targets, objective="time", walks=None, banned=frozenset(), bound=None, h=None):
    """sources / targets: {durak: o durağa yürüme dakikası} (liste de olabilir -> 0 dk).
    h: {düğüm: varışa en az kalan dk} verilirse A* olarak çalışır (sadece "time" kriteri); h'de olmayan düğüm budanır."""
    walks = WALKS if walks is None else walks
    if not isinstance(sources, dict): sources = {s: 0.0 for s in sources}
    if not isinstance(targets, dict): targets = {t: 0.0 for t in targets}

    def cost_of(minutes, kind):
        if objective == "transfers":
            return (1 if kind == "board" else 0, minutes)
        if objective == "walk" and kind in ("walk", "walk_end"):
            return (minutes * WALK_WEIGHT * KOSUL["agirlik"],)
        return (minutes,)

    def add(a, b):
        return tuple(x + y for x, y in zip(a, b))

    def prio(c, node):                                   # öncelik: Dijkstra'da maliyet, A*'da maliyet + alt sınır
        if h is None:
            return c
        if node == DEST[0]:
            return c
        hv = h.get(node)
        return None if hv is None else (c[0] + hv,)

    zero = (0, 0.0) if objective == "transfers" else (0.0,)
    best, prev, heap, counter = {}, {}, [], 0
    for s, w in sources.items():
        state = (s, "walk" if w > 0 else "start")
        c = add(zero, cost_of(w, "walk"))
        pr = prio(c, s)
        if pr is not None and (state not in best or c < best[state]):
            best[state] = c
            heap.append((pr, counter, state)); counter += 1
    heapq.heapify(heap)                                  # Min-Heap
    done = set()
    while heap:
        pr, _, state = heapq.heappop(heap)              # en ucuz durum
        if state in done:
            continue                                     # tembel silme: eski kayıt
        if bound is not None and pr[-1] > bound:
            break                                        # sınırı aştı: daha iyisi yok
        cost = best[state]
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
            if kind == "board" and lid in banned:
                continue
            nstate = (nxt, kind)
            new = add(cost, cost_of(minutes, kind))
            if nstate not in best or new < best[nstate]:
                pr = prio(new, nxt)
                if pr is None:
                    continue                             # buradan varışa yol yok
                best[nstate] = new
                prev[nstate] = (state, minutes, kind, lid)
                heapq.heappush(heap, (pr, counter, nstate)); counter += 1
    return None, [], len(done)

def rebuild_path(prev, state):
    path = []
    while state in prev:
        p, minutes, kind, lid = prev[state]
        path.append((p[0], state[0], minutes, kind, lid))
        state = p
    return path[::-1]

# --- A* için alt sınır: varıştan geriye, kuralları gevşetilmiş tek bir Dijkstra (ters graf) ---
_ters_cache = {}
def ters_graf(gun, saat):
    k = graf_anahtari(gun, saat)                         # A* alt sınırı aynı trafik/vapur durumuyla
    if k not in _ters_cache:
        rev = defaultdict(list)
        for u, es in get_graph(gun, saat)[0].items():
            for v, m, _, _ in es:
                rev[v].append((u, m))
        _ters_cache[k] = dict(rev)
    return _ters_cache[k]

class YurumeTers:
    """walks'ın tersi: durağa hangi duraklardan kaç dk'da yürünür."""
    def __init__(self, w):
        frm = np.repeat(np.arange(len(w.ptr) - 1), np.diff(w.ptr))
        o = np.argsort(w.to, kind="stable")
        self.frm, self.cost = frm[o], w.cost[o]
        self.ptr = np.r_[0, np.cumsum(np.bincount(w.to, minlength=len(w.ptr) - 1))]
        self.idx, self.cache = w.idx, {}
    def get(self, sid, default=()):
        r = self.cache.get(sid)
        if r is None:
            i = self.idx.get(sid)
            if i is None:
                return default
            a, b = int(self.ptr[i]), int(self.ptr[i + 1])
            r = self.cache[sid] = list(zip([STOP_IDS[x] for x in self.frm[a:b].tolist()], self.cost[a:b].tolist()))
        return r

_walk_ters = {}
def alt_sinir(gun, saat, profil, targets, limit):
    """Her düğümden varışa en az süre (dk), en fazla `limit` dk'ya kadar."""
    if profil not in _walk_ters:
        _walk_ters[profil] = YurumeTers(WALKS_P[profil])
    rev, wr = ters_graf(gun, saat), _walk_ters[profil]
    dist, heap = {}, [(c, i, t) for i, (t, c) in enumerate(targets.items())]
    heapq.heapify(heap); cnt = len(heap)
    while heap:
        d, _, u = heapq.heappop(heap)
        if u in dist:
            continue
        if d > limit:
            break
        dist[u] = d
        es = rev.get(u, ())
        if isinstance(u, str):
            es = itertools.chain(es, wr.get(u, ()))
        for v, m in es:
            if v not in dist:
                heapq.heappush(heap, (d + m, cnt, v)); cnt += 1
    return dist

import requests

lines_at = defaultdict(set)                              # durak -> o duraktan geçen hat numaraları
for lid, seq in line_stops.items():
    for _, sid, _ in seq:
        lines_at[sid].add(lines[lid]["short"])
modes_at = defaultdict(set)
for lid, seq in line_stops.items():
    for _, sid, _ in seq:
        modes_at[sid].add(lines[lid]["mode"])
landmarks = [sid for sid in stops if sid.startswith("R")]   # raylı sistem istasyonları ve iskeleler
_lm_tree = cKDTree([(stops[s]["lon"] * KX, stops[s]["lat"] * KY) for s in landmarks])

def yakin_istasyon(lat, lon):
    d, i = _lm_tree.query((lon * KX, lat * KY))
    return stops[landmarks[i]]["name"], d / 1000

def near_stops(lat, lon, radius=WALK_MAX_M):
    """Noktaya kuş uçuşu yakın duraklar: {durak: tahmini yürüme dk} (sokak ağı olmadan, yedek)"""
    out = {}
    for sid in grid.near(lat, lon):
        d = haversine_m(lat, lon, stops[sid]["lat"], stops[sid]["lon"])
        if d <= radius:
            out[sid] = d * WALK_DETOUR / WALK_M_PER_MIN * KOSUL["K"]
    return out

def _ikon(sids):
    m = set().union(*(modes_at[s] for s in sids))
    for mode, ic in (("Marmaray", "🚆"), ("Metro", "🚇"), ("Tramvay", "🚊"), ("Füniküler", "🚞"), ("Teleferik", "🚡"),
                     ("Vapur", "⛴️"), ("Metrobüs", "🚍")):
        if mode in m:
            return ic
    return "🚏"

def durak_yerleri(query, limit=6, benzer=False):
    """Adında sorgu geçen duraklar. benzer=True: yazım hatasına dayanıklı benzerlik araması (difflib)."""
    if not normalize(query):
        return []
    names = index.suggest(query, n=3) if benzer else index.search(query)
    places = []
    for n in names:
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
                yer = "istasyon / iskele"
            elif km <= 3:
                yer = f"{ist} yakını"
            else:
                yer = f"{ist} ({km:.0f} km)"
            alt = f"{yer} · {', '.join(hatlar[:4])}{'…' if len(hatlar) > 4 else ''}"
            places.append({"label": f"{_ikon(c)} {h['name']} — {alt}", "name": h["name"], "sub": alt,
                           "lat": h["lat"], "lon": h["lon"], "stops": c, "access": {i: 0.0 for i in c}})
        if len(places) >= limit:
            break
    return places[:limit]

_geo_cache = {}
def _photon(query, limit):
    r = requests.get("https://photon.komoot.io/api/",
                     params={"q": query, "limit": limit, "lat": 41.02, "lon": 28.98,
                             "bbox": "27.9,40.7,29.95,41.65"},
                     headers={"User-Agent": "istanbul-rota-ders-projesi/2.0"}, timeout=3)
    r.raise_for_status()
    out = []
    for f in r.json().get("features", []):
        p = f["properties"]; lon, lat = f["geometry"]["coordinates"]
        name = p.get("name") or " ".join(x for x in (p.get("street"), p.get("housenumber")) if x)
        sub = ", ".join(dict.fromkeys(x for x in (p.get("street") if p.get("name") else None, p.get("district"),
                                                  p.get("city")) if x))
        if name:
            out.append((name, sub, lat, lon))
    return out

def _nominatim(query, limit):
    r = requests.get("https://nominatim.openstreetmap.org/search",
                     params={"q": query, "format": "jsonv2", "addressdetails": 1, "limit": limit,
                             "countrycodes": "tr", "viewbox": "27.9,41.65,29.95,40.7", "bounded": 1,
                             "accept-language": "tr"},
                     headers={"User-Agent": "istanbul-rota-ders-projesi/2.0"}, timeout=8)
    r.raise_for_status()
    out = []
    for x in r.json():
        a = x.get("address", {})
        name = x.get("name") or x["display_name"].split(",")[0]
        sub = ", ".join(dict.fromkeys(p for p in (a.get("suburb") or a.get("quarter") or a.get("neighbourhood"),
                                                  a.get("town") or a.get("city_district") or a.get("county")) if p))
        out.append((name, sub, float(x["lat"]), float(x["lon"])))
    return out

def adres_yerleri(query, limit=4, canli=False):
    """Adres/mekân arama (internet gerekir; çalışmazsa boş liste). Yürüme erişimi seçilince hesaplanır."""
    q = query.strip()
    if len(q) < 3:
        return []
    key = (normalize(q), limit)
    if key not in _geo_cache:
        res = []
        for f in ((_photon,) if canli else (_photon, _nominatim)):
            try:
                res = f(q, limit)
                if res:
                    break
            except Exception as e:
                print(f"(adres araması: {f.__name__.strip('_')} {type(e).__name__})")
        _geo_cache[key] = res
    places = []
    for name, sub, lat, lon in _geo_cache[key]:
        if not (40.75 < lat < 41.52 and 27.95 < lon < 29.92):
            continue
        places.append({"label": f"📍 {name} — {sub}" if sub else f"📍 {name}", "name": name, "sub": sub,
                       "lat": lat, "lon": lon, "stops": [], "access": None})
    return places

def yer_ara(query, canli=False):
    """Önce adında sorgu geçen duraklar, sonra adres/mekân sonuçları.
    İkisi de boşsa yazımı benzeyen duraklar ('kadıkoy' -> 'Kadıköy')."""
    d = durak_yerleri(query, limit=5 if len(query.strip()) >= 3 else 6)
    a = adres_yerleri(query, canli=canli)
    q = normalize(query)
    tam = [p for p in d if normalize(p["name"]) == q]     # adı birebir aynı durak en üstte
    digr = [p for p in d if p not in tam]
    # semt/mekân adları (ör. "Cihangir") için adres sonucu, adı sadece benzeyen duraklardan önce gelsin
    sira = tam + a[:2] + digr + a[2:]
    return sira[:8] or durak_yerleri(query, benzer=True)

def erisim(P, profil="normal", yon="cikis"):
    """Yerden (çıkış) / yere (varış) yürüyerek ulaşılan duraklar {durak: dk}; profil başına önbellekli."""
    key = f"_acc_{profil}_{yon}_{KOSUL['K']}"
    if key not in P:
        acc = dict(P["access"]) if P.get("stops") else {}
        try:
            for sid, c in nokta_erisim(P["lat"], P["lon"], profil, yon).items():
                if not P.get("stops") and c < acc.get(sid, 1e9):
                    acc[sid] = c
        except Exception as e:                           # sokak ağında sorun olursa kuş uçuşu yedek
            print("(sokak erişimi hesaplanamadı:", type(e).__name__, ")")
            acc = acc or near_stops(P["lat"], P["lon"])
        P[key] = acc or near_stops(P["lat"], P["lon"])
    return P[key]

for p in durak_yerleri("Taşköprü"):
    print(p["label"])

from collections import deque

PSEUDO = {}                                              # başlangıç/varış noktası (adres) için geçici "durak"

def info(sid):
    return stops.get(sid) or PSEUDO[sid]

def to_legs(path, origin):
    legs = []
    first = path[0][0]
    if origin["access"].get(first, 0) > 0:               # adresten ilk durağa yürüme
        legs.append({"type": "walk", "from": "__O__", "to": first, "min": origin["access"][first],
                     "stops": ["__O__", first]})
    for u, v, minutes, kind, lid in path:
        if kind == "board":
            legs.append({"type": "ride", "line": lid, "i": v[1], "j": v[1], "from": u, "to": u,
                         "wait": minutes - BOARD_PENALTY, "ride": 0.0, "n": 0, "stops": [u]})
        elif kind == "ride":
            sid = line_stops[lid][v[1]][1]
            L = legs[-1]
            L["ride"] += minutes; L["n"] += 1; L["to"] = sid; L["stops"].append(sid); L["j"] = v[1]
        elif kind in ("walk", "walk_end") and minutes > 0:
            to = "__D__" if kind == "walk_end" else v
            legs.append({"type": "walk", "from": u, "to": to, "min": minutes, "stops": [u, to]})
    return legs

def _uc_nokta(sid):
    s = info(sid)
    return s["lat"], s["lon"], (STOP_NODE.get(sid) if sid in stops else None)

def zenginlestir(legs, gun, saat, profil):
    """Yürüme parçalarına sokak yolu + yokuş; yolculuk parçalarına eşdeğer hatlar + birleşik bekleme."""
    for L in legs:
        if L["type"] == "walk":
            a, b = _uc_nokta(L["from"]), _uc_nokta(L["to"])
            y = yol_bul(a[0], a[1], b[0], b[1], profil, a[2], b[2])
            L.update(yol=y, min=y["tmin"])
        else:
            es = [c for c in esdeger_desenler(L["line"], L["i"], L["j"]) if wait_at(c, gun, saat) is not None]
            es = sorted(set(es) | {L["line"]}, key=lambda c: (c != L["line"], lines[c]["short"]))
            L["esdeger"] = es
            hatlar = sorted({re.sub(r"(?<=[A-Za-zİı])\d$", "", lines[m]["short"]) if lines[m]["mode"] == "Marmaray" else lines[m]["short"]
                             for c in es for m in UYELER[c]},
                            key=lambda s: (s != lines[L["line"]]["short"], len(s), s))
            L["hatlar"] = hatlar
            n = sum(hours.get((m, gun), [0] * 24)[saat] for c in es for m in UYELER[c])
            if n > 0:                                    # birleşik sıklık: hangisi önce gelirse
                L["wait"] = min(L["wait"], min(max(60 / n / 2, 1.0), MAX_WAIT))
    return legs

def ozetle(legs):
    walk = sum(L["min"] for L in legs if L["type"] == "walk")
    total = walk + sum(L["wait"] + L["ride"] for L in legs if L["type"] == "ride")
    rides = [L for L in legs if L["type"] == "ride"]
    ys = [L["yol"] for L in legs if L["type"] == "walk" and "yol" in L]
    return {"total": total, "walk": walk, "rides": len(rides), "transfers": max(len(rides) - 1, 0),
            "climb": sum(y["climb"] for y in ys), "maxup": max((y["maxup"] for y in ys), default=0),
            "dik": [d for y in ys for d in y["dik"]], "walk_m": sum(y["len"] for y in ys)}

def imza(legs):
    """Rotanın kimliği: hangi duraktan hangi durağa hangi tür araçla. Otobüs numarası dahil değil."""
    return tuple((normalize(info(L["from"])["name"]), normalize(info(L["to"])["name"]), lines[L["line"]]["mode"])
                 for L in legs if L["type"] == "ride") or ("yürüme",)

def _ride_pairs(legs):
    out = {}
    for L in legs:
        if L["type"] == "ride":
            seq = line_stops[L["line"]]
            for k in range(L["i"], L["j"]):
                out[(normalize(stops[seq[k][1]]["name"]), normalize(stops[seq[k + 1][1]]["name"]))] = seq[k + 1][2]
    return out

def alternatif_rotalar(A, B, gun=VARSAYILAN_GUN, saat=VARSAYILAN_SAAT, profil="normal",
                       pencere=ALT_PENCERE, maks=ALT_MAKS, sure_siniri=4.0):
    g_adj, n_aktif = get_graph(gun, saat)
    walks = WALKS_P[profil]
    accA, accB = erisim(A, profil, "cikis"), erisim(B, profil, "varis")
    t0 = time.perf_counter()
    yollar, denenen = [], set()

    hcache = {}
    def dene(objective="time", banned=frozenset(), bound=None, w=walks, wp=profil):
        h = None
        if objective == "time" and bound is not None:
            if wp not in hcache:
                hcache[wp] = alt_sinir(gun, saat, wp, accB, bound)
            h = hcache[wp]
        cost, path, _ = dijkstra(g_adj, accA, accB, objective, w, banned, bound, h)
        if cost is not None:
            yollar.append((path, banned))
        return cost, path

    cost0, path0 = dene()
    # Doğrudan yürüme adayı
    crow = haversine_m(A["lat"], A["lon"], B["lat"], B["lon"])
    adaylar = []
    if crow <= WALK_MAX_M * 1.2:
        y = yol_bul(A["lat"], A["lon"], B["lat"], B["lon"], profil)
        if not y["yedek"] and y["tmin"] <= 45:
          adaylar.append([{"type": "walk", "from": "__O__", "to": "__D__", "min": y["tmin"], "yol": y,
                         "stops": ["__O__", "__D__"]}])
    if cost0 is not None:
        bound = cost0[0] + pencere + 2 * BOARD_PENALTY
        kuyruk = deque([path0])
        while kuyruk and time.perf_counter() - t0 < sure_siniri:
            path = kuyruk.popleft()
            ban0 = next(b for p, b in yollar if p is path)
            for L in to_legs(path, {"access": accA}):
                if L["type"] != "ride":
                    continue
                es = esdeger_desenler(L["line"], L["i"], L["j"])
                ban = frozenset(ban0 | set(es) | {L["line"]})
                if ban in denenen or len(denenen) >= 16 or time.perf_counter() - t0 > sure_siniri:
                    continue
                denenen.add(ban)
                c, p = dene("time", ban, bound)
                if c is not None:
                    kuyruk.append(p)
        for obj in ("transfers", "walk"):
            if time.perf_counter() - t0 < sure_siniri + 4:
                dene(obj)
        if profil == "normal" and time.perf_counter() - t0 < sure_siniri + 6:
            dene("time", bound=bound + 10, w=WALKS_P["kacin"], wp="kacin")   # yokuşsuz yürüyüşlü alternatif
    for path, _ in yollar:
        if path:
            adaylar.append(to_legs(path, {"access": accA}))

    # zenginleştir + tekilleştir
    PSEUDO["__O__"] = {"name": A["name"], "lat": A["lat"], "lon": A["lon"]}
    PSEUDO["__D__"] = {"name": B["name"], "lat": B["lat"], "lon": B["lon"]}
    rotalar = {}
    for legs in adaylar:
        legs = _origin_walk_fix(legs, A, accA)
        zenginlestir(legs, gun, saat, profil)
        oz = ozetle(legs)
        k = imza(legs)
        if k in rotalar:
            eski = rotalar[k]
            for L1, L2 in zip([l for l in eski["legs"] if l["type"] == "ride"], [l for l in legs if l["type"] == "ride"]):
                L1["hatlar"] = list(dict.fromkeys(L1["hatlar"] + L2["hatlar"]))
            if oz["total"] < eski["oz"]["total"] - 0.5:
                eski.update(legs=legs, oz=oz)
            continue
        rotalar[k] = {"legs": legs, "oz": oz}
    if not rotalar:
        return [], {"aktif": n_aktif, "ms": (time.perf_counter() - t0) * 1000}
    liste = sorted(rotalar.values(), key=lambda r: (round(r["oz"]["total"]), r["oz"]["transfers"], r["oz"]["walk"]))
    yurus = rotalar.get(("yürüme",))
    if yurus:                                            # yürümek daha hızlıysa: araçlı rota ancak yokuşu belirgin azaltıyorsa
        yo = yurus["oz"]
        liste = [r for r in liste if r is yurus or r["oz"]["total"] < yo["total"] - 1 or r["oz"]["climb"] < yo["climb"] - 20]
    en_iyi = liste[0]["oz"]["total"]
    def baskin(a, b):                                    # a, b'den hiçbir açıdan kötü değil mi?
        return (a["total"] <= b["total"] + 1 and a["transfers"] <= b["transfers"] and a["walk"] <= b["walk"] + 1
                and a["climb"] <= b["climb"] + 5)
    def ustun(a, b):                                     # a'nın b'ye göre belirgin bir artısı var mı?
        return (a["transfers"] < b["transfers"] or a["walk"] < b["walk"] - 3 or a["climb"] < b["climb"] - 15
                or a["maxup"] < min(b["maxup"], 99) - 4)
    secilen = []
    for r in liste:
        oz = r["oz"]
        if oz["total"] > en_iyi + pencere:
            continue
        rp = _ride_pairs(r["legs"]); rt = sum(rp.values()) or 1
        ekle = True
        for k, s in enumerate(secilen):
            sp = _ride_pairs(s["legs"]); st = sum(sp.values()) or 1
            ortak = sum(v for kk, v in rp.items() if kk in sp)
            if not rp or not sp or (ortak / rt < 0.8 and ortak / st < 0.8):
                continue                                 # aynı koridor değil
            if baskin(oz, s["oz"]):                      # yeni rota eskisini her açıdan geçiyor: yerine koy
                secilen[k] = r; ekle = False; break
            if not ustun(oz, s["oz"]):                   # aynı yol, artısı yok: gösterme (sadece hat farkı)
                ekle = False; break
        if ekle:
            secilen.append(r)
    secilen = [r for i, r in enumerate(secilen) if all(r is not x for x in secilen[:i])]
    secilen = secilen[:maks]
    # etiketler
    def bests(key):
        v = min(key(r) for r in secilen)
        return [r for r in secilen if key(r) == v]
    for r in secilen:
        r["etiket"] = []
    for ad, key in (("En hızlı", lambda r: round(r["oz"]["total"])),
                    ("En az aktarma", lambda r: (r["oz"]["transfers"], round(r["oz"]["total"]))),
                    ("En az yürüme", lambda r: round(r["oz"]["walk"])),
                    ("En az yokuş", lambda r: (round(r["oz"]["climb"] / 5), r["oz"]["maxup"]))):
        b = bests(key)
        if len(b) < len(secilen):
            for r in b:
                r["etiket"].append(ad)
    return secilen, {"aktif": n_aktif, "ms": (time.perf_counter() - t0) * 1000, "arama": len(yollar)}

def _origin_walk_fix(legs, A, accA):
    """to_legs ilk yürüme için A['access'] kullanır; erişim sözlüğüyle düzelt."""
    if legs and legs[0]["type"] != "walk" and accA.get(legs[0]["from"], 0) > 0:
        f = legs[0]["from"]
        legs = [{"type": "walk", "from": "__O__", "to": f, "min": accA[f], "stops": ["__O__", f]}] + legs
    return legs

SIRALAMA = {"süre": lambda r: (r["oz"]["total"],),
            "aktarma": lambda r: (r["oz"]["transfers"], r["oz"]["total"]),
            "yürüme": lambda r: (round(r["oz"]["walk"]), r["oz"]["total"]),
            "yokuş": lambda r: (round(r["oz"]["climb"] / 5), r["oz"]["maxup"] // 3, r["oz"]["total"])}

import json, html as _html

MODE_ICON = {"Metro": "🚇", "Marmaray": "🚆", "Tramvay": "🚊", "Füniküler": "🚞", "Teleferik": "🚡",
             "Vapur": "⛴️", "Metrobüs": "🚍", "Otobüs": "🚌"}
# Hat renkleri: Metro İstanbul harita renklerine yakın değerler. Marmaray: turkuaz.
LINE_COLOR = {"M1A": "#E2231A", "M1B": "#E2231A", "M2": "#009A4D", "M2A": "#009A4D", "M3": "#0098D8",
              "M3A": "#0098D8", "M4": "#E5007E", "M5": "#6F2A91", "M6": "#C49A6C", "M7": "#F49AC1",
              "M8": "#4A90D9", "M9": "#F5C400", "M10": "#8DC63F", "M11": "#8B6DB0", "M12": "#00A3A1",
              "T1": "#0067AC", "T3": "#8B5A2B", "T4": "#F39200", "T5": "#7B4A9E",
              "F1": "#8B5A2B", "F2": "#7F7F7F", "F3": "#8DC63F", "F4": "#8B5A2B", "TF1": "#A0522D", "TF2": "#A0522D"}
MODE_COLOR = {"Marmaray": "#00B5AD", "Metrobüs": "#D0101B", "Vapur": "#0B4F8A", "Otobüs": "#1A73E8",
              "Metro": "#5F6368", "Tramvay": "#0067AC", "Füniküler": "#8B5A2B", "Teleferik": "#A0522D"}
GUN_ADI = {"hi": "hafta içi", "cmt": "cumartesi", "paz": "pazar"}
KRITER = {"süre": "time", "aktarma": "transfers", "yürüme": "walk", "yokuş": "time"}

def hat_rengi(lid):
    L = lines[lid]
    if L["mode"] == "Marmaray":
        return MODE_COLOR["Marmaray"]
    if L["mode"] in ("Metro", "Tramvay", "Füniküler", "Teleferik") and L["short"] in LINE_COLOR:
        return LINE_COLOR[L["short"]]
    return MODE_COLOR.get(L["mode"], "#333333")

def ad(sid):
    s = info(sid)
    return s["name"] + (" ♿" if s.get("wc") == "1" else "")

def dk(x):
    return "<1" if 0 < x < 0.5 else f"{x:.0f}"

def _yon(lid):
    return stops[line_stops[lid][-1][1]]["name"]

def _rota_json(r, saat):
    legs = []
    for L in r["legs"]:
        if L["type"] == "walk":
            y = L["yol"]
            legs.append({"t": "walk", "from": ad(L["from"]), "to": ad(L["to"]), "min": round(L["min"], 1),
                         "m": round(y["len"]), "climb": round(y["climb"]), "desc": round(y["descent"]),
                         "maxup": int(y["maxup"]), "dik": [{"ad": d["ad"], "len": round(d["len"]), "g": d["g"]} for d in y["dik"]],
                         "c": [[round(a, 6), round(b, 6)] for a, b in y["coords"]],
                         "p": [{"c": [[round(a, 6), round(b, 6)] for a, b in pc["c"]], "g": pc["g"]} for pc in y["parcalar"] if abs(pc["g"]) >= 8],
                         "prof": y["profil"], "yedek": y["yedek"], "pd": y["profil_disi"]})
        else:
            Ld = lines[L["line"]]
            legs.append({"t": "ride", "mode": Ld["mode"], "ic": MODE_ICON.get(Ld["mode"], "🚌"),
                         "short": "Marmaray" if Ld["mode"] == "Marmaray" else Ld["short"], "hatlar": L.get("hatlar", [Ld["short"]]), "color": hat_rengi(L["line"]),
                         "yon": _yon(L["line"]), "from": ad(L["from"]), "to": ad(L["to"]), "wait": round(L["wait"], 1),
                         "ride": round(L["ride"], 1), "n": L["n"],
                         "stops": [[info(s)["lat"], info(s)["lon"], ad(s)] for s in L["stops"]]})
    oz = r["oz"]
    return {"legs": legs, "total": round(oz["total"]), "walk": round(oz["walk"]), "walk_m": round(oz["walk_m"]),
            "transfers": oz["transfers"], "climb": round(oz["climb"]), "maxup": int(oz["maxup"]),
            "dik": len(oz["dik"]), "etiket": r.get("etiket", []),
            "dep": f"{saat:02d}:00", "arr": f"{(saat + int((oz['total'] + 0.5) // 60)) % 24:02d}:{int(oz['total'] + 0.5) % 60:02d}",
            "wc": r.get("wc", [])}

def egim_katmani(lat0, lon0, lat1, lon1, min_g=5, maks=9000):
    """Kutudaki sokak parçaları ve eğimleri (harita katmanı için)."""
    gl0 = np.minimum(G_LAT[G_PTR[:-1]], G_LAT[G_PTR[1:] - 1]); gl1 = np.maximum(G_LAT[G_PTR[:-1]], G_LAT[G_PTR[1:] - 1])
    go0 = np.minimum(G_LON[G_PTR[:-1]], G_LON[G_PTR[1:] - 1]); go1 = np.maximum(G_LON[G_PTR[:-1]], G_LON[G_PTR[1:] - 1])
    m = (gl1 >= lat0) & (gl0 <= lat1) & (go1 >= lon0) & (go0 <= lon1) & (G_GMAX >= min_g)
    ids = np.nonzero(m)[0]
    if len(ids) > maks:
        ids = ids[np.argsort(-G_GMAX[ids])[:maks]]
    out = []
    for g in ids.tolist():
        a, b = int(G_PTR[g]), int(G_PTR[g + 1])
        out.append({"c": np.round(np.c_[G_LAT[a:b], G_LON[a:b]].astype(float), 6).tolist(),
                    "g": int(G_GRADE[g]), "x": int(G_GMAX[g]), "n": str(SOKAK_ADI[G_NAME[g]]), "l": round(float(G_LEN[g]))})
    return out

def _bbox(pts, pad_m=250):
    la = [p[0] for p in pts]; lo = [p[1] for p in pts]
    dla, dlo = pad_m / KY, pad_m / KX
    return min(la) - dla, min(lo) - dlo, max(la) + dla, max(lo) + dlo

SAYFA_CSS = r"""
:root{--bg:#ffffff;--fg:#1f1f1f;--mut:#5f6368;--line:#ececec;--card:#fff;--hi:#f4f7fc;--acc:#1a73e8;--soft:#f6f6f6;--shadow:0 1px 3px rgba(60,64,67,.2),0 4px 8px rgba(60,64,67,.1)}
@media (prefers-color-scheme:dark){:root{--bg:#1c1c1e;--fg:#e6e6e6;--mut:#a1a1a6;--line:#2f2f33;--card:#242426;--hi:#26282c;--acc:#8ab4f8;--soft:#2a2a2d}}
*{box-sizing:border-box}html,body{margin:0;height:100%;font-family:Inter,Roboto,"Segoe UI",system-ui,sans-serif;color:var(--fg);background:var(--bg)}
#wrap{display:flex;height:100%}
#panel{width:390px;min-width:390px;height:100%;overflow:auto;border-right:1px solid var(--line);background:var(--bg)}
#map{flex:1;height:100%}
.hdr{padding:14px 16px 10px;border-bottom:1px solid var(--line);position:sticky;top:0;background:var(--bg);z-index:5}
.hdr .od{font-size:14px;line-height:1.5}.hdr .od b{font-weight:600}.hdr .meta{font-size:12px;color:var(--mut);margin-top:4px}
.dot{display:inline-block;width:9px;height:9px;border-radius:50%;margin-right:7px;vertical-align:middle}
.card{padding:14px 16px;border-bottom:1px solid var(--line);cursor:pointer;transition:background .15s}
.card:hover{background:rgba(127,127,127,.06)}.card.on{background:var(--hi)}
.row1{display:flex;align-items:baseline;justify-content:space-between;gap:8px}
.tm{font-size:15px;color:var(--fg)}.dur{font-size:20px;font-weight:600;white-space:nowrap}
.chips{display:flex;flex-wrap:wrap;align-items:center;gap:4px;margin:8px 0 6px}
.chip{display:inline-flex;align-items:center;gap:3px;border-radius:6px;padding:2px 7px;font-size:13px;font-weight:600;color:#fff;line-height:20px}
.chip.w{background:transparent;color:var(--mut);padding:2px 0;font-weight:500}
.sep{color:var(--mut);font-size:12px}
.sub{font-size:12.5px;color:var(--mut);display:flex;flex-wrap:wrap;gap:4px 12px}
.tags{display:flex;gap:6px;margin-top:8px;flex-wrap:wrap}
.tag{font-size:11.5px;padding:2px 8px;border-radius:10px;background:#e6f4ea;color:#137333;font-weight:600}
.tag.t1{background:#e8f0fe;color:#1967d2}.tag.t2{background:#fef7e0;color:#b06000}.tag.t3{background:#fce8e6;color:#c5221f}
.warn{margin-top:6px;font-size:12.5px;color:#b06000}
.steps{display:none;margin-top:12px}.card.open .steps{display:block}
.adim{margin-top:8px;border:1px solid var(--line);background:var(--bg);color:var(--acc);border-radius:16px;padding:4px 12px;font-size:12.5px;cursor:pointer;font-family:inherit}
.card.open .adim:after{content:" ▴"}.card:not(.open) .adim:after{content:" ▾"}
.no{display:inline-flex;align-items:center;justify-content:center;width:24px;height:24px;border-radius:50%;background:var(--acc);color:#fff;font-size:12px;font-weight:700;flex:none}
@media (prefers-color-scheme:dark){.no{color:#1c1c1e}}
.vis{display:grid;grid-template-columns:24px 1fr auto;gap:2px 12px;align-items:start;padding:10px 0}
.vis .ad{font-weight:600;font-size:14.5px;line-height:1.35}.vis .zaman{font-size:13px;font-weight:600;color:var(--fg);white-space:nowrap;font-variant-numeric:tabular-nums}
.vis .mu{grid-column:2/4;font-size:12.5px;color:var(--mut);line-height:1.5}
.badge{display:inline-block;font-size:11.5px;padding:1px 8px;border-radius:10px;background:var(--soft);color:var(--mut);margin:4px 4px 0 0}
.badge.mk{color:#188038}
.yolk{margin:0 0 0 11px;padding:6px 0 6px 23px;border-left:2px dashed var(--line);font-size:12.5px;color:var(--mut);line-height:1.9}
.yolk .chip{font-size:11.5px;padding:0 6px;line-height:18px;vertical-align:middle}
.yolk .r{display:flex;flex-wrap:wrap;gap:4px;align-items:center}.yolk .gec{color:var(--acc)}
.algo{margin:8px 16px 16px;border:1px solid var(--line);border-radius:10px;overflow:hidden;font-size:12.5px}
.algo table{border-collapse:collapse;width:100%}.algo td,.algo th{padding:6px 8px;border-top:1px solid var(--line);text-align:left}
.algo th{background:var(--hi);border-top:0;font-weight:600}.algo .r{text-align:right;font-variant-numeric:tabular-nums}
.lbl{background:#fff;border:0;border-radius:8px;box-shadow:0 1px 3px rgba(0,0,0,.35);font-weight:700;font-size:12px;color:#202124;padding:3px 8px;cursor:pointer}
.lbl.on{background:#1a73e8;color:#fff}.lbl:before{display:none}
.nomk{width:26px;height:26px;border-radius:50%;background:#1a73e8;color:#fff;border:2px solid #fff;box-shadow:0 1px 4px rgba(0,0,0,.45);display:flex;align-items:center;justify-content:center;font-weight:700;font-size:13px}
.st{display:grid;grid-template-columns:22px 1fr;gap:0 10px;position:relative}
.rail{position:relative;display:flex;justify-content:center}
.rail i{position:absolute;top:0;bottom:0;width:6px;border-radius:3px}
.rail i.wk{width:0;border-left:4px dotted #9aa0a6;background:none}
.node{position:relative;z-index:2;width:14px;height:14px;border-radius:50%;background:var(--bg);border:3px solid #5f6368;margin-top:2px}
.st .tx{padding-bottom:14px;font-size:13.5px}
.st .tx b{font-weight:600}.st .mu{color:var(--mut);font-size:12.5px;margin-top:2px}
details{margin-top:4px}summary{cursor:pointer;color:var(--acc);font-size:12.5px}
details ol{margin:4px 0 0 0;padding-left:18px;color:var(--mut);font-size:12.5px}
.prof{margin-top:6px}
.legend{background:var(--card);padding:8px 10px;border-radius:8px;box-shadow:var(--shadow);font-size:12px;color:var(--fg);line-height:18px}
.legend{cursor:pointer}.legend.mini{width:28px;height:22px;overflow:hidden;padding:2px 5px}.legend.mini:before{content:"⛰️"}.legend.mini *{display:none}
@media (max-width:760px){.legend{font-size:10.5px;line-height:14px;padding:5px 7px}}
.legend i{display:inline-block;width:18px;height:5px;border-radius:3px;margin-right:6px;vertical-align:middle}
.leaflet-control-layers{border-radius:8px!important;box-shadow:var(--shadow)!important;border:0!important}
.pin{width:26px;height:26px;border-radius:50% 50% 50% 0;transform:rotate(-45deg);background:#ea4335;border:2px solid #fff;box-shadow:0 1px 4px rgba(0,0,0,.4)}
.pin:after{content:"";position:absolute;width:8px;height:8px;border-radius:50%;background:#a50e0e;left:7px;top:7px}
.og{width:16px;height:16px;border-radius:50%;background:#fff;border:4px solid #202124;box-shadow:0 1px 3px rgba(0,0,0,.4)}
.empty{padding:28px 18px;color:var(--mut);font-size:14px}
.foot{padding:10px 16px 18px;font-size:11.5px;color:var(--mut)}
.wcl{margin:0;padding-left:18px;font-size:12.5px;color:var(--mut)}
@media (max-width:760px){#wrap{flex-direction:column-reverse}#panel{width:100%;min-width:0;height:56%;border-right:0;border-top:1px solid var(--line)}#map{height:44%;flex:none}}
"""

SAYFA_JS = r"""
const D = DATA;
const map = L.map('map', {zoomControl: true, preferCanvas: false});
// Not: CARTO / OSM karoları iframe (srcdoc) içinden anahtar ya da referer istiyor; Esri karoları anahtarsız çalışır.
const ESRI = 'https://server.arcgisonline.com/ArcGIS/rest/services/';
const KOYU = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;   // koyu temada koyu harita
const TON = KOYU ? 'Dark' : 'Light';
const sade = L.layerGroup([
  L.tileLayer(ESRI + 'Canvas/World_' + TON + '_Gray_Base/MapServer/tile/{z}/{y}/{x}', {attribution: 'Tiles © Esri — Esri, HERE, Garmin, © OpenStreetMap', maxZoom: 19, maxNativeZoom: 16}),
  L.tileLayer(ESRI + 'Canvas/World_' + TON + '_Gray_Reference/MapServer/tile/{z}/{y}/{x}', {maxZoom: 19, maxNativeZoom: 16})]).addTo(map);
const sokak = L.tileLayer(ESRI + 'World_Street_Map/MapServer/tile/{z}/{y}/{x}', {attribution: 'Tiles © Esri', maxZoom: 19});
const voyager = sade;
const esri = L.tileLayer(ESRI + 'World_Imagery/MapServer/tile/{z}/{y}/{x}',
  {attribution: 'Tiles © Esri', maxZoom: 19});
const hill = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/Elevation/World_Hillshade/MapServer/tile/{z}/{y}/{x}',
  {attribution: 'Hillshade © Esri', maxZoom: 19, opacity: 0.35});
function gcol(g){g=Math.abs(g);return g<5?'#34a853':g<8?'#a3c644':g<10?'#fbbc04':g<15?'#f57c00':'#d93025'}
const egim = L.layerGroup();
(D.egim||[]).forEach(e=>{L.polyline(e.c,{color:gcol(e.x),weight:e.x>=10?4:3,opacity:.85})
  .bindTooltip((e.n||'isimsiz sokak')+' · en dik %'+e.x+' · '+e.l+' m').addTo(egim)});
if (D.egimAcik) egim.addTo(map);
const overlays = {'Eğim (sokaklar)': egim, 'Topoğrafya (gölgeli kabartma)': hill};
L.control.layers({'Sade': sade, 'Sokak': sokak, 'Uydu': esri}, overlays, {collapsed: true, position: 'topright'}).addTo(map);

// Centripetal Catmull-Rom: duraklar arası düz çizgileri yumuşak eğriye çevirir
function smooth(pts, seg){
  if (pts.length < 3) return pts; seg = seg || 8;
  const P = [pts[0]].concat(pts, [pts[pts.length-1]]), out = [];
  const d = (a,b)=>Math.pow(Math.hypot(a[0]-b[0], (a[1]-b[1])*0.755), 0.5) || 1e-9;
  for (let i=1;i<P.length-2;i++){
    const p0=P[i-1],p1=P[i],p2=P[i+1],p3=P[i+2];
    const t0=0,t1=t0+d(p0,p1),t2=t1+d(p1,p2),t3=t2+d(p2,p3);
    for (let k=0;k<seg;k++){
      const t=t1+(t2-t1)*k/seg;
      const A1=lerp(p0,p1,t0,t1,t),A2=lerp(p1,p2,t1,t2,t),A3=lerp(p2,p3,t2,t3,t);
      const B1=lerp(A1,A2,t0,t2,t),B2=lerp(A2,A3,t1,t3,t);
      out.push(lerp(B1,B2,t1,t2,t));
    }
  }
  out.push(pts[pts.length-1]); return out;
}
function lerp(a,b,ta,tb,t){const u=(tb-ta)||1e-9;return [a[0]*(tb-t)/u+b[0]*(t-ta)/u, a[1]*(tb-t)/u+b[1]*(t-ta)/u]}

const routeLayers = [];
function drawRoute(r, on){
  const g = L.layerGroup(), all=[];
  r.legs.forEach((l,i)=>{
    if (l.t==='visit'){
      all.push([l.lat,l.lon]);
      if (l.c && on){ all.push(...l.c);
        L.polyline(l.c,{color:'#fff',weight:9,opacity:.95,lineCap:'round'}).addTo(g);
        L.polyline(l.c,{color:'#1a73e8',weight:5,opacity:.9,dashArray:'0.1 9',lineCap:'round'}).bindTooltip(l.ad).addTo(g); }
      if (on) L.marker([l.lat,l.lon],{icon:L.divIcon({className:'',html:'<div class="nomk">'+l.no+'</div>',iconSize:[26,26],iconAnchor:[13,13]}),zIndexOffset:800})
        .bindTooltip(l.no+'. '+l.ad+' · '+l.giris+'–'+l.cikis).addTo(g);
      return;
    }
    if (l.t==='pass'){
      if (on) L.circleMarker([l.lat,l.lon],{radius:5,color:'#1a73e8',weight:2,fillColor:'#fff',fillOpacity:1})
        .bindTooltip('Yol üstünde: '+l.ad).addTo(g);
      return;
    }
    if (l.t==='walk'){
      all.push(...l.c);
      if (on) L.polyline(l.c,{color:'#fff',weight:8,opacity:.9,lineCap:'round'}).addTo(g);
      L.polyline(l.c,{color:on?'#5f6368':'#bdc1c6',weight:on?5:4,dashArray:'0.1 9',lineCap:'round',opacity:on?1:.8}).addTo(g);
      if (on) l.p.forEach(p=>{ if (p.g>=8||p.g<=-12) L.polyline(p.c,{color:gcol(p.g),weight:6,dashArray:'0.1 9',lineCap:'round'})
           .bindTooltip((p.g>0?'↗ yokuş yukarı %':'↘ iniş %')+Math.abs(p.g)).addTo(g)});
    } else {
      const pts = l.stops.map(s=>[s[0],s[1]]); all.push(...pts);
      const sm = smooth(pts, 8);
      if (on){
        L.polyline(sm,{color:'#fff',weight:11,opacity:1,lineJoin:'round',lineCap:'round'}).addTo(g);
        L.polyline(sm,{color:l.color,weight:7,opacity:1,lineJoin:'round',lineCap:'round'})
          .bindTooltip(l.ic+' '+l.hatlar.join(' · ')+' → '+l.yon).addTo(g);
        l.stops.forEach((s,k)=>{const end=(k===0||k===l.stops.length-1);
          L.circleMarker([s[0],s[1]],{radius:end?6:3.2,color:end?'#202124':l.color,weight:end?3:2,fillColor:'#fff',fillOpacity:1})
           .bindTooltip(s[2]).addTo(g)});
      } else {
        L.polyline(sm,{color:'#9aa0a6',weight:5,opacity:.55,lineJoin:'round',lineCap:'round'}).addTo(g);
      }
    }
  });
  if (all.length && D.routes.length > 1){                    // haritada her alternatifin üstünde süre etiketi
    const m = all[Math.floor(all.length/2)];
    L.tooltip({permanent:true,direction:'center',className:'lbl'+(on?' on':''),interactive:true})
      .setContent(r.lbl || (r.total+' dk')).setLatLng(m).addTo(g);
  }
  return {g, all};
}
let cur = -1;
function select(i){
  routeLayers.forEach(x=>map.removeLayer(x.g)); routeLayers.length=0;
  D.routes.forEach((r,k)=>{ if(k!==i){const x=drawRoute(r,false); x.g.addTo(map); x.g.eachLayer(l=>{ if(l.on) l.on('click',()=>select(k)); const el=l.getElement&&l.getElement(); if(el&&el.classList.contains('lbl')) el.addEventListener('click',()=>select(k)); }); routeLayers.push(x);} });
  const x = drawRoute(D.routes[i], true); x.g.addTo(map); routeLayers.push(x);
  document.querySelectorAll('.card').forEach((c,k)=>c.classList.toggle('on',k===i));
  const vis = D.routes[i].legs.filter(l=>l.t==='visit').map(l=>[l.lat,l.lon]);   // gezi: gezilen yerlere odaklan
  const odak = vis.length > 1 ? vis : x.all;
  if (cur !== i && odak.length) map.fitBounds(L.latLngBounds(odak), {padding:[50,50], maxZoom:16});
  cur = i;
  const c = document.querySelectorAll('.card')[i]; if (c && window.innerWidth>760) c.scrollIntoView({block:'nearest',behavior:'smooth'});
}
document.querySelectorAll('.card').forEach((c,k)=>c.addEventListener('click',e=>{
  if(e.target.closest('details')) return;
  if(e.target.closest('.adim')){ c.classList.toggle('open'); select(k); return; }
  select(k)}));
const pinO = L.divIcon({className:'',html:'<div class="og"></div>',iconSize:[24,24],iconAnchor:[12,12]});
const pinD = L.divIcon({className:'',html:'<div class="pin"></div>',iconSize:[26,26],iconAnchor:[13,26]});
if (D.O) L.marker(D.O,{icon:pinO,zIndexOffset:900}).bindTooltip(D.On).addTo(map);
if (D.D) L.marker(D.D,{icon:pinD,zIndexOffset:1000}).bindTooltip(D.Dn).addTo(map);
(D.wc||[]).forEach(t=>L.marker([t.lat,t.lon],{icon:L.divIcon({className:'',html:'<div style="font-size:20px">🚻</div>',iconSize:[22,22],iconAnchor:[11,11]})})
   .bindTooltip(t.ad+' · '+t.info).addTo(map));
(D.paths||[]).forEach((p,k)=>{});
if (D.routes.length) select(0);
else if (D.fit) map.fitBounds(D.fit); else map.setView(D.O||[41.01,28.98], 14);
if (D.onload) D.onload(map);
"""

def _profil_svg(prof, w=250, h=46):
    if len(prof) < 2:
        return ""
    xs = [p[0] for p in prof]; zs = [p[1] for p in prof]
    zmin, zmax = min(zs), max(zs)
    rng = max(zmax - zmin, 8)
    X = lambda d: 2 + (w - 4) * d / max(xs[-1], 1)
    Y = lambda z: h - 4 - (h - 10) * (z - zmin) / rng
    pts = " ".join(f"{X(d):.1f},{Y(z):.1f}" for d, z in prof)
    return (f'<svg class="prof" width="{w}" height="{h + 12}" viewBox="0 0 {w} {h + 12}" role="img" aria-label="yükseklik profili">'
            f'<polygon points="2,{h - 2} {pts} {w - 2},{h - 2}" fill="rgba(26,115,232,.13)"/>'
            f'<polyline points="{pts}" fill="none" stroke="#1a73e8" stroke-width="2" stroke-linejoin="round"/>'
            f'<text x="2" y="{h + 10}" font-size="10" fill="#80868b">{zs[0]:.0f} m</text>'
            f'<text x="{w - 2}" y="{h + 10}" font-size="10" fill="#80868b" text-anchor="end">{zs[-1]:.0f} m · en yüksek {zmax:.0f} m</text></svg>')

def _e(s):
    return _html.escape(str(s))

def _kart_html(r, i):
    chips = []
    for k, l in enumerate(r["legs"]):
        if k:
            chips.append('<span class="sep">›</span>')
        if l["t"] == "walk":
            if len(r["legs"]) == 1:
                chips.append(f'<span class="chip w">🚶 {l["m"]} m yürüyüş</span>')
            else:
                chips.append(f'<span class="chip w">🚶 {dk(l["min"])}</span>')
        else:
            extra = f' +{len(l["hatlar"]) - 1}' if len(l["hatlar"]) > 1 else ""
            chips.append(f'<span class="chip" style="background:{l["color"]}">{l["ic"]} {_e(l["short"])}{extra}</span>')
    sub = [f'🚶 {r["walk"]} dk ({r["walk_m"]} m)']
    if any(l["t"] == "ride" for l in r["legs"]):
        sub.append(f'🔁 {r["transfers"]} aktarma' if r["transfers"] else "aktarmasız")
    if r["climb"] >= 3:
        sub.append(f'↗ {r["climb"]} m tırmanış')
    tagcls = {"En hızlı": "t1", "En az aktarma": "", "En az yürüme": "t2", "En az yokuş": ""}
    tags = "".join(f'<span class="tag {tagcls.get(t, "")}">{t}</span>' for t in r["etiket"])
    warn = ""
    if r["maxup"] >= COK_DIK:
        warn = f'<div class="warn">⚠ Çok dik yokuş var (en dik %{r["maxup"]}). Daha az yokuşlu seçenek için “Dik yokuştan kaçın”.</div>'
    elif r["maxup"] >= DIK:
        warn = f'<div class="warn">⚠ Dik yokuş var (en dik %{r["maxup"]})</div>'
    steps = []
    for l in r["legs"]:
        if l["t"] == "walk":
            ws = [f'{l["m"]} m']
            if l["climb"] >= 2: ws.append(f'↗ {l["climb"]} m')
            if l["desc"] >= 2: ws.append(f'↘ {l["desc"]} m')
            if l["maxup"] >= 5: ws.append(f'en dik %{l["maxup"]}')
            dikler = "".join(f'<div class="warn">⚠ {_e(d["ad"])}: {d["len"]} m boyunca %{d["g"]} {"çok dik " if d["g"] >= COK_DIK else "dik "}yokuş</div>'
                             for d in l["dik"][:3])
            not_ = ('<div class="mu">(sokak ağı bulunamadı; kuş uçuşu tahmin)</div>' if l["yedek"] else
                    '<div class="mu">(seçili profilde yol yok; normal yürüyüş yolu gösteriliyor)</div>' if l["pd"] else "")
            steps.append(f'<div class="st"><div class="rail"><i class="wk"></i></div><div class="tx">'
                         f'<b>🚶 Yürü {dk(l["min"])} dk</b> <span class="mu">· {" · ".join(ws)}</span>'
                         f'<div class="mu">{_e(l["from"])} → {_e(l["to"])}</div>{dikler}{not_}{_profil_svg(l["prof"])}</div></div>')
        else:
            durak = "".join(f"<li>{_e(s[2])}</li>" for s in l["stops"][1:-1])
            ayni = (f'<div class="mu">Aynı güzergâh: {" · ".join(_e(h) for h in l["hatlar"][:8])}'
                    f'{"…" if len(l["hatlar"]) > 8 else ""}</div>') if len(l["hatlar"]) > 1 else ""
            steps.append(f'<div class="st"><div class="rail"><i style="background:{l["color"]}"></i><div class="node" style="border-color:{l["color"]}"></div></div>'
                         f'<div class="tx"><b>{_e(l["from"])}</b>'
                         f'<div style="margin:6px 0"><span class="chip" style="background:{l["color"]}">{l["ic"]} {_e(l["short"])}</span> '
                         f'<span class="mu">{_e(l["yon"])} yönü</span></div>{ayni}'
                         f'<div class="mu">~{dk(l["wait"])} dk bekleme · {l["n"]} durak · {dk(l["ride"])} dk</div>'
                         + (f'<details><summary>{l["n"] - 1} ara durak</summary><ol>{durak}</ol></details>' if l["n"] > 1 else "")
                         + f'<div style="margin-top:8px"><b>{_e(l["to"])}</b> <span class="mu">— in</span></div></div></div>')
    wc = ""
    if r.get("wc"):
        wc = '<div class="mu" style="margin-top:4px">🚻 Yol üstündeki tuvaletler</div><ul class="wcl">' + "".join(
            f'<li>{_e(t["ad"])} — {_e(t["info"])}</li>' for t in r["wc"][:5]) + "</ul>"
    return (f'<div class="card" data-i="{i}"><div class="row1"><span class="tm">{r["dep"]} – {r["arr"]}</span>'
            f'<span class="dur">{r["total"]} dk</span></div><div class="chips">{"".join(chips)}</div>'
            f'<div class="sub">{"".join(f"<span>{s}</span>" for s in sub)}</div>'
            f'{warn}<div class="tags">{tags}</div><button class="adim">Adım adım</button>'
            f'<div class="steps">{"".join(steps)}{wc}</div></div>')

def sayfa(data, panel_html, h=None):
    """Tek parça HTML (Leaflet). Gradio'da iframe içinde gösterilir."""
    doc = f"""<!doctype html><html lang="tr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/leaflet@1.9.4/dist/leaflet.css">
<script src="https://cdn.jsdelivr.net/npm/leaflet@1.9.4/dist/leaflet.js"></script>
<style>{SAYFA_CSS}</style></head><body><div id="wrap"><div id="panel">{panel_html}</div><div id="map"></div></div>
<script>const DATA = {json.dumps(data, ensure_ascii=False)};{SAYFA_JS}</script></body></html>"""
    return doc

def iframe(doc, h=720):
    return (f'<iframe srcdoc="{_html.escape(doc)}" style="width:100%;height:min({h}px,86vh);border:0;'
            f'border-radius:16px;box-shadow:0 1px 3px rgba(60,64,67,.2),0 4px 12px rgba(60,64,67,.12)"></iframe>')

def rota_sayfasi(A, B, rotalar, meta, gun, saat, profil, wc_list=()):
    saat = int(saat)
    R = [_rota_json(r, saat) for r in rotalar]
    walk_pts = [c for r in rotalar for L in r["legs"] if L["type"] == "walk" for c in L["yol"]["coords"]]
    egim = []
    if walk_pts:
        egim = egim_katmani(*_bbox(walk_pts, 300), min_g=5, maks=4000)
    data = {"routes": R, "O": [A["lat"], A["lon"]], "D": [B["lat"], B["lon"]], "On": A["name"], "Dn": B["name"],
            "egim": egim, "egimAcik": False, "wc": [{"lat": t["lat"], "lon": t["lon"], "ad": t["ad"], "info": i}
                                                     for t, i in wc_list]}
    hdr = (f'<div class="hdr"><div class="od"><span class="dot" style="background:#202124"></span><b>{_e(A["name"])}</b><br>'
           f'<span class="dot" style="background:#ea4335"></span><b>{_e(B["name"])}</b></div>'
           f'<div class="meta">{GUN_ADI[gun]} {saat:02d}:00 · {PROFILLER[profil]} · {len(R)} rota · '
           f'{meta.get("aktif", 0):,} hat çalışıyor'
           + (f'<br>{_e(meta["kosul"])}' if meta.get("kosul") else "")
           + "".join(f'<br><b style="color:#b06000">{_e(u)}</b>' for u in meta.get("uyarilar", [])) + '</div></div>')
    if R:
        body = "".join(_kart_html(r, i) for i, r in enumerate(R))
    else:
        body = '<div class="empty">Bu saatte rota bulunamadı. Başka bir saat ya da yürüyüş profili deneyin.</div>'
    foot = (f'<div class="foot">Süreler tahminidir (sefer sıklığı + mesafe). Yürüyüş sokak ağı üzerinden, yokuşa göre '
            f'hesaplanır. Haritada sağ üstten <b>Eğim</b> katmanını açabilirsiniz. · {meta.get("ms", 0):.0f} ms</div>')
    return sayfa(data, hdr + body + foot)

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
    return {"label": f"🚻 {t['ad']} — {t['ilce'].title()}", "name": f"🚻 {t['ad'].title()}", "sub": t["ilce"].title(),
            "lat": t["lat"], "lon": t["lon"], "stops": [], "access": None}

_rota_cache = {}
def rota_hesapla(A, B, kriter="süre", gun=VARSAYILAN_GUN, saat=VARSAYILAN_SAAT, tuvalet=True, profil="normal",
                 hava=None):
    """A, B: yer sözlükleri. Dönüş: (en iyi rotanın legs'i, markdown metin, yol üstü tuvaletler, tüm rotalar, meta)"""
    if hava is not None:                                 # None: mevcut KOSUL (testler); arayüz her zaman verir
        kosul_ayarla(gun, saat, hava)
    key = (A["label"], A["lat"], A["lon"], B["label"], B["lat"], B["lon"], gun, saat, profil, KOSUL["anahtar"])
    if key not in _rota_cache:
        _rota_cache[key] = alternatif_rotalar(A, B, gun, saat, profil)
    rotalar, meta = _rota_cache[key]
    meta = dict(meta, kosul=KOSUL["etiket"], uyarilar=list(KOSUL.get("uyarilar", [])))
    rotalar = list(rotalar)
    rotalar.sort(key=SIRALAMA.get(kriter, SIRALAMA["süre"]))
    baslik = f"🟢 **{A['label']}**  \n🔴 **{B['label']}**  \n{GUN_ADI[gun]} {saat:02d}:00 · kriter: {kriter} · {PROFILLER[profil]}  \n{KOSUL['etiket']}\n\n" + "".join(f"> {u}  \n" for u in KOSUL.get("uyarilar", []))
    if not rotalar:
        return [], baslik + "❌ Bu saatte yol bulunamadı.", [], [], meta
    wc_all = []
    for r in rotalar:
        r["wc"] = []
        if tuvalet:
            wc = yol_ustu_tuvaletler(r["legs"])
            r["wc"] = [{"ad": t["ad"].title(), "info": f"{yer} durağına {d:.0f} m · bakım odası: {t['bakim_odasi']}"} for d, t, yer in wc]
            wc_all += [(t, f"{yer} durağına {d:.0f} m") for d, t, yer in wc]
    satirlar = []
    for i, r in enumerate(rotalar):
        oz = r["oz"]
        parca = " › ".join(f"🚶{dk(L['min'])}" if L["type"] == "walk" else
                           f"{MODE_ICON.get(lines[L['line']]['mode'], '🚌')} {'/'.join(L.get('hatlar', [lines[L['line']]['short']])[:3])}"
                           for L in r["legs"])
        satirlar.append(f"{i + 1}. **{oz['total']:.0f} dk** · {parca} · 🚶 {oz['walk']:.0f} dk · ↗ {oz['climb']:.0f} m"
                        + (f" · ⚠ en dik %{oz['maxup']}" if oz["maxup"] >= DIK else "")
                        + (f" · _{', '.join(r['etiket'])}_" if r.get("etiket") else ""))
    metin = baslik + "\n".join(satirlar) + f"\n\n<sub>{meta['ms']:.0f} ms, {meta.get('arama', 0)} arama</sub>"
    wc_best = yol_ustu_tuvaletler(rotalar[0]["legs"]) if tuvalet else []
    return rotalar[0]["legs"], metin, wc_best, rotalar, meta

def rota(nereden, nereye, kriter="süre", gun=VARSAYILAN_GUN, saat=VARSAYILAN_SAAT, harita_goster=False, tuvalet=True,
         profil="normal", hava="oto"):
    """Kodla kullanım: rota("Kadıköy", "Taksim", "süre", "hi", 8). Yer adı (metin) ya da yer sözlüğü alır."""
    yerler = []
    for q in (nereden, nereye):
        if isinstance(q, dict):
            yerler.append(q); continue
        bulunan = yer_ara(q)
        if not bulunan:
            print(f"❌ '{q}' bulunamadı."); return None
        yerler.append(bulunan[0])
    legs, metin, wc, rotalar, meta = rota_hesapla(*yerler, kriter, gun, saat, tuvalet, profil, hava)
    print(re.sub(r"</?(sub|b|i)>|\*\*|(?<!\w)_|_(?!\w)", "", metin))
    if legs and harita_goster:
        from IPython.display import HTML, display
        display(HTML(iframe(rota_sayfasi(*yerler, rotalar, meta, gun, saat, profil))))
    return legs

import re
_ = rota("Kadıköy", "Taksim")

from datetime import date, datetime, timedelta, timezone

GUN_ADLARI = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]
AY_ADLARI = ["", "Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"]
BOLGELER = ["Fatih", "Balat", "Beyoğlu", "Beşiktaş", "Kadıköy", "Üsküdar"]
BOLGE_ACIKLAMA = {"Fatih": "Sultanahmet · Eminönü", "Balat": "Fener · Balat · Ayvansaray", "Beyoğlu": "Galata · İstiklal · Karaköy",
                  "Beşiktaş": "Dolmabahçe · Yıldız · Ortaköy", "Kadıköy": "Çarşı · Moda · Yeldeğirmeni",
                  "Üsküdar": "Kız Kulesi · Kuzguncuk · Çamlıca"}
TEMPO = {"sakin": 1.3, "normal": 1.0, "hızlı": 0.75}     # gezme süresi çarpanı
MUZEKART_KUYRUK = 0.5                                    # Müzekart'la gişe sırası atlanır: kuyruğun yarısı kalır
CUMA_ARASI = (12 * 60, 14 * 60 + 30)                     # Cuma namazı: camiler turist ziyaretine kapalı
LAMBDA = {"Önerilen plan": 1.0, "Daha rahat plan": 3.0}  # yol + bekleme dakikası başına ceza (skor puanı)
GEZI_MAKS_ADAY = 16
GECIS_KATSAYI = 0.6                                      # geçiş noktaları rotayı yönlendirmesin: puanın %60'ı
GIRIS_PAYI = 10                                          # her durakta giriş/çıkış, güvenlik, ayakkabı, fotoğraf payı (dk)
CADDE_UCLARI = {"Y02": ("Taksim", "Tünel"), "D03": ("Altıyol (Boğa)", "Moda yönü")}
GAMMA = 0.6                                              # yürürken çıkılan her metre yokuş için ceza (puan)
RHO = 12                                                 # insanların gezme sırasına ters düşen her çift için ceza (puan)
DONUS_SON = 22 * 60                                      # dönüşte varış saati "fark etmez" ise gün en geç burada biter

def gun_tipi(gun_idx):                                   # haftanın günü -> toplu taşıma tarifesi
    return "paz" if gun_idx == 6 else "cmt" if gun_idx == 5 else "hi"

def mevsim(t):
    return "kis" if t.month in (11, 12, 1, 2, 3) else "yaz"

def _dk(hhmm):
    h, m = map(int, hhmm.split(":"))
    return h * 60 + m

def _aralik(s):
    a, b = s.split("-")
    return _dk(a), _dk(b)

def saat_yaz(dk):
    dk = int(round(dk))
    return f"{dk // 60 % 24:02d}:{dk % 60:02d}"

def load_yerler(folder):
    out = []
    with open(f"{folder}/gezi_yerleri.csv", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            y = {"id": r["id"], "ad": r["ad"], "bolge": r["bolge"], "tur": r["tur"],
                 "lat": float(r["lat"]), "lon": float(r["lon"]),
                 "lat2": float(r["lat2"] or r["lat"]), "lon2": float(r["lon2"] or r["lon"]),
                 "sure": int(r["sure_dk"]), "kuyruk": int(r["kuyruk_dk"]), "muzekart": r["muzekart"] == "1",
                 "ucretli": r["ucretli"] == "1", "saat": {"yaz": _aralik(r["yaz"]), "kis": _aralik(r["kis"])},
                 "gise": int(r["gise_dk"]), "kapali": {int(g) for g in r["kapali_gun"].split(",") if g != ""},
                 "cuma": r["cuma_ogle"] == "1", "notlar": r["notlar"], "kaynak": r["kaynak"],
                 "ozel": {int(g): _aralik(s) for g, s in (p.split("=") for p in r["ozel"].split(";") if p)},
                 "sira": int(r["sira"])}
            for k in ("populerlik", "tarih", "manzara", "eglence", "kultur"):
                y[k] = int(r[k])
            y["skor"] = round((3 * y["populerlik"] ** 2 + 2 * (y["tarih"] + y["manzara"] + y["eglence"] + y["kultur"])
                               + 0.2 * y["sure"]) * (GECIS_KATSAYI if y["tur"] == "gecis" else 1))
            out.append(y)
    return out

YERLER = load_yerler(DATA_DIR)
YER_BY_ID = {y["id"]: y for y in YERLER}                 # hash tablosu
print(f"{len(YERLER)} gezi noktası:", ", ".join(f"{b} ({sum(y['bolge'] == b for y in YERLER)})" for b in BOLGELER))

def gun_saatleri(y, gun_idx, mev):
    """O gün için (açılış, kapanış, son giriş) ya da None (kapalı)."""
    if gun_idx in y["kapali"]:
        return None
    a, k = y["ozel"].get(gun_idx, y["saat"][mev])
    return a, k, k - y["gise"]

def _cadde_ustunde(y, caddeler, esik=60):
    """Geçiş noktası bir caddenin gerçek yürüme yolunun ≤ 60 m yakınında mı? (ör. Çiçek Pasajı İstiklal'de)"""
    for c in caddeler:
        yol = np.array(yol_bul(c["lat"], c["lon"], c["lat2"], c["lon2"])["coords"])
        if np.hypot((yol[:, 0] - y["lat"]) * KY, (yol[:, 1] - y["lon"]) * KX).min() <= esik:
            return True
    return False

def dugumler(yerler, gun_idx, mev, muzekart=False, tempo=1.0):
    """Algoritmanın göreceği düğümler. Cadde iki yönlü iki düğüm olur (aynı 'grup'). Kapalı yerler hiç girmez.
    Bir caddenin üstündeki geçiş noktası ayrı durak olmaz; caddeyi yürürken 'yol üstünde' görülür."""
    out = []
    caddeler = [y for y in yerler if y["tur"] == "cadde"]
    for y in yerler:
        if y["tur"] == "gecis" and _cadde_ustunde(y, caddeler):
            continue
        s = gun_saatleri(y, gun_idx, mev)
        if s is None:
            continue
        kuyruk = y["kuyruk"] * (MUZEKART_KUYRUK if muzekart and y["muzekart"] else 1.0)
        yonler = [((y["lat"], y["lon"]), (y["lat2"], y["lon2"]), "")]
        if y["tur"] == "cadde":
            yonler.append(((y["lat2"], y["lon2"]), (y["lat"], y["lon"]), "ters"))
        for giris, cikis, yon in yonler:
            z_in, z_out = float(yukseklik(*giris)), float(yukseklik(*cikis))
            out.append({"y": y, "grup": y["id"], "giris_ll": giris, "cikis_ll": cikis, "yon": yon,
                        "gin": (giris[1] * KX, giris[0] * KY), "gout": (cikis[1] * KX, cikis[0] * KY),
                        "z_in": z_in, "z_out": z_out, "ic_tirm": max(0.0, z_out - z_in), "cadde": y["tur"] == "cadde",
                        "sira": y["sira"],
                        "skor": y["skor"], "acilis": s[0], "kapanis": s[1], "son_giris": s[2],
                        "ara": CUMA_ARASI if (y["cuma"] and gun_idx == 4) else None,
                        "kuyruk": kuyruk,
                        "sure_top": kuyruk + y["sure"] * tempo + (GIRIS_PAYI if y["tur"] == "yer" else 0)})
    return out

def ziyaret(n, varis):
    """Düğüme `varis` dakikasında varınca (giriş, çıkış) ya da None. Erken varılırsa açılışı, Cuma namazında
    camide namazın bitmesini bekler; son girişten sonra ya da kapanışı aşacaksa gezilemez."""
    giris = max(varis, n["acilis"])
    if n["ara"] and giris < n["ara"][1] and giris + n["sure_top"] > n["ara"][0]:
        giris = n["ara"][1]
    if giris > n["son_giris"]:
        return None
    cikis = giris + n["sure_top"]
    if cikis > n["kapanis"]:
        return None
    return giris, cikis

def _kesisir(p1, p2, q1, q2):
    """İki doğru parçası birbirini kesiyor mu? (uç ortaksa kesişme sayılmaz)"""
    def yon(a, b, c):
        return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
    if min(math.dist(p1, q1), math.dist(p1, q2), math.dist(p2, q1), math.dist(p2, q2)) < 1:
        return False
    d1, d2, d3, d4 = yon(q1, q2, p1), yon(q1, q2, p2), yon(p1, p2, q1), yon(p1, p2, q2)
    return (d1 * d2 < 0) and (d3 * d4 < 0)

def adim(onceki, j, aday, yuru, parcalar, gidilen_siralar):
    """j'ye geçmenin ŞEKİL cezası ve yeni yürüyüş parçaları. Kesişme varsa None (o sıra yasak).
    ceza = γ × (yürürken çıkılan metre) + ρ × (insanların sırasına ters düşen önceki yer sayısı)"""
    a = aday[j]
    yeni, tirm = [], a.get("ic_tirm", 0.0)
    if onceki is not None and yuru is not None and yuru[onceki][j]:
        b = aday[onceki]
        tirm += max(0.0, a.get("z_in", 0) - b.get("z_out", 0))
        if "gout" in b:
            yeni.append((b["gout"], a["gin"]))
    if a.get("cadde") and "gin" in a:
        yeni.append((a["gin"], a["gout"]))
    for p in yeni:
        for q in parcalar:
            if _kesisir(p[0], p[1], q[0], q[1]):
                return None
    ters = sum(1 for r in gidilen_siralar if r > a.get("sira", 0))
    return GAMMA * tirm + RHO * ters, yeni

def plan_simule(sira, aday, T, bas, don, t0, bitis, ceza=0.0, yuru=None):
    """Bir sırayı uygular. (değer, skor, yol+bekleme dk, çizelge) ya da None (sığmıyor / aynı yer iki kez / kesişiyor).
    Üç yöntem de (brute force, greedy, backtracking) aynı kuralla ölçülsün diye tek fonksiyon."""
    t, kayip, skor, sekil, cizelge, onceki, gruplar, parcalar, siralar = t0, 0.0, 0, 0.0, [], None, set(), [], []
    for j in sira:
        if aday[j]["grup"] in gruplar:
            return None
        gruplar.add(aday[j]["grup"])
        git = bas[j] if onceki is None else T[onceki][j]
        z = ziyaret(aday[j], t + git)
        if z is None:
            return None
        ad_ = adim(onceki, j, aday, yuru, parcalar, siralar)
        if ad_ is None:
            return None
        sekil += ad_[0]; parcalar += ad_[1]; siralar.append(aday[j].get("sira", 0))
        kayip += git + (z[0] - t - git); skor += aday[j]["skor"]
        cizelge.append((j, t + git, z[0], z[1]))
        t, onceki = z[1], j
    if don is not None and sira:
        kayip += don[onceki]; t += don[onceki]
    if t > bitis:
        return None
    return skor - ceza * kayip - sekil, skor, kayip, cizelge

def gezi_greedy(aday, T, bas, don, t0, bitis, ceza=0.0, yuru=None):
    """Greedy: her adımda skor / (yol + bekleme + gezme) oranı en iyi, hâlâ sığan ve rotayı kesmeyen yere git.
    Geri dönüş yok (bir kez seçilen yer bırakılmaz)."""
    sira, t, onceki, adim_sayisi, gruplar, parcalar, siralar = [], t0, None, 0, set(), [], []
    while True:
        en_iyi = None
        for j in range(len(aday)):
            if aday[j]["grup"] in gruplar:
                continue
            adim_sayisi += 1
            git = bas[j] if onceki is None else T[onceki][j]
            z = ziyaret(aday[j], t + git)
            if z is None or z[1] + (don[j] if don is not None else 0) > bitis:
                continue
            ad_ = adim(onceki, j, aday, yuru, parcalar, siralar)
            if ad_ is None:
                continue
            oran = aday[j]["skor"] / max(z[1] - t, 1)
            if en_iyi is None or oran > en_iyi[0]:
                en_iyi = (oran, j, z[1], ad_[1])
        if en_iyi is None:
            return sira, adim_sayisi
        _, j, t, yeni = en_iyi
        sira.append(j); gruplar.add(aday[j]["grup"]); onceki = j; parcalar += yeni; siralar.append(aday[j].get("sira", 0))

def gezi_backtracking(aday, T, bas, don, t0, bitis, ceza=0.0, yuru=None, dugum_siniri=2_000_000):
    """Backtracking + dal budama (branch & bound). Özyinelemeli: ara(...).
    • Budama: kalan sürede yerleri skor/maliyet oranına göre KESİRLİ doldurmak (kesirli knapsack = greedy) iyimser
      bir üst sınırdır (cezaları yok sayar); mevcut değer + üst sınır en iyiyi geçemiyorsa dal açılmaz.
    • Kesişme yasağı yüzünden geleceğe kalan seçenekler YOLUN TAMAMINA bağlıdır (sadece son yere değil);
      bu yüzden "(son yer, gezilen küme)" üzerinden memoization (DP) burada doğru olmaz, kullanılmaz."""
    n = len(aday)
    en_az_gelis = [min([bas[j]] + [T[i][j] for i in range(n) if i != j and aday[i]["grup"] != aday[j]["grup"]])
                   for j in range(n)]
    maliyet = [en_az_gelis[j] + aday[j]["sure_top"] for j in range(n)]
    oran_sirasi = sorted(range(n), key=lambda j: -aday[j]["skor"] / max(maliyet[j], 1))
    ikiz = [[i for i in range(n) if aday[i]["grup"] == aday[j]["grup"]] for j in range(n)]
    en_az_donus = min(don) if don is not None and n else 0
    en_iyi = {"deger": 0.0, "sira": []}
    sayac = {"dugum": 0, "budama": 0, "kesisme": 0}

    def ust_sinir(kalan_sure, kalan):
        toplam = 0.0
        for j in oran_sirasi:
            if j in kalan:
                if maliyet[j] <= kalan_sure:
                    toplam += aday[j]["skor"]; kalan_sure -= maliyet[j]
                else:
                    toplam += aday[j]["skor"] * max(kalan_sure, 0) / maliyet[j]
                    break
        return toplam

    def ara(onceki, t, sira, kalan, deger, parcalar, siralar):
        sayac["dugum"] += 1
        if sayac["dugum"] > dugum_siniri:
            return
        if sira and (don is None or t + don[onceki] <= bitis):     # plan burada bitebilir mi?
            son = deger - (ceza * don[onceki] if don is not None else 0)
            if son > en_iyi["deger"] + 1e-9:
                en_iyi.update(deger=son, sira=list(sira))
        if deger + ust_sinir(bitis - t - en_az_donus, kalan) <= en_iyi["deger"] + 1e-9:
            sayac["budama"] += 1                         # bu daldan daha iyisi çıkamaz: geri dön
            return
        for j in oran_sirasi:                            # umut verici yerler önce: iyi çözüm erken bulunur
            if j not in kalan:
                continue
            git = bas[j] if onceki is None else T[onceki][j]
            z = ziyaret(aday[j], t + git)
            if z is None or z[1] + en_az_donus > bitis:
                continue                                 # sığmıyor / kapalı
            ad_ = adim(onceki, j, aday, yuru, parcalar, siralar)
            if ad_ is None:
                sayac["kesisme"] += 1                    # rota kendini keserdi ("8" çizerdi): bu dalı açma
                continue
            cikan = [i for i in ikiz[j] if i in kalan]   # caddenin iki yönünden biri seçilince diğeri de düşer
            sira.append(j); kalan.difference_update(cikan); siralar.append(aday[j].get("sira", 0))
            ara(j, z[1], sira, kalan, deger + aday[j]["skor"] - ceza * (z[0] - t) - ad_[0], parcalar + ad_[1], siralar)
            sira.pop(); kalan.update(cikan); siralar.pop()   # geri al (backtrack)

    ara(None, t0, [], set(range(n)), 0.0, [], [])
    return en_iyi["sira"], sayac

def gezi_brute_force(aday, T, bas, don, t0, bitis, ceza=0.0, yuru=None):
    """Tüm alt kümelerin tüm sıraları (sadece küçük n için: doğrulama ve karşılaştırma)."""
    en_iyi, en_iyi_sira, sayi = 0.0, [], 0
    for k in range(1, len(aday) + 1):
        for sira in itertools.permutations(range(len(aday)), k):
            sayi += 1
            s = plan_simule(sira, aday, T, bas, don, t0, bitis, ceza, yuru)
            if s and s[0] > en_iyi + 1e-9:
                en_iyi, en_iyi_sira = s[0], list(sira)
    return en_iyi_sira, sayi

def permutasyon_sayisi(n):
    """Brute force'un deneyeceği sıra sayısı: Σ_{k=1..n} n!/(n-k)!"""
    toplam, p = 0, 1
    for k in range(1, n + 1):
        p *= n - k + 1; toplam += p
    return toplam

def tek_kaynak(adj, sources, walks, limit, hedefler=None):
    """Dijkstra'nın hedefsiz hâli: kaynaktan `limit` dk içindeki her durağa en kısa süre {durak: dk}.
    `hedefler` verilirse hepsine ulaşınca durur (gerisini aramak gereksiz)."""
    best, heap, cnt, done, out = {}, [], 0, set(), {}
    kalan = set(hedefler) if hedefler is not None else None
    for s, w in sources.items():
        st = (s, "walk" if w > 0 else "start")
        if w < best.get(st, 1e18):
            best[st] = w; heap.append((w, cnt, st)); cnt += 1
    heapq.heapify(heap)
    while heap:
        c, _, st = heapq.heappop(heap)
        if st in done:
            continue
        if c > limit:
            break
        done.add(st)
        node, last = st
        if isinstance(node, str) and last != "board" and node not in out:
            out[node] = c
            if kalan is not None:
                kalan.discard(node)
                if not kalan:
                    break
        edges = adj.get(node, ())
        if isinstance(node, str) and last != "walk":
            edges = itertools.chain(edges, walks.get(node, ()))
        for nxt, m, kind, _ in edges:
            if kind == "alight" and last == "board":
                continue
            ns, nc = (nxt, kind), c + m
            if nc < best.get(ns, 1e18):
                best[ns] = nc; heapq.heappush(heap, (nc, cnt, ns)); cnt += 1
    return out

def _nokta(ll, ad="nokta"):
    return {"label": ad, "name": ad, "lat": ll[0], "lon": ll[1], "stops": [], "access": None}

def gezi_matrisleri(A, aday, gun, saat, profil, B=None, yuruyus_esigi=20):
    """T[i][j]: i'nin ÇIKIŞINDAN j'nin GİRİŞİNE en kısa süre (yürüme ya da toplu taşıma); bas[j]: A'dan; don[i]: B'ye.
    Ayrıca caddelerin içindeki yürüyüş süresi (giriş → çıkış)."""
    n = len(aday)
    cik = [a["cikis_ll"] for a in aday]; gir = [a["giris_ll"] for a in aday]
    hepsi_ll = cik + gir
    xs = [lo * KX for _, lo in hepsi_ll]; ys = [la * KY for la, _ in hepsi_ll]
    A_, EID, sel, loc = _altgraf(min(xs) - 900, max(xs) + 900, min(ys) - 900, max(ys) + 900, profil)
    def dugum(ll):
        c = [(nd, d) for nd, d in yakin_dugumler(ll[0], ll[1], k=6, r=400) if loc[nd] >= 0]
        return (loc[c[0][0]], c[0][1] / WALK_M_PER_MIN) if c else (-1, 0.0)
    cd = [dugum(ll) for ll in cik]; gd = [dugum(ll) for ll in gir]
    INF = float("inf")
    T = [[0.0 if i == j else INF for j in range(n)] for i in range(n)]
    mod = [["yürü"] * n for _ in range(n)]
    ok = [i for i in range(n) if cd[i][0] >= 0]
    if ok:                                               # TEK scipy çağrısı: tüm çıkışlardan tüm girişlere yürüme
        dist = sp_dijkstra(A_, directed=True, indices=[cd[i][0] for i in ok], limit=90)
        for r, i in enumerate(ok):
            for j in range(n):
                if i != j and gd[j][0] >= 0 and np.isfinite(dist[r, gd[j][0]]):
                    T[i][j] = float(dist[r, gd[j][0]]) + cd[i][1] + gd[j][1]
    ic = [0.0] * n                                       # caddenin baştan sona yürünmesi (yokuşa göre)
    for j, a in enumerate(aday):
        if a["y"]["tur"] == "cadde":
            ic[j] = yol_bul(*a["giris_ll"], *a["cikis_ll"], profil)["tmin"]
    g_adj, _ = get_graph(gun, saat)
    walks = WALKS_P[profil]
    varis = [erisim(_nokta(ll), profil, "varis") for ll in gir]
    hedef_hepsi = {s for v in varis for s in v}
    for i in range(n):                                   # uzak çiftler için toplu taşıma (ör. Çamlıca)
        uzak = [j for j in range(n) if T[i][j] > yuruyus_esigi and haversine_m(*cik[i], *gir[j]) > 1500]
        if not uzak:
            continue
        d = tek_kaynak(g_adj, erisim(_nokta(cik[i]), profil, "cikis"), walks, limit=75,
                       hedefler={s for j in uzak for s in varis[j]})
        for j in uzak:
            t = min((d[s] + w for s, w in varis[j].items() if s in d), default=INF)
            if t + 3 < T[i][j]:
                T[i][j], mod[i][j] = t, "toplu"
    d = tek_kaynak(g_adj, erisim(A, profil, "cikis"), walks, limit=200, hedefler=hedef_hepsi)
    bas, bas_mod = [], []
    for j in range(n):
        t = min((d[s] + w for s, w in varis[j].items() if s in d), default=INF); m = "toplu"
        if haversine_m(A["lat"], A["lon"], *gir[j]) < 2500:
            yw = yol_bul(A["lat"], A["lon"], *gir[j], profil)
            if not yw["yedek"] and yw["tmin"] <= t + 3:
                t, m = yw["tmin"], "yürü"
        bas.append(t); bas_mod.append(m)
    don = don_mod = None
    if B is not None:
        h = alt_sinir(gun, saat, profil, erisim(B, profil, "varis"), 240)
        don, don_mod = [], []
        for i in range(n):
            t = min((w + h[s] for s, w in erisim(_nokta(cik[i]), profil, "cikis").items() if s in h), default=INF); m = "toplu"
            if haversine_m(B["lat"], B["lon"], *cik[i]) < 2500:
                yw = yol_bul(*cik[i], B["lat"], B["lon"], profil)
                if not yw["yedek"] and yw["tmin"] <= t + 3:
                    t, m = yw["tmin"], "yürü"
            don.append(t); don_mod.append(m)
    return T, mod, bas, bas_mod, don, don_mod, ic

def gezi_planla(A, bolge, tarih, bas_dk, bitis_dk, muzekart=False, tempo="normal", profil="normal", B=None):
    """İki plan: Önerilen (λ=1) ve Daha rahat (λ=3), ikisi de backtracking ile kesin en iyi.
    Karşılaştırma için greedy ve brute force sayıları da meta'da (arayüzde gösterilmez)."""
    t_bas = time.perf_counter()
    gun_idx, mev = tarih.weekday(), mevsim(tarih)
    gun, saat = gun_tipi(gun_idx), min(int(bas_dk // 60), 23)
    kosul_ayarla(gun, saat, "oto", tarih=tarih)          # o günün hava tahmini (yağmurda yürüme uzar)
    yerler = [y for y in YERLER if y["bolge"] == bolge]
    aday = dugumler(yerler, gun_idx, mev, muzekart, TEMPO[tempo])
    meta = {"kapali": [y["ad"] for y in yerler if gun_saatleri(y, gun_idx, mev) is None], "mevsim": mev, "aday": len(aday)}
    if len(aday) > GEZI_MAKS_ADAY:                       # çok aday varsa en yüksek skorlu k tanesi (Min-Heap)
        aday = heapq.nlargest(GEZI_MAKS_ADAY, aday, key=lambda a: a["skor"])
    if not aday or bitis_dk <= bas_dk:
        return [], meta
    T, mod, bas, bas_mod, don, don_mod, ic = gezi_matrisleri(A, aday, gun, saat, profil, B)
    for j, a in enumerate(aday):                         # cadde: içindeki yürüyüş de gezme süresine eklenir
        a["ic_yurume"] = ic[j]; a["sure_top"] += ic[j]
    meta["matris_ms"] = (time.perf_counter() - t_bas) * 1000
    yuru = [[mod[i][j] == "yürü" for j in range(len(aday))] for i in range(len(aday))]
    k = dict(aday=aday, T=T, bas=bas, don=don, t0=bas_dk, bitis=bitis_dk, yuru=yuru)
    planlar, gorulen = [], {}
    for ad_, lam in LAMBDA.items():
        t0 = time.perf_counter()
        sira, say = gezi_backtracking(**k, ceza=lam)
        meta[ad_] = {"sayac": say, "ms": (time.perf_counter() - t0) * 1000}
        sim = plan_simule(sira, **k, ceza=lam) if sira else None
        if not sim:
            continue
        key = tuple(aday[j]["grup"] + aday[j]["yon"] for j in sira)
        if key in gorulen:
            continue
        p = {"ad": ad_, "sira": sira, "skor": sim[1], "kayip": sim[2], "cizelge": sim[3], "aday": aday,
             "mod": mod, "bas_mod": bas_mod, "don_mod": don_mod, "T": T, "bas": bas, "don": don, "bolge": bolge}
        gorulen[key] = p; planlar.append(p)
    t0 = time.perf_counter(); g, adim_say = gezi_greedy(**k, ceza=1.0)
    meta["greedy"] = {"skor": (plan_simule(g, **k) or (0, 0))[1], "adim": adim_say, "ms": (time.perf_counter() - t0) * 1000}
    meta["brute"] = permutasyon_sayisi(len(aday))
    meta["ms"] = (time.perf_counter() - t_bas) * 1000
    return planlar, meta

def _yolculuk(P, Q, gun, saat, profil, mod):
    """İki nokta arası çizilecek bacaklar: yürüme (sokaktan) ya da toplu taşıma (Dijkstra + tarif)."""
    PSEUDO["__O__"] = {"name": P["name"], "lat": P["lat"], "lon": P["lon"]}
    PSEUDO["__D__"] = {"name": Q["name"], "lat": Q["lat"], "lon": Q["lon"]}
    def yuru():
        y = yol_bul(P["lat"], P["lon"], Q["lat"], Q["lon"], profil)
        return [{"type": "walk", "from": "__O__", "to": "__D__", "min": y["tmin"], "yol": y, "stops": ["__O__", "__D__"]}]
    if mod == "yürü":
        return yuru()
    g_adj, _ = get_graph(gun, saat)
    accA, accB = erisim(P, profil, "cikis"), erisim(Q, profil, "varis")
    cost, path, _ = dijkstra(g_adj, accA, accB, "time", WALKS_P[profil])
    if not path:
        return yuru()
    return zenginlestir(_origin_walk_fix(to_legs(path, {"access": accA}), P, accA), gun, saat, profil)

def _yol_ustu(coords, plan_gruplari, bolge, gorulen):
    """Yürüyüş yolunun ≤ 60 m yakınından geçilen, planda olmayan 'geçiş' noktaları (Kamondo, Hipodrom…)."""
    if len(coords) < 2:
        return []
    c = np.array(coords)
    out = []
    for y in YERLER:
        if y["bolge"] != bolge or y["tur"] != "gecis" or y["id"] in plan_gruplari or y["id"] in gorulen:
            continue
        d = np.hypot((c[:, 0] - y["lat"]) * KY, (c[:, 1] - y["lon"]) * KX).min()
        if d <= 60:
            out.append(y); gorulen.add(y["id"])
    return out

def gezi_json(p, A, B, tarih, profil):
    """Planı sayfa JSON'una çevirir; saatleri gerçek çizilen yolculuk süreleriyle yeniden hesaplar."""
    gun = gun_tipi(tarih.weekday())
    aday = p["aday"]
    plan_gruplari = {aday[j]["grup"] for j in p["sira"]}
    t = p["cizelge"][0][1] - p["bas"][p["sira"][0]]       # yola çıkış saati
    bas_saat = t
    legs_json, onceki_P, walk_m, climb, toplu, gorulen = [], A, 0, 0, 0, set()
    def bacak(P, Q, mod, t):
        legs = _yolculuk(P, Q, gun, min(int(t // 60), 23), profil, mod)
        r = _rota_json({"legs": legs, "oz": ozetle(legs)}, int(t // 60) % 24)
        sure = sum(L["min"] if L["type"] == "walk" else L["wait"] + L["ride"] for L in legs)
        return r, sure, sum(L["type"] == "ride" for L in legs)
    for no, j in enumerate(p["sira"], 1):
        a = aday[j]; y = a["y"]
        mod = p["bas_mod"][j] if no == 1 else p["mod"][p["sira"][no - 2]][j]
        r, sure, nt = bacak(onceki_P, _nokta(a["giris_ll"], y["ad"]), mod, t)
        for L in r["legs"]:
            legs_json.append(L)
            if L["t"] == "walk":
                for g in _yol_ustu(L["c"], plan_gruplari, p["bolge"], gorulen):
                    legs_json.append({"t": "pass", "ad": g["ad"], "lat": g["lat"], "lon": g["lon"]})
        walk_m += r["walk_m"]; climb += r["climb"]; toplu += nt
        z = ziyaret(a, t + sure) or (max(t + sure, a["acilis"]), t + sure + a["sure_top"])
        item = {"t": "visit", "no": no, "ad": y["ad"], "lat": a["giris_ll"][0], "lon": a["giris_ll"][1], "tur": y["tur"],
                "giris": saat_yaz(z[0]), "cikis": saat_yaz(z[1]), "bekle": round(z[0] - (t + sure)),
                "kuyruk": round(a["kuyruk"]), "sure": round(z[1] - z[0]), "mk": a["kuyruk"] < y["kuyruk"],
                "ucretli": y["ucretli"], "notlar": y["notlar"], "saat": f"{saat_yaz(a['acilis'])}–{saat_yaz(a['kapanis'])}"}
        if y["tur"] == "cadde":                          # caddenin kendisi: baştan sona yürüyüş
            yc = yol_bul(*a["giris_ll"], *a["cikis_ll"], profil)
            item["c"] = [[round(u, 6), round(v, 6)] for u, v in yc["coords"]]
            u1, u2 = CADDE_UCLARI.get(y["id"], ("baş", "son"))
            item["uc"] = f"{u2} → {u1}" if a["yon"] == "ters" else f"{u1} → {u2}"
            item["gec"] = [g["ad"] for g in _yol_ustu(item["c"], plan_gruplari, p["bolge"], gorulen)]
            walk_m += round(yc["len"]); climb += round(yc["climb"])
        legs_json.append(item)
        t, onceki_P = z[1], _nokta(a["cikis_ll"], y["ad"])
    if B is not None:
        r, sure, nt = bacak(onceki_P, B, p["don_mod"][p["sira"][-1]], t)
        legs_json += r["legs"]; walk_m += r["walk_m"]; climb += r["climb"]; toplu += nt; t += sure
    return {"legs": legs_json, "ad": p["ad"], "skor": p["skor"], "n": len(p["sira"]), "dep": saat_yaz(bas_saat),
            "arr": saat_yaz(t), "total": round(t - bas_saat), "walk_m": walk_m, "climb": climb, "toplu": toplu,
            "etiket": [], "transfers": 0, "walk": 0, "maxup": 0}

print("Gezi modu hazır.")

import gradio as gr
from datetime import datetime, timezone, timedelta

def _simdi():
    t = datetime.now(timezone(timedelta(hours=3)))           # İstanbul saati
    return ("paz" if t.weekday() == 6 else "cmt" if t.weekday() == 5 else "hi"), t.hour

_YER_KAYDI = {}                                          # gösterilen her seçenek: etiket -> yer (hash tablosu)

def _kaydet(yerler):
    for p in yerler:
        _YER_KAYDI[p["label"]] = p
    return yerler

def ara(q):
    """Yazdıkça çalışır: durak + adres önerileri, ilki seçili gelir. Seçenek değeri = etiketin kendisi:
    yavaş gelen bir arama sonucu başka bir aramanın listesiyle karışsa bile seçilen yer doğru bulunur."""
    yerler = _kaydet((yer_ara(q or "", canli=True) if (q or "").strip() else [])[:4])
    ch = [(p["label"], p["label"]) for p in yerler]
    msg = "" if yerler or not (q or "").strip() else "Sonuç yok — farklı yazmayı deneyin."
    return gr.update(choices=ch, value=ch[0][1] if ch else None, visible=bool(ch), info=msg or None), yerler

def _uyar_mi(txt, p):
    """Kutuda yazan metnin her kelimesi, yerin adındaki bir kelimenin başı mı?"""
    ad_kelimeleri = normalize(p["label"]).split()
    return all(any(k.startswith(w) for k in ad_kelimeleri) for w in normalize(txt).split())

def sec(val, yerler, txt=None):
    """Seçili etiketin yeri (önce bu listede, yoksa daha önce gösterilenlerde). Seçim kutudaki metinle uyuşmuyorsa
    (yavaş gelen bir arama sonucu araya girdiyse) yazılan metinle yeniden aranır."""
    p = None
    if val is not None:
        p = next((q for q in (yerler or []) if q["label"] == val), None) or _YER_KAYDI.get(val)
    if txt and txt.strip() and (p is None or (not p["label"].startswith("📍 Konumum") and not _uyar_mi(txt, p))):
        bulunan = _kaydet(yer_ara(txt)[:4])
        p = bulunan[0] if bulunan else p
    return p

def konumdan(latlon, yerler):
    try:
        lat, lon = map(float, latlon.split(","))
    except Exception:
        return gr.update(value="", placeholder="⚠ Konum alınamadı (tarayıcı izni gerekli)"), gr.update(), yerler
    P = {"label": "📍 Konumum", "name": "Konumum", "sub": f"{lat:.5f}, {lon:.5f}", "lat": lat, "lon": lon,
         "stops": [], "access": None}
    P["label"] = f"📍 Konumum — {lat:.4f}, {lon:.4f}"
    _kaydet([P])
    return "📍 Konumum", gr.update(choices=[(P["label"], P["label"])], value=P["label"], visible=True), [P]

def rota_ui(a_val, a_yerler, b_val, b_yerler, gun, saat, kriter, profil, tuvalet, a_txt=None, b_txt=None, hava="oto"):
    A, B = sec(a_val, a_yerler, a_txt), sec(b_val, b_yerler, b_txt)
    if A is None or B is None:
        return iframe(sayfa({"routes": []}, '<div class="empty">Nereden ve nereye için yazıp listeden bir yer seçin.</div>'))
    _, _, _, rotalar, meta = rota_hesapla(A, B, kriter, gun, int(saat), tuvalet, profil, hava)
    return iframe(rota_sayfasi(A, B, rotalar, meta, gun, int(saat), profil))

def degistir(a_txt, a_rd, a_yer, b_txt, b_rd, b_yer):
    ch = lambda Y: [(p["label"], p["label"]) for p in (Y or [])]
    return (b_txt, gr.update(choices=ch(b_yer), value=b_rd, visible=bool(b_yer)), b_yer,
            a_txt, gr.update(choices=ch(a_yer), value=a_rd, visible=bool(a_yer)), a_yer)

def yokus_ui(val, yerler, yaricap, txt=None):
    P = sec(val, yerler, txt)
    if P is None:
        return iframe(sayfa({"routes": []}, '<div class="empty">Bir yer arayıp seçin.</div>'))
    r = int(yaricap)
    lat0, lon0, lat1, lon1 = P["lat"] - r / KY, P["lon"] - r / KX, P["lat"] + r / KY, P["lon"] + r / KX
    eg = egim_katmani(lat0, lon0, lat1, lon1, min_g=0, maks=14000)
    # en dik sokaklar (ada göre)
    agg = {}
    for e in eg:
        if e["n"] and e["l"] >= 30:                     # ≥30 m parçanın ortalama eğimi: tek pikselin gürültüsüne dayanıklı
            a = agg.setdefault(e["n"], {"x": 0, "l": 0, "c": e["c"]})
            a["l"] += e["l"]
            if abs(e["g"]) > a["x"]:
                a["x"], a["c"] = abs(e["g"]), e["c"]
    top = sorted(agg.items(), key=lambda kv: -kv[1]["x"])[:12]
    z0 = float(yukseklik(P["lat"], P["lon"]))
    dagilim = np.histogram([e["x"] for e in eg], bins=[0, 5, 8, 10, 15, 101], weights=[e["l"] for e in eg])[0]
    tot = max(dagilim.sum(), 1)
    renk = ["#34a853", "#a3c644", "#fbbc04", "#f57c00", "#d93025"]
    adlar = ["düz <%5", "%5–8", "%8–10", "dik %10–15", "çok dik %15+"]
    bar = "".join(f'<div title="{adlar[i]}" style="flex:{dagilim[i] / tot:.4f};background:{renk[i]}"></div>' for i in range(5))
    legend = "".join(f'<span><i class="dot" style="background:{renk[i]}"></i>{adlar[i]} {dagilim[i] / tot:.0%}</span>' for i in range(5))
    liste = "".join(f'<div class="card" onclick="go({i})"><div class="row1"><span class="tm">{_e(n)}</span>'
                    f'<span class="dur" style="color:{egim_sinifi(a["x"])[1]}">%{a["x"]}</span></div>'
                    f'<div class="sub"><span>{egim_sinifi(a["x"])[0]}</span><span>{a["l"]} m</span></div></div>'
                    for i, (n, a) in enumerate(top))
    panel = (f'<div class="hdr"><div class="od"><b>⛰️ {_e(P["name"])}</b></div><div class="meta">Zemin yüksekliği ≈ {z0:.0f} m · '
             f'{r} m çevre · {len(eg):,} sokak parçası</div>'
             f'<div style="display:flex;height:10px;border-radius:5px;overflow:hidden;margin-top:10px">{bar}</div>'
             f'<div class="sub" style="margin-top:6px">{legend}</div></div>'
             f'<div class="meta" style="padding:10px 16px 0;color:var(--mut);font-size:12px">EN DİK SOKAKLAR</div>{liste}'
             f'<div class="foot">Eğim: Copernicus 30 m yükseklik modeli (binalar filtrelenmiş) + OpenStreetMap sokakları. '
             f'Kısa sokaklarda ±%2–3 hata olabilir.</div>')
    data = {"routes": [], "O": [P["lat"], P["lon"]], "On": P["name"], "egim": eg, "egimAcik": True,
            "fit": [[lat0, lon0], [lat1, lon1]], "top": [a["c"] for _, a in top]}
    doc = sayfa(data, panel).replace("if (D.onload) D.onload(map);",
                                     "window.go=function(i){const c=D.top[i];map.fitBounds(L.latLngBounds(c),{maxZoom:18,padding:[60,60]});"
                                     "const h=L.polyline(c,{color:'#1a73e8',weight:10,opacity:.5}).addTo(map);setTimeout(()=>map.removeLayer(h),2500)};")
    return iframe(doc)

def tuvalet_ui(val, yerler, aktif, bakim, ulasim, profil, txt=None):
    P = sec(val, yerler, txt)
    if P is None:
        return iframe(sayfa({"routes": []}, '<div class="empty">Bulunduğunuz yeri arayıp seçin.</div>'))
    bulunan = yakin_tuvaletler(P["lat"], P["lon"], n=8, sadece_aktif=aktif, bakim_odasi=bakim, sadece_ulasim=ulasim)
    PSEUDO["__O__"] = {"name": P["name"], "lat": P["lat"], "lon": P["lon"]}
    rotalar = []
    for d, t in bulunan:
        if d <= 2500:                                    # yürüme mesafesindekiler: sokaktan yol + yokuş
            y = yol_bul(P["lat"], P["lon"], t["lat"], t["lon"], profil)
            PSEUDO[f"__T{t['id']}"] = {"name": f"🚻 {t['ad'].title()}", "lat": t["lat"], "lon": t["lon"]}
            legs = [{"type": "walk", "from": "__O__", "to": f"__T{t['id']}", "min": y["tmin"], "yol": y}]
            r = {"legs": legs, "oz": ozetle(legs), "etiket": [], "t": t, "d": d}
            rotalar.append(r)
    rotalar.sort(key=lambda r: r["oz"]["total"])
    if rotalar:
        rotalar[0]["etiket"] = ["En yakın (yürüyerek)"]
    h = _simdi()[1]
    R = []
    for r in rotalar:
        j = _rota_json(r, h); t = r["t"]
        j["etiket"] = r["etiket"] + [t["ilce"].title(), "Bakım odası" if t["bakim_odasi"] == "Var" else "Bakım odası yok", t["hizmet_yeri"]]
        R.append(j)
    kartlar = "".join(_kart_html(j, i).replace(f'<span class="tm">{j["dep"]} – {j["arr"]}</span>',
                                               f'<span class="tm">🚻 <b>{_e(r["t"]["ad"].title())}</b></span>')
                      for i, (j, r) in enumerate(zip(R, rotalar)))
    uzak = [(d, t) for d, t in bulunan if d > 2500]
    if uzak:
        kartlar += '<div class="empty">Yürüme mesafesinin dışında: ' + ", ".join(f"{_e(t['ad'].title())} ({d / 1000:.1f} km)" for d, t in uzak) + \
                   " — 🧭 Rota sekmesinden toplu taşımayla gidebilirsiniz.</div>"
    if not bulunan:
        kartlar = '<div class="empty">Bu filtrelerle yakında tuvalet yok.</div>'
    panel = (f'<div class="hdr"><div class="od"><b>🚻 {_e(P["name"])} yakınındaki tuvaletler</b></div>'
             f'<div class="meta">{PROFILLER[profil]} yürüyüş · sokak ağı üzerinden</div></div>{kartlar}')
    data = {"routes": R, "O": [P["lat"], P["lon"]], "On": P["name"],
            "wc": [{"lat": t["lat"], "lon": t["lon"], "ad": t["ad"].title(), "info": f"{d:.0f} m · {t['durum']}"} for d, t in bulunan]}
    return iframe(sayfa(data, panel))


def _gezi_kart_html(r, i):
    """Sade plan kartı: saat · yer adı; aralarda tek satır yolculuk."""
    adimlar, yol_dk, yol_hat, yol_yuru, gec = [], 0.0, [], 0.0, []
    def yol_bitir():
        nonlocal yol_dk, yol_hat, yol_yuru, gec
        if yol_dk >= 0.5:
            if yol_hat:
                metin = " › ".join(dict.fromkeys(yol_hat)) + f' · {dk(yol_dk)} dk'
            else:
                metin = f'🚶 {dk(yol_dk)} dk yürüyüş'
            if gec:
                metin += f'<br><span class="gec">yol üstünde: {_e(", ".join(gec))}</span>'
            adimlar.append(f'<div class="yolk">{metin}</div>')
        yol_dk, yol_hat, yol_yuru, gec = 0.0, [], 0.0, []
    for l in r["legs"]:
        if l["t"] == "walk":
            yol_dk += l["min"]
        elif l["t"] == "ride":
            yol_dk += l["wait"] + l["ride"]
            yol_hat.append(f'<span class="chip" style="background:{l["color"]}">{l["ic"]} {_e(l["short"])}</span>')
        elif l["t"] == "pass":
            gec.append(l["ad"])
        else:
            yol_bitir()
            alt = f'{l["sure"]} dk'
            if l["tur"] == "cadde":
                alt += f' · {_e(l["uc"])} yürüyerek' + (f' · {_e(", ".join(l["gec"]))}' if l.get("gec") else "")
            if l["mk"]:
                alt += ' · Müzekart'
            adimlar.append(f'<div class="vis"><span class="no">{l["no"]}</span><span class="ad">{_e(l["ad"])}</span>'
                           f'<span class="zaman">{l["giris"]}</span><div class="mu">{alt}</div></div>')
    yol_bitir()
    sa, dk_ = divmod(r["total"], 60)
    ozet = f'{r["n"]} yer · {r["walk_m"] / 1000:.1f} km yürüyüş'.replace(".", ",")
    return (f'<div class="card{" open" if i == 0 else ""}" data-i="{i}"><div class="row1">'
            f'<span class="tm"><b>{_e(r["ad"])}</b></span><span class="dur">{r["dep"]}–{r["arr"]}</span></div>'
            f'<div class="sub"><span>{ozet}</span></div>'
            f'<button class="adim">Plan</button><div class="steps">{"".join(adimlar)}</div></div>')

def tarih_yaz(t):
    return f"{t.day} {AY_ADLARI[t.month]} {GUN_ADLARI[t.weekday()]}"

def gezi_sayfasi(A, B, planlar, meta, bolge, tarih, bas_dk, bitis_dk, profil):
    R = []
    for p in planlar:
        j = gezi_json(p, A, B, tarih, profil)
        j["lbl"] = "Önerilen" if p["ad"].startswith("Öner") else "Rahat"
        R.append(j)
    son = f" · dönüş: {_e(B['name'])}" if B else ""
    hdr = (f'<div class="hdr"><div class="od"><b>{_e(bolge)}</b></div>'
           f'<div class="meta">{tarih_yaz(tarih)} · {_e(A["name"])}\'dan {saat_yaz(bas_dk)}{son}</div>'
           + (f'<div class="meta">Bugün kapalı: {_e(", ".join(meta["kapali"]))}</div>' if meta.get("kapali") else "") + '</div>')
    if R:
        body = "".join(_gezi_kart_html(r, i) for i, r in enumerate(R))
    else:
        body = ('<div class="empty">Bu zaman aralığında gezilebilecek yer çıkmadı. Daha erken başlamayı ya da süreyi '
                'uzatmayı deneyin.</div>')
    foot = '<div class="foot">Saatler Kasım 2026 itibarıyla derlendi; gitmeden önce kontrol edin.</div>' 
    data = {"routes": R, "O": [A["lat"], A["lon"]], "On": A["name"]}
    if B:
        data.update(D=[B["lat"], B["lon"]], Dn=B["name"])
    return sayfa(data, hdr + body + foot)

def gezi_ui(g_val, g_yerler, bolge, tarih_s, bas_dk, sure, donus, d_val, d_yerler, varis_dk, muzekart, tempo, profil,
            g_txt=None, d_txt=None):
    A = sec(g_val, g_yerler, g_txt)
    B = sec(d_val, d_yerler, d_txt) if donus else None
    if A is None or not bolge or (donus and B is None):
        return iframe(sayfa({"routes": []}, '<div class="empty">Nereden çıkacağınızı ve gezmek istediğiniz bölgeyi seçin'
                                            + (', dönüş yerini de seçin' if donus else '') + '.</div>'))
    tarih = date.fromisoformat(tarih_s)
    if donus:                                            # dönüşte süre sorulmaz: gün yerler kapanınca biter
        bitis = DONUS_SON if int(varis_dk) < 0 else int(varis_dk)
    else:
        bitis = int(bas_dk) + float(sure) * 60
    if bitis <= int(bas_dk) + 30:
        return iframe(sayfa({"routes": []}, '<div class="empty">Varış saati çıkış saatinden en az yarım saat sonra olmalı.</div>'))
    planlar, meta = gezi_planla(A, bolge, tarih, int(bas_dk), bitis, bool(muzekart), tempo, profil, B)
    return iframe(gezi_sayfasi(A, B, planlar, meta, bolge, tarih, int(bas_dk), bitis, profil))

GUNLER = [("Hafta içi", "hi"), ("Cumartesi", "cmt"), ("Pazar", "paz")]
SAATLER = [(f"{h:02d}:00", h) for h in range(24)]
PROFIL_SECENEK = [("🚶 Normal", "normal"), ("⛰️ Dik yokuştan kaçın", "kacin"), ("♿ Engelsiz", "engel")]
KRITER_SECENEK = [("⏱ En hızlı", "süre"), ("🔁 Az aktarma", "aktarma"), ("🚶 Az yürüme", "yürüme"), ("⛰️ Az yokuş", "yokuş")]
ilk_a, ilk_b, ilk_g = _kaydet(yer_ara("Kadıköy")[:4]), _kaydet(yer_ara("Taksim")[:4]), _kaydet(yer_ara("Tuzla")[:4])
gun0, saat0 = _simdi()
_bugun = datetime.now(timezone(timedelta(hours=3))).date()
TARIHLER = [(tarih_yaz(_bugun + timedelta(days=i)) + (" (bugün)" if i == 0 else ""), (_bugun + timedelta(days=i)).isoformat())
            for i in range(14)]
BAS_SAATLER = [(f"{h:02d}:{m:02d}", h * 60 + m) for h in range(7, 21) for m in (0, 30)]
VARIS_SAATLER = [("Fark etmez", -1)] + [(f"{h:02d}:{m:02d}", h * 60 + m) for h in range(9, 24) for m in (0, 30)]

CSS = """
.gradio-container{max-width:1400px!important}
#baslik h1{font-size:19px;margin:2px 0 0;font-weight:650;letter-spacing:-.2px}
#baslik p{margin:2px 0 0;color:var(--body-text-color-subdued);font-size:13.5px}
.arama textarea,.arama input{font-size:16px!important}
.sonuclar{overflow:auto}
.sonuclar .wrap{display:flex!important;flex-direction:column!important;gap:0!important}
.sonuclar label{width:100%!important;border:0!important;border-radius:8px!important;padding:6px 8px!important;font-size:13.5px!important;justify-content:flex-start!important;background:transparent!important;box-shadow:none!important}
.sonuclar input[type=radio]{display:none!important}
.sonuclar label.selected,.sonuclar label.selected span{background:var(--color-accent-soft)!important;border-color:var(--color-accent)!important;color:var(--body-text-color)!important}
.sonuclar{max-height:170px!important}
.secim label.selected{background:var(--color-accent)!important;border-color:var(--color-accent)!important}
.secim label.selected span{color:#fff!important}
.degis button{min-width:44px!important;font-size:18px!important}
.bul{font-size:16px!important;min-height:48px!important}
.secim .wrap{gap:6px!important}.secim label{padding:7px 10px!important;border-radius:999px!important;font-size:13.5px!important}
footer{display:none!important}
@media (max-width:760px){.gradio-container{padding:6px!important}}
"""
KONUM_JS = """() => new Promise(res => { if(!navigator.geolocation){res(['']);return}
  navigator.geolocation.getCurrentPosition(p => res([p.coords.latitude + ',' + p.coords.longitude]), e => res(['']),
  {enableHighAccuracy:true, timeout:8000}); })"""

with gr.Blocks(title="Tanrı İstemezse") as demo:
    gr.Markdown("# Tanrı İstemezse", elem_id="baslik")
    with gr.Tab("🧭 Rota"):
        a_yer, b_yer = gr.State(ilk_a), gr.State(ilk_b)
        konum_tmp = gr.Textbox(visible=False)
        with gr.Row(equal_height=False):
            with gr.Column(scale=4, min_width=300):
                with gr.Row():
                    a_txt = gr.Textbox(label="Nereden", value="Kadıköy", placeholder="Durak, adres veya mekân…",
                                       elem_classes="arama", scale=8)
                    konum = gr.Button("📍", scale=1, min_width=44, elem_classes="degis")
                a_rd = gr.Radio([(p["label"], p["label"]) for p in ilk_a], value=ilk_a[0]["label"], show_label=False,
                                elem_classes="sonuclar", container=False)
                with gr.Row():
                    b_txt = gr.Textbox(label="Nereye", value="Taksim", placeholder="Durak, adres veya mekân…",
                                       elem_classes="arama", scale=8)
                    ters = gr.Button("⇅", scale=1, min_width=44, elem_classes="degis")
                b_rd = gr.Radio([(p["label"], p["label"]) for p in ilk_b], value=ilk_b[0]["label"], show_label=False,
                                elem_classes="sonuclar", container=False)
                with gr.Row():
                    gun = gr.Dropdown(GUNLER, value=gun0, label="Gün", min_width=120)
                    saat = gr.Dropdown(SAATLER, value=saat0, label="Saat", min_width=110)
                    hava = gr.Dropdown(HAVA_SECENEK, value="oto", label="Hava", min_width=150)
                with gr.Accordion("Tercihler", open=False):
                    profil = gr.Radio(PROFIL_SECENEK, value="normal", label="Yürüyüş", elem_classes="secim")
                    kriter = gr.Radio(KRITER_SECENEK, value="süre", label="Sırala", elem_classes="secim")
                    tuv = gr.Checkbox(value=True, label="Yol üstündeki tuvaletleri göster")
                bul = gr.Button("Rotaları göster", variant="primary", elem_classes="bul")
            with gr.Column(scale=9):
                sonuc = gr.HTML(elem_id="sonuc")
        a_txt.input(ara, a_txt, [a_rd, a_yer], trigger_mode="always_last", show_progress="hidden")
        b_txt.input(ara, b_txt, [b_rd, b_yer], trigger_mode="always_last", show_progress="hidden")
        a_txt.submit(ara, a_txt, [a_rd, a_yer])
        b_txt.submit(ara, b_txt, [b_rd, b_yer])
        ters.click(degistir, [a_txt, a_rd, a_yer, b_txt, b_rd, b_yer], [a_txt, a_rd, a_yer, b_txt, b_rd, b_yer])
        konum.click(None, None, konum_tmp, js=KONUM_JS)
        konum_tmp.change(konumdan, [konum_tmp, a_yer], [a_txt, a_rd, a_yer])
        girdiler = [a_rd, a_yer, b_rd, b_yer, gun, saat, kriter, profil, tuv, a_txt, b_txt, hava]
        bul.click(rota_ui, girdiler, sonuc).then(None, js="() => document.getElementById('sonuc')?.scrollIntoView({behavior:'smooth', block:'start'})")
        for c in (kriter, profil, hava):
            c.change(rota_ui, girdiler, sonuc)
        demo.load(rota_ui, girdiler, sonuc)
    with gr.Tab("⛰️ Yokuş haritası"):
        y_yer = gr.State(ilk_b)
        with gr.Row(equal_height=False):
            with gr.Column(scale=4, min_width=300):
                y_txt = gr.Textbox(label="Nerenin yokuşlarına bakalım?", value="Taksim", placeholder="Semt, sokak, durak…",
                                   elem_classes="arama")
                y_rd = gr.Radio([(p["label"], p["label"]) for p in ilk_b], value=ilk_b[0]["label"], show_label=False,
                                elem_classes="sonuclar", container=False)
                y_r = gr.Slider(400, 2000, value=900, step=100, label="Çevre (m)")
                y_bul = gr.Button("Eğim haritasını göster", variant="primary", elem_classes="bul")
            with gr.Column(scale=9):
                y_out = gr.HTML()
        y_txt.input(ara, y_txt, [y_rd, y_yer], trigger_mode="always_last", show_progress="hidden")
        y_txt.submit(ara, y_txt, [y_rd, y_yer])
        y_bul.click(yokus_ui, [y_rd, y_yer, y_r, y_txt], y_out)
        y_rd.change(yokus_ui, [y_rd, y_yer, y_r, y_txt], y_out)
    with gr.Tab("🚻 Tuvalet"):
        t_yer = gr.State(ilk_a)
        with gr.Row(equal_height=False):
            with gr.Column(scale=4, min_width=300):
                t_txt = gr.Textbox(label="Neredesiniz?", value="Kadıköy", placeholder="Durak, adres veya mekân…",
                                   elem_classes="arama")
                t_rd = gr.Radio([(p["label"], p["label"]) for p in ilk_a], value=ilk_a[0]["label"], show_label=False,
                                elem_classes="sonuclar", container=False)
                with gr.Row():
                    aktif = gr.Checkbox(value=True, label="Sadece aktif")
                    bakim = gr.Checkbox(value=False, label="Bakım odası")
                    ulasim = gr.Checkbox(value=False, label="İstasyonda")
                t_profil = gr.Radio(PROFIL_SECENEK, value="normal", label="Yürüyüş", elem_classes="secim")
                t_bul = gr.Button("En yakın tuvaletler", variant="primary", elem_classes="bul")
            with gr.Column(scale=9):
                t_out = gr.HTML()
        t_txt.input(ara, t_txt, [t_rd, t_yer], trigger_mode="always_last", show_progress="hidden")
        t_txt.submit(ara, t_txt, [t_rd, t_yer])
        t_bul.click(tuvalet_ui, [t_rd, t_yer, aktif, bakim, ulasim, t_profil, t_txt], t_out)
    with gr.Tab("🧳 Gezi") as gezi_tab:
        g_yer, d_yer = gr.State(ilk_g), gr.State(ilk_b)
        with gr.Row(equal_height=False):
            with gr.Column(scale=4, min_width=300):
                g_txt = gr.Textbox(label="Nereden çıkacaksınız?", value="Tuzla", placeholder="Durak, adres veya mekân…",
                                   elem_classes="arama")
                g_rd = gr.Radio([(p["label"], p["label"]) for p in ilk_g], value=ilk_g[0]["label"], show_label=False,
                                elem_classes="sonuclar", container=False)
                bolge = gr.Radio([(f"{b}", b) for b in BOLGELER], value="Beyoğlu", label="Bölge",
                                 elem_classes="secim")
                with gr.Row():
                    g_tarih = gr.Dropdown(TARIHLER, value=TARIHLER[0][1], label="Gün", scale=3, min_width=200)
                    g_bas = gr.Dropdown(BAS_SAATLER, value=9 * 60, label="Çıkış saati", scale=2, min_width=110)
                g_donus = gr.Checkbox(value=False, label="Gezi bitince bir yere döneceğim")
                with gr.Column(visible=True) as sure_kutu:
                    g_sure = gr.Slider(2, 12, value=5, step=0.5, label="Kaç saatiniz var?")
                with gr.Column(visible=False) as donus_kutu:
                    d_txt = gr.Textbox(label="Nereye?", value="Taksim", placeholder="Durak, adres veya mekân…",
                                       elem_classes="arama")
                    d_rd = gr.Radio([(p["label"], p["label"]) for p in ilk_b], value=ilk_b[0]["label"], show_label=False,
                                    elem_classes="sonuclar", container=False)
                    d_varis = gr.Dropdown(VARIS_SAATLER, value=-1, label="En geç varış (isteğe bağlı)")
                with gr.Accordion("Tercihler", open=False):
                    g_mk = gr.Checkbox(value=False, label="Müzekart'ım var")
                    g_tempo = gr.Radio([("Sakin", "sakin"), ("Normal", "normal"), ("Hızlı", "hızlı")], value="normal",
                                       label="Gezi temposu", elem_classes="secim")
                    g_profil = gr.Radio(PROFIL_SECENEK, value="normal", label="Yürüyüş", elem_classes="secim")
                g_bul = gr.Button("Gezi planı yap", variant="primary", elem_classes="bul")
            with gr.Column(scale=9):
                g_out = gr.HTML(elem_id="gezi_sonuc")
        g_txt.input(ara, g_txt, [g_rd, g_yer], trigger_mode="always_last", show_progress="hidden")
        g_txt.submit(ara, g_txt, [g_rd, g_yer])
        d_txt.input(ara, d_txt, [d_rd, d_yer], trigger_mode="always_last", show_progress="hidden")
        d_txt.submit(ara, d_txt, [d_rd, d_yer])
        g_donus.change(lambda v: (gr.update(visible=not v), gr.update(visible=v)), g_donus, [sure_kutu, donus_kutu])
        gezi_girdi = [g_rd, g_yer, bolge, g_tarih, g_bas, g_sure, g_donus, d_rd, d_yer, d_varis, g_mk, g_tempo, g_profil,
                      g_txt, d_txt]
        gezi_tab.select(gezi_ui, gezi_girdi, g_out)     # sekme açılınca varsayılan plan hemen gelsin
        g_bul.click(gezi_ui, gezi_girdi, g_out).then(None, js="() => document.getElementById('gezi_sonuc')?.scrollIntoView({behavior:'smooth', block:'start'})")

TEMA = gr.themes.Default(primary_hue="blue", neutral_hue="gray", radius_size="md",
                         font=[gr.themes.GoogleFont("Inter"), "system-ui", "sans-serif"]).set(
    body_background_fill="#f7f7f8", body_background_fill_dark="#141416",
    block_background_fill="#ffffff", block_background_fill_dark="#1c1c1e",
    block_border_width="0px", block_shadow="0 1px 2px rgba(0,0,0,.06)", block_shadow_dark="none",
    block_label_background_fill="transparent", block_label_background_fill_dark="transparent",
    block_title_background_fill="transparent", block_title_background_fill_dark="transparent",
    block_label_text_color="#5f6368", block_label_text_color_dark="#a1a1a6",
    block_title_text_color="#3c4043", block_title_text_color_dark="#c7c7cc",
    input_background_fill="#f7f7f8", input_background_fill_dark="#242426",
    border_color_primary="#e5e5e5", border_color_primary_dark="#2f2f33")
if __name__ == "__main__" and os.environ.get("ROTA_NO_LAUNCH") != "1":
    try:
        import google.colab  # noqa: F401
        _colab = True
    except ImportError:
        _colab = False
    demo.launch(share=_colab, theme=TEMA, css=CSS)
