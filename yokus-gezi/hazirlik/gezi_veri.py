"""gezi_yerleri.csv üretir. Kaynaklar: Kültür ve Turizm Bakanlığı / Milli Saraylar duyuruları (2026), istanbul.com rehberleri,
haber siteleri (Kasım 2026 aramaları). Koordinatlar: OpenStreetMap Nominatim (her biri tek tek doğrulandı).
tur: yer (normal durak) · gecis (yol üstünde bakılıp geçilen) · cadde (iki ucu olan, baştan sona yürünen)
saat: "yaz" = 1 Nisan–31 Ekim, "kis" = 1 Kasım–31 Mart. gise = kapanıştan kaç dk önce son giriş.
ozel: güne özel saat (0=Pzt … 6=Paz), ör. "6=12:00-18:00". kapali: kapalı günler. cuma: Cuma 12:00–14:30 turist ziyaretine kapalı.
"""
import csv, json

G = {g[0]: (g[2], g[3]) for g in json.load(open("geocode.json")) if g[7]}   # önceki doğrulanmış koordinatlar

def k(old_id, fallback):
    return G.get(old_id, fallback)

R = []
def yer(id, ad, bolge, tur, ll, sure, kuyruk=0, mk=0, ucret=0, yaz="00:00-23:59", kis=None, gise=0, kapali="", cuma=0,
        pop=3, tarih=0, manzara=0, eglence=0, kultur=0, ll2=None, ozel="", not_="", kaynak="OSM konum"):
    kis = kis or yaz
    R.append(dict(id=id, ad=ad, bolge=bolge, tur=tur, lat=round(ll[0], 6), lon=round(ll[1], 6),
                  lat2=round(ll2[0], 6) if ll2 else "", lon2=round(ll2[1], 6) if ll2 else "",
                  sure_dk=sure, kuyruk_dk=kuyruk, muzekart=mk, ucretli=ucret, yaz=yaz, kis=kis, gise_dk=gise,
                  kapali_gun=kapali, cuma_ogle=cuma, ozel=ozel, populerlik=pop, tarih=tarih, manzara=manzara,
                  eglence=eglence, kultur=kultur, notlar=not_, kaynak=kaynak))

# ------------------------------------------------------------- Fatih (Sultanahmet – Eminönü)
B = "Fatih"
yer("F01", "Ayasofya-i Kebir Camii", B, "yer", (41.00858, 28.98017), 45, 20, 0, 0, "09:00-19:00", "09:00-17:00", cuma=1,
    pop=5, tarih=5, manzara=4, eglence=2, kultur=5, not_="T.C. vatandaşlarına ücretsiz; namaz vakitlerinde kısa aralar",
    kaynak="istanbulclues, istanbul.com (2026)")
yer("F02", "Topkapı Sarayı", B, "yer", (41.01134, 28.98320), 150, 20, 1, 1, "09:00-18:30", "09:00-18:00", gise=60, kapali="1",
    pop=5, tarih=5, manzara=4, eglence=2, kultur=5, not_="Salı kapalı; Harem ve Aya İrini'de Müzekart geçmeyebilir",
    kaynak="Milli Saraylar 2026 esasları, Türkgün (2026)")
yer("F03", "Sultanahmet Camii", B, "yer", k("F03", (41.0054, 28.9768)), 30, 10, 0, 0, "09:00-18:30", "09:00-17:30", cuma=1,
    pop=5, tarih=5, manzara=2, eglence=1, kultur=4, not_="Ücretsiz; namaz vakitlerinde ~30 dk kapalı", kaynak="istanbul.com (2026)")
yer("F04", "Yerebatan Sarnıcı", B, "yer", k("F04", (41.0084, 28.9779)), 40, 35, 0, 1, "09:00-19:00", "09:00-18:00", gise=30,
    pop=5, tarih=5, manzara=1, eglence=4, kultur=4, not_="Vakıflar'a devredildi; Müzekart durumu belirsiz",
    kaynak="Alomaliye 03.11.2026, Türkgün (2026)")
yer("F05", "İstanbul Arkeoloji Müzeleri", B, "yer", k("F05", (41.0117, 28.9813)), 90, 5, 1, 1, "09:00-19:00", "09:00-18:00", gise=60,
    pop=3, tarih=5, manzara=1, eglence=2, kultur=5, not_="Çinili Köşk restorasyonda", kaynak="KTB, Euronews (09.2026)")
