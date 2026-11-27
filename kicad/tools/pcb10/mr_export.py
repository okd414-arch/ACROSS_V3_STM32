# 自前の格子配線 (maze router) 用に、障害物と配線する接続を JSON に書き出す (2026-11-22)
#   KiCad の Python で動かす。接続の一覧は drc_sum.py が書いた temp/drc_sum.json の unconnected_items。
#   配線層: 0=F.Cu 1=In2.Cu 2=In5.Cu 3=B.Cu (内層 In1/In3/In4/In6 は面なので使わない)
# usage: python mr_export.py out.json [pcb] [--nets REGEX]
import sys, json, os, tempfile, re, math
import pcbnew

out = sys.argv[1]
PCB = sys.argv[2] if len(sys.argv) > 2 and not sys.argv[2].startswith('--') else 'C:/MyWorks/ACROSS_V3_STM32/kicad/ACROSS_V3.kicad_pcb'
NETRE = re.compile(sys.argv[sys.argv.index('--nets') + 1]) if '--nets' in sys.argv else None
b = pcbnew.LoadBoard(PCB)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lay10 import LAY  # 10 層の写し (2026-11-24): 0=F 1=In2 2=In3 3=In6 4=In7 5=B
T = pcbnew.ToMM


def poly_pts(item, lay):
    ps = pcbnew.SHAPE_POLY_SET()
    item.TransformShapeToPolygon(ps, lay, 0, pcbnew.FromMM(0.005), pcbnew.ERROR_INSIDE)
    res = []
    for i in range(ps.OutlineCount()):
        o = ps.Outline(i)
        res.append([[T(o.CPoint(k).x), T(o.CPoint(k).y)] for k in range(o.PointCount())])
    return res


# はがしてはいけないネット: 降圧電源のスイッチ (LX)・ブートストラップ・大電流の入力
KEEP = re.compile(r'VLX|PM_BST|\+24V|C110-Pad1|D10[123]-K|J101-Pin_2|U706-LX')
items = []
uuid_map = {}
for f in b.GetFootprints():
    for p in f.Pads():
        ls = [i for i, l in enumerate(LAY) if p.IsOnLayer(l) and p.FlashLayer(l)]
        polys = {i: poly_pts(p, LAY[i]) for i in ls}
        d = p.GetDrillSize()
        hole = [T(p.GetPosition().x), T(p.GetPosition().y), T(max(d.x, d.y)) / 2] if d.x > 0 else None
        items.append({'k': 'pad', 'net': p.GetNetname(), 'polys': polys, 'hole': hole,
                      'pos': [T(p.GetPosition().x), T(p.GetPosition().y)], 'ref': f.GetReference()})
        uuid_map[p.m_Uuid.AsString()] = len(items) - 1
for t in b.GetTracks():
    if t.Type() == pcbnew.PCB_VIA_T:
        items.append({'k': 'via', 'net': t.GetNetname(), 'c': [T(t.GetPosition().x), T(t.GetPosition().y)],
                      'r': T(t.GetWidth(pcbnew.F_Cu)) / 2, 'hole': T(t.GetDrillValue()) / 2,
                      'uuid': t.m_Uuid.AsString(), 'soft': not t.IsLocked() and not KEEP.search(t.GetNetname())})
    else:
        if t.GetLayer() not in LAY:
            continue
        items.append({'k': 'seg', 'net': t.GetNetname(), 'l': LAY.index(t.GetLayer()),
                      'a': [T(t.GetStart().x), T(t.GetStart().y)], 'b': [T(t.GetEnd().x), T(t.GetEnd().y)], 'w': T(t.GetWidth()),
                      'uuid': t.m_Uuid.AsString(), 'soft': not t.IsLocked() and not KEEP.search(t.GetNetname())})
    uuid_map[t.m_Uuid.AsString()] = len(items) - 1
# 信号層のゾーン (電源まわりのベタ、2026-11-22): 塗った形をパッドと同じ扱いの障害物にする
for z in b.Zones():
    if z.GetIsRuleArea():
        continue
    polys = {}
    for i, l in enumerate(LAY):
        if not z.IsOnLayer(l):
            continue
        fp = z.GetFilledPolysList(l)
        res = []
        for k in range(fp.OutlineCount()):
            o = fp.Outline(k)
            res.append([[T(o.CPoint(m).x), T(o.CPoint(m).y)] for m in range(o.PointCount())])
        if res:
            polys[i] = res
    if polys:
        bb = z.GetBoundingBox()
        items.append({'k': 'pad', 'net': z.GetNetname(), 'polys': polys, 'hole': None,
                      'pos': [T(bb.GetCenter().x), T(bb.GetCenter().y)], 'ref': 'ZONE'})

# ネットのクラス
nets = {}
for name, ni in b.GetNetInfo().NetsByName().items():
    n = str(name)
    try:
        nets[n] = ni.GetNetClassName().split(',') if hasattr(ni, 'GetNetClassName') else ['Default']
    except Exception:
        nets[n] = ['Default']
pro = json.load(open(PCB[:-10] + '.kicad_pro', encoding='utf8'))
classes = {c['name']: {'w': c.get('track_width', 0.12), 'clr': c.get('clearance', 0.1)} for c in pro['net_settings']['classes']}

