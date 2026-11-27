# 部品番号 (参照記号) のシルク文字を、重ならず読めるように整える (2026-11-20)
# 方針: 部品の周りの空いた位置を探す → 無理なら文字高さを 0.75mm まで縮める → それでも無理なら非表示
# usage: python silk_text.py in.kicad_pcb [out.kicad_pcb]   (out を省略すると in を上書き)
import sys, math
import pcbnew
from pcbnew import VECTOR2I, ToMM

SRC = sys.argv[1]
DST = sys.argv[2] if len(sys.argv) > 2 else SRC
SIZES = [1.0, 0.9, 0.8, 0.75]      # 文字高さ (mm)。0.75 が下限
CLB = 0.25                         # 裏面へ移すときの他部品との間隔
MARGIN = 0.12                      # 文字の箱と障害物との間隔
PADEXP = 0.22                      # パッドの外側にあるシルク外形ぶんの余裕
BOARD = (0.0, 0.0, 160.0, 100.0)
EDGE = 0.5

b = pcbnew.LoadBoard(SRC)
fps = [f for f in b.GetFootprints() if not f.GetReference().startswith('#')]


def mm(v):
    return int(round(v * 1e6))


def box(bb):
    return (ToMM(bb.GetX()), ToMM(bb.GetY()), ToMM(bb.GetX() + bb.GetWidth()), ToMM(bb.GetY() + bb.GetHeight()))


def tht(f):
    return bool(f.GetAttributes() & pcbnew.FP_THROUGH_HOLE) or any(p.GetDrillSize().x > 0 for p in f.Pads())


def hit(a, o, m=0.0):
    return a[2] + m > o[0] and a[0] - m < o[2] and a[3] + m > o[1] and a[1] - m < o[3]


# 障害物 (面ごと): パッドの箱 (+余裕)、大きな部品は本体の箱も
obst = {'F': [], 'B': []}
own = {}
for f in fps:
    sides = ['B' if f.IsFlipped() else 'F']
    if tht(f):
        sides = ['F', 'B']
    r = f.GetReference()
    boxes = []
    for p in f.Pads():
        x0, y0, x1, y1 = box(p.GetBoundingBox())
        boxes.append((x0 - PADEXP, y0 - PADEXP, x1 + PADEXP, y1 + PADEXP))
    bx = box(f.GetBoundingBox(False))
    # 本体の外形 (シルクが描かれる範囲) も避ける: 小さな部品はパッド+0.22 の箱で足りるので、パッド箱の和集合
    if boxes:
        ub = (min(x[0] for x in boxes), min(x[1] for x in boxes), max(x[2] for x in boxes), max(x[3] for x in boxes))
    else:
        ub = bx
    own[r] = ub
    # 部品全体の外形 (パッドの和集合) を 1 つの障害物として使う (大きな IC/コネクタは、中にも文字が置けないので好都合)
    for s in sides:
        obst[s].append((r, ub))
        for bb in boxes:
            obst[s].append((r, bb))
# 取付穴の周り
for f in fps:
    if f.GetReference().startswith('H'):
        c = f.GetPosition()
        cx, cy = ToMM(c.x), ToMM(c.y)
        for s in ('F', 'B'):
            obst[s].append((f.GetReference(), (cx - 3.5, cy - 3.5, cx + 3.5, cy + 3.5)))

placed = {'F': [], 'B': []}   # すでに置いた文字の箱


def text_side(f):
    return 'B' if f.IsFlipped() else 'F'


def try_place(f, size):
    t = f.Reference()
    r = f.GetReference()
    s = text_side(f)
    t.SetVisible(True)
    t.SetTextSize(VECTOR2I(mm(size), mm(size)))
    t.SetTextThickness(mm(max(0.12, size * 0.15)))
    t.SetHorizJustify(pcbnew.GR_TEXT_H_ALIGN_CENTER)
    t.SetVertJustify(pcbnew.GR_TEXT_V_ALIGN_CENTER)
    ub = own[r]
    cx, cy = (ub[0] + ub[2]) / 2, (ub[1] + ub[3]) / 2
    best = None
    # 候補: 部品の上・下・左・右 (外側)、文字の向きは 0° と 90°。部品から近い順
    for ang in (0, 90):
        t.SetTextAngleDegrees(ang if s == 'F' else ang)
        t.SetTextPos(VECTOR2I(mm(cx), mm(cy)))
        tb = box(t.GetBoundingBox())
        tw, th = tb[2] - tb[0], tb[3] - tb[1]
        cands = []
        for gap in (0.0, 0.2, 0.4, 0.7, 1.0, 1.5, 2.2):
            cands += [(cx, ub[1] - gap - th / 2 - MARGIN), (cx, ub[3] + gap + th / 2 + MARGIN),
                      (ub[0] - gap - tw / 2 - MARGIN, cy), (ub[2] + gap + tw / 2 + MARGIN, cy)]
            # 端に寄せた位置 (部品の幅より文字が長いとき用)
            for sh in (-1, 1):
                cands += [(cx + sh * (tw / 2 + 0.3), ub[1] - gap - th / 2 - MARGIN), (cx + sh * (tw / 2 + 0.3), ub[3] + gap + th / 2 + MARGIN),
                          (ub[0] - gap - tw / 2 - MARGIN, cy + sh * (th / 2 + 0.3)), (ub[2] + gap + tw / 2 + MARGIN, cy + sh * (th / 2 + 0.3))]
        for (px, py) in cands:
            rect = (px - tw / 2, py - th / 2, px + tw / 2, py + th / 2)
            if rect[0] < BOARD[0] + EDGE or rect[1] < BOARD[1] + EDGE or rect[2] > BOARD[2] - EDGE or rect[3] > BOARD[3] - EDGE:
                continue
            if any(hit(rect, ob, MARGIN) for (rr, ob) in obst[s] if rr != r or True):
                continue
            if any(hit(rect, ob, MARGIN) for ob in placed[s]):
                continue
            d = (px - cx) ** 2 + (py - cy) ** 2
            if best is None or d < best[0]:
                best = (d, px, py, ang, rect)
        # 角度 0 で見つかれば 90° は試さない
        if best is not None:
            break
    if best is None:
        return False
    _, px, py, ang, rect = best
    t.SetTextAngleDegrees(ang)
    t.SetTextPos(VECTOR2I(mm(px), mm(py)))
    placed[s].append(rect)
    return True


