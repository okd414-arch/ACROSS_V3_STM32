# DDR の長さ合わせ: 目標の長さを決めて、足りない線に蛇行 (コの字の山の連続) を入れる (2026-11-23)
#   通常の Python (numpy)。入力: ddr_tune_plan.py の JSON (区間ごとの経路の線と長さ) と mr_export.py の JSON (障害物)。
#   出力: 置き換えの一覧 (ddr_tune_apply.py が基板に入れる)。
#   目標 (AN5122 6.1 / 6.3 節、真ん中をねらう):
#     CLK (P/N 平均) が一番長い。A/C は U301 で CLK - 0.5、U301→U302 の区間は CLK と同じ。
#     レーン k の長さ T_k = max(DQS, レーン内の DQ の最大)。DQ・DQM・DQS をそこへ。CLK - T_k は 0〜14。
#   蛇行: 区間の経路の直線の線を、山 (高さ h) の並びに置き換える。山 1 つで 2h 伸びる。
#     ペア (P/N が平行に並んだ線) は同じ山を中心線に作り、それぞれの離れ (o) だけずらす → P と N は同じだけ伸びる。
#   置く前に、周りの銅 (他のネットの線・ビア・パッド、同じネットの他の線) との間隔を幾何で確かめる。
# usage: python ddr_tune.py plan.json items.json out.json [--only REGEX] [--dry]
import sys, json, math, re
import numpy as np

plan = json.load(open(sys.argv[1], encoding='utf8'))
D_ = json.load(open(sys.argv[2], encoding='utf8'))
OUT = sys.argv[3]
ONLY = re.compile(sys.argv[sys.argv.index('--only') + 1]) if '--only' in sys.argv else None
items, nets, classes, relax = D_['items'], D_['nets'], D_['classes'], D_['relax']
W = 0.1
TOL_DQ = 0.5      # DQ-DQS はこの範囲なら直さない (規則は ±1.016)
TOL_AC = 0.35
HS = [2.5, 2.0, 1.5, 1.2, 1.0, 0.8, 0.65, 0.5, 0.4, 0.3]  # 山の高さの候補 (高い方から)
MARG = 0.015


def clr_of(net):
    return max(classes.get(c, classes['Default'])['clr'] for c in nets.get(net, ['Default'])) if net else 0.1


def in_relax(x, y):
    return any(r[0] <= x <= r[2] and r[1] <= y <= r[3] for r in relax)


# ---- 長さと目標
def leg(net, lg):
    v = plan.get(net, {}).get(lg)
    return None if v is None else v['len']


def mean2(a, b):
    return None if a is None or b is None else (a + b) / 2


AC = sorted(n for n, v in plan.items() if 'U301-U302' in v and not re.search(r'CLK|DQ|RESETN', n))
# レーンのつながる先は plan の区間から決める (2026-11-23 のレーン入れ替えで 1 → U302、2 → U301)
lane_chip = {k: ('U1-U301' if 'U1-U301' in plan.get(f'DDR_DQS{k}P', {}) else 'U1-U302') for k in range(4)}
L1 = [k for k in range(4) if lane_chip[k] == 'U1-U301']
L2 = [k for k in range(4) if lane_chip[k] == 'U1-U302']
lanes = {k: [f'DDR_DQ{i}' for i in range(8 * k, 8 * k + 8)] + [f'DDR_DQM{k}'] for k in range(4)}
C1 = mean2(leg('DDR_CLKP', 'U1-U301'), leg('DDR_CLKN', 'U1-U301'))
c2 = mean2(leg('DDR_CLKP', 'U301-U302'), leg('DDR_CLKN', 'U301-U302'))
T = {}
for k, lg in lane_chip.items():
    dqs = mean2(leg(f'DDR_DQS{k}P', lg), leg(f'DDR_DQS{k}N', lg))
    T[k] = max([x for x in [dqs] + [leg(n, lg) for n in lanes[k]] if x is not None])
a1 = max(leg(n, 'U1-U301') for n in AC if leg(n, 'U1-U301') is not None)
a2 = max(leg(n, 'U301-U302') for n in AC if leg(n, 'U301-U302') is not None)
C1t = max([C1, a1 + 0.5] + [T[k] + 0.5 for k in L1])
for k in L1:
    T[k] = max(T[k], C1t - 14)
c2t = max(c2, a2 - 0.3, max(T[k] for k in L2) + 0.5 - C1t)
C2t = C1t + c2t
for k in L2:
    T[k] = max(T[k], C2t - 14)
