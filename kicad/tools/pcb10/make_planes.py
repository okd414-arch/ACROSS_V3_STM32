# 電源・GND の面 (ゾーン) を作る (2026-11-21)。既存のゾーンは消して作り直す。
#   L2 (In1) / L7 (In6): GND (一次側)、GND_A (A)、GND_D (D)
#   L4 (In3): VDD (一次側の全面) + VDD_DDR の島 (DDR3L と SoC の DDR 側、PMIC から回廊)、A = +3.3V_A、D = +5V_D
#   L5 (In4): +3.3V (一次側の全面) + VDD_CORE の島 (SoC の周り、PMIC から回廊)、A = +5V_A、D = +9V_D
#   面の層は層の種類を power にする (Freerouting は信号を通さず、面への接続だけに使う)
#   領域: A = x109〜, y〜53 / D = x125〜, y77〜 / 一次側との間は 2mm (境界線は x=108, y=54, x=124, y=76)
#   eMMC (U401、0.5mm ピッチ) の使っているボールにはパッド内ビア (0.25/0.15、JLCPCB の穴埋め VIP 前提) を置く
# usage: python make_planes.py
import pcbnew
from pcbnew import VECTOR2I

PCB = 'C:/MyWorks/ACROSS_V3_STM32/kicad/ACROSS_V3.kicad_pcb'
b = pcbnew.LoadBoard(PCB)


def mm(v):
    return int(round(v * 1e6))


E = 0.5  # 基板端からの距離
W, H = 160.0, 100.0
PRIMARY = [(E, E), (107, E), (107, 56), (W - E, 56), (W - E, 74), (123, 74), (123, H - E), (E, H - E)]
DOM_A = [(109, E), (W - E, E), (W - E, 53), (109, 53)]
DOM_D = [(125, 77), (W - E, 77), (W - E, H - E), (125, H - E)]
VDD_DDR = [(32.5, 37.5), (62.0, 37.5), (62.0, 25.5), (92.5, 25.5), (92.5, 78.0), (62.0, 78.0), (62.0, 41.0), (49.0, 41.0), (49.0, 43.5), (32.5, 43.5)]
VDD_CORE = [(29.0, 38.5), (45.0, 38.5), (45.0, 33.0), (73.0, 33.0), (73.0, 67.0), (45.0, 67.0), (45.0, 48.5), (29.0, 48.5)]

L = {n: b.GetLayerID(n) for n in ('In1.Cu', 'In3.Cu', 'In4.Cu', 'In6.Cu')}
for n, lid in L.items():
    b.SetLayerType(lid, pcbnew.LT_POWER)

for z in list(b.Zones()):
    if not z.GetIsRuleArea():
        b.Remove(z)


def zone(net, layer, pts, prio=0):
    ni = b.FindNet(net)
    assert ni is not None, net
    z = pcbnew.ZONE(b)
    z.SetLayer(L[layer])
    z.SetNetCode(ni.GetNetCode())
    o = z.Outline()
    o.NewOutline()
    for x, y in pts:
        o.Append(mm(x), mm(y))
    z.SetAssignedPriority(prio)
    z.SetMinThickness(mm(0.2))
    z.SetThermalReliefGap(mm(0.3))
    z.SetThermalReliefSpokeWidth(mm(0.4))
    z.SetLocalClearance(mm(0.2))
    z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_AREA)
    z.SetMinIslandArea(mm(3) * mm(3))
    z.SetZoneName(f'{net}_{layer}')
    b.Add(z)
    return z


for lay in ('In1.Cu', 'In6.Cu'):
    zone('GND', lay, PRIMARY)
    zone('GND_A', lay, DOM_A, 1)
    zone('GND_D', lay, DOM_D, 1)
zone('VDD', 'In3.Cu', PRIMARY)
zone('VDD_DDR', 'In3.Cu', VDD_DDR, 2)
zone('+3.3V_A', 'In3.Cu', DOM_A, 1)
zone('+5V_D', 'In3.Cu', DOM_D, 1)
zone('+3.3V', 'In4.Cu', PRIMARY)
zone('VDD_CORE', 'In4.Cu', VDD_CORE, 2)
zone('+5V_A', 'In4.Cu', DOM_A, 1)
zone('+9V_D', 'In4.Cu', DOM_D, 1)

# eMMC のパッド内ビア (既存のものは消してから)
fp = b.FindFootprintByReference('U401')
pads = [p for p in fp.Pads() if p.GetNetname() and not p.GetNetname().startswith('unconnected')]
padpos = {(p.GetPosition().x, p.GetPosition().y) for p in pads}
for t in list(b.GetTracks()):
    if t.Type() == pcbnew.PCB_VIA_T and (t.GetPosition().x, t.GetPosition().y) in padpos:
        b.Remove(t)
# 外周 2 列にあるボールは表面で引き出せるので VIP にしない (列/行の端から 1 番目)
xs = sorted({p.GetPosition().x for p in fp.Pads()})
ys = sorted({p.GetPosition().y for p in fp.Pads()})
n_vip = 0
for p in pads:
    ix = xs.index(p.GetPosition().x)
    iy = ys.index(p.GetPosition().y)
    edge = ix in (0, len(xs) - 1) or iy in (0, len(ys) - 1)
    if edge:
        continue
    v = pcbnew.PCB_VIA(b)
    v.SetPosition(p.GetPosition())
    v.SetWidth(mm(0.25))
    v.SetDrill(mm(0.15))
    v.SetNetCode(p.GetNetCode())
    v.SetLocked(True)
    b.Add(v)
    n_vip += 1
print('eMMC VIP', n_vip, 'of', len(pads))

filler = pcbnew.ZONE_FILLER(b)
filler.Fill(b.Zones())
b.Save(PCB)
for z in b.Zones():
    print(z.GetZoneName(), round(z.GetFilledArea() / 1e12, 1), 'mm2')
