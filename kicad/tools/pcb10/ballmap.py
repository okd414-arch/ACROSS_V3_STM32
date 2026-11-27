# BGA のボール配置をネットの種類で文字マップにする (2026-11-21)
# usage: python ballmap.py survey.json REF
import sys, json, re

d = json.load(open(sys.argv[1], encoding='utf8'))
ref = sys.argv[2]
f = [f for f in d['fps'] if f['ref'] == ref][0]
xs = sorted(set(p['x'] for p in f['pads']))
ys = sorted(set(p['y'] for p in f['pads']))
code = {}
legend = {}


def c(net):
    if not net:
        return '.'
    rules = [('GND$', 'g'), ('^VDD_CORE', 'C'), ('^VDD_DDR', 'R'), ('^VDD$', 'V'), ('^\\+3\\.3V$', '3'), ('VREF', 'f'), ('VDDA', 'a'),
             ('VDD_USB', 'u'), ('VDD_SD', 's'), ('^DDR_', 'd'), ('^USB', 'U'), ('^ETH', 'e'), ('^LCD', 'l'), ('^EMMC', 'm'), ('^SD_', 'x')]
    for rx, ch in rules:
        if re.search(rx, net):
            return ch
    return 'o'


grid = {(p['x'], p['y']): c(p['net']) for p in f['pads']}
print(ref, len(xs), 'x', len(ys), 'x0', xs[0], 'y0', ys[0])
for y in ys:
    print(f'{y:7.2f} ' + ''.join(grid.get((x, y), ' ') for x in xs))
cnt = {}
for p in f['pads']:
    cnt[p['net']] = cnt.get(p['net'], 0) + 1
print(sorted(((v, k) for k, v in cnt.items() if not re.match('^(DDR_|LCD|ETH|EMMC|SD_)', k or '')), reverse=True)[:30])