print(f'今: CLK U301 {C1:.1f} 区間2 {c2:.1f}  A/C 最大 {a1:.1f} / {a2:.1f}  レーン {", ".join(f"{T[k]:.1f}" for k in range(4))}')
print(f'目標: CLK U301 {C1t:.1f} U302 {C2t:.1f}  A/C {C1t - 0.5:.1f} / 区間2 {c2t:.1f}')
req = []  # (名前, [ネット], 区間, 伸ばす長さ)
req.append(('CLK', ['DDR_CLKP', 'DDR_CLKN'], 'U1-U301', C1t - C1))
req.append(('CLK2', ['DDR_CLKP', 'DDR_CLKN'], 'U301-U302', c2t - c2))
for k, lg in lane_chip.items():
    dqs = mean2(leg(f'DDR_DQS{k}P', lg), leg(f'DDR_DQS{k}N', lg))
    req.append((f'DQS{k}', [f'DDR_DQS{k}P', f'DDR_DQS{k}N'], lg, T[k] - dqs))
    for n in lanes[k]:
        if leg(n, lg) is not None and abs(T[k] - leg(n, lg)) > TOL_DQ:
            req.append((n[4:], [n], lg, T[k] - leg(n, lg)))
for n in AC:
    if leg(n, 'U1-U301') is not None:
        req.append((n[4:], [n], 'U1-U301', C1t - 0.5 - leg(n, 'U1-U301')))
    if leg(n, 'U301-U302') is not None:
        req.append((n[4:] + '_2', [n], 'U301-U302', c2t - leg(n, 'U301-U302')))
if '--band' in sys.argv:
    # 緩めた規則 (2026-11-23 ユーザー「等長は 20mm 程度まで許容」): 比べる相手との差を ±B に収める (伸ばすだけ)。
    #   レーン内 (DQ・DQM・DQS): 一番長いもの - B 以上に。CLK と DQS、CLK と A/C (それぞれのメモリで): 互いに 長い方 - B 以上に。
    B = float(sys.argv[sys.argv.index('--band') + 1])
    req = []
    dqs = {k: mean2(leg(f'DDR_DQS{k}P', lg), leg(f'DDR_DQS{k}N', lg)) for k, lg in lane_chip.items()}
    mem = {k: {n: leg(n, lane_chip[k]) for n in lanes[k] if leg(n, lane_chip[k]) is not None} for k in range(4)}
    a1s = {n: leg(n, 'U1-U301') for n in AC if leg(n, 'U1-U301') is not None}
    C1t = max([C1] + [v - B for v in a1s.values()] + [dqs[k] - B for k in L1])
    a1t = {n: max(v, C1t - B) for n, v in a1s.items()}
    tot = {n: a1t[n] + leg(n, 'U301-U302') for n in AC if n in a1t and leg(n, 'U301-U302') is not None}
    C2t = max([C1t + c2] + [v - B for v in tot.values()] + [dqs[k] - B for k in L2])
    for k in range(4):
        Ck = C1t if k in L1 else C2t
        top = max([dqs[k]] + list(mem[k].values()))
        dt = max(dqs[k], top - B, Ck - B)
        T[k] = dt
        req.append((f'DQS{k}', [f'DDR_DQS{k}P', f'DDR_DQS{k}N'], lane_chip[k], dt - dqs[k]))
        for n, v in mem[k].items():
            req.append((n[4:], [n], lane_chip[k], max(top, dt) - B - v))
    req.append(('CLK', ['DDR_CLKP', 'DDR_CLKN'], 'U1-U301', C1t - C1))
    req.append(('CLK2', ['DDR_CLKP', 'DDR_CLKN'], 'U301-U302', C2t - C1t - c2))
    for n, v in a1s.items():
        req.append((n[4:], [n], 'U1-U301', a1t[n] - v))
    for n, v in tot.items():
        req.append((n[4:] + '_2', [n], 'U301-U302', C2t - B - v))
    c2t = C2t - C1t
    print(f'帯 ±{B}: CLK 目標 U301 {C1t:.1f} U302 {C2t:.1f}  DQS 目標 ' + ', '.join(f'{T[k]:.1f}' for k in range(4)))
    req = [r for r in req if r[3] > 0.3 and (not ONLY or ONLY.search(r[0]))]
