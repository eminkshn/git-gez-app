"""yokus_gezi.ipynb defterine hava durumu + saatlik trafik ekler (bir kez çalıştırılır).
Kullanım: python tools/patch_hava_trafik.py yokus-gezi/yokus_gezi.ipynb"""
import sys
import nbformat

path = sys.argv[1]
nb = nbformat.read(path, as_version=4)


def cell_with(text):
    idx = [i for i, c in enumerate(nb.cells) if text in c.source]
    assert len(idx) == 1, (text, idx)
    return nb.cells[idx[0]], idx[0]


def rep(text_in_cell, old, new, count=1):
    c, _ = cell_with(text_in_cell)
    assert c.source.count(old) == count, (old[:60], c.source.count(old))
    c.source = c.source.replace(old, new)


# 1) Ayarlar ---------------------------------------------------------------------------------
rep('PROFILLER = {', 'PROFILLER = {', '''# Hava ve trafik (docs/PLAN_TRAFIK_HAVA.md) — eşik ve katsayılar başlangıç VARSAYIMIDIR, ölçümle güncellenmeli
HAVA_ESIK = {"yagmur_mm": 0.5, "sicak_c": 33, "ruzgar_kmh": 50, "firtina_kmh": 70, "sis_m": 500}
HAVA_YURUME_K = {"acik": 1.0, "yagmur": 1.15, "kar": 1.5, "sicak": 1.1}     # yürüme süresi çarpanı
HAVA_AGIRLIK_K = {"acik": 1.0, "yagmur": 1.5, "kar": 2.0, "sicak": 1.25}    # "en az yürüme"de yürümenin ek ağırlığı
TRAFIK_SINIR = (0.7, 2.0)                    # otobüs süresi çarpanı en az / en çok
KOSUL = {"sinif": "acik", "K": 1.0, "agirlik": 1.0, "vapur_kapali": False, "trafik": False,
         "anahtar": ("acik", False, False), "etiket": ""}          # şu anki hava/trafik durumu (arama başında ayarlanır)
PROFILLER = {''')

# 2) Yürüme bağlantıları: hava çarpanı ----------------------------------------------------------
rep('class Yurume:', '''        self.cache = {}
    def get(self, sid, default=()):''', '''        self.cache = {}
        self.cache_k = {}                                # hava çarpanlı kopyalar: (durak, K) -> liste
    def get(self, sid, default=()):''')
rep('class Yurume:', '''        return r
    def __len__(self):''', '''        k = KOSUL["K"]
        if k == 1.0:
            return r
        rk = self.cache_k.get((sid, k))
        if rk is None:                                   # yağmur/kar: yürüme süreleri uzar
            rk = self.cache_k[(sid, k)] = [(t, c * k, kind, x) for t, c, kind, x in r]
        return rk
    def __len__(self):''')

# 3) Noktadan erişim + sokak yolu + kuş uçuşu yedek: hava çarpanı --------------------------------
rep('def nokta_erisim(', '''            if c <= limit:
                out[sid] = c''', '''            if c <= limit:
                out[sid] = c * KOSUL["K"]''')
rep('def yol_bul(', '''    if key in _yol_cache:
        return _yol_cache[key]''', '''    if key in _yol_cache:
        return _hava_yol(_yol_cache[key])''')
rep('def yol_bul(', '''    _yol_cache[key] = sonuc
    return sonuc''', '''    _yol_cache[key] = sonuc
    return _hava_yol(sonuc)

def _hava_yol(s):
    """Önbellekteki yürüyüş sonucu hava çarpanıyla (önbellek değişmez)."""
    return s if KOSUL["K"] == 1.0 else dict(s, tmin=s["tmin"] * KOSUL["K"])''')
rep('def near_stops(', '''            out[sid] = d * WALK_DETOUR / WALK_M_PER_MIN''', '''            out[sid] = d * WALK_DETOUR / WALK_M_PER_MIN * KOSUL["K"]''')
rep('def erisim(', '''    key = f"_acc_{profil}_{yon}"''', '''    key = f"_acc_{profil}_{yon}_{KOSUL['K']}"''')

# 4) Dijkstra: "en az yürüme"de yağmurda yürüme daha pahalı -------------------------------------
rep('def dijkstra(', '''            return (minutes * WALK_WEIGHT,)''', '''            return (minutes * WALK_WEIGHT * KOSUL["agirlik"],)''')

