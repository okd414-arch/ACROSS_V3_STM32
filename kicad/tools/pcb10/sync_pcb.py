# 回路図の部品番号の振り直し (refmap) と最新のネットリストを、基板に反映する (位置は変えない)
# usage: python sync_pcb.py netlist.xml [refmap.json]
import sys, json, collections, xml.etree.ElementTree as ET
import pcbnew
KICAD = 'C:/MyWorks/ACROSS_V3_STM32/kicad'
PCB = KICAD + '/ACROSS_V3.kicad_pcb'
root = ET.parse(sys.argv[1]).getroot()
mp = json.load(open(sys.argv[2], encoding='utf8')) if len(sys.argv) > 2 else {}
comps = {}
for c in root.find('components'):
    sp = c.find('sheetpath')
    comps[c.get('ref')] = dict(path=sp.get('tstamps') + c.find('tstamps').text.split()[0], sheet=sp.get('names'))
padnet = {}
netnames = []
for n in root.find('nets'):
    netnames.append(n.get('name'))
    for nd in n:
        padnet[(nd.get('ref'), nd.get('pin'))] = n.get('name')
b = pcbnew.LoadBoard(PCB)
fps = list(b.GetFootprints())
# 1. 部品番号 (同時に置き換えるため、いったん全部の旧→新の表を作る)
newref = {}
for fp in fps:
    old = fp.GetReference()
    newref[old] = mp.get(old, old)
for fp in fps:
    fp.SetReference(newref[fp.GetReference()])
miss = [fp.GetReference() for fp in fps if fp.GetReference() not in comps]
assert not miss, miss
# 2. パス (シートのUUID + 部品のUUID)、シート名
for fp in fps:
    c = comps[fp.GetReference()]
    fp.SetPath(pcbnew.KIID_PATH(c['path']))
    fp.SetSheetname(c['sheet'].strip('/').split('/')[-1] if c['sheet'] != '/' else '')
# 3. ネット: 無ければ作り、全パッドへ割り当て。使われなくなったネットは消す
items = {}
for name in netnames:
    ni = b.FindNet(name)
    if ni is None:
        ni = pcbnew.NETINFO_ITEM(b, name)
        b.Add(ni)
    items[name] = ni
bad = 0
for fp in fps:
    for pad in fp.Pads():
        nn = padnet.get((fp.GetReference(), pad.GetNumber()))
        if nn:
            pad.SetNet(items[nn])
        elif pad.GetNetname():
            bad += 1
used = set(p.GetNetname() for fp in fps for p in fp.Pads())
removed = 0
for name, ni in list(b.GetNetInfo().NetsByName().items()):
    n = str(name)
    if n and n not in padnet.values() and n not in used:
        b.Remove(ni); removed += 1
b.Save(PCB)
print('parts', len(fps), 'nets', len(netnames), 'pads with stale net', bad, 'removed nets', removed)
