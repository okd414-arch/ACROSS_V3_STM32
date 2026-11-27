# 局所的な遠回り (輪・折り返し・1 区間だけの遠回り) を探す (2026-11-25)
#   ネット全体の長さの比では見逃す形を、パッドとパッドの 1 区間ごとに調べる。
#   - 銅のつながりをグラフにする (線の端・ビア。パッドは中にある点につなぐ)
#   - パッドの最小全域木の辺ごとに、銅の上の最短の道をたどり、
#       比 (道の長さ ÷ 直線) が 1.6 以上かつ 3mm 以上長い → 「区間の遠回り」
#       道の上の点が、4mm 以上前の点から 0.6mm 以内に戻る → 「輪・折り返し」
#   - 面 (ゾーン) のあるネットは除く
# usage: python detour_local.py pcb out.json
import sys, math, json, heapq, collections
import pcbnew

b = pcbnew.LoadBoard(sys.argv[1])
T = pcbnew.ToMM
zn = set(z.GetNetname() for z in b.Zones())


def key(p):
    return (round(T(p.x), 2), round(T(p.y), 2))


G = collections.defaultdict(lambda: collections.defaultdict(dict))  # net -> node -> {node: len}
vias = collections.defaultdict(list)
for t in b.GetTracks():
    n = t.GetNetname()
    if not n or n in zn:
        continue
    if t.Type() == pcbnew.PCB_VIA_T:
        vias[n].append(key(t.GetPosition()))
        G[n][key(t.GetPosition())]
        continue
    a, e = key(t.GetStart()), key(t.GetEnd())
    l = math.dist(a, e)
    G[n][a][e] = min(l, G[n][a].get(e, 1e9))
    G[n][e][a] = min(l, G[n][e].get(a, 1e9))

pads = collections.defaultdict(list)
for p in b.GetPads():
    n = p.GetNetname()
    if n in G:
        pads[n].append(p)

res = []
for n, g in G.items():
    P = pads.get(n, [])
    if len(P) < 2:
        continue
    nodes = list(g.keys())
    # パッド → 中にある節点 (なければ一番近い節点 0.3mm 以内)
    pn = []
    for p in P:
        inside = [q for q in nodes if p.HitTest(pcbnew.VECTOR2I(pcbnew.FromMM(q[0]), pcbnew.FromMM(q[1])))]
        if not inside:
            c = key(p.GetPosition())
            near = [q for q in nodes if math.dist(q, c) < 0.3]
            inside = near
        pn.append(inside)
    # パッドどうしの最小全域木
    C = [key(p.GetPosition()) for p in P]
    inT = [False] * len(P); d = [1e9] * len(P); par = [-1] * len(P); d[0] = 0
    edges = []
    for _ in P:
        i = min((k for k in range(len(P)) if not inT[k]), key=lambda k: d[k]); inT[i] = True
        if par[i] >= 0:
            edges.append((par[i], i))
        for k in range(len(P)):
            if not inT[k] and math.dist(C[i], C[k]) < d[k]:
                d[k] = math.dist(C[i], C[k]); par[k] = i
    for i, j in edges:
        if not pn[i] or not pn[j]:
            continue
        # ダイクストラ (始点は i のパッドの中の節点すべて)
        dist = {}; prev = {}
        h = [(0.0, q) for q in pn[i]]
        for q in pn[i]:
            dist[q] = 0.0
        goal = set(pn[j]); end = None
        while h:
            dd, u = heapq.heappop(h)
            if dd > dist.get(u, 1e9):
                continue
            if u in goal:
                end = u; break
            for v, w in g[u].items():
                if dd + w < dist.get(v, 1e9):
                    dist[v] = dd + w; prev[v] = u; heapq.heappush(h, (dd + w, v))
        if end is None:
            continue
        path = [end]
        while path[-1] in prev:
            path.append(prev[path[-1]])
        path.reverse()
        # 道が途中で同じネットのほかのパッドを通るなら、直接の区間ではない (フライバイなど) ので見ない
        others = set(q for k, lst in enumerate(pn) if k not in (i, j) for q in lst)
        if any(q in others for q in path[1:-1]):
            continue
        L = dist[end]
        S = math.dist(C[i], C[j])
        flags = []
        if S > 0.5 and L / S >= 1.6 and L - S >= 3:
            flags.append('区間の遠回り')
        # 輪・折り返し: 道を 0.2mm ごとに点にして、4mm 以上前の点に 0.6mm 以内で戻るか
        pts = []
        for a, e in zip(path, path[1:]):
            l = math.dist(a, e); k = max(1, int(l / 0.2))
            for s in range(k):
                pts.append((a[0] + (e[0] - a[0]) * s / k, a[1] + (e[1] - a[1]) * s / k))
        pts.append(path[-1])
        acc = [0.0]
        for a, e in zip(pts, pts[1:]):
            acc.append(acc[-1] + math.dist(a, e))
        loop_at = None
        for s in range(len(pts)):
            for r in range(0, s):
                if acc[s] - acc[r] < 4.0:
                    break
                if math.dist(pts[s], pts[r]) < 0.6:
                    loop_at = pts[s]; break
            if loop_at:
                break
        if loop_at:
            flags.append('輪・折り返し')
        if flags:
            mid = loop_at or pts[len(pts) // 2]
            res.append({'net': n, 'flags': flags, 'L': round(L, 1), 'S': round(S, 1),
                        'a': P[i].GetParentFootprint().GetReference() + '.' + P[i].GetNumber(),
                        'b': P[j].GetParentFootprint().GetReference() + '.' + P[j].GetNumber(),
                        'at': [round(mid[0], 2), round(mid[1], 2)],
                        'path': [[round(x, 2), round(y, 2)] for x, y in path]})  # 道 (2026-11-26、全体図に描くため)

res.sort(key=lambda r: -(r['L'] - r['S']))
json.dump(res, open(sys.argv[2], 'w', encoding='utf8'), ensure_ascii=False, indent=1)
nets = sorted(set(r['net'] for r in res))
c = collections.Counter(f for r in res for f in r['flags'])
print('見つかった区間', len(res), 'ネット', len(nets), dict(c))
for r in res[:30]:
    print(f"{r['net'][:30]:30s} {'+'.join(r['flags']):14s} {r['a']}→{r['b']} 道 {r['L']} 直線 {r['S']} @{r['at']}")
