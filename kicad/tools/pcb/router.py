# -*- coding: utf-8 -*-
"""Grid A* router for ACROSS_V3.kicad_pcb (run with KiCad's python.exe).

Stages: zones (GND planes, power zones) -> BGA fanout -> plane-net vias -> route nets -> save.
Grid 0.2 mm, 8 copper layers. Signal track 0.1 mm, power track 0.25 mm, via 0.45/0.2 (eMMC via-in-pad 0.3/0.15).
"""
import sys, math, heapq, time, re, collections, json
import numpy as np
import pcbnew
from pcbnew import VECTOR2I, ToMM

PCB = 'ACROSS_V3.kicad_pcb'
G = 0.2
W, H = 190.0, 110.0
NX, NY = int(round(W / G)) + 1, int(round(H / G)) + 1
NL = 8
F, IN1, IN2, IN3, IN4, IN5, IN6, B = range(8)
KLAYER = [pcbnew.F_Cu, pcbnew.In1_Cu, pcbnew.In2_Cu, pcbnew.In3_Cu, pcbnew.In4_Cu, pcbnew.In5_Cu, pcbnew.In6_Cu, pcbnew.B_Cu]
SIG_LAYERS = [F, IN2, IN5, B]
PWR_LAYERS = [IN3, IN4]
ROUTE_LAYERS = [F, IN2, IN3, IN4, IN5, B]
CL = 0.1
EXTRA = [0.05, 0.125, 0.225]     # class 0: 0.1 track, class 1: 0.25 track, class 2: via r
VIA_D, VIA_DR = 0.45, 0.2
SVIA_D, SVIA_DR = 0.3, 0.15      # small via (eMMC via-in-pad)
EDGE_CL = 0.3
PLANE_NETS = {'GND', 'GND_A', 'GND_B', 'GND_D'}
LOG = []

def log(*a):
    s = ' '.join(str(x) for x in a)
    LOG.append(s)
    print(s, flush=True)

def mm(v):
    return int(round(v * 1e6))

board = pcbnew.LoadBoard(PCB)
# clear previous routing
for t in list(board.GetTracks()):
    board.Remove(t)
for z in list(board.Zones()):
    board.Remove(z)

netinfo = board.GetNetInfo()
nets_by_name = {}
for n in netinfo.NetsByName().values() if hasattr(netinfo, 'NetsByName') else []:
    pass
netid = {}
netobj = {}
for fp in board.GetFootprints():
    for p in fp.Pads():
        nm = p.GetNetname()
        if nm and nm not in netid:
            netid[nm] = len(netid) + 1
            netobj[nm] = p.GetNet()
idname = {v: k for k, v in netid.items()}

def routable(nm):
    return nm and not nm.startswith('unconnected-')

# ---------------------------------------------------------------- occupancy
occ = np.zeros((3, NL, NY, NX), dtype=np.int32)
XS = np.arange(NX) * G
YS = np.arange(NY) * G

def _apply(k, layers, y0, y1, x0, x1, mask, nid):
    for l in layers:
        sub = occ[k, l, y0:y1, x0:x1]
        m0 = mask & (sub == 0)
        mc = mask & (sub != 0) & (sub != nid)
        sub[m0] = nid
        sub[mc] = -1

def _win(xmin, ymin, xmax, ymax):
    x0 = max(0, int(math.floor(xmin / G))); x1 = min(NX, int(math.ceil(xmax / G)) + 1)
    y0 = max(0, int(math.floor(ymin / G))); y1 = min(NY, int(math.ceil(ymax / G)) + 1)
    return x0, x1, y0, y1

def mark_dist(nid, layers, bbox, distfn, classes=(0, 1, 2), hard=False):
    """distfn(X,Y)-> distance from object edge (0 inside). bbox in mm (object extents)."""
    R = CL + max(EXTRA) + 0.01
    x0, x1, y0, y1 = _win(bbox[0] - R, bbox[1] - R, bbox[2] + R, bbox[3] + R)
    if x0 >= x1 or y0 >= y1:
        return
    X, Y = np.meshgrid(XS[x0:x1], YS[y0:y1])
    d = distfn(X, Y)
    for k in classes:
        mask = d < CL + EXTRA[k] - 1e-6
        _apply(k, layers, y0, y1, x0, x1, mask, -1 if hard else nid)

