# DDR_ADDR / DDR_DATA の線を 0.1mm に細くする (2026-11-22、ルール緩和: 幅 0.12→0.1、間隔 0.1→0.09)
#   0.8mm ピッチのビアの間 (0.5mm) に 2 本通せるようになる (0.1*2 + 0.09*3 = 0.47)。
# usage: python shrink_ddr.py [pcb]
import sys
import pcbnew

PCB = sys.argv[1] if len(sys.argv) > 1 else 'C:/MyWorks/ACROSS_V3_STM32/kicad/ACROSS_V3.kicad_pcb'
b = pcbnew.LoadBoard(PCB)
W = pcbnew.FromMM(0.1)
n = 0
for t in b.GetTracks():
    if t.Type() != pcbnew.PCB_TRACE_T:
        continue
    nc = t.GetNet().GetNetClassName() if hasattr(t.GetNet(), 'GetNetClassName') else ''
    if ('DDR_ADDR' in nc or 'DDR_DATA' in nc) and t.GetWidth() > W:
        t.SetWidth(W)
        n += 1
pcbnew.ZONE_FILLER(b).Fill(b.Zones())
b.Save(PCB)
print('細くした線', n)
