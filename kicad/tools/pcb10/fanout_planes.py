# 面のネット (GND・VDD など) の表面実装パッドに、面へ落とすビアを置く (2026-11-21)
#   Freerouting は面への引き出しが苦手 (r1 で未配線 772 本のうち 658 本がこれ) なので、先に機械的に置く。
#   - BGA (0.8mm ピッチ): ボールの斜め 4 方向の格子の中心 (ドッグボーン)。部品の中心から外向きを優先
#   - 大きいパッド (放熱パッド): パッドの中にビアを格子状に並べる
#   - その他: パッドの外側 (部品の中心から遠い向きを優先) に、短い線でつないでビア
#   重なりは pcbnew の形状 (Collide) で調べる。置いたあと DRC で違反したビアは消す (drc は別に drc_sum.py)
# usage: python fanout_planes.py [pcb]
import sys, math
import pcbnew

PCB = sys.argv[1] if len(sys.argv) > 1 else 'C:/MyWorks/ACROSS_V3_STM32/kicad/ACROSS_V3.kicad_pcb'
VIA_D, VIA_H = 0.45, 0.2
CLR = 0.15          # 他のネットとの間隔 (電源クラスの値)
CLR_BGA = 0.1       # BGA の中 (.kicad_dru の bga_escape_clearance と同じ)
CUR_CLR = [CLR]
W_BGA, W_PAD = 0.2, 0.3
EP_AREA = 1.5       # これより大きいパッドは放熱パッドとして中にビアを並べる
EP_PITCH = 1.0

mm = pcbnew.FromMM
b = pcbnew.LoadBoard(PCB)

# 面のあるネットと、その層 (内層)
plane = {}
for z in b.Zones():
    if z.GetIsRuleArea():
        continue
    inner = [l for l in z.GetLayerSet().Seq() if pcbnew.IsInnerCopperLayer(l)]
    if inner:
        plane.setdefault(z.GetNetname(), []).append(z)


def in_plane(net, pos):
    for z in plane.get(net, []):
        if z.Outline().Contains(pos):
            return True
    return False


# 障害物 (層ごと): (net, shape)
OBST = []  # (netcode, layerset_is_front, layerset_is_back, shape, inner)


def add_obst(net, lset, shape):
    OBST.append((net, lset.Contains(pcbnew.F_Cu), lset.Contains(pcbnew.B_Cu), shape,
                 any(pcbnew.IsInnerCopperLayer(l) for l in lset.Seq())))


def poly_of(item, lay):
    ps = pcbnew.SHAPE_POLY_SET()
    item.TransformShapeToPolygon(ps, lay, 0, mm(0.005), pcbnew.ERROR_INSIDE)
    return ps


def add_item(item):
    """部品のパッド・ビア・線を障害物に登録 (外層ごと + 内層は穴あき部品とビア)"""
    for lay in (pcbnew.F_Cu, pcbnew.B_Cu):
        if item.IsOnLayer(lay):
            ls = pcbnew.LSET(); ls.AddLayer(lay)
            add_obst(item.GetNetCode(), ls, poly_of(item, lay))
    if item.Type() == pcbnew.PCB_VIA_T or (item.Type() == pcbnew.PCB_PAD_T and item.GetDrillSize().x > 0):
        ls = pcbnew.LSET(); ls.AddLayer(pcbnew.In1_Cu)
        add_obst(item.GetNetCode(), ls, poly_of(item, pcbnew.F_Cu if item.Type() == pcbnew.PCB_VIA_T else pcbnew.In1_Cu))


for f in b.GetFootprints():
    for p in f.Pads():
        add_item(p)
for t in b.GetTracks():
    add_item(t)

edge = b.GetBoardEdgesBoundingBox()
# 全体を格子に分けて探す
G = mm(2)
grid = {}


