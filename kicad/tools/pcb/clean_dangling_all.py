# DRC の track_dangling / via_dangling を、ロックしたものも含めて消す (2026-11-22、仕上げ用)
#   部品を動かしたあとに残った古い fanout の線や、1 つの層にしかつながっていないビア (役に立っていない) を片づける。
#   先に drc_sum.py でその基板の DRC を回しておく。消したあとは未配線が増えていないか必ず確かめる。
# usage: python clean_dangling_all.py [pcb]
import sys, json, os, tempfile
import pcbnew

PCB = sys.argv[1] if len(sys.argv) > 1 else 'C:/MyWorks/ACROSS_V3_STM32/kicad/ACROSS_V3.kicad_pcb'
d = json.load(open(os.path.join(tempfile.gettempdir(), 'drc_sum.json'), encoding='utf8'))
bad = {x['uuid'] for v in d['violations'] if v['type'] in ('track_dangling', 'via_dangling') for x in v['items']}
b = pcbnew.LoadBoard(PCB)
kill = [t for t in b.GetTracks() if t.m_Uuid.AsString() in bad]
for t in kill:
    b.Remove(t)
pcbnew.ZONE_FILLER(b).Fill(b.Zones())
b.Save(PCB)
print('消した', len(kill))
