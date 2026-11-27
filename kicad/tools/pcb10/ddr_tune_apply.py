# ddr_tune.py の置き換え (蛇行) を基板に入れる (2026-11-23)。KiCad の Python で動かす。
#   もとの線を消して蛇行の線を入れる → DRC → 違反した置き換えは、蛇行を消してもとの線に戻す (最大 3 回)。
# usage: python ddr_tune_apply.py tune.json pcb
import sys, json, os, subprocess, tempfile
import pcbnew

E = json.load(open(sys.argv[1], encoding='utf8'))['edits']
PCB = sys.argv[2]
CLI = 'C:/Program Files/KiCad/10.0/bin/kicad-cli.exe'
LAY = [pcbnew.F_Cu, pcbnew.In2_Cu, pcbnew.In5_Cu, pcbnew.B_Cu]
mm = pcbnew.FromMM
b = pcbnew.LoadBoard(PCB)
byid = {t.m_Uuid.AsString(): t for t in b.GetTracks()}


def P(x, y):
    return pcbnew.VECTOR2I(mm(x), mm(y))


state = []
for e in E:
    orig = []
    for u in e['remove']:
        t = byid.get(u)
        if t is None:
            continue
        orig.append((t.GetStart(), t.GetEnd(), t.GetWidth(), t.GetLayer(), t.GetNetname()))
        b.Remove(t)
    new = []
    for l, ax, ay, bx, by, w, net in e['add']:
        t = pcbnew.PCB_TRACK(b)
        t.SetStart(P(ax, ay)); t.SetEnd(P(bx, by)); t.SetWidth(mm(w)); t.SetLayer(LAY[l]); t.SetNet(b.FindNet(net))
        b.Add(t)
        new.append(t)
    state.append({'orig': orig, 'new': new, 'ids': {t.m_Uuid.AsString() for t in new}, 'alive': True})
print('入れた置き換え', len(state))
BAD = ('clearance', 'tracks_crossing', 'shorting_items', 'copper_edge_clearance', 'hole_clearance', 'track_dangling')
for it in range(3):
    pcbnew.ZONE_FILLER(b).Fill(b.Zones())
    b.Save(PCB)
    out = os.path.join(tempfile.gettempdir(), 'tune_drc.json')
    subprocess.run([CLI, 'pcb', 'drc', '--format', 'json', '--severity-error', '--severity-warning', '-o', out, PCB], capture_output=True)
    d = json.load(open(out, encoding='utf8'))
    bad = {x['uuid'] for v in d['violations'] if v['type'] in BAD for x in v['items']}
    kill = [s for s in state if s['alive'] and s['ids'] & bad]
    print(f'DRC {it}: 違反した置き換え {len(kill)}', flush=True)
    if not kill:
        break
    for s in kill:
        for t in s['new']:
            b.Remove(t)
        for st, en, w, l, net in s['orig']:
            t = pcbnew.PCB_TRACK(b)
            t.SetStart(st); t.SetEnd(en); t.SetWidth(w); t.SetLayer(l); t.SetNet(b.FindNet(net))
            b.Add(t)
        s['alive'] = False
pcbnew.ZONE_FILLER(b).Fill(b.Zones())
b.Save(PCB)
print('残した', sum(s['alive'] for s in state), '戻した', sum(not s['alive'] for s in state))
