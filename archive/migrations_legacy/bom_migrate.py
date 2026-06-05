"""
bom_migrate.py — PV ERP BOM schema migration + data import
Adds the proper BOM tables to the existing erp.db without breaking anything.
Run once: python bom_migrate.py
"""

import sqlite3, csv, sys
from pathlib import Path

DB_PATH   = Path(__file__).parent.parent / "erp.db"
DATA_DIR  = Path("C:/Users/PV_Natthapat/Downloads/files_extracted/bom_migration/pv_erp_migration/data")

# ── Connect ────────────────────────────────────────────────────────────────────
conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row
conn.execute("PRAGMA journal_mode = WAL")
conn.execute("PRAGMA foreign_keys = ON")

print(f"Connected to {DB_PATH}")

# ── Step 1: Extend existing materials table ────────────────────────────────────
print("Step 1: Extending materials table ...")
for sql in [
    "ALTER TABLE materials ADD COLUMN name_th TEXT DEFAULT ''",
    "ALTER TABLE materials ADD COLUMN name_zh TEXT DEFAULT ''",
    "ALTER TABLE materials ADD COLUMN is_active INTEGER NOT NULL DEFAULT 1",
    "ALTER TABLE materials ADD COLUMN supplier_id INTEGER REFERENCES suppliers(id) ON DELETE SET NULL",
    "ALTER TABLE materials ADD COLUMN price REAL DEFAULT 0",
]:
    try:
        conn.execute(sql)
        conn.commit()
        print(f"  OK: {sql[:60]}")
    except Exception:
        pass  # column already exists

# Sync price ← unit_cost for existing rows
conn.execute("UPDATE materials SET price = unit_cost WHERE price = 0 AND unit_cost IS NOT NULL")
conn.commit()

# ── Step 2: Create new tables ─────────────────────────────────────────────────
print("Step 2: Creating new BOM tables ...")

conn.executescript("""
PRAGMA foreign_keys = OFF;

CREATE TABLE IF NOT EXISTS suppliers (
    id    INTEGER PRIMARY KEY AUTOINCREMENT,
    name  TEXT    NOT NULL UNIQUE,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS bom_groups (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT    NOT NULL,
    calc_method TEXT    NOT NULL CHECK (calc_method IN ('per_sheet','per_pallet')),
    sort_order  INTEGER NOT NULL DEFAULT 0,
    notes       TEXT
);

CREATE TABLE IF NOT EXISTS compound_skus (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    code       TEXT    NOT NULL UNIQUE,
    name       TEXT    NOT NULL,
    batch_kg   REAL    NOT NULL CHECK (batch_kg > 0),
    notes      TEXT,
    is_active  INTEGER NOT NULL DEFAULT 1,
    created_at TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS compound_lines (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    compound_sku_id  INTEGER NOT NULL REFERENCES compound_skus(id) ON DELETE CASCADE,
    material_id      INTEGER NOT NULL REFERENCES materials(id)      ON DELETE RESTRICT,
    ratio            REAL    NOT NULL CHECK (ratio > 0 AND ratio <= 1),
    unit             TEXT    NOT NULL DEFAULT 'kg',
    notes            TEXT,
    created_at       TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at       TEXT    NOT NULL DEFAULT (datetime('now')),
    UNIQUE (compound_sku_id, material_id)
);

CREATE TABLE IF NOT EXISTS packing_skus (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    code       TEXT    NOT NULL UNIQUE,
    name       TEXT    NOT NULL,
    customer   TEXT,
    notes      TEXT,
    is_active  INTEGER NOT NULL DEFAULT 1,
    created_at TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS packing_lines (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    packing_sku_id  INTEGER NOT NULL REFERENCES packing_skus(id) ON DELETE CASCADE,
    material_id     INTEGER NOT NULL REFERENCES materials(id)     ON DELETE RESTRICT,
    seq             INTEGER NOT NULL DEFAULT 0,
    qty             REAL    NOT NULL DEFAULT 1,
    qty_unit        TEXT,
    notes           TEXT,
    created_at      TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT    NOT NULL DEFAULT (datetime('now')),
    UNIQUE (packing_sku_id, material_id)
);

CREATE TABLE IF NOT EXISTS skus (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    code            TEXT    NOT NULL UNIQUE,
    name            TEXT    NOT NULL,
    thickness_mm    REAL,
    width_mm        REAL,
    length_mm       REAL,
    pallet_qty      INTEGER NOT NULL DEFAULT 1,
    packing_sku_id  INTEGER REFERENCES packing_skus(id) ON DELETE SET NULL,
    approved_date   TEXT,
    revision        INTEGER NOT NULL DEFAULT 0,
    is_active       INTEGER NOT NULL DEFAULT 1,
    notes           TEXT,
    created_at      TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS bom_lines (
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
    UNIQUE (sku_id, material_id),
    CHECK (NOT (qty_override IS NOT NULL AND usage_g_per_face IS NOT NULL))
);

CREATE INDEX IF NOT EXISTS idx_skus_code        ON skus(code);
CREATE INDEX IF NOT EXISTS idx_bom_lines_sku    ON bom_lines(sku_id);
CREATE INDEX IF NOT EXISTS idx_bom_lines_mat    ON bom_lines(material_id);
CREATE INDEX IF NOT EXISTS idx_compound_lines_c ON compound_lines(compound_sku_id);
CREATE INDEX IF NOT EXISTS idx_packing_lines_p  ON packing_lines(packing_sku_id);
CREATE INDEX IF NOT EXISTS idx_materials_code   ON materials(code);

PRAGMA foreign_keys = ON;
""")
conn.commit()
print("  Tables created.")

