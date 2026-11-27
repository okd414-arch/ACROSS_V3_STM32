# 長さ合わせを 1 回まわす (2026-11-23): DRC → ddr_tune_plan → mr_export → ddr_tune → ddr_tune_apply → ddr_check
#   一時ファイルは TMP/TEMP (呼ぶ側で、別のセッションと分ける)
# usage: python ddr_tune_round.py pcb tag [ddr_tune の追加の引数 ...]
import sys, subprocess, os

K = 'C:/MyWorks/ACROSS_V3_STM32/kicad'
KPY = 'C:/Program Files/KiCad/10.0/bin/python.exe'
T = K + '/tools/pcb/'
PCB, tag = sys.argv[1], sys.argv[2]
extra = sys.argv[3:]
W = os.path.dirname(PCB)


def run(cmd, show=True):
    p = subprocess.run(cmd, capture_output=True, text=True, encoding='utf8', errors='replace', cwd=W)
    out = '\n'.join(l for l in (p.stdout + p.stderr).splitlines() if 'swig' not in l and 'memory leak' not in l)
    if show:
        print(out, flush=True)
    return out


run([sys.executable, T + 'drc_sum.py', PCB, '0'], show=False)
run([KPY, T + 'ddr_tune_plan.py', PCB, f'{W}/tp_{tag}.json'])
run([KPY, T + 'mr_export.py', f'{W}/ti_{tag}.json', PCB])
run([sys.executable, T + 'ddr_tune.py', f'{W}/tp_{tag}.json', f'{W}/ti_{tag}.json', f'{W}/tt_{tag}.json'] + extra)
run([KPY, T + 'ddr_tune_apply.py', f'{W}/tt_{tag}.json', PCB])
run([KPY, T + 'ddr_check.py', PCB] + (['--tol', '20'] if '--band' in extra else []))
