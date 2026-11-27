# 小さな降圧 (SY8113B: U602 / U603 / U706) のまわりを表のベタとビアで直す (2026-11-25)
#   部品は動かさない (入力コンデンサは IC の真下、ブートは真上、帰還は左で、配置はデータシートの例に近い)。
#   - LX: ピン 6 → ブートのコンデンサ (LX 側) → コイルのパッド 1 を表のベタ (矩形の和) に
#   - 出力: コイルのパッド 2 → 出力コンデンサを表のベタに。出力の面 (内層) へのビアを 2 個
#   - GND: ピン 2・入力コンデンサ・出力コンデンサの GND パッドの横に GND の面へのビア (短い線 0.3)
#   - ビアは全層で他のネットの銅から 0.2 以上、穴どうし 0.6 以上の場所を探して置く
#   同じ名前のゾーンがあれば作り直す。ビアは何度も足さないよう、1 回だけ流すこと。
# usage: python buck_pour.py pcb
import sys, math
import pcbnew

PCB = sys.argv[1]
mm = pcbnew.FromMM
T = pcbnew.ToMM
b = pcbnew.LoadBoard(PCB)
CU = [l for l in b.GetEnabledLayers().CuStack()]


def P(x, y):
    return pcbnew.VECTOR2I(mm(x), mm(y))


def pad(ref, num):
    return [q for q in b.FindFootprintByReference(ref).Pads() if q.GetNumber() == num][0]


def xy(p):
    return T(p.GetPosition().x), T(p.GetPosition().y)


def free(x, y, net, seg_from=None):
    c = P(x, y)
    via = pcbnew.SHAPE_CIRCLE(c, mm(0.3))
    lo = seg_from if seg_from is not None else c
    bx0, bx1 = min(lo.x, c.x) - mm(1.5), max(lo.x, c.x) + mm(1.5)
    by0, by1 = min(lo.y, c.y) - mm(1.5), max(lo.y, c.y) + mm(1.5)
    sg = pcbnew.SHAPE_SEGMENT(seg_from, c, mm(0.3)) if seg_from is not None else None
    for t in b.GetTracks():
        bb = t.GetBoundingBox()
        if bb.GetLeft() > bx1 or bb.GetRight() < bx0 or bb.GetTop() > by1 or bb.GetBottom() < by0:
            continue
        if t.Type() == pcbnew.PCB_VIA_T:
            if (t.GetPosition() - c).EuclideanNorm() < mm(0.6 + (0.25 if t.GetNetCode() != net.GetNetCode() else 0)):
                return False
        if t.GetNetCode() == net.GetNetCode():
            continue
        for l in CU:
            if t.IsOnLayer(l) and t.GetEffectiveShape(l).Collide(via, mm(0.2)):
                return False
        if sg is not None and t.IsOnLayer(pcbnew.F_Cu) and t.GetEffectiveShape(pcbnew.F_Cu).Collide(sg, mm(0.2)):
            return False
    for pd in b.GetPads():
        q = pd.GetPosition()
        if q.x < bx0 - mm(4) or q.x > bx1 + mm(4) or q.y < by0 - mm(4) or q.y > by1 + mm(4):
            continue
        if pd.HasHole() and (q - c).EuclideanNorm() < mm(0.3 + T(pd.GetDrillSize().x) / 2 + 0.25):
            return False
        if pd.GetNetCode() == net.GetNetCode():
            continue
        for l in CU:
            if pd.IsOnLayer(l) and pd.GetEffectiveShape(l).Collide(via, mm(0.2)):
                return False
        if sg is not None and pd.IsOnLayer(pcbnew.F_Cu) and pd.GetEffectiveShape(pcbnew.F_Cu).Collide(sg, mm(0.2)):
            return False
    return True


def spot(x, y, net, seg_from=None, rmax=1.6):
    for r in [0] + [0.1 * i for i in range(1, int(rmax / 0.1) + 1)]:
        for a in range(0, 360, 20 if r else 360):
            xx, yy = x + r * math.cos(math.radians(a)), y + r * math.sin(math.radians(a))
            if free(xx, yy, net, seg_from):
                return xx, yy
    return None


