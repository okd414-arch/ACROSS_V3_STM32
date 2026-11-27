#!/bin/bash
# usage: render.sh name layers  -> tools/pcb/name.png
K="C:/Program Files/KiCad/10.0/bin/kicad-cli.exe"
"$K" pcb export svg --layers "$2" --mode-single --page-size-mode 2 --exclude-drawing-sheet $3 -o tools/pcb/$1.svg ACROSS_V3.kicad_pcb >/dev/null 2>&1
python - "$1" "$4" <<'P' 2>/dev/null
import sys
sys.path.insert(0,'C:/Users/K.Okada/AppData/Local/Temp/pymu')
import fitz
n=sys.argv[1]; dpi=int(sys.argv[2]) if len(sys.argv)>2 and sys.argv[2] else 150
d=fitz.open('tools/pcb/'+n+'.svg'); d[0].get_pixmap(dpi=dpi).save('tools/pcb/'+n+'.png')
P
rm -f tools/pcb/$1.svg
