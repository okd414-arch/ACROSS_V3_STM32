# PMIC (STPMIC1, U104) まわりの作り直し (2026-11-22)
#   方針 (ST AN5431 の配置の優先順位と、一般的な DC-DC の配線指針):
#   - コイルを各 VLX ピンのすぐ横に置き、スイッチの銅を短く太くする (VLX は 0.25 の首から 0.4)
#   - 降圧の入力 (+5V) は In2 に +5V のベタを敷き、各 VIN ピンのすぐ横のビアでつなぐ。入力コンデンサは下の角
#   - 出力は面 (VDD_CORE=In4 島, VDD_DDR=In3 島, VDD=In3) にビアで落とす。VDD と +3.3V は F.Cu のベタでもコイルとコンデンサをつなぐ
#   - 帰還 (センス) ピンは出力の面・ベタからとる
#   - F.Cu の GND ベタはこのあと (配線のあと) pmic_gnd_pour.py で入れる
# usage: python pmic_rework.py [pcb]
import sys
import pcbnew

PCB = sys.argv[1] if len(sys.argv) > 1 else 'C:/MyWorks/ACROSS_V3_STM32/kicad/ACROSS_V3.kicad_pcb'
mm = pcbnew.FromMM
T = pcbnew.ToMM
b = pcbnew.LoadBoard(PCB)


def P(x, y):
    return pcbnew.VECTOR2I(mm(x), mm(y))


# 1) 範囲の線・ビアを消す (ロックしたものも)。ただし U104 の放熱パッドのビアと、GND ピン → 放熱パッドの線は残す
RX0, RY0, RX1, RY1 = 28.6, 39.4, 46.6, 58.0
EP = (34.3, 46.3, 37.7, 49.7)


def inbox(p, bx):
    return bx[0] <= T(p.x) <= bx[2] and bx[1] <= T(p.y) <= bx[3]


def hits(t, bx):
    if t.Type() == pcbnew.PCB_VIA_T:
        return inbox(t.GetPosition(), bx)
    a, e = t.GetStart(), t.GetEnd()
    return any(inbox(pcbnew.VECTOR2I(int(a.x + (e.x - a.x) * k / 10), int(a.y + (e.y - a.y) * k / 10)), bx) for k in range(11))


U104BOX = (33.0, 44.5, 39.0, 51.5)
rm = []
for t in b.GetTracks():
    if not hits(t, (RX0, RY0, RX1, RY1)):
        continue
    if t.GetNetname() == 'GND':
        if t.Type() == pcbnew.PCB_VIA_T and inbox(t.GetPosition(), EP):
            continue
        if t.Type() != pcbnew.PCB_VIA_T and inbox(t.GetStart(), U104BOX) and inbox(t.GetEnd(), U104BOX) and t.IsLocked():
            continue
    rm.append(t)
for t in rm:
    b.Remove(t)
print('消した線・ビア', len(rm))

# 2) 部品の配置 (ref: x, y, 回転)  ※すべて表面。C136/C127 だけ裏 (位置だけずらす)
PLACE = {
    'L103': (31.25, 49.37, 270),   # VLX_1 (pin7) のすぐ左。1=VLX 上
    'L104': (31.25, 53.6, 270),    # VLX_2 (pin11) の左下
    'L105': (41.55, 46.7, 90),    # VLX_3 (pin29) のすぐ右。1=VLX 下
    'L106': (41.55, 50.95, 270),  # VLX_4 (pin25) のすぐ右。1=VLX 上
    'L102': (41.2, 43.0, 180),    # 昇圧: 2=VLX_BST 左
    'C117': (38.1, 42.3, 90),     # 昇圧の出力 (PM_BST) pin34/37 の上
    'C122': (33.9, 53.5, 270),    # 降圧 1・2 の入力 (+5V) 左下の角
    'C124': (39.1, 53.6, 270),    # 降圧 3・4 の入力 (+5V) 右下の角
    'C119': (37.27, 53.6, 270),   # LDO6
    'C135': (41.5, 54.7, 270),    # VDDA
    'C139': (43.12, 54.65, 90),    # VREF_DDR
    'C133': (44.0, 46.6, 270),    # VDD の出力
    'C134': (44.0, 51.0, 90),     # +3.3V の出力
    'C132': (31.4, 56.75, 0),     # VDD_DDR の出力
    'C131': (30.62, 44.0, 90),    # VDD_CORE の出力 (そのまま)
}
BACK = {'C136': (30.75, 47.62), 'C127': (29.3, 51.8)}  # C127 は L103 の VDD_CORE パッドの面ビアをよけて左へ
for ref, (x, y, r) in PLACE.items():
    f = b.FindFootprintByReference(ref)
    f.SetPosition(P(x, y))
    f.SetOrientationDegrees(r)
for ref, (x, y) in BACK.items():
    f = b.FindFootprintByReference(ref)
    f.SetPosition(P(x, y))