req = [r for r in req if r[3] > (TOL_AC if len(r[1]) == 1 else 0.3) and (not ONLY or ONLY.search(r[0]))]
print('伸ばす', len(req), '本、合計', round(sum(r[3] for r in req), 1), 'mm')

# ---- 障害物 (カプセル = 線分 + 半径)。層ごと。パッドは輪郭の辺 + 中の判定
OB = {l: [] for l in range(4)}   # (ax, ay, bx, by, r, net, kind, uuid)
PADP = {l: [] for l in range(4)}  # (poly np.array, net, bbox)
for it in items:
    if it['k'] == 'seg':
        OB[it['l']].append((*it['a'], *it['b'], it['w'] / 2, it['net'], 'seg', it.get('uuid')))
    elif it['k'] == 'via':
        for l in range(4):
            OB[l].append((*it['c'], *it['c'], it['r'], it['net'], 'via', it.get('uuid')))
    else:
        for l, polys in it['polys'].items():
            for p in polys:
                pa = np.array(p)
                for i in range(len(p)):
                    q, r_ = p[i], p[(i + 1) % len(p)]
                    OB[int(l)].append((q[0], q[1], r_[0], r_[1], 0.0, it['net'], 'pad', None))
                PADP[int(l)].append((pa, it['net'], (pa[:, 0].min(), pa[:, 1].min(), pa[:, 0].max(), pa[:, 1].max())))
        if it.get('hole') and not it['polys']:
            h = it['hole']
            for l in range(4):
                OB[l].append((h[0], h[1], h[0], h[1], h[2] + 0.12, it['net'], 'hole', None))
OBA = {}


def rebuild(l):
    o = OB[l]
    arr = np.array([[x[0], x[1], x[2], x[3], x[4]] for x in o])
    onet = np.array([x[5] or '' for x in o], dtype=object)
    ouid = np.array([x[7] or '' for x in o], dtype=object)
    cx, cy = (arr[:, 0] + arr[:, 2]) / 2, (arr[:, 1] + arr[:, 3]) / 2
    inr = np.zeros(len(o), bool)
    for r in relax:
        inr |= (cx >= r[0]) & (cx <= r[2]) & (cy >= r[1]) & (cy <= r[3])
    cl = np.array([clr_of(n) for n in onet])
    c = np.where(inr, 0.09, np.maximum(0.09, cl))
    OBA[l] = (arr, onet, ouid, c)


PADA = {}
for l in range(4):
    PADA[l] = np.array([bb for _, _, bb in PADP[l]]) if PADP[l] else np.zeros((0, 4))


for l in range(4):
    rebuild(l)


def segdist(P0, P1, Q0, Q1):
    # 線分の組 (P: M 本, Q: K 本) の最短距離 M×K
    P0 = P0[:, None, :]; P1 = P1[:, None, :]; Q0 = Q0[None]; Q1 = Q1[None]

    def pd(X, A, B):
        AB = B - A
        L2 = (AB ** 2).sum(-1)
        t = np.where(L2 > 0, ((X - A) * AB).sum(-1) / np.where(L2 > 0, L2, 1), 0)
        t = np.clip(t, 0, 1)
        return np.hypot(*(np.moveaxis(X - A - t[..., None] * AB, -1, 0)))
    d = np.minimum.reduce([pd(P0, Q0, Q1), pd(P1, Q0, Q1), pd(Q0, P0, P1), pd(Q1, P0, P1)])

    def cr(A, B, C):
        return (B[..., 0] - A[..., 0]) * (C[..., 1] - A[..., 1]) - (B[..., 1] - A[..., 1]) * (C[..., 0] - A[..., 0])
    d1, d2 = cr(Q0, Q1, P0), cr(Q0, Q1, P1)
    d3, d4 = cr(P0, P1, Q0), cr(P0, P1, Q1)
    inter = ((d1 > 0) != (d2 > 0)) & ((d3 > 0) != (d4 > 0))
    return np.where(inter, 0.0, d)


