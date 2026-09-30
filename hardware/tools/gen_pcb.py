#!/usr/bin/env python3
"""ExpressLRS Realtime Recorder の基板(.kicad_pcb)を生成する。

方針:
- 2層。**裏面(B.Cu)は全面GNDベタ**。全部品がスルーホールなのでGNDパッドは
  ベタに直結する。GND用の配線もビアも一切要らない。
- 信号は表面(F.Cu)のみ、ビア0。Picoの左列に繋がる部品は左、右列(VBUS)は右に
  置き、Picoを跨ぐ配線が発生しないようにした。
- 左側の部品は「Picoのピンと同じY座標」に並べてあるので、配線は水平一直線で
  済み交差しない（ピン順と部品順を一致させている）。
- ネット割当は回路図のネットリストから読む。配線端点がパッドと一致するかは
  生成時に自己検査する。
"""
import hashlib, math, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sexp, fplib

HERE = os.path.dirname(os.path.abspath(__file__))
fplib.LOCAL['recorder'] = os.path.join(HERE, 'recorder.pretty')

NETLIST = sys.argv[1] if len(sys.argv) > 1 else 'net.net'
SCH     = sys.argv[2] if len(sys.argv) > 2 else 'recorder.kicad_sch'
OUT     = sys.argv[3] if len(sys.argv) > 3 else 'recorder.kicad_pcb'

_uid = [0]
def uuid():
    _uid[0] += 1
    h = hashlib.md5(f'elrs-pcb-{_uid[0]}'.encode()).hexdigest()
    return f'{h[0:8]}-{h[8:12]}-{h[12:16]}-{h[16:20]}-{h[20:32]}'

# ---------------------------------------------------------------- 基板
BX0, BY0, BW, BH = 10.0, 10.0, 105.0, 85.0
BX1, BY1 = BX0 + BW, BY0 + BH
S, P = 0.25, 0.8                      # 信号線幅 / 電源線幅

# Pico: 中心(76,44) → 左列 x=67.11 / 右列 x=84.89 / pin1 y=19.87 / ピッチ2.54
PICO_L, PICO_R, PIN1_Y = 67.11, 84.89, 19.87
def ly(n):  return PIN1_Y + (n - 1) * 2.54          # 左列 pin1..20
def ry(n):  return PIN1_Y + (40 - n) * 2.54         # 右列 pin21..40

PLACE = {
    'U1':  (76.0, 44.0, 0),
    # --- 左上: CRSF（GP0/GP1のYに合わせる）---
    'J1':  (33.0, 20.0, 180),      # pad1(33)=CRSF pad2(30.5)=GND pad3(28)=VBAT
    'R6':  (48.0, ly(1), 180),     # pad1(48)=CRSF_TX pad2(37.84)=BUS
    'R7':  (52.0, ly(2), 0),       # pad1(52)=BUS pad2(62.16)=GP1側
    # --- 左中: ボタン・スイッチ・UART（GP2/GP3/GP4/GP5/GP6のYに合わせる）---
    'SW1': (20.0, ly(4), 0),       # pad1 が (20,y) と (26.5,y) の2箇所
    'SW3': (43.62, ly(5), 180),    # pad1(43.62)=SW_ARM pad2(36)=GND
    'J4':  (30.0, ly(6), 0),       # (30,GP4) (30,GP5) (30,GND=pin8) と1:1
    'SW2': (20.0, ly(9), 0),
    # --- 左下: LEDと抵抗 ---
    'D1':  (33.0, 49.0, 0), 'R1': (49.16, 49.0, 180),
    'D2':  (33.0, 54.5, 0), 'R2': (49.16, 54.5, 180),
    'D3':  (33.0, 60.0, 0), 'R3': (49.16, 60.0, 180),
    'D4':  (33.0, 65.5, 0), 'R4': (49.16, 65.5, 180),
    'D5':  (33.0, 71.0, 0), 'R5': (49.16, 71.0, 180),
    # --- 下: 電源入力 ---
    'J3':  (20.0, 88.0, 0),        # LiPoピグテール直付け
    'F1':  (46.0, 84.0, 180),      # pad1(46,80.6)=VBAT側 pad2(36.08,80.6)=LiPo側
    'C1':  (58.0, 88.0, 0),
    'C2':  (70.0, 88.0, 0),
    'J2':  (96.0, 80.0, 0),        # 降圧モジュール MP1584EN 22.3x16.8mm
    # --- 右: 5Vレール（Pico VBUSの近く）---
    'C3':  (99.0, 24.0, 0),
    'C4':  (99.0, 32.0, 0),
    'D6':  (109.16, 40.0, 180),    # pad2(99)=+5V pad1(109.16)=GND
}
# ref -> (dx, dy): リファレンス文字の位置を部品原点基準で上書き
REF_POS = {f'D{i}': (-4.5, 0.0) for i in range(1, 6)}

