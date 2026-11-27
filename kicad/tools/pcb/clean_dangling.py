# 行き止まりの線・どこにもつながらないビアを消す (2026-11-22)。ロックしたものは残す。
#   kicad-cli の DRC の track_dangling / via_dangling を見て消す、を変化がなくなるまで (最大 8 回)。
#   pcbnew は 1 プロセスで基板を何度も読むと壊れるので、1 回ごとに自分を別プロセスで呼ぶ。
# usage: python clean_dangling.py [pcb]
import sys, json, os, subprocess, tempfile

PCB = sys.argv[1] if len(sys.argv) > 1 and sys.argv[1] != '--once' else 'C:/MyWorks/ACROSS_V3_STM32/kicad/ACROSS_V3.kicad_pcb'
CLI = 'C:/Program Files/KiCad/10.0/bin/kicad-cli.exe'
KPY = 'C:/Program Files/KiCad/10.0/bin/python.exe'

if '--once' in sys.argv:
    import pcbnew
    out = os.path.join(tempfile.gettempdir(), 'dangling_drc.json')
    subprocess.run([CLI, 'pcb', 'drc', '--format', 'json', '--severity-all', '-o', out, PCB], capture_output=True)
    d = json.load(open(out, encoding='utf8'))
    bad = {x['uuid'] for v in d['violations'] if v['type'] in ('track_dangling', 'via_dangling') for x in v['items']}
    b = pcbnew.LoadBoard(PCB)
    rm = [t for t in b.GetTracks() if t.m_Uuid.AsString() in bad and not t.IsLocked()]
    for t in rm:
        b.Remove(t)
    if rm:
        pcbnew.ZONE_FILLER(b).Fill(b.Zones())
        b.Save(PCB)
    print('N', len(rm))
    sys.exit(0)

total = 0
for it in range(8):
    p = subprocess.run([KPY, os.path.abspath(__file__), PCB, '--once'], capture_output=True, text=True, encoding='utf8', errors='replace')
    n = int([l for l in p.stdout.splitlines() if l.startswith('N ')][-1].split()[1])
    print(f'回 {it}: 消した {n}', flush=True)
    total += n
    if n == 0:
        break
print('合計', total)
