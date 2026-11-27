# シルク配置の確認画像 (2026-11-23)  usage: python silk_view.py obs.json layout.json side x0 y0 x1 y1 out.png
import json, sys
from PIL import Image, ImageDraw
d = json.load(open(sys.argv[1], encoding='utf8')); L = json.load(open(sys.argv[2], encoding='utf8'))['refs']
s = sys.argv[3]; x0, y0, x1, y1 = map(float, sys.argv[4:8]); out = sys.argv[8]
K = float(sys.argv[9]) if len(sys.argv) > 9 else 40
im = Image.new('RGB', (int((x1 - x0) * K), int((y1 - y0) * K)), 'white'); dr = ImageDraw.Draw(im)
P = lambda p: ((p[0] - x0) * K, (p[1] - y0) * K)
fps = {f['ref']: f for f in d['fps']}
for f in d['fps']:
    if f['side'] == s and f['courtyard']:
        c = f['courtyard']; dr.rectangle([P(c[:2]), P(c[2:])], outline=(200, 200, 255))
for o in d['mask'][s]:
    dr.polygon([P(p) for p in o['poly']], fill=(230, 160, 60))
for o in d['silk'][s]:
    dr.polygon([P(p) for p in o['poly']], fill=(60, 60, 60))
for ref, e in L.items():
    f = fps[ref]
    if f['side'] != s and e['layer'][0] != s:
        continue
    u = f['text']['unit'][str(int(e['angle']) % 180)]; h = e['h']; th = e['th']
    r = (e['x'] + u[0] * h - th / 2, e['y'] + u[1] * h - th / 2, e['x'] + u[2] * h + th / 2, e['y'] + u[3] * h + th / 2)
    col = (220, 0, 0) if e['changed'] == 'moved' else (0, 150, 0)
    if not e['visible']:
        col = (180, 180, 180)
    dr.rectangle([P(r[:2]), P(r[2:])], outline=col, width=2)
    dr.text(P((r[0], r[1])), ref, fill=col)
    dr.line([P(f['pos']), P((e['x'], e['y']))], fill=(255, 150, 150))
im.save(out)
