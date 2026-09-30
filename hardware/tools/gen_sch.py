#!/usr/bin/env python3
"""ExpressLRS Realtime Recorder の回路図(.kicad_sch)を生成する。

KiCad標準ライブラリからシンボル定義を取り出して埋め込むので、
生成物はKiCadでそのまま開ける。配線はネットラベル方式。
"""
import hashlib, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sexp

SYMDIR = '/Applications/KiCad/KiCad.app/Contents/SharedSupport/symbols'
OUT = sys.argv[1] if len(sys.argv) > 1 else 'recorder.kicad_sch'

_uid = [0]
def uuid():
    _uid[0] += 1
    h = hashlib.md5(f'elrs-recorder-{_uid[0]}'.encode()).hexdigest()
    return f'{h[0:8]}-{h[8:12]}-{h[12:16]}-{h[16:20]}-{h[20:32]}'

# ---------------------------------------------------------------- シンボル取得
_libcache = {}
def load_lib(lib):
    if lib not in _libcache:
        _libcache[lib] = sexp.parse(open(f'{SYMDIR}/{lib}.kicad_sym').read())[0]
    return _libcache[lib]

_symcache = {}
def get_symbol(lib_id):
    """lib_symbols に入れる定義と、ピン座標 {番号: (x, y, rot)} を返す"""
    if lib_id in _symcache:
        return _symcache[lib_id]
    lib, name = lib_id.split(':')
    doc = load_lib(lib)
    for s in sexp.find(doc, 'symbol'):
        if s[1][1] != name:
            continue
        node = [x for x in s]
        node[1] = ('str', lib_id)          # lib_symbols では lib_id 名で持つ
        pins = {}
        for sub in sexp.find(s, 'symbol'):
            for p in sexp.find(sub, 'pin'):
                at = sexp.find(p, 'at')[0]
                num = sexp.find(p, 'number')[0][1][1]
                pins[num] = (float(at[1]), float(at[2]), float(at[3]))
        _symcache[lib_id] = (node, pins)
        return _symcache[lib_id]
    raise SystemExit(f'symbol not found: {lib_id}')

# ---------------------------------------------------------------- 配置ヘルパ
elements = []      # 出力する S式ノード
used_libs = {}

def pin_xy(lib_id, at, num, mirror_y=False):
    """シンボル座標→回路図座標。回路図はY下向き、シンボルはY上向き。"""
    _, pins = get_symbol(lib_id)
    sx, sy, rot = pins[num]
    px, py, prot = at
    if prot == 180:
        sx, sy = -sx, -sy
        rot = (rot + 180) % 360
    elif prot == 90:
        sx, sy = -sy, sx
        rot = (rot + 90) % 360
    elif prot == 270:
        sx, sy = sy, -sx
        rot = (rot + 270) % 360
    if mirror_y:
        sx = -sx
        rot = (180 - rot) % 360
    return (round(px + sx, 2), round(py - sy, 2), rot)

def place(lib_id, ref, value, at, mirror_y=False, hide_ref=False,
          footprint=''):
    if not footprint:
        footprint = FOOTPRINTS.get(ref, '')
    node, _ = get_symbol(lib_id)
    used_libs[lib_id] = node
    u = uuid()
    sym = ['symbol',
           ['lib_id', ('str', lib_id)],
           ['at', str(at[0]), str(at[1]), str(int(at[2]))],
           ['unit', '1']]
    if mirror_y:
        sym.append(['mirror', 'y'])
    sym += [['exclude_from_sim', 'no'], ['in_bom', 'yes'], ['on_board', 'yes'],
            ['dnp', 'no'], ['uuid', ('str', u)]]
    # Reference / Value は本体の少し外へ
    # 回転部品でも本体に重ならないよう、上下に離して中央揃えで置く
    off = 5.08 if at[2] in (90, 270) else 3.81
    ref_fx = ['effects', ['font', ['size', '1.27', '1.27']]]
    if hide_ref:                      # 電源シンボルの #PWR は慣例どおり隠す
        ref_fx.append(['hide', 'yes'])
    sym.append(['property', ('str', 'Reference'), ('str', ref),
                ['at', str(at[0]), str(round(at[1] - off, 2)), '0'],
                ref_fx])
    sym.append(['property', ('str', 'Value'), ('str', value),
                ['at', str(at[0]), str(round(at[1] + off, 2)), '0'],
                ['effects', ['font', ['size', '1.27', '1.27']]]])
    sym.append(['property', ('str', 'Footprint'), ('str', footprint),
                ['at', str(at[0]), str(at[1]), '0'],
                ['effects', ['font', ['size', '1.27', '1.27']], ['hide', 'yes']]])
    sym.append(['instances',
                ['project', ('str', 'recorder'),
                 ['path', ('str', '/' + ROOT_UUID),
                  ['reference', ('str', ref)], ['unit', '1']]]])
    elements.append(sym)
    return at

