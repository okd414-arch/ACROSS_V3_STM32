# 長すぎる DDR の区間をはがす (2026-11-23)。引き直すと短くなることを期待する (蛇行で合わせる量を減らす)
#   グループ (レーン、A/C の区間 1、A/C の区間 2) の中央値より LIM mm 以上長い区間の線を消す。ビアは後で掃除 (clean_dangling)。
#   KiCad の Python。plan は ddr_tune_plan.py の JSON。
# usage: python ddr_strip_long.py pcb plan.json [LIM=8]
import sys, json, re, statistics
import pcbnew

PCB, plan = sys.argv[1], json.load(open(sys.argv[2], encoding='utf8'))
LIM = float(sys.argv[3]) if len(sys.argv) > 3 else 8.0
groups = {}
for n, legs in plan.items():
    for lg, v in legs.items():
        if v is None:
            continue
        m = re.match(r'DDR_DQ(\d+)$', n) or re.match(r'DDR_DQ[MS](\d)', n)
        if m:
            k = int(m.group(1)) // 8 if n.startswith('DDR_DQ') and n[6:].isdigit() else int(m.group(1))
            g = f'lane{k}'
        elif 'CLK' in n or 'RESETN' in n:
            continue
        else:
            g = 'ac_' + lg
        groups.setdefault(g, []).append((n, lg, v))
kill = set()
for g, L in groups.items():
    med = statistics.median(v['len'] for _, _, v in L)
    for n, lg, v in L:
        if v['len'] > med + LIM and not re.search(r'DQS', n):
            print(f'{g:16s} {n:12s} {lg:10s} {v["len"]:6.1f} (中央値 {med:.1f})')
            kill |= {s['uuid'] for s in v['segs']}
b = pcbnew.LoadBoard(PCB)
rm = [t for t in b.GetTracks() if t.m_Uuid.AsString() in kill]
for t in rm:
    b.Remove(t)
pcbnew.ZONE_FILLER(b).Fill(b.Zones())
b.Save(PCB)
print('消した線', len(rm))
