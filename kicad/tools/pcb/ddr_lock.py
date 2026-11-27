# 線とビアをロックする / 外す (2026-11-24)。ロックした線は mr_route の --rip ではがされない。
#   KiCad の Python。
# usage: python ddr_lock.py pcb lock NET1,NET2,...
#        python ddr_lock.py pcb unlock-all     (このツールでロックしたもの = DDR_ と VREF_DDR を外す)
import sys
import pcbnew

PCB, mode = sys.argv[1], sys.argv[2]
b = pcbnew.LoadBoard(PCB)
n = 0
if mode == 'lock':
    nets = set(sys.argv[3].split(','))
    for t in b.GetTracks():
        if t.GetNetname() in nets and not t.IsLocked():
            t.SetLocked(True)
            n += 1
else:
    for t in b.GetTracks():
        if (t.GetNetname().startswith('DDR_') or t.GetNetname() == 'VREF_DDR') and t.IsLocked():
            t.SetLocked(False)
            n += 1
b.Save(PCB)
print(mode, n)
