<#
.SYNOPSIS
  Register a daily Windows Task Scheduler task that runs scripts/backup_db.py.

.DESCRIPTION
  Idempotent. Re-runs cleanly: deletes the existing task and recreates it
  with the latest config.

  Defaults:
    * Task name      : PVWoodERP-DailyBackup
    * Trigger        : daily at 02:00 (local time)
    * Action         : python scripts/backup_db.py --keep 30 --quiet
    * Working dir    : project root
    * Run as         : the user that ran this script (so the python.exe
                       on PATH is the same one the user tests with).
                       Override with -RunAsUser SYSTEM if you want it to
                       fire even when nobody is logged in.

  Run AS ADMINISTRATOR (creating a scheduled task that runs at startup
  or as SYSTEM requires admin rights).

.PARAMETER TaskName
  Default: PVWoodERP-DailyBackup.

.PARAMETER TriggerTime
  Default: 02:00. 24-hour HH:MM format.

.PARAMETER Keep
  How many recent snapshots to retain. Default: 30.

.PARAMETER RunAsUser
  'SYSTEM' = runs at boot, no user session needed (recommended for prod).
  'CurrentUser' = runs as you; only fires if you've logged in since boot.
  Default: SYSTEM.

.EXAMPLE
  # Standard install on the live server, runs at 2 AM every day:
  .\scripts\install_backup_task.ps1

.EXAMPLE
  # Backup at noon and keep 90 days of history:
  .\scripts\install_backup_task.ps1 -TriggerTime "12:00" -Keep 90
#>
[CmdletBinding()]
param(
    [string]$TaskName    = 'PVWoodERP-DailyBackup',
    [string]$TriggerTime = '02:00',
    [int]   $Keep        = 30,
    [ValidateSet('SYSTEM','CurrentUser')]
    [string]$RunAsUser   = 'SYSTEM'
)

$ErrorActionPreference = 'Stop'

$currentUser = [Security.Principal.WindowsIdentity]::GetCurrent()
$isAdmin     = (New-Object Security.Principal.WindowsPrincipal($currentUser)).IsInRole(
    [Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Host "[ERROR] Must run as Administrator." -ForegroundColor Red
    exit 1
}

# ── Discover paths ────────────────────────────────────────────
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$scriptPath  = Join-Path $projectRoot 'scripts\backup_db.py'
if (-not (Test-Path $scriptPath)) {
    Write-Host "[ERROR] backup_db.py not found at $scriptPath" -ForegroundColor Red
    exit 1
}

$pythonCmd = $null
if (Get-Command py -ErrorAction SilentlyContinue) {
    $pythonCmd = (Get-Command py).Source
    $pythonArgs = "-3 `"$scriptPath`" --keep $Keep --quiet"
} elseif (Get-Command python -ErrorAction SilentlyContinue) {
    $pythonCmd = (Get-Command python).Source
    $pythonArgs = "`"$scriptPath`" --keep $Keep --quiet"
} else {
    Write-Host "[ERROR] Python not found on PATH." -ForegroundColor Red
    exit 1
}

Write-Host "──────────────────────────────────────────────"  -ForegroundColor Cyan
Write-Host " PVWood ERP backup task install"                  -ForegroundColor Cyan
Write-Host "──────────────────────────────────────────────"  -ForegroundColor Cyan
Write-Host " task name    : $TaskName"
Write-Host " trigger      : daily at $TriggerTime"
Write-Host " action       : $pythonCmd $pythonArgs"
Write-Host " working dir  : $projectRoot"
Write-Host " run as       : $RunAsUser"
Write-Host " keep         : $Keep snapshots"
Write-Host ""

# ── Remove any prior task of the same name ─────────────────────
$existing = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($existing) {
    Write-Host "[1/3] Removing existing task..."
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
} else {
    Write-Host "[1/3] No existing task — fresh install."
}

# ── Build the task ─────────────────────────────────────────────
Write-Host "[2/3] Building task..."
$action  = New-ScheduledTaskAction `
              -Execute $pythonCmd `
              -Argument $pythonArgs `
              -WorkingDirectory $projectRoot

$trigger = New-ScheduledTaskTrigger -Daily -At $TriggerTime

# Run hidden, allow on battery, run even if the trigger was missed (e.g.
# because the server was off at 02:00 — run as soon as it boots).
$settings = New-ScheduledTaskSettingsSet `
              -AllowStartIfOnBatteries `
              -DontStopIfGoingOnBatteries `
              -StartWhenAvailable `
              -ExecutionTimeLimit (New-TimeSpan -Minutes 15) `
              -Hidden

if ($RunAsUser -eq 'SYSTEM') {
    $principal = New-ScheduledTaskPrincipal `
                    -UserId 'SYSTEM' `
                    -LogonType ServiceAccount `
                    -RunLevel Highest
} else {
    $principal = New-ScheduledTaskPrincipal `
                    -UserId $env:USERNAME `
                    -LogonType InteractiveToken `
                    -RunLevel Highest
}

Register-ScheduledTask `
    -TaskName    $TaskName `
    -Action      $action `
    -Trigger     $trigger `
    -Settings    $settings `
    -Principal   $principal `
    -Description "PVWood ERP daily SQLite snapshot. Keeps the $Keep most-recent backups under <project>/backups/. See scripts/backup_db.py." `
    | Out-Null

# ── Smoke-test: run it once now ────────────────────────────────
Write-Host "[3/3] Triggering an immediate test run..."
Start-ScheduledTask -TaskName $TaskName
Start-Sleep -Seconds 3

$state = (Get-ScheduledTask -TaskName $TaskName).State
Write-Host ""
Write-Host "OK  Task '$TaskName' registered. Current state: $state" -ForegroundColor Green
Write-Host ""
Write-Host "Check the result with:"
Write-Host "  Get-ScheduledTaskInfo -TaskName $TaskName"
Write-Host "  Get-ChildItem $projectRoot\backups\erp-*.db | Sort-Object LastWriteTime -Descending | Select-Object -First 3"
Write-Host ""
Write-Host "To run the backup manually any time:"
Write-Host "  Start-ScheduledTask -TaskName $TaskName"
Write-Host "  # or"
Write-Host "  py -3 scripts\backup_db.py"
