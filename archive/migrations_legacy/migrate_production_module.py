"""
Migration: apply production module schema to erp.db.
Run from the execution/ directory: python migrate_production_module.py
"""
import sqlite3, os, sys
sys.stdout.reconfigure(encoding='utf-8')

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'erp.db')
conn = sqlite3.connect(DB_PATH)
conn.execute("PRAGMA journal_mode = WAL")
# We run creation WITHOUT FK enforcement so the sku view reference doesn't block
conn.execute("PRAGMA foreign_keys = OFF")

print("Applying production module schema...")

conn.executescript("""
-- Bridge: alias our 'skus' table as 'sku' so FK references resolve
CREATE VIEW IF NOT EXISTS sku AS
    SELECT code AS sku_id, name AS sku_name FROM skus WHERE is_active=1;

-- Manufacturing lines (P01/P02/P37)
CREATE TABLE IF NOT EXISTS manufacturing_line (
    line_id   TEXT PRIMARY KEY,
    line_name TEXT NOT NULL,
    active    INTEGER NOT NULL DEFAULT 1
);
INSERT OR IGNORE INTO manufacturing_line (line_id, line_name) VALUES
    ('P01','Production Line 1'),
    ('P02','Production Line 2'),
    ('P37','Production Line 37');

-- Employees
CREATE TABLE IF NOT EXISTS employee (
    emp_id     TEXT PRIMARY KEY,
    emp_name   TEXT NOT NULL,
    department TEXT NOT NULL,
    role       TEXT NOT NULL,
    line_id    TEXT REFERENCES manufacturing_line(line_id),
    active     INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Production tables (laminating / repair physical tables)
CREATE TABLE IF NOT EXISTS production_table (
    table_id   TEXT PRIMARY KEY,
    table_type TEXT NOT NULL,
    line_id    TEXT NOT NULL REFERENCES manufacturing_line(line_id),
    active     INTEGER NOT NULL DEFAULT 1
);
INSERT OR IGNORE INTO production_table (table_id, table_type, line_id) VALUES
    ('T01','LAMINATING','P01'),('T02','LAMINATING','P01'),
    ('T03','LAMINATING','P01'),('T04','LAMINATING','P01'),
    ('T05','LAMINATING','P02'),('T06','LAMINATING','P02'),
    ('T07','LAMINATING','P02'),('T08','LAMINATING','P37'),
    ('T09','LAMINATING','P37'),('T10','LAMINATING','P37');

-- Press/sander machines (separate from general 'machines' table)
CREATE TABLE IF NOT EXISTS prod_machine (
    machine_id   TEXT PRIMARY KEY,
    machine_type TEXT NOT NULL,
    line_id      TEXT NOT NULL REFERENCES manufacturing_line(line_id),
    active       INTEGER NOT NULL DEFAULT 1
);
INSERT OR IGNORE INTO prod_machine (machine_id, machine_type, line_id) VALUES
    ('CP-01','COLD_PRESS','P01'),('CP-02','COLD_PRESS','P02'),
    ('HP-01','HOT_PRESS','P01'),('HP-02','HOT_PRESS','P02'),('HP-37','HOT_PRESS','P37'),
    ('SND-01','SANDER','P01'),('SND-02','SANDER','P02'),('SND-37','SANDER','P37');

-- NCG reason codes
CREATE TABLE IF NOT EXISTS ncg_reason (
    reason_code TEXT PRIMARY KEY,
    description TEXT NOT NULL
);
INSERT OR IGNORE INTO ncg_reason (reason_code, description) VALUES
    ('NCG-DELAMINATION',  'Veneer delamination from substrate'),
    ('NCG-SANDED-VENEER', 'Veneer sanded through during sanding op'),
    ('NCG-GLUE-BLEED',    'Glue bleed through to face veneer'),
    ('NCG-SURFACE-ROUGH', 'Surface roughness below spec'),
    ('NCG-THICKNESS-VAR', 'Thickness variation outside tolerance'),
    ('NCG-OTHER',         'Other - see notes');

-- Production order (manufacturing work order, not the sales PO)
CREATE TABLE IF NOT EXISTS mfg_order (
    order_id      TEXT PRIMARY KEY,
    po_ref        TEXT DEFAULT '',   -- links back to purchase_orders.po_number
    customer_code TEXT NOT NULL DEFAULT '',
    sku_code      TEXT NOT NULL,     -- references skus.code
    line_id       TEXT NOT NULL REFERENCES manufacturing_line(line_id),
    qty_ordered   INTEGER NOT NULL CHECK (qty_ordered > 0),
    due_date      TEXT DEFAULT '',
    status        TEXT NOT NULL DEFAULT 'OPEN'
                      CHECK (status IN ('OPEN','IN_PROGRESS','COMPLETED','CANCELLED')),
    created_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Production batch (core traceability spine)
CREATE TABLE IF NOT EXISTS prod_batch (
    batch_id        TEXT PRIMARY KEY,     -- BTH-YYYYMMDD-XXXX
    order_id        TEXT REFERENCES mfg_order(order_id),
    sku_code        TEXT NOT NULL,        -- references skus.code
    line_id         TEXT NOT NULL REFERENCES manufacturing_line(line_id),
    qty_planned     INTEGER NOT NULL CHECK (qty_planned > 0),
    production_date TEXT NOT NULL DEFAULT (date('now')),
    shift           TEXT NOT NULL CHECK (shift IN ('MORNING','AFTERNOON','NIGHT')),
    status          TEXT NOT NULL DEFAULT 'GLUE_MIX'
                        CHECK (status IN (
                            'GLUE_MIX','LAMINATING','COLD_PRESS',
                            'REPAIR','SANDING','HOT_PRESS','GRADING','COMPLETE'
                        )),
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Glue mix log
CREATE TABLE IF NOT EXISTS glue_mix_log (
    mix_id       TEXT PRIMARY KEY,
    batch_id     TEXT NOT NULL REFERENCES prod_batch(batch_id),
    recipe_code  TEXT NOT NULL,           -- compound_skus.code
    qty_kg       REAL NOT NULL CHECK (qty_kg > 0),
    operator_id  TEXT REFERENCES employee(emp_id),
    operator_name TEXT DEFAULT '',        -- free text fallback if no emp_id
    mix_time_min INTEGER,
    notes        TEXT,
    mixed_at     TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Laminating log (one row per table per batch)
CREATE TABLE IF NOT EXISTS laminating_log (
    lam_id       TEXT PRIMARY KEY,
    batch_id     TEXT NOT NULL REFERENCES prod_batch(batch_id),
    table_id     TEXT NOT NULL REFERENCES production_table(table_id),
    emp_code_1   TEXT NOT NULL,
    emp_code_2   TEXT NOT NULL,
    glue_mix_ref TEXT REFERENCES glue_mix_log(mix_id),
    pcs_target   INTEGER NOT NULL CHECK (pcs_target > 0),
    pcs_actual   INTEGER NOT NULL CHECK (pcs_actual >= 0),
    shift_start  TEXT NOT NULL DEFAULT (datetime('now')),
    notes        TEXT
);

-- Cold press log
CREATE TABLE IF NOT EXISTS cold_press_log (
    cp_id        TEXT PRIMARY KEY,
    batch_id     TEXT NOT NULL REFERENCES prod_batch(batch_id),
    machine_id   TEXT NOT NULL,
    operator_id  TEXT,
    operator_name TEXT DEFAULT '',
    pressure_bar REAL,
    dwell_min    INTEGER,
    pcs_in       INTEGER NOT NULL CHECK (pcs_in >= 0),
    pcs_out      INTEGER NOT NULL CHECK (pcs_out >= 0),
    pressed_at   TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Repair log
CREATE TABLE IF NOT EXISTS repair_log (
    repair_id    TEXT PRIMARY KEY,
    batch_id     TEXT NOT NULL REFERENCES prod_batch(batch_id),
    table_id     TEXT NOT NULL,
    repair_type  TEXT NOT NULL CHECK (repair_type IN ('ROUGH','FINE')),
    emp_code_1   TEXT NOT NULL,
    emp_code_2   TEXT NOT NULL,
    pcs_repaired INTEGER NOT NULL CHECK (pcs_repaired >= 0),
    notes        TEXT,
    repaired_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Sanding log
CREATE TABLE IF NOT EXISTS sanding_log (
    sand_id      TEXT PRIMARY KEY,
    batch_id     TEXT NOT NULL REFERENCES prod_batch(batch_id),
    machine_id   TEXT NOT NULL,
    operator_id  TEXT,
    operator_name TEXT DEFAULT '',
    grit_setting TEXT NOT NULL,
    feed_speed   REAL,
    pcs_in       INTEGER NOT NULL CHECK (pcs_in >= 0),
    pcs_out      INTEGER NOT NULL CHECK (pcs_out >= 0),
    defect_count INTEGER NOT NULL DEFAULT 0 CHECK (defect_count >= 0),
    notes        TEXT,
    sanded_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Hot press log
CREATE TABLE IF NOT EXISTS hot_press_log (
    hp_id          TEXT PRIMARY KEY,
    batch_id       TEXT NOT NULL REFERENCES prod_batch(batch_id),
    machine_id     TEXT NOT NULL,
    operator_id    TEXT,
    operator_name  TEXT DEFAULT '',
    temp_c         REAL NOT NULL,
    pressure_bar   REAL NOT NULL,
    press_time_min INTEGER NOT NULL,
    pcs_in         INTEGER NOT NULL CHECK (pcs_in >= 0),
    pcs_out        INTEGER NOT NULL CHECK (pcs_out >= 0),
    pressed_at     TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Grading log (QC output)
CREATE TABLE IF NOT EXISTS grading_log (
    grade_id        TEXT PRIMARY KEY,
    batch_id        TEXT NOT NULL REFERENCES prod_batch(batch_id),
    grader_id       TEXT,
    grader_name     TEXT DEFAULT '',
    grade_outcome   TEXT NOT NULL CHECK (grade_outcome IN ('PASS','PARTIAL_NCG','FULL_NCG','REJECT')),
    pcs_grade_a     INTEGER NOT NULL DEFAULT 0 CHECK (pcs_grade_a >= 0),
    pcs_grade_b     INTEGER NOT NULL DEFAULT 0 CHECK (pcs_grade_b >= 0),
    pcs_ncg         INTEGER NOT NULL DEFAULT 0 CHECK (pcs_ncg >= 0),
    pcs_reject      INTEGER NOT NULL DEFAULT 0 CHECK (pcs_reject >= 0),
    ncg_reason_code TEXT REFERENCES ncg_reason(reason_code),
    notes           TEXT,
    graded_at       TEXT NOT NULL DEFAULT (datetime('now'))
);

-- ============================================================
-- VIEWS
-- ============================================================
DROP VIEW IF EXISTS v_ncg_backtrack;
CREATE VIEW v_ncg_backtrack AS
SELECT
    g.grade_id, g.batch_id,
    pb.sku_code, pb.line_id, pb.production_date, pb.shift,
    g.pcs_ncg, g.pcs_reject, g.ncg_reason_code, g.graded_at,
    COALESCE(g.grader_id, g.grader_name) AS grader,
    GROUP_CONCAT(DISTINCT l.table_id) AS lam_tables,
    GROUP_CONCAT(DISTINCT l.emp_code_1 || '+' || l.emp_code_2) AS lam_pairs,
    ROUND(SUM(l.pcs_actual)*1.0/NULLIF(SUM(l.pcs_target),0)*100,1) AS lam_efficacy_pct,
    GROUP_CONCAT(DISTINCT lm.recipe_code) AS glue_recipes,
    GROUP_CONCAT(DISTINCT r.emp_code_1 || '+' || r.emp_code_2
        || '(' || r.repair_type || ')') AS repair_pairs,
    sl.operator_name AS sanding_operator,
    sl.defect_count AS sanding_defects,
    sl.grit_setting,
    hp.operator_name AS hotpress_operator,
    hp.temp_c, hp.pressure_bar AS hp_pressure, hp.press_time_min
FROM grading_log g
JOIN prod_batch pb ON pb.batch_id = g.batch_id
LEFT JOIN laminating_log l ON l.batch_id = g.batch_id
LEFT JOIN glue_mix_log lm ON lm.batch_id = g.batch_id
LEFT JOIN repair_log r ON r.batch_id = g.batch_id
LEFT JOIN sanding_log sl ON sl.batch_id = g.batch_id
LEFT JOIN hot_press_log hp ON hp.batch_id = g.batch_id
WHERE g.pcs_ncg > 0 OR g.pcs_reject > 0
GROUP BY g.grade_id;

DROP VIEW IF EXISTS v_lam_efficacy;
CREATE VIEW v_lam_efficacy AS
SELECT
    l.table_id, pb.line_id, pb.sku_code, pb.production_date, pb.shift,
    l.emp_code_1, l.emp_code_2,
    l.pcs_target, l.pcs_actual,
    ROUND(l.pcs_actual*100.0/NULLIF(l.pcs_target,0),1) AS efficacy_pct
FROM laminating_log l
JOIN prod_batch pb ON pb.batch_id = l.batch_id;

DROP VIEW IF EXISTS v_sanding_defect_rate;
CREATE VIEW v_sanding_defect_rate AS
SELECT
    COALESCE(sl.operator_id, sl.operator_name) AS operator,
    pb.line_id,
    COUNT(DISTINCT sl.sand_id) AS runs,
    SUM(sl.pcs_in) AS total_pcs,
    SUM(sl.defect_count) AS total_defects,
    ROUND(SUM(sl.defect_count)*100.0/NULLIF(SUM(sl.pcs_in),0),2) AS defect_rate_pct
FROM sanding_log sl
JOIN prod_batch pb ON pb.batch_id = sl.batch_id
GROUP BY COALESCE(sl.operator_id, sl.operator_name), pb.line_id;

DROP VIEW IF EXISTS v_daily_production;
CREATE VIEW v_daily_production AS
SELECT
    pb.production_date, pb.line_id, pb.sku_code,
    COUNT(DISTINCT pb.batch_id) AS batches,
    SUM(pb.qty_planned) AS qty_planned,
    SUM(g.pcs_grade_a + g.pcs_grade_b) AS qty_good,
    SUM(g.pcs_ncg) AS qty_ncg,
    SUM(g.pcs_reject) AS qty_reject,
    ROUND(SUM(g.pcs_ncg)*100.0/
        NULLIF(SUM(g.pcs_grade_a+g.pcs_grade_b+g.pcs_ncg+g.pcs_reject),0),2) AS ncg_rate_pct
FROM prod_batch pb
LEFT JOIN grading_log g ON g.batch_id = pb.batch_id
GROUP BY pb.production_date, pb.line_id, pb.sku_code;

DROP VIEW IF EXISTS v_ncg_by_reason;
CREATE VIEW v_ncg_by_reason AS
SELECT
    g.ncg_reason_code, nr.description, pb.line_id,
    COUNT(DISTINCT g.grade_id) AS ncg_batches,
    SUM(g.pcs_ncg) AS total_ncg_pcs
FROM grading_log g
JOIN prod_batch pb ON pb.batch_id = g.batch_id
JOIN ncg_reason nr ON nr.reason_code = g.ncg_reason_code
WHERE g.pcs_ncg > 0
GROUP BY g.ncg_reason_code, pb.line_id;
""")

conn.commit()
conn.execute("PRAGMA foreign_keys = ON")

# Verify
tables = [r[0] for r in conn.execute(
    "SELECT name FROM sqlite_master WHERE type IN ('table','view') ORDER BY name"
).fetchall()]
new_tables = [t for t in tables if t in [
    'manufacturing_line','employee','production_table','prod_machine','ncg_reason',
    'mfg_order','prod_batch','glue_mix_log','laminating_log','cold_press_log',
    'repair_log','sanding_log','hot_press_log','grading_log','sku',
    'v_ncg_backtrack','v_lam_efficacy','v_sanding_defect_rate','v_daily_production','v_ncg_by_reason'
]]
print(f"Created {len(new_tables)} new tables/views:")
for t in sorted(new_tables):
    print(f"  + {t}")
conn.close()
print("\nMigration complete.")
