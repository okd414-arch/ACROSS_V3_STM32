# 格子配線の繰り返し (2026-11-22): はがす本数を制限して引く → 掃除 → はがさずに引く → 掃除。
#   1 回ごとに未配線の数を数え、一番良い状態の写しを残す。悪くなったら一番良い写しに戻す。
#   写し: work/途中経過/NN_loopK_未配線M.kicad_pcb
# usage: python mr_loop.py 開始番号 回数 [--maxrip 3] [--keep]
#   --keep: 悪くなっても戻して続ける。回ごとに MR_SEED を変えて、引く順番をばらつかせる
import sys, subprocess, shutil, json, os, tempfile, re

K = 'C:/MyWorks/ACROSS_V3_STM32/kicad'
PCB = os.environ.get('ACROSS_PCB', K + '/ACROSS_V3.kicad_pcb')  # 別の基板で回すときは環境変数で
W = K + '/work'
no0, rounds = int(sys.argv[1]), int(sys.argv[2])
maxrip = sys.argv[sys.argv.index('--maxrip') + 1] if '--maxrip' in sys.argv else '3'
PY = sys.executable


def run(args):
    p = subprocess.run([PY] + args, capture_output=True, text=True, encoding='utf8', errors='replace', cwd=W)
    return p.stdout + p.stderr


def unconn():
    run([K + '/tools/pcb/drc_sum.py', PCB, '0'])
    d = json.load(open(os.path.join(tempfile.gettempdir(), 'drc_sum.json'), encoding='utf8'))
    return len(d['unconnected_items'])


best = unconn()
best_file = W + '/途中経過/' + os.environ.get('ACROSS_SNAP', '') + f'{no0:02d}_loop開始_未配線{best}.kicad_pcb'
shutil.copy(PCB, best_file)
print('開始 未配線', best, flush=True)
no = no0 + 1
for k in range(rounds):
    out = run([K + '/tools/pcb/mr_group.py', f'{no:02d}', f'loop{k}_はがし{maxrip}', '.', '--rip', '--maxrip', maxrip])
    print('\n'.join(l for l in out.splitlines() if re.match(r'(ok |残した)', l)), flush=True)
    run([K + '/tools/pcb/clean_dangling.py', PCB])
    out = run([K + '/tools/pcb/mr_group.py', f'{no + 1:02d}', f'loop{k}_はがさず', '.'])
    print('\n'.join(l for l in out.splitlines() if re.match(r'(ok |残した)', l)), flush=True)
    run([K + '/tools/pcb/clean_dangling.py', PCB])
    u = unconn()
    print(f'回 {k}: 未配線 {u} (一番良い {best})', flush=True)
    if u < best:
        best = u
        old = best_file
        best_file = W + '/途中経過/' + os.environ.get('ACROSS_SNAP', '') + f'{no + 1:02d}_loop{k}_未配線{u}.kicad_pcb'
        shutil.copy(PCB, best_file)
        os.remove(old)  # 写しは一番良いものだけ残す
    elif u > best:
        shutil.copy(best_file, PCB)
        print('悪くなったので戻した', best_file, flush=True)
        if '--keep' not in sys.argv:
            break
    elif '--keep' not in sys.argv:
        break
    # --keep: 悪くても止めずに、次の回は引く順番を変えて (MR_SEED) もう一度試す (2026-11-22)
    os.environ['MR_SEED'] = str(k + 1)
    no += 2
    if best == 0:
        break
print('終わり 未配線', best, best_file)
