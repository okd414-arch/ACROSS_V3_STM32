# ACROSS V3 ピン割り当て (確定案、LFBGA448)

作成: 2026-11-13 / 元資料: DS_stm32mp157c.pdf Table 7 (ピン表、LFBGA448の列)

## 検証方法と限界

- データシートのピン表 (Table 7) をテキスト抽出し、**LFBGA448のボール番号の列**と、各ピンの代替機能の一覧を機械的に読み取った。
- 割り当てた全ピンについて、**そのピンに必要な機能が代替機能の一覧にあること**を、スクリプトで確認した (パルス用TIM2/TIM5、UART、ETH RMII、SDMMC、I2C4、LTDC 28本、OTG_ID)。
- LTDCは、**同じ信号に使える全ピンから、PI/PJ/PKだけで28信号が重複なく割り当てられる**ことを、2部マッチングで確認した。
- **限界**: 機械的な読み取りなので、**ボール番号の最終確認は、STM32CubeMXでの競合チェックと、データシート原本の目視**で行う。ピンの電気的条件 (VSW電源ドメイン、アナログ専用、起動時の状態など) は未確認。

## 1. 検証済みの割り当て (前回までの案)

| 機能 | ピン (ボール) | 確認 |
|---|---|---|
| HSE (10MPPS) | PH0-OSC_IN (T1) | ピン名一致 |
| パルス出力 TIM2_CH1 | PG8 (Y8) | 機能あり |
| エンコーダ TIM5_CH1/CH2 | PH10 (B1) / PH11 (B3) | 機能あり |
| 1PPS 捕捉 TIM5_CH3 | PH12 (F5) | 機能あり |
| エンコーダZ TIM5_CH4 | PI0 (D1) | 機能あり |
| UART7 (GPS) RX/TX | PE7 (W10) / PE8 (Y12) | 機能あり |
| UART4 (デバッグ) TX/RX | PG11 (U11) / PB2 (V13) | 機能あり |
| ETH RMII | REF_CLK PA1 (V4)、MDIO PA2 (AB2)、MDC PC1 (AB3)、CRS_DV PA7 (Y9)、RXD0 PC4 (AB6)、RXD1 PC5 (AA6)、TX_EN PB11 (Y5)、TXD0 PG13 (AA1)、TXD1 PG14 (AA2) | 機能あり (ETH1_RMII_*) |
| microSD (SDMMC1) | D0 PC8 (E14)、D1 PC9 (D14)、D2 PC10 (F14)、D3 PC11 (D15)、CK PC12 (E12)、CMD PD2 (D12) | 機能あり |
| eMMC (SDMMC2 8bit) | CK PE3 (A10)、CMD PG6 (D11)、D0 PB14 (A13)、D1 PB15 (B12)、D2 PB3 (A12)、D3 PB4 (C13)、D4 PA8 (B13)、D5 PA9 (A11)、D6 PE5 (C12)、D7 PD3 (B11) | 機能あり |
| PMIC I2C4 SCL/SDA | PZ4 (G1) / PZ5 (H4) | 機能あり |
| PMIC INT / WAKEUP | PA0 (AA3、WKUP1) / PC13 (N2) | PC13 は WKUP3 |
| SWD | **SWDIO = JTMS-SWDIO (E17)、SWCLK = JTCK-SWCLK (D17)** (専用ピン) | **2026-11-13訂正**: 旧記載の PA13 (W3) / PA14 (R3) は誤り (PA13/PA14にSWD機能は無い。CubeMXのDBとEV1回路図で確認、.iocは正しく専用ピンを使用)。PA13/PA14は空き |
| USB OTG ID | PA10 (Y17) | OTG_HS_ID あり |
| USB DP/DM | USB_DP1 (AA15)、USB_DM1 (AB15)、USB_DP2 (AB14)、USB_DM2 (AA14)、USB_RREF (AA17) | 専用ピン |

注意: **PG13、PG14、PB11 はLTDCのR0、B0、G5の代替機能も持つが、LTDCは別のピンに割り当てたので競合しない。**

## 2. LTDC (24bit RGB、28信号) — PI/PJ/PKのみで割り当て可能

