# シルク文字 (Reference) の配置データを基板に書き込む (2026-11-23)
# usage: python apply_silk.py [pcb] [--layout silk_layout.json] [-o out.kicad_pcb] [--dry]
#   pcb 省略時は本番 kicad/ACROSS_V3.kicad_pcb。-o 省略時は上書き保存。
#   部品番号ごとに 位置・角度・文字高さ・線幅・層 (表裏)・表示/非表示 を設定する。部品は動かさない。
#   位置は「部品原点 + (dx, dy)」で決めるので、部品が少し動いていても文字は部品について行く。
#   データ作成時から部品が動いた/回った部品は警告を出す (その部品は DRC で確認すること)。
import sys, os, json
import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
KICAD = os.path.dirname(os.path.dirname(HERE))
args = sys.argv[1:]
pcb = os.path.join(KICAD, 'ACROSS_V3.kicad_pcb')
layout = os.path.join(HERE, 'silk_layout.json')
out = None; dry = False
i = 0
while i < len(args):
    a = args[i]
    if a == '--layout':
        layout = args[i + 1]; i += 2; continue
    if a == '-o':
        out = args[i + 1]; i += 2; continue
    if a == '--dry':
        dry = True; i += 1; continue
    pcb = a; i += 1
out = out or pcb

J = json.load(open(layout, encoding='utf8'))
L = J['refs']
CLIP = J.get('clip_graphics', {})
b = pcbnew.LoadBoard(pcb)
mm = pcbnew.FromMM
n_set = n_hide = 0
warn = []
seen = set()
for fp in b.GetFootprints():
    ref = fp.GetReference()
    e = L.get(ref)
    if e is None:
        warn.append('データなし: ' + ref)
        continue
    seen.add(ref)
    px, py = fp.GetPosition().x / 1e6, fp.GetPosition().y / 1e6
    rot = fp.GetOrientationDegrees()
    if abs(px - e['fp'][0]) > 0.01 or abs(py - e['fp'][1]) > 0.01 or abs(((rot - e['fp'][2]) + 180) % 360 - 180) > 0.1:
        warn.append('部品が動いている: %s (%.3f,%.3f,%.1f) → データ作成時 %s' % (ref, px, py, rot, e['fp']))
    side_now = 'B' if fp.IsFlipped() else 'F'
    if e['layer'][0] != side_now:
        warn.append('表裏が違う: %s 今 %s, データ %s (層は今の面に合わせる)' % (ref, side_now, e['layer']))
    t = fp.Reference()
    t.SetLayer(pcbnew.F_SilkS if side_now == 'F' else pcbnew.B_SilkS)
    t.SetMirrored(side_now == 'B')
    t.SetTextSize(pcbnew.VECTOR2I(mm(e['h']), mm(e['h'])))
    t.SetTextThickness(mm(e['th']))
    t.SetTextAngleDegrees(e['angle'])
    t.SetPosition(pcbnew.VECTOR2I(mm(px + e['dx']), mm(py + e['dy'])))
    t.SetVisible(bool(e['visible']))
    n_set += 1
    if not e['visible']:
        n_hide += 1


# ---- 部品外形のシルク線がパッドに掛かっているものを、パッドの手前で切る ----
#   clip_graphics: {"REF": 間隔mm}。線分と矩形が対象 (円・円弧はそのまま)。
def clip_seg(a, c, boxes):
    # 線分 a→c から boxes (x0,y0,x1,y1) の中の部分を取り除いた残りの区間 [(t0,t1)...]
    keep = [(0.0, 1.0)]
    dx, dy = c[0] - a[0], c[1] - a[1]
    for bx in boxes:
        t0, t1 = 0.0, 1.0; okk = True
        for p_, q_ in ((-dx, a[0] - bx[0]), (dx, bx[2] - a[0]), (-dy, a[1] - bx[1]), (dy, bx[3] - a[1])):
            if abs(p_) < 1e-12:
                if q_ < 0:
                    okk = False; break
            else:
                t = q_ / p_
                if p_ < 0:
                    t0 = max(t0, t)
                else:
                    t1 = min(t1, t)
        if not okk or t0 >= t1:
            continue
        nk = []
        for u0, u1 in keep:
            if t1 <= u0 or t0 >= u1:
                nk.append((u0, u1)); continue
            if u0 < t0:
                nk.append((u0, t0))
            if t1 < u1:
                nk.append((t1, u1))
        keep = nk
    return keep


