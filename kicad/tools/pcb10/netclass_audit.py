# Default クラスのネットのうち、電源系の部品 (インダクタ・ダイオード・FB・電源IC・入力コネクタ) につながるものを出す (2026-11-21)
# usage: python netclass_audit.py survey.json
import sys, json, re

d = json.load(open(sys.argv[1], encoding='utf8'))
pro = json.load(open('C:/MyWorks/ACROSS_V3_STM32/kicad/ACROSS_V3.kicad_pro', encoding='utf8'))
assigned = {p['pattern'] for p in pro['net_settings']['netclass_patterns']}
pins = {}
for f in d['fps']:
    for p in f['pads']:
        if p['net']:
            pins.setdefault(p['net'], []).append((f['ref'], p['n'], f['val']))
PWR_REF = re.compile(r'^(L\d|FB\d|D\d|F\d|U10[1-4]|U601|U609|U705|U706|J101|Q\d)')
for n, L in sorted(pins.items()):
    if n in assigned or n.startswith('unconnected') or n in ('GND', 'GND_A', 'GND_D'):
        continue
    hit = [f'{r}.{pn}' for r, pn, v in L if PWR_REF.match(r)]
    if hit:
        print(f'{n:60s} {len(L):3d}  ' + ' '.join(f'{r}.{pn}' for r, pn, v in L)[:150])
