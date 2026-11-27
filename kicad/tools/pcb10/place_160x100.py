# 基板 160x100mm への再配置 (2026-11-16)
# 入力: バックアップの「配置のみ(配線前)」基板 (ネット付き) → 出力: kicad/ACROSS_V3.kicad_pcb
# 方針: 絶縁ドメインごとに領域を決め、絶縁をまたぐ部品 (DC-DC、アイソレータ、フォトカプラ) は
#       一次側のパッドが一次側の領域に向くように、境界線の上に置く。他の部品は領域内で、つながる部品の近くに置く。
import sys, re, collections, math
import pcbnew
from pcbnew import VECTOR2I, ToMM

BASE = 'C:/MyWorks/ACROSS_V3_STM32'
SRC = BASE + '/バックアップ_20261116/ACROSS_V3_配置のみ(配線前).kicad_pcb'
OUT = BASE + '/kicad/ACROSS_V3.kicad_pcb'
W, H = 160.0, 100.0
EDGE = 2.0      # 端に寄せない部品と基板端の距離
CL = 0.3        # 部品どうしの最小間隔 (外形の箱)

# ---- 領域 (x0, y0, x1, y1) ----
XB = 92.0   # 一次側とドメインA/Bの境界 (縦)
XF0, XF1 = 127.0, 134.0   # 一次側の「指」(B と C/D の間)
YT0, YT1 = 41.0, 49.0     # 一次側の「舌」(A と B/C/D の間)
REG = {
    'P': [(0, 0, XB - 1, H), (XB - 1, YT0, W, YT1), (XF0, YT0, XF1, H)],
    'A': [(XB + 1, 0, W, YT0 - 2)],
    'B': [(XB + 1, YT1 + 2, XF0 - 2, H)],
    'C': [(XF1 + 2, YT1 + 2, W, 76)],
    'D': [(XF1 + 2, 78, W, H)],
}
GND_DOM = {'GND': 'P', 'GND_A': 'A', 'GND_B': 'B', 'GND_D': 'D'}
BRIDGES = {'U801', 'U806', 'U807', 'U809', 'U901', 'U904', 'U905', 'U906', 'U907', 'U908', 'U909', 'U910', 'U912'}
HOLES = {'H101': (4, 4), 'H102': (80, 4), 'H103': (156, 4), 'H104': (4, 96), 'H105': (80, 96), 'H106': (156, 96)}

