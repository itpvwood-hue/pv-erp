<#
.SYNOPSIS
  One-command deploy for the PVWood ERP server: snapshot DB -> git pull ->
  restart the Windows service -> health/version check.

.DESCRIPTION
  Run this from an *Administrator* PowerShell on the FACTORY SERVER (the box
  that staff connect to), inside the repo clone. It is safe to re-run.

  It does NOT touch erp.db, .env, or docs_storage/ - those are gitignored and
  stay on the server across pulls. DB schema migrations run automatically when
  the service restarts (init_db() is idempotent).

.EXAMPLE
  cd D:\PVWood\erp
  .\scripts\deploy.ps1
#>
[CmdletBinding()]
param(
    [string]$ServiceName = "PVWoodERP",   # NSSM Windows service (if you use one)
    [string]$TaskName    = "",            # Task Scheduler task name (auto-detected if blank)
    [int]$Port           = 8000,
    [switch]$SkipBackup
)

$ErrorActionPreference = "Stop"

# -- Locate repo root (parent of this script's folder) -----------------
$repo = Split-Path -Parent $PSScriptRoot
Set-Location $repo
Write-Host "Repo: $repo" -ForegroundColor Cyan

# Refresh PATH from the registry so git / py are found even if this PowerShell
# window was opened before they were installed (a freshly-installed tool isn't
# on the PATH of already-running shells).
$env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" +
            [System.Environment]::GetEnvironmentVariable("Path","User")

# Resolve the listen port from config.py (.env) unless -Port was passed, so the
# health check (and port-process kill) target the port the server actually binds.
if (-not $PSBoundParameters.ContainsKey('Port')) {
    try {
        $cfgExec = Join-Path $repo 'execution'
        $p = (& py -3 -c "import sys;sys.path.insert(0,r'$cfgExec');from config import PORT;print(PORT)" 2>$null)
        if ($p) { $Port = [int]($p.ToString().Trim()) }
    } catch {}
}
Write-Host "Port: $Port" -ForegroundColor Cyan

# -- Must be Administrator (Restart-Service needs it) ------------------
$isAdmin = ([Security.Principal.WindowsPrincipal] `
    [Security.Principal.WindowsIdentity]::GetCurrent()
).IsInRole([Security.Principal.WindowsBuiltinRole]::Administrator)
if (-not $isAdmin) {
    Write-Error "Run this in an Administrator PowerShell (needed to restart the service)."
    exit 1
}

# -- 1. Snapshot the DB before anything (paranoia is cheap) ------------
if (-not $SkipBackup) {
    Write-Host "`n[1/4] Backing up the database..." -ForegroundColor Cyan
    try { py -3 scripts\backup_db.py } catch { Write-Warning "Backup failed: $_ (continuing)" }
} else {
    Write-Host "`n[1/4] Skipping backup (-SkipBackup)." -ForegroundColor DarkYellow
}

# -- 2. Pull new code (fast-forward only; abort on conflict) -----------
Write-Host "`n[2/4] Pulling latest code..." -ForegroundColor Cyan
$before = (git rev-parse --short HEAD)
git fetch origin
git pull --ff-only origin main
if ($LASTEXITCODE -ne 0) {
    Write-Error "git pull failed. Working tree may be dirty - resolve manually (git status), then re-run."
    exit 1
}
$after = (git rev-parse --short HEAD)
if ($before -eq $after) {
    Write-Host "Already at $after - no new code. Restarting anyway to be safe." -ForegroundColor DarkYellow
} else {
    Write-Host "Updated $before -> $after" -ForegroundColor Green
}

# -- 3. Restart the running server (NSSM service OR scheduled task) -----
# Picks up the new code; DB migrations run on startup. Works whichever way
# the server is launched: a Windows service, a Task Scheduler task, or just
# a process holding the port.
Write-Host "`n[3/4] Restarting the ERP server..." -ForegroundColor Cyan

function Stop-PortProcess([int]$p) {
    $conns = Get-NetTCPConnection -LocalPort $p -State Listen -ErrorAction SilentlyContinue
    foreach ($procId in (@($conns.OwningProcess) | Sort-Object -Unique)) {
        if ($procId) { Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue }
    }
}

$restarted = $false

# (a) NSSM / Windows service, if one is installed and registered.
$svc = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
if ($svc) {
    try {
        Restart-Service -Name $ServiceName -Force -ErrorAction Stop
        Write-Host "  restarted Windows service '$ServiceName'" -ForegroundColor Green
        $restarted = $true
    } catch {
        Write-Host "  service '$ServiceName' exists but would not restart: $($_.Exception.Message)" -ForegroundColor Yellow
    }
}

# (b) Task Scheduler task (your setup). Find it by name, else auto-detect a
#     task whose action runs uvicorn / main:app / start.bat / this repo.
if (-not $restarted) {
    $task = $null
    if ($TaskName) {
        $task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    }
    if (-not $task) {
        $task = Get-ScheduledTask -ErrorAction SilentlyContinue | Where-Object {
            $a = ($_.Actions | ForEach-Object { "$($_.Execute) $($_.Arguments)" }) -join ' '
            $a -match 'uvicorn|main:app|start\.bat|pvwood|pv-erp'
        } | Select-Object -First 1
    }
    if ($task) {
        $tn = $task.TaskName
        Write-Host "  restarting scheduled task '$tn'..." -ForegroundColor Cyan
        Stop-ScheduledTask -TaskName $tn -ErrorAction SilentlyContinue
        Start-Sleep -Seconds 2
        Stop-PortProcess $Port      # in case the server detached from the task
        Start-Sleep -Seconds 1
        Start-ScheduledTask -TaskName $tn
        Write-Host "  scheduled task '$tn' restarted" -ForegroundColor Green
        $restarted = $true
    }
}

if (-not $restarted) {
    Write-Host "No PVWoodERP service or scheduled task found to restart." -ForegroundColor Red
    Write-Host "Options:" -ForegroundColor Yellow
    Write-Host "  - Pass your task name:   .\scripts\deploy.ps1 -TaskName 'Your Task Name'" -ForegroundColor Yellow
    Write-Host "  - List tasks to find it: Get-ScheduledTask | Where-Object State -ne 'Disabled' | Select TaskName,TaskPath" -ForegroundColor Yellow
    Write-Host "  - Or start it manually:  .\start.bat" -ForegroundColor Yellow
    exit 1
}

# -- 4. Verify health + version ----------------------------------------
Write-Host "`n[4/4] Verifying..." -ForegroundColor Cyan
$ok = $false
for ($i = 0; $i -lt 20; $i++) {
    Start-Sleep -Seconds 1
    try {
        $h = Invoke-RestMethod -Uri "http://localhost:$Port/api/health" -TimeoutSec 3
        if ($h.ok -or $h.status -eq "ok") { $ok = $true; break }
    } catch { }
}
if (-not $ok) {
    Write-Error "Service did not become healthy on port $Port. Check logs\server.log and 'Get-Service $ServiceName'."
    exit 1
}
$ver = Invoke-RestMethod -Uri "http://localhost:$Port/api/version" -TimeoutSec 3
Write-Host ("`nDeployed OK - version {0} (build {1})" -f $ver.version, $ver.build_date) -ForegroundColor Green
