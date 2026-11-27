# DDR のバイトレーン 1 と 2 を、メモリ側で入れ替える (2026-11-23)
#   AN5122 3.1 節「4 つのバイトは入れ替え可能 (バイト内のビットも)」。
#   前: U1 のレーン 1 (U1 の下寄り) → U301 (上)、レーン 2 (U1 の上寄り) → U302 (下) で、U1 の前で交差していた。
#   後: レーン 2 → U301、レーン 1 → U302。DQ(8+i) <-> DQ(16+i)、DQS1 <-> DQS2、DQM1 <-> DQM2 (メモリのピン側だけ)。
#   回路図 03_ddr.kicad_sch: U301 の横 (x=58.42) と U302 の横 (x=124.46) のグローバルラベルの名前を入れ替える。U1 の横 (x=203.2) はそのまま。
#   基板: U301 / U302 のパッドのネットを入れ替え、そのネットの配線は消す (引き直す)。
# usage: python ddr_lane_swap.py sch    (通常の Python で回路図)
#        python ddr_lane_swap.py pcb FILE (KiCad の Python で基板)
import sys, re

M = {}
for i in range(8):
    M[f'DDR_DQ{8 + i}'] = f'DDR_DQ{16 + i}'
    M[f'DDR_DQ{16 + i}'] = f'DDR_DQ{8 + i}'
for s in ('P', 'N'):
    M[f'DDR_DQS1{s}'] = f'DDR_DQS2{s}'
    M[f'DDR_DQS2{s}'] = f'DDR_DQS1{s}'
M['DDR_DQM1'] = 'DDR_DQM2'
M['DDR_DQM2'] = 'DDR_DQM1'

if sys.argv[1] == 'sch':
    F = 'C:/MyWorks/ACROSS_V3_STM32/kicad/03_ddr.kicad_sch'
    t = open(F, encoding='utf8').read()
    n = 0

    def rep(m):
        global n
        if m.group(3) in ('58.42', '124.46') and m.group(1) in M:
            n += 1
            return m.group(0).replace(f'"{m.group(1)}"', f'"{M[m.group(1)]}"', 1)
        return m.group(0)
    t2 = re.sub(r'\(global_label "([^"]+)"(\s+\(shape \w+\)\s+\(at )([\d.\-]+) ', rep, t)
    open(F, 'w', encoding='utf8', newline='').write(t2)
    print('入れ替えたラベル', n)
else:
    import pcbnew
    PCB = sys.argv[2]
    b = pcbnew.LoadBoard(PCB)
    n = 0
    for ref in ('U301', 'U302'):
        for pd in b.FindFootprintByReference(ref).Pads():
            nn = pd.GetNetname()
            if nn in M:
                pd.SetNet(b.FindNet(M[nn]))
                n += 1
    kill = [t for t in b.GetTracks() if t.GetNetname() in M]
    for t in kill:
        b.Remove(t)
    pcbnew.ZONE_FILLER(b).Fill(b.Zones())
    b.Save(PCB)
    print('入れ替えたパッド', n, '消した線', len(kill))