def seg_dist(x1, y1, x2, y2, hw):
    dx, dy = x2 - x1, y2 - y1
    L2 = dx * dx + dy * dy
    def f(X, Y):
        if L2 == 0:
            t = 0
        else:
            t = np.clip(((X - x1) * dx + (Y - y1) * dy) / L2, 0, 1)
        px, py = x1 + t * dx, y1 + t * dy
        return np.maximum(np.hypot(X - px, Y - py) - hw, 0)
    return f

def circ_dist(cx, cy, r):
    return lambda X, Y: np.maximum(np.hypot(X - cx, Y - cy) - r, 0)

def rect_dist(cx, cy, w, h, ang):
    ca, sa = math.cos(math.radians(ang)), math.sin(math.radians(ang))
    def f(X, Y):
        u = (X - cx) * ca - (Y - cy) * sa
        v = (X - cx) * sa + (Y - cy) * ca
        du = np.maximum(np.abs(u) - w / 2, 0)
        dv = np.maximum(np.abs(v) - h / 2, 0)
        return np.hypot(du, dv)
    return f

def mark_seg(nid, layers, x1, y1, x2, y2, hw, classes=(0, 1, 2)):
    mark_dist(nid, layers, (min(x1, x2) - hw, min(y1, y2) - hw, max(x1, x2) + hw, max(y1, y2) + hw), seg_dist(x1, y1, x2, y2, hw), classes)

def mark_via(nid, x, y, d=VIA_D):
    mark_dist(nid, range(NL), (x - d / 2, y - d / 2, x + d / 2, y + d / 2), circ_dist(x, y, d / 2))

# edges
for k in range(3):
    m = int(math.ceil((EDGE_CL + EXTRA[k]) / G))
    occ[k, :, :m, :] = -1; occ[k, :, -m:, :] = -1; occ[k, :, :, :m] = -1; occ[k, :, :, -m:] = -1

# pads
padinfo = []   # (fp, pad, nm, x, y, layers, shape)
def pad_layers(p):
    if p.GetAttribute() in (pcbnew.PAD_ATTRIB_PTH, pcbnew.PAD_ATTRIB_NPTH):
        return list(range(NL))
    return [F] if p.IsOnLayer(pcbnew.F_Cu) else [B]

def pad_distfn(p):
    pos = p.GetPosition(); cx, cy = ToMM(pos.x), ToMM(pos.y)
    sz = p.GetSize(pcbnew.F_Cu) if hasattr(p, 'GetSize') else p.GetSize()
    w, h = ToMM(sz.x), ToMM(sz.y)
    ang = p.GetOrientation().AsDegrees()
    shape = p.GetShape(pcbnew.F_Cu) if p.GetAttribute() != pcbnew.PAD_ATTRIB_NPTH else pcbnew.PAD_SHAPE_CIRCLE
    if shape == pcbnew.PAD_SHAPE_CIRCLE:
        r = w / 2
        if p.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH:
            r = max(r, ToMM(p.GetDrillSize().x) / 2)
        return cx, cy, (cx - r, cy - r, cx + r, cy + r), circ_dist(cx, cy, r)
    e = max(w, h) / 2 + 0.01
    return cx, cy, (cx - e, cy - e, cx + e, cy + e), rect_dist(cx, cy, w, h, -ang)

BGA_REFS = {'U1', 'U501', 'U502'}
EMMC = 'U601'
t0 = time.time()
for fp in board.GetFootprints():
    for p in fp.Pads():
        nm = p.GetNetname()
        nid = netid.get(nm, 0) if routable(nm) else 0
        layers = pad_layers(p)
        cx, cy, bb, fn = pad_distfn(p)
        if nid == 0:
            mark_dist(0, layers, bb, fn, hard=True)
        else:
            mark_dist(nid, layers, bb, fn)
            # no vias inside SMD pads (except BGA dogbone/eMMC VIP handled separately)
            if p.GetAttribute() == pcbnew.PAD_ATTRIB_SMD and fp.GetReference() not in BGA_REFS and fp.GetReference() != EMMC:
                mark_dist(nid, range(NL), bb, fn, classes=(2,), hard=True)
        padinfo.append((fp, p, nm, cx, cy, layers, fn, bb))
