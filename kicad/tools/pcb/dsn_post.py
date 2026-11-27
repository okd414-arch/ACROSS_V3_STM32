# KiCad の DSN を Freerouting 用に加工する (2026-11-21)
#   1. 絶縁: ISO_A / ISO_D / ISO_C を含むクラスと、それを含まないクラスの間に 2mm (class_class)
#   2. DDR のクラスは F.Cu / In2.Cu (L3) / In5.Cu (L6) だけを使う (use_layer)
#   3. 面: 大きい面 (VDD、+3.3V) に、島 (VDD_DDR、VDD_CORE) の形の穴 (window) を開ける
#   4. Freerouting の設定 (autoroute_settings): 層ごとの優先方向 (F 横、In2 縦、In5 横、B 縦) とコスト
# usage: python dsn_post.py in.dsn out.dsn [--only NETREGEX] [--fanout]
import sys, re, argparse

ap = argparse.ArgumentParser()
ap.add_argument('inp')
ap.add_argument('out')
ap.add_argument('--against', type=float, default=3.0, help='優先方向に逆らう配線のコスト倍率')
ap.add_argument('--fanout', action='store_true')
ap.add_argument('--skip', default='', help='外す加工 (カンマ区切り: cc,layer,window,ars)')
a = ap.parse_args()
SKIP = set(a.skip.split(','))
t = open(a.inp, encoding='utf8').read()

# --- 2. DDR の層の制限
DDR_LAYERS = 'F.Cu In2.Cu In5.Cu'


def add_use_layer(m):
    blk = m.group(0)
    if 'use_layer' in blk:
        return blk
    return blk.replace('(circuit', f'(circuit\n        (use_layer {DDR_LAYERS})', 1)


if 'layer' not in SKIP:
    t = re.sub(r'\(class DDR_(DATA|ADDR|DIFF)\b.*?\(circuit', add_use_layer, t, flags=re.S)

# --- 1. 絶縁の class_class
names = re.findall(r'\(class ("[^"]+"|\S+)', t)
names = [n for n in names if n != 'class']
cc = []
for g in ('ISO_A', 'ISO_D', 'ISO_C'):
    inside = [n for n in names if g in n.strip('"').split(',')]
    outside = [n for n in names if g not in n.strip('"').split(',')]
    for i in inside:
        for o in outside:
            cc.append(f'    (class_class (classes {i} {o})\n      (rule (clearance 2000))\n    )')
if 'cc' not in SKIP:
    net_end = t.rfind('(wiring')
    net_close = t.rfind(')', 0, net_end)  # (network ...) の閉じ括弧
    t = t[:net_close] + '\n' + '\n'.join(cc) + '\n  ' + t[net_close:]

# --- 3. 面の穴
planes = {}
for m in re.finditer(r'\(plane (\S+) \(polygon (\S+) 0 ([-\d\s.]+)\)\)', t):
    planes.setdefault(m.group(2), []).append((m.group(1), m.group(3), m.group(0)))
# Freerouting は window を読めない (読み込みが止まる) ので、島の右辺から外周の x=107 の辺まで
# 幅 0.2mm の切れ目を入れて、穴のない 1 本の多角形にする (DSN の座標は y が負)
HOLES = {('In3.Cu', 'VDD'): 'VDD_DDR', ('In4.Cu', '+3.3V'): 'VDD_CORE'}
SLIT_Y = -50000.0  # 切れ目の y (DSN 座標)
SLIT_W = 200.0


def pts_of(s):
    v = [float(x) for x in s.split()]
    p = list(zip(v[0::2], v[1::2]))
    if p[0] == p[-1]:
        p = p[:-1]
    return p


def area(p):
    return sum(p[i][0] * p[(i + 1) % len(p)][1] - p[(i + 1) % len(p)][0] * p[i][1] for i in range(len(p))) / 2


def insert_on_vertical_edge(p, x, y):
    """多角形 p の、x の縦の辺で y を含むものを探し、その辺の index を返す"""
    for i in range(len(p)):
        a, b = p[i], p[(i + 1) % len(p)]
        if abs(a[0] - x) < 1 and abs(b[0] - x) < 1 and min(a[1], b[1]) < y < max(a[1], b[1]):
            return i
    raise ValueError(f'縦の辺が見つからない x={x} y={y}')


