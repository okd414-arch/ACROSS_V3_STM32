# ACROSS V3 設計メモ (Zynq → STM32MP157 置き換え検討)

最終更新: 2026-11-12 / 状態: 部品構成を決定、PoC前

## 方針

- Zynq(FPGA + Linux)の across_app を、STM32MP157(A7 Linux + M4)に置き換える
- パルス送出(50MHz基準、uint32間隔、最大256MB×2)は **M4 + ハードウェアDMA連鎖**で行う
- A7(Linux)は既存C++アプリ(UDP:8000、ini、ログ、auto_launcher連携)を流用し、`/dev/uio` のレジスタ操作部分だけ置き換える
- パルステーブルは起動時にDDRへ全展開(走行中のSD/eMMCアクセスなし)

## パルス送出の構成(RM0436で確認済み)

```
DDR --MDMA(16KB/回, ハード連鎖)--> SRAM(ピンポン) --DMA1/2(TIMx_UP要求)--> TIM2 or TIM5(32bit) ARR --> PWM(CCR=pulseWidth固定)
```

- TIM2/TIM5は32bit。DMAMUX入力: TIM2_UP=22, TIM5_UP=59 (Table 111)
- DMA1/2の転送完了 → MDMAトリガ(str0〜15)がハード配線 (Table 98)
- TIM2/TIM5はETZPCでM4専有にできる(type 2)。MDMAは専有不可(チャンネル分割で共用)
- ARRはARPE=1(プリロード)。DMAが書いた値は次周期から有効 → 先頭1〜2個は事前設定
- 未確認: MDMAをM4側から使う方法(割り当て)、M4専有チャンネルの設計

## クロック

- GPS由来の **10MPPS**(3.3V CMOS)を HSE バイパスで入力、**1PPS** も別入力
- PLL3: HSE 10MHz → DIVM3=1 → VCO×60(600MHz) → ÷3 → 200MHz(mcu_ck)
  - APB1÷2 → timg1_ck=200MHz → TIM PSC=3 → **50MHz**
- GPS未接続時(開発用)は **RCモード**: HSI 64MHz → DIVM3=8 → VCO×75 → ÷3 → 200MHz
  - RCモードでも **通常と全く同じように動かす**(ユーザーはLEDで判断)
  - 精度はHSIで約±1%(GPS基準ではない)
- 起動時にHSERDYで10MPPS有無を判定(512クロック数えたら立つ。バイパスでの無入力挙動は実機で要確認)
- クロック基準の切替は**停止中のみ**。走行中の喪失は安全停止+警告。HSE CSSは使わない(有効だとシステムリセット)
- LED/外部信号で状態通知(GPSモード正常 / RCモード / 走行中喪失)
- 注意: ログは通常とRCで同形式になるため、区別フラグ(行末追記など)を検討
- 未確認: OSC_INの入力条件(VDDが3.3Vか。VIH=0.7×VDD)、起動ROMの10MHz対応、TF-A/U-BootのPLL設定(24MHz前提)の組み直し、PLL12(A7/DDR)をHSI基準にできるか

## 決定した部品(JLCPCB、2026-11-12時点の在庫・価格)

| 部品 | 型番 | JLCPCB番号 | 在庫 | 単価 |
|---|---|---|---|---|
| SoC | **STM32MP157AAA3 (LFBGA-448、650MHz、暗号なし)** ※2026-11-13にDAB1(354)から変更。354はGPIO 94本でLTDC RGB888・32bitエンコーダ・PMIC標準I2Cが成立しないため | C961771 | 17 | $15.56 |
| PMIC | STPMIC1APQR (EV1と同じA版) | C2156052 | 265 | $4.59 |
| DDR3L ×2 (32bit/1GB) | NT5CC256M16ER-EKI (4Gbit x16) | C2841153 | 558 | $27.99 |
| eMMC | KLM8G1GETF-B041 (8GB, eMMC5.1, FBGA-153 11.5x13) | C499918 | 1016 | $17.75 |

- 全て Extended 部品。発注時に在庫を再確認すること
- DDR3LはEV1(NT5CC256M16ER-EK ×2)と同系統なので、EV1のDDR配線・ST公式設定を流用する
- eMMC代案: KLM4G1FETE-B041 (4GB SLC, C500273, $21.45)。ただしフットプリントが10x11で別物
- 見送り: MP135/MP133(M4なし)、MP257(世代違い)

## 参考資料(このフォルダ)

- RM0436.pdf (リファレンスマニュアル)
- DS_stm32mp157c.pdf (データシート), DB_stm32mp157f-ev1.pdf
- STM32MP157F-EV1/ (回路図 MB1263=メイン基板、MB1230=DSI LCD、MB1379=カメラ)

## 2026-11-13 の決定事項

- SoCはSTM32MP157AAA3 (LFBGA448)。ピン割り当て案は `ACROSS_V3_ピン割り当て案.md`、IOは `ACROSS_V3_IO一覧.md`
- USB ×2: USB-1 = USBHポート1 (Linuxホスト: USBメモリ、Wi-Fi子機)、USB-2 = OTG HS (PCとの高速通信、必須ではない)。USBHのポート2とOTGはPHYを共有
- UART ×2: UART4 = デバッグ (UART-USB変換IC経由)、UART7 = GF-8801 (時刻調整、gpsd/chrony、NTPはLinuxで実装)
- 絶縁ドメインはA (サーボ側)、B (GPS側)、C (外部OC)、D (モニタTTL) の4つ。USB・デバッグUART・Ethernetは絶縁しない
- エンコーダ分解能 200〜4096、最大60Hz → パルス最大245.76kHz。高速デジタルアイソレータが必要
- 状態LED: 緑×2、赤×2

