<#
.SYNOPSIS
  Register the PVWood ERP as a Windows service via NSSM.

.DESCRIPTION
  Idempotent. Re-run after `git pull` to refresh the service config (the
  service is stopped, reconfigured, and restarted in one pass).

  What it does:
    * Verifies nssm.exe is on PATH.
    * Auto-discovers the project root (this script's parent's parent) and
      a Python interpreter (prefers the `py -3` launcher, falls back to
      `python`).
    * Creates the PVWoodERP service (or updates it if already installed).
    * Points stdout + stderr at logs\service-stdout.log / -stderr.log with
      5 MB rotation so the disk can't fill from runaway output.
    * Sets startup = SERVICE_AUTO_START so the ERP comes back on reboot.
    * Sets restart-on-crash with a 5 s cooldown so a single bad request
      can't loop the service at 100 % CPU.
    * Starts the service.

  Run this AS ADMINISTRATOR (Windows requires admin to create/modify
  services). Right-click PowerShell -> Run as administrator.

.PARAMETER ServiceName
  Override the Windows service name. Default: PVWoodERP.

.PARAMETER BindHost
  Override the listen address. Default: 0.0.0.0 (all interfaces).
  Use 127.0.0.1 to confine the service to the loopback interface.

.PARAMETER Port
  Override the listen port. Default: 8000.

.EXAMPLE
  # Standard install (run from an elevated PowerShell prompt):
  cd "D:\PVWood\erp"
  .\scripts\install_service.ps1

.EXAMPLE
  # Install on a non-default port:
  .\scripts\install_service.ps1 -Port 8080

.NOTES
  Download NSSM (single-file binary, free) from https://nssm.cc/download
  Unzip and copy nssm.exe to a directory on the system PATH, e.g.
    C:\Windows\System32\nssm.exe
  Then re-run this script.
#>
[CmdletBinding()]
param(
    [string]$ServiceName = 'PVWoodERP',
    [string]$BindHost    = '0.0.0.0',
    [int]   $Port        = 8000
)

$ErrorActionPreference = 'Stop'

