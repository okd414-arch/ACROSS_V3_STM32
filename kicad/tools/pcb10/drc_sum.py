# kicad-cli の DRC を流して、違反の種類ごとの数と例を出す (2026-11-21)
# usage: python drc_sum.py [pcb] [N例]
import sys, json, subprocess, collections, os, tempfile

KICAD = 'C:/MyWorks/ACROSS_V3_STM32/kicad'
pcb = sys.argv[1] if len(sys.argv) > 1 else KICAD + '/ACROSS_V3.kicad_pcb'
nex = int(sys.argv[2]) if len(sys.argv) > 2 else 3
out = os.path.join(tempfile.gettempdir(), 'drc_sum.json')
subprocess.run(['C:/Program Files/KiCad/10.0/bin/kicad-cli.exe', 'pcb', 'drc', '--format', 'json', '--severity-all', '-o', out, pcb],
               capture_output=True)
d = json.load(open(out, encoding='utf8'))
c = collections.Counter(v['type'] for v in d['violations'])
IGN = {'silk_overlap', 'silk_over_copper', 'drill_out_of_range'}
print('violations', sum(c.values()), c.most_common())
ex = collections.defaultdict(list)
for v in d['violations']:
    if v['type'] in IGN:
        continue
    if len(ex[v['type']]) < nex:
        ex[v['type']].append(v['description'] + ' | ' + ' / '.join(i['description'] for i in v['items']))
for k, L in ex.items():
    print('--', k)
    for s in L:
        print('   ', s[:300])
print('unconnected', len(d.get('unconnected_items', [])), 'parity', len(d.get('schematic_parity', [])))
