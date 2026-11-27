# ネットクラスと絶縁・インピーダンスの DRC ルールを作る (2026-11-20、2026-11-21 配線幅を確定)
#   .kicad_pro の net_settings (classes / netclass_patterns) と ACROSS_V3.kicad_dru を書き出す。何度でも再実行できる。
#   ISO_A / ISO_D / ISO_C のメンバー: parts.json (部品の所属 dom) を渡せば基板のパッドから判定し直す。
#   引数なしなら .kicad_pro にある今の割り当てをそのまま使う。
#   インピーダンス制御の配線幅は impedance_fd.py (2D 差分法、積層 JLC08161H-3313) で計算した値。
#     外層 (L1/L8、3313 0.0994mm 上のマイクロストリップ): 50Ω = 0.16、100Ω差動 = 0.11/0.15、90Ω差動 = 0.14/0.13
#     内層 (L3/L6、コア 0.1mm で GND、2116×3 で電源面): 50Ω = 0.12、100Ω差動 = 0.10/0.20、90Ω差動 = 0.12/0.16
#   ネットクラスの値は内層 (DDR は内層が主)。外層の幅は .kicad_dru のルールで層ごとに指定する。
# usage: python make_netclasses.py [parts.json]   (KiCad の Python で)
import sys, json, re, copy
import pcbnew

KICAD = 'C:/MyWorks/ACROSS_V3_STM32/kicad'
PCB = KICAD + '/ACROSS_V3.kicad_pcb'
PRO = KICAD + '/ACROSS_V3.kicad_pro'
DRU = KICAD + '/ACROSS_V3.kicad_dru'

pro = json.load(open(PRO, encoding='utf8'))
ns = pro.setdefault('net_settings', {})
b = pcbnew.LoadBoard(PCB)
iso = {'A': [], 'D': [], 'C': []}
if len(sys.argv) > 1:
    parts = json.load(open(sys.argv[1], encoding='utf8'))
    # 絶縁をまたぐ部品のピンの側
    SIDE = {'U601': {'3': 'A', '4': 'A'}, 'U609': {'3': 'A', '4': 'A'}, 'U606': {str(i): 'A' for i in range(1, 9)},
            'U607': {str(i): 'A' for i in range(5, 9)}, 'U705': {'3': 'D', '4': 'D'}, 'U707': {str(i): 'D' for i in range(5, 9)},
            'U701': {'3': 'C', '4': 'C'}, 'U702': {'3': 'C', '4': 'C'}, 'U703': {'3': 'C', '4': 'C'}, 'U704': {'3': 'C', '4': 'C'}}
    netsides = {}
    for f in b.GetFootprints():
        r = f.GetReference()
        if r.startswith('#'):
            continue
        dom = parts.get(r, {}).get('dom', 'P')
        for p in f.Pads():
            n = p.GetNetname()
            if not n or n.startswith('unconnected'):
                continue
            if r in SIDE:
                side = SIDE[r].get(p.GetNumber(), 'P')
            elif r == 'J702':
                side = 'C'
            else:
                side = {'A': 'A', 'D': 'D', 'OC': 'C'}.get(dom, 'P')
            netsides.setdefault(n, set()).add(side)
    for n, s in netsides.items():
        if len(s) == 1 and list(s)[0] in iso:
            iso[list(s)[0]].append(n)
else:
    for p in ns.get('netclass_patterns', []):
        if p['netclass'].startswith('ISO_'):
            iso[p['netclass'][4]].append(p['pattern'])
allnets = [str(n) for n in b.GetNetInfo().NetsByName().keys() if str(n)]


def pick(rx):
    return sorted(n for n in allnets if re.search(rx, n))


groups = {
    # 電源とGND (面のネットは、パッドから面へのビアまでの短い線)。スイッチノード・入力の経路も含む (2026-11-21 追加)
    'POWER': pick(r'^(VDD$|VDD_CORE|VDD_DDR|VDDA|VDD_USB|VDD_SD|\+3\.3V$|\+5V$|\+24V$|VBUS_SW|OTG_VBUS|\+9V_|\+5V_|\+3\.3V_|VREF_DDR|VTT_DDR'
                  r'|GND$|GND_A$|GND_D$)|PM_BST$|^Net-\((U104-VLX_\w+|C110-Pad1|D101-K|D102-K|D103-K|J101-Pin_2|J402-VBUS|U403-VBUS|U404-VBUS|U706-LX)\)$'),
    'DDR_DATA': pick(r'^DDR_(DQ\d+|DQM\d)$'),
    'DDR_ADDR': pick(r'^DDR_(A\d+|BA\d|RASN|CASN|WEN|CKE|CSN|ODT|RESETN)$'),
    'DDR_DIFF': pick(r'^DDR_(CLK[PN]|DQS\d[PN])$'),
    'USB_DIFF': pick(r'^USB[12]_D[PM]$'),
    'HS_SIG': pick(r'^(ETH_(REF_CLK|CRS_DV|TX_EN|RXD\d|TXD\d)|LCD_|EMMC_(CK|CMD|D\d)|SD_(CK|CMD|D\d)|GPS_10MPPS)'),
}
default = [c for c in ns['classes'] if c['name'] == 'Default'][0]
# Default: 配線 0.12 / 間隔 0.1 (0.8mm ピッチ BGA のビアの間 0.35 を 1 本通せる値。内層では 50Ω)、
#   ビアは JLCPCB の割増なしの下限 (0.45 / 0.2)
default.update(track_width=0.12, clearance=0.1, via_diameter=0.45, via_drill=0.2, diff_pair_width=0.15, diff_pair_gap=0.15, diff_pair_via_gap=0.25)