| 信号 | ピン (ボール) | 信号 | ピン (ボール) | 信号 | ピン (ボール) |
|---|---|---|---|---|---|
| R0 | PI15 (F3) | G0 | PJ7 (L4) | B0 | PJ12 (B8) |
| R1 | PJ0 (J2) | G1 | PJ8 (H6) | B1 | PJ13 (A7) |
| R2 | PJ1 (L6) | G2 | PJ9 (L2) | B2 | PJ14 (B7) |
| R3 | PJ2 (K4) | G3 | PJ10 (J3) | B3 | PJ15 (C7) |
| R4 | PJ3 (J1) | G4 | PJ11 (K6) | B4 | PI4 (J6) |
| R5 | PJ4 (K2) | G5 | PK0 (D8) | B5 | PI5 (F2) |
| R6 | PJ5 (K1) | G6 | PI1 (E2) | B6 | PI6 (G5) |
| R7 | PJ6 (L5) | G7 | PI2 (E1) | B7 | PI7 (F1) |
| CLK | PI14 (D2) | HSYNC | PI10 (W1) | VSYNC | PI13 (H1) |
| DE | PK7 (B5) | | | | |

- 候補が1本しかない信号 (R0、R1〜R6、G0、G1、G5、B0〜B3、CLK、DE) があり、それらは固定。他は代替の候補 (PK系) もあるので、基板配線に合わせて入れ替えられる。
- 以前の案に入れていた PA10 (LCD_B1) などは使っていない。

## 3. その他のGPIO (新規)

| 用途 | 信号 | ピン (ボール) | 備考 |
|---|---|---|---|
| 状態LED | 緑1 / 緑2 / 赤1 / 赤2 | PD0 (C10) / PD1 (B10) / PD4 (C9) / PD5 (A9) | 出力 |
| 外部OC出力 | OC1〜OC4 | PF0 (E10) / PF1 (B9) / PF2 (F13) / PF3 (V3) | 出力 (フォトカプラのLED) |
| モーター方向 (OC) | M_DIR_OC | PF4 (F9) | 出力 (フォトカプラ) |
| モーター方向 | DIR (RS-422/TTL、アイソレータ) | PF5 (D9) | 出力。M4が制御 |
| GPS | LOCK / ALM_N / RST_N | PG0 (W5) / PG1 (Y4) / PG2 (W4) | LOCK、ALM_Nは入力、RST_Nは出力 |
| GPS 1PPS (A7側) | pps-gpio | PG3 (U4) | 入力 (M4用のPH12と同じ信号を分岐) |
| リセット・検出 | PHY_RST / eMMC_RST / SD_CD | PE1 (D7) / PE2 (Y2) / PE4 (F15) | |
| タッチ | I2C1 SCL / SDA、INT、RST | PB8 (AB8) / PB9 (F12)、PE6 (E9)、PE9 (W11) | I2C1。タッチはST1633I |
| パネル制御 | DISP / BL_EN | PE10 (W14) / PE11 (D5) | 出力 |
| バックライトPWM | BL_PWM (TIM3_CH4) | PB1 (AA5) | A7側 (Linux pwm-backlight)。昇圧TPS61165のCTRLへ |

- 上記の新規割り当て: 24本。**空きGPIOは約66本**。
- 避けたピン: PH4/PH5 (I2C2。PH4の行は「VSW電源ドメイン」の注記つきで、ピン表の読み取りが怪しいため)、PA11/PA12 (USB FSの追加機能を持つ)、PA15 (JTDI)、PC14/PC15 (LSE)、PH1 (HSE)。

## 4. CubeMXで確認すること (A7の残り)

1. 全割り当てをCubeMXに入力し、**競合 (赤表示) がないこと**を確認。
2. ボール番号の目視確認: 特に、候補が1本の信号 (LTDC R0〜R6など)、USB、PMIC、SWD。
3. PE4 (SD_CD)、PE1〜PE2など、起動時 (リセット直後) のピン状態が問題にならないか。起動に関わるピン (BOOT0〜2、PA13/PA14) は専用。
4. LTDCのピンのVDD電源ドメイン (PI/PJ/PKはVDD)。
5. パルス・エンコーダのタイマ (TIM2、TIM5) を、M4専有 (ETZPC) にして、Linuxが触らないようにすること。
