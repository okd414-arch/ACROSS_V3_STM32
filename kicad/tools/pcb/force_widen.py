# 指定のネットの線を目標の幅にそろえ、当たる他のネットの線・ビアをはがす (2026-11-25)
#   はがしたネットは、このあと mr_route で引き直す (呼ぶ側)。
#   - 目標の幅: 範囲の中 (本線) と外 (枝) で分ける
#   - パッド・基板の端は動かせないので、それに当たらない一番太い幅にとどめる (0.1 刻み、今の幅より細くはしない)
#   - 細かいピン (パッドの短辺が目標より細い) につながる線の端 0.8mm は、そのまま (長い線は先に 0.8mm で分ける)
#   - 間隔: 絶縁ドメイン違い 2.0 (絶縁部品のパッドは除く)、それ以外 0.2
#   - BGA・QFN の中 (U1 U301 U302 U104 U401 U501) は触らない。ロックした線・ビアは、はがさない (その所は細くする)
# usage: python force_widen.py pcb NETREGEX 本線の幅 枝の幅 x0 y0 x1 y1 [-o victims.json]
import sys, re, json, collections
import pcbnew

a = sys.argv[1:]
vout = None
if '-o' in a:
    i = a.index('-o'); vout = a[i + 1]; del a[i:i + 2]
PCB, RX, WM, WB = a[0], re.compile(a[1]), float(a[2]), float(a[3])
BX = tuple(map(float, a[4:8]))
mm = pcbnew.FromMM
T = pcbnew.ToMM
b = pcbnew.LoadBoard(PCB)
SKIP_FP = ['U1', 'U301', 'U302', 'U104', 'U401', 'U501']
BRIDGE = ('U601', 'U606', 'U607', 'U609', 'U701', 'U702', 'U703', 'U704', 'U705', 'U707')
CLR, ISO_CLR, EDGE = 0.2, 2.0, 0.4
skip = []
for r in SKIP_FP:
    f = b.FindFootprintByReference(r)
    if f:
        cy = f.GetCourtyard(pcbnew.B_CrtYd if f.IsFlipped() else pcbnew.F_CrtYd)
        skip.append(cy.BBox() if cy.OutlineCount() else f.GetBoundingBox())
iso_c = {}


def iso(n):
    if n not in iso_c:
        ni = b.FindNet(n) if n else None
        s = ni.GetNetClassName() if ni else ''
        m = re.search(r'ISO_[A-Z]', s or '')
        iso_c[n] = m.group(0) if m else ''
    return iso_c[n]


def inbx(p):
    return BX[0] <= T(p.x) <= BX[2] and BX[1] <= T(p.y) <= BX[3]


# 細かいピン: このネットのパッドで短辺が目標より細いもの
fine = []
for p in b.GetPads():
    if RX.search(p.GetNetname()):
        s = p.GetSize(pcbnew.F_Cu) if hasattr(p, 'GetSize') else p.GetSize()
        fine.append((p, min(T(s.x), T(s.y))))


def near_fine(pt, w):
    for p, s in fine:
        if s < w - 1e-6 and p.HitTest(pt):
            return True
    return False


