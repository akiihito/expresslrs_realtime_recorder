# ExpressLRS Realtime Recorder

USBゲームパッドをExpressLRS送信機として使用するアダプター。
Raspberry Pi PicoでゲームパッドのUSB HID入力を取得し、CRSFプロトコルに変換してExpressLRS送信モジュールに送信する。

## システム構成

```
USBゲームパッド
    ↓ USB Host (HID, micro-USB)
Raspberry Pi Pico
    ├→ GP0 UART0 TX (CRSF 921.6kbps 反転 半二重) → BetaFPV Nano TX Module V2 → ExpressLRS → BetaFPV Pavo Pico II
    └→ GP4/5 UART1 (921600bps) → USB-シリアル変換 → PC (デバッグ/値確認・ログ記録)
```

操作を Pico 内蔵フラッシュに記録し、再生できる（GP2ボタンでモード切替、ゲームパッドのLBで記録start/stop）。
詳細は「動作モード」参照。入力デバイスの癖に合わせた**入力プロファイル**（GP6で切替）も持つ。

> 詳細な仕様・設計判断の経緯は [`CLAUDE.md`](CLAUDE.md)、操作一覧の印刷用シートは
> [`docs/controls.html`](docs/controls.html) にある。

## ハードウェア

| コンポーネント | 説明 |
|---------------|------|
| Raspberry Pi Pico | メインマイコン |
| Logitech F310 | 入力デバイス（**裏スイッチをDモードに**）。汎用HIDパッドも可 |
| BetaFPV LiteRadio 3 | 入力デバイス（プロポ。GP6でLITERADIOプロファイルに切替） |
| BetaFPV Nano TX Module V2 | ExpressLRS送信モジュール |
| BetaFPV Pavo Pico II | 機体（F4 2-3S 20A AIO FC, Serial ELRS 2.4G受信機内蔵） |

## ピン配置

| Pico Pin | 接続先 | 説明 |
|----------|--------|------|
| USB (micro-USB) | ゲームパッド | USB Host |
| GP0 (UART0 TX) | Nano TX | CRSF出力 (921.6kbps 反転 半二重) |
| GP1 (UART0 RX) | Nano TX | 半二重テレメトリ受信 |
| GP4 (UART1 TX) | USB-シリアル変換 → PC | デバッグ出力 (921600bps) |
| GP5 (UART1 RX) | USB-シリアル変換 → PC | デバッグ入力（コマンド） |
| GP2 | タクトSW → GND | モード切替ボタン（内部プルアップ） |
| GP6 | タクトSW → GND | 入力プロファイル切替ボタン |
| GP10 / GP11 / GP12 | LED(100Ω) → GND | モードLED 赤=記録 / 緑=再生 / 青=単純 |
| GP13 / GP14 | LED(100Ω) → GND | 入力プロファイルLED 汎用 / LiteRadio |
| VBUS (pin40) | 降圧モジュール出力 5V | Pico＋ゲームパッドの給電（**VSYSではない**） |
| GND (pin3) | 共通GND | LiPo−を起点にスター結線 |
| 内蔵LED | - | 状態表示（接続:点灯 / 未接続:点滅 / 再生モード:速点滅） |

LEDの直列抵抗は**実機で100Ω**（緑/青はVf≈3Vあり330Ωでは暗い）。GP3はArmスイッチ用に予約。
**GP15(pin20)は本個体にヘッダ未実装のため使用不可**。
Nano TX Module は 5V では動かないので **LiPo(7〜13V)をVBATへ直結**する。
電源・配線の詳細とスター結線は [`CLAUDE.md`](CLAUDE.md) 参照。

## ビルド

### 必要環境