log('pads marked', len(padinfo), '%.1fs' % (time.time() - t0))

# ---------------------------------------------------------------- output helpers
def add_track(nm, layer, x1, y1, x2, y2, w):
    if abs(x1 - x2) < 1e-6 and abs(y1 - y2) < 1e-6:
        return
    t = pcbnew.PCB_TRACK(board)
    t.SetStart(VECTOR2I(mm(x1), mm(y1))); t.SetEnd(VECTOR2I(mm(x2), mm(y2)))
    t.SetWidth(mm(w)); t.SetLayer(KLAYER[layer]); t.SetNet(netobj[nm])
    board.Add(t)
    mark_seg(netid[nm], [layer], x1, y1, x2, y2, w / 2)

def add_via(nm, x, y, d=VIA_D, dr=VIA_DR):
    v = pcbnew.PCB_VIA(board)
    v.SetPosition(VECTOR2I(mm(x), mm(y)))
    v.SetWidth(mm(d)); v.SetDrill(mm(dr)); v.SetNet(netobj[nm])
    v.SetViaType(pcbnew.VIATYPE_THROUGH)
    v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
    board.Add(v)
    mark_via(netid[nm], x, y, d)

def gx(x):
    return int(round(x / G))

def cell_ok(k, l, iy, ix, nid):
    if ix < 0 or iy < 0 or ix >= NX or iy >= NY:
        return False
    v = occ[k, l, iy, ix]
    return v == 0 or v == nid

def via_ok(iy, ix, nid):
    if ix < 0 or iy < 0 or ix >= NX or iy >= NY:
        return False
    col = occ[2, :, iy, ix]
    return bool(np.all((col == 0) | (col == nid)))

# ---------------------------------------------------------------- zones
def make_zone(nm, layer, poly, prio, clearance=None, minw=0.15):
    z = pcbnew.ZONE(board)
    z.SetLayer(KLAYER[layer]); z.SetNet(netobj[nm])
    ol = z.Outline(); ol.NewOutline()
    for x, y in poly:
        ol.Append(mm(x), mm(y))
    z.SetAssignedPriority(prio)
    if clearance is not None:
        z.SetLocalClearance(mm(clearance))
    z.SetMinThickness(mm(minw))
    z.SetPadConnection(pcbnew.ZONE_CONNECTION_THERMAL)
    z.SetThermalReliefGap(mm(0.25)); z.SetThermalReliefSpokeWidth(mm(0.3))
    z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
    board.Add(z)
    return z

def rect(x0, y0, x1, y1):
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]

# domain regions from parts that have pads on a domain GND (and not on GND)
dom_bb = {}
for dn in ('GND_A', 'GND_B', 'GND_D'):
    bbs = []
    for fp in board.GetFootprints():
        ns = set(p.GetNetname() for p in fp.Pads())
        if dn in ns and 'GND' not in ns:
            bb = fp.GetBoundingBox(False)
            bbs.append((ToMM(bb.GetX()), ToMM(bb.GetY()), ToMM(bb.GetRight()), ToMM(bb.GetBottom())))
    if bbs:
        dom_bb[dn] = (min(b[0] for b in bbs) - 1, min(b[1] for b in bbs) - 1, max(b[2] for b in bbs) + 1, max(b[3] for b in bbs) + 1)
log('domain boxes', {k: tuple(round(v, 1) for v in b) for k, b in dom_bb.items()})
for layer in (IN1, IN6):
    make_zone('GND', layer, rect(0.3, 0.3, W - 0.3, H - 0.3), 0, minw=0.2)
    for dn, bb in dom_bb.items():
        make_zone(dn, layer, rect(max(bb[0], 0.3), max(bb[1], 0.3), min(bb[2], W - 0.3), min(bb[3], H - 0.3)), 5, clearance=2.0, minw=0.2)