# ── Step 3: Seed bom_groups ────────────────────────────────────────────────────
print("Step 3: Seeding bom_groups ...")
conn.execute("INSERT OR IGNORE INTO bom_groups (id,name,calc_method,sort_order,notes) VALUES (1,'Core Materials','per_sheet',1,'Board + veneers + glues')")
conn.execute("INSERT OR IGNORE INTO bom_groups (id,name,calc_method,sort_order,notes) VALUES (2,'Packing','per_pallet',2,'Via packing_sku_id on skus')")
conn.commit()

# ── Step 4: Create views ───────────────────────────────────────────────────────
print("Step 4: Creating views ...")
views = [
    ("compound_cost", """
        SELECT cs.id, cs.code, cs.name, cs.batch_kg,
            ROUND(SUM(m.price * cl.ratio), 6)               AS cost_per_kg_mixed,
            ROUND(SUM(m.price * cl.ratio) * cs.batch_kg, 2) AS typical_batch_cost
        FROM compound_skus cs
        JOIN compound_lines cl ON cl.compound_sku_id = cs.id
        JOIN materials       m  ON m.id = cl.material_id
        GROUP BY cs.id
    """),
    ("core_bom", """
        SELECT s.code AS sku_code, s.name AS sku_name, s.pallet_qty,
            bl.seq, m.code AS mat_code, m.name_th, m.name AS mat_name,
            m.unit, m.price AS unit_price,
            CASE WHEN bl.usage_g_per_face IS NOT NULL THEN s.pallet_qty
                 ELSE COALESCE(bl.qty_override, s.pallet_qty) END AS qty,
            CASE WHEN bl.usage_g_per_face IS NOT NULL
                 THEN COALESCE(bl.qty_unit,'g/face')
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
    """),
    ("packing_bom", """
        SELECT ps.code AS packing_sku_code, ps.name AS packing_sku_name,
            pl.seq, m.code AS mat_code, m.name_th, m.name AS mat_name,
            m.unit, m.price AS unit_price,
            pl.qty, pl.qty_unit,
            ROUND(m.price * pl.qty, 4) AS line_cost,
            sp.name AS supplier, pl.id AS packing_line_id
        FROM packing_lines pl
        JOIN packing_skus ps ON ps.id = pl.packing_sku_id
        JOIN materials    m  ON m.id  = pl.material_id
        LEFT JOIN suppliers sp ON sp.id = m.supplier_id
        ORDER BY ps.code, pl.seq
    """),
    ("bom_full", """
        SELECT s.code AS sku_code, s.name AS sku_name, s.pallet_qty,
            'Core Materials' AS section,
            cb.seq, cb.mat_code, cb.mat_name, cb.description,
            cb.unit_price, cb.qty, cb.qty_unit, cb.usage_g_per_face,
            cb.line_cost, cb.supplier
        FROM core_bom cb
        JOIN skus s ON s.code = cb.sku_code
        UNION ALL
        SELECT s.code, s.name, s.pallet_qty, 'Packing' AS section,
            pb.seq, pb.mat_code, pb.mat_name, pb.description,
            pb.unit_price, pb.qty, pb.qty_unit, NULL,
            pb.line_cost, pb.supplier
        FROM skus s
        JOIN packing_skus ps ON ps.id = s.packing_sku_id
        JOIN packing_bom  pb ON pb.packing_sku_code = ps.code
        ORDER BY sku_code, section DESC, seq
    """),
    ("bom_cost_summary", """
        SELECT sku_code, sku_name, pallet_qty, section,
            ROUND(SUM(line_cost), 4) AS section_total
        FROM bom_full
        GROUP BY sku_code, section
    """),
]

