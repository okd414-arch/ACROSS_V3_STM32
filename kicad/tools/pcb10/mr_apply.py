# mr_route.py の結果を基板に入れる (2026-11-22)。KiCad の Python で動かす。
#   入れたあと kicad-cli で DRC を回し、違反を出した経路は接続ごと取り除く (最大 4 回)。
#   取り除いた経路は routes_rejected.json に書く。
# usage: python mr_apply.py routes.json [pcb]
import sys, json, os, subprocess, tempfile
import pcbnew

R = json.load(open(sys.argv[1], encoding='utf8'))
PCB = sys.argv[2] if len(sys.argv) > 2 else 'C:/MyWorks/ACROSS_V3_STM32/kicad/ACROSS_V3.kicad_pcb'
CLI = 'C:/Program Files/KiCad/10.0/bin/kicad-cli.exe'
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lay10 import LAY  # 10 層の写し (2026-11-24)
mm = pcbnew.FromMM
b = pcbnew.LoadBoard(PCB)


def P(x, y):
    return pcbnew.VECTOR2I(mm(x), mm(y))


# はがす線 (mr_route --rip が選んだもの)
ripset = {u for r in R['routes'] for u in r.get('rip', [])}
if ripset:
    rm = [t for t in b.GetTracks() if t.m_Uuid.AsString() in ripset]
    for t in rm:
        b.Remove(t)
    print('はがした線', len(rm), 'ネット', sorted({n for r in R['routes'] for n in r.get('rip_nets', [])}))
added = []  # 経路ごとの uuid の集合
objs = []
for r in R['routes']:
    net = b.FindNet(r['net'])
    us, os_ = set(), []
    for l, ax, ay, bx, by, w in r['segs']:
        t = pcbnew.PCB_TRACK(b)
        t.SetStart(P(ax, ay)); t.SetEnd(P(bx, by)); t.SetWidth(mm(w)); t.SetLayer(LAY[l]); t.SetNet(net)
        b.Add(t); us.add(t.m_Uuid.AsString()); os_.append(t)
    for vv in r['vias']:
        x, y = vv[0], vv[1]
        dia, drl = (vv[2], vv[3]) if len(vv) > 2 else (0.45, 0.2)
        v = pcbnew.PCB_VIA(b)
        v.SetPosition(P(x, y)); v.SetWidth(mm(dia)); v.SetDrill(mm(drl)); v.SetNet(net)
        b.Add(v); us.add(v.m_Uuid.AsString()); os_.append(v)
    added.append(us)
    objs.append(os_)
print('入れた経路', len(added))

BAD_TYPES = ('clearance', 'tracks_crossing', 'shorting_items', 'copper_edge_clearance', 'hole_clearance',
             'hole_to_hole', 'holes_co_located', 'track_width', 'via_diameter', 'annular_width')
rej = []
alive = set(range(len(added)))
for it in range(4):
    pcbnew.ZONE_FILLER(b).Fill(b.Zones())
    b.Save(PCB)
    out = os.path.join(tempfile.gettempdir(), 'mr_apply_drc.json')
    subprocess.run([CLI, 'pcb', 'drc', '--format', 'json', '--severity-error', '--severity-warning', '-o', out, PCB], capture_output=True)
    d = json.load(open(out, encoding='utf8'))
    bad = set()
    for v in d['violations']:
        if v['type'] in BAD_TYPES:
            for x in v['items']:
                bad.add(x['uuid'])
    kill = [i for i in alive if added[i] & bad]
    import collections
    why = collections.Counter()
    allnew = set().union(*[added[i] for i in alive]) if alive else set()
    for v in d['violations']:
        if v['type'] in BAD_TYPES and any(x['uuid'] in allnew for x in v['items']):
            why[v['type']] += 1
            if why[v['type']] <= 2:
                print('   ', v['type'], v['description'][:90], '|', ' / '.join(x['description'][:40] for x in v['items']))
    print('   違反の種類', dict(why))
    print(f'DRC {it}: 違反した経路 {len(kill)}', flush=True)
    if not kill:
        break
    for i in kill:
        for o in objs[i]:
            b.Remove(o)
        alive.discard(i)
        rej.append(R['routes'][i])
pcbnew.ZONE_FILLER(b).Fill(b.Zones())
b.Save(PCB)
json.dump(rej, open(os.path.splitext(sys.argv[1])[0] + '_rejected.json', 'w', encoding='utf8'))
print('残した経路', len(alive), '取り除いた', len(rej))
