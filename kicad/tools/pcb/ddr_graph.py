# DDR のネットの銅のつながりを、長さつきのグラフにする (2026-11-23、ddr_check.py と mr_export.py --chain で使う)
#   節点 = 線の端・ビア (層ごと)・パッド ('pad', 部品番号)。辺の長さ = 線の長さ、ビアは層の間の厚み。
#   T 字 (線の途中につながる)・ビアの銅の中の線の端・パッドの中の線の端もつなぐ。
import collections, heapq, math
import pcbnew

T = pcbnew.ToMM
Z = {pcbnew.F_Cu: 0.0, pcbnew.In2_Cu: 0.25, pcbnew.In5_Cu: 1.31, pcbnew.B_Cu: 1.54}
CU = list(Z)


def key(p, l):
    return (round(T(p.x), 3), round(T(p.y), 3), l)


SEG = collections.defaultdict(dict)  # net -> (節点, 節点) -> 線の情報 (build のあと使える)


def path(graph, net, src, dst):
    # src から dst までの最短経路の節点の並び (なければ None)
    g = graph[net]
    d = {src: 0.0}
    pr = {}
    h = [(0.0, 0, src)]
    k = 0
    while h:
        dd, _, u = heapq.heappop(h)
        if u == dst:
            break
        if dd > d.get(u, 1e18):
            continue
        for v, L in g[u]:
            nd = dd + L
            if nd < d.get(v, 1e18):
                d[v] = nd
                pr[v] = u
                k += 1
                heapq.heappush(h, (nd, k, v))
    if dst not in d:
        return None
    res = [dst]
    while res[-1] != src:
        res.append(pr[res[-1]])
    return res[::-1]


def build(b, prefix='DDR_'):
    SEG.clear()
    graph =collections.defaultdict(lambda: collections.defaultdict(list))  # net -> node -> [(node, len)]
    pts = collections.defaultdict(lambda: collections.defaultdict(list))    # net -> layer -> [(x, y, node)]

    def edge(net, a, c, L):
        graph[net][a].append((c, L))
        graph[net][c].append((a, L))
        for nd in (a, c):
            pts[net][nd[2]].append((nd[0], nd[1], nd))

    tracks = [t for t in b.GetTracks() if t.GetNetname().startswith(prefix)]
    for t in tracks:
        n = t.GetNetname()
        if t.Type() == pcbnew.PCB_VIA_T:
            ls = [l for l in CU if t.IsOnLayer(l)]
            p = t.GetPosition()
            for la, lb in zip(ls, ls[1:]):
                edge(n, key(p, la), key(p, lb), abs(Z[lb] - Z[la]))
        elif t.GetLayer() in Z:
            a_, c_ = key(t.GetStart(), t.GetLayer()), key(t.GetEnd(), t.GetLayer())
            edge(n, a_, c_, T(t.GetLength()))
            info = {'uuid': t.m_Uuid.AsString(), 'l': CU.index(t.GetLayer()), 'a': [a_[0], a_[1]], 'b': [c_[0], c_[1]], 'w': T(t.GetWidth())}
            SEG[n][(a_, c_)] = info
            SEG[n][(c_, a_)] = info
    segs = collections.defaultdict(list)
    for t in tracks:
        n = t.GetNetname()
        if t.Type() != pcbnew.PCB_VIA_T and t.GetLayer() in Z:
            segs[n].append((key(t.GetStart(), t.GetLayer()), key(t.GetEnd(), t.GetLayer()), T(t.GetWidth()) / 2))
        elif t.Type() == pcbnew.PCB_VIA_T:
            p = t.GetPosition()
            r = T(t.GetWidth(pcbnew.F_Cu)) / 2
            for l in CU:
                if not t.IsOnLayer(l):
                    continue
                c = key(p, l)
                for x, y, nd in list(pts[n][l]):
                    if nd != c and math.hypot(x - c[0], y - c[1]) < r:
                        graph[n][nd].append((c, 0.0)); graph[n][c].append((nd, 0.0))
    for n, ss in segs.items():
        for a_, c_, hw in ss:
            l = a_[2]
            ax, ay, cx, cy = a_[0], a_[1], c_[0], c_[1]
            L2 = (cx - ax) ** 2 + (cy - ay) ** 2
            if L2 == 0:
                continue
            for x, y, nd in list(pts[n][l]):
                if nd in (a_, c_):
                    continue
                t_ = ((x - ax) * (cx - ax) + (y - ay) * (cy - ay)) / L2
                if 0 < t_ < 1 and math.hypot(ax + t_ * (cx - ax) - x, ay + t_ * (cy - ay) - y) < hw:
                    Ls = math.sqrt(L2)
                    graph[n][nd].append((a_, t_ * Ls)); graph[n][a_].append((nd, t_ * Ls))
                    graph[n][nd].append((c_, (1 - t_) * Ls)); graph[n][c_].append((nd, (1 - t_) * Ls))
    pads = {}
    for fp in b.GetFootprints():
        for pd in fp.Pads():
            n = pd.GetNetname()
            if not n.startswith(prefix):
                continue
            node = ('pad', fp.GetReference())
            pads[(n, fp.GetReference())] = node
            graph[n][node]  # 線がなくても節点を作る
            for l in CU:
                if not (pd.IsOnLayer(l) and pd.FlashLayer(l)):
                    continue
                for x, y, nd in pts[n][l]:
                    if pd.HitTest(pcbnew.VECTOR2I(pcbnew.FromMM(x), pcbnew.FromMM(y)), pcbnew.FromMM(0.01)):
                        graph[n][node].append((nd, 0.0))
                        graph[n][nd].append((node, 0.0))
    return graph, pads


def dist(graph, net, src):
    g = graph[net]
    d = {src: 0.0}
    h = [(0.0, 0, src)]
    k = 0
    while h:
        dd, _, u = heapq.heappop(h)
        if dd > d.get(u, 1e18):
            continue
        for v, L in g[u]:
            nd = dd + L
            if nd < d.get(v, 1e18):
                d[v] = nd
                k += 1
                heapq.heappush(h, (nd, k, v))
    return d