- [Pico SDK](https://github.com/raspberrypi/pico-sdk)（tinyusb サブモジュール込み）
- CMake 3.13以上
- **ARM GNU Toolchain の公式 tar.xz 版**。⚠️ Homebrew formula の `arm-none-eabi-gcc` は
  newlib(`nosys.specs`) を持たず**リンクに失敗する**ので使わない。

### SDKへのパッチ適用（初回・SDK入れ直し時に1回）

```bash
export PICO_SDK_PATH=/path/to/pico-sdk
./scripts/apply_sdk_patch.sh
```

⚠️ **これを忘れると Logitech F310 が HID レポートを1本も返さない**（列挙とHIDマウントまでは
成功するので原因が分かりにくい）。F310が最初の転送を DATA1 PID で始めるのに対し、RP2040 は
データシーケンスエラーから回復できないチップバグ（TinyUSB issue #2776）があるため。
SDK は git 管理外なので、入れ直すと失われる。冪等なので何度実行してもよい。

### Picoファームウェアのビルド

```bash
export PICO_SDK_PATH=/path/to/pico-sdk
export PICO_TOOLCHAIN_PATH=/path/to/gcc-arm-none-eabi
mkdir build && cd build
cmake ..
make -j$(sysctl -n hw.ncpu)   # Linux なら $(nproc)
```

⚠️ `build/` で cmake を再実行するときは `PICO_SDK_PATH` と `PICO_TOOLCHAIN_PATH` を
**両方渡すこと**（キャッシュを消すと環境が失われる）。

### テストのビルド・実行

```bash
mkdir build_test && cd build_test
cmake -DBUILD_TESTS=ON ..
make -j$(sysctl -n hw.ncpu)
ctest --output-on-failure
```

ドキュメントがコードから古くなっていないかの機械チェック（UARTコマンド・GPIO番号・
調整パラメータの網羅）も合わせて走らせる。詳細と限界は [`CLAUDE.md`](CLAUDE.md) の「開発ルール」。

```bash
python3 scripts/check_docs.py
```

ホスト側でリンクが `tapi error: malformed file` / `unknown architecture` で失敗する場合は、
CommandLineTools の SDK が Xcode の `ld` より新しいのが原因。
`-DCMAKE_OSX_SYSROOT=$(xcode-select -p)/Platforms/MacOSX.platform/Developer/SDKs/MacOSX.sdk`
を付けて configure すれば通る（恒久対応はXcodeの更新）。

## 書き込み

1. PicoのBOOTSELボタンを押しながらUSB接続
2. `RPI-RP2`としてマウントされることを確認
3. 書き込みスクリプトを実行:

```bash
./scripts/flash.sh
```

または手動で:

```bash
cp build/expresslrs_realtime_recorder.uf2 /Volumes/RPI-RP2/
```

## シリアルモニター

micro-USB はゲームパッド専有なので、PCログは **UART1(GP4/5) + USB-シリアル変換**で取る。

```bash
./scripts/monitor.sh            # デフォルト 921600bps
./scripts/monitor.sh 115200     # ⚠️ 手元のFTDI変換器は分周器バグで8倍ずれるのでこちら
```

終了: `Ctrl+A`, `K`, `y`（`Ctrl+A`→`D` はデタッチでポートを掴んだままになる）

| キー | 動作 |
|---|---|
| `?` | ヘルプ。1行目に**現在のモード・入力プロファイル・フラッシュのログ数** |
| `d` | スナップショット（生HID → state → CRSF → フレーム → CRC を全段ダンプ） |
| `s` | 連続ストリーム ON/OFF（25Hz CSV、`live_view.py` 用）※トグル |
| `r` | 記録 start/stop（RECORD時のみ。ゲームパッドのLBと同じ） |
| `p` | 再生 start/stop（PLAYBACK時のみ） |
| `i` | 入力プロファイル切替（GP6ボタンと同じ） |
| `t` | スロットル/舵の現在設定と各スティック位置での出力を表示 |
| `[` `]` | ホバリング推力 −/+ 1% |
| `,` `.` | スロットルのエクスポ 弱/強 |
| `5` `6` | 上昇方向の可動幅 −/+ 5%（上に倒した時の加速が強すぎる時は `5`） |
| `7` `8` | 舵角スケール −/+ 5% |
| `9` `0` | 舵のエクスポ 弱/強 5% |

チューニング値は**電源を切ると既定値に戻る**。良い値が出たらソースの `*_DEFAULT_PCT` に焼き直す。

1秒ごとのハートビートの先頭にも現在の状態が出る（`SIMPLE` / `REC-idle` / `REC-ON` /
`REC-FULL` / `PLAY-idle` / `PLAY-ON`）。LEDと同じ情報だが、ログを見返す時に必要になる。

```
[REC-ON   ][CONN] CH1-4:  992  992  499  992 | BTN: 0x0010
```

リアルタイムのバーゲージ表示:

```bash
python3 scripts/live_view.py    # 要 pip install pyserial
```

## 動作モード（単純 / 記録 / 再生）

GP2ボタンで3モードを循環し、GP10-12のLEDで表示する。起動時は安全な**単純(SIMPLE)**。

| モード | LED | 動作 |
|--------|-----|------|
| SIMPLE (単純) | GP12 青 点灯 | ゲームパッド → CRSF パススルー |
| RECORD (記録) | GP10 赤 | パススルー＋**LBで指定した区間**を記録（50Hz, RAM→フラッシュ） |
| PLAYBACK (再生) | GP11 緑 | フラッシュのログを CRSF として再送出 |

- **GP2 短押し**: モード循環 / **GP2 長押し(0.6秒)**: PLAYBACK中に再生 start/stop
- **記録はRECORDに入っただけでは始まらない**。ゲームパッドの **LB**（またはUART `r`）で
  start/stop する。開始のたびにバッファはクリア＝「最後に開始した所からの記録」。
  - 赤LED: **ゆっくり点滅**=待機 / **点灯**=記録中 / **速い点滅**=バッファ満杯(120秒)
- フラッシュへの書出しは**RECORDを抜けた時**に一括（飛行中に書くとXIPが止まり500Hz送信が
  破綻するため）。LBを一度も押さずに通過した時は書かず、保存済みログを残す。
- 再生は PLAYBACK 入場では自動開始しない。長押し or `p` で開始、末尾で自動停止。
  - 緑LED: **点灯**=待機 / **点滅**=再生中（ボタンを受け付けた合図）
- 切断時はスロットル最小＋Arm解除のフェイルセーフを送出（Armトグルのラッチもリセット）。

### 入力プロファイル（GP6で切替、LEDはGP13/GP14）

| プロファイル | スロットル(CH3)の扱い |
|---|---|
| GENERIC (汎用パッド) | **位置型・中央=ホバリング推力**。下端=最小/上端=ホバリング+15%。手を離すとホバリングに戻る |
| LITERADIO (LiteRadio 3) | **絶対値**。ジンバル位置をそのままスロットルに |

GENERIC ではスティックのストロークが実機プロポより遥かに短いため、ロール/ピッチ/ヨーに
**エクスポと舵角スケール**を掛けて鋭さを落としている。D-pad上下でホバリング推力を±1%トリムできる
（電圧降下で沈み始めた時用）。⚠️ **LiteRadio 3 を使う時は必ずLITERADIOに切り替える**
（GENERICのままだと軸がバラバラになる）。

## 配線・プロトタイプ

- [`hardware/`](hardware/) — KiCad 9 プロジェクト（回路図ERC・基板DRCクリーン、105×85mm 2層）。
  KiCad無しで見るなら `hardware/recorder.pdf`（回路図）/ `hardware/pcb-fab.pdf`（基板1:1）。
  ⚠️ **未発注・未検証**。部品表と発注前チェックは [`hardware/README.md`](hardware/README.md)。
- [`docs/perfboard.html`](docs/perfboard.html) — ユニバーサル基板版の配置＆配線リスト（PCB発注前に手組みする用）。
  ⚠️ `docs/perfboard-layout.html` は**旧版**（保護部品が未反映）なので使わない。
- [`docs/breadboard-bringup.md`](docs/breadboard-bringup.md) — 段階的ブリングアップ手順（Stage A〜F）と実施記録
- [`docs/hardware-validation.md`](docs/hardware-validation.md) — 単票チェックリスト（上の各Stageから参照）
- [`docs/controls.html`](docs/controls.html) — 操作一覧（印刷用）

## プロジェクト構造

```
expresslrs_realtime_recorder/
├── CMakeLists.txt
├── README.md
├── CLAUDE.md                    # プロジェクト仕様書
├── include/
│   ├── crsf.h                   # CRSFプロトコル定義
│   ├── usb_gamepad.h            # ゲームパッドAPI
│   ├── hid_parser.h             # HIDレポートディスクリプタ解析
│   ├── recorder.h               # 記録/再生API
│   └── tusb_config.h            # TinyUSB設定
├── src/
│   ├── main.c                   # メインアプリ（モード/ボタン/LED/マッピング）
│   ├── crsf.c                   # CRSF実装
│   ├── usb_gamepad.c            # USB Host実装
│   ├── hid_parser.c             # ディスクリプタから軸配置を求める
│   └── recorder.c               # 記録/再生（RAM蓄積→フラッシュ）
├── tests/                       # ホストPCで走るユニットテスト(gtest)
│   ├── test_crsf.cpp
│   ├── test_usb_gamepad.cpp
│   ├── test_hid_parser.cpp
│   └── test_recorder.cpp        # 記録ロジック（間引き/ラッチ/再開）
├── scripts/
│   ├── flash.sh                 # 書き込み
│   ├── monitor.sh               # シリアルモニター
│   ├── apply_sdk_patch.sh       # SDKへのF310ワークアラウンド適用
│   ├── check_docs.py            # コードとドキュメントの食い違い検出
│   └── live_view.py             # リアルタイム値ビューア
├── patches/                     # SDKへ当てるパッチ本体
├── docs/                        # ブリングアップ手順・配線図・操作一覧
├── hardware/                    # KiCadプロジェクト（回路図・基板）
├── references/                  # 参照回路図などの資料
└── .claude/
    └── skills/
        ├── build.md             # /build スキル
        └── test.md              # /test スキル
```

## CRSFプロトコル

| 項目 | 値 |
|------|-----|
| ボーレート | 921,600 bps（Nano TX V2 モジュール用。レシーバ直結は420,000） |
| 信号 | 反転UART（Nano TX V2 の S.Port） |
| 通信方式 | 半二重（送信後テレメトリをドレイン） |
| フレームタイプ | 0x16 (RC Channels Packed) |
| チャンネル数 | 16 |
| チャンネル解像度 | 11bit (0-2047) |
| チャンネル値範囲 | 172 (min) - 992 (mid) - 1811 (max) |
| CRC | CRC8-DVB-S2 (多項式 0xD5) |

### パケット構造

```
[SYNC: 0xC8] [LEN: 24] [TYPE: 0x16] [PAYLOAD: 22bytes] [CRC: 1byte]
```

## 対応コントローラー

| デバイス | VID:PID | 状態 |
|---|---|---|
| Logitech F310 | `046D:C216` | **実機確認済み**。裏スイッチを **D** に（Xモードは `046D:C21D` でHIDではない）。SDKパッチ必須 |
| BetaFPV LiteRadio 3 | `0483:572B` | **実機確認済み**。16bit×8ch、AETR順。LITERADIOプロファイルで使う |
| Sony DualShock 4 | `054C:09CC` / `054C:05C4` | 専用パーサーあり（実機未検証） |
| 汎用HIDゲームパッド | — | レポートディスクリプタを解析して軸配置を自動判定 |

## チャンネルマッピング (Mode 2, GENERICプロファイル)

| CRSFチャンネル | ゲームパッド入力 | 備考 |
|---------------|-----------------|------|
| CH1 (Roll) | 右スティック X | エクスポ＋舵角スケール |
| CH2 (Pitch) | 右スティック Y | 反転、エクスポ＋舵角スケール |
| CH3 (Throttle) | 左スティック Y | 反転。**位置型・中央=ホバリング推力**、不感帯＋エクスポ。上側は可動幅を制限（既定15%） |
| CH4 (Yaw) | 左スティック X | エクスポ＋舵角スケール |
| CH5 / CH6 | L2 / R2 トリガー | F310のL2/R2はデジタルなので常に中央値 |
| CH7 (Arm) | Aボタン (Cross) | **押下エッジでトグル**（押しボタンでは保持できないため） |
| CH8 | Bボタン (Circle) | ON/OFF |
| CH9 | Xボタン (Square) | ON/OFF |
| CH10 | Yボタン (Triangle) | ON/OFF |
| CH11 | LBボタン (L1) | ON/OFF。**RECORD中は記録のstart/stopトリガー**（機体側は未使用） |
| CH12 | RBボタン (R1) | ON/OFF |
| CH13-16 | 未使用 | 中央値固定 |
| — | D-pad 上/下 | ホバリング推力を±1%トリム（GENERIC時） |

LITERADIOプロファイルでは送信機がAETRのチャンネル順で軸を並べるため、スティック解釈を挟まず
CH1〜 をそのまま素通しする（スロットルも絶対値）。

> ⚠️ **Armはスロットルスティックを下に押さえたまま行う**。中央がホバリング推力（既定20%≒1200us）
> なので、中央のままだとBetaflightがスロットル高としてArmを拒否する。押さえたままArm →
> ゆっくり離すとホバリングまで上がって離陸、という実機プロポと同じ手順になる。

## 参考資料

- [CRSF Protocol Specification](https://github.com/crsf-wg/crsf/wiki)
- [ExpressLRS CRSF Implementation](https://github.com/ExpressLRS/ExpressLRS/blob/master/src/lib/CrsfProtocol/crsf_protocol.h)
- [TinyUSB Host HID Example](https://github.com/hathach/tinyusb/tree/master/examples/host/hid_controller)
- [Pico SDK Documentation](https://raspberrypi.github.io/pico-sdk-doxygen/)

## ライセンス

MIT License
