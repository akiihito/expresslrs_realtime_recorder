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
place['SW1'] = {'1': (8, 6), '2': (10, 8)}                     # モード（対角の2本を使う）
place['SW3'] = {'1': (13, 10), '2': (16, 10)}                  # ArmスライドSW
place['J4'] = {'1': (2, 8), '2': (2, 9), '3': (2, 10)}         # TX / RX / GND
place['SW2'] = {'1': (8, 12), '2': (10, 14)}                   # 入力切替
for i, r in enumerate((16, 18, 20, 22, 24), start=1):
    place[f'D{i}'] = {'1': (2, r), '2': (3, r)}                # K / A
    place[f'R{i}'] = {'1': (8, r), '2': (4, r)}                # Pico側 / LED側
# J3とF1は基板右下（電源側）にまとめる。ヒューズホルダは基板取付品でもピンが
# φ1.7-1.78mm・ピッチが2.54の倍数でないためユニバーサル基板の穴に入らず、
# リード線で繋いで本体は接着で固定する（J2と同じ扱い）。本体ぶんの場所が要るので
# Picoの右の空き（列28-35×行17-25）に縦置きする。
# ⚠️ 中央（列11-19×行11-25）の方が広いが、そこはPicoの左列から左へ出る13本の
# 配線が通る帯なので、12Vの太線を通さない。
# J3も一緒に右下へ: 離すとヒューズ前の無保護なLiPo+が基板を横断してしまう。
place['J3'] = {'1': (35, 26), '2': (33, 26)}                   # LiPo+ / LiPo-
place['F1'] = {'2': (33, 24), '1': (33, 20)}                   # LiPo側 / VBAT側（縦置き）
place['C1'] = {'1': (13, 26), '2': (15, 26)}
place['C2'] = {'1': (17, 26), '2': (19, 26)}
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
    ('SW1', 8, 6, 10, 8, 'SW1 MODE'),
    ('J4', 2, 8, 2, 10, 'J4 UART'),
    ('SW3', 13, 10, 16, 10, 'SW3 ARM'),
    ('SW2', 8, 12, 10, 14, 'SW2 INPUT'),
    ('J3', 33, 26, 35, 26, 'J3 LiPo'),
    ('F1', 31, 18, 35, 25, 'F1 FUSE（縦置き）'),
    ('C1', 13, 26, 15, 26, 'C1'),
    ('C2', 17, 26, 19, 26, 'C2'),
    ('J2', 28, 4, 35, 10, 'J2 MP1584EN（リード線で配線）'),
    ('C3', 30, 12, 32, 12, 'C3'),
    ('C4', 30, 14, 32, 14, 'C4'),
    ('D6', 30, 16, 34, 16, 'D6 TVS'),
]
for i, r in enumerate((16, 18, 20, 22, 24), start=1):
    BOXES.append((f'D{i}', 2, r, 3, r, f'D{i}'))
    BOXES.append((f'R{i}', 4, r, 8, r, f'R{i} 100R'))

LED_NAME = {1: 'REC', 2: 'PLAY', 3: 'SIMPLE', 4: 'GENERIC', 5: 'LITERADIO'}

# ---------------------------------------------------------------- GND母線
# 裏面に張る裸のすずメッキ線。部品を動かすとここを異ネットのピンが貫通しうるので、
# 生成時に検査する（下の「母線の検査」）。
# ⚠️ 幹(A)を列30で止めてあるのは、右下の (33,24) F1.2 と (35,26) J3.1 が
# **ヒューズより前のLiPo+** で、裸線が隣を通ると半田のはみ出しでヒューズを
# 介さずにLiPoが短絡するため。J3.2へは被覆線で引く。
GND_BUS = [
    ('A', '行25 / 列1〜30',  [(c, 25) for c in range(1, 31)],
     '幹。列30で止める（右下はヒューズ前のLiPo+が近い）'),
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
    ('F', '列10 / 行8〜25',  [(10, r) for r in range(8, 26)],
     'SW1.2 / SW2.2'),
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
<b>⚠️ 幹(A)を列30で止めているのは安全のため。</b>右下の <code>(33,24) F1.2</code> と
<code>(35,26) J3.1</code> は<b>ヒューズより前のLiPo+</b>で、裸の母線が隣の穴を通ると
半田のはみ出しで<b>ヒューズを介さずにLiPoが短絡する</b>（数十Aが出る）。
<code>J3.2 (33,26)</code> へは被覆線で引くこと。
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
     <code>(35,26)</code> と <code>(33,20)</code> を直結する（図のF1枠は使わない）。<br>
     基板上に置きたい場合は、J2と同じく<b>リード線で (33,24) と (33,20) に繋ぎ</b>、
     本体は接着（ホットボンド／両面テープ）か結束バンドで固定する。ヒューズを挿す力が
     かかるので<b>はんだだけで支えないこと</b>。図の枠は本体ぶんの場所の目安で、
     基板の右端なので指が入りヒューズを抜き差しできる。</li>
 <li>⚠️ <b>基板中央（列11-19×行11-25）が一番広いが、そこにF1を置かないこと</b>。
     Picoの左列から左へ出る配線が13本通る帯で、ここに<b>LiPo+(7〜13V)の太線を2本
     横断させる</b>ことになる。擦れて信号線と短絡すると12VがGPIOに乗ってPicoが死ぬ。
     電源は下端と右側にまとめ、信号の帯と交わらせない。</li>
 <li><b>タクトスイッチ(SW1/SW2)</b>: ブレッドボードで使っているものをそのまま使う
     （2.54mmピッチに入る足のもの）。<b>対角の2本</b>を使うこと。同じ側の2本は
     内部で繋がっていて、押しても切り替わらない。</li>
 <li><b>LED(D1〜D5)</b>と<b>電解コン(C1/C3)</b>は極性あり。LEDは長い足がアノード(A)、
     図では右側の穴。</li>
 <li><b>D6 TVS</b>は双方向品なので極性不問。</li>
 <li><b>C1/C2はJ1(Nano TX)の近く、C3/C4はPicoのVBUS近く</b>が理想だが、
     ユニバーサル基板では配線が長くなるのは避けられない。せめて
     <b>太めの線（φ0.6mm以上）</b>で繋ぐ。</li>
 <li><b>R6(680Ω)はGP0とNano TXの間に必ず直列</b>で入れる。半二重バスの衝突保護。</li>
</ul>

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