def cls(name, **kw):
    c = copy.deepcopy(default)
    c['name'] = name
    c['priority'] = 100
    c.update(kw)
    return c


classes = [default,
           # 電源: 自動配線は 0.25 (PMIC の 0.4mm ピッチに入る幅) で通し、配線後に余裕のある所を太くする (widen_power.py)
           cls('POWER', track_width=0.25, clearance=0.15, via_diameter=0.45, via_drill=0.2),
           # 50Ω 単線 (内層 0.12)。間隔 0.1 (BGA のビアの間を通すため。DDR は配線長が短いのでクロストークは許容)
           cls('DDR_DATA', track_width=0.10, clearance=0.09),
           cls('DDR_ADDR', track_width=0.10, clearance=0.09),
           # 100Ω 差動 (内層 0.10 / 0.20)
           cls('DDR_DIFF', track_width=0.10, clearance=0.09, diff_pair_width=0.10, diff_pair_gap=0.20),
           # 90Ω 差動 (外層 0.14 / 0.13 が主。ネットクラスは外層の値)
           cls('USB_DIFF', track_width=0.14, clearance=0.15, diff_pair_width=0.14, diff_pair_gap=0.13),
           # 50Ω 単線 (ETH RMII・LCD・eMMC/SD・10MPPS)。ネットクラスは内層 0.12、外層は DRC ルールで 0.16 (opt)
           cls('HS_SIG', track_width=0.12, clearance=0.1),
           cls('ISO_A', clearance=0.15), cls('ISO_D', clearance=0.15), cls('ISO_C', clearance=0.15)]
ns['classes'] = classes
pats = []
for k in ('POWER', 'DDR_DATA', 'DDR_ADDR', 'DDR_DIFF', 'USB_DIFF', 'HS_SIG'):
    pats += [{'netclass': k, 'pattern': n} for n in groups[k]]
for k, key in (('ISO_A', 'A'), ('ISO_D', 'D'), ('ISO_C', 'C')):
    pats += [{'netclass': k, 'pattern': n} for n in sorted(iso[key])]
