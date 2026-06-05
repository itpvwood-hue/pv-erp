@echo off
title PVWood ERP
echo.
echo  ==========================================
echo       PVWood ERP - Local Server
echo  ==========================================
echo.

REM ── Find Python ─────────────────────────────────────────────
REM Prefer the `py` launcher (most portable on Windows).
where py >NUL 2>&1
if %errorlevel%==0 (
    set PYTHON=py -3
) else (
    where python >NUL 2>&1
    if %errorlevel%==0 (
        set PYTHON=python
    ) else (
        echo [ERROR] Python not found on PATH. Install Python 3.10+ and re-run.
        pause & exit /b 1
    )
)
echo Using: %PYTHON%

REM ── Install / update deps ───────────────────────────────────
echo [1/3] Checking dependencies...
%PYTHON% -m pip install -r requirements.txt -q
if errorlevel 1 (
    echo [ERROR] Failed to install dependencies.
    pause & exit /b 1
)

REM ── Seed only on a fresh install ────────────────────────────
if not exist erp.db (
    echo [2/3] No erp.db found - seeding demo data...
    %PYTHON% scripts\seed_data.py
) else (
    echo [2/3] Database found. Skipping seed.
)

REM ── Launch ──────────────────────────────────────────────────
REM HOST + PORT come from .env (loaded by execution/config.py at import
REM time). The values below are only used when those env vars are unset.
if "%HOST%"=="" set HOST=0.0.0.0
if "%PORT%"=="" set PORT=8000

echo [3/3] Starting ERP server on %HOST%:%PORT% ...
echo.
echo  Open your browser: http://localhost:%PORT%
echo  Press Ctrl+C to stop.
echo.
%PYTHON% -m uvicorn execution.main:app --host %HOST% --port %PORT% --reload
pause