def wire(a, b):
    elements.append(['wire',
                     ['pts', ['xy', str(a[0]), str(a[1])],
                             ['xy', str(b[0]), str(b[1])]],
                     ['stroke', ['width', '0'], ['type', 'default']],
                     ['uuid', ('str', uuid())]])

def label(text, at, rot=0, justify='left'):
    elements.append(['label', ('str', text),
                     ['at', str(at[0]), str(at[1]), str(int(rot))],
                     ['effects', ['font', ['size', '1.27', '1.27']],
                      ['justify', justify]],
                     ['uuid', ('str', uuid())]])

def junction(at):
    elements.append(['junction', ['at', str(at[0]), str(at[1])],
                     ['diameter', '0'], ['color', '0', '0', '0', '0'],
                     ['uuid', ('str', uuid())]])

def no_connect(at):
    elements.append(['no_connect', ['at', str(at[0]), str(at[1])],
                     ['uuid', ('str', uuid())]])

def text_note(s, at, size=1.27):
    # 複数行はKiCadの文字列エスケープに依存しないよう、行ごとに別要素で置く
    for i, line in enumerate(s.split('\n')):
        elements.append(['text', ('str', line),
                         ['at', str(round(at[0], 2)),
                          str(round(at[1] + i * (size * 1.6), 2)), '0'],
                         ['effects', ['font', ['size', str(size), str(size)]],
                          ['justify', 'left']],
                         ['uuid', ('str', uuid())]])

def stub_label(lib_id, at, pin, name, length=5.08, mirror_y=False):
    """ピンから短い配線を出してネットラベルを付ける"""
    x, y, rot = pin_xy(lib_id, at, pin, mirror_y)
    if rot == 0:      end, lrot, just = (x - length, y), 0, 'right'
    elif rot == 180:  end, lrot, just = (x + length, y), 0, 'left'
    elif rot == 90:   end, lrot, just = (x, y + length), 90, 'right'
    else:             end, lrot, just = (x, y - length), 90, 'left'
    end = (round(end[0], 2), round(end[1], 2))
    wire((x, y), end)
    label(name, end, lrot, just)
    return end

def power(lib_id, at, mirror=False):
    """電源シンボル（GND/+5V等）を置いてピン座標を返す"""
    node, _ = get_symbol(lib_id)
    used_libs[lib_id] = node
    name = lib_id.split(':')[1]
    place(lib_id, '#PWR', name, at, mirror_y=mirror, hide_ref=True)
    return pin_xy(lib_id, at, '1', mirror)


# ================================================================= フットプリント
# 全てスルーホール。初めての基板をハンダ付け1工程で組めるようにするため。
# ⚠️ J2(降圧モジュール)は実物を測っていないので暫定。J3はピグテールを直付けする想定。
FOOTPRINTS = {
    'U1': 'recorder:RPi_Pico_Headers',
    'R1': 'Resistor_THT:R_Axial_DIN0207_L6.3mm_D2.5mm_P10.16mm_Horizontal',
    'D1': 'LED_THT:LED_D3.0mm',
    'C1': 'Capacitor_THT:CP_Radial_D10.0mm_P5.00mm',
    'C2': 'Capacitor_THT:C_Disc_D5.0mm_W2.5mm_P5.00mm',
    'C3': 'Capacitor_THT:CP_Radial_D6.3mm_P2.50mm',
    'C4': 'Capacitor_THT:C_Disc_D5.0mm_W2.5mm_P5.00mm',
    'D6': 'Diode_THT:D_DO-15_P10.16mm_Horizontal',
    'F1': 'Fuse:Fuseholder_Blade_Mini_Keystone_3568',
    'SW1': 'Button_Switch_THT:SW_PUSH_6mm',
    'SW2': 'Button_Switch_THT:SW_PUSH_6mm',
    'SW3': 'Button_Switch_THT:SW_DIP_SPSTx01_Slide_9.78x4.72mm_W7.62mm_P2.54mm',
    'J1': 'Connector_JST:JST_XH_B3B-XH-A_1x03_P2.50mm_Vertical',
    'J2': 'Connector_PinHeader_2.54mm:PinHeader_1x04_P2.54mm_Vertical',
    'J3': 'Connector_Wire:SolderWire-0.75sqmm_1x02_P7mm_D1.25mm_OD3.5mm',
    'J4': 'Connector_PinHeader_2.54mm:PinHeader_1x03_P2.54mm_Vertical',
}
for _r in ('R2', 'R3', 'R4', 'R5', 'R6', 'R7'):
    FOOTPRINTS[_r] = FOOTPRINTS['R1']
