import sys, re, os, math, collections
import xml.etree.ElementTree as ET
import pcbnew
from pcbnew import VECTOR2I, FromMM, ToMM

KICAD = 'C:/MyWorks/ACROSS_V3_STM32/kicad'
OUT = KICAD + '/ACROSS_V3.kicad_pcb'
XML = 'C:/Users/K.Okada/AppData/Local/Temp/w/final.xml'
W, H = 190.0, 110.0
EDGE = 3.0   # keep parts this far from the edge (non-edge parts)

fpt = open(os.path.expandvars('%APPDATA%/kicad/10.0/fp-lib-table'), encoding='utf8').read()
libs = {}
env = {'KICAD9_FOOTPRINT_DIR': 'C:/Program Files/KiCad/10.0/share/kicad/footprints', 'MY_KICAD_FOLDER': 'C:/OneDrive_link/KiCAD', 'KIPRJMOD': KICAD}
for m in re.finditer(r'\(lib \(name "([^"]*)"\)\(type "[^"]*"\)\(uri "([^"]*)"', fpt):
    libs[m.group(1)] = re.sub(r'\$\{(\w+)\}', lambda mm: env.get(mm.group(1), mm.group(0)), m.group(2))
libs['ACROSS_V3'] = KICAD + '/ACROSS_V3.pretty'

# ---------------- seeds (explicit targets) ----------------
# ref: (x, y, facing)  facing = None / 'left' / 'right' / 'up' / 'down' (direction the connector opening points)
SEEDS = collections.OrderedDict([
    # holes
    ('H101', (4, 4, None)), ('H102', (95, 4, None)), ('H103', (186, 4, None)),
    ('H104', (4, 106, None)), ('H105', (95, 106, None)), ('H106', (186, 106, None)),
    # power input (left)
    ('J101', (6, 55, 'left')), ('F101', (19, 55, None)), ('D101', (19, 66, None)), ('Q101', (27, 46, None)),
    ('U101', (36, 38, None)), ('C103', (22, 24, None)), ('U102', (24, 88, None)), ('L101', (40, 88, None)),
    ('D103', (38, 99, None)), ('U103', (46, 64, None)),
    # PMIC
    ('U201', (58, 58, None)), ('SW201', (62, 88, None)),
    # SoC
    ('U1', (90, 54, None)), ('SW301', (72, 80, None)), ('J301', (104, 86, None)), ('JP301', (70, 22, None)),
    ('D301', (116, 6, None)), ('D302', (120, 6, None)), ('D303', (124, 6, None)), ('D304', (128, 6, None)),
    # memory
    ('U501', (118, 38, None)), ('U502', (118, 72, None)), ('U601', (104, 20, None)),
    # LCD / ethernet / USB / SD
    ('J702', (60, 8, 'up')), ('J701', (62, 99, 'down')), ('U701', (62, 76, None)),
    ('J602', (83, 100, 'down')), ('J603', (99, 103, 'down')), ('J604', (112, 103, 'down')), ('J601', (128, 101, 'down')),
    # domain A (top right)
    ('J801', (185, 20, 'right')), ('J802', (185, 42, 'right')), ('U801', (142, 12, None)), ('U806', (158, 30, None)),
    ('U807', (172, 10, None)), ('U804', (148, 44, None)), ('U808', (166, 46, None)), ('U805', (160, 10, None)),
    ('U809', (172, 24, None)), ('SW801', (176, 52, None)), ('U802', (142, 26, None)), ('U803', (142, 38, None)),
    # domains B/C/D (bottom right)
    ('U904', (142, 60, None)), ('U905', (158, 60, None)), ('U901', (178, 62, None)), ('U902', (148, 68, None)),
    ('U903', (164, 68, None)), ('J901', (148, 86, None)), ('J902', (178.48, 86, None)),
    ('J903', (166, 103, 'down')), ('J904', (184, 103, 'down')),
    ('U906', (138, 78, None)), ('U907', (138, 89, None)), ('U908', (138, 100, None)), ('U909', (152, 102, None)),
    ('U910', (183, 72, None)), ('U911', (172, 74, None)), ('U912', (184, 82, None)),
])
HOLES_MM = [(4, 4), (95, 4), (186, 4), (4, 106), (95, 106), (186, 106)]

