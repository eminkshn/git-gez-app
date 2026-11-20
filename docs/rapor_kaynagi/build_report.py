"""Algorithm design report -> HTML (inline SVG flowcharts) -> PDF via Chromium."""
import html

INK, ACC, SOFT, MID, PALE, BG = "#14213D", "#C2410C", "#4A5568", "#8A97AB", "#FBE3D6", "#FFFFFF"

# ------------------------------------------------------------------ flowchart helper
COLW, ROWH = 250, 92
NW, NH, DW, DH = 210, 52, 230, 74

def flow(nodes, edges, cols=3, rows=None, width=None):
    """nodes: {id: (kind, text, col, row)} kind in term/proc/dec/io
       edges: (a, b, label, mode) mode: down | right | left | loopL | loopR | up"""
    rows = rows or (max(n[3] for n in nodes.values()) + 1)
    W = width or (cols * COLW + 40)
    H = rows * ROWH + 20
    X = lambda c: 20 + COLW / 2 + c * COLW
    Y = lambda r: 10 + ROWH / 2 + r * ROWH
    out = [f'<svg viewBox="0 0 {W} {H}" width="{W}" height="{H}" xmlns="http://www.w3.org/2000/svg">',
           f'<defs><marker id="ah" markerWidth="10" markerHeight="8" refX="9" refY="4" orient="auto">'
           f'<path d="M0,0 L10,4 L0,8 z" fill="{INK}"/></marker></defs>']

    def size(k):
        return (DW, DH) if k == "dec" else (NW, NH)

    def side(nid, s):
        k, _, c, r = nodes[nid]
        w, h = size(k)
        x, y = X(c), Y(r)
        return {"top": (x, y - h / 2), "bottom": (x, y + h / 2), "left": (x - w / 2, y), "right": (x + w / 2, y)}[s]

    for a, b, label, mode in edges:
        ka, kb = nodes[a][2], nodes[b][2]
        if mode == "down":
            p = [side(a, "bottom"), side(b, "top")]
        elif mode == "up":
            p = [side(a, "top"), side(b, "bottom")]
        elif mode == "right":
            s, t = side(a, "right"), side(b, "top")
            p = [s, (t[0], s[1]), t]
        elif mode == "left":
            s, t = side(a, "left"), side(b, "top")
            p = [s, (t[0], s[1]), t]
        elif mode == "rightin":
            s, t = side(a, "bottom"), side(b, "right")
            p = [s, (s[0], t[1]), t]
        elif mode == "leftin":
            s, t = side(a, "bottom"), side(b, "left")
            p = [s, (s[0], t[1]), t]
        elif mode == "loopL":
            s, t = side(a, "left"), side(b, "left")
            x = min(s[0], t[0]) - 22
            p = [s, (x, s[1]), (x, t[1]), t]
        elif mode == "loopR":
            s, t = side(a, "right"), side(b, "right")
            x = max(s[0], t[0]) + 22
            p = [s, (x, s[1]), (x, t[1]), t]
        pts = " ".join(f"{x:.0f},{y:.0f}" for x, y in p)
        out.append(f'<polyline points="{pts}" fill="none" stroke="{INK}" stroke-width="1.6" marker-end="url(#ah)"/>')
        if label:
            lx, ly = p[0][0] + (p[1][0] - p[0][0]) / 2, p[0][1] + (p[1][1] - p[0][1]) / 2
            if mode == "down":
                lx, ly = p[0][0] + 14, p[0][1] + 16
            out.append(f'<text x="{lx + 2:.0f}" y="{ly - 5:.0f}" font-size="12" font-weight="700" fill="{ACC}">{label}</text>')

    for nid, (k, text, c, r) in nodes.items():
        x, y = X(c), Y(r)
        w, h = size(k)
        if k == "term":
            out.append(f'<rect x="{x - w / 2}" y="{y - h / 2}" width="{w}" height="{h}" rx="{h / 2}" fill="{INK}"/>')
            col = "#FFFFFF"
        elif k == "proc":
            out.append(f'<rect x="{x - w / 2}" y="{y - h / 2}" width="{w}" height="{h}" rx="4" fill="#FFFFFF" stroke="{INK}" stroke-width="1.6"/>')
            col = INK
        elif k == "io":
            o = 16
            out.append(f'<polygon points="{x - w / 2 + o},{y - h / 2} {x + w / 2},{y - h / 2} {x + w / 2 - o},{y + h / 2} {x - w / 2},{y + h / 2}" fill="{PALE}" stroke="{ACC}" stroke-width="1.6"/>')
            col = INK
        else:
            out.append(f'<polygon points="{x},{y - h / 2} {x + w / 2},{y} {x},{y + h / 2} {x - w / 2},{y}" fill="#FFF7E6" stroke="{ACC}" stroke-width="1.6"/>')
            col = INK
        lines = text.split("\n")
        y0 = y - (len(lines) - 1) * 7.5 + 4
        for i, ln in enumerate(lines):
            out.append(f'<text x="{x}" y="{y0 + i * 15:.0f}" font-size="12.5" text-anchor="middle" fill="{col}">{html.escape(ln)}</text>')
    out.append("</svg>")
    return "\n".join(out)

