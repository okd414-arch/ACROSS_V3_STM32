import os, uuid

OUT = 'C:/MyWorks/ACROSS_V3_STM32/kicad/ACROSS_V3.pretty'
os.makedirs(OUT, exist_ok=True)
T = chr(9)

def u():
    return str(uuid.uuid4())

def f(v):
    return ('%.4f' % v).rstrip('0').rstrip('.')

class FP:
    def __init__(self, name, descr, tags, attr):
        self.name = name; self.descr = descr; self.tags = tags; self.attr = attr
        self.body = []
        self.ref_at = (0, -3)
        self.val_at = (0, 3)

    def line(self, x1, y1, x2, y2, layer, w=0.12):
        self.body.append('(fp_line (start %s %s) (end %s %s) (stroke (width %s) (type solid)) (layer "%s") (uuid "%s"))' % (f(x1), f(y1), f(x2), f(y2), f(w), layer, u()))

    def rect(self, x1, y1, x2, y2, layer, w=0.12):
        self.body.append('(fp_rect (start %s %s) (end %s %s) (stroke (width %s) (type solid)) (fill no) (layer "%s") (uuid "%s"))' % (f(x1), f(y1), f(x2), f(y2), f(w), layer, u()))

    def circle(self, x, y, r, layer, w=0.12):
        self.body.append('(fp_circle (center %s %s) (end %s %s) (stroke (width %s) (type solid)) (fill no) (layer "%s") (uuid "%s"))' % (f(x), f(y), f(x + r), f(y), f(w), layer, u()))

    def smd(self, name, x, y, w, h, shape='rect', paste=True):
        layers = '"F.Cu" "F.Mask" "F.Paste"' if paste else '"F.Cu" "F.Mask"'
        self.body.append('(pad "%s" smd %s (at %s %s) (size %s %s) (layers %s) (uuid "%s"))' % (name, shape, f(x), f(y), f(w), f(h), layers, u()))

    def tht(self, name, x, y, d, drill):
        self.body.append('(pad "%s" thru_hole circle (at %s %s) (size %s %s) (drill %s) (layers "*.Cu" "*.Mask") (uuid "%s"))' % (name, f(x), f(y), f(d), f(d), f(drill), u()))

    def npth(self, x, y, drill):
        self.body.append('(pad "" np_thru_hole circle (at %s %s) (size %s %s) (drill %s) (layers "*.Cu" "*.Mask") (uuid "%s"))' % (f(x), f(y), f(drill), f(drill), f(drill), u()))

    def write(self):
        s = []
        s.append('(footprint "%s"' % self.name)
        s.append(T + '(version 20260206)')
        s.append(T + '(generator "pcbnew")')
        s.append(T + '(generator_version "10.0")')
        s.append(T + '(layer "F.Cu")')
        s.append(T + '(descr "%s")' % self.descr)
        s.append(T + '(tags "%s")' % self.tags)
        s.append(T + '(property "Reference" "REF**" (at %s %s 0) (layer "F.SilkS") (uuid "%s") (effects (font (size 1 1) (thickness 0.15))))' % (f(self.ref_at[0]), f(self.ref_at[1]), u()))
        s.append(T + '(property "Value" "%s" (at %s %s 0) (layer "F.Fab") (uuid "%s") (effects (font (size 1 1) (thickness 0.15))))' % (self.name, f(self.val_at[0]), f(self.val_at[1]), u()))
        s.append(T + '(property "Datasheet" "" (at 0 0 0) (unlocked yes) (layer "F.Fab") (hide yes) (uuid "%s") (effects (font (size 1.27 1.27) (thickness 0.15))))' % u())
        s.append(T + '(property "Description" "" (at 0 0 0) (unlocked yes) (layer "F.Fab") (hide yes) (uuid "%s") (effects (font (size 1.27 1.27) (thickness 0.15))))' % u())
        s.append(T + '(attr %s)' % self.attr)
        for b in self.body:
            s.append(T + b)
        s.append(T + '(embedded_fonts no)')
        s.append(')')
        path = OUT + '/' + self.name + '.kicad_mod'
        open(path, 'w', encoding='utf8', newline='').write(chr(10).join(s) + chr(10))
        print('wrote', path)


p = FP('USB_A_Samtec_USB-A-S-X-X-TH_Horizontal', 'Samtec USB-A-S-x-x-TH USB A receptacle, horizontal through hole, from Samtec drawing (rev S) recommended PCB layout', 'USB A Samtec TH horizontal', 'through_hole')
for name, x in (('1', 0.0), ('2', 2.5), ('3', 4.5), ('4', 7.0)):
    p.tht(name, x, 0, 1.6, 0.92)
p.tht('SH', 3.5 - 6.57, 2.71, 3.2, 2.30)
p.tht('SH', 3.5 + 6.57, 2.71, 3.2, 2.30)
p.rect(-2.75, -1.0, 9.75, 13.1, 'F.Fab')
p.rect(-2.85, -1.1, 9.85, 13.2, 'F.SilkS')
p.rect(-3.2, -1.5, 10.2, 13.5, 'F.CrtYd', 0.05)
p.circle(0, -2.2, 0.3, 'F.SilkS')
p.ref_at = (3.5, -2.8); p.val_at = (3.5, 14.6)
p.write()
