import re
TOK = re.compile(r'"(?:[^"\\]|\\.)*"|\(|\)|[^\s()]+')
def parse(s):
    toks = TOK.findall(s)
    pos = 0
    def rd():
        nonlocal pos
        t = toks[pos]; pos += 1
        if t == '(':
            l = []
            while toks[pos] != ')':
                l.append(rd())
            pos += 1
            return l
        return t
    return rd()
def q(t):
    return t[1:-1] if isinstance(t, str) and t.startswith('"') else t
def find(l, name):
    return [x for x in l if isinstance(x, list) and x and x[0] == name]
