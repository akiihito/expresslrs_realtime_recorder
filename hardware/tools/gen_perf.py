#!/usr/bin/env python3
"""ユニバーサル基板（2.54mmピッチ）版の配置図と配線リストを生成する。

配線リストは回路図のネットリストから機械的に作るので、配線漏れが起きない。
各部品の全ピンに穴を割り当てたかも検査する。
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sexp

NETLIST = sys.argv[1] if len(sys.argv) > 1 else 'net.net'
OUT     = sys.argv[2] if len(sys.argv) > 2 else 'perfboard.html'

COLS, ROWS = 35, 26          # 95 x 72 mm クラスの基板に収まる穴数

# ---------------------------------------------------------------- 配置
# ref -> {パッド番号: (列, 行)}   列は左→右 1..36、行は上→下 1..27
PICO_L, PICO_R = 20, 27      # Picoの左右ピン列
place = {}

# Pico: 左列 pin1..20 が行3..22、右列 pin40..21 が行3..22
place['U1'] = {}
for n in range(1, 21):
    place['U1'][str(n)] = (PICO_L, n + 2)
for m in range(21, 41):
    place['U1'][str(m)] = (PICO_R, 43 - m)

place['J1'] = {'1': (2, 3), '2': (3, 3), '3': (4, 3)}          # CRSF / GND / VBAT
place['R6'] = {'1': (18, 3), '2': (14, 3)}                     # GP0側 / バス側
place['R7'] = {'1': (14, 5), '2': (18, 5)}                     # バス側 / GP1側
place['SW1'] = {'1': (7, 6), '2': (10, 8)}                     # モード（対角の2本・3穴x2穴）
place['SW3'] = {'1': (13, 10), '2': (16, 10)}                  # ArmスライドSW
place['J4'] = {'1': (2, 8), '2': (2, 9), '3': (2, 10)}         # TX / RX / GND
place['SW2'] = {'1': (7, 12), '2': (10, 14)}                   # 入力切替（同上）
for i, r in enumerate((16, 18, 20, 22, 24), start=1):
    place[f'D{i}'] = {'1': (2, r), '2': (3, r)}                # K / A
    place[f'R{i}'] = {'1': (8, r), '2': (4, r)}                # Pico側 / LED側
# 電源入力は左下。行26を左から右へ J3 → F1 → C1 → C2 と並べ、電流の向きと
# 図の並びを一致させる（C1/C2の＋が左なのはこのため）。
# ⚠️ J3とF1は必ず隣どうしにする。離すとヒューズ前の無保護なLiPo+が基板を横断する。
# ⚠️ 中央（列11-19×行11-25）は広いが、Picoの左列から左へ出る13本の配線が通る帯。
# 12Vの太線を通さない。
# ホルダ本体はどのみち穴に入らない（φ1.7-1.78mmピン・2.54の倍数でないピッチ）ので、
# 手組みでは配線用ホルダを線に割り込ませるか、接着して(6,26)と(10,26)へリード線で繋ぐ。
# 基板には余白があるので、本体は行26より下へはみ出してよい。
place['J3'] = {'2': (8, 26), '1': (10, 26)}                    # LiPo- / LiPo+
place['F1'] = {'2': (12, 26), '1': (16, 26)}                   # LiPo側 / VBAT側
place['C1'] = {'1': (19, 26), '2': (21, 26)}
place['C2'] = {'1': (23, 26), '2': (25, 26)}
place['J2'] = {'3': (28, 9), '4': (28, 5), '1': (35, 9), '2': (35, 5)}  # OUT+/OUT-/IN+/IN-
place['C3'] = {'1': (30, 12), '2': (32, 12)}
place['C4'] = {'1': (30, 14), '2': (32, 14)}
place['D6'] = {'2': (30, 16), '1': (34, 16)}                   # +5V / GND

# 図に描く部品の枠 (ref, 左列, 上行, 右列, 下行, 表示名)
BOXES = [
    ('U1', PICO_L, 3, PICO_R, 22, 'Raspberry Pi Pico (2x20 メスヘッダ)'),
    ('J1', 2, 3, 4, 3, 'Nano TX'),
    ('R6', 14, 3, 18, 3, 'R6 680R'),
    ('R7', 14, 5, 18, 5, 'R7 1k'),
    ('SW1', 7, 6, 10, 8, 'SW1 MODE'),
    ('J4', 2, 8, 2, 10, 'J4 UART'),
    ('SW3', 13, 10, 16, 10, 'SW3 ARM'),
    ('SW2', 7, 12, 10, 14, 'SW2 INPUT'),
    ('J3', 8, 26, 10, 26, 'J3 LiPo'),
    ('F1', 11, 26, 17, 26, 'F1 FUSE'),
    ('C1', 19, 26, 21, 26, 'C1'),
    ('C2', 23, 26, 25, 26, 'C2'),
    ('J2', 28, 4, 35, 10, 'J2 MP1584EN（リード線で配線）'),
    ('C3', 30, 12, 32, 12, 'C3'),
    ('C4', 30, 14, 32, 14, 'C4'),
    ('D6', 30, 16, 34, 16, 'D6 TVS'),
]
for i, r in enumerate((16, 18, 20, 22, 24), start=1):
    BOXES.append((f'D{i}', 2, r, 3, r, f'D{i}'))
    BOXES.append((f'R{i}', 4, r, 8, r, f'R{i} 100R'))

LED_NAME = {1: 'REC', 2: 'PLAY', 3: 'SIMPLE', 4: 'GENERIC', 5: 'LITERADIO'}


def _hole(ref, pin):
    """その部品ピンの穴を '(列,行)' で返す。"""
    c, r = place[ref][pin]
    return f'({c},{r})'


def _mm(a, b):
    """2穴間のマンハッタン距離[mm]。配線長の目安。"""
    return round((abs(a[0] - b[0]) + abs(a[1] - b[1])) * 2.54)


c1p, c3p = _hole('C1', '1'), _hole('C3', '1')   # 電解コンの＋側（pin1）
j3p, j3g = _hole('J3', '1'), _hole('J3', '2')   # LiPo+ / LiPo-
sw1a, sw1b = _hole('SW1', '1'), _hole('SW1', '2')  # 対角の2本
sw2a, sw2b = _hole('SW2', '1'), _hole('SW2', '2')
f1in, f1out = _hole('F1', '2'), _hole('F1', '1')  # ヒューズ前 / ヒューズ後
d2 = _mm(place['C2']['1'], place['J1']['3'])    # 100nF → Nano TX VBAT
d4 = _mm(place['C4']['1'], place['U1']['40'])   # 100nF → Pico VBUS
fuse_gap = _mm(place['J3']['1'], place['F1']['2'])  # ヒューズ前の無保護な区間

# ---------------------------------------------------------------- GND母線
# 裏面に張る裸のすずメッキ線。部品を動かすとここを異ネットのピンが貫通しうるので、
# 生成時に検査する（下の「母線の検査」）。
# ⚠️ (10,26) J3.1 と (12,26) F1.2 はヒューズより前のLiPo+。裸線が隣の穴を通ると
# 半田のはみ出しでヒューズを介さずLiPoが短絡するので、幹Aは列13から始め、
# 幹Fは (10,25) を空けて行24へ迂回させてある。
# J3は LiPo− を外側(列8)に置いてある。+(列10)とF1入口(列12)を隣どうしにして、
# 無保護な区間にGNDピンを挟まないため。
GND_BUS = [
    ('A', '行25 / 列13〜30', [(c, 25) for c in range(13, 31)],
     '幹。列13から始める（左隣の(12,26)がヒューズ前のLiPo+）。'
     'Fとは (13,24)-(13,25) で隣接するので、そこで繋ぐ'),
    ('B', '列2 / 行10〜25',  [(2, r) for r in range(10, 26)],
     'J4.3 と D1〜D5 のカソードを直に拾う'),
    ('B+', '列3 / 行3〜10',  [(3, r) for r in range(3, 11)],
     'J1.2。(3,10)-(2,10) でBへ渡す'),
    ('C', '列19 / 行3〜25',  [(19, r) for r in range(3, 26)],
     'Picoの左列のGND 4本（列20の行5/10/15/20）'),
    ('D', '列28 / 行11〜25', [(28, r) for r in range(11, 26)],
     'Picoの右列のGND 2本（列27の行15/20）'),
    ('E', '行5 / 列27〜35',  [(c, 5) for c in range(27, 36)],
     'U1.38 / J2.4 / J2.2。Dへは (28,5)-(28,11) を<b>被覆線</b>で（(28,9)が+5V）'),
    ('F', '列10 行8〜24 ＋ 行24 列9〜13 ＋ (9,25)(8,25)',
     [(10, r) for r in range(8, 25)] + [(c, 24) for c in range(9, 14)]
     + [(9, 25), (8, 25)],
     'SW1.2 / SW2.2 と、J3.2(LiPo−)の基板全体のGND戻りを (8,25) で受ける。'
     '(13,24)-(13,25) で幹Aに繋がる。'
     '⚠️ (10,25) を空けてあるのは、真下の (10,26) がヒューズ前のLiPo+だから'),
]

# ---------------------------------------------------------------- ネットリスト
doc = sexp.parse(open(NETLIST).read())[0]
nets = {}
for n in sexp.find(sexp.find(doc, 'nets')[0], 'net'):
    name = sexp.val(n, 'name')
    nodes = [(sexp.val(nd, 'ref'), sexp.val(nd, 'pin')) for nd in sexp.find(n, 'node')]
    if len(nodes) > 1:
        nets[name] = nodes

# --- 検査: ネットに出てくる全ピンに穴が割り当てられているか ---
missing = []
for name, nodes in nets.items():
    for ref, pin in nodes:
        if ref not in place or pin not in place[ref]:
            missing.append(f'{ref}.{pin} ({name})')
if missing:
    print('穴が未割り当てのピン:', ', '.join(missing))
    sys.exit(1)

# --- 穴の重複チェック ---
used = {}
dups = []
for ref, pins in place.items():
    for pin, hole in pins.items():
        if hole in used:
            dups.append(f'{hole}: {used[hole]} と {ref}.{pin}')
        used[hole] = f'{ref}.{pin}'
if dups:
    print('穴の重複:', '; '.join(dups))
    sys.exit(1)

# --- コンデンサの向き: フットプリント名の CP_ が有極性、C_ が無極性 ---
comps = {}
for c in sexp.find(sexp.find(doc, 'components')[0], 'comp'):
    comps[sexp.val(c, 'ref')] = (sexp.val(c, 'value'), sexp.val(c, 'footprint'))

# --- 母線の検査: 裸線が異ネットのピンを貫通しないか ---
hole2net = {}
for name, nodes in nets.items():
    for ref, pin in nodes:
        hole2net[place[ref][pin]] = (name.lstrip('/'), f'{ref}.{pin}')
pierced = []
for tag, where, cells, _why in GND_BUS:
    for h in cells:
        if h in hole2net and hole2net[h][0] != 'GND':
            pierced.append(f'{tag} {h} に {hole2net[h][1]} ({hole2net[h][0]})')
if pierced:
    print('GND母線が異ネットを貫通:', '; '.join(pierced))
    sys.exit(1)

bus_cells = {h for _t, _w, cells, _y in GND_BUS for h in cells}
gnd_pins = {h for h, (n, _p) in hole2net.items() if n == 'GND'}
def near_bus(h):
    return h in bus_cells or any((h[0] + dc, h[1] + dr) in bus_cells
                                 for dc, dr in ((1, 0), (-1, 0), (0, 1), (0, -1)))
gnd_drops = []
for h in sorted(gnd_pins - {g for g in gnd_pins if near_bus(g)}, key=lambda x: (x[1], x[0])):
    d = min(abs(h[0] - c) + abs(h[1] - r) for c, r in bus_cells)
    gnd_drops.append((hole2net[h][1], h, d))

cap_rows = []
for ref in sorted(r for r in place if r[0] == 'C' and r[1:].isdigit()):
    value, fp = comps[ref]
    hot, gnd = place[ref]['1'], place[ref]['2']        # pin1=電源側 / pin2=GND
    cap_rows.append({
        'ref': ref,
        'value': value,
        'polar': ':CP_' in fp,
        'hot': hot, 'gnd': gnd,
        'hot_side': '左' if hot[0] < gnd[0] else '右',
        'gnd_side': '右' if hot[0] < gnd[0] else '左',
        'rail': hole2net[hot][0],
    })


def label(ref, pin):
    c, r = place[ref][pin]
    return f'{chr(64 + (c - 1) // 26 + 1) if c > 26 else ""}{c}-{r}'

def hole(ref, pin):
    c, r = place[ref][pin]
    return f'({c},{r})'

# ---------------------------------------------------------------- 出力
rows_wire = []
gnd_holes = []
for name, nodes in sorted(nets.items()):
    pretty = name.lstrip('/')
    pts = [(ref, pin) for ref, pin in nodes]
    if pretty == 'GND':
        gnd_holes = [f'{r}.{p} {hole(r,p)}' for r, p in pts]
        continue
    chain = ' → '.join(f'<b>{hole(r,p)}</b> {r}.{p}' for r, p in pts)
    rows_wire.append((pretty, len(pts), chain))

P = 22          # 1穴あたりのpx
M = 44
W = M * 2 + (COLS - 1) * P
H = M * 2 + (ROWS - 1) * P

COLORS = {'U1': '--pico', 'J1': '--crsf', 'R6': '--crsf', 'R7': '--crsf',
          'J2': '--pwr', 'J3': '--pwr', 'F1': '--pwr', 'C1': '--pwr', 'C2': '--pwr',
          'C3': '--pwr', 'C4': '--pwr', 'D6': '--pwr', 'J4': '--dbg'}

def build_svg(mirror=False):
    """mirror=True ではんだ面（裏から見た図）。列が左右反転する。"""
    def mc(c): return (COLS + 1 - c) if mirror else c
    def hx(c): return M + (mc(c) - 1) * P
    def hy(r): return M + (r - 1) * P
    g = []
    g.append(f'<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg">')
    g.append(f'<rect x="{M-18}" y="{M-18}" width="{W-2*M+36}" height="{H-2*M+36}" rx="8" '
             f'fill="var(--board)" stroke="var(--line)"/>')
    for c in range(1, COLS + 1):
        for r in range(1, ROWS + 1):
            g.append(f'<circle cx="{hx(c)}" cy="{hy(r)}" r="3" fill="var(--hole)"/>')
    for c in range(1, COLS + 1, 5):
        g.append(f'<text x="{hx(c)}" y="{M-24}" text-anchor="middle" font-size="11" '
                 f'fill="var(--muted)">{c}</text>')
    for r in range(1, ROWS + 1, 5):
        g.append(f'<text x="{M-24}" y="{hy(r)+4}" text-anchor="middle" font-size="11" '
                 f'fill="var(--muted)">{r}</text>')
    for ref, c0, r0, c1, r1, nm in BOXES:
        col = COLORS.get(ref, '--ui')
        xa, xb = sorted((hx(c0), hx(c1)))
        x, y = xa - 9, hy(r0) - 9
        w_, h_ = (xb - xa) + 18, (r1 - r0) * P + 18
        g.append(f'<rect x="{x}" y="{y}" width="{w_}" height="{h_}" rx="5" fill="none" '
                 f'stroke="var({col})" stroke-width="1.8" stroke-dasharray="5 3"/>')
        g.append(f'<text x="{x + 3}" y="{y - 4}" font-size="11.5" font-weight="600" '
                 f'fill="var({col})">{nm}</text>')
    used_pins = {(r, p) for ns in nets.values() for r, p in ns}
    for ref, pins in place.items():
        col = COLORS.get(ref, '--ui')
        for pin, (c, r) in pins.items():
            if (ref, pin) not in used_pins:
                continue
            g.append(f'<circle cx="{hx(c)}" cy="{hy(r)}" r="5.5" fill="var({col})"/>')
    g.append('</svg>')
    return ''.join(g)

svg = [build_svg(False)]
svg_back = build_svg(True)

wire_rows = '\n'.join(
    f'<tr><td class="mono"><b>{n}</b></td><td class="mono">{cnt}</td><td>{ch}</td></tr>'
    for n, cnt, ch in rows_wire)

html = f"""<!doctype html>
<html lang="ja"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>ユニバーサル基板 配置＆配線（現行回路）</title>
<style>
 :root{{--bg:#f7f8fa;--surface:#fff;--board:#e8eef3;--hole:#9fb0bf;--ink:#16202a;
   --muted:#5d6b7a;--line:#d3dbe3;--accent:#0e7c86;
   --pico:#1f6f3c;--pwr:#c8471f;--crsf:#2f7d32;--dbg:#2f6fd0;--ui:#7a4fd0;}}
 @media(prefers-color-scheme:dark){{:root{{--bg:#0c1116;--surface:#151d25;--board:#14202a;
   --hole:#3b4d5c;--ink:#e7eef5;--muted:#93a3b3;--line:#233039;--accent:#2dd4bf;
   --pico:#3fa565;--pwr:#f08a5d;--crsf:#5cc46a;--dbg:#6aa6f2;--ui:#a98ce8;}}}}
 *{{box-sizing:border-box}} body{{margin:0;background:var(--bg);color:var(--ink);
   font-family:ui-sans-serif,-apple-system,"Hiragino Sans","Noto Sans JP",sans-serif;
   line-height:1.6}}
 .wrap{{max-width:1080px;margin:0 auto;padding:36px 20px 70px}}
 h1{{font-size:26px;margin:0 0 6px}} h2{{font-size:18px;margin:34px 0 8px}}
 .lede{{color:var(--muted);margin:0 0 6px;max-width:64ch}}
 .fig{{background:var(--surface);border:1px solid var(--line);border-radius:12px;
   padding:14px;overflow-x:auto;margin-top:12px}}
 .fig svg{{display:block;min-width:820px;width:100%;height:auto}}
 table{{border-collapse:collapse;width:100%;font-size:13.5px;margin-top:8px}}
 th,td{{border-bottom:1px solid var(--line);padding:7px 10px;text-align:left;
   vertical-align:top}}
 th{{background:var(--board);font-size:11.5px;letter-spacing:.06em;text-transform:uppercase;
   color:var(--muted)}}
 .mono{{font-family:ui-monospace,Menlo,monospace;white-space:nowrap}}
 .note{{background:var(--surface);border:1px solid var(--line);border-left:4px solid var(--accent);
   border-radius:8px;padding:12px 15px;margin:14px 0;font-size:14px}}
 .warn{{border-left-color:var(--pwr)}}
 ol li,ul li{{margin:4px 0}} code{{font-family:ui-monospace,Menlo,monospace;
   background:var(--board);padding:1px 5px;border-radius:4px;font-size:.92em}}
 @media print{{body{{background:#fff}} .fig{{break-inside:avoid}}}}
</style></head><body><div class="wrap">
<h1>ユニバーサル基板 — 配置＆配線</h1>
<p class="lede">検証済みの回路（KiCad版と同一のネットリスト）を 2.54mm ピッチの
マス目に落としたもの。配線リストはネットリストから機械生成しているので漏れが無い。</p>

<div class="note">
<b>必要な基板: {COLS} × {ROWS} 穴以上（穴の範囲で約 {(COLS-1)*2.54:.0f} × {(ROWS-1)*2.54:.0f} mm）</b><br>
95×72mm クラスの片面ユニバーサル基板でぎりぎり収まる。<b>買う前に実物の穴数を数えること</b>
（縁の余白のぶん、カタログ寸法より穴数が少ない。95×72mmでも30×25穴しかない製品が実在する）。
余裕を見るなら 100×75mm 以上。具体的な商品と、基板以外に買うものは
<a href="../hardware/README.md">hardware/README.md の「部品」</a>にまとめてある。
座標は <code>(列, 行)</code> で、左上が (1,1)。
</div>

<div class="note warn">
<b>⚠️ 通電前に必ず確認（Pico即死を防ぐ3点）</b>
<ol style="margin:6px 0 0">
 <li><b>降圧モジュールは繋ぐ前に単体で5.0Vへ調整</b>。可変品は初期12V等のことがある。</li>
 <li><b>+5V と VBAT(7〜13V) を絶対に接触させない</b>。テスターの導通モードで
     <code>(28,9)</code> と <code>(35,9)</code> の間が導通しないことを確認（降圧モジュール未接続時）。</li>
 <li><b>給電は VBUS (27,3) のみ</b>。VSYS (27,4) には入れない
     （内部D1でUSBに5Vが回らずゲームパッドに給電できない）。</li>
 <li><b>J3.1 → F1.2 の線（ヒューズより前）は最短で引き、VBATの線と束ねない</b>。
     ここだけはヒューズに守られていないので、短絡するとF1が意味を失う。</li>
</ol>
</div>

<div class="fig">{''.join(svg)}</div>

<h2>はんだ面（裏から見た図）</h2>
<div class="note warn">
<b>裏返すと左右が反転する。</b>上の図は部品面（表）から見たもの。実際に配線するのは裏なので、
配線中はこちらの図を見ること。<b>行番号は変わらず、列番号だけ右から左に進む。</b>
</div>
<div class="fig">{svg_back}</div>

<h2>一番下の行（電源）の並び</h2>
<p class="lede">行{ROWS}は左から右へ <b>{j3p} J3(LiPo+) → {f1in} F1 {f1out} → C1 → C2</b> と、
電流の向きどおりに並べてある。C1/C2の＋が左を向いているのはこのため。</p>
<div class="note warn">
<b>J3とF1は必ず隣どうしに置く。</b>この2つの間だけはヒューズに守られていないので、
離すと無保護なLiPo+が基板を横断することになる。現状は {j3p} から {f1in} まで
<b>{fuse_gap}mm</b>。
</div>

<h2>裏面の配線について — 確認済みのことと、していないこと</h2>
<div class="note">
<b>確認済み（生成のたびに機械で検査）</b>
<ul style="margin:6px 0">
 <li>ネットリストの全ピンに穴が割り当たっている（漏れたら図を作らない）</li>
 <li>同じ穴を2つの部品が使っていない</li>
 <li><b>裸のGND母線が、別ネットのピンを貫通していない</b></li>
</ul>
<b>していないこと</b>
<ul style="margin:6px 0">
 <li><b>1本ずつの引き回しは決めていない</b>（下の配線リストの28本）。被覆線・UEWを使う前提なので
     交差は自由で、順番も問わない。裏面で実際にどう這わせるかは組む人の裁量。</li>
 <li>実物の部品での現物合わせ（J2とF1は実測していない）</li>
</ul>
</div>

<h2>配線のやり方</h2>
<p class="lede">片面ユニバーサル基板の前提。<b>部品は表に挿し、配線は全部裏（はんだ面）</b>。</p>
<table><thead><tr><th>用途</th><th>使うもの</th><th>理由</th></tr></thead><tbody>
<tr><td>GND母線</td><td class="mono">すずメッキ線 φ0.6</td>
    <td>太く低抵抗。直線で引ければ交差しないので裸線でよい</td></tr>
<tr><td>電源 (+5V / VBAT)</td><td class="mono">被覆線 AWG24程度</td>
    <td>電流が流れる。交差するので被覆必須</td></tr>
<tr><td>信号</td><td class="mono">被覆線 AWG26〜30 / UEW(ポリウレタン線)</td>
    <td>本数が多く交差する。UEWなら細くて取り回しが楽</td></tr>
<tr><td>隣接する穴どうし</td><td class="mono">部品の足</td>
    <td>切り落とさず曲げて隣へ渡す。線が減る</td></tr>
</tbody></table>
<div class="note">
<b>足を使える箇所</b>（隣の穴なので線が要らない）:
LEDのアノードと抵抗の足 — <span class="mono">D1(3,16)-R1(4,16)</span> /
<span class="mono">D2(3,18)-R2(4,18)</span> / <span class="mono">D3(3,20)-R3(4,20)</span> /
<span class="mono">D4(3,22)-R4(4,22)</span> / <span class="mono">D5(3,24)-R5(4,24)</span>
</div>
<div class="note warn">
<b>はんだブリッジで長い距離を繋がない。</b>隣の穴どうしなら可だが、何穴も盛って繋ぐのは
後で剥がれる・短絡する。素直に線を使う。
</div>

<h2>配線リスト（GND以外）</h2>
<p class="lede">同じネットの穴どうしを繋ぐ。→ の順に繋いでも、どの順でも電気的には同じ。</p>
<table><thead><tr><th>ネット</th><th>点数</th><th>繋ぐ穴</th></tr></thead>
<tbody>{wire_rows}</tbody></table>

<h2>GND（{len(gnd_holes)}点）</h2>
<div class="note warn">
<b>1本ずつ配線せず、下の6本の母線を張る。</b> 錫メッキ線（φ0.6mm程度）を裏面に渡し、
各GND点から最短で落とす。母線は<b>裸線なので、通る穴に別ネットのピンがあってはいけない</b> —
生成時に検査しており、引っかかれば図が作られない。
</div>
<table><thead><tr><th>母線</th><th>場所</th><th>役目</th></tr></thead><tbody>
{''.join(f'<tr><td class="mono"><b>{t}</b></td><td class="mono">{w}</td><td>{y}</td></tr>'
         for t, w, _c, y in GND_BUS)}
</tbody></table>
<div class="note warn">
<b>⚠️ 幹(A)が列13から始まるのは安全のため。</b><code>{j3p} J3.1</code> と
<code>{f1in} F1.2</code> は<b>ヒューズより前のLiPo+</b>で、裸の母線が隣の穴を通ると
半田のはみ出しで<b>ヒューズを介さずにLiPoが短絡する</b>（数十Aが出る）。
この2つの真上 <code>(10,25)</code>〜<code>(12,25)</code> には<b>裸線を置かない</b>
（幹Fを行24へ迂回させてあるのはこのため）。<br>
LiPo−側の <code>{j3g} J3.2</code> を外側に置いてあるのも同じ理由で、
<b>無保護な {j3p}→{f1in} の区間にGNDピンを挟まない</b>ようにしている。
GND戻りは幹Fの末端 <code>(8,25)</code> で受ける。
</div>
<p>この6本に<b>直結または隣（1穴）になるGND点が {len(gnd_pins) - len(gnd_drops)}/{len(gnd_pins)}</b>。
残り {len(gnd_drops)}点は個別に線を落とす:</p>
<table><thead><tr><th>GND点</th><th>穴</th><th>最寄りの母線まで</th></tr></thead><tbody>
{''.join(f'<tr><td class="mono">{p}</td><td class="mono">({h[0]},{h[1]})</td>'
         f'<td class="mono">{d}穴</td></tr>' for p, h, d in gnd_drops)}
</tbody></table>
<p class="lede">GND全{len(gnd_holes)}点:</p>
<p class="mono" style="font-size:12.5px;line-height:2">{'　'.join(gnd_holes)}</p>

<h2>組み立て順</h2>
<ol>
 <li><b>ヘッダから</b>。Picoの2×20メスヘッダを (20,3)-(20,22) と (27,3)-(27,22) に。
     <b>USB側を行1（上端）に向ける</b>。7穴間隔（17.78mm）であることを挿す前に確認。</li>
 <li><b>GNDバス</b>を張る（上記）。後からだと部品が邪魔になる。</li>
 <li>背の低い順に: 抵抗 → ダイオード/LED → IC無し → コンデンサ → スイッチ →
     コネクタ → ヒューズホルダ。</li>
 <li>各ネットを配線したら、<b>テスターの導通モードで配線リストを1行ずつ潰す</b>。
     通電前にここで潰すのが一番安い。</li>
 <li>通電前に <b>J3の極性</b>と <b>+5VとVBATが短絡していないこと</b>をテスターで確認。</li>
 <li>降圧モジュールは<b>繋ぐ前に単体で5.0Vに調整</b>してから接続する。</li>
</ol>

<h2>部品ごとの注意</h2>
<p>定数・寸法・購入情報は <a href="../hardware/README.md">hardware/README.md の「部品」</a>が正本。
ここは手組み固有の落とし穴だけ。</p>
<ul>
 <li><b>J2 降圧モジュール(MP1584EN)</b>: 穴の左右間隔が18.9mmで
     <b>2.54mmの倍数にならない</b>（7.44穴ぶん）。基板に直接挿さらないので、
     <b>リード線で配線する</b>か、片側だけピンヘッダで固定して反対側を線で繋ぐ。
     図の枠は設置スペースの目安。</li>
 <li><b>F1 ヒューズホルダは基板に挿さらない</b>。基板取付品はどちらも
     <b>足が太く、ピッチも2.54mmの倍数でない</b> —
     ミニ平型 <code>118222</code> は φ1.78mm・9.92×3.4mm、
     ミゼットのクリップ <code>110521</code>(FUC-03A) は φ1.7mm・足間6.7mm。
     ユニバーサル基板の穴(φ約1mm)には入らない。<br>
     <b>手組みでは配線用（インライン）ヒューズホルダを使い、LiPo+ の線に割り込ませるのが素直</b>。
     ヒューズ交換もしやすく、挿抜の力が基板にかからない。この場合F1は基板に載らないので
     <code>{f1in}</code> と <code>{f1out}</code> を直結する（図のF1枠は使わない）。<br>
     基板上に置きたい場合は、J2と同じく<b>リード線で {f1in} と {f1out} に繋ぎ</b>、
     本体は接着（ホットボンド／両面テープ）か結束バンドで固定する。ヒューズを挿す力が
     かかるので<b>はんだだけで支えないこと</b>。<b>買う基板は図の {COLS}×{ROWS} 穴より
     大きいので、本体は行{ROWS}より下へはみ出してよい</b> — 基板の端なので指が入り、
     ヒューズを抜き差しできる。</li>
 <li>⚠️ <b>基板中央（列11-19×行11-25）が一番広いが、そこにF1を置かないこと</b>。
     Picoの左列から左へ出る配線が13本通る帯で、ここに<b>LiPo+(7〜13V)の太線を2本
     横断させる</b>ことになる。擦れて信号線と短絡すると12VがGPIOに乗ってPicoが死ぬ。
     電源は下端と右側にまとめ、信号の帯と交わらせない。</li>
 <li><b>タクトスイッチ(SW1/SW2)は4本足のうち「対角の2本」だけを使う</b>。
     SW1は <code>{sw1a}</code> と <code>{sw1b}</code>、SW2は <code>{sw2a}</code> と
     <code>{sw2b}</code>。<b>残り2本は挿さない</b>（切るか、穴の無い所へ逃がす）。<br>
     4本足は<b>2本ずつが内部で繋がって1つの端子</b>になっていて、押すとその2組の間が繋がる。
     同じ組の2本を選ぶと、押しても押さなくても導通したまま＝常時押されている状態になる。
     <b>対角なら、どちらの向きで組になっていても必ず別々の端子を掴む</b>ので安全。</li>
 <li>⚠️ <b>挿す前にテスターで確かめる</b>。選んだ2本が、<b>離した状態で導通せず、
     押すと導通する</b>こと。これだけは部品の個体差に関係なく確実。<br>
     足間は6.5×4.5mmで2.54mmの倍数でないので、<b>7.62×5.08mm（3穴×2穴）に広げて</b>挿す。
     6.5mmを7.62mmへ広げる方が、5.08mmへ狭めるより足への負担が小さい。</li>
 <li><b>LED(D1〜D5)は極性あり</b>。<b>長い足がアノード(A)で、図では右側の穴</b>
     （抵抗に近い方）。短い足＝胴の平らな側が左でGND。</li>
 <li><b>電解コン C1/C3 も極性あり</b>。どちらの穴が＋かは下の
     「コンデンサの向き」の表に出してある。</li>
 <li><b>D6 TVS</b>は双方向品なので極性不問。</li>
 <li><b>コンデンサは2個1組で、容量違いを並列に入れている</b>（図で横並びなのはこのため）。
     C1(470µF)/C3(100µF)は<b>蓄え</b> — 送信バーストや突入電流でレールが落ちるのを支える、
     ミリ秒の仕事。C2/C4(100nF)は<b>高周波の逃がし</b>。電解コンはESR/ESLが大きく
     高周波では効かないので、セラミックを並べる。</li>
 <li>⚠️ <b>100nF(C2/C4)に効くのは「太い線」ではなく「短い線」</b>。効きを決めるのは
     配線の<b>ループインダクタンス</b>で、ほぼ長さに比例する（太さはほとんど効かない）。
     現状 <b>C2→J1.3 が約{d2}mm、C4→U1.40 が約{d4}mm</b>。この長さだと10MHz付近で
     配線のインピーダンスが100nF自身の数十倍になり、<b>ほぼ効かない</b>。
     <b>このまま行くと決めた（2026-11-03）</b>。動かすのは、組んでから症状が出た時でよい
     （CRSFのエラー増、ゲームパッド挿抜でのリセット、電源まわりのノイズ）。
     その時は <b>C2をJ1の隣、C4をU1.40の隣へ動かす</b>（GND側の戻りも一緒に短くする）。
     C1/C3は蓄えが仕事なので、この距離でも実害は無い。</li>
 <li><b>R6(680Ω)はGP0とNano TXの間に必ず直列</b>で入れる。半二重バスの衝突保護。</li>
</ul>

<h2>コンデンサの向き</h2>
<div class="note warn">
<b>左右は「部品面（最初の図）」で見たときの左右。</b>部品は部品面から挿すのでこれでよいが、
<b>はんだ面の図は列が右から左に進む</b>ので、向きをあちらの図で決めないこと。
</div>
<table><thead><tr><th>参照</th><th>容量</th><th>極性</th>
<th>＋側（電源）</th><th>−側（GND）</th></tr></thead><tbody>
{''.join(
    '<tr><td class="mono"><b>%s</b></td><td class="mono">%s</td><td>%s</td>'
    '<td class="mono">(%d,%d) %s &nbsp;%s</td>'
    '<td class="mono">(%d,%d) %s</td></tr>'
    % (c['ref'], c['value'],
       '<b>あり</b>（電解）' if c['polar'] else 'なし（セラミック）',
       c['hot'][0], c['hot'][1], c['hot_side'], c['rail'],
       c['gnd'][0], c['gnd'][1], c['gnd_side'])
    for c in cap_rows)}
</tbody></table>
<p class="lede"><b>電解コン（C1/C3）の見分け方</b>: <b>長い足が＋</b>。胴に白い帯が入っている側が
−なので、<b>白帯を「−側」の列に向けて挿す</b>。足を切ってしまった後は白帯だけが頼りになる。<br>
C2/C4 はセラミックなので<b>どちら向きでもよい</b>。表の列は配線の都合で決まっているだけ。</p>

<h2>LEDの対応</h2>
<table><thead><tr><th>LED</th><th>色</th><th>意味</th><th>Pico</th></tr></thead><tbody>
{''.join(f'<tr><td class="mono">D{i}</td><td>{c}</td><td>{LED_NAME[i]}</td>'
         f'<td class="mono">GP{9+i} (pin{19 if i == 5 else 13+i})</td></tr>'
         for i, c in enumerate(['赤','緑','青','任意','任意'], start=1))}
</tbody></table>
<p class="lede">D5 のみ GP14 (pin19)。GP15(pin20) は本個体にヘッダが無いため未使用。</p>

</div></body></html>
"""
open(OUT, 'w').write(html)
print(f'wrote {OUT}: {len(place)} parts, {len(rows_wire)} nets + GND({len(gnd_holes)}点)')
