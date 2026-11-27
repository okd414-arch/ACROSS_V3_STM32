# PMIC の上の列 pin38 (VBUS_SW)・pin39 (VDD_USB) の引き出しと、VDD_SD の内層の引き出し (2026-11-22)
#   pin38/39 のすぐ上にビア (In2 は +5V ベタなので、このあと In5/B で引く)。VDD_SD はビアから In5 で南へ出す。
# usage: python pmic_top_fix.py [pcb]
import sys
import pcbnew

PCB = sys.argv[1] if len(sys.argv) > 1 else 'C:/MyWorks/ACROSS_V3_STM32/kicad/ACROSS_V3.kicad_pcb'
mm = pcbnew.FromMM
T = pcbnew.ToMM
b = pcbnew.LoadBoard(PCB)


def P(x, y):
    return pcbnew.VECTOR2I(mm(x), mm(y))


kill = []
for t in b.GetTracks():
    if t.IsLocked() or t.GetNetname() not in ('VBUS_SW', 'VDD_USB'):
        continue
    pts = [t.GetPosition()] if t.Type() == pcbnew.PCB_VIA_T else [t.GetStart(), t.GetEnd()]
    if any(35.9 <= T(p.x) <= 36.95 and 43.0 <= T(p.y) <= 45.1 for p in pts):
        kill.append(t)
print('消す', len(kill))
for t in kill:
    b.Remove(t)
add = []


def trk(pts, w, n, lay=pcbnew.F_Cu):
    for a, c in zip(pts, pts[1:]):
        t = pcbnew.PCB_TRACK(b)
        t.SetStart(P(*a)); t.SetEnd(P(*c)); t.SetWidth(mm(w)); t.SetLayer(lay); t.SetNet(b.FindNet(n)); t.SetLocked(True)
        add.append(t)


def via(x, y, n):
    v = pcbnew.PCB_VIA(b)
    v.SetPosition(P(x, y)); v.SetWidth(mm(0.3)); v.SetDrill(mm(0.15)); v.SetNet(b.FindNet(n)); v.SetLocked(True)
    add.append(v)


trk([(36.6, 45.04), (36.6, 44.6), (36.55, 44.3)], 0.2, 'VBUS_SW')
via(36.55, 44.3, 'VBUS_SW')
trk([(36.2, 45.04), (36.2, 44.6), (36.05, 44.25)], 0.2, 'VDD_USB')
via(36.05, 44.25, 'VDD_USB')
# VDD_SD: ビア (37.0,51.72) から In5 で南へ
trk([(37.0, 51.72), (37.8, 52.5), (37.8, 55.5)], 0.2, 'VDD_SD', pcbnew.In5_Cu)
for o in add:
    b.Add(o)
pcbnew.ZONE_FILLER(b).Fill(b.Zones())
b.Save(PCB)
print('ok')

# 実際には、このあと裏の C120 を (35.8, 45.2) (U104 の真下の裏、ピン 40 のそば) へ動かした (ビアの真下だったため)

