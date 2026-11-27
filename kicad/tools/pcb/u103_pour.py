# 5V eFuse (U103 TPS259531) まわりの表のベタ (2026-11-25)
#   - 入力 (降圧の出力 Net-(C110-Pad1)、最大 3A): U103 のピン 3・4 の直下から、出力コンデンサのベタ (U102_VOUT) まで
#   - 出力 (+5V): ピン 5 から C123・C125・C126 の +5V パッドまで。In2 の +5V の面へのビアを 4 個 (全層で空いている所)
#   同じ名前のゾーンがあれば作り直す。ビアを何度も足さないよう、1 回だけ流すこと。
# usage: python u103_pour.py pcb
import sys, math
import pcbnew

PCB = sys.argv[1]
mm = pcbnew.FromMM
T = pcbnew.ToMM
b = pcbnew.LoadBoard(PCB)
CU = [l for l in b.GetEnabledLayers().CuStack()]


def P(x, y):
    return pcbnew.VECTOR2I(mm(x), mm(y))


def free(x, y, net):
    c = P(x, y)
    via = pcbnew.SHAPE_CIRCLE(c, mm(0.3))
    for t in list(b.GetTracks()) + list(b.GetPads()):
        q = t.GetPosition()
        bb = t.GetBoundingBox()
        if bb.GetLeft() > c.x + mm(1.5) or bb.GetRight() < c.x - mm(1.5) or bb.GetTop() > c.y + mm(1.5) or bb.GetBottom() < c.y - mm(1.5):
            continue
        hole = (t.Type() == pcbnew.PCB_VIA_T) or (t.Type() == pcbnew.PCB_PAD_T and t.HasHole())
        if hole and (q - c).EuclideanNorm() < mm(0.65 if t.GetNetCode() == net.GetNetCode() else 0.85):
            return False
        if t.GetNetCode() == net.GetNetCode():
            continue
        for l in CU:
            if t.IsOnLayer(l) and t.GetEffectiveShape(l).Collide(via, mm(0.2)):
                return False
    return True


def zone(name, netname, pts, pri=6):
    for z in list(b.Zones()):
        if z.GetZoneName() == name:
            b.Remove(z)
    z = pcbnew.ZONE(b)
    z.SetLayer(pcbnew.F_Cu)
    z.SetNet(b.FindNet(netname))
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


zone('U103_IN', 'Net-(C110-Pad1)', [(30.75, 27.1), (31.4, 27.1), (31.4, 28.3), (32.3, 28.3), (32.3, 33.0), (30.75, 33.0)])
zone('U103_OUT', '+5V', [(32.75, 27.6), (34.2, 27.6), (34.2, 25.0), (35.9, 25.0), (35.9, 32.3), (32.75, 32.3)])
net = b.FindNet('+5V')
n = 0
for x, y in [(33.4, 29.3), (33.4, 30.6), (33.4, 31.7), (34.4, 30.1), (34.4, 31.6), (33.4, 28.6)]:
    if n >= 4:
        break
    if free(x, y, net):
        v = pcbnew.PCB_VIA(b); v.SetPosition(P(x, y)); v.SetWidth(mm(0.6)); v.SetDrill(mm(0.3)); v.SetNet(net); b.Add(v)
        n += 1
        print('ビア +5V', x, y)
pcbnew.ZONE_FILLER(b).Fill(b.Zones())
b.Save(PCB)
print('保存', PCB)