yer("F06", "Gülhane Parkı", B, "yer", k("F06", (41.0129, 28.9812)), 30, 0, 0, 0, "07:00-22:00", "07:00-21:00",
    pop=3, tarih=2, manzara=3, eglence=3, kultur=1)
yer("F07", "Sultanahmet Meydanı (Hipodrom)", B, "gecis", (41.00590, 28.97500), 15, pop=4, tarih=5, manzara=2, eglence=2, kultur=3)
yer("F08", "Türk ve İslam Eserleri Müzesi", B, "yer", k("F08", (41.0063, 28.9748)), 60, 5, 1, 1, "09:00-19:00", "09:00-18:00",
    gise=60, kapali="0", pop=2, tarih=4, manzara=1, eglence=1, kultur=5, kaynak="İstanbul İl Kültür Turizm Md. (istanbul.ktb.gov.tr)")
yer("F09", "Kapalıçarşı", B, "yer", k("F09", (41.0107, 28.9680)), 60, 0, 0, 0, "08:30-19:00", kapali="6",
    pop=5, tarih=4, manzara=1, eglence=5, kultur=3, not_="Pazar kapalı", kaynak="Kültür Portalı, eleman.net (2026)")
yer("F10", "Süleymaniye Camii", B, "yer", k("F10", (41.0162, 28.9639)), 40, 0, 0, 0, "09:00-18:30", "09:00-17:00", cuma=1,
    pop=4, tarih=5, manzara=5, eglence=1, kultur=4)
yer("F11", "Mısır Çarşısı", B, "yer", k("F11", (41.0165, 28.9706)), 40, 0, 0, 0, "08:00-19:30", "08:00-19:00",
    pop=4, tarih=4, manzara=1, eglence=5, kultur=3)
yer("F12", "Rüstem Paşa Camii", B, "yer", k("F12", (41.0177, 28.9707)), 20, 0, 0, 0, "09:00-18:00", "09:00-17:00", cuma=1,
    pop=2, tarih=4, manzara=1, eglence=1, kultur=5)
yer("F13", "Küçük Ayasofya Camii", B, "yer", k("F13", (41.0027, 28.9726)), 20, 0, 0, 0, "09:00-18:00", "09:00-17:00", cuma=1,
    pop=2, tarih=4, manzara=1, eglence=1, kultur=3)
yer("F14", "Eminönü ve Galata Köprüsü", B, "gecis", (41.01880, 28.97340), 15, pop=4, tarih=3, manzara=5, eglence=4, kultur=2)

# ------------------------------------------------------------- Balat (Fener – Balat – Ayvansaray)
B = "Balat"
yer("B01", "Balat'ın renkli sokakları (Merdivenli Yokuş)", B, "yer", (41.03125, 28.94620), 40, 0, 0, 0, "08:00-20:00", "08:00-17:30",
    pop=4, tarih=3, manzara=3, eglence=4, kultur=3, not_="Gün ışığında gezilmesi önerilir")
yer("B02", "Sveti Stefan Bulgar Kilisesi", B, "yer", (41.03178, 28.94969), 25, 5, 0, 0, "09:00-17:00",
    pop=3, tarih=4, manzara=3, eglence=1, kultur=4)
yer("B03", "Fener Rum Patrikhanesi", B, "yer", (41.02940, 28.95214), 20, 0, 0, 0, "09:00-16:00",
    pop=2, tarih=5, manzara=1, eglence=1, kultur=4)
yer("B04", "Fener Rum Lisesi (Kırmızı Mektep)", B, "gecis", (41.02928, 28.94939), 10,
    pop=3, tarih=4, manzara=4, eglence=1, kultur=3, not_="Dışarıdan görülür")
yer("B05", "Kariye Camii (Chora)", B, "yer", k("B05", (41.0310, 28.9390)), 40, 15, 0, 0, "09:00-18:00", "09:00-17:00", kapali="4",
    pop=4, tarih=5, manzara=1, eglence=1, kultur=5, not_="Cuma turist ziyaretine kapalı; T.C. vatandaşlarına ücretsiz",
    kaynak="Habertürk, DHA (2024), istanbul.com (2026)")
