# ビアを 0.45/0.2 から 0.3/0.15 に小さくする (2026-11-22、配線の詰まり対策でルールを緩めた)
#   対象: 信号のビア全部 + BGA (U1/U301/U302) の中のビア (電源・GND も)。BGA の外の電源のビアはそのまま。
#   JLC の 8 層: ビア 0.25/0.15 まで可。ランド幅 (0.3-0.15)/2 = 0.075。
# usage: python shrink_vias.py [pcb]
import sys
import pcbnew

PCB = sys.argv[1] if len(sys.argv) > 1 else 'C:/MyWorks/ACROSS_V3_STM32/kicad/ACROSS_V3.kicad_pcb'
b = pcbnew.LoadBoard(PCB)
mm = pcbnew.FromMM
bga = [b.FindFootprintByReference(r).GetCourtyard(pcbnew.F_CrtYd).BBox() for r in ('U1', 'U301', 'U302')]
n = 0
for t in b.GetTracks():
    if t.Type() != pcbnew.PCB_VIA_T or t.GetWidth(pcbnew.F_Cu) < mm(0.4):
        continue
    power = 'POWER' in t.GetNetClassName().split(',')
    inb = any(bb.Contains(t.GetPosition()) for bb in bga)
    if power and not inb:
        continue
    t.SetWidth(mm(0.3))
    t.SetDrill(mm(0.15))
    n += 1
pcbnew.ZONE_FILLER(b).Fill(b.Zones())
b.Save(PCB)
print('小さくしたビア', n)
