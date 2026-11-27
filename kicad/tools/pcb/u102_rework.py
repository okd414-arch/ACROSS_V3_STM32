# 24V→5V 降圧 (U102 TPS54360) まわりの作り直し (2026-11-25)
#   方針 (TPS54360 データシートの配置例と、一般的な DC-DC の配線指針):
#   - 熱いループ (入力コンデンサ → VIN → 内部 FET → SW → ダイオード D103 → GND → 入力コンデンサ) を最短に。
#     入力コンデンサ C104 (4.7u)・C106 (100n) は VIN ピン (左) の横、D103 は IC の上、アノードの GND と入力コンデンサの GND を表の GND ベタで直結
#   - SW は表のベタ (ピン 8 → C107 → D103 のカソード → L101)。ブートの C107 は IC の真上
#   - L101 は右上。出力 (5V、eFuse の前) は表のベタで L101 → 出力コンデンサ → U103 へ
#   - 帰還 (FB) と補償 (COMP) は SW の反対側 (右下)、EN・RT は左下。SW の銅から離す
#   - C103 (電解 100u) は L101 と重ならないよう上へ。TP104・R112 は少しずらす (線の端も一緒に)
#   局所のネットの線・ビアは全部消し、電源 (+24V / GND / 出力) は範囲の中だけ消す。あとで mr_route で引く。
# usage: python u102_rework.py pcb
import sys
import pcbnew

PCB = sys.argv[1]
mm = pcbnew.FromMM
T = pcbnew.ToMM
b = pcbnew.LoadBoard(PCB)


def P(x, y):
    return pcbnew.VECTOR2I(mm(x), mm(y))


LOCAL = {'Net-(U102-BOOT)', 'Net-(U102-EN)', 'Net-(U102-RT{slash}CLK)', 'Net-(U102-FB)', 'Net-(U102-COMP)',
         'Net-(C109-Pad1)', 'Net-(D103-K)'}
PWR = {'+24V', 'GND', 'Net-(C110-Pad1)'}
BOX = (1.5, 30.5, 29.3, 56.0)
VOUT = 'Net-(C110-Pad1)'


def inbox(p):
    return BOX[0] <= T(p.x) <= BOX[2] and BOX[1] <= T(p.y) <= BOX[3]


def hits(t):
    if t.Type() == pcbnew.PCB_VIA_T:
        return inbox(t.GetPosition())
    a, e = t.GetStart(), t.GetEnd()
    return any(inbox(pcbnew.VECTOR2I(int(a.x + (e.x - a.x) * k / 10), int(a.y + (e.y - a.y) * k / 10))) for k in range(11))


# 1) 少しずらす部品 (線の端も一緒に): TP104、R112
tracks = [t for t in b.GetTracks() if t.Type() != pcbnew.PCB_VIA_T]
for ref, dx, dy in (('TP104', 0.0, -1.2), ('R112', 0.0, -0.55)):
    fp = b.FindFootprintByReference(ref)
    d = P(dx, dy)
    for pd in fp.Pads():
        for t in tracks:
            if t.GetNetCode() != pd.GetNetCode() or not pd.IsOnLayer(t.GetLayer()):
                continue
            for get, set_ in ((t.GetStart, t.SetStart), (t.GetEnd, t.SetEnd)):
                if pd.HitTest(get()):
                    set_(get() + d)
    fp.Move(d)

# 2) 線・ビアを消す
rm = []
for t in b.GetTracks():
    n = t.GetNetname()
    if n in LOCAL or (n in PWR and hits(t)):
        rm.append(t)
for t in rm:
    b.Remove(t)
print('消した線・ビア', len(rm))