yer("B06", "Yavuz Sultan Selim Camii", B, "yer", k("B06", (41.0280, 28.9497)), 20, 0, 0, 0, "09:00-18:00", "09:00-17:00", cuma=1,
    pop=2, tarih=4, manzara=5, eglence=1, kultur=3)
yer("B07", "Tekfur Sarayı Müzesi", B, "yer", k("B08", (41.0346, 28.9411)), 40, 5, 0, 1, "09:00-19:00", "09:00-17:00", gise=30, kapali="0",
    pop=2, tarih=4, manzara=3, eglence=2, kultur=4, not_="İBB müzesi; saatleri kontrol edin")

# ------------------------------------------------------------- Beyoğlu
B = "Beyoğlu"
yer("Y01", "Galata Kulesi", B, "yer", k("Y01", (41.0256, 28.9742)), 40, 30, 1, 1, "08:30-23:00", "10:00-20:00", gise=30,
    pop=5, tarih=4, manzara=5, eglence=3, kultur=3, not_="Kış: 10:00–20:00; Müzekart gündüz geçerli",
    kaynak="KTB istanbul.ktb.gov.tr (Galata Kulesi), istanbul.com (2026)")
yer("Y02", "İstiklal Caddesi", B, "cadde", (41.03580, 28.98460), 20, ll2=(41.02862, 28.97473),
    pop=5, tarih=3, manzara=2, eglence=5, kultur=3, not_="Taksim ↔ Tünel arası yürünür (~1,4 km)")
yer("Y03", "Taksim Meydanı ve AKM", B, "gecis", (41.03783, 28.98502), 10, pop=4, tarih=3, manzara=2, eglence=3, kultur=3)
yer("Y04", "Pera Müzesi", B, "yer", k("Y04", (41.0317, 28.9749)), 75, 5, 0, 1, "10:00-19:00", gise=30, kapali="0", ozel="4=10:00-22:00;6=12:00-18:00",
    pop=3, tarih=3, manzara=1, eglence=2, kultur=5, kaynak="istanbul-tourist-information (2026)")
yer("Y05", "İstanbul Modern", B, "yer", k("Y05", (41.0265, 28.9830)), 90, 10, 0, 1, "10:00-18:00", gise=30, kapali="0", ozel="4=10:00-20:00",
    pop=3, tarih=2, manzara=4, eglence=3, kultur=5)
yer("Y06", "Galataport ve Karaköy sahili", B, "yer", k("Y06", (41.0270, 28.9810)), 40, 0, 0, 0, "08:00-23:00",
    pop=4, tarih=1, manzara=4, eglence=4, kultur=2)
yer("Y07", "Çiçek Pasajı", B, "gecis", (41.03410, 28.97792), 10, pop=3, tarih=4, manzara=1, eglence=4, kultur=3)
yer("Y08", "Galata Mevlevihanesi Müzesi", B, "yer", k("Y08", (41.0283, 28.9739)), 35, 5, 1, 1, "09:00-19:00", "09:00-17:00", gise=30,
    kapali="0", pop=2, tarih=5, manzara=2, eglence=2, kultur=5, not_="Saatleri kontrol edin")
yer("Y09", "Masumiyet Müzesi", B, "yer", k("Y09", (41.0313, 28.9785)), 60, 5, 0, 1, "10:00-18:00", gise=30, kapali="0",
    pop=3, tarih=2, manzara=1, eglence=3, kultur=5)
yer("Y10", "Kamondo Merdivenleri", B, "gecis", k("Y10", (41.0240, 28.9745)), 5, pop=3, tarih=4, manzara=3, eglence=2, kultur=2)

# ------------------------------------------------------------- Beşiktaş
B = "Beşiktaş"
yer("K01", "Dolmabahçe Sarayı", B, "yer", k("K01", (41.0391, 29.0004)), 90, 20, 0, 1, "09:00-19:00", "09:00-18:00", gise=60, kapali="0",
    pop=5, tarih=5, manzara=4, eglence=2, kultur=5, not_="Pazartesi kapalı; kışın gişe 17:00", kaynak="Milli Saraylar 2026 esasları, Alomaliye 07.10.2026")
yer("K02", "Dolmabahçe Saat Kulesi", B, "gecis", (41.03766, 28.99636), 5, pop=2, tarih=3, manzara=3, eglence=1, kultur=2)
yer("K03", "Deniz Müzesi", B, "yer", (41.04150, 29.00610), 60, 5, 0, 1, "09:00-17:00", gise=30, kapali="0",
    pop=3, tarih=4, manzara=2, eglence=3, kultur=4, not_="Saatleri kontrol edin")