# 1) 対象の線を集める (長い線は 0.8mm の端と真ん中に分ける)
tg = []
for t in list(b.GetTracks()):
    if t.Type() == pcbnew.PCB_VIA_T or not RX.search(t.GetNetname()):
        continue
    if any(bb.Contains(t.GetStart()) or bb.Contains(t.GetEnd()) for bb in skip):
        continue
    s0, e0 = pcbnew.VECTOR2I(t.GetStart()), pcbnew.VECTOR2I(t.GetEnd())
    L = T((e0 - s0).EuclideanNorm())
    segs = [t]
    if L > 1.8:
        k1, k2 = 0.8 / L, 1 - 0.8 / L
        p1 = pcbnew.VECTOR2I(int(s0.x + (e0.x - s0.x) * k1), int(s0.y + (e0.y - s0.y) * k1))
        p2 = pcbnew.VECTOR2I(int(s0.x + (e0.x - s0.x) * k2), int(s0.y + (e0.y - s0.y) * k2))
        t.SetEnd(p1)
        for q0, q1 in ((p1, p2), (p2, e0)):
            u = pcbnew.PCB_TRACK(b); u.SetStart(q0); u.SetEnd(q1); u.SetWidth(t.GetWidth()); u.SetLayer(t.GetLayer())
            u.SetNet(t.GetNet()); b.Add(u); segs.append(u)
    for u in segs:
        mid = pcbnew.VECTOR2I((u.GetStart().x + u.GetEnd().x) // 2, (u.GetStart().y + u.GetEnd().y) // 2)
        w = WM if inbx(mid) else WB
        if near_fine(u.GetStart(), w) or near_fine(u.GetEnd(), w):
            if T((u.GetEnd() - u.GetStart()).EuclideanNorm()) <= 0.85:
                continue
        if T(u.GetWidth()) < w - 1e-6:
            tg.append((u, w))

# 2) 障害物の格子
G = 2.0
grid = collections.defaultdict(list)
CU = [l for l in b.GetEnabledLayers().CuStack()]


def cells(bb):
    return [(i, j) for i in range(int(T(bb.GetLeft()) // G), int(T(bb.GetRight()) // G) + 1)
            for j in range(int(T(bb.GetTop()) // G), int(T(bb.GetBottom()) // G) + 1)]


for it in list(b.GetTracks()) + list(b.GetPads()):
    for l in CU:
        if it.IsOnLayer(l):
            for c in cells(it.GetBoundingBox()):
                grid[(l, c)].append(it)
edge = b.GetBoardEdgesBoundingBox()


def hits(t, w):
    # 当たるもの: (動かせない (パッド・ロック・端) があるか, はがせる線・ビアの一覧)
    l = t.GetLayer()
    sg = pcbnew.SHAPE_SEGMENT(t.GetStart(), t.GetEnd(), mm(w))
    bb = sg.BBox()
    why.clear()
    if (bb.GetLeft() < edge.GetLeft() + mm(EDGE) or bb.GetRight() > edge.GetRight() - mm(EDGE) or
            bb.GetTop() < edge.GetTop() + mm(EDGE) or bb.GetBottom() > edge.GetBottom() - mm(EDGE)):
        why.append('edge')
        return True, []
    bb.Inflate(mm(ISO_CLR))
    ni = iso(t.GetNetname())
    hard, soft, seen = False, [], set()
    for c in cells(bb):
        for it in grid.get((l, c), []):
            if id(it) in seen or id(it) in removed or it.GetNetCode() == t.GetNetCode():
                continue
            seen.add(id(it))
            on = it.GetNetname()
            need = ISO_CLR if (on and not on.startswith('unconnected-') and iso(on) != ni) else CLR
            if need == ISO_CLR and it.Type() == pcbnew.PCB_PAD_T and it.GetParentFootprint().GetReference() in BRIDGE:
                need = CLR
            if it.GetEffectiveShape(l).Collide(sg, mm(need)):
                if (it.Type() == pcbnew.PCB_PAD_T or it.IsLocked() or RX.search(on)
                        or any(bb2.Contains(it.GetPosition()) for bb2 in skip)):
                    hard = True
                    why.append(('pad ' + it.GetParentFootprint().GetReference()) if it.Type() == pcbnew.PCB_PAD_T
                               else ('lock ' if it.IsLocked() else '') + on[:20])
                else:
                    soft.append(it)
    return hard, soft


victims = set()
removed = set()
why = []
stuck = collections.Counter()
cnt = collections.Counter()
for t, w in sorted(tg, key=lambda q: -q[1]):
    w0 = T(t.GetWidth())
    ww = w
    while ww > w0 + 1e-6:
        hard, soft = hits(t, ww)
        if not hard:
            for it in soft:
                if id(it) in removed:
                    continue
                victims.add(it.GetNetname())
                removed.add(id(it))
                b.Remove(it)  # 格子には残るが、removed で飛ばす
            t.SetWidth(mm(ww))
            for c in cells(t.GetBoundingBox()):
                grid[(t.GetLayer(), c)].append(t)
            cnt[ww] += 1
            break
        ww = round(ww - 0.1, 2)
    else:
        cnt['そのまま'] += 1
        hits(t, w0 + 0.1)
        stuck[' / '.join(sorted(set(why)))[:80]] += 1
print('幅ごとの区間', dict(cnt))
print('止まった理由', stuck.most_common(15))
print('はがしたネット', len(victims), sorted(victims))
if vout:
    json.dump(sorted(victims), open(vout, 'w', encoding='utf8'), ensure_ascii=False)
# ゾーンの塗り直しはしない (線を消したあとの Zones() は落ちることがある)。別の処理で zone_fill.py を流すこと
b.Save(PCB)
print('保存', PCB)