# 3) 部品の位置 (x, y, 角度)
PL = {
    'D103': (11.0, 37.4, 180), 'C107': (12.0, 42.1, 0), 'L101': (21.9, 42.3, 0),
    'C103': (22.3, 33.0, 0), 'C104': (4.9, 43.2, 90), 'C106': (7.4, 44.6, 90),
    'C113': (28.1, 41.3, 270),
    'C108': (18.0, 47.75, 0), 'R108': (18.0, 49.5, 0), 'C109': (18.0, 51.25, 180),
    'R110': (13.4, 50.0, 180), 'R109': (15.4, 52.6, 90),
    'R105': (4.2, 47.6, 270), 'R106': (6.0, 49.4, 270), 'R107': (7.9, 51.0, 90),
}
for ref, (x, y, r) in PL.items():
    fp = b.FindFootprintByReference(ref)
    fp.SetPosition(P(x, y))
    fp.SetOrientationDegrees(r)
for ref in PL:
    fp = b.FindFootprintByReference(ref)
    print(ref, ' '.join(f'{pd.GetNumber()}:{pd.GetNetname()[:14]}@({T(pd.GetPosition().x):.2f},{T(pd.GetPosition().y):.2f})' for pd in fp.Pads()))

# 4) 表のベタ (優先度: SW 6, VIN 6, VOUT 6, GND 2)。同じ名前があれば作り直す
ZONES = [
    ('U102_SW', 'Net-(D103-K)', 6, [(12.3, 36.0), (16.3, 36.0), (16.3, 40.3), (19.9, 40.3), (19.9, 44.3), (15.6, 44.65),
                                     (13.8, 44.65), (13.8, 43.0), (12.3, 43.0)]),
    ('U102_VIN', '+24V', 6, [(3.4, 44.0), (6.4, 44.0), (6.4, 44.9), (10.1, 44.9), (10.1, 46.05), (5.0, 46.05),
                             (5.0, 47.3), (3.4, 47.3)]),
    ('U102_GND', 'GND', 2, [(3.4, 35.9), (10.2, 35.9), (10.2, 41.0), (8.1, 43.1), (8.1, 44.75), (6.55, 44.75),
                            (6.55, 43.9), (3.4, 43.9)]),
    ('U102_VOUT', VOUT, 6, [(23.9, 44.3), (23.9, 39.9), (28.0, 39.9), (28.0, 35.9), (32.6, 35.9), (32.6, 32.8),
                            (38.3, 32.8), (38.3, 38.5), (29.5, 38.5), (29.5, 44.0)]),
]
for z in list(b.Zones()):
    if z.GetZoneName() in [q[0] for q in ZONES]:
        b.Remove(z)
for name, net, pri, pts in ZONES:
    z = pcbnew.ZONE(b)
    z.SetLayer(pcbnew.F_Cu)
    z.SetNet(b.FindNet(net))
    z.SetZoneName(name)
    ol = z.Outline()
    ol.NewOutline()
    for x, y in pts:
        ol.Append(mm(x), mm(y))
    z.SetAssignedPriority(pri)
    z.SetLocalClearance(mm(0.25))
    z.SetMinThickness(mm(0.2))
    z.SetPadConnection(pcbnew.ZONE_CONNECTION_FULL)
    z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
    b.Add(z)

# 5) GND のビア (0.6/0.3): 入力コンデンサ・ダイオードの GND ベタ、帰還・補償の GND パッドの横
VIAS = [(4.0, 37.0), (5.2, 37.0), (4.0, 39.0), (5.2, 39.0), (9.6, 40.3), (8.6, 41.6),
        (3.7, 40.5), (6.2, 40.5)]
gnd = b.FindNet('GND')
CU = [l for l in b.GetEnabledLayers().CuStack()]


