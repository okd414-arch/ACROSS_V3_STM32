# 8 層の基板を 10 層にした写しを作る (2026-11-24、案 B の試し)
#   並び: F(信号) In1 GND / In2 信号 / In3 信号(新) / In4 電源(旧 In3) / In5 電源(旧 In4) / In6 信号(新) / In7 信号(旧 In5) / In8 GND(旧 In6) / B(信号)
#   DDR の線とビアは消す (引き直す)。KiCad の Python。
# usage: python make_l10.py src.kicad_pcb dst.kicad_pcb
import sys
import pcbnew

src, dst = sys.argv[1], sys.argv[2]
b = pcbnew.LoadBoard(src)
MOVE = [(pcbnew.In6_Cu, pcbnew.In8_Cu), (pcbnew.In5_Cu, pcbnew.In7_Cu), (pcbnew.In4_Cu, pcbnew.In5_Cu), (pcbnew.In3_Cu, pcbnew.In4_Cu)]
# 先に DDR の線とビアを消す
kill = [t for t in b.GetTracks() if t.GetNetname().startswith('DDR_')]
for t in kill:
    b.Remove(t)
print('消した DDR の線・ビア', len(kill))
b.SetCopperLayerCount(10)
ds = b.GetDesignSettings()
ds.SetCopperLayerCount(10)
en = b.GetEnabledLayers()
for l in (pcbnew.In7_Cu, pcbnew.In8_Cu):
    en.AddLayer(l)
b.SetEnabledLayers(en)
b.SetVisibleLayers(en)
n = 0
for old, new in MOVE:  # 下の層から順に (重ならないように)
    for t in b.GetTracks():
        if t.Type() != pcbnew.PCB_VIA_T and t.GetLayer() == old:
            t.SetLayer(new)
            n += 1
    for z in b.Zones():
        ls = z.GetLayerSet()
        if ls.Contains(old):
            ls.RemoveLayer(old)
            ls.AddLayer(new)
            z.SetLayerSet(ls)
            n += 1
    for d in b.GetDrawings():
        if d.GetLayer() == old:
            d.SetLayer(new)
            n += 1
print('移した', n)
for l in range(10):
    pass
# 層の名前と種類
names = {pcbnew.In1_Cu: 'In1.Cu', pcbnew.In2_Cu: 'In2.Cu', pcbnew.In3_Cu: 'In3.Cu', pcbnew.In4_Cu: 'In4.Cu',
         pcbnew.In5_Cu: 'In5.Cu', pcbnew.In6_Cu: 'In6.Cu', pcbnew.In7_Cu: 'In7.Cu', pcbnew.In8_Cu: 'In8.Cu'}
for l in (pcbnew.In1_Cu, pcbnew.In4_Cu, pcbnew.In5_Cu, pcbnew.In8_Cu):
    b.SetLayerType(l, pcbnew.LT_POWER)
for l in (pcbnew.In2_Cu, pcbnew.In3_Cu, pcbnew.In6_Cu, pcbnew.In7_Cu):
    b.SetLayerType(l, pcbnew.LT_SIGNAL)
# スタックアップを 10 層で作り直す (厚みは KiCad の既定、全体 1.6mm 程度)
# (BuildDefaultStackupList は Python から呼べないので、スタックアップは fix_stackup10.py で文字列として直す)
pcbnew.ZONE_FILLER(b).Fill(b.Zones())
b.Save(dst)
print('保存', dst, '銅層', b.GetCopperLayerCount())
