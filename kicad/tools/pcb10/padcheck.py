import re, sys, glob, os
sys.path.insert(0, 'C:/Users/K.Okada/AppData/Local/Temp/w')
import pcbnew
from sx import parse, q, find

kicad = 'C:/MyWorks/ACROSS_V3_STM32/kicad'
fpt = open(os.path.expandvars('%APPDATA%/kicad/10.0/fp-lib-table'), encoding='utf8').read()
libs = {}
env = {'KICAD9_FOOTPRINT_DIR': 'C:/Program Files/KiCad/10.0/share/kicad/footprints', 'MY_KICAD_FOLDER': 'C:/OneDrive_link/KiCAD', 'KIPRJMOD': kicad}
for m in re.finditer(r'\(lib \(name "([^"]*)"\)\(type "[^"]*"\)\(uri "([^"]*)"', fpt):
    libs[m.group(1)] = re.sub(r'\$\{(\w+)\}', lambda mm: env.get(mm.group(1), mm.group(0)), m.group(2))
libs['ACROSS_V3'] = kicad + '/ACROSS_V3.pretty'

cache = {}
def pads_of(fp):
    if fp in cache:
        return cache[fp]
    lib, name = fp.split(':', 1)
    f = pcbnew.FootprintLoad(libs[lib], name)
    r = None if f is None else set(p.GetNumber() for p in f.Pads())
    cache[fp] = r
    return r

problems = []
checked = 0
for sf in sorted(glob.glob(kicad + '/[0-9]*.kicad_sch')):
    s = open(sf, encoding='utf8').read()
    t = parse(s)
    symlib = {}
    for ls in find(t, 'lib_symbols'):
        for sy in find(ls, 'symbol'):
            pins = set()
            def walk(l):
                for x in l:
                    if isinstance(x, list):
                        if x and x[0] == 'pin':
                            pins.add(q(find(x, 'number')[0][1]))
                        else:
                            walk(x)
            walk(sy)
            symlib[q(sy[1])] = pins
    seen = set()
    for x in t:
        if isinstance(x, list) and x and x[0] == 'symbol':
            lid = q(find(x, 'lib_id')[0][1])
            props = {q(p[1]): q(p[2]) for p in find(x, 'property')}
            ref = props.get('Reference', '')
            if ref.startswith('#'):
                continue
            fp = props.get('Footprint', '')
            if not fp:
                problems.append((os.path.basename(sf)[:2], ref, 'NO FOOTPRINT'))
                continue
            if (ref, fp) in seen:
                continue
            seen.add((ref, fp))
            pads = pads_of(fp)
            checked += 1
            if pads is None:
                problems.append((os.path.basename(sf)[:2], ref, 'LOAD FAIL ' + fp)); continue
            pins = symlib.get(lid, set())
            miss = sorted(p for p in pins if p not in pads)
            if miss:
                problems.append((os.path.basename(sf)[:2], ref, lid, fp, 'pins not in pads: ' + ','.join(miss[:8])))
print('checked', checked)
for p in problems:
    print(p)
