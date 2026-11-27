# 絶縁領域 v4 (2026-11-20): A を縦長にして右寄せ、D を縮小、C (OC 出力のフォトカプラ) を下へ
#   A: x 108-160, y 0-54 / D: x 124-160, y 76-100 / C は領域なし (一次側) / 一次側はそれ以外
# usage: python regions_v4.py lines   (目安線を更新。保存して終了)
#        python regions_v4.py parts   (絶縁をまたぐ部品・コネクタを移動。別プロセスで)
import sys
import pcbnew
from pcbnew import VECTOR2I, ToMM

KICAD = 'C:/MyWorks/ACROSS_V3_STM32/kicad'
PCB = KICAD + '/ACROSS_V3.kicad_pcb'
STAGE = sys.argv[1]
b = pcbnew.LoadBoard(PCB)
LC = b.GetLayerID('Cmts.User')


def mm(v):
    return int(round(v * 1e6))


if STAGE == 'lines':
    for d in list(b.GetDrawings()):
        if d.GetLayer() == LC:
            b.Remove(d)

    def line(x1, y1, x2, y2):
        s = pcbnew.PCB_SHAPE(b)
        s.SetShape(pcbnew.SHAPE_T_SEGMENT)
        s.SetLayer(LC)
        s.SetStart(VECTOR2I(mm(x1), mm(y1)))
        s.SetEnd(VECTOR2I(mm(x2), mm(y2)))
        s.SetWidth(mm(0.2))
        b.Add(s)

    def label(t, x, y):
        s = pcbnew.PCB_TEXT(b)
        s.SetLayer(LC)
        s.SetText(t)
        s.SetPosition(VECTOR2I(mm(x), mm(y)))
        s.SetTextSize(VECTOR2I(mm(1.8), mm(1.8)))
        b.Add(s)

    line(108, 0, 108, 54)       # A の左辺 (絶縁部品がまたぐ線)
    line(108, 54, 160, 54)      # A の下辺
    line(124, 76, 124, 100)     # D の左辺 (絶縁部品がまたぐ線)
    line(124, 76, 160, 76)      # D の上辺
    label('A (GND_A)', 111, 52)
    label('D (GND_D)', 127, 78)
    b.Save(PCB)
    sys.exit(0)

fps = {f.GetReference(): f for f in b.GetFootprints()}


def mv_center(r, cx, cy, ang=None):
    f = fps[r]
    if ang is not None:
        f.SetOrientationDegrees(ang)
    bb = f.GetBoundingBox(False)
    p = f.GetPosition()
    f.SetPosition(VECTOR2I(p.x + mm(cx - ToMM(bb.GetX() + bb.GetWidth() / 2)), p.y + mm(cy - ToMM(bb.GetY() + bb.GetHeight() / 2))))


def shift(r, dx, dy=0.0):
    f = fps[r]
    p = f.GetPosition()
    f.SetPosition(VECTOR2I(p.x + mm(dx), p.y + mm(dy)))


# A の絶縁をまたぐ部品: x=93 → x=108 へ 15mm 右へ (y は据え置き)
for r in ('U601', 'U606', 'U607', 'U609'):
    shift(r, 15.0)
# J602 (サーボ出力、上辺): 境界から 2mm 以上離す
shift('J602', 9.0)
# C: OC 出力のフォトカプラを下げる (A の下辺 y=54 から 2mm 以上離す)
for r, cx, cy in (('U701', 126.0, 60.0), ('U702', 140.0, 60.0), ('U703', 126.0, 67.0), ('U704', 140.0, 67.0)):
    mv_center(r, cx, cy, 0)
mv_center('J702', 156.0, 64.0)
# D: 絶縁 DC-DC U705 (ピン 2 と 3 の中点が x=124)、U707 (x=124)
f = fps['U705']
pads = {p.GetNumber(): p for p in f.Pads()}
mid = (ToMM(pads['2'].GetPosition().x) + ToMM(pads['3'].GetPosition().x)) / 2
bb = f.GetBoundingBox(False)
f.SetPosition(VECTOR2I(f.GetPosition().x + mm(124.0 - mid), f.GetPosition().y + mm(83.0 - ToMM(bb.GetY() + bb.GetHeight() / 2))))
mv_center('U707', 124.0, 93.0, 0)
mv_center('J703', 156.0, 87.0)
b.Save(PCB)
for r in ('U601', 'U606', 'U607', 'U609', 'J602', 'U701', 'U702', 'U703', 'U704', 'J702', 'U705', 'U707', 'J703'):
    bb = fps[r].GetBoundingBox(False)
    print(r, round(ToMM(bb.GetX()), 1), round(ToMM(bb.GetY()), 1), round(ToMM(bb.GetRight()), 1), round(ToMM(bb.GetBottom()), 1))
