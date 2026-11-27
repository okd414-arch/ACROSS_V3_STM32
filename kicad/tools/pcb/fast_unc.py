# DRC を使わずに、未配線の一覧を drc_sum.json と同じ形で書く (2026-11-25、mr_export.py 用。数秒で終わる)
#   KiCad のつながり情報 (ラッツネスト) の辺ごとに、両端の部品の ID・位置・説明 ([ネット名] を含む)。violations は空。
# usage: python fast_unc.py pcb [out.json (省略時は TEMP/drc_sum.json)]
import sys, os, json, tempfile
import pcbnew

b = pcbnew.LoadBoard(sys.argv[1])
out = sys.argv[2] if len(sys.argv) > 2 else os.path.join(tempfile.gettempdir(), 'drc_sum.json')
T = pcbnew.ToMM
b.BuildConnectivity()
c = b.GetConnectivity()
un = []
for n in range(1, b.GetNetCount()):
    rn = c.GetRatsnestForNet(n)
    if rn is None:
        continue
    for e in rn.GetEdges():
        if e.IsVisible() is False:
            pass
        its = []
        for nd in (e.GetSourceNode(), e.GetTargetNode()):
            it = nd.Parent()
            p = nd.Pos()
            its.append({'uuid': it.m_Uuid.AsString(), 'pos': {'x': T(p.x), 'y': T(p.y)},
                        'description': f'{it.GetClass()} [{it.GetNetname()}]'})
        un.append({'items': its})
json.dump({'violations': [], 'unconnected_items': un, 'schematic_parity': []}, open(out, 'w', encoding='utf8'), ensure_ascii=False)
print('unconnected', len(un))
