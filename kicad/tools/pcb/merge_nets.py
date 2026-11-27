# 並列で直した写しを、ネット単位で 1 枚にまとめる (2026-11-25)
#   基板 (base) から指定のネットの線・ビアを消し、写しから同じネットの線・ビアを持ってくる。
#   写しごとに直したネットの一覧 (JSON) を渡す。どの写しでも、他の写しのネットは元のまま (はがさない設定で回したこと)。
#   --revert で、指定のネットを base の元の線に戻す (ぶつかったときの片方を戻すため。--orig に元の基板)
# usage: python merge_nets.py base.kicad_pcb out.kicad_pcb copy1.kicad_pcb nets1.json [copy2 nets2 ...]
#        python merge_nets.py --revert cur.kicad_pcb out.kicad_pcb --orig orig.kicad_pcb nets.json
import sys, json
import pcbnew


def clone_into(b, src_item):
    if src_item.Type() == pcbnew.PCB_VIA_T:
        v = pcbnew.PCB_VIA(b)
        v.SetPosition(src_item.GetPosition())
        v.SetWidth(src_item.GetWidth(pcbnew.F_Cu))
        v.SetDrill(src_item.GetDrillValue())
        v.SetViaType(src_item.GetViaType())
        top, bot = src_item.TopLayer(), src_item.BottomLayer()
        v.SetLayerPair(top, bot)
        v.SetNet(b.FindNet(src_item.GetNetname()))
        v.SetLocked(src_item.IsLocked())
        b.Add(v)
    elif src_item.Type() == pcbnew.PCB_ARC_T:
        a = pcbnew.PCB_ARC(b)
        a.SetStart(src_item.GetStart()); a.SetMid(src_item.GetMid()); a.SetEnd(src_item.GetEnd())
        a.SetWidth(src_item.GetWidth()); a.SetLayer(src_item.GetLayer()); a.SetNet(b.FindNet(src_item.GetNetname()))
        b.Add(a)
    else:
        t = pcbnew.PCB_TRACK(b)
        t.SetStart(src_item.GetStart()); t.SetEnd(src_item.GetEnd())
        t.SetWidth(src_item.GetWidth()); t.SetLayer(src_item.GetLayer()); t.SetNet(b.FindNet(src_item.GetNetname()))
        t.SetLocked(src_item.IsLocked())
        b.Add(t)


def replace(b, src, nets):
    rm = [t for t in b.GetTracks() if t.GetNetname() in nets]
    for t in rm:
        b.Remove(t)
    n = 0
    for t in src.GetTracks():
        if t.GetNetname() in nets:
            clone_into(b, t); n += 1
    return len(rm), n


a = sys.argv[1:]
if a[0] == '--revert':
    cur, out = a[1], a[2]
    orig = a[a.index('--orig') + 1]
    nets = set(json.load(open(a[a.index('--orig') + 2], encoding='utf8')))
    b = pcbnew.LoadBoard(cur)
    o = pcbnew.LoadBoard(orig)
    print('戻した', replace(b, o, nets), len(nets), 'ネット')
else:
    base, out = a[0], a[1]
    b = pcbnew.LoadBoard(base)
    for cp, nf in zip(a[2::2], a[3::2]):
        nets = set(json.load(open(nf, encoding='utf8')))
        src = pcbnew.LoadBoard(cp)
        r, n = replace(b, src, nets)
        print(cp, 'ネット', len(nets), '消した', r, '持ってきた', n)
# ゾーンの塗り直しはしない (線を消して足したあとに Zones() を呼ぶと落ちる)。別の処理で zone_fill.py を流すこと
b.Save(out)
print('保存', out)