def ok_path(l, pts, net, excl_uuid, excl_pts, hw=W / 2):
    # 折れ線 pts (層 l) が障害物から十分離れているか
    A = np.array(pts[:-1]); B = np.array(pts[1:])
    arr, onet, ouid, cc = OBA[l]
    bx0, by0 = min(p[0] for p in pts) - 1.0, min(p[1] for p in pts) - 1.0
    bx1, by1 = max(p[0] for p in pts) + 1.0, max(p[1] for p in pts) + 1.0
    m = (np.maximum(arr[:, 0], arr[:, 2]) >= bx0) & (np.minimum(arr[:, 0], arr[:, 2]) <= bx1) & \
        (np.maximum(arr[:, 1], arr[:, 3]) >= by0) & (np.minimum(arr[:, 1], arr[:, 3]) <= by1)
    if excl_uuid:
        m &= ~np.isin(ouid, list(excl_uuid))
    same = np.isin(onet, list(net))
    c = cc.copy()
    if same[m].any():
        # 同じネット (ペアなら両方): 区間の端のそばの線・ビア・パッドは見ない。ほかは 0.2 離す
        near = np.zeros(len(arr), bool)
        for q in excl_pts:
            near |= np.minimum(np.hypot(arr[:, 0] - q[0], arr[:, 1] - q[1]), np.hypot(arr[:, 2] - q[0], arr[:, 3] - q[1])) < 0.6
        m &= ~(same & near)
        c = np.where(same, 0.2, c)
    idx = np.nonzero(m)[0]
    if len(idx):
        Q = arr[idx]
        d = segdist(A, B, Q[:, 0:2], Q[:, 2:4])
        if (d < (c[idx] + Q[:, 4] + hw + MARG)[None]).any():
            return False
    # パッドの中に入っていないか (大きいパッド)
    P_ = np.array(pts)
    bbs = PADA[l]
    if len(bbs) == 0:
        return True
    hit = (P_[:, None, 0] >= bbs[None, :, 0]) & (P_[:, None, 0] <= bbs[None, :, 2]) & (P_[:, None, 1] >= bbs[None, :, 1]) & (P_[:, None, 1] <= bbs[None, :, 3])
    for k in np.nonzero(hit.any(axis=0))[0]:
        pa, pn, bb = PADP[l][k]
        if pn in net:
            continue
        for x, y in pts:
            if bb[0] <= x <= bb[2] and bb[1] <= y <= bb[3]:
                xs, ys = pa[:, 0], pa[:, 1]
                inside = False
                for i in range(len(pa)):
                    j = i - 1
                    if (ys[i] > y) != (ys[j] > y) and x < (xs[j] - xs[i]) * (y - ys[i]) / (ys[j] - ys[i] + 1e-30) + xs[i]:
                        inside = not inside
                if inside:
                    return False
    return True


def member_path(a, u, n, o, t0, t1, bumps):
    # 中心線の点 a、向き u、山の向き n。ずれ o の線の折れ線 (t0 から t1 まで)
    def P(s, h):
        return (a[0] + u[0] * s + n[0] * h, a[1] + u[1] * s + n[1] * h)
    pts = [P(t0, o)]
    for s1, s2, h in bumps:
        pts += [P(s1 - o, o), P(s1 - o, h + o), P(s2 + o, h + o), P(s2 + o, o)]
    pts.append(P(t1, o))
    return pts


def candidates(names, lg):
    # 区間の経路の線から、蛇行を入れられる直線 (1 本、またはペアの平行な 2 本) を探す
    segs = [plan[n][lg]['segs'] for n in names]
    out = []
    if len(names) == 1:
        for s in segs[0]:
            a, b = np.array(s['a']), np.array(s['b'])
            L = np.linalg.norm(b - a)
            if L < 1.0:
                continue
            u = (b - a) / L
            out.append({'l': s['l'], 'a': a, 'u': u, 'L': L, 'mem': [(s, 0.0, 0.0)], 'w': s['w']})
    else:
        for sp in segs[0]:
            ap, bp = np.array(sp['a']), np.array(sp['b'])
            Lp = np.linalg.norm(bp - ap)
            if Lp < 1.0:
                continue
            u = (bp - ap) / Lp
            nn = np.array([-u[1], u[0]])
            for sn in segs[1]:
                if sn['l'] != sp['l']:
                    continue
                an, bn = np.array(sn['a']), np.array(sn['b'])
                Ln = np.linalg.norm(bn - an)
                if Ln < 1.0:
                    continue
                un = (bn - an) / Ln
                if abs(abs(un @ u) - 1) > 1e-3:
                    continue
                off_a, off_b = (an - ap) @ nn, (bn - ap) @ nn
                if abs(off_a - off_b) > 0.01 or not (0.2 <= abs(off_a) <= 0.4):
                    continue
                ta, tb = sorted([(an - ap) @ u, (bn - ap) @ u])
                s0, s1 = max(0.0, ta), min(Lp, tb)
                if s1 - s0 < 2.0:
                    continue
                o = off_a / 2
                a = ap + u * s0 + nn * o  # 中心線の始まり
                out.append({'l': sp['l'], 'a': a, 'u': u, 'L': s1 - s0, 'mem': [(sp, -o, None), (sn, o, None)], 'w': sp['w'], 'nn': nn})
    out.sort(key=lambda c: -c['L'])
    return out


