# ドメイン B (GPS 絶縁) を削除し、GF-8801 小基板への 1x10 ピンヘッダに置き換える (2026-11-16)
import re, sys, uuid
sys.path.insert(0, 'tools')
from sch_items import split_top, kind, pos

F = '07_domB_gps.kicad_sch'
s = open(F, encoding='utf8').read()
SHEET = '/51c71bd7-082e-50b5-bfc9-e38d265bca01/3bfaa551-c7ce-5ef3-9638-3fd775794cd5'
BS = chr(92)


def u():
    return str(uuid.uuid4())


def top_blocks(txt, start_idx):
    """txt[start_idx] の '(' で始まる要素の直下の子要素 (start, end) を返す"""
    res = []
    d = 0
    instr = False
    st = None
    p = start_idx
    while p < len(txt):
        c = txt[p]
        if instr:
            if c == BS:
                p += 1
            elif c == '"':
                instr = False
        else:
            if c == '"':
                instr = True
            elif c == '(':
                d += 1
                if d == 2:
                    st = p
            elif c == ')':
                if d == 2:
                    res.append((st, p + 1))
                d -= 1
                if d == 0:
                    break
        p += 1
    return res, p


items = split_top(s)
tpl = {}
rm = []
for a, b in items:
    t = s[a:b]
    k = kind(t)
    if k in ('lib_symbols', 'sheet_instances', 'title_block', 'version', 'generator', 'generator_version', 'uuid', 'paper'):
        continue
    p = pos(t)
    if p is None:
        continue
    if p[0] < 200:
        if k == 'symbol':
            ref = re.search(r'\(property "Reference" "([^"]+)"', t).group(1)
            tpl[ref] = t
        if k == 'global_label' and 'GPS_1PPS' in t[:40] and p[1] > 190:
            tpl['GL'] = t
        if k == 'text':
            tpl['TEXT'] = t
        rm.append((a, b))
for a, b in sorted(rm, reverse=True):
    a2 = a
    while a2 > 0 and s[a2 - 1] in '\n\t':
        a2 -= 1
    s = s[:a2] + s[b:]


def clone_symbol(base, ref, value, x, y, rot, lib_id=None, hide_texts=False):
    t = tpl[base]
    old_ref = re.search(r'\(property "Reference" "([^"]+)"', t).group(1)
    t = t.replace('"%s"' % old_ref, '"%s"' % ref)
    if value is not None:
        t = re.sub(r'(\(property "Value" ")[^"]*(")', lambda m: m.group(1) + value + m.group(2), t, count=1)
    if lib_id:
        t = re.sub(r'\(lib_id "[^"]+"\)', '(lib_id "%s")' % lib_id, t, count=1)
    mo = re.search(r'\(lib_id "[^"]+"\)\s*\(at ([-\d.]+) ([-\d.]+)', t)
    dx, dy = x - float(mo.group(1)), y - float(mo.group(2))
    t = re.sub(r'\(at ([-\d.]+) ([-\d.]+)( \d+)?\)',
               lambda m: '(at %s %s%s)' % (round(float(m.group(1)) + dx, 4), round(float(m.group(2)) + dy, 4), m.group(3) or ''), t)
    if rot is not None:
        t = re.sub(r'(\(lib_id "[^"]+"\)\s*\(at [-\d.]+ [-\d.]+ )\d+\)', lambda m: m.group(1) + '%d)' % rot, t, count=1)
    t = re.sub(r'\(uuid "[0-9a-f-]+"\)', lambda m: '(uuid "%s")' % u(), t)
    t = re.sub(r'\n\t\t\t\(project "09_domB_gps"\s*\(path "[^"]+"\s*\(reference "[^"]+"\)\s*\(unit \d\)\s*\)\s*\)', '', t)
    if hide_texts:
        for name in ('Reference', 'Value'):
            t = re.sub(r'(\(property "%s" "[^"]*"\s*\(at [-\d.]+ [-\d.]+ \d+\))' % name, lambda m: m.group(1) + '\n\t\t\t(hide yes)', t, count=1)
    return t + '\n'


