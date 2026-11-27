# シルク文字 (Reference) の置き場所を探して silk_layout.json を作る (2026-11-23)
# usage: python silk_solve.py silk_obs.json silk_layout.json [--force REF,REF..] [--hide REF,..]
#   silk_obs.json は silk_extract.py の出力。pcbnew は使わない (numpy + PIL)。
#   方式: 0.05mm 格子の占有マップ (パッドのマスク開口・シルク図形・基板外周) を作り、
#   今の位置で問題ない文字はそのまま、問題のある文字だけ部品の周りを探して置き直す。
import sys, json, math
import numpy as np
from PIL import Image, ImageDraw

RES = 0.05            # mm / cell
BW, BH = 160.0, 100.0
H_MIN = 0.78          # 文字高さの下限 (ユーザー指定)
TH_MIN = 0.15         # 線幅の下限 (JLCPCB)
M_PAD = 0.10          # 文字とマスク開口の間隔
M_SILK = 0.10         # 文字とシルク図形・他の文字の間隔
M_EDGE = 0.30         # 基板端からの間隔
SIZES = [1.0, 0.9, 0.8, H_MIN]
SEARCH = 3.0          # 部品の外形からどこまで離して探すか (mm)

args = sys.argv[1:]
src, dst = args[0], args[1]
force = set(); prehide = set()
for i, a in enumerate(args):
    if a == '--force':
        force = set(args[i + 1].split(','))
    if a == '--hide':
        prehide = set(args[i + 1].split(','))
d = json.load(open(src, encoding='utf8'))
NX, NY = int(round(BW / RES)), int(round(BH / RES))


def to_px(p):
    return (p[0] / RES, p[1] / RES)


def new_img():
    return Image.new('L', (NX, NY), 0)


def integral(img):
    a = (np.asarray(img) > 0).astype(np.int32)
    s = np.zeros((NY + 1, NX + 1), np.int32)
    s[1:, 1:] = a.cumsum(0).cumsum(1)
    return s


def rect_cells(x0, y0, x1, y1):
    """mm の矩形 → 格子の範囲 (外側に丸める、はみ出しは端で切る)"""
    i0 = np.clip(np.floor(x0 / RES).astype(int), 0, NX); i1 = np.clip(np.ceil(x1 / RES).astype(int), 0, NX)
    j0 = np.clip(np.floor(y0 / RES).astype(int), 0, NY); j1 = np.clip(np.ceil(y1 / RES).astype(int), 0, NY)
    return i0, j0, i1, j1


def query(S, x0, y0, x1, y1):
    i0, j0, i1, j1 = rect_cells(x0, y0, x1, y1)
    return S[j1, i1] - S[j0, i1] - S[j1, i0] + S[j0, i0]


# ---- 障害物マップ (表裏) ----
hard = {}; body = {}
for s in ('F', 'B'):
    im = new_img(); dr = ImageDraw.Draw(im)
    for o in d['mask'][s]:
        dr.polygon([to_px(p) for p in o['poly']], fill=1, outline=1)
    for o in d['silk'][s]:
        dr.polygon([to_px(p) for p in o['poly']], fill=1, outline=1)
    for o in d['fixedtext'][s]:
        x0, y0, x1, y1 = o['bb']; dr.rectangle([x0 / RES, y0 / RES, x1 / RES, y1 / RES], fill=1)
    hard[s] = im
    # 部品の本体 (コートヤード) : 他の部品の下に文字を置かないための重み
    cy = new_img(); dc = ImageDraw.Draw(cy)
    for f in d['fps']:
        if f['side'] == s and f['courtyard']:
            x0, y0, x1, y1 = f['courtyard']; dc.rectangle([x0 / RES, y0 / RES, x1 / RES, y1 / RES], fill=1)
    body[s] = integral(cy)

# 自部品の本体外形 (パッド + シルク図形の外接矩形)
own = {}
for s in ('F', 'B'):
    for o in d['mask'][s] + d['silk'][s]:
        if not o['owner']:
            continue
        xs = [p[0] for p in o['poly']]; ys = [p[1] for p in o['poly']]
        b = own.setdefault(o['owner'], [1e9, 1e9, -1e9, -1e9])
        b[0] = min(b[0], min(xs)); b[1] = min(b[1], min(ys)); b[2] = max(b[2], max(xs)); b[3] = max(b[3], max(ys))


def text_rect(t, x, y, ang, h, th):
    u = t['unit'][str(int(ang))]
    return (x + u[0] * h - th / 2, y + u[1] * h - th / 2, x + u[2] * h + th / 2, y + u[3] * h + th / 2)


def side_of(t):
    return 'B' if t['layer'].startswith('B') else 'F'


