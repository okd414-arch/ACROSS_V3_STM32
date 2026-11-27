# Freerouting の SES を基板に取り込んで、ゾーンを塗り直して保存する (2026-11-21)
# usage: python import_ses.py in.ses [in.kicad_pcb] [out.kicad_pcb]
import sys
import pcbnew

PCB = 'C:/MyWorks/ACROSS_V3_STM32/kicad/ACROSS_V3.kicad_pcb'
ses = sys.argv[1]
src = sys.argv[2] if len(sys.argv) > 2 else PCB
dst = sys.argv[3] if len(sys.argv) > 3 else src
b = pcbnew.LoadBoard(src)
n0 = len(b.GetTracks())
try:
    ok = pcbnew.ImportSpecctraSES(b, ses)
except TypeError:
    ok = pcbnew.ImportSpecctraSES(ses)
print('import', ok, 'tracks', n0, '->', len(b.GetTracks()))
pcbnew.ZONE_FILLER(b).Fill(b.Zones())
b.Save(dst)
print('saved', dst)
