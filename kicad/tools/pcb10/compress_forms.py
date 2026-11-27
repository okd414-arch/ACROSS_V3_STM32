def forms(s):
    out = []; depth = 0; start = None
    instr = False
    i = 0
    n = len(s)
    while i < n:
        ch = s[i]
        if instr:
            if ch == '\\':
                i += 2; continue
            if ch == '"':
                instr = False
        else:
            if ch == '"':
                instr = True
            elif ch == '(':
                if depth == 1:
                    start = i
                depth += 1
            elif ch == ')':
                depth -= 1
                if depth == 1:
                    out.append((start, i + 1))
        i += 1
    return out
