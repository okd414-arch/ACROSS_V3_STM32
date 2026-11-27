# DDR の配線長を AN5122 (STM32MP1 DDR 配線ガイド) の規則で確かめる (2026-11-23)
#   ネットごとに、線とビアのつながりをたどって U1 のパッドから各メモリ (U301 / U302) のパッドまでの最短の長さを出す。
#   ビアの長さは層の間の厚み (F 0 / In2 0.25 / In5 1.31 / B 1.54 mm)。IC パッケージの中の長さは入れていない (ST の表が必要)。
#   規則 (DDR3L 2 個のフライバイ、6.1 / 6.3 節):
#     - 同じバイトの DQ・DQM と DQS (P/N の平均) の差 ±1.016mm
#     - DQS は CLK (平均) より 0〜14.986mm 短い (そのメモリでの長さ)
#     - アドレス・コマンドは CLK より 0〜1.016mm 短い (それぞれのメモリで)
#     - 2 個目と 1 個目のバイトの長さの差 33.02mm 以内、CLK 120mm 以内
#   ペアは P/N を並べて引く (長さの許容値は書かれていない)。ここでは P/N の差も出す。
# usage: python ddr_check.py [pcb] [--json out.json]
import sys, re, json, heapq, collections, math
import pcbnew

PCB = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith('--') else 'C:/MyWorks/ACROSS_V3_STM32/kicad/ACROSS_V3.kicad_pcb'
OUT = sys.argv[sys.argv.index('--json') + 1] if '--json' in sys.argv else None
# --tol T: ユーザーの緩めた規則 (2026-11-23「等長は 20mm 程度まで許容」)。DQ-DQS、CLK-DQS、CLK-A/C をすべて ±T で見る。P/N の差は 10mm 以内。
TOL = float(sys.argv[sys.argv.index('--tol') + 1]) if '--tol' in sys.argv else None
PN_MAX = 10.0
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ddr_graph
b = pcbnew.LoadBoard(PCB)
graph, pads = ddr_graph.build(b)


def dist(net, src):
    return ddr_graph.dist(graph, net, src)

nets = sorted({k[0] for k in pads})
L = {}
for n in nets:
    if ('DDR_' + n[4:], 'U1') not in pads:
        continue
    d = dist(n, pads[(n, 'U1')])
    L[n] = {r: d.get(pads[(n, r)]) for r in ('U301', 'U302') if (n, r) in pads}


def f(v):
    return '  --  ' if v is None else f'{v:6.1f}'


def mean(a, c):
    return None if a is None or c is None else (a + c) / 2


bad = []
clk = {r: mean(L['DDR_CLKP'].get(r), L['DDR_CLKN'].get(r)) for r in ('U301', 'U302')}
print('CLK  U301', f(clk['U301']), ' U302', f(clk['U302']), '  P/N の差', ' '.join(f(abs(L['DDR_CLKP'][r] - L['DDR_CLKN'][r]) if L['DDR_CLKP'][r] and L['DDR_CLKN'][r] else None) for r in ('U301', 'U302')))
for r in ('U301', 'U302'):
    if TOL and L['DDR_CLKP'][r] and L['DDR_CLKN'][r] and abs(L['DDR_CLKP'][r] - L['DDR_CLKN'][r]) > PN_MAX:
        bad.append(f'CLK {r} P/N差')
    if clk[r] and clk[r] > 120:
        bad.append(f'CLK {r} {clk[r]:.1f} > 120')
# レーンのつながる先はパッドから決める (2026-11-23 のレーン入れ替えで 1 → U302、2 → U301)
lanes = {k: ('U301' if (f'DDR_DQS{k}P', 'U301') in pads else 'U302') for k in range(4)}
first_mem = [k for k in lanes if lanes[k] == 'U301']
second_mem = [k for k in lanes if lanes[k] == 'U302']
lane_len = {}
for k, r in lanes.items():
    dqs = mean(L[f'DDR_DQS{k}P'][r], L[f'DDR_DQS{k}N'][r])
    lane_len[k] = dqs
    pn = abs(L[f'DDR_DQS{k}P'][r] - L[f'DDR_DQS{k}N'][r]) if dqs is not None else None
    mem = [f'DDR_DQ{i}' for i in range(8 * k, 8 * k + 8)] + [f'DDR_DQM{k}']
    dv = {m: (None if L[m][r] is None or dqs is None else L[m][r] - dqs) for m in mem}
    nbad = sum(1 for v in dv.values() if v is None or abs(v) > (TOL or 1.016))
    if TOL and pn is not None and pn > PN_MAX:
        bad.append(f'レーン{k} DQS P/N差 {pn:.1f}')
    c2 = None if dqs is None or clk[r] is None else clk[r] - dqs
    print(f'レーン{k} ({r}) DQS {f(dqs)} P/N差 {f(pn)}  CLK-DQS {f(c2)} (0〜15)  DQ-DQS の差: ' + ' '.join(f'{m[4:]}{"" if v is None else f"{v:+.1f}"}' for m, v in dv.items()) + f'  外れ {nbad}')
    if nbad:
        bad.append(f'レーン{k} DQ-DQS 外れ {nbad}')
    if c2 is None or not ((-TOL <= c2 <= TOL) if TOL else (0 <= c2 <= 14.986)):
        bad.append(f'レーン{k} CLK-DQS {c2}')
ac = [n for n in nets if L.get(n) and 'U302' in L[n] and not re.search(r'CLK|DQ', n) and n != 'DDR_RESETN']
for r in ('U301', 'U302'):
    dv = {n: (None if L[n][r] is None or clk[r] is None else clk[r] - L[n][r]) for n in ac}
    nb = [n for n, v in dv.items() if v is None or not ((-TOL <= v <= TOL) if TOL else (0 <= v <= 1.016))]
    vals = [v for v in dv.values() if v is not None]
    print(f'A/C {r}: CLK-A/C の範囲 {min(vals) if vals else 0:+.1f} 〜 {max(vals) if vals else 0:+.1f} (0〜1.016)  外れ {len(nb)}/{len(ac)}')
    if nb:
        bad.append(f'A/C {r} 外れ {len(nb)}')
if None not in lane_len.values():
    d12 = max(lane_len[k] for k in second_mem) - min(lane_len[k] for k in first_mem)
    print(f'バイトの長さ 2 個目 - 1 個目: {d12:.1f} (33.02 以内)')
print('規則の外れ:', len(bad), '; '.join(bad))
if OUT:
    json.dump({'L': L, 'clk': clk, 'bad': bad}, open(OUT, 'w', encoding='utf8'), ensure_ascii=False, indent=0)