# 絶縁をまたぐ部品: (境界の軸, 境界の座標, 一次側の向き(-1: 座標の小さい側), 境界に沿った位置, 相手のドメイン)
BRIDGE_POS = {
    'U801': ('x', XB, -1, 6.0, 'A'), 'U806': ('x', XB, -1, 17.5, 'A'), 'U807': ('x', XB, -1, 28.0, 'A'), 'U809': ('x', XB, -1, 35.0, 'A'),
    'U904': ('x', XB, -1, 57.5, 'B'), 'U905': ('x', XB, -1, 70.0, 'B'), 'U901': ('x', XB, -1, 83.0, 'B'),
    'U906': ('x', XF1, -1, 54.0, 'C'), 'U907': ('x', XF1, -1, 60.0, 'C'), 'U908': ('x', XF1, -1, 66.0, 'C'), 'U909': ('x', XF1, -1, 72.0, 'C'),
    'U910': ('x', XF1, -1, 83.0, 'D'), 'U912': ('x', XF1, -1, 93.0, 'D'),
}
# 位置を決める部品: ref: (x, y, 向き)  向き = コネクタの開口方向 (端に寄せる) / 'rotN' = 回転角
SEEDS = collections.OrderedDict([
    # 電源入力 (左端)
    ('J101', (0, 20, 'left')), ('F101', (13, 13, None)), ('D101', (13, 27, None)), ('Q101', (21, 21, None)),
    ('U101', (28, 13, None)), ('C103', (22, 33, None)), ('U103', (32, 27, None)),
    ('U102', (12, 46, None)), ('L101', (24, 47, None)), ('D103', (12, 57, None)),
    # デバッグ USB-C (左端)
    ('J604', (0, 70, 'left')), ('U605', (17, 72, None)),
    # PMIC
    ('U201', (36, 48, None)),
    # SoC・メモリ
    ('U1', (58, 50, None)), ('U501', (79, 38, None)), ('U502', (79, 62, None)), ('U601', (57, 23, None)),
    # 上辺: LCD FPC、状態LED
    ('J702', (42, 0, 'up')), ('D301', (61, 2.5, None)), ('D302', (64.5, 2.5, None)), ('D303', (68, 2.5, None)), ('D304', (71.5, 2.5, None)),
    # 下辺: RJ45、USB-A、USB-C (OTG)、microSD
    ('J701', (17.6, H, 'down')), ('J602', (36.3, H, 'down')), ('J603', (51.0, H, 'down')), ('J601', (66.2, H, 'down')),
    ('U701', (30, 70, None)),
    # 操作・デバッグ
    ('SW301', (46, 71, None)), ('SW201', (40, 62, None)), ('J301', (86, 82, None)), ('JP301', (72, 74, None)),
    # ドメインA (右上): 端子は右辺と上辺
    ('J801', (W, 22, 'right')), ('J802', (118, 0, 'up')),
    ('U804', (130, 22, None)), ('U808', (112, 26, None)), ('U805', (134, 8, None)), ('SW801', (145, 34, None)),
    ('U802', (104, 7, None)), ('U803', (104, 15, None)),
    # ドメインB (GPS): ソケットは横向き 2列 (列間隔 30.48)
    ('J901', (112.5, 59.5, 'rot90')), ('J902', (112.5, 89.98, 'rot90')),
    ('U902', (104, 74, None)), ('U903', (116, 74, None)),
    # ドメインC/D: 端子は右辺
    ('J903', (W, 63, 'right')), ('J904', (W, 84, 'right')), ('U911', (144, 88, None)),
])

def mm(v):
    return int(round(v * 1e6))

board = pcbnew.LoadBoard(SRC)
# 外形を作り直す
edges = [d for d in board.GetDrawings() if d.GetLayer() == pcbnew.Edge_Cuts]
assert len(edges) == 4, len(edges)
for seg, (x1, y1, x2, y2) in zip(edges, [(0, 0, W, 0), (W, 0, W, H), (W, H, 0, H), (0, H, 0, 0)]):
    seg.SetStart(VECTOR2I(mm(x1), mm(y1))); seg.SetEnd(VECTOR2I(mm(x2), mm(y2)))

# 絶縁ドメインの領域の目安 (Cmts.User)。再実行に備えて、前回の目安線と文字を消してから描く
for d in [d for d in board.GetDrawings() if d.GetLayer() == pcbnew.Cmts_User]:
    board.Delete(d)
def cline(x1, y1, x2, y2):
    s = pcbnew.PCB_SHAPE(board)
    s.SetShape(pcbnew.SHAPE_T_SEGMENT); s.SetLayer(pcbnew.Cmts_User)
    s.SetStart(VECTOR2I(mm(x1), mm(y1))); s.SetEnd(VECTOR2I(mm(x2), mm(y2))); s.SetWidth(mm(0.15))
    board.Add(s)
def ctext(x, y, t):
    s = pcbnew.PCB_TEXT(board)
    s.SetText(t); s.SetLayer(pcbnew.Cmts_User); s.SetPosition(VECTOR2I(mm(x), mm(y)))
    s.SetTextSize(VECTOR2I(mm(1.5), mm(1.5))); s.SetTextThickness(mm(0.2))
    board.Add(s)
