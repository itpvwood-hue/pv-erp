# PVWood ERP — On-Prem Deployment Runbook

For deploying to (and operating) a Windows Server on the factory LAN.

Replaces the older `MIGRATION.md` which was written for v2.1.0 and predates
the dynamic portal split, NSSM service supervision, the backup job, and the
`/api/health` endpoint.

---

## 1. Prerequisites on the server

| Thing | Why | How |
|---|---|---|
| Windows Server 2019+ (or Win 10/11 Pro) | host OS | already provisioned |
| Python 3.10 or newer | runtime | https://www.python.org/downloads/windows/ — tick **"Add python.exe to PATH"** during install |
| `py` launcher | preferred Python invocation | comes with the python.org installer |
| Git | for `git pull` updates | https://git-scm.com/download/win |
| NSSM | runs the ERP as a Windows service | https://nssm.cc/download — unzip and copy `nssm.exe` to `C:\Windows\System32\` |
| Firewall rule for port 8000 | LAN clients can reach the API | `New-NetFirewallRule -DisplayName "PVWood ERP" -Direction Inbound -LocalPort 8000 -Protocol TCP -Action Allow` |

Verify in an Administrator PowerShell:

```powershell
py --version          # should print 3.10.x or higher
git --version
nssm version          # should print NSSM 2.24 or newer
```

---

## 2. First-time install

### 2.1 Drop the code

Pick a stable path (avoid user-profile folders so the service doesn't break
on profile cleanup). Recommended: `D:\PVWood\erp`.

```powershell
cd D:\PVWood
git clone <your-repo-url> erp
cd erp
```

### 2.2 Configure environment

```powershell
Copy-Item .env.example .env
notepad .env
```

Fill in:
- `ANTHROPIC_API_KEY` (required for Factory Assistant + daily reports; rest of the ERP works without)
- `HOST=0.0.0.0` (default; LAN-accessible)
- `PORT=8000` (or change if 8000 is taken)
- `DB_PATH=` / `DOCS_DIR=` / `LOG_DIR=` / `BACKUP_DIR=` (override only if you want them on a different drive)
- `CORS_ORIGINS=http://localhost:8000,http://127.0.0.1:8000,http://<server-lan-name>:8000` (add the LAN hostname or IP your users will hit)

### 2.3 Install Python dependencies + seed the DB

Run the existing helper (it's idempotent — safe to re-run):

```powershell
.\start.bat
```

…and let it install deps + run the seed. **Stop it with Ctrl+C** once you see *"Starting ERP server"* — the service install in the next step is the real way to run it. `start.bat` itself is for ad-hoc dev only.

### 2.4 Register the Windows service

From an Administrator PowerShell:

```powershell
.\scripts\install_service.ps1
```

What happens:
- Service `PVWoodERP` is registered with NSSM.
- Auto-starts on boot.
- Restarts on crash with a 5 s cooldown.
- Logs to `logs\service-stdout.log` and `logs\service-stderr.log`, rotated at 5 MB or daily.
- Working dir set to `execution\` so `uvicorn main:app` resolves.

Verify:

```powershell
Get-Service PVWoodERP            # should show Running
curl http://localhost:8000/api/health
```

### 2.5 Schedule daily backups

```powershell
.\scripts\install_backup_task.ps1
```

What happens:
- Task `PVWoodERP-DailyBackup` registered.
- Fires daily at 02:00.
- Runs as SYSTEM so it works without anyone being logged in.
- Snapshots go to `backups\erp-YYYYMMDD-HHMMSS.db` via SQLite's online backup API — **the ERP service does NOT need to be stopped**.
- Keeps the newest 30 snapshots; older are auto-pruned.
- Triggers a smoke-test run immediately so you can verify it works without waiting until tomorrow.

Verify:

```powershell
Get-ScheduledTask -TaskName PVWoodERP-DailyBackup
Get-ChildItem .\backups\erp-*.db | Sort-Object LastWriteTime -Descending | Select-Object -First 3
```

### 2.6 First-time user setup

Open `http://<server>:8000/admin` from any browser on the LAN. Sign in with the seed admin user (`admin` / `admin`) and **immediately**:
1. Change the admin password (top-right user pill → My Profile).
2. Create real user accounts for each operator.
3. Delete or disable the seed `admin` user once a real Managerial user exists.

---

## 3. Updating to a new version

### Quick path — one command

From an **Administrator** PowerShell in the repo clone:

```powershell
cd D:\PVWood\erp
.\scripts\deploy.ps1
```

`deploy.ps1` does the whole cycle: snapshot the DB → `git pull --ff-only` →
restart the service → poll `/api/health` → print the deployed version. It
never touches `erp.db`, `.env`, or `docs_storage/` (all gitignored, so they
survive every pull), and DB schema migrations run automatically on restart.
Flags: `-SkipBackup`, `-ServiceName`, `-Port`.

### Manual path (what the script automates)

```powershell
cd D:\PVWood\erp

# 1. Snapshot before the update (paranoia is cheap).
py -3 scripts\backup_db.py

# 2. Pull new code.
git fetch
git status                # confirm clean working tree
git pull --ff-only

# 3. Refresh the service config (idempotent — handles new flags etc.).
#    Must be Administrator PowerShell.
.\scripts\install_service.ps1

# 4. Verify.
Get-Service PVWoodERP
curl http://localhost:8000/api/health
curl http://localhost:8000/api/version
```

### One-time: convert an old archive (.7z) install to a git clone

If the server's current install came from an uploaded `.7z` (not a git
clone), do this **once** to switch it onto `git pull` deploys. Your data
(`erp.db`, `.env`, `docs_storage/`) is preserved because it's gitignored.

