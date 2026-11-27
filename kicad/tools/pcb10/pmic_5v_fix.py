# PMIC の +5V を In2 のベタにまとめる (2026-11-22、pmic_rework.py のあと)
#   - pin36 (+5V、上の列) のすぐ上にビアを置いてベタへ
#   - In2 の +5V ベタを L102 (昇圧コイル) の +5V パッドの下まで広げ、パッドの横のビアでつなぐ (本線の +5V とつながる)
# usage: python pmic_5v_fix.py [pcb]
import sys
import pcbnew

PCB = sys.argv[1] if len(sys.argv) > 1 else 'C:/MyWorks/ACROSS_V3_STM32/kicad/ACROSS_V3.kicad_pcb'
mm = pcbnew.FromMM
T = pcbnew.ToMM
b = pcbnew.LoadBoard(PCB)
N = b.FindNet('+5V')


def P(x, y):
    return pcbnew.VECTOR2I(mm(x), mm(y))


def via(x, y, d, h):
    v = pcbnew.PCB_VIA(b)
    v.SetPosition(P(x, y)); v.SetWidth(mm(d)); v.SetDrill(mm(h)); v.SetNet(N); v.SetLocked(True)
    b.Add(v)


def trk(a, c, w):
    t = pcbnew.PCB_TRACK(b)
    t.SetStart(P(*a)); t.SetEnd(P(*c)); t.SetWidth(mm(w)); t.SetLayer(pcbnew.F_Cu); t.SetNet(N); t.SetLocked(True)
    b.Add(t)


via(37.6, 44.35, 0.3, 0.15)
trk((37.4, 45.04), (37.4, 44.6), 0.2)
trk((37.4, 44.6), (37.6, 44.35), 0.2)
# pin37 (PM_BST) → C117: ビアの左を回る
PMB = b.FindNet('/01 電源入力 (24V・降圧5V・保護)・PMIC STPMIC1・取付穴/PM_BST')
for a, c in (((37.0, 45.04), (37.0, 44.1)), ((37.0, 44.1), (37.45, 43.65))):
    t = pcbnew.PCB_TRACK(b)
    t.SetStart(P(*a)); t.SetEnd(P(*c)); t.SetWidth(mm(0.3)); t.SetLayer(pcbnew.F_Cu); t.SetNet(PMB); t.SetLocked(True)
    b.Add(t)
via(43.3, 43.0, 0.45, 0.2)
trk((42.27, 43.0), (43.3, 43.0), 0.5)
# ベタを広げる: L102 の下 (39.5..43.7 x 42.4..44.6)
RECT = (39.5, 42.4, 43.7, 44.6)
rm = []
for t in b.GetTracks():
    if t.Type() == pcbnew.PCB_VIA_T or t.GetLayer() != pcbnew.In2_Cu or t.GetNetname() == '+5V':
        continue
    pts = [t.GetStart(), t.GetEnd()]
    pts += [pcbnew.VECTOR2I(int(pts[0].x + (pts[1].x - pts[0].x) * k / 8), int(pts[0].y + (pts[1].y - pts[0].y) * k / 8)) for k in range(1, 8)]
    if any(RECT[0] - 0.3 <= T(p.x) <= RECT[2] + 0.3 and RECT[1] - 0.3 <= T(p.y) <= RECT[3] + 0.3 for p in pts) and not t.IsLocked():
        rm.append(t)
for t in rm:
    b.Remove(t)
print('In2 の線を消した', len(rm), sorted({t.GetNetname() for t in rm}))
# 元の +5V ベタ (PMIC_+5V_In2) の外形を L102 の下まで広げる (ゾーンを 2 枚にしない)
z = [z for z in b.Zones() if z.GetZoneName() == 'PMIC_+5V_In2'][0]
ol = z.Outline()
ol.RemoveAllContours()
ol.NewOutline()
for x, y in [(32.3, 44.3), (RECT[0], 44.3), (RECT[0], RECT[1]), (RECT[2], RECT[1]), (RECT[2], RECT[3]), (40.3, RECT[3]), (40.3, 53.2), (32.3, 53.2)]:
    ol.Append(mm(x), mm(y))
pcbnew.ZONE_FILLER(b).Fill(b.Zones())
b.Save(PCB)
print('ok')
