"""KiCad S式の最小パーサ／シリアライザ。"""

def parse(text):
    toks, i, n = [], 0, len(text)
    def read(i):
        # 空白飛ばし
        while i < n and text[i] in ' \t\r\n':
            i += 1
        if i >= n:
            return None, i
        c = text[i]
        if c == '(':
            lst = []
            i += 1
            while True:
                while i < n and text[i] in ' \t\r\n':
                    i += 1
                if i < n and text[i] == ')':
                    return lst, i + 1
                item, i = read(i)
                if item is None:
                    return lst, i
                lst.append(item)
        if c == '"':
            i += 1
            buf = []
            while i < n and text[i] != '"':
                if text[i] == '\\':
                    buf.append(text[i + 1]); i += 2
                else:
                    buf.append(text[i]); i += 1
            return ('str', ''.join(buf)), i + 1
        buf = []
        while i < n and text[i] not in ' \t\r\n()':
            buf.append(text[i]); i += 1
        return ''.join(buf), i
    out = []
    while True:
        v, i = read(i)
        if v is None:
            break
        out.append(v)
    return out


def dump(node, indent=0):
    pad = '  ' * indent
    if isinstance(node, tuple):          # 文字列リテラル
        s = node[1].replace('\\', '\\\\').replace('"', '\\"')
        return f'"{s}"'
    if isinstance(node, str):
        return node
    head = node[0] if node else ''
    simple = all(not isinstance(c, list) for c in node)
    parts = [dump(c, indent + 1) for c in node]
    if simple:
        return '(' + ' '.join(parts) + ')'
    out = ['(' + parts[0]]
    for c, p in zip(node[1:], parts[1:]):
        out.append(('\n' + pad + '  ' + p) if isinstance(c, list) else (' ' + p))
    out.append('\n' + pad + ')')
    return ''.join(out)


def find(node, name):
    """直下の子から (name ...) を全部返す"""
    return [c for c in node if isinstance(c, list) and c and c[0] == name]


def val(node, name, idx=1):
    for c in find(node, name):
        v = c[idx]
        return v[1] if isinstance(v, tuple) else v
    return None
