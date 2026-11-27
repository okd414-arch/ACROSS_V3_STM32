# U104 の下の列 (pin13..21) の引き出しを決める (2026-11-22)
#   帯 (ピンの先 y51.36 〜 コンデンサ y52.05) の中に、偶数ピンはビア (0.8mm おき)、奇数ピンはその間を真下へ。
#   帯のまわりのロックしていない線・ビアは消して、あとで格子配線で引き直す。
# usage: python pmic_bottom.py [pcb]
import sys
import pcbnew

PCB = sys.argv[1] if len(sys.argv) > 1 else 'C:/MyWorks/ACROSS_V3_STM32/kicad/ACROSS_V3.kicad_pcb'
mm = pcbnew.FromMM
T = pcbnew.ToMM
b = pcbnew.LoadBoard(PCB)


def P(x, y):
    return pcbnew.VECTOR2I(mm(x), mm(y))


BOX = (33.6, 51.0, 38.2, 55.5)


def touch(t):
    pts = [t.GetPosition()] if t.Type() == pcbnew.PCB_VIA_T else [t.GetStart(), t.GetEnd()]
    if t.Type() != pcbnew.PCB_VIA_T:
        a, e = pts
        pts = [pcbnew.VECTOR2I(int(a.x + (e.x - a.x) * k / 10), int(a.y + (e.y - a.y) * k / 10)) for k in range(11)]
    return any(BOX[0] <= T(p.x) <= BOX[2] and BOX[1] <= T(p.y) <= BOX[3] for p in pts)


rm = [t for t in b.GetTracks() if not t.IsLocked() and touch(t)]
for t in rm:
    b.Remove(t)
print('消した', len(rm))


def trk(pts, w, n):
    for a, c in zip(pts, pts[1:]):
        t = pcbnew.PCB_TRACK(b)
        t.SetStart(P(*a)); t.SetEnd(P(*c)); t.SetWidth(mm(w)); t.SetLayer(pcbnew.F_Cu); t.SetNet(b.FindNet(n)); t.SetLocked(True)
        b.Add(t)


def via(x, y, n):
    v = pcbnew.PCB_VIA(b)
    v.SetPosition(P(x, y)); v.SetWidth(mm(0.3)); v.SetDrill(mm(0.15)); v.SetNet(b.FindNet(n)); v.SetLocked(True)
    b.Add(v)


Y = 50.96
# 偶数ピン: 真下のビア
for x, n in ((34.6, 'VTT_DDR'), (35.4, 'VREF_DDR'), (36.2, 'Net-(U104-LDO2_OUT)'), (37.0, 'VDD_SD')):
    trk([(x, Y), (x, 51.72)], 0.2, n)
    via(x, 51.72, n)
# pin13 VDD_DDR: 左下のビア (このあと内層で VDD_DDR の島へ)
trk([(34.2, Y), (34.2, 51.4), (33.85, 51.75)], 0.2, 'VDD_DDR')
via(33.85, 51.75, 'VDD_DDR')
# pin17 PONKEY_N: ビアの間を真下へ、帯の下でビア (このあと裏で C116 へ)
trk([(35.8, Y), (35.8, 53.6)], 0.15, 'Net-(U104-PONKEY_N)')
via(35.8, 53.6, 'Net-(U104-PONKEY_N)')
# pin19 +3.3V: ビアの間を下へ、C119 の左でビア
trk([(36.6, Y), (36.6, 52.0), (36.45, 52.9)], 0.2, '+3.3V')
via(36.45, 52.9, '+3.3V')
# 裏の C118 (LDO2) は帯のビアの下にならないよう下げる
b.FindFootprintByReference('C118').SetPosition(P(35.0, 54.3))
# pin21 LDO6: C119 の pad1 へ直接
trk([(37.4, Y), (37.4, 51.7), (37.3, 52.4)], 0.25, 'Net-(U104-LDO6_OUT)')
pcbnew.ZONE_FILLER(b).Fill(b.Zones())
b.Save(PCB)
print('ok')
