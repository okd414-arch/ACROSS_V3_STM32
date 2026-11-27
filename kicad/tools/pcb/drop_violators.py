# DRC の間隔違反に関わる (ロックしていない) 線を消す (2026-11-22)。消した線はあとで格子配線で引き直す。
#   違反の 2 つのうち、線 (配線) の方を消す。両方が線なら短い方。
# usage: python drop_violators.py [pcb]   (先に drc_sum.py でその基板の DRC を回しておく)
import sys, json, os, tempfile
import pcbnew

PCB = sys.argv[1] if len(sys.argv) > 1 else 'C:/MyWorks/ACROSS_V3_STM32/kicad/ACROSS_V3.kicad_pcb'
TYPES = ('clearance', 'tracks_crossing', 'shorting_items', 'hole_clearance', 'track_width')
d = json.load(open(os.path.join(tempfile.gettempdir(), 'drc_sum.json'), encoding='utf8'))
b = pcbnew.LoadBoard(PCB)
by = {t.m_Uuid.AsString(): t for t in b.GetTracks()}
kill = set()
for v in d['violations']:
    if v['type'] not in TYPES:
        continue
    ts = [by[x['uuid']] for x in v['items'] if x['uuid'] in by and by[x['uuid']].Type() == pcbnew.PCB_TRACE_T and not by[x['uuid']].IsLocked()]
    if v['type'] == 'track_width':
        continue  # 細い線は fix_narrow.py で
    if ts:
        kill.add(min(ts, key=lambda t: t.GetLength()).m_Uuid.AsString())
for u in kill:
    b.Remove(by[u])
pcbnew.ZONE_FILLER(b).Fill(b.Zones())
b.Save(PCB)
print('消した線', len(kill))
