# 自前の格子配線 (maze router)。mr_export.py の JSON を読み、未配線の接続を 1 本ずつ引く (2026-11-22)
#   通常の Python (numpy, scipy) で動かす。結果は JSON (mr_apply.py で基板に入れる)。
#   - 格子 0.05mm、層 0=F 1=In2 2=In5 3=B (+ ビアの仮想層)。DDR は B を使わない
#   - 障害物は「他のネットの銅までの距離 - 必要な間隔」の場 D を層ごとに作り、線の半幅・ビアの半径と比べる
#   - 間隔: クラスの値の大きい方。BGA・eMMC の中は 0.1。絶縁ドメインが違えば 2.0
#   - 層の優先方向 (F 横、In2 縦、In5 横、B 縦) に逆らうと 2 倍のコスト、ビアは 1.2mm 分のコスト
#   - 経路はあとで直線に間引く (どの角度でも、障害物に当たらない範囲で)
# usage: python mr_route.py mr.json routes.json [--margin 4] [--only REGEX]
import sys, json, math, re, time, argparse, os
import numpy as np
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import dijkstra

ap = argparse.ArgumentParser()
ap.add_argument('inp')
ap.add_argument('out')
ap.add_argument('--margin', type=float, default=4.0)
ap.add_argument('--only', default=None)
ap.add_argument('--grid', type=float, default=0.05)
ap.add_argument('--first', default=None, help='このネットを先に引く (正規表現)')
ap.add_argument('--wide', default=None, help='このネットは 0.5mm から試す (正規表現)')
ap.add_argument('--maxrip', type=int, default=99, help='1 本の経路ではがしてよい線の数の上限')
ap.add_argument('--rip', action='store_true', help='道がないとき、他のネットの (ロックしていない) 線をはがして通す')
ap.add_argument('--pairs', action='store_true', help='差動ペア (DDR_CLK/DQS の P/N) は P を先に引き、N を P に沿わせる (2026-11-23)')
a = ap.parse_args()
G = a.grid
D_ = json.load(open(a.inp, encoding='utf8'))
items, nets, classes, relax, edge = D_['items'], D_['nets'], D_['classes'], D_['relax'], D_['edge']
VIA_R, VIA_HOLE = 0.15, 0.075   # 0.3/0.15 (2026-11-22 に 0.45/0.2 から小さくした)
PVIA_R, PVIA_HOLE = 0.225, 0.1  # 電源のビア 0.45/0.2
MARG = 0.02           # 格子の誤差の分の余裕
HOLE_TRACK = 0.21     # 穴と線の間隔 (基板の設定 0.2 + 余裕)
HOLE_HOLE = 0.25
EDGE_CLR = 0.3
PREF = ['h', 'v', 'h', 'v']
AGAINST = 2.0
VIA_COST = 1.2
# 絶縁の境目をまたぐ部品 (絶縁 DC-DC・アイソレータ・フォトカプラ)。そのパッドとの間は 2mm ではなく普通の間隔 (絶縁は部品が保証)
BRIDGE = set(['U601', 'U606', 'U607', 'U609', 'U701', 'U702', 'U703', 'U704', 'U705', 'U707'])
RIP_COST = 3.0
VIP_R, VIP_HOLE, VIP_COST = 0.125, 0.075, float(os.environ.get('MR_VIP_COST', 6.0))  # 環境変数で変えられる (2026-11-22)


def iso_of(net):
    if not net or net.startswith('unconnected-'):
        return None
    for c in nets.get(net, []):
        if c.startswith('ISO_'):
            return c
    return ''


def clr_of(net):
    return max(classes.get(c, classes['Default'])['clr'] for c in nets.get(net, ['Default'])) if net else 0.1


def w_of(net):
    return max(classes.get(c, classes['Default'])['w'] for c in nets.get(net, ['Default']))


def in_relax(x, y):
    return any(r[0] <= x <= r[2] and r[1] <= y <= r[3] for r in relax)


def need_clr(rnet, inet, x, y):
    ri, ii = iso_of(rnet), iso_of(inet)
    if ri is not None and ii is not None and ri != ii:
        return 2.0
    if in_relax(x, y):
        return 0.09  # BGA・QFN・eMMC の中 (DRU と同じ。2026-11-22 に 0.1 → 0.09)
    return max(clr_of(rnet), clr_of(inet))


