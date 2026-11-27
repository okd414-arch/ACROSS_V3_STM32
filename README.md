# ACROSS V3 (STM32MP157 版、DDR3L 1個構成)

STM32MP157AAA3 (LFBGA448) 1枚の基板 (160×100 mm、8 層、JLCPCB 発注) の設計データです。Zynq で動いていた `across_app` を置き換えます。サーボアンプへ、uint32 のパルス間隔 (50 MHz ティック) をモーターパルス列として正確に再生するのが中核機能です。

**この版は DDR3L を 1個 (MT41K512M16VRP-107 IT:P、8Gbit ×16、1GB) にした版です** (2026-11-27)。NT5CC256M16 ×2 (32bit) の版とは別です。現在の状態は、回路図が 1個構成に更新済み、**基板はまだ 2個構成の配置・配線のまま**です。

## Zynq 版 (FPGA) の機能と STM32MP157 での置き換え

時間の正確さが要る所 (パルス出力・エンコーダ・1PPS の保持) は、**ハードウェアのタイマと DMA** で置き換えます。ソフトの判断が要る所 (時刻管理、パルス表の作成、通信) は、**Linux の across_app** をほぼそのまま使います。FPGA のロジックが担っていた分は、**Cortex-M4 のファームウェア**で補います。

| # | 機能 | Zynq 版 (FPGA) | STM32MP157 版 | 状態 |
|---|---|---|---|---|
| 1 | パルス列の送出 (uint32 間隔、50 MHz 基準、最大 256 MB ×2) | FPGA がメモリのテーブルを DMA で読んでパルスにする | DDR → MDMA → SRAM (ピンポン) → DMA1/2 → **TIM2 (32bit) の ARR を更新する PWM** (CCR は固定) | 方式決定。評価ボードでの検証は未 |
| 2 | パルステーブルの作成 (加速 ACC、FM 変調) | PS 側の across_app が展開 (`SET ACC PULSE`、`SET FM PULSE`) | **A7 の across_app** が起動時に DDR (1GB) へ全展開。走行中は SD/eMMC に触れない | 流用 |
| 3 | 基準クロック | GPS の 10MPPS を FPGA に入力 | **HSE (10 MHz、デジタルバイパス) → PLL3 200 MHz → TIM2 (PSC = 3) = 50 MHz**。基板上の 10 MHz 発振器と GPS の 10MPPS をジャンパーで選ぶ | 方式決定 |
| 4 | 1PPS 同期のカウンタ (エンコーダ値を 1PPS に同期して記録、リセットされない 1PPS カウンタ) | FPGA のレジスタ (READ_REG[19]・[29]) | **TIM5 の入力キャプチャ (PH12、CH3)** で、1PPS の立ち上がり時のエンコーダ値をハードウェアで保持。リセットされない 1PPS カウンタは M4 のソフトで数える | 要設計 |
| 5 | エンコーダの積算 (A/B、分解能 200〜4096、最大 60 Hz) | FPGA のカウンタ | **TIM5 のエンコーダモード (32bit、PH10/PH11)**。Z 相は入力キャプチャ (PI0、CH4) | ピン決定済み |
| 6 | 位相合わせ (`arrangePhase`) | FPGA が、モーターの位相を合わせて、トリガ待ちの状態にする | **M4 のファームウェアで再実装** (エンコーダ値・Z 相を見て、パルス送出の開始位置を調整) | **要確認** (FPGA の仕様が未確認) |
| 7 | FM 変調 (加速のあとの周波数変調) | FPGA のロジック | パルステーブルに展開する (#1・#2 と同じ流れ)。M4 で ARR を変調する案もある | **要確認** |
| 8 | 加速開始のトリガ、時刻管理 (`startTime`、`reverseCycleTime`、CW/CCW を交互に) | PS の across_app が時刻を見て、FPGA へ開始を指示 | **A7 の across_app** が時刻を管理し、**M4 へ開始を通知**する (IPCC / RPMsg、または共有メモリ) | 要設計 |
| 9 | 方向出力 (CW/CCW) | FPGA の出力 (`GPIO_ACTIVATE_ON_CW/CCW`) | M4 の GPIO。RS-422、TTL 5V (モニタ用)、オープンコレクタ (M_DIR_OC) の 3系統を常に出力 | 回路図済み |
| 10 | モーターパルスの出力 | FPGA の出力 | **TIM2_CH1 (PG8)** → 高速デジタルアイソレータ → RS-422 ドライバ。TTL 5V のモニタ出力も別系統 | 回路図済み |
| 11 | FPGA コアのリセット (`GPIO_RESET_ACROSS_CORE`) | AXI GPIO | M4 ファームウェアの再起動 (remoteproc)、または M4 側のソフトのリセット | 要設計 |
| 12 | レジスタの読み書き (`/dev/uio`、`REGISTER?`、`monitor`、`verbose` ログ) | `/dev/uio` で FPGA のレジスタを操作 | **A7 ↔ M4 の共有メモリ (RPMsg)** に置き換える。across_app は、この部分だけ書き換える | 要設計 |
| 13 | GPS の時刻 (NTP、時刻合わせ) | PS の Linux (gpsd/chrony) と推測 | **A7 の Linux** のまま。UART7 (GF-8801) + 1PPS (PG3、pps-gpio) | ピン決定済み。Zynq 版の構成は要確認 |
| 14 | 運転の制御 (UDP 8000、auto_launcher.py、ログ) | PS の Linux | **A7 の Linux** のまま (Ethernet は LAN8720A、RMII) | 流用 |
| 15 | 状態の表示 | MicroZed の LED | 状態 LED を 4個 (緑 ×2、赤 ×2) | 回路図済み |
| 16 | 外部との絶縁、保護 | ドーターカード | 絶縁ドメイン (A: サーボ側、C: 外部 OC、D: モニタ TTL)。GPS は小基板 (GF-8801) をヘッダ (J701) で接続。24 V 入力 | 回路図済み |

「要確認」は、FPGA の RTL (位相合わせ・FM 変調) をまだ確認していないものです。詳しくは `ACROSS_V3_設計メモ.md` の「次の作業」を参照してください。

## まず読むもの
1. `ACROSS_V3_引き継ぎ資料.md` — 現在の状態、決定事項、残作業 (先頭の「★★」の節が最新)
2. `ACROSS_V3_回路図作成メモ.md` — 回路図の規約、設計の決定、フットプリントの割り当て
3. `CLAUDE.md` — 作業の指示 (回答は日本語、など)

## フォルダ
| 場所 | 中身 |
|---|---|
| `ACROSS_V3_*.md`、`*.csv` | 設計メモ、部品選定、ピン割り当て、電源見積もり、配線計画など |
| `kicad/` | KiCad 10 のプロジェクト (`ACROSS_V3.kicad_pro`)。回路図 7 シート (`01_…`〜`07_…`)、基板 `ACROSS_V3.kicad_pcb`、自作ライブラリ `ACROSS_V3.pretty`・`ACROSS_V3.kicad_sym`、設計ルール `ACROSS_V3.kicad_dru` |
| `kicad/tools/` | Python のスクリプト (配置・配線・長さ合わせ・シルクなど) |
| `STM32MP157F-EV1/` | ST の評価ボード (EV1) の回路図と基板データ。DDR などの参考用 |
| `データシート/` | データシートの一覧のみ (PDF は入れていません) |

## 開くとき
- **KiCad 10** で `kicad/ACROSS_V3.kicad_pro` を開きます。
- 個人ライブラリ (`0my_*` の小さい記号、`01_MY` のフットプリント) は作者の PC の `C:\OneDrive_link\KiCAD\` にあります。持っていない場合は、記号や足跡が見つからない警告が出ます (一部は `kicad/ACROSS_V3.kicad_sym`・`ACROSS_V3.pretty` に入っています)。
- `kicad/tools` の Python スクリプトには、作者の PC の絶対パス (`C:\MyWorks\ACROSS_V3_STM32` など) が書いてあります。別の場所で動かすときは書き換えてください。
- 回路図は GUI で編集済みです。スクリプトで作り直さないでください。

## 注意
- 設計のデータは作業中です。発注に使う前に、`ACROSS_V3_引き継ぎ資料.md` の「残作業」を確認してください。
