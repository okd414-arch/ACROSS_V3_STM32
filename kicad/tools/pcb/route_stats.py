# 配線の縦横の割合を層ごとに測る (2026-11-20)
# 方針: 表面 F.Cu = 横、裏面 B.Cu = 縦 (強めの原則)。DDR・USB・ETH・LCD・eMMC/SD などの高速配線は対象外 (別に集計)。
# 内層の信号層は L3 (In2.Cu) = 縦、L6 (In5.Cu) = 横 を提案中 (未確認)。
# usage: python route_stats.py board.kicad_pcb
import sys, re, collections
import pcbnew
from pcbnew import ToMM

b = pcbnew.LoadBoard(sys.argv[1])
EXEMPT = re.compile(r'^(DDR_|USB[12]_D|ETH_|LCD_|EMMC_(CK|CMD|D\d)|SD_(CK|CMD|D\d)|GPS_10MPPS)')
WANT = {'F.Cu': 'H', 'In2.Cu': 'V', 'In5.Cu': 'H', 'B.Cu': 'V'}
stat = collections.defaultdict(lambda: collections.Counter())
for t in b.GetTracks():
    if t.GetClass() != 'PCB_TRACK':
        continue
    layer = b.GetLayerName(t.GetLayer())
    x0, y0, x1, y1 = ToMM(t.GetStart().x), ToMM(t.GetStart().y), ToMM(t.GetEnd().x), ToMM(t.GetEnd().y)
    dx, dy = abs(x1 - x0), abs(y1 - y0)
    n = t.GetNetname()
    grp = 'exempt' if EXEMPT.match(n) else 'normal'
    if dy <= 0.05 * max(dx, 1e-9) or dy < 0.01:
        o = 'H'
    elif dx <= 0.05 * max(dy, 1e-9) or dx < 0.01:
        o = 'V'
    else:
        o = 'D'
    stat[(grp, layer)][o] += (dx * dx + dy * dy) ** 0.5
print('層ごとの配線長 (mm) と、向きの割合 [H=横, V=縦, D=斜め]')
for (grp, layer), c in sorted(stat.items()):
    tot = sum(c.values())
    want = WANT.get(layer, '-')
    ok = c.get(want, 0) / tot * 100 if tot and want in 'HV' else float('nan')
    print(f'{grp:7s} {layer:7s} 合計 {tot:8.1f}  H {c["H"]/tot*100:5.1f}%  V {c["V"]/tot*100:5.1f}%  D {c["D"]/tot*100:5.1f}%   (原則 {want}: {ok:5.1f}%)')