def keyhole(outer, island):
    xi = max(q[0] for q in island)  # 島の右辺
    xo = 107000.0  # 外周の x=107 の辺 (A の左)
    if area(outer) * area(island) > 0:
        island = island[::-1]  # 外周と逆回り
    io = insert_on_vertical_edge(outer, xo, SLIT_Y)
    ii = insert_on_vertical_edge(island, xi, SLIT_Y)
    a, b = outer[io], outer[(io + 1) % len(outer)]
    down = b[1] < a[1]  # 外周の辺の向き (y が減る = DSN で下向き)
    y1, y2 = (SLIT_Y + SLIT_W / 2, SLIT_Y - SLIT_W / 2) if down else (SLIT_Y - SLIT_W / 2, SLIT_Y + SLIT_W / 2)
    # 島を、切れ目の 1 本目の点から 1 周してもとの辺の 2 本目の点まで
    ring = []
    n = len(island)
    ia, ib = island[ii], island[(ii + 1) % n]
    # 島の辺 ia→ib 上で、切れ目の 2 点を辺の向きに合わせる
    if (ib[1] - ia[1]) * (y2 - y1) > 0:
        s_in, s_out = (xi, y2), (xi, y1)  # 入る点は辺の先の方
    else:
        s_in, s_out = (xi, y1), (xi, y2)
    ring.append(s_in)
    k = (ii + 1) % n
    for _ in range(n):
        ring.append(island[k])
        k = (k + 1) % n
    ring.append(s_out)
    # 並び: 外周 a → (xo, 入る y) → 島を 1 周 → (xo, 出る y) → 外周 b。入る点は外周の辺で a に近い方
    assert abs(ring[0][1] - a[1]) < abs(ring[-1][1] - a[1]), '切れ目の順序が逆 (多角形の向きを確認)'
    return outer[:io + 1] + [(xo, ring[0][1])] + ring + [(xo, ring[-1][1])] + outer[io + 1:]


for (lay, base), isl in ([] if 'window' in SKIP else HOLES.items()):
    L = planes.get(lay, [])
    bp = [p for p in L if p[0] == base]
    ip = [p for p in L if p[0] == isl]
    if not bp or not ip:
        print('面が見つからない', lay, base, isl)
        continue
    poly = keyhole(pts_of(bp[0][1]), pts_of(ip[0][1]))
    poly.append(poly[0])
    s = '  '.join(f'{x:g} {y:g}' for x, y in poly)
    assert t.count(bp[0][2]) == 1
    t = t.replace(bp[0][2], f'(plane {base} (polygon {lay} 0  {s}))', 1)
    print('keyhole', lay, base, '-', isl, len(poly), 'pts')

# --- 4. autoroute_settings
dirs = {'F.Cu': 'horizontal', 'In2.Cu': 'vertical', 'In5.Cu': 'horizontal', 'B.Cu': 'vertical'}
lr = []
for lay in ('F.Cu', 'In1.Cu', 'In2.Cu', 'In3.Cu', 'In4.Cu', 'In5.Cu', 'In6.Cu', 'B.Cu'):
    if lay in dirs:
        lr.append(f'''      (layer_rule {lay}
        (active on)
        (preferred_direction {dirs[lay]})
        (preferred_direction_trace_costs 1.0)
        (against_preferred_direction_trace_costs {a.against})
      )''')
    else:
        lr.append(f'''      (layer_rule {lay}
        (active off)
        (preferred_direction horizontal)
        (preferred_direction_trace_costs 1.0)
        (against_preferred_direction_trace_costs 1.0)
      )''')
ars = f'''    (autoroute_settings
      (fanout {'on' if a.fanout else 'off'})
      (autoroute on)
      (postroute on)
      (vias on)
      (via_costs 50)
      (plane_via_costs 5)
      (start_ripup_costs 100)
      (start_pass_no 1)
{chr(10).join(lr)}
    )
'''
# DSN の structure に書くと読み込みが止まるので、-dr で渡すルールファイルにする
rules_path = re.sub(r'\.dsn$', '', a.out) + '.rules'
if 'ars' not in SKIP:
    dname = re.sub(r'\.dsn$', '', a.out.replace('\\', '/').split('/')[-1])  # 設計名は DSN のファイル名と一致させる
    open(rules_path, 'w', encoding='utf8').write(f'(rules PCB {dname}\n  (snap_angle\n    fortyfive_degree\n  )\n{ars})\n')
    print('rules', rules_path)
open(a.out, 'w', encoding='utf8').write(t)
print('classes', len(names), 'class_class', len(cc), 'ddr use_layer', t.count('use_layer'))
