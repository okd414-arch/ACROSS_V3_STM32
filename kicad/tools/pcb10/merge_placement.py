# 並列で作った配置結果 (result_P.json / result_AD.json / 提案) を本体の基板に統合する (2026-11-20)
# usage: python merge_placement.py pl_dir
import sys, json
import pcbnew
from pcbnew import VECTOR2I

KICAD = 'C:/MyWorks/ACROSS_V3_STM32/kicad'
PCB = KICAD + '/ACROSS_V3.kicad_pcb'
D = sys.argv[1]
res = {}
NAMES = sys.argv[2].split(',') if len(sys.argv) > 2 else ['result_P.json', 'result_AD.json']
for name in NAMES:
    r = json.load(open(D + '/' + name, encoding='utf8'))
    dup = set(res) & set(r)
    assert not dup, ('重複', name, sorted(dup))
    res.update(r)
prop = {}
print('proposal', prop)
b = pcbnew.LoadBoard(PCB)
fps = {f.GetReference(): f for f in b.GetFootprints()}


def mm(v):
    return int(round(v * 1e6))


def apply(r, x, y, rot, side):
    f = fps[r]
    if (side == 'B') != f.IsFlipped():
        f.Flip(f.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
    f.SetOrientationDegrees(rot)
    f.SetPosition(VECTOR2I(mm(x), mm(y)))


n = 0
for r, v in res.items():
    apply(r, v['x'], v['y'], v['rot'], v['side'])
    n += 1
# 提案 (C705)
for r, v in (prop.items() if isinstance(prop, dict) else []):
    if isinstance(v, dict) and 'x' in v:
        if r in res:
            print('提案が結果と重複:', r)
        old = fps[r].GetPosition()
        apply(r, v['x'], v['y'], v.get('rot', fps[r].GetOrientationDegrees()), v.get('side', 'B' if fps[r].IsFlipped() else 'F'))
        print('proposal applied', r, v)
b.Save(PCB)
print('applied', n)
