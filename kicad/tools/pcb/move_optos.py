# ドメイン C のフォトカプラ (U701〜U704) を 1 列に並べ直す (2026-11-22)
#   以前の配置: U701/U703 (x=126) の 2 次側の右に U702/U704 (x=140) の 1 次側があり、
#   2 次側 (ISO_C) の線が J702 へ行くには 1 次側を横切るしかなかった (r2 で絶縁 2mm 違反)。
#   新しい配置: 4 個とも x=140、1 次側 (ピン 1・2) は左、2 次側 (ピン 3・4) は右 = J702 側。
#   上から J702 のピン順 (COM, OC4, OC3, OC2, OC1) に合わせて U704, U703, U702, U701。
#   この部品につながる配線 (OC*_OUT, OC_COM, R70x-Pad2) と、ピン 2 (GND) から面へのビアは消す (あとで引き直す)。
# usage: python move_optos.py [pcb]
import sys
import pcbnew

PCB = sys.argv[1] if len(sys.argv) > 1 else 'C:/MyWorks/ACROSS_V3_STM32/kicad/ACROSS_V3.kicad_pcb'
NEW = {'U704': 56.9, 'U703': 62.6, 'U702': 68.3, 'U701': 74.0}
X = 140.0
mm = pcbnew.FromMM
b = pcbnew.LoadBoard(PCB)
parts = [b.FindFootprintByReference(r) for r in NEW]
nets = set()
gnd_pads = []
for f in parts:
    for p in f.Pads():
        if p.GetNetname() == 'GND':
            gnd_pads.append(p.GetPosition())
        else:
            nets.add(p.GetNetname())
dele = []
for t in b.GetTracks():
    if t.GetNetname() in nets:
        dele.append(t)
# GND のドッグボーン: パッドの位置から出る線と、その先のビア
gnd_ends = []
for t in b.GetTracks():
    if t.Type() == pcbnew.PCB_TRACE_T and t.GetNetname() == 'GND':
        for a, e in ((t.GetStart(), t.GetEnd()), (t.GetEnd(), t.GetStart())):
            if any(a == q for q in gnd_pads):
                dele.append(t)
                gnd_ends.append(e)
for t in b.GetTracks():
    if t.Type() == pcbnew.PCB_VIA_T and t.GetNetname() == 'GND' and any(t.GetPosition() == e for e in gnd_ends):
        dele.append(t)
print('消す', len(dele), '本 (ネット', len(nets), ')')
for t in {id(x): x for x in dele}.values():
    b.Remove(t)
for f in parts:
    f.SetOrientationDegrees(0)
    f.SetPosition(pcbnew.VECTOR2I(mm(X), mm(NEW[f.GetReference()])))
    print(f.GetReference(), X, NEW[f.GetReference()])
pcbnew.ZONE_FILLER(b).Fill(b.Zones())
b.Save(PCB)
