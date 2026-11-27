# 指定した範囲を通る (ロックしていない) 線・ビアを消す (2026-11-22)。範囲の引き直し用。
#   線は、端か途中が範囲に入っていれば消す (範囲を横切るだけの線も消える)。
# usage: python region_rip.py x0 y0 x1 y1 [pcb]
import sys
import pcbnew

x0, y0, x1, y1 = map(float, sys.argv[1:5])
PCB = sys.argv[5] if len(sys.argv) > 5 else 'C:/MyWorks/ACROSS_V3_STM32/kicad/ACROSS_V3.kicad_pcb'
b = pcbnew.LoadBoard(PCB)
box = pcbnew.BOX2I(pcbnew.VECTOR2I(pcbnew.FromMM(x0), pcbnew.FromMM(y0)), pcbnew.VECTOR2I(pcbnew.FromMM(x1 - x0), pcbnew.FromMM(y1 - y0)))


def hits(t):
    if t.Type() == pcbnew.PCB_VIA_T:
        return box.Contains(t.GetPosition())
    a, e = t.GetStart(), t.GetEnd()
    for k in range(11):  # 線の上の 11 点
        p = pcbnew.VECTOR2I(int(a.x + (e.x - a.x) * k / 10), int(a.y + (e.y - a.y) * k / 10))
        if box.Contains(p):
            return True
    return False


rm = [t for t in b.GetTracks() if not t.IsLocked() and hits(t)]
for t in rm:
    b.Remove(t)
pcbnew.ZONE_FILLER(b).Fill(b.Zones())
b.Save(PCB)
print('消した', len(rm))
