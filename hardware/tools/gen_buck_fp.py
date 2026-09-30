#!/usr/bin/env python3
"""MP1584EN 降圧モジュール（22.3×16.8mm）のフットプリントを生成する。

寸法の根拠: 購入品の商品写真を画像解析してパッド位置を実測した。
基板左上からの実測値(mm):
    左列 x=1.63 / 右列 x=20.50
    y = 1.67, 4.22, 12.50, 15.08（上下対称・ペア間隔2.54mm）
これを中心対称に整えて x=±9.45 / y=±6.70,±4.16 とした。

ピン配置（部品面から見て。商品写真の表裏2枚から確定）:
    左列 = IN−(上ペア) / IN+(下ペア)
    右列 = OUT−(上ペア) / OUT+(下ペア)
裏面シルクは OUT−(左上) IN−(右上) OUT+(左下) IN+(右下) で、
裏返すと左右が入れ替わるため上記になる。部品面の ⊖/⊕ 表記が出力側に
あることとも一致する。

回路図シンボル Conn_01x04 との対応:
    pad1=IN+ pad2=IN− pad3=OUT+ pad4=OUT−
"""
import sys

BOARD_W, BOARD_H = 22.3, 16.8
PAD_X = 9.45          # 中心からの左右距離（実測 9.35 / 9.52 の中間）
PAD_Y_OUT = 6.70      # 外側の穴
PAD_Y_IN = PAD_Y_OUT - 2.54   # 内側の穴 = 4.16
DRILL, PAD = 1.0, 1.7

# (パッド番号, ラベル, x, y) 部品面から見た配置
PADS = [
    ('2', 'IN-',  -PAD_X, -PAD_Y_OUT), ('2', 'IN-',  -PAD_X, -PAD_Y_IN),
    ('1', 'IN+',  -PAD_X,  PAD_Y_IN),  ('1', 'IN+',  -PAD_X,  PAD_Y_OUT),
    ('4', 'OUT-',  PAD_X, -PAD_Y_OUT), ('4', 'OUT-',  PAD_X, -PAD_Y_IN),
    ('3', 'OUT+',  PAD_X,  PAD_Y_IN),  ('3', 'OUT+',  PAD_X,  PAD_Y_OUT),
]

out = []
w = out.append
w('(footprint "MP1584EN_Module"')
w('  (version 20240108)')
w('  (generator "gen_buck_fp.py")')
w('  (layer "F.Cu")')
w('  (descr "MP1584EN adjustable buck module, 22.3x16.8mm, 8 holes in 4 pairs '
  '(2.54mm pitch). Pads: 1=IN+ 2=IN- 3=OUT+ 4=OUT-. Dimensions measured from '
  'product photos; verify against the real module with a 1:1 printout.")')
w('  (tags "module buck dc-dc MP1584 MP1584EN")')
w('  (attr through_hole)')
w(f'  (property "Reference" "REF**" (at 0 {-BOARD_H/2 - 1.6:.2f} 0) (layer "F.SilkS")')
w('    (effects (font (size 1 1) (thickness 0.15))))')
w(f'  (property "Value" "MP1584EN" (at 0 {BOARD_H/2 + 1.6:.2f} 0) (layer "F.Fab")')
w('    (effects (font (size 1 1) (thickness 0.15))))')

hx, hy = BOARD_W / 2, BOARD_H / 2
for layer, width in (('F.SilkS', 0.12), ('F.Fab', 0.1)):
    w(f'  (fp_rect (start {-hx:.2f} {-hy:.2f}) (end {hx:.2f} {hy:.2f}) '
      f'(stroke (width {width}) (type solid)) (fill no) (layer "{layer}"))')
w(f'  (fp_rect (start {-hx-0.25:.2f} {-hy-0.25:.2f}) (end {hx+0.25:.2f} {hy+0.25:.2f}) '
  '(stroke (width 0.05) (type solid)) (fill no) (layer "F.CrtYd"))')

# 入力→出力の向きを矢印で示す（裏面シルクの矢印に相当）
w('  (fp_line (start -3.0 0) (end 3.0 0) (stroke (width 0.15) (type solid)) (layer "F.SilkS"))')
w('  (fp_line (start 3.0 0) (end 1.6 -0.9) (stroke (width 0.15) (type solid)) (layer "F.SilkS"))')
w('  (fp_line (start 3.0 0) (end 1.6 0.9) (stroke (width 0.15) (type solid)) (layer "F.SilkS"))')
w('  (fp_text user "IN" (at -5.2 0 0) (layer "F.SilkS") '
  '(effects (font (size 0.9 0.9) (thickness 0.13))))')
w('  (fp_text user "OUT" (at 5.6 0 0) (layer "F.SilkS") '
  '(effects (font (size 0.9 0.9) (thickness 0.13))))')

# 端子ラベル（実装前に見える位置＝パッドの内側）
for label, x, y in (('IN-', -PAD_X + 3.4, -(PAD_Y_OUT + PAD_Y_IN) / 2),
                    ('IN+', -PAD_X + 3.4,  (PAD_Y_OUT + PAD_Y_IN) / 2),
                    ('OUT-', PAD_X - 3.6, -(PAD_Y_OUT + PAD_Y_IN) / 2),
                    ('OUT+', PAD_X - 3.6,  (PAD_Y_OUT + PAD_Y_IN) / 2)):
    w(f'  (fp_text user "{label}" (at {x:.2f} {y:.2f} 0) (layer "F.SilkS") '
      '(effects (font (size 0.8 0.8) (thickness 0.12))))')

for i, (num, _lab, x, y) in enumerate(PADS):
    shape = 'rect' if (num == '1' and y == PAD_Y_OUT) else 'circle'
    w(f'  (pad "{num}" thru_hole {shape} (at {x:.2f} {y:.2f}) '
      f'(size {PAD} {PAD}) (drill {DRILL}) (layers "*.Cu" "*.Mask"))')

w(')')
path = sys.argv[1] if len(sys.argv) > 1 else 'MP1584EN_Module.kicad_mod'
open(path, 'w').write('\n'.join(out) + '\n')
print(f'wrote {path}')