LEGEND = flow({"t": ("term", "Start / End", 0, 0), "i": ("io", "Input / Output", 1, 0),
               "p": ("proc", "Process", 2, 0), "d": ("dec", "Decision?", 3, 0)}, [], cols=4)

# ------------------------------------------------------------------ flowcharts
F_MAIN = flow({
    "s": ("term", "START", 1, 0),
    "in": ("io", "Read: from, to, day,\nhour, criterion", 1, 1),
    "pl": ("proc", "Find places\n(Algorithm 1)", 1, 2),
    "f": ("dec", "Both places\nfound?", 1, 3),
    "sg": ("io", "Show similar names", 0, 4),
    "g": ("proc", "Get graph for day + hour\n(Algorithm 3, cached)", 1, 4),
    "dj": ("proc", "Dijkstra with chosen\ncriterion (Algorithm 4)", 1, 5),
    "r": ("dec", "Route\nfound?", 1, 6),
    "nr": ("io", "\"No route at\nthis hour\"", 2, 7),
    "lg": ("proc", "Build directions (legs)\n+ toilets near transfers", 1, 7),
    "o": ("io", "Show directions + map", 1, 8),
    "e": ("term", "END", 1, 9),
}, [("s", "in", "", "down"), ("in", "pl", "", "down"), ("pl", "f", "", "down"),
    ("f", "sg", "No", "left"), ("f", "g", "Yes", "down"), ("g", "dj", "", "down"), ("dj", "r", "", "down"),
    ("r", "nr", "No", "right"), ("r", "lg", "Yes", "down"), ("lg", "o", "", "down"), ("o", "e", "", "down"),
    ("sg", "e", "", "leftin"), ("nr", "e", "", "rightin")])

F_SEARCH = flow({
    "s": ("term", "START", 1, 0),
    "in": ("io", "Read query text q", 1, 1),
    "n": ("proc", "q ← normalize(q)\n(lowercase, ç→c, ğ→g …)", 1, 2),
    "st": ("proc", "Stops whose name\ncontains q (dict)", 1, 3),
    "gr": ("proc", "Group same-name stops\nwithin 800 m, add label", 1, 4),
    "ad": ("proc", "Address search\n(OpenStreetMap)", 1, 5),
    "d": ("dec", "Any result?", 1, 6),
    "fz": ("proc", "Similar names\n(difflib)", 2, 7),
    "o": ("io", "Return list of places", 1, 8),
    "e": ("term", "END", 1, 9),
}, [("s", "in", "", "down"), ("in", "n", "", "down"), ("n", "st", "", "down"), ("st", "gr", "", "down"),
    ("gr", "ad", "", "down"), ("ad", "d", "", "down"), ("d", "o", "Yes", "down"), ("d", "fz", "No", "right"),
    ("fz", "o", "", "rightin"), ("o", "e", "", "down")])

F_GRID = flow({
    "s": ("term", "START", 1, 0),
    "c": ("proc", "Cell size = 2 km\nputs every stop in\ncells[row, col]", 1, 1),
    "a": ("dec", "Next stop A?", 1, 2),
    "o": ("io", "Return walking links", 2, 3),
    "e": ("term", "END", 2, 4),
    "b": ("proc", "B ← next stop in the\n9 cells around A", 1, 3),
    "d": ("dec", "distance(A, B)\n≤ 2 km ?", 1, 4),
    "add": ("proc", "Add link A → B\ntime = d × 1.3 ÷ 75", 1, 5),
    "m": ("dec", "More B in\n9 cells?", 1, 6),
}, [("s", "c", "", "down"), ("c", "a", "", "down"), ("a", "b", "Yes", "down"), ("a", "o", "No", "right"),
    ("o", "e", "", "down"), ("b", "d", "", "down"), ("d", "add", "Yes", "down"), ("d", "m", "No", "loopR"),
    ("add", "m", "", "down"), ("m", "b", "Yes", "loopL"), ("m", "a", "No", "loopR")])

F_GRAPH = flow({
    "s": ("term", "START", 1, 0),
    "in": ("io", "Read day, hour h", 1, 1),
    "l": ("dec", "Next line L?", 1, 2),
    "o": ("io", "Return graph", 2, 3),
    "e": ("term", "END", 2, 4),
    "n": ("proc", "n ← trips of L in hour h\np ← trips in hour h − 1", 1, 3),
    "d": ("dec", "n = 0 and\np = 0 ?", 1, 4),
    "w": ("proc", "wait ← min(max(30 ÷ n, 1), 30)\n(n = 0 → use n = 1)", 1, 5),
    "ed": ("proc", "Add board, ride, get-off\nedges for every stop of L", 1, 6),
}, [("s", "in", "", "down"), ("in", "l", "", "down"), ("l", "n", "Yes", "down"), ("l", "o", "No", "right"),
    ("o", "e", "", "down"), ("n", "d", "", "down"), ("d", "w", "No", "down"),
    ("d", "l", "Yes (skip line)", "loopL"), ("w", "ed", "", "down"), ("ed", "l", "", "loopR")])

