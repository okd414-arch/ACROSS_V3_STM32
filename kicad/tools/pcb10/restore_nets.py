# 指定ネットの線・ビアを、別の基板 (写し) のものに置き換える (2026-11-22)
#   うっかりはがしたネットを、前の写しの配線に戻す用。戻したあと DRC でぶつかる線は drop_violators.py で消す。
# usage: python restore_nets.py 写し.kicad_pcb REGEX [pcb]
import sys, re
import pcbnew

SRC = sys.argv[1]
RX = re.compile(sys.argv[2])
PCB = sys.argv[3] if len(sys.argv) > 3 else 'C:/MyWorks/ACROSS_V3_STM32/kicad/ACROSS_V3.kicad_pcb'
src = pcbnew.LoadBoard(SRC)
items = []
for t in src.GetTracks():
    n = t.GetNetname()
    if not RX.search(n):
        continue
    if t.Type() == pcbnew.PCB_VIA_T:
        items.append(('v', n, t.GetPosition().x, t.GetPosition().y, t.GetWidth(pcbnew.F_Cu), t.GetDrillValue(), t.IsLocked()))
    else:
        items.append(('t', n, t.GetStart().x, t.GetStart().y, t.GetEnd().x, t.GetEnd().y, t.GetWidth(), t.GetLayer(), t.IsLocked()))
b = pcbnew.LoadBoard(PCB)
kill = [t for t in b.GetTracks() if RX.search(t.GetNetname())]
nets = sorted({t.GetNetname() for t in kill} | {i[1] for i in items})
for t in kill:
    b.Remove(t)
add = []
for it in items:
    if it[0] == 'v':
        _, n, x, y, d, h, lk = it
        v = pcbnew.PCB_VIA(b)
        v.SetPosition(pcbnew.VECTOR2I(x, y)); v.SetWidth(d); v.SetDrill(h); v.SetNet(b.FindNet(n)); v.SetLocked(lk)
        add.append(v)
    else:
        _, n, ax, ay, ex, ey, w, l, lk = it
        t = pcbnew.PCB_TRACK(b)
        t.SetStart(pcbnew.VECTOR2I(ax, ay)); t.SetEnd(pcbnew.VECTOR2I(ex, ey)); t.SetWidth(w); t.SetLayer(l); t.SetNet(b.FindNet(n)); t.SetLocked(lk)
        add.append(t)
for o in add:
    b.Add(o)
pcbnew.ZONE_FILLER(b).Fill(b.Zones())
b.Save(PCB)
print('消した', len(kill), '戻した', len(add), 'ネット', nets)
