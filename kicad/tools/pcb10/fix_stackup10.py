# 10 層の写しのスタックアップを書き換える (2026-11-24)。通常の Python。
#   誘電体 (上から): PP 0.08 / core 0.15 / PP 0.12 / core 0.15 / PP 0.37 / core 0.15 / PP 0.12 / core 0.15 / PP 0.08
#   銅 外層 0.035・内層 0.0152、マスク 0.02 x2 → 全体 約 1.6mm
#   銅の上面からの深さ (ddr_graph の Z に使う): F 0 / In1 0.115 / In2 0.280 / In3 0.415 / In4 0.580 / In5 0.965 / In6 1.130 / In7 1.265 / In8 1.430 / B 1.525
# usage: python fix_stackup10.py pcb
import sys, re

F = sys.argv[1]
t = open(F, encoding='utf8').read()
i = t.index('(stackup')
depth, j = 0, i
while True:
    if t[j] == '(':
        depth += 1
    elif t[j] == ')':
        depth -= 1
        if depth == 0:
            break
    j += 1
cu = ['F.Cu'] + [f'In{k}.Cu' for k in range(1, 9)] + ['B.Cu']
di = [('prepreg', 0.08), ('core', 0.15), ('prepreg', 0.12), ('core', 0.15), ('prepreg', 0.37),
      ('core', 0.15), ('prepreg', 0.12), ('core', 0.15), ('prepreg', 0.08)]
L = ['(stackup',
     '(layer "F.SilkS" (type "Top Silk Screen"))',
     '(layer "F.Paste" (type "Top Solder Paste"))',
     '(layer "F.Mask" (type "Top Solder Mask") (thickness 0.02) (material "Liquid Ink") (epsilon_r 3.8) (loss_tangent 0))']
for k, c in enumerate(cu):
    L.append(f'(layer "{c}" (type "copper") (thickness {0.035 if c in ("F.Cu", "B.Cu") else 0.0152}))')
    if k < len(di):
        ty, th = di[k]
        mat = 'FR4 core' if ty == 'core' else '2116 PP'
        L.append(f'(layer "dielectric {k + 1}" (type "{ty}") (thickness {th}) (material "{mat}") (epsilon_r {4.4 if ty == "core" else 4.16}) (loss_tangent 0.02))')
L += ['(layer "B.Mask" (type "Bottom Solder Mask") (thickness 0.02) (material "Liquid Ink") (epsilon_r 3.8) (loss_tangent 0))',
      '(layer "B.Paste" (type "Bottom Solder Paste"))',
      '(layer "B.SilkS" (type "Bottom Silk Screen"))',
      '(copper_finish "ENIG")', '(dielectric_constraints yes))']
t = t[:i] + '\n\t\t\t'.join(L) + t[j + 1:]
open(F, 'w', encoding='utf8', newline='').write(t)
print('スタックアップを 10 層にした')