F_DIJ = flow({
    "s": ("term", "START", 1, 0),
    "in": ("io", "Read graph, start stops,\ntarget stops, criterion", 1, 1),
    "i": ("proc", "best[start] ← 0\nheap ← all start states", 1, 2),
    "em": ("dec", "Heap empty?", 1, 3),
    "no": ("io", "Return \"no route\"", 2, 4),
    "p": ("proc", "state ← heap.pop()\n(cheapest)", 1, 4),
    "dn": ("dec", "Already\nfinished?", 1, 5),
    "ds": ("dec", "state is\nDESTINATION?", 1, 6),
    "rb": ("io", "Rebuild path\nand return it", 2, 7),
    "ed": ("proc", "For every edge allowed by\nRule 1 and Rule 2:\nnew ← cost + edge cost", 1, 7),
    "ch": ("dec", "new < best\n[next] ?", 1, 8),
    "up": ("proc", "best[next] ← new\nprev[next] ← state\nheap.push(next)", 1, 9),
    "e": ("term", "END", 2, 9),
}, [("s", "in", "", "down"), ("in", "i", "", "down"), ("i", "em", "", "down"), ("em", "no", "Yes", "right"),
    ("em", "p", "No", "down"), ("p", "dn", "", "down"), ("dn", "em", "Yes", "loopL"), ("dn", "ds", "No", "down"),
    ("ds", "rb", "Yes", "right"), ("ds", "ed", "No", "down"), ("ed", "ch", "", "down"),
    ("ch", "up", "Yes", "down"), ("ch", "ed", "No (next edge)", "loopR"), ("up", "em", "", "loopL"),
    ("rb", "e", "", "down"), ("no", "e", "", "loopR")], rows=10)

F_WC = flow({
    "s": ("term", "START", 1, 0),
    "in": ("io", "Read position (lat, lon),\nfilters, n", 1, 1),
    "t": ("dec", "Next toilet T?", 1, 2),
    "f": ("dec", "T passes the\nfilters?", 1, 3),
    "d": ("proc", "d ← distance(position, T)\nadd (d, T) to list", 1, 4),
    "h": ("proc", "heapq.nsmallest(n, list)\n(sorted by d)", 2, 3),
    "o": ("io", "Return n nearest toilets", 2, 4),
    "e": ("term", "END", 2, 5),
}, [("s", "in", "", "down"), ("in", "t", "", "down"), ("t", "f", "Yes", "down"), ("t", "h", "No", "right"),
    ("f", "d", "Yes", "down"), ("f", "t", "No", "loopL"), ("d", "t", "", "loopL"), ("h", "o", "", "down"),
    ("o", "e", "", "down")])

# ------------------------------------------------------------------ pseudocode blocks
def pc(s):
    s = html.escape(s.strip("\n"))
    for kw in ["BEGIN", "END", "IF", "THEN", "ELSE", "WHILE", "DO", "FOR EACH", "IN", "RETURN", "READ",
               "PRINT", "AND", "OR", "NOT", "CONTINUE", "STOP", "FUNCTION", "ENDIF", "ENDWHILE", "ENDFOR"]:
        s = s.replace(f"{kw} ", f"<b>{kw}</b> ").replace(f"{kw}\n", f"<b>{kw}</b>\n")
    return f'<pre class="pc">{s}</pre>'

P_MAIN = pc("""
BEGIN
  READ from_text, to_text, day, hour, criterion
  A ← FindPlaces(from_text)[selected]          // Algorithm 1
  B ← FindPlaces(to_text)[selected]
  IF A is empty OR B is empty THEN
      PRINT similar names
      STOP
  ENDIF
  G ← GetGraph(day, hour)                       // Algorithm 3 (cached)
  cost, path ← Dijkstra(G, A.stops, B.stops, criterion)   // Algorithm 4
  IF path is empty THEN
      PRINT "No route at this hour"
  ELSE
      legs ← BuildLegs(path)
      toilets ← ToiletsNear(transfer points of legs, 300 m)  // Algorithm 5
      PRINT directions(legs), toilets, map
  ENDIF
END
""")

P_SEARCH = pc("""
FUNCTION FindPlaces(q)
BEGIN
  q ← Normalize(q)                       // "KADIKÖY" → "kadikoy"
  names ← all keys of name_index that contain q      // name_index is a dict
  places ← empty list
  FOR EACH name IN names DO
      groups ← group stops of name: same group if distance ≤ 800 m
      FOR EACH g IN groups DO
          label ← name + nearest station + lines of g
          ADD (label, g) TO places
      ENDFOR
  ENDFOR
  ADD AddressSearch(q) TO places          // OpenStreetMap, stops within 2 km
  IF places is empty THEN
      places ← SimilarNames(q)            // difflib, only as last try
  ENDIF
  RETURN places
END
""")