for _d in ('D2', 'D3', 'D4', 'D5'):
    FOOTPRINTS[_d] = FOOTPRINTS['D1']

ROOT_UUID = uuid()

# ================================================================= 回路
PICO = 'MCU_Module:RaspberryPi_Pico'
PX, PY = 139.70, 109.22
# フットプリントはPCB設計時に割り当てる（ここでは未指定）
place(PICO, 'U1', 'Raspberry Pi Pico', (PX, PY, 0))

# --- Pico 左側: 信号 ---
stub_label(PICO, (PX, PY, 0), '1',  'CRSF_TX')     # GP0
# GP1は保護抵抗を挟んでバスへ。GP0側の680Ωと違い直結だと、J1を逆挿しした際に
# VBAT(最大13V)が素通しでGPIOへ入る。1kΩなら故障電流を十数mAに抑えられる。
# 921600bpsに対し 1k×入力容量数pF = 数ns なので波形への影響は無視できる。
gp1 = pin_xy(PICO, (PX, PY, 0), '2')
place('Device:R', 'R7', '1k', (gp1[0] - 12.7, gp1[1], 90))
r7r = pin_xy('Device:R', (gp1[0] - 12.7, gp1[1], 90), '2')
r7l = pin_xy('Device:R', (gp1[0] - 12.7, gp1[1], 90), '1')
wire((gp1[0], gp1[1]), (r7r[0], r7r[1]))
wire((r7l[0], r7l[1]), (r7l[0] - 5.08, r7l[1]))
label('CRSF_BUS', (r7l[0] - 5.08, r7l[1]), 0, 'right')
stub_label(PICO, (PX, PY, 0), '4',  'BTN_MODE')    # GP2
stub_label(PICO, (PX, PY, 0), '5',  'SW_ARM')      # GP3
stub_label(PICO, (PX, PY, 0), '6',  'DBG_TX')      # GP4
stub_label(PICO, (PX, PY, 0), '7',  'DBG_RX')      # GP5
stub_label(PICO, (PX, PY, 0), '9',  'BTN_INPUT')   # GP6
stub_label(PICO, (PX, PY, 0), '14', 'LED_REC')     # GP10
stub_label(PICO, (PX, PY, 0), '15', 'LED_PLAY')    # GP11
stub_label(PICO, (PX, PY, 0), '16', 'LED_SIMPLE')  # GP12
stub_label(PICO, (PX, PY, 0), '17', 'LED_GENERIC') # GP13
stub_label(PICO, (PX, PY, 0), '19', 'LED_LITERADIO')# GP14

# --- Pico 電源 ---
vb = pin_xy(PICO, (PX, PY, 0), '40')               # VBUS (上)
wire((vb[0], vb[1]), (vb[0], vb[1] - 7.62))
power('power:+5V', (vb[0], vb[1] - 7.62, 0))

gnd = pin_xy(PICO, (PX, PY, 0), '3')               # GND (下, 全GNDピン共通)
wire((gnd[0], gnd[1]), (gnd[0], gnd[1] + 5.08))
power('power:GND', (gnd[0], gnd[1] + 5.08, 0))

# 意図的に使わないピンには No-Connect を付ける（ERCを通し、意図を明示する）
for _p in ('10', '11', '12', '20', '21', '22', '24', '25', '26', '27', '29',
           '30', '31', '32', '33', '34', '35', '36', '37', '39'):
    _x, _y, _ = pin_xy(PICO, (PX, PY, 0), _p)
    no_connect((_x, _y))

