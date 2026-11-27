#!/bin/bash
# usage: render_clip.sh name layers x0 y0 x1 y1 [dpi]  (mm, board coords; board origin at 0,0) -> tools/pcb/name.png
K="C:/Program Files/KiCad/10.0/bin/kicad-cli.exe"
"$K" pcb export svg --layers "$2" --mode-single --page-size-mode 2 --exclude-drawing-sheet -o tools/pcb/$1.svg ACROSS_V3.kicad_pcb >/dev/null 2>&1
python - "$1" "$3" "$4" "$5" "$6" "${7:-300}" <<'P' 2>/dev/null
import sys
sys.path.insert(0,'C:/Users/K.Okada/AppData/Local/Temp/pymu')
import fitz
n,x0,y0,x1,y1,dpi=sys.argv[1],*map(float,sys.argv[2:6]),int(sys.argv[6])
d=fitz.open('tools/pcb/'+n+'.svg'); pg=d[0]
r=pg.rect; s=r.width/160.0   # board area only: page width = board width
clip=fitz.Rect(x0*s,y0*s,x1*s,y1*s)
pg.get_pixmap(dpi=dpi,clip=clip).save('tools/pcb/'+n+'.png')
P
rm -f tools/pcb/$1.svg
