# ACROSS V3 ピン割り当て案 (ドラフト)

作成: 2026-11-13 / 元資料: DS_stm32mp157c.pdf (ピン表 Table 7)、RM0436.pdf
注意: ピン表はPDFからテキスト抽出して機械的に読み取った。**最終確定はSTM32CubeMXでの競合チェックと、データシート原本での照合が必要**。

## 決定 (2026-11-13): SoCは STM32MP157AAA3 (LFBGA448) に変更

以下の「LFBGA354はピンが足りない」は、変更の理由。以降の割り当ては448前提。USB・UARTの追加要件は次節。

## 追加要件: USB と UART (2026-11-13)

### USB (STM32MP157内蔵のHS PHYを2系統使う)

| ポート | 用途 | 使うUSBコントローラ | ピン (LFBGA448) |
|---|---|---|---|
| USB-1 | Linuxのホスト。USBメモリ、Wi-Fi子機 | USBH (EHCI/OHCI、HS対応) | USB_DP1 = AA15 / USB_DM1 = AB15 |
| USB-2 | PCとのハイスピード通信 (必須ではない) | USB OTG HS (デバイス動作。Linuxのgadgetで CDC-ACM / ECM など) | USB_DP2 = AB14 / USB_DM2 = AA14、OTG_VBUS = V15、ID = PA10 (OTG_ID) |

- 共通: USB_RREF = AA17 (外付け精密抵抗 → GND)。VSS_USBHS = Y13, Y14, AA13, AA16, Y15。
- **USB-2はUSBHのポート2とPHYを共有する**。OTGを使う間はUSBHのポート2は使えない。つまり「2ポート」はUSB-1 (USBH port1) + USB-2 (OTG) の構成になる。
- 電源: VDD3V3_USBHS (AB13) = 3.07〜3.6V、VDDA1V8_REG (AB12)、VDDA1V1_REG (AB17)。OTGデバイス動作では **VDD3V3_USBFS** (OTG_VBUS/IDを給電) にも3.3Vが必要。**VDDA1V8_REGが立つ前にVDD3V3_USBHSを入れると破損**するので、PMICの起動順序で保証する (STPMIC1の標準構成に従う)。
- VBUS供給: STPMIC1A はUSB用の電源スイッチ (ホスト用) とOTG用5Vブーストを持つ。USB-1のVBUSは、この電源スイッチで給電し過電流保護を兼ねる (STPMIC1とEV1の回路で要確認)。
- USB-2をPCにつなぐ場合、PCのVBUSで給電されるのを避ける (本基板は5V単一電源。OTG_VBUS検出は分圧/ダイオード経由)。
- ESD保護ICとコモンモードチョークは必須ではないが、ESD保護 (USB2.0用の低容量品) をDP/DMに入れる。
- 絶縁: USBはデバッグ/保守用なので絶縁しない。

### UART (2系統)

| UART | 用途 | ピン (LFBGA448) | 備考 |
|---|---|---|---|
| UART4 | デバッグ。**UART-USB変換IC経由**で、PCにUSBシリアルとして見せる | UART4_TX = PG11 (U11) / UART4_RX = PB2 (V13) | 絶縁なし。変換IC (CP2102N、CH340系、FT232系などをJLCPCBで選定) と専用のUSBコネクタ (Type-C か micro-B) が別に要る。USB-1/USB-2とは別物 |
| UART7 | GF-8801 (GPS)。時刻調整 (gpsd + chrony)。NTPサーバ機能もLinuxで実装 | UART7_RX = PE7 (W10) / UART7_TX = PE8 (Y12) | ドメインBのデジタルアイソレータ経由。既定38400bps。GPS時刻はNMEA + 1PPS |

- デバッグUARTをU-Boot/Linuxのコンソールにする。TF-A/U-Bootの初期出力もUART4に出る (STの標準と同じ)。
- 注意: 上記のPG11/PB2などは、EV1の配線 (UART4 = ST-LINK VCP) に合わせた。最終はCubeMXで確認する。

## (変更前の検討) LFBGA354 (STM32MP157DAB1) はピンが足りない

| パッケージ | GPIOの数 | 備考 |
|---|---|---|
| LFBGA354 (DAB1、決定済みの型番) | **94** | PH、PI、PJ、PK、PZ の各ポートが存在しない。PF は6本、PG は10本のみ |
| LFBGA448 (AAA3 / DAA1) | **172** | 全ポートが使える |