## 次の作業

0. 周辺部品の第1次選定は `ACROSS_V3_部品選定.md` (アイソレータ、RS-422、フォトカプラ、絶縁DC-DC、CH340C、USB ESD、LAN8720A、RJ45、microSD)。残り: LDO/電源、RGBパネル、USBコネクタ、GF-8801ソケット等

1. 周辺部品の検索: microSDソケット、10MPPS入力バッファ、タッチパネルとコントローラ(GT911/FT5x06)、LED、コネクタ
2. 評価ボード(STM32MP157F-EV1/DK2)でPoC: TIM+DMAの固定パルス → MDMA連鎖 → 長時間試験
3. 未確認項目: データシートでOSC_IN電圧、起動ROMの10MHz対応、MDMAのM4割り当て
4. FPGAのRTL/機能仕様の確認(位相合わせ arrangePhase、FM変調)
5. 実パルスファイル(pulse_acc.bin / pulse_mod.bin)のサイズ確認、最大パルス周波数の確認

## 2026-11-13 追記: クロック方針の変更 (ユーザー決定)

- **HSIは使わない。クロックはHSEのみ** (PLL1/2/3/4 すべて HSE 10MHz を入力とする)。以前の「GPSが無いときはHSI (RCモード)」は**廃止**。
- **10MHz発振器を基板上に実装**し、**ジャンパーで HSE の入力源を選ぶ**: 基板上の10MHz発振器 / GPSの10MPPS。HSEはデジタルバイパス (OSC_IN)。
- 理由: PLL1/2 (A7、DDR 533MHz) をRC (HSI) 基準にすると、DDRクロックのジッタ・温度ドリフトの余裕が小さい (未検証)。GPS無しでも起動できるようにするため。
- 影響: HSERDYがGPS無しでどう振る舞うか (C2) は、基板上の発振器を選べば問題にならない。GPS側を選んだまま10MPPSが無いと起動しない (運用の注意)。
- CubeMXのクロック値 (HSE 10MHz、全DIVM=/1。**.iocに保存済みを確認、11:30**): PLL1 X65 (650MHz)、PLL2 X53 + **FRACV2=2457** (R=532.9993MHz DDR、P=266.4996MHz AXI。2458だとAXIが266.5MHzを超える)、PLL3 X60 (200MHz)、PLL4 X48 (R4 /20 = 24MHz USBPHYC、P4 /5 = 96MHz ETH (上限125MHz)、Q4 /20 = **24MHz LTDC** (パネルの画素クロック 23〜27MHz))。
- SDMMC1の黄色い警告 (PF2=OC3、PE4=SD_CD、I2C1との競合) は、他のモード (電圧変換器つき、MMC 8bit) を選んだ場合の警告で、現在の `SD 4 bits Wide bus` には影響しない。無視してよい。
- 回路図で決めること: 発振器の部品 (3.3V CMOS出力、低ジッタ、周波数安定度)、ジャンパー (3ピン) と、HSE入力の直列抵抗、10MPPS側の絶縁アイソレータ経路との接続。

## 2026-11-13 追記: 電源入力を24Vに変更 (ユーザー決定)

- **電源入力は DC24V (ACアダプタ 24V/2A)**。5V入力から変更。**昇圧は使わない** (バックライトの昇圧 TPS61165 を廃止)。電流が足りない場合は、アダプタを変更してよい (ユーザー)。
- 基板上で24Vから 5V (降圧、約2〜3A) を作り、PMIC (STPMIC1、入力5.5V以下) 以降は従来どおり。
- バックライト (LED 約18.3V、60mA) は、24Vから**定電流の降圧またはリニア**で駆動 (PWM調光は維持)。
- 絶縁DC-DC (ドメインA〜D) は、24V入力品に変更する。ドメインAは 24V→9V (B2409S系) + 降圧2個 (5.0V、3.3V) の案。
- 24Vは基板上のデバッグ (フォトカプラの試験) にも使える (テストポイント)。
- **サーボ側の24Vとは共有しない** (ロジックのGNDとサーボ側のGNDを分けて、絶縁ドメインを保つ)。Z相OCの24Vプルアップも別電源 (ユーザーが用意)。
- 入力保護の部品は**見直し** (5V用の部品は流用できない): eFuse TPS259541 (最大18V) は不可、TVSはSMBJ28A前後、逆接続PMOSは耐圧40V以上、入力コンデンサは50V。部品は回路図の前に選ぶ。

## 追記 (2026-11-27): DDR3L を 1個に変更

- 上の表の「DDR3L ×2 (32bit/1GB) NT5CC256M16ER-EKI」は、このフォルダ (ACROSS_V3_STM32) では **MT41K512M16VRP-107 IT:P ×1 (16bit/1GB、C2831669)** に変更した。EV1 の DDR 設定 (32bit) はそのまま使えないので、CubeMX の DDR ツールで 16bit・8Gbit の設定を作り直す。