```powershell
# Stop the service so nothing has the DB open.
Stop-Service PVWoodERP -ErrorAction SilentlyContinue

cd D:\PVWood
git clone https://github.com/itpvwood-hue/pv-erp.git erp-git
cd erp-git

# Bring the live data over from the old install (adjust the old path).
Copy-Item ..\erp\.env            .\.env            -Force
Copy-Item ..\erp\erp.db          .\erp.db          -Force
Copy-Item ..\erp\docs_storage\*  .\docs_storage\   -Recurse -Force -ErrorAction SilentlyContinue

# Point the service at this clone and start it.
.\scripts\install_service.ps1
.\scripts\deploy.ps1            # verifies health + version

# Once verified, the old D:\PVWood\erp folder can be archived/removed.
```

From then on, every release is just `.\scripts\deploy.ps1`.

If `git pull` fails because the working tree has untracked changes (rare on a server, but possible if someone edited `.env` or `erp.db` lives in the repo path), stash or remove them first.

### Rollback

```powershell
git log --oneline -10                # find the previous good commit
Stop-Service PVWoodERP
git reset --hard <commit-sha>
Restart-Service PVWoodERP            # restart with the rolled-back code
```

If the rollback also needs to undo a DB schema change, restore from a pre-update snapshot:

```powershell
Stop-Service PVWoodERP
Copy-Item .\backups\erp-<timestamp>.db .\erp.db -Force
Restart-Service PVWoodERP
```

---

## 4. Operating the live service

| Action | Command |
|---|---|
| Status | `Get-Service PVWoodERP` |
| Start | `Start-Service PVWoodERP` |
| Stop | `Stop-Service PVWoodERP` |
| Restart | `Restart-Service PVWoodERP` |
| Inspect config | `nssm edit PVWoodERP` (GUI) |
| Tail stdout | `Get-Content logs\service-stdout.log -Tail 50 -Wait` |
| Tail stderr | `Get-Content logs\service-stderr.log -Tail 50 -Wait` |
| Tail application log | `Get-Content logs\server.log -Tail 50 -Wait` |
| Health check | `curl http://localhost:8000/api/health` |
| List backups | `Get-ChildItem .\backups\erp-*.db \| Sort-Object LastWriteTime -Descending` |
| Force a backup now | `Start-ScheduledTask -TaskName PVWoodERP-DailyBackup` or `py -3 scripts\backup_db.py` |
| Remove service | `.\scripts\uninstall_service.ps1` (DB and backups untouched) |

### `/api/health` JSON

```json
{
  "ok": true,
  "version": "2.16.0",
  "uptime_s": 12345,
  "now": "2026-06-09T10:51:33",
  "db_reachable": true,
  "disk_free_mb": 83369.2
}
```