def wire(x1, y1, x2, y2):
    return '\t(wire\n\t\t(pts\n\t\t\t(xy %s %s) (xy %s %s)\n\t\t)\n\t\t(stroke\n\t\t\t(width 0)\n\t\t\t(type default)\n\t\t)\n\t\t(uuid "%s")\n\t)\n' % (x1, y1, x2, y2, u())


def junction(x, y):
    return '\t(junction\n\t\t(at %s %s)\n\t\t(diameter 0)\n\t\t(color 0 0 0 0)\n\t\t(uuid "%s")\n\t)\n' % (x, y, u())


def glabel(name, x, y, ang):
    t = tpl['GL']
    t = re.sub(r'\(global_label "[^"]+"', '(global_label "%s"' % name, t, count=1)
    t = re.sub(r'\(at [-\d.]+ [-\d.]+ \d+\)', '(at %s %s %d)' % (x, y, ang), t, count=2)
    t = re.sub(r'\(uuid "[0-9a-f-]+"\)', lambda m: '(uuid "%s")' % u(), t)
    return t + '\n'


def prop(n, v, x, y, hide=False, just=None):
    return ('\t\t(property "%s" "%s"\n\t\t\t(at %s %s 0)\n%s\t\t\t(show_name no)\n\t\t\t(do_not_autoplace no)\n\t\t\t(effects\n\t\t\t\t(font\n\t\t\t\t\t(size 1.27 1.27)\n\t\t\t\t)\n%s\t\t\t)\n\t\t)\n'
            % (n, v, round(x, 4), round(y, 4), '\t\t\t(hide yes)\n' if hide else '', '\t\t\t\t(justify %s)\n' % just if just else ''))


out = ''
hx, hy = 63.5, 88.9


def pin_y(n):
    return round(hy - 10.16 + 2.54 * (n - 1), 4)


hdr = ('\t(symbol\n\t\t(lib_id "0my_connector:header_1x10")\n\t\t(at %s %s 0)\n\t\t(unit 1)\n\t\t(body_style 1)\n\t\t(exclude_from_sim no)\n\t\t(in_bom yes)\n\t\t(on_board yes)\n\t\t(in_pos_files yes)\n\t\t(dnp no)\n\t\t(uuid "%s")\n' % (hx, hy, u()))
hdr += prop('Reference', 'J701', hx, hy - 12.7) + prop('Value', 'GF-8801 小基板 1x10', hx, hy + 15.24)
hdr += prop('Footprint', 'Connector_PinHeader_2.54mm:PinHeader_1x10_P2.54mm_Vertical', hx - 2.54, hy - 10.16, True)
hdr += prop('Datasheet', '~', hx, hy, True) + prop('Description', 'GF-8801 breakout board: +5V, GND, 10MPPS, 1PPS, LOCK, ALM_N, TXD, RXD (3.3V CMOS)', hx, hy, True)
for n in range(1, 11):
    hdr += '\t\t(pin "%d"\n\t\t\t(uuid "%s")\n\t\t)\n' % (n, u())
hdr += '\t\t(instances\n\t\t\t(project "ACROSS_V3"\n\t\t\t\t(path "%s"\n\t\t\t\t\t(reference "J701")\n\t\t\t\t\t(unit 1)\n\t\t\t\t)\n\t\t\t)\n\t\t)\n\t)\n' % SHEET
out += hdr
X = 58.42
out += wire(X, pin_y(1), 43.18, pin_y(1))
out += clone_symbol('#PWR09040', '#PWR09201', None, 43.18, pin_y(1), 0, lib_id='0my_schematic:+5V')
out += wire(X, pin_y(3), 43.18, pin_y(3))
out += clone_symbol('#PWR09040', '#PWR09202', None, 43.18, pin_y(3), 0)
out += wire(X, pin_y(2), 55.88, pin_y(2)) + wire(55.88, pin_y(2), 55.88, pin_y(3))
out += wire(X, pin_y(4), 55.88, pin_y(4)) + wire(55.88, pin_y(4), 55.88, pin_y(3))
out += junction(55.88, pin_y(3))
out += clone_symbol('C710', 'C701', '10uF', 48.26, round((pin_y(1) + pin_y(3)) / 2, 4), 0)
out += junction(48.26, pin_y(1)) + junction(48.26, pin_y(3))
sig = [('GPS_10MPPS', 'R710'), ('GPS_1PPS', 'R701'), ('GPS_LOCK', 'R702'), ('GPS_ALM_N', 'R703'), ('GPS_TXD', 'R704'), ('GPS_RXD', 'R705')]
for i, (net, ref) in enumerate(sig):
    y = pin_y(5 + i)
    out += wire(53.34, y, X, y)
    out += clone_symbol('R710', ref, '33', 50.8, y, 90, hide_texts=True)
    out += wire(48.26, y, 45.72, y)
    out += glabel(net, 45.72, y, 180)
