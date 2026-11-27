# 部品を少しだけ動かし、そのパッドにつながる線の端も一緒に動かす (2026-11-24、配線後の微調整用)
#   線の端がパッドの中にあるものを、部品と同じだけずらす (線は斜めになることがある)。大きく動かすときは使わない。
#   動かしたあとは DRC で確かめること。
# usage: python nudge.py pcb REF dx dy [REF dx dy ...] [-o out]
import sys
import pcbnew

a = sys.argv[1:]
out = None
if '-o' in a:
    i = a.index('-o'); out = a[i + 1]; del a[i:i + 2]
pcb = a[0]; out = out or pcb
b = pcbnew.LoadBoard(pcb)
mm = pcbnew.FromMM
tracks = [t for t in b.GetTracks() if not isinstance(t, pcbnew.PCB_VIA)]
for k in range(1, len(a), 3):
    ref, dx, dy = a[k], float(a[k + 1]), float(a[k + 2])
    fp = b.FindFootprintByReference(ref)
    d = pcbnew.VECTOR2I(mm(dx), mm(dy))
    n = 0
    for pd in fp.Pads():
        for t in tracks:
            if t.GetNetCode() != pd.GetNetCode() or not pd.IsOnLayer(t.GetLayer()):
                continue
            for get, set_ in ((t.GetStart, t.SetStart), (t.GetEnd, t.SetEnd)):
                p = get()
                if pd.HitTest(p):
                    set_(p + d); n += 1
    fp.Move(d)
    print(ref, 'moved', dx, dy, '線の端', n)
pcbnew.ZONE_FILLER(b).Fill(b.Zones())  # 穴のある部品を動かしたときのため、ゾーンを塗り直す
b.Save(out)
