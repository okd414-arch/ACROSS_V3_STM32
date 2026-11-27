# 電源の線を、間隔が取れる範囲で太くする (2026-11-25、配線が終わったあと。古い widen_power.py は DRC を回す方式)
#   - ネットごとに目標の幅を決め、広い順 (0.1 刻み) に試して、他のネットの銅 (線・ビア・パッド) との間隔が取れる一番太い幅にする
#   - 間隔: 絶縁ドメイン (ネットクラス ISO_A / ISO_C / ISO_D) が違えば 2.0 (絶縁部品のパッドは除く)、それ以外は 0.2。基板の端から 0.4
#   - 長い線 (> 2mm) は、両端 0.8mm と真ん中 (1mm ほどずつ) に分けてから試す (細いピンの近くは細いまま、途中は太く)
#   - BGA・QFN の中 (U1 U301 U302 U104 U401 U501 の外形の中) は触らない
#   - ゾーン (ベタ) はあとで塗り直すので、障害物に入れない
# usage: python widen_power2.py pcb
import sys, re, collections, os
import pcbnew

PCB = sys.argv[1]
mm = pcbnew.FromMM
T = pcbnew.ToMM
b = pcbnew.LoadBoard(PCB)

# (ネットの正規表現, 目標の幅) 上から順に
TARGET = [
    (r'^\+24V$|^Net-\(J101-Pin_2\)$|^Net-\(D101-K\)$|^Net-\(D102-K\)$', 1.0),
    (r'^Net-\(C110-Pad1\)$|^Net-\(D103-K\)$', 1.2),
    (r'^\+5V$|VBUS', 0.6),
    (r'^Net-\(U(602|603|706)-LX\)$', 0.6),
    (r'^\+9V_[AD]$|^\+5V_[AD]$|^\+3\.3V_A$|^VTT_DDR$', 0.5),
    (r'^\+3\.3V$|^VDD$|^VDD_CORE$|^VDD_DDR$|^VDDA$|^VDD_SD$|^VDD_USB$', 0.4),
    (r'Z_24V$', 0.3),
]
# もう一段太くする設定 (環境変数 WP_PROFILE=big、2026-11-25)。電流の多い順に並べる (先に太くしたものが場所を取る)
if os.environ.get('WP_PROFILE') == 'big':
    TARGET = [
        (r'^\+24V$|^Net-\(J101-Pin_2\)$|^Net-\(D101-K\)$|^Net-\(D102-K\)$', 2.0),
        (r'^Net-\(C110-Pad1\)$|^Net-\(D103-K\)$', 2.0),
        (r'^\+5V$', 1.2),
        (r'^VDD_CORE$|^VDD_DDR$', 0.6),
        (r'^VDD$|^\+3\.3V$', 0.6),
        (r'VBUS', 0.8),
        (r'^Net-\(U(602|603|706)-LX\)$', 0.8),
        (r'^\+9V_[AD]$|^\+5V_[AD]$|^\+3\.3V_A$|^VTT_DDR$', 0.6),
        (r'^VDDA$|^VDD_SD$|^VDD_USB$', 0.5),
    ]
    ORDER = [t for _, t in TARGET]
SKIP_FP = ['U1', 'U301', 'U302', 'U104', 'U401', 'U501']
BRIDGE = ('U601', 'U606', 'U607', 'U609', 'U701', 'U702', 'U703', 'U704', 'U705', 'U707')
CLR, ISO_CLR, EDGE = 0.2, 2.0, 0.4

skip_boxes = []
for r in SKIP_FP:
    f = b.FindFootprintByReference(r)
    if f:
        cy = f.GetCourtyard(pcbnew.B_CrtYd if f.IsFlipped() else pcbnew.F_CrtYd)
        skip_boxes.append(cy.BBox() if cy.OutlineCount() else f.GetBoundingBox())


def in_skip(p):
    return any(bb.Contains(p) for bb in skip_boxes)


iso_cache = {}


def iso(net):
    if net not in iso_cache:
        ni = b.FindNet(net) if net else None
        s = ''
        if ni:
            try:
                s = ni.GetNetClassName()
            except Exception:
                s = ''
        m = re.search(r'ISO_[A-Z]', s or '')
        iso_cache[net] = m.group(0) if m else ''
    return iso_cache[net]


def target_of(n):
    for rx, tw in TARGET:
        if re.search(rx, n):
            return tw
    return None


