# デバッグ用のシルク文字を追加する (2026-11-24)
#   コネクタ・ジャンパー・スイッチのピンごとの信号名、テストポイント・LED・コネクタの名前、ブートの表、基板名。
#   置いた文字は全部「DBG_SILK」のグループに入れる。再実行するとグループごと消してから置き直す。
#   位置は自動で探す: ほかの部品の外形 (courtyard)・パッド・基板の縁・取付穴・既にある文字と重ならない所。
#   ピン名は、表 (F.SilkS) に全部置けなければ、そのコネクタの分を裏 (B.SilkS、鏡文字) に置く (コネクタは全部スルーホール)。
#   部品の名前は表、置けなければ裏。文字の高さは 1.0 → 0.9 → 0.8mm (JLC の下限は 0.8 程度)。
# usage: python debug_silk.py pcb [-o out]
import sys
import pcbnew

pcb = sys.argv[1]
out = sys.argv[sys.argv.index('-o') + 1] if '-o' in sys.argv else pcb
b = pcbnew.LoadBoard(pcb)
mm, tomm = pcbnew.FromMM, pcbnew.ToMM
SILK = {'F': b.GetLayerID('F.SilkS'), 'B': b.GetLayerID('B.SilkS')}
CRT = {'F': b.GetLayerID('F.CrtYd'), 'B': b.GetLayerID('B.CrtYd')}
HS, TH = (1.0, 0.9, 0.8), 0.15
GAP = 0.2

# --- ピンごとの名前 (回路図のネットから決めた、2026-11-24) ---
PINS = {
    'J101': {'1': 'GND', '2': '+24V'},
    'J201': {'1': 'SWCLK', '2': 'GND', '3': 'SWDIO', '4': 'NRST', '5': '3V3'},
    'J601': {'1': 'A+', '2': 'A-', '3': 'B+', '4': 'B-', '5': 'Z+', '6': 'Z-', '7': 'Z24V', '8': 'ZOC', '9': 'GND_A'},
    'J602': {'1': 'PUL+', '2': 'PUL-', '3': 'DIR+', '4': 'DIR-', '5': 'GND_A', '6': 'DOC_C', '7': 'DOC_E'},
    'J701': {'1': '+5V', '2': 'GND', '3': 'GND', '4': 'GND', '5': '10M', '6': '1PPS', '7': 'LOCK', '8': 'ALM', '9': 'TX', '10': 'RX'},
    'J702': {'1': 'OC1', '2': 'OC2', '3': 'OC3', '4': 'OC4', '5': 'COM'},
    'J703': {'1': 'PUL', '2': 'DIR', '3': 'GND_D'},
    'JP201': {'1': 'TCXO', '2': 'HSE', '3': 'GPS'},
    'J503': {'1': 'BL+', '2': 'BL-'},
}
# --- 部品の近くに置く名前 ---
LABELS = {
    'J201': 'SWD', 'J401': 'microSD', 'J402': 'USB HOST', 'J403': 'USB OTG', 'J404': 'DEBUG UART',
    'J501': 'ETH', 'J502': 'LCD', 'J503': 'BL TEST', 'J601': 'ENCODER', 'J602': 'SERVO', 'J701': 'GPS',
    'J702': 'OC OUT', 'J703': 'MON TTL', 'J101': '24V IN', 'JP201': 'HSE SEL', 'SW101': 'PWR',
    'SW601': 'Z:422/OC', 'SW602': 'TERM A B Z', 'SW201': 'BOOT B0 B1 B2',
    'D201': 'G1', 'D202': 'G2', 'D203': 'R1', 'D204': 'R2',
}
fps = {fp.GetReference(): fp for fp in b.GetFootprints()}
for r, fp in fps.items():
    if r.startswith('TP'):
        v = fp.GetValue()
        LABELS[r] = v[3:] if v.startswith('TP_') else v
FREE = [  # 空いている所を探して置く文字 (文字, 近くの部品, 面)
    ('B2B1B0 (ON=1): 000 USB/UART  010 eMMC  101 SD', 'SW201'),
    ('ACROSS V3  2026-11', None),
]


def box_of(bb, g=0.0):
    return (tomm(bb.GetLeft()) - g, tomm(bb.GetTop()) - g, tomm(bb.GetRight()) + g, tomm(bb.GetBottom()) + g)


# 既存のデバッグ用グループを消す
for g in list(b.Groups()):
    if g.GetName() == 'DBG_SILK':
        for it in list(g.GetItems()):
            b.Remove(it)
        b.Remove(g)

