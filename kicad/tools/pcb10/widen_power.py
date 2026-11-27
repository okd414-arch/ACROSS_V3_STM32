# 電源クラスの配線を、DRC に引っかからない範囲で太くする (2026-11-21)
#   幅の候補を大きい順に試す: 線を広げて保存 → kicad-cli で DRC → 違反した線を元に戻す、を違反がなくなるまで繰り返す。
#   面のネット (GND・VDD など、ビアまでの短い線) は 0.4 まで、それ以外の電源は 1.0 まで。
# usage: python widen_power.py [pcb]
import sys, json, subprocess, os, tempfile, re
import pcbnew

PCB = sys.argv[1] if len(sys.argv) > 1 else 'C:/MyWorks/ACROSS_V3_STM32/kicad/ACROSS_V3.kicad_pcb'
CLI = 'C:/Program Files/KiCad/10.0/bin/kicad-cli.exe'
PLANE_NETS = {'GND', 'GND_A', 'GND_D', 'VDD', 'VDD_DDR', 'VDD_CORE', '+3.3V', '+3.3V_A', '+5V_A', '+5V_D', '+9V_D'}
STEPS_BIG = [1.0, 0.6, 0.4]
STEPS_PLANE = [0.4]


def mm(v):
    return int(round(v * 1e6))


def drc_bad_uuids(path):
    out = os.path.join(tempfile.gettempdir(), 'widen_drc.json')
    subprocess.run([CLI, 'pcb', 'drc', '--format', 'json', '--severity-error', '-o', out, path], capture_output=True)
    d = json.load(open(out, encoding='utf8'))
    bad = set()
    for v in d['violations']:
        if v['type'] in ('clearance', 'tracks_crossing', 'shorting_items', 'copper_edge_clearance', 'hole_clearance', 'track_width'):
            for it in v['items']:
                bad.add(it['uuid'])
    return bad


b = pcbnew.LoadBoard(PCB)
cand = {}
for t in b.GetTracks():
    if t.Type() != pcbnew.PCB_TRACE_T:
        continue
    nc = t.GetEffectiveNetClass().GetName() if hasattr(t, 'GetEffectiveNetClass') else t.GetNetClassName()
    if 'POWER' not in nc.split(','):
        continue
    steps = STEPS_PLANE if t.GetNetname() in PLANE_NETS else STEPS_BIG
    cand[t.m_Uuid.AsString()] = (t, t.GetWidth(), steps)
print('候補', len(cand))
done = {}
for step_i in range(max(len(STEPS_BIG), len(STEPS_PLANE))):
    trying = {}
    for u, (t, w0, steps) in cand.items():
        if u in done or step_i >= len(steps):
            continue
        w = mm(steps[step_i])
        if w > t.GetWidth():
            trying[u] = (t, t.GetWidth())
            t.SetWidth(w)
    for it in range(5):
        b.Save(PCB)
        bad = drc_bad_uuids(PCB) & set(trying)
        print(f'幅 {STEPS_BIG[step_i] if step_i < len(STEPS_BIG) else "-"}: 試行 {len(trying)} 違反 {len(bad)}', flush=True)
        if not bad:
            break
        for u in bad:
            t, wprev = trying.pop(u)
            t.SetWidth(wprev)
    for u in trying:
        done[u] = True
pcbnew.ZONE_FILLER(b).Fill(b.Zones())
b.Save(PCB)
print('太くした線', len(done), '/', len(cand))