fps = {f['ref']: f for f in d['fps']}
# 現状を正規化 (高さ >= 0.78, 線幅 >= 0.15)
cur = {}
for f in d['fps']:
    t = f['text']
    h = max(t['h'], H_MIN); th = max(t['th'], TH_MIN)
    ang = int(round(t['angle'])) % 180
    cur[f['ref']] = dict(x=t['pos'][0], y=t['pos'][1], angle=ang, h=h, th=th, visible=t['visible'],
                         layer=t['layer'], angle_raw=t['angle'])


def inside_board(r):
    return r[0] >= M_EDGE and r[1] >= M_EDGE and r[2] <= BW - M_EDGE and r[3] <= BH - M_EDGE


# ---- 今の位置で問題がないかを調べる ----
S = {s: integral(hard[s]) for s in ('F', 'B')}
rects = {}
for ref, c in cur.items():
    t = fps[ref]['text']
    if t['angle'] % 90:
        raise SystemExit('unexpected angle ' + ref)
    rects[ref] = text_rect(t, c['x'], c['y'], c['angle'], c['h'], c['th'])
bad = set()
for ref, c in cur.items():
    if not c['visible']:
        bad.add(ref); continue
    r = rects[ref]; s = side_of(fps[ref]['text'])
    if ref in force or not inside_board(r):
        bad.add(ref); continue
    m = M_PAD
    if query(S[s], r[0] - m, r[1] - m, r[2] + m, r[3] + m) > 0:
        bad.add(ref)
# 文字同士
refs = list(cur)
for i, a in enumerate(refs):
    for b2 in refs[i + 1:]:
        if not (cur[a]['visible'] and cur[b2]['visible']):
            continue
        if side_of(fps[a]['text']) != side_of(fps[b2]['text']):
            continue
        ra, rb = rects[a], rects[b2]; m = M_SILK
        if ra[0] < rb[2] + m and rb[0] < ra[2] + m and ra[1] < rb[3] + m and rb[1] < ra[3] + m:
            bad.add(a); bad.add(b2)
print('keep', len(cur) - len(bad), 'replace', len(bad))

# 動かさない文字を障害物に入れる
for ref, c in cur.items():
    if ref in bad or not c['visible']:
        continue
    s = side_of(fps[ref]['text']); r = rects[ref]
    ImageDraw.Draw(hard[s]).rectangle([r[0] / RES, r[1] / RES, r[2] / RES - 1e-6, r[3] / RES - 1e-6], fill=1)
S = {s: integral(hard[s]) for s in ('F', 'B')}


def gap(r, b):
    dx = max(b[0] - r[2], r[0] - b[2], 0); dy = max(b[1] - r[3], r[1] - b[3], 0)
    return np.hypot(dx, dy)


def place(ref):
    f = fps[ref]; t = f['text']; s = side_of(t)
    ob = own.get(ref) or f['fpbb']
    c = cur[ref]
    h0 = min(max(c['h'], H_MIN), 1.0)
    th = TH_MIN
    fp_vert = int(round(f['rot'])) % 180 == 90
    # 近くの他部品の本体
    others = [own[o] for o in own if o != ref and fps.get(o) and fps[o]['side'] == f['side']
              and own[o][0] < ob[2] + SEARCH + 4 and own[o][2] > ob[0] - SEARCH - 4
              and own[o][1] < ob[3] + SEARCH + 4 and own[o][3] > ob[1] - SEARCH - 4]
    best = None; ngood = 0
    sizes = [x for x in SIZES if x <= h0 + 1e-9]
    if not sizes or sizes[0] < h0 - 1e-9:
        sizes = [h0] + sizes
    for h in sizes:
        for ang in (0, 90):
            u = t['unit'][str(ang)]
            w0 = (u[2] - u[0]) * h + th; hh = (u[3] - u[1]) * h + th
            ext = max(w0, hh)
            xs = np.arange(ob[0] - SEARCH - ext, ob[2] + SEARCH + ext, 0.05)
            ys = np.arange(ob[1] - SEARCH - ext, ob[3] + SEARCH + ext, 0.05)
            X, Y = np.meshgrid(xs, ys)
            x0 = X + u[0] * h - th / 2; y0 = Y + u[1] * h - th / 2
            x1 = X + u[2] * h + th / 2; y1 = Y + u[3] * h + th / 2
            ok = (x0 >= M_EDGE) & (y0 >= M_EDGE) & (x1 <= BW - M_EDGE) & (y1 <= BH - M_EDGE)
            m = max(M_PAD, M_SILK)
            q = query(S[s], x0 - m, y0 - m, x1 + m, y1 + m)
            ok &= (q == 0)
            if not ok.any():
                continue
            dx = np.maximum(np.maximum(ob[0] - x1, x0 - ob[2]), 0)
            dy = np.maximum(np.maximum(ob[1] - y1, y0 - ob[3]), 0)
            g = np.hypot(dx, dy)
            ok &= g <= SEARCH
            if not ok.any():
                continue
            # 他部品の本体の下に入る割合
            area = (np.ceil(x1 / RES) - np.floor(x0 / RES)) * (np.ceil(y1 / RES) - np.floor(y0 / RES))
            cov = query(body[s], x0, y0, x1, y1) / np.maximum(area, 1)
            cyo = f['courtyard'] or ob
            ix = np.clip(np.minimum(x1, cyo[2]) - np.maximum(x0, cyo[0]), 0, None)
            iy = np.clip(np.minimum(y1, cyo[3]) - np.maximum(y0, cyo[1]), 0, None)
            cov = np.clip(cov - ix * iy / np.maximum((x1 - x0) * (y1 - y0), 1e-6), 0, 1)
            # 他部品の方が近い (どの部品の文字か紛らわしい)
            amb = np.zeros_like(g)
            for o in others:
                dxo = np.maximum(np.maximum(o[0] - x1, x0 - o[2]), 0)
                dyo = np.maximum(np.maximum(o[1] - y1, y0 - o[3]), 0)
                go = np.hypot(dxo, dyo)
                amb = np.maximum(amb, np.clip(g - go + 0.1, 0, None))
            cost = g * 1.0 + cov * 3.0 + amb * 2.0 + (h0 - h) * 4.0
            if (ang == 90) != fp_vert:
                cost = cost + 0.4
            # 元の位置に近いほど少し良い
            cost = cost + 0.02 * np.hypot(X - c['x'], Y - c['y'])
            cost = np.where(ok, cost, np.inf)
            ngood += int((cost < 1.0).sum())
            k = np.unravel_index(np.argmin(cost), cost.shape)
            cv = cost[k]
            if best is None or cv < best[0]:
                best = (float(cv), float(X[k]), float(Y[k]), ang, h, th,
                        (float(x0[k]), float(y0[k]), float(x1[k]), float(y1[k])), float(g[k]), float(cov[k]), float(amb[k]))
    return best, ngood