text_note('USB(micro-B) = ゲームパッド接続\n※VSYS給電はNG（USBポートに5Vが回らない）',
          (PX - 30, PY - 48), 1.27)

# ================================================================= LED 5個
LEDS = [('D1', 'LED_REC',       'Red',   'R1'),
        ('D2', 'LED_PLAY',      'Green', 'R2'),
        ('D3', 'LED_SIMPLE',    'Blue',  'R3'),
        ('D4', 'LED_GENERIC',   'LED',   'R4'),
        ('D5', 'LED_LITERADIO', 'LED',   'R5')]
LX, LY0, DY = 243.84, 60.96, 15.24
for i, (dref, net, color, rref) in enumerate(LEDS):
    y = LY0 + i * DY
    # R(横向き) → LED(横向き) → GND
    place('Device:R', rref, '100R', (LX, y, 90))
    rl = pin_xy('Device:R', (LX, y, 90), '1')
    rr = pin_xy('Device:R', (LX, y, 90), '2')
    wire((rl[0], rl[1]), (rl[0] - 5.08, rl[1]))
    label(net, (rl[0] - 5.08, rl[1]), 0, 'right')

    place('Device:LED', dref, color, (LX + 15.24, y, 90))
    la = pin_xy('Device:LED', (LX + 15.24, y, 90), '2')   # アノード
    lk = pin_xy('Device:LED', (LX + 15.24, y, 90), '1')   # カソード
    wire((rr[0], rr[1]), (la[0], la[1]))
    wire((lk[0], lk[1]), (lk[0] + 5.08, lk[1]))
    power('power:GND', (lk[0] + 5.08, lk[1], 90))

text_note('LEDは5個とも100Ω（緑/青はVf≈3Vで330Ωでは暗い）',
          (LX - 12, LY0 - 10), 1.27)

# ================================================================= スイッチ 3個
SWS = [('SW1', 'BTN_MODE',  'SW_Push', 'モード切替(GP2)'),
       ('SW2', 'BTN_INPUT', 'SW_Push', '入力切替(GP6)'),
       ('SW3', 'SW_ARM',    'SW_SPST', 'Armトグル(GP3)')]
SX, SY0 = 55.88, 71.12
for i, (ref, net, kind, note) in enumerate(SWS):
    y = SY0 + i * 20.32
    lib = f'Switch:{kind}'
    place(lib, ref, kind, (SX, y, 0))
    p1 = pin_xy(lib, (SX, y, 0), '1')
    p2 = pin_xy(lib, (SX, y, 0), '2')
    wire((p1[0], p1[1]), (p1[0] - 5.08, p1[1]))
    label(net, (p1[0] - 5.08, p1[1]), 0, 'right')
    wire((p2[0], p2[1]), (p2[0] + 5.08, p2[1]))
    power('power:GND', (p2[0] + 5.08, p2[1], 90))
    text_note(note, (SX - 12, y - 6), 1.0)

text_note('スイッチは内部プルアップ使用のため外付け抵抗不要',
          (SX - 15, SY0 - 14), 1.27)

# ================================================================= Nano TX V2
NX, NY = 243.84, 144.78
place('Connector_Generic:Conn_01x03', 'J1', 'Nano TX V2', (NX, NY, 0))
# ピン1=CRSF, 2=GND, 3=VBAT（背面視 左から）
c1 = pin_xy('Connector_Generic:Conn_01x03', (NX, NY, 0), '1')
c2 = pin_xy('Connector_Generic:Conn_01x03', (NX, NY, 0), '2')
c3 = pin_xy('Connector_Generic:Conn_01x03', (NX, NY, 0), '3')
# CRSF は 680Ω 直列
place('Device:R', 'R6', '680R', (c1[0] - 20.32, c1[1], 90))
r6l = pin_xy('Device:R', (c1[0] - 20.32, c1[1], 90), '1')
r6r = pin_xy('Device:R', (c1[0] - 20.32, c1[1], 90), '2')
wire((r6l[0], r6l[1]), (r6l[0] - 5.08, r6l[1]))
label('CRSF_TX', (r6l[0] - 5.08, r6l[1]), 0, 'right')
# 半二重: RX(GP1)は抵抗より先のバス側に付く（参照図 63bit R63b と同じ）。
# 自分の送信エコーもRXに入るが、ファーム側の drain 処理で読み捨てている。
# T字接続を確実にするため、水平線を分岐点で2本に割って端点を一致させる。
mid = (round(c1[0] - 7.62, 2), c1[1])
wire((r6r[0], r6r[1]), mid)
wire(mid, (c1[0], c1[1]))
wire(mid, (mid[0], mid[1] - 7.62))
label('CRSF_BUS', (mid[0], mid[1] - 7.62), 90, 'left')
junction(mid)
wire((c2[0], c2[1]), (c2[0] - 7.62, c2[1]))
power('power:GND', (c2[0] - 7.62, c2[1], 270))
wire((c3[0], c3[1]), (c3[0] - 7.62, c3[1]))
label('VBAT_7_13V', (c3[0] - 7.62, c3[1]), 0, 'right')
text_note('Nano TX V2 (背面視 左から CRSF/GND/7-13V)\n※半二重1本・反転UART 921600bps',
          (NX - 30, NY - 10), 1.27)

