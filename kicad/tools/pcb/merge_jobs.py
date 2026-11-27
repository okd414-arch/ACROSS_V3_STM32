# 並列で直した写しをまとめ、別の写しのネットどうしがぶつかったら片方を元に戻す (2026-11-25)
#   1) start (元の基板) に、写しごとの受け持ちのネット (owned) の線・ビアを写しから持ってくる (merge_nets.py)
#   2) DRC。違反の 2 つの部品が、どちらも持ってきたネットで、受け持ちの写しが違うなら、後の写しのほうのネットを元に戻す
#   3) 違反がなくなるか、5 回まで繰り返す。未配線が出たら、そのネットも元に戻す
#   一時ファイルは TMP/TEMP。パスは絶対パス。
# usage: python merge_jobs.py start.kicad_pcb out.kicad_pcb jobs.json
#   jobs.json: [[写しの pcb, [ネット...]], ...] (順番が優先度。前のほうを残す)
import sys, json, os, subprocess, tempfile, re, collections

K = 'C:/MyWorks/ACROSS_V3_STM32/kicad'
KPY = 'C:/Program Files/KiCad/10.0/bin/python.exe'
T = K + '/tools/pcb/'
START, OUT, JF = map(os.path.abspath, sys.argv[1:4])
jobs = json.load(open(JF, encoding='utf8'))
W = os.path.dirname(OUT)
owner = {}
for i, (pcb, nets) in enumerate(jobs):
    for n in nets:
        owner.setdefault(n, i)


def run(cmd):
    p = subprocess.run(cmd, capture_output=True, text=True, encoding='utf8', errors='replace', cwd=W)
    return p.stdout + p.stderr


# 写しごとに別の処理で (pcbnew は 1 つの処理の中で線を消して足すと、あとで GetTracks が壊れる)
cur = START
for i, (pcb, nets) in enumerate(jobs):
    nf = os.path.join(W, f'_owned_{i}.json')
    json.dump([n for n in nets if owner[n] == i], open(nf, 'w', encoding='utf8'), ensure_ascii=False)
    out = run([KPY, T + 'merge_nets.py', cur, OUT, pcb, nf])
    print([l for l in out.splitlines() if 'ネット' in l or 'Error' in l][-1:], flush=True)
    cur = OUT
IGN = {'silk_overlap', 'silk_over_copper', 'lib_footprint_issues', 'lib_footprint_mismatch', 'copper_sliver'}
reverted = []
for it in range(6):
    run(['python', T + 'drc_sum.py', OUT, '0'])
    d = json.load(open(os.path.join(tempfile.gettempdir(), 'drc_sum.json'), encoding='utf8'))
    bad = [v for v in d['violations'] if v['type'] not in IGN]
    un = set()
    for u in d['unconnected_items']:
        m = re.search(r'\[([^\]]+)\]', u['items'][0]['description'])
        if m and m.group(1) in owner:
            un.add(m.group(1))
    rv = set(un)
    for v in bad:
        ns = []
        for x in v['items']:
            m = re.search(r'\[([^\]]+)\]', x['description'])
            if m:
                ns.append(m.group(1))
        own = [n for n in ns if n in owner and n not in reverted]
        if len(own) >= 2 and owner[own[0]] != owner[own[1]]:
            rv.add(max(own, key=lambda n: owner[n]))  # 後の写しのほうを戻す
        elif len(own) == 1 and len(ns) >= 2:
            rv.add(own[0])  # 持ってきたネットと、元のままのネットがぶつかった (ありえないはずだが念のため)
    print(f'回 {it}: 違反 {len(bad)} {dict(collections.Counter(v["type"] for v in bad))}、未配線 {len(d["unconnected_items"])}、戻す {sorted(rv)}', flush=True)
    if not rv:
        break
    reverted += sorted(rv)
    rf = os.path.join(W, '_rev.json')
    json.dump(sorted(rv), open(rf, 'w', encoding='utf8'), ensure_ascii=False)
    run([KPY, T + 'merge_nets.py', '--revert', OUT, OUT, '--orig', START, rf])
print('元に戻したネット', len(reverted), reverted, flush=True)
