# 遠回りのネットを引き直して短くする (2026-11-25、配線が全部終わったあとの後処理)
#   1) detour.py と同じ物差し (引いた線の長さ ÷ パッドの最小全域木) で、遠回りのネットを選ぶ (比 >= 1.5、余分 >= 5mm)
#   2) 8 本ずつ (環境変数 DF_GROUP): そのネットの線・ビアを全部消す (差動ペアは相方も) → mr_route で引く (残れば はがして引く) → 掃除
#   3) 採用の条件: 未配線 0、DRC の違反 (シルク・ライブラリ以外) が増えない、その組の線の長さの合計が短くなる、
#      DDR の規則の外れ (ddr_check) が増えない。だめなら元に戻し、組が 2 本以上なら 1 本ずつに分けてやり直す
#   一時ファイルは TMP/TEMP (呼ぶ側で分ける)。パスは絶対パスで渡すこと。
# usage: python detour_fix.py <abs pcb> [比の下限 1.5] [--nets nets.json (ネット名の一覧。指定すると比で選ばずにこれを直す)]
import sys, subprocess, shutil, json, os, tempfile, re, collections

K = 'C:/MyWorks/ACROSS_V3_STM32/kicad'
KPY = 'C:/Program Files/KiCad/10.0/bin/python.exe'
T = K + '/tools/pcb/'
PCB = os.path.abspath(sys.argv[1])
NETS = json.load(open(sys.argv[sys.argv.index('--nets') + 1], encoding='utf8')) if '--nets' in sys.argv else None
LIM = float(sys.argv[2]) if len(sys.argv) > 2 and not sys.argv[2].startswith('--') else 1.5
W = os.path.dirname(PCB)
BK = os.path.join(W, 'bk.kicad_pcb')
NORIP = os.environ.get('DF_NORIP') == '1'  # 並列で回すときは他のネットをはがさない (あとで写しをまとめるため)
RIPOWN = os.environ.get('DF_RIP_OWN') == '1'  # 受け持ちのネット (--nets) に限って、はがして引いてよい
GS = int(os.environ.get('DF_GROUP', '8'))  # 1 組のネットの数
IGN = {'silk_overlap', 'silk_over_copper', 'lib_footprint_issues', 'lib_footprint_mismatch', 'copper_sliver'}

HELP = r'''
import pcbnew, sys, json, math, collections
b = pcbnew.LoadBoard(sys.argv[1]); T = pcbnew.ToMM
mode = sys.argv[2]
if mode == 'len':
    L = collections.Counter(); V = collections.Counter()
    for t in b.GetTracks():
        if t.Type() == pcbnew.PCB_VIA_T: V[t.GetNetname()] += 1
        else: L[t.GetNetname()] += T(t.GetLength())
    pads = collections.defaultdict(list)
    for p in b.GetPads():
        if p.GetNetname(): pads[p.GetNetname()].append((T(p.GetPosition().x), T(p.GetPosition().y)))
    zn = set(z.GetNetname() for z in b.Zones())
    out = {}
    for n, l in L.items():
        P = pads.get(n, [])
        if len(P) < 2 or n in zn: continue
        inT = [False] * len(P); d = [1e9] * len(P); d[0] = 0; m = 0
        for _ in P:
            i = min((k for k in range(len(P)) if not inT[k]), key=lambda k: d[k]); inT[i] = True; m += d[i]
            for k in range(len(P)):
                if not inT[k]: d[k] = min(d[k], math.dist(P[i], P[k]))
        out[n] = [l, m, V[n]]
    json.dump(out, open(sys.argv[3], 'w', encoding='utf8'))
elif mode == 'unc':
    # 全部はがしたネットの未配線: パッドの最小全域木の辺を drc_sum.json と同じ形で書く
    nets = set(json.load(open(sys.argv[3], encoding='utf8')))
    by = collections.defaultdict(list)
    for p in b.GetPads():
        if p.GetNetname() in nets: by[p.GetNetname()].append(p)
    un = []
    for n, P in by.items():
        C = [(T(p.GetPosition().x), T(p.GetPosition().y)) for p in P]
        inT = [False] * len(P); d = [1e9] * len(P); par = [-1] * len(P); d[0] = 0
        for _ in P:
            i = min((k for k in range(len(P)) if not inT[k]), key=lambda k: d[k]); inT[i] = True
            if par[i] >= 0:
                un.append({'items': [{'uuid': P[j].m_Uuid.AsString(), 'pos': {'x': C[j][0], 'y': C[j][1]},
                                      'description': f'パッド [{n}]'} for j in (par[i], i)]})
            for k in range(len(P)):
                if not inT[k] and math.dist(C[i], C[k]) < d[k]: d[k] = math.dist(C[i], C[k]); par[k] = i
    json.dump({'violations': [], 'unconnected_items': un}, open(sys.argv[4], 'w', encoding='utf8'), ensure_ascii=False)
    print('unc', len(un))
elif mode == 'ucount':
    b.BuildConnectivity(); print('UCOUNT', b.GetConnectivity().GetUnconnectedCount(False))
elif mode == 'rip':
    nets = set(json.load(open(sys.argv[3], encoding='utf8')))
    rm = [t for t in b.GetTracks() if t.GetNetname() in nets]
    for t in rm: b.Remove(t)
    b.Save(sys.argv[1]); print('rip', len(rm))
'''
HP = os.path.join(W, '_df_help.py')
open(HP, 'w', encoding='utf8').write(HELP)


