# ロックしていない線・ビアを全部消す (2026-11-22)。面へのビア・eMMC のパッド内ビア・U104 の GND など、ロックしたものは残す。
#   Freerouting を最初からやり直す用。
# usage: python strip_routes.py in.kicad_pcb out.kicad_pcb
import sys
import pcbnew

b = pcbnew.LoadBoard(sys.argv[1])
rm = [t for t in b.GetTracks() if not t.IsLocked()]
for t in rm:
    b.Remove(t)
pcbnew.ZONE_FILLER(b).Fill(b.Zones())
b.Save(sys.argv[2])
print('消した', len(rm), '残した', len(b.GetTracks()))
