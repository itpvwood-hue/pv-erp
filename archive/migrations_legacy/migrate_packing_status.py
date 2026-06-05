"""
Migration: Fix prod_batch status CHECK constraint to include PACKING.
Handles partial-run state: prod_batch_new exists, prod_batch was dropped.
"""
import sqlite3, os, sys
sys.stdout.reconfigure(encoding='utf-8')

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'erp.db')
conn = sqlite3.connect(DB_PATH)
conn.execute("PRAGMA foreign_keys = OFF")

try:
    # Check current state
    tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
    has_new = 'prod_batch_new' in tables
    has_old = 'prod_batch' in tables
    print(f"State: prod_batch={'exists' if has_old else 'MISSING'}, prod_batch_new={'exists' if has_new else 'missing'}")

    conn.executescript("""
        -- Drop all views that depend on prod_batch
        DROP VIEW IF EXISTS v_ncg_backtrack;
        DROP VIEW IF EXISTS v_lam_efficacy;
        DROP VIEW IF EXISTS v_sanding_defect_rate;
        DROP VIEW IF EXISTS v_daily_production;
        DROP VIEW IF EXISTS v_ncg_by_reason;

        -- If prod_batch still exists, migrate it; otherwise just rename _new
        DROP TABLE IF EXISTS prod_batch_new2;
    """)

    if has_old:
        # Full migration path
        conn.executescript("""
            CREATE TABLE prod_batch_new2 (
                batch_id        TEXT PRIMARY KEY,
                order_id        TEXT REFERENCES mfg_order(order_id),
                sku_code        TEXT NOT NULL,
                line_id         TEXT NOT NULL REFERENCES manufacturing_line(line_id),
                qty_planned     INTEGER NOT NULL CHECK (qty_planned > 0),
                production_date TEXT NOT NULL DEFAULT (date('now')),
                shift           TEXT NOT NULL CHECK (shift IN ('MORNING','AFTERNOON','NIGHT')),
                status          TEXT NOT NULL DEFAULT 'GLUE_MIX'
                                    CHECK (status IN (
                                        'GLUE_MIX','LAMINATING','COLD_PRESS',
                                        'REPAIR','SANDING','HOT_PRESS',
                                        'GRADING','PACKING','COMPLETE'
                                    )),
                created_at      TEXT NOT NULL DEFAULT (datetime('now'))
            );
            INSERT INTO prod_batch_new2 SELECT * FROM prod_batch;
            DROP TABLE prod_batch;
            ALTER TABLE prod_batch_new2 RENAME TO prod_batch;
            DROP TABLE IF EXISTS prod_batch_new;
        """)
        print("Full migration done.")
    elif has_new:
        # Partial-run recovery: just rename _new -> prod_batch
        conn.executescript("""
            ALTER TABLE prod_batch_new RENAME TO prod_batch;
        """)
        print("Renamed prod_batch_new -> prod_batch.")
    else:
        print("ERROR: Neither prod_batch nor prod_batch_new found!")

    # Recreate all views
    conn.executescript("""
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

        CREATE VIEW v_lam_efficacy AS
        SELECT
            l.table_id, pb.line_id, pb.sku_code, pb.production_date, pb.shift,
            l.emp_code_1, l.emp_code_2,
            l.pcs_target, l.pcs_actual,
            ROUND(l.pcs_actual*100.0/NULLIF(l.pcs_target,0),1) AS efficacy_pct
        FROM laminating_log l
        JOIN prod_batch pb ON pb.batch_id = l.batch_id;

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

    # Verify
    row = conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='prod_batch'").fetchone()
    if row and 'PACKING' in row[0]:
        print("VERIFIED: PACKING is in the status CHECK constraint.")
    else:
        print("ERROR: verification failed.")
        if row: print(row[0])

    views = [v[0] for v in conn.execute("SELECT name FROM sqlite_master WHERE type='view'").fetchall()]
    print(f"Views: {views}")
    count = conn.execute("SELECT COUNT(*) FROM prod_batch").fetchone()[0]
    print(f"prod_batch rows: {count}")

except Exception as e:
    conn.rollback()
    print(f"ERROR: {e}")
    import traceback; traceback.print_exc()
finally:
    conn.execute("PRAGMA foreign_keys = ON")
    conn.close()
