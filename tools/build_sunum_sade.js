// GitGez (simple version) — presentation for Canva editing. Every element is a plain, editable object on the slide.
const pptxgen = require("pptxgenjs");
const pres = new pptxgen();
pres.layout = "LAYOUT_16x9";           // 10 x 5.625 in
pres.title = "GitGez — Istanbul Route and Tour Planner";
pres.author = "Muhammed Emin Küçükşahin, Emir Yılmaz, Fatih Mehmet Miçillioğlu";
pres.theme = { headFontFace: "Arial", bodyFontFace: "Arial" };

const INK = "14213D", SOFT = "4A5568", ACC = "C2410C", ACC_SOFT = "FBE3D6", LIGHT = "FFFFFF", ALT = "E8EDF2",
      MID = "8A97AB", ON_DARK = "F7F5F0", ON_DARK_SOFT = "C3CEDD", CARD = "FFFFFF", CARD_ALT = "F7F9FB";
const F = "Arial", MONO = "Courier New";

let pageNo = 0;
function slide(kind, who, notes) {
  const s = pres.addSlide();
  pageNo += 1;
  s.background = { color: kind === "dark" ? INK : kind === "alt" ? ALT : LIGHT };
  s._dark = kind === "dark"; s._alt = kind === "alt";
  if (who) s.addText(who, { x: 0.6, y: 5.17, w: 6, h: 0.28, fontFace: F, fontSize: 10, color: s._dark ? ON_DARK_SOFT : MID, margin: 0, isTextBox: true, objectName: "Footer" });
  s.addText(String(pageNo), { x: 8.9, y: 5.17, w: 0.5, h: 0.28, fontFace: F, fontSize: 10, align: "right", color: s._dark ? ON_DARK_SOFT : MID, margin: 0, isTextBox: true, objectName: "Page number" });
  if (notes) s.addNotes(notes);
  return s;
}
function head(s, eyebrow, title) {
  s.addText(eyebrow, { x: 0.6, y: 0.42, w: 8.8, h: 0.26, fontFace: F, fontSize: 11, bold: true, charSpacing: 1.5, color: s._dark ? "F4A37E" : ACC, margin: 0, isTextBox: true, objectName: "Eyebrow" });
  s.addText(title, { x: 0.6, y: 0.7, w: 8.8, h: 0.62, fontFace: F, fontSize: 28, bold: true, color: s._dark ? ON_DARK : INK, margin: 0, isTextBox: true, objectName: "Title" });
}
function card(s, x, y, w, h, title, body, opt = {}) {
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h, rectRadius: 0.12, fill: { color: s._alt ? CARD_ALT : CARD },
    line: { color: s._dark ? CARD : "DDE3EA", width: 0.75 }, shadow: { type: "outer", color: "000000", opacity: 0.08, blur: 6, offset: 2, angle: 90 }, objectName: "Card" });
  const runs = [];
  if (title) runs.push({ text: title, options: { fontSize: opt.tsize || 16, bold: true, color: opt.tcolor || INK, breakLine: true, paraSpaceAfter: 6 } });
  body.forEach((b, i) => runs.push({ text: b, options: { fontSize: opt.size || 13, color: SOFT, breakLine: i < body.length - 1, paraSpaceAfter: 5 } }));
  s.addText(runs, { x: x + 0.2, y: y + 0.15, w: w - 0.4, h: h - 0.3, fontFace: F, valign: "top", margin: 0, isTextBox: true, objectName: "Card text" });
}
function placeholder(s, x, y, w, h, kind, label) {
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h, rectRadius: 0.1, fill: { color: "F3F6FA" },
    line: { color: ACC, width: 1.5, dashType: "dash" }, objectName: `${kind} placeholder` });
  s.addText([{ text: kind, options: { fontSize: 16, bold: true, color: ACC, breakLine: true } },
             { text: label, options: { fontSize: 12, color: SOFT, breakLine: true } },
             { text: "Put the image here and delete this box", options: { fontSize: 10, color: MID } }],
    { x, y, w, h, fontFace: F, align: "center", valign: "middle", margin: 0.1, isTextBox: true, objectName: `${kind} placeholder text` });
}
function table(s, rows, x, y, w, colW, opt = {}) {
  const fs = opt.size || 13;
  const data = rows.map((r, i) => r.map((c, j) => ({ text: String(c), options: {
    bold: i === 0, color: i === 0 ? INK : SOFT, fontFace: F, fontSize: fs, align: (opt.right || []).includes(j) ? "right" : "left",
    fill: { color: i === 0 ? (s._alt ? "D5DEE8" : ALT) : (s._alt ? CARD_ALT : CARD) }, valign: "middle",
    border: [{ type: "none" }, { type: "none" }, { pt: 0.75, color: "DDE3EA" }, { type: "none" }] } })));
  s.addTable(data, { x, y, w, colW, rowH: opt.rowH || 0.36, margin: [0.04, 0.1, 0.04, 0.1], objectName: "Table" });
}
const big = (s, x, y, w, num, label) => {
  s.addText(num, { x, y, w, h: 0.75, fontFace: F, fontSize: 40, bold: true, color: ON_DARK, margin: 0, isTextBox: true, objectName: "Stat" });
  s.addText(label, { x, y: y + 0.78, w, h: 0.5, fontFace: F, fontSize: 14, color: ON_DARK_SOFT, margin: 0, isTextBox: true, objectName: "Stat label" });
};
const text = (s, t, x, y, w, h, o = {}) => s.addText(t, Object.assign({ x, y, w, h, fontFace: F, fontSize: 14, color: s._dark ? ON_DARK_SOFT : SOFT, margin: 0, valign: "top", isTextBox: true }, o));
const code = (s, lines, x, y, w, h, size = 11) => {
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h, rectRadius: 0.1, fill: { color: INK }, line: { color: INK }, objectName: "Code box" });
  s.addText(lines.map((l, i) => ({ text: l, options: { breakLine: i < lines.length - 1, color: ON_DARK } })),
    { x: x + 0.15, y: y + 0.1, w: w - 0.3, h: h - 0.2, fontFace: MONO, fontSize: size, valign: "top", margin: 0, isTextBox: true, objectName: "Code" });
};

