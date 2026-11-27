# DDR の配線長をグループごとに集計する (2026-11-21)。ビアは層の間の厚みを足す (簡易に 1 個 0.8mm)
#   データ: バイトレーン 0〜3 (DQ0-7+DQM0+DQS0 …)。アドレス・コマンド・CLK はフライバイなので全長 (参考)
# usage: python ddr_lengths.py [pcb]
import sys, re, collections
import pcbnew

PCB = sys.argv[1] if len(sys.argv) > 1 else 'C:/MyWorks/ACROSS_V3_STM32/kicad/ACROSS_V3.kicad_pcb'
b = pcbnew.LoadBoard(PCB)
L = collections.Counter()
V = collections.Counter()
for t in b.GetTracks():
    n = t.GetNetname()
    if not n.startswith('DDR_'):
        continue
    if t.Type() == pcbnew.PCB_VIA_T:
        V[n] += 1
    else:
        L[n] += pcbnew.ToMM(t.GetLength())


def lane(n):
    m = re.match(r'DDR_DQ(\d+)$', n)
    if m:
        return f'lane{int(m.group(1)) // 8}'
    m = re.match(r'DDR_(DQM|DQS)(\d)', n)
    if m:
        return f'lane{m.group(2)}'
    if re.match(r'DDR_CLK', n):
        return 'clk'
    return 'addr/cmd'


g = collections.defaultdict(list)
nets = sorted({str(k) for k in b.GetNetInfo().NetsByName().keys() if str(k).startswith('DDR_')})
for n in nets:
    g[lane(n)].append((n, L[n] + 0.8 * V[n], V[n]))
for k in sorted(g):
    v = [x[1] for x in g[k]]
    print(f'{k:9s} n={len(v):2d}  min {min(v):6.1f}  max {max(v):6.1f}  差 {max(v) - min(v):5.1f} mm')
    if k.startswith('lane') or k == 'clk':
        print('   ', ' '.join(f'{n[4:]}={l:.1f}({vi}v)' for n, l, vi in g[k]))
