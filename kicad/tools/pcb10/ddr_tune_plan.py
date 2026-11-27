# 長さ合わせ (蛇行) の下準備 (2026-11-23)。KiCad の Python で動かす。
#   DDR のネットごとに、区間 (U1→1 個目のメモリ、U301→U302) の経路に乗っている線と、その長さを JSON に書く。
#   ddr_tune.py がこれと mr_export の JSON (障害物) を読んで蛇行を決める。
# usage: python ddr_tune_plan.py pcb out.json
import sys, os, json, re
import pcbnew
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ddr_graph

PCB, OUT = sys.argv[1], sys.argv[2]
b = pcbnew.LoadBoard(PCB)
g, pads = ddr_graph.build(b)
res = {}
for (net, ref) in list(pads):
    if ref != 'U1':
        continue
    chips = [r for r in ('U301', 'U302') if (net, r) in pads]
    if not chips:
        continue
    legs = {}
    pairs = [('U1', chips[0])] + ([('U301', 'U302')] if len(chips) == 2 else [])
    for ra, rb in pairs:
        p = ddr_graph.path(g, net, pads[(net, ra)], pads[(net, rb)])
        if p is None:
            legs[f'{ra}-{rb}'] = None
            continue
        L = 0.0
        segs = []
        for u, v in zip(p, p[1:]):
            for w_, ll in g[net][u]:
                if w_ == v:
                    L += ll
                    break
            s = ddr_graph.SEG[net].get((u, v))
            if s:
                segs.append(s)
        legs[f'{ra}-{rb}'] = {'len': L, 'segs': segs}
    res[net] = legs
json.dump(res, open(OUT, 'w', encoding='utf8'))
print('nets', len(res), 'legs', sum(len(v) for v in res.values()), 'not connected', sum(1 for v in res.values() for x in v.values() if x is None))