# power zones: rectangle around the net's BGA pads (+ margin) on a power layer
def pads_of(ref, nm):
    fp = [f for f in board.GetFootprints() if f.GetReference() == ref][0]
    return [(ToMM(p.GetPosition().x), ToMM(p.GetPosition().y)) for p in fp.Pads() if p.GetNetname() == nm]

ZONE_NETS = {}   # nm -> (layer, rect)
def power_zone(nm, layer, pts, margin, prio):
    x0 = min(p[0] for p in pts) - margin; x1 = max(p[0] for p in pts) + margin
    y0 = min(p[1] for p in pts) - margin; y1 = max(p[1] for p in pts) + margin
    make_zone(nm, layer, rect(x0, y0, x1, y1), prio, minw=0.15)
    ZONE_NETS[nm] = (layer, (x0, y0, x1, y1))
    nid = netid[nm]
    # block other nets' tracks inside the zone rect on that layer (vias may pass)
    xa, xb, ya, yb = _win(x0 - 0.3, y0 - 0.3, x1 + 0.3, y1 + 0.3)
    for k in (0, 1):
        sub = occ[k, layer, ya:yb, xa:xb]
        sub[(sub != nid)] = -1
        sub[(sub == 0)] = nid

power_zone('VDD_CORE', IN3, pads_of('U1', 'VDD_CORE'), 0.6, 3)
power_zone('VDD_DDR', IN4, pads_of('U1', 'VDD_DDR') + pads_of('U501', 'VDD_DDR') + pads_of('U502', 'VDD_DDR'), 0.6, 3)
log('zones done')

# ---------------------------------------------------------------- BGA fanout
TERM = collections.defaultdict(list)   # nm -> list of terminals: dict(cells=set((l,iy,ix)), pt=(x,y), layers)
FANNED = set()   # (ref, padnum)

def fanout_bga(ref):
    fp = [f for f in board.GetFootprints() if f.GetReference() == ref][0]
    c = fp.GetPosition(); cx, cy = ToMM(c.x), ToMM(c.y)
    n = 0
    for p in fp.Pads():
        nm = p.GetNetname()
        if not routable(nm):
            continue
        px, py = ToMM(p.GetPosition().x), ToMM(p.GetPosition().y)
        sx = 1 if px >= cx else -1; sy = 1 if py >= cy else -1
        vx, vy = px + 0.4 * sx, py + 0.4 * sy
        ok = via_ok(gx(vy), gx(vx), netid[nm])
        if not ok:
            for (ax, ay) in ((-sx, sy), (sx, -sy), (-sx, -sy)):
                vx2, vy2 = px + 0.4 * ax, py + 0.4 * ay
                if via_ok(gx(vy2), gx(vx2), netid[nm]):
                    vx, vy, ok = vx2, vy2, True
                    break
        if not ok:
            log('  fanout fail', ref, p.GetNumber(), nm)
            continue
        w = 0.1
        add_track(nm, F, px, py, vx, vy, w)
        add_via(nm, vx, vy)
        FANNED.add((ref, p.GetNumber()))
        n += 1
        if nm not in PLANE_NETS and nm not in ZONE_NETS:
            TERM[nm].append(dict(pt=(vx, vy), layers=list(range(NL)), via=True, ref=ref))
    log('fanout', ref, n)

def fanout_emmc():
    fp = [f for f in board.GetFootprints() if f.GetReference() == EMMC][0]
    n = 0
    for p in fp.Pads():
        nm = p.GetNetname()
        if not routable(nm):
            continue
        px, py = ToMM(p.GetPosition().x), ToMM(p.GetPosition().y)
        v = pcbnew.PCB_VIA(board)
        v.SetPosition(VECTOR2I(mm(px), mm(py))); v.SetWidth(mm(SVIA_D)); v.SetDrill(mm(SVIA_DR))
        v.SetNet(netobj[nm]); v.SetViaType(pcbnew.VIATYPE_THROUGH); v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
        board.Add(v)
        mark_via(netid[nm], px, py, SVIA_D)
        FANNED.add((EMMC, p.GetNumber()))
        n += 1
        if nm not in PLANE_NETS:
            TERM[nm].append(dict(pt=(px, py), layers=list(range(NL)), via=True, ref=EMMC))
    log('fanout eMMC (via in pad)', n)

