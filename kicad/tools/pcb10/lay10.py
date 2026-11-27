# 10 層の写し用の配線層の定義 (2026-11-24)。KiCad の Python から import する。
#   配線層の番号: 0=F 1=In2 2=In3 3=In6 4=In7 5=B (面: In1 GND / In4・In5 電源 / In8 GND)
#   Z は銅の上面からの深さ mm (fix_stackup10.py のスタックアップ)
import pcbnew

LAY = [pcbnew.F_Cu, pcbnew.In2_Cu, pcbnew.In3_Cu, pcbnew.In6_Cu, pcbnew.In7_Cu, pcbnew.B_Cu]
Z = {pcbnew.F_Cu: 0.0, pcbnew.In2_Cu: 0.280, pcbnew.In3_Cu: 0.415, pcbnew.In6_Cu: 1.130, pcbnew.In7_Cu: 1.265, pcbnew.B_Cu: 1.525}