# --- 障害物 (面ごと) ---
obst = {'F': [], 'B': []}
for fp in b.GetFootprints():
    side = 'B' if fp.IsFlipped() else 'F'
    cy = fp.GetCourtyard(CRT[side])
    if cy.OutlineCount():
        obst[side].append(box_of(cy.BBox()))
    for pd in fp.Pads():
        bx = box_of(pd.GetBoundingBox(), 0.15)
        if pd.GetAttribute() in (pcbnew.PAD_ATTRIB_PTH, pcbnew.PAD_ATTRIB_NPTH):
            obst['F'].append(bx); obst['B'].append(bx)
        else:
            obst[side].append(bx)
    for it in fp.GraphicalItems():
        for s in 'FB':
            if it.GetLayer() == SILK[s]:
                obst[s].append(box_of(it.GetBoundingBox(), 0.05))
    for t in (fp.Reference(), fp.Value()):
        for s in 'FB':
            if t.IsVisible() and t.GetLayer() == SILK[s]:
                obst[s].append(box_of(t.GetBoundingBox(), 0.05))
for d in b.GetDrawings():
    for s in 'FB':
        if d.GetLayer() == SILK[s]:
            obst[s].append(box_of(d.GetBoundingBox(), 0.05))
for r, fp in fps.items():   # 取付穴 (ネジの頭) の周り
    if r.startswith('H'):
        p = fp.GetPosition()
        for s in 'FB':
            obst[s].append((tomm(p.x) - 3.3, tomm(p.y) - 3.3, tomm(p.x) + 3.3, tomm(p.y) + 3.3))
eb = b.GetBoardEdgesBoundingBox()
EX0, EY0, EX1, EY1 = tomm(eb.GetLeft()) + 0.5, tomm(eb.GetTop()) + 0.5, tomm(eb.GetRight()) - 0.5, tomm(eb.GetBottom()) - 0.5

grp = pcbnew.PCB_GROUP(b)
grp.SetName('DBG_SILK')
b.Add(grp)
placed = {'F': 0, 'B': 0}


def hits(r, s):
    x0, y0, x1, y1 = r
    if x0 < EX0 or y0 < EY0 or x1 > EX1 or y1 > EY1:
        return True
    for o in obst[s]:
        if x0 < o[2] and x1 > o[0] and y0 < o[3] and y1 > o[1]:
            return True
    return False


def make(text, x, y, h, ang, s, just=0):
    # just: -1 = 文字の始まりが (x, y)、1 = 終わりが (x, y)、0 = 中央 (いずれも見る向きで)
    t = pcbnew.PCB_TEXT(b)
    t.SetText(text)
    t.SetLayer(SILK[s])
    t.SetTextSize(pcbnew.VECTOR2I(mm(h), mm(h)))
    t.SetTextThickness(mm(TH))
    t.SetTextAngleDegrees(ang)
    if s == 'B':
        t.SetMirrored(True)
    t.SetHorizJustify({0: pcbnew.GR_TEXT_H_ALIGN_CENTER, -1: pcbnew.GR_TEXT_H_ALIGN_LEFT, 1: pcbnew.GR_TEXT_H_ALIGN_RIGHT}[just])
    t.SetVertJustify(pcbnew.GR_TEXT_V_ALIGN_CENTER)
    t.SetPosition(pcbnew.VECTOR2I(mm(x), mm(y)))
    # 鏡文字では左寄せ/右寄せの伸びる向きが逆になる → 箱で確かめて、はみ出す向きを直す
    if s == 'B' and just != 0:
        bx = box_of(t.GetBoundingBox())
        if ang == 0:
            want_right = (just == -1)     # 始まりが (x, y) → 右へ伸びてほしい
            if want_right and bx[0] < x - 0.01 or (not want_right) and bx[2] > x + 0.01:
                t.SetHorizJustify(pcbnew.GR_TEXT_H_ALIGN_RIGHT if just == -1 else pcbnew.GR_TEXT_H_ALIGN_LEFT)
        else:
            want_up = (just == -1)
            if want_up and bx[3] > y + 0.01 or (not want_up) and bx[1] < y - 0.01:
                t.SetHorizJustify(pcbnew.GR_TEXT_H_ALIGN_RIGHT if just == -1 else pcbnew.GR_TEXT_H_ALIGN_LEFT)
    return t


def tbox(t):
    return box_of(t.GetBoundingBox(), GAP)


def put(t, s):
    b.Add(t)
    grp.AddItem(t)
    obst[s].append(tbox(t))
    placed[s] += 1


