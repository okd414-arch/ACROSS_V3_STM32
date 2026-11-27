# PMIC (U104) まわりの部品・パッド・ゾーンを一覧にする (2026-11-22、作り直しの下調べ)
# usage: python pmic_dump.py [pcb] [x0 y0 x1 y1]
import sys
import pcbnew

PCB = sys.argv[1] if len(sys.argv) > 1 else 'C:/MyWorks/ACROSS_V3_STM32/kicad/ACROSS_V3.kicad_pcb'
x0, y0, x1, y1 = map(float, sys.argv[2:6]) if len(sys.argv) > 5 else (18, 24, 62, 66)
b = pcbnew.LoadBoard(PCB)
T = pcbnew.ToMM
print('== U104 ピン')
for p in b.FindFootprintByReference('U104').Pads():
    print(f'  {p.GetNumber():>3} {T(p.GetPosition().x):7.2f} {T(p.GetPosition().y):7.2f}  {p.GetNetname()}')
print('== 部品')
for f in b.GetFootprints():
    x, y = T(f.GetPosition().x), T(f.GetPosition().y)
    if not (x0 <= x <= x1 and y0 <= y <= y1) or f.GetReference() == 'U104':
        continue
    pads = ' '.join(f'{p.GetNumber()}={p.GetNetname().split("/")[-1]}' for p in f.Pads())
    side = 'B' if f.IsFlipped() else 'F'
    print(f'  {f.GetReference():6} {x:7.2f} {y:7.2f} {side} rot{f.GetOrientationDegrees():5.0f} {f.GetValue():12} {f.GetFPID().GetLibItemName()}  {pads}')
print('== ゾーン')
for z in b.Zones():
    bb = z.GetBoundingBox()
    zx0, zy0, zx1, zy1 = T(bb.GetX()), T(bb.GetY()), T(bb.GetRight()), T(bb.GetBottom())
    if zx1 < x0 or zx0 > x1 or zy1 < y0 or zy0 > y1:
        continue
    print(f'  {z.GetZoneName():22} {z.GetNetname():14} {",".join(b.GetLayerName(l) for l in z.GetLayerSet().Seq())}  prio{z.GetAssignedPriority()}  ({zx0:.1f},{zy0:.1f})-({zx1:.1f},{zy1:.1f})')