for r in ('U1', 'U501', 'U502'):
    fanout_bga(r)
fanout_emmc()

# ---------------------------------------------------------------- plane-net vias for other pads
def find_via_near(nm, layer, px, py, fn, rmax=2.0):
    nid = netid[nm]
    best = None
    R = int(rmax / G)
    ix0, iy0 = gx(px), gx(py)
    cands = []
    for dy in range(-R, R + 1):
        for dx in range(-R, R + 1):
            d = math.hypot(dx, dy) * G
            if d <= rmax:
                cands.append((d, ix0 + dx, iy0 + dy))
    cands.sort()
    for d, ix, iy in cands:
        if not via_ok(iy, ix, nid):
            continue
        vx, vy = ix * G, iy * G
        # straight stub pad-center -> via must be clear on the pad layer
        nst = max(2, int(math.hypot(vx - px, vy - py) / 0.05))
        good = True
        for i in range(nst + 1):
            t = i / nst
            qx, qy = px + (vx - px) * t, py + (vy - py) * t
            if not cell_ok(0, layer, gx(qy), gx(qx), nid):
                good = False
                break
        if good:
            return vx, vy
    return None

nplane = 0
for fp, p, nm, cx, cy, layers, fn, bb in padinfo:
    if (fp.GetReference(), p.GetNumber()) in FANNED or not routable(nm):
        continue
    if p.GetAttribute() == pcbnew.PAD_ATTRIB_PTH:
        if nm in PLANE_NETS:
            continue
        TERM[nm].append(dict(pt=(cx, cy), layers=list(range(NL)), via=False, ref=fp.GetReference()))
        continue
    if p.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH:
        continue
    L0 = layers[0]
    in_zone = nm in ZONE_NETS and (lambda r: r[0] <= cx <= r[2] and r[1] <= cy <= r[3])(ZONE_NETS[nm][1])
    if nm in PLANE_NETS or in_zone:
        r = find_via_near(nm, L0, cx, cy, fn)
        if r:
            w = 0.25 if fp.GetReference() not in BGA_REFS else 0.1
            add_track(nm, L0, cx, cy, r[0], r[1], 0.2)
            add_via(nm, r[0], r[1])
            nplane += 1
        else:
            log('  plane via fail', fp.GetReference(), p.GetNumber(), nm)
            TERM[nm].append(dict(pt=(cx, cy), layers=[L0], via=False, ref=fp.GetReference(), failplane=True))
        continue
    TERM[nm].append(dict(pt=(cx, cy), layers=[L0], via=False, ref=fp.GetReference()))
log('plane/zone vias', nplane, '%.1fs' % (time.time() - t0))

# ---------------------------------------------------------------- A* router
POWER = set(n for n in netid if n.startswith('+') or n.startswith('VDD') or n.startswith('VTT') or n.startswith('VREF') or 'VBUS' in n)
for n, ts in TERM.items():
    if len(ts) >= 6 and n not in PLANE_NETS:
        POWER.add(n)
VIA_COST = 8.0
DIRS = [(1, 0, 1.0), (-1, 0, 1.0), (0, 1, 1.0), (0, -1, 1.0), (1, 1, 1.414), (1, -1, 1.414), (-1, 1, 1.414), (-1, -1, 1.414)]

def layer_cost(nm, l):
    if nm in POWER:
        return 1.0 if l in (IN3, IN4) else 1.6
    return 1.0 if l in SIG_LAYERS else 2.5

def term_cells(t, nid, k):
    x, y = t['pt']
    cells = []
    ix, iy = gx(x), gx(y)
    for l in t['layers']:
        if l not in ROUTE_LAYERS:
            continue
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                if math.hypot(ix + dx - x / G, iy + dy - y / G) * G <= 0.21 and cell_ok(k, l, iy + dy, ix + dx, nid):
                    cells.append((l, iy + dy, ix + dx))
    return cells

