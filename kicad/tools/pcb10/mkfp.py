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

# ---------- 1. FPC XDFC-0522-45P ----------
p = FP('FPC_XDFC-0522-45P_0.5mm_BackFlip', 'LianXin XDFC-0522-45P 0.5mm FPC connector, 45 pins, back flip, from LCSC datasheet C22363834', 'FPC 0.5mm 45P XDFC-0522', 'smd')
for i in range(45):
    p.smd(str(i + 1), (i - 22) * 0.5, 0, 0.30, 1.20)
p.smd('MP', -12.8, 3.15, 1.80, 2.00)
p.smd('MP', 12.8, 3.15, 1.80, 2.00)
p.rect(-13.225, 0.5, 13.225, 5.2, 'F.Fab')
p.rect(-13.6, -1.2, 13.6, 5.6, 'F.CrtYd', 0.05)
p.line(-13.225, 0.5, -13.225, 5.2, 'F.SilkS'); p.line(13.225, 0.5, 13.225, 5.2, 'F.SilkS')
p.line(-13.225, 5.2, 13.225, 5.2, 'F.SilkS')
p.line(-11.15, -1.0, -11.15, -1.0, 'F.SilkS')
p.circle(-11.0, -1.3, 0.2, 'F.SilkS')
p.ref_at = (0, -2.5); p.val_at = (0, 7)
p.write()

# ---------- 2. microSD TF-01A ----------
p = FP('microSD_TF-01A_Hroparts', 'Korean Hroparts TF-01A push-push microSD socket, from datasheet C91145 PCB layout (courtyard approximate)', 'microSD TF-01A', 'smd')
for k in range(1, 9):
    p.smd(str(k), -(k - 1) * 1.10, 0, 0.70, 1.30)
p.smd('9', -8.8, 0, 0.70, 1.30)
p.smd('SH', -9.93, 0.85, 1.20, 1.40)
p.smd('SH', 4.78, 0.85, 1.20, 1.40)
p.smd('SH', -9.93, 10.55, 1.20, 2.00)
p.smd('SH', 5.59, 10.55, 1.20, 2.00)
p.npth(-7.12, 10.70, 1.00)
p.npth(0.88, 10.70, 1.00)
p.rect(-10.9, -0.2, 6.2, 12.0, 'F.Fab')
p.rect(-11.3, -1.2, 6.6, 12.4, 'F.CrtYd', 0.05)
p.line(-10.9, 12.0, 6.2, 12.0, 'F.SilkS')
p.circle(1.2, -1.2, 0.2, 'F.SilkS')
p.ref_at = (-2.5, -2.4); p.val_at = (-2.5, 13.6)
p.write()

# ---------- 3. SIP4 1W ----------
p = FP('Converter_DCDC_SIP4_11.6x6mm_P2.54mm', 'Isolated DC-DC SIP-4 (B2409S-1WR3 etc., 11.6x6.0x10.16mm), pins 1-4 at 2.54mm, drill 1.0, from Mornsun B_S-1WR3 datasheet layout', 'DCDC SIP4 1W', 'through_hole')
for i in range(4):
    p.tht(str(i + 1), i * 2.54, 0, 1.7, 1.0)
p.rect(-1.99, -5.1, 9.61, 0.9, 'F.Fab')
p.rect(-2.2, -5.3, 9.82, 1.1, 'F.SilkS')
p.rect(-2.5, -5.6, 10.12, 1.4, 'F.CrtYd', 0.05)
p.circle(0, -2.2, 0.35, 'F.SilkS')
p.ref_at = (3.81, -6.6); p.val_at = (3.81, 2.5)
p.write()

# ---------- 4. SIP4 2W (pins 1,2,4,6) ----------
p = FP('Converter_DCDC_SIP4_19.65x7.05mm_P2.54mm_Pins1-2-4-6', 'Isolated DC-DC 2W SIP (B2405S-2WR3 etc., 19.65x7.05x10.16mm), pins 1,2,4,6 on 2.54mm grid, drill 1.0, from Mornsun IB2405S-2WR3 datasheet layout', 'DCDC SIP 2W', 'through_hole')
for name, idx in (('1', 0), ('2', 1), ('4', 3), ('6', 5)):
    p.tht(name, idx * 2.54, 0, 1.7, 1.0)
p.rect(-2.21, -6.15, 17.44, 0.9, 'F.Fab')
p.rect(-2.4, -6.35, 17.64, 1.1, 'F.SilkS')
p.rect(-2.7, -6.65, 17.94, 1.4, 'F.CrtYd', 0.05)
p.circle(0, -2.2, 0.35, 'F.SilkS')
p.ref_at = (7.62, -7.6); p.val_at = (7.62, 2.5)
p.write()

# ---------- 5. STPMIC1 WFQFN-44 ----------
p = FP('WFQFN-44-1EP_5x6mm_P0.4mm_EP3.6x4.6mm', 'ST WFQFN 44L (5x6x0.8) recommended footprint (STPMIC1 datasheet DS12792 Rev10 fig.65), pin 1 top-left, counter-clockwise', 'WFQFN 44 0.4mm STPMIC1', 'smd')
for i in range(12):   # left, pins 1-12, top to bottom
    p.smd(str(i + 1), -2.45, (i - 5.5) * 0.4, 0.80, 0.22)
for j in range(10):   # bottom, pins 13-22, left to right
    p.smd(str(13 + j), (j - 4.5) * 0.4, 2.96, 0.25, 0.80)
for i in range(12):   # right, pins 23-34, bottom to top
    p.smd(str(23 + i), 2.45, (5.5 - i) * 0.4, 0.80, 0.22)
for j in range(10):   # top, pins 35-44, right to left
    p.smd(str(35 + j), (4.5 - j) * 0.4, -2.96, 0.25, 0.80)
p.smd('45', 0, 0, 3.60, 4.60)
p.rect(-2.5, -3.0, 2.5, 3.0, 'F.Fab')
p.rect(-3.3, -3.6, 3.3, 3.6, 'F.CrtYd', 0.05)
p.line(-2.6, -3.1, -1.6, -3.1, 'F.SilkS'); p.line(-2.6, -3.1, -2.6, -2.6, 'F.SilkS')
p.circle(-3.1, -2.7, 0.15, 'F.SilkS')
p.ref_at = (0, -4.3); p.val_at = (0, 4.3)
p.write()

# ---------- 6. inductor PSPMAA0805 ----------
p = FP('L_PSPMAA0805_8.5x8.0mm', 'PROD Tech PSPMAA0805 molded inductor 8.5x8.0x5.0mm, land pattern a=3.5 b=2.4 c=6.9 from datasheet', 'inductor PSPMAA0805', 'smd')
p.smd('1', -3.45, 0, 2.40, 3.50)
p.smd('2', 3.45, 0, 2.40, 3.50)
p.rect(-4.25, -4.0, 4.25, 4.0, 'F.Fab')
p.line(-4.35, -4.1, 4.35, -4.1, 'F.SilkS'); p.line(-4.35, 4.1, 4.35, 4.1, 'F.SilkS')
p.rect(-4.9, -4.4, 4.9, 4.4, 'F.CrtYd', 0.05)
p.ref_at = (0, -5.4); p.val_at = (0, 5.4)
p.write()
