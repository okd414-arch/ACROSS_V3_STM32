# 名前が REGEX に合うネットの、ロックしていない線・ビアをすべて消す (2026-11-22、まとめて引き直す用)
# usage: python strip_nets.py REGEX [pcb]
import sys, re
import pcbnew

RX = re.compile(sys.argv[1])
PCB = sys.argv[2] if len(sys.argv) > 2 else 'C:/MyWorks/ACROSS_V3_STM32/kicad/ACROSS_V3.kicad_pcb'
b = pcbnew.LoadBoard(PCB)
kill = [t for t in b.GetTracks() if not t.IsLocked() and RX.search(t.GetNetname())]
for t in kill:
    b.Remove(t)
pcbnew.ZONE_FILLER(b).Fill(b.Zones())
b.Save(PCB)
print('消した', len(kill))
