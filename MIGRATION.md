# PVWood ERP — Local Server Migration Guide

This document explains what to copy, where it lives, and how to start the
ERP on a different machine (e.g. a dedicated office server).

---

## 1. Application version

The currently-deployed version is the single source of truth in
`execution/version.py`:

```python
VERSION    = "2.1.0"
BUILD_DATE = "2026-05-27"
```

Two ways to read it at runtime:

- **In the browser**: any logged-in user — bottom of the sidebar shows
  `v2.1.0 · 2026-05-27`. Click to see the full release history.
- **From the API**: `GET /api/version` returns `{name, version, build_date,
  patch, minor, major, today, changelog[]}`.

The full changelog also lives at the bottom of `execution/version.py`. When
shipping a change, bump `VERSION` + `BUILD_DATE` and add a one-line entry to
the top of `CHANGELOG`.

Versioning scheme: **MAJOR.MINOR.PATCH**

| Bump   | When                                                          |
|--------|---------------------------------------------------------------|
| MAJOR  | Breaking schema/API change (rare).                            |
| MINOR  | New feature / module, backwards-compatible.                   |
| PATCH  | Bug fix / small UX tweak. Bump for every shipped change.      |

---

## 2. Where the database lives

The ERP uses **SQLite** in WAL mode. The database is **one file** plus two
companion files that exist while the server is running:

```
<project root>/
  erp.db          ← main database file (the only file with permanent data)
  erp.db-wal      ← write-ahead log (transient — disappears on clean shutdown)
  erp.db-shm      ← shared-memory index (transient)
```

**Absolute path on the current machine**:

```
C:\Users\PV_Natthapat\Desktop\Calude ERP\erp.db
```

The path is defined in **`execution/database.py`** line 8:

```python
DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'erp.db')
```

i.e. always one directory above `execution/`. Move the project folder and
the DB path stays correct automatically — no config edit needed.

### Backups

Because SQLite is a single file, a backup is just a copy of `erp.db`. Do this
**while the server is stopped** to avoid copying a partially-flushed WAL:

```powershell
# Stop server first (Ctrl+C in the uvicorn terminal)
Copy-Item "erp.db" "backups\erp-$(Get-Date -Format yyyyMMdd-HHmmss).db"
```

For a **live (running-server) backup**, use SQLite's online backup API —
this script does it safely:

```powershell
python -c "import sqlite3; src=sqlite3.connect('erp.db'); dst=sqlite3.connect('backups/erp-live.db'); src.backup(dst); src.close(); dst.close()"
```

---

## 3. Migrating to a new server

### What to copy

Copy the **entire project folder** to the new machine — the layout matters
because relative paths inside the code expect `erp.db` to sit next to
`execution/`:

```
Calude ERP/
├── erp.db                 ← THE DATA (most important)
├── execution/             ← Python backend
├── frontend/              ← HTML/JS/CSS + /static/assets/*.svg
├── logs/                  ← server logs (rotates; safe to leave behind)
├── requirements.txt       ← Python deps (create if missing — see below)
├── MIGRATION.md           ← this file
└── start.bat              ← Windows launcher (already in the project)
```

Do **not** copy `__pycache__/`, `.pyc` files, or the `erp.db-wal` /
`erp.db-shm` files (recreated on first start).

### Prerequisites on the new server

- **Python 3.10+** (3.11 / 3.12 / 3.14 all tested).
- **pip install** the runtime deps:

```powershell
pip install fastapi uvicorn pydantic
```

(If a `requirements.txt` exists, prefer `pip install -r requirements.txt`.)

### First start on the new machine

From the project root:

```powershell
python -m uvicorn execution.main:app --host 0.0.0.0 --port 8000
```

- `--host 0.0.0.0` makes the server reachable from other machines on the LAN.
  Use `127.0.0.1` if you only want localhost access.
- `--port 8000` is the default — change to `--port 80` for "no port in URL"
  on the LAN (requires admin/root on the host).

Verify it's up:

```powershell
curl http://localhost:8000/api/version
```

Should return something like:

```json
{"name":"PVWood ERP","version":"2.1.0","build_date":"2026-05-27", ...}
```

### Auto-start on boot (Windows)

Easiest path: **Task Scheduler** → Create Basic Task → trigger "When the
computer starts" → action "Start a program":

- Program: `python`
- Arguments: `-m uvicorn execution.main:app --host 0.0.0.0 --port 8000`
- Start in: `C:\Path\To\Calude ERP`

For a more robust setup, install **NSSM** (Non-Sucking Service Manager) and
register uvicorn as a Windows service — survives crashes + restarts on
reboot.

---

## 4. Logs — where they are and how to read them

All server output (uvicorn requests, exceptions, application info) lands in:

```
<project root>/logs/server.log
```

The log **rotates at 5 MB**, keeping the 5 most recent files
(`server.log`, `server.log.1`, … `server.log.5`).

### Accessing logs from the Admin Portal

When you have a working browser:

1. Sign in to the Admin Portal at `/admin`.
2. Click **Server Logs** in the sidebar.
3. Pick how many lines to show (100 / 200 / 500 / 2000 / 5000).
4. **Copy All** → paste into chat to report an error.
5. **Download .log** → save a timestamped copy.
6. Toggle **auto-refresh 10 s** to watch logs live (useful while reproducing
   a bug).

The endpoint is `GET /api/admin/logs/tail?n=<lines>` if you want to script it.

### Accessing logs from the command line (no browser)

```powershell
# Last 200 lines
Get-Content "logs\server.log" -Tail 200

# Live tail (Ctrl+C to stop)
Get-Content "logs\server.log" -Wait -Tail 50
```

---

## 5. Quick-reference: file locations on this machine

| What                | Path                                                       |
|---------------------|------------------------------------------------------------|
| **Database**        | `C:\Users\PV_Natthapat\Desktop\Calude ERP\erp.db`          |
| Project root        | `C:\Users\PV_Natthapat\Desktop\Calude ERP\`                |
| Backend code        | `C:\Users\PV_Natthapat\Desktop\Calude ERP\execution\`      |
| Frontend code       | `C:\Users\PV_Natthapat\Desktop\Calude ERP\frontend\`       |
| Logo SVGs           | `C:\Users\PV_Natthapat\Desktop\Calude ERP\frontend\assets\`|
| **Logs**            | `C:\Users\PV_Natthapat\Desktop\Calude ERP\logs\server.log` |
| Version file        | `C:\Users\PV_Natthapat\Desktop\Calude ERP\execution\version.py` |

---

## 6. Sending error reports

When something breaks and you want a fix:

1. Reproduce the error (do the action that fails).
2. **Admin Portal → Server Logs → Copy All** (or download the .log file).
3. Paste the log output in chat along with:
   - what page / module you were on
   - what action you tried
   - what you saw (screenshot is great)
   - the version shown in the sidebar (e.g. `v2.1.0`)

That gives the maintainer enough to diagnose without remoting into your host.
