# STPMIC1 (U104、0.4mm ピッチ QFN) の GND ピンのビアを、中央の放熱パッド (GND) への短い線に置き換える (2026-11-22)
#   fanout_planes.py がピンの外側に置いたビアが、隣のピンの引き出しをふさいでいたため。
# usage: python fix_u104_gnd.py [pcb]
import sys
import pcbnew

PCB = sys.argv[1] if len(sys.argv) > 1 else 'C:/MyWorks/ACROSS_V3_STM32/kicad/ACROSS_V3.kicad_pcb'
b = pcbnew.LoadBoard(PCB)
f = b.FindFootprintByReference('U104')
ep = [p for p in f.Pads() if p.GetNumber() == '45'][0]
epbb = ep.GetBoundingBox()
gpads = [p for p in f.Pads() if p.GetNetname() == 'GND' and p.GetNumber() != '45']
gpos = [p.GetPosition() for p in gpads]
# ピンから出ている GND の線と、その先のビアを消す
rm, ends = [], []
for t in b.GetTracks():
    if t.Type() == pcbnew.PCB_TRACE_T and t.GetNetname() == 'GND':
        for a_, e_ in ((t.GetStart(), t.GetEnd()), (t.GetEnd(), t.GetStart())):
            if any(a_ == q for q in gpos):
                rm.append(t); ends.append(e_)
for t in b.GetTracks():
    if t.Type() == pcbnew.PCB_VIA_T and t.GetNetname() == 'GND' and any(t.GetPosition() == e for e in ends):
        rm.append(t)
uniq = {id(x): x for x in rm}
for t in uniq.values():
    b.Remove(t)
print('消した', len(uniq))
# ピンの中心から放熱パッドの縁の内側 0.2mm まで、ピンの幅 0.2 の線
for p in gpads:
    c = p.GetPosition()
    x, y = c.x, c.y
    m = pcbnew.FromMM(0.2)
    if c.x < epbb.GetLeft():
        q = pcbnew.VECTOR2I(epbb.GetLeft() + m, y)
    elif c.x > epbb.GetRight():
        q = pcbnew.VECTOR2I(epbb.GetRight() - m, y)
    elif c.y > epbb.GetBottom():
        q = pcbnew.VECTOR2I(x, epbb.GetBottom() - m)
    else:
        q = pcbnew.VECTOR2I(x, epbb.GetTop() + m)
    t = pcbnew.PCB_TRACK(b)
    t.SetStart(c); t.SetEnd(q); t.SetWidth(pcbnew.FromMM(0.2)); t.SetLayer(pcbnew.F_Cu); t.SetNet(p.GetNet()); t.SetLocked(True)
    b.Add(t)
    print('GND', p.GetNumber(), '->', pcbnew.ToMM(q.x), pcbnew.ToMM(q.y))
pcbnew.ZONE_FILLER(b).Fill(b.Zones())
b.Save(PCB)
