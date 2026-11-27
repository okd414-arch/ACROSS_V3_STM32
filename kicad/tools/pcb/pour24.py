# 24V 入力まわりの表のベタ (2026-11-25)
#   線を太くしても、パッドに挟まれて細いまま残る所を、すき間いっぱいのベタにする。
#   - D102-K (Q101 の source → U101 の IN、24V の全電流が通る): Q101・D102・C101・R102・U101 の左側の範囲
#   - +24V (U101 の OUT ピン → ビア): U101 の右上
#   ほかのネットのパッド・線は、ゾーンの塗りが 0.25 の間隔でよける。同じ名前のゾーンがあれば作り直す。
#   このあと別の処理で zone_fill.py を流すこと (ここでは塗らない。線を消したあとの Zones() は落ちるため、念のため)
# usage: python pour24.py pcb
import sys
import pcbnew

PCB = sys.argv[1]
mm = pcbnew.FromMM
b = pcbnew.LoadBoard(PCB)
Z = [
    ('IN24_D102K', 'Net-(D102-K)', [(19.9, 11.4), (26.6, 11.4), (26.6, 15.6), (27.0, 15.6), (27.0, 22.8),
                                     (19.0, 22.8), (19.0, 15.6), (19.9, 15.6)]),
    ('IN24_OUT', '+24V', [(29.7, 10.8), (34.6, 10.8), (34.6, 13.2), (29.7, 13.2)]),
]
# 同じ名前のゾーンがあれば外形だけ置き換える (pcbnew は Remove のあとに新しいゾーンを作ると壊れるため)
have = {z.GetZoneName(): z for z in b.Zones()}
for name, net, pts in Z:
    z = have.get(name)
    if z is None:
        z = pcbnew.ZONE(b)
        b.Add(z)
    z.SetLayer(pcbnew.F_Cu)
    z.SetNet(b.FindNet(net))
    z.SetZoneName(name)
    ol = z.Outline()
    ol.RemoveAllContours()
    ol.NewOutline()
    for x, y in pts:
        ol.Append(mm(x), mm(y))
    z.SetAssignedPriority(6)
    z.SetLocalClearance(mm(0.25))
    z.SetMinThickness(mm(0.25))
    z.SetPadConnection(pcbnew.ZONE_CONNECTION_FULL)
    z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
b.Save(PCB)
print('ゾーンを置いた', [q[0] for q in Z])