// ---------------- 1. Cover
{
  const s = slide("dark", null, 'Emin starts. "Hello everyone. Our project is GitGez. \'Git\' means go, \'gez\' means travel around. The app does two things. First, it finds the best route in Istanbul by public transport. Second, it plans a tour: which places to visit, and in which order, in a limited time. We will focus on the algorithms. Emir will explain the route algorithms, and Fatih will explain the tour algorithms and show the app."');
  text(s, "ALGORITHMS COURSE · GROUP PROJECT", 0.6, 0.6, 8.8, 0.3, { fontSize: 11, bold: true, color: "F4A37E", charSpacing: 1.5 });
  text(s, "GitGez", 0.6, 1.05, 8.8, 1.0, { fontSize: 60, bold: true, color: ON_DARK });
  text(s, "Istanbul route and tour planner: find the best route, and plan the best tour in a limited time.", 0.6, 2.15, 7.8, 0.75, { fontSize: 18, color: ON_DARK_SOFT });
  text(s, "Dijkstra · Backtracking · Greedy · Brute force · Hash tables · Heaps", 0.6, 3.0, 8.8, 0.3, { fontSize: 12 });
  [["Muhammed Emin Küçükşahin", 0.6, 3.0], ["Emir Yılmaz", 3.85, 1.8], ["Fatih Mehmet Miçillioğlu", 5.9, 3.0]].forEach(([n, x, w]) =>
    text(s, n, x, 4.45, w, 0.35, { fontSize: 14, bold: true, color: ON_DARK }));
  text(s, "İstanbul Ticaret Üniversitesi", 0.6, 4.85, 5, 0.3, { fontSize: 11 });
}
// ---------------- 2. Problem
{
  const s = slide("light", "Emin · Problem", "This is step 1 from Chapter 4: understand the problem. We have two problems. The route problem: go from A to B. The tour problem: you have, for example, five hours in Fatih. Which places should you see, and in which order? The route problem is a shortest path problem. The tour problem is like the knapsack problem from Chapter 1, with an order.");
  head(s, "1 · UNDERSTAND THE PROBLEM", "Two problems, one app");
  card(s, 0.6, 1.6, 4.3, 2.75, "🧭  Route", ["Input: from, to, day, hour, weather", "Output: the best route and one alternative, step by step, with a map", "Algorithm: Dijkstra + Min-Heap"]);
  card(s, 5.1, 1.6, 4.3, 2.75, "🧳  Tour (beta)", ["Input: start place, region, date, free hours", "Output: which places to visit and in which order", "Algorithm: backtracking + branch and bound"]);
  text(s, "Extra: walking on real streets with hills · weather and traffic · nearest public toilets", 0.6, 4.6, 8.8, 0.3, { fontSize: 13 });
}
// ---------------- 3. Data
{
  const s = slide("dark", "Emin · Data", "All data is real. The transport data comes from the Istanbul municipality, IBB. It was not clean: broken coordinates, broken Turkish letters, and no bus times between stops. We fixed these problems. The streets come from OpenStreetMap. We added a height for every street part from a satellite height map, so we know where the hills are. We also use one month of real traffic data from IBB, 1.76 million measurements, and 57 places to visit with opening hours.");
  head(s, "REAL DATA · NOT A TOY EXAMPLE", "The real city");
  big(s, 0.6, 1.75, 2.1, "14,357", "stops, 3,041 lines");
  big(s, 2.85, 1.75, 2.1, "1.28 M", "street parts with slope");
  big(s, 5.1, 1.75, 2.1, "1.76 M", "traffic measurements");
  big(s, 7.35, 1.75, 2.1, "57", "places to visit");
  text(s, "IBB open data (transport, 436 toilets, hourly traffic) · OpenStreetMap streets · Copernicus height map · Open-Meteo weather · We cleaned 175 MB of messy data.", 0.6, 3.95, 8.8, 0.7, { fontSize: 14 });
}
// ---------------- 4. Graph model
{
  const s = slide("light", "Emin · Model", "We use two graphs. The first one is the transport graph. A stop node means: I am waiting. A line-stop node means: I am on this vehicle. So the algorithm knows the difference between staying on the metro and changing to another vehicle. The board edge costs the waiting time. The second graph is the street graph. Its edges are real streets, and the cost is the walking time, which depends on the hill.");
  head(s, "2 · MODEL: TWO GRAPHS", "Waiting at a stop ≠ sitting in a vehicle");
  const nodes = [["Stop\nYenikapı", true], ["On M2\nYenikapı", false], ["On M2\nTaksim", false], ["Stop\nTaksim", true], ["Stop\nTaksim (bus)", true]];
  const edges = [["board", "waiting"], ["ride", "travel time"], ["get off", "0 min"], ["walk", "on streets"]];
  nodes.forEach(([t, stop], i) => {
    const x = 0.6 + i * 1.84;
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y: 1.65, w: 1.3, h: 0.8, rectRadius: 0.12, fill: { color: stop ? INK : ACC_SOFT }, line: { color: stop ? INK : ACC, width: 1.5 }, objectName: "Node" });
    text(s, t, x, 1.65, 1.3, 0.8, { fontSize: 11, bold: true, align: "center", valign: "middle", color: stop ? ON_DARK : INK });
    if (i < edges.length) {
      s.addShape(pres.shapes.LINE, { x: x + 1.32, y: 2.05, w: 0.5, h: 0, line: { color: MID, width: 1.5, endArrowType: "triangle" }, objectName: "Edge" });
      text(s, edges[i][0], x + 1.18, 1.45, 0.8, 0.22, { fontSize: 10, bold: true, color: ACC, align: "center" });
      text(s, edges[i][1], x + 1.18, 2.47, 0.8, 0.22, { fontSize: 9, align: "center" });
    }
  });
  card(s, 0.6, 3.05, 4.3, 1.85, "Transport graph", ["Stops and “on a vehicle” nodes. 4 edge types: board, ride, get off, walk. Cost = minutes."]);
  card(s, 5.1, 3.05, 4.3, 1.85, "Street graph", ["462,198 crossings, 1.28 M street parts. Cost = walking minutes uphill or downhill."]);
}
// ---------------- 5. System overview (Algorithm 1 flowchart)
{
  const s = slide("light", "Emin · Design",
    "This flowchart shows the whole system. We use the standard symbols from Chapter 1. First the user chooses a tab: Route, Toilet or Tour. Each box is one step, and we will explain the algorithms now. Now Emir will explain the route algorithms.\n\n" +
    "FOR THE FLOWCHART (Algorithm 1 · System overview, docs/SADE_ALGORITMALAR.md):\n" +
    "START → user chooses a tab\nRoute: read from, to, day, hour, weather, sorting → find places (hash table) → set weather and traffic → graph for this day and hour → walking time to nearby stops → best route = Dijkstra → alternative = ban lines, Dijkstra again → show map + steps\n" +
    "Toilet: read place → nearest 5 toilets (heap) → walking path to the nearest\n" +
    "Tour: read start, region, date, start hour, free hours → open places, 12 best (heap) → travel time matrix (Dijkstra) → best plan = backtracking + branch and bound → show plan\nEND");
  head(s, "3 · DESIGN · FLOWCHART", "How the system works");
  text(s, [
    { text: "Route", options: { bold: true, color: INK, fontSize: 15, breakLine: true } },
    { text: "Place search — hash table", options: { bullet: { type: "number" }, breakLine: true } },
    { text: "Walking on streets — Dijkstra", options: { bullet: { type: "number" }, breakLine: true } },
    { text: "Best route — Dijkstra + heap", options: { bullet: { type: "number" }, breakLine: true } },
    { text: "1 alternative — ban lines, search again", options: { bullet: { type: "number" }, breakLine: true } },
    { text: "Tour (beta)", options: { bold: true, color: INK, fontSize: 15, breakLine: true } },
    { text: "Backtracking + branch and bound", options: { bullet: { type: "number", numberStartAt: 5 }, breakLine: true } },
    { text: "Toilet", options: { bold: true, color: INK, fontSize: 15, breakLine: true } },
    { text: "Nearest toilets — heap", options: { bullet: { type: "number", numberStartAt: 6 } } },
  ], 0.6, 1.55, 3.7, 3.4, { fontSize: 13, paraSpaceAfter: 4 });
  placeholder(s, 4.55, 1.45, 4.85, 3.55, "FLOWCHART", "Algorithm 1 · System overview");
}
// ---------------- 6. Place search
{
  const s = slide("light", "Emir · Algorithms", "Emir starts. First problem: find the place. The user can write the name in different ways, for example with or without Turkish letters. So we normalize the name and put it in a Python dictionary. A dictionary is a hash table, so the search is O(1). For addresses, like İstanbul Ticaret Üniversitesi, we use the free OpenStreetMap search. One more problem: there are four stops called Taşköprü in different parts of the city. So we show the nearest station next to each one.");
  head(s, "PLACE SEARCH · HASH TABLE", "Which “Taşköprü”?");
  code(s, ['normalize("KADIKÖY") → "kadikoy"', 'index["kadikoy"] → 13 stops    O(1)'], 0.6, 1.55, 4.6, 0.8, 12);
  text(s, [
    { text: "Stop name: a Python dict (hash table)", options: { breakLine: true } },
    { text: "Address or place: OpenStreetMap search → stops you can walk to", options: { breakLine: true } },
    { text: "Typing mistake: “üsküdr” → Üsküdar" } ], 0.6, 2.6, 4.6, 1.8, { fontSize: 14, paraSpaceAfter: 8 });
  card(s, 5.5, 1.55, 3.9, 3.0, "4 stops named “TAŞKÖPRÜ”", ["🚏 near Taşköprü (Pendik)", "🚏 near Alibeyköy", "🚏 near Parseller", "🚏 15 km from Beykoz", "We group stops by location and show the nearest station."]);
}
// ---------------- 7. Streets
{
  const s = slide("alt", "Emir · Algorithms", "In Istanbul, a short walk can be very hard because of hills. So we do not use straight lines. We walk on the real street graph. Every street part has a slope from the height map. Tobler's function gives the walking speed for a slope. Then we run Dijkstra on the street graph, with the scipy library. A grid hash first finds the stops that are close enough, so we do not search the whole city.");
  head(s, "WALKING ON REAL STREETS", "Istanbul has hills");
  text(s, [
    { text: "Tobler’s hiking function: ", options: { bold: true, color: INK } },
    { text: "walking speed depends on the slope. Flat: 4.5 km/h. 10 % uphill: about 3.3 km/h.", options: { breakLine: true } },
    { text: "Dijkstra on the street graph ", options: { bold: true, color: INK } },
    { text: "(462,198 crossings) finds the walking time from the start to the stops near it.", options: { breakLine: true } },
    { text: "Grid (spatial hashing): ", options: { bold: true, color: INK } },
    { text: "the city in 2 km squares; we look only at 9 squares, not at 14,357 stops." } ], 0.6, 1.55, 5.0, 3.3, { fontSize: 14, paraSpaceAfter: 12 });
  card(s, 5.9, 1.55, 3.5, 1.45, "One walking profile", ["Normal walking with Tobler time: 854,799 stop-to-stop links."]);
  card(s, 5.9, 3.2, 3.5, 1.45, "18 %", ["of all street parts are steeper than 8 %."], { tsize: 22, tcolor: ACC });
}
// ---------------- 8. Dijkstra in 4 steps
{
  const s = slide("light", "Emir · Algorithms", "Our main algorithm is Dijkstra. We did not see it in class, so I will explain it. We start with cost zero. We always take the cheapest node from a Min-Heap. We saw the Min-Heap in Chapter 3. Then we check its neighbours. If we find a cheaper way, we update the cost. All our costs are minutes, and minutes are never negative. This is why Dijkstra gives the correct answer.");
  head(s, "SHORTEST PATH · DIJKSTRA + MIN-HEAP", "Dijkstra’s algorithm in 4 steps");
  text(s, [
    "The start costs 0. Put it in a Min-Heap.",
    "Take the cheapest node from the heap. Its best cost is now final.",
    "Look at its neighbours. Is this way cheaper? Then update and add to the heap.",
    "Stop when the destination comes out of the heap." ].map((t, i) => ({ text: t, options: { bullet: { type: "number" }, breakLine: i < 3 } })),
    0.6, 1.6, 4.9, 3.2, { fontSize: 15, color: INK, paraSpaceAfter: 12 });
  card(s, 5.8, 1.55, 3.6, 1.5, "Why is it correct?", ["No cost is negative. So nobody can find a cheaper way to a node later."]);
  card(s, 5.8, 3.25, 3.6, 1.5, "Why a heap?", ["The cheapest node is always on top. Taking it costs only O(log n)."]);
}
// ---------------- 9. Dijkstra flowchart + pseudocode (Algorithm 2)
{
  const s = slide("light", "Emir · Algorithms",
    "Here is the same Dijkstra algorithm as a flowchart and as pseudocode. Dijkstra is a greedy algorithm, from Chapter 1: at every step it takes the best choice now, the cheapest state. Usually greedy algorithms are not always optimal. But here it is optimal, because all costs are minutes, and minutes are never negative. The loop always ends, because every state is finished only once. This is the finiteness property.\n\n" +
    "PSEUDOCODE (Algorithm 2, docs/SADE_ALGORITMALAR.md):\n" +
    "FUNCTION Dijkstra(graph, sources, targets, criterion, banned)\n  heap ← every start stop with its walking time\n  WHILE heap is not empty DO\n    (cost, state) ← heap.pop()\n    IF state IN done THEN CONTINUE   // lazy deletion\n    add state to done\n    IF state = DESTINATION THEN RETURN cost, RebuildPath(state)\n    IF node is a target stop THEN heap.push(cost + walk to the end, DESTINATION)\n    FOR EACH edge (node → next, minutes, kind, line) DO\n      IF kind = walk AND last = walk THEN CONTINUE      // rule 1\n      IF kind = alight AND last = board THEN CONTINUE   // rule 2\n      IF kind = board AND line IN banned THEN CONTINUE\n      new ← cost + EdgeCost(minutes, kind, criterion)\n      IF new < best[next] THEN best[next] ← new; previous[next] ← state; heap.push(new, next)\n  RETURN \"no route\"");
  head(s, "DIJKSTRA · FLOWCHART + PSEUDOCODE", "Algorithm 2: Dijkstra + Min-Heap");
  placeholder(s, 0.6, 1.45, 4.3, 3.25, "FLOWCHART", "Algorithm 2 · Dijkstra + Min-Heap");
  placeholder(s, 5.1, 1.45, 4.3, 3.25, "PSEUDOCODE", "Algorithm 2 · Dijkstra + Min-Heap");
  text(s, [{ text: "Class: ", options: { bold: true, color: INK } }, { text: "greedy   ·   " }, { text: "Complexity: ", options: { bold: true, color: INK } }, { text: "O((V + E) log V)   ·   " }, { text: "Ends: ", options: { bold: true, color: INK } }, { text: "every state is finished once" }],
    0.6, 4.8, 8.8, 0.3, { fontSize: 12 });
}
// ---------------- 10. Criteria and rules
{
  const s = slide("alt", "Emir · Algorithms", "We have three sorting options but only one Dijkstra. We only change the cost. For fewest transfers, the cost is a pair: number of vehicles first, then minutes. Python compares tuples from left to right, so fewer vehicles always wins. We also found that the algorithm can cheat. It walked for 40 minutes from stop to stop, or it got on a bus and got off at the same stop. So we added two rules. To check them, the state is the node and the type of the last edge.");
  head(s, "THREE SORTING OPTIONS, TWO RULES", "One Dijkstra, many questions");
  code(s, ["fastest         → (minutes,)", "fewest transfers → (vehicles, minutes)", "least walking   → (ride + 4 × walking,)"], 0.6, 1.55, 4.9, 1.2, 12);
  text(s, "The cost is a tuple. Python compares tuples from left to right: (1, 74) < (2, 38).", 0.6, 2.95, 4.9, 0.8, { fontSize: 14 });
  card(s, 5.8, 1.55, 3.6, 1.5, "Rule 1: no walk after walk", ["Otherwise the algorithm walks from stop to stop for 40 minutes."]);
  card(s, 5.8, 3.25, 3.6, 1.5, "Rule 2: no “get on, get off”", ["Otherwise it gets on a bus and off at the same stop, to walk again."]);
}
// ---------------- 11. Alternative
{
  const s = slide("light", "Emir · Algorithms", "People like to choose, so we show one alternative. After we find the best route, we ban its lines and run Dijkstra again. Then we get a route that really uses other vehicles. Buses with the same stops, like 34, 34A and 34AS, count as one line, so we ban them together. For example from Kadıköy to Taksim, the best route is bus, Marmaray and M2, 32 minutes. The alternative is the ferry, then the tram and the funicular, 47 minutes. If the alternative is more than 30 minutes slower, we do not show it.");
  head(s, "MORE THAN ONE ROUTE", "Alternative: ban the lines, search again");
  text(s, [
    "Find the best route with Dijkstra.",
    "Ban its lines (and lines with the same stops, like 34 / 34A / 34AS).",
    "Run Dijkstra again → a route with really different vehicles.",
    "Show it only if it is at most 30 min slower." ].map((t, i) => ({ text: t, options: { bullet: { type: "number" }, breakLine: i < 3 } })),
    0.6, 1.6, 5.0, 3.0, { fontSize: 15, color: INK, paraSpaceAfter: 12 });
  card(s, 5.9, 1.55, 3.5, 1.5, "32 min", ["Kadıköy → Taksim, weekday 08:00", "Bus 12A → Marmaray → M2"], { tsize: 24, tcolor: ACC });
  card(s, 5.9, 3.25, 3.5, 1.5, "47 min", ["Alternative", "Ferry → T1 → F1"], { tsize: 24, tcolor: ACC });
}
// ---------------- 12. Day and hour
{
  const s = slide("alt", "Emir · Algorithms", "The data has the start time of every trip. So for every line we count how many trips start in each hour, for weekdays, Saturday and Sunday. When the user chooses an hour, we build the graph for that hour. Lines with no trips are not in the graph. At 3 in the morning only 82 lines are running. The algorithm cannot use the metro, so it finds the 24-hour metrobus and a night bus by itself.");
  head(s, "DAY AND HOUR", "At 03:00 there is no metro");
  table(s, [["Kadıköy → Taksim", "Lines running", "Fastest route found", "Time"],
            ["Weekday 08:00", "2,924", "Bus 12A → Marmaray → M2", "32 min"],
            ["Sunday 23:00", "1,526", "Same route, longer waiting", "38 min"],
            ["Weekday 03:00", "82", "Metrobus 34AS → night bus 25G", "83 min"]],
        0.6, 1.6, 8.8, [2.2, 1.6, 3.8, 1.2], { right: [1, 3], rowH: 0.45, size: 14 });
  text(s, "For every line, we count the trips per hour. No trip → we do not use the line. Few trips → longer waiting (half of the time between two trips).", 0.6, 4.0, 8.8, 0.7, { fontSize: 14 });
}
// ---------------- 13. Weather and traffic
{
  const s = slide("light", "Emir · Algorithms", "We added weather and traffic. The algorithm does not change. Only the edge costs change. When it rains, walking takes longer, so we multiply walking minutes by 1.15. In a storm, ferries may stop, so we remove the ferry edges from the graph. For buses, we use one month of real IBB traffic data, 1.76 million measurements: we compare the speed at this hour with the normal speed in that area. Example: from Kadıköy to Ataşehir at 6 pm, without traffic the best route is M4 and bus 19E, 34 minutes. With traffic the algorithm finds a new route with more metro, 38 minutes. All costs are still positive, so Dijkstra is still correct.");
  head(s, "WEATHER AND TRAFFIC", "Rain and rush hour change the costs");
  table(s, [["Condition", "Edge we change", "New cost"],
            ["🌧 Rain", "walk", "minutes × 1.15"],
            ["❄️ Snow", "walk", "minutes × 1.5"],
            ["🌬 Storm (wind ≥ 70 km/h)", "ferry ride", "edge removed"],
            ["🚦 Rush hour", "bus ride", "minutes × traffic factor (0.7 – 2.0)"]],
        0.6, 1.5, 8.8, [3.0, 2.2, 3.6], { rowH: 0.4, size: 13 });
  text(s, [{ text: "Real data, January 2025: ", options: { bold: true, color: INK } },
           { text: "Kadıköy → Ataşehir, weekday 18:00 · without traffic 34 min (M4 + bus 19E) · with traffic 38 min, new route M4 + M8 + bus 10" }],
    0.6, 3.75, 8.8, 0.6, { fontSize: 13 });
  text(s, "All costs stay positive → Dijkstra is still correct.", 0.6, 4.5, 8.8, 0.3, { fontSize: 13, bold: true, color: ACC });
}
// ---------------- 14. Tour = knapsack
{
  const s = slide("dark", "Fatih · Tour", "Fatih starts. The tour problem is like the 0-1 knapsack problem from Chapter 1. The knapsack is your free time. The items are the places. Every place has a weight, the time it needs, and a value, its score. But there is one big difference: the order matters. The travel time depends on where you come from. We also have real rules: opening hours, closed days, Friday prayer for mosques, and the last entry time. In the app this mode is still a beta version.");
  head(s, "4 · TOUR MODE · CHAPTER 1: KNAPSACK", "A knapsack, but the order matters");
  card(s, 0.6, 1.6, 2.75, 2.2, "Time", ["KNAPSACK", "The bag = your free time (for example 5 hours)"], { tsize: 24, tcolor: ACC });
  card(s, 3.62, 1.6, 2.75, 2.2, "Places", ["ITEMS", "Weight = travel + waiting + queue + visit time"], { tsize: 24, tcolor: ACC });
  card(s, 6.65, 1.6, 2.75, 2.2, "Score", ["VALUE", "Popularity, history, view, fun, culture"], { tsize: 24, tcolor: ACC });
  text(s, "Rules: opening hours · closed days (Topkapı: Tuesday) · Friday prayer · last entry", 0.6, 4.15, 8.8, 0.5, { fontSize: 15, color: ON_DARK_SOFT });
}
// ---------------- 15. Three classes
{
  const s = slide("light", "Fatih · Tour", "We solved the tour problem with three algorithm classes from Chapter 1. Greedy is fast but short-sighted. Brute force is correct but too slow. Backtracking is in the middle. It builds the plan step by step and goes back when a path is bad. The important part is pruning. For every branch, we calculate an optimistic upper bound: we fill the remaining time greedily, even with half places. If even this optimistic value cannot beat the best plan, we cut the branch. Because the bound is never too small, we never cut the best plan.");
  head(s, "THREE ALGORITHM CLASSES FROM CHAPTER 1", "Greedy, backtracking, brute force");
  card(s, 0.6, 1.55, 2.75, 2.55, "Greedy", ["Always go to the place with the best score ÷ time. Never go back.", "Fast, but can miss the best plan."]);
  card(s, 3.62, 1.55, 2.75, 2.55, "Backtracking + branch and bound", ["Try a place, go deeper, go back and try another.", "Prune: if even the best case of this branch cannot win, stop."], { tcolor: ACC });
  card(s, 6.65, 1.55, 2.75, 2.55, "Brute force", ["Try every order of every subset of places.", "Always correct, but 14 places → 237 billion orders."]);
  text(s, [{ text: "Upper bound for pruning ", options: { bold: true, color: INK } }, { text: "= fill the rest of the time greedily, with fractions of places (fractional knapsack). It is optimistic, so pruning is safe." }], 0.6, 4.35, 8.8, 0.6, { fontSize: 13 });
}
// ---------------- 16. Backtracking pseudocode
{
  const s = slide("light", "Fatih · Tour", "Here is backtracking as pseudocode. The function calls itself, so it is recursive. First, we save the plan if it is the best so far. Then we check the bound. If we cannot win, we go back. Otherwise, we try every next place that fits: there is enough time and the place is open. In the worst case this is n factorial, like brute force. But pruning cuts most branches, so in practice we open only a few thousand nodes.");
  head(s, "BACKTRACKING · PSEUDOCODE", "Search, prune, go back");
  code(s, ["FUNCTION Search(last, time, plan, value)",
           "  IF value > best.value THEN best ← plan",
           "  IF value + UpperBound(...) ≤ best.value THEN",
           "    RETURN                       // prune",
           "  FOR EACH place j not in plan DO",
           "    (enter, leave) ← Visit(j, time + T[last][j])",
           "    IF j fits THEN",
           "      Search(j, leave, plan + j, new value)",
           "  RETURN                         // go back"], 0.6, 1.5, 5.4, 3.2, 11);
  card(s, 6.3, 1.5, 3.1, 1.45, "Class", ["Backtracking (recursive) + branch and bound"]);
  card(s, 6.3, 3.15, 3.1, 1.55, "Worst case: O(n!)", ["In practice a few thousand nodes (Fatih: 2,291 nodes, 1,621 pruned)"]);
}
// ---------------- 17. Tour results
{
  const s = slide("alt", "Fatih · Results", "Here are the results. The value is the total score minus the time lost on the way. Backtracking finds a better plan than greedy in every region. In Balat, greedy even gets a negative value: it goes to a nice place first, and then the rest of the plan is bad. Brute force would need 237 billion orders for Fatih, so we cannot run it. But on a small case with 6 places we ran brute force, and it found exactly the same plan as backtracking. This shows that our pruning is correct. We measured this once, with our detailed version.");
  head(s, "TOUR RESULTS · START TAKSİM, WEDNESDAY 09:00–15:00", "Backtracking always wins");
  table(s, [["Region", "Places", "Greedy", "Backtracking", "Brute force orders"],
            ["Fatih", "14", "160", "244", "237 billion"], ["Beyoğlu", "10", "170", "220", "9.9 million"],
            ["Üsküdar", "10", "56", "175", "9.9 million"], ["Kadıköy", "7", "24", "131", "13,699"], ["Balat", "7", "−17", "94", "13,699"]],
        0.6, 1.5, 5.7, [1.0, 0.75, 0.85, 1.35, 1.75], { right: [1, 2, 3, 4], rowH: 0.38, size: 12 });
  card(s, 6.5, 1.5, 2.9, 2.0, "Proof on 6 places", ["Brute force: 1,956 orders", "Backtracking: 18 nodes", "Same best plan ✓"]);
  text(s, "Value = score − time lost on the way. Measured once with the detailed version.", 6.5, 3.7, 2.9, 0.9, { fontSize: 12 });
}
// ---------------- 18. Complexity
{
  const s = slide("light", "Fatih · Analysis", "Chapter 7 is about analysis, so we measured. First: Dijkstra with a simple list needs to look at the whole list every time. With a heap it is 82 times faster on Kadıköy to Taksim, and 167 times faster on a long route. Second: for the tour, brute force grows like n factorial. With 14 places it is 237 billion orders, but backtracking opens only about two thousand nodes. Best and worst cases: Dijkstra is fastest when the goal is near, slowest when there is no route. Backtracking is fastest when it finds a good plan early, because then it prunes a lot.");
  head(s, "5 · ANALYSIS (CHAPTER 7)", "We measured the complexity");
  card(s, 0.6, 1.55, 2.75, 3.2, "Dijkstra: list vs heap", ["Kadıköy → Taksim: 8.3 s → 0.10 s (82×)", "Taksim → Bostancı: 45.4 s → 0.27 s (167×)", "O(V²) vs O((V + E) log V)"]);
  card(s, 3.62, 1.55, 2.75, 3.2, "Tour: brute force vs backtracking", ["10 places: 9.9 million orders vs ~1,000 nodes", "14 places: 237 billion orders vs 1,975 nodes", "O(n!) vs pruned search"]);
  card(s, 6.65, 1.55, 2.75, 3.2, "Best / worst case", ["Dijkstra — best: goal next to start; worst: no route, every node", "Backtracking — best: good plan early; worst: no pruning, O(n!)"]);
}
// ---------------- 19. Tests
{
  const s = slide("alt", "Fatih · Tests", "Step 4 of Chapter 4 is to prove that the algorithm is correct. We have 46 automatic checks in our detailed version, and the simple app uses the same algorithms. The two strongest: our Dijkstra gives the same answer as networkx, a well-known library, and backtracking gives the same answer as brute force on small cases. The tests also found real bugs, and we fixed them.");
  head(s, "6 · PROVE IT IS CORRECT", "46 automatic checks, all pass");
  text(s, ["Our Dijkstra = networkx Dijkstra on the real network", "Backtracking = brute force on small cases", "Banned lines are really not used",
           "No metro at 03:00, metrobus yes", "Rain → longer walks · storm → no ferry · traffic → slower buses", "Wrong input → message, no crash"]
    .map((t, i, a) => ({ text: t, options: { bullet: true, breakLine: i < a.length - 1 } })), 0.6, 1.55, 5.2, 3.0, { fontSize: 14, color: INK, paraSpaceAfter: 6 });
  card(s, 6.1, 1.55, 3.3, 2.6, "Bugs the tests found", ["Grid cells too small (335 m, not 400 m)", "“Get on, get off” trick", "“Galata Kulesi” found “Ali Kul Lisesi”"]);
  text(s, "Tests are in the detailed version (yokus-gezi). The simple app uses the same algorithms.", 0.6, 4.65, 8.8, 0.3, { fontSize: 12 });
}
// ---------------- 20. Demo
{
  const s = slide("dark", "Fatih · Demo", "Now we show the app. Route tab: from Kadıköy to İstanbul Ticaret University. Type the name and choose the place from the list. Show the best route and the alternative, step by step. Change the hour to 03:00: no metro, a night bus. Choose the weather Fırtınalı (storm) on a route with a ferry: the ferry disappears. Open Tercihler and change the sorting. Toilet tab: the nearest toilets. Tour tab: Fatih, five hours, on a Tuesday: Topkapı Palace is not in the plan, because it is closed. If there is no internet, the route search still works; only the map, the address search and the weather need the internet.");
  head(s, "LIVE DEMO", "Let’s use the app");
  card(s, 0.6, 1.55, 2.05, 2.5, "🧭 Route", ["Kadıköy → İstanbul Ticaret University", "Hour 03:00, weather 🌬 storm"], { size: 12 });
  card(s, 2.85, 1.55, 2.05, 2.5, "⇅ Sort", ["Fastest → fewer transfers → less walking", "The routes change"], { size: 12 });
  card(s, 5.1, 1.55, 2.05, 2.5, "🚻 Toilet", ["Nearest 5 toilets", "Walking path to the nearest"], { size: 12 });
  card(s, 7.35, 1.55, 2.05, 2.5, "🧳 Tour (beta)", ["Fatih, 5 hours", "Tuesday: Topkapı is closed"], { size: 12 });
  text(s, "python app.py → opens in the browser · also works on a phone", 0.6, 4.35, 8.8, 0.4, { fontSize: 16, color: ON_DARK_SOFT });
}
// ---------------- 21. Limits
{
  const s = slide("light", "Fatih · Conclusion", "It is better to say the limitations ourselves. Our traffic is an average from the past, not live traffic. And the app runs on one laptop for one user. Next steps: live data, a mobile app with a server, GPS tracking, so the app can say: get off at the next stop. And the app stores, for many users. The algorithms stay the same. They only move to the server.");
  head(s, "HONEST REVIEW", "Limitations and next steps");
  card(s, 0.6, 1.55, 4.3, 3.25, "Limitations", ["Traffic is a past average, not live.", "Trips per hour, not the exact timetable.", "One weather point for the whole city.", "Tour data collected by hand (beta).", "Runs on one laptop, for one user."]);
  card(s, 5.1, 1.55, 4.3, 3.25, "Next steps", ["Live data: traffic now, bus positions", "Mobile app + server: the graph lives on the server", "GPS tracking: “get off at the next stop”", "App stores, many users at the same time"]);
}
// ---------------- 22. Course topics
{
  const s = slide("alt", "Fatih · Summary", "This slide shows that the project uses many topics from the course. Especially Chapter 1: we used three algorithm classes, greedy, backtracking and brute force, on the same problem, and we compared them.");
  head(s, "LINK TO THE COURSE", "Topics we used");
  table(s, [["Chapter", "Where in the project?"],
            ["1 · Algorithm basics", "Flowcharts, pseudocode · greedy, backtracking, brute force · knapsack"],
            ["3 · Heap, Hash", "Min-Heap in Dijkstra and for the nearest toilets · dict for stops, grid and lines"],
            ["4 · Algorithm design", "6 steps: problem, technique, design, correctness, analysis, code"],
            ["5 · Search", "Hash search · graph search (Dijkstra)"],
            ["7 · Analysis", "O(V²) vs O((V+E) log V), O(n!) vs pruning, best / worst case: measured"],
            ["8 · Libraries", "heapq, numpy, scipy, gradio, requests"],
            ["Not in class", "Dijkstra, Tobler’s function, branch and bound: explained and tested"]],
        0.6, 1.45, 8.8, [2.3, 6.5], { rowH: 0.4, size: 12 });
}
// ---------------- 23. End
{
  const s = slide("dark", "GitGez · Küçükşahin · Yılmaz · Miçillioğlu",
    "Possible questions and short answers:\n1) Why Dijkstra and not BFS? BFS counts every step as 1. Our edges have different minutes.\n2) Why is greedy not enough for the tour? It never goes back. In Balat it found a value of −17, backtracking found 94.\n3) How do you know backtracking is correct? On small cases it gives the same plan as brute force, and the upper bound is never too small, so pruning never cuts the best plan.\n4) Why not A*? A* is faster on long routes (our detailed version has it), but Dijkstra with a heap is simpler and fast enough here: about 0.1–0.3 s per search.\n5) Where do the hills come from? A satellite height map (Copernicus) and Tobler's walking function.\n6) Complexity? Dijkstra O((V+E) log V); backtracking worst case O(n!), in practice a few thousand nodes.\n7) Is the traffic live? No. It is the average speed from IBB data for that day type and hour. Live data is a next step.\n8) Does weather break Dijkstra? No. Costs get bigger, but they are never negative.");
  text(s, "THANK YOU", 0.6, 0.6, 8.8, 0.3, { fontSize: 11, bold: true, color: "F4A37E", charSpacing: 1.5 });
  text(s, "Questions?", 0.6, 1.1, 8.8, 1.0, { fontSize: 54, bold: true, color: ON_DARK });
  text(s, "GitGez · python app.py", 0.6, 2.3, 8.8, 0.5, { fontSize: 20 });
  text(s, "Data: IBB Open Data (GTFS, toilets, traffic) · Open-Meteo (weather) · OpenStreetMap / Overture (streets, ODbL) · Copernicus DEM GLO-30 (heights)", 0.6, 4.3, 8.8, 0.6, { fontSize: 11 });
}

pres.writeFile({ fileName: process.argv[2] }).then(f => console.log("written", f));
