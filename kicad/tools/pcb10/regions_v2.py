# 絶縁領域の再定義 (2026-11-20): C/D を 1 ブロックにまとめて境界を x=112 に。絶縁をまたぐ部品とコネクタの位置を決める
# A: x 93-160, y 0-39 (従来どおり) / C: x 112-160, y 43-72 / D: x 112-160, y 75-100 / 一次側: それ以外
import sys
import pcbnew
from pcbnew import VECTOR2I, ToMM

KICAD = 'C:/MyWorks/ACROSS_V3_STM32/kicad'
PCB = KICAD + '/ACROSS_V3.kicad_pcb'
b = pcbnew.LoadBoard(PCB)
fps = {f.GetReference(): f for f in b.GetFootprints()}


def mm(v):
    return int(round(v * 1e6))


STAGE = sys.argv[1]   # lines → parts (別プロセス。Remove 後は SWIG のオブジェクトが壊れるため)
# ---- 目安線 (Cmts.User) ----
if STAGE == 'lines':
    LC = b.GetLayerID('Cmts.User')
    for d in list(b.GetDrawings()):
        if d.GetLayer() != LC:
            continue
        bb = d.GetBoundingBox()
        x0, y0 = ToMM(bb.GetX()), ToMM(bb.GetY())
        txt = d.GetText() if d.GetClass() == 'PCB_TEXT' else ''
        # 旧 C/D 関連 (x>=135) と、C・D の文字を消す。A の線 (x=93, y=39) と A の文字は残す
        if (d.GetClass() == 'PCB_SHAPE' and x0 >= 135) or txt.startswith('C') or txt.startswith('D (GND_D)') or txt.startswith('D '):
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


    line(112, 43, 160, 43)     # C の上辺
    line(112, 43, 112, 100)    # C/D の左辺 (絶縁部品がまたぐ線)
    line(112, 72, 160, 72)     # C の下辺
    line(112, 75, 160, 75)     # D の上辺
    label('C (OC output)', 115, 45)
    label('D (GND_D)', 115, 77)
    b.Save(PCB)
    sys.exit(0)


def mv_center(r, cx, cy, ang=None):
    f = fps[r]
    if ang is not None:
        f.SetOrientationDegrees(ang)
    bb = f.GetBoundingBox(False)
    p = f.GetPosition()
    f.SetPosition(VECTOR2I(p.x + mm(cx - ToMM(bb.GetX() + bb.GetWidth() / 2)), p.y + mm(cy - ToMM(bb.GetY() + bb.GetHeight() / 2))))


# ---- 絶縁をまたぐ部品 (一次側のパッドを左 = x<112 に) ----
# フォトカプラ ×4 (C): パッドの中心が x=112
for r, cy in (('U701', 47.0), ('U702', 53.0), ('U703', 59.0), ('U704', 65.0)):
    mv_center(r, 112.0, cy, 0)
# 絶縁 DC-DC U705 (D): 一次側ピン (1,2) が左、二次側 (3,4) が右。ピン2とピン3の中点が x=112
f = fps['U705']
pads = {p.GetNumber(): p for p in f.Pads()}
mid = (ToMM(pads['2'].GetPosition().x) + ToMM(pads['3'].GetPosition().x)) / 2
f.SetPosition(VECTOR2I(f.GetPosition().x + mm(112.0 - mid), mm(80.5)))
# アイソレータ U707 (D): 左 = 一次側
mv_center('U707', 112.0, 91.0, 0)
# 出力コネクタ (右辺)
f = fps['J702']
bb = f.GetBoundingBox(False)
f.SetPosition(VECTOR2I(f.GetPosition().x, f.GetPosition().y + mm(56.0 - ToMM(bb.GetY() + bb.GetHeight() / 2))))
# J701 (GF-8801 小基板): 下辺に横向き (ピン1が左)
f = fps['J701']
for ang in (90, 270):
    f.SetOrientationDegrees(ang)
    xs = {p.GetNumber(): ToMM(p.GetPosition().x) for p in f.Pads()}
    if xs['10'] > xs['1']:
        break
bb = f.GetBoundingBox(False)
p = f.GetPosition()
f.SetPosition(VECTOR2I(p.x + mm(98.0 - (ToMM(bb.GetX()) + ToMM(bb.GetWidth()) / 2)), p.y + mm(96.5 - (ToMM(bb.GetY()) + ToMM(bb.GetHeight()) / 2))))
b.Save(PCB)
for r in ('U701', 'U702', 'U703', 'U704', 'U705', 'U707', 'J701', 'J702'):
    bb = fps[r].GetBoundingBox(False)
    print(r, round(ToMM(bb.GetX()), 1), round(ToMM(bb.GetY()), 1), round(ToMM(bb.GetRight()), 1), round(ToMM(bb.GetBottom()), 1))