ns['netclass_patterns'] = pats
# 文字の高さの下限 (ユーザー許可: 0.75mm まで)
pro['board']['design_settings']['rules']['min_text_height'] = 0.75
json.dump(pro, open(PRO, 'w', encoding='utf8'), ensure_ascii=False, indent=2)
rule = '''(version 1)
# KiCad のルールは後に書いたものが優先。BGA の緩和を先に書き、絶縁ルールで上書きされるようにする
# BGA (U1、DDR3L) の下: 高速の線も間隔 0.1 まで許す
(rule "bga_escape_clearance"
  (condition "A.insideCourtyard('U1') || A.insideCourtyard('U301') || A.insideCourtyard('U302') || A.insideCourtyard('U104')")
  (constraint clearance (min 0.09mm))
  (constraint hole_clearance (min 0.15mm)))
# eMMC (U401、0.5mm ピッチ) のパッド内ビア: 0.25 / 0.15 (JLCPCB の多層の下限、穴埋め VIP)
(rule "emmc_vip"
  (condition "A.Type == 'Via' && (A.insideCourtyard('U401') || A.insideCourtyard('U1') || A.insideCourtyard('U301') || A.insideCourtyard('U302'))")
  (constraint hole_size (min 0.15mm))
  (constraint via_diameter (min 0.25mm))
  (constraint annular_width (min 0.05mm)))
(rule "emmc_clearance"
  (condition "A.insideCourtyard('U401')")
  (constraint clearance (min 0.09mm))
  (constraint hole_clearance (min 0.15mm)))
# 絶縁ドメインの沿面・空間 (2.0mm): ISO_A / ISO_D / ISO_C のネットと、それ以外のネットの間。パッドどうしは除く (絶縁部品のピン間隔は部品で決まる)
(rule "iso_A_2mm" (severity error)
  (condition "(A.NetClass == 'ISO_A') != (B.NetClass == 'ISO_A') && (A.Type != 'Pad' || B.Type != 'Pad') && A.NetName != 'unconnected-*' && B.NetName != 'unconnected-*' && A.NetName != '' && B.NetName != '' && ((A.Type != 'Pad' && B.Type != 'Pad') || (!A.memberOfFootprint('U601') && !B.memberOfFootprint('U601') && !A.memberOfFootprint('U606') && !B.memberOfFootprint('U606') && !A.memberOfFootprint('U607') && !B.memberOfFootprint('U607') && !A.memberOfFootprint('U609') && !B.memberOfFootprint('U609') && !A.memberOfFootprint('U701') && !B.memberOfFootprint('U701') && !A.memberOfFootprint('U702') && !B.memberOfFootprint('U702') && !A.memberOfFootprint('U703') && !B.memberOfFootprint('U703') && !A.memberOfFootprint('U704') && !B.memberOfFootprint('U704') && !A.memberOfFootprint('U705') && !B.memberOfFootprint('U705') && !A.memberOfFootprint('U707') && !B.memberOfFootprint('U707')))")
  (constraint clearance (min 2mm)))
(rule "iso_D_2mm" (severity error)
  (condition "(A.NetClass == 'ISO_D') != (B.NetClass == 'ISO_D') && (A.Type != 'Pad' || B.Type != 'Pad') && A.NetName != 'unconnected-*' && B.NetName != 'unconnected-*' && A.NetName != '' && B.NetName != '' && ((A.Type != 'Pad' && B.Type != 'Pad') || (!A.memberOfFootprint('U601') && !B.memberOfFootprint('U601') && !A.memberOfFootprint('U606') && !B.memberOfFootprint('U606') && !A.memberOfFootprint('U607') && !B.memberOfFootprint('U607') && !A.memberOfFootprint('U609') && !B.memberOfFootprint('U609') && !A.memberOfFootprint('U701') && !B.memberOfFootprint('U701') && !A.memberOfFootprint('U702') && !B.memberOfFootprint('U702') && !A.memberOfFootprint('U703') && !B.memberOfFootprint('U703') && !A.memberOfFootprint('U704') && !B.memberOfFootprint('U704') && !A.memberOfFootprint('U705') && !B.memberOfFootprint('U705') && !A.memberOfFootprint('U707') && !B.memberOfFootprint('U707')))")
  (constraint clearance (min 2mm)))
(rule "iso_C_2mm" (severity error)
  (condition "(A.NetClass == 'ISO_C') != (B.NetClass == 'ISO_C') && (A.Type != 'Pad' || B.Type != 'Pad') && A.NetName != 'unconnected-*' && B.NetName != 'unconnected-*' && A.NetName != '' && B.NetName != '' && ((A.Type != 'Pad' && B.Type != 'Pad') || (!A.memberOfFootprint('U601') && !B.memberOfFootprint('U601') && !A.memberOfFootprint('U606') && !B.memberOfFootprint('U606') && !A.memberOfFootprint('U607') && !B.memberOfFootprint('U607') && !A.memberOfFootprint('U609') && !B.memberOfFootprint('U609') && !A.memberOfFootprint('U701') && !B.memberOfFootprint('U701') && !A.memberOfFootprint('U702') && !B.memberOfFootprint('U702') && !A.memberOfFootprint('U703') && !B.memberOfFootprint('U703') && !A.memberOfFootprint('U704') && !B.memberOfFootprint('U704') && !A.memberOfFootprint('U705') && !B.memberOfFootprint('U705') && !A.memberOfFootprint('U707') && !B.memberOfFootprint('U707')))")
  (constraint clearance (min 2mm)))

# インピーダンス制御 (impedance_fd.py、積層 JLC08161H-3313)。opt = 目標の幅、min = BGA などで細くする下限
(rule "z50_outer"
  (layer outer)
  (condition "A.NetClass == 'DDR_DATA' || A.NetClass == 'DDR_ADDR' || A.NetClass == 'HS_SIG'")
  (constraint track_width (min 0.1mm) (opt 0.16mm)))
(rule "z50_inner"
  (layer inner)
  (condition "A.NetClass == 'DDR_DATA' || A.NetClass == 'DDR_ADDR' || A.NetClass == 'HS_SIG'")
  (constraint track_width (min 0.09mm) (opt 0.12mm)))
(rule "z100_outer"
  (layer outer)
  (condition "A.NetClass == 'DDR_DIFF'")
  (constraint track_width (min 0.09mm) (opt 0.11mm))
  (constraint diff_pair_gap (min 0.1mm) (opt 0.15mm)))
(rule "z100_inner"
  (layer inner)
  (condition "A.NetClass == 'DDR_DIFF'")
  (constraint track_width (min 0.09mm) (opt 0.10mm))
  (constraint diff_pair_gap (min 0.1mm) (opt 0.20mm)))
(rule "z90_outer"
  (layer outer)
  (condition "A.NetClass == 'USB_DIFF'")
  (constraint track_width (min 0.1mm) (opt 0.14mm))
  (constraint diff_pair_gap (min 0.1mm) (opt 0.13mm)))
(rule "z90_inner"
  (layer inner)
  (condition "A.NetClass == 'USB_DIFF'")
  (constraint track_width (min 0.1mm) (opt 0.12mm))
  (constraint diff_pair_gap (min 0.1mm) (opt 0.16mm)))
'''
open(DRU, 'w', encoding='utf8').write(rule)
for k in groups:
    print(k, len(groups[k]))
for k in iso:
    print('ISO', k, len(iso[k]), sorted(iso[k])[:10])