out += clone_symbol('TP704', 'TP704', 'TP_GPS_10MPPS', 30.48, 114.3, 0)
out += glabel('GPS_10MPPS', 30.48, 114.3, 270)
out += clone_symbol('TP705', 'TP705', 'TP_GPS_1PPS', 40.64, 114.3, 0)
out += glabel('GPS_1PPS', 40.64, 114.3, 270)
note = ('GF-8801 小基板 (ブレークアウト) との接続: J701 (1x10 ピンヘッダ) = 1: +5V、2〜4: GND、5: GPS_10MPPS、6: GPS_1PPS、7: GPS_LOCK、8: GPS_ALM_N、9: GPS_TXD、10: GPS_RXD。'
        + BS + 'n'
        + '信号は 3.3V CMOS (SoC の VDD と直結)、各信号に直列抵抗 33Ω。TXD/RXD の名前は SoC 基準 (GPS_TXD = SoC 送信 = GPS の RXD)。5V は +5V から (約 0.15A)、小基板で 3.7V を作る。絶縁なし。')
t = tpl['TEXT']
t = re.sub(r'\(text "[^"]*"', lambda m: '(text "%s"' % note, t, count=1)
t = re.sub(r'\(uuid "[0-9a-f-]+"\)', lambda m: '(uuid "%s")' % u(), t)
out += t + '\n'
m = s.rindex('\n)')
s = s[:m + 1] + out + s[m + 1:]


def lib_end(txt):
    k = txt.index('(lib_symbols')
    kids, p = top_blocks(txt, k)
    return k, p, kids


def embed(libfile, name):
    lib = open('C:/OneDrive_link/KiCAD/LIBRARY/' + libfile, encoding='utf8').read()
    i = lib.index('\t(symbol "%s"' % name)
    j = lib.find('\n\t(symbol "', i + 10)
    if j < 0:
        j = lib.rindex('\n)')
    blk = lib[i:j].rstrip('\n')
    libname = libfile.replace('.kicad_sym', '')
    blk = blk.replace('(symbol "%s"' % name, '(symbol "%s:%s"' % (libname, name), 1)
    return '\n'.join('\t' + l if l else l for l in blk.split('\n'))


k, p, kids = lib_end(s)
add = ''
for lf, nm in (('0my_connector.kicad_sym', 'header_1x10'), ('0my_schematic.kicad_sym', '+5V')):
    if '(symbol "%s:%s"' % (lf.replace('.kicad_sym', ''), nm) not in s[k:p]:
        add += '\n' + embed(lf, nm)
s = s[:p].rstrip('\n\t') + add + '\n\t' + s[p:]
# 使われていない lib_symbols を削除
lib_ids = set(re.findall(r'\(lib_id "([^"]+)"\)', s))
k, p, kids = lib_end(s)
for a, b in reversed(kids):
    nm = re.match(r'\(symbol "([^"]+)"', s[a:b]).group(1)
    if nm not in lib_ids:
        a2 = a
        while a2 > 0 and s[a2 - 1] in '\n\t':
            a2 -= 1
        s = s[:a2] + s[b:]
open(F, 'w', encoding='utf8', newline='').write(s)
print('ok', sorted(lib_ids))