# ---------------- read netlist ----------------
root = ET.parse(XML).getroot()
comps = {}
for c in root.find('components'):
    ref = c.get('ref')
    sp = c.find('sheetpath')
    comps[ref] = dict(
        value=c.find('value').text or '', fp=c.find('footprint').text,
        sheet=re.match(r'/(\d\d)', sp.get('names')).group(1) if re.match(r'/(\d\d)', sp.get('names')) else '00',
        path=sp.get('tstamps') + c.find('tstamps').text,
        lcsc=(c.find('fields/field[@name="LCSC"]').text if c.find('fields/field[@name="LCSC"]') is not None else None))
nets = collections.OrderedDict()
for n in root.find('nets'):
    nets[n.get('name')] = [(nd.get('ref'), nd.get('pin')) for nd in n]

# ---------------- board ----------------
board = pcbnew.NewBoard(OUT)
board.SetCopperLayerCount(8)
ds = board.GetDesignSettings()

def mm(v):
    return int(round(v * 1e6))

# outline
for (x1, y1, x2, y2) in [(0, 0, W, 0), (W, 0, W, H), (W, H, 0, H), (0, H, 0, 0)]:
    seg = pcbnew.PCB_SHAPE(board)
    seg.SetShape(pcbnew.SHAPE_T_SEGMENT)
    seg.SetLayer(pcbnew.Edge_Cuts)
    seg.SetStart(VECTOR2I(mm(x1), mm(y1))); seg.SetEnd(VECTOR2I(mm(x2), mm(y2)))
    seg.SetWidth(mm(0.1))
    board.Add(seg)

netitems = {}
for name in nets:
    ni = pcbnew.NETINFO_ITEM(board, name)
    board.Add(ni)
    netitems[name] = ni
padnet = {}
for name, nodes in nets.items():
    for ref, pin in nodes:
        padnet[(ref, pin)] = name

fps = {}
for ref, c in comps.items():
    lib, name = c['fp'].split(':', 1)
    fp = pcbnew.FootprintLoad(libs[lib], name)
    fp.SetFPID(pcbnew.LIB_ID(lib, name))
    fp.SetReference(ref)
    fp.SetValue(c['value'])
    fp.SetPath(pcbnew.KIID_PATH(c['path']))
    for pad in fp.Pads():
        nn = padnet.get((ref, pad.GetNumber()))
        if nn:
            pad.SetNet(netitems[nn])
    board.Add(fp)
    fps[ref] = fp

# ---------------- placement ----------------
occ = {'F': [], 'B': []}
CL = 0.25

def bbox_mm(fp):
    bb = fp.GetBoundingBox(False)
    return (ToMM(bb.GetX()), ToMM(bb.GetY()), ToMM(bb.GetX() + bb.GetWidth()), ToMM(bb.GetY() + bb.GetHeight()))

def is_tht(fp):
    return bool(fp.GetAttributes() & pcbnew.FP_THROUGH_HOLE)

def set_center(fp, cx, cy):
    b = bbox_mm(fp)
    bx, by = (b[0] + b[2]) / 2, (b[1] + b[3]) / 2
    p = fp.GetPosition()
    fp.SetPosition(VECTOR2I(p.x + mm(cx - bx), p.y + mm(cy - by)))

def rect_free(r, sides, edge_ok):
    x0, y0, x1, y1 = r
    lim = 0.5 if edge_ok else EDGE
    if x0 < lim or y0 < lim or x1 > W - lim or y1 > H - lim:
        return False
    for hx, hy in HOLES_MM:
        if x1 > hx - 4 and x0 < hx + 4 and y1 > hy - 4 and y0 < hy + 4:
            return False
    for s in sides:
        for o in occ[s]:
            if x1 + CL > o[0] and x0 - CL < o[2] and y1 + CL > o[1] and y0 - CL < o[3]:
                return False
    return True

offsets = sorted(((dx * 0.5, dy * 0.5) for dx in range(-160, 161) for dy in range(-160, 161)), key=lambda t: t[0] ** 2 + t[1] ** 2)

def face(fp, facing):
    want = {'left': (-1, 0), 'right': (1, 0), 'up': (0, -1), 'down': (0, 1)}[facing]
    best = None
    for ang in (0, 90, 180, 270):
        fp.SetOrientationDegrees(ang)
        b = bbox_mm(fp)
        bc = ((b[0] + b[2]) / 2, (b[1] + b[3]) / 2)
        pts = [(ToMM(p.GetPosition().x), ToMM(p.GetPosition().y)) for p in fp.Pads() if p.GetNumber() not in ('SH', 'MP', '')]
        if not pts:
            continue
        pc = (sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts))
        v = (bc[0] - pc[0], bc[1] - pc[1])
        d = v[0] * want[0] + v[1] * want[1]
        if best is None or d > best[0]:
            best = (d, ang)
    fp.SetOrientationDegrees(best[1])