MOUNT_HOLES = [(14.0, 14.0), (111.0, 14.0), (14.0, 91.0), (111.0, 91.0)]

ROUTES = [
    # --- CRSF ---
    ('CRSF_TX',   [(PICO_L, ly(1)), (48.0, ly(1))], S),
    ('CRSF_BUS',  [(52.0, ly(2)), (52.0, 25.0), (35.0, 25.0), (35.0, 20.0), (33.0, 20.0)], S),
    ('CRSF_BUS',  [(37.84, ly(1)), (37.84, 25.0)], S),
    ('Net-(U1-GPIO1)', [(PICO_L, ly(2)), (62.16, ly(2))], S),
    # --- 左の信号は全て水平一直線 ---
    ('BTN_MODE',  [(PICO_L, ly(4)), (26.5, ly(4))], S),
    ('SW_ARM',    [(PICO_L, ly(5)), (43.62, ly(5))], S),
    ('DBG_TX',    [(PICO_L, ly(6)), (30.0, ly(6))], S),
    ('DBG_RX',    [(PICO_L, ly(7)), (30.0, ly(7))], S),
    ('BTN_INPUT', [(PICO_L, ly(9)), (26.5, ly(9))], S),
    # --- LED 5系統 ---
    ('LED_REC',       [(PICO_L, ly(14)), (55.0, ly(14)), (49.16, 49.0)], S),
    ('LED_PLAY',      [(PICO_L, ly(15)), (55.0, ly(15)), (49.16, 54.5)], S),
    ('LED_SIMPLE',    [(PICO_L, ly(16)), (55.0, ly(16)), (49.16, 60.0)], S),
    ('LED_GENERIC',   [(PICO_L, ly(17)), (55.0, ly(17)), (49.16, 65.5)], S),
    ('LED_LITERADIO', [(PICO_L, ly(19)), (55.0, ly(19)), (49.16, 71.0)], S),
    ('Net-(D1-A)', [(39.0, 49.0), (35.54, 49.0)], S),
    ('Net-(D2-A)', [(39.0, 54.5), (35.54, 54.5)], S),
    ('Net-(D3-A)', [(39.0, 60.0), (35.54, 60.0)], S),
    ('Net-(D4-A)', [(39.0, 65.5), (35.54, 65.5)], S),
    ('Net-(D5-A)', [(39.0, 71.0), (35.54, 71.0)], S),
    # --- 電源 ---
    ('Net-(J3-Pin_1)', [(20.0, 88.0), (20.0, 80.6), (36.08, 80.6)], P),
    ('VBAT_7_13V', [(46.0, 80.6), (86.55, 80.6), (86.55, 84.16)], P),
    ('VBAT_7_13V', [(58.0, 80.6), (58.0, 88.0)], P),
    ('VBAT_7_13V', [(70.0, 80.6), (70.0, 88.0)], P),
    ('VBAT_7_13V', [(46.0, 80.6), (46.0, 74.0), (16.0, 74.0), (16.0, 20.0), (28.0, 20.0)], P),
    ('+5V', [(105.45, 84.16), (105.45, 89.0), (97.0, 89.0), (97.0, PIN1_Y), (PICO_R, PIN1_Y)], P),
    ('+5V', [(97.0, 24.0), (99.0, 24.0)], P),
    ('+5V', [(97.0, 32.0), (99.0, 32.0)], P),
    ('+5V', [(97.0, 40.0), (99.0, 40.0)], P),
]