# 混んでいる部品 (周りの障害物が多い) から先に処理する
def crowd(f):
    ub = own[f.GetReference()]
    s = text_side(f)
    n = 0
    for rr, ob in obst[s]:
        if rr != f.GetReference() and hit(ob, (ub[0] - 3, ub[1] - 3, ub[2] + 3, ub[3] + 3)):
            n += 1
    return -n


order = sorted(fps, key=crowd)
stats = {'1.0': 0, 'small': 0, 'hidden': 0}
hidden = []
shrunk = []
for f in order:
    ok = False
    for i, size in enumerate(SIZES):
        if try_place(f, size):
            ok = True
            if i == 0:
                stats['1.0'] += 1
            else:
                stats['small'] += 1
                shrunk.append((f.GetReference(), size))
            break
    if not ok:
        f.Reference().SetVisible(False)
        stats['hidden'] += 1
        hidden.append(f.GetReference())
# --- パスコン (C) で文字が出せなかったものは、裏面への移動を試す (ユーザーの許可: シルクが表示できないパスコンに限る) ---
u1 = [f for f in fps if f.GetReference() == 'U1']
keep_u1 = None
if u1:
    ubx = box(u1[0].GetBoundingBox(False))
    keep_u1 = (ubx[0] - 0.3, ubx[1] - 0.3, ubx[2] + 0.3, ubx[3] + 0.3)   # U1 の真下はビアの場所として空ける
flipped = []
for f in order:
    r = f.GetReference()
    if r not in hidden or not r.startswith('C') or f.IsFlipped() or tht(f):
        continue
    p0 = f.GetPosition()
    ok = False
    for dx, dy in [(0, 0)] + [(a * 0.25, c * 0.25) for a in range(-8, 9) for c in range(-8, 9) if (a or c)]:
        f.SetPosition(VECTOR2I(p0.x + mm(dx), p0.y + mm(dy)))
        if not f.IsFlipped():
            f.Flip(f.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
        # 裏面の占有判定 (自分以外の裏面の部品・両面を占有する部品、U1 の真下)
        mine = []
        for p in f.Pads():
            x0, y0, x1, y1 = box(p.GetBoundingBox())
            mine.append((x0 - PADEXP, y0 - PADEXP, x1 + PADEXP, y1 + PADEXP))
        okpos = all(not any(hit(m, ob, CLB) for rr, ob in obst['B'] if rr != r) for m in mine)
        if okpos and keep_u1 is not None and any(hit(m, keep_u1) for m in mine):
            okpos = False
        bx2 = box(f.GetBoundingBox(False))
        if okpos and (bx2[0] < EDGE or bx2[1] < EDGE or bx2[2] > BOARD[2] - EDGE or bx2[3] > BOARD[3] - EDGE):
            okpos = False
        if okpos:
            ok = True
            break
        f.Flip(f.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
    if not ok:
        f.SetPosition(p0)
        continue
    # 表面側の障害物から自分を外し、裏面に自分を追加
    obst['F'] = [(rr, ob) for rr, ob in obst['F'] if rr != r]
    ub = None
    for p in f.Pads():
        x0, y0, x1, y1 = box(p.GetBoundingBox())
        obst['B'].append((r, (x0 - PADEXP, y0 - PADEXP, x1 + PADEXP, y1 + PADEXP)))
    xs = [ob for rr, ob in obst['B'] if rr == r]
    own[r] = (min(o[0] for o in xs), min(o[1] for o in xs), max(o[2] for o in xs), max(o[3] for o in xs))
    shown = False
    for i, size in enumerate(SIZES):
        if try_place(f, size):
            shown = True
            break
    if shown:
        hidden.remove(r)
        stats['hidden'] -= 1
        stats['to_back'] = stats.get('to_back', 0) + 1
        flipped.append(r)
    else:
        f.Reference().SetVisible(False)
b.Save(DST)
print('to back', sorted(flipped))
print(stats)
print('shrunk', len(shrunk), sorted(shrunk)[:80])
print('hidden', len(hidden), sorted(hidden))
