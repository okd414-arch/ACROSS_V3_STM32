# 残った未配線に的を絞る (2026-11-22): 未配線の両端のまわり (±R mm) の線を消し、その接続を先に引いてから、消した分を引き直す。
#   1 回ごとに未配線の数を比べ、悪くなったら元に戻す。
# usage: python mr_focus.py 開始番号 回数 [--r 1.5]
import sys, subprocess, shutil, json, os, tempfile, re

K = 'C:/MyWorks/ACROSS_V3_STM32/kicad'
KPY = 'C:/Program Files/KiCad/10.0/bin/python.exe'
PCB = os.environ.get('ACROSS_PCB', K + '/ACROSS_V3.kicad_pcb')
W = K + '/work'
no, rounds = int(sys.argv[1]), int(sys.argv[2])
R = float(sys.argv[sys.argv.index('--r') + 1]) if '--r' in sys.argv else 1.5
PY = sys.executable


def run(args, py=PY):
    p = subprocess.run([py] + args, capture_output=True, text=True, encoding='utf8', errors='replace', cwd=W)
    return p.stdout + p.stderr


def unconn():
    run([K + '/tools/pcb/drc_sum.py', PCB, '0'])
    d = json.load(open(os.path.join(tempfile.gettempdir(), 'drc_sum.json'), encoding='utf8'))
    return d['unconnected_items']


tmp = W + '/_focus_best.kicad_pcb'
for k in range(rounds):
    U = unconn()
    best = len(U)
    shutil.copy(PCB, tmp)
    nets = set()
    for v in U:
        for it in v['items'][:2]:
            m = re.search(r'\[([^\]]+)\]', it['description'])
            if m:
                nets.add(m.group(1))
            x, y = it['pos']['x'], it['pos']['y']
            run([K + '/tools/pcb/region_rip.py', str(x - R), str(y - R), str(x + R), str(y + R), PCB], py=KPY)
    run([K + '/tools/pcb/clean_dangling.py', PCB])
    rx = '^(' + '|'.join(re.escape(n) for n in sorted(nets)) + ')$'
    out = run([K + '/tools/pcb/mr_group.py', f'{no:03d}', 'focus', '.', '--first', rx, '--rip', '--maxrip', '6'])
    print('\n'.join(l for l in out.splitlines() if re.match(r'(ok |残した|FAIL)', l)), flush=True)
    run([K + '/tools/pcb/clean_dangling.py', PCB])
    out = run([K + '/tools/pcb/mr_group.py', f'{no + 1:03d}', 'focus2', '.'])
    run([K + '/tools/pcb/clean_dangling.py', PCB])
    u = len(unconn())
    print(f'回 {k}: 未配線 {best} → {u}', flush=True)
    if u > best:
        shutil.copy(tmp, PCB)
        print('悪くなったので戻した', flush=True)
    no += 2
    if u == 0:
        break
os.remove(tmp)
print('終わり 未配線', len(unconn()))