P_GRID = pc("""
FUNCTION WalkingLinks(stops, R = 2000 m)
BEGIN
  cells ← empty dict
  FOR EACH s IN stops DO
      key ← (floor(s.lat ÷ R_lat), floor(s.lon ÷ R_lon))   // cell size = R
      ADD s TO cells[key]
  ENDFOR
  links ← empty dict
  FOR EACH A IN stops DO
      FOR EACH B IN the 9 cells around A DO
          d ← Haversine(A, B)
          IF B ≠ A AND d ≤ R THEN
              ADD (B, d × 1.3 ÷ 75 minutes) TO links[A]
          ENDIF
      ENDFOR
  ENDFOR
  RETURN links
END
""")

P_GRAPH = pc("""
FUNCTION GetGraph(day, h)
BEGIN
  IF (day, h) IN cache THEN RETURN cache[(day, h)]
  G ← empty adjacency list
  FOR EACH line L DO
      n ← departures[L, day, h] ;  p ← departures[L, day, h − 1]
      IF n = 0 AND p = 0 THEN CONTINUE          // line is not running
      IF n = 0 THEN n ← 1
      wait ← min(max(60 ÷ n ÷ 2, 1), 30)        // half of the gap
      FOR EACH stop i of L DO
          ADD edge stop_i → (L, i)     cost wait + 2   ("board")
          ADD edge (L, i) → stop_i     cost 0          ("get off")
          ADD edge (L, i) → (L, i+1)   cost ride time  ("ride")
      ENDFOR
  ENDFOR
  cache[(day, h)] ← G
  RETURN G
END
""")

P_DIJ = pc("""
FUNCTION Dijkstra(G, sources, targets, criterion)
BEGIN
  heap ← empty Min-Heap ;  best ← empty dict ;  prev ← empty dict ;  done ← empty set
  FOR EACH (s, walk_minutes) IN sources DO
      best[(s, start)] ← Cost(walk_minutes, "walk") ;  heap.push((s, start))
  ENDFOR
  WHILE heap is not empty DO
      state ← heap.pop()                         // cheapest state, O(log n)
      IF state IN done THEN CONTINUE              // old copy (lazy deletion)
      ADD state TO done
      IF state = DESTINATION THEN RETURN best[state], Rebuild(prev, state)
      (node, last) ← state
      IF node IN targets THEN
          try DESTINATION with cost best[state] + Cost(targets[node], "walk")
      ENDIF
      FOR EACH edge (node → next, minutes, kind) IN G[node] + walks[node] DO
          IF kind = walk AND last = walk THEN CONTINUE        // Rule 1
          IF kind = get_off AND last = board THEN CONTINUE    // Rule 2
          new ← best[state] + Cost(minutes, kind)
          IF (next, kind) NOT IN best OR new < best[(next, kind)] THEN
              best[(next, kind)] ← new ;  prev[(next, kind)] ← state
              heap.push((next, kind))
          ENDIF
      ENDFOR
  ENDWHILE
  RETURN "no route"
END

FUNCTION Cost(minutes, kind)          // the cost is a tuple
  IF criterion = fastest   THEN RETURN (minutes)
  IF criterion = transfers THEN RETURN (1 if kind = board else 0, minutes)
  IF criterion = walking   THEN RETURN (minutes × 4 if kind = walk else minutes)
""")

P_WC = pc("""
FUNCTION NearestToilets(lat, lon, n, only_open, care_room, only_station)
BEGIN
  list ← empty list
  FOR EACH T IN toilets DO                   // 436 records: linear search
      IF only_open AND T.status ≠ "Active" THEN CONTINUE
      IF care_room AND T.care_room ≠ "Yes" THEN CONTINUE
      IF only_station AND T.place ≠ "Transport" THEN CONTINUE
      ADD (Haversine(lat, lon, T), T) TO list
  ENDFOR
  RETURN heapq.nsmallest(n, list)           // n smallest distances, sorted
END
""")

# ------------------------------------------------------------------ document
def algo(num, title, purpose, steps, chart, pseudo, cplx, klass, note=""):
    li = "".join(f"<li>{s}</li>" for s in steps)
    return f"""
<section class="algo">
<h2><span class="tag">Algorithm {num}</span> {title}</h2>
<p class="purpose">{purpose}</p>
<div class="meta"><span><b>Class:</b> {klass}</span><span><b>Complexity:</b> {cplx}</span></div>
<h3>Steps (natural language)</h3><ol class="steps">{li}</ol>
{note}
<div class="keep"><h3>Flowchart</h3><div class="chart{' big' if num in (1, 4) else ''}">{chart}</div></div>
<div class="keep"><h3>Pseudocode</h3>{pseudo}</div>
</section>"""