def crt_box(fp, s):
    cy = fp.GetCourtyard(CRT['B' if fp.IsFlipped() else 'F'])
    return box_of(cy.BBox()) if cy.OutlineCount() else box_of(fp.GetBoundingBox(False))


fail = []
where = {}

# --- 1. ピンごとの名前 ---
for ref, names in PINS.items():
    fp = fps.get(ref)
    if fp is None:
        fail.append(ref + ' (部品なし)'); continue
    P = {p.GetNumber(): (tomm(p.GetPosition().x), tomm(p.GetPosition().y)) for p in fp.Pads() if p.GetNumber() in names}
    xs = [v[0] for v in P.values()]; ys = [v[1] for v in P.values()]
    horiz = (max(xs) - min(xs)) > (max(ys) - min(ys))
    done = False
    for s in ('F', 'B'):
        cb = crt_box(fp, s)
        best = None
        for h in HS:
            for side in (-1, 1):
                for off in (0.1, 0.4, 0.8):
                    ts = []
                    for n, (x, y) in P.items():
                        if horiz:   # 文字は 90° (下から上へ読む)。上側は下端を、下側は上端を外形に合わせる
                            edge = cb[1] - off - GAP if side < 0 else cb[3] + off + GAP
                            ts.append(make(names[n], x, edge, h, 90, s, just=(-1 if side < 0 else 1)))
                        else:
                            edge = cb[0] - off - GAP if side < 0 else cb[2] + off + GAP
                            ts.append(make(names[n], edge, y, h, 0, s, just=(1 if side < 0 else -1)))
                    bad = sum(hits(tbox(t), s) for t in ts)
                    if best is None or bad < best[0]:
                        best = (bad, ts)
                    if bad == 0:
                        break
                if best[0] == 0:
                    break
            if best[0] == 0:
                break
        if best[0] == 0:
            for t in best[1]:
                put(t, s)
            where[ref] = s
            done = True
            break
    if not done:
        fail.append(f'{ref} のピン名 (表・裏とも重なる: {best[0]} 個)')


# --- 2. 部品の名前 ---
def place_near(text, fp, sides=('F', 'B'), hs=HS):
    for s in sides:
        cb = crt_box(fp, s)
        cx, cyy = (cb[0] + cb[2]) / 2, (cb[1] + cb[3]) / 2
        for h in hs:
            for k in range(0, 25):
                d = k * 0.4
                cands = []
                for sh in (0, -1, 1, -2, 2, -3, 3):
                    cands += [(cx + sh * 1.5, cb[1] - d - h / 2 - GAP - 0.05, 0, 0), (cx + sh * 1.5, cb[3] + d + h / 2 + GAP + 0.05, 0, 0),
                              (cb[0] - d - GAP - 0.05, cyy + sh * 1.5, 0, 1), (cb[2] + d + GAP + 0.05, cyy + sh * 1.5, 0, -1),
                              (cb[0] - d - h / 2 - GAP - 0.05, cyy + sh * 1.5, 90, 0), (cb[2] + d + h / 2 + GAP + 0.05, cyy + sh * 1.5, 90, 0)]
                for x, y, ang, just in cands:
                    t = make(text, x, y, h, ang, s, just)
                    if not hits(tbox(t), s):
                        return t, s
    return None, None


for ref, text in sorted(LABELS.items(), key=lambda kv: (not kv[0].startswith('J'), kv[0])):
    fp = fps.get(ref)
    if fp is None:
        continue
    t, s = place_near(text, fp)
    if t is None:
        fail.append(f'{ref}: {text}'); continue
    put(t, s)
    if s == 'B':
        where[ref + '(名前)'] = 'B'

# --- 3. 空いている所に置く文字 ---
for text, near in FREE:
    t = s = None
    if near:
        t, s = place_near(text, fps[near], hs=(0.8,))
    if t is None:
        for s in ('F', 'B'):
            h = 1.5 if near is None else 0.8
            for y in [EY1 - 1 - k * 0.5 for k in range(0, 190)]:
                for x in [EX0 + 6 + k * 1.0 for k in range(0, 150)]:
                    c = make(text, x, y, h, 0, s, -1)
                    if not hits(tbox(c), s):
                        t = c; break
                if t: break
            if t: break
    if t is None:
        fail.append('FREE: ' + text)
    else:
        put(t, s)
        where['FREE: ' + text[:12]] = s

b.Save(out)
print('置いた文字 表', placed['F'], '裏', placed['B'])
print('裏に置いたもの:', ', '.join(k for k, v in where.items() if v == 'B'))
for f in fail:
    print('  ×', f)
