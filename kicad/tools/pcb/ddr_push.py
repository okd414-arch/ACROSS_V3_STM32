# 残った未配線を押し込む (2026-11-24)。ddr_loop が同じ数で止まったときに使う。
#   1 回: DRC の未配線のネット → 広い範囲 (--margin) で、はがしてよい数を多めにして引く → 通れたネットの線をロック
#   → はがされたネットが次の回の未配線になる。ロックした線は二度とはがさないので、行ったり来たりしない。
#   最後にロックを外す。未配線が一番少なかった時の基板を best_push.kicad_pcb に写す。
# usage: python ddr_push.py pcb 回数 [--maxrip 15] [--margin 12]
import sys, subprocess, shutil, json, os, tempfile

K = 'C:/MyWorks/ACROSS_V3_STM32/kicad'
KPY = 'C:/Program Files/KiCad/10.0/bin/python.exe'
T = K + '/tools/pcb/'
PCB, rounds = sys.argv[1], int(sys.argv[2])
maxrip = sys.argv[sys.argv.index('--maxrip') + 1] if '--maxrip' in sys.argv else '15'
margin = sys.argv[sys.argv.index('--margin') + 1] if '--margin' in sys.argv else '12'
W = os.path.dirname(PCB)
BEST = os.path.join(W, 'best_push.kicad_pcb')


def run(cmd):
    p = subprocess.run(cmd, capture_output=True, text=True, encoding='utf8', errors='replace', cwd=W)
    return p.stdout + p.stderr


def unc_nets():
    run([sys.executable, T + 'drc_sum.py', PCB, '0'])
    d = json.load(open(os.path.join(tempfile.gettempdir(), 'drc_sum.json'), encoding='utf8'))
    nets = set()
    for v in d['unconnected_items']:
        for it in v['items']:
            s = it['description']
            if '[' in s:
                nets.add(s[s.index('[') + 1:s.index(']')])
    return len(d['unconnected_items']), nets


u, before = unc_nets()
best = u
shutil.copy(PCB, BEST)
print('開始 未配線', u, sorted(before), flush=True)
for k in range(rounds):
    j, r = os.path.join(W, f'p_{k}.json'), os.path.join(W, f'p_{k}_routes.json')
    run([KPY, T + 'mr_export.py', j, PCB, '--chain'])
    out = run([sys.executable, T + 'mr_route.py', j, r, '--pairs', '--first', 'CLK|DQS', '--rip', '--maxrip', maxrip, '--margin', margin])
    print('   ', k, [l for l in out.splitlines() if l.startswith('ok ')], flush=True)
    run([KPY, T + 'mr_apply.py', r, PCB])
    run([KPY, T + 'clean_dangling.py', PCB])
    u, after = unc_nets()
    done = before - after
    if done:
        run([KPY, T + 'ddr_lock.py', PCB, 'lock', ','.join(sorted(done))])
    print(f'回 {k}: 未配線 {u} 通れた {sorted(done)} 残り {sorted(after)}', flush=True)
    if u < best:
        best = u
        shutil.copy(PCB, BEST)
    before = after
    if u == 0:
        break
for f in (PCB, BEST):
    run([KPY, T + 'ddr_lock.py', f, 'unlock-all'])
print('終わり 未配線', best)