# ================================================================= 電源系
BX, BY = 60.96, 160.02
place('Connector_Generic:Conn_01x04', 'J2', 'Buck MP1584E', (BX, BY, 0))
b = {n: pin_xy('Connector_Generic:Conn_01x04', (BX, BY, 0), n)
     for n in ('1', '2', '3', '4')}
for n, net in (('1', 'VBAT_7_13V'), ('3', '+5V')):
    wire((b[n][0], b[n][1]), (b[n][0] - 7.62, b[n][1]))
    label(net, (b[n][0] - 7.62, b[n][1]), 0, 'right')
for n in ('2', '4'):
    wire((b[n][0], b[n][1]), (b[n][0] - 7.62, b[n][1]))
    power('power:GND', (b[n][0] - 7.62, b[n][1], 270))
text_note('IN+ / IN- / OUT+ / OUT-\n⚠️ Picoに繋ぐ前にテスターで5.0Vへ調整',
          (BX - 30, BY - 10), 1.27)

PWX, PWY = 60.96, 205.74
place('Connector_Generic:Conn_01x02', 'J3', 'LiPo 3S / PSU', (PWX, PWY, 0))
p1 = pin_xy('Connector_Generic:Conn_01x02', (PWX, PWY, 0), '1')
p2 = pin_xy('Connector_Generic:Conn_01x02', (PWX, PWY, 0), '2')
# LiPo+ の主線にヒューズ。定格は実測して決めること（初期値2A）
place('Device:Fuse', 'F1', '2A', (p1[0] - 15.24, p1[1], 90))
f1a = pin_xy('Device:Fuse', (p1[0] - 15.24, p1[1], 90), '1')
f1b = pin_xy('Device:Fuse', (p1[0] - 15.24, p1[1], 90), '2')
wire((f1b[0], f1b[1]), (p1[0], p1[1]))
wire((f1a[0], f1a[1]), (f1a[0] - 5.08, f1a[1]))
label('VBAT_7_13V', (f1a[0] - 5.08, f1a[1]), 0, 'right')
wire((p2[0], p2[1]), (p2[0] - 7.62, p2[1]))
power('power:GND', (p2[0] - 7.62, p2[1], 270))
text_note('⚠️ Buck出力5VとLiPo+は絶対に接続しない\nGNDはLiPo−起点のスター結線',
          (PWX - 30, PWY - 8), 1.27)

# ================================================================= コンデンサ
# ラベル方式なので、各コンデンサは「電源ラベル → コンデンサ → GND」で置くだけでよい。
CAPS = [('C1', 'Device:C_Polarized', '470uF/25V', 'VBAT_7_13V'),
        ('C2', 'Device:C',           '100nF',     'VBAT_7_13V'),
        ('C3', 'Device:C_Polarized', '100uF/16V', '+5V'),
        ('C4', 'Device:C',           '100nF',     '+5V')]
CX, CY, CDX = 132.08, 187.96, 20.32
for i, (ref, lib, val, net) in enumerate(CAPS):
    x = CX + i * CDX
    place(lib, ref, val, (x, CY, 0))
    top = pin_xy(lib, (x, CY, 0), '1')
    bot = pin_xy(lib, (x, CY, 0), '2')
    wire((top[0], top[1]), (top[0], top[1] - 5.08))
    if net == '+5V':
        power('power:+5V', (top[0], top[1] - 5.08, 0))
    else:
        label(net, (top[0], top[1] - 5.08), 90, 'left')
    wire((bot[0], bot[1]), (bot[0], bot[1] + 5.08))
    power('power:GND', (bot[0], bot[1] + 5.08, 0))

