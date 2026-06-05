"""
Migration: Auth + Supply Warehouse Module
Creates: users, user_sessions, user_departments,
         consumable_request, dept_cost_ledger
Seeds:   4 default accounts (one per role)
"""
import sys, os, sqlite3, hashlib
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.dirname(__file__))
from database import DB_PATH

def _hash(pw): return hashlib.sha256(pw.encode('utf-8')).hexdigest()

conn = sqlite3.connect(DB_PATH)
conn.execute("PRAGMA journal_mode=WAL")
conn.execute("PRAGMA foreign_keys = OFF")

DDL = """
-- ── Auth tables ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS users (
    user_id      TEXT PRIMARY KEY,
    username     TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role         TEXT NOT NULL CHECK(role IN (
                    'MANAGERIAL','PRODUCTION_PLANNING',
                    'DEPARTMENT_LEADER','WAREHOUSE')),
    display_name TEXT NOT NULL,
    active       INTEGER DEFAULT 1,
    created_at   TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS user_sessions (
    token      TEXT PRIMARY KEY,
    user_id    TEXT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    expires_at TEXT NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS user_departments (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    TEXT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    department TEXT NOT NULL,
    line_id    TEXT,
    UNIQUE(user_id, department, line_id)
);

-- ── Supply Warehouse tables ───────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS consumable_request (
    request_id    TEXT PRIMARY KEY,
    requested_by  TEXT NOT NULL REFERENCES users(user_id),
    department    TEXT NOT NULL,
    line_id       TEXT,
    material_id   INTEGER NOT NULL REFERENCES materials(id),
    qty_requested REAL NOT NULL,
    qty_fulfilled REAL DEFAULT 0,
    status        TEXT DEFAULT 'PENDING'
                  CHECK(status IN ('PENDING','PARTIAL','FULFILLED','CANCELLED')),
    notes         TEXT,
    created_at    TEXT DEFAULT CURRENT_TIMESTAMP,
    fulfilled_by  TEXT REFERENCES users(user_id),
    fulfilled_at  TEXT
);

CREATE TABLE IF NOT EXISTS dept_cost_ledger (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    department  TEXT NOT NULL,
    line_id     TEXT,
    month_year  TEXT NOT NULL,          -- 'YYYY-MM'
    material_id INTEGER NOT NULL REFERENCES materials(id),
    qty         REAL NOT NULL,
    unit_cost   REAL NOT NULL,
    total_cost  REAL NOT NULL,
    request_id  TEXT REFERENCES consumable_request(request_id),
    created_at  TEXT DEFAULT CURRENT_TIMESTAMP
);
"""

conn.executescript(DDL)

# ── Seed default accounts ──────────────────────────────────────────────────────
DEFAULTS = [
    ('USR-000001', 'admin',     _hash('admin123'),     'MANAGERIAL',           'Administrator'),
    ('USR-000002', 'planner',   _hash('planner123'),   'PRODUCTION_PLANNING',  'Production Planner'),
    ('USR-000003', 'leader',    _hash('leader123'),    'DEPARTMENT_LEADER',    'Dept Leader (Demo)'),
    ('USR-000004', 'warehouse', _hash('warehouse123'), 'WAREHOUSE',            'Warehouse Manager'),
]
for row in DEFAULTS:
    try:
        conn.execute(
            "INSERT OR IGNORE INTO users "
            "(user_id,username,password_hash,role,display_name) VALUES (?,?,?,?,?)",
            row
        )
        print(f"  OK {row[1]} / {row[0]}")
    except Exception as e:
        print(f"  skip {row[1]}: {e}")

conn.commit()
conn.close()

print("\nAuth + Supply Warehouse migration complete.")
print("\nDefault accounts:")
print("  admin       / admin123     -> MANAGERIAL")
print("  planner     / planner123   -> PRODUCTION_PLANNING")
print("  leader      / leader123    -> DEPARTMENT_LEADER")
print("  warehouse   / warehouse123 -> WAREHOUSE")
print("\nCreate real accounts via User Management page (admin role).")