for name, body in views:
    try:
        conn.execute(f"DROP VIEW IF EXISTS {name}")
        conn.execute(f"CREATE VIEW {name} AS {body}")
        print(f"  View {name} OK")
    except Exception as e:
        print(f"  View {name} FAILED: {e}")
conn.commit()

# ── Step 5: Import CSVs ────────────────────────────────────────────────────────

def read_csv(filename):
    path = DATA_DIR / filename
    if not path.exists():
        print(f"  SKIP (not found): {filename}")
        return []
    with open(path, encoding='utf-8-sig') as f:
        return list(csv.DictReader(f))

def clean(v):
    if v is None: return None
    s = str(v).strip()
    return s if s else None

def to_float(v, default=None):
    try: return float(v)
    except: return default

def to_int(v, default=None):
    try: return int(float(v))
    except: return default

# Materials
print("\nStep 5a: Importing materials ...")
rows = read_csv("scraped_materials.csv")
inserted = updated = 0
for row in rows:
    code     = clean(row.get('code'))
    supplier = clean(row.get('supplier'))
    if not code: continue

    sup_id = None
    if supplier:
        conn.execute("INSERT OR IGNORE INTO suppliers (name) VALUES (?)", (supplier,))
        r = conn.execute("SELECT id FROM suppliers WHERE name=?", (supplier,)).fetchone()
        sup_id = r[0] if r else None

    existing = conn.execute("SELECT id FROM materials WHERE code=?", (code,)).fetchone()
    name_th  = clean(row.get('name_th')) or ''
    price    = to_float(row.get('price'), 0)
    unit     = clean(row.get('unit')) or 'sheet'
    desc     = clean(row.get('description')) or ''
    active   = to_int(row.get('is_active'), 1)

    if existing:
        conn.execute("""UPDATE materials SET name_th=?,unit=?,price=?,
            unit_cost=?,supplier_id=?,is_active=? WHERE code=?""",
            (name_th, unit, price, price, sup_id, active, code))
        updated += 1
    else:
        conn.execute("""INSERT INTO materials (code,name,name_th,unit,price,unit_cost,supplier_id,is_active,type)
            VALUES (?,?,?,?,?,?,?,?,?)""",
            (code, name_th or code, name_th, unit, price, price, sup_id, active, 'other'))
        inserted += 1

conn.commit()
print(f"  Materials: +{inserted} inserted, ~{updated} updated")