SILK = [
    (20.0, 93.5, 'ExpressLRS Realtime Recorder  rev.A', 1.2),
    (12.0, 20.5, 'NanoTX', 0.9),
    (12.0, 26.0, 'MODE', 0.9),
    (12.0, 38.8, 'INPUT', 0.9),
    (42.0, 25.5, 'ARM', 0.9),
    (33.5, 40.5, 'UART', 0.9),
    (20.0, 49.0, 'REC', 0.9),
    (20.0, 54.5, 'PLAY', 0.9),
    (20.0, 60.0, 'SIMPLE', 0.9),
    (20.0, 65.5, 'GEN', 0.9),
    (20.0, 71.0, 'LR', 0.9),
    (14.0, 84.0, 'LiPo 3S', 0.9),
    (38.0, 76.0, 'FUSE', 0.9),
]

# ---------------------------------------------------------------- ネット
def load_nets():
    doc = sexp.parse(open(NETLIST).read())[0]
    pin2net, names = {}, ['']
    for n in sexp.find(sexp.find(doc, 'nets')[0], 'net'):
        name = sexp.val(n, 'name')
        names.append(name)
        for nd in sexp.find(n, 'node'):
            pin2net[(sexp.val(nd, 'ref'), sexp.val(nd, 'pin'))] = name
    return pin2net, names

pin2net, net_names = load_nets()
_idx = {nm: i for i, nm in enumerate(net_names)}

def resolve(name):
    """ローカルラベルはネットリスト上 '/NAME' になる。両方試す。"""
    for cand in (name, '/' + name):
        if cand in _idx:
            return cand, _idx[cand]
    raise SystemExit(f'net not found: {name}')

# ---------------------------------------------------------------- 回路図から取得
def sch_props(schfile):
    doc = sexp.parse(open(schfile).read())[0]
    fps, vals = {}, {}
    for s in sexp.find(doc, 'symbol'):
        ref = fp = val = None
        for pr in sexp.find(s, 'property'):
            k = pr[1][1]
            if k == 'Reference': ref = pr[2][1]
            elif k == 'Value':   val = pr[2][1]
            elif k == 'Footprint': fp = pr[2][1]
        if ref and not ref.startswith('#'):
            if fp:  fps[ref] = fp
            if val: vals[ref] = val
    return fps, vals

FOOTPRINT, VALUES = sch_props(SCH)

# ---------------------------------------------------------------- 幾何
def rot_pt(x, y, deg):
    r = math.radians(deg)
    return (x * math.cos(r) + y * math.sin(r), -x * math.sin(r) + y * math.cos(r))

def pad_positions(ref):
    """[(番号, 絶対x, 絶対y)] 同番号の複数パッドも全部返す"""
    node, _ = fplib.load(FOOTPRINT[ref])
    px, py, rot = PLACE[ref]
    out = []
    for p in sexp.find(node, 'pad'):
        num = p[1][1] if isinstance(p[1], tuple) else p[1]
        at = sexp.find(p, 'at')[0]
        dx, dy = rot_pt(float(at[1]), float(at[2]), rot)
        out.append((num, round(px + dx, 3), round(py + dy, 3)))
    return out

# 全パッドを (x,y) -> [(ref,num,net)] に
ALL_PADS = {}
for ref in PLACE:
    for num, x, y in pad_positions(ref):
        ALL_PADS.setdefault((x, y), []).append((ref, num, pin2net.get((ref, num))))