def place(names, lg, need, used):
    pair = len(names) == 2
    A_ = 0.75 if pair else 0.45   # 山の上の幅 (中心線)
    G_ = 0.75 if pair else 0.45   # 山と山の間
    E_ = 0.6 if pair else 0.35    # 線の端からの余白
    edits = []
    for c in candidates(names, lg):
        if need <= 0.3:
            break
        if any(m[0]['uuid'] in used for m in c['mem']):
            continue
        L = c['L']
        nb_fit = int((L - 2 * E_ + G_) // (A_ + G_))
        if nb_fit < 1:
            continue
        done = False
        for h in HS:
            if done:
                break
            nb = min(nb_fit, math.ceil(need / (2 * h) - 1e-9))
            last_h = h if nb * 2 * h <= need else need / 2 - (nb - 1) * h
            if last_h < 0.15:
                nb -= 1
                last_h = h
            if nb < 1:
                continue
            span = nb * A_ + (nb - 1) * G_
            gain = 2 * h * (nb - 1) + 2 * last_h
            for side in (1, -1):
                if done:
                    break
                nvec = np.array([-c['u'][1], c['u'][0]]) * side
                st = E_
                while st + span <= L - E_ + 1e-9 and not done:
                    bumps = []
                    s = st
                    for i in range(nb):
                        bumps.append((s, s + A_, last_h if i == nb - 1 else h))
                        s += A_ + G_
                    ok = True
                    paths = []
                    for seg, o, _ in c['mem']:
                        oo = o * side if pair else 0.0  # 山の向きに合わせた符号 (n 側が +)
                        # 中心線の座標 → 線の始まり・終わり (メンバーの線の上)
                        pts = member_path(c['a'], c['u'], nvec, oo, 0.0, L, bumps)
                        # 中心線の始まり・終わりの点を、もとの線の端とつなぐ
                        sa, sb = np.array(seg['a']), np.array(seg['b'])
                        if (sb - sa) @ c['u'] < 0:
                            sa, sb = sb, sa
                        full = [tuple(sa)] + pts + [tuple(sb)]
                        full = [p for i, p in enumerate(full) if i == 0 or math.hypot(p[0] - full[i - 1][0], p[1] - full[i - 1][1]) > 1e-4]
                        excl = {m[0]['uuid'] for m in c['mem']}
                        if not ok_path(c['l'], pts, set(names), excl, [tuple(sa), tuple(sb)], hw=seg['w'] / 2):
                            ok = False
                            break
                        paths.append((seg, full))
                    if ok:
                        done = True
                        edits.append({'names': names, 'gain': gain, 'remove': [p[0]['uuid'] for p in paths],
                                      'add': [[c['l'], p[i][0], p[i][1], p[i + 1][0], p[i + 1][1], seg['w'], seg_net] for (seg, p), seg_net in zip(paths, names) for i in range(len(p) - 1)]})
                        for (seg, p), seg_net in zip(paths, names):
                            used.add(seg['uuid'])
                            for i in range(len(p) - 1):
                                OB[c['l']].append((p[i][0], p[i][1], p[i + 1][0], p[i + 1][1], seg['w'] / 2, seg_net, 'seg', None))
                        rebuild(c['l'])
                        need -= gain
                    st += 0.2
    return edits, need


used = set()
allE, left = [], []
# 長く伸ばすものから
for name, names, lg, need in sorted(req, key=lambda r: -r[3]):
    if any(plan[n].get(lg) is None for n in names):
        left.append((name, need, '未配線'))
        continue
    e, rest = place(names, lg, need, used)
    allE += e
    print(f'{name:10s} {lg:10s} 伸ばす {need:5.1f}  入れた {need - rest:5.1f}  残り {rest:5.1f}', flush=True)
    if rest > (TOL_AC if len(names) == 1 else 0.3):
        left.append((name, round(rest, 2), lg))
json.dump({'edits': allE, 'left': left, 'targets': {'C1': C1t, 'c2': c2t, 'T': T}}, open(OUT, 'w', encoding='utf8'))
print('置き換え', len(allE), ' 足りないまま', len(left), left[:20])
