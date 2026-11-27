# Freerouting がピンの手前で細くした線 (0.06〜0.09) を、ネットクラスの幅に戻す (2026-11-22)
#   クラスの幅 → 0.1 (基板の最小) の順に試し、DRC で違反した線は 1 段戻す。最後まで細いものは一覧を出す。
# usage: python fix_narrow.py [pcb]
import sys, json, subprocess, os, tempfile
import pcbnew

PCB = sys.argv[1] if len(sys.argv) > 1 else 'C:/MyWorks/ACROSS_V3_STM32/kicad/ACROSS_V3.kicad_pcb'
CLI = 'C:/Program Files/KiCad/10.0/bin/kicad-cli.exe'


def mm(v):
    return int(round(v * 1e6))


def drc_bad(path):
    out = os.path.join(tempfile.gettempdir(), 'narrow_drc.json')
    subprocess.run([CLI, 'pcb', 'drc', '--format', 'json', '--severity-error', '-o', out, path], capture_output=True)
    d = json.load(open(out, encoding='utf8'))
    bad = set()
    for v in d['violations']:
        if v['type'] in ('clearance', 'tracks_crossing', 'shorting_items', 'copper_edge_clearance', 'hole_clearance', 'diff_pair_gap_out_of_range'):
            for it in v['items']:
                bad.add(it['uuid'])
    return bad


b = pcbnew.LoadBoard(PCB)
pro = json.load(open(PCB[:-10] + '.kicad_pro', encoding='utf8'))
CW = {c['name']: c.get('track_width', 0.12) for c in pro['net_settings']['classes']}
cand = {}
for t in b.GetTracks():
    if t.Type() != pcbnew.PCB_TRACE_T:
        continue
    cw = mm(max(CW.get(n, CW.get('Default', 0.12)) for n in t.GetNetClassName().split(',')))
    if t.GetWidth() < cw:
        steps = [cw] + ([mm(0.1)] if cw > mm(0.1) else [])
        cand[t.m_Uuid.AsString()] = (t, steps)
print('細い線', len(cand))
for si in range(2):
    trying = {}
    for u, (t, steps) in cand.items():
        if si < len(steps) and steps[si] > t.GetWidth():
            trying[u] = (t, t.GetWidth())
            t.SetWidth(steps[si])
    for it in range(6):
        b.Save(PCB)
        bad = drc_bad(PCB) & set(trying)
        print(f'段 {si}: 試行 {len(trying)} 違反 {len(bad)}', flush=True)
        if not bad:
            break
        for u in bad:
            t, w = trying.pop(u)
            t.SetWidth(w)
    for u in trying:
        if si == 0 or True:
            pass
left = [(t.GetNetname(), round(pcbnew.ToMM(t.GetWidth()), 3), b.GetLayerName(t.GetLayer())) for u, (t, s) in cand.items() if t.GetWidth() < mm(0.1)]
pcbnew.ZONE_FILLER(b).Fill(b.Zones())
b.Save(PCB)
print('0.1 未満のまま', len(left))
for x in left[:60]:
    print('  ', x)
