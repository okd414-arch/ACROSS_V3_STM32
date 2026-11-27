# 格子配線を 1 まとまり (IC やネットのグループ) 分まとめて回す (2026-11-22)
#   DRC (未接続の一覧) → mr_export → mr_route (--only) → mr_apply → 途中経過の写しを保存
#   写し: kicad/work/途中経過/NN_名前.kicad_pcb (あとで画像にするため、テキストのまま残す)
# usage: python mr_group.py NN 名前 NETREGEX [--margin 4]
import sys, subprocess, shutil, os

K = 'C:/MyWorks/ACROSS_V3_STM32/kicad'
KPY = 'C:/Program Files/KiCad/10.0/bin/python.exe'
PCB = os.environ.get('ACROSS_PCB', K + '/ACROSS_V3.kicad_pcb')  # 別の基板で回すときは環境変数で
W = K + '/work'
no, name, rx = sys.argv[1], sys.argv[2], sys.argv[3]
extra = [x for x in sys.argv[4:] if x != '--snap']


def run(cmd):
    p = subprocess.run(cmd, capture_output=True, text=True, encoding='utf8', errors='replace', cwd=W)
    for line in (p.stdout + p.stderr).splitlines():
        if 'memory leak' not in line:
            print(line, flush=True)


run([sys.executable, K + '/tools/pcb/drc_sum.py', PCB, '0'])
run([KPY, K + '/tools/pcb/mr_export.py', W + f'/mr_{no}.json', PCB])
run([sys.executable, K + '/tools/pcb/mr_route.py', W + f'/mr_{no}.json', W + f'/mr_{no}_routes.json', '--only', rx] + extra)
run([KPY, K + '/tools/pcb/mr_apply.py', W + f'/mr_{no}_routes.json', PCB])
# 写しは --snap のときだけ (途中経過は完成までに 4 つ程度でよい、とユーザー指示 2026-11-22)
if '--snap' in sys.argv:
    os.makedirs(W + '/途中経過', exist_ok=True)
    dst = W + f'/途中経過/{no}_{name}.kicad_pcb'
    shutil.copy(PCB, dst)
    print('写し', dst)