# 5) Hava + trafik hücresi: graf hücresinin önüne ----------------------------------------------
_, gi = cell_with('def build_graph(')
md_i = gi - 1 if nb.cells[gi - 1].cell_type == "markdown" else gi
nb.cells.insert(md_i, nbformat.v4.new_markdown_cell('''## Hava durumu ve trafik
- **Hava:** seçilen gün/saat için [Open-Meteo](https://open-meteo.com) saatlik tahmini (geçmiş günler için arşiv). Anahtar gerekmez.
  Yağmur/kar/sıcak → yürüme süreleri uzar; rüzgâr hamlesi ≥ 50 km/sa → vapur uyarısı, ≥ 70 km/sa (fırtına) → vapurlar kullanılmaz.
  İnternet yoksa ya da tarih 16 günden uzaksa hava etkisi yok sayılır. Arayüzden elle de seçilebilir (demo için).
- **Trafik:** `trafik.csv` (İBB *Saatlik Trafik Yoğunluk* verisinden `tools/prep_trafik.py` ile) varsa otobüs sürelerine
  o saatin çarpanı uygulanır (metrobüs, raylı sistem ve vapur etkilenmez). Dosya yoksa eski sabit hız kullanılır.
- Kenar maliyetleri saate göre değişir ama **hep pozitif kalır** → Dijkstra ve A* doğru kalır. Graf önbelleği anahtarı: (gün, saat, vapur, trafik).'''))
nb.cells.insert(md_i + 1, nbformat.v4.new_code_cell(r'''import requests
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
def hava_tahmini(tarih, saat):
    """Open-Meteo saatlik değerler (İstanbul merkez) ya da None. Geçmiş günler arşivden."""
    key = (tarih, saat)
    if key not in _hava_cache:
        gecmis = tarih < datetime.now(IST).date()
        url = "https://archive-api.open-meteo.com/v1/archive" if gecmis else "https://api.open-meteo.com/v1/forecast"
        alanlar = ["temperature_2m", "precipitation", "snowfall", "wind_gusts_10m"] + ([] if gecmis else ["visibility"])
        try:
            r = requests.get(url, params={"latitude": 41.015, "longitude": 28.98, "hourly": ",".join(alanlar),
                                          "timezone": "Europe/Istanbul", "start_date": tarih.isoformat(),
                                          "end_date": tarih.isoformat()}, headers=_UA, timeout=6)
            r.raise_for_status()
            h = r.json()["hourly"]
            _hava_cache[key] = {a: h[a][saat] for a in alanlar if h.get(a) and h[a][saat] is not None}
        except Exception as e:
            print(f"(hava bilgisi alınamadı: {type(e).__name__})")
            _hava_cache[key] = None
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
            sinif, firtina, olcum = "acik", False, "hava bilgisi yok (internet ya da 16 günden uzak tarih)"
    else:
        sinif, firtina = ("acik", True) if hava == "firtina" else (hava, False)
        olcum = "elle seçildi"
        if firtina:
            uyar.append("⛴ Fırtına: vapurlar kullanılmıyor")
    K = HAVA_YURUME_K[sinif]
    trafik = bool(trafik and TRAFIK)
    parca = [f"{HAVA_AD[sinif]} ({olcum})"]
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
    for yol in (f"{folder}/trafik.csv", "trafik.csv"):
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
'''))

# 6) Graf: fırtınada vapur yok, otobüse trafik çarpanı; önbellek anahtarı -----------------------
rep('def build_graph(', '''        seq = line_stops[lid]
        wait = wait_at(lid, gun, saat)''', '''        seq = line_stops[lid]
        if KOSUL["vapur_kapali"] and lines[lid]["mode"] == "Vapur":
            continue                         # fırtına: vapur yok
        wait = wait_at(lid, gun, saat)''')
rep('def build_graph(', '''            if i + 1 < len(seq):
                adj[node].append(((lid, i + 1), seq[i + 1][2], "ride", lid))''', '''            if i + 1 < len(seq):
                dk = seq[i + 1][2] * (trafik_carpani(lid, i, gun, saat) if KOSUL["trafik"] else 1.0)
                adj[node].append(((lid, i + 1), dk, "ride", lid))''')
rep('def build_graph(', '''def get_graph(gun, saat):
    if (gun, saat) not in _graph_cache:
        _graph_cache[(gun, saat)] = build_graph(gun, saat)
    return _graph_cache[(gun, saat)]''', '''def graf_anahtari(gun, saat):
    return (gun, saat, KOSUL["vapur_kapali"], KOSUL["trafik"])

def get_graph(gun, saat):
    k = graf_anahtari(gun, saat)
    if k not in _graph_cache:
        _graph_cache[k] = build_graph(gun, saat)
    return _graph_cache[k]''')