def gkey(x, y):
    return (x // G, y // G)


def index(i):
    bb = OBST[i][3].BBox()
    for gx in range(bb.GetLeft() // G, bb.GetRight() // G + 1):
        for gy in range(bb.GetTop() // G, bb.GetBottom() // G + 1):
            grid.setdefault((gx, gy), []).append(i)


for i in range(len(OBST)):
    index(i)


def near(bb):
    s = set()
    for gx in range(bb.GetLeft() // G - 1, bb.GetRight() // G + 2):
        for gy in range(bb.GetTop() // G - 1, bb.GetBottom() // G + 2):
            s.update(grid.get((gx, gy), ()))
    return s


class Q:
    """問い合わせの形: 点 (円) か 線分"""
    def __init__(self, a, r, b_=None):
        self.a, self.r, self.b = a, r, b_

    def BBox(self):
        e = self.b or self.a
        x0, x1 = min(self.a.x, e.x) - self.r, max(self.a.x, e.x) + self.r
        y0, y1 = min(self.a.y, e.y) - self.r, max(self.a.y, e.y) + self.r
        return pcbnew.BOX2I(pcbnew.VECTOR2I(x0, y0), pcbnew.VECTOR2I(x1 - x0, y1 - y0))


def circ(p, r):
    return Q(p, r)


def segq(a, b_, w):
    return Q(a, w // 2, b_)


def free(net, q, front, back, inner):
    clr = mm(CUR_CLR[0])
    for i in near(q.BBox()):
        n, f_, b_, s, inn = OBST[i]
        if n == net:
            continue
        if not ((front and f_) or (back and b_) or (inner and inn)):
            continue
        hit = s.Collide(q.a, q.r + clr) if q.b is None else s.Collide(pcbnew.SEG(q.a, q.b), q.r + clr)
        if hit:
            return False
    return True


HOLES = []  # (x, y, 穴の半径) すべての穴 (ネットに関係なく、穴どうしの間隔 0.25 を守る)
for f in b.GetFootprints():
    for p in f.Pads():
        if p.GetDrillSize().x > 0:
            HOLES.append((p.GetPosition().x, p.GetPosition().y, max(p.GetDrillSize().x, p.GetDrillSize().y) // 2))
for t in b.GetTracks():
    if t.Type() == pcbnew.PCB_VIA_T:
        HOLES.append((t.GetPosition().x, t.GetPosition().y, t.GetDrillValue() // 2))


def hole_ok(pos):
    lim = mm(VIA_H) // 2 + mm(0.26)
    return all(math.hypot(pos.x - x, pos.y - y) >= lim + r for x, y, r in HOLES)


def ok_via(net, pos):
    if not hole_ok(pos):
        return False
    if not edge.Contains(pos):
        return False
    m = mm(0.6)
    if not (edge.GetLeft() + m < pos.x < edge.GetRight() - m and edge.GetTop() + m < pos.y < edge.GetBottom() - m):
        return False
    return in_plane(b.FindNet(net).GetNetname(), pos) and free(net, circ(pos, mm(VIA_D) // 2), True, True, True)


def put(net, pos, pad=None, lay=pcbnew.F_Cu, w=W_PAD):
    v = pcbnew.PCB_VIA(b)
    v.SetPosition(pos)
    v.SetWidth(mm(VIA_D))
    v.SetDrill(mm(VIA_H))
    v.SetNetCode(net)
    v.SetLocked(True)  # Freerouting が動かさないように
    b.Add(v)
    HOLES.append((pos.x, pos.y, mm(VIA_H) // 2))
    n0 = len(OBST); add_item(v)
    for i in range(n0, len(OBST)):
        index(i)
    if pad is not None:
        t = pcbnew.PCB_TRACK(b)
        t.SetStart(pad)
        t.SetEnd(pos)
        t.SetWidth(mm(w))
        t.SetLayer(lay)
        t.SetNetCode(net)
        t.SetLocked(True)
        b.Add(t)
        n0 = len(OBST); add_item(t)
        for i in range(n0, len(OBST)):
            index(i)


def has_via(p):
    bb = p.GetBoundingBox()
    for t in b.GetTracks():
        if t.Type() == pcbnew.PCB_VIA_T and t.GetNetCode() == p.GetNetCode() and bb.Contains(t.GetPosition()):
            return True
    return False


stat = {'bga': 0, 'ep': 0, 'pad': 0, 'fail': 0, 'skip': 0}
fails = []
vias_now = [t for t in b.GetTracks() if t.Type() == pcbnew.PCB_VIA_T]
track_ends = {}
for t in b.GetTracks():
    if t.Type() == pcbnew.PCB_TRACE_T:
        track_ends.setdefault(t.GetNetCode(), []).extend([t.GetStart(), t.GetEnd()])
for f in b.GetFootprints():
    pads = list(f.Pads())
    bga = len(pads) >= 60 and all(p.GetShape() == pcbnew.PAD_SHAPE_CIRCLE for p in pads[:20])
    fc = f.GetPosition()
    CUR_CLR[0] = CLR_BGA if bga else CLR
    for p in pads:
        net = p.GetNetname()
        if net not in plane or p.GetAttribute() != pcbnew.PAD_ATTRIB_SMD:
            continue
        lay = pcbnew.F_Cu if p.IsOnLayer(pcbnew.F_Cu) else pcbnew.B_Cu
        nc = p.GetNetCode()
        pc = p.GetPosition()
        if any(v.GetNetCode() == nc and p.HitTest(v.GetPosition()) for v in vias_now) or \
                any(p.HitTest(e) for e in track_ends.get(nc, ())):  # すでに線かビアがつながっている
            stat['skip'] += 1
            continue
        sx, sy = pcbnew.ToMM(p.GetSize().x), pcbnew.ToMM(p.GetSize().y)
        # 放熱パッド
        if sx * sy >= EP_AREA and not bga:
            bb = p.GetBoundingBox()
            # 部品にすでに放熱ビア (穴あきパッド) があるなら置かない
            if any(o.GetDrillSize().x > 0 and bb.Contains(o.GetPosition()) for o in pads):
                stat['skip'] += 1
                continue
            nx = max(1, int((pcbnew.ToMM(bb.GetWidth()) - 0.3) // EP_PITCH))
            ny = max(1, int((pcbnew.ToMM(bb.GetHeight()) - 0.3) // EP_PITCH))
            k = 0
            for ix in range(nx):
                for iy in range(ny):
                    q = pcbnew.VECTOR2I(int(pc.x + mm((ix - (nx - 1) / 2) * EP_PITCH)), int(pc.y + mm((iy - (ny - 1) / 2) * EP_PITCH)))
                    if p.HitTest(q) and hole_ok(q) and in_plane(net, q) and free(nc, circ(q, mm(VIA_D) // 2), True, True, True):
                        put(nc, q)
                        k += 1
            if k:
                stat['ep'] += k
                continue
        dx, dy = pc.x - fc.x, pc.y - fc.y
        cands = []
        if bga:
            h = mm(0.4)
            for sx_ in (1, -1):
                for sy_ in (1, -1):
                    sc = sx_ * dx + sy_ * dy  # 外向きほど大きい
                    cands.append((-sc, pcbnew.VECTOR2I(pc.x + sx_ * h, pc.y + sy_ * h)))
            w = W_BGA
        else:
            hx, hy = p.GetBoundingBox().GetWidth() // 2, p.GetBoundingBox().GetHeight() // 2
            for d in (0.4, 0.7, 1.1):
                r = mm(VIA_D / 2 + d)
                for ux, uy in ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)):
                    q = pcbnew.VECTOR2I(int(pc.x + ux * (hx + r) / (1.414 if ux and uy else 1) * (1 if not uy else 1)),
                                        int(pc.y + uy * (hy + r) / (1.414 if ux and uy else 1)))
                    sc = ux * dx + uy * dy
                    cands.append((d * 10 - sc / max(1, math.hypot(dx, dy)), q))
            w = min(W_PAD, pcbnew.ToMM(min(p.GetSize().x, p.GetSize().y)))
        CUR_CLR[0] = CLR_BGA if bga else CLR
        cands.sort(key=lambda c: c[0])
        done = False
        ls = pcbnew.LSET(); ls.AddLayer(lay)
        for _, q in cands:
            if not ok_via(nc, q):
                continue
            seg = segq(pc, q, mm(w))
            if not free(nc, seg, lay == pcbnew.F_Cu, lay == pcbnew.B_Cu, False):
                continue
            put(nc, q, pc, lay, w)
            done = True
            stat['bga' if bga else 'pad'] += 1
            break
        if not done:
            stat['fail'] += 1
            fails.append(f'{f.GetReference()}-{p.GetNumber()}({net})')
print(stat)
print('置けなかった:', ' '.join(fails[:80]), '...' if len(fails) > 80 else '')
pcbnew.ZONE_FILLER(b).Fill(b.Zones())
b.Save(PCB)
