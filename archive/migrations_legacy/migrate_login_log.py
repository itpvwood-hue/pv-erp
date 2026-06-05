"""Migration: Add login_log table for backend audit trail."""
import sqlite3, os, sys
sys.stdout.reconfigure(encoding='utf-8')

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'erp.db')
conn = sqlite3.connect(DB_PATH)
try:
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS login_log (
            log_id     TEXT PRIMARY KEY,
            user_id    TEXT NOT NULL REFERENCES users(user_id),
            username   TEXT NOT NULL,
            role       TEXT NOT NULL,
            ip_address TEXT,
            logged_at  TEXT NOT NULL DEFAULT (datetime('now'))
        );
        CREATE INDEX IF NOT EXISTS idx_login_log_user ON login_log(user_id);
        CREATE INDEX IF NOT EXISTS idx_login_log_at   ON login_log(logged_at);
    """)
    conn.commit()
    print("login_log table created.")
    row = conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='login_log'").fetchone()
    print(row[0])
except Exception as e:
    print("ERROR:", e)
finally:
    conn.close()