# --- 距離の計算 (格子の点の配列に対して)
def d_seg(X, Y, ax, ay, bx, by):
    dx, dy = bx - ax, by - ay
    L2 = dx * dx + dy * dy
    if L2 == 0:
        return np.hypot(X - ax, Y - ay)
    t = np.clip(((X - ax) * dx + (Y - ay) * dy) / L2, 0, 1)
    return np.hypot(X - ax - t * dx, Y - ay - t * dy)


def d_poly(X, Y, pts):
    p = np.asarray(pts)
    d = np.full(X.shape, np.inf)
    inside = np.zeros(X.shape, bool)
    n = len(p)
    for i in range(n):
        x1, y1 = p[i]
        x2, y2 = p[(i + 1) % n]
        d = np.minimum(d, d_seg(X, Y, x1, y1, x2, y2))
        cond = (y1 > Y) != (y2 > Y)
        with np.errstate(divide='ignore', invalid='ignore'):
            xc = (x2 - x1) * (Y - y1) / (y2 - y1 + 1e-30) + x1
        inside ^= cond & (X < xc)
    d[inside] = 0
    return d


# 新しく引いた線・ビアも障害物に加える
def item_bbox(it):
    if it['k'] == 'seg':
        r = it['w'] / 2
        return min(it['a'][0], it['b'][0]) - r, min(it['a'][1], it['b'][1]) - r, max(it['a'][0], it['b'][0]) + r, max(it['a'][1], it['b'][1]) + r
    if it['k'] == 'via':
        x, y = it['c']; r = it['r']
        return x - r, y - r, x + r, y + r
    xs = [q[0] for ps in it['polys'].values() for poly in ps for q in poly] or [it['pos'][0]]
    ys = [q[1] for ps in it['polys'].values() for poly in ps for q in poly] or [it['pos'][1]]
    hr = it['hole'][2] if it['hole'] else 0
    return min(xs) - hr, min(ys) - hr, max(xs) + hr, max(ys) + hr


for it in items:
    it['bb'] = item_bbox(it)

# 絶縁ドメインの面の範囲 (ビアを置いてはいけない場所の判定)
DOM = {'ISO_A': lambda x, y: x >= 109 and y <= 53, 'ISO_D': lambda x, y: x >= 125 and y >= 77}


PAIR_PITCH = 0.3      # 差動ペアの中心間 (幅 0.1 + 間隔 0.2、DDR_DIFF クラス)
PITCH_OF = lambda n: 0.30 if n.startswith('USB') else PAIR_PITCH  # USB_DIFF は 幅 0.14 + 間隔 0.15 (クラスの間隔が 0.15 なので) (2026-11-26)
FOLLOW_PEN = 4.0      # N が P に沿っていないときのコストの倍率
ROOM_PEN = 1.8        # P を引くとき、横に N の入る余地がない所のコストの倍率 (BGA の外)
# MR_PAIR_PEN="沿う,余地" で上の 2 つを変える。MR_RIP_FIRST=正規表現 のネットは、はじめから はがしてよい設定で引く (2026-11-26、USB の差動ペア)
if os.environ.get('MR_PAIR_PEN'):
    FOLLOW_PEN, ROOM_PEN = map(float, os.environ['MR_PAIR_PEN'].split(','))
RIP_FIRST = re.compile(os.environ['MR_RIP_FIRST']) if os.environ.get('MR_RIP_FIRST') else None