354で困ること:

1. **LTDC (RGB888の24bit) が現実的でない。** 354では、LCD_R0 は PG13 のみ、LCD_R3 は PB0 のみ、LCD_G2 は PA6 のみなど、各色信号の選択肢が1〜4本しかなく、PI/PJ/PKの豊富な候補が使えない。Ethernet(RMII)、microSD、eMMC(8bit) と同時に使うと、ほぼ競合する。**RGB565 (16bit色) なら成立する可能性はあるが、余裕がない。**
2. **PMICのI2C (STの標準配線 PZ4/PZ5) が使えない。** 354にはPZポートが無く、I2C4を別のピン (PE2/PD13 など) に振り替える必要がある。
3. **32bitタイマでエンコーダを数えられない。** TIM5のCH1/CH2は、354ではPA0/PA1だけで、PA1はEthernet RMIIのREF_CLK専用、PA0はPMIC割り込み(WKUP1)用と競合する。エンコーダは16bitタイマ (ソフトで拡張) になる。
4. 画面、Ethernet、SDカード、eMMC、カスタムIO (約40本) の合計で、94本では余裕がない。

448 (LFBGA448 18×18、0.8mmピッチ) なら、全て解決し、32bitのTIM5エンコーダ + 1PPSでのカウンタ保持もハードウェアで実現できる。

**提案: SoCを STM32MP157AAA3 (LFBGA448、JLCPCB C961771、在庫17、$15.56) に変更する。** 650MHzのA7、暗号機能なしだが、M4(209MHz)と今回の機能には影響しない。DAB1より安い。DAA1 (800MHz版、LFBGA448) は、LCSCで在庫が極少。

## 割り当て案 (LFBGA448 を前提、ボール番号付き)

### M4が占有するもの (パルス送出、エンコーダ、1PPS)

| 機能 | 信号 | ピン (ボール) | メモ |
|---|---|---|---|
| クロック | 10MPPS → HSE (バイパス) | PH0-OSC_IN (T1) | 絶縁バッファ出力 → 直列抵抗 → OSC_IN |
| パルス出力 | TIM2_CH1 | PG8 (Y8) | 32bit。DMA要求は TIM2_UP (DMAMUX 22)。RS-422/TTLの出力段へ |
| エンコーダ A | TIM5_CH1 | PH10 (B1) | 32bit エンコーダモード |
| エンコーダ B | TIM5_CH2 | PH11 (B3) | 同上 |
| 1PPS 捕捉 | TIM5_CH3 | PH12 (F5) | 1PPS立ち上がりで TIM5_CNT (エンコーダ値) をハードウェアで保持 |
| エンコーダ Z | TIM5_CH4 | PI0 (D1) | 入力キャプチャ |

### A7 (Linux) が使うもの

| 機能 | 信号 | ピン (ボール) |
|---|---|---|
| GPS UART | UART7_RX / TX | PE7 (W10) / PE8 (Y12) |
| デバッグUART | UART4_TX / RX | PG11 (U11) / PB2 (V13) (STの標準配線と同じ) |
| Ethernet (RMII) | REF_CLK / MDIO / MDC / CRS_DV | PA1 (V4) / PA2 (AB2) / PC1 (AB3) / PA7 (Y9) |
|  | RXD0 / RXD1 / TX_EN / TXD0 / TXD1 | PC4 (AB6) / PC5 (AA6) / PB11 (Y5) / PG13 (AA1) / PG14 (AA2) |
| microSD (SDMMC1) | D0〜D3 / CK / CMD | PC8 (E14) / PC9 (D14) / PC10 (F14) / PC11 (D15) / PC12 (E12) / PD2 (D12) |
| eMMC (SDMMC2、8bit) | CK / CMD | PE3 (A10) / PG6 (D11) |
|  | D0〜D7 | PB14 (A13) / PB15 (B12) / PB3 (A12) / PB4 (C13) / PA8 (B13) / PA9 (A11) / PE5 (C12) / PD3 (B11) |
| PMIC | I2C4 SCL / SDA | PZ4 (G1) / PZ5 (H4) |
|  | PMIC割り込み (WKUP1) | PA0 (AA3) |
|  | PWR_ON / PWR_LP / NRST | V1 / U1 / R2 (専用ピン) |
| ブート | BOOT0 / BOOT1 / BOOT2 | N3 / N4 / P4 (専用ピン) |
| LTDC (RGB888) | R0〜R7, G0〜G7, B0〜B7, CLK, HSYNC, VSYNC, DE | PI/PJ/PK のポートを使う (CubeMXで確定) |
| タッチ | I2C (SCL/SDA)、割り込み、リセット | CubeMXで確定 |