A monitoring tool can poll this every minute. `ok=false` means *either* the DB is unreachable *or* disk free is below 500 MB.

---

## 5. Common issues

### "Service registered but won't start"

```powershell
Get-Content logs\service-stderr.log -Tail 80
```

Most-common causes:
- `ANTHROPIC_API_KEY` missing — comment out by setting it to `your_anthropic_api_key_here`; the rest of the ERP runs fine without it.
- Wrong `PORT` (taken by something else) — check `netstat -ano | findstr :8000`.
- `DB_PATH` points at a directory the SYSTEM account can't write to.

### "Audit script fails"

The audit (`python tests/test_audit.py`) connects to `http://127.0.0.1:8000`. It needs the service to be running. Start the service first.

### "Page X is missing for user Y"

Check `ROLE_PAGES` in `frontend/index.html` (search for `const ROLE_PAGES`). Each role's allowed pages are explicit; a missing page is intentional, not a bug.

### "Can't reach ERP from a LAN client"

```powershell
# Confirm the service is listening on all interfaces
netstat -ano | findstr :8000      # should show 0.0.0.0:8000 LISTENING

# Confirm the firewall is open
Get-NetFirewallRule -DisplayName "PVWood ERP"
Test-NetConnection -ComputerName <server> -Port 8000   # from the client
```

### "Backup task never fires"

```powershell
Get-ScheduledTaskInfo -TaskName PVWoodERP-DailyBackup
```

Look at `LastRunTime` and `LastTaskResult` (0 = success). If `LastTaskResult` is nonzero, run the action manually to see the error:

```powershell
py -3 scripts\backup_db.py
```

---

## 6. Where everything lives

```
D:\PVWood\erp\                       <- $projectRoot (everywhere below)
├── .env                              your secrets (NOT committed)
├── erp.db                            live SQLite database
├── erp.db-shm, erp.db-wal            transient — disappear on clean shutdown
├── backups\                          daily snapshots (and any ad-hoc)
│   ├── erp-20260609-020000.db
│   └── erp-20260608-020000.db
├── docs_storage\                     supplier PO PDFs etc.
├── logs\
│   ├── server.log                    application log (FastAPI + uvicorn + project)
│   ├── service-stdout.log            NSSM-captured stdout (rotated 5 MB / daily)
│   └── service-stderr.log            NSSM-captured stderr
├── execution\
│   ├── main.py                       FastAPI app
│   ├── database.py                   schema + queries + migrations
│   ├── config.py                     env-driven config (DB_PATH, LOG_PATH, …)
│   ├── factory_assistant.py          Claude tool-use agent
│   └── version.py                    VERSION + CHANGELOG
├── frontend\
│   ├── index.html                    SPA shell (~5.8k lines)
│   ├── admin.html, finance.html      legacy portal entry points
│   ├── css\styles.css                extracted CSS
│   └── js\
│       ├── i18n.js, core.js, nav.js, auth.js     shared
│       └── portal_warehouse.js / planning.js / accounting.js / admin.js
│                                     loaded on demand by auth.js based
│                                     on the signed-in user's role
├── scripts\
│   ├── install_service.ps1           NSSM-based Windows service install
│   ├── uninstall_service.ps1         service removal
│   ├── install_backup_task.ps1       Task Scheduler install for daily backup
│   ├── backup_db.py                  the actual backup logic (online SQLite)
│   ├── seed_data.py                  first-run DB seed (called by start.bat)
│   └── bom_import_new.py             one-off CSV importers
├── tests\
│   └── test_audit.py                 37 endpoint smoke tests
└── DEPLOY.md                         this file
```

---

## 7. Versioning

Truth lives in `execution/version.py`. Display:
- **Browser**: bottom of the sidebar — click for the full changelog modal.
- **API**: `GET /api/version` → `{ name, version, build_date, changelog[] }`.

Scheme: **MAJOR.MINOR.PATCH**
- MAJOR — breaking schema or API change (rare).
- MINOR — new feature / module, backwards-compatible.
- PATCH — bug fix / small UX tweak.

To ship a change:
1. Bump `VERSION` + `BUILD_DATE` in `execution/version.py`.
2. Prepend a one-line entry to `CHANGELOG`.
3. Commit, push, and on the server: `git pull` + `.\scripts\install_service.ps1` to restart.