rep('def ters_graf(', '''    if (gun, saat) not in _ters_cache:''', '''    k = graf_anahtari(gun, saat)                         # A* alt sınırı aynı trafik/vapur durumuyla
    if k not in _ters_cache:''')
rep('def ters_graf(', '''        _ters_cache[(gun, saat)] = dict(rev)
    return _ters_cache[(gun, saat)]''', '''        _ters_cache[k] = dict(rev)
    return _ters_cache[k]''')

# 7) Rota: hava parametresi, önbellek anahtarı, başlıkta hava/trafik satırı -----------------------
rep('def rota_hesapla(', '''def rota_hesapla(A, B, kriter="süre", gun=VARSAYILAN_GUN, saat=VARSAYILAN_SAAT, tuvalet=True, profil="normal"):''',
    '''def rota_hesapla(A, B, kriter="süre", gun=VARSAYILAN_GUN, saat=VARSAYILAN_SAAT, tuvalet=True, profil="normal",
                 hava=None):''')
rep('def rota_hesapla(', '''    key = (A["label"], A["lat"], A["lon"], B["label"], B["lat"], B["lon"], gun, saat, profil)
    if key not in _rota_cache:
        _rota_cache[key] = alternatif_rotalar(A, B, gun, saat, profil)
    rotalar, meta = _rota_cache[key]''', '''    if hava is not None:                                 # None: mevcut KOSUL (testler); arayüz her zaman verir
        kosul_ayarla(gun, saat, hava)
    key = (A["label"], A["lat"], A["lon"], B["label"], B["lat"], B["lon"], gun, saat, profil, KOSUL["anahtar"])
    if key not in _rota_cache:
        _rota_cache[key] = alternatif_rotalar(A, B, gun, saat, profil)
    rotalar, meta = _rota_cache[key]
    meta = dict(meta, kosul=KOSUL["etiket"], uyarilar=list(KOSUL.get("uyarilar", [])))''')
rep('def rota_hesapla(', '''{GUN_ADI[gun]} {saat:02d}:00 · kriter: {kriter} · {PROFILLER[profil]}\\n\\n"''',
    '''{GUN_ADI[gun]} {saat:02d}:00 · kriter: {kriter} · {PROFILLER[profil]}  \\n{KOSUL['etiket']}\\n\\n" + "".join(f"> {u}  \\n" for u in KOSUL.get("uyarilar", []))''')
rep('def rota(nereden', '''harita_goster=False, tuvalet=True,
         profil="normal"):''', '''harita_goster=False, tuvalet=True,
         profil="normal", hava="oto"):''')
rep('def rota(nereden', '''rota_hesapla(*yerler, kriter, gun, saat, tuvalet, profil)''', '''rota_hesapla(*yerler, kriter, gun, saat, tuvalet, profil, hava)''')
rep('def rota_sayfasi(', '''f'{meta.get("aktif", 0):,} hat çalışıyor</div></div>')''', '''f'{meta.get("aktif", 0):,} hat çalışıyor'
           + (f'<br>{_e(meta["kosul"])}' if meta.get("kosul") else "")
           + "".join(f'<br><b style="color:#b06000">{_e(u)}</b>' for u in meta.get("uyarilar", [])) + '</div></div>')''')

# 8) Gezi: o tarihin hava tahmini -------------------------------------------------------------
rep('def gezi_planla(', '''    gun, saat = gun_tipi(gun_idx), min(int(bas_dk // 60), 23)''', '''    gun, saat = gun_tipi(gun_idx), min(int(bas_dk // 60), 23)
    kosul_ayarla(gun, saat, "oto", tarih=tarih)          # o günün hava tahmini (yağmurda yürüme uzar)''')

# 9) Arayüz: hava seçimi ----------------------------------------------------------------------
rep('def rota_ui(', '''def rota_ui(a_val, a_yerler, b_val, b_yerler, gun, saat, kriter, profil, tuvalet, a_txt=None, b_txt=None):''',
    '''def rota_ui(a_val, a_yerler, b_val, b_yerler, gun, saat, kriter, profil, tuvalet, a_txt=None, b_txt=None, hava="oto"):''')
