"""İstanbul sokak eğimleri ve yokuşa duyarlı yürüme ağı.

Girdi : streets.parquet (Overture Maps / OSM yol segmentleri), dem/*.tif (Copernicus GLO-30, 1")
Çıktı : out/dem.npz      İstanbul yükseklik ızgarası (bina/ağaç etkisi morfolojik açma ile azaltılmış)
        out/sokak.npz    yürünebilir sokak ağı (düğüm, yönlü kenar, eğim, geometri)
        out/yurume.npz   durak->durak yürüme bağlantıları, 3 profil (normal / dik yokuştan kaçın / engelsiz)
"""
import csv, math, os, sys, time
import numpy as np
import pyarrow.parquet as pq
import shapely, tifffile
from scipy import ndimage, sparse
from scipy.sparse.csgraph import dijkstra
from scipy.spatial import cKDTree

T0 = time.time()
def log(*a):
    print(f"[{time.time() - T0:6.0f}s]", *a, flush=True)

DATA = sys.argv[1] if len(sys.argv) > 1 else "../data"
os.makedirs("out", exist_ok=True)
W, S, E, N = 27.95, 40.75, 29.92, 41.52           # çalışma kutusu
LAT0 = 41.0
KX, KY = 111_320 * math.cos(math.radians(LAT0)), 110_950   # derece -> metre (yerel)

# ---------------------------------------------------------------- 1) DEM
R = 3600
mos = np.zeros((2 * R, 3 * R), np.float32)          # lat 40..42, lon 27..30 ; satır 0 = 42°K
for lat in (40, 41):
    for lon in (27, 28, 29):
        n = f"Copernicus_DSM_COG_10_N{lat}_00_E0{lon}_00_DEM"
        a = tifffile.imread(f"dem/{n}.tif")
        assert a.shape == (R, R), a.shape
        r0 = (41 - lat) * R; c0 = (lon - 27) * R
        mos[r0:r0 + R, c0:c0 + R] = a
r0, r1 = int((42 - N) * R), int(math.ceil((42 - S) * R))
c0, c1 = int((W - 27) * R), int(math.ceil((E - 27) * R))
dsm = np.clip(mos[r0:r1, c0:c1], 0, None)
del mos
TOP, LEFT, RES = 42 - r0 / R, 27 + c0 / R, 1 / R
log("DSM", dsm.shape)
# Copernicus bir yüzey modelidir (bina + ağaç dahil). Sokak eğimi için zemine yaklaştır:
# gri morfolojik açma (~150 m pencere) dar yükseltileri (binaları) siler, Gauss ile yumuşatılır.
dtm = ndimage.grey_opening(dsm, size=(5, 7))
dtm = ndimage.gaussian_filter(dtm, sigma=1.0).astype(np.float32)
log("DTM hazır")

def elev(lat, lon):
    """Bilineer örnekleme (dizi girişli)"""
    fr = (TOP - lat) / RES - 0.5
    fc = (lon - LEFT) / RES - 0.5
    i = np.clip(np.floor(fr).astype(np.int64), 0, dtm.shape[0] - 2)
    j = np.clip(np.floor(fc).astype(np.int64), 0, dtm.shape[1] - 2)
    di = np.clip(fr - i, 0, 1); dj = np.clip(fc - j, 0, 1)
    z00 = dtm[i, j]; z01 = dtm[i, j + 1]; z10 = dtm[i + 1, j]; z11 = dtm[i + 1, j + 1]
    return (z00 * (1 - di) * (1 - dj) + z01 * (1 - di) * dj + z10 * di * (1 - dj) + z11 * di * dj)

