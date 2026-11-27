# 残り数本で止まったときの追い込み (2026-11-24)
#   1 回 = 未配線の 1 本だけを、はがす数の上限なし・広い範囲で通す → はがれた線を (はがして) 引く → はがさずに引く → 掃除。
#   未配線が 0 になるか、回数を使い切るまで。一番良い時を best.kicad_pcb に写す。悪くなったら戻す。
#   一時ファイルは TMP/TEMP (呼ぶ側で分ける)。パスは絶対パスで渡すこと (道具は基板のフォルダで動く)。
# usage: python ddr_chase.py pcb 回数 [--margin 30]
import sys, subprocess, shutil, json, os, tempfile, re, random

K = 'C:/MyWorks/ACROSS_V3_STM32/kicad'
KPY = 'C:/Program Files/KiCad/10.0/bin/python.exe'
T = K + '/tools/pcb/'
PCB = os.path.abspath(sys.argv[1])
rounds = int(sys.argv[2])
margin = sys.argv[sys.argv.index('--margin') + 1] if '--margin' in sys.argv else '30'
W = os.path.dirname(PCB)
BEST = os.path.join(W, 'best.kicad_pcb')


def run(cmd):
    p = subprocess.run(cmd, capture_output=True, text=True, encoding='utf8', errors='replace', cwd=W)
    return p.stdout + p.stderr


def drc():
    run([sys.executable, T + 'drc_sum.py', PCB, '0'])
    d = json.load(open(os.path.join(tempfile.gettempdir(), 'drc_sum.json'), encoding='utf8'))
    nets = []
    for u in d['unconnected_items']:
        m = re.search(r'\[([^\]]+)\]', u['items'][0]['description'])
        if m:
            nets.append(m.group(1))
    return nets


def step(tag, args):
    j, r = os.path.join(W, f'c_{tag}.json'), os.path.join(W, f'c_{tag}_r.json')
    run([KPY, T + 'mr_export.py', j, PCB, '--chain'])
    out = run([sys.executable, T + 'mr_route.py', j, r, '--pairs'] + args)
    print('   ', tag, [l for l in out.splitlines() if l.startswith(('ok ', 'OK '))][:6], flush=True)
    run([KPY, T + 'mr_apply.py', r, PCB])
    run([KPY, T + 'clean_dangling.py', PCB])


nets = drc()
best = len(nets)
shutil.copy(PCB, BEST)
print('開始 未配線', best, nets, flush=True)
rng = random.Random(int(os.environ.get('MR_SEED', '1')))
for k in range(rounds):
    if not nets:
        break
    net = rng.choice(nets)
    step(f'{k}a', ['--only', re.escape(net) + '$', '--rip', '--maxrip', '99', '--margin', margin])
    if drc():
        step(f'{k}b', ['--rip', '--maxrip', '3', '--margin', '8'])
    if drc():
        step(f'{k}c', ['--margin', '8'])
    nets = drc()
    print(f'回 {k} ({net}): 未配線 {len(nets)} {nets} (一番良い {best})', flush=True)
    if len(nets) < best:
        best = len(nets); shutil.copy(PCB, BEST)
    elif len(nets) > best + 2:
        shutil.copy(BEST, PCB); nets = drc()
        print('   悪くなったので戻した', flush=True)
    os.environ['MR_SEED'] = str(rng.randint(1, 10 ** 6))
print('終わり 未配線', best)