yer("K04", "Beşiktaş Çarşı", B, "yer", (41.04300, 29.00580), 30, pop=3, tarih=1, manzara=1, eglence=4, kultur=2)
yer("K05", "Yıldız Parkı", B, "yer", k("K03", (41.0490, 29.0120)), 45, 0, 0, 0, "08:00-22:00", "08:00-19:00",
    pop=3, tarih=2, manzara=4, eglence=3, kultur=1)
yer("K06", "Yıldız Sarayı", B, "yer", (41.05071, 29.01170), 60, 5, 0, 1, "09:00-18:00", "09:00-18:00", gise=60, kapali="2",
    pop=2, tarih=4, manzara=3, eglence=1, kultur=4, not_="Çarşamba kapalı", kaynak="Milli Saraylar 2026 esasları")
yer("K07", "Çırağan Sarayı (dıştan)", B, "gecis", (41.04347, 29.01531), 5, pop=2, tarih=4, manzara=4, eglence=1, kultur=2)
yer("K08", "Ortaköy Meydanı ve Camii", B, "yer", (41.04729, 29.02677), 40, pop=5, tarih=3, manzara=5, eglence=4, kultur=3)
yer("K09", "Ihlamur Kasrı", B, "yer", (41.05071, 29.00120), 40, 5, 0, 1, "09:00-18:00", gise=60, kapali="0",
    pop=1, tarih=4, manzara=2, eglence=1, kultur=4, kaynak="Milli Saraylar 2026 esasları")

# ------------------------------------------------------------- Kadıköy
B = "Kadıköy"
yer("D01", "Kadıköy İskelesi ve rıhtım", B, "gecis", (40.99291, 29.02287), 10, pop=3, tarih=2, manzara=4, eglence=3, kultur=2)
yer("D02", "Tarihi Kadıköy Çarşısı", B, "yer", k("D02", (40.9905, 29.0260)), 45, 0, 0, 0, "08:00-22:00",
    pop=4, tarih=2, manzara=1, eglence=5, kultur=3)
yer("D03", "Bahariye Caddesi", B, "cadde", (40.99049, 29.02921), 15, ll2=(40.98426, 29.02736),
    pop=3, tarih=2, manzara=1, eglence=4, kultur=3, not_="Altıyol (Boğa) ↔ Bahariye sonu")
yer("D04", "Süreyya Operası", B, "gecis", k("D06", (40.9878, 29.0310)), 5, pop=2, tarih=3, manzara=1, eglence=1, kultur=4)
yer("D05", "Moda Sahili", B, "yer", (40.97893, 29.02519), 45, pop=4, tarih=1, manzara=5, eglence=4, kultur=1)
yer("D06", "Yeldeğirmeni", B, "yer", k("D05", (40.9960, 29.0280)), 35, 0, 0, 0, "09:00-21:00",
    pop=2, tarih=2, manzara=1, eglence=3, kultur=4)
yer("D07", "Haydarpaşa Garı (dıştan)", B, "gecis", (40.99655, 29.01926), 10, pop=3, tarih=4, manzara=4, eglence=1, kultur=3)

# ------------------------------------------------------------- Üsküdar
B = "Üsküdar"
yer("U01", "Kız Kulesi (Salacak'tan tekneyle)", B, "yer", (41.02135, 29.00585), 75, 10, 1, 1, "09:00-18:00", gise=60,
    pop=5, tarih=4, manzara=5, eglence=3, kultur=3, not_="Süreye tekne gidiş-dönüş dahil; Müzekart girişte geçerli, tekne ücretli",
    kaynak="Türkgün, istanbul.com (2026)")
yer("U02", "Mihrimah Sultan Camii", B, "yer", (41.02682, 29.01597), 15, 0, 0, 0, "09:00-18:00", "09:00-17:00", cuma=1,
    pop=3, tarih=4, manzara=3, eglence=1, kultur=4)
yer("U03", "Yeni Valide Camii", B, "yer", (41.02479, 29.01515), 15, 0, 0, 0, "09:00-18:00", "09:00-17:00", cuma=1,
    pop=2, tarih=4, manzara=1, eglence=1, kultur=3)
