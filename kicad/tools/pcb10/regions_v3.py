# 絶縁領域 v3 (2026-11-20): C (OC 出力) は領域を分けず一次側の扱い。D (GND_D) のみ x 112-160, y 62-100
# usage: python regions_v3.py lines   (目安線を更新。保存して終了)
#        python regions_v3.py parts   (絶縁をまたぐ部品・コネクタを移動。別プロセスで)
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
        if d.GetLayer() != LC:
            continue
        bb = d.GetBoundingBox()
        x0, y0 = round(ToMM(bb.GetX())), round(ToMM(bb.GetY()))
        txt = d.GetText() if d.GetClass() == 'PCB_TEXT' else ''
        # 旧 C/D の線・文字 (x>=111 で y>=42 のもの、および C/D の文字)。A の線 (y<=39) は残す
        if (d.GetClass() == 'PCB_SHAPE' and x0 >= 111 and y0 >= 42) or txt.startswith('C (') or txt.startswith('D ('):
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

    line(112, 62, 160, 62)     # D の上辺
    line(112, 62, 112, 100)    # D の左辺 (絶縁部品がまたぐ線)
    label('D (GND_D)', 115, 64)
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


# フォトカプラ ×4 (OC 出力): 一次側の領域内、J702 の近くに 2x2。LED 側 (一次側) が左、出力側が右
for r, cx, cy in (('U701', 126.0, 47.0), ('U702', 140.0, 47.0), ('U703', 126.0, 54.0), ('U704', 140.0, 54.0)):
    mv_center(r, cx, cy, 0)
# J702: 右辺
mv_center('J702', 156.0, 51.0)
# 絶縁 DC-DC U705 (D): ピン 2 と 3 の中点が x=112
f = fps['U705']
pads = {p.GetNumber(): p for p in f.Pads()}
mid = (ToMM(pads['2'].GetPosition().x) + ToMM(pads['3'].GetPosition().x)) / 2
f.SetPosition(VECTOR2I(f.GetPosition().x + mm(112.0 - mid), mm(70.0)))
# アイソレータ U707 (D): 左 = 一次側
mv_center('U707', 112.0, 90.0, 0)
b.Save(PCB)
for r in ('U701', 'U702', 'U703', 'U704', 'U705', 'U707', 'J702'):
    bb = fps[r].GetBoundingBox(False)
    print(r, round(ToMM(bb.GetX()), 1), round(ToMM(bb.GetY()), 1), round(ToMM(bb.GetRight()), 1), round(ToMM(bb.GetBottom()), 1))