rep('def rota_ui(', '''rota_hesapla(A, B, kriter, gun, int(saat), tuvalet, profil)''', '''rota_hesapla(A, B, kriter, gun, int(saat), tuvalet, profil, hava)''')
rep('with gr.Tab("🧭 Rota', '''                    saat = gr.Dropdown(SAATLER, value=saat0, label="Saat", min_width=110)''', '''                    saat = gr.Dropdown(SAATLER, value=saat0, label="Saat", min_width=110)
                    hava = gr.Dropdown(HAVA_SECENEK, value="oto", label="Hava", min_width=150)''')
rep('with gr.Tab("🧭 Rota', '''        girdiler = [a_rd, a_yer, b_rd, b_yer, gun, saat, kriter, profil, tuv, a_txt, b_txt]''',
    '''        girdiler = [a_rd, a_yer, b_rd, b_yer, gun, saat, kriter, profil, tuv, a_txt, b_txt, hava]''')
rep('with gr.Tab("🧭 Rota', '''        for c in (kriter, profil):''', '''        for c in (kriter, profil, hava):''')

# 10) Testler: nötr başla + hava/trafik testleri ------------------------------------------------
rep('def run_tests():', '''def run_tests():
''', '''def run_tests():
    kosul_ayarla("hi", 8, "acik", trafik=False)          # testler hava/trafikten bağımsız başlasın
''')
rep('def run_tests():', '''    print("\\nTüm testler geçti ✅")''', '''    # Hava: yağmurda yürüme uzar, araç süresi değişmez; fırtınada vapur kullanılmaz
    U, Bj = yer_ara("Üsküdar")[0], yer_ara("Beşiktaş")[0]
    kosul_ayarla("hi", 8, "acik", trafik=False)
    acik = rota_hesapla(U, Bj, "süre", "hi", 8, False)[3]
    kosul_ayarla("hi", 8, "yagmur", trafik=False)
    yag = rota_hesapla(U, Bj, "süre", "hi", 8, False)[3]
    assert yag[0]["oz"]["walk"] > acik[0]["oz"]["walk"] * 1.1
    kosul_ayarla("hi", 8, "firtina", trafik=False)
    assert all(lines[L["line"]]["mode"] != "Vapur" for r in rota_hesapla(U, Bj, "süre", "hi", 8, False)[3]
               for L in r["legs"] if L["type"] == "ride")
    assert acik and any(lines[L["line"]]["mode"] == "Vapur" for r in acik for L in r["legs"] if L["type"] == "ride")
    # Hava sınıfı eşikleri
    assert hava_sinifi({"precipitation": 2.0, "temperature_2m": 10, "wind_gusts_10m": 20})[0] == "yagmur"
    assert hava_sinifi({"snowfall": 0.4, "precipitation": 0.4, "temperature_2m": -1})[0] == "kar"
    assert hava_sinifi({"wind_gusts_10m": 80})[1] is True
    # Trafik: sahte bir tabloyla 08:00'de otobüs yolculuğu uzar, metrobüs/raylı değişmez
    global TRAFIK, TRAFIK_SEHIR
    eski = (TRAFIK, TRAFIK_SEHIR)
    TRAFIK, TRAFIK_SEHIR = {("x", "hi", 8): 1.0}, {("hi", 8): 1.6}
    kosul_ayarla("hi", 8, "acik", trafik=True)
    g_t = get_graph("hi", 8)[0]
    kosul_ayarla("hi", 8, "acik", trafik=False)
    g_0 = get_graph("hi", 8)[0]
    def ride_dk(g, mode):
        return sum(m for es in g.values() for _, m, k, lid in es if k == "ride" and lines[lid]["mode"] == mode)
    assert ride_dk(g_t, "Otobüs") > ride_dk(g_0, "Otobüs") * 1.5 and ride_dk(g_t, "Metro") == ride_dk(g_0, "Metro")
    TRAFIK, TRAFIK_SEHIR = eski
    for k_ in [k for k in _graph_cache if k[3]]:            # sahte trafik grafını önbellekten at
        _graph_cache.pop(k_); _ters_cache.pop(k_, None)
    kosul_ayarla("hi", 8, "acik", trafik=False)
    assert geohash(41.0082, 28.9784, 6) == "sxk9" + geohash(41.0082, 28.9784, 6)[4:] and len(geohash(41.0, 29.0, 7)) == 7

    print("\\nTüm testler geçti ✅")''')

nbformat.write(nb, path)
print("ok", len(nb.cells), "hücre")