# uygulamaya giden DEM: 2" (~60x47 m), desimetre int16
h2 = dtm[: dtm.shape[0] // 2 * 2, : dtm.shape[1] // 2 * 2]
h2 = h2.reshape(h2.shape[0] // 2, 2, h2.shape[1] // 2, 2).mean(axis=(1, 3))
np.savez_compressed("out/dem.npz", z_dm=np.round(h2 * 10).astype(np.int16),
                    top=TOP, left=LEFT, res=2 * RES)
for ad, la, lo in [("Taksim Meydanı", 41.0369, 28.9850), ("Karaköy", 41.0225, 28.9770),
                   ("Çamlıca Tepesi", 41.0273, 29.0687), ("Kadıköy iskele", 40.9925, 29.0236),
                   ("Cihangir", 41.0318, 28.9830)]:
    print(f"   {ad:<16} DSM {dsm[int((TOP - la) / RES), int((lo - LEFT) / RES)]:6.1f} m   zemin {float(elev(np.array(la), np.array(lo))):6.1f} m")

# ---------------------------------------------------------------- 2) Sokaklar
t = pq.read_table("streets.parquet")
cls = np.array(t.column("class").to_pylist(), dtype=object)
sub = np.array(t.column("subclass").to_pylist(), dtype=object)
flags = t.column("road_flags").to_pylist()
conns = t.column("connectors").to_pylist()
names = t.column("name").to_pylist()
geoms = shapely.from_wkb(t.column("geometry").to_numpy(zero_copy_only=False))
log("segment", len(cls))

HARIC = {"motorway"}
keep = np.ones(len(cls), bool)
for k in range(len(cls)):
    c = cls[k]
    if c in HARIC or (c == "trunk" and sub[k] == "link"):
        keep[k] = False
    elif flags[k] and any(("is_under_construction" in f["values"] or "is_abandoned" in f["values"])
                          and f["between"] is None for f in flags[k]):
        keep[k] = False
CLASS_FACTOR = {"trunk": 1.4, "primary": 1.1, "steps": 1.0}

name_ids, name_list = {}, [""]
node_id, node_ll = {}, []
e_u, e_v, e_seg, e_g = [], [], [], []        # kenar: düğüm u, v; geometri indeksi
g_ptr, g_xy = [0], []                         # geometri (lon, lat) dizileri
g_bridge, g_steps, g_factor, g_name = [], [], [], []

def nid(cid, lon, lat):
    i = node_id.get(cid)
    if i is None:
        i = node_id[cid] = len(node_ll)
        node_ll.append((lat, lon))
    return i

for k in np.nonzero(keep)[0]:
    g = geoms[k]
    if g is None or g.is_empty:
        continue
    xy = shapely.get_coordinates(g)
    if len(xy) < 2:
        continue
    d = np.r_[0, np.cumsum(np.hypot(np.diff(xy[:, 0]) * KX, np.diff(xy[:, 1]) * KY))]
    L = d[-1]
    if L <= 0:
        continue
    cs = sorted((c["at"], c["connector_id"]) for c in (conns[k] or []))
    if not cs or cs[0][0] > 1e-6:
        cs = [(0.0, f"s{k}a")] + cs
    if cs[-1][0] < 1 - 1e-6:
        cs = cs + [(1.0, f"s{k}b")]
    fl = flags[k] or []
    nm = names[k] or ""
    if nm not in name_ids:
        name_ids[nm] = len(name_list); name_list.append(nm)
    for (a0, ca), (a1, cb) in zip(cs, cs[1:]):
        if a1 - a0 < 1e-9:
            continue
        s0, s1 = a0 * L, a1 * L
        inner = (d > s0) & (d < s1)
        px = np.r_[np.interp(s0, d, xy[:, 0]), xy[inner, 0], np.interp(s1, d, xy[:, 0])]
        py = np.r_[np.interp(s0, d, xy[:, 1]), xy[inner, 1], np.interp(s1, d, xy[:, 1])]
        u = nid(ca, px[0], py[0]); v = nid(cb, px[-1], py[-1])
        if u == v:
            continue
        mid = (a0 + a1) / 2
        br = any(f["between"] is None or f["between"][0] - 1e-6 <= mid <= f["between"][1] + 1e-6
                 for f in fl if ("is_bridge" in f["values"] or "is_tunnel" in f["values"]))
        e_u.append(u); e_v.append(v); e_g.append(len(g_ptr) - 1)
        g_xy.append(np.c_[px, py]); g_ptr.append(g_ptr[-1] + len(px))
        g_bridge.append(br); g_steps.append(cls[k] == "steps")
        g_factor.append(CLASS_FACTOR.get(cls[k], 1.0)); g_name.append(name_ids[nm])

g_xy = np.concatenate(g_xy).astype(np.float64)
g_ptr = np.array(g_ptr, np.int64)
node_ll = np.array(node_ll)
NE, NN = len(e_u), len(node_ll)
log(f"{NN:,} düğüm, {NE:,} kenar, {len(g_xy):,} nokta")

# ---------------------------------------------------------------- 3) Eğim: ~25 m'lik parçalar
seg_len = np.hypot(np.diff(g_xy[:, 0]) * KX, np.diff(g_xy[:, 1]) * KY)
seg_len[g_ptr[1:-1] - 1] = 0                            # geometri sınırlarını kes
cum = np.r_[0, np.cumsum(seg_len)]
start = cum[g_ptr[:-1]]
elen = cum[g_ptr[1:] - 1] - start                       # kenar uzunluğu (m)
npc = np.maximum(1, np.round(elen / 25).astype(np.int64))   # parça sayısı
ps = np.r_[0, np.cumsum(npc + 1)]                          # her kenarın örnek noktası başlangıcı
edge_of = np.repeat(np.arange(NE), npc + 1)
frac = np.arange(ps[-1]) - ps[edge_of]
sd = start[edge_of] + elen[edge_of] * frac / npc[edge_of]   # global kümülatif mesafe
sx = np.interp(sd, cum, g_xy[:, 0]); sy = np.interp(sd, cum, g_xy[:, 1])
# kümülatif mesafede sınır noktaları çakışabilir; her kenarın uç noktalarını tam geometriye sabitle
sx[ps[:-1]] = g_xy[g_ptr[:-1], 0]; sy[ps[:-1]] = g_xy[g_ptr[:-1], 1]
sx[ps[1:] - 1] = g_xy[g_ptr[1:] - 1, 0]; sy[ps[1:] - 1] = g_xy[g_ptr[1:] - 1, 1]
z = elev(sy, sx)
br = np.array(g_bridge)
if br.any():                                             # köprü/tünel: uçlar arası doğrusal
    zb0, zb1 = z[ps[:-1]], z[ps[1:] - 1]
    lin = zb0[edge_of] + (zb1 - zb0)[edge_of] * frac / npc[edge_of]
    z = np.where(br[edge_of], lin, z)
log("yükseklik örneklendi", len(z))

# parçalar (her kenarın ardışık örnekleri)
is_piece = np.ones(len(z) - 1, bool); is_piece[ps[1:-1] - 1] = False
pe = edge_of[:-1][is_piece]
dz = np.diff(z)[is_piece]
dl = np.repeat(elen / npc, npc)                          # parça uzunluğu
assert len(dl) == len(dz) == len(pe)
s = np.clip(dz / np.maximum(dl, 1e-6), -0.6, 0.6)
STEPS = np.array(g_steps); FACT = np.array(g_factor)

V0 = 75.0                                                 # düz yolda m/dk (≈4,5 km/sa)
def tobler(sl):                                           # Tobler yürüyüş fonksiyonu, düzde V0
    return V0 * np.exp(-3.5 * np.abs(sl + 0.05)) / math.exp(-3.5 * 0.05)

def kacin_carpan(sl):                                     # "dik yokuştan kaçın" ek maliyeti
    up = np.clip(sl - 0.07, 0, None)
    dn = np.clip(-sl - 0.12, 0, None)
    return 1 + 14 * up + 4 * dn                           # %15'lik yokuş ≈ 2,1x, %20 ≈ 2,8x

def topla(vals):
    return np.bincount(pe, weights=vals, minlength=NE)

out = {}
for yon, sg in (("f", s), ("b", -s)):
    t_norm = topla(dl / tobler(sg)) * FACT
    t_norm = np.where(STEPS, t_norm * 1.25, t_norm)
    c_kac = topla(dl / tobler(sg) * kacin_carpan(sg)) * FACT
    c_kac = np.where(STEPS, c_kac * 1.5, c_kac)
    climb = topla(np.clip(dz if yon == "f" else -dz, 0, None))
    mx = np.zeros(NE); np.maximum.at(mx, pe, np.where(dl >= 12, sg, 0))
    steep = np.zeros(NE); np.maximum.at(steep, pe, np.where(dl >= 12, np.abs(sg), 0))
    c_kac = np.where(mx > 0.18, np.inf, c_kac)             # %18'den dik yokuş çıkışı: bu yoldan yürüme iptal
    c_eng = np.where((steep > 0.08) | STEPS, np.inf, t_norm)
    out[yon] = (t_norm, c_kac, c_eng, climb, mx)
grade_avg = (z[ps[1:] - 1] - z[ps[:-1]]) / np.maximum(elen, 1)
grade_max = np.zeros(NE); np.maximum.at(grade_max, pe, np.where(dl >= 12, np.abs(s), 0))
log("eğimler hesaplandı;", f"%8 üstü kenar: {(grade_max > .08).mean():.1%}, %15 üstü: {(grade_max > .15).mean():.1%}")

# ---------------------------------------------------------------- 4) Yönlü ağ (CSR)
eu = np.array(e_u, np.int64); ev = np.array(e_v, np.int64)
U = np.r_[eu, ev]; V = np.r_[ev, eu]
GID = np.r_[np.arange(NE), -np.arange(NE) - 1]           # negatif = geometri ters yönde
cols = [np.r_[out["f"][i], out["b"][i]] for i in range(5)]
order = np.lexsort((V, U))
U, V, GID = U[order], V[order], GID[order]
T_N, C_K, C_E, CLIMB, MXUP = [c[order] for c in cols]
indptr = np.r_[0, np.cumsum(np.bincount(U, minlength=NN))]
log("yönlü kenar", len(U))

# durakları ağa bağla
stops = list(csv.DictReader(open(f"{DATA}/stops.csv", encoding="utf-8")))
sll = np.array([(float(r["lat"]), float(r["lon"])) for r in stops])
nxy = np.c_[node_ll[:, 1] * KX, node_ll[:, 0] * KY]
tree = cKDTree(nxy)
# sadece büyük bileşendeki düğümlere bağla (kopuk küçük parçalara değil)
G0 = sparse.csr_matrix((np.ones(len(U)), V, indptr), shape=(NN, NN))
ncomp, lab = sparse.csgraph.connected_components(G0, directed=False)
big = np.bincount(lab)
okn = big[lab] >= 200
tree_ok = cKDTree(nxy[okn]); okidx = np.nonzero(okn)[0]
d_snap, k_snap = tree_ok.query(np.c_[sll[:, 1] * KX, sll[:, 0] * KY])
stop_node = okidx[k_snap]
log(f"durak bağlama: medyan {np.median(d_snap):.0f} m, %95 {np.percentile(d_snap, 95):.0f} m, max {d_snap.max():.0f} m")

np.savez_compressed(
    "out/sokak.npz",
    node_lat=node_ll[:, 0].astype(np.float32), node_lon=node_ll[:, 1].astype(np.float32),
    indptr=indptr.astype(np.int32), to=V.astype(np.int32), gid=GID.astype(np.int32),
    t_norm=T_N.astype(np.float32), c_kacin=C_K.astype(np.float32), c_engel=C_E.astype(np.float32),
    climb=np.minimum(CLIMB * 10, 65535).astype(np.uint16), maxup=np.clip(np.round(MXUP * 100), 0, 127).astype(np.int8),
    g_ptr=g_ptr.astype(np.int32), g_lon=g_xy[:, 0].astype(np.float32), g_lat=g_xy[:, 1].astype(np.float32),
    g_len=elen.astype(np.float32), g_grade=np.clip(np.round(grade_avg * 100), -100, 100).astype(np.int8),
    g_gmax=np.clip(np.round(grade_max * 100), 0, 100).astype(np.uint8), g_name=np.array(g_name, np.int32),
    g_steps=STEPS, names=np.array(name_list, dtype=str),
    stop_ids=np.array([r["stop_id"] for r in stops], dtype=str),
    stop_node=stop_node.astype(np.int32), stop_snap=d_snap.astype(np.float32),
    )
log("sokak.npz yazıldı")

# ---------------------------------------------------------------- 5) Durak -> durak yürüme (3 profil)
LIMIT = {"normal": 25.0, "kacin": 30.0, "engel": 25.0}  # maliyet sınırı (dk)
WEIGHT = {"normal": T_N, "kacin": C_K, "engel": C_E}
snap_min = d_snap / V0
NS = len(stops)
cell = 2500.0
sxy = np.c_[sll[:, 1] * KX, sll[:, 0] * KY]
ckey = np.floor(sxy / cell).astype(np.int64)
groups = {}
for i, kk in enumerate(map(tuple, ckey)):
    groups.setdefault(kk, []).append(i)
# kenar arama: (u, v) -> yönlü kenar indeksi
ekey = U * NN + V
LEN_D = elen[np.where(GID < 0, -GID - 1, GID)]

res = {}
for prof in ("normal", "kacin", "engel"):
    w = WEIGHT[prof]
    fin = np.isfinite(w)
    rows = {"to": [], "cost": [], "tmin": [], "climb": [], "maxup": [], "len": []}
    ptr_lists = [[] for _ in range(NS)]
    for kk, members in groups.items():
        lo = (np.array(kk) * cell) - 2100; hi = (np.array(kk) + 1) * cell + 2100
        nsel = np.nonzero((nxy[:, 0] >= lo[0]) & (nxy[:, 0] <= hi[0]) & (nxy[:, 1] >= lo[1]) & (nxy[:, 1] <= hi[1]))[0]
        loc = -np.ones(NN, np.int64); loc[nsel] = np.arange(len(nsel))
        m = fin & (loc[U] >= 0) & (loc[V] >= 0)
        ru, rv, rw = loc[U[m]], loc[V[m]], w[m] + 1e-6
        o = np.lexsort((rw, rv, ru))                      # paralel kenarlar: en ucuzu kalsın (csr toplamasın)
        ru, rv, rw = ru[o], rv[o], rw[o]
        first = np.r_[True, (ru[1:] != ru[:-1]) | (rv[1:] != rv[:-1])]
        A = sparse.csr_matrix((rw[first], (ru[first], rv[first])), shape=(len(nsel), len(nsel)))
        # hedef duraklar: kutudaki duraklar
        tsel = np.nonzero((sxy[:, 0] >= lo[0]) & (sxy[:, 0] <= hi[0]) & (sxy[:, 1] >= lo[1]) & (sxy[:, 1] <= hi[1]) & (loc[stop_node] >= 0))[0]
        srcn = np.unique(loc[stop_node[members]])
        if (srcn < 0).any():
            srcn = srcn[srcn >= 0]
        dist, pred = dijkstra(A, directed=True, indices=srcn, limit=LIMIT[prof], return_predecessors=True)
        srow = {n: r for r, n in enumerate(srcn)}
        tl = loc[stop_node[tsel]]
        for r, n in enumerate(srcn):
            # bu kaynaktan ağaç boyunca gerçek süre, tırmanış, en dik yokuş (işaretçi sıçratma ile)
            reach = np.isfinite(dist[r])
            p = pred[r].astype(np.int64)
            par = np.where(p >= 0, p, np.arange(len(p)))
            gidx = np.full(len(p), -1, np.int64)
            has = p >= 0
            kq = nsel[par[has]] * NN + nsel[np.nonzero(has)[0]]
            pos = np.searchsorted(ekey, kq)
            # paralel kenarlar olabilir: aynı (u,v) için en ucuzu
            gidx[np.nonzero(has)[0]] = pos
            tt = np.where(has, T_N[np.maximum(gidx, 0)], 0.0)
            cl = np.where(has, CLIMB[np.maximum(gidx, 0)], 0.0)
            mu = np.where(has, MXUP[np.maximum(gidx, 0)], 0.0)
            ln = np.where(has, LEN_D[np.maximum(gidx, 0)], 0.0)
            # doğru işaretçi sıçratma: S[i] = değer(i) + S[par(i)]
            S_t, S_c, S_l, M_u = tt.copy(), cl.copy(), ln.copy(), mu.copy()
            q = par.copy()
            for _ in range(13):
                notroot = q != np.arange(len(q))
                if not notroot.any():
                    break
                S_t = S_t + np.where(notroot, S_t[q], 0)
                S_c = S_c + np.where(notroot, S_c[q], 0)
                S_l = S_l + np.where(notroot, S_l[q], 0)
                M_u = np.maximum(M_u, np.where(notroot, M_u[q], 0))
                q = q[q]
            for si in members:
                if loc[stop_node[si]] != n:
                    continue
                ok = np.isfinite(dist[r][tl]) & (tsel != si)
                tg = tsel[ok]; tn = tl[ok]
                cost = dist[r][tn] + snap_min[si] + snap_min[tg]
                tmin = S_t[tn] + snap_min[si] + snap_min[tg]
                keepm = cost <= LIMIT[prof]
                ptr_lists[si].append((tg[keepm], cost[keepm], tmin[keepm], S_c[tn][keepm], M_u[tn][keepm], S_l[tn][keepm] + d_snap[si] + d_snap[tg][keepm]))
    to_l, c_l, t_l, cl_l, mu_l, ln_l, cnt = [], [], [], [], [], [], []
    for si in range(NS):
        if ptr_lists[si]:
            a = [np.concatenate(x) for x in zip(*ptr_lists[si])]
        else:
            a = [np.zeros(0)] * 6
        to_l.append(a[0]); c_l.append(a[1]); t_l.append(a[2]); cl_l.append(a[3]); mu_l.append(a[4]); ln_l.append(a[5])
        cnt.append(len(a[0]))
    res[prof] = dict(ptr=np.r_[0, np.cumsum(cnt)].astype(np.int32),
                     to=np.concatenate(to_l).astype(np.uint16),
                     cost=np.concatenate(c_l).astype(np.float16), tmin=np.concatenate(t_l).astype(np.float16),
                     climb=np.minimum(np.round(np.concatenate(cl_l)), 255).astype(np.uint8),
                     maxup=np.clip(np.round(np.concatenate(mu_l) * 100), 0, 127).astype(np.int8),
                     len=np.minimum(np.concatenate(ln_l), 65535).astype(np.uint16))
    log(f"profil {prof}: {len(res[prof]['to']):,} durak çifti")

np.savez_compressed("out/yurume.npz", **{f"{p}_{k}": v for p, d in res.items() for k, v in d.items()})
log("yurume.npz yazıldı")
