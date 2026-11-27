import re, sys, glob
sys.path.insert(0, 'C:/Users/K.Okada/AppData/Local/Temp/w')
from compress_forms import forms

CR = chr(13); LF = chr(10)
ASSIGN = json_assign = {}
import json
ASSIGN = json.load(open(sys.argv[2], encoding='utf8'))
apply = sys.argv[1] == '1'
done = set()
for f in sorted(glob.glob('[0-9]*.kicad_sch')):
    raw = open(f, encoding='utf8', newline='').read()
    crlf = CR + LF in raw
    raw = raw.replace(CR + LF, LF)
    reps = []
    for a, b in forms(raw):
        blk = raw[a:b]
        if not blk.startswith('(symbol' + LF):
            continue
        m = re.search(r'"Reference" "([^"]*)"', blk)
        if not m or m.group(1) not in ASSIGN:
            continue
        ref = m.group(1)
        fm = re.search(r'\(property "Footprint" "([^"]*)"', blk)
        nb = blk.replace(fm.group(0), '(property "Footprint" "%s"' % ASSIGN[ref], 1)
        reps.append((a, b, nb)); done.add(ref)
        print(f[:2], ref, repr(fm.group(1)), '->', ASSIGN[ref])
    if apply and reps:
        for a, b, nb in sorted(reps, reverse=True):
            raw = raw[:a] + nb + raw[b:]
        open(f, 'w', encoding='utf8', newline='').write(raw.replace(LF, CR + LF) if crlf else raw)
print('missing', [r for r in ASSIGN if r not in done])