placed = {}
def place(ref, tx, ty, side='F', facing=None, edge_ok=False, maxr=80):
    fp = fps[ref]
    if side == 'B':
        fp.Flip(fp.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
    if facing:
        face(fp, facing)
    tht = is_tht(fp)
    sides = ['F', 'B'] if tht else [side]
    for dx, dy in offsets:
        if dx * dx + dy * dy > maxr * maxr:
            break
        set_center(fp, tx + dx, ty + dy)
        b = bbox_mm(fp)
        if rect_free(b, sides, edge_ok):
            for s in sides:
                occ[s].append(b)
            placed[ref] = ((b[0] + b[2]) / 2, (b[1] + b[3]) / 2)
            return True
    print('FAILED to place', ref)
    set_center(fp, tx, ty)
    return False

# connectivity helper
adj = collections.defaultdict(lambda: collections.defaultdict(float))
for name, nodes in nets.items():
    refs = sorted(set(r for r, p in nodes))
    if len(refs) < 2 or len(refs) > 14:
        continue
    wgt = 1.0 / (len(refs) - 1)
    for a in refs:
        for b in refs:
            if a != b:
                adj[a][b] += wgt

# 1. seeds
for ref, (x, y, facing) in SEEDS.items():
    if ref in fps:
        place(ref, x, y, 'F', facing, edge_ok=(facing is not None or ref.startswith('H')))
    else:
        print('seed not in netlist', ref)

# keepouts around BGAs (fanout room): top margin, bottom via field
for kref, mF, mB in (('U1', 2.5, 0.8), ('U501', 1.5, 0.8), ('U502', 1.5, 0.8), ('U601', 1.0, 0.8)):
    kb = bbox_mm(fps[kref])
    occ['F'].append((kb[0] - mF, kb[1] - mF, kb[2] + mF, kb[3] + mF))
    occ['B'].append((kb[0] - mB, kb[1] - mB, kb[2] + mB, kb[3] + mB))
netcount = collections.Counter(n for (r, p), n in padnet.items())
def is_pwr(n):
    return n.startswith('GND') or n.startswith('+') or n.startswith('VDD') or n.startswith('VTT') or n.startswith('VREF') or netcount[n] >= 6
nets_of = collections.defaultdict(set)
for (r, p), n in padnet.items():
    nets_of[r].add(n)

# 2. the rest: iterative, pick the unplaced part with strongest link to placed parts
BOTTOM_ANCHORS = {'U1', 'U501', 'U502'}
rest = [r for r in fps if r not in placed]
sheet_main = {}
for r, c in comps.items():
    if r in placed:
        sheet_main.setdefault(c['sheet'], []).append(r)
while rest:
    best = None
    for r in rest:
        score = sum(w for o, w in adj[r].items() if o in placed)
        if best is None or score > best[0]:
            best = (score, r)
    score, r = best
    rest.remove(r)
    links = [(o, w) for o, w in adj[r].items() if o in placed]
    if links:
        tw = sum(w for o, w in links)
        tx = sum(placed[o][0] * w for o, w in links) / tw
        ty = sum(placed[o][1] * w for o, w in links) / tw
        anchor = max(links, key=lambda t: t[1])[0]
    else:
        same = [o for o in sheet_main.get(comps[r]['sheet'], []) if o in placed]
        if same:
            tx = sum(placed[o][0] for o in same) / len(same)
            ty = sum(placed[o][1] for o in same) / len(same)
        else:
            tx, ty = W / 2, H / 2
        anchor = None
    side = 'F'
    if re.match(r'C\d', r) and comps[r]['sheet'] == '03' and nets_of[r] and all(is_pwr(n) for n in nets_of[r]):
        side = 'B'
        tx, ty = placed['U1']
    place(r, tx, ty, side)
    sheet_main.setdefault(comps[r]['sheet'], []).append(r)

# snap all footprints to the 0.2mm grid (routing grid)
for fp in fps.values():
    p = fp.GetPosition()
    fp.SetPosition(VECTOR2I(int(round(p.x / 200000.0)) * 200000, int(round(p.y / 200000.0)) * 200000))

# ---------------- save ----------------
board.Save(OUT)
print('saved', OUT, 'parts', len(fps))
# summary
unplaced = [r for r in fps if r not in placed]
print('unplaced', unplaced)
