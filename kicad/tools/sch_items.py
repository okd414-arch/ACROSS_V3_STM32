# 回路図ファイルのトップレベル項目を切り出す共通関数 (2026-11-16)
import re

BS = chr(92)


def split_top(s):
    """kicad_sch の直下の要素を (start, end) のリストで返す。文字列中の括弧は無視。"""
    depth = 0
    items = []
    p = s.index('(')
    instr = False
    start = None
    while p < len(s):
        c = s[p]
        if instr:
            if c == BS:
                p += 1
            elif c == '"':
                instr = False
        else:
            if c == '"':
                instr = True
            elif c == '(':
                depth += 1
                if depth == 2:
                    start = p
            elif c == ')':
                if depth == 2:
                    items.append((start, p + 1))
                depth -= 1
        p += 1
    return items


def kind(t):
    return re.match(r'\(([a-z_]+)', t).group(1)


def pos(t):
    k = kind(t)
    if k in ('wire', 'polyline', 'bus'):
        m = re.search(r'\(xy ([-\d.]+) ([-\d.]+)\)', t)
    else:
        m = re.search(r'\(at ([-\d.]+) ([-\d.]+)', t)
    return (float(m.group(1)), float(m.group(2))) if m else None