for dom, rects in REG.items():
    if dom == 'P':
        continue
    for (x0, y0, x1, y1) in rects:
        for seg in ((x0, y0, x1, y0), (x1, y0, x1, y1), (x1, y1, x0, y1), (x0, y1, x0, y0)):
            if not ((seg[0] == seg[2] and seg[0] in (0, W)) or (seg[1] == seg[3] and seg[1] in (0, H))):
                cline(*seg)
ctext(XB + 12, YT0 - 4, 'ドメインA (GND_A)'); ctext(XB + 8, H - 3, 'ドメインB (GND_B)')
ctext(XF1 + 10, 52, 'C'); ctext(XF1 + 10, 79.5, 'D (GND_D)')

fps = {fp.GetReference(): fp for fp in board.GetFootprints()}
# 一旦すべて表面・回転0へ戻す
for fp in fps.values():
    if fp.IsFlipped():
        fp.Flip(fp.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
    fp.SetOrientationDegrees(0)

# ---- ネットのドメイン (絶縁部品以外でつながるネットをまとめる) ----
par = {}
def uf(x):
    while par.setdefault(x, x) != x:
        x = par[x]
    return x
for r, fp in fps.items():
    ns = [p.GetNetname() for p in fp.Pads() if p.GetNetname() and not p.GetNetname().startswith('unconnected-')]
    for n in ns:
        uf(n)
    if r in BRIDGES:
        continue
    for n in ns[1:]:
        par[uf(ns[0])] = uf(n)
grp = collections.defaultdict(set)
for n in list(par):
    grp[uf(n)].add(n)
netdom = {}
for k, s in grp.items():
    g = [GND_DOM[n] for n in s if n in GND_DOM]
    assert len(g) <= 1, s
    d = g[0] if g else 'C'      # グランドの無いまとまり = ドメインC (外部OC出力、J903)
    for n in s:
        netdom[n] = d
partdom = {}
for r, fp in fps.items():
    if r in BRIDGES or r in HOLES:
        continue
    ds = set(netdom[p.GetNetname()] for p in fp.Pads() if p.GetNetname() in netdom)
    assert len(ds) <= 1, (r, ds)
    partdom[r] = ds.pop() if ds else 'P'

# ---- 配置の道具 ----
occ = {'F': [], 'B': []}
def bbox(fp):
    bb = fp.GetBoundingBox(False)
    return (ToMM(bb.GetX()), ToMM(bb.GetY()), ToMM(bb.GetX() + bb.GetWidth()), ToMM(bb.GetY() + bb.GetHeight()))
def is_tht(fp):
    return bool(fp.GetAttributes() & pcbnew.FP_THROUGH_HOLE)
def move_by(fp, dx, dy):
    p = fp.GetPosition()
    fp.SetPosition(VECTOR2I(p.x + mm(dx), p.y + mm(dy)))
def set_center(fp, cx, cy):
    b = bbox(fp)
    move_by(fp, cx - (b[0] + b[2]) / 2, cy - (b[1] + b[3]) / 2)
def inside(r, rects, m):
    return any(r[0] >= q[0] + m and r[1] >= q[1] + m and r[2] <= q[2] - m and r[3] <= q[3] - m for q in rects)
def collide(r, sides):
    for s in sides:
        for o in occ[s]:
            if r[2] + CL > o[0] and r[0] - CL < o[2] and r[3] + CL > o[1] and r[1] - CL < o[3]:
                return True
    return False
def free(r, sides, dom, edge_ok):
    lim = 0.3 if edge_ok else EDGE
    if r[0] < lim or r[1] < lim or r[2] > W - lim or r[3] > H - lim:
        return False
    if dom and not inside(r, REG[dom], 0 if edge_ok else 0.0):
        # 端のコネクタは基板端まで領域とみなす
        return False
    return not collide(r, sides)
def commit(fp, ref, sides):
    b = bbox(fp)
    for s in sides:
        occ[s].append(b)
    placed[ref] = ((b[0] + b[2]) / 2, (b[1] + b[3]) / 2)

def pad_pts(fp, skip=('SH', 'MP', 'EP', '')):
    return [(ToMM(p.GetPosition().x), ToMM(p.GetPosition().y)) for p in fp.Pads() if p.GetNumber() not in skip]
def face(fp, facing):
    want = {'left': (-1, 0), 'right': (1, 0), 'up': (0, -1), 'down': (0, 1)}[facing]
    best = None
    for ang in (0, 90, 180, 270):
        fp.SetOrientationDegrees(ang)
        b = bbox(fp)
        pts = pad_pts(fp)
        pc = (sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts))
        v = ((b[0] + b[2]) / 2 - pc[0], (b[1] + b[3]) / 2 - pc[1])
        d = v[0] * want[0] + v[1] * want[1]
        if best is None or d > best[0] + 1e-6:
            best = (d, ang)
    fp.SetOrientationDegrees(best[1])

