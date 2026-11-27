# DDR の配線 (線・ビア) を全部はがす (2026-11-23、AN5122 に合わせた DDR の引き直しの最初)
#   ロックしたものも含めて、ネット名が DDR_ で始まるものを消す (VTT_DDR は電源なので残す)。
# usage: python ddr_strip.py pcb
import sys
import pcbnew

PCB = sys.argv[1]
b = pcbnew.LoadBoard(PCB)
kill = [t for t in b.GetTracks() if t.GetNetname().startswith('DDR_')]
for t in kill:
    b.Remove(t)
pcbnew.ZONE_FILLER(b).Fill(b.Zones())
b.Save(PCB)
print('消した', len(kill))
