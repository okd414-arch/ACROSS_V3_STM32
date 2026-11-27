# 0402 (01_MY:chip1005) → 0603 (01_MY:chip1608b) に基板のフットプリントを入れ替え、SoC (U1) の周りに再配置する (2026-11-16)
# usage: python swap_0603.py swap   (入れ替えて保存)
#        python swap_0603.py place  (別プロセスで再配置。入れ替え直後は SWIG のオブジェクトが壊れるため2段階)
# 裏面: U1 の外周に、電源ボールに近い辺へ。表面の分は元の位置の近く。
import collections, sys, json
import pcbnew
from pcbnew import VECTOR2I, ToMM

KICAD = 'C:/MyWorks/ACROSS_V3_STM32/kicad'
PCB = KICAD + '/ACROSS_V3.kicad_pcb'
TMP = KICAD + '/tools/pcb/swap_0603.json'
LIB = 'C:/OneDrive_link/KiCAD/Modules/01_MY'
W, H = 160.0, 100.0
CL = 0.25        # 部品どうしの最小間隔 (外形の箱どうし)
UMARGIN = 0.3    # U1 の外形から離す距離 (ビアの引き出し用)
STAGE = sys.argv[1]

def mm(v):
    return int(round(v * 1e6))

b = pcbnew.LoadBoard(PCB)

if STAGE == 'swap':
    rec = {}; olds = []
    for f in list(b.GetFootprints()):
        if f.GetFPID().GetLibItemName().wx_str() != 'chip1005':
            continue
        olds.append(f)
        rec[f.GetReference()] = dict(value=f.GetValue(), path=f.GetPath().AsString(), sheet=f.GetSheetname(),
                                     side='B' if f.IsFlipped() else 'F', pos=(ToMM(f.GetPosition().x), ToMM(f.GetPosition().y)),
                                     nets={p.GetNumber(): p.GetNetname() for p in f.Pads()})
    json.dump(rec, open(TMP, 'w', encoding='utf8'), ensure_ascii=False)
    for f in olds:
        b.Remove(f)
    nets = {str(k): v for k, v in b.GetNetInfo().NetsByName().items()}
    for r in sorted(rec):
        d = rec[r]
        n = pcbnew.FootprintLoad(LIB, 'chip1608b')
        n.SetFPID(pcbnew.LIB_ID('01_MY', 'chip1608b'))
        n.SetReference(r); n.SetValue(d['value']); n.SetPath(pcbnew.KIID_PATH(d['path'])); n.SetSheetname(d['sheet'])
        for p in n.Pads():
            p.SetNet(nets[d['nets'][p.GetNumber()]])
        n.SetPosition(VECTOR2I(mm(d['pos'][0]), mm(d['pos'][1])))
        b.Add(n)
        if d['side'] == 'B':
            n.Flip(n.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
    b.Save(PCB)
    print('swapped', len(rec))
    sys.exit(0)

# ------------------------- place -------------------------
rec = json.load(open(TMP, encoding='utf8'))
old = set(rec)
fps = {f.GetReference(): f for f in b.GetFootprints()}

def bbox(f):
    bb = f.GetBoundingBox(False)
    return (ToMM(bb.GetX()), ToMM(bb.GetY()), ToMM(bb.GetX() + bb.GetWidth()), ToMM(bb.GetY() + bb.GetHeight()))
def tht(f):
    # 穴のあるパッド (テストポイントの PTH パッドなど) を持つ部品は、両面を占有する
    return bool(f.GetAttributes() & pcbnew.FP_THROUGH_HOLE) or any(p.GetDrillSize().x > 0 for p in f.Pads())
def set_center(f, cx, cy):
    x0, y0, x1, y1 = bbox(f)
    p = f.GetPosition()
    f.SetPosition(VECTOR2I(p.x + mm(cx - (x0 + x1) / 2), p.y + mm(cy - (y0 + y1) / 2)))

occ = {'F': [], 'B': []}
for r, f in fps.items():
    if r in old:
        continue
    bb = bbox(f)
    if tht(f):
        occ['F'].append(bb); occ['B'].append(bb)
    else:
        occ['B' if f.IsFlipped() else 'F'].append(bb)
u1 = fps['U1']; ub = bbox(u1)
keep = (ub[0] - UMARGIN, ub[1] - UMARGIN, ub[2] + UMARGIN, ub[3] + UMARGIN)
occ['B'].append(keep)   # 裏面は U1 の真下をビアの場所として空ける

def collide(r, side):
    return any(r[2] + CL > o[0] and r[0] - CL < o[2] and r[3] + CL > o[1] and r[1] - CL < o[3] for o in occ[side])
def inboard(r):
    return r[0] >= 0.8 and r[1] >= 0.8 and r[2] <= W - 0.8 and r[3] <= H - 0.8

offs = sorted(((dx * 0.25, dy * 0.25) for dx in range(-80, 81) for dy in range(-80, 81)), key=lambda t: t[0] ** 2 + t[1] ** 2)
def place(f, tx, ty, side, angs):
    best = None
    for a in angs:
        f.SetOrientationDegrees(a if side == 'F' else (180 - a) % 360)
        for dx, dy in offs:
            d2 = dx * dx + dy * dy
            if best and d2 >= best[0]:
                break
            set_center(f, tx + dx, ty + dy)
            bb = bbox(f)
            if inboard(bb) and not collide(bb, side):
                best = (d2, a, tx + dx, ty + dy)
                break
    if best is None:
        return False
    f.SetOrientationDegrees(best[1] if side == 'F' else (180 - best[1]) % 360)
    set_center(f, best[2], best[3])
    occ[side].append(bbox(f))
    return True

# 各コンデンサの目標位置: つながる電源ネットの U1 ボールのうち、外周に近いものを重複なく割り当て
upads = collections.defaultdict(list)
for p in u1.Pads():
    if p.GetNetname() and not p.GetNetname().startswith('GND'):
        upads[p.GetNetname()].append((ToMM(p.GetPosition().x), ToMM(p.GetPosition().y)))
def edge_dist(pt):
    return min(pt[0] - ub[0], ub[2] - pt[0], pt[1] - ub[1], ub[3] - pt[1])
used = set(); fail = []
for r in sorted(old):
    f = fps[r]; side = rec[r]['side']
    nets = [p.GetNetname() for p in f.Pads() if p.GetNetname() and not p.GetNetname().startswith('GND')]
    cand = [pt for n in nets for pt in upads.get(n, []) if pt not in used] or [pt for n in nets for pt in upads.get(n, [])]
    if side == 'F' or not cand:
        ok = place(f, rec[r]['pos'][0], rec[r]['pos'][1], side, (0, 90))
    else:
        pt = min(cand, key=edge_dist); used.add(pt)
        dl, dr, dt, db = pt[0] - ub[0], ub[2] - pt[0], pt[1] - ub[1], ub[3] - pt[1]
        m = min(dl, dr, dt, db)
        if m == dl:   tx, ty, angs = keep[0] - 1.2, pt[1], (0,)
        elif m == dr: tx, ty, angs = keep[2] + 1.2, pt[1], (0,)
        elif m == dt: tx, ty, angs = pt[0], keep[1] - 1.2, (90,)
        else:         tx, ty, angs = pt[0], keep[3] + 1.2, (90,)
        ok = place(f, tx, ty, side, angs)
    if not ok:
        fail.append(r)
print('failed', fail)
b.Save(PCB)
print('saved')
