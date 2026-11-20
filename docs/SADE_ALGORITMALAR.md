# Sade sürümde kullanılan algoritmalar
Bu not, akış şeması (flowchart) ve sözde kod (pseudocode) hazırlamak içindir. Kod: `sade/gitgez_sade.ipynb`
(fonksiyon adları parantez içinde). Sözde kodlar sunum İngilizce olduğu için İngilizce.

**Akış şeması önerisi:** zorunlu olanlar **1 (genel sistem)**, **6 (Dijkstra)**, **7 (alternatif rota)**, **11 (backtracking)**.
Diğerleri için sözde kod ya da doğal dil yeterli. (Sunumdaki "How the system works" şemasında hâlâ "Dijkstra or A*" yazıyor:
sade sürümde A* yok, "Dijkstra" olarak düzeltilmeli.)

| # | Algoritma | Nerede (fonksiyon) | Ne için | Sınıf | Karmaşıklık |
|---|---|---|---|---|---|
| 2 | Hash tablosu ile arama | `StopIndex.search`, `durak_yerleri` | Yazılan adı duraklarla eşleştirmek | Arama (hash) | Tam ad O(1) |
| 3 | Benzerlik araması | `StopIndex.suggest` (difflib) | Yazım hatası: "üsküdr" → Üsküdar | Kaba kuvvet | O(N·k) |
| 4 | Izgara hash'i | `Grid.near` | Bir noktaya yakın durakları bulmak | Uzamsal hash | O(9 kare) |
| 5 | Sokakta Dijkstra (scipy) | `nokta_erisim`, `yol_bul` | Başlangıç/varıştan duraklara yürüme süresi, yürüyüş yolu | Greedy (Dijkstra) | O((V+E) log V) |
| — | Saate göre graf kurma | `build_graph`, `wait_at` | O saatte çalışan hatlarla graf | — | O(L + S) |
| 6 | **Dijkstra + Min-Heap** | `dijkstra`, `rebuild_path` | En iyi rota (3 kritere göre) | Greedy | O((V+E) log V) |
| 7 | **Alternatif rota** | `rota_bul`, `esdeger_desenler` | 2. rota: hatları yasakla, tekrar ara | Dijkstra × 2 | 2 × Dijkstra |
| 8 | Hava ve trafik çarpanı | `kosul_ayarla`, `trafik_carpani`, `geohash` | Kenar maliyetlerini saate göre değiştirmek | — | Kenar başına O(1) |
| 9 | En yakın k tuvalet | `yakin_tuvaletler` (heapq.nsmallest) | En yakın 5 tuvalet | Heap | O(N log k) |
| 10 | Gezi: süre matrisi | `sure_matrisi`, `tek_kaynak` | Yerler arası yolculuk süreleri | Dijkstra | n × Dijkstra |
| 11 | **Backtracking + dal budama** | `gezi_backtracking`, `ziyaret` | Hangi yerler, hangi sırayla | Backtracking + branch & bound | En kötü O(n!) |
| 12 | Kesirli knapsack üst sınırı | `ust_sinir` (11'in içinde) | Budama için iyimser tahmin | Greedy | O(n) |

---

## 1. Genel sistem (akış şeması)
```
START
  user chooses tab
  IF tab = Route THEN
      read from, to, day, hour, weather, sorting
      find places (2)                 -> from/to place
      set weather + traffic (8)
      build or reuse graph for day/hour (graph)
      walking access from/to stops (5)
      best route = Dijkstra (6)
      alternative = ban lines, Dijkstra again (7)
      show map + step-by-step text
  ELSE IF tab = Toilet THEN
      read place -> nearest 5 toilets (9) -> walking path to the nearest (5)
  ELSE IF tab = Tour THEN
      read start, region, date, start hour, hours
      open places of that day, 12 best (heap)
      travel time matrix (10)
      best plan = backtracking (11, 12)
      show plan with times
END
```

## 2. Hash tablosu ile yer arama
**Ne yapar:** "KADIKÖY", "kadikoy", "Kadıköy" aynı anahtara dönüşür (`normalize`: Türkçe harf → Latin, küçük harf,
noktalama yok). Sözlükte `ad → durak listesi` tutulur, tam ad O(1)'de bulunur. Aynı adlı ama birbirinden 800 m'den uzak
duraklar ayrı seçenek olur (ör. 4 farklı "Taşköprü"), yanına en yakın istasyonun adı yazılır.
Adres/mekân (ör. "İstanbul Ticaret Üniversitesi") için internetten Photon (OpenStreetMap) araması yapılır.
```
FUNCTION FindPlace(text)
    key ← normalize(text)
    IF key IN index THEN RETURN index[key]           // O(1)
    names ← all names whose words start with the typed words
    IF names is empty THEN names ← similar names (difflib)
    group stops of each name by location (≤ 800 m = same place)
    RETURN groups + address results
```

## 4. Izgara hash'i (yakın duraklar)
**Ne yapar:** Şehri 2 km × 2 km karelere böler; sözlük `kare → duraklar`. Bir noktaya 2 km'den yakın durak ancak
kendi karesinde ya da 8 komşu karede olabilir. 14.357 durağın hepsine bakmak yerine ~9 kareye bakılır.
```
FUNCTION NearStops(lat, lon)
    (i, j) ← (lat ÷ cell height, lon ÷ cell width)
    FOR di IN -1..1, dj IN -1..1 DO
        output stops in cell (i+di, j+dj)
```

## 5. Sokakta yürüme (Dijkstra, scipy)
**Ne yapar:** Sokak ağı bir graf: düğüm = kavşak, kenar = sokak parçası, maliyet = yürüme dakikası.
Yürüme hızı eğime göre **Tobler fonksiyonu** ile önceden hesaplandı (düz 4,5 km/sa, yokuş yukarı daha yavaş).
- `nokta_erisim`: başlangıç noktasından 27 dk içinde yürünebilen duraklar ve süreleri (varış için ters yönde).
- `yol_bul`: iki nokta arası yürüyüş yolu (haritada çizilir) + süre, mesafe, tırmanış.
- Hız için sadece iki noktayı kapsayan kutudaki sokaklar alınır (alt graf). Birden çok başlangıç kavşağı için
  sanal bir "süper kaynak" düğüm eklenir.
- Durak → durak yürüme bağlantıları (854.799 tane) aynı yöntemle önceden hesaplandı (`yurume.npz`).

## Saate göre graf kurma
**Düğümler:** durak (`"durakta bekliyorum"`) ve `(hat, i)` (`"bu hattın i. durağında araçtayım"`).
**Kenarlar:** board (bin: bekleme + 2 dk), ride (yolculuk dk), alight (in: 0 dk), walk (yürüme dk).
O saatte ve bir önceki saatte seferi olmayan hat grafa girmez. Bekleme = 60 ÷ saatlik sefer ÷ 2 (en az 1, en çok 30 dk).
Aynı durakları izleyen hatlar (34A, 34AS…) tek "desen" olur, seferleri toplanır. Graf her (gün, saat, fırtına, trafik)
için bir kez kurulur, önbellekte saklanır.
```
FUNCTION BuildGraph(day, hour)
    FOR EACH line pattern DO
        IF storm AND line is ferry THEN CONTINUE
        wait ← WaitTime(line, day, hour)
        IF wait = none THEN CONTINUE                 // not running at this hour
        FOR EACH stop i of the line DO
            add edge stop → (line, i)      cost = wait + 2      "board"
            add edge (line, i) → stop      cost = 0             "alight"
            add edge (line, i) → (line, i+1) cost = minutes × traffic factor   "ride"
```

## 6. Dijkstra + Min-Heap (ana algoritma, akış şeması)
**Ne yapar:** Başlangıçtan varışa en ucuz yolu bulur. Her adımda heap'ten **en ucuz** durumu alır (greedy).
Maliyetler negatif olmadığı için heap'ten çıkan durumun maliyeti kesindir → doğru sonuç.
- **Başlangıç:** başlangıçtan yürüyerek ulaşılan bütün duraklar heap'e, yürüme süreleriyle.
- **Maliyet bir tuple:** en hızlı `(dk)`, az aktarma `(biniş sayısı, dk)`, az yürüme `(araç dk + 4 × yürüme dk)`.
  Python tuple'ları soldan sağa karşılaştırır: `(1, 74) < (2, 38)`.
- **Durum = (düğüm, son kenar türü).** İki kural: (1) yürüme üstüne yürüme yok, (2) binip hemen inmek yok.
- **Tembel silme:** heap'te aynı durumun eski, pahalı kaydı kalabilir; çıkınca "bitti" listesindeyse atlanır.
- **Yasaklı hatlar** (alternatif için) parametreyle verilir: o hatlara binilmez.
```
FUNCTION Dijkstra(graph, sources, targets, criterion, banned)
    heap ← all start stops with their walking time
    best ← {}; done ← {}
    WHILE heap is not empty DO
        (cost, state) ← heap.pop()                   // cheapest state
        IF state IN done THEN CONTINUE               // old entry (lazy deletion)
        add state to done
        IF state = DESTINATION THEN RETURN cost, path
        IF node is a target stop THEN
            push DESTINATION with cost + walking time to the end
        FOR EACH edge (node → next, minutes, kind, line) DO
            IF kind = walk AND last = walk THEN CONTINUE          // rule 1
            IF kind = alight AND last = board THEN CONTINUE       // rule 2
            IF kind = board AND line IN banned THEN CONTINUE
            new ← cost + edgeCost(minutes, kind, criterion)
            IF new < best[next] THEN
                best[next] ← new; previous[next] ← state
                heap.push(new, next)
    RETURN "no route"
```
**Yol geri kurma (`rebuild_path`):** varıştan başlayıp `previous` zinciriyle başa kadar git, sonra ters çevir.
**Karmaşıklık:** O((V + E) log V). En iyi durum: hedef başlangıca çok yakın. En kötü durum: rota yok, her düğüm açılır.

## 7. Alternatif rota (akış şeması)
**Ne yapar:** İnsanlara seçenek sunmak için 1 alternatif. En iyi rotanın kullandığı hatlar (ve aynı durakları izleyen
eşdeğer hatlar: 34 / 34A / 34AS) **yasaklanır**, Dijkstra tekrar çalışır → gerçekten başka araçlarla giden rota.
Hedef 2,4 km'den yakınsa sadece yürüyüş de bir aday olur. Adaylar seçilen kritere göre sıralanır, ilk ikisi gösterilir;
alternatif en iyisinden 30 dk'dan fazla uzunsa gösterilmez.
```
FUNCTION Routes(A, B, day, hour, criterion)
    route1 ← Dijkstra(graph, accessFrom(A), accessTo(B), criterion, banned = {})
    banned ← lines of route1 + lines with the same stops
    IF banned is not empty THEN
        route2 ← Dijkstra(graph, accessFrom(A), accessTo(B), criterion, banned)
    IF distance(A, B) ≤ 2.4 km THEN walkRoute ← walk on streets
    sort candidates by criterion; keep the first 2
    remove the 2nd if it is more than 30 min slower
    RETURN routes
```

## 8. Hava durumu ve trafik
Algoritma değişmez, sadece **kenar maliyetleri** değişir (hep pozitif kalır → Dijkstra hâlâ doğru).
- Hava (Open-Meteo, o gün ve saat): yağmur → yürüme × 1,15; kar → × 1,5; rüzgâr hamlesi ≥ 70 km/sa → vapur kenarları silinir.
- Trafik (`trafik.csv`, İBB Ocak 2025): otobüs durak arası süresi × çarpan (0,7–2,0). Çarpan = bölgenin normal hızı ÷ o
  saatteki hızı. Bölge = iki durağın orta noktasının **geohash** kodu (koordinatı ~1 km'lik kutu koduna çevirir:
  boylamı ve enlemi sırayla ikiye bölerek). Tablo sözlükte: `(bölge, gün, saat) → çarpan`, O(1).

## 9. En yakın tuvaletler
Her aktif tuvaletin kuş uçuşu uzaklığı hesaplanır, en küçük 5'i `heapq.nsmallest` (Min-Heap) ile seçilir: O(N log k).
En yakınına sokaktan yürüme yolu (5) çizilir.

## 10. Gezi: süre matrisi
`T[i][j]` = i. yerden j. yere en kısa süre.
1. Yürüme: bütün yerleri kapsayan tek sokak alt grafında, scipy Dijkstra **tüm yerlerden birden** çalışır.
2. Yürümesi 20 dk'dan uzun çiftler için toplu taşıma: `tek_kaynak` (hedefi olmayan Dijkstra; bütün hedef duraklara
   ulaşınca durur). Matriste ikisinden kısa olan kalır.