def net(n):
    return b.FindNet(n)


def trk(pts, w, n, lay=pcbnew.F_Cu):
    for (ax, ay), (bx, by) in zip(pts, pts[1:]):
        t = pcbnew.PCB_TRACK(b)
        t.SetStart(P(ax, ay)); t.SetEnd(P(bx, by)); t.SetWidth(mm(w)); t.SetLayer(lay); t.SetNet(net(n)); t.SetLocked(True)
        b.Add(t)


def via(x, y, n, d=0.3, h=0.15):
    v = pcbnew.PCB_VIA(b)
    v.SetPosition(P(x, y)); v.SetWidth(mm(d)); v.SetDrill(mm(h)); v.SetNet(net(n)); v.SetLocked(True)
    b.Add(v)


# 3) スイッチ (VLX) の銅: ピンの間は 0.25、出たら 0.4
V1, V2, V3, V4 = 'Net-(U104-VLX_1)', 'Net-(U104-VLX_2)', 'Net-(U104-VLX_3)', 'Net-(U104-VLX_4)'
#   ピンからはまず真横にパッドの外端 (左 33.05 / 右 38.95) まで出してから曲げる (となりのピンにかからないように)
trk([(33.55, 48.2), (33.0, 48.2)], 0.25, V1); trk([(33.0, 48.2), (32.2, 48.15)], 0.35, V1)
trk([(33.55, 49.8), (32.95, 49.8), (32.8, 50.2)], 0.25, V2); trk([(32.8, 50.2), (32.8, 51.3), (32.2, 52.2)], 0.3, V2)
trk([(38.45, 47.8), (39.0, 47.8)], 0.25, V3); trk([(39.0, 47.8), (40.6, 47.8)], 0.4, V3)
trk([(38.45, 49.4), (39.0, 49.4)], 0.25, V4); trk([(39.0, 49.4), (40.6, 49.6)], 0.4, V4)

# 4) ピンのすぐ横のビア (入力 +5V → In2 のベタ、帰還 → 面)
for path, n in [
        ([(33.55, 48.6), (32.75, 48.7)], '+5V'),                      # pin8  VIN1
        ([(33.55, 50.2), (33.5, 50.7)], '+5V'),                       # pin12 VIN2 (角のピンなので下へ)
        ([(38.45, 48.2), (38.95, 48.2), (39.45, 48.4)], '+5V'),       # pin28 VIN3
        ([(33.55, 49.0), (33.05, 49.0), (32.75, 49.35)], 'VDD_DDR'),  # pin9  帰還 (In3 の VDD_DDR 島)
        ([(33.55, 47.4), (33.05, 47.4), (32.9, 47.45)], 'VDD_CORE'),  # pin5  帰還 (In4 の VDD_CORE 島)
        ([(38.45, 47.0), (39.25, 47.0)], 'VDD'),                      # pin31 帰還 (In3 の VDD)
]:
    trk(path, 0.2, n)
    via(path[-1][0], path[-1][1], n)
# pin27 (+3.3V 帰還) は少し曲げてビアへ (このあと In5 などで +3.3V の出力につなぐ)
trk([(38.45, 48.6), (38.95, 48.6), (39.25, 48.8), (40.05, 48.85)], 0.2, '+3.3V')
via(40.05, 48.85, '+3.3V')


# 5) ベタ (ゾーン)
def zone(n, lay, pts, prio, clr=0.2, minw=0.15, name=None):
    z = pcbnew.ZONE(b)
    z.SetLayer(lay)
    z.SetNet(net(n))
    ol = z.Outline()
    ol.NewOutline()
    for x, y in pts:
        ol.Append(mm(x), mm(y))
    z.SetAssignedPriority(prio)
    z.SetLocalClearance(mm(clr))
    z.SetMinThickness(mm(minw))
    z.SetPadConnection(pcbnew.ZONE_CONNECTION_FULL)
    z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
    if name:
        z.SetZoneName(name)
    b.Add(z)


def rect(x0, y0, x1, y1):
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]


zone('+5V', pcbnew.In2_Cu, rect(32.3, 44.3, 40.3, 53.2), 5, name='PMIC_+5V_In2')
zone('VDD', pcbnew.F_Cu, rect(40.45, 45.0, 44.73, 46.26), 5, name='PMIC_VDD_F')
zone('+3.3V', pcbnew.F_Cu, rect(40.45, 51.4, 44.73, 52.65), 5, name='PMIC_3V3_F')
zone('VDD_DDR', pcbnew.F_Cu, [(30.3, 54.0), (32.5, 54.0), (32.5, 55.35), (31.0, 55.35), (31.0, 57.5), (29.9, 57.5), (29.9, 54.0)], 5, name='PMIC_VDD_DDR_F')

pcbnew.ZONE_FILLER(b).Fill(b.Zones())
b.Save(PCB)
print('保存', PCB)