# --- 自己検査 ---
# 配線の端点は「同ネットのパッド上」か「同ネットの別配線上（T字分岐）」の
# どちらかでなければならない。座標の打ち間違いをここで潰す。
def on_segment(pt, a, b, eps=1e-6):
    (x, y), (ax, ay), (bx, by) = pt, a, b
    cross = (bx - ax) * (y - ay) - (by - ay) * (x - ax)
    if abs(cross) > 1e-3:
        return False
    return (min(ax, bx) - eps <= x <= max(ax, bx) + eps and
            min(ay, by) - eps <= y <= max(ay, by) + eps)

problems = []
for ri, (name, pts, _wd) in enumerate(ROUTES):
    full, _ = resolve(name)
    for end in (pts[0], pts[-1]):
        key = (round(end[0], 3), round(end[1], 3))
        if any(h[2] == full for h in ALL_PADS.get(key, [])):
            continue
        joined = False
        for rj, (n2, pts2, _w2) in enumerate(ROUTES):
            if rj == ri or resolve(n2)[0] != full:
                continue
            for k in range(len(pts2) - 1):
                if on_segment(end, pts2[k], pts2[k + 1]):
                    joined = True
                    break
            if joined:
                break
        if not joined:
            problems.append(f'  {name}: 端点 {end} が同ネットのパッドにも配線にも繋がらない '
                            f'(そこにあるのは {ALL_PADS.get(key) or "何も無し"})')
if problems:
    print('自己検査でエラー:')
    print('\n'.join(problems))
    sys.exit(1)

# ---------------------------------------------------------------- 出力
out = []
w = out.append
w('(kicad_pcb')
w('  (version 20240108)')
w('  (generator "gen_pcb.py")')
w('  (generator_version "9.0")')
w('  (general (thickness 1.6) (legacy_teardrops no))')
w('  (paper "A4")')
w('  (title_block (title "ExpressLRS Realtime Recorder") (date "2026-09-30") (rev "A"))')
w('  (layers')
w('    (0 "F.Cu" signal) (31 "B.Cu" signal)')
w('    (32 "B.Adhes" user "B.Adhesive") (33 "F.Adhes" user "F.Adhesive")')
w('    (34 "B.Paste" user) (35 "F.Paste" user)')
w('    (36 "B.SilkS" user "B.Silkscreen") (37 "F.SilkS" user "F.Silkscreen")')
w('    (38 "B.Mask" user) (39 "F.Mask" user)')
w('    (40 "Dwgs.User" user "User.Drawings") (41 "Cmts.User" user "User.Comments")')
w('    (42 "Eco1.User" user "User.Eco1") (43 "Eco2.User" user "User.Eco2")')
w('    (44 "Edge.Cuts" user) (45 "Margin" user)')
w('    (46 "B.CrtYd" user "B.Courtyard") (47 "F.CrtYd" user "F.Courtyard")')
w('    (48 "B.Fab" user) (49 "F.Fab" user)')
w('  )')
w('  (setup (pad_to_mask_clearance 0) (allow_soldermask_bridges_in_footprints no))')
for i, nm in enumerate(net_names):
    w(f'  (net {i} "{nm}")')

corners = [(BX0, BY0), (BX1, BY0), (BX1, BY1), (BX0, BY1)]
for i in range(4):
    a, b = corners[i], corners[(i + 1) % 4]
    w(f'  (gr_line (start {a[0]} {a[1]}) (end {b[0]} {b[1]}) '
      f'(stroke (width 0.1) (type solid)) (layer "Edge.Cuts") (uuid "{uuid()}"))')

SKIP = ('version', 'generator', 'generator_version', 'layer', 'at', 'uuid', 'tedit')