def astar(nid, nm, k, sources, goals, goal_pt, bbox):
    gx0, gy0, gx1, gy1 = bbox
    goalset = set(goals)
    tx, ty = goal_pt
    openh = []
    gscore = {}
    came = {}
    for s in sources:
        gscore[s] = 0.0
        heapq.heappush(openh, (math.hypot(s[2] - tx, s[1] - ty), 0.0, s))
    closed = set()
    nexp = 0
    while openh:
        f, g, cur = heapq.heappop(openh)
        if cur in closed:
            continue
        closed.add(cur)
        if cur in goalset:
            path = [cur]
            while cur in came:
                cur = came[cur]
                path.append(cur)
            return path[::-1], nexp
        nexp += 1
        if nexp > 400000:
            return None, nexp
        l, y, x = cur
        lc = layer_cost(nm, l)
        for dx, dy, c in DIRS:
            nx_, ny_ = x + dx, y + dy
            if nx_ < gx0 or nx_ > gx1 or ny_ < gy0 or ny_ > gy1:
                continue
            v = occ[k, l, ny_, nx_]
            if v != 0 and v != nid:
                continue
            if dx and dy:
                v1 = occ[k, l, y, nx_]; v2 = occ[k, l, ny_, x]
                if (v1 != 0 and v1 != nid) or (v2 != 0 and v2 != nid):
                    continue
            nb = (l, ny_, nx_)
            ng = g + c * lc
            if ng < gscore.get(nb, 1e18):
                gscore[nb] = ng; came[nb] = cur
                heapq.heappush(openh, (ng + math.hypot(nx_ - tx, ny_ - ty), ng, nb))
        # via
        col = occ[2, :, y, x]
        if np.all((col == 0) | (col == nid)):
            for l2 in ROUTE_LAYERS:
                if l2 == l:
                    continue
                v = occ[k, l2, y, x]
                if v != 0 and v != nid:
                    continue
                nb = (l2, y, x)
                ng = g + VIA_COST
                if ng < gscore.get(nb, 1e18):
                    gscore[nb] = ng; came[nb] = cur
                    heapq.heappush(openh, (ng + math.hypot(x - tx, y - ty), ng, nb))
    return None, nexp

def emit_path(nm, path, width):
    """path: list of (l,iy,ix). Emit tracks (merged) and vias."""
    segs = []
    i = 0
    n = len(path)
    start = path[0]
    prev = path[0]
    pdir = None
    for j in range(1, n):
        cur = path[j]
        if cur[0] != prev[0]:
            # via between prev and cur (same x,y)
            if start != prev:
                segs.append(('t', start, prev))
            segs.append(('v', prev))
            start = cur; pdir = None
        else:
            d = (cur[1] - prev[1], cur[2] - prev[2])
            if pdir is not None and d != pdir:
                segs.append(('t', start, prev))
                start = prev
            pdir = d
        prev = cur
    if start != prev:
        segs.append(('t', start, prev))
    for s in segs:
        if s[0] == 't':
            a, b = s[1], s[2]
            add_track(nm, a[0], a[2] * G, a[1] * G, b[2] * G, b[1] * G, width)
        else:
            a = s[1]
            add_via(nm, a[2] * G, a[1] * G)