# 1) 長い線を分ける
targets = []
for t in list(b.GetTracks()):
    if t.Type() == pcbnew.PCB_VIA_T:
        continue
    w = target_of(t.GetNetname())
    if w is None or T(t.GetWidth()) >= w - 1e-6 or in_skip(t.GetStart()) or in_skip(t.GetEnd()):
        continue
    a, e = pcbnew.VECTOR2I(t.GetStart()), pcbnew.VECTOR2I(t.GetEnd())  # 写す (参照のままだと SetEnd で変わる)
    L = T((e - a).EuclideanNorm())
    if L > 2.0:
        # 両端 0.8mm と、真ん中を 1mm ほどの区間に分ける
        ks = [0.8 / L] + [0.8 / L + (1 - 1.6 / L) * i / max(1, round(L - 1.6)) for i in range(1, max(1, round(L - 1.6)))] + [1 - 0.8 / L]
        pts = [pcbnew.VECTOR2I(int(a.x + (e.x - a.x) * k), int(a.y + (e.y - a.y) * k)) for k in ks]
        t.SetEnd(pts[0])
        segs = [t]
        for s0, s1 in zip(pts, pts[1:] + [e]):
            u = pcbnew.PCB_TRACK(b); u.SetStart(s0); u.SetEnd(s1); u.SetWidth(t.GetWidth()); u.SetLayer(t.GetLayer())
            u.SetNet(t.GetNet()); b.Add(u); segs.append(u)
        targets += [(s, w) for s in segs]
    else:
        targets.append((t, w))

# 2) 障害物の格子 (2mm のます) を層ごとに
G = 2.0
grid = collections.defaultdict(list)


def cells(bb):
    x0, y0 = int(T(bb.GetLeft()) // G), int(T(bb.GetTop()) // G)
    x1, y1 = int(T(bb.GetRight()) // G), int(T(bb.GetBottom()) // G)
    return [(i, j) for i in range(x0, x1 + 1) for j in range(y0, y1 + 1)]


CU = [l for l in b.GetEnabledLayers().CuStack()]
for it in list(b.GetTracks()) + list(b.GetPads()):
    for l in CU:
        if it.IsOnLayer(l):
            for c in cells(it.GetBoundingBox()):
                grid[(l, c)].append(it)

edge = b.GetBoardEdgesBoundingBox()


def ok(t, w):
    l = t.GetLayer()
    sg = pcbnew.SHAPE_SEGMENT(t.GetStart(), t.GetEnd(), mm(w))
    bb = sg.BBox()
    if (bb.GetLeft() < edge.GetLeft() + mm(EDGE) or bb.GetRight() > edge.GetRight() - mm(EDGE) or
            bb.GetTop() < edge.GetTop() + mm(EDGE) or bb.GetBottom() > edge.GetBottom() - mm(EDGE)):
        return False
    bb.Inflate(mm(ISO_CLR))
    ni = iso(t.GetNetname())
    seen = set()
    for c in cells(bb):
        for it in grid.get((l, c), []):
            if id(it) in seen or it.GetNetCode() == t.GetNetCode():
                continue
            seen.add(id(it))
            on = it.GetNetname()
            need = ISO_CLR if (on and not on.startswith('unconnected-') and iso(on) != ni) else CLR
            if need == ISO_CLR and it.Type() == pcbnew.PCB_PAD_T and it.GetParentFootprint().GetReference() in BRIDGE:
                need = CLR
            if it.GetEffectiveShape(l).Collide(sg, mm(need)):
                return False
    return True


cnt = collections.Counter()
for t, w in (sorted(targets, key=lambda q: [i for i, (rx, _) in enumerate(TARGET) if re.search(rx, q[0].GetNetname())][0]) if os.environ.get('WP_PROFILE') == 'big' else sorted(targets, key=lambda q: -q[1])):
    w0 = T(t.GetWidth())
    ww = w
    done = False
    while ww > w0 + 1e-6:
        if ok(t, ww):
            t.SetWidth(mm(ww))
            for c in cells(t.GetBoundingBox()):
                if t not in grid[(t.GetLayer(), c)]:
                    grid[(t.GetLayer(), c)].append(t)
            cnt[(t.GetNetname()[:24], round(ww, 2))] += 1
            done = True
            break
        ww = round(ww - 0.1, 2)
    if not done:
        cnt[(t.GetNetname()[:24], 'same')] += 1

for k, v in sorted(cnt.items(), key=lambda q: str(q[0])):
    print(k, v)
pcbnew.ZONE_FILLER(b).Fill(b.Zones())
b.Save(PCB)
print('保存', PCB)
