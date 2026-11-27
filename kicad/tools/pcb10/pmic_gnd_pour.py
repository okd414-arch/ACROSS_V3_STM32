# PMIC (U104) まわりの F.Cu に GND のベタを入れる (2026-11-22、配線が終わったあと)
#   入力・出力コンデンサの GND パッドと放熱パッドのビアを、表の銅で太く短くつなぐ (DC-DC の電流ループを小さくする)。
#   優先度は電源のベタ (5) より下 (1)。島は消す。すでに同じ名前のゾーンがあれば作り直す。
# usage: python pmic_gnd_pour.py [pcb]
import sys
import pcbnew

PCB = sys.argv[1] if len(sys.argv) > 1 else 'C:/MyWorks/ACROSS_V3_STM32/kicad/ACROSS_V3.kicad_pcb'
mm = pcbnew.FromMM
b = pcbnew.LoadBoard(PCB)
NAME = 'PMIC_GND_F'
for z in list(b.Zones()):
    if z.GetZoneName() == NAME:
        b.Remove(z)
z = pcbnew.ZONE(b)
z.SetLayer(pcbnew.F_Cu)
z.SetNet(b.FindNet('GND'))
ol = z.Outline()
ol.NewOutline()
for x, y in [(28.8, 39.8), (46.4, 39.8), (46.4, 57.8), (28.8, 57.8)]:
    ol.Append(mm(x), mm(y))
z.SetAssignedPriority(1)
z.SetLocalClearance(mm(0.2))
z.SetMinThickness(mm(0.2))
z.SetPadConnection(pcbnew.ZONE_CONNECTION_FULL)
z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
z.SetZoneName(NAME)
b.Add(z)
pcbnew.ZONE_FILLER(b).Fill(b.Zones())
b.Save(PCB)
print('GND ベタを入れた')
