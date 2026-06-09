<#
.SYNOPSIS
  Stop and remove the PVWoodERP Windows service.

.DESCRIPTION
  Idempotent. Does nothing if the service doesn't exist.
  Run AS ADMINISTRATOR (right-click PowerShell -> Run as administrator).

  Database files (erp.db, erp.db-wal, erp.db-shm) are NOT touched.
  Backups under backups\ are NOT touched.

.PARAMETER ServiceName
  Default: PVWoodERP.
#>
[CmdletBinding()]
param([string]$ServiceName = 'PVWoodERP')

$ErrorActionPreference = 'Stop'

$currentUser = [Security.Principal.WindowsIdentity]::GetCurrent()
$isAdmin     = (New-Object Security.Principal.WindowsPrincipal($currentUser)).IsInRole(
    [Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Host "[ERROR] Must run as Administrator." -ForegroundColor Red
    exit 1
}

$svc = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
if (-not $svc) {
    Write-Host "No service named '$ServiceName' is installed. Nothing to do." -ForegroundColor Yellow
    exit 0
}

if ($svc.Status -eq 'Running') {
    Write-Host "Stopping $ServiceName..."
    & nssm.exe stop $ServiceName confirm | Out-Null
    Start-Sleep -Seconds 1
}

Write-Host "Removing $ServiceName..."
& nssm.exe remove $ServiceName confirm | Out-Null
Write-Host "OK  $ServiceName removed. Database and backups are untouched." -ForegroundColor Green