def free(x, y, seg_from=None):
    # 全層で、他のネットの銅から 0.2 以上、穴どうし 0.6 以上。seg_from があれば、そこからの F.Cu の線 (0.3) も確かめる
    c = P(x, y)
    via = pcbnew.SHAPE_CIRCLE(c, mm(0.3))
    lo = seg_from if seg_from is not None else c
    bx0, bx1 = min(lo.x, c.x) - mm(1.5), max(lo.x, c.x) + mm(1.5)
    by0, by1 = min(lo.y, c.y) - mm(1.5), max(lo.y, c.y) + mm(1.5)
    for t in b.GetTracks():
        bb = t.GetBoundingBox()
        if bb.GetLeft() > bx1 or bb.GetRight() < bx0 or bb.GetTop() > by1 or bb.GetBottom() < by0:
            continue
        if t.Type() == pcbnew.PCB_VIA_T:
            if (t.GetPosition() - c).EuclideanNorm() < mm(0.6 + (0.25 if t.GetNetCode() != gnd.GetNetCode() else 0)):
                return False
        if t.GetNetCode() == gnd.GetNetCode():
            continue
        for l in CU:
            if t.IsOnLayer(l) and t.GetEffectiveShape(l).Collide(via, mm(0.2)):
                return False
        if seg_from is not None and t.IsOnLayer(pcbnew.F_Cu):
            sg = pcbnew.SHAPE_SEGMENT(seg_from, c, mm(0.3))
            if t.GetEffectiveShape(pcbnew.F_Cu).Collide(sg, mm(0.2)):
                return False
    for pd in b.GetPads():
        q = pd.GetPosition()
        if abs(T(q.x) - x) > 8 or abs(T(q.y) - y) > 8:
            continue
        if pd.HasHole() and (q - c).EuclideanNorm() < mm(0.3 + T(pd.GetDrillSize().x) / 2 + 0.25):
            return False
        if pd.GetNetCode() == gnd.GetNetCode():
            continue
        for l in CU:
            if pd.IsOnLayer(l) and pd.GetEffectiveShape(l).Collide(via, mm(0.2)):
                return False
        if seg_from is not None and pd.IsOnLayer(pcbnew.F_Cu):
            sg = pcbnew.SHAPE_SEGMENT(seg_from, c, mm(0.3))
            if pd.GetEffectiveShape(pcbnew.F_Cu).Collide(sg, mm(0.2)):
                return False
    return True


def spot(x, y, seg_from=None, rmax=1.6):
    k = 0
    import math
    for r in [0] + [0.1 * i for i in range(1, int(rmax / 0.1) + 1)]:
        for a in range(0, 360, 20 if r else 360):
            xx, yy = x + r * math.cos(math.radians(a)), y + r * math.sin(math.radians(a))
            if free(xx, yy, seg_from):
                return xx, yy
    return None


def addvia(x, y):
    v = pcbnew.PCB_VIA(b)
    v.SetPosition(P(x, y))
    v.SetWidth(mm(0.6))
    v.SetDrill(mm(0.3))
    v.SetNet(gnd)
    b.Add(v)


for x0, y0 in VIAS:
    q = spot(x0, y0)
    if q is None:
        print('ビアが置けない', x0, y0); continue
    x, y = q
    addvia(x, y)
    print('GND ビア', round(x, 2), round(y, 2))
# 6) パッドの横にビアを置いて短い線でつなぐ (GND の面へ)、ピン 7 (GND) は放熱パッドへ
GV = [('R110', '2', 12.5, 51.3), ('R106', '2', 6.0, 51.5), ('R107', '1', 7.9, 53.1), ('C108', '2', 20.0, 47.75),
      ('C109', '2', 17.1, 52.6), ('C113', '2', 28.1, 43.95), ('C103', '2', 28.8, 33.0)]
for ref, num, x0, y0 in GV:
    pd = [q for q in b.FindFootprintByReference(ref).Pads() if q.GetNumber() == num][0]
    q = spot(x0, y0, pd.GetPosition())
    if q is None:
        print('ビアが置けない', ref, num); continue
    x, y = q
    addvia(x, y)
    print('GND ビア', ref, num, round(x, 2), round(y, 2))
    t = pcbnew.PCB_TRACK(b); t.SetStart(pd.GetPosition()); t.SetEnd(P(x, y)); t.SetWidth(mm(0.3)); t.SetLayer(pcbnew.F_Cu)
    t.SetNet(gnd); b.Add(t)
t = pcbnew.PCB_TRACK(b); t.SetStart(P(14.7, 45.47)); t.SetEnd(P(13.2, 45.47)); t.SetWidth(mm(0.5)); t.SetLayer(pcbnew.F_Cu)
t.SetNet(gnd); b.Add(t)

pcbnew.ZONE_FILLER(b).Fill(b.Zones())
b.Save(PCB)
print('保存', PCB)
