# 基板全体の配線の図に、遠回りの場所を番号つきで描く (2026-11-26)
#   detour_local.py の結果 (path つき) を読む。全部の線は薄く (層ごとの色)、遠回りの道は太い赤紫、番号の丸を置く。
#   右に番号の一覧 (ネット・区間・道の長さ/直線)。上から見た図 (裏の部品も表から透かして見た向き)。
# usage: python detour_map.py pcb local.json out.png [px/mm]
import sys, json
import pcbnew
from PIL import Image, ImageDraw, ImageFont

b = pcbnew.LoadBoard(sys.argv[1]); T = pcbnew.ToMM
res = json.load(open(sys.argv[2], encoding='utf8'))
S = float(sys.argv[4]) if len(sys.argv) > 4 else 12
eb = b.GetBoardEdgesBoundingBox()
x0, y0, x1, y1 = T(eb.GetLeft()) - 2, T(eb.GetTop()) - 2, T(eb.GetRight()) + 2, T(eb.GetBottom()) + 2
W, H = int((x1 - x0) * S), int((y1 - y0) * S)
PANEL = 800
im = Image.new('RGB', (W + PANEL, max(H, 60 + 30 * len(res))), 'white')
d = ImageDraw.Draw(im)
try:
    F = ImageFont.truetype('C:/Windows/Fonts/meiryo.ttc', 18); FB = ImageFont.truetype('C:/Windows/Fonts/meiryob.ttc', 16)
except OSError:
    F = FB = ImageFont.load_default()


def P(x, y):
    return ((x - x0) * S, (y - y0) * S)


# 外形
for dw in b.GetDrawings():
    if dw.GetLayer() == pcbnew.Edge_Cuts:
        bb = dw.GetBoundingBox()
        d.rectangle([P(T(eb.GetLeft()), T(eb.GetTop())), P(T(eb.GetRight()), T(eb.GetBottom()))], outline=(0, 0, 0), width=2)
        break
# パッド
for p in b.GetPads():
    bb = p.GetBoundingBox()
    d.rectangle([P(T(bb.GetLeft()), T(bb.GetTop())), P(T(bb.GetRight()), T(bb.GetBottom()))], fill=(225, 225, 225))
# 全部の線 (薄く)
col = {'F.Cu': (240, 170, 170), 'B.Cu': (160, 200, 240), 'In2.Cu': (235, 205, 140), 'In5.Cu': (195, 175, 230)}
for t in b.GetTracks():
    if t.Type() == pcbnew.PCB_VIA_T:
        continue
    c = col.get(b.GetLayerName(t.GetLayer()))
    if not c:
        continue
    d.line([P(T(t.GetStart().x), T(t.GetStart().y)), P(T(t.GetEnd().x), T(t.GetEnd().y))], fill=c, width=max(1, int(T(t.GetWidth()) * S)))
# 部品番号 (主な IC だけ)
for f in b.GetFootprints():
    r = f.GetReference()
    if r[:1] in 'UJ' and len(f.Pads()) >= 6:
        bb = f.GetBoundingBox(False)
        d.text(P(T(bb.GetLeft()), T(bb.GetTop()) - 1.6), r, fill=(90, 90, 90), font=FB)
# 遠回りの道
HL = (200, 0, 150)
for r in res:
    pts = [P(x, y) for x, y in r.get('path', [])]
    if len(pts) > 1:
        d.line(pts, fill=HL, width=max(3, int(0.35 * S)), joint='curve')
# 番号の丸 (重なるときは少しずらす)
placed = []
for k, r in enumerate(res, 1):
    cx, cy = P(*r['at'])
    for _ in range(12):
        if all((cx - a) ** 2 + (cy - b_) ** 2 > 30 ** 2 for a, b_ in placed):
            break
        cy -= 26
    placed.append((cx, cy))
    R = 13
    loop = len(r['flags']) > 1
    d.ellipse([cx - R, cy - R, cx + R, cy + R], fill=(255, 255, 255), outline=(220, 0, 0) if loop else HL, width=3)
    s = str(k)
    tw = d.textlength(s, font=FB)
    d.text((cx - tw / 2, cy - 11), s, fill=(0, 0, 0), font=FB)
# 一覧
X = W + 20
d.text((X, 14), f'遠回り {len(res)} か所 (赤紫の線が遠回りの道。赤い丸は輪・折り返しもある所)', fill=(0, 0, 0), font=F)
for k, r in enumerate(res, 1):
    y = 50 + (k - 1) * 30
    net = r['net'] if len(r['net']) <= 24 else r['net'].split('/')[-1][-23:]
    d.text((X, y), f"{k:2d}. {net}", fill=(0, 0, 0), font=F)
    d.text((X + 360, y), f"{r['a']}→{r['b']}  {r['L']}/{r['S']}mm", fill=(80, 80, 80), font=F)
d.text((X, 50 + len(res) * 30 + 10), '色: 赤=表 黄=In2 紫=In5 青=裏 (線の道/直線の長さ)', fill=(80, 80, 80), font=F)
im.save(sys.argv[3])
print('保存', sys.argv[3], im.size)
