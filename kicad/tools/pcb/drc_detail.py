# drc_sum.py が書いた JSON (temp/drc_sum.json) から、指定の種類の違反を全部と、未接続のネットを出す (2026-11-22)
# usage: python drc_detail.py [type,type...] [--unconn]
import sys, json, os, tempfile, collections, re

d = json.load(open(os.path.join(tempfile.gettempdir(), 'drc_sum.json'), encoding='utf8'))
types = set(sys.argv[1].split(',')) if len(sys.argv) > 1 and not sys.argv[1].startswith('--') else set()
for v in d['violations']:
    if v['type'] in types:
        print(v['type'], '|', v['description'], '|', ' / '.join(f"{i['description']} @({i['pos']['x']:.2f},{i['pos']['y']:.2f})" for i in v['items']))
if '--unconn' in sys.argv:
    c = collections.Counter()
    for v in d['unconnected_items']:
        m = re.search(r'\[([^\]]+)\]', v['items'][0]['description'])
        c[m.group(1) if m else '?'] += 1
    print('未接続', sum(c.values()))
    print('  ' + '  '.join(f'{k}:{n}' for k, n in c.most_common()))
if '--hole' in sys.argv:
    vals = [float(re.search(r'現状 ([\d.]+)', v['description']).group(1)) for v in d['violations'] if v['type'] == 'hole_clearance']
    print('hole_clearance 最小', min(vals) if vals else '-', '件数', len(vals))