def route(job, w, margin, rip=False, guide=None, leader=False):
    # guide: 相手 (P) の経路 {'segs': [...], 'vias': [...]}。あれば N をそれに沿わせる (2026-11-23)
    net = job['net']
    ddr = net.startswith('DDR_')
    layers_ok = [0, 1, 2, 3]  # DDR も B を使ってよい (2026-11-22 に緩めた)
    pts = job['a']['pts'] + job['b']['pts']
    x0 = max(edge[0], min(p[0] for p in pts) - margin)
    y0 = max(edge[1], min(p[1] for p in pts) - margin)
    x1 = min(edge[2], max(p[0] for p in pts) + margin)
    y1 = min(edge[3], max(p[1] for p in pts) + margin)
    nx, ny = int((x1 - x0) / G) + 1, int((y1 - y0) / G) + 1
    xs = x0 + np.arange(nx) * G
    ys = y0 + np.arange(ny) * G
    D = np.full((4, ny, nx), 9.0)   # 各層: 他のネットの銅まで - 必要な間隔
    VB = np.full((ny, nx), 9.0)     # 自分のパッドの上 (ビア禁止)
    Sf = np.full((4, ny, nx), 9.0)  # はがしてよい他のネットの線 (rip のとき)
    soft = []
    HT = np.full((ny, nx), 9.0)     # 他のネットの穴まで - 0.2
    H = np.full((ny, nx), 9.0)      # 穴まで (ネットに関係なく) - 穴の半径
    reach = max(w / 2, VIA_R) + MARG + 0.05
    for ii, it in enumerate(items):
        if it.get('dead'):
            continue
        bx0, by0, bx1, by1 = it['bb']
        same = it['net'] == net and net != ''
        holer = it.get('hole') if it['k'] == 'pad' else ([it['c'][0], it['c'][1], it['hole']] if it['k'] == 'via' else None)
        cx, cy = (bx0 + bx1) / 2, (by0 + by1) / 2
        c = need_clr(net, '' if (it['k'] == 'pad' and it.get('ref') in BRIDGE) else it['net'], cx, cy) if not (it['k'] == 'pad' and it.get('ref') in BRIDGE) else max(clr_of(net), clr_of(it['net']))
        ext = c + reach + 0.3
        if bx1 + ext < x0 or bx0 - ext > x1 or by1 + ext < y0 or by0 - ext > y1:
            continue
        ix0 = max(0, int((bx0 - ext - x0) / G)); ix1 = min(nx, int((bx1 + ext - x0) / G) + 2)
        iy0 = max(0, int((by0 - ext - y0) / G)); iy1 = min(ny, int((by1 + ext - y0) / G) + 2)
        if ix0 >= ix1 or iy0 >= iy1:
            continue
        X, Y = np.meshgrid(xs[ix0:ix1], ys[iy0:iy1])
        # はがしてよいビア (2026-11-22): 全層の「はがしてよい」範囲にする。穴の間隔もその範囲に含める
        if rip and it['k'] == 'via' and it.get('soft') and not same:
            dd = np.minimum(np.hypot(X - it['c'][0], Y - it['c'][1]) - it['r'] - c,
                            np.hypot(X - it['c'][0], Y - it['c'][1]) - it['hole'] - HOLE_TRACK)
            soft.append((ii, c))
            for l in range(4):
                sl = Sf[l, iy0:iy1, ix0:ix1]
                np.minimum(sl, dd, out=sl)
            continue
        if holer:
            dh = np.hypot(X - holer[0], Y - holer[1]) - holer[2]
            H[iy0:iy1, ix0:ix1] = np.minimum(H[iy0:iy1, ix0:ix1], dh)
            if not same:  # 他のネットの穴と線の間隔 (0.2)
                HT[iy0:iy1, ix0:ix1] = np.minimum(HT[iy0:iy1, ix0:ix1], dh - HOLE_TRACK)
        if same:
            # 自分のネットの表面実装パッドの上にはビアを置かない
            if it['k'] == 'pad' and not holer and it.get('ref') != 'ZONE':
                for l, polys in it['polys'].items():
                    if int(l) in (0, 3):
                        dd = np.min([d_poly(X, Y, pp) for pp in polys], axis=0) - VIA_R - 0.05
                        sl = VB[iy0:iy1, ix0:ix1]
                        np.minimum(sl, dd, out=sl)
            continue
        if it['k'] == 'seg':
            dd = d_seg(X, Y, it['a'][0], it['a'][1], it['b'][0], it['b'][1]) - it['w'] / 2 - c
            if rip and it.get('soft'):
                soft.append((ii, c))
                sl = Sf[it['l'], iy0:iy1, ix0:ix1]
                np.minimum(sl, dd, out=sl)
                continue
            sl = D[it['l'], iy0:iy1, ix0:ix1]
            np.minimum(sl, dd, out=sl)
        elif it['k'] == 'via':
            dd = np.hypot(X - it['c'][0], Y - it['c'][1]) - it['r'] - c
            for l in range(4):
                sl = D[l, iy0:iy1, ix0:ix1]
                np.minimum(sl, dd, out=sl)
        else:
            for l, polys in it['polys'].items():
                l = int(l)
                dd = np.min([d_poly(X, Y, pp) for pp in polys], axis=0) - c
                sl = D[l, iy0:iy1, ix0:ix1]
                np.minimum(sl, dd, out=sl)
            if holer and not it['polys']:  # 銅のない穴 (NPTH)
                dd = np.hypot(X - holer[0], Y - holer[1]) - holer[2] - HOLE_TRACK
                for l in range(4):
                    sl = D[l, iy0:iy1, ix0:ix1]
                    np.minimum(sl, dd, out=sl)
    # 基板の端
    XX, YY = np.meshgrid(xs, ys)
    de = np.minimum.reduce([XX - edge[0], edge[2] - XX, YY - edge[1], edge[3] - YY]) - EDGE_CLR
    for l in range(4):
        np.minimum(D[l], de, out=D[l])
    free = D >= w / 2 + MARG
    softblk = Sf < w / 2 + MARG
    softvia = Sf.min(axis=0) < VIA_R + MARG
    free &= (HT >= w / 2 + MARG)[None]
    for l in range(4):
        if l not in layers_ok:
            free[l] = False
    # ビアの穴と他のネットの銅: BGA 等の中は 0.15、外は 0.2 (D は銅の間隔 0.1 以上を引いた値なので、その分を足して比べる)
    inrel = np.zeros((ny, nx), bool)
    for r in relax:
        inrel |= (XX >= r[0]) & (XX <= r[2]) & (YY >= r[1]) & (YY <= r[3])
    vneed = np.where(inrel, max(VIA_R, VIA_HOLE + 0.15 - 0.1), max(VIA_R, VIA_HOLE + HOLE_TRACK - 0.1)) + MARG
    viaok = (D.min(axis=0) >= vneed) & (H >= VIA_HOLE + HOLE_HOLE + MARG) & (VB >= 0)
    # 絶縁ドメインの面: ドメインの外のネットのビアは中に置かない、ドメインのネットのビアは外に置かない
    ri = iso_of(net)
    for g, f in DOM.items():
        m = np.vectorize(f)(XX, YY) if False else ((XX >= 109) & (YY <= 53) if g == 'ISO_A' else (XX >= 125) & (YY >= 77))
        if ri == g:
            viaok &= m
        else:
            viaok &= ~m
    # 始点・終点
    def cells(end):
        res = []
        for p in end['pts']:
            ix, iy = int(round((p[0] - x0) / G)), int(round((p[1] - y0) / G))
            if 0 <= ix < nx and 0 <= iy < ny:
                for l in end['layers']:
                    if l in layers_ok:
                        res.append((l, iy, ix, p))
        return res
    S, Tt = cells(job['a']), cells(job['b'])
    if not S or not Tt:
        return None, 'outside'
    for l, iy, ix, p in S + Tt:  # 端点のまわり (自分のパッドの中) は通れる
        free[l, max(0, iy - 1):iy + 2, max(0, ix - 1):ix + 2] = True
    # BGA (U1/U301/U302) のボールが囲まれて出られないとき用: ボールの中に 0.25/0.15 のビア (穴埋め VIP)
    vip = set()
    for end, cl in ((job['a'], S), (job['b'], Tt)):
        itm = items[end['item']]
        if itm['k'] == 'pad' and not itm['hole'] and any(r[0] <= itm['pos'][0] <= r[2] and r[1] <= itm['pos'][1] <= r[3] for r in relax[:3]):
            for l, iy, ix, p in cl:
                if D[:, iy, ix].min() >= VIP_R + MARG and H[iy, ix] >= VIP_HOLE + HOLE_HOLE + MARG:
                    vip.add((iy, ix))
    NL = 5
    N = NL * ny * nx
    idx = np.arange(ny * nx).reshape(ny, nx)
    rows, cols, wts = [], [], []
    steps = [(0, 1, 1.0, 'h'), (1, 0, 1.0, 'v'), (1, 1, 1.4142, 'd'), (1, -1, 1.4142, 'd')]
    # 差動ペア (2026-11-23): N は P の中心線から PAIR_PITCH 離れた帯の中なら安い。P は横に N の余地がある所が安い
    band = None
    if guide is not None:
        band = np.zeros((4, ny, nx), bool)
        lo = np.where(inrel, 0.17, PITCH_OF(net) - 0.06)
        hi = np.where(inrel, 0.45, PITCH_OF(net) + 0.06)
        for l in range(4):
            gd = np.full((ny, nx), 9.0)
            for s in guide['segs']:
                if s[0] != l:
                    continue
                ix0 = max(0, int((min(s[1], s[3]) - 0.6 - x0) / G)); ix1 = min(nx, int((max(s[1], s[3]) + 0.6 - x0) / G) + 2)
                iy0 = max(0, int((min(s[2], s[4]) - 0.6 - y0) / G)); iy1 = min(ny, int((max(s[2], s[4]) + 0.6 - y0) / G) + 2)
                if ix0 >= ix1 or iy0 >= iy1:
                    continue
                sub = gd[iy0:iy1, ix0:ix1]
                np.minimum(sub, d_seg(XX[iy0:iy1, ix0:ix1], YY[iy0:iy1, ix0:ix1], s[1], s[2], s[3], s[4]), out=sub)
            band[l] = (gd >= lo) & (gd <= hi)
        gv = np.full((ny, nx), 9.0)
        for vv in guide['vias']:
            np.minimum(gv, np.hypot(XX - vv[0], YY - vv[1]), out=gv)
        near_gv = gv <= 0.9
    room = None
    if leader:
        room = (D < 0.2 + PITCH_OF(net) / 2 + 0.05) & (~inrel)[None]
    for l in range(4):
        if l not in layers_ok:
            continue
        fl = free[l]
        for dy, dx, ln, kind in steps:
            f = PREF[l]
            fac = 1.0 if kind == f else (AGAINST if kind in 'hv' else 1.5)
            ys0 = slice(0, ny - dy)
            if dx >= 0:
                xs0, xs1 = slice(0, nx - dx), slice(dx, nx)
            else:
                xs0, xs1 = slice(-dx, nx), slice(0, nx + dx)
            ys1 = slice(dy, ny)
            m = fl[ys0, xs0] & fl[ys1, xs1]
            u = idx[ys0, xs0][m] + l * ny * nx
            v = idx[ys1, xs1][m] + l * ny * nx
            if band is not None:
                inb = band[l][ys0, xs0][m] & band[l][ys1, xs1][m]
                fac = np.where(inb, 1.0, fac * FOLLOW_PEN)
            elif room is not None:
                fac = fac * np.where(room[l][ys0, xs0][m] | room[l][ys1, xs1][m], ROOM_PEN, 1.0)
            c = ln * G * fac + RIP_COST * (softblk[l][ys0, xs0][m] | softblk[l][ys1, xs1][m])
            rows += [u, v]; cols += [v, u]; wts += [c, c]
    # ビア: 各層 <-> ビア層
    vm = viaok
    for l in layers_ok:
        m = vm & free[l]
        u = idx[m] + l * ny * nx
        v = idx[m] + 4 * ny * nx
        c = VIA_COST / 2 + RIP_COST * 5 * softvia[m]
        if band is not None:
            c = c + np.where(near_gv[m], 0.0, 1.5)
        rows += [u, v]; cols += [v, u]; wts += [c, c]
    for iy, ix in vip:
        for l in layers_ok:
            free[l, iy, ix] = True
            u, v = l * ny * nx + idx[iy, ix], 4 * ny * nx + idx[iy, ix]
            c = np.array([VIP_COST / 2])
            rows += [np.array([u]), np.array([v])]; cols += [np.array([v]), np.array([u])]; wts += [c, c]
    r = np.concatenate(rows); cc = np.concatenate(cols); ww = np.concatenate(wts)
    gph = coo_matrix((ww, (r, cc)), shape=(N, N)).tocsr()
    src = sorted({l * ny * nx + iy * nx + ix for l, iy, ix, p in S})
    dist, pred, srcs = dijkstra(gph, directed=True, indices=src, min_only=True, return_predecessors=True)
    tg = [(l * ny * nx + iy * nx + ix, p) for l, iy, ix, p in Tt]
    best = min(tg, key=lambda t: dist[t[0]])
    if not np.isfinite(dist[best[0]]):
        ra = int(np.isfinite(dist).sum())
        d2 = dijkstra(gph, directed=True, indices=sorted({t[0] for t in tg}), min_only=True)
        rb = int(np.isfinite(d2).sum())
        return None, f'no path (始点から届く {ra} / 終点から {rb} 節点)'
    path = []
    n = best[0]
    while n >= 0:
        path.append(n)
        n = pred[n]
    path.reverse()
    sp = next(p for l, iy, ix, p in S if l * ny * nx + iy * nx + ix == path[0])
    # はがす線: 経路の節点がその線の禁止範囲に入っているもの
    ripped = []
    if soft:
        pn = [divmod(int(n), ny * nx) for n in path]
        pl_ = np.array([q[0] for q in pn])
        py_ = np.array([q[1] // nx for q in pn]) * G + y0
        px_ = np.array([q[1] % nx for q in pn]) * G + x0
        for ii, c in soft:
            it = items[ii]
            if it['k'] == 'via':
                lim = np.where(pl_ == 4, VIA_R, w / 2) + MARG
                r_ = np.hypot(px_ - it['c'][0], py_ - it['c'][1])
                dd = np.minimum(r_ - it['r'] - c, r_ - it['hole'] - HOLE_TRACK)
                if (dd < lim).any():
                    ripped.append(ii)
                continue
            m = (pl_ == it['l']) | (pl_ == 4)
            if not m.any():
                continue
            lim = np.where(pl_[m] == 4, VIA_R, w / 2) + MARG
            dd = d_seg(px_[m], py_[m], it['a'][0], it['a'][1], it['b'][0], it['b'][1]) - it['w'] / 2 - c
            if (dd < lim).any():
                ripped.append(ii)
    if rip and len({items[i]['net'] for i in ripped}) > a.maxrip:  # ネットの数で数える (2026-11-22)
        return None, f'はがすネットが多すぎる ({len({items[i]["net"] for i in ripped})})'
    ep = best[1]
    # 節点 → (層, x, y)
    seq = []
    for n in path:
        l, rem = divmod(n, ny * nx)
        iy, ix = divmod(rem, nx)
        seq.append((l, x0 + ix * G, y0 + iy * G))
    # 層ごとの折れ線と、ビア
    polylines, vias = [], []
    cur = [(seq[0][0], sp[0], sp[1])]
    for i, (l, x, y) in enumerate(seq):
        if l == 4:
            if cur and len(cur) > 1:
                polylines.append(cur)
            iy_, ix_ = int(round((y - y0) / G)), int(round((x - x0) / G))
            vias.append((x, y, 0.25, 0.15) if (iy_, ix_) in vip else (x, y, VIA_R * 2, VIA_HOLE * 2))
            cur = []
            continue
        if not cur:
            cur = [(l, x, y)]
        else:
            cur.append((l, x, y))
    cur.append((cur[-1][0], ep[0], ep[1]))
    polylines.append(cur)
    # ビアの位置を折れ線の端にそろえる
    segs = []
    for pl in polylines:
        lay = pl[0][0]
        P = [(x, y) for _, x, y in pl]
        fr = free[lay]
        if soft:
            # はがすときは、経路の上のマス以外の「はがしてよい線」も避けて間引く (はがす線は経路の節点で選んだので)
            onp = np.zeros((ny, nx), bool)
            for _, x, y in pl:
                onp[int(round((y - y0) / G)), int(round((x - x0) / G))] = True
            fr = fr & (~softblk[lay] | onp)
        if band is not None:  # N は間引いても P に沿ったまま (帯の中か、元の経路の上だけ)
            onp = np.zeros((ny, nx), bool)
            for _, x, y in pl:
                onp[int(round((y - y0) / G)), int(round((x - x0) / G))] = True
            fr = fr & (band[lay] | onp)
        P = simplify(P, fr, x0, y0, nx, ny)
        for (ax_, ay_), (bx_, by_) in zip(P, P[1:]):
            if abs(ax_ - bx_) > 1e-6 or abs(ay_ - by_) > 1e-6:
                segs.append([int(lay), round(float(ax_), 4), round(float(ay_), 4), round(float(bx_), 4), round(float(by_), 4), float(w)])
    return {'net': net, 'segs': segs, 'vias': [[round(float(x), 4), round(float(y), 4), d_, h_] for x, y, d_, h_ in vias], 'cost': float(dist[best[0]]), 'rip': [items[i]['uuid'] for i in ripped], 'rip_nets': sorted({items[i]['net'] for i in ripped}), '_rip_idx': ripped}, 'ok'


def clear_line(P0, P1, fr, x0, y0, nx, ny):
    L = math.hypot(P1[0] - P0[0], P1[1] - P0[1])
    n = max(2, int(L / (G / 2)) + 1)
    for k in range(n + 1):
        t = k / n
        x, y = P0[0] + (P1[0] - P0[0]) * t, P0[1] + (P1[1] - P0[1]) * t
        ix, iy = int(round((x - x0) / G)), int(round((y - y0) / G))
        if not (0 <= ix < nx and 0 <= iy < ny) or not fr[iy, ix]:
            return False
    return True


def simplify(P, fr, x0, y0, nx, ny):
    if len(P) <= 2:
        return P
    out = [P[0]]
    i = 0
    while i < len(P) - 1:
        j = len(P) - 1
        while j > i + 1 and not clear_line(P[i], P[j], fr, x0, y0, nx, ny):
            j -= 1
        out.append(P[j])
        i = j
    return out


def add_result(res):
    for i in res.pop('_rip_idx', []):
        items[i]['dead'] = True
    for l, ax_, ay_, bx_, by_, w in res['segs']:
        it = {'k': 'seg', 'net': res['net'], 'l': l, 'a': [ax_, ay_], 'b': [bx_, by_], 'w': w}
        it['bb'] = item_bbox(it)
        items.append(it)
    for x, y, d_, h_ in res['vias']:
        it = {'k': 'via', 'net': res['net'], 'c': [x, y], 'r': d_ / 2, 'hole': h_ / 2}
        it['bb'] = item_bbox(it)
        items.append(it)


jobs = D_['jobs']
if a.only:
    jobs = [j for j in jobs if re.search(a.only, j['net'])]


def jlen(j):
    p, q = j['a']['pts'][0], j['b']['pts'][0]
    return math.hypot(p[0] - q[0], p[1] - q[1])


import random
_rng = random.Random(int(os.environ['MR_SEED'])) if os.environ.get('MR_SEED') else None  # 引く順番のばらつき (mr_loop --keep)
PAIR_RE = re.compile(r'^(DDR_(?:CLK|DQS\d)|USB\d_D)([PNM])$')  # USB の DP/DM も (2026-11-26。P が先、N/M が沿う)
_key = {id(j): (0 if a.first and re.search(a.first, j['net']) else 1, jlen(j) * (1 + 0.6 * _rng.random() if _rng else 1), 0) for j in jobs}
if a.pairs:  # N は対応する P (同じ区間) のすぐ後に引く
    for j in jobs:
        m = PAIR_RE.match(j['net'])
        if m and m.group(2) in 'NM':
            pj = next((k for k in jobs if k['net'] == m.group(1) + 'P' and k.get('leg') == j.get('leg')), None)
            if pj:
                _key[id(j)] = _key[id(pj)][:2] + (1,)
jobs.sort(key=lambda j: _key[id(j)])
done, fail = [], []
for j in jobs:
    t0 = time.time()
    w = w_of(j['net'])
    guide, leader = None, False
    if a.pairs:
        m = PAIR_RE.match(j['net'])
        if m and m.group(2) == 'P':
            leader = True
        elif m:
            guide = next(({'segs': r['segs'], 'vias': r['vias']} for r in done if r['net'] == m.group(1) + 'P' and r.get('leg') == j.get('leg')), None)
    if a.wide and re.search(a.wide, j['net']):
        w = 0.5
    tries = [(w, a.margin, False), (w, a.margin * 2.5, False)] + ([(0.3, a.margin * 2.5, False)] if w > 0.3 else []) + ([(0.15, a.margin * 2.5, False)] if w > 0.15 else [])
    if a.rip:
        tries.append((min(w, 0.15) if w > 0.12 else w, a.margin * 2.5, True))
    if RIP_FIRST and RIP_FIRST.search(j['net']):
        tries = [(w, a.margin * 2.5, True)] + tries
    res, why = None, ''
    for ww, mg, rp in tries:
        res, why = route(j, ww, mg, rp, guide=guide, leader=leader)
        if res:
            res['leg'] = j.get('leg')
            break
    dt = time.time() - t0
    if res:
        add_result(res)
        done.append(res)
        print(f'OK   {j["net"][-28:]:28s} {jlen(j):5.1f}mm  segs {len(res["segs"]):3d} vias {len(res["vias"])} w {res["segs"][0][5] if res["segs"] else "-"}  はがす {len(res["rip"])} {",".join(n[-12:] for n in res["rip_nets"])}  {dt:.1f}s', flush=True)
    else:
        fail.append({'net': j['net'], 'why': why, 'a': j['a']['pts'][0], 'b': j['b']['pts'][0]})
        print(f'FAIL {j["net"][-28:]:28s} {jlen(j):5.1f}mm  {why}  {dt:.1f}s', flush=True)
json.dump({'routes': done, 'fail': fail}, open(a.out, 'w', encoding='utf8'))
print('ok', len(done), 'fail', len(fail))