def route_net(nm):
    nid = netid[nm]
    terms = TERM[nm]
    if nm in ZONE_NETS:
        # the zone itself is part of the tree: a virtual terminal made of zone cells
        pass
    if len(terms) + (1 if nm in ZONE_NETS else 0) < 2:
        return True, 0
    width, k = (0.25, 1) if nm in POWER else (0.1, 0)
    tree_cells = set()
    tree_pts = []
    remaining = list(range(len(terms)))
    if nm in ZONE_NETS:
        layer, r = ZONE_NETS[nm]
        for iy in range(gx(r[1]) + 1, gx(r[3])):
            for ix in range(gx(r[0]) + 1, gx(r[2])):
                if occ[0, layer, iy, ix] == nid:
                    tree_cells.add((layer, iy, ix))
        tree_pts.append(((r[0] + r[2]) / 2, (r[1] + r[3]) / 2))
        # terminals already inside the zone (vias) are connected
        remaining = [i for i in remaining if not (terms[i].get('via') and r[0] <= terms[i]['pt'][0] <= r[2] and r[1] <= terms[i]['pt'][1] <= r[3])]
    else:
        # start from the terminal closest to the centroid
        cx = sum(t['pt'][0] for t in terms) / len(terms); cy = sum(t['pt'][1] for t in terms) / len(terms)
        i0 = min(remaining, key=lambda i: math.hypot(terms[i]['pt'][0] - cx, terms[i]['pt'][1] - cy))
        for kk in (k, 0):
            cs = term_cells(terms[i0], nid, kk)
            if cs:
                break
        tree_cells.update(cs)
        tree_pts.append(terms[i0]['pt'])
        remaining.remove(i0)
    fails = 0
    while remaining:
        # nearest terminal to the tree
        def dmin(i):
            p = terms[i]['pt']
            return min(math.hypot(p[0] - q[0], p[1] - q[1]) for q in tree_pts)
        i = min(remaining, key=dmin)
        remaining.remove(i)
        t = terms[i]
        ok = False
        for kk, wd in ((k, width), (0, 0.1)) if k == 1 else ((0, width),):
            src = term_cells(t, nid, kk)
            if not src:
                continue
            # goal: tree cells; heuristic toward nearest tree point
            q = min(tree_pts, key=lambda q: math.hypot(t['pt'][0] - q[0], t['pt'][1] - q[1]))
            mg = 6.0
            xs = [t['pt'][0], q[0]]; ys = [t['pt'][1], q[1]]
            for margin in (mg, 20.0):
                bb = (max(0, gx(min(xs) - margin)), max(0, gx(min(ys) - margin)), min(NX - 1, gx(max(xs) + margin)), min(NY - 1, gx(max(ys) + margin)))
                goals = [c for c in tree_cells if bb[0] <= c[2] <= bb[2] and bb[1] <= c[1] <= bb[3]]
                if not goals:
                    continue
                path, ne = astar(nid, nm, kk, src, goals, (q[0] / G, q[1] / G), bb)
                if path:
                    break
            if path:
                # stub from exact terminal point to first cell
                first = path[0]
                if not t.get('via'):
                    add_track(nm, first[0], t['pt'][0], t['pt'][1], first[2] * G, first[1] * G, min(wd, 0.2))
                else:
                    add_track(nm, first[0], t['pt'][0], t['pt'][1], first[2] * G, first[1] * G, 0.1)
                emit_path(nm, path, wd)
                tree_cells.update(path)
                tree_pts.append(t['pt'])
                for c in path[::3]:
                    tree_pts.append((c[2] * G, c[1] * G))
                ok = True
                break
        if not ok:
            fails += 1
            log('  FAIL', nm, t.get('ref'), t['pt'])
            # still add as tree point so the rest can proceed (unconnected)
    return fails == 0, fails

# order: DDR, short signals, power, rest
def net_span(nm):
    ps = [t['pt'] for t in TERM[nm]]
    if not ps:
        return 0
    return (max(p[0] for p in ps) - min(p[0] for p in ps)) + (max(p[1] for p in ps) - min(p[1] for p in ps))

order = [n for n in TERM if n not in PLANE_NETS]
def prio(n):
    if n.startswith('DDR_') and n not in POWER:
        return (0, net_span(n))
    if n in POWER:
        return (2, -len(TERM[n]))
    return (1, net_span(n))
order.sort(key=prio)
only = sys.argv[1:] if len(sys.argv) > 1 else None
results = {}
t1 = time.time()
for idx, nm in enumerate(order):
    if only and not any(re.search(o, nm) for o in only):
        continue
    ok, fails = route_net(nm)
    results[nm] = fails
    if idx % 25 == 0:
        log('progress', idx, '/', len(order), '%.0fs' % (time.time() - t1))
nfail = sum(1 for v in results.values() if v)
log('routed nets', len(results), 'nets with failures', nfail, 'failed connections', sum(results.values()), '%.0fs' % (time.time() - t1))
json.dump(results, open('tools/pcb/route_result.json', 'w'), indent=0)
board.Save(PCB)
open('tools/pcb/route_log.txt', 'w', encoding='utf8').write('\n'.join(LOG))
log('saved')