css = f"""
@page {{ size: A4; margin: 16mm 15mm 18mm 15mm; }}
body {{ font-family: 'DejaVu Sans', Arial, sans-serif; color: {INK}; font-size: 10.5pt; line-height: 1.45; }}
h1 {{ font-size: 24pt; margin: 0 0 6px; }}
h2 {{ font-size: 15pt; margin: 20px 0 6px; border-bottom: 2px solid {ACC}; padding-bottom: 4px; }}
h3 {{ font-size: 11.5pt; margin: 14px 0 6px; color: {ACC}; }}
.tag {{ background: {INK}; color: #fff; font-size: 10pt; padding: 2px 8px; border-radius: 10px; vertical-align: middle; }}
.cover {{ height: 245mm; display: flex; flex-direction: column; justify-content: center; }}
.cover .sub {{ font-size: 13pt; color: {SOFT}; }}
.cover .box {{ margin-top: 30px; border-left: 4px solid {ACC}; padding: 8px 14px; background: #F7F5F0; }}
table {{ border-collapse: collapse; width: 100%; margin: 6px 0 10px; font-size: 9.5pt; }}
th, td {{ border: 1px solid #C9D2DE; padding: 5px 7px; text-align: left; vertical-align: top; }}
th {{ background: #E8EDF2; }}
.ok {{ color: #1B7F3B; font-weight: 700; }} .part {{ color: #B26A00; font-weight: 700; }} .no {{ color: #B42318; font-weight: 700; }}
.pc {{ background: #F7F5F0; border: 1px solid #E2DED5; border-radius: 6px; padding: 10px 12px; font-family: 'DejaVu Sans Mono', monospace;
       font-size: 8.6pt; line-height: 1.45; white-space: pre-wrap; page-break-inside: avoid; }}
.pc b {{ color: {ACC}; }}
.chart {{ text-align: center; page-break-inside: avoid; }}
.chart svg {{ max-width: 100%; max-height: 128mm; width: auto; height: auto; }}
.chart.big svg {{ max-height: 205mm; }}
.keep {{ break-inside: avoid; page-break-inside: avoid; }}
.algo {{ page-break-before: always; }}
.purpose {{ font-size: 11pt; }}
.meta {{ display: flex; gap: 24px; background: #E8EDF2; padding: 6px 10px; border-radius: 6px; font-size: 9.5pt; }}
.steps li {{ margin-bottom: 3px; }}
.pb {{ page-break-before: always; }}
.small {{ color: {SOFT}; font-size: 9pt; }}
"""

