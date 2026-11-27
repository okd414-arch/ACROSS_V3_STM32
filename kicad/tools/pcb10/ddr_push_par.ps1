# ddr_push.py を写しごとに並列で回す (2026-11-24)
# usage: powershell -File ddr_push_par.ps1 元の基板 名前 SEED 回数 MaxRip Margin
param([string]$Src, [string]$Name, [int]$Seed, [int]$Rounds = 12, [int]$MaxRip = 15, [string]$Margin = "12")
$K = "C:\MyWorks\ACROSS_V3_STM32\kicad"
$W = "$K\work\$Name"
New-Item -ItemType Directory -Force $W, "$W\tmp" | Out-Null
Copy-Item $Src "$W\$Name.kicad_pcb"
foreach ($e in 'kicad_pro', 'kicad_dru') { Copy-Item "$K\work\l10\l10.$e" "$W\$Name.$e" }
$env:TMP = "$W\tmp"; $env:TEMP = "$W\tmp"; $env:MR_VIP_COST = "0.3"; $env:MR_SEED = "$Seed"
python "$K\tools\pcb10\ddr_push.py" "$W\$Name.kicad_pcb" $Rounds --maxrip $MaxRip --margin $Margin *> "$W\push.log"
