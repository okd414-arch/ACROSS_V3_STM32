# Freerouting のログの未配線一覧を、ネットクラスと部品ごとに集計する (2026-11-21)
# usage: python fr_unrouted.py fr.log [kicad_pro]
import sys, re, json, collections

log = open(sys.argv[1], encoding='utf8', errors='replace').read()
pro = sys.argv[2] if len(sys.argv) > 2 else '../ACROSS_V3.kicad_pro'
# 最後の一覧だけを使う
blocks = log.split('unrouted connection')
nets = collections.OrderedDict()
cur = None
for line in log.splitlines():
    m = re.search(r"Net '([^']+)' \((\d+) unrouted", line)
    if m:
        cur = m.group(1)
        nets[cur] = []
        continue
    m = re.match(r'\s+- (\S+)\s+->\s+(\S+)', line)
    if m and cur:
        nets[cur].append((m.group(1), m.group(2)))
p = json.load(open(pro, encoding='utf8'))
pats = p['net_settings'].get('netclass_patterns', [])


def cls(n):
    out = []
    for q in pats:
        try:
            if re.fullmatch(q['pattern'].replace('*', '.*') if not q['pattern'].startswith('^') else q['pattern'], n) or re.search(q['pattern'], n):
                out.append(q['netclass'])
        except re.error:
            pass
    return ','.join(sorted(set(out))) or 'Default'


C = collections.Counter()
R = collections.Counter()
for n, cs in nets.items():
    c = cls(n)
    C[c] += len(cs)
    for a, b in cs:
        R[a.split('-')[0]] += 1
        R[b.split('-')[0]] += 1
print('ネット', len(nets), '接続', sum(len(v) for v in nets.values()))
for k, v in C.most_common():
    print(f'  {v:4d}  {k}')
print('部品 (上位 25)')
print('  ' + ' '.join(f'{k}:{v}' for k, v in R.most_common(25)))