def run(cmd, env=None):
    e = dict(os.environ)
    if env:
        e.update(env)
    p = subprocess.run(cmd, capture_output=True, text=True, encoding='utf8', errors='replace', cwd=W, env=e)
    return p.stdout + p.stderr


def lengths():
    j = os.path.join(W, '_len.json')
    run([KPY, HP, PCB, 'len', j])
    return json.load(open(j, encoding='utf8'))


def drc():
    run([sys.executable, T + 'drc_sum.py', PCB, '0'])
    d = json.load(open(os.path.join(tempfile.gettempdir(), 'drc_sum.json'), encoding='utf8'))
    c = collections.Counter(v['type'] for v in d['violations'] if v['type'] not in IGN)
    global UNETS
    UNETS = set()
    for u in d['unconnected_items']:
        m = re.search(r'\[([^\]]+)\]', u['items'][0]['description'])
        if m:
            UNETS.add(m.group(1))
    return len(d['unconnected_items']), sum(c.values()), c


UNETS = set()


def ucount():
    m = re.search(r'UCOUNT (\d+)', run([KPY, HP, PCB, 'ucount']))
    return int(m.group(1)) if m else 999


def check():
    # 未配線が増えていなければ DRC を省く (mr_apply.py が中で DRC をかけ、違反した経路は取り除いている)
    global UNETS
    if ucount() <= U0:
        UNETS = set()
        return 0, v0, collections.Counter()
    return drc()


def ddr_bad():
    out = run([KPY, T + 'ddr_check.py', PCB, '--tol', '20'])
    m = re.search(r'規則の外れ:\s*(\d+)', out)
    return int(m.group(1)) if m else 999


def route(tag, extra):
    env = {'MR_VIP_COST': '0.2'}
    if RIPOWN and NETS:
        env['MR_SOFT_ONLY'] = '^(' + '|'.join(re.escape(n) for n in NETS) + ')$'
        if '--rip' not in extra:
            extra = extra + ['--rip', '--maxrip', '3']
    j, r = os.path.join(W, f'd_{tag}.json'), os.path.join(W, f'd_{tag}_r.json')
    # mr_export は drc_sum.json の未配線の一覧を読む。全部はがしたネットなので、パッドから作る (DRC を省く)
    run([KPY, HP, PCB, 'unc', os.path.join(W, '_nets.json'), os.path.join(tempfile.gettempdir(), 'drc_sum.json')])
    run([KPY, T + 'mr_export.py', j, PCB, '--chain'], env=env)
    run([sys.executable, T + 'mr_route.py', j, r, '--pairs', '--margin', os.environ.get('DF_MARGIN', '8')] + extra, env=env)
    run([KPY, T + 'mr_apply.py', r, PCB])
    run([KPY, T + 'clean_dangling.py', PCB])


def partner(n):
    if re.search(r'DDR_(CLK|DQS\d)P$', n):
        return n[:-1] + 'N'
    if re.search(r'DDR_(CLK|DQS\d)N$', n):
        return n[:-1] + 'P'
    return None


L0 = lengths()
bad = sorted([n for n, (l, m, v) in L0.items() if m > 1 and l / m >= LIM and l - m > 5], key=lambda n: -L0[n][0] / L0[n][1])
if NETS is not None:
    bad = [n for n in NETS if n in L0]
