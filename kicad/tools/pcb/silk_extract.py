# シルク配置探索用に、基板から障害物と文字情報を JSON に書き出す (2026-11-23)
# usage: python silk_extract.py pcb out.json
#   パッド (マスク開口)、シルク図形 (ポリゴン化)、基板外形、各部品の Reference 文字の情報
import sys, json
import pcbnew

pcb, out = sys.argv[1], sys.argv[2]
b = pcbnew.LoadBoard(pcb)
MM = 1e-6
F_SILK, B_SILK = pcbnew.F_SilkS, pcbnew.B_SilkS
F_CU, B_CU = pcbnew.F_Cu, pcbnew.B_Cu
F_MASK, B_MASK = pcbnew.F_Mask, pcbnew.B_Mask


def polys_of(ps):
    res = []
    for i in range(ps.OutlineCount()):
        o = ps.Outline(i)
        res.append([(o.CPoint(k).x * MM, o.CPoint(k).y * MM) for k in range(o.PointCount())])
    return res


def shape_polys(item, layer):
    ps = pcbnew.SHAPE_POLY_SET()
    item.TransformShapeToPolygon(ps, layer, 0, 5000, pcbnew.ERROR_OUTSIDE)
    return polys_of(ps)


def bbox(it):
    bb = it.GetBoundingBox()
    return [bb.GetLeft() * MM, bb.GetTop() * MM, bb.GetRight() * MM, bb.GetBottom() * MM]


data = {'silk': {'F': [], 'B': []}, 'mask': {'F': [], 'B': []}, 'fixedtext': {'F': [], 'B': []},
        'fps': [], 'edge': None}

# 基板外形
ol = pcbnew.SHAPE_POLY_SET()
b.GetBoardPolygonOutlines(ol, True)
data['edge'] = polys_of(ol)
for i in range(ol.OutlineCount()):
    for h in range(ol.HoleCount(i)):
        hp = ol.Hole(i, h)
        data.setdefault('edge_holes', []).append([(hp.CPoint(k).x * MM, hp.CPoint(k).y * MM) for k in range(hp.PointCount())])

side = {F_SILK: 'F', B_SILK: 'B'}

# 基板直下のシルク図形・文字
for d in b.GetDrawings():
    L = d.GetLayer()
    if L in side:
        if isinstance(d, (pcbnew.PCB_TEXT,)) or d.GetClass() in ('PCB_TEXT', 'PCB_TEXTBOX'):
            data['fixedtext'][side[L]].append({'owner': '', 'bb': bbox(d)})
        else:
            for p in shape_polys(d, L):
                data['silk'][side[L]].append({'owner': '', 'poly': p})
    elif L in (F_MASK, B_MASK):
        s = 'F' if L == F_MASK else 'B'
        for p in shape_polys(d, L):
            data['mask'][s].append({'owner': '', 'poly': p})

for fp in b.GetFootprints():
    ref = fp.GetReference()
    fside = 'B' if fp.IsFlipped() else 'F'
    # フットプリント内シルク図形
    for g in fp.GraphicalItems():
        L = g.GetLayer()
        if L not in side:
            if L in (F_MASK, B_MASK):
                s = 'F' if L == F_MASK else 'B'
                for p in shape_polys(g, L):
                    data['mask'][s].append({'owner': ref, 'poly': p})
            continue
        if g.GetClass() in ('PCB_TEXT', 'MTEXT', 'FP_TEXT', 'PCB_TEXTBOX'):
            if g.IsVisible() if hasattr(g, 'IsVisible') else True:
                data['fixedtext'][side[L]].append({'owner': ref, 'bb': bbox(g)})
            continue
        for p in shape_polys(g, L):
            data['silk'][side[L]].append({'owner': ref, 'poly': p})
    # パッドのマスク開口
    for pad in fp.Pads():
        for L, s in ((F_MASK, 'F'), (B_MASK, 'B')):
            if pad.IsOnLayer(L):
                for p in shape_polys(pad, L):
                    data['mask'][s].append({'owner': ref, 'pad': pad.GetNumber(), 'poly': p})
    # 他のフィールド (Value など) でシルクに見えているもの
    for f in fp.GetFields():
        if f.IsReference():
            continue
        if f.IsVisible() and f.GetLayer() in side:
            data['fixedtext'][side[f.GetLayer()]].append({'owner': ref, 'bb': bbox(f), 'field': f.GetName()})
    r = fp.Reference()
    # 文字の素の外形: 高さ 10mm・細線で角度 0/90 の線の外形 (位置基準・高さ 1 あたり) を測る (保存しない)
    ang0 = r.GetTextAngleDegrees()
    sz0 = r.GetTextSize(); th0 = r.GetTextThickness(); pos0 = r.GetPosition()
    unit = {}
    for a in (0, 90):
        r.SetTextAngleDegrees(a)
        r.SetTextSize(pcbnew.VECTOR2I(pcbnew.FromMM(10.0), pcbnew.FromMM(10.0)))
        r.SetTextThickness(pcbnew.FromMM(0.1))
        e = r.GetEffectiveTextShape(False).BBox()
        unit[str(a)] = [(e.GetLeft() - pos0.x) * MM / 10 + 0.005, (e.GetTop() - pos0.y) * MM / 10 + 0.005,
                        (e.GetRight() - pos0.x) * MM / 10 - 0.005, (e.GetBottom() - pos0.y) * MM / 10 - 0.005]
    r.SetTextAngleDegrees(ang0); r.SetTextSize(sz0); r.SetTextThickness(th0)
    e = r.GetEffectiveTextShape(False).BBox()
    effbb = [e.GetLeft() * MM, e.GetTop() * MM, e.GetRight() * MM, e.GetBottom() * MM]
    cy = fp.GetCourtyard(pcbnew.F_CrtYd if fside == 'F' else pcbnew.B_CrtYd)
    cyb = None
    if cy.OutlineCount():
        bbc = cy.BBox()
        cyb = [bbc.GetLeft() * MM, bbc.GetTop() * MM, bbc.GetRight() * MM, bbc.GetBottom() * MM]
    data['fps'].append({
        'ref': ref, 'side': fside, 'pos': [fp.GetPosition().x * MM, fp.GetPosition().y * MM],
        'rot': fp.GetOrientationDegrees(), 'fpbb': bbox(fp), 'courtyard': cyb,
        'lib': str(fp.GetFPID().GetLibItemName()),
        'text': {'visible': r.IsVisible(), 'layer': r.GetLayerName(), 'pos': [r.GetPosition().x * MM, r.GetPosition().y * MM],
                 'angle': ang0, 'h': sz0.y * MM, 'w': sz0.x * MM, 'th': th0 * MM, 'bb': bbox(r),
                 'unit': unit, 'effbb': effbb, 'mirror': r.IsMirrored(), 'nchar': len(r.GetShownText(False))},
    })

json.dump(data, open(out, 'w', encoding='utf8'))
print('fps', len(data['fps']), 'silkF', len(data['silk']['F']), 'silkB', len(data['silk']['B']),
      'maskF', len(data['mask']['F']), 'maskB', len(data['mask']['B']), 'edge', len(data['edge']))
