# NEURON installer for Windows 10 and 11, through WSL2 and Ubuntu 24.04.
#
# STATUS: UNVERIFIED. Written without a Windows machine to run it on; the owner's test in TESTING.md
# decides whether it works. The decision rules (memory limit, tier, networking) match neuron/install.py
# `windows_plan`, which is unit-tested; keep the two the same.
#
# Run in PowerShell (a normal window, not administrator):
#   Set-ExecutionPolicy -Scope Process Bypass
#   .\install-windows.ps1            # check, ask, install, start
#   .\install-windows.ps1 -Plan      # only show what it found and would do
#
# It asks before every step that needs administrator rights, changes WSL settings, or restarts the computer.

param([switch]$Plan, [int]$Port = 8642, [string]$Distro = "Ubuntu-24.04")
$ErrorActionPreference = "Stop"
$env:WSL_UTF8 = "1"                       # newer WSL prints UTF-8 instead of UTF-16 when this is set

function Say($m) { Write-Host "`n== $m" -ForegroundColor Cyan }
function Info($m) { Write-Host "   $m" }
function Stop-With($m) { Write-Host "`nInstall stopped: $m" -ForegroundColor Yellow; exit 1 }
function Ask($q) { $a = Read-Host "   $q [y/N]"; return ($a -match '^(y|yes)$') }