placed = {}
offsets = sorted(((dx * 0.5, dy * 0.5) for dx in range(-120, 121) for dy in range(-120, 121)), key=lambda t: t[0] ** 2 + t[1] ** 2)
def place(ref, tx, ty, side='F', dom=None, edge_ok=False, maxr=60, axis=None):
    fp = fps[ref]
    if side == 'B' and not fp.IsFlipped():
        fp.Flip(fp.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
    sides = ['F', 'B'] if is_tht(fp) else [side]
    for dx, dy in offsets:
        if dx * dx + dy * dy > maxr * maxr:
            break
        if axis == 'x' and dy != 0 or axis == 'y' and dx != 0:
            continue
        set_center(fp, tx + dx, ty + dy)
        if free(bbox(fp), sides, dom, edge_ok):
            commit(fp, ref, sides)
            return True
    print('FAILED', ref, dom, tx, ty)
    set_center(fp, tx, ty)
    commit(fp, ref, sides)
    return False

# ---- 1. 取付穴 ----
for ref, (x, y) in HOLES.items():
    fp = fps[ref]
    set_center(fp, x, y)
    commit(fp, ref, ['F', 'B'])

# ---- 2. 絶縁をまたぐ部品 ----
for ref, (ax, c, pdir, along, dom) in BRIDGE_POS.items():
    fp = fps[ref]
    prim = lambda p: netdom.get(p.GetNetname()) == 'P'
    best = None
    for ang in (0, 90, 180, 270):
        fp.SetOrientationDegrees(ang)
        k = 0 if ax == 'x' else 1
        pp = [(ToMM(p.GetPosition().x), ToMM(p.GetPosition().y)) for p in fp.Pads() if p.GetNetname() in netdom and prim(p)]
        ss = [(ToMM(p.GetPosition().x), ToMM(p.GetPosition().y)) for p in fp.Pads() if p.GetNetname() in netdom and not prim(p)]
        # 一次側が pdir 側にあり、二次側と完全に分かれる向き
        gap = (min(q[k] for q in ss) - max(q[k] for q in pp)) if pdir < 0 else (min(q[k] for q in pp) - max(q[k] for q in ss))
        if best is None or gap > best[0]:
            best = (gap, ang)
    fp.SetOrientationDegrees(best[1])
    k = 0 if ax == 'x' else 1
    pp = [(ToMM(p.GetPosition().x), ToMM(p.GetPosition().y))[k] for p in fp.Pads() if p.GetNetname() in netdom and prim(p)]
    ss = [(ToMM(p.GetPosition().x), ToMM(p.GetPosition().y))[k] for p in fp.Pads() if p.GetNetname() in netdom and not prim(p)]
    mid = (max(pp) + min(ss)) / 2 if pdir < 0 else (min(pp) + max(ss)) / 2
    b = bbox(fp)
    if ax == 'x':
        move_by(fp, c - mid, along - (b[1] + b[3]) / 2)
    else:
        move_by(fp, along - (b[0] + b[2]) / 2, c - mid)
    commit(fp, ref, ['F', 'B'] if is_tht(fp) else ['F'])
    print('bridge %s ang=%d gap=%.2f' % (ref, best[1], best[0]))

# ---- 3. 位置を決める部品 ----
for ref, (x, y, f) in SEEDS.items():
    fp = fps[ref]
    dom = partdom.get(ref, 'P')
    if f in ('left', 'right', 'up', 'down'):
        face(fp, f)
        b = bbox(fp)
        w, h = b[2] - b[0], b[3] - b[1]
        if f == 'left':
            x = 0.3 + w / 2
        if f == 'right':
            x = W - 0.3 - w / 2
        if f == 'up':
            y = 0.3 + h / 2
        if f == 'down':
            y = H - 0.3 - h / 2
        place(ref, x, y, 'F', None, edge_ok=True, axis=('y' if f in ('left', 'right') else 'x'))
    else:
        if f and f.startswith('rot'):
            fp.SetOrientationDegrees(int(f[3:]))
        place(ref, x, y, 'F', dom)

# BGAの周りは引き出し用に空ける (表: 外周, 裏: ビアの範囲)
for kref, mF, mB in (('U1', 2.5, 0.6), ('U501', 1.5, 0.6), ('U502', 1.5, 0.6), ('U601', 1.0, 0.6)):
    kb = bbox(fps[kref])
    occ['F'].append((kb[0] - mF, kb[1] - mF, kb[2] + mF, kb[3] + mF))
    occ['B'].append((kb[0] - mB, kb[1] - mB, kb[2] + mB, kb[3] + mB))

# ---- 4. 残り: つながりの強い順に、つながる部品の近くへ ----
nets = collections.defaultdict(list)
for r, fp in fps.items():
    for p in fp.Pads():
        if p.GetNetname():
            nets[p.GetNetname()].append(r)
adj = collections.defaultdict(lambda: collections.defaultdict(float))
for n, refs in nets.items():
    refs = sorted(set(refs))
    if len(refs) < 2 or len(refs) > 14:
        continue
    wgt = 1.0 / (len(refs) - 1)
    for a in refs:
        for b2 in refs:
            if a != b2:
                adj[a][b2] += wgt
netcount = collections.Counter()
for n, refs in nets.items():
    netcount[n] = len(refs)
def is_pwr(n):
    return n.startswith('GND') or n.startswith('+') or n.startswith('VDD') or n.startswith('VTT') or n.startswith('VREF') or netcount[n] >= 6
nets_of = {r: set(p.GetNetname() for p in fp.Pads() if p.GetNetname()) for r, fp in fps.items()}

rest = [r for r in fps if r not in placed]
while rest:
    best = max(rest, key=lambda r: (sum(w for o, w in adj[r].items() if o in placed), r))
    rest.remove(best)
    r = best
    dom = partdom.get(r, 'P')
    links = [(o, w) for o, w in adj[r].items() if o in placed]
    if links:
        tw = sum(w for o, w in links)
        tx = sum(placed[o][0] * w for o, w in links) / tw
        ty = sum(placed[o][1] * w for o, w in links) / tw
    else:
        q = REG[dom][0]
        tx, ty = (q[0] + q[2]) / 2, (q[1] + q[3]) / 2
    side = 'F'
    # SoC電源のデカップリング (03シートの、電源だけにつながるコンデンサ) は裏面、SoCの下
    if re.match(r'C3\d\d$', r) and nets_of[r] and all(is_pwr(n) for n in nets_of[r]):
        side = 'B'
        tx, ty = placed['U1']
    place(r, tx, ty, side, dom)

# 0.1mm グリッドへ
for fp in fps.values():
    p = fp.GetPosition()
    fp.SetPosition(VECTOR2I(int(round(p.x / 100000.0)) * 100000, int(round(p.y / 100000.0)) * 100000))

board.Save(OUT)
print('saved', OUT, len(fps))
cnt = collections.Counter(partdom.get(r, 'BR') for r in fps)
print(cnt)
