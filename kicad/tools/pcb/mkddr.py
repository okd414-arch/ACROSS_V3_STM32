import re
src = open('C:/Users/K.Okada/AppData/Local/Temp/w/mkfp.py', encoding='utf8').read()
exec(src[:src.index('# ---------- 1. FPC')])

ref = open('C:/Program Files/KiCad/10.0/share/kicad/footprints/Package_BGA.pretty/Micron_FBGA-96_8x14mm_Layout9x16_P0.8mm.kicad_mod', encoding='utf8').read()
pads = re.findall(r'\(pad "([A-Z]\d)" smd circle\s*\(at ([-\d.]+) ([-\d.]+)\)', ref)
print(len(pads), pads[:3], pads[-1])

p = FP('FBGA-96_8x13mm_Layout9x16_P0.8mm', 'Nanya NT5CC256M16ER (DDR3L 4Gb x16) 96-ball TFBGA, body 8.00x13.00mm, ball pitch 0.80mm, ball dia 0.40-0.50mm (Nanya DDR3-4Gb E-Die datasheet v1.8 p.5); pad dia 0.40', 'BGA 96 0.8 DDR3 DDR3L Nanya', 'smd')
for name, x, y in pads:
    p.body.append('(pad "%s" smd circle (at %s %s) (size 0.4 0.4) (property pad_prop_bga) (layers "F.Cu" "F.Mask" "F.Paste") (uuid "%s"))' % (name, x, y, u()))
# fab outline with chamfered A1 corner (top left)
c = 1.0
pts = [(-4.0 + c, -6.5), (4.0, -6.5), (4.0, 6.5), (-4.0, 6.5), (-4.0, -6.5 + c)]
for (x1, y1), (x2, y2) in zip(pts, pts[1:] + pts[:1]):
    p.line(x1, y1, x2, y2, 'F.Fab', 0.1)
# silk corners
for sx in (-1, 1):
    for sy in (-1, 1):
        if sx == -1 and sy == -1:
            continue
        p.line(sx * 4.1, sy * 6.6, sx * 4.1, sy * 5.6, 'F.SilkS')
        p.line(sx * 4.1, sy * 6.6, sx * 3.1, sy * 6.6, 'F.SilkS')
p.line(-4.1, -5.6, -4.1, -6.0, 'F.SilkS'); p.line(-3.1, -6.6, -3.6, -6.6, 'F.SilkS')
p.line(-4.1, -5.6, -3.1, -6.6, 'F.SilkS')
p.rect(-4.4, -6.9, 4.4, 6.9, 'F.CrtYd', 0.05)
p.ref_at = (0, -8.0); p.val_at = (0, 8.0)
p.write()