# 降圧モジュールが短絡故障すると入力の12Vが5Vレールに出る。このとき電流は
# 正常範囲なのでヒューズは飛ばない。TVSが導通して電流を引きヒューズを飛ばす。
# ⚠️ クランプ電圧はPicoの絶対最大(5.5V)より高いので、Picoの延命は保証できない。
# 主目的は「そのまま12Vが載り続ける状態」を断つことと、活線挿抜サージの吸収。
TVX, TVY = 213.36, 187.96
# KiCadのD_TVSは双方向シンボル。双方向品(P6KE6.8CA, DO-15)を指定して図と部品を一致させる。
# 双方向は実装時に極性を間違えようがないという利点もある。
place('Device:D_TVS', 'D6', 'P6KE6.8CA', (TVX, TVY, 90))
tv1 = pin_xy('Device:D_TVS', (TVX, TVY, 90), '1')
tv2 = pin_xy('Device:D_TVS', (TVX, TVY, 90), '2')
top_pin, bot_pin = (tv1, tv2) if tv1[1] < tv2[1] else (tv2, tv1)
wire((top_pin[0], top_pin[1]), (top_pin[0], top_pin[1] - 5.08))
power('power:+5V', (top_pin[0], top_pin[1] - 5.08, 0))
wire((bot_pin[0], bot_pin[1]), (bot_pin[0], bot_pin[1] + 5.08))
power('power:GND', (bot_pin[0], bot_pin[1] + 5.08, 0))

text_note('C1/C2: Nano TX VBAT直近に置く（送信バーストの電圧ドロップ対策）\n'
          'C3/C4: Pico VBUS直近に置く（ゲームパッド接続時の突入電流対策）\n'
          '⚠️ 電解コンの耐圧は3S満充電12.6Vを超えること。極性に注意\n'
          'D6: Buck短絡故障時に12Vが5Vへ出るのを断つ（ヒューズを飛ばす）',
          (CX - 12, CY - 24), 1.27)

# ================================================================= デバッグUART
UX, UY = 243.84, 215.90
place('Connector_Generic:Conn_01x03', 'J4', 'USB-Serial', (UX, UY, 0))
u1 = pin_xy('Connector_Generic:Conn_01x03', (UX, UY, 0), '1')
u2 = pin_xy('Connector_Generic:Conn_01x03', (UX, UY, 0), '2')
u3 = pin_xy('Connector_Generic:Conn_01x03', (UX, UY, 0), '3')
wire((u1[0], u1[1]), (u1[0] - 7.62, u1[1]))
label('DBG_TX', (u1[0] - 7.62, u1[1]), 0, 'right')
wire((u2[0], u2[1]), (u2[0] - 7.62, u2[1]))
label('DBG_RX', (u2[0] - 7.62, u2[1]), 0, 'right')
wire((u3[0], u3[1]), (u3[0] - 7.62, u3[1]))
power('power:GND', (u3[0] - 7.62, u3[1], 270))
text_note('変換器RXD←DBG_TX / TXD→DBG_RX\n921600bps（手持ちFTDIは115200指定で読める）',
          (UX - 32, UY - 10), 1.27)

# ================================================================= 出力
doc = ['kicad_sch',
       ['version', '20231120'],
       ['generator', ('str', 'eeschema')],
       ['generator_version', ('str', '9.0')],
       ['uuid', ('str', ROOT_UUID)],
       ['paper', ('str', 'A3')],
       ['title_block',
        ['title', ('str', 'ExpressLRS Realtime Recorder')],
        ['date', ('str', '2026-08-27')],
        ['rev', ('str', 'A')],
        ['comment', '1', ('str', 'Pico + gamepad -> CRSF -> Nano TX V2')]],
       ['lib_symbols'] + list(used_libs.values())]
doc += elements
doc.append(['sheet_instances', ['path', ('str', '/'), ['page', ('str', '1')]]])

open(OUT, 'w').write(sexp.dump(doc) + '\n')
print(f'wrote {OUT}: {len(elements)} elements, {len(used_libs)} symbols')
