# silk_solve.py を繰り返し、紛らわしい/遠い文字の周りの文字も一緒に置き直す (2026-11-23)
# usage: python silk_auto.py silk_obs.json silk_layout.json [回数]
import sys, json, subprocess, os
HERE = os.path.dirname(os.path.abspath(__file__))
obs, dst = sys.argv[1], sys.argv[2]
N = int(sys.argv[3]) if len(sys.argv) > 3 else 4
d = json.load(open(obs, encoding='utf8'))
fps = {f['ref']: f for f in d['fps']}
force = set()


def score(L):
    tot = 0; poor = []
    for r, e in L.items():
        if e.get('changed') == 'hidden':
            tot += 20; poor.append(r)
        if 'q' in e:
            g, cov, amb = e['q']
            tot += g + 3 * cov + 2 * amb + (1.0 - e['h']) * 8
            if g > 0.8 or cov > 0.25 or amb > 0.2:
                poor.append(r)
    return tot, poor


best = None
for it in range(N):
    cmd = [sys.executable, os.path.join(HERE, 'silk_solve.py'), obs, dst + '.try']
    if force:
        cmd += ['--force', ','.join(sorted(force))]
    o = subprocess.run(cmd, capture_output=True, text=True, encoding='utf8')
    L = json.load(open(dst + '.try', encoding='utf8'))['refs']
    tot, poor = score(L)
    print('iter', it, 'force', len(force), 'score %.2f' % tot, 'poor', poor, flush=True)
    if best is None or tot < best[0]:
        best = (tot, open(dst + '.try', encoding='utf8').read())
    if not poor:
        break
    # poor な文字の部品の近く (4mm) にある文字を強制的に動かす対象に加える
    add = set()
    for r in poor:
        f = fps[r]; cx, cy = f['pos']
        for g in d['fps']:
            if g['side'] == f['side'] and abs(g['pos'][0] - cx) < 4 and abs(g['pos'][1] - cy) < 4:
                add.add(g['ref'])
    if add <= force:
        break
    force |= add
open(dst, 'w', encoding='utf8').write(best[1])
os.remove(dst + '.try')
print('best score %.2f' % best[0])