# Compound SKUs
print("Step 5b: Importing compound_skus ...")
rows = read_csv("scraped_compound_skus.csv")
ins = 0
for row in rows:
    code = clean(row.get('code'))
    if not code: continue
    conn.execute("""INSERT OR REPLACE INTO compound_skus (code,name,batch_kg,notes,is_active)
        VALUES (?,?,?,?,?)""",
        (code, clean(row.get('name')) or code,
         to_float(row.get('batch_kg'), 70),
         clean(row.get('notes')), to_int(row.get('is_active'), 1)))
    ins += 1
conn.commit()
print(f"  Compound SKUs: {ins} upserted")

# Compound Lines
print("Step 5c: Importing compound_lines ...")
rows = read_csv("scraped_compound_lines.csv")
ins = skipped = 0
for row in rows:
    ccode = clean(row.get('compound_sku_code'))
    mcode = clean(row.get('material_code'))
    if not ccode or not mcode: continue
    cr = conn.execute("SELECT id FROM compound_skus WHERE code=?", (ccode,)).fetchone()
    mr = conn.execute("SELECT id FROM materials WHERE code=?", (mcode,)).fetchone()
    if not cr or not mr:
        skipped += 1; continue
    conn.execute("""INSERT OR REPLACE INTO compound_lines (compound_sku_id,material_id,ratio,unit,notes)
        VALUES (?,?,?,?,?)""",
        (cr[0], mr[0], to_float(row.get('ratio'), 0),
         clean(row.get('unit')) or 'kg', clean(row.get('notes'))))
    ins += 1
conn.commit()
# Sync compound cost → materials.price
conn.execute("""
    UPDATE materials SET price = (
        SELECT cost_per_kg_mixed FROM compound_cost
        WHERE compound_cost.code = materials.code
    )
    WHERE code IN (SELECT code FROM compound_cost)
""")
conn.execute("""
    UPDATE materials SET unit_cost = price
    WHERE code IN (SELECT code FROM compound_cost)
""")
conn.commit()
print(f"  Compound lines: {ins} upserted, {skipped} skipped, glue prices synced")

# Packing SKUs
print("Step 5d: Importing packing_skus ...")
rows = read_csv("scraped_packing_skus.csv")
ins = 0
for row in rows:
    code = clean(row.get('code'))
    if not code: continue
    conn.execute("""INSERT OR REPLACE INTO packing_skus (code,name,customer,notes,is_active)
        VALUES (?,?,?,?,?)""",
        (code, clean(row.get('name')) or code, clean(row.get('customer')),
         clean(row.get('notes')), to_int(row.get('is_active'), 1)))
    ins += 1
conn.commit()
print(f"  Packing SKUs: {ins} upserted")

# Packing Lines
print("Step 5e: Importing packing_lines ...")
rows = read_csv("scraped_packing_lines.csv")
ins = skipped = 0
for row in rows:
    pcode = clean(row.get('packing_sku_code'))
    mcode = clean(row.get('material_code'))
    if not pcode or not mcode: continue
    pr = conn.execute("SELECT id FROM packing_skus WHERE code=?", (pcode,)).fetchone()
    mr = conn.execute("SELECT id FROM materials WHERE code=?", (mcode,)).fetchone()
    if not pr or not mr:
        skipped += 1; continue
    conn.execute("""INSERT OR REPLACE INTO packing_lines (packing_sku_id,material_id,seq,qty,qty_unit,notes)
        VALUES (?,?,?,?,?,?)""",
        (pr[0], mr[0], to_int(row.get('seq'), 0), to_float(row.get('qty'), 1),
         clean(row.get('qty_unit')), clean(row.get('notes'))))
    ins += 1
conn.commit()
print(f"  Packing lines: {ins} upserted, {skipped} skipped")

