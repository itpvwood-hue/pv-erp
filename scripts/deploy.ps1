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
    [string]$ServiceName = "PVWoodERP",
    [int]$Port = 8000,
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

# -- 3. Restart the service (picks up new code; runs migrations) -------
Write-Host "`n[3/4] Restarting service '$ServiceName'..." -ForegroundColor Cyan
$svc = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
if (-not $svc) {
    Write-Host "Service '$ServiceName' is not installed yet." -ForegroundColor Yellow
    Write-Host "deploy.ps1 only UPDATES an existing service. Run the one-time install first:" -ForegroundColor Yellow
    Write-Host "    .\scripts\install_service.ps1" -ForegroundColor Yellow
    exit 1
}
try {
    Restart-Service -Name $ServiceName -Force -ErrorAction Stop
} catch {
    Write-Host "Could not restart '$ServiceName': $($_.Exception.Message)" -ForegroundColor Red
    Write-Host "The service may be half-registered / 'marked for deletion'. Re-run the installer:" -ForegroundColor Yellow
    Write-Host "    .\scripts\install_service.ps1   (it now waits for a stuck delete to clear)" -ForegroundColor Yellow
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