yer("U04", "Şemsi Paşa Camii", B, "yer", k("U06", (41.0262, 29.0111)), 15, 0, 0, 0, "09:00-18:00", "09:00-17:00", cuma=1,
    pop=3, tarih=4, manzara=5, eglence=1, kultur=3)
yer("U05", "Salacak sahili", B, "gecis", (41.02000, 29.00700), 20, pop=4, tarih=1, manzara=5, eglence=3, kultur=1)
yer("U06", "Kuzguncuk", B, "yer", (41.03216, 29.03603), 45, pop=3, tarih=3, manzara=3, eglence=3, kultur=3)
yer("U07", "Fethi Paşa Korusu", B, "yer", (41.03271, 29.02743), 40, 0, 0, 0, "08:00-20:00", "08:00-18:00",
    pop=2, tarih=2, manzara=5, eglence=3, kultur=1)
yer("U08", "Beylerbeyi Sarayı", B, "yer", k("U07", (41.0428, 29.0400)), 60, 10, 0, 1, "09:00-18:00", gise=60, kapali="0",
    pop=3, tarih=5, manzara=4, eglence=2, kultur=4, kaynak="Milli Saraylar 2026 esasları, İstiklal (2026)")
yer("U09", "Çamlıca Tepesi", B, "yer", k("U03", (41.0273, 29.0687)), 40, 0, 0, 0, "07:00-22:00",
    pop=4, tarih=1, manzara=5, eglence=3, kultur=1)
yer("U10", "Büyük Çamlıca Camii", B, "yer", (41.03453, 29.07059), 30, 0, 0, 0, "09:00-20:00", "09:00-18:00", cuma=1,
    pop=3, tarih=2, manzara=4, eglence=1, kultur=4)

# İnsanların gezme sırası (web'deki yürüyüş rotalarından; yokuşlu yerlerde tepeden aşağı):
# Fatih: Sultanahmet kümesi -> Kapalıçarşı -> Süleymaniye -> Rüstem Paşa -> Mısır Çarşısı -> Eminönü (headout, Lonely Planet)
# Balat: Kariye/Tekfur (tepe) -> Yavuz Selim -> Balat sokakları -> Fener -> Bulgar Kilisesi (kıyı) (istanbulclues, thetripverdict)
# Beyoğlu: Taksim -> İstiklal -> Tünel/Pera -> Mevlevihane -> Galata Kulesi -> Kamondo -> Karaköy (istanbul.com, guruwalk)
# Beşiktaş: Dolmabahçe -> Beşiktaş -> Yıldız (üst kapı) -> Çırağan -> Ortaköy (Lonely Planet, thetripverdict)
# Kadıköy: Haydarpaşa/Yeldeğirmeni -> iskele -> çarşı -> Bahariye -> Moda (istanbul.com)
# Üsküdar: Çamlıca (tepe) -> Beylerbeyi/Kuzguncuk -> meydan camileri -> Şemsi Paşa -> Salacak -> Kız Kulesi (gün batımı)
SIRA = {"F13": 1, "F07": 2, "F08": 3, "F03": 4, "F01": 5, "F04": 6, "F02": 7, "F05": 8, "F06": 9, "F09": 10, "F10": 11,
        "F12": 12, "F11": 13, "F14": 14,
        "B05": 1, "B07": 2, "B06": 3, "B01": 4, "B04": 5, "B03": 6, "B02": 7,
        "Y03": 1, "Y02": 2, "Y07": 3, "Y09": 4, "Y04": 5, "Y08": 6, "Y01": 7, "Y10": 8, "Y06": 9, "Y05": 10,
        "K02": 1, "K01": 2, "K03": 3, "K04": 4, "K09": 5, "K06": 6, "K05": 7, "K07": 8, "K08": 9,
        "D07": 1, "D06": 2, "D01": 3, "D02": 4, "D03": 5, "D04": 6, "D05": 7,
        "U10": 1, "U09": 2, "U08": 3, "U06": 4, "U07": 5, "U02": 6, "U03": 7, "U04": 8, "U05": 9, "U01": 10}
for r in R:
    r["sira"] = SIRA[r["id"]]

with open("out/gezi_yerleri.csv", "w", encoding="utf-8", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(R[0])); w.writeheader(); w.writerows(R)
import collections
print(len(R), "yer", collections.Counter(r["bolge"] for r in R), collections.Counter(r["tur"] for r in R))
