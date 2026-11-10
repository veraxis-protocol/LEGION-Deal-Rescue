# LEGION Deal Rescue — fresh seven-party end-to-end run (Windows PowerShell 5.1+).
#
#   .\scripts\run_live_e2e.ps1 -NimKeyFile C:\path\to\nvapi.txt [-Port 8795] [-NoServe]
#
# What it does (nothing else):
#   1. Clones the EXTERNAL PolyForm-Noncommercial dependencies at their pinned commits into .\external\ (not part of
#      this Apache-2.0 repository; see NOTICE): LEGION Core d083c44, LEGION-Federation 9d2a32a, LEGION-Marketplace 906ec0f.
#   2. Creates .\external\.venv and installs LEGION-Marketplace\requirements.lock.
#   3. Runs one fresh deal: 7 party processes + marketplace + coordinator, NVIDIA NIM decisions, then the
#      independent read-only Judge (legion_marketplace.judge) while the parties are still running.
#   4. Runs the existing 25-case adversarial negative suite against the live party processes.
#   5. Builds the evidence-linked Deal Dossier, runs the UI evidence auditor and serves the app.
# All manufacture / shipment / buyer-ledger effects are SIMULATED. This script never calls PayPal.
param([Parameter(Mandatory = $true)][string]$NimKeyFile, [int]$Port = 8795, [switch]$NoServe)
$ErrorActionPreference = "Stop"
$Repo = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$Ext = Join-Path $Repo "external"
$Pins = [ordered]@{
    "LEGION-Core"        = @("https://github.com/veraxis-protocol/LEGION.git", "d083c44af2526e38068e0220891cd0bb5fce52af")
    "LEGION-Federation"  = @("https://github.com/veraxis-protocol/LEGION-Federation.git", "9d2a32a5c32758bea1ad2200955da1cc9213356c")
    "LEGION-Marketplace" = @("https://github.com/veraxis-protocol/LEGION-Marketplace.git", "906ec0f553c0f8076127f7abab98825e188342ef")
}
$JudgeSha = "9146122791d2d2a6f4cada2019c825b2c4925b6e4182fe91f55a7bae74f2992f"
if (-not (Test-Path $NimKeyFile)) { throw "NIM key file not found: $NimKeyFile" }
New-Item -ItemType Directory -Force $Ext | Out-Null
foreach ($name in $Pins.Keys) {
    $dir = Join-Path $Ext $name; $url, $sha = $Pins[$name]
    if (-not (Test-Path $dir)) { git clone -q $url $dir }
    git -C $dir checkout -q $sha
    if ((git -C $dir rev-parse HEAD) -ne $sha) { throw "$name is not at pinned commit $sha" }
}
$judge = (Get-FileHash (Join-Path $Ext "LEGION-Marketplace\legion_marketplace\judge.py") -Algorithm SHA256).Hash.ToLower()
if ($judge -ne $JudgeSha) { throw "Judge source hash mismatch: $judge" }
$Venv = Join-Path $Ext ".venv"
if (-not (Test-Path $Venv)) { python -m venv $Venv }
$Py = Join-Path $Venv "Scripts\python.exe"
& $Py -m pip install -q -r (Join-Path $Ext "LEGION-Marketplace\requirements.lock")

$Stamp = Get-Date -Format "yyyyMMddTHHmmss"
$Ev = Join-Path $Repo "demo_evidence"
$Run = Join-Path $Ev "runs\A2-live-$Stamp"   # "A2" = discovery + federation arm of the harness (--arm A2)
$env:PYTHONPATH = "$(Join-Path $Ext 'LEGION-Federation');$(Join-Path $Ext 'LEGION-Marketplace')"
$env:LMF_FEDERATION_ROOT = Join-Path $Ext "LEGION-Federation"
$env:LMF_NIM_KEY_FILE = (Resolve-Path $NimKeyFile).Path
Push-Location (Join-Path $Ext "LEGION-Marketplace")
& $Py -m legion_marketplace.e2e --core (Join-Path $Ext "LEGION-Core") --out $Run --arm A2
$e2e = $LASTEXITCODE
& $Py -m legion_marketplace.negatives --core (Join-Path $Ext "LEGION-Core") --out (Join-Path $Ev "negatives-live-$Stamp")
$neg = $LASTEXITCODE
Pop-Location
Write-Host "e2e exit=$e2e negatives exit=$neg run=$Run"
Get-Content (Join-Path $Run "judge_stdout.txt")
Set-Location $Repo
python -B scripts\build_and_serve.py --evidence demo_evidence --counted "A2-live-$Stamp" --negatives "negatives-live-$Stamp" --port $Port $(if ($NoServe) { "--no-serve" })
