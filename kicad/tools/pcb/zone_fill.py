# ゾーンを塗り直して保存するだけ (2026-11-25、merge_nets.py のあとに別の処理で流す)
# usage: python zone_fill.py pcb
import sys
import pcbnew
b = pcbnew.LoadBoard(sys.argv[1])
pcbnew.ZONE_FILLER(b).Fill(b.Zones())
b.Save(sys.argv[1])
print('塗り直した', sys.argv[1])