# 難しい順 (良い置き場所が少ない部品から) に置く
diff = {}
for ref in bad:
    if ref in prehide:
        diff[ref] = -1; continue
    bst, ng = place(ref)
    diff[ref] = ng if bst is not None else -1
order = sorted(bad, key=lambda r: diff[r])
result = {}
hidden = []
for ref in order:
    if ref in prehide:
        hidden.append(ref); continue
    bst, _ = place(ref)
    if bst is None:
        hidden.append(ref); continue
    cv, x, y, ang, h, th, r, g, cov, amb = bst
    s = side_of(fps[ref]['text'])
    ImageDraw.Draw(hard[s]).rectangle([r[0] / RES, r[1] / RES, r[2] / RES - 1e-6, r[3] / RES - 1e-6], fill=1)
    S[s] = integral(hard[s])
    result[ref] = dict(x=x, y=y, angle=ang, h=h, th=th, cost=cv, gap=g, cov=cov, amb=amb)

out = {'_note': 'apply_silk.py 用。部品番号ごとの Reference 文字。dx,dy は部品原点からの位置 (mm, 基板座標)。angle は基板上の絶対角度。',
       'refs': {}}
for ref in sorted(cur, key=lambda r: (r.rstrip('0123456789'), int(''.join(ch for ch in r if ch.isdigit()) or 0))):
    f = fps[ref]; c = cur[ref]
    if ref in result:
        r = result[ref]
        e = dict(x=round(r['x'], 4), y=round(r['y'], 4), angle=r['angle'], h=r['h'], th=r['th'], visible=True, changed='moved',
                 q=[round(r['gap'], 2), round(r['cov'], 2), round(r['amb'], 2)])
    elif ref in hidden:
        e = dict(x=round(c['x'], 4), y=round(c['y'], 4), angle=int(round(c['angle_raw'])), h=c['h'], th=c['th'], visible=False,
                 changed='hidden')
    else:
        e = dict(x=round(c['x'], 4), y=round(c['y'], 4), angle=int(round(c['angle_raw'])), h=c['h'], th=c['th'], visible=c['visible'],
                 changed='' if (abs(c['h'] - f['text']['h']) < 1e-6 and abs(c['th'] - f['text']['th']) < 1e-6) else 'size')
    e['layer'] = c['layer']
    e['fp'] = [round(f['pos'][0], 4), round(f['pos'][1], 4), round(f['rot'], 2)]
    e['dx'] = round(e['x'] - f['pos'][0], 4); e['dy'] = round(e['y'] - f['pos'][1], 4)
    out['refs'][ref] = e
json.dump(out, open(dst, 'w', encoding='utf8'), ensure_ascii=False, indent=1)
print('moved', len(result), 'hidden', len(hidden), sorted(hidden))
for ref in sorted(result, key=lambda r: -result[r]['cost'])[:25]:
    r = result[ref]
    print('  %-6s h=%.2f a=%d gap=%.2f cov=%.2f amb=%.2f cost=%.2f' % (ref, r['h'], r['angle'], r['gap'], r['cov'], r['amb'], r['cost']))