n_clip = 0
for ref, gap_mm in CLIP.items():
    fp = b.FindFootprintByReference(ref)
    if fp is None:
        warn.append('clip: 部品なし ' + ref); continue
    items = [g for g in list(fp.GraphicalItems())
             if g.GetClass() == 'PCB_SHAPE' and g.GetLayer() in (pcbnew.F_SilkS, pcbnew.B_SilkS)
             and g.GetShape() in (pcbnew.SHAPE_T_SEGMENT, pcbnew.SHAPE_T_RECT)]
    plan = []
    for g in items:
        Ly = g.GetLayer(); mlay = pcbnew.F_Mask if Ly == pcbnew.F_SilkS else pcbnew.B_Mask
        w = g.GetWidth() / 1e6
        cl = gap_mm + w / 2
        boxes = []
        for pad in fp.Pads():
            if not pad.IsOnLayer(mlay):
                continue
            ps = pcbnew.SHAPE_POLY_SET()
            pad.TransformShapeToPolygon(ps, mlay, 0, 5000, pcbnew.ERROR_OUTSIDE)
            bb = ps.BBox()
            boxes.append((bb.GetLeft() / 1e6 - cl, bb.GetTop() / 1e6 - cl, bb.GetRight() / 1e6 + cl, bb.GetBottom() / 1e6 + cl))
        st, en = g.GetStart(), g.GetEnd()
        if g.GetShape() == pcbnew.SHAPE_T_RECT:
            x0, y0, x1, y1 = st.x / 1e6, st.y / 1e6, en.x / 1e6, en.y / 1e6
            segs = [((x0, y0), (x1, y0)), ((x1, y0), (x1, y1)), ((x1, y1), (x0, y1)), ((x0, y1), (x0, y0))]
        else:
            segs = [((st.x / 1e6, st.y / 1e6), (en.x / 1e6, en.y / 1e6))]
        out_segs = []; changed = g.GetShape() == pcbnew.SHAPE_T_RECT
        for a, c in segs:
            keep = clip_seg(a, c, boxes)
            if keep != [(0.0, 1.0)]:
                changed = True
            ln = ((c[0] - a[0]) ** 2 + (c[1] - a[1]) ** 2) ** 0.5
            for u0, u1 in keep:
                if (u1 - u0) * ln < 0.15 and ln > 0.15:
                    continue
                out_segs.append(((a[0] + (c[0] - a[0]) * u0, a[1] + (c[1] - a[1]) * u0),
                                 (a[0] + (c[0] - a[0]) * u1, a[1] + (c[1] - a[1]) * u1)))
        if changed:
            plan.append((g, Ly, g.GetWidth(), out_segs))
    for g, Ly, wid, segs in plan:
        fp.Remove(g)
        for a, c in segs:
            ns = pcbnew.PCB_SHAPE(fp, pcbnew.SHAPE_T_SEGMENT)
            ns.SetLayer(Ly); ns.SetWidth(wid)
            ns.SetStart(pcbnew.VECTOR2I(mm(a[0]), mm(a[1]))); ns.SetEnd(pcbnew.VECTOR2I(mm(c[0]), mm(c[1])))
            fp.Add(ns)
        n_clip += 1
print('clipped graphics', n_clip)

for ref in L:
    if ref not in seen:
        warn.append('基板にない部品: ' + ref)
print('set', n_set, 'hidden', n_hide)
for w in warn:
    print('WARN', w)
if not dry:
    pcbnew.SaveBoard(out, b)
    print('saved', out)