3. `bas[j]` = başlangıç noktasından j. yere süre (aynı yöntem).

## 11. Backtracking + dal budama (akış şeması)
**Problem:** 0-1 knapsack + sıra. Çanta = süre; eşya = yer; ağırlık = yol + bekleme + gezme; değer = puan.
**Değer** = Σ puan − (yol + bekleme dakikası). Adaylar: o gün açık yerlerden en yüksek puanlı 12 tanesi (`heapq.nlargest`).
**Kurallar (`ziyaret`):** erken varılırsa açılış beklenir; Cuma 12:00–14:30 camiler kapalı; son girişten sonra ya da
kapanışı aşacaksa gezilemez; plan süre sınırını aşamaz.
```
FUNCTION Search(last, time, plan, value)
    IF value > best.value THEN best ← plan            // save the best plan so far
    IF value + UpperBound(endTime − time, remaining) ≤ best.value THEN
        RETURN                                        // prune: this branch cannot win
    FOR EACH place j in remaining (best score/time ratio first) DO
        arrive ← time + T[last][j]
        (enter, leave) ← Visit(j, arrive)            // opening hours, Friday prayer
        IF not possible OR leave > endTime THEN CONTINUE
        add j to plan; remove j from remaining
        Search(j, leave, plan, value + score[j] − (enter − time))   // recursion
        remove j from plan; add j to remaining       // go back (backtrack)
```
**Neden doğru:** üst sınır asla gerçek en iyi değerden küçük değildir (iyimser), bu yüzden budama en iyi planı kesmez.
**Neden bitiyor:** her çağrı plana yeni bir yer ekler, en fazla 12 yer var → derinlik ≤ 12.
**Karmaşıklık:** en kötü O(n!) (kaba kuvvet gibi); budama sayesinde pratikte birkaç bin düğüm
(ör. Fatih: 2.291 düğüm, 1.621 dal budandı).

## 12. Kesirli knapsack üst sınırı (greedy)
Kalan süreyi, puan ÷ süre oranı en iyi yerlerle doldur; sığmayan son yerin **bir kısmını** al. Gerçekte yer bölünemez,
bu yüzden sonuç her zaman gerçekten ulaşılabilecek değerden büyük ya da eşittir (iyimser).
```
FUNCTION UpperBound(freeTime, remaining)
    total ← 0
    FOR EACH place j in remaining, best ratio first DO
        IF cost[j] ≤ freeTime THEN total ← total + score[j]; freeTime ← freeTime − cost[j]
        ELSE RETURN total + score[j] × freeTime ÷ cost[j]     // fraction of the last place
    RETURN total
```