# ── Sanity: must be administrator ──────────────────────────────
$currentUser = [Security.Principal.WindowsIdentity]::GetCurrent()
$isAdmin     = (New-Object Security.Principal.WindowsPrincipal($currentUser)).IsInRole(
    [Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Host "[ERROR] This script must be run as Administrator." -ForegroundColor Red
    Write-Host "        Right-click PowerShell -> Run as administrator, then re-run." -ForegroundColor Red
    exit 1
}

# ── Sanity: NSSM on PATH ───────────────────────────────────────
$nssm = (Get-Command nssm -ErrorAction SilentlyContinue)
if (-not $nssm) {
    Write-Host "[ERROR] nssm.exe not found on PATH." -ForegroundColor Red
    Write-Host "        Download from https://nssm.cc/download (single .exe, ~300 kB)." -ForegroundColor Yellow
    Write-Host "        Unzip and copy nssm.exe to C:\Windows\System32\nssm.exe (or anywhere on PATH)." -ForegroundColor Yellow
    Write-Host "        Then re-run this script." -ForegroundColor Yellow
    exit 1
}

# ── Project root + python discovery ────────────────────────────
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$logsDir     = Join-Path $projectRoot 'logs'
if (-not (Test-Path $logsDir)) { New-Item -ItemType Directory -Force -Path $logsDir | Out-Null }

# Prefer the `py` launcher (most portable on Windows). Fall back to plain python.
$pythonCmd = $null
$pythonArgsPrefix = @()
if (Get-Command py -ErrorAction SilentlyContinue) {
    $pythonCmd = (Get-Command py).Source
    $pythonArgsPrefix = @('-3')
} elseif (Get-Command python -ErrorAction SilentlyContinue) {
    $pythonCmd = (Get-Command python).Source
} else {
    Write-Host "[ERROR] No Python interpreter found on PATH." -ForegroundColor Red
    Write-Host "        Install Python 3.10+ from python.org and re-run." -ForegroundColor Yellow
    exit 1
}

Write-Host "──────────────────────────────────────────────"  -ForegroundColor Cyan
Write-Host " PVWood ERP service install"                       -ForegroundColor Cyan
Write-Host "──────────────────────────────────────────────"  -ForegroundColor Cyan
Write-Host " service name : $ServiceName"
Write-Host " project root : $projectRoot"
Write-Host " python       : $pythonCmd $($pythonArgsPrefix -join ' ')"
Write-Host " bind         : $BindHost:$Port"
Write-Host " logs         : $logsDir\service-stdout.log + service-stderr.log"
Write-Host ""

# ── Stop + remove any prior service of the same name ───────────
# We deliberately overwrite — re-running this script is the documented
# way to refresh service config after a git pull.
$existing = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
if ($existing) {
    Write-Host "[1/5] Existing service detected; stopping and removing..."
    if ($existing.Status -eq 'Running') {
        & nssm.exe stop $ServiceName confirm | Out-Null
    }
    & nssm.exe remove $ServiceName confirm | Out-Null
    Start-Sleep -Seconds 1
} else {
    Write-Host "[1/5] No existing service named '$ServiceName' — fresh install."
}

# ── Install the service ─────────────────────────────────────────
# Uvicorn is launched from the execution/ folder via -m so the existing
# `from database import ...` lazy-style relative imports keep resolving.
Write-Host "[2/5] Registering service..."
$uvicornArgs = $pythonArgsPrefix + @(
    '-m', 'uvicorn',
    'main:app',
    '--host', $BindHost,
    '--port', $Port.ToString(),
    '--log-level', 'info'
)
& nssm.exe install $ServiceName $pythonCmd $uvicornArgs | Out-Null

# Working directory MUST be execution/ so `main:app` resolves.
$executionDir = Join-Path $projectRoot 'execution'
& nssm.exe set $ServiceName AppDirectory $executionDir | Out-Null

# ── Logging: stdout + stderr to rotating files ─────────────────
Write-Host "[3/5] Configuring log rotation..."
& nssm.exe set $ServiceName AppStdout (Join-Path $logsDir 'service-stdout.log') | Out-Null
& nssm.exe set $ServiceName AppStderr (Join-Path $logsDir 'service-stderr.log') | Out-Null
& nssm.exe set $ServiceName AppRotateFiles  1        | Out-Null   # enable rotation
& nssm.exe set $ServiceName AppRotateOnline 1        | Out-Null   # rotate even while service runs
& nssm.exe set $ServiceName AppRotateBytes  5242880  | Out-Null   # 5 MB per file
& nssm.exe set $ServiceName AppRotateSeconds 86400   | Out-Null   # daily rotation regardless of size

# ── Lifecycle: auto-start + restart on crash ───────────────────
Write-Host "[4/5] Setting auto-start + crash-restart..."
& nssm.exe set $ServiceName Start          SERVICE_AUTO_START  | Out-Null
& nssm.exe set $ServiceName AppExit        Default Restart     | Out-Null   # any exit -> restart
& nssm.exe set $ServiceName AppRestartDelay 5000               | Out-Null   # 5s cooldown so a crash loop doesn't peg CPU
& nssm.exe set $ServiceName AppThrottle     10000              | Out-Null   # if process dies within 10s of start, consider it failed

# Human-readable description shown in services.msc
& nssm.exe set $ServiceName Description    "PVWood ERP (FastAPI + uvicorn). Project root: $projectRoot" | Out-Null
& nssm.exe set $ServiceName DisplayName    "PVWood ERP"                                                | Out-Null

# ── Start it ────────────────────────────────────────────────────
Write-Host "[5/5] Starting service..."
& nssm.exe start $ServiceName | Out-Null
Start-Sleep -Seconds 2
$svc = Get-Service -Name $ServiceName
Write-Host ""
if ($svc.Status -eq 'Running') {
    Write-Host "OK  $ServiceName is RUNNING." -ForegroundColor Green
    Write-Host "    http://${BindHost}:$Port  (also http://localhost:$Port from this server)"
    Write-Host ""
    Write-Host "Common commands:"
    Write-Host "  Get-Service $ServiceName            # status"
    Write-Host "  Restart-Service $ServiceName        # restart after pulling new code"
    Write-Host "  Stop-Service $ServiceName           # stop"
    Write-Host "  nssm edit $ServiceName              # GUI to inspect config"
    Write-Host "  Get-Content $logsDir\service-stdout.log -Tail 50 -Wait    # tail logs"
} else {
    Write-Host "WARN  Service registered but status is '$($svc.Status)'." -ForegroundColor Yellow
    Write-Host "      Check $logsDir\service-stderr.log for the startup error."
    exit 2
}
