# 基板を Specctra DSN に書き出す (2026-11-21)
# usage: python export_dsn.py [pcb] out.dsn
import sys
import pcbnew

PCB = 'C:/MyWorks/ACROSS_V3_STM32/kicad/ACROSS_V3.kicad_pcb'
pcb, out = (sys.argv[1], sys.argv[2]) if len(sys.argv) > 2 else (PCB, sys.argv[1])
b = pcbnew.LoadBoard(pcb)
ok = pcbnew.ExportSpecctraDSN(b, out)
print('export', ok, out)
