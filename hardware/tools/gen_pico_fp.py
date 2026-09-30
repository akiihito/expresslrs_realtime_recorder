#!/usr/bin/env python3
"""Raspberry Pi Pico を2×20メスヘッダに載せる前提のフットプリントを生成する。

KiCad標準ライブラリにPicoのフットプリントが無いため自作。
寸法: 基板 51.0×21.0mm / パッド40個 2.54mmピッチ / 列間 17.78mm(0.7in)。
40パッドは基板長手方向に中央揃え（両端の余白 (51-48.26)/2 = 1.37mm）、
列は幅方向中央揃え（両端の余白 (21-17.78)/2 = 1.61mm）。
"""
import sys

PITCH = 2.54
ROW_SPACING = 17.78
N_PER_SIDE = 20
SPAN = (N_PER_SIDE - 1) * PITCH          # 48.26
BOARD_L, BOARD_W = 51.0, 21.0
DRILL, PAD = 1.0, 1.8

out = []
w = out.append
w('(footprint "RPi_Pico_Headers"')
w('  (version 20240108)')
w('  (generator "gen_pico_fp.py")')
w('  (layer "F.Cu")')
w('  (descr "Raspberry Pi Pico on 2x20 female headers. 51.0x21.0mm, '
  '2.54mm pitch, 17.78mm row spacing. Pin 1 at top-left with USB up.")')
w('  (tags "raspberry pi pico rp2040 module header")')
w('  (attr through_hole)')

# --- テキスト ---
w(f'  (property "Reference" "REF**" (at 0 {-BOARD_L/2 - 2:.2f} 0) (layer "F.SilkS")')
w('    (effects (font (size 1 1) (thickness 0.15))))')
w(f'  (property "Value" "RPi_Pico" (at 0 {BOARD_L/2 + 2:.2f} 0) (layer "F.Fab")')
w('    (effects (font (size 1 1) (thickness 0.15))))')

# --- 外形（シルク＋Fab）。USB側(pin1側)の角を落として向きを示す ---
hx, hy = BOARD_W / 2, BOARD_L / 2
chamf = 1.0   # 2.0だとpin1のハンダマスクに掛かる
for layer, width in (('F.SilkS', 0.12), ('F.Fab', 0.1)):
    pts = [(-hx + chamf, -hy), (hx, -hy), (hx, hy), (-hx, hy), (-hx, -hy + chamf)]
    for i in range(len(pts) - 1):
        a, b = pts[i], pts[i + 1]
        w(f'  (fp_line (start {a[0]:.2f} {a[1]:.2f}) (end {b[0]:.2f} {b[1]:.2f}) '
          f'(stroke (width {width}) (type solid)) (layer "{layer}"))')
    w(f'  (fp_line (start {pts[-1][0]:.2f} {pts[-1][1]:.2f}) '
      f'(end {pts[0][0]:.2f} {pts[0][1]:.2f}) '
      f'(stroke (width {width}) (type solid)) (layer "{layer}"))')

# USB コネクタの位置をシルクで示す（基板端からはみ出す側）
w(f'  (fp_rect (start -3.5 {-hy:.2f}) (end 3.5 {-hy + 2:.2f}) '
  '(stroke (width 0.12) (type solid)) (fill no) (layer "F.SilkS"))')
w(f'  (fp_text user "USB" (at 0 {-hy + 3.2:.2f} 0) (layer "F.SilkS") '
  '(effects (font (size 0.8 0.8) (thickness 0.12))))')

# --- コートヤード ---
cx, cy = hx + 0.25, hy + 0.25
w(f'  (fp_rect (start {-cx:.2f} {-cy:.2f}) (end {cx:.2f} {cy:.2f}) '
  '(stroke (width 0.05) (type solid)) (fill no) (layer "F.CrtYd"))')

# --- パッド: 1-20 が左列を上から下、21-40 が右列を下から上 ---
y0 = -SPAN / 2
for i in range(N_PER_SIDE):
    left_num = i + 1
    right_num = 40 - i
    y = y0 + i * PITCH
    for num, x in ((left_num, -ROW_SPACING / 2), (right_num, ROW_SPACING / 2)):
        shape = 'rect' if num == 1 else 'circle'
        w(f'  (pad "{num}" thru_hole {shape} (at {x:.2f} {y:.2f}) '
          f'(size {PAD} {PAD}) (drill {DRILL}) (layers "*.Cu" "*.Mask"))')

w(')')

path = sys.argv[1] if len(sys.argv) > 1 else 'RPi_Pico_Headers.kicad_mod'
open(path, 'w').write('\n'.join(out) + '\n')
print(f'wrote {path}')