# Elevated steps run as a separate script, after asking, so this window never needs administrator rights.
function Run-Elevated($commands, $why) {
    if (-not (Ask "$why This needs administrator approval. Continue?")) { return $false }
    $file = Join-Path $env:TEMP "neuron-admin-step.ps1"
    Set-Content -Path $file -Value ($commands -join "`r`n") -Encoding UTF8
    $p = Start-Process powershell.exe -ArgumentList "-NoProfile -ExecutionPolicy Bypass -File `"$file`"" -Verb RunAs -Wait -PassThru
    return ($p.ExitCode -eq 0)
}

# ---- 1. what this computer has ------------------------------------------------------------------------
Say "Checking this computer"
$os = Get-CimInstance Win32_OperatingSystem
$build = [int]$os.BuildNumber
$cs = Get-CimInstance Win32_ComputerSystem
$cpu = Get-CimInstance Win32_Processor | Select-Object -First 1
$ramGB = [math]::Round($cs.TotalPhysicalMemory / 1GB, 1)
$freeGB = [math]::Round((Get-PSDrive -Name C).Free / 1GB, 1)
$win = if ($build -ge 22000) { "Windows 11" } else { "Windows 10" }
Info "$win, build $build; memory $ramGB GB; free disk on C: $freeGB GB"

if ($build -lt 19041) { Stop-With "WSL2 needs Windows 10 version 2004 (build 19041) or newer. Please update Windows first." }
$virt = $cs.HypervisorPresent -or $cpu.VirtualizationFirmwareEnabled
if (-not $virt) {
    Stop-With ("Hardware virtualisation is switched off. Restart into the BIOS/UEFI settings and turn on " +
               "Intel VT-x / AMD-V (sometimes called SVM or Virtualization Technology), then run this again.")
}
Info "hardware virtualisation: on"
if ($freeGB -lt 15) { Stop-With "NEURON needs about 15 GB free on drive C (Ubuntu, tools and one model); $freeGB GB is free." }

# ---- 2. the plan: same rules as windows_plan() in neuron/install.py --------------------------------------
$reserveGB = [math]::Max(3, [math]::Ceiling($ramGB * 0.30))       # left for Windows itself
$wslGB = [math]::Floor($ramGB - $reserveGB)
if ($wslGB -lt 3) { Stop-With "This computer has $ramGB GB of memory; after keeping $reserveGB GB for Windows, less than 3 GB is left for NEURON." }
$usable = $wslGB - [math]::Max(1, $wslGB * 0.15)                   # what neuron/install.py leaves for Ubuntu inside WSL
$tier = if ($usable -ge 8) { "8gb" } elseif ($usable -ge 4) { "4gb" } else { "2gb" }

$wslVersion = ""
try { $wslVersion = (wsl.exe --version 2>$null | Select-String -Pattern 'WSL[^:]*:\s*([0-9.]+)' | Select-Object -First 1).Matches[0].Groups[1].Value } catch { }
$wslMajor = if ($wslVersion) { [int]($wslVersion.Split('.')[0]) } else { 0 }
$mirrored = ($build -ge 22621) -and ($wslMajor -ge 2)
$net = if ($mirrored) { "mirrored networking (Windows 11 22H2 or newer)" } else { "port forwarding from Windows to WSL" }
Info "WSL memory limit: $wslGB GB (keeps $reserveGB GB for Windows); expected NEURON tier: $tier"
Info "phone access: $net, port $Port"
if ($Plan) { Info "(plan only, nothing changed)"; exit 0 }

# ---- 3. WSL and Ubuntu -------------------------------------------------------------------------------
Say "WSL2 and $Distro"
$distros = @()
try { $distros = (wsl.exe -l -q 2>$null) | ForEach-Object { $_.Trim([char]0, ' ') } | Where-Object { $_ } } catch { }
if (-not ($distros -contains $Distro)) {
    $ok = Run-Elevated @("wsl.exe --install -d $Distro") "WSL2 and $Distro will be installed (about 1-2 GB download)."
    if (-not $ok) { Stop-With "WSL was not installed." }
    Info "When Ubuntu opens for the first time it asks you to choose a user name and password: that is your Ubuntu account."
    if (Ask "Windows usually needs a restart to finish installing WSL. Restart now?") { Restart-Computer }
    Stop-With "Restart Windows, open Ubuntu once from the Start menu to create your account, then run this script again."
}
Info "found $Distro"

# ---- 4. WSL settings: memory limit and networking --------------------------------------------------------
$cfg = Join-Path $env:USERPROFILE ".wslconfig"
$want = [ordered]@{ "memory" = "$($wslGB)GB"; "swap" = "2GB" }
if ($mirrored) { $want["networkingMode"] = "mirrored" }
$lines = if (Test-Path $cfg) { Get-Content $cfg } else { @() }
$out = New-Object System.Collections.Generic.List[string]; $inWsl2 = $false; $seen = @{}; $hadSection = $false
foreach ($l in $lines) {
    if ($l -match '^\s*\[(.+)\]\s*$') {
        if ($inWsl2) { foreach ($k in $want.Keys) { if (-not $seen[$k]) { $out.Add("$k=$($want[$k])") } } }
        $inWsl2 = ($Matches[1].Trim().ToLower() -eq "wsl2"); if ($inWsl2) { $hadSection = $true }
        $out.Add($l); continue
    }
    if ($inWsl2 -and $l -match '^\s*([A-Za-z]+)\s*=') {
        $k = $Matches[1]; $match = $want.Keys | Where-Object { $_ -ieq $k }
        if ($match) { $out.Add("$match=$($want[$match])"); $seen[$match] = $true; continue }
    }
    $out.Add($l)
}
if ($inWsl2) { foreach ($k in $want.Keys) { if (-not $seen[$k]) { $out.Add("$k=$($want[$k])") } } }
if (-not $hadSection) { $out.Add("[wsl2]"); foreach ($k in $want.Keys) { $out.Add("$k=$($want[$k])") } }
$newText = ($out -join "`r`n")
$oldText = ($lines -join "`r`n")
if ($newText -ne $oldText) {
    Info "WSL settings to write to $cfg :"; $want.GetEnumerator() | ForEach-Object { Info "  $($_.Key)=$($_.Value)" }
    if (Ask "Write these settings (your old file is kept as .wslconfig.neuron-backup) and restart WSL? Running Linux programs will stop.") {
        if (Test-Path $cfg) { Copy-Item $cfg "$cfg.neuron-backup" -Force }
        Set-Content -Path $cfg -Value $newText -Encoding ASCII
        wsl.exe --shutdown
        Info "settings written; WSL restarted"
    } else { Info "settings not changed (NEURON may pick a different tier, and the phone may not reach it)" }
} else { Info "WSL settings already as needed" }

# ---- 5. NEURON inside Ubuntu ---------------------------------------------------------------------------
Say "Installing NEURON inside $Distro"
Info "Ubuntu may ask for your Ubuntu password (for system packages) and GitHub may ask you to sign in (the repository is private)."
$inside = 'set -e; command -v git >/dev/null || (sudo apt-get update -q && sudo apt-get install -y -q git); ' +
          '[ -d ~/Neuron ] || git clone https://github.com/Sthmpe/Neuron.git ~/Neuron; cd ~/Neuron && git pull --ff-only; ' +
          'bash scripts/install.sh --no-start'
wsl.exe -d $Distro -- bash -lc $inside
if ($LASTEXITCODE -ne 0) { Stop-With "the installer inside Ubuntu reported a problem (see the lines above)." }

# ---- 6. phone access -----------------------------------------------------------------------------------
Say "Letting your phone reach NEURON (port $Port, private networks only)"
$fw = "New-NetFirewallRule -DisplayName 'NEURON phone page' -Direction Inbound -LocalPort $Port -Protocol TCP -Action Allow -Profile Private -ErrorAction SilentlyContinue | Out-Null"
if ($mirrored) {
    $cmds = @($fw, "New-NetFirewallHyperVRule -Name NEURON -DisplayName 'NEURON phone page' -Direction Inbound -VMCreatorId '{40E0AC32-46A5-438A-A0B2-2B479E8F2E90}' -Protocol TCP -LocalPorts $Port -Action Allow -ErrorAction SilentlyContinue | Out-Null")
} else {
    $cmds = @($fw)               # the port forward itself is refreshed at every start (WSL's address changes after a restart)
}
if (-not (Run-Elevated $cmds "A Windows Firewall rule will allow your phone to reach port $Port on private (home) networks.")) {
    Info "firewall not changed: the phone may not reach NEURON"
}

# ---- 7. start script -----------------------------------------------------------------------------------
$dir = Join-Path $env:USERPROFILE "NEURON"; New-Item -ItemType Directory -Force -Path $dir | Out-Null
$start = Join-Path $dir "Start-NEURON.ps1"
$mirroredText = if ($mirrored) { '$true' } else { '$false' }
$startText = @"
# Starts NEURON inside $Distro and shows the address for your phone. Created by install-windows.ps1.
`$env:WSL_UTF8 = "1"
`$ip = (Get-NetIPConfiguration | Where-Object { `$_.IPv4DefaultGateway -ne `$null -and `$_.NetAdapter.Status -eq 'Up' } | Select-Object -First 1).IPv4Address.IPAddress
`$mirrored = $mirroredText
if (-not `$mirrored) {
    `$wslIp = (wsl.exe -d $Distro -- hostname -I).Trim().Split(' ')[0]
    `$cmd = "netsh interface portproxy delete v4tov4 listenport=$Port listenaddress=0.0.0.0; netsh interface portproxy add v4tov4 listenport=$Port listenaddress=0.0.0.0 connectport=$Port connectaddress=`$wslIp"
    Write-Host "Refreshing the port forward to WSL (`$wslIp); Windows will ask for administrator approval."
    Start-Process powershell.exe -ArgumentList "-NoProfile -Command `$cmd" -Verb RunAs -Wait
}
Write-Host "On your phone (same Wi-Fi) open: http://`${ip}:$Port"
wsl.exe -d $Distro -- bash -lc "NEURON_PUBLIC_HOST=`$ip ~/.neuron/start.sh"
"@
Set-Content -Path $start -Value $startText -Encoding UTF8
Info "start script: $start"
Info "new pairing code while NEURON runs:  wsl -d $Distro -- ~/.neuron/start.sh code"
if (Ask "Start NEURON now?") { & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $start }
