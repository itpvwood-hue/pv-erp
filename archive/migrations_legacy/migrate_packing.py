"""Migration: Phase 3 — Packing Station (packing_log table)."""
import sys, os, sqlite3
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.dirname(__file__))
from database import DB_PATH

conn = sqlite3.connect(DB_PATH)
conn.execute("PRAGMA journal_mode=WAL")
conn.execute("PRAGMA foreign_keys = OFF")

conn.executescript("""
CREATE TABLE IF NOT EXISTS packing_log (
    pack_id       TEXT PRIMARY KEY,
    batch_id      TEXT NOT NULL REFERENCES prod_batch(batch_id),
    operator_name TEXT,
    table_id      TEXT,
    pcs_in        INTEGER DEFAULT 0,
    pcs_packed    INTEGER DEFAULT 0,
    pcs_held      INTEGER DEFAULT 0,
    cartons_count INTEGER DEFAULT 0,
    packaging_sku TEXT,
    notes         TEXT,
    logged_at     TEXT DEFAULT CURRENT_TIMESTAMP
);
""")

conn.commit()
conn.close()
print("Packing migration complete. Created: packing_log")