un0, v0, c0 = drc()
d0 = ddr_bad()
U0 = ucount()
print(f'開始: 遠回り {len(bad)} 本、未配線 {un0}、違反 {v0} {dict(c0)}、DDR の外れ {d0}', flush=True)
# 組: 相方も入れる。5 本ずつ
groups, seen = [], set()
cur = []
for n in bad:
    if n in seen:
        continue
    g = [n] + ([partner(n)] if partner(n) and partner(n) in L0 else [])
    seen.update(g)
    cur += g
    if len(cur) >= GS:
        groups.append(cur); cur = []
if cur:
    groups.append(cur)
queue = list(groups)
acc, rej, later = [], [], []
k = 0
while queue:
    g = queue.pop(0)
    k += 1
    shutil.copy(PCB, BK)
    before_all = {n: L0[n][0] for n in g if n in L0}
    jn = os.path.join(W, '_nets.json')
    json.dump(g, open(jn, 'w', encoding='utf8'))
    run([KPY, HP, PCB, 'rip', jn])
    route(f'{k}a', [] if NORIP else ['--rip', '--maxrip', os.environ.get('DF_MAXRIP', '3')])  # 1 回で (DRC が 1 回 2 分かかるので回数を減らす)
    un, v, c = check()
    if un and not NORIP:
        route(f'{k}b', [])
        un, v, c = check()
    if un and NORIP and UNETS and set(UNETS) <= set(g) and len(set(g)) > 1:
        # 通らなかったネットを先に引いて、組をもう一度引く
        first = '^(' + '|'.join(re.escape(n) for n in sorted(UNETS)) + ')$'
        hard = sorted(UNETS)
        shutil.copy(BK, PCB)
        run([KPY, HP, PCB, 'rip', jn])
        route(f'{k}f', ['--first', first])
        un, v, c = check()
        print(f'   {hard} を先に引いてやり直し: 未配線 {un}、違反 {v}', flush=True)
    failed = []
    if un and UNETS and set(UNETS) <= set(g) and set(UNETS) != set(g):
        # 通らなかったネットだけ元の線 (BK) に戻し、ほかは評価する
        failed = sorted(UNETS)
        fj = os.path.join(W, '_failed.json')
        json.dump(failed, open(fj, 'w', encoding='utf8'))
        run([KPY, T + 'merge_nets.py', '--revert', PCB, PCB, '--orig', BK, fj])
        un, v, c = drc()  # 元に戻した線がぶつかるかは DRC でしかわからない
        print(f'   通らなかった {failed} を元に戻した: 未配線 {un}、違反 {v}', flush=True)
        if un == 0 and v <= v0:
            g = [n for n in g if n not in failed]
            later.extend(failed)
        else:
            failed = []
    L1 = lengths()
    before = sum(before_all.get(n, 0) for n in g)
    after = sum(L1.get(n, [0])[0] for n in g)
    dd = ddr_bad() if any(n.startswith('DDR_') for n in g) else d0
    okk = un == 0 and v <= v0 and after < before - 1.0 and dd <= d0
    print(f'組 {k} {g}: 長さ {before:.1f} → {after:.1f}、未配線 {un}、違反 {v}、DDR の外れ {dd} → {"採用" if okk else "戻す"}', flush=True)
    if okk:
        acc += g; L0 = L1; v0 = v; d0 = dd
    else:
        shutil.copy(BK, PCB)
        if len(g) > 1:
            singles, s2 = [], set()
            for n in g:
                if n in s2:
                    continue
                q = [n] + ([partner(n)] if partner(n) in g else [])
                s2.update(q); singles.append(q)
            if len(singles) > 1:
                queue += singles
                continue
        rej += g
print('通らず元に戻したネット', len(later), later, flush=True)
print('終わり: 採用', len(acc), acc, flush=True)
print('戻した', len(rej), rej, flush=True)
un, v, c = drc()
print(f'最後の DRC: 未配線 {un}、違反 {v} {dict(c)}', flush=True)
L2 = lengths()
print('遠回り (比 %.1f 以上) の残り:' % LIM, sum(1 for n, (l, m, v) in L2.items() if m > 1 and l / m >= LIM and l - m > 5), flush=True)
