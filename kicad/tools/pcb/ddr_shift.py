# DDR メモリ側の部品をまとめて右へ動かし、U1 との間の通り道を広げる (2026-11-24、案 A)
#   動かす: U301 / U302 と、x >= 72.5・y 22〜80 にある R3xx / C3xx (終端抵抗、VTT・VDD_DDR・VREF のコンデンサ、ZQ 抵抗)。
#           U1 の ZQ 抵抗 R328 (DDR_ZQ) は U1 のそばに残す。
#   消す: DDR_ の線とビアは全部 (引き直す)。それ以外のネットは、動かした部品のパッドがあるネットのうち、
#         動かす範囲 (x >= 72.5) の中にある線とビア。VDD_DDR の In3 ゾーンは右端を dx 広げる。
#   KiCad の Python。usage: python ddr_shift.py in.kicad_pcb out.kicad_pcb [dx=3]
import sys, re
import pcbnew

SRC, DST = sys.argv[1], sys.argv[2]
DX = float(sys.argv[3]) if len(sys.argv) > 3 else 3.0
b = pcbnew.LoadBoard(SRC)
mm = pcbnew.FromMM
X0, Y0, Y1 = 72.5, 22.0, 80.0

moved, nets = [], set()
for f in b.GetFootprints():
    r = f.GetReference()
    p = f.GetPosition()
    x, y = p.x / 1e6, p.y / 1e6
    if r in ('U301', 'U302') or (re.match(r'[RC]3\d\d$', r) and r != 'R328' and x >= X0 and Y0 <= y <= Y1):
        moved.append(r)
        nets |= {pd.GetNetname() for pd in f.Pads()}
        f.Move(pcbnew.VECTOR2I(mm(DX), 0))


def inside(pt):
    return pt.x / 1e6 >= X0 - 0.5 and Y0 - 1 <= pt.y / 1e6 <= Y1 + 1


kill = []
for t in b.GetTracks():
    n = t.GetNetname()
    if n.startswith('DDR_'):
        kill.append(t)
    elif n in nets and (inside(t.GetStart()) or inside(t.GetEnd())):
        kill.append(t)
for t in kill:
    b.Remove(t)
for z in b.Zones():
    if z.GetNetname() == 'VDD_DDR':
        ol = z.Outline()
        for i in range(ol.TotalVertices()):
            v = ol.CVertex(i)
            if v.x / 1e6 > 90:
                ol.SetVertex(i, pcbnew.VECTOR2I(v.x + mm(DX), v.y))
pcbnew.ZONE_FILLER(b).Fill(b.Zones())
b.Save(DST)
print('動かした', len(moved), '消した線', len(kill))
print(' '.join(sorted(moved)))