# Board SKUs (skus table)
print("Step 5f: Importing board_skus (skus table) ...")
rows = read_csv("scraped_board_skus.csv")
ins = skipped = 0
for row in rows:
    code = clean(row.get('code'))
    if not code: continue
    pkg_code = clean(row.get('packing_sku_code'))
    pkg_id = None
    if pkg_code:
        pr = conn.execute("SELECT id FROM packing_skus WHERE code=?", (pkg_code,)).fetchone()
        pkg_id = pr[0] if pr else None
    conn.execute("""INSERT OR REPLACE INTO skus
        (code,name,thickness_mm,width_mm,length_mm,pallet_qty,packing_sku_id,approved_date,revision,notes)
        VALUES (?,?,?,?,?,?,?,?,?,?)""",
        (code, clean(row.get('name')) or code,
         to_float(row.get('thickness_mm')), to_float(row.get('width_mm')), to_float(row.get('length_mm')),
         to_int(row.get('pallet_qty'), 1), pkg_id, clean(row.get('approved_date')),
         to_int(row.get('revision'), 0), clean(row.get('notes'))))
    ins += 1
conn.commit()
print(f"  Board SKUs: {ins} upserted")

# BOM Lines
print("Step 5g: Importing bom_lines ...")
rows = read_csv("scraped_bom_lines.csv")
grp_row = conn.execute("SELECT id FROM bom_groups WHERE name='Core Materials'").fetchone()
grp_id  = grp_row[0] if grp_row else 1
ins = skipped = 0
for row in rows:
    sku_code = clean(row.get('sku_code'))
    mat_code = clean(row.get('material_code'))
    if not sku_code or not mat_code: continue
    sr = conn.execute("SELECT id FROM skus WHERE code=?", (sku_code,)).fetchone()
    mr = conn.execute("SELECT id FROM materials WHERE code=?", (mat_code,)).fetchone()
    if not sr or not mr:
        print(f"  WARN: sku={sku_code} mat={mat_code} — one not found, skipping")
        skipped += 1; continue
    qty_ov  = (lambda v: float(v) if v and v.strip() else None)(row.get('qty_override'))
    g_face  = (lambda v: float(v) if v and v.strip() else None)(row.get('usage_g_per_face'))
    conn.execute("""INSERT OR REPLACE INTO bom_lines
        (sku_id,material_id,group_id,seq,qty_override,usage_g_per_face,qty_unit,notes)
        VALUES (?,?,?,?,?,?,?,?)""",
        (sr[0], mr[0], grp_id, to_int(row.get('seq'), 0),
         qty_ov, g_face, clean(row.get('qty_unit')), clean(row.get('notes'))))
    ins += 1
conn.commit()
print(f"  BOM lines: {ins} upserted, {skipped} skipped")

# ── Step 6: Verify ─────────────────────────────────────────────────────────────
print("\nStep 6: Verification ...")
print(f"  materials:     {conn.execute('SELECT COUNT(*) FROM materials').fetchone()[0]}")
print(f"  suppliers:     {conn.execute('SELECT COUNT(*) FROM suppliers').fetchone()[0]}")
print(f"  compound_skus: {conn.execute('SELECT COUNT(*) FROM compound_skus').fetchone()[0]}")
print(f"  compound_lines:{conn.execute('SELECT COUNT(*) FROM compound_lines').fetchone()[0]}")
print(f"  packing_skus:  {conn.execute('SELECT COUNT(*) FROM packing_skus').fetchone()[0]}")
print(f"  packing_lines: {conn.execute('SELECT COUNT(*) FROM packing_lines').fetchone()[0]}")
print(f"  skus:          {conn.execute('SELECT COUNT(*) FROM skus').fetchone()[0]}")
print(f"  bom_lines:     {conn.execute('SELECT COUNT(*) FROM bom_lines').fetchone()[0]}")

# Sample BOM
sample = conn.execute("SELECT * FROM bom_full WHERE sku_code='4WBM30B41'").fetchall()
print(f"\n  Sample BOM (4WBM30B41) — {len(sample)} lines:")
for r in sample:
    print(f"    seq={r['seq']} {r['mat_code']:<14} qty={r['qty']} {r['qty_unit']:<8} cost={r['line_cost']}")

conn.close()
print("\nDone.")
