# 基板の現状を調べる (部品・ネット・ゾーン) → JSON と要約を出す (2026-11-21)
# usage: python survey.py out.json
import sys, json
import pcbnew

PCB = 'C:/MyWorks/ACROSS_V3_STM32/kicad/ACROSS_V3.kicad_pcb'
b = pcbnew.LoadBoard(PCB)
mm = pcbnew.ToMM
fps = []
for f in b.GetFootprints():
    bb = f.GetCourtyard(pcbnew.F_CrtYd if not f.IsFlipped() else pcbnew.B_CrtYd).BBox() if False else f.GetBoundingBox(False)
    pads = [{'n': p.GetNumber(), 'net': p.GetNetname(), 'x': round(mm(p.GetPosition().x), 3), 'y': round(mm(p.GetPosition().y), 3),
             'th': p.GetAttribute() == pcbnew.PAD_ATTRIB_PTH, 'sx': round(mm(p.GetSize(pcbnew.F_Cu).x), 3), 'sy': round(mm(p.GetSize(pcbnew.F_Cu).y), 3)}
            for p in f.Pads()]
    fps.append({'ref': f.GetReference(), 'val': f.GetValue(), 'fp': str(f.GetFPID().GetLibItemName()),
                'x': round(mm(f.GetPosition().x), 3), 'y': round(mm(f.GetPosition().y), 3), 'rot': f.GetOrientationDegrees(),
                'back': f.IsFlipped(), 'bbox': [round(mm(bb.GetLeft()), 2), round(mm(bb.GetTop()), 2), round(mm(bb.GetRight()), 2), round(mm(bb.GetBottom()), 2)],
                'pads': pads})
nets = {}
for f in fps:
    for p in f['pads']:
        if p['net']:
            nets.setdefault(p['net'], []).append(f['ref'] + '.' + p['n'])
zones = [{'net': z.GetNetname(), 'layers': [b.GetLayerName(l) for l in z.GetLayerSet().Seq()], 'keepout': z.GetIsRuleArea()} for z in b.Zones()]
json.dump({'fps': fps, 'nets': nets, 'zones': zones, 'tracks': len(b.GetTracks())}, open(sys.argv[1], 'w', encoding='utf8'), ensure_ascii=False)
print('footprints', len(fps), 'nets', len(nets), 'zones', len(zones), 'tracks', len(b.GetTracks()))
print('has DSN export', hasattr(pcbnew, 'ExportSpecctraDSN'), 'SES import', hasattr(pcbnew, 'ImportSpecctraSES'))
big = sorted(nets.items(), key=lambda kv: -len(kv[1]))[:25]
for n, m in big:
    print(f'{len(m):4d} {n}')
for f in sorted(fps, key=lambda f: -len(f['pads']))[:15]:
    print(f['ref'], f['val'], f['fp'], len(f['pads']), f['x'], f['y'], 'B' if f['back'] else 'F')
