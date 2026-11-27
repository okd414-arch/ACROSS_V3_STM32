# 指定ネットのパッドの分布 (範囲と、どの部品にあるか) を出す (2026-11-21)
# usage: python netspread.py survey.json NET [NET ...]
import sys, json

d = json.load(open(sys.argv[1], encoding='utf8'))
pos = {}
for f in d['fps']:
    for p in f['pads']:
        pos.setdefault(p['net'], []).append((f['ref'], p['x'], p['y'], f['back']))
for n in sys.argv[2:]:
    L = pos.get(n, [])
    if not L:
        print(n, 'なし')
        continue
    xs = [a[1] for a in L]
    ys = [a[2] for a in L]
    refs = {}
    for a in L:
        refs[a[0]] = refs.get(a[0], 0) + 1
    print(f'{n}: {len(L)} pads  x {min(xs):.1f}..{max(xs):.1f}  y {min(ys):.1f}..{max(ys):.1f}')
    print('   ', ' '.join(f'{r}({c})' if c > 1 else r for r, c in sorted(refs.items())))
