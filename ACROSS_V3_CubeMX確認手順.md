# ACROSS V3 CubeMXでのピン確認 (手順と結果)

作成: 2026-11-13

## すでに実施した検証 (CubeMXのデータベースを使用)

ユーザーのPCにインストール済みの **STM32CubeMX (6.16.1) のMCUデータベース**
`C:\Program Files\STMicroelectronics\STM32Cube\STM32CubeMX\db\mcu\STM32MP157AAAx.xml` (LFBGA448、448ボール、176 GPIO) を直接読み、割り当て全94ピンを検証した。これは、データシートのPDFを文字抽出した値より信頼できる (CubeMXが実際に使う定義)。

| 検証項目 | 結果 |
|---|---|
| ボール番号の一致 (LFBGA448) | **全94ピン一致** (PDF抽出の値とCubeMXのデータベースが一致) |
| 割り当てた機能がそのピンにあること (CubeMXの信号名で) | **全て存在** (ETH1_REF_CLK/MDIO/MDC/CRS_DV/RXD0/RXD1/TX_EN/TXD0/TXD1、LTDC 28信号、TIM2/TIM3/TIM5、UART4/7、SDMMC1/2、I2C1/I2C4、USB_OTG_HS_ID) |
| ボール番号の重複 | なし |
| SWD (PA13/PA14) | 専用のデバッグ機能 (既定) |

## ユーザーが行うCubeMXでの確認 (手順)

CubeMXをこちらから自動操作することはできなかった (コマンドライン実行は結果が出力されない)。**GUIでの確認はユーザーにお願いする。**

1. CubeMXを起動 → **New Project → MCU/MPU Selector → 「STM32MP157AAAx」(LFBGA448)** を選ぶ。
2. 右のコンテキスト選択で、**Cortex-A7 (Linux)** と **Cortex-M4** の両方を有効にする。
3. **Pinout & Configuration** で、`ACROSS_V3_CubeMX入力表.csv` の各ピンに、「CubeMX signal」の機能を割り当てる。ピン名を検索して、機能を選ぶ。
   - 全94ピン。LTDCの28信号はPI/PJ/PK。
   - 列「Context」で、**M4専有 (TIM2、TIM5、パルス/方向のGPIO)** と **A7 (Linux)** を分ける。TIM2・TIM5・DMA1/DMA2は、**CortexM4** のコンテキストに割り当てる。
4. 競合 (ピンが赤、または「conflict」の表示) が出ていないことを確認する。出たら、ピン名と競合先を記録して、こちらに知らせる。
5. **Clock Configuration**: HSEを「BYPASS Clock Source」に設定 (PH0-OSC_IN)、周波数10MHz。PLL3→TIM2/TIM5のクロック200MHz (APB1÷2)。「HSE = 10MHz、PLL3で200MHz」が成立するか確認 (設計メモの「クロック」の節)。
6. 確認後、`.ioc` ファイルを保存して、フォルダ `ACROSS_V3` に置く。**こちらで内容を読んで検証できる**。

### 確認のポイント (CubeMXで出やすい指摘)
- ETH RMII: 9ピンが全部同じグループ (ETH1) で選べるか。MDIO/MDCを含めて。
- SDMMC2 (eMMC) 8bit: D0〜D7、CK、CMDが同じコンテキスト (A7) で割り当てられるか。
- LTDC 24bit: 28信号が全て有効か (RGB888)。
- TIM2/TIM5 (M4専有)・TIM3 (A7)・USB OTG HS・I2C1/I2C4/I2C5の同時使用。
- PA13/PA14 (SWD) を、CubeMXの「DEBUG」で Serial Wire にしたとき、他の機能と競合しないこと。

## 注意

- **PA13 (SWDIO) は、代替機能として UART4_TX を持つが、本基板のUART4 TXは PG11** なので、競合しない。
- PD0〜PD5、PF0〜PF5 などのGPIOは、M4とA7のどちらが操作するかを、ETZPCで割り当てる。上記の「M4/A7」は、**運用方針を決めて確定**する (例: パルス・方向 (PF4、PF5) = M4、LED・外部OC = A7)。