# BGA・eMMC の中は間隔 0.1 (DRU)
relax = []
for r in ('U1', 'U301', 'U302', 'U401', 'U104'):
    f = b.FindFootprintByReference(r)
    bb = f.GetCourtyard(pcbnew.F_CrtYd).BBox()
    relax.append([T(bb.GetLeft()), T(bb.GetTop()), T(bb.GetRight()), T(bb.GetBottom())])
eb = b.GetBoardEdgesBoundingBox()
edge = [T(eb.GetLeft()), T(eb.GetTop()), T(eb.GetRight()), T(eb.GetBottom())]

# 配線する接続
d = json.load(open(os.path.join(tempfile.gettempdir(), 'drc_sum.json'), encoding='utf8'))
jobs = []
zone_bb = {}
for z in b.Zones():
    bb = z.GetBoundingBox()
    zone_bb[z.m_Uuid.AsString()] = (z.GetNetname(), T(bb.GetLeft()), T(bb.GetTop()), T(bb.GetRight()), T(bb.GetBottom()), z)


def zone_sub(uid, other):
    # ゾーンの端 → ゾーンの中の同じネットのパッド・ビアで、相手 (other) にいちばん近いもの (2026-11-22)
    net, zx0, zy0, zx1, zy1, z = zone_bb[uid]
    best, bd = None, 1e9
    for i, x in enumerate(items):
        if x['net'] != net or x.get('ref') == 'ZONE' or x['k'] == 'seg':
            continue
        p = x['pos'] if x['k'] == 'pad' else x['c']
        if not (zx0 <= p[0] <= zx1 and zy0 <= p[1] <= zy1):
            continue
        if not z.HitTestFilledArea(z.GetFirstLayer(), pcbnew.VECTOR2I(pcbnew.FromMM(p[0]), pcbnew.FromMM(p[1])), 0) and not any(
                z.HitTestFilledArea(l, pcbnew.VECTOR2I(pcbnew.FromMM(p[0]), pcbnew.FromMM(p[1])), 0) for l in z.GetLayerSet().Seq()):
            continue
        dd = math.hypot(p[0] - other[0], p[1] - other[1])
        if dd < bd:
            best, bd = i, dd
    return best


CHAIN = '--chain' in sys.argv  # DDR を決まった順番でつなぐ (2026-11-23、AN5122 のフライバイ: U1 → U301 → U302 → 終端)
if CHAIN:
    # DDR 以外の未配線 (はがされたネット) は、ふつうどおり DRC の一覧から (下のループで DDR_ を飛ばす)
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import ddr_graph
    _g, _pads = ddr_graph.build(b)
    padidx = {}
    for i, x in enumerate(items):
        if x['k'] == 'pad' and x['net'].startswith('DDR_'):
            padidx.setdefault((x['net'], x['ref']), i)
    for net in sorted({k[0] for k in padidx}):
        if NETRE and not NETRE.search(net):
            continue
        refs = [r for (n, r) in padidx if n == net]
        order = ['U1'] + [r for r in ('U301', 'U302') if r in refs] + sorted(r for r in refs if r.startswith('R') and r != 'R326')
        if 'R326' in refs:
            order.append('R326')
        for ra, rb in zip(order, order[1:]):
            if _pads[(net, rb)] in ddr_graph.dist(_g, net, _pads[(net, ra)]):
                continue  # もうつながっている区間
            ends = []
            for r in (ra, rb):
                i = padidx[(net, r)]
                ends.append({'pts': [items[i]['pos']], 'layers': sorted(int(k) for k in items[i]['polys'].keys()), 'item': i})
            jobs.append({'net': net, 'a': ends[0], 'b': ends[1], 'leg': f'{ra}-{rb}'})
for v in d['unconnected_items']:
    ends = []
    for k, it in enumerate(v['items'][:2]):
        i = uuid_map.get(it['uuid'])
        if i is None and it['uuid'] in zone_bb:
            o = v['items'][1 - k]['pos']
            i = zone_sub(it['uuid'], (o['x'], o['y']))
        if i is None:
            ends = None
            break
        x = items[i]
        if x['k'] == 'pad':
            ends.append({'pts': [x['pos']], 'layers': sorted(int(k) for k in x['polys'].keys()), 'item': i})
        elif x['k'] == 'via':
            ends.append({'pts': [x['c']], 'layers': list(range(len(LAY))), 'item': i})
        else:
            ends.append({'pts': [x['a'], x['b']], 'layers': [x['l']], 'item': i})
    if not ends:
        continue
    net = items[ends[0]['item']]['net']
    if CHAIN and net.startswith('DDR_'):
        continue
    if NETRE and not NETRE.search(net):
        continue
    jobs.append({'net': net, 'a': ends[0], 'b': ends[1]})
json.dump({'items': items, 'nets': nets, 'classes': classes, 'relax': relax, 'edge': edge, 'jobs': jobs, 'nsig': len(LAY)},
          open(out, 'w', encoding='utf8'))
print('items', len(items), 'jobs', len(jobs))
