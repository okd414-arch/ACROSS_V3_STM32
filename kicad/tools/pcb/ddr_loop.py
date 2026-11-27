# DDR の引き直し用の繰り返し配線 (2026-11-23)。mr_loop.py の DDR 版。
#   1 回 = DRC → mr_export --chain (DDR はフライバイの順の区間、ほかは DRC の未配線) → mr_route --pairs [--rip] → mr_apply → 掃除
#   はがす回とはがさない回を交互に。未配線が減ったら best.kicad_pcb に写す。悪くなったら戻して、順番を変えて続ける。
#   一時ファイルの場所は TMP/TEMP (別のセッションと分けるため、呼ぶ側で設定する)
# usage: python ddr_loop.py pcb 回数 [--maxrip 3] [--first REGEX]
import sys, subprocess, shutil, json, os, tempfile

K = 'C:/MyWorks/ACROSS_V3_STM32/kicad'
KPY = 'C:/Program Files/KiCad/10.0/bin/python.exe'
PCB = sys.argv[1]
rounds = int(sys.argv[2])
maxrip = sys.argv[sys.argv.index('--maxrip') + 1] if '--maxrip' in sys.argv else '3'
first = sys.argv[sys.argv.index('--first') + 1] if '--first' in sys.argv else 'CLK|DQS'
margin = sys.argv[sys.argv.index('--margin') + 1] if '--margin' in sys.argv else '4'  # 探す範囲の余白。混んだ所は広げると通る (2026-11-23)
W = os.path.dirname(PCB)
BEST = os.path.join(W, 'best.kicad_pcb')
T = K + '/tools/pcb/'


def run(cmd):
    p = subprocess.run(cmd, capture_output=True, text=True, encoding='utf8', errors='replace', cwd=W)
    return p.stdout + p.stderr


def unconn():
    run([sys.executable, T + 'drc_sum.py', PCB, '0'])
    d = json.load(open(os.path.join(tempfile.gettempdir(), 'drc_sum.json'), encoding='utf8'))
    return len(d['unconnected_items'])


def one(tag, rip):
    run([sys.executable, T + 'drc_sum.py', PCB, '0'])
    j, r = os.path.join(W, f'l_{tag}.json'), os.path.join(W, f'l_{tag}_routes.json')
    run([KPY, T + 'mr_export.py', j, PCB, '--chain'])
    out = run([sys.executable, T + 'mr_route.py', j, r, '--pairs', '--first', first, '--margin', margin] + (['--rip', '--maxrip', maxrip] if rip else []))
    print('   ', tag, [l for l in out.splitlines() if l.startswith('ok ')], flush=True)
    out = run([KPY, T + 'mr_apply.py', r, PCB])
    print('   ', [l for l in out.splitlines() if l.startswith('残した')], flush=True)
    run([KPY, T + 'clean_dangling.py', PCB])


best = unconn()
shutil.copy(PCB, BEST)
print('開始 未配線', best, flush=True)
for k in range(rounds):
    one(f'{k}a', True)
    one(f'{k}b', False)
    u = unconn()
    print(f'回 {k}: 未配線 {u} (一番良い {best})', flush=True)
    if u < best:
        best = u
        shutil.copy(PCB, BEST)
    elif u > best:
        shutil.copy(BEST, PCB)
        print('   悪くなったので戻した', flush=True)
    os.environ['MR_SEED'] = str(int(os.environ.get('MR_SEED_BASE', '0')) + k + 1)  # 並列で回すときは写しごとに MR_SEED_BASE を変える
    if best == 0:
        break
print('終わり 未配線', best)