### GPIOで足りるもの (ピンはCubeMXで確定)

| 用途 | 本数 | 方向 |
|---|---|---|
| 状態LED (緑×2、赤×2) | 4 | 出力 |
| 外部ステータスOC出力 | 4 | 出力 |
| モーター方向 (RS-422/TTL共通) | 1 | 出力 |
| M_DIR_OC | 1 | 出力 |
| GPS LOCK / ALM_N | 2 | 入力 |
| GPS RST_N | 1 | 出力 |
| 1PPS (A7側、pps-gpio) | 1 | 入力 (M4用と同じ信号を分岐) |
| PHYリセット、eMMCリセット、SDカード検出 | 3 | 出/入 |
| タッチ割り込み/リセット、バックライト | 3 | 入/出 |

## DMAとM4の割り当て (RM0436より)

- TIM2、TIM5はETZPCでM4専有にできる。DMA1/DMA2もM4側に割り当てる。
- パルス送出の流れ: DDR → MDMA → SRAM → DMA → TIM2_ARR (DMAMUX入力 TIM2_UP = 22)。
- エンコーダのカウント (TIM5、32bit) は、パルスとは別のタイマで、お互い干渉しない。

## 次の作業

SoCは448(AAA3)で確定。次は、CubeMXでのボール単位の競合確認 (LTDC RGB888、タッチI2C、残りGPIO約20本、USB OTG_ID)、そして絶縁IC・RS-422・DC-DC・フォトカプラ・USB変換ICなどのJLCPCB部品選定。

## 追加 (2026-11-13): 信号一覧の更新と、A7の残作業

### 確定した要件から必要な信号

| 区分 | 信号 | 本数 | 備考 |
|---|---|---|---|
| LTDC (パネル DT050CTFT-IPS-SHB-PTS) | R0〜R7、G0〜G7、B0〜B7、CLK、HSYNC、VSYNC、DE | 27 | 24bit RGB、25MHz。PI/PJ/PKポートの候補から、配線がまとまる組合せをCubeMXで選ぶ |
| パネル制御 | DISP、バックライトPWM (昇圧のCTRL)、バックライト昇圧EN | 3 | PWMはタイマ出力 |
| タッチ (ST1633I) | I2C SCL/SDA、INT、RST | 4 | 3.3V。アドレスは要確認 |
| SWD | SWDIO = PA13、SWCLK = PA14 (専用機能) | 2 | 他の機能に使わない。NRSTも使う |
| USB | OTG_ID (PA10)、OTG_VBUS (専用)、USBH/OTG DP/DM (専用) | 1〜 | ホスト用VBUSの制御はPMIC |
| UART | UART4 (デバッグ)、UART7 (GPS) | 4 | 割当済み |
| 状態LED | 緑×2、赤×2 | 4 | |
| 外部OC出力 | ×4 + M_DIR_OC | 5 | |
| モーター方向 | RS-422、TTL (同じ信号) | 1 | |
| GPS | LOCK、ALM_N、RST_N、1PPS (A7側) | 4 | |
| その他 | PHYリセット、eMMCリセット、SDカード検出 | 3 | |
| ステータス | PMIC (I2C4、INT、WAKEUP) | 4 | PZ4/PZ5、PA0、PC13 |

### CubeMXでの確定 (A7)

- 上記の合計を、LFBGA448のGPIO 172本に収める (現在の見積もりは概ね余裕あり)。
- **ボール番号は、データシート原本 (Table 7) で、使う全ピンについて照合する**。
- 競合の確認: TIM2/TIM5の入出力 (パルス、エンコーダ、1PPS)、UART4 (PG11/PB2) とSWD (PA13/PA14) とPA12 (UART4_TX候補) の重複、SDMMC1/2、ETH RMII、LTDC。
- パルス・エンコーダのタイマ割当は、M4の専有 (ETZPC) と整合させる。