def emit_footprint(ref, fp, at, hide_text=False):
    node, _ = fplib.load(fp)
    px, py, rot = at
    new = ['footprint', node[1],
           ['layer', ('str', 'F.Cu')],
           ['uuid', ('str', uuid())]]
    atn = ['at', str(px), str(py)] + ([str(rot)] if rot else [])
    new.append(atn)
    for c in node[2:]:
        if not isinstance(c, list) or c[0] in SKIP:
            continue
        c = [x for x in c if not (isinstance(x, list) and x[0] == 'uuid')]
        if c[0] == 'property':
            key = c[1][1]
            if key == 'Reference':
                c[2] = ('str', ref)
                if ref in REF_POS:
                    dx, dy = REF_POS[ref]
                    c = [x for x in c if not (isinstance(x, list) and x[0] == 'at')]
                    c.insert(3, ['at', str(dx), str(dy), '0'])
            elif key == 'Value':
                c[2] = ('str', VALUES.get(ref, ''))
            if hide_text:
                c = [x for x in c if not (isinstance(x, list) and x[0] == 'effects')]
                c.append(['effects', ['font', ['size', '1', '1'], ['thickness', '0.15']],
                          ['hide', 'yes']])
            c.append(['uuid', ('str', uuid())])
        elif c[0] == 'pad':
            num = c[1][1] if isinstance(c[1], tuple) else c[1]
            nn = pin2net.get((ref, num))
            if nn:
                c.append(['net', str(_idx[nn]), ('str', nn)])
            c.append(['uuid', ('str', uuid())])
        new.append(c)
    w('  ' + sexp.dump(new, 1))

for ref in sorted(PLACE):
    emit_footprint(ref, FOOTPRINT[ref], PLACE[ref])
for i, (hx, hy) in enumerate(MOUNT_HOLES):
    emit_footprint(f'H{i+1}', 'MountingHole:MountingHole_3.2mm_M3', (hx, hy, 0), hide_text=True)

# --- 同番号パッドの橋渡し ---
# フューズホルダやタクトSWは同じ番号のパッドを複数持つ。KiCadはそれらを
# 内部接続とはみなさないので、部品の足元で銅箔を渡しておく。
JUMPERS = []
for ref in sorted(PLACE):
    bynum = {}
    for num, x, y in pad_positions(ref):
        bynum.setdefault(num, []).append((x, y))
    for num, pts_ in bynum.items():
        nn = pin2net.get((ref, num))
        if not nn or len(pts_) < 2:
            continue
        for k in range(len(pts_) - 1):
            JUMPERS.append((nn, [pts_[k], pts_[k + 1]], S))

for name, pts, width in list(ROUTES) + [(j[0], j[1], j[2]) for j in JUMPERS]:
    _full, n = resolve(name)
    for i in range(len(pts) - 1):
        a, b = pts[i], pts[i + 1]
        if a == b:
            continue
        w(f'  (segment (start {a[0]} {a[1]}) (end {b[0]} {b[1]}) (width {width}) '
          f'(layer "F.Cu") (net {n}) (uuid "{uuid()}"))')

gnd = _idx['GND']
m = 0.3
w(f'  (zone (net {gnd}) (net_name "GND") (layers "B.Cu") (uuid "{uuid()}")')
w('    (name "GND_bottom") (hatch edge 0.5)')
w('    (connect_pads (clearance 0.5)) (min_thickness 0.25)')
w('    (fill yes (thermal_gap 0.5) (thermal_bridge_width 0.5))')
w('    (polygon (pts')
w(f'      (xy {BX0+m} {BY0+m}) (xy {BX1-m} {BY0+m}) (xy {BX1-m} {BY1-m}) (xy {BX0+m} {BY1-m})')
w('    )))')

for (lx, lyy, txt, size) in SILK:
    w(f'  (gr_text "{txt}" (at {lx} {lyy}) (layer "F.SilkS") (uuid "{uuid()}")')
    w(f'    (effects (font (size {size} {size}) (thickness 0.15)) (justify left)))')

w(')')
open(OUT, 'w').write('\n'.join(out) + '\n')
print(f'wrote {OUT}: {len(PLACE)} parts + {len(MOUNT_HOLES)} holes, '
      f'{len(ROUTES)} routes + {len(JUMPERS)} jumpers  (自己検査OK)')
