# mr_export.py の JSON から、基板の一部を層ごとの色で PNG に描く (2026-11-22、配線の確認用)
#   F=赤 In2=緑 In5=青 B=紫、パッド=灰 (F) / 薄紫 (B)、ビア=黒い輪。ネット名を指定するとその銅を黄色で強調。
# usage: python mr_plot.py mr.json out.png x0 y0 x1 y1 [--net REGEX] [--labels]
import sys, json, re
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon, Circle

d = json.load(open(sys.argv[1], encoding='utf8'))
out = sys.argv[2]
x0, y0, x1, y1 = map(float, sys.argv[3:7])
NET = re.compile(sys.argv[sys.argv.index('--net') + 1]) if '--net' in sys.argv else None
LAB = '--labels' in sys.argv
COL = ['#d62728', '#2ca02c', '#1f77b4', '#9467bd']
fig, ax = plt.subplots(figsize=(12, 12 * (y1 - y0) / (x1 - x0)), dpi=110)


def inside(x, y, m=1.0):
    return x0 - m <= x <= x1 + m and y0 - m <= y <= y1 + m


for it in d['items']:
    hl = NET and NET.search(it['net'] or '')
    if it['k'] == 'pad':
        if not inside(*it['pos'], 3):
            continue
        for l, polys in it['polys'].items():
            for p in polys:
                ax.add_patch(Polygon(p, closed=True, fc=('#ffd700' if hl else ('#bbbbbb' if l == '0' else '#d8c8ee')), ec='#555555', lw=0.3, zorder=1 if l == '3' else 2))
        if LAB and it['net'] and inside(*it['pos'], 0):
            ax.text(it['pos'][0], it['pos'][1], it['net'][-10:], fontsize=3, ha='center', va='center', zorder=9)
    elif it['k'] == 'seg':
        if not (inside(*it['a']) or inside(*it['b'])):
            continue
        ax.plot([it['a'][0], it['b'][0]], [it['a'][1], it['b'][1]], color='#ffd700' if hl else COL[it['l']],
                lw=it['w'] * 72 * 12 / (x1 - x0) / 25.4 * 25.4, solid_capstyle='round', alpha=0.75, zorder=3 + it['l'] * 0.1)
    elif it['k'] == 'via':
        if not inside(*it['c']):
            continue
        ax.add_patch(Circle(it['c'], it['r'], fc='#ffd700' if hl else 'white', ec='black', lw=0.5, zorder=6))
for j in d.get('jobs', []):
    p, q = j['a']['pts'][0], j['b']['pts'][0]
    if inside(*p, 5) or inside(*q, 5):
        ax.plot([p[0], q[0]], [p[1], q[1]], color='magenta', lw=0.6, ls=':', zorder=8)
ax.set_xlim(x0, x1)
ax.set_ylim(y1, y0)
ax.set_aspect('equal')
ax.grid(True, lw=0.2)
ax.set_title(f'({x0},{y0})-({x1},{y1})  F=red In2=green In5=blue B=purple  ratsnest=magenta', fontsize=8)
plt.savefig(out, bbox_inches='tight')
print('saved', out)