def via_to(ref, num, dx, dy, netname):
    # パッドの中心から (dx, dy) のあたりにビアを置き、0.3 の線でつなぐ
    net = b.FindNet(netname)
    pd = pad(ref, num)
    x0, y0 = xy(pd)
    q = spot(x0 + dx, y0 + dy, net, pd.GetPosition())
    if q is None:
        print('  ビアが置けない', ref, num); return
    v = pcbnew.PCB_VIA(b); v.SetPosition(P(*q)); v.SetWidth(mm(0.6)); v.SetDrill(mm(0.3)); v.SetNet(net); b.Add(v)
    t = pcbnew.PCB_TRACK(b); t.SetStart(pd.GetPosition()); t.SetEnd(P(*q)); t.SetWidth(mm(0.3)); t.SetLayer(pcbnew.F_Cu)
    t.SetNet(net); b.Add(t)
    print(f'  ビア {netname} {ref}.{num} ({q[0]:.2f},{q[1]:.2f})')


def via_free(x, y, netname):
    net = b.FindNet(netname)
    q = spot(x, y, net)
    if q is None:
        print('  ビアが置けない', netname, x, y); return
    v = pcbnew.PCB_VIA(b); v.SetPosition(P(*q)); v.SetWidth(mm(0.6)); v.SetDrill(mm(0.3)); v.SetNet(net); b.Add(v)
    print(f'  ビア {netname} ({q[0]:.2f},{q[1]:.2f})')


def rects_zone(name, netname, rects, pri=6):
    ps = pcbnew.SHAPE_POLY_SET()
    for x0, y0, x1, y1 in rects:
        r = pcbnew.SHAPE_POLY_SET()
        r.NewOutline()
        for x, y in ((x0, y0), (x1, y0), (x1, y1), (x0, y1)):
            r.Append(mm(x), mm(y))
        ps.BooleanAdd(r)
    for z in list(b.Zones()):
        if z.GetZoneName() == name:
            b.Remove(z)
    z = pcbnew.ZONE(b)
    z.SetLayer(pcbnew.F_Cu)
    z.SetNet(b.FindNet(netname))
    z.SetZoneName(name)
    ol = z.Outline()
    ol.NewOutline()
    o = ps.Outline(0)
    for i in range(o.PointCount()):
        p = o.CPoint(i)
        ol.Append(p.x, p.y)
    z.SetAssignedPriority(pri)
    z.SetLocalClearance(mm(0.25))
    z.SetMinThickness(mm(0.2))
    z.SetPadConnection(pcbnew.ZONE_CONNECTION_FULL)
    z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
    b.Add(z)


# (IC, ブートのコンデンサ, コイル, 入力コンデンサ, 出力コンデンサ, GND, 出力ネット, 出力コンデンサの出力側パッド)
CFG = [('U602', 'C604', 'L601', 'C603', 'C605', 'GND_A', '+5V_A', '1'),
       ('U603', 'C607', 'L602', 'C606', 'C608', 'GND_A', '+3.3V_A', '1'),
       ('U706', 'C705', 'L701', 'C704', 'C706', 'GND_D', '+5V_D', '1')]
for ic, cbs, L, cin, cout, gnd, vout, cop in CFG:
    print(ic)
    p6x, p6y = xy(pad(ic, '6'))
    bx, by = xy(pad(cbs, '2'))
    l1x, l1y = xy(pad(L, '1'))
    l2x, l2y = xy(pad(L, '2'))
    ox, oy = xy(pad(cout, cop))
    lx_net = pad(ic, '6').GetNetname()
    rects_zone(ic + '_LX', lx_net, [
        (min(bx, p6x) - 0.55, by - 0.6, max(bx, p6x) + 0.7, p6y + 0.3),
        (p6x, l1y - 1.95, l1x + 0.7, p6y + 0.3),
        (l1x - 0.7, l1y - 1.95, l1x + 0.7, l1y + 1.95)])
    rects_zone(ic + '_OUT', vout, [
        (l2x - 0.7, l2y - 1.95, l2x + 1.8, l2y + 1.95),
        (min(l2x - 0.7, ox - 0.6), min(l2y - 1.95, oy - 0.8), max(l2x + 0.7, ox + 0.8), max(l2y + 1.95, oy + 0.8))])
    via_to(ic, '2', -1.3, 0.0, gnd)
    via_to(cin, '2', -1.2, 0.0, gnd)
    gn = '2' if cop == '1' else '1'
    gx, gy = xy(pad(cout, gn))
    d = math.hypot(gx - l2x, gy - l2y)
    via_to(cout, gn, 1.2 * (gx - l2x) / d, 1.2 * (gy - l2y) / d, gnd)
    via_free(l2x + 1.3, l2y - 1.0, vout)
    via_free(l2x + 1.3, l2y + 1.0, vout)

pcbnew.ZONE_FILLER(b).Fill(b.Zones())
b.Save(PCB)
print('保存', PCB)
