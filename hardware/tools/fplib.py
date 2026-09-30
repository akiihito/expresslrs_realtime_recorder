"""KiCadフットプリントの読み込みとジオメトリ取得。"""
import os, sexp

FPDIR = '/Applications/KiCad/KiCad.app/Contents/SharedSupport/footprints'
LOCAL = {}          # ライブラリ名 -> ディレクトリ（プロジェクト固有用）

_cache = {}

def load(lib_id):
    """(node, pads) を返す。pads は {番号: (x, y)}（フットプリント原点基準）"""
    if lib_id in _cache:
        return _cache[lib_id]
    lib, name = lib_id.split(':')
    path = os.path.join(LOCAL.get(lib, f'{FPDIR}/{lib}.pretty'), f'{name}.kicad_mod')
    node = sexp.parse(open(path).read())[0]
    pads = {}
    for p in sexp.find(node, 'pad'):
        num = p[1][1] if isinstance(p[1], tuple) else p[1]
        at = sexp.find(p, 'at')[0]
        pads[num] = (float(at[1]), float(at[2]))
    _cache[lib_id] = (node, pads)
    return _cache[lib_id]

def extent(lib_id):
    """(w, h, x0, y0, x1, y1) 外形の目安。CrtYd優先、無ければパッドから推定。"""
    node, pads = load(lib_id)
    xs, ys = [], []
    for tag in ('fp_line', 'fp_rect', 'fp_poly', 'fp_circle'):
        for g in sexp.find(node, tag):
            layer = sexp.val(g, 'layer')
            if layer not in ('F.CrtYd', 'B.CrtYd'):
                continue
            for key in ('start', 'end', 'center'):
                for pt in sexp.find(g, key):
                    xs.append(float(pt[1])); ys.append(float(pt[2]))
            for pts in sexp.find(g, 'pts'):
                for xy in sexp.find(pts, 'xy'):
                    xs.append(float(xy[1])); ys.append(float(xy[2]))
    if not xs:
        for (x, y) in pads.values():
            xs.append(x); ys.append(y)
        if xs:
            xs = [min(xs) - 1.5, max(xs) + 1.5]
            ys = [min(ys) - 1.5, max(ys) + 1.5]
    if not xs:
        return (0, 0, 0, 0, 0, 0)
    return (max(xs) - min(xs), max(ys) - min(ys), min(xs), min(ys), max(xs), max(ys))
