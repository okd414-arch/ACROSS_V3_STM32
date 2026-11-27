# STPMIC1 (U104) の降圧のインダクタと出力コンデンサの位置を、スイッチのピンの側に合わせて入れ替える (2026-11-22)
#   以前: VLX_2 (左下のピン 11) の L104 が右上、VLX_3 (右のピン 29) の L105 が左下 → スイッチ線が PMIC の上で交差していた。
#   L104 <-> L105、C132 (VDD_DDR) <-> C133 (VDD) を入れ替える。
#   VDD_DDR の島 (In3) を左下の帯 (x 29.5-33, y 43.5-55.5) まで広げ、新しい L104・C132 の出力が島に落ちるようにする。
#   入れ替える部品のパッドにつながる線・ビア (ロックした面へのビアも) は消す (あとで引き直す)。
# usage: python pmic_swap.py [pcb]
import sys
import pcbnew

PCB = sys.argv[1] if len(sys.argv) > 1 else 'C:/MyWorks/ACROSS_V3_STM32/kicad/ACROSS_V3.kicad_pcb'
mm = pcbnew.FromMM
b = pcbnew.LoadBoard(PCB)
pairs = [('L104', 'L105'), ('C132', 'C133')]
parts = [b.FindFootprintByReference(r) for p in pairs for r in p]
pads = [p for f in parts for p in f.Pads()]
# パッドにつながる線と、その先のビア
rm, ends = [], []
for t in b.GetTracks():
    if t.Type() == pcbnew.PCB_TRACE_T:
        for a_, e_ in ((t.GetStart(), t.GetEnd()), (t.GetEnd(), t.GetStart())):
            if any(p.GetNetCode() == t.GetNetCode() and p.HitTest(a_) for p in pads):
                rm.append(t); ends.append((t.GetNetCode(), e_))
for t in b.GetTracks():
    if t.Type() == pcbnew.PCB_VIA_T:
        if any(n == t.GetNetCode() and t.GetPosition() == e for n, e in ends) or any(p.GetNetCode() == t.GetNetCode() and p.HitTest(t.GetPosition()) for p in pads):
            rm.append(t)
u = {id(x): x for x in rm}
for t in u.values():
    b.Remove(t)
print('消した', len(u))
for r1, r2 in pairs:
    f1, f2 = b.FindFootprintByReference(r1), b.FindFootprintByReference(r2)
    p1, p2 = f1.GetPosition(), f2.GetPosition()
    o1, o2 = f1.GetOrientationDegrees(), f2.GetOrientationDegrees()
    f1.SetPosition(p2); f1.SetOrientationDegrees(o2)
    f2.SetPosition(p1); f2.SetOrientationDegrees(o1)
    print('入れ替え', r1, r2)
# VDD_DDR の島を広げる
NEW = [(29.5, 37.5), (62.0, 37.5), (62.0, 25.5), (92.5, 25.5), (92.5, 78.0), (62.0, 78.0), (62.0, 41.0), (49.0, 41.0),
       (49.0, 43.5), (33.0, 43.5), (33.0, 55.5), (29.5, 55.5)]
for z in b.Zones():
    if z.GetNetname() == 'VDD_DDR' and z.GetLayer() == pcbnew.In3_Cu:
        o = z.Outline()
        o.RemoveAllContours()
        o.NewOutline()
        for x, y in NEW:
            o.Append(mm(x), mm(y))
        print('VDD_DDR の島を広げた')
pcbnew.ZONE_FILLER(b).Fill(b.Zones())
b.Save(PCB)
