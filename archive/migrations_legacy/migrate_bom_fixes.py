"""
migrate_bom_fixes.py
--------------------
1. Add thickness_mm / width_mm / length_mm / auto_glue_code to materials
2. Change bom_lines UNIQUE(sku_id, material_id) → UNIQUE(sku_id, seq)
   so the same glue formula can be used for both face and back slots.
   Drops and recreates the 3 views that reference bom_lines.
"""
import sqlite3, sys
from pathlib import Path

DB = Path(__file__).parent.parent / 'erp.db'

CORE_BOM_VIEW = """
CREATE VIEW core_bom AS
    SELECT s.code AS sku_code, s.name AS sku_name, s.pallet_qty,
        bl.seq, m.code AS mat_code, m.name_th, m.name AS mat_name,
        m.unit, m.price AS unit_price,
        CASE WHEN bl.usage_g_per_face IS NOT NULL THEN s.pallet_qty
             ELSE COALESCE(bl.qty_override, s.pallet_qty) END AS qty,
        CASE WHEN bl.usage_g_per_face IS NOT NULL
             THEN COALESCE(bl.qty_unit,"g/face")
             ELSE COALESCE(bl.qty_unit,m.unit) END AS qty_unit,
        bl.usage_g_per_face,
        ROUND(CASE WHEN bl.usage_g_per_face IS NOT NULL
            THEN m.price * (bl.usage_g_per_face / 1000.0) * s.pallet_qty
            ELSE m.price * COALESCE(bl.qty_override, s.pallet_qty) END, 4) AS line_cost,
        sp.name AS supplier,
        bl.id   AS bom_line_id
    FROM bom_lines bl
    JOIN skus       s  ON s.id  = bl.sku_id
    JOIN materials  m  ON m.id  = bl.material_id
    JOIN bom_groups bg ON bg.id = bl.group_id
    LEFT JOIN suppliers sp ON sp.id = m.supplier_id
    ORDER BY s.code, bl.seq
"""

BOM_FULL_VIEW = """
CREATE VIEW bom_full AS
    SELECT s.code AS sku_code, s.name AS sku_name, s.pallet_qty,
        "Core Materials" AS section,
        cb.seq, cb.mat_code, cb.mat_name, cb.unit_price, cb.qty, cb.qty_unit,
        cb.usage_g_per_face, cb.line_cost, cb.supplier
    FROM core_bom cb
    JOIN skus s ON s.code = cb.sku_code
    UNION ALL
    SELECT s.code, s.name, s.pallet_qty, "Packing" AS section,
        pb.seq, pb.mat_code, pb.mat_name, pb.unit_price, pb.qty, pb.qty_unit,
        NULL, pb.line_cost, pb.supplier
    FROM skus s
    JOIN packing_skus ps ON ps.id = s.packing_sku_id
    JOIN packing_bom  pb ON pb.packing_sku_code = ps.code
    ORDER BY sku_code, section DESC, seq
"""

BOM_COST_VIEW = """
CREATE VIEW bom_cost_summary AS
    SELECT sku_code, sku_name, pallet_qty, section,
        ROUND(SUM(line_cost), 4) AS section_total
    FROM bom_full
    GROUP BY sku_code, section
"""

conn = sqlite3.connect(DB)
conn.execute('PRAGMA journal_mode=WAL')
conn.execute('PRAGMA foreign_keys=OFF')

# ── 1. Add new columns to materials ───────────────────────────
for col, coldef in [
    ('thickness_mm',  'REAL'),
    ('width_mm',      'REAL'),
    ('length_mm',     'REAL'),
    ('auto_glue_code','TEXT'),
]:
    try:
        conn.execute(f'ALTER TABLE materials ADD COLUMN {col} {coldef}')
        print(f'  + materials.{col} added')
    except Exception:
        print(f'  · materials.{col} already exists')

conn.commit()

# ── 2. Drop views that reference bom_lines ────────────────────
for vname in ['bom_cost_summary', 'bom_full', 'core_bom']:
    conn.execute(f'DROP VIEW IF EXISTS {vname}')
    print(f'  dropped view {vname}')

# ── 3. Recreate bom_lines with UNIQUE(sku_id, seq) ────────────
has_new = conn.execute(
    "SELECT name FROM sqlite_master WHERE type='table' AND name='bom_lines_new'"
).fetchone()
has_old = conn.execute(
    "SELECT name FROM sqlite_master WHERE type='table' AND name='bom_lines'"
).fetchone()

if has_old:
    if has_new:
        conn.execute('DROP TABLE bom_lines_new')
    conn.execute("""
        CREATE TABLE bom_lines_new (
            id                INTEGER PRIMARY KEY AUTOINCREMENT,
            sku_id            INTEGER NOT NULL REFERENCES skus(id)       ON DELETE CASCADE,
            material_id       INTEGER NOT NULL REFERENCES materials(id)  ON DELETE RESTRICT,
            group_id          INTEGER NOT NULL REFERENCES bom_groups(id) ON DELETE RESTRICT,
            seq               INTEGER NOT NULL DEFAULT 0,
            qty_override      REAL,
            usage_g_per_face  REAL,
            qty_unit          TEXT,
            notes             TEXT,
            created_at        TEXT    NOT NULL DEFAULT (datetime('now')),
            updated_at        TEXT    NOT NULL DEFAULT (datetime('now')),
            UNIQUE (sku_id, seq),
            CHECK (NOT (qty_override IS NOT NULL AND usage_g_per_face IS NOT NULL))
        )
    """)
    count = conn.execute('SELECT count(*) FROM bom_lines').fetchone()[0]
    conn.execute("""
        INSERT OR IGNORE INTO bom_lines_new
        SELECT id, sku_id, material_id, group_id, seq,
               qty_override, usage_g_per_face, qty_unit, notes,
               created_at, updated_at
        FROM bom_lines ORDER BY id
    """)
    migrated = conn.execute('SELECT count(*) FROM bom_lines_new').fetchone()[0]
    conn.execute('DROP TABLE bom_lines')
    conn.execute('ALTER TABLE bom_lines_new RENAME TO bom_lines')
    print(f'  bom_lines: {migrated}/{count} rows migrated — now UNIQUE(sku_id, seq)')
elif has_new:
    conn.execute('ALTER TABLE bom_lines_new RENAME TO bom_lines')
    print('  bom_lines_new renamed to bom_lines')
else:
    print('  bom_lines not found — skipping')

# ── 4. Recreate views ─────────────────────────────────────────
conn.execute(CORE_BOM_VIEW)
conn.execute(BOM_FULL_VIEW)
conn.execute(BOM_COST_VIEW)
print('  views recreated: core_bom, bom_full, bom_cost_summary')

conn.commit()
conn.execute('PRAGMA foreign_keys=ON')
conn.close()
print('Migration complete.')
