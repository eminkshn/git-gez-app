# Simple version: 4 algorithms for flowcharts and pseudocode
Code: `sade/gitgez_sade.ipynb` (function names in brackets). Terms are in English, as on the slides.

| # | Algorithm | Function | What it does | Class | Complexity |
|---|---|---|---|---|---|
| 1 | **System overview** | Gradio interface | Route / Toilet / Tour tabs | — | — |
| 2 | **Dijkstra + Min-Heap** | `dijkstra`, `rebuild_path` | Best route by public transport | Greedy | O((V + E) log V) |
| 3 | **Alternative route** | `rota_bul` | Second route: ban the lines, search again | Dijkstra × 2 | 2 × Dijkstra |
| 4 | **Backtracking + branch and bound** | `gezi_backtracking`, `ziyaret`, `ust_sinir` | Tour: which places, in which order | Backtracking | Worst case O(n!) |

Note: the "How the system works" flowchart on the slides still says "Dijkstra or A*". The simple version has no A*,
so the box should say only "Dijkstra".

---

## 1. System overview (flowchart)
```
START
  user chooses a tab
  IF tab = Route THEN
      read from, to, day, hour, weather, sorting
      find the places (hash table search)
      set weather and traffic (edge costs)
      build the graph for this day and hour (or take it from the cache)
      walking time from start to nearby stops, and from stops to destination
      best route ← Dijkstra                          (algorithm 2)
      alternative ← ban lines, Dijkstra again          (algorithm 3)
      show map + step-by-step directions
  ELSE IF tab = Toilet THEN
      read place
      nearest 5 toilets (heap)
      walking path to the nearest one
  ELSE IF tab = Tour THEN
      read start place, region, date, start hour, free hours
      places open on that day → the 12 best (heap)
      travel time matrix between places (Dijkstra)
      best plan ← backtracking + branch and bound     (algorithm 4)
      show plan with times
END
```

## 2. Dijkstra + Min-Heap (flowchart + pseudocode)
**Goal:** the cheapest path from start to destination in the transport graph.

**Graph:** two node types — *stop* ("I am waiting at the stop") and *(line, i)* ("I am on this line at stop i").
Four edge types — **board** (cost = waiting time + 2 min transfer penalty), **ride** (travel time),
**alight** (0 min), **walk** (walking time on streets).

**Main ideas:**
- **Greedy choice:** always take the cheapest state from the Min-Heap.
- **Cost is a tuple** (Python compares tuples left to right):
  fastest = `(minutes)`, fewest transfers = `(boardings, minutes)`, least walking = `(ride minutes + 4 × walking minutes)`.
- **State = (node, type of last edge).** Two rules: (1) no walk after a walk, (2) no "board then alight" trick.
- **Lazy deletion:** an old, more expensive copy of a state can stay in the heap; when it comes out, skip it.
- **Banned lines:** a parameter for the alternative route (algorithm 3).
```
FUNCTION Dijkstra(graph, sources, targets, criterion, banned)
    heap ← every start stop with its walking time
    best ← empty; done ← empty
    WHILE heap is not empty DO
        (cost, state) ← heap.pop()                    // cheapest state
        IF state IN done THEN CONTINUE                // old copy (lazy deletion)
        add state to done
        IF state = DESTINATION THEN
            RETURN cost, RebuildPath(state)
        IF node is a target stop THEN
            heap.push(cost + walking time to the end, DESTINATION)
        FOR EACH edge (node → next, minutes, kind, line) DO
            IF kind = walk AND last = walk THEN CONTINUE          // rule 1
            IF kind = alight AND last = board THEN CONTINUE       // rule 2
            IF kind = board AND line IN banned THEN CONTINUE
            new ← cost + EdgeCost(minutes, kind, criterion)
            IF new < best[next] THEN
                best[next] ← new
                previous[next] ← state
                heap.push(new, next)
    RETURN "no route"

FUNCTION RebuildPath(state)
    path ← empty
    WHILE state has a previous DO
        add the edge (previous → state) to path
        state ← previous[state]
    RETURN reverse(path)
```
- **Correctness:** all costs are minutes, never negative → when a state leaves the heap, its cost is final.
  Weather and traffic only multiply costs by positive numbers or remove edges (storm → no ferry), so this stays true.
- **Finiteness:** every state is finished only once.
- **Complexity:** O((V + E) log V). **Best case:** the destination is next to the start.
  **Worst case:** no route, every state is opened.

## 3. Alternative route (flowchart + pseudocode)
**Goal:** give the user a second, really different route.
```
FUNCTION Routes(A, B, day, hour, criterion)
    route1 ← Dijkstra(graph, from A, to B, criterion, banned = {})
    banned ← lines of route1 + lines with the same stops (34 / 34A / 34AS)
    IF banned is not empty THEN
        route2 ← Dijkstra(graph, from A, to B, criterion, banned)
    IF distance(A, B) ≤ 2.4 km THEN
        walkRoute ← walking on streets
    sort all candidates by the criterion; keep the first 2
    IF the 2nd is more than 30 min slower than the 1st THEN remove it
    RETURN routes
```
Example: Kadıköy → Taksim, weekday 08:00 — best 32 min (bus 12A → Marmaray → M2),
alternative 47 min (ferry → T1 → F1).

## 4. Backtracking + branch and bound (flowchart + pseudocode)
**Problem:** 0-1 knapsack with order. Knapsack = free time; items = places; weight = travel + waiting + visit time;
value = score. **Plan value** = total score − (travel + waiting minutes).
Candidates: places open on that day, the 12 with the highest score.

**Rules (`Visit`):** if you arrive early, wait for opening; mosques are closed on Friday 12:00–14:30;
no entry after the last entry time; the visit must end before closing; the plan must end before the time limit.
```
FUNCTION Search(last, time, plan, value)
    IF value > best.value THEN best ← plan                // save the best plan so far
    IF value + UpperBound(endTime − time, remaining) ≤ best.value THEN
        RETURN                                            // prune: this branch cannot win
    FOR EACH place j in remaining (best score/time ratio first) DO
        arrive ← time + T[last][j]
        (enter, leave) ← Visit(j, arrive)
        IF not possible OR leave > endTime THEN CONTINUE
        add j to plan; remove j from remaining
        Search(j, leave, plan, value + score[j] − (enter − time))    // recursion
        remove j from plan; add j to remaining           // go back (backtrack)

FUNCTION UpperBound(freeTime, remaining)                  // fractional knapsack (greedy)
    total ← 0
    FOR EACH place j in remaining, best score/time ratio first DO
        IF cost[j] ≤ freeTime THEN
            total ← total + score[j]; freeTime ← freeTime − cost[j]
        ELSE
            RETURN total + score[j] × freeTime ÷ cost[j]  // a fraction of the last place
    RETURN total
```
- **Correctness:** the upper bound is optimistic (a real place cannot be split), so it is never smaller than
  the real best value of the branch → pruning never removes the best plan.
- **Finiteness:** every call adds one new place; at most 12 places → recursion depth ≤ 12.
- **Complexity:** worst case O(n!) like brute force; with pruning only a few thousand nodes
  (example: Fatih, 2,291 nodes, 1,621 branches pruned).
- **Best case:** a good plan is found early, so most branches are pruned. **Worst case:** no pruning.