doc = f"""<!doctype html><html><head><meta charset="utf-8"><title>Algorithm Design Report</title><style>{css}</style></head><body>

<div class="cover">
<p class="small">ALGORITHMS COURSE · GROUP PROJECT</p>
<h1>Istanbul Public Transport Route Planner</h1>
<p class="sub">Algorithm design report: steps, flowcharts, pseudocode and analysis</p>
<div class="box">
<p><b>Group:</b> [Name Surname 1] · [Name Surname 2] · [Name Surname 3]</p>
<p><b>Data:</b> IBB Open Data Portal (GTFS: IETT buses + rail and ferries; city toilets) · OpenStreetMap (address search)</p>
<p><b>Code:</b> istanbul_rota.ipynb (Google Colab) · app.py (local Gradio app) · veri_hazirlama.py (data preparation)</p>
</div>
<p class="small" style="margin-top:30px">The report follows the 6 problem-solving steps of Chapter 4. Each algorithm is shown in the three
representation methods of Chapter 1: natural language, flowchart and pseudocode.</p>
</div>

<h2 class="pb">Step 1 · Understand the problem</h2>
<p>A person wants to travel from one place in Istanbul to another place by public transport. There is not only one “best” route,
so the user chooses a criterion.</p>
<table>
<tr><th style="width:22%">Input</th><td>Start place and destination (stop name, address or place name) · day (weekday / Saturday / Sunday) ·
hour (0–23) · criterion: <i>fastest</i>, <i>fewest transfers</i> or <i>least walking</i></td></tr>
<tr><th>Output</th><td>Step-by-step directions (line, from stop, to stop, number of stops, waiting and riding minutes, walking),
total time, number of transfers, open public toilets near the transfer points, and a map</td></tr>
<tr><th>Constraints</th><td>Real network: 14,357 stops, 3,041 lines · walking at most 2 km between two vehicles · only lines
that run in the chosen hour · an answer in a few seconds</td></tr>
<tr><th>Special cases</th><td>Same-name stops in different districts (4 × “Taşköprü”) · no route at night · start and destination very close
(walk only) · wrong or unknown place name</td></tr>
</table>
<p><b>Example (by hand):</b> Kadıköy → Taksim, weekday 08:00. M4 Kadıköy → Ayrılık Çeşmesi (2 min), walk 1 min to Marmaray,
Marmaray to Yenikapı (11 min), walk 3 min, M2 Yenikapı → Taksim (8 min) + waiting ≈ <b>32 minutes, 2 transfers</b>.</p>

<h2>Step 2 · Choose the design technique</h2>
<table>
<tr><th style="width:26%">Sub-problem</th><th style="width:30%">Technique</th><th>Why</th></tr>
<tr><td>Find a stop by name</td><td>Hashing (dict)</td><td>O(1) average search instead of scanning 14,357 names</td></tr>
<tr><td>Find stops within 2 km</td><td>Spatial hashing (grid)</td><td>Brute force needs 14,357² ≈ 206 million checks</td></tr>
<tr><td>Best route</td><td><b>Greedy</b>: Dijkstra with a Min-Heap</td><td>Costs are minutes (never negative), so the greedy choice “take the cheapest node” is always correct</td></tr>
<tr><td>Nearest toilets</td><td>Linear search + heap (nsmallest)</td><td>Only 436 records, one pass is enough</td></tr>
<tr><td>Comparison only</td><td>Brute force (naive Dijkstra, all pairs)</td><td>To measure the benefit of the heap and the grid (Step 5)</td></tr>
</table>
<p>Why not BFS? BFS counts every edge as 1. Our edges have different minutes (a metro stop is 2 minutes, a ferry is 13 minutes),
so BFS would not find the fastest route.</p>

<h2>Step 3 · Design: data structures</h2>
<table>
<tr><th style="width:26%">Structure</th><th style="width:34%">Python</th><th>Used for</th></tr>
<tr><td>Hash table</td><td><code>dict</code>: normalized name → stop ids</td><td>Stop search (Algorithm 1)</td></tr>
<tr><td>Grid</td><td><code>dict</code>: (row, col) → stops</td><td>Walking links (Algorithm 2)</td></tr>
<tr><td>Graph (adjacency list)</td><td><code>dict</code>: node → list of (next, minutes, kind, line)</td><td>Network for one day + hour (Algorithm 3)</td></tr>
<tr><td>Min-Heap</td><td><code>heapq</code> (list)</td><td>Dijkstra (Algorithm 4), nearest toilets (Algorithm 5)</td></tr>
<tr><td>Cache</td><td><code>dict</code>: (day, hour) → graph</td><td>Build a graph only once per hour</td></tr>
</table>
<p><b>Graph model.</b> Two node types: a <i>stop</i> (“I am waiting here”) and a <i>line-stop</i> (line, i) (“I am on this vehicle”).
Four edge types: <b>board</b> (stop → line-stop, cost = waiting time + 2 min transfer penalty), <b>ride</b> (line-stop → next line-stop,
cost = travel time), <b>get off</b> (line-stop → stop, cost 0), <b>walk</b> (stop → stop within 2 km, cost = distance × 1.3 ÷ 75 m/min).
Weekday 08:00: 141,273 nodes, 1,770,996 walking links.</p>
<h3>Flowchart symbols used in this report (Chapter 1)</h3>
<div class="chart">{LEGEND}</div>

<h2 class="pb">Overview · Whole system</h2>
<p>The main program uses the five algorithms below.</p>
<div class="chart big">{F_MAIN}</div>
<div class="keep"><h3>Pseudocode</h3>{P_MAIN}</div>

{algo(1, "Place search (hashing)",
      "Turns the text of the user (“kadikoy”, “İstanbul Ticaret Üniversitesi”, “Taşköprü”) into a list of places. A place has a label and a set of stops with walking minutes.",
      ["Normalize the text: lowercase, Turkish letters to ASCII (ç→c, ğ→g, ı→i, ö→o, ş→s, ü→u), remove symbols.",
       "Take all stop names in the dictionary that contain the text.",
       "Group stops with the same name if they are closer than 800 m. Give every group a label: name, nearest station, lines.",
       "Ask OpenStreetMap for addresses and places. For each result, take all stops within 2 km and their walking minutes.",
       "If there is still no result, use similar names (difflib) as the last try.",
       "Return the list. The user chooses one place."],
      F_SEARCH, P_SEARCH, "dict lookup O(1); scan of names O(N) with N ≈ 9,000 names",
      "Hashing · Linear search")}

{algo(2, "Walking links (grid hash)",
      "Finds every pair of stops that are at most 2 km apart. These pairs become walking edges for transfers.",
      ["Cut the map into squares of 2 km × 2 km. Put every stop into its square (dict key = row, column).",
       "For every stop A, look only at the stops in the same square and the 8 squares around it.",
       "Calculate the real distance (Haversine). If it is ≤ 2 km, add a walking link A → B.",
       "Walking time = distance × 1.3 (streets are not straight) ÷ 75 m per minute.",
       "Repeat for all stops. The links do not depend on the hour, so we build them only once."],
      F_GRID, P_GRID, "≈ O(n · k) with k ≈ stops in 9 cells; brute force O(n²)",
      "Spatial hashing (brute force only for comparison)",
      '<p class="small">Why is the cell size equal to the walking distance? Then the 2 km circle around A never leaves the 3 × 3 block. A test found that with 0.004° cells the cell was only 335 m wide in longitude, so some pairs were missing.</p>')}

{algo(3, "Graph for a day and an hour",
      "Builds the network for the chosen day and hour. Lines that do not run are not added. Waiting time comes from the number of trips in that hour.",
      ["For every line, read the number of departures n in hour h and p in hour h − 1 (for this day type).",
       "If n = 0 and p = 0, the line is not running: skip it.",
       "If n = 0 but p > 0, a vehicle can still be on the way: use n = 1.",
       "Waiting time = half of the gap = 60 ÷ n ÷ 2 minutes, at least 1 and at most 30.",
       "Add board, ride and get-off edges for every stop of the line.",
       "Save the graph in the cache, so the next search in this hour is fast."],
      F_GRAPH, P_GRAPH, "O(L + S) with L lines and S line-stops (130,187)",
      "Iterative (loop) algorithm")}

{algo(4, "Best route: Dijkstra with a Min-Heap",
      "Finds the cheapest route from the start stops to the target stops. The cost depends on the criterion. This is the main algorithm of the project.",
      ["Put all start stops into the Min-Heap. Their cost is the walking time from the start place (0 for a stop).",
       "Take the cheapest state from the heap. If we already finished this state, skip it (lazy deletion).",
       "If the state is the destination, rebuild the path with the <i>prev</i> table and stop.",
       "If the node is a target stop, add the destination with the cost of the last walk.",
       "Look at every edge. Rule 1: no walk after a walk. Rule 2: no get-off right after boarding.",
       "If the new cost is smaller than the best known cost of the next state, save it and push it into the heap.",
       "If the heap becomes empty, there is no route at this hour."],
      F_DIJ, P_DIJ, "O((V + E) log V)",
      "<b>Greedy</b> (always take the cheapest node)",
      """<p><b>One algorithm, three criteria.</b> The cost is a tuple. Python compares tuples from left to right:</p>
