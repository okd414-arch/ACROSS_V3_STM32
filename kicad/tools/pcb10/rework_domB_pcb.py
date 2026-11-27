# ドメイン B 削除 + GF-8801 小基板用ヘッダ (J701) + バッファ (U406) 追加を基板に反映 (2026-11-16)
# usage: python rework_domB_pcb.py remove netlist.xml  (不要部品の削除。保存)
#        python rework_domB_pcb.py add netlist.xml     (新規部品の追加。別プロセスで)
#        python sync_pcb.py netlist.xml               (ネット・パスの同期)
#        python rework_domB_pcb.py place netlist.xml  (新規部品を配置)
import sys, json, xml.etree.ElementTree as ET
import pcbnew
from pcbnew import VECTOR2I, ToMM

KICAD = 'C:/MyWorks/ACROSS_V3_STM32/kicad'
PCB = KICAD + '/ACROSS_V3.kicad_pcb'
STAGE = sys.argv[1]
root = ET.parse(sys.argv[2]).getroot()
comps = {}
for c in root.find('components'):
    sp = c.find('sheetpath')
    comps[c.get('ref')] = dict(value=c.findtext('value') or '', fp=c.findtext('footprint') or '',
                               path=sp.get('tstamps') + c.find('tstamps').text.split()[0], sheet=sp.get('names'))
b = pcbnew.LoadBoard(PCB)


def mm(v):
    return int(round(v * 1e6))


NEW = ['J701', 'C701', 'U406', 'C415']
if STAGE == 'remove':
    gone = []
    for f in list(b.GetFootprints()):
        r = f.GetReference()
        if r not in comps or r in ('J701', 'C701'):
            gone.append(r)
            b.Remove(f)
    print('removed', len(gone), sorted(gone))
    b.Save(PCB)
    sys.exit(0)

if STAGE == 'add':
    for r in NEW:
        lib, name = comps[r]['fp'].split(':')
        libdir = {'01_MY': 'C:/OneDrive_link/KiCAD/Modules/01_MY',
                  'Connector_PinHeader_2.54mm': 'C:/Program Files/KiCad/10.0/share/kicad/footprints/Connector_PinHeader_2.54mm.pretty',
                  'Package_SO': 'C:/Program Files/KiCad/10.0/share/kicad/footprints/Package_SO.pretty'}[lib]
        n = pcbnew.FootprintLoad(libdir, name)
        n.SetFPID(pcbnew.LIB_ID(lib, name))
        n.SetReference(r)
        n.SetValue(comps[r]['value'])
        n.SetPath(pcbnew.KIID_PATH(comps[r]['path']))
        n.SetPosition(VECTOR2I(mm(100), mm(70)))
        b.Add(n)
    # 値の更新 (直列抵抗)
    for f in b.GetFootprints():
        r = f.GetReference()
        if r in comps and f.GetValue() != comps[r]['value']:
            print('value', r, f.GetValue(), '->', comps[r]['value'])
            f.SetValue(comps[r]['value'])
    b.Save(PCB)
    sys.exit(0)

# ---------------------------- place ----------------------------
W, H = 160.0, 100.0
CL = 0.3
fps = {f.GetReference(): f for f in b.GetFootprints()}


def bbox(f):
    bb = f.GetBoundingBox(False)
    return (ToMM(bb.GetX()), ToMM(bb.GetY()), ToMM(bb.GetX() + bb.GetWidth()), ToMM(bb.GetY() + bb.GetHeight()))


def tht(f):
    return bool(f.GetAttributes() & pcbnew.FP_THROUGH_HOLE) or any(p.GetDrillSize().x > 0 for p in f.Pads())


def set_center(f, cx, cy):
    x0, y0, x1, y1 = bbox(f)
    p = f.GetPosition()
    f.SetPosition(VECTOR2I(p.x + mm(cx - (x0 + x1) / 2), p.y + mm(cy - (y0 + y1) / 2)))


occ = {'F': [], 'B': []}
for r, f in fps.items():
    if r in NEW:
        continue
    bb = bbox(f)
    if tht(f):
        occ['F'].append(bb)
        occ['B'].append(bb)
    else:
        occ['B' if f.IsFlipped() else 'F'].append(bb)


def collide(r, side):
    return any(r[2] + CL > o[0] and r[0] - CL < o[2] and r[3] + CL > o[1] and r[1] - CL < o[3] for o in occ[side])


def inboard(r):
    return r[0] >= 1.0 and r[1] >= 1.0 and r[2] <= W - 1.0 and r[3] <= H - 1.0


offs = sorted(((dx * 0.25, dy * 0.25) for dx in range(-120, 121) for dy in range(-120, 121)), key=lambda t: t[0] ** 2 + t[1] ** 2)


def place(r, tx, ty, ang, side='F'):
    f = fps[r]
    if side == 'B' and not f.IsFlipped():
        f.Flip(f.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
    f.SetOrientationDegrees(ang if side == 'F' else (180 - ang) % 360)
    for dx, dy in offs:
        set_center(f, tx + dx, ty + dy)
        bb = bbox(f)
        if inboard(bb) and not collide(bb, side):
            occ[side].append(bb)
            if tht(f):
                occ['B' if side == 'F' else 'F'].append(bb)
            print(r, 'at', round(tx + dx, 2), round(ty + dy, 2), 'side', side)
            return True
    print(r, 'FAILED')
    return False


# J701: 縦のピンヘッダ (ピン1が上)、旧ドメイン B の左端あたり
place('J701', 97.0, 76.0, 0)
jb = bbox(fps['J701'])
# 直列抵抗: ヘッダの右に並べる
rows = [('R710', 5), ('R701', 6), ('R702', 7), ('R703', 8), ('R704', 9), ('R705', 10)]
for r, pn in rows:
    pad = [p for p in fps['J701'].Pads() if p.GetNumber() == str(pn)][0]
    place(r, ToMM(pad.GetPosition().x) + 4.5, ToMM(pad.GetPosition().y), 0)
pad1 = [p for p in fps['J701'].Pads() if p.GetNumber() == '1'][0]
place('C701', ToMM(pad1.GetPosition().x) + 4.0, ToMM(pad1.GetPosition().y) - 0.5, 90)
# バッファ U406: 旧ドメイン B の右寄り (OC フォトカプラの近く)
place('U406', 116.0, 84.0, 90)
ub = bbox(fps['U406'])
place('C415', (ub[0] + ub[2]) / 2, ub[1] - 2.5, 0)
b.Save(PCB)
print('saved')
