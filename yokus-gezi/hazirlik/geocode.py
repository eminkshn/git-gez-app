import time, math, requests, csv
from poi_taslak import POI
def hv(a,b,c,d):
    R=6371000; p1,p2=math.radians(a),math.radians(c); dp=p2-p1; dl=math.radians(d-b)
    x=math.sin(dp/2)**2+math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2; return 2*R*math.asin(math.sqrt(x))
out=[]
for p in POI:
    lat0, lon0, q = p[3], p[4], p[-1]
    best=None
    for src in ("nom","photon"):
        try:
            if src=="nom":
                r=requests.get("https://nominatim.openstreetmap.org/search", params={"q": q+", İstanbul","format":"jsonv2","limit":3,"countrycodes":"tr"}, headers={"User-Agent":"rota-ders-projesi/1.0"}, timeout=10).json()
                cands=[(float(x["lat"]),float(x["lon"]),x["display_name"][:60]) for x in r]
            else:
                r=requests.get("https://photon.komoot.io/api/", params={"q":q,"limit":3,"lat":lat0,"lon":lon0}, timeout=10).json()
                cands=[(f["geometry"]["coordinates"][1],f["geometry"]["coordinates"][0],f["properties"].get("name","")) for f in r["features"]]
        except Exception as e:
            cands=[]
        for la,lo,nm in cands:
            d=hv(lat0,lon0,la,lo)
            if best is None or d<best[0]: best=(d,la,lo,nm,src)
        time.sleep(1.1)
        if best and best[0] < 400: break
    d,la,lo,nm,src = best if best else (1e9,lat0,lon0,"-","-")
    ok = d < 600
    out.append((p[0], p[1], round(la if ok else lat0,6), round(lo if ok else lon0,6), round(d), nm, src, ok))
    print(f"{p[0]} {p[1][:34]:<34} {d:7.0f} m {'OK ' if ok else 'XX '} {src} {nm}", flush=True)
import json; json.dump(out, open("geocode.json","w"), ensure_ascii=False)