<table><tr><th>Criterion</th><th>Cost of an edge</th><th>Meaning</th></tr>
<tr><td>Fastest</td><td>(minutes)</td><td>smallest total time</td></tr>
<tr><td>Fewest transfers</td><td>(1 if board else 0, minutes)</td><td>first fewer vehicles, then less time</td></tr>
<tr><td>Least walking</td><td>(minutes × 4 if walk else minutes)</td><td>walking is 4 times more expensive</td></tr></table>
<p class="small">The state is (node, kind of the last edge). This is how Rule 1 and Rule 2 can be checked.</p>""")}

{algo(5, "Nearest public toilets",
      "Finds the n nearest public toilets to a position, with filters. It is also used to list open toilets within 300 m of the transfer points of a route.",
      ["For every toilet, check the filters: open, with a care room, at a station.",
       "Calculate the distance from the position (Haversine) and put (distance, toilet) into a list.",
       "Take the n smallest distances with heapq.nsmallest. The result is sorted by distance.",
       "Route to a toilet: use the toilet as a destination with the “least walking” criterion. If walking directly is better, show only walking."],
      F_WC, P_WC, "O(T log n) with T = 436 toilets",
      "Linear search + heap")}

<h2 class="pb">Step 4 · Prove that it is correct</h2>
<p>One wrong test shows a bug; many passing tests make us confident. The notebook has 10 automatic tests:</p>
<table>
<tr><th style="width:5%">#</th><th>Test</th><th style="width:16%">Result</th></tr>
<tr><td>1–3</td><td>Small graphs with known answers: fastest, unreachable target, fewest transfers</td><td class="ok">pass</td></tr>
<tr><td>4</td><td>Least walking chooses a 15-minute ride instead of a 10-minute walk</td><td class="ok">pass</td></tr>
<tr><td>5</td><td>Our Dijkstra = networkx Dijkstra on the real rail + ferry + metrobus network, 20 random routes</td><td class="ok">20 / 20</td></tr>
<tr><td>6</td><td>Real routes: no two walks in a row, every ride has ≥ 1 stop, least walking walks ≤ fastest</td><td class="ok">pass</td></tr>
<tr><td>7</td><td>Hour: at 03:00 the M2 metro is not used, at 08:00 it is; metrobus runs at night</td><td class="ok">pass</td></tr>
<tr><td>8</td><td>Same-name stops have different labels; unknown name gives a message, not a crash</td><td class="ok">pass</td></tr>
<tr><td>9–10</td><td>Nearest toilets are sorted and filtered; a very close toilet gives “walk only”</td><td class="ok">pass</td></tr>
</table>
<p><b>Bugs that the tests found:</b> (1) grid cells were 335 m wide instead of 400 m, so walking links were missing;
(2) the algorithm used “get on, get off” to walk twice (Rule 2 added); (3) “Galata Kulesi” matched “Ali Kul Lisesi”
(similar-name search is now only the last try).</p>

<h2>Step 5 · Analyze the algorithm (Chapter 7)</h2>
<table>
<tr><th style="width:26%">Algorithm</th><th style="width:18%">Best case</th><th style="width:22%">Worst case</th><th>Average / measured</th></tr>
<tr><td>1 · Place search</td><td>O(1) exact name</td><td>O(N) scan + network call</td><td>a few ms (+ OpenStreetMap ≈ 0.5 s)</td></tr>
<tr><td>2 · Walking links</td><td>Ω(n)</td><td>O(n²) if all stops in one cell</td><td>≈ O(n): 1.4 s for 14,357 stops (brute force ≈ 67 s)</td></tr>
<tr><td>3 · Graph</td><td colspan="2">Θ(L + S), always all lines</td><td>≈ 1 s once per hour (then cached)</td></tr>
<tr><td>4 · Dijkstra</td><td>Ω(1): target next to start</td><td>O((V + E) log V): no route, all nodes</td><td>0.1 – 4 s; 0.2 s for Kadıköy → Taksim</td></tr>
<tr><td>5 · Toilets</td><td colspan="2">Θ(T log n), always all 436</td><td>&lt; 1 ms</td></tr>
</table>
<h3>Measurement 1: Min-Heap vs simple list in Dijkstra</h3>
<table>
<tr><th>Route</th><th>Simple list O(V²)</th><th>Min-Heap O((V+E) log V)</th><th>Faster</th></tr>
<tr><td>Avcılar → Zincirlikuyu</td><td>0.00 s</td><td>0.000 s</td><td>2×</td></tr>
<tr><td>Bakırköy → Kartal</td><td>0.26 s</td><td>0.014 s</td><td>18×</td></tr>
<tr><td>Kadıköy → Taksim</td><td>7.67 s</td><td>0.112 s</td><td>68×</td></tr>
<tr><td>Taksim → Bostancı</td><td>46.52 s</td><td>0.261 s</td><td>179×</td></tr>
</table>
<h3>Measurement 2: growth of the walking-link search</h3>
<table>
<tr><th>Stops (n)</th><th>Brute force O(n²)</th><th>Grid ≈ O(n)</th></tr>
<tr><td>500</td><td>0.06 s</td><td>0.003 s</td></tr><tr><td>1,000</td><td>0.26 s</td><td>0.023 s</td></tr>
<tr><td>2,000</td><td>1.10 s</td><td>0.038 s</td></tr><tr><td>4,000</td><td>5.19 s</td><td>0.138 s</td></tr>
</table>
<p>When n is two times bigger, brute force is about 4–5 times slower: this is the sign of O(n²).</p>

<h2 class="pb">Step 6 · Write the code</h2>
<table>
<tr><th style="width:28%">File</th><th>Content</th></tr>
<tr><td>veri_hazirlama.py</td><td>Data cleaning: 175 MB raw GTFS → 1.4 MB network (encoding fix, coordinate fix, estimated bus times, trips per hour)</td></tr>
<tr><td>istanbul_rota.ipynb</td><td>Google Colab notebook: all algorithms, 10 tests, measurements, Gradio interface</td></tr>
<tr><td>app.py</td><td>The same code as a local app: <code>python app.py</code> opens the interface in the browser</td></tr>
<tr><td>istanbul_ag.zip</td><td>stops, lines, line stops, trips per hour, city toilets</td></tr>
</table>

<h2>Properties of a good algorithm (Chapter 1) · checked for Dijkstra</h2>
<table>
<tr><th style="width:22%">Property</th><th>How our algorithm has it</th></tr>
<tr><td>Input / Output</td><td>Input: graph, start stops, target stops, criterion. Output: cost and path, or “no route”.</td></tr>
<tr><td>Clarity</td><td>Every step is one clear operation (pop, compare, push). See the pseudocode.</td></tr>
<tr><td>Correctness</td><td>All costs are ≥ 0, so the greedy choice is safe. 20 / 20 equal to networkx.</td></tr>
<tr><td>Finiteness</td><td>Every state is finished at most once, and the number of states is finite (nodes × 5 edge kinds). So the loop ends.</td></tr>
<tr><td>Effectiveness</td><td>Only basic operations: addition, comparison, heap push and pop.</td></tr>
<tr><td>Efficiency</td><td>O((V + E) log V); 179 × faster than the simple list version on a long route.</td></tr>
<tr><td>Generality</td><td>Works for any start, destination, day, hour and criterion; also for toilets as destinations.</td></tr>
</table>

<h2>Limitations</h2>
<ul>
<li>Bus times are estimated (distance ÷ average speed); the data has no time at each stop. There is no traffic.</li>
<li>The hour uses trips per hour, not the exact timetable (“catch the bus at 08:12”).</li>
<li>Rail data is until 2024; new lines can be missing. Wheelchair data only for 94 stations; no elevator data.</li>
<li>Walking uses straight-line distance × 1.3, not real streets. Address search and the map need the internet.</li>
</ul>
</body></html>"""

open("/tmp/claude-0/-home-user/7db0ee4d-a6d4-5bc7-b7de-e3e4820ef40e/scratchpad/report/report.html", "w", encoding="utf-8").write(doc)
print("html ok")
