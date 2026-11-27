# DDR の繰り返し配線を、写しごとに順番 (MR_SEED) を変えて並列に回す (2026-11-23)
# usage: powershell -File ddr_par.ps1 元の基板 名前 SEEDの基準 回数
param([string]$Src, [string]$Name, [int]$Base, [int]$Rounds = 6, [int]$MaxRip = 3, [string]$Vip = "0.3", [string]$Margin = "4")
$K = "C:\MyWorks\ACROSS_V3_STM32\kicad"
$W = "$K\work\$Name"
New-Item -ItemType Directory -Force $W, "$W\tmp" | Out-Null
$srcDir = Split-Path $Src
$srcBase = [IO.Path]::GetFileNameWithoutExtension($Src)
Copy-Item $Src "$W\$Name.kicad_pcb"
foreach ($e in 'kicad_pro', 'kicad_dru') { Copy-Item "$K\work\ddr2\ddr2.$e" "$W\$Name.$e" }
$env:TMP = "$W\tmp"; $env:TEMP = "$W\tmp"; $env:MR_VIP_COST = $Vip
$env:MR_SEED_BASE = "$Base"; $env:MR_SEED = "$Base"
python "$K\tools\pcb\ddr_loop.py" "$W\$Name.kicad_pcb" $Rounds --maxrip $MaxRip --margin $Margin *> "$W\loop.log"
