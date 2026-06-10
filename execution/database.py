"""
Database layer for Veneer Overlay Factory ERP.
SQLite with raw SQL. All tables created via init_db().
"""
import sqlite3, json, os, uuid, re
from datetime import date as datemod

try:
    from config import DB_PATH
except ImportError:
    # Fallback for tools that import database.py standalone (e.g. archive scripts)
    DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'erp.db')

def get_db():
    # timeout=30: wait up to 30 seconds for a write lock instead of failing immediately
    # check_same_thread=False: allow connection across FastAPI's worker thread pool
    conn = sqlite3.connect(DB_PATH, timeout=30.0, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    # WAL mode → readers don't block writers (and vice-versa)
    conn.execute("PRAGMA journal_mode = WAL")
    # Belt & suspenders: also set busy_timeout via PRAGMA (in ms)
    conn.execute("PRAGMA busy_timeout = 30000")
    # NORMAL sync is safe with WAL and significantly faster than FULL
    conn.execute("PRAGMA synchronous = NORMAL")
    return conn

def row_to_dict(row): return dict(row) if row else None
def rows_to_list(rows): return [dict(r) for r in rows]

def init_db():
    conn = get_db()
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript("""
        -- ── Core ERP Tables ──────────────────────────────────────
        -- Manufacturing lines. Base columns only; line_type + sort_order are
        -- added by the _migrations ALTER list below. Must exist before the
        -- line_flow / stations tables (which FK to it) and before
        -- _seed_lines_and_departments() runs.
        CREATE TABLE IF NOT EXISTS manufacturing_line (
            line_id   TEXT PRIMARY KEY,
            line_name TEXT NOT NULL,
            active    INTEGER NOT NULL DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS materials (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            type TEXT NOT NULL,
            unit TEXT NOT NULL,
            current_stock REAL DEFAULT 0,
            reorder_point REAL DEFAULT 0,
            unit_cost REAL DEFAULT 0,
            supplier TEXT DEFAULT '',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            sku TEXT UNIQUE NOT NULL,
            description TEXT DEFAULT '',
            unit TEXT DEFAULT 'sheet',
            selling_price REAL DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS bom (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER NOT NULL,
            material_id INTEGER NOT NULL,
            quantity_per_unit REAL NOT NULL,
            waste_factor REAL DEFAULT 0.05,
            notes TEXT DEFAULT '',
            FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE,
            FOREIGN KEY (material_id) REFERENCES materials(id),
            UNIQUE(product_id, material_id)
        );
        CREATE TABLE IF NOT EXISTS machines (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            type TEXT NOT NULL,
            capacity_per_shift INTEGER NOT NULL,
            status TEXT DEFAULT 'active',
            last_maintenance TEXT DEFAULT '',
            next_maintenance TEXT DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_number TEXT UNIQUE NOT NULL,
            customer TEXT NOT NULL,
            product_id INTEGER NOT NULL,
            quantity INTEGER NOT NULL,
            produced_qty INTEGER DEFAULT 0,
            due_date TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            priority INTEGER DEFAULT 3,
            notes TEXT DEFAULT '',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (product_id) REFERENCES products(id)
        );
        CREATE TABLE IF NOT EXISTS production_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            log_date TEXT NOT NULL,
            shift TEXT NOT NULL,
            product_id INTEGER NOT NULL,
            machine_id INTEGER NOT NULL,
            order_id INTEGER,
            planned_qty INTEGER NOT NULL,
            actual_qty INTEGER NOT NULL,
            downtime_minutes INTEGER DEFAULT 0,
            downtime_reason TEXT DEFAULT '',
            operator_count INTEGER DEFAULT 1,
            material_usage TEXT DEFAULT '{}',
            notes TEXT DEFAULT '',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (product_id) REFERENCES products(id),
            FOREIGN KEY (machine_id) REFERENCES machines(id)
        );
        CREATE TABLE IF NOT EXISTS reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            report_date TEXT NOT NULL,
            report_type TEXT NOT NULL,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            generated_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        -- ── Purchase & Production Workflow ────────────────────────
        CREATE TABLE IF NOT EXISTS purchase_orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            po_number TEXT UNIQUE NOT NULL,
            customer TEXT NOT NULL,
            order_date TEXT NOT NULL,
            delivery_date TEXT DEFAULT '',
            status TEXT DEFAULT 'open',
            notes TEXT DEFAULT '',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS po_lines (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            po_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            quantity INTEGER NOT NULL,
            unit_price REAL DEFAULT 0,
            production_line TEXT DEFAULT 'P01',
            notes TEXT DEFAULT '',
            FOREIGN KEY (po_id) REFERENCES purchase_orders(id) ON DELETE CASCADE,
            FOREIGN KEY (product_id) REFERENCES products(id)
        );
        CREATE TABLE IF NOT EXISTS production_orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            prod_order_number TEXT UNIQUE NOT NULL,
            po_line_id INTEGER,
            po_id INTEGER,
            product_id INTEGER NOT NULL,
            production_line TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            status TEXT DEFAULT 'planned',
            priority INTEGER DEFAULT 3,
            planned_start TEXT DEFAULT '',
            planned_end TEXT DEFAULT '',
            actual_start TEXT DEFAULT '',
            actual_end TEXT DEFAULT '',
            notes TEXT DEFAULT '',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (po_line_id) REFERENCES po_lines(id),
            FOREIGN KEY (po_id) REFERENCES purchase_orders(id),
            FOREIGN KEY (product_id) REFERENCES products(id)
        );

        -- ── Batch Tracking ────────────────────────────────────────
        CREATE TABLE IF NOT EXISTS batches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            batch_number TEXT UNIQUE NOT NULL,
            prod_order_id INTEGER NOT NULL,
            parent_batch_id INTEGER,
            quantity INTEGER NOT NULL,
            current_department TEXT NOT NULL DEFAULT 'fc',
            status TEXT DEFAULT 'active',
            split_reason TEXT DEFAULT '',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (prod_order_id) REFERENCES production_orders(id),
            FOREIGN KEY (parent_batch_id) REFERENCES batches(id)
        );
        CREATE TABLE IF NOT EXISTS batch_movements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            batch_id INTEGER NOT NULL,
            from_department TEXT DEFAULT '',
            to_department TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            time_in_dept_minutes INTEGER DEFAULT 0,
            moved_at TEXT DEFAULT CURRENT_TIMESTAMP,
            moved_by TEXT DEFAULT '',
            notes TEXT DEFAULT '',
            FOREIGN KEY (batch_id) REFERENCES batches(id)
        );

        -- ── Department Records ────────────────────────────────────
        CREATE TABLE IF NOT EXISTS laminating_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            batch_id INTEGER NOT NULL,
            record_date TEXT NOT NULL,
            shift TEXT DEFAULT 'morning',
            tables_open INTEGER DEFAULT 1,
            glue_code TEXT DEFAULT '',
            glue_qty_kg REAL DEFAULT 0,
            planned_qty INTEGER DEFAULT 0,
            actual_qty INTEGER DEFAULT 0,
            ncg_qty INTEGER DEFAULT 0,
            operator_count INTEGER DEFAULT 2,
            time_minutes INTEGER DEFAULT 480,
            notes TEXT DEFAULT '',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (batch_id) REFERENCES batches(id)
        );
        CREATE TABLE IF NOT EXISTS repair_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            batch_id INTEGER NOT NULL,
            record_date TEXT NOT NULL,
            pair_name TEXT NOT NULL,
            repair_type TEXT NOT NULL,
            veneer_species TEXT DEFAULT '',
            pcs_repaired INTEGER DEFAULT 0,
            pcs_rejected INTEGER DEFAULT 0,
            time_minutes INTEGER DEFAULT 0,
            notes TEXT DEFAULT '',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (batch_id) REFERENCES batches(id)
        );
        CREATE TABLE IF NOT EXISTS sanding_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            batch_id INTEGER NOT NULL,
            record_date TEXT NOT NULL,
            machine_name TEXT DEFAULT '',
            operator TEXT NOT NULL,
            belt_id TEXT DEFAULT '',
            belt_life_pcs INTEGER DEFAULT 0,
            planned_qty INTEGER DEFAULT 0,
            actual_qty INTEGER DEFAULT 0,
            ncg_qty INTEGER DEFAULT 0,
            ncg_reason TEXT DEFAULT '',
            time_minutes INTEGER DEFAULT 0,
            notes TEXT DEFAULT '',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (batch_id) REFERENCES batches(id)
        );
        CREATE TABLE IF NOT EXISTS grading_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            batch_id INTEGER NOT NULL,
            record_date TEXT NOT NULL,
            total_graded INTEGER DEFAULT 0,
            grade_lg INTEGER DEFAULT 0,
            grade_c INTEGER DEFAULT 0,
            ncg_qty INTEGER DEFAULT 0,
            send_to_repair INTEGER DEFAULT 0,
            send_to_sanding INTEGER DEFAULT 0,
            grader TEXT DEFAULT '',
            notes TEXT DEFAULT '',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (batch_id) REFERENCES batches(id)
        );
        -- Generic dept activity for FC, Cold Press, Hot Press, Bleach, Packing
        CREATE TABLE IF NOT EXISTS dept_activities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            batch_id INTEGER NOT NULL,
            department TEXT NOT NULL,
            record_date TEXT NOT NULL,
            planned_qty INTEGER DEFAULT 0,
            actual_qty INTEGER DEFAULT 0,
            ncg_qty INTEGER DEFAULT 0,
            operator TEXT DEFAULT '',
            time_minutes INTEGER DEFAULT 0,
            extra_data TEXT DEFAULT '{}',
            notes TEXT DEFAULT '',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (batch_id) REFERENCES batches(id)
        );
    """)
    conn.commit()

    # ── FC Transfer Requests table ────────────────────────────
    conn.execute("""
        CREATE TABLE IF NOT EXISTS fc_transfer_requests (
            request_id  TEXT PRIMARY KEY,
            material_id INTEGER NOT NULL,
            qty_requested REAL NOT NULL,
            qty_fulfilled REAL DEFAULT 0,
            status      TEXT DEFAULT 'PENDING',
            notes       TEXT DEFAULT '',
            requested_by TEXT NOT NULL,
            fulfilled_by TEXT,
            created_at  TEXT DEFAULT CURRENT_TIMESTAMP,
            fulfilled_at TEXT,
            FOREIGN KEY (material_id) REFERENCES materials(id)
        )
    """)
    # ── Veneer Re-grade Log ────────────────────────────────────
    conn.execute("""
        CREATE TABLE IF NOT EXISTS veneer_regrade_log (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            record_id     TEXT UNIQUE NOT NULL,
            from_material_id INTEGER NOT NULL,
            to_material_id   INTEGER NOT NULL,
            qty           REAL NOT NULL,
            from_location TEXT DEFAULT 'fc_station',
            to_location   TEXT DEFAULT 'main_warehouse',
            graded_by     TEXT NOT NULL,
            notes         TEXT DEFAULT '',
            created_at    TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (from_material_id) REFERENCES materials(id),
            FOREIGN KEY (to_material_id)   REFERENCES materials(id)
        )
    """)
    # ── Production Order Veneer Grade Mix ─────────────────────
    conn.execute("""
        CREATE TABLE IF NOT EXISTS prod_order_veneer_alloc (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            prod_order_id INTEGER NOT NULL,
            side          TEXT NOT NULL,
            material_id   INTEGER NOT NULL,
            qty_allocated REAL NOT NULL,
            pct_of_total  REAL DEFAULT 0,
            FOREIGN KEY (prod_order_id) REFERENCES production_orders(id) ON DELETE CASCADE,
            FOREIGN KEY (material_id)   REFERENCES materials(id),
            UNIQUE(prod_order_id, side, material_id)
        )
    """)
    conn.commit()

    # ── Migrations (safe to run on existing DBs) ──────────────
    # ── NCG multi-issue table ─────────────────────────────────────
    conn.execute("""
        CREATE TABLE IF NOT EXISTS grading_ncg_issues (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            grade_id    TEXT NOT NULL,
            reason_code TEXT NOT NULL,
            pcs_count   INTEGER NOT NULL DEFAULT 0,
            notes       TEXT DEFAULT '',
            FOREIGN KEY (grade_id) REFERENCES grading_log(grade_id)
        )
    """)
    conn.commit()

    # ── Station Presets (saved machine/table/operator combos) ────
    conn.execute("""
        CREATE TABLE IF NOT EXISTS station_presets (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            name            TEXT NOT NULL,
            department      TEXT NOT NULL,
            preset_data     TEXT NOT NULL,
            created_by      TEXT DEFAULT '',
            last_used_at    TEXT DEFAULT '',
            use_count       INTEGER DEFAULT 0,
            created_at      TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_station_presets_dept ON station_presets(department)")
    conn.commit()

    # ── HR Attendance ─────────────────────────────────────────────
    conn.execute("""
        CREATE TABLE IF NOT EXISTS hr_attendance (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            work_date       TEXT NOT NULL,
            emp_id          TEXT NOT NULL,
            department      TEXT NOT NULL,
            shift           TEXT DEFAULT 'MORNING',
            time_in         TEXT DEFAULT '',
            time_out        TEXT DEFAULT '',
            regular_hours   REAL DEFAULT 0,
            ot_hours        REAL DEFAULT 0,
            status          TEXT DEFAULT 'PRESENT',
            notes           TEXT DEFAULT '',
            logged_by       TEXT DEFAULT '',
            created_at      TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(work_date, emp_id, shift)
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_hr_attendance_date ON hr_attendance(work_date,department)")

    # ── Station Stock ─────────────────────────────────────────────
    conn.execute("""
        CREATE TABLE IF NOT EXISTS station_stock (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            department      TEXT NOT NULL,
            line_id         TEXT DEFAULT '',
            material_id     INTEGER NOT NULL,
            current_qty     REAL DEFAULT 0,
            min_qty         REAL DEFAULT 0,
            last_updated    TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(department, line_id, material_id),
            FOREIGN KEY (material_id) REFERENCES materials(id)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS station_stock_movements (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            department      TEXT NOT NULL,
            line_id         TEXT DEFAULT '',
            material_id     INTEGER NOT NULL,
            qty_change      REAL NOT NULL,
            movement_type   TEXT NOT NULL,
            batch_ref       TEXT DEFAULT '',
            reference       TEXT DEFAULT '',
            notes           TEXT DEFAULT '',
            created_by      TEXT DEFAULT '',
            created_at      TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (material_id) REFERENCES materials(id)
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_station_stock_dept ON station_stock(department,line_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_station_stock_mvmt ON station_stock_movements(department,created_at)")
    conn.commit()

    # ── Glue Recipes table ────────────────────────────────────────
    conn.execute("""
        CREATE TABLE IF NOT EXISTS glue_recipes (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            recipe_code     TEXT UNIQUE NOT NULL,
            name            TEXT NOT NULL,
            resin_ratio     REAL DEFAULT 100,
            hardener_ratio  REAL DEFAULT 20,
            extender_ratio  REAL DEFAULT 0,
            filler_ratio    REAL DEFAULT 0,
            water_ratio     REAL DEFAULT 0,
            mix_time_min    INTEGER DEFAULT 20,
            notes           TEXT DEFAULT '',
            is_active       INTEGER DEFAULT 1
        )
    """)

    # ── Purchasing: planner + warehouse can raise purchase requests ──
    conn.execute("""
        CREATE TABLE IF NOT EXISTS purchase_requests (
            id                INTEGER PRIMARY KEY AUTOINCREMENT,
            request_number    TEXT UNIQUE,
            request_type      TEXT NOT NULL,           -- RAW_MATERIAL | CONSUMABLE
            material_id       INTEGER NOT NULL,
            qty_requested     REAL NOT NULL,
            uom               TEXT DEFAULT '',
            source_po_id      INTEGER,                 -- nullable: sales PO that triggered this
            priority          INTEGER DEFAULT 2,       -- 1=High 2=Med 3=Low
            needed_by         TEXT,
            suggested_supplier TEXT DEFAULT '',
            notes             TEXT DEFAULT '',
            status            TEXT DEFAULT 'NEW',      -- NEW | APPROVED | ORDERED | RECEIVED | CANCELLED
            requested_by      TEXT,
            requested_at      TEXT DEFAULT (datetime('now')),
            approved_by       TEXT,
            approved_at       TEXT,
            ordered_at        TEXT,
            received_at       TEXT,
            supplier_po_ref   TEXT DEFAULT '',
            po_issued_at      TEXT,
            awaiting_since    TEXT,
            estimated_arrival TEXT,
            FOREIGN KEY (material_id) REFERENCES materials(id),
            FOREIGN KEY (source_po_id) REFERENCES purchase_orders(id)
        )
    """)

    # ── Raw material lots (FIFO) — glue, boards, veneers ──
    conn.execute("""
        CREATE TABLE IF NOT EXISTS material_lots (
            id                INTEGER PRIMARY KEY AUTOINCREMENT,
            lot_code          TEXT NOT NULL,
            material_id       INTEGER NOT NULL,
            supplier          TEXT DEFAULT '',
            supplier_lot_ref  TEXT DEFAULT '',
            received_qty      REAL NOT NULL,
            remaining_qty     REAL NOT NULL,
            uom               TEXT DEFAULT '',
            unit_cost         REAL DEFAULT 0,
            received_at       TEXT DEFAULT (datetime('now')),
            expiry_date       TEXT,
            purchase_request_id INTEGER,
            notes             TEXT DEFAULT '',
            is_active         INTEGER DEFAULT 1,
            FOREIGN KEY (material_id) REFERENCES materials(id),
            FOREIGN KEY (purchase_request_id) REFERENCES purchase_requests(id)
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_mat_lots_mat ON material_lots(material_id, received_at)")

    # ── PDF / document storage linked to material or lot ──
    conn.execute("""
        CREATE TABLE IF NOT EXISTS material_documents (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            material_id   INTEGER NOT NULL,
            lot_id        INTEGER,
            doc_type      TEXT DEFAULT 'OTHER',     -- COA | MSDS | SUPPLIER_CERT | INSPECTION | OTHER
            filename      TEXT NOT NULL,
            stored_path   TEXT NOT NULL,
            file_size     INTEGER DEFAULT 0,
            content_type  TEXT DEFAULT 'application/pdf',
            uploaded_by   TEXT,
            uploaded_at   TEXT DEFAULT (datetime('now')),
            notes         TEXT DEFAULT '',
            FOREIGN KEY (material_id) REFERENCES materials(id),
            FOREIGN KEY (lot_id) REFERENCES material_lots(id)
        )
    """)

    # ── Refuel windows: configurable daily slots warehouse offers ──
    conn.execute("""
        CREATE TABLE IF NOT EXISTS refuel_windows (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            label        TEXT NOT NULL,
            start_hour   INTEGER NOT NULL,
            start_min    INTEGER DEFAULT 0,
            cutoff_hour  INTEGER NOT NULL,
            cutoff_min   INTEGER DEFAULT 30,
            days_of_week TEXT DEFAULT 'mon,tue,wed,thu,fri,sat',
            active       INTEGER DEFAULT 1,
            notes        TEXT DEFAULT ''
        )
    """)

    # ── LG (scrap) bin: per-station scrap pcs with reason ──
    conn.execute("""
        CREATE TABLE IF NOT EXISTS scrap_log (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            batch_id        INTEGER NOT NULL,
            batch_number    TEXT,
            dept            TEXT NOT NULL,
            production_line TEXT DEFAULT '',
            pcs_scrapped    INTEGER NOT NULL,
            reason_code     TEXT NOT NULL,
            reason_detail   TEXT DEFAULT '',
            disposition     TEXT DEFAULT 'PENDING_REVIEW',
            reviewed_by     TEXT,
            reviewed_at     TEXT,
            review_notes    TEXT DEFAULT '',
            created_by      TEXT,
            created_at      TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (batch_id) REFERENCES batches(id)
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_scrap_disp ON scrap_log(disposition)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_scrap_dept ON scrap_log(dept)")

    # ── Forklifts & oil-request log (registered by station leaders) ──
    conn.execute("""
        CREATE TABLE IF NOT EXISTS forklifts (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            code          TEXT UNIQUE NOT NULL,
            name          TEXT DEFAULT '',
            dept          TEXT DEFAULT '',
            production_line TEXT DEFAULT '',
            model         TEXT DEFAULT '',
            fuel_type     TEXT DEFAULT 'diesel',
            status        TEXT DEFAULT 'active',   -- active | maintenance | retired
            hours_meter   REAL DEFAULT 0,
            last_service_at TEXT,
            notes         TEXT DEFAULT '',
            created_at    TEXT DEFAULT (datetime('now')),
            created_by    TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS forklift_oil_requests (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            forklift_id     INTEGER NOT NULL,
            oil_type        TEXT DEFAULT 'hydraulic',  -- hydraulic | engine | gear | other
            qty_litres      REAL NOT NULL,
            requested_by    TEXT,
            requested_at    TEXT DEFAULT (datetime('now')),
            status          TEXT DEFAULT 'PENDING',   -- PENDING | FULFILLED | CANCELLED
            fulfilled_qty   REAL DEFAULT 0,
            fulfilled_by    TEXT,
            fulfilled_at    TEXT,
            notes           TEXT DEFAULT '',
            FOREIGN KEY (forklift_id) REFERENCES forklifts(id)
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_fko_fl ON forklift_oil_requests(forklift_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_fko_status ON forklift_oil_requests(status)")

    # ── Purchase request shipment schedule ──
    # A single PR may arrive in multiple physical shipments.  Purchasing
    # schedules them with planned dates; Warehouse marks each RECEIVED as the
    # goods arrive, which spawns a material_lot for that shipment quantity.
    conn.execute("""
        CREATE TABLE IF NOT EXISTS pr_shipments (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            pr_id           INTEGER NOT NULL,
            sequence        INTEGER DEFAULT 1,
            planned_qty     REAL NOT NULL,
            planned_arrival TEXT,
            supplier_ref    TEXT DEFAULT '',
            carrier         TEXT DEFAULT '',
            notes           TEXT DEFAULT '',
            status          TEXT DEFAULT 'PLANNED',   -- PLANNED | RECEIVED | PARTIAL | CANCELLED
            received_qty    REAL DEFAULT 0,
            received_at     TEXT,
            received_by     TEXT,
            lot_id          INTEGER,
            created_at      TEXT DEFAULT (datetime('now')),
            created_by      TEXT,
            FOREIGN KEY (pr_id)  REFERENCES purchase_requests(id),
            FOREIGN KEY (lot_id) REFERENCES material_lots(id)
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_prs_pr     ON pr_shipments(pr_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_prs_status ON pr_shipments(status)")

    # ── PR ↔ Document many-to-many link (one supplier PO PDF spanning many PRs) ──
    conn.execute("""
        CREATE TABLE IF NOT EXISTS pr_document_links (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            pr_id       INTEGER NOT NULL,
            document_id INTEGER NOT NULL,
            linked_at   TEXT DEFAULT (datetime('now')),
            UNIQUE(pr_id, document_id),
            FOREIGN KEY (pr_id) REFERENCES purchase_requests(id),
            FOREIGN KEY (document_id) REFERENCES material_documents(id)
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_prdl_pr ON pr_document_links(pr_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_prdl_doc ON pr_document_links(document_id)")

    # ── Batch ↔ Lot consumption ledger (traceability) ──
    conn.execute("""
        CREATE TABLE IF NOT EXISTS batch_material_lots (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            batch_id      INTEGER NOT NULL,
            material_id   INTEGER NOT NULL,
            lot_id        INTEGER NOT NULL,
            qty_consumed  REAL NOT NULL,
            uom           TEXT DEFAULT '',
            role          TEXT DEFAULT '',           -- face / back / base / glue / consumable
            consumed_at   TEXT DEFAULT (datetime('now')),
            consumed_by   TEXT,
            notes         TEXT DEFAULT '',
            FOREIGN KEY (batch_id) REFERENCES batches(id),
            FOREIGN KEY (material_id) REFERENCES materials(id),
            FOREIGN KEY (lot_id) REFERENCES material_lots(id)
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_bml_batch ON batch_material_lots(batch_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_bml_lot ON batch_material_lots(lot_id)")

    # ── Glue mix ↔ batch link (one mix can serve many batches / POs) ──
    # A single glue mix is often shared across batches from DIFFERENT sales POs
    # (operators group identical recipes). glue_mix_log only carries one primary
    # batch_id; this table records EVERY batch a mix served so traceability
    # attributes the real mix to all of them.
    conn.execute("""
        CREATE TABLE IF NOT EXISTS glue_mix_batches (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            mix_id       TEXT NOT NULL,
            batch_number TEXT NOT NULL,
            UNIQUE(mix_id, batch_number)
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_gmb_batch ON glue_mix_batches(batch_number)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_gmb_mix ON glue_mix_batches(mix_id)")
    conn.commit()

    # ── Auth, SKU/BOM, packing, and station-log tables ───────────────
    # These existed on long-lived databases (created by earlier schema
    # revisions) but were never in this CREATE block, so a FRESH database
    # (new server install) came up WITHOUT them — users/sessions/skus/
    # bom_lines/station logs all missing, which broke login and seeding.
    # Recreated here verbatim (IF NOT EXISTS, so existing DBs are untouched).
    # Migration-added columns are already inlined; the _migrations ALTERs
    # below that re-add them simply no-op on fresh DBs (errors are caught).
    conn.executescript("""
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
        CREATE TABLE IF NOT EXISTS login_log (
            log_id     TEXT PRIMARY KEY,
            user_id    TEXT NOT NULL REFERENCES users(user_id),
            username   TEXT NOT NULL,
            role       TEXT NOT NULL,
            ip_address TEXT,
            logged_at  TEXT NOT NULL DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS suppliers (
            id    INTEGER PRIMARY KEY AUTOINCREMENT,
            name  TEXT    NOT NULL UNIQUE,
            notes TEXT
        );
        CREATE TABLE IF NOT EXISTS employee (
            emp_id     TEXT PRIMARY KEY,
            emp_name   TEXT NOT NULL,
            department TEXT NOT NULL,
            role       TEXT NOT NULL,
            line_id    TEXT REFERENCES manufacturing_line(line_id),
            active     INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
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
        CREATE TABLE IF NOT EXISTS bom_groups (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT    NOT NULL,
            calc_method TEXT    NOT NULL CHECK (calc_method IN ('per_sheet','per_pallet')),
            sort_order  INTEGER NOT NULL DEFAULT 0,
            notes       TEXT
        );
        CREATE TABLE IF NOT EXISTS bom_lines (
            id                INTEGER PRIMARY KEY AUTOINCREMENT,
            sku_id            INTEGER NOT NULL REFERENCES skus(id)       ON DELETE CASCADE,
            material_id       INTEGER          REFERENCES materials(id),
            glue_recipe_id    INTEGER          REFERENCES glue_recipes(id),
            group_id          INTEGER NOT NULL REFERENCES bom_groups(id) ON DELETE RESTRICT,
            seq               INTEGER NOT NULL DEFAULT 0,
            qty_override      REAL,
            usage_g_per_face  REAL,
            qty_unit          TEXT,
            notes             TEXT,
            created_at        TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at        TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP,
            waste_factor      REAL,
            UNIQUE (sku_id, seq),
            CHECK (NOT (qty_override IS NOT NULL AND usage_g_per_face IS NOT NULL)),
            CHECK (material_id IS NOT NULL OR glue_recipe_id IS NOT NULL)
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
        CREATE TABLE IF NOT EXISTS ncg_reason (
            reason_code TEXT PRIMARY KEY,
            description TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS mfg_order (
            order_id      TEXT PRIMARY KEY,
            po_ref        TEXT DEFAULT '',
            customer_code TEXT NOT NULL DEFAULT '',
            sku_code      TEXT NOT NULL,
            line_id       TEXT NOT NULL REFERENCES manufacturing_line(line_id),
            qty_ordered   INTEGER NOT NULL CHECK (qty_ordered > 0),
            due_date      TEXT DEFAULT '',
            status        TEXT NOT NULL DEFAULT 'OPEN'
                              CHECK (status IN ('OPEN','IN_PROGRESS','COMPLETED','CANCELLED')),
            created_at    TEXT NOT NULL DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS prod_batch (
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
                                    'GRADING','PACKING','COMPLETE')),
            created_at      TEXT NOT NULL DEFAULT (datetime('now')),
            notes           TEXT DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS production_table (
            table_id   TEXT PRIMARY KEY,
            table_type TEXT NOT NULL,
            line_id    TEXT NOT NULL REFERENCES manufacturing_line(line_id),
            active     INTEGER NOT NULL DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS prod_machine (
            machine_id   TEXT PRIMARY KEY,
            machine_type TEXT NOT NULL,
            line_id      TEXT NOT NULL REFERENCES manufacturing_line(line_id),
            active       INTEGER NOT NULL DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS glue_mix_log (
            mix_id       TEXT PRIMARY KEY,
            batch_id     TEXT NOT NULL,
            recipe_code  TEXT NOT NULL,
            qty_kg       REAL NOT NULL CHECK (qty_kg > 0),
            operator_id  TEXT,
            operator_name TEXT DEFAULT '',
            mix_time_min INTEGER,
            notes        TEXT,
            mixed_at     TEXT NOT NULL DEFAULT (datetime('now')),
            recipe_id           INTEGER,
            actual_total_kg     REAL,
            actual_total_cost   REAL,
            actual_cost_per_kg  REAL,
            actual_components   TEXT
        );
        CREATE TABLE IF NOT EXISTS laminating_log (
            lam_id       TEXT PRIMARY KEY,
            batch_id     TEXT NOT NULL,
            table_id     TEXT NOT NULL,
            emp_code_1   TEXT NOT NULL,
            emp_code_2   TEXT NOT NULL,
            glue_mix_ref TEXT,
            pcs_target   INTEGER NOT NULL CHECK (pcs_target > 0),
            pcs_actual   INTEGER NOT NULL CHECK (pcs_actual >= 0),
            shift_start  TEXT NOT NULL DEFAULT (datetime('now')),
            notes        TEXT,
            time_minutes INTEGER DEFAULT 0,
            material_role TEXT DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS cold_press_log (
            cp_id        TEXT PRIMARY KEY,
            batch_id     TEXT NOT NULL,
            machine_id   TEXT NOT NULL,
            operator_id  TEXT,
            operator_name TEXT DEFAULT '',
            pressure_bar REAL,
            dwell_min    INTEGER,
            pcs_in       INTEGER NOT NULL CHECK (pcs_in >= 0),
            pcs_out      INTEGER NOT NULL CHECK (pcs_out >= 0),
            pressed_at   TEXT NOT NULL DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS repair_log (
            repair_id    TEXT PRIMARY KEY,
            batch_id     TEXT NOT NULL,
            table_id     TEXT NOT NULL,
            repair_type  TEXT NOT NULL CHECK (repair_type IN ('ROUGH','FINE')),
            emp_code_1   TEXT NOT NULL,
            emp_code_2   TEXT NOT NULL,
            pcs_repaired INTEGER NOT NULL CHECK (pcs_repaired >= 0),
            notes        TEXT,
            repaired_at  TEXT NOT NULL DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS sanding_log (
            sand_id      TEXT PRIMARY KEY,
            batch_id     TEXT NOT NULL,
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
        CREATE TABLE IF NOT EXISTS hot_press_log (
            hp_id          TEXT PRIMARY KEY,
            batch_id       TEXT NOT NULL,
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
        CREATE TABLE IF NOT EXISTS grading_log (
            grade_id        TEXT PRIMARY KEY,
            batch_id        TEXT NOT NULL,
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
        CREATE TABLE IF NOT EXISTS packing_log (
            pack_id       TEXT PRIMARY KEY,
            batch_id      TEXT NOT NULL,
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
            fulfilled_at  TEXT,
            priority      INTEGER DEFAULT 2,
            needed_by     TEXT,
            needed_time   TEXT,
            qty_received  REAL DEFAULT 0,
            received_at   TEXT,
            received_by   TEXT
        );
        CREATE TABLE IF NOT EXISTS dept_cost_ledger (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            department  TEXT NOT NULL,
            line_id     TEXT,
            month_year  TEXT NOT NULL,
            material_id INTEGER NOT NULL REFERENCES materials(id),
            qty         REAL NOT NULL,
            unit_cost   REAL NOT NULL,
            total_cost  REAL NOT NULL,
            request_id  TEXT REFERENCES consumable_request(request_id),
            created_at  TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_skus_code        ON skus(code);
        CREATE INDEX IF NOT EXISTS idx_packing_lines_p  ON packing_lines(packing_sku_id);
        CREATE INDEX IF NOT EXISTS idx_login_log_user   ON login_log(user_id);
        CREATE INDEX IF NOT EXISTS idx_login_log_at     ON login_log(logged_at);
        CREATE INDEX IF NOT EXISTS idx_bl_sku           ON bom_lines(sku_id);
        CREATE INDEX IF NOT EXISTS idx_bl_glue_recipe   ON bom_lines(glue_recipe_id);
    """)
    conn.commit()

    _migrations = [
        "ALTER TABLE materials ADD COLUMN code TEXT DEFAULT ''",
        "ALTER TABLE materials ADD COLUMN fc_stock REAL DEFAULT 0",
        "ALTER TABLE fc_transfer_requests ADD COLUMN direction TEXT DEFAULT 'inbound'",
        "ALTER TABLE fc_transfer_requests ADD COLUMN batch_ref TEXT DEFAULT ''",
        "ALTER TABLE fc_transfer_requests ADD COLUMN po_ref TEXT DEFAULT ''",
        "ALTER TABLE bom ADD COLUMN veneer_role TEXT DEFAULT ''",
        "ALTER TABLE production_orders ADD COLUMN confirmed_face_veneer_id INTEGER",
        "ALTER TABLE production_orders ADD COLUMN confirmed_back_veneer_id INTEGER",
        "ALTER TABLE production_orders ADD COLUMN fc_confirmed INTEGER DEFAULT 0",
        "ALTER TABLE batch_movements ADD COLUMN veneer_side TEXT DEFAULT ''",
        "ALTER TABLE dept_activities ADD COLUMN veneer_side TEXT DEFAULT ''",
        "ALTER TABLE laminating_records ADD COLUMN veneer_side TEXT DEFAULT ''",
        "ALTER TABLE sanding_records ADD COLUMN veneer_side TEXT DEFAULT ''",
        "ALTER TABLE repair_records ADD COLUMN veneer_side TEXT DEFAULT ''",
        "ALTER TABLE grading_records ADD COLUMN veneer_side TEXT DEFAULT ''",
        "ALTER TABLE prod_batch ADD COLUMN notes TEXT DEFAULT ''",
        "ALTER TABLE laminating_log ADD COLUMN time_minutes INTEGER DEFAULT 0",
        "ALTER TABLE laminating_log ADD COLUMN material_role TEXT DEFAULT ''",
        # Component → station-stock material mapping for glue recipes
        "ALTER TABLE glue_recipes ADD COLUMN resin_material_id     INTEGER",
        "ALTER TABLE glue_recipes ADD COLUMN hardener_material_id  INTEGER",
        "ALTER TABLE glue_recipes ADD COLUMN extender_material_id  INTEGER",
        "ALTER TABLE glue_recipes ADD COLUMN filler_material_id    INTEGER",
        "ALTER TABLE glue_recipes ADD COLUMN water_material_id     INTEGER",
        # Real recipe components (kg per batch) — from PV Wood glue recipe spreadsheet
        "ALTER TABLE glue_recipes ADD COLUMN e0_glue_kg          REAL DEFAULT 0",
        "ALTER TABLE glue_recipes ADD COLUMN latex_g312_kg       REAL DEFAULT 0",
        "ALTER TABLE glue_recipes ADD COLUMN flour_kg            REAL DEFAULT 0",
        "ALTER TABLE glue_recipes ADD COLUMN yellow_pigment_kg   REAL DEFAULT 0",
        "ALTER TABLE glue_recipes ADD COLUMN hardener_kg         REAL DEFAULT 0",
        "ALTER TABLE glue_recipes ADD COLUMN red_pigment_kg      REAL DEFAULT 0",
        "ALTER TABLE glue_recipes ADD COLUMN black_pigment_kg    REAL DEFAULT 0",
        "ALTER TABLE glue_recipes ADD COLUMN titanium_kg         REAL DEFAULT 0",
        "ALTER TABLE glue_recipes ADD COLUMN total_kg            REAL DEFAULT 0",
        # Conditions for use
        "ALTER TABLE glue_recipes ADD COLUMN veneer_thickness    TEXT DEFAULT ''",
        "ALTER TABLE glue_recipes ADD COLUMN wood_species        TEXT DEFAULT ''",
        "ALTER TABLE glue_recipes ADD COLUMN core_board          TEXT DEFAULT ''",
        # JSON map of ingredient_key → materials.id so the glue-mix shortfall
        # check can resolve catalog stock without fuzzy name-matching.
        # Keys: e0_glue, latex_g312, flour, yellow_pigment, hardener,
        #       red_pigment, black_pigment, titanium
        "ALTER TABLE glue_recipes ADD COLUMN material_links      TEXT DEFAULT '{}'",
        # Phase A glue cleanup (2026-05-29): BOM/compound lines that used to
        # link a glue placeholder by material_id now also carry a direct link
        # to the recipe. Phase B will drop the material_id placeholder rows.
        "ALTER TABLE bom            ADD COLUMN glue_recipe_id INTEGER",
        "ALTER TABLE bom_lines      ADD COLUMN glue_recipe_id INTEGER",
        "ALTER TABLE compound_lines ADD COLUMN glue_recipe_id INTEGER",
        # 2.6.0 — actual usage + cost capture per glue-mix batch (operator may
        # override recipe ratios for humidity / temperature; we keep both the
        # proposed recipe link AND the actual cost computed from real prices).
        "ALTER TABLE glue_mix_log   ADD COLUMN recipe_id           INTEGER",
        "ALTER TABLE glue_mix_log   ADD COLUMN actual_total_kg     REAL",
        "ALTER TABLE glue_mix_log   ADD COLUMN actual_total_cost   REAL",
        "ALTER TABLE glue_mix_log   ADD COLUMN actual_cost_per_kg  REAL",
        "ALTER TABLE glue_mix_log   ADD COLUMN actual_components   TEXT",  # JSON: [{material_id, name, kg, price, cost}]
        # Exact pcs tracking — overrides quantity*pallet_qty when set (used after pcs-based splits)
        "ALTER TABLE batches ADD COLUMN pcs_actual INTEGER",
        # Machine info enhancements (for Station Log integration)
        "ALTER TABLE machines ADD COLUMN dept TEXT DEFAULT ''",
        "ALTER TABLE machines ADD COLUMN production_line TEXT DEFAULT ''",
        "ALTER TABLE machines ADD COLUMN capacity_per_hour REAL DEFAULT 0",
        "ALTER TABLE machines ADD COLUMN notes TEXT DEFAULT ''",
        # Extra PR lifecycle columns (added for the supplier-ordering workflow)
        "ALTER TABLE purchase_requests ADD COLUMN po_issued_at      TEXT",
        "ALTER TABLE purchase_requests ADD COLUMN awaiting_since    TEXT",
        "ALTER TABLE purchase_requests ADD COLUMN estimated_arrival TEXT",
        # Link uploaded supplier-PO PDFs back to the originating PR so they
        # propagate to every lot received against it (traceability).
        "ALTER TABLE material_documents ADD COLUMN purchase_request_id INTEGER",
        # Oil-request scheduling (warehouse refueling workflow)
        "ALTER TABLE forklift_oil_requests ADD COLUMN priority TEXT DEFAULT 'NORMAL'",
        "ALTER TABLE forklift_oil_requests ADD COLUMN scheduled_for TEXT",
        "ALTER TABLE forklift_oil_requests ADD COLUMN postponed_count INTEGER DEFAULT 0",
        # Link an oil request to the material/lot used to satisfy it (oil drums)
        "ALTER TABLE forklift_oil_requests ADD COLUMN oil_material_id INTEGER",
        "ALTER TABLE forklift_oil_requests ADD COLUMN oil_lot_id INTEGER",
        # Material requests (consumable + FC) now carry priority + needed-by
        # so warehouse can prioritise the queue.
        "ALTER TABLE consumable_request    ADD COLUMN priority   INTEGER DEFAULT 2",
        "ALTER TABLE consumable_request    ADD COLUMN needed_by  TEXT",
        "ALTER TABLE fc_transfer_requests  ADD COLUMN priority   INTEGER DEFAULT 2",
        "ALTER TABLE fc_transfer_requests  ADD COLUMN needed_by  TEXT",
        # Sales PO priority cascades through Material Shortfalls → FC Prep
        "ALTER TABLE purchase_orders       ADD COLUMN priority   INTEGER DEFAULT 2",
        # Multi-material PR groups — one user submission can span many materials,
        # all sharing the same group number so warehouse sees them together.
        "ALTER TABLE purchase_requests     ADD COLUMN group_number TEXT",
        # VCMX make-to-stock production (plywood core + MDF face/back substrate)
        "ALTER TABLE production_orders     ADD COLUMN is_vcmx INTEGER DEFAULT 0",
        "ALTER TABLE production_orders     ADD COLUMN vcmx_bom_id INTEGER",
        "ALTER TABLE production_orders     ADD COLUMN is_make_to_stock INTEGER DEFAULT 0",
        # VCMX BOM dimensions (so finished VCMX SKU appears as a real base board)
        "ALTER TABLE vcmx_boms             ADD COLUMN thickness_mm REAL",
        "ALTER TABLE vcmx_boms             ADD COLUMN width_mm     REAL",
        "ALTER TABLE vcmx_boms             ADD COLUMN length_mm    REAL",
        "ALTER TABLE vcmx_boms             ADD COLUMN pcs_per_pallet INTEGER",
        # Material requests can now specify a time-of-day window so warehouse
        # can batch deliveries (morning / afternoon).
        "ALTER TABLE consumable_request    ADD COLUMN needed_time TEXT",
        "ALTER TABLE fc_transfer_requests  ADD COLUMN needed_time TEXT",
        # 2.10.0 — lines/stations promotion. Extend manufacturing_line so it
        # can express aux lines (PUV/PVS/PSP) and sort order alongside main
        # lines (P01/P02/P37). is_active mirrors the existing `active` column
        # but uses the project's standard column name.
        "ALTER TABLE manufacturing_line    ADD COLUMN line_type   TEXT NOT NULL DEFAULT 'main'",
        "ALTER TABLE manufacturing_line    ADD COLUMN sort_order  INTEGER NOT NULL DEFAULT 0",
        # 2.11.x — line scope on per-station data so analytics can JOIN to a
        # concrete (line, dept) station row. dept_activities + station_presets
        # are the two that lacked it; station_stock + station_stock_movements
        # already carry line_id.
        "ALTER TABLE dept_activities       ADD COLUMN line_id  TEXT DEFAULT ''",
        "ALTER TABLE station_presets       ADD COLUMN line_id  TEXT DEFAULT ''",
        # 2.18.0 — two-step consumable receive. Warehouse 'fulfill' issues
        # stock (deducts WH, marks FULFILLED); the requesting station then
        # confirms physical receipt, which deposits into station_stock. Track
        # how much the station has actually received so partial receipts work.
        "ALTER TABLE consumable_request    ADD COLUMN qty_received REAL DEFAULT 0",
        "ALTER TABLE consumable_request    ADD COLUMN received_at  TEXT",
        "ALTER TABLE consumable_request    ADD COLUMN received_by  TEXT",
        # 2.19.1 — when a station issued/used (or counted) a consumable, as
        # stated by the operator. Distinct from created_at (when it was logged).
        "ALTER TABLE station_stock_movements ADD COLUMN occurred_at TEXT",
        # 2.20.0 — per-BOM-line waste factor for the structured BOM. The FC
        # requirement calc used to hardcode 5% for every bom_lines material;
        # now waste is per line (boards 0, veneers vary, set in the BOM
        # Builder). NULL on existing rows so the one-time seed below can tell
        # "never set" from "deliberately 0".
        "ALTER TABLE bom_lines ADD COLUMN waste_factor REAL",
    ]
    # ── VCMX BOM master ─────────────────────────────────────────
    conn.execute("""
        CREATE TABLE IF NOT EXISTS vcmx_boms (
            id                   INTEGER PRIMARY KEY AUTOINCREMENT,
            sku_code             TEXT UNIQUE NOT NULL,
            sku_name             TEXT NOT NULL,
            material_id          INTEGER,                 -- paired materials row (type='vcmx')
            core_material_id     INTEGER NOT NULL,
            face_material_id     INTEGER NOT NULL,
            back_material_id     INTEGER NOT NULL,
            glue_material_id     INTEGER,
            glue_qty_per_panel   REAL DEFAULT 0,
            labour_cost_per_panel REAL DEFAULT 0,
            notes                TEXT DEFAULT '',
            active               INTEGER DEFAULT 1,
            created_by           TEXT DEFAULT '',
            created_at           TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (material_id)      REFERENCES materials(id),
            FOREIGN KEY (core_material_id) REFERENCES materials(id),
            FOREIGN KEY (face_material_id) REFERENCES materials(id),
            FOREIGN KEY (back_material_id) REFERENCES materials(id),
            FOREIGN KEY (glue_material_id) REFERENCES materials(id)
        )
    """)
    # ── VCMX laminating log (one row per completion event) ──────
    conn.execute("""
        CREATE TABLE IF NOT EXISTS vcmx_laminating_log (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            batch_id        INTEGER NOT NULL,
            prod_order_id   INTEGER NOT NULL,
            vcmx_bom_id     INTEGER NOT NULL,
            qty_produced    INTEGER NOT NULL,
            qty_ncg         INTEGER DEFAULT 0,
            glue_actual_kg  REAL DEFAULT 0,
            material_cost   REAL DEFAULT 0,
            labour_cost     REAL DEFAULT 0,
            unit_cost       REAL DEFAULT 0,
            output_lot_id   INTEGER,
            operator        TEXT DEFAULT '',
            notes           TEXT DEFAULT '',
            completed_at    TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (batch_id)      REFERENCES batches(id),
            FOREIGN KEY (vcmx_bom_id)   REFERENCES vcmx_boms(id),
            FOREIGN KEY (output_lot_id) REFERENCES material_lots(id)
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_vcmx_log_batch ON vcmx_laminating_log(batch_id)")

    # ── Departments registry ────────────────────────────────────
    # Replaces the hardcoded DEPARTMENTS list in database.py and the
    # parallel DEPTS / DLBL / DICO dicts in the frontend. is_centralised=1
    # means there is exactly one station regardless of how many lines feed
    # in (currently: packing, fg_warehouse, fg_receiving).
    conn.execute("""
        CREATE TABLE IF NOT EXISTS departments (
            code           TEXT PRIMARY KEY,
            label          TEXT NOT NULL,
            icon           TEXT,
            is_centralised INTEGER NOT NULL DEFAULT 0,
            sort_order     INTEGER NOT NULL DEFAULT 0,
            is_active      INTEGER NOT NULL DEFAULT 1
        )
    """)

    # ── Line flow ──────────────────────────────────────────────
    # Replaces the hardcoded LINE_FLOW = { P01: [...], P02: [...], P37: [...] }
    # dict in the frontend. One row per (line, sequence position, department).
    conn.execute("""
        CREATE TABLE IF NOT EXISTS line_flow (
            line_code        TEXT NOT NULL,
            seq              INTEGER NOT NULL,
            department_code  TEXT NOT NULL,
            PRIMARY KEY (line_code, seq),
            FOREIGN KEY (line_code)       REFERENCES manufacturing_line(line_id),
            FOREIGN KEY (department_code) REFERENCES departments(code)
        )
    """)

    # ── Stations ───────────────────────────────────────────────
    # A concrete (line, department) pair. Per-line departments (fc, laminating,
    # cold_press, hot_press, bleach, repair, sanding, grading) get one row per
    # main line. Centralised departments (packing, fg_receiving, fg_warehouse)
    # get exactly one row with line_code = NULL — the UI renders these as
    # "ALL LINES". This is the row to FK against from per-station analytics:
    # dept_activities, station_stock(_movements), station_presets.
    conn.execute("""
        CREATE TABLE IF NOT EXISTS stations (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            line_code           TEXT,
            department_code     TEXT NOT NULL,
            label               TEXT,
            capacity_per_shift  INTEGER,
            is_active           INTEGER NOT NULL DEFAULT 1,
            FOREIGN KEY (line_code)       REFERENCES manufacturing_line(line_id),
            FOREIGN KEY (department_code) REFERENCES departments(code)
        )
    """)
    # SQLite treats NULL as distinct in UNIQUE — fine for the centralised case
    # where exactly one (NULL, dept_code) row should exist. Index to enforce
    # the per-line case (no duplicate (line_code, dept) pairs).
    conn.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_stations_line_dept
            ON stations(line_code, department_code)
    """)

    # ── Factory Assistant memory (2.19.0) ──────────────────────
    # fa_conversations: every chat turn, keyed by browser session_id, so the
    # assistant can recall the current conversation across requests.
    conn.execute("""
        CREATE TABLE IF NOT EXISTS fa_conversations (
            id          TEXT PRIMARY KEY,        -- UUID
            session_id  TEXT NOT NULL,
            user_id     TEXT NOT NULL,
            role        TEXT NOT NULL,           -- 'user' | 'assistant'
            content     TEXT NOT NULL,
            tool_calls  TEXT,                    -- JSON, nullable
            created_at  TEXT DEFAULT (datetime('now'))
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_fa_conv_session ON fa_conversations(session_id)")

    # fa_knowledge: durable operational insights — either observed by the
    # assistant from data, or injected by a manager. Surfaced into future
    # answers via keyword match.
    conn.execute("""
        CREATE TABLE IF NOT EXISTS fa_knowledge (
            id                 TEXT PRIMARY KEY,  -- UUID
            category           TEXT NOT NULL,     -- line_behaviour|supplier|seasonal|ncg_pattern|material|general
            title              TEXT NOT NULL,
            content            TEXT NOT NULL,
            source             TEXT NOT NULL,     -- assistant_observed|manager_input
            confidence         TEXT DEFAULT 'medium',  -- low|medium|high
            created_at         TEXT DEFAULT (datetime('now')),
            last_referenced_at TEXT
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_fa_knowledge_category ON fa_knowledge(category)")

    # Seed a default 11:00 refuel window if the table is empty
    if conn.execute("SELECT COUNT(*) FROM refuel_windows").fetchone()[0] == 0:
        conn.execute("""INSERT INTO refuel_windows
            (label, start_hour, start_min, cutoff_hour, cutoff_min, active, notes)
            VALUES ('Default Mid-day Slot', 11, 0, 10, 30, 1,
                    'Default daily refueling window — adjust in Warehouse → Forklift Refueling → Settings')""")
        conn.commit()
    for sql in _migrations:
        try:
            conn.execute(sql)
            conn.commit()
        except Exception:
            pass  # column already exists

    # ── One-time seed of bom_lines.waste_factor (idempotent: only NULLs) ──
    # Preserve the historical 5% on existing veneer lines (seq 2/3) and fix
    # boards (seq 1) + everything else to 0%. New rows get an explicit value
    # from save_bom_for_sku, so this never re-fires.
    try:
        conn.execute("""
            UPDATE bom_lines
               SET waste_factor = CASE WHEN seq IN (2,3) THEN 0.05 ELSE 0 END
             WHERE waste_factor IS NULL
        """)
        conn.commit()
    except Exception:
        pass

    # ── Backfill glue_mix_batches from existing glue_mix_log (idempotent) ──
    # Captures each mix's primary batch_id plus any batch numbers recorded in
    # the legacy "[Shared mix across batches: …]" notes tag, so historical
    # shared mixes are linked. INSERT OR IGNORE keeps it safe to run each boot.
    try:
        import re as _re
        for r in conn.execute("SELECT mix_id, batch_id, notes FROM glue_mix_log").fetchall():
            bns = set()
            if r['batch_id']:
                bns.add(str(r['batch_id']).strip())
            m = _re.search(r'Shared mix across batches:\s*([^\]]+)', r['notes'] or '')
            if m:
                for bn in m.group(1).split(','):
                    bn = bn.strip()
                    if bn:
                        bns.add(bn)
            for bn in bns:
                conn.execute(
                    "INSERT OR IGNORE INTO glue_mix_batches (mix_id, batch_number) VALUES (?,?)",
                    (r['mix_id'], bn))
        conn.commit()
    except Exception:
        pass

    # ── Seed actual PV Wood glue recipes (idempotent: keyed by recipe_code) ──
    _seed_real_glue_recipes(conn)
    # ── Seed lines, departments, line flow (idempotent) ─────────────
    _seed_lines_and_departments(conn)
    # ── Bootstrap admin on a brand-new DB so a fresh install can log in ──
    _seed_default_admin(conn)
    # Phase B cleanup removed glue_formula placeholders from materials entirely;
    # _normalize_glue_materials is no longer needed.

    conn.close()


# ── Real PV Wood glue recipes (from spreadsheet) ─────────────────
# Format: (recipe_code, name, veneer_thickness, wood_species, core_board,
#          e0, latex_g312, flour, yellow_pig, hardener, red_pig, black_pig, titanium, total_kg)
PV_GLUE_RECIPES = [
    ('Glue 1',  'Glue 1',  '0.15-0.25', 'W.Oak, Hickory',                                       '',                  36, 5,  11, 0.15, 0,     0,    0,    1.0, 53.15),
    ('Glue 2',  'Glue 2',  '0.15-0.25', 'RED OAK M2, Cherry, Beech, Alder',                     '',                  36, 5,  12, 0.15, 0,     0.06, 0,    1.0, 54.21),
    ('Glue 3',  'Glue 3',  '0.15-0.25', 'W.ASH',                                                '',                  36, 5,  11, 0,    0,     0,    0,    1.0, 53.0),
    ('Glue 4',  'Glue 4',  '0.15mm',    'US SAPELE, MAHOGANY',                                  '',                  36, 5,  11, 0.1,  0.002, 0.15, 0,    0.5, 52.752),
    ('Glue 5',  'Glue 5',  '0.2mm',     'TEAK DS, WALNUT',                                      '',                  36, 5,  11, 0.1,  0,     0.035,0.14, 0.2, 52.475),
    ('Glue 6',  'Glue 6',  '0.2-0.6mm', 'DS BIRCH, DS W.BIRCH',                                 '',                  36, 24, 11, 0.1,  0,     0,    0,    0.5, 71.6),
    ('Glue 7',  'Glue 7',  '',          'DS OKOUME, SAPELE (WPF), LAUAN, Engineered Hardwood',  '',                  36, 0,  10, 0.02, 0,     0.035,0,    0,   46.055),
    ('Glue 8',  'Glue 8',  '0.4-0.6mm', 'MAPLE',                                                'MDF',               36, 5,  10, 0,    0.002, 0,    0,    0,   51.002),
    ('Glue 9',  'Glue 9',  '0.3-0.5mm', 'Red Oak, Hickory, Alder, Beech, Knotty Pine, Cherry, W.Oak, ASH, WALNUT, APITONG', '', 36, 5, 11, 0, 0, 0, 0, 0, 52.0),
    ('Glue 10', 'Glue 10', '0.2-0.3mm', 'W.MAPLE',                                              'VC (Plywood), PB',  36, 5,  10, 0.25, 0,     0,    0,    1.5, 52.75),
    ('Glue 11', 'Glue 11', '0.2-0.3mm', 'W.MAPLE',                                              'MDF',               36, 5,  10, 0.1,  0,     0,    0,    0.5, 51.6),
    ('Glue 12', 'Glue 12', '0.3mm',     'W.MAPLE',                                              'VC (Platform)',     36, 5,  12, 0.5,  0,     0,    0,    3.0, 56.5),
    ('Glue 13', 'Glue 13', '',          'W.BIRCH, N.BIRCH',                                     '',                  36, 24, 12, 0.5,  0,     0,    0,    3.0, 75.5),
    ('Glue 14', 'Glue 14', '0.2mm',     'EV POPLAR',                                            '',                  36, 0,  11, 0,    0,     0,    0,    1.0, 48.0),
]

def _seed_real_glue_recipes(conn):
    """Replace any existing recipes with the canonical 14 PV Wood recipes (idempotent by recipe_code)."""
    # Delete legacy placeholder recipes (UF/PF/MR fakes from before)
    conn.execute("DELETE FROM glue_recipes WHERE recipe_code LIKE 'GLU-%'")
    for r in PV_GLUE_RECIPES:
        code, name, vthk, species, core, e0, latex, flour, yp, hd, rp, bp, ti, total = r
        existing = conn.execute("SELECT id FROM glue_recipes WHERE recipe_code=?", (code,)).fetchone()
        if existing:
            conn.execute("""UPDATE glue_recipes SET name=?, veneer_thickness=?, wood_species=?, core_board=?,
                e0_glue_kg=?, latex_g312_kg=?, flour_kg=?, yellow_pigment_kg=?, hardener_kg=?,
                red_pigment_kg=?, black_pigment_kg=?, titanium_kg=?, total_kg=?, is_active=1
                WHERE id=?""",
                (name, vthk, species, core, e0, latex, flour, yp, hd, rp, bp, ti, total, existing['id']))
        else:
            conn.execute("""INSERT INTO glue_recipes
                (recipe_code, name, veneer_thickness, wood_species, core_board,
                 e0_glue_kg, latex_g312_kg, flour_kg, yellow_pigment_kg, hardener_kg,
                 red_pigment_kg, black_pigment_kg, titanium_kg, total_kg, is_active, mix_time_min)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,1,20)""",
                (code, name, vthk, species, core, e0, latex, flour, yp, hd, rp, bp, ti, total))
    conn.commit()


# ── Lines + Departments + Line Flow seed ─────────────────────
# Single source of truth: edit these tuples to add/rename a line or dept.
# All inserts are upserts keyed by primary key so re-running init_db is safe.

# (code, label, line_type, sort_order)
_DEFAULT_LINES = [
    ('P01', 'Production Line 01', 'main', 1),
    ('P02', 'Production Line 02', 'main', 2),
    ('P37', 'Production Line 37', 'main', 3),
    ('PUV', 'UV Line',             'aux',  10),
    ('PVS', 'Veneer Slicing',      'aux',  11),
    ('PSP', 'Veneer Splicing',     'aux',  12),
]

# (code, label, icon, is_centralised, sort_order)
_DEFAULT_DEPARTMENTS = [
    ('fc',            'FC / Cutting',  'bi-box-seam',    0,  1),
    ('laminating',    'Laminating',    'bi-layers',      0,  2),
    ('cold_press',    'Cold Press',    'bi-snow',        0,  3),
    ('hot_press',     'Hot Press',     'bi-fire',        0,  4),
    ('bleach',        'Bleach',        'bi-droplet',     0,  5),
    ('repair',        'Repair',        'bi-tools',       0,  6),
    ('sanding',       'Sanding',       'bi-circle-half', 0,  7),
    ('grading',       'Grading',       'bi-stars',       0,  8),
    ('packing',       'Packing',       'bi-box',         1,  9),  # centralised
    ('fg_receiving',  'FG Receiving',  'bi-inbox',       1, 10),  # centralised
    ('fg_warehouse',  'FG Warehouse',  'bi-building',    1, 11),  # centralised
]

# Production flow per line. Aux lines have no flow (they're request-only hubs).
# Each list = department code sequence the line traverses.
_DEFAULT_FLOW = {
    'P01': ['fc', 'laminating', 'cold_press', 'hot_press', 'bleach', 'repair', 'sanding', 'grading', 'packing', 'fg_warehouse'],
    'P02': ['fc', 'laminating', 'cold_press', 'hot_press', 'bleach', 'repair', 'sanding', 'grading', 'packing', 'fg_warehouse'],
    'P37': ['fc', 'laminating', 'cold_press', 'hot_press', 'bleach', 'repair', 'sanding', 'grading', 'packing', 'fg_warehouse'],
}

def _seed_lines_and_departments(conn):
    """Upsert default lines, departments, and per-line flow. Idempotent:
    existing rows keep their is_active state; only label/icon/sort_order
    get refreshed from the canonical lists above. To remove a line/dept
    cleanly, set is_active=0 in the DB (don't delete — rows in batches or
    consumable_request may reference it)."""
    for code, label, ltype, order in _DEFAULT_LINES:
        existing = conn.execute(
            "SELECT line_id FROM manufacturing_line WHERE line_id=?", (code,)).fetchone()
        if existing:
            conn.execute("""UPDATE manufacturing_line
                            SET line_name=?, line_type=?, sort_order=?
                            WHERE line_id=?""",
                         (label, ltype, order, code))
        else:
            conn.execute("""INSERT INTO manufacturing_line
                            (line_id, line_name, active, line_type, sort_order)
                            VALUES (?,?,1,?,?)""",
                         (code, label, ltype, order))

    for code, label, icon, centralised, order in _DEFAULT_DEPARTMENTS:
        existing = conn.execute(
            "SELECT code FROM departments WHERE code=?", (code,)).fetchone()
        if existing:
            conn.execute("""UPDATE departments SET label=?, icon=?,
                            is_centralised=?, sort_order=? WHERE code=?""",
                         (label, icon, centralised, order, code))
        else:
            conn.execute("""INSERT INTO departments
                            (code, label, icon, is_centralised, sort_order, is_active)
                            VALUES (?,?,?,?,?,1)""",
                         (code, label, icon, centralised, order))

    # Replace line_flow rows for known lines (so renaming the flow is just
    # editing _DEFAULT_FLOW). Untouched lines keep their custom flow if any.
    for line_code, depts in _DEFAULT_FLOW.items():
        conn.execute("DELETE FROM line_flow WHERE line_code=?", (line_code,))
        for i, dept_code in enumerate(depts):
            conn.execute("""INSERT INTO line_flow (line_code, seq, department_code)
                            VALUES (?,?,?)""", (line_code, i, dept_code))

    # Stations — one row per (line, per-line dept), plus one row per
    # centralised dept with line_code=NULL. Idempotent: skip if the pair
    # already exists. Labels reuse the dept's display label so renaming a
    # department (in _DEFAULT_DEPARTMENTS) propagates here on next boot.
    dept_label = {d[0]: d[1]      for d in _DEFAULT_DEPARTMENTS}
    centralised = {d[0]           for d in _DEFAULT_DEPARTMENTS if d[3] == 1}
    for line_code, depts in _DEFAULT_FLOW.items():
        for dept in depts:
            if dept in centralised: continue   # handled below
            existing = conn.execute(
                "SELECT id FROM stations WHERE line_code=? AND department_code=?",
                (line_code, dept)).fetchone()
            label = f"{line_code} · {dept_label.get(dept, dept)}"
            if existing:
                conn.execute("UPDATE stations SET label=? WHERE id=?", (label, existing[0]))
                continue
            conn.execute("""INSERT INTO stations
                            (line_code, department_code, label, is_active)
                            VALUES (?,?,?,1)""", (line_code, dept, label))
    for dept_code in centralised:
        existing = conn.execute(
            "SELECT id FROM stations WHERE line_code IS NULL AND department_code=?",
            (dept_code,)).fetchone()
        label = f"{dept_label.get(dept_code, dept_code)} (all lines)"
        if existing:
            conn.execute("UPDATE stations SET label=? WHERE id=?", (label, existing[0]))
            continue
        conn.execute("""INSERT INTO stations
                        (line_code, department_code, label, is_active)
                        VALUES (NULL,?,?,1)""", (dept_code, label))
    conn.commit()


# `_normalize_glue_materials` was removed in Phase B. Glue placeholders no
# longer exist in the materials table — recipes live in glue_recipes and
# FG BOM lines link to them via bom_lines.glue_recipe_id.


# ═══════════════════════════════════════════════════════════════
# MATERIALS
# ═══════════════════════════════════════════════════════════════
# Internal helpers — pass the open connection in. The repeated
# `SELECT * FROM materials WHERE id=?` / `WHERE code=?` patterns used to
# be inlined at 16+ call sites; centralising lets schema additions land
# in one place. Helpers return the raw Row / scalar — callers wrap with
# row_to_dict() when they need a dict.
def _mat_by_id(conn, mid):
    """Return the materials row for an id, or None."""
    if mid is None: return None
    return conn.execute("SELECT * FROM materials WHERE id=?", (mid,)).fetchone()

def _mat_by_code(conn, code):
    """Return the materials row for a code, or None."""
    if not code: return None
    return conn.execute("SELECT * FROM materials WHERE code=?", (code,)).fetchone()

def _mat_id_by_code(conn, code):
    """Return materials.id for a code, or None if not present."""
    if not code: return None
    row = conn.execute("SELECT id FROM materials WHERE code=?", (code,)).fetchone()
    return row[0] if row else None


def get_all_materials():
    conn = get_db()
    rows = conn.execute("SELECT * FROM materials ORDER BY type, name").fetchall()
    conn.close(); return rows_to_list(rows)

def get_material(mid):
    conn = get_db()
    row = _mat_by_id(conn, mid)
    conn.close(); return row_to_dict(row)

def create_material(data):
    conn = get_db()
    cur = conn.execute(
        """INSERT INTO materials
           (name,type,unit,current_stock,reorder_point,unit_cost,supplier,
            thickness_mm,width_mm,length_mm,auto_glue_code)
           VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        (data['name'], data['type'], data['unit'],
         data.get('current_stock', 0), data.get('reorder_point', 0),
         data.get('unit_cost', 0), data.get('supplier', ''),
         data.get('thickness_mm'), data.get('width_mm'), data.get('length_mm'),
         data.get('auto_glue_code'))
    )
    conn.commit()
    row = _mat_by_id(conn, cur.lastrowid)
    conn.close(); return row_to_dict(row)

def update_material(mid, data):
    """Update an existing materials row. `code` was previously missing from
    the SET clause — edits to the SKU code silently dropped."""
    conn = get_db()
    # Normalise code: empty string → NULL so the UNIQUE-friendly behaviour works
    new_code = (data.get('code') or '').strip() or None
    conn.execute(
        """UPDATE materials
           SET code=?,name=?,type=?,unit=?,current_stock=?,reorder_point=?,
               unit_cost=?,supplier=?,
               thickness_mm=?,width_mm=?,length_mm=?,auto_glue_code=?
           WHERE id=?""",
        (new_code, data['name'], data['type'], data['unit'],
         data.get('current_stock', 0), data.get('reorder_point', 0),
         data.get('unit_cost', 0), data.get('supplier', ''),
         data.get('thickness_mm'), data.get('width_mm'), data.get('length_mm'),
         data.get('auto_glue_code'), mid)
    )
    conn.commit()
    row = _mat_by_id(conn, mid)
    conn.close(); return row_to_dict(row)

def delete_material(mid):
    conn = get_db(); conn.execute("DELETE FROM materials WHERE id=?",(mid,)); conn.commit(); conn.close()

def bulk_upsert_material(data):
    """
    Upsert a material. Looks up existing row by code first, then by name.
    Supports core fields plus extended veneer / board attributes:
      Veneer: species, cut_type, grade, matching, face_back, fsc
      Board:  board_type, glue_type, fsc
      Both:   thickness_mm, width_mm, length_mm
    Any field not present in the CSV row is preserved on existing rows.
    """
    conn = get_db()
    code = (data.get('code') or '').strip()
    name = (data.get('name') or '').strip()
    if not name:
        conn.close()
        raise ValueError("name is required")

    ex = None
    if code:
        ex = _mat_by_code(conn, code)
    if not ex:
        ex = conn.execute("SELECT * FROM materials WHERE name=?", (name,)).fetchone()

    # Helpers
    def _f(k, default=None):
        v = data.get(k)
        if v is None or v == '': return default
        try: return float(v)
        except Exception: return default
    def _s(k, default=''):
        v = data.get(k)
        return default if v is None else str(v).strip()

    # Normalise category labels to internal type codes so CSV imports work
    # regardless of whether the user-facing label or the internal code is used.
    _TYPE_ALIAS = {
        'veneer':            'veneer_sheet',
        'veneers':           'veneer_sheet',
        'veneer_sheet':      'veneer_sheet',
        'veneer sheet':      'veneer_sheet',
        'board':             'core_board',
        'boards':            'core_board',
        'core_board':        'core_board',
        'core board':        'core_board',
        # Anything in the "Consumables bucket"
        'consumable':        'adhesive',
        'consumables':       'adhesive',
        'adhesive':          'adhesive',
        'chemical':          'adhesive',
        'edge_banding':      'adhesive',
        'glue':              'glue_formula',
        'glues':             'glue_formula',
        'glue and additives':'glue_formula',
        'glue and additive': 'glue_formula',
        'glue_formula':      'glue_formula',
        'glue formula':      'glue_formula',
        'additive':          'glue_formula',
        'additives':         'glue_formula',
        'packing':           'packing',
        'packaging':         'packing',
        'pack':              'packing',
        'other':             'other',
        'others':            'other',
        'misc':              'other',
        'miscellaneous':     'other',
    }
    if data.get('type'):
        raw_t = str(data['type']).strip().lower()
        data['type'] = _TYPE_ALIAS.get(raw_t, raw_t)

    # Existing row column set (so we don't crash if a column is absent in older DBs)
    existing_cols = {r[1] for r in conn.execute("PRAGMA table_info(materials)").fetchall()}

    # Build a column-by-column update dict based on what's actually in the CSV row.
    # Core fields always overwrite (using defaults for missing).
    # `min_stock` is the canonical CSV header for the materials.reorder_point
    # column — accept both names so older CSVs still import cleanly.
    _min_csv = data.get('min_stock') if data.get('min_stock') not in (None, '') else data.get('reorder_point')
    fields = {
        'code':           code if code else (ex['code'] if ex else ''),
        'name':           name,
        'type':           _s('type', ex['type'] if ex else 'other'),
        'unit':           _s('unit', ex['unit'] if ex else 'pcs'),
        'current_stock':  _f('current_stock', float(ex['current_stock']) if ex and ex['current_stock'] is not None else 0),
        'reorder_point':  (float(_min_csv) if _min_csv not in (None, '') else (float(ex['reorder_point']) if ex and ex['reorder_point'] is not None else 0)),
        'unit_cost':      _f('unit_cost', float(ex['unit_cost']) if ex and ex['unit_cost'] is not None else 0),
        'supplier':       _s('supplier', ex['supplier'] if ex else ''),
    }
    # Extended veneer + board fields — only included if column exists AND CSV has the value
    extended_keys = ['thickness_mm','width_mm','length_mm',
                     'species','cut_type','grade','matching','face_back','fsc',
                     'board_type','glue_type',
                     # 2.6.1: surfaced in exports → also accept on import
                     'acc_code','name_th','name_zh','auto_glue_code','fc_stock']
    _numeric_extended = {'thickness_mm','width_mm','length_mm','fc_stock'}
    for k in extended_keys:
        if k not in existing_cols: continue
        if k in data and data.get(k) not in (None, ''):
            if k in _numeric_extended:
                fields[k] = _f(k)
            else:
                fields[k] = _s(k)

    if ex:
        cols = ', '.join(f'{k}=?' for k in fields.keys())
        params = list(fields.values()) + [ex['id']]
        conn.execute(f"UPDATE materials SET {cols} WHERE id=?", params)
        mid = ex['id']; action = 'updated'
    else:
        cols = ', '.join(fields.keys())
        ph   = ', '.join('?' for _ in fields)
        cur = conn.execute(f"INSERT INTO materials ({cols}) VALUES ({ph})", list(fields.values()))
        mid = cur.lastrowid; action = 'created'

    conn.commit(); conn.close()
    return {'id': mid, 'name': name, 'code': fields['code'], 'action': action}

# ═══════════════════════════════════════════════════════════════
# PRODUCTS
# ═══════════════════════════════════════════════════════════════
def get_all_products():
    conn = get_db()
    rows = conn.execute("SELECT * FROM products ORDER BY name").fetchall()
    conn.close(); return rows_to_list(rows)

def get_product(pid):
    conn = get_db()
    row = conn.execute("SELECT * FROM products WHERE id=?",(pid,)).fetchone()
    conn.close(); return row_to_dict(row)

def create_product(data):
    conn = get_db()
    cur = conn.execute(
        "INSERT INTO products (name,sku,description,unit,selling_price) VALUES (?,?,?,?,?)",
        (data['name'],data['sku'],data.get('description',''),data.get('unit','sheet'),data.get('selling_price',0))
    )
    conn.commit()
    row = conn.execute("SELECT * FROM products WHERE id=?",(cur.lastrowid,)).fetchone()
    conn.close(); return row_to_dict(row)

def update_product(pid, data):
    conn = get_db()
    conn.execute(
        "UPDATE products SET name=?,sku=?,description=?,unit=?,selling_price=? WHERE id=?",
        (data['name'],data['sku'],data.get('description',''),data.get('unit','sheet'),data.get('selling_price',0),pid)
    )
    conn.commit()
    row = conn.execute("SELECT * FROM products WHERE id=?",(pid,)).fetchone()
    conn.close(); return row_to_dict(row)

def delete_product(pid):
    conn = get_db(); conn.execute("DELETE FROM products WHERE id=?",(pid,)); conn.commit(); conn.close()

# ═══════════════════════════════════════════════════════════════
# BOM
# ═══════════════════════════════════════════════════════════════
def get_bom_for_product(pid):
    conn = get_db()
    rows = conn.execute("""
        SELECT b.*,m.name as material_name,m.type as material_type,
               m.unit as material_unit,m.current_stock,m.unit_cost
        FROM bom b JOIN materials m ON b.material_id=m.id WHERE b.product_id=? ORDER BY m.type,m.name
    """,(pid,)).fetchall()
    conn.close(); return rows_to_list(rows)

def get_all_bom():
    conn = get_db()
    rows = conn.execute("""
        SELECT b.*,p.name as product_name,p.sku,m.name as material_name,
               m.type as material_type,m.unit as material_unit
        FROM bom b JOIN products p ON b.product_id=p.id JOIN materials m ON b.material_id=m.id
        ORDER BY p.name,m.type
    """).fetchall()
    conn.close(); return rows_to_list(rows)

def create_bom_entry(data):
    conn = get_db()
    cur = conn.execute(
        "INSERT INTO bom (product_id,material_id,quantity_per_unit,waste_factor,notes) VALUES (?,?,?,?,?)",
        (data['product_id'],data['material_id'],data['quantity_per_unit'],data.get('waste_factor',0.05),data.get('notes',''))
    )
    conn.commit()
    row = conn.execute("""SELECT b.*,m.name as material_name,m.type as material_type,
        m.unit as material_unit,m.current_stock,m.unit_cost FROM bom b JOIN materials m ON b.material_id=m.id WHERE b.id=?
    """,(cur.lastrowid,)).fetchone()
    conn.close(); return row_to_dict(row)

def update_bom_entry(bid, data):
    conn = get_db()
    conn.execute("UPDATE bom SET quantity_per_unit=?,waste_factor=?,notes=? WHERE id=?",
                 (data['quantity_per_unit'],data.get('waste_factor',0.05),data.get('notes',''),bid))
    conn.commit()
    row = conn.execute("""SELECT b.*,m.name as material_name,m.type as material_type,
        m.unit as material_unit,m.current_stock,m.unit_cost FROM bom b JOIN materials m ON b.material_id=m.id WHERE b.id=?
    """,(bid,)).fetchone()
    conn.close(); return row_to_dict(row)

def delete_bom_entry(bid):
    conn = get_db(); conn.execute("DELETE FROM bom WHERE id=?",(bid,)); conn.commit(); conn.close()

def bulk_upsert_bom(data):
    conn = get_db()
    product = conn.execute("SELECT * FROM products WHERE sku=?",(data['product_sku'],)).fetchone()
    if not product:
        conn.close(); return {'error':f"SKU '{data['product_sku']}' not found",'row':data}
    # Look up material by code first, then by name
    mat_code = data.get('material_code','').strip()
    material = None
    if mat_code:
        material = conn.execute("SELECT * FROM materials WHERE code=?",(mat_code,)).fetchone()
    if not material:
        material = conn.execute("SELECT * FROM materials WHERE name=?",(data['material_name'],)).fetchone()
    if not material:
        cur = conn.execute("INSERT INTO materials (code,name,type,unit) VALUES (?,?,?,?)",
                           (mat_code,data['material_name'],data.get('material_type','other'),data.get('unit','pcs')))
        material_id = cur.lastrowid; mat_action='created'
    else:
        material_id = material['id']; mat_action='found'
    veneer_role = data.get('veneer_role','').strip().lower()
    if veneer_role not in ('face','back',''):
        veneer_role = ''
    # Upsert: if same product+material+veneer_role exists update it; otherwise insert
    existing = conn.execute(
        "SELECT * FROM bom WHERE product_id=? AND material_id=? AND veneer_role=?",
        (product['id'],material_id,veneer_role)).fetchone()
    qty = float(data.get('qty_per_unit', data.get('quantity_per_unit',1)))
    waste = float(data.get('waste_factor',0.05))
    if existing:
        conn.execute("UPDATE bom SET quantity_per_unit=?,waste_factor=?,notes=? WHERE id=?",
                     (qty,waste,data.get('notes',''),existing['id'])); bom_action='updated'
    else:
        conn.execute(
            "INSERT INTO bom (product_id,material_id,quantity_per_unit,waste_factor,veneer_role,notes) VALUES (?,?,?,?,?,?)",
            (product['id'],material_id,qty,waste,veneer_role,data.get('notes',''))); bom_action='created'
    conn.commit(); conn.close()
    return {'product_sku':data['product_sku'],'material_name':data['material_name'],
            'veneer_role':veneer_role,'material_action':mat_action,'bom_action':bom_action}

# ═══════════════════════════════════════════════════════════════
# MACHINES
# ═══════════════════════════════════════════════════════════════
def get_all_machines():
    conn = get_db()
    rows = conn.execute("SELECT * FROM machines ORDER BY type,name").fetchall()
    conn.close(); return rows_to_list(rows)

def get_machine(mid):
    conn = get_db()
    row = conn.execute("SELECT * FROM machines WHERE id=?",(mid,)).fetchone()
    conn.close(); return row_to_dict(row)

def create_machine(data):
    conn = get_db()
    cur = conn.execute(
        """INSERT INTO machines
           (name, type, dept, production_line, capacity_per_shift, capacity_per_hour,
            status, last_maintenance, next_maintenance, notes)
           VALUES (?,?,?,?,?,?,?,?,?,?)""",
        (data['name'], data.get('type', data.get('dept', '')),
         data.get('dept', data.get('type', '')),
         data.get('production_line', ''),
         float(data.get('capacity_per_shift') or 0),
         float(data.get('capacity_per_hour') or 0),
         data.get('status', 'active'),
         data.get('last_maintenance', ''), data.get('next_maintenance', ''),
         data.get('notes', ''))
    )
    conn.commit()
    row = conn.execute("SELECT * FROM machines WHERE id=?", (cur.lastrowid,)).fetchone()
    conn.close(); return row_to_dict(row)

def update_machine(mid, data):
    conn = get_db()
    conn.execute(
        """UPDATE machines SET name=?, type=?, dept=?, production_line=?,
           capacity_per_shift=?, capacity_per_hour=?, status=?,
           last_maintenance=?, next_maintenance=?, notes=? WHERE id=?""",
        (data['name'], data.get('type', data.get('dept', '')),
         data.get('dept', data.get('type', '')),
         data.get('production_line', ''),
         float(data.get('capacity_per_shift') or 0),
         float(data.get('capacity_per_hour') or 0),
         data.get('status', 'active'),
         data.get('last_maintenance', ''), data.get('next_maintenance', ''),
         data.get('notes', ''), mid)
    )
    conn.commit()
    row = conn.execute("SELECT * FROM machines WHERE id=?", (mid,)).fetchone()
    conn.close(); return row_to_dict(row)

def delete_machine(mid):
    conn = get_db(); conn.execute("DELETE FROM machines WHERE id=?",(mid,)); conn.commit(); conn.close()

# ═══════════════════════════════════════════════════════════════
# ORDERS (Legacy / Customer Orders)
# ═══════════════════════════════════════════════════════════════
def get_all_orders():
    conn = get_db()
    rows = conn.execute("""
        SELECT o.*,p.name as product_name,p.sku FROM orders o JOIN products p ON o.product_id=p.id
        ORDER BY o.priority,o.due_date
    """).fetchall()
    conn.close(); return rows_to_list(rows)

def get_order(oid):
    conn = get_db()
    row = conn.execute("SELECT o.*,p.name as product_name,p.sku FROM orders o JOIN products p ON o.product_id=p.id WHERE o.id=?",(oid,)).fetchone()
    conn.close(); return row_to_dict(row)

def create_order(data):
    conn = get_db()
    cur = conn.execute(
        "INSERT INTO orders (order_number,customer,product_id,quantity,produced_qty,due_date,status,priority,notes) VALUES (?,?,?,?,?,?,?,?,?)",
        (data['order_number'],data['customer'],data['product_id'],data['quantity'],
         data.get('produced_qty',0),data['due_date'],data.get('status','pending'),data.get('priority',3),data.get('notes',''))
    )
    conn.commit()
    row = conn.execute("SELECT o.*,p.name as product_name,p.sku FROM orders o JOIN products p ON o.product_id=p.id WHERE o.id=?",(cur.lastrowid,)).fetchone()
    conn.close(); return row_to_dict(row)

def update_order(oid, data):
    conn = get_db()
    conn.execute(
        "UPDATE orders SET order_number=?,customer=?,product_id=?,quantity=?,produced_qty=?,due_date=?,status=?,priority=?,notes=? WHERE id=?",
        (data['order_number'],data['customer'],data['product_id'],data['quantity'],
         data.get('produced_qty',0),data['due_date'],data.get('status','pending'),data.get('priority',3),data.get('notes',''),oid)
    )
    conn.commit()
    row = conn.execute("SELECT o.*,p.name as product_name,p.sku FROM orders o JOIN products p ON o.product_id=p.id WHERE o.id=?",(oid,)).fetchone()
    conn.close(); return row_to_dict(row)

def delete_order(oid):
    conn = get_db(); conn.execute("DELETE FROM orders WHERE id=?",(oid,)); conn.commit(); conn.close()

# ═══════════════════════════════════════════════════════════════
# PRODUCTION LOGS
# ═══════════════════════════════════════════════════════════════
def get_all_production_logs(date_filter=None):
    conn = get_db()
    base = """SELECT pl.*,p.name as product_name,p.sku,m.name as machine_name,o.order_number
              FROM production_logs pl JOIN products p ON pl.product_id=p.id
              JOIN machines m ON pl.machine_id=m.id LEFT JOIN orders o ON pl.order_id=o.id"""
    if date_filter:
        rows = conn.execute(base+" WHERE pl.log_date=? ORDER BY pl.shift,pl.created_at",(date_filter,)).fetchall()
    else:
        rows = conn.execute(base+" ORDER BY pl.log_date DESC,pl.shift LIMIT 500").fetchall()
    conn.close(); return rows_to_list(rows)

def create_production_log(data):
    conn = get_db()
    cur = conn.execute(
        """INSERT INTO production_logs
           (log_date,shift,product_id,machine_id,order_id,planned_qty,actual_qty,
            downtime_minutes,downtime_reason,operator_count,material_usage,notes)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
        (data['log_date'],data['shift'],data['product_id'],data['machine_id'],
         data.get('order_id'),data['planned_qty'],data['actual_qty'],
         data.get('downtime_minutes',0),data.get('downtime_reason',''),
         data.get('operator_count',1),json.dumps(data.get('material_usage',{})),data.get('notes',''))
    )
    if data.get('order_id'):
        conn.execute("UPDATE orders SET produced_qty=produced_qty+? WHERE id=?",(data['actual_qty'],data['order_id']))
    conn.commit()
    row = conn.execute("""SELECT pl.*,p.name as product_name,p.sku,m.name as machine_name,o.order_number
        FROM production_logs pl JOIN products p ON pl.product_id=p.id
        JOIN machines m ON pl.machine_id=m.id LEFT JOIN orders o ON pl.order_id=o.id WHERE pl.id=?""",(cur.lastrowid,)).fetchone()
    conn.close(); return row_to_dict(row)

def delete_production_log(lid):
    conn = get_db(); conn.execute("DELETE FROM production_logs WHERE id=?",(lid,)); conn.commit(); conn.close()

# ═══════════════════════════════════════════════════════════════
# REPORTS
# ═══════════════════════════════════════════════════════════════
def get_all_reports():
    conn = get_db()
    rows = conn.execute("SELECT * FROM reports ORDER BY generated_at DESC LIMIT 100").fetchall()
    conn.close(); return rows_to_list(rows)

def save_report(data):
    conn = get_db()
    cur = conn.execute("INSERT INTO reports (report_date,report_type,title,content) VALUES (?,?,?,?)",
                       (data['report_date'],data['report_type'],data['title'],data['content']))
    conn.commit()
    row = conn.execute("SELECT * FROM reports WHERE id=?",(cur.lastrowid,)).fetchone()
    conn.close(); return row_to_dict(row)

# ═══════════════════════════════════════════════════════════════
# PURCHASE ORDERS
# ═══════════════════════════════════════════════════════════════
def get_all_purchase_orders():
    conn = get_db()
    rows = conn.execute("""
        SELECT po.*,COUNT(DISTINCT pol.id) as line_count,COALESCE(SUM(pol.quantity),0) as total_qty
        FROM purchase_orders po LEFT JOIN po_lines pol ON pol.po_id=po.id
        GROUP BY po.id ORDER BY po.created_at DESC
    """).fetchall()
    conn.close(); return rows_to_list(rows)

def get_purchase_order(po_id):
    conn = get_db()
    po = row_to_dict(conn.execute("SELECT * FROM purchase_orders WHERE id=?",(po_id,)).fetchone())
    if po:
        po['lines'] = rows_to_list(conn.execute("""
            SELECT pol.*,p.name as product_name,p.sku FROM po_lines pol
            JOIN products p ON pol.product_id=p.id WHERE pol.po_id=?
        """,(po_id,)).fetchall())
    conn.close(); return po

def create_purchase_order(data):
    conn = get_db()
    prio = int(data.get('priority') or 2)
    if prio not in (1,2,3): prio = 2
    cur = conn.execute(
        "INSERT INTO purchase_orders (po_number,customer,order_date,delivery_date,status,notes,priority) VALUES (?,?,?,?,?,?,?)",
        (data['po_number'],data['customer'],data['order_date'],data.get('delivery_date',''),
         data.get('status','open'),data.get('notes',''),prio)
    )
    conn.commit()
    row = conn.execute("SELECT * FROM purchase_orders WHERE id=?",(cur.lastrowid,)).fetchone()
    conn.close(); return row_to_dict(row)

def update_purchase_order(po_id, data):
    conn = get_db()
    prio = int(data.get('priority') or 2)
    if prio not in (1,2,3): prio = 2
    conn.execute(
        "UPDATE purchase_orders SET po_number=?,customer=?,order_date=?,delivery_date=?,status=?,notes=?,priority=? WHERE id=?",
        (data['po_number'],data['customer'],data['order_date'],data.get('delivery_date',''),
         data.get('status','open'),data.get('notes',''),prio,po_id)
    )
    conn.commit()
    row = conn.execute("SELECT * FROM purchase_orders WHERE id=?",(po_id,)).fetchone()
    conn.close(); return row_to_dict(row)

def delete_purchase_order(po_id):
    conn = get_db(); conn.execute("DELETE FROM purchase_orders WHERE id=?",(po_id,)); conn.commit(); conn.close()

_PO_LINE_SELECT = """
    SELECT pol.*, p.name as product_name, p.sku,
           ps.code as packing_sku_code, ps.name as packing_sku_name, ps.customer as packing_customer
    FROM po_lines pol
    JOIN products p ON pol.product_id = p.id
    LEFT JOIN packing_skus ps ON ps.id = pol.packing_sku_id
"""

def get_po_lines(po_id):
    conn = get_db()
    rows = conn.execute(_PO_LINE_SELECT + " WHERE pol.po_id=? ORDER BY pol.id", (po_id,)).fetchall()
    conn.close(); return rows_to_list(rows)

def get_po_material_readiness(po_id: int) -> dict:
    """
    BOM explosion for every line in a PO using the bom_lines / skus system.
    Returns material requirements vs. current stock, per material, with shortfalls.
    """
    conn = get_db()

    # PO header
    po = row_to_dict(conn.execute("SELECT * FROM purchase_orders WHERE id=?", (po_id,)).fetchone())
    if not po:
        conn.close(); return None

    # All PO lines that have a matching product
    lines = rows_to_list(conn.execute("""
        SELECT pol.quantity, pol.product_id, p.name AS product_name, p.sku
        FROM po_lines pol
        JOIN products p ON pol.product_id = p.id
        WHERE pol.po_id = ?
        ORDER BY pol.id
    """, (po_id,)).fetchall())

    missing_bom_skus = []   # SKUs with no BOM defined
    mat_map = {}            # material_id → aggregated row

    for line in lines:
        qty_ord  = float(line['quantity'] or 0)
        sku      = line['sku']

        # Resolve SKU via skus table (BOM builder stores BOMs here)
        sku_row = conn.execute(
            "SELECT id, pallet_qty FROM skus WHERE code=?", (sku,)
        ).fetchone()

        bom_rows = []
        if sku_row:
            pallet_qty = float(sku_row[1] or 1) or 1
            bom_rows = rows_to_list(conn.execute("""
                SELECT bl.material_id, bl.qty_override, bl.usage_g_per_face,
                       m.name AS material_name, m.type AS material_type,
                       m.unit, m.current_stock, m.unit_cost
                FROM bom_lines bl
                JOIN materials m ON m.id = bl.material_id
                WHERE bl.sku_id = ?
            """, (sku_row[0],)).fetchall())

        if not bom_rows:
            if sku not in missing_bom_skus:
                missing_bom_skus.append(sku)
            continue

        for b in bom_rows:
            # Skip glue_formula materials — these are mixed components managed
            # via station stock min/max, not BOM-driven readiness checks
            if (b.get('material_type') or '').lower() == 'glue_formula':
                continue
            mid = b['material_id']
            if b['usage_g_per_face'] is not None:
                # Glue: grams per face × pallet_qty sheets / 1000 → kg per pallet
                needed = qty_ord * pallet_qty * float(b['usage_g_per_face']) / 1000.0
            else:
                # Board/veneer: qty_override sheets per pallet (default = pallet_qty)
                qty_per_pallet = float(b['qty_override'] or pallet_qty)
                needed = qty_ord * qty_per_pallet

            if mid not in mat_map:
                mat_map[mid] = {
                    'material_id':   mid,
                    'material_name': b['material_name'],
                    'material_type': b['material_type'],
                    'unit':          b['unit'],
                    'current_stock': float(b['current_stock'] or 0),
                    'unit_cost':     float(b['unit_cost'] or 0),
                    'required':      0.0,
                    'used_by':       [],
                }
            mat_map[mid]['required'] += needed
            if sku not in mat_map[mid]['used_by']:
                mat_map[mid]['used_by'].append(sku)

    # Build result rows
    STATUS_ORDER = {'short': 0, 'low': 1, 'ok': 2}
    materials = []
    total_shortfall_cost = 0.0

    for m in mat_map.values():
        req       = round(m['required'], 3)
        stock     = m['current_stock']
        shortfall = round(max(0.0, req - stock), 3)
        sc        = round(shortfall * m['unit_cost'], 2)
        total_shortfall_cost += sc

        # status: short = can't fulfill at all; low = covered but <20% buffer remains
        if shortfall > 0:
            status = 'short'
        elif stock < req * 1.20:
            status = 'low'
        else:
            status = 'ok'

        materials.append({
            **m,
            'required':        req,
            'stock':           stock,          # alias for frontend (also keeps current_stock)
            'shortfall':       shortfall,
            'shortfall_cost':  sc,
            'status':          status,
        })

    materials.sort(key=lambda r: (STATUS_ORDER[r['status']], r['material_name']))
    conn.close()

    return {
        'po_id':              po_id,
        'po_number':          po.get('po_number', ''),
        'lines_checked':      len(lines),
        'lines_no_product':   0,   # lines without a linked product are excluded above
        'lines_missing_bom':  len(missing_bom_skus),
        'missing_bom_skus':   missing_bom_skus,
        'materials':          materials,
        'total_shortfall_cost': round(total_shortfall_cost, 2),
        'has_shortfall':      any(m['status'] == 'short' for m in materials),
        'all_ok':             all(m['status'] == 'ok' for m in materials) and not missing_bom_skus,
    }

def create_po_line(data):
    conn = get_db()
    cur = conn.execute(
        "INSERT INTO po_lines (po_id,product_id,quantity,unit_price,production_line,notes,packing_sku_id,pcs_per_pallet) VALUES (?,?,?,?,?,?,?,?)",
        (data['po_id'], data['product_id'], data['quantity'], data.get('unit_price', 0),
         data.get('production_line', 'P01'), data.get('notes', ''), data.get('packing_sku_id'),
         data.get('pcs_per_pallet') or None)
    )
    conn.commit()
    row = conn.execute(_PO_LINE_SELECT + " WHERE pol.id=?", (cur.lastrowid,)).fetchone()
    conn.close(); return row_to_dict(row)

def update_po_line(line_id, data):
    conn = get_db()
    conn.execute(
        "UPDATE po_lines SET quantity=?,unit_price=?,production_line=?,notes=?,packing_sku_id=?,pcs_per_pallet=? WHERE id=?",
        (data['quantity'], data.get('unit_price', 0), data.get('production_line', 'P01'),
         data.get('notes', ''), data.get('packing_sku_id'),
         data.get('pcs_per_pallet') or None, line_id)
    )
    conn.commit()
    row = conn.execute(_PO_LINE_SELECT + " WHERE pol.id=?", (line_id,)).fetchone()
    conn.close(); return row_to_dict(row)

def delete_po_line(line_id):
    conn = get_db()
    # Nullify production_orders.po_line_id before deleting (FK constraint)
    conn.execute("UPDATE production_orders SET po_line_id=NULL WHERE po_line_id=?", (line_id,))
    conn.execute("DELETE FROM po_lines WHERE id=?", (line_id,))
    conn.commit()
    conn.close()

# ═══════════════════════════════════════════════════════════════
# PRODUCTION ORDERS
# ═══════════════════════════════════════════════════════════════
def get_all_production_orders(po_id=None):
    conn = get_db()
    base = """SELECT po.*,p.name as product_name,p.sku,
                     porder.po_number,porder.customer,
                     COUNT(DISTINCT b.id) as batch_count,
                     COALESCE(SUM(CASE WHEN b.status='active' THEN b.quantity ELSE 0 END),0) as active_qty
              FROM production_orders po
              JOIN products p ON po.product_id=p.id
              LEFT JOIN purchase_orders porder ON po.po_id=porder.id
              LEFT JOIN batches b ON b.prod_order_id=po.id"""
    if po_id:
        rows = conn.execute(base+" WHERE po.po_id=? GROUP BY po.id ORDER BY po.priority,po.created_at",(po_id,)).fetchall()
    else:
        rows = conn.execute(base+" GROUP BY po.id ORDER BY po.status,po.priority,po.created_at DESC").fetchall()
    conn.close(); return rows_to_list(rows)

def get_production_order(order_id):
    conn = get_db()
    row = conn.execute("""
        SELECT po.*,p.name as product_name,p.sku,porder.po_number,porder.customer
        FROM production_orders po JOIN products p ON po.product_id=p.id
        LEFT JOIN purchase_orders porder ON po.po_id=porder.id WHERE po.id=?
    """,(order_id,)).fetchone()
    conn.close(); return row_to_dict(row)

def create_production_order(data):
    conn = get_db()
    cur = conn.execute(
        """INSERT INTO production_orders
           (prod_order_number,po_line_id,po_id,product_id,production_line,quantity,status,priority,planned_start,planned_end,notes)
           VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        (data['prod_order_number'],data.get('po_line_id'),data.get('po_id'),
         data['product_id'],data['production_line'],data['quantity'],
         data.get('status','planned'),data.get('priority',3),
         data.get('planned_start',''),data.get('planned_end',''),data.get('notes',''))
    )
    conn.commit()
    row = conn.execute("""SELECT po.*,p.name as product_name,p.sku,porder.po_number,porder.customer
        FROM production_orders po JOIN products p ON po.product_id=p.id
        LEFT JOIN purchase_orders porder ON po.po_id=porder.id WHERE po.id=?""",(cur.lastrowid,)).fetchone()
    conn.close(); return row_to_dict(row)

def update_production_order(order_id, data):
    conn = get_db()
    conn.execute(
        """UPDATE production_orders SET prod_order_number=?,production_line=?,quantity=?,status=?,
           priority=?,planned_start=?,planned_end=?,actual_start=?,actual_end=?,notes=? WHERE id=?""",
        (data['prod_order_number'],data['production_line'],data['quantity'],data.get('status','planned'),
         data.get('priority',3),data.get('planned_start',''),data.get('planned_end',''),
         data.get('actual_start',''),data.get('actual_end',''),data.get('notes',''),order_id)
    )
    conn.commit()
    row = conn.execute("""SELECT po.*,p.name as product_name,p.sku,porder.po_number,porder.customer
        FROM production_orders po JOIN products p ON po.product_id=p.id
        LEFT JOIN purchase_orders porder ON po.po_id=porder.id WHERE po.id=?""",(order_id,)).fetchone()
    conn.close(); return row_to_dict(row)

def release_production_order(order_id):
    """Release a production order — creates an initial batch in the FC department."""
    conn = get_db()
    order = row_to_dict(conn.execute("SELECT * FROM production_orders WHERE id=?",(order_id,)).fetchone())
    if not order:
        conn.close(); return None
    conn.execute("UPDATE production_orders SET status='in_progress',actual_start=? WHERE id=?",
                 (datemod.today().isoformat(),order_id))
    # Find next available batch number — scan for the lowest unused suffix to avoid collisions
    # from prior failed releases or deleted batches
    existing_nums = {r[0] for r in conn.execute(
        "SELECT batch_number FROM batches WHERE prod_order_id=?",(order_id,)).fetchall()}
    n = 1
    while True:
        batch_num = f"BTH-{order_id:04d}-{n:03d}"
        # Also check global uniqueness in case of cross-order overlap
        if batch_num not in existing_nums and not conn.execute(
                "SELECT 1 FROM batches WHERE batch_number=? LIMIT 1",(batch_num,)).fetchone():
            break
        n += 1
        if n > 9999:
            conn.close(); raise RuntimeError("Batch number overflow")
    cur = conn.execute(
        "INSERT INTO batches (batch_number,prod_order_id,quantity,current_department,status) VALUES (?,?,?,?,?)",
        (batch_num,order_id,order['quantity'],'fc','active')
    )
    bid = cur.lastrowid
    conn.execute(
        "INSERT INTO batch_movements (batch_id,from_department,to_department,quantity,notes) VALUES (?,?,?,?,?)",
        (bid,'','fc',order['quantity'],'Initial batch — order released')
    )
    conn.commit(); conn.close()
    return {"order_id":order_id,"batch_number":batch_num,"batch_id":bid}

def delete_production_order(order_id):
    """Delete a production order and all its linked data (batches + all dept records)."""
    conn = get_db()
    # 1. Find all batch ids for this order
    batch_ids = [r[0] for r in conn.execute(
        "SELECT id FROM batches WHERE prod_order_id=?", (order_id,)).fetchall()]
    if batch_ids:
        ph = ','.join('?' for _ in batch_ids)
        for tbl in ('batch_movements','laminating_records','repair_records',
                    'sanding_records','grading_records','dept_activities'):
            conn.execute(f"DELETE FROM {tbl} WHERE batch_id IN ({ph})", batch_ids)
        conn.execute(f"DELETE FROM batches WHERE id IN ({ph})", batch_ids)
    # 2. Delete the production order itself
    conn.execute("DELETE FROM production_orders WHERE id=?", (order_id,))
    conn.commit()
    conn.close()

# ═══════════════════════════════════════════════════════════════
# BATCHES
# ═══════════════════════════════════════════════════════════════
DEPARTMENTS = ['fc','laminating','cold_press','hot_press','bleach','repair','sanding','grading','packing','fg_receiving','fg_warehouse']

def get_all_batches(department=None, prod_order_id=None):
    conn = get_db()
    base = """SELECT b.*,po.prod_order_number,po.production_line,po.quantity as order_qty,
                     po.priority, p.name as product_name,p.sku,
                     porder.po_number,porder.customer,
                     COALESCE(sk.pallet_qty, 1) as pallet_qty,
                     COALESCE(b.pcs_actual, b.quantity * COALESCE(sk.pallet_qty, 1)) as total_pcs
              FROM batches b JOIN production_orders po ON b.prod_order_id=po.id
              JOIN products p ON po.product_id=p.id
              LEFT JOIN purchase_orders porder ON po.po_id=porder.id
              LEFT JOIN skus sk ON sk.code = p.sku"""
    if department:
        rows = conn.execute(base+" WHERE b.current_department=? ORDER BY b.created_at",(department,)).fetchall()
    elif prod_order_id:
        rows = conn.execute(base+" WHERE b.prod_order_id=? ORDER BY b.created_at",(prod_order_id,)).fetchall()
    else:
        rows = conn.execute(base+" ORDER BY b.current_department,b.status,b.created_at").fetchall()
    conn.close(); return rows_to_list(rows)

def get_batch(batch_id):
    conn = get_db()
    row = conn.execute("""SELECT b.*,po.prod_order_number,po.production_line,po.quantity as order_qty,
        po.priority, p.name as product_name,p.sku,
        porder.po_number,porder.customer,
        COALESCE(sk.pallet_qty, 1) as pallet_qty,
        COALESCE(b.pcs_actual, b.quantity * COALESCE(sk.pallet_qty, 1)) as total_pcs
        FROM batches b JOIN production_orders po ON b.prod_order_id=po.id
        JOIN products p ON po.product_id=p.id
        LEFT JOIN purchase_orders porder ON po.po_id=porder.id
        LEFT JOIN skus sk ON sk.code = p.sku
        WHERE b.id=?""",(batch_id,)).fetchone()
    conn.close(); return row_to_dict(row)

def delete_batch(batch_id):
    """Void a single batch and all its dept records. Nullifies parent_batch_id on any split children."""
    conn = get_db()
    # Detach any split children so they aren't orphaned
    conn.execute("UPDATE batches SET parent_batch_id=NULL WHERE parent_batch_id=?", (batch_id,))
    # Delete all linked records
    for tbl in ('batch_movements','laminating_records','repair_records',
                'sanding_records','grading_records','dept_activities'):
        conn.execute(f"DELETE FROM {tbl} WHERE batch_id=?", (batch_id,))
    conn.execute("DELETE FROM batches WHERE id=?", (batch_id,))
    conn.commit()
    conn.close()

def move_batch(batch_id, to_department, quantity, time_minutes=0, notes='', moved_by=''):
    conn = get_db()
    try:
        batch = row_to_dict(conn.execute("SELECT * FROM batches WHERE id=?",(batch_id,)).fetchone())
        if not batch: return None
        from_dept = batch['current_department']
        conn.execute("UPDATE batches SET current_department=? WHERE id=?",(to_department,batch_id))
        conn.execute(
            "INSERT INTO batch_movements (batch_id,from_department,to_department,quantity,time_in_dept_minutes,moved_by,notes) VALUES (?,?,?,?,?,?,?)",
            (batch_id,from_dept,to_department,quantity,time_minutes,moved_by,notes)
        )
        if to_department == 'fg_warehouse':
            conn.execute("UPDATE batches SET status='completed' WHERE id=?",(batch_id,))
        conn.commit()
        row = conn.execute("SELECT * FROM batches WHERE id=?",(batch_id,)).fetchone()
        return row_to_dict(row)
    finally:
        try: conn.close()
        except Exception: pass

def split_batch(batch_id, split_qty, reason, new_dept=None, new_status='ncg'):
    conn = get_db()
    batch = row_to_dict(conn.execute("SELECT * FROM batches WHERE id=?",(batch_id,)).fetchone())
    if not batch or split_qty >= batch['quantity']:
        conn.close(); return None
    conn.execute("UPDATE batches SET quantity=? WHERE id=?",(batch['quantity']-split_qty,batch_id))
    n = conn.execute("SELECT COUNT(*) FROM batches WHERE parent_batch_id=?",(batch_id,)).fetchone()[0]
    new_num = f"{batch['batch_number']}-S{n+1:02d}"
    dept = new_dept or batch['current_department']
    cur = conn.execute(
        "INSERT INTO batches (batch_number,prod_order_id,parent_batch_id,quantity,current_department,status,split_reason) VALUES (?,?,?,?,?,?,?)",
        (new_num,batch['prod_order_id'],batch_id,split_qty,dept,new_status,reason)
    )
    new_id = cur.lastrowid
    conn.execute(
        "INSERT INTO batch_movements (batch_id,from_department,to_department,quantity,notes) VALUES (?,?,?,?,?)",
        (new_id,batch['current_department'],dept,split_qty,f"Split from {batch['batch_number']}: {reason}")
    )
    conn.commit()
    new_batch = row_to_dict(conn.execute("SELECT * FROM batches WHERE id=?",(new_id,)).fetchone())
    conn.close(); return new_batch

def _batch_total_pcs(batch_dict, conn):
    """Return effective total pcs for a batch (pcs_actual override or quantity*pallet_qty)."""
    if batch_dict.get('pcs_actual') is not None:
        return int(batch_dict['pcs_actual'])
    # Look up pallet_qty from SKU
    pallet_qty = 1
    sku_row = conn.execute("""
        SELECT sk.pallet_qty FROM batches b
        JOIN production_orders po ON po.id = b.prod_order_id
        JOIN products p ON p.id = po.product_id
        LEFT JOIN skus sk ON sk.code = p.sku
        WHERE b.id = ?""", (batch_dict['id'],)).fetchone()
    if sku_row and sku_row[0]:
        pallet_qty = int(sku_row[0])
    return int(batch_dict.get('quantity') or 0) * pallet_qty


def split_batch_by_pcs(batch_id, pcs_to_split, reason, new_dept=None, new_status='active'):
    """
    Split a batch by piece count instead of pallet count. The split-off batch gets
    pcs_actual set explicitly (no pallet rounding). The original batch's pcs_actual
    is reduced by the split amount.
    Returns the new batch row or None if invalid.
    """
    conn = get_db()
    batch = row_to_dict(conn.execute("SELECT * FROM batches WHERE id=?", (batch_id,)).fetchone())
    if not batch:
        conn.close(); return None
    total_pcs = _batch_total_pcs(batch, conn)
    pcs_to_split = int(pcs_to_split)
    if pcs_to_split <= 0 or pcs_to_split >= total_pcs:
        conn.close(); return None
    remaining = total_pcs - pcs_to_split
    # Set pcs_actual on the original to the remainder (preserve quantity/pallet_qty for accounting)
    conn.execute("UPDATE batches SET pcs_actual=? WHERE id=?", (remaining, batch_id))
    # Build new batch number
    n = conn.execute("SELECT COUNT(*) FROM batches WHERE parent_batch_id=?", (batch_id,)).fetchone()[0]
    new_num = f"{batch['batch_number']}-S{n+1:02d}"
    dept = new_dept or batch['current_department']
    # New batch keeps the original's quantity (pallet count) but pcs_actual is the precise amount
    cur = conn.execute(
        """INSERT INTO batches (batch_number, prod_order_id, parent_batch_id,
            quantity, pcs_actual, current_department, status, split_reason)
           VALUES (?,?,?,?,?,?,?,?)""",
        (new_num, batch['prod_order_id'], batch_id,
         batch['quantity'], pcs_to_split, dept, new_status, reason)
    )
    new_id = cur.lastrowid
    conn.execute(
        """INSERT INTO batch_movements (batch_id, from_department, to_department, quantity, notes)
           VALUES (?,?,?,?,?)""",
        (new_id, batch['current_department'], dept, pcs_to_split,
         f"Split {pcs_to_split} pcs from {batch['batch_number']}: {reason}")
    )
    conn.commit()
    new_batch = row_to_dict(conn.execute("SELECT * FROM batches WHERE id=?", (new_id,)).fetchone())
    conn.close()
    return new_batch


# Station-log table names that reference a batch by batch_number string
_STATION_LOG_TABLES = [
    'glue_mix_log', 'laminating_log', 'cold_press_log', 'repair_log',
    'sanding_log', 'hot_press_log', 'grading_log', 'packing_log',
]

def merge_batches(keep_batch_id, drop_batch_id):
    """
    Merge two batches that are at the same department and from the same production order.
    The 'keep' batch absorbs the 'drop' batch's pcs and station logs; the 'drop' batch is deleted.
    Returns the merged batch row or raises ValueError.
    """
    conn = get_db()
    keep = row_to_dict(conn.execute("SELECT * FROM batches WHERE id=?", (keep_batch_id,)).fetchone())
    drop = row_to_dict(conn.execute("SELECT * FROM batches WHERE id=?", (drop_batch_id,)).fetchone())
    if not keep or not drop:
        conn.close(); raise ValueError("Batch not found")
    if keep_batch_id == drop_batch_id:
        conn.close(); raise ValueError("Cannot merge a batch with itself")
    if keep['prod_order_id'] != drop['prod_order_id']:
        conn.close(); raise ValueError("Batches must be from the same production order")
    if keep['current_department'] != drop['current_department']:
        conn.close(); raise ValueError("Batches must be in the same department to merge")

    keep_pcs = _batch_total_pcs(keep, conn)
    drop_pcs = _batch_total_pcs(drop, conn)
    new_pcs = keep_pcs + drop_pcs

    # Update keep batch — set pcs_actual explicitly (sum of both)
    conn.execute("UPDATE batches SET pcs_actual=? WHERE id=?", (new_pcs, keep_batch_id))

    # Re-point all station logs from drop batch_number to keep batch_number
    for tbl in _STATION_LOG_TABLES:
        try:
            conn.execute(
                f"UPDATE {tbl} SET batch_id=? WHERE batch_id=?",
                (keep['batch_number'], drop['batch_number'])
            )
        except Exception:
            pass  # table may not exist if older DB

    # Re-point batch_movements (history)
    conn.execute("UPDATE batch_movements SET batch_id=? WHERE batch_id=?",
                 (keep_batch_id, drop_batch_id))

    # Re-point any child split batches whose parent was the drop batch
    conn.execute("UPDATE batches SET parent_batch_id=? WHERE parent_batch_id=?",
                 (keep_batch_id, drop_batch_id))

    # Log the merge as a movement
    conn.execute(
        """INSERT INTO batch_movements (batch_id, from_department, to_department, quantity, notes)
           VALUES (?,?,?,?,?)""",
        (keep_batch_id, keep['current_department'], keep['current_department'], drop_pcs,
         f"Merged batch {drop['batch_number']} ({drop_pcs} pcs) into {keep['batch_number']}")
    )

    # Delete the drop batch
    conn.execute("DELETE FROM batches WHERE id=?", (drop_batch_id,))

    conn.commit()
    merged = row_to_dict(conn.execute("SELECT * FROM batches WHERE id=?", (keep_batch_id,)).fetchone())
    conn.close()
    return merged


def find_mergeable_siblings(batch_id):
    """Return other batches in the same dept + same prod_order that could be merged with this one."""
    conn = get_db()
    b = row_to_dict(conn.execute("SELECT * FROM batches WHERE id=?", (batch_id,)).fetchone())
    if not b:
        conn.close(); return []
    rows = rows_to_list(conn.execute("""
        SELECT b.*, COALESCE(sk.pallet_qty, 1) as pallet_qty
        FROM batches b
        LEFT JOIN production_orders po ON po.id = b.prod_order_id
        LEFT JOIN products p ON p.id = po.product_id
        LEFT JOIN skus sk ON sk.code = p.sku
        WHERE b.id != ?
          AND b.prod_order_id = ?
          AND b.current_department = ?
          AND b.status = 'active'""",
        (batch_id, b['prod_order_id'], b['current_department'])
    ).fetchall())
    conn.close(); return rows


def get_batch_history(batch_id):
    conn = get_db()
    rows = conn.execute("SELECT * FROM batch_movements WHERE batch_id=? ORDER BY moved_at",(batch_id,)).fetchall()
    conn.close(); return rows_to_list(rows)

# ═══════════════════════════════════════════════════════════════
# PLANNING FLOW
# ═══════════════════════════════════════════════════════════════
def get_planning_flow():
    conn = get_db()
    batches = rows_to_list(conn.execute("""
        SELECT b.*,po.prod_order_number,po.production_line,po.quantity as order_qty,
               p.name as product_name,p.sku,porder.po_number,porder.customer
        FROM batches b JOIN production_orders po ON b.prod_order_id=po.id
        JOIN products p ON po.product_id=p.id LEFT JOIN purchase_orders porder ON po.po_id=porder.id
        WHERE b.status NOT IN ('completed') ORDER BY b.current_department,b.status,b.created_at
    """).fetchall())
    conn.close()
    flow = {d:[] for d in DEPARTMENTS}
    for b in batches:
        d = b.get('current_department','fc')
        if d in flow: flow[d].append(b)
    return flow

def get_po_flow_matrix():
    conn = get_db()
    # Per production order: quantity at each department
    po_orders = rows_to_list(conn.execute("""
        SELECT po.id,po.prod_order_number,po.production_line,po.quantity as total_qty,po.status,
               p.name as product_name,p.sku,porder.po_number,porder.customer
        FROM production_orders po JOIN products p ON po.product_id=p.id
        LEFT JOIN purchase_orders porder ON po.po_id=porder.id
        WHERE po.status NOT IN ('cancelled')
        ORDER BY porder.customer,po.prod_order_number
    """).fetchall())
    batch_dist = rows_to_list(conn.execute("""
        SELECT b.prod_order_id,b.current_department,b.status,SUM(b.quantity) as qty
        FROM batches b GROUP BY b.prod_order_id,b.current_department,b.status
    """).fetchall())
    conn.close()
    # Build distribution map
    dist_map = {}
    for row in batch_dist:
        key = row['prod_order_id']
        if key not in dist_map: dist_map[key] = {}
        d = row['current_department']
        dist_map[key][d] = dist_map[key].get(d,0) + row['qty']
    for order in po_orders:
        order['dept_dist'] = dist_map.get(order['id'],{})
    return po_orders

# ═══════════════════════════════════════════════════════════════
# DEPARTMENT RECORDS
# ═══════════════════════════════════════════════════════════════
def create_laminating_record(data):
    conn = get_db()
    cur = conn.execute(
        """INSERT INTO laminating_records
           (batch_id,record_date,shift,tables_open,glue_code,glue_qty_kg,planned_qty,actual_qty,ncg_qty,operator_count,time_minutes,notes)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
        (data['batch_id'],data['record_date'],data.get('shift','morning'),data.get('tables_open',1),
         data.get('glue_code',''),data.get('glue_qty_kg',0),data.get('planned_qty',0),
         data.get('actual_qty',0),data.get('ncg_qty',0),data.get('operator_count',2),
         data.get('time_minutes',480),data.get('notes',''))
    )
    conn.commit()
    row = conn.execute("SELECT * FROM laminating_records WHERE id=?",(cur.lastrowid,)).fetchone()
    conn.close(); return row_to_dict(row)

def get_laminating_records(batch_id=None):
    conn = get_db()
    if batch_id:
        rows = conn.execute("SELECT * FROM laminating_records WHERE batch_id=? ORDER BY record_date DESC",(batch_id,)).fetchall()
    else:
        rows = conn.execute("SELECT * FROM laminating_records ORDER BY record_date DESC LIMIT 200").fetchall()
    conn.close(); return rows_to_list(rows)

def get_laminating_stats():
    conn = get_db()
    rows = conn.execute("""
        SELECT record_date,SUM(tables_open) as total_tables,SUM(planned_qty) as planned,
               SUM(actual_qty) as actual,SUM(ncg_qty) as ncg,
               ROUND(100.0*SUM(actual_qty)/NULLIF(SUM(planned_qty),0),1) as efficiency_pct
        FROM laminating_records WHERE record_date>=date('now','-30 days')
        GROUP BY record_date ORDER BY record_date DESC
    """).fetchall()
    conn.close(); return rows_to_list(rows)

def create_repair_record(data):
    conn = get_db()
    cur = conn.execute(
        """INSERT INTO repair_records
           (batch_id,record_date,pair_name,repair_type,veneer_species,pcs_repaired,pcs_rejected,time_minutes,notes)
           VALUES (?,?,?,?,?,?,?,?,?)""",
        (data['batch_id'],data['record_date'],data['pair_name'],data['repair_type'],
         data.get('veneer_species',''),data.get('pcs_repaired',0),data.get('pcs_rejected',0),
         data.get('time_minutes',0),data.get('notes',''))
    )
    conn.commit()
    row = conn.execute("SELECT * FROM repair_records WHERE id=?",(cur.lastrowid,)).fetchone()
    conn.close(); return row_to_dict(row)

def get_repair_records(batch_id=None):
    conn = get_db()
    if batch_id:
        rows = conn.execute("SELECT * FROM repair_records WHERE batch_id=? ORDER BY record_date DESC",(batch_id,)).fetchall()
    else:
        rows = conn.execute("SELECT * FROM repair_records ORDER BY record_date DESC LIMIT 200").fetchall()
    conn.close(); return rows_to_list(rows)

def get_repair_stats():
    conn = get_db()
    by_pair = rows_to_list(conn.execute("""
        SELECT pair_name,repair_type,SUM(pcs_repaired) as total_repaired,SUM(pcs_rejected) as total_rejected,
               SUM(time_minutes) as total_minutes,
               ROUND(1.0*SUM(time_minutes)/NULLIF(SUM(pcs_repaired),0),2) as avg_min_per_pc
        FROM repair_records WHERE record_date>=date('now','-30 days')
        GROUP BY pair_name,repair_type ORDER BY pair_name
    """).fetchall())
    by_species = rows_to_list(conn.execute("""
        SELECT veneer_species,repair_type,
               ROUND(AVG(1.0*time_minutes/NULLIF(pcs_repaired,0)),2) as avg_min_per_pc,
               SUM(pcs_repaired) as total_repaired
        FROM repair_records WHERE pcs_repaired>0 AND veneer_species!='' AND record_date>=date('now','-30 days')
        GROUP BY veneer_species,repair_type ORDER BY veneer_species
    """).fetchall())
    conn.close(); return {"by_pair":by_pair,"by_species":by_species}

def create_sanding_record(data):
    conn = get_db()
    cur = conn.execute(
        """INSERT INTO sanding_records
           (batch_id,record_date,machine_name,operator,belt_id,belt_life_pcs,planned_qty,actual_qty,ncg_qty,ncg_reason,time_minutes,notes)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
        (data['batch_id'],data['record_date'],data.get('machine_name',''),data['operator'],
         data.get('belt_id',''),data.get('belt_life_pcs',0),data.get('planned_qty',0),
         data.get('actual_qty',0),data.get('ncg_qty',0),data.get('ncg_reason',''),
         data.get('time_minutes',0),data.get('notes',''))
    )
    conn.commit()
    row = conn.execute("SELECT * FROM sanding_records WHERE id=?",(cur.lastrowid,)).fetchone()
    conn.close(); return row_to_dict(row)

def get_sanding_records(batch_id=None):
    conn = get_db()
    if batch_id:
        rows = conn.execute("SELECT * FROM sanding_records WHERE batch_id=? ORDER BY record_date DESC",(batch_id,)).fetchall()
    else:
        rows = conn.execute("SELECT * FROM sanding_records ORDER BY record_date DESC LIMIT 200").fetchall()
    conn.close(); return rows_to_list(rows)

def get_sanding_stats():
    conn = get_db()
    by_op = rows_to_list(conn.execute("""
        SELECT operator,SUM(actual_qty) as total_output,SUM(ncg_qty) as total_ncg,
               ROUND(100.0*SUM(ncg_qty)/NULLIF(SUM(actual_qty),0),2) as ncg_rate_pct
        FROM sanding_records WHERE record_date>=date('now','-30 days')
        GROUP BY operator ORDER BY ncg_rate_pct DESC
    """).fetchall())
    by_belt = rows_to_list(conn.execute("""
        SELECT belt_id,SUM(actual_qty) as total_pcs,SUM(ncg_qty) as total_ncg
        FROM sanding_records WHERE belt_id!='' AND record_date>=date('now','-30 days')
        GROUP BY belt_id ORDER BY total_pcs DESC
    """).fetchall())
    conn.close(); return {"by_operator":by_op,"by_belt":by_belt}

def create_grading_record(data):
    conn = get_db()
    cur = conn.execute(
        """INSERT INTO grading_records
           (batch_id,record_date,total_graded,grade_lg,grade_c,ncg_qty,send_to_repair,send_to_sanding,grader,notes)
           VALUES (?,?,?,?,?,?,?,?,?,?)""",
        (data['batch_id'],data['record_date'],data.get('total_graded',0),
         data.get('grade_lg',0),data.get('grade_c',0),data.get('ncg_qty',0),
         data.get('send_to_repair',0),data.get('send_to_sanding',0),
         data.get('grader',''),data.get('notes',''))
    )
    conn.commit()
    row = conn.execute("SELECT * FROM grading_records WHERE id=?",(cur.lastrowid,)).fetchone()
    conn.close(); return row_to_dict(row)

def get_grading_records(batch_id=None):
    conn = get_db()
    if batch_id:
        rows = conn.execute("SELECT * FROM grading_records WHERE batch_id=? ORDER BY record_date DESC",(batch_id,)).fetchall()
    else:
        rows = conn.execute("SELECT * FROM grading_records ORDER BY record_date DESC LIMIT 200").fetchall()
    conn.close(); return rows_to_list(rows)

def create_dept_activity(data):
    conn = get_db()
    cur = conn.execute(
        """INSERT INTO dept_activities
           (batch_id,department,record_date,planned_qty,actual_qty,ncg_qty,operator,time_minutes,extra_data,notes)
           VALUES (?,?,?,?,?,?,?,?,?,?)""",
        (data['batch_id'],data['department'],data['record_date'],data.get('planned_qty',0),
         data.get('actual_qty',0),data.get('ncg_qty',0),data.get('operator',''),
         data.get('time_minutes',0),json.dumps(data.get('extra_data',{})),data.get('notes',''))
    )
    conn.commit()
    row = conn.execute("SELECT * FROM dept_activities WHERE id=?",(cur.lastrowid,)).fetchone()
    conn.close(); return row_to_dict(row)

def get_dept_activities(department=None, batch_id=None):
    conn = get_db()
    if batch_id and department:
        rows = conn.execute("SELECT * FROM dept_activities WHERE batch_id=? AND department=? ORDER BY record_date DESC",(batch_id,department)).fetchall()
    elif batch_id:
        rows = conn.execute("SELECT * FROM dept_activities WHERE batch_id=? ORDER BY record_date DESC",(batch_id,)).fetchall()
    elif department:
        rows = conn.execute("SELECT * FROM dept_activities WHERE department=? ORDER BY record_date DESC LIMIT 200",(department,)).fetchall()
    else:
        rows = conn.execute("SELECT * FROM dept_activities ORDER BY record_date DESC LIMIT 200").fetchall()
    conn.close(); return rows_to_list(rows)

# ═══════════════════════════════════════════════════════════════
# DASHBOARD & AI CONTEXT
# ═══════════════════════════════════════════════════════════════
def get_dashboard_stats():
    conn = get_db()
    today = datemod.today().isoformat()
    stats = {
        "total_products": conn.execute("SELECT COUNT(*) FROM products").fetchone()[0],
        "total_materials": conn.execute("SELECT COUNT(*) FROM materials").fetchone()[0],
        "active_orders": conn.execute("SELECT COUNT(*) FROM orders WHERE status IN ('pending','in_progress')").fetchone()[0],
        "active_pos": conn.execute("SELECT COUNT(*) FROM purchase_orders WHERE status IN ('open','in_production')").fetchone()[0],
        "active_prod_orders": conn.execute("SELECT COUNT(*) FROM production_orders WHERE status='in_progress'").fetchone()[0],
        "total_batches_wip": conn.execute("SELECT COUNT(*) FROM batches WHERE status='active'").fetchone()[0],
        "low_stock_alerts": conn.execute("SELECT COUNT(*) FROM materials WHERE current_stock<=reorder_point AND reorder_point>0").fetchone()[0],
        "active_machines": conn.execute("SELECT COUNT(*) FROM machines WHERE status='active'").fetchone()[0],
    }
    row = conn.execute("SELECT COALESCE(SUM(actual_qty),0),COALESCE(SUM(planned_qty),0) FROM production_logs WHERE log_date=?",(today,)).fetchone()
    stats["today_output"] = row[0]
    stats["today_efficiency_pct"] = round(row[0]/row[1]*100,1) if row[1]>0 else 0
    stats["production_trend"] = rows_to_list(conn.execute("""
        SELECT log_date,SUM(actual_qty) as total FROM production_logs
        WHERE log_date>=date('now','-6 days') GROUP BY log_date ORDER BY log_date
    """).fetchall())
    stats["low_stock_items"] = rows_to_list(conn.execute("""
        SELECT name,type,current_stock,reorder_point,unit FROM materials
        WHERE current_stock<=reorder_point AND reorder_point>0 ORDER BY (current_stock/NULLIF(reorder_point,0)) LIMIT 5
    """).fetchall())
    stats["dept_wip"] = rows_to_list(conn.execute("""
        SELECT current_department,SUM(quantity) as qty,COUNT(*) as batches
        FROM batches WHERE status='active' GROUP BY current_department
    """).fetchall())
    conn.close(); return stats

def get_full_bom_context():
    conn = get_db()
    ctx = {
        "products": rows_to_list(conn.execute("SELECT * FROM products").fetchall()),
        "materials": rows_to_list(conn.execute("SELECT * FROM materials").fetchall()),
        "bom": rows_to_list(conn.execute("""
            SELECT b.*,p.name as product_name,p.sku,m.name as material_name,
                   m.type as material_type,m.unit as material_unit,m.current_stock,m.unit_cost
            FROM bom b JOIN products p ON b.product_id=p.id JOIN materials m ON b.material_id=m.id
        """).fetchall()),
    }
    conn.close(); return ctx

def get_capacity_context():
    conn = get_db()
    ctx = {
        "machines": rows_to_list(conn.execute("SELECT * FROM machines").fetchall()),
        "active_orders": rows_to_list(conn.execute("""
            SELECT o.*,p.name as product_name FROM orders o JOIN products p ON o.product_id=p.id
            WHERE o.status IN ('pending','in_progress') ORDER BY o.priority,o.due_date
        """).fetchall()),
        "recent_logs": rows_to_list(conn.execute("""
            SELECT pl.log_date,pl.shift,p.name as product_name,m.name as machine_name,
                   pl.planned_qty,pl.actual_qty,pl.downtime_minutes
            FROM production_logs pl JOIN products p ON pl.product_id=p.id
            JOIN machines m ON pl.machine_id=m.id WHERE pl.log_date>=date('now','-7 days')
            ORDER BY pl.log_date DESC
        """).fetchall()),
    }
    conn.close(); return ctx


def get_fc_material_requirements(prod_order_id):
    """Return BOM-based material requirements vs current stock for a production order,
    including face/back veneer options and current confirmation status."""
    conn = get_db()
    order = row_to_dict(conn.execute("""
        SELECT po.*,
               p.name as product_name, p.sku as product_sku,
               pur.po_number, pur.customer,
               fv.id as face_veneer_id, fv.name as face_veneer_name, fv.code as face_veneer_code,
               bv.id as back_veneer_id, bv.name as back_veneer_name, bv.code as back_veneer_code,
               COALESCE(sk.pallet_qty, 1) as pallet_qty
        FROM production_orders po
        JOIN products p ON p.id = po.product_id
        LEFT JOIN purchase_orders pur ON pur.id = po.po_id
        LEFT JOIN materials fv ON fv.id = po.confirmed_face_veneer_id
        LEFT JOIN materials bv ON bv.id = po.confirmed_back_veneer_id
        LEFT JOIN skus sk ON sk.code = p.sku
        WHERE po.id = ?
    """, (prod_order_id,)).fetchone())
    if not order:
        conn.close(); return None

    bom_rows = rows_to_list(conn.execute("""
        SELECT b.id, b.quantity_per_unit, b.waste_factor, b.veneer_role, b.notes as bom_notes,
               m.id as material_id, m.code as material_code,
               m.name as material_name, m.type as material_type,
               m.unit, m.current_stock, m.fc_stock, m.reorder_point, m.unit_cost, m.supplier
        FROM bom b
        JOIN materials m ON m.id = b.material_id
        WHERE b.product_id = ?
        ORDER BY b.veneer_role DESC, m.type, m.name
    """, (order['product_id'],)).fetchall())

    FC_STOCK_TYPES = {'veneer_sheet', 'core_board'}
    qty = order.get('quantity', 0)
    requirements = []
    all_ok = True

    # ── If old BOM table has no entries, fall back to new skus+bom_lines system ──
    if not bom_rows:
        product_sku = order.get('product_sku') or ''
        sku_row = row_to_dict(conn.execute(
            "SELECT * FROM skus WHERE code=?", (product_sku,)
        ).fetchone()) if product_sku else None

        if sku_row:
            pallet_qty = float(sku_row.get('pallet_qty') or 1) or 1
            bl_rows = rows_to_list(conn.execute("""
                SELECT bl.seq, bl.qty_override, bl.usage_g_per_face, bl.notes as bom_notes,
                       bl.waste_factor,
                       m.id as material_id, m.code as material_code,
                       m.name as material_name, m.type as material_type,
                       m.unit, m.current_stock, m.fc_stock,
                       m.reorder_point, m.unit_cost, m.supplier
                FROM bom_lines bl
                JOIN materials m ON m.id = bl.material_id
                WHERE bl.sku_id = ?
                ORDER BY bl.seq
            """, (sku_row['id'],)).fetchall())

            # seq→veneer_role mapping: 2=face, 3=back, others=None
            SEQ_ROLE = {2: 'face', 3: 'back'}

            for bl in bl_rows:
                seq = bl.get('seq') or 0
                mat_type = bl.get('material_type') or ''
                qty_override = bl.get('qty_override')
                usage_g = bl.get('usage_g_per_face')

                # Glue formulas are managed by Glue Mix Station — not FC's responsibility
                if mat_type == 'glue_formula':
                    continue

                if qty_override is not None:
                    # Material is sheets/pcs per pallet — default falls back to pallet_qty
                    qty_per_pallet = float(qty_override)
                else:
                    # Default: one sheet/pc per pallet position
                    qty_per_pallet = float(pallet_qty)
                # Per-line waste (boards 0, veneers vary). NULL falls back to 0.
                wf = float(bl.get('waste_factor') or 0)
                # Total required = pallets ordered × pcs per pallet × (1 + waste)
                required = round(qty * qty_per_pallet * (1 + wf), 2)

                veneer_role = SEQ_ROLE.get(seq)
                use_fc = mat_type in FC_STOCK_TYPES
                stock = float(bl.get('fc_stock') or 0) if use_fc else float(bl.get('current_stock') or 0)
                if required == 0:
                    status = 'ok'
                elif stock >= required:
                    status = 'ok'
                elif stock >= required * 0.7:
                    status = 'low'; all_ok = False
                else:
                    status = 'insufficient'; all_ok = False

                requirements.append({
                    **bl,
                    'veneer_role': veneer_role,
                    'quantity_per_unit': round(float(qty_override or 0) / pallet_qty, 4) if qty_override is not None else None,
                    'waste_factor': wf,
                    'required_qty': required,
                    'available_qty': stock,
                    'stock_location': 'fc_station' if use_fc else 'main_warehouse',
                    'shortfall': max(0, round(required - stock, 2)),
                    'status': status,
                })
    else:
        for item in bom_rows:
            # Glue formulas are managed by Glue Mix Station — not FC's responsibility
            if (item.get('material_type') or '') == 'glue_formula':
                continue
            wf = item.get('waste_factor') or 0.05
            required = round(item['quantity_per_unit'] * qty * (1 + wf), 2)
            # Veneers and boards are checked against FC station stock; consumables use WH stock
            use_fc = item.get('material_type') in FC_STOCK_TYPES
            stock = float(item.get('fc_stock') or 0) if use_fc else float(item.get('current_stock') or 0)
            if stock >= required:
                status = 'ok'
            elif stock >= required * 0.7:
                status = 'low'; all_ok = False
            else:
                status = 'insufficient'; all_ok = False
            requirements.append({
                **item,
                'required_qty': required,
                'available_qty': stock,
                'stock_location': 'fc_station' if use_fc else 'main_warehouse',
                'shortfall': max(0, round(required - stock, 2)),
                'status': status,
            })

    # Veneer options for face/back selection: only show those with FC station stock
    # Include species/grade/face_back for grade-mix UI suggestions
    veneer_options = rows_to_list(conn.execute("""
        SELECT id, code, name, fc_stock, current_stock AS wh_stock, unit,
               species, grade, face_back, cut_type, matching
        FROM materials
        WHERE type = 'veneer_sheet' AND fc_stock > 0
        ORDER BY species, grade, name
    """).fetchall())

    # Existing grade-mix allocations if FC already confirmed
    existing_alloc = rows_to_list(conn.execute("""
        SELECT a.side, a.material_id, a.qty_allocated, a.pct_of_total,
               m.name AS material_name, m.code AS material_code,
               m.grade, m.species, m.fc_stock, m.unit
        FROM prod_order_veneer_alloc a
        JOIN materials m ON m.id = a.material_id
        WHERE a.prod_order_id = ?
        ORDER BY a.side, a.qty_allocated DESC
    """, (prod_order_id,)).fetchall())

    conn.close()
    return {
        'order': order,
        'requirements': requirements,
        'all_ok': all_ok,
        'veneer_options': veneer_options,
        'existing_alloc': existing_alloc,
    }


def confirm_veneer_selection(prod_order_id, face_veneer_id, back_veneer_id):
    """FC confirms which veneer goes to face and back for a production order."""
    conn = get_db()
    conn.execute("""
        UPDATE production_orders
        SET confirmed_face_veneer_id=?, confirmed_back_veneer_id=?, fc_confirmed=1
        WHERE id=?
    """, (face_veneer_id or None, back_veneer_id or None, prod_order_id))
    conn.commit()
    order = row_to_dict(conn.execute("""
        SELECT po.*,
               fv.name as face_veneer_name, fv.code as face_veneer_code,
               bv.name as back_veneer_name, bv.code as back_veneer_code
        FROM production_orders po
        LEFT JOIN materials fv ON fv.id = po.confirmed_face_veneer_id
        LEFT JOIN materials bv ON bv.id = po.confirmed_back_veneer_id
        WHERE po.id=?
    """, (prod_order_id,)).fetchone())
    conn.close()
    return order


def get_fg_warehouse_dashboard():
    """
    FG Warehouse dashboard data:
      • Stock per SKU (from batches currently at fg_warehouse dept)
      • Open POs with order vs in-stock fulfillment %
      • Incoming batches still in production (not yet at fg_warehouse)
      • KPI summary
    """
    conn = get_db()

    # 1. Stock by SKU — sum of pcs from batches currently at fg_warehouse
    stock_rows = rows_to_list(conn.execute("""
        SELECT p.sku as sku_code,
               p.name as product_name,
               COALESCE(sk.pallet_qty, 1) as pallet_qty,
               sk.thickness_mm, sk.width_mm, sk.length_mm,
               COUNT(b.id) as batch_count,
               SUM(COALESCE(b.pcs_actual, b.quantity * COALESCE(sk.pallet_qty, 1))) as in_stock_pcs,
               SUM(b.quantity) as in_stock_pallets
        FROM batches b
        JOIN production_orders po ON po.id = b.prod_order_id
        JOIN products p ON p.id = po.product_id
        LEFT JOIN skus sk ON sk.code = p.sku
        WHERE b.current_department = 'fg_warehouse' AND b.status != 'completed'
        GROUP BY p.sku
        ORDER BY in_stock_pcs DESC
    """).fetchall())

    # Build stock-by-sku lookup for PO fulfillment calc
    sku_stock = {r['sku_code']: int(r['in_stock_pcs'] or 0) for r in stock_rows}

    # 2. Open POs (status not closed/cancelled) with line-by-line fulfillment
    open_pos = rows_to_list(conn.execute("""
        SELECT pur.id, pur.po_number, pur.customer, pur.order_date,
               pur.delivery_date, pur.status, pur.notes
        FROM purchase_orders pur
        WHERE pur.status IN ('open', 'in_progress', 'partial', 'released')
           OR pur.status IS NULL
           OR pur.status = ''
        ORDER BY pur.order_date DESC, pur.id DESC
        LIMIT 50
    """).fetchall())

    # For each open PO, compute lines + fulfillment from FG stock
    for po in open_pos:
        lines = rows_to_list(conn.execute("""
            SELECT pol.id, pol.quantity as pallets_ordered, pol.pcs_per_pallet,
                   p.sku, p.name as product_name, pol.production_line
            FROM po_lines pol
            JOIN products p ON p.id = pol.product_id
            WHERE pol.po_id = ?
        """, (po['id'],)).fetchall())
        po_total_ordered = 0
        po_total_in_stock = 0
        for line in lines:
            pcs_per_plt = int(line.get('pcs_per_pallet') or 0)
            if not pcs_per_plt:
                # Fall back to SKU pallet_qty
                sk = conn.execute("SELECT pallet_qty FROM skus WHERE code=?", (line['sku'],)).fetchone()
                pcs_per_plt = int(sk[0]) if sk and sk[0] else 1
            line['pcs_ordered'] = int(line['pallets_ordered'] or 0) * pcs_per_plt
            line['pcs_in_stock'] = int(sku_stock.get(line['sku'], 0))
            line['fulfillment_pct'] = round(min(100, line['pcs_in_stock'] / line['pcs_ordered'] * 100), 1) if line['pcs_ordered'] else 0
            po_total_ordered += line['pcs_ordered']
            po_total_in_stock += min(line['pcs_in_stock'], line['pcs_ordered'])
        po['lines'] = lines
        po['total_pcs_ordered'] = po_total_ordered
        po['total_pcs_in_stock'] = po_total_in_stock
        po['fulfillment_pct'] = round(min(100, po_total_in_stock / po_total_ordered * 100), 1) if po_total_ordered else 0

    # 3. Pending receipt — batches that packing has released to the FG receiving zone
    pending_receipt = rows_to_list(conn.execute("""
        SELECT b.id, b.batch_number, b.quantity, b.pcs_actual, b.current_department, b.created_at,
               COALESCE(b.pcs_actual, b.quantity * COALESCE(sk.pallet_qty, 1)) as total_pcs,
               COALESCE(sk.pallet_qty, 1) as pallet_qty,
               p.sku, p.name as product_name,
               po.prod_order_number, po.production_line, po.priority,
               pur.po_number, pur.customer,
               (SELECT MAX(moved_at) FROM batch_movements
                WHERE batch_id=b.id AND to_department='fg_receiving') as released_at
        FROM batches b
        JOIN production_orders po ON po.id = b.prod_order_id
        JOIN products p ON p.id = po.product_id
        LEFT JOIN purchase_orders pur ON pur.id = po.po_id
        LEFT JOIN skus sk ON sk.code = p.sku
        WHERE b.current_department = 'fg_receiving'
          AND b.status = 'active'
        ORDER BY po.priority, b.created_at
    """).fetchall())

    # 4. In production — batches still being made (NOT yet at fg_receiving or fg_warehouse)
    in_production = rows_to_list(conn.execute("""
        SELECT b.id, b.batch_number, b.quantity, b.pcs_actual, b.current_department, b.created_at,
               COALESCE(b.pcs_actual, b.quantity * COALESCE(sk.pallet_qty, 1)) as total_pcs,
               COALESCE(sk.pallet_qty, 1) as pallet_qty,
               p.sku, p.name as product_name,
               po.prod_order_number, po.production_line, po.priority,
               pur.po_number, pur.customer
        FROM batches b
        JOIN production_orders po ON po.id = b.prod_order_id
        JOIN products p ON p.id = po.product_id
        LEFT JOIN purchase_orders pur ON pur.id = po.po_id
        LEFT JOIN skus sk ON sk.code = p.sku
        WHERE b.current_department NOT IN ('fg_receiving', 'fg_warehouse')
          AND b.status = 'active'
        ORDER BY po.priority, b.created_at
    """).fetchall())

    # KPI summary
    kpis = {
        'skus_in_stock': len(stock_rows),
        'total_pcs_in_stock': sum(int(r['in_stock_pcs'] or 0) for r in stock_rows),
        'total_pallets_in_stock': sum(int(r['in_stock_pallets'] or 0) for r in stock_rows),
        'open_pos': len(open_pos),
        'pending_receipt_batches': len(pending_receipt),
        'pending_receipt_pcs': sum(int(r['total_pcs'] or 0) for r in pending_receipt),
        'in_production_batches': len(in_production),
        'in_production_pcs': sum(int(r['total_pcs'] or 0) for r in in_production),
    }

    conn.close()
    return {
        'kpis': kpis,
        'stock_by_sku': stock_rows,
        'open_pos': open_pos,
        'pending_receipt': pending_receipt,
        'in_production': in_production,
    }


def receive_batch_to_warehouse(batch_id, received_by=''):
    """Mark a batch as received at FG warehouse — moves it to fg_warehouse department."""
    return move_batch(batch_id, 'fg_warehouse', None, 0,
                      f'Received into FG warehouse', received_by)


def get_fc_movements(limit=50, mat_type=None):
    """
    Unified FC stock movement log — covers both veneers AND boards.
    Returns inbound transfers (WH→FC), outbound returns (FC→WH),
    veneer regrades (within FC), and batch releases (FC→laminating).
    """
    conn = get_db()
    rows = []
    type_filter = ""
    type_params = ()
    if mat_type:
        type_filter = " AND m.type = ?"
        type_params = (mat_type,)

    # 1. Inbound transfer fulfillments (WH → FC)
    inbound = conn.execute(f"""
        SELECT 'TRANSFER_IN' as kind, t.request_id as ref,
               t.fulfilled_at as ts, t.qty_fulfilled as qty,
               m.id as material_id, m.code as material_code, m.name as material_name,
               m.type as material_type, m.unit,
               t.requested_by as requested_by, t.fulfilled_by as actor,
               t.notes as notes,
               'WH' as from_loc, 'FC' as to_loc
        FROM fc_transfer_requests t
        JOIN materials m ON m.id = t.material_id
        WHERE t.status IN ('FULFILLED','PARTIAL')
          AND COALESCE(t.direction,'inbound') = 'inbound'
          AND t.qty_fulfilled > 0
          AND t.fulfilled_at IS NOT NULL
          {type_filter}
        ORDER BY t.fulfilled_at DESC
        LIMIT ?
    """, (*type_params, limit)).fetchall()
    rows.extend([dict(r) for r in inbound])

    # 2. Outbound returns (FC → WH)
    outbound = conn.execute(f"""
        SELECT 'RETURN_TO_WH' as kind, t.request_id as ref,
               t.fulfilled_at as ts, t.qty_fulfilled as qty,
               m.id as material_id, m.code as material_code, m.name as material_name,
               m.type as material_type, m.unit,
               t.requested_by as requested_by, t.fulfilled_by as actor,
               t.notes as notes,
               'FC' as from_loc, 'WH' as to_loc
        FROM fc_transfer_requests t
        JOIN materials m ON m.id = t.material_id
        WHERE t.status IN ('FULFILLED','PARTIAL')
          AND t.direction = 'outbound'
          AND t.qty_fulfilled > 0
          AND t.fulfilled_at IS NOT NULL
          {type_filter}
        ORDER BY t.fulfilled_at DESC
        LIMIT ?
    """, (*type_params, limit)).fetchall()
    rows.extend([dict(r) for r in outbound])

    # 3. Veneer regrades within FC (veneers only, but include for completeness)
    if not mat_type or mat_type == 'veneer_sheet':
        regrade = conn.execute("""
            SELECT 'REGRADE' as kind, rl.record_id as ref,
                   rl.created_at as ts, rl.qty,
                   tm.id as material_id, tm.code as material_code, tm.name as material_name,
                   tm.type as material_type, tm.unit,
                   '' as requested_by, rl.graded_by as actor,
                   rl.notes,
                   'FC ' || COALESCE(fm.species,'') || ' ' || COALESCE(fm.grade,'') as from_loc,
                   'FC ' || COALESCE(tm.species,'') || ' ' || COALESCE(tm.grade,'') as to_loc
            FROM veneer_regrade_log rl
            JOIN materials fm ON fm.id = rl.from_material_id
            JOIN materials tm ON tm.id = rl.to_material_id
            ORDER BY rl.created_at DESC
            LIMIT ?
        """, (limit,)).fetchall()
        rows.extend([dict(r) for r in regrade])

    # 4. Batch releases (FC → laminating) — shows what batches left FC for production
    releases = conn.execute("""
        SELECT 'RELEASE_TO_LAM' as kind, b.batch_number as ref,
               bm.moved_at as ts, bm.quantity as qty,
               NULL as material_id, '' as material_code,
               'Batch ' || b.batch_number || ' — ' || COALESCE(p.name,'') as material_name,
               'batch' as material_type, 'pallet' as unit,
               '' as requested_by, COALESCE(bm.moved_by,'') as actor,
               COALESCE(bm.notes,'') as notes,
               'FC' as from_loc, 'Laminating' as to_loc
        FROM batch_movements bm
        JOIN batches b ON b.id = bm.batch_id
        JOIN production_orders po ON po.id = b.prod_order_id
        JOIN products p ON p.id = po.product_id
        WHERE bm.from_department = 'fc' AND bm.to_department = 'laminating'
        ORDER BY bm.moved_at DESC
        LIMIT ?
    """, (limit,)).fetchall()
    if not mat_type:
        rows.extend([dict(r) for r in releases])

    # Sort by timestamp desc, return top N
    rows.sort(key=lambda r: (r.get('ts') or ''), reverse=True)
    conn.close()
    return rows[:limit]


def get_all_fc_batches():
    """Return all active batches at FC with their production order + stock context."""
    conn = get_db()
    rows = rows_to_list(conn.execute("""
        SELECT b.*, po.prod_order_number, po.production_line, po.quantity as order_qty,
               p.name as product_name, p.sku as product_sku,
               pur.po_number, pur.customer,
               po.id as prod_order_id,
               COALESCE(sk.pallet_qty, 1) as pallet_qty
        FROM batches b
        JOIN production_orders po ON po.id = b.prod_order_id
        JOIN products p ON p.id = po.product_id
        LEFT JOIN purchase_orders pur ON pur.id = po.po_id
        LEFT JOIN skus sk ON sk.code = p.sku
        WHERE b.current_department = 'fc' AND b.status = 'active'
        ORDER BY b.created_at DESC
    """).fetchall())
    conn.close(); return rows


def get_line_board(production_line=None):
    """Return batches grouped by department, filtered by production line."""
    conn = get_db()
    query = """
        SELECT b.*, po.prod_order_number, po.production_line, po.priority,
               p.name as product_name, p.sku as product_sku,
               pur.po_number, pur.customer,
               po.id as prod_order_id
        FROM batches b
        JOIN production_orders po ON po.id = b.prod_order_id
        JOIN products p ON p.id = po.product_id
        LEFT JOIN purchase_orders pur ON pur.id = po.po_id
        WHERE b.status = 'active'
    """
    params = []
    if production_line and production_line != 'all':
        query += " AND po.production_line = ?"
        params.append(production_line)
    query += " ORDER BY po.priority, b.created_at"
    rows = rows_to_list(conn.execute(query, params).fetchall())
    conn.close()
    # Group by department
    board = {}
    for r in rows:
        dept = r['current_department']
        board.setdefault(dept, []).append(r)
    return board


# ═══════════════════════════════════════════════════════════════
# PROPER BOM MODULE — skus / bom_lines / compound / packing
# ═══════════════════════════════════════════════════════════════

def get_all_skus(search=None):
    conn = get_db()
    q = "SELECT s.*, ps.code as packing_sku_code, ps.customer FROM skus s LEFT JOIN packing_skus ps ON ps.id=s.packing_sku_id"
    params = []
    if search:
        q += " WHERE s.code LIKE ? OR s.name LIKE ?"
        params = [f"%{search}%", f"%{search}%"]
    q += " ORDER BY s.code"
    rows = rows_to_list(conn.execute(q, params).fetchall())
    conn.close(); return rows

def get_sku(code):
    conn = get_db()
    row = conn.execute(
        "SELECT s.*, ps.code as packing_sku_code, ps.customer FROM skus s LEFT JOIN packing_skus ps ON ps.id=s.packing_sku_id WHERE s.code=?",
        (code,)).fetchone()
    conn.close(); return row_to_dict(row)

def get_sku_bom(sku_code):
    conn = get_db()
    rows = rows_to_list(conn.execute("SELECT * FROM bom_full WHERE sku_code=?", (sku_code,)).fetchall())
    conn.close(); return rows

def get_sku_cost(sku_code):
    conn = get_db()
    rows = rows_to_list(conn.execute("SELECT * FROM bom_cost_summary WHERE sku_code=?", (sku_code,)).fetchall())
    conn.close(); return rows

def _recipe_to_summary(conn, recipe_row, with_ingredients: bool = False):
    """Convert a glue_recipes row into the same shape compound_cost used to
    return (so existing API consumers keep working)."""
    import json as _json
    r = dict(recipe_row)
    INGREDIENT_KG_COL = [
        ('e0_glue','e0_glue_kg','UREA-RESIN'),
        ('latex_g312','latex_g312_kg','LATEX-G312'),
        ('flour','flour_kg','WHEAT-FLOUR'),
        ('yellow_pigment','yellow_pigment_kg','OXIDE-YELLOW'),
        ('hardener','hardener_kg',None),
        ('red_pigment','red_pigment_kg','OXIDE-RED'),
        ('black_pigment','black_pigment_kg','FLUORESCENT'),
        ('titanium','titanium_kg','TITANIUM-PWD'),
    ]
    try:
        links = _json.loads(r.get('material_links') or '{}')
    except Exception:
        links = {}
    total_kg = float(r.get('total_kg') or 0)
    total_cost = 0.0
    sum_kg_with_price = 0.0
    ingredients = []
    for ing_key, kg_col, fallback_code in INGREDIENT_KG_COL:
        kg = float(r.get(kg_col) or 0)
        if kg <= 0: continue
        mat_id = links.get(ing_key)
        mat = None
        if mat_id:
            mat = conn.execute("SELECT id, code, name, unit, price FROM materials WHERE id=?",
                               (mat_id,)).fetchone()
        if not mat and fallback_code:
            mat = conn.execute("SELECT id, code, name, unit, price FROM materials WHERE code=?",
                               (fallback_code,)).fetchone()
        ratio = (kg / total_kg) if total_kg > 0 else 0
        if mat:
            price = float(mat['price'] or 0)
            total_cost += kg * price
            sum_kg_with_price += kg
            if with_ingredients:
                ingredients.append({
                    'material_id':   mat['id'],
                    'ingredient_key':ing_key,
                    'material_code': mat['code'],
                    'ingredient_name': mat['name'],
                    'unit':          mat['unit'] or 'kg',
                    'price':         price,
                    'ratio':         ratio,
                    'kg':            kg,
                })
        elif with_ingredients:
            ingredients.append({
                'material_id': None,
                'ingredient_key': ing_key,
                'material_code': fallback_code or ing_key,
                'ingredient_name': ing_key,
                'unit': 'kg', 'price': 0, 'ratio': ratio, 'kg': kg,
            })
    cost_per_kg = (total_cost / sum_kg_with_price) if sum_kg_with_price > 0 else 0
    out = {
        'id':            r['id'],
        'code':          r['recipe_code'],
        'name':          r.get('name') or r['recipe_code'],
        'batch_kg':      total_kg,
        'cost_per_kg_mixed': round(cost_per_kg, 6),
        'typical_batch_cost': round(cost_per_kg * total_kg, 2),
        'is_active':     r.get('is_active', 1),
    }
    if with_ingredients:
        out['ingredients'] = ingredients
        out['lines']       = ingredients
    return out


def get_glue_recipes_summary():
    """Return all active glue recipes as cost summaries (no ingredient
    breakdown). Backed by `glue_recipes` since Phase B."""
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT * FROM glue_recipes WHERE COALESCE(is_active,1)=1 ORDER BY recipe_code"
        ).fetchall()
        return [_recipe_to_summary(conn, r) for r in rows]
    finally:
        conn.close()


def get_glue_recipe_detail(code):
    """Return one glue recipe with ingredient breakdown, by recipe_code."""
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT * FROM glue_recipes WHERE recipe_code=? AND COALESCE(is_active,1)=1",
            (code,)).fetchone()
        if not row: return None
        return _recipe_to_summary(conn, row, with_ingredients=True)
    finally:
        conn.close()

def get_all_packing_skus():
    conn = get_db()
    rows = rows_to_list(conn.execute("SELECT * FROM packing_skus ORDER BY code").fetchall())
    conn.close(); return rows

def get_packing_sku(code):
    conn = get_db()
    ps = row_to_dict(conn.execute("SELECT * FROM packing_skus WHERE code=?", (code,)).fetchone())
    lines = rows_to_list(conn.execute("SELECT * FROM packing_bom WHERE packing_sku_code=? ORDER BY seq", (code,)).fetchall())
    conn.close()
    if not ps: return None
    ps['lines'] = lines
    return ps

# ── Compound SKU CRUD ────────────────────────────────────────────────────────

def get_glue_recipes_with_ingredients():
    """Recipe list with ingredient breakdown, backed by glue_recipes."""
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT * FROM glue_recipes WHERE COALESCE(is_active,1)=1 ORDER BY recipe_code"
        ).fetchall()
        return [_recipe_to_summary(conn, r, with_ingredients=True) for r in rows]
    finally:
        conn.close()


# ── Packing SKU CRUD ─────────────────────────────────────────────────────────

def get_packing_skus_with_lines():
    conn = get_db()
    rows = rows_to_list(conn.execute(
        "SELECT * FROM packing_skus WHERE is_active=1 ORDER BY code").fetchall())
    for ps in rows:
        lines = rows_to_list(conn.execute("""
            SELECT pl.id, pl.seq, pl.qty, pl.qty_unit, pl.notes,
                   m.code as material_code, m.name as material_name, m.price
            FROM packing_lines pl
            JOIN materials m ON m.id=pl.material_id
            WHERE pl.packing_sku_id=? ORDER BY pl.seq
        """, (ps['id'],)).fetchall())
        ps['lines'] = lines
    conn.close()
    return rows

def save_packing_sku(data):
    conn = get_db()
    code = data['code'].strip()
    existing = conn.execute("SELECT id FROM packing_skus WHERE code=?", (code,)).fetchone()
    if existing:
        conn.execute("""UPDATE packing_skus SET name=?, customer=?, notes=?, updated_at=CURRENT_TIMESTAMP
                        WHERE code=?""",
                     (data.get('name',''), data.get('customer',''), data.get('notes',''), code))
        pid = existing['id']
    else:
        conn.execute("""INSERT INTO packing_skus (code, name, customer, notes, is_active)
                        VALUES (?,?,?,?,1)""",
                     (code, data.get('name',''), data.get('customer',''), data.get('notes','')))
        pid = conn.execute("SELECT id FROM packing_skus WHERE code=?", (code,)).fetchone()['id']
    conn.commit(); conn.close()
    return {'id': pid, 'code': code}

def delete_packing_sku(pid):
    conn = get_db()
    conn.execute("DELETE FROM packing_lines WHERE packing_sku_id=?", (pid,))
    conn.execute("DELETE FROM packing_skus WHERE id=?", (pid,))
    conn.commit(); conn.close()

def add_packing_line(packing_id, mat_code, qty, qty_unit='pallet', seq=0, notes=''):
    conn = get_db()
    mat = conn.execute("SELECT id FROM materials WHERE code=?", (mat_code,)).fetchone()
    if not mat:
        conn.close()
        raise ValueError(f"Material '{mat_code}' not found")
    if not seq:
        row = conn.execute("SELECT COALESCE(MAX(seq),0)+1 FROM packing_lines WHERE packing_sku_id=?",
                           (packing_id,)).fetchone()
        seq = row[0]
    conn.execute("""INSERT INTO packing_lines (packing_sku_id, material_id, seq, qty, qty_unit, notes)
                    VALUES (?,?,?,?,?,?)""", (packing_id, mat['id'], seq, qty, qty_unit, notes))
    conn.commit(); conn.close()

def delete_packing_line(lid):
    conn = get_db()
    conn.execute("DELETE FROM packing_lines WHERE id=?", (lid,))
    conn.commit(); conn.close()

# ─────────────────────────────────────────────────────────────────────────────

def _glue_recipe_cost_per_kg(conn, recipe_id: int) -> float | None:
    """Compute a glue recipe's cost-per-kg of mixed product from its
    `material_links` map and the linked ingredients' live prices.
    Returns None if the recipe has no usable kg amounts or links."""
    r = conn.execute("SELECT * FROM glue_recipes WHERE id=?", (recipe_id,)).fetchone()
    if not r: return None
    r = dict(r)
    import json as _json
    try:
        links = _json.loads(r.get('material_links') or '{}')
    except Exception:
        links = {}
    if not links: return None
    INGREDIENT_KG_COL = {
        'e0_glue':'e0_glue_kg', 'latex_g312':'latex_g312_kg', 'flour':'flour_kg',
        'yellow_pigment':'yellow_pigment_kg', 'hardener':'hardener_kg',
        'red_pigment':'red_pigment_kg', 'black_pigment':'black_pigment_kg',
        'titanium':'titanium_kg',
    }
    total_kg = 0.0; total_cost = 0.0
    for ing_key, mat_id in links.items():
        col = INGREDIENT_KG_COL.get(ing_key)
        if not col: continue
        kg = float(r.get(col) or 0)
        if kg <= 0: continue
        m = conn.execute("SELECT price FROM materials WHERE id=?", (mat_id,)).fetchone()
        if not m: continue
        total_cost += kg * float(m[0] or 0)
        total_kg   += kg
    return (total_cost / total_kg) if total_kg > 0 else None


def update_material_price(mat_code, price):
    """Update a material's catalog price. Glue recipes that reference this
    material as an ingredient will pick up the new price on the next read
    (cost is computed live from glue_recipes.material_links)."""
    conn = get_db()
    try:
        conn.execute(
            "UPDATE materials SET price=?, unit_cost=? WHERE code=?",
            (price, price, mat_code))
        conn.commit()
        row = conn.execute("SELECT * FROM materials WHERE code=?", (mat_code,)).fetchone()
        return row_to_dict(row)
    finally:
        conn.close()

def get_material_usage(mat_code):
    """List every place this material is referenced — FG BOM lines, packing
    BOMs, and glue recipes (via material_links). After Phase B the legacy
    compound_lines table no longer exists."""
    conn = get_db()
    try:
        core = rows_to_list(conn.execute("""
            SELECT s.code AS sku_code, s.name AS sku_name, bl.seq,
                   bl.qty_override, bl.usage_g_per_face
            FROM bom_lines bl
            JOIN skus s      ON s.id=bl.sku_id
            JOIN materials m ON m.id=bl.material_id
            WHERE m.code=? ORDER BY s.code""", (mat_code,)).fetchall())
        packing = rows_to_list(conn.execute("""
            SELECT ps.code AS packing_sku_code, ps.name AS packing_sku_name, pl.qty
            FROM packing_lines pl
            JOIN packing_skus ps ON ps.id=pl.packing_sku_id
            JOIN materials m     ON m.id=pl.material_id
            WHERE m.code=? ORDER BY ps.code""", (mat_code,)).fetchall())
        # Glue recipes that reference this material via material_links JSON.
        # SQLite has no JSON path search by value, so we scan + parse.
        mat_id_row = conn.execute("SELECT id FROM materials WHERE code=?",
                                  (mat_code,)).fetchone()
        compounds = []
        if mat_id_row:
            target_id = mat_id_row[0]
            import json as _json
            for r in conn.execute(
                "SELECT id, recipe_code, name, material_links FROM glue_recipes "
                "WHERE COALESCE(is_active,1)=1").fetchall():
                try:
                    links = _json.loads(r[3] or '{}')
                except Exception:
                    continue
                for ing_key, mid in links.items():
                    if int(mid or 0) == target_id:
                        compounds.append({
                            'recipe_id':   r[0],
                            'recipe_code': r[1],
                            'recipe_name': r[2],
                            'ingredient_key': ing_key,
                        })
                        break
        return {'core_bom': core, 'packing': packing,
                'glue_recipe_ingredient': compounds,
                # Legacy key retained for any FE consumer
                'compound_ingredient':    compounds}
    finally:
        conn.close()


def get_structured_bom(sku_code=None):
    """Return BOM as structured dict per FG SKU: base board, face/back veneer,
    face/back glue formula, packing spec, cost per pallet and per sheet."""
    conn = get_db()
    if sku_code:
        skus = conn.execute("SELECT * FROM skus WHERE code=? AND is_active=1", (sku_code,)).fetchall()
    else:
        skus = conn.execute("SELECT * FROM skus WHERE is_active=1 ORDER BY code").fetchall()

    result = []
    for s in skus:
        sid = s['id']
        code = s['code']
        pallet_qty = s['pallet_qty'] or 1

        # Core BOM lines for this SKU. Glue lines store glue_recipe_id (FK into
        # glue_recipes) with material_id=NULL since Phase B, so we LEFT JOIN both
        # tables and pick whichever resolves. An inner JOIN on materials would
        # silently drop every glue row.
        lines = conn.execute("""
            SELECT bl.seq, bl.qty_override, bl.usage_g_per_face, bl.qty_unit,
                   bl.glue_recipe_id, bl.waste_factor,
                   m.code as mat_code, m.name as mat_name, m.name_th,
                   m.type as mat_type, m.unit, m.price,
                   gr.recipe_code as glue_code, gr.name as glue_name
            FROM bom_lines bl
            LEFT JOIN materials    m  ON m.id  = bl.material_id
            LEFT JOIN glue_recipes gr ON gr.id = bl.glue_recipe_id
            WHERE bl.sku_id = ?
            ORDER BY bl.seq
        """, (sid,)).fetchall()

        entry = {
            'sku_code':    code,
            'sku_name':    s['name'],
            'thickness_mm': s['thickness_mm'],
            'width_mm':    s['width_mm'],
            'length_mm':   s['length_mm'],
            'pallet_qty':  pallet_qty,
            'base_board':  None,
            'face_veneer': None,
            'back_veneer': None,
            'face_glue':   None,
            'back_glue':   None,
            'packing':     None,
            'core_cost':   0,
            'packing_cost':0,
            'total_cost':  0,
            'cost_per_sheet': 0,
        }

        for l in lines:
            is_glue_row = l['glue_recipe_id'] is not None
            qty = l['qty_override'] if l['qty_override'] else pallet_qty

            if is_glue_row:
                # Resolve glue cost live from glue_recipes.material_links via
                # _recipe_to_summary so price changes on ingredient materials
                # propagate to the FG cost without a separate sync step.
                recipe_row = conn.execute(
                    "SELECT * FROM glue_recipes WHERE id=?", (l['glue_recipe_id'],)
                ).fetchone()
                if recipe_row:
                    summary = _recipe_to_summary(conn, recipe_row)
                    price_per_kg = summary.get('cost_per_kg_mixed') or 0
                else:
                    price_per_kg = 0
                if l['usage_g_per_face'] is not None:
                    line_cost = round(price_per_kg * (l['usage_g_per_face'] / 1000.0) * pallet_qty, 4)
                else:
                    line_cost = 0
                item = {
                    'code':   l['glue_code'] or '',
                    'name':   l['glue_name'] or '',
                    'name_th': None,
                    'qty':    qty,
                    'unit':   'kg',
                    'price':  price_per_kg,
                    'usage_g_per_face': l['usage_g_per_face'],
                    'cost':   line_cost,
                    'glue_recipe_id': l['glue_recipe_id'],
                }
                if l['seq'] == 4:
                    entry['face_glue'] = item
                elif l['seq'] == 5:
                    entry['back_glue'] = item
                entry['core_cost'] = round(entry['core_cost'] + line_cost, 4)
                continue

            # Non-glue row — backed by materials
            if l['usage_g_per_face'] is not None:
                line_cost = round((l['price'] or 0) * (l['usage_g_per_face'] / 1000.0) * pallet_qty, 4)
            else:
                line_cost = round((l['price'] or 0) * qty, 4)

            item = {
                'code':   l['mat_code'],
                'name':   l['mat_name'],
                'name_th': l['name_th'],
                'qty':    qty,
                'unit':   l['unit'],
                'price':  l['price'],
                'usage_g_per_face': l['usage_g_per_face'],
                'waste_factor': float(l['waste_factor']) if l['waste_factor'] is not None else 0,
                'cost':   line_cost,
            }

            mt = l['mat_type']
            seq = l['seq']
            if mt == 'core_board':
                entry['base_board'] = item
            elif mt == 'veneer_sheet' and seq == 2:
                entry['face_veneer'] = item
            elif mt == 'veneer_sheet' and seq == 3:
                entry['back_veneer'] = item
            # Legacy: glue used to be stored as a materials row (type=glue_formula).
            # Keep this branch so any pre-Phase-B rows still display.
            elif mt == 'glue_formula' and seq == 4:
                entry['face_glue'] = item
            elif mt == 'glue_formula' and seq == 5:
                entry['back_glue'] = item

            entry['core_cost'] = round(entry['core_cost'] + line_cost, 4)

        # Packing
        if s['packing_sku_id']:
            ps = conn.execute("SELECT * FROM packing_skus WHERE id=?", (s['packing_sku_id'],)).fetchone()
            if ps:
                pack_lines = conn.execute("""
                    SELECT pl.qty, m.price, m.code as mat_code
                    FROM packing_lines pl JOIN materials m ON m.id=pl.material_id
                    WHERE pl.packing_sku_id=?
                """, (ps['id'],)).fetchall()
                packing_cost = round(sum((pl['price'] or 0) * pl['qty'] for pl in pack_lines), 4)
                entry['packing'] = {
                    'code': ps['code'],
                    'name': ps['name'],
                    'customer': ps['customer'],
                    'cost': packing_cost,
                }
                entry['packing_cost'] = packing_cost

        entry['total_cost'] = round(entry['core_cost'] + entry['packing_cost'], 4)
        entry['cost_per_sheet'] = round(entry['total_cost'] / pallet_qty, 4) if pallet_qty else 0
        result.append(entry)

    conn.close()
    return result[0] if (sku_code and result) else result


def save_bom_for_sku(data):
    """Create or update a complete BOM for one FG SKU via the BOM Builder.
    Upserts skus, replaces bom_lines (seq 1-5), and syncs to legacy products table.
    data keys: sku_code, sku_name, thickness_mm, width_mm, length_mm, pallet_qty,
               base_board_code, base_board_qty,
               face_veneer_code, face_veneer_qty,
               back_veneer_code, back_veneer_qty,
               face_glue_code, face_glue_usage_g,
               back_glue_code, back_glue_usage_g,
               packing_sku_code
    """
    conn = get_db()
    code = data['sku_code'].strip().upper()

    # Group id for Core Materials
    grp = conn.execute("SELECT id FROM bom_groups WHERE name='Core Materials'").fetchone()
    grp_id = grp[0] if grp else 1

    # Resolve packing_sku_id
    packing_id = None
    if data.get('packing_sku_code'):
        row = conn.execute("SELECT id FROM packing_skus WHERE code=?",
                           (data['packing_sku_code'],)).fetchone()
        if row:
            packing_id = row[0]

    pallet_qty = int(data.get('pallet_qty') or 1) or 1

    # Upsert skus
    existing = conn.execute("SELECT id FROM skus WHERE code=?", (code,)).fetchone()
    if existing:
        sku_id = existing[0]
        conn.execute("""
            UPDATE skus SET name=?, thickness_mm=?, width_mm=?, length_mm=?,
            pallet_qty=?, packing_sku_id=?, is_active=1,
            updated_at=datetime('now') WHERE id=?
        """, (data.get('sku_name',''), data.get('thickness_mm'), data.get('width_mm'),
              data.get('length_mm'), pallet_qty, packing_id, sku_id))
    else:
        cur = conn.execute("""
            INSERT INTO skus (code, name, thickness_mm, width_mm, length_mm,
                              pallet_qty, packing_sku_id, is_active)
            VALUES (?,?,?,?,?,?,?,1)
        """, (code, data.get('sku_name',''), data.get('thickness_mm'), data.get('width_mm'),
              data.get('length_mm'), pallet_qty, packing_id))
        sku_id = cur.lastrowid

    # Replace bom_lines
    conn.execute("DELETE FROM bom_lines WHERE sku_id=?", (sku_id,))

    def mat_id(mat_code):
        if not mat_code: return None
        row = conn.execute("SELECT id FROM materials WHERE code=?", (mat_code,)).fetchone()
        return row[0] if row else None

    def glue_recipe_id(recipe_code):
        if not recipe_code: return None
        row = conn.execute(
            "SELECT id FROM glue_recipes WHERE recipe_code=?", (recipe_code,)).fetchone()
        return row[0] if row else None

    # Non-glue lines (seq 1-3) — resolve against materials.code. Each carries
    # a per-line waste factor (boards default 0, veneers default 0.05). The
    # FC requirement calc multiplies required qty by (1 + waste_factor).
    def _waste(key, default):
        v = data.get(key)
        if v is None or v == '':
            return default
        try:
            return max(0.0, float(v))
        except (TypeError, ValueError):
            return default

    for seq, code_key, qty_key, waste_key, waste_default in [
        (1, 'base_board_code',  'base_board_qty',  'base_board_waste',  0.0),
        (2, 'face_veneer_code', 'face_veneer_qty', 'face_veneer_waste', 0.05),
        (3, 'back_veneer_code', 'back_veneer_qty', 'back_veneer_waste', 0.05),
    ]:
        mat_code = data.get(code_key)
        if not mat_code: continue
        mid = mat_id(mat_code)
        if not mid: continue
        qty = float(data.get(qty_key) or pallet_qty)
        wf = _waste(waste_key, waste_default)
        conn.execute(
            "INSERT INTO bom_lines (sku_id,material_id,group_id,seq,qty_override,waste_factor) VALUES (?,?,?,?,?,?)",
            (sku_id, mid, grp_id, seq, qty, wf))

    # Glue lines (seq 4-5) — resolve against glue_recipes.recipe_code first,
    # fall back to materials.code only if the user picked a legacy glue_formula
    # placeholder material. After Phase B the front-end picker uses recipes.
    for seq, code_key, usage_key in [
        (4, 'face_glue_code', 'face_glue_usage_g'),
        (5, 'back_glue_code', 'back_glue_usage_g'),
    ]:
        picked = data.get(code_key)
        if not picked: continue
        usage_g = float(data.get(usage_key) or 45)
        rid = glue_recipe_id(picked)
        if rid:
            conn.execute(
                "INSERT INTO bom_lines (sku_id,glue_recipe_id,group_id,seq,usage_g_per_face) VALUES (?,?,?,?,?)",
                (sku_id, rid, grp_id, seq, usage_g))
            continue
        # legacy fallback: glue stored as a materials row
        mid = mat_id(picked)
        if mid:
            conn.execute(
                "INSERT INTO bom_lines (sku_id,material_id,group_id,seq,usage_g_per_face) VALUES (?,?,?,?,?)",
                (sku_id, mid, grp_id, seq, usage_g))

    conn.commit()

    # Sync to legacy products table so order intake can find this FG
    prod = conn.execute("SELECT id FROM products WHERE sku=?", (code,)).fetchone()
    if prod:
        conn.execute("UPDATE products SET name=? WHERE sku=?",
                     (data.get('sku_name',''), code))
    else:
        conn.execute("INSERT INTO products (name, sku, description) VALUES (?,?,'fg')",
                     (data.get('sku_name',''), code))
    conn.commit()
    conn.close()

    return get_structured_bom(code)


# ═══════════════════════════════════════════════════════════════
# PRODUCTION MODULE — Employees
# ═══════════════════════════════════════════════════════════════
def get_employees(dept=None, line_id=None, active_only=True):
    conn = get_db(); params = []
    q = "SELECT * FROM employee WHERE 1=1"
    if active_only: q += " AND active=1"
    if dept: q += " AND department=?"; params.append(dept)
    if line_id: q += " AND line_id=?"; params.append(line_id)
    rows = conn.execute(q + " ORDER BY emp_name", params).fetchall()
    conn.close(); return rows_to_list(rows)

def save_employee(data, emp_id=None):
    conn = get_db()
    final_id = emp_id
    if emp_id:
        conn.execute(
            "UPDATE employee SET emp_name=?,department=?,role=?,line_id=?,active=? WHERE emp_id=?",
            (data['emp_name'],data['department'],data.get('role',''),
             data.get('line_id'),data.get('active',1),emp_id))
    else:
        final_id = data.get('emp_id') or f"EMP-{uuid.uuid4().hex[:6].upper()}"
        conn.execute(
            "INSERT INTO employee (emp_id,emp_name,department,role,line_id) VALUES (?,?,?,?,?)",
            (final_id,data['emp_name'],data['department'],data.get('role',''),data.get('line_id')))
    conn.commit()
    row = conn.execute("SELECT * FROM employee WHERE emp_id=?",
                       (final_id,)).fetchone()
    conn.close(); return row_to_dict(row)

def delete_employee(emp_id):
    conn = get_db()
    conn.execute("UPDATE employee SET active=0 WHERE emp_id=?", (emp_id,))
    conn.commit(); conn.close()

def get_manufacturing_lines(active_only=True, line_type=None):
    """Return all production lines, ordered by sort_order then code.
    line_type can be 'main' or 'aux' to filter; None returns both."""
    conn = get_db()
    q = """SELECT line_id AS code, line_name AS label,
                  COALESCE(line_type,'main') AS line_type,
                  COALESCE(sort_order,0)     AS sort_order,
                  active                     AS is_active
             FROM manufacturing_line WHERE 1=1"""
    params = []
    if active_only:    q += " AND active = 1"
    if line_type:      q += " AND COALESCE(line_type,'main') = ?"; params.append(line_type)
    q += " ORDER BY sort_order ASC, line_id ASC"
    rows = conn.execute(q, params).fetchall()
    conn.close(); return rows_to_list(rows)

def get_prod_machines(machine_type=None):
    conn = get_db(); params = []
    q = "SELECT * FROM prod_machine WHERE active=1"
    if machine_type: q += " AND machine_type=?"; params.append(machine_type)
    rows = conn.execute(q + " ORDER BY machine_id", params).fetchall()
    conn.close(); return rows_to_list(rows)

def get_departments(active_only=True):
    """Return all departments, ordered by sort_order."""
    conn = get_db()
    q = "SELECT * FROM departments"
    if active_only: q += " WHERE is_active = 1"
    q += " ORDER BY sort_order ASC, code ASC"
    rows = conn.execute(q).fetchall()
    conn.close(); return rows_to_list(rows)

def get_line_flow(line_code):
    """Return the ordered department sequence for one line.
    Aux lines (PUV/PVS/PSP) return [] — they're request-only hubs."""
    conn = get_db()
    rows = conn.execute("""
        SELECT lf.seq, lf.department_code AS code,
               d.label, d.icon, d.is_centralised
          FROM line_flow lf
          LEFT JOIN departments d ON d.code = lf.department_code
         WHERE lf.line_code = ?
         ORDER BY lf.seq ASC
    """, (line_code,)).fetchall()
    conn.close(); return rows_to_list(rows)

def get_all_line_flows():
    """Return all line flows as { line_code: [dept_code, ...] }. Used by the
    frontend to populate LINE_FLOW in one fetch instead of N+1."""
    conn = get_db()
    rows = conn.execute("""
        SELECT line_code, seq, department_code
          FROM line_flow ORDER BY line_code, seq
    """).fetchall()
    conn.close()
    flow = {}
    for r in rows:
        flow.setdefault(r['line_code'], []).append(r['department_code'])
    return flow

def get_stations(line_code=None, department_code=None, active_only=True):
    """Return concrete (line, department) stations with display labels
    joined in. Filter by line_code (None for centralised) or department_code.
    Centralised stations carry line_code = NULL; the call-site decides whether
    to show 'ALL LINES' or hide the column."""
    conn = get_db()
    q = """
        SELECT s.id, s.line_code, s.department_code,
               s.label, s.capacity_per_shift, s.is_active,
               d.label AS department_label, d.icon AS department_icon,
               d.is_centralised, d.sort_order AS dept_sort,
               l.line_name AS line_label, l.line_type, l.sort_order AS line_sort
          FROM stations s
          LEFT JOIN departments        d ON d.code   = s.department_code
          LEFT JOIN manufacturing_line l ON l.line_id = s.line_code
         WHERE 1=1
    """
    params = []
    if active_only:                          q += " AND s.is_active = 1"
    if department_code is not None:          q += " AND s.department_code = ?"; params.append(department_code)
    if line_code is not None:
        if line_code == '':
            q += " AND s.line_code IS NULL"
        else:
            q += " AND s.line_code = ?"; params.append(line_code)
    q += " ORDER BY l.sort_order IS NULL, l.sort_order, s.line_code, d.sort_order, s.department_code"
    rows = conn.execute(q, params).fetchall()
    conn.close(); return rows_to_list(rows)

# ═══════════════════════════════════════════════════════════════
# PRODUCTION MODULE — Mfg Orders & Batches
# ═══════════════════════════════════════════════════════════════
def _wo_id():
    from datetime import date
    return f"WO-{date.today().strftime('%Y%m%d')}-{uuid.uuid4().hex[:4].upper()}"

def _batch_id():
    from datetime import date
    return f"BTH-{date.today().strftime('%Y%m%d')}-{uuid.uuid4().hex[:4].upper()}"

def _new_log_id(prefix):
    return f"{prefix}-{uuid.uuid4().hex[:8].upper()}"

def get_mfg_orders(status=None, line_id=None):
    conn = get_db(); params = []
    q = "SELECT * FROM mfg_order WHERE 1=1"
    if status: q += " AND status=?"; params.append(status)
    if line_id: q += " AND line_id=?"; params.append(line_id)
    rows = conn.execute(q + " ORDER BY created_at DESC", params).fetchall()
    conn.close(); return rows_to_list(rows)

def create_mfg_order(data):
    conn = get_db()
    oid = _wo_id()
    conn.execute(
        """INSERT INTO mfg_order (order_id,po_ref,customer_code,sku_code,line_id,qty_ordered,due_date)
           VALUES (?,?,?,?,?,?,?)""",
        (oid,data.get('po_ref',''),data.get('customer_code',''),
         data['sku_code'],data['line_id'],data['qty_ordered'],data.get('due_date','')))
    conn.commit()
    row = conn.execute("SELECT * FROM mfg_order WHERE order_id=?", (oid,)).fetchone()
    conn.close(); return row_to_dict(row)

def get_prod_batches(line_id=None, status=None, date_=None, order_id=None):
    conn = get_db(); params = []
    q = """SELECT pb.*, mo.sku_code as order_sku, mo.po_ref, mo.customer_code
           FROM prod_batch pb
           LEFT JOIN mfg_order mo ON mo.order_id = pb.order_id
           WHERE 1=1"""
    if line_id: q += " AND pb.line_id=?"; params.append(line_id)
    if status:  q += " AND pb.status=?";  params.append(status)
    if date_:   q += " AND pb.production_date=?"; params.append(date_)
    if order_id: q += " AND pb.order_id=?"; params.append(order_id)
    rows = conn.execute(q + " ORDER BY pb.created_at DESC", params).fetchall()
    conn.close(); return rows_to_list(rows)

def create_prod_batch(data):
    conn = get_db()
    bid = _batch_id()
    conn.execute(
        """INSERT INTO prod_batch (batch_id,order_id,sku_code,line_id,qty_planned,production_date,shift)
           VALUES (?,?,?,?,?,?,?)""",
        (bid,data.get('order_id'),data['sku_code'],data['line_id'],data['qty_planned'],
         data.get('production_date') or datemod.today().isoformat(),
         data.get('shift') or 'MORNING'))
    conn.commit()
    row = conn.execute("SELECT * FROM prod_batch WHERE batch_id=?", (bid,)).fetchone()
    conn.close(); return row_to_dict(row)

def advance_prod_batch_status(batch_id, new_status):
    conn = get_db()
    conn.execute("UPDATE prod_batch SET status=? WHERE batch_id=?", (new_status, batch_id))
    conn.commit(); conn.close()

def get_prod_batch(batch_id):
    conn = get_db()
    row = conn.execute("SELECT * FROM prod_batch WHERE batch_id=?", (batch_id,)).fetchone()
    conn.close(); return row_to_dict(row)

# ═══════════════════════════════════════════════════════════════
# PRODUCTION MODULE — Station Logs
# ═══════════════════════════════════════════════════════════════
STATUS_FLOW = {
    'GLUE_MIX': 'LAMINATING', 'LAMINATING': 'COLD_PRESS',
    'COLD_PRESS': 'REPAIR', 'REPAIR': 'SANDING',
    'SANDING': 'HOT_PRESS', 'HOT_PRESS': 'GRADING',
    'GRADING': 'PACKING', 'PACKING': 'COMPLETE'
}

# ═══════════════════════════════════════════════════════════════
# HR ATTENDANCE
# ═══════════════════════════════════════════════════════════════
def _calc_hours(time_in, time_out):
    """Calc hours between HH:MM strings, returns float."""
    try:
        if not time_in or not time_out: return 0.0
        h1,m1 = [int(x) for x in time_in.split(':')]
        h2,m2 = [int(x) for x in time_out.split(':')]
        mins = (h2*60+m2) - (h1*60+m1)
        if mins < 0: mins += 24*60
        return round(mins/60.0, 2)
    except Exception:
        return 0.0

def get_attendance(work_date=None, dept=None, emp_id=None):
    conn = get_db()
    q = """SELECT a.*, e.emp_name, e.role AS position
           FROM hr_attendance a
           LEFT JOIN employee e ON a.emp_id = e.emp_id WHERE 1=1"""
    params = []
    if work_date: q += " AND a.work_date=?"; params.append(work_date)
    if dept:      q += " AND a.department=?"; params.append(dept)
    if emp_id:    q += " AND a.emp_id=?"; params.append(emp_id)
    q += " ORDER BY a.work_date DESC, a.shift, e.emp_name"
    rows = rows_to_list(conn.execute(q, params).fetchall())
    conn.close(); return rows

def save_attendance(data: dict) -> dict:
    conn = get_db()
    aid = data.get('id')
    # Auto-calc hours if not set
    reg = data.get('regular_hours')
    if reg in (None, 0, '') and data.get('time_in') and data.get('time_out'):
        total = _calc_hours(data['time_in'], data['time_out'])
        # Subtract OT from total to get regular
        ot = float(data.get('ot_hours') or 0)
        reg = max(0, total - ot)
    if aid:
        conn.execute("""UPDATE hr_attendance SET work_date=?,emp_id=?,department=?,shift=?,
            time_in=?,time_out=?,regular_hours=?,ot_hours=?,status=?,notes=?,logged_by=?
            WHERE id=?""",
            (data['work_date'],data['emp_id'],data['department'],data.get('shift','MORNING'),
             data.get('time_in',''),data.get('time_out',''),float(reg or 0),
             float(data.get('ot_hours') or 0),data.get('status','PRESENT'),
             data.get('notes',''),data.get('logged_by',''),aid))
    else:
        # Upsert by (date, emp_id, shift)
        existing = conn.execute(
            "SELECT id FROM hr_attendance WHERE work_date=? AND emp_id=? AND shift=?",
            (data['work_date'],data['emp_id'],data.get('shift','MORNING'))
        ).fetchone()
        if existing:
            aid = existing['id']
            conn.execute("""UPDATE hr_attendance SET department=?,
                time_in=?,time_out=?,regular_hours=?,ot_hours=?,status=?,notes=?,logged_by=?
                WHERE id=?""",
                (data['department'],
                 data.get('time_in',''),data.get('time_out',''),float(reg or 0),
                 float(data.get('ot_hours') or 0),data.get('status','PRESENT'),
                 data.get('notes',''),data.get('logged_by',''),aid))
        else:
            cur = conn.execute("""INSERT INTO hr_attendance
                (work_date,emp_id,department,shift,time_in,time_out,regular_hours,ot_hours,status,notes,logged_by)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (data['work_date'],data['emp_id'],data['department'],data.get('shift','MORNING'),
                 data.get('time_in',''),data.get('time_out',''),float(reg or 0),
                 float(data.get('ot_hours') or 0),data.get('status','PRESENT'),
                 data.get('notes',''),data.get('logged_by','')))
            aid = cur.lastrowid
    conn.commit()
    row = row_to_dict(conn.execute("SELECT * FROM hr_attendance WHERE id=?", (aid,)).fetchone())
    conn.close(); return row

def delete_attendance(aid: int):
    conn = get_db()
    conn.execute("DELETE FROM hr_attendance WHERE id=?", (aid,))
    conn.commit(); conn.close()

def get_attendance_summary(from_date, to_date, dept=None):
    """Aggregated by employee for HRM export."""
    conn = get_db()
    q = """SELECT a.emp_id, e.emp_name, e.role AS position, a.department,
                  COUNT(DISTINCT a.work_date) AS days_worked,
                  SUM(a.regular_hours) AS total_regular,
                  SUM(a.ot_hours) AS total_ot,
                  SUM(CASE WHEN a.status='ABSENT' THEN 1 ELSE 0 END) AS absent_count,
                  SUM(CASE WHEN a.status='LATE' THEN 1 ELSE 0 END) AS late_count
           FROM hr_attendance a LEFT JOIN employee e ON a.emp_id=e.emp_id
           WHERE a.work_date BETWEEN ? AND ?"""
    params = [from_date, to_date]
    if dept: q += " AND a.department=?"; params.append(dept)
    q += " GROUP BY a.emp_id, a.department ORDER BY e.emp_name"
    rows = rows_to_list(conn.execute(q, params).fetchall())
    conn.close(); return rows

# ═══════════════════════════════════════════════════════════════
# STATION STOCK (per-department small consumable stock)
# ═══════════════════════════════════════════════════════════════
def get_station_stock(dept, line_id=None):
    conn = get_db()
    q = """SELECT s.*, m.code AS material_code, m.name AS material_name,
                  m.type AS material_type, m.unit, m.unit_cost,
                  m.current_stock AS wh_stock
           FROM station_stock s JOIN materials m ON s.material_id=m.id
           WHERE s.department=?"""
    params = [dept]
    if line_id: q += " AND s.line_id=?"; params.append(line_id)
    q += " ORDER BY m.type, m.name"
    rows = rows_to_list(conn.execute(q, params).fetchall())
    conn.close(); return rows

def get_station_stock_movements(dept, line_id=None, from_date=None, to_date=None, limit=200):
    conn = get_db()
    q = """SELECT mv.*, m.code AS material_code, m.name AS material_name, m.unit
           FROM station_stock_movements mv JOIN materials m ON mv.material_id=m.id
           WHERE mv.department=?"""
    params = [dept]
    if line_id: q += " AND mv.line_id=?"; params.append(line_id)
    if from_date: q += " AND DATE(mv.created_at)>=?"; params.append(from_date)
    if to_date:   q += " AND DATE(mv.created_at)<=?"; params.append(to_date)
    q += " ORDER BY mv.created_at DESC LIMIT ?"; params.append(limit)
    rows = rows_to_list(conn.execute(q, params).fetchall())
    conn.close(); return rows

def log_station_stock_movement(data: dict) -> dict:
    """Log a movement and update station_stock current_qty.
       movement_type: RECEIVE (+), ISSUE (-), ADJUST (set to qty), BATCH_USE (-)
    """
    conn = get_db()
    dept = data['department']
    line_id = data.get('line_id', '')
    mat_id = int(data['material_id'])
    qty = float(data['qty_change'])
    mtype = data['movement_type']

    # Find or create stock row
    row = conn.execute("SELECT * FROM station_stock WHERE department=? AND line_id=? AND material_id=?",
                       (dept, line_id, mat_id)).fetchone()
    if row:
        sid = row['id']; current = float(row['current_qty'])
    else:
        cur = conn.execute(
            "INSERT INTO station_stock (department,line_id,material_id,current_qty) VALUES (?,?,?,?)",
            (dept, line_id, mat_id, 0))
        sid = cur.lastrowid; current = 0.0

    # Compute new qty based on movement type
    if mtype == 'ADJUST':
        new_qty = qty  # Set absolute value
        delta = qty - current
    elif mtype == 'RECEIVE':
        new_qty = current + abs(qty); delta = abs(qty)
    elif mtype in ('ISSUE', 'BATCH_USE'):
        new_qty = current - abs(qty); delta = -abs(qty)
    else:
        new_qty = current + qty; delta = qty

    # occurred_at = operator-stated date/time of the issue/use/count. Falls
    # back to "now" when the caller doesn't supply one.
    occurred_at = (data.get('occurred_at') or '').strip() or None
    # Record movement
    conn.execute("""INSERT INTO station_stock_movements
        (department,line_id,material_id,qty_change,movement_type,batch_ref,reference,notes,created_by,occurred_at)
        VALUES (?,?,?,?,?,?,?,?,?,COALESCE(?, datetime('now')))""",
        (dept, line_id, mat_id, delta, mtype, data.get('batch_ref',''),
         data.get('reference',''), data.get('notes',''), data.get('created_by',''),
         occurred_at))
    # Update stock
    conn.execute("UPDATE station_stock SET current_qty=?, last_updated=CURRENT_TIMESTAMP WHERE id=?",
                 (new_qty, sid))
    conn.commit()
    row = row_to_dict(conn.execute("""SELECT s.*, m.name AS material_name, m.unit
                                       FROM station_stock s JOIN materials m ON s.material_id=m.id
                                       WHERE s.id=?""", (sid,)).fetchone())
    conn.close(); return row

def update_station_stock_min(stock_id: int, min_qty: float):
    conn = get_db()
    conn.execute("UPDATE station_stock SET min_qty=? WHERE id=?", (min_qty, stock_id))
    conn.commit(); conn.close()


# ═══════════════════════════════════════════════════════════════
# STATION PRESETS (saved machine/table/operator sets)
# ═══════════════════════════════════════════════════════════════
import json as _json

def get_station_presets(department=None):
    conn = get_db()
    q = "SELECT * FROM station_presets"
    params = []
    if department:
        q += " WHERE department=?"; params.append(department)
    # Sort by use_count DESC, then last_used DESC, then name
    q += " ORDER BY use_count DESC, last_used_at DESC, name"
    rows = rows_to_list(conn.execute(q, params).fetchall())
    conn.close()
    # Parse preset_data JSON for each
    for r in rows:
        try: r['preset_data'] = _json.loads(r.get('preset_data') or '{}')
        except Exception: r['preset_data'] = {}
    return rows

def save_station_preset(data: dict) -> dict:
    conn = get_db()
    pid = data.get('id')
    payload = data.get('preset_data', {})
    if isinstance(payload, dict): payload = _json.dumps(payload)
    if pid:
        conn.execute(
            "UPDATE station_presets SET name=?, department=?, preset_data=? WHERE id=?",
            (data['name'], data['department'], payload, pid))
    else:
        cur = conn.execute(
            """INSERT INTO station_presets (name, department, preset_data, created_by)
               VALUES (?, ?, ?, ?)""",
            (data['name'], data['department'], payload, data.get('created_by', '')))
        pid = cur.lastrowid
    conn.commit()
    row = row_to_dict(conn.execute("SELECT * FROM station_presets WHERE id=?", (pid,)).fetchone())
    conn.close()
    try: row['preset_data'] = _json.loads(row.get('preset_data') or '{}')
    except Exception: row['preset_data'] = {}
    return row

def delete_station_preset(pid: int):
    conn = get_db()
    conn.execute("DELETE FROM station_presets WHERE id=?", (pid,))
    conn.commit(); conn.close()

def touch_station_preset(pid: int):
    """Mark preset as used: increment use_count + bump last_used_at."""
    conn = get_db()
    conn.execute(
        "UPDATE station_presets SET use_count=use_count+1, last_used_at=CURRENT_TIMESTAMP WHERE id=?",
        (pid,))
    conn.commit(); conn.close()


def get_glue_recipes(active_only=True):
    conn = get_db()
    q = "SELECT * FROM glue_recipes"
    if active_only: q += " WHERE is_active=1"
    rows = rows_to_list(conn.execute(q + " ORDER BY recipe_code").fetchall())
    conn.close(); return rows

def save_glue_recipe(data: dict) -> dict:
    """Save recipe with kg-based component layout (PV Wood format).
    `material_links` is a dict mapping ingredient key → materials.id so
    the glue-mix shortfall check can resolve catalog stock without fuzzy
    name-matching. Valid keys: e0_glue, latex_g312, flour, yellow_pigment,
    hardener, red_pigment, black_pigment, titanium."""
    conn = get_db()
    rid = data.get('id')
    # Normalise the material_links payload: keep only known keys, int values
    _VALID_INGREDIENTS = {'e0_glue','latex_g312','flour','yellow_pigment',
                          'hardener','red_pigment','black_pigment','titanium'}
    raw_links = data.get('material_links') or {}
    if isinstance(raw_links, str):
        try: raw_links = json.loads(raw_links)
        except Exception: raw_links = {}
    links = {}
    for k, v in (raw_links or {}).items():
        if k in _VALID_INGREDIENTS:
            try:
                vi = int(v) if v not in (None, '', 0) else None
                if vi: links[k] = vi
            except (TypeError, ValueError):
                pass
    flds = dict(
        name=data.get('name',''),
        veneer_thickness=data.get('veneer_thickness',''),
        wood_species=data.get('wood_species',''),
        core_board=data.get('core_board',''),
        e0_glue_kg=float(data.get('e0_glue_kg') or 0),
        latex_g312_kg=float(data.get('latex_g312_kg') or 0),
        flour_kg=float(data.get('flour_kg') or 0),
        yellow_pigment_kg=float(data.get('yellow_pigment_kg') or 0),
        hardener_kg=float(data.get('hardener_kg') or 0),
        red_pigment_kg=float(data.get('red_pigment_kg') or 0),
        black_pigment_kg=float(data.get('black_pigment_kg') or 0),
        titanium_kg=float(data.get('titanium_kg') or 0),
        mix_time_min=int(data.get('mix_time_min') or 20),
        notes=data.get('notes',''),
        is_active=int(data.get('is_active', 1)),
        material_links=json.dumps(links),
    )
    # Auto-compute total_kg if not provided
    components_sum = (flds['e0_glue_kg'] + flds['latex_g312_kg'] + flds['flour_kg']
                      + flds['yellow_pigment_kg'] + flds['hardener_kg'] + flds['red_pigment_kg']
                      + flds['black_pigment_kg'] + flds['titanium_kg'])
    flds['total_kg'] = float(data.get('total_kg') or components_sum)

    if rid:
        cols = ', '.join(f'{k}=?' for k in flds.keys())
        conn.execute(f"UPDATE glue_recipes SET {cols} WHERE id=?",
                     (*flds.values(), rid))
    else:
        flds['recipe_code'] = data['recipe_code']
        cols = ', '.join(flds.keys()); ph = ', '.join('?' for _ in flds)
        conn.execute(f"INSERT INTO glue_recipes ({cols}) VALUES ({ph})",
                     tuple(flds.values()))
        rid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.commit()
    # Phase B: glue cost is now computed live from glue_recipes.material_links
    # whenever the cost is read, so there is nothing to re-sync after a write.
    row = row_to_dict(conn.execute("SELECT * FROM glue_recipes WHERE id=?", (rid,)).fetchone())
    conn.close(); return row

# ═══════════════════════════════════════════════════════════════
# ACCOUNTING — read-only aggregations for the Accounting department
# ═══════════════════════════════════════════════════════════════

def get_accounting_stock_movements(from_date=None, to_date=None,
                                   dept=None, kinds=None, limit=2000):
    """
    Unified stock-movement feed for accounting:
      • station_stock_movements (RECEIVE / ISSUE / ADJUST / BATCH_USE)
      • fc_transfer_requests (FULFILLED) split into inbound (WH→FC) + outbound (FC→WH)
      • veneer_regrade_log (FC regrades)
      • consumable_request fulfillment (WH → dept consumption)
    """
    conn = get_db()
    rows = []
    fd = from_date or '1900-01-01'
    td = to_date or '9999-12-31'

    # 1. Station stock movements (per-department consumable in/out)
    q = f"""
        SELECT 'STATION_STOCK' as source, mv.movement_type as kind, mv.department as dept,
               mv.line_id as line_id, mv.created_at as ts, mv.created_by as actor,
               mv.material_id, m.code as material_code, m.name as material_name,
               m.unit, COALESCE(m.unit_cost, m.price, 0) as unit_cost,
               mv.qty_change as qty, mv.batch_ref as ref, mv.notes
        FROM station_stock_movements mv
        JOIN materials m ON m.id = mv.material_id
        WHERE DATE(mv.created_at) BETWEEN ? AND ?
        {' AND mv.department=?' if dept else ''}
        ORDER BY mv.created_at DESC LIMIT ?
    """
    params = [fd, td]
    if dept: params.append(dept)
    params.append(limit)
    rows.extend([dict(r) for r in conn.execute(q, params).fetchall()])

    # 2. FC transfers (fulfilled) — both directions
    q = """
        SELECT 'FC_TRANSFER' as source,
               CASE WHEN COALESCE(t.direction,'inbound')='inbound' THEN 'TRANSFER_IN' ELSE 'RETURN_TO_WH' END as kind,
               'fc' as dept, '' as line_id,
               t.fulfilled_at as ts, t.fulfilled_by as actor,
               m.id as material_id, m.code as material_code, m.name as material_name,
               m.unit, COALESCE(m.unit_cost, m.price, 0) as unit_cost,
               t.qty_fulfilled as qty, t.request_id as ref, t.notes
        FROM fc_transfer_requests t
        JOIN materials m ON m.id = t.material_id
        WHERE t.status IN ('FULFILLED','PARTIAL')
          AND t.qty_fulfilled > 0
          AND t.fulfilled_at IS NOT NULL
          AND DATE(t.fulfilled_at) BETWEEN ? AND ?
        ORDER BY t.fulfilled_at DESC LIMIT ?
    """
    rows.extend([dict(r) for r in conn.execute(q, [fd, td, limit]).fetchall()])

    # 3. Veneer regrades (within FC)
    q = """
        SELECT 'REGRADE' as source, 'REGRADE' as kind, 'fc' as dept, '' as line_id,
               rl.created_at as ts, rl.graded_by as actor,
               tm.id as material_id, tm.code as material_code,
               (COALESCE(fm.species,'')||' '||COALESCE(fm.grade,'')||' → '||COALESCE(tm.species,'')||' '||COALESCE(tm.grade,'')) as material_name,
               tm.unit, COALESCE(tm.unit_cost, tm.price, 0) as unit_cost,
               rl.qty, rl.record_id as ref, rl.notes
        FROM veneer_regrade_log rl
        JOIN materials fm ON fm.id = rl.from_material_id
        JOIN materials tm ON tm.id = rl.to_material_id
        WHERE DATE(rl.created_at) BETWEEN ? AND ?
        ORDER BY rl.created_at DESC LIMIT ?
    """
    rows.extend([dict(r) for r in conn.execute(q, [fd, td, limit]).fetchall()])

    # 4. Consumable requests fulfilled by WH (issued to dept)
    q = """
        SELECT 'CONSUMABLE_REQ' as source, 'WH_ISSUE' as kind,
               cr.department as dept, cr.line_id as line_id,
               cr.fulfilled_at as ts, cr.fulfilled_by as actor,
               m.id as material_id, m.code as material_code, m.name as material_name,
               m.unit, COALESCE(m.unit_cost, m.price, 0) as unit_cost,
               cr.qty_fulfilled as qty, cr.request_id as ref, cr.notes
        FROM consumable_request cr
        JOIN materials m ON m.id = cr.material_id
        WHERE cr.status IN ('FULFILLED','PARTIAL')
          AND cr.qty_fulfilled > 0
          AND cr.fulfilled_at IS NOT NULL
          AND DATE(cr.fulfilled_at) BETWEEN ? AND ?
        ORDER BY cr.fulfilled_at DESC LIMIT ?
    """
    rows.extend([dict(r) for r in conn.execute(q, [fd, td, limit]).fetchall()])

    # 5. Raw material receipts (warehouse received from supplier)
    q = """
        SELECT 'LOT_RECEIPT' as source, 'RECEIPT' as kind,
               'warehouse' as dept, '' as line_id,
               ml.received_at as ts, '' as actor,
               m.id as material_id, m.code as material_code, m.name as material_name,
               m.unit, COALESCE(ml.unit_cost, m.unit_cost, m.price, 0) as unit_cost,
               ml.received_qty as qty, ml.lot_code as ref, ml.notes
        FROM material_lots ml
        JOIN materials m ON m.id = ml.material_id
        WHERE DATE(ml.received_at) BETWEEN ? AND ?
        ORDER BY ml.received_at DESC LIMIT ?
    """
    rows.extend([dict(r) for r in conn.execute(q, [fd, td, limit]).fetchall()])

    # Filter by kind if specified
    if kinds:
        rows = [r for r in rows if r['kind'] in kinds]

    # Compute cost impact per row
    for r in rows:
        r['cost_impact'] = round(abs(float(r.get('qty') or 0)) * float(r.get('unit_cost') or 0), 2)

    # Sort by timestamp desc
    rows.sort(key=lambda r: (r.get('ts') or ''), reverse=True)
    conn.close()
    return rows[:limit]


def get_accounting_production_output(from_date=None, to_date=None, dept=None, line=None):
    """Aggregate production output by date + dept + line (from station log tables)."""
    conn = get_db()
    try:
        return _get_accounting_production_output_impl(conn, from_date, to_date, dept, line)
    finally:
        try: conn.close()
        except Exception: pass

def _get_accounting_production_output_impl(conn, from_date, to_date, dept, line):
    fd = from_date or '1900-01-01'
    td = to_date or '9999-12-31'

    # Per-station logs are keyed by batch_id (string = batch_number).
    # Join via prod_batch or batches to get line/dept context.
    # Use SUM(pcs_actual) from each station log to compute throughput.
    output = {}

    # Helper to add a station log's pcs to the output bucket
    def _add(date, dept_key, line_key, sku, pcs_in, pcs_out, defects=0):
        key = (date, dept_key, line_key or '', sku or '')
        b = output.setdefault(key, {
            'date': date, 'dept': dept_key, 'line': line_key or '', 'sku': sku or '',
            'pcs_in': 0, 'pcs_out': 0, 'defects': 0,
        })
        b['pcs_in'] += int(pcs_in or 0)
        b['pcs_out'] += int(pcs_out or 0)
        b['defects'] += int(defects or 0)

    # Each station log uses its own timestamp column. Run each in an isolated
    # try/except so one bad table can't kill the whole report or leak the
    # connection (which used to cascade into "database is locked" elsewhere).
    station_queries = [
        # (label, sql, columns to feed _add)
        ('cold_press', """
            SELECT DATE(cp.pressed_at) as d, 'cold_press' as dept,
                   COALESCE(po.production_line,'') as line, COALESCE(p.sku,'') as sku,
                   cp.pcs_in, cp.pcs_out, 0 as defects
            FROM cold_press_log cp
            LEFT JOIN batches b ON b.batch_number = cp.batch_id
            LEFT JOIN production_orders po ON po.id = b.prod_order_id
            LEFT JOIN products p ON p.id = po.product_id
            WHERE DATE(cp.pressed_at) BETWEEN ? AND ?
        """),
        ('hot_press', """
            SELECT DATE(hp.pressed_at) as d, 'hot_press' as dept,
                   COALESCE(po.production_line,'') as line, COALESCE(p.sku,'') as sku,
                   hp.pcs_in, hp.pcs_out, 0 as defects
            FROM hot_press_log hp
            LEFT JOIN batches b ON b.batch_number = hp.batch_id
            LEFT JOIN production_orders po ON po.id = b.prod_order_id
            LEFT JOIN products p ON p.id = po.product_id
            WHERE DATE(hp.pressed_at) BETWEEN ? AND ?
        """),
        ('sanding', """
            SELECT DATE(sl.sanded_at) as d, 'sanding' as dept,
                   COALESCE(po.production_line,'') as line, COALESCE(p.sku,'') as sku,
                   sl.pcs_in, sl.pcs_out, sl.defect_count as defects
            FROM sanding_log sl
            LEFT JOIN batches b ON b.batch_number = sl.batch_id
            LEFT JOIN production_orders po ON po.id = b.prod_order_id
            LEFT JOIN products p ON p.id = po.product_id
            WHERE DATE(sl.sanded_at) BETWEEN ? AND ?
        """),
        ('laminating', """
            SELECT DATE(ll.shift_start) as d, 'laminating' as dept,
                   COALESCE(po.production_line,'') as line, COALESCE(p.sku,'') as sku,
                   ll.pcs_target as pcs_in, ll.pcs_actual as pcs_out, 0 as defects
            FROM laminating_log ll
            LEFT JOIN batches b ON b.batch_number = ll.batch_id
            LEFT JOIN production_orders po ON po.id = b.prod_order_id
            LEFT JOIN products p ON p.id = po.product_id
            WHERE DATE(ll.shift_start) BETWEEN ? AND ?
        """),
        ('grading', """
            SELECT DATE(g.graded_at) as d, 'grading' as dept,
                   COALESCE(po.production_line,'') as line, COALESCE(p.sku,'') as sku,
                   (g.pcs_grade_a + g.pcs_grade_b + g.pcs_ncg + g.pcs_reject) as pcs_in,
                   (g.pcs_grade_a + g.pcs_grade_b) as pcs_out,
                   (g.pcs_ncg + g.pcs_reject) as defects
            FROM grading_log g
            LEFT JOIN batches b ON b.batch_number = g.batch_id
            LEFT JOIN production_orders po ON po.id = b.prod_order_id
            LEFT JOIN products p ON p.id = po.product_id
            WHERE DATE(g.graded_at) BETWEEN ? AND ?
        """),
        ('packing', """
            SELECT DATE(pk.logged_at) as d, 'packing' as dept,
                   COALESCE(po.production_line,'') as line, COALESCE(p.sku,'') as sku,
                   pk.pcs_in, pk.pcs_packed as pcs_out, 0 as defects
            FROM packing_log pk
            LEFT JOIN batches b ON b.batch_number = pk.batch_id
            LEFT JOIN production_orders po ON po.id = b.prod_order_id
            LEFT JOIN products p ON p.id = po.product_id
            WHERE DATE(pk.logged_at) BETWEEN ? AND ?
        """),
    ]
    for label, q in station_queries:
        try:
            for r in conn.execute(q, [fd, td]).fetchall():
                _add(r['d'], r['dept'], r['line'], r['sku'],
                     r['pcs_in'] or 0, r['pcs_out'] or 0, r['defects'] or 0)
        except Exception as e:
            # Don't let one broken station kill the whole report.
            # Log to stderr; connection stays alive thanks to outer try/finally.
            import sys; print(f"[accounting/{label}] skipped: {e}", file=sys.stderr)

    result = list(output.values())
    if dept: result = [r for r in result if r['dept'] == dept]
    if line: result = [r for r in result if r['line'] == line]
    # Yield % calc
    for r in result:
        r['yield_pct'] = round(r['pcs_out'] / r['pcs_in'] * 100, 1) if r['pcs_in'] else 0
    result.sort(key=lambda r: (r['date'], r['dept'], r['line']), reverse=True)
    return result


def get_accounting_summary(from_date=None, to_date=None):
    """High-level summary KPIs for the period."""
    conn = get_db()
    fd = from_date or '1900-01-01'
    td = to_date or '9999-12-31'

    # Total stock movements value
    total_consumption = conn.execute("""
        SELECT COALESCE(SUM(cr.qty_fulfilled * COALESCE(m.unit_cost, m.price, 0)), 0) as v
        FROM consumable_request cr
        JOIN materials m ON m.id = cr.material_id
        WHERE cr.status IN ('FULFILLED','PARTIAL')
          AND DATE(cr.fulfilled_at) BETWEEN ? AND ?
    """, [fd, td]).fetchone()[0]

    total_fc_transfers = conn.execute("""
        SELECT COALESCE(SUM(t.qty_fulfilled * COALESCE(m.unit_cost, m.price, 0)), 0) as v
        FROM fc_transfer_requests t JOIN materials m ON m.id = t.material_id
        WHERE t.status IN ('FULFILLED','PARTIAL')
          AND DATE(t.fulfilled_at) BETWEEN ? AND ?
    """, [fd, td]).fetchone()[0]

    # Total production output (pcs that passed grading)
    total_good = conn.execute("""
        SELECT COALESCE(SUM(pcs_grade_a + pcs_grade_b), 0)
        FROM grading_log WHERE DATE(created_at) BETWEEN ? AND ?
    """, [fd, td]).fetchone()[0]
    total_ncg = conn.execute("""
        SELECT COALESCE(SUM(pcs_ncg + pcs_reject), 0)
        FROM grading_log WHERE DATE(created_at) BETWEEN ? AND ?
    """, [fd, td]).fetchone()[0]

    # By-dept cost breakdown (from dept_cost_ledger if present)
    dept_costs = []
    try:
        dept_costs = rows_to_list(conn.execute("""
            SELECT dcl.department, COUNT(*) as request_count,
                   COALESCE(SUM(dcl.total_cost), 0) as total_cost
            FROM dept_cost_ledger dcl
            WHERE DATE(dcl.created_at) BETWEEN ? AND ?
            GROUP BY dcl.department
            ORDER BY total_cost DESC
        """, [fd, td]).fetchall())
    except Exception:
        pass

    # Batch movements count
    batch_releases = conn.execute("""
        SELECT COUNT(*) FROM batch_movements
        WHERE from_department='fc' AND to_department='laminating'
          AND DATE(moved_at) BETWEEN ? AND ?
    """, [fd, td]).fetchone()[0]
    batches_to_fg = conn.execute("""
        SELECT COUNT(*) FROM batch_movements
        WHERE to_department='fg_warehouse'
          AND DATE(moved_at) BETWEEN ? AND ?
    """, [fd, td]).fetchone()[0]

    conn.close()
    return {
        'period': {'from': fd, 'to': td},
        'total_consumption_value': round(total_consumption, 2),
        'total_fc_transfer_value': round(total_fc_transfers, 2),
        'total_good_pcs': int(total_good),
        'total_defect_pcs': int(total_ncg),
        'yield_pct': round(total_good / (total_good + total_ncg) * 100, 1) if (total_good + total_ncg) > 0 else 0,
        'batch_releases': batch_releases,
        'batches_to_fg': batches_to_fg,
        'dept_costs': dept_costs,
    }


# ════════════════════════════════════════════════════════════════
# PURCHASING — purchase requests + supplier orders
# ════════════════════════════════════════════════════════════════
def _next_pr_number(conn) -> str:
    today = datemod.today().strftime("%Y%m%d")
    n = conn.execute("SELECT COUNT(*) FROM purchase_requests WHERE request_number LIKE ?",
                     (f"PR-{today}-%",)).fetchone()[0]
    return f"PR-{today}-{n+1:03d}"

def _next_pr_group_number(conn) -> str:
    today = datemod.today().strftime("%Y%m%d")
    n = conn.execute("SELECT COUNT(DISTINCT group_number) FROM purchase_requests "
                     "WHERE group_number LIKE ?", (f"PRG-{today}-%",)).fetchone()[0]
    return f"PRG-{today}-{n+1:03d}"


def create_purchase_requests_bulk(*, lines: list, requested_by: str = '',
                                  source_po_id=None, priority: int = 2,
                                  needed_by: str = None, suggested_supplier: str = '',
                                  notes: str = '') -> dict:
    """Create one purchase_requests row per line; all share a group_number.
    Each line may carry a list of `splits` [{planned_qty, planned_arrival, carrier}]
    that seed pr_shipments so warehouse sees split deliveries up-front.

    line keys: request_type, material_id, qty_requested, uom (opt),
               priority (opt — overrides header), needed_by (opt),
               suggested_supplier (opt), notes (opt), splits (opt list).
    """
    if not lines:
        raise ValueError("at least one line is required")
    conn = get_db()
    try:
        group_num = _next_pr_group_number(conn)
        created = []
        for ln in lines:
            rt = ln.get('request_type') or 'RAW_MATERIAL'
            if rt not in ('RAW_MATERIAL', 'CONSUMABLE'):
                raise ValueError(f"invalid request_type {rt}")
            mid = int(ln.get('material_id') or 0)
            qty = float(ln.get('qty_requested') or 0)
            if not mid or qty <= 0:
                raise ValueError("each line needs material_id and positive qty")
            line_prio = int(ln.get('priority') or priority or 2)
            if line_prio not in (1, 2, 3): line_prio = 2
            num = _next_pr_number(conn)
            cur = conn.execute("""
                INSERT INTO purchase_requests
                  (request_number, request_type, material_id, qty_requested, uom,
                   source_po_id, priority, needed_by, suggested_supplier, notes,
                   requested_by, status, group_number)
                VALUES (?,?,?,?,?,?,?,?,?,?,?, 'NEW', ?)
            """, (num, rt, mid, qty, ln.get('uom') or '',
                  source_po_id, line_prio,
                  ln.get('needed_by') or needed_by,
                  ln.get('suggested_supplier') or suggested_supplier,
                  ln.get('notes') or notes,
                  requested_by, group_num))
            pr_id = cur.lastrowid
            # Seed shipments from split list
            splits = ln.get('splits') or []
            seq = 0
            for sp in splits:
                sq = float(sp.get('planned_qty') or 0)
                if sq <= 0: continue
                seq += 1
                conn.execute("""
                    INSERT INTO pr_shipments
                      (pr_id, sequence, planned_qty, planned_arrival, carrier,
                       notes, created_by)
                    VALUES (?,?,?,?,?,?,?)
                """, (pr_id, seq, sq, sp.get('planned_arrival') or None,
                      sp.get('carrier') or '', sp.get('notes') or '',
                      requested_by))
            created.append({'id': pr_id, 'request_number': num,
                            'material_id': mid, 'qty_requested': qty,
                            'splits_created': seq})
        conn.commit()
        return {'group_number': group_num, 'count': len(created),
                'requests': created}
    finally:
        conn.close()

def create_purchase_request(*, request_type: str, material_id: int, qty_requested: float,
                            uom: str = '', source_po_id=None, priority: int = 2,
                            needed_by: str = None, suggested_supplier: str = '',
                            notes: str = '', requested_by: str = '') -> dict:
    if request_type not in ('RAW_MATERIAL', 'CONSUMABLE'):
        raise ValueError("request_type must be RAW_MATERIAL or CONSUMABLE")
    if not material_id or float(qty_requested) <= 0:
        raise ValueError("material_id and positive qty_requested are required")
    conn = get_db()
    try:
        num = _next_pr_number(conn)
        cur = conn.execute("""
            INSERT INTO purchase_requests
            (request_number, request_type, material_id, qty_requested, uom, source_po_id,
             priority, needed_by, suggested_supplier, notes, requested_by, status)
            VALUES (?,?,?,?,?,?,?,?,?,?,?, 'NEW')
        """, (num, request_type, material_id, float(qty_requested), uom, source_po_id,
              int(priority or 2), needed_by, suggested_supplier, notes, requested_by))
        conn.commit()
        return {"id": cur.lastrowid, "request_number": num, "status": "NEW"}
    finally:
        conn.close()

def list_purchase_requests(status=None, request_type=None) -> list:
    conn = get_db()
    q = """SELECT pr.*, m.code AS material_code, m.name AS material_name, m.type AS material_type,
                  po.po_number AS source_po_number,
                  (
                    (SELECT COUNT(*) FROM material_documents d
                       WHERE d.purchase_request_id = pr.id AND d.lot_id IS NULL)
                    + (SELECT COUNT(*) FROM pr_document_links l
                       WHERE l.pr_id = pr.id)
                  ) AS doc_count
           FROM purchase_requests pr
           JOIN materials m ON m.id = pr.material_id
           LEFT JOIN purchase_orders po ON po.id = pr.source_po_id
           WHERE 1=1"""
    params = []
    if status:
        q += " AND pr.status = ?"; params.append(status)
    if request_type:
        q += " AND pr.request_type = ?"; params.append(request_type)
    q += " ORDER BY pr.group_number DESC NULLS LAST, pr.priority ASC, pr.requested_at DESC LIMIT 2000"
    rows = rows_to_list(conn.execute(q, params).fetchall())
    conn.close()
    return rows

def update_purchase_request_status(pr_id: int, status: str, actor: str = '',
                                   supplier_po_ref: str = '',
                                   estimated_arrival: str = '') -> dict:
    # NEW              = Request raised by Planning/Warehouse
    # APPROVED         = Purchasing has reviewed and approved
    # PO_ISSUED        = Purchase order sent to supplier
    # AWAITING_ARRIVAL = Supplier confirmed; materials in transit, ETA known
    # RECEIVED         = Materials physically received
    # CANCELLED        = Request cancelled
    valid = ('NEW','APPROVED','PO_ISSUED','AWAITING_ARRIVAL','RECEIVED','OVER_RECEIVED','CANCELLED')
    if status not in valid:
        raise ValueError(f"invalid status (must be one of {valid})")
    conn = get_db()
    try:
        row = conn.execute("SELECT * FROM purchase_requests WHERE id=?", (pr_id,)).fetchone()
        if not row:
            return {"error": "not found"}
        ts_col = {
            'APPROVED':         'approved_at',
            'PO_ISSUED':        'po_issued_at',
            'AWAITING_ARRIVAL': 'awaiting_since',
            'RECEIVED':         'received_at',
        }.get(status)
        actor_col = {'APPROVED':'approved_by'}.get(status)
        sets = ["status = ?"]; params = [status]
        if ts_col:    sets.append(f"{ts_col} = datetime('now')")
        if actor_col and actor: sets.append(f"{actor_col} = ?"); params.append(actor)
        if supplier_po_ref:
            sets.append("supplier_po_ref = ?"); params.append(supplier_po_ref)
        if estimated_arrival:
            sets.append("estimated_arrival = ?"); params.append(estimated_arrival)
        params.append(pr_id)
        conn.execute(f"UPDATE purchase_requests SET {', '.join(sets)} WHERE id = ?", params)
        conn.commit()
        return {"ok": True, "id": pr_id, "status": status}
    finally:
        conn.close()

def get_material_shortfalls(material_types: list = None) -> dict:
    """Aggregate raw-material shortfalls across all open sales POs.
    Returns one row per material with: required (sum of BOM × qty over all open POs),
    on_hand (fc_stock + stock), shortfall, and the contributing POs.
    Default scope: material types 'board' and 'veneer'."""
    if material_types is None:
        material_types = ['board', 'veneer']
    conn = get_db()
    try:
        return _get_material_shortfalls_impl(conn, material_types)
    finally:
        conn.close()

def _get_material_shortfalls_impl(conn, material_types):
    """Iterate every open sales PO and reuse get_po_material_readiness so the
    math (pallets × pallet_qty for boards/veneers, g/face for glue, glue_formula
    skipped, etc.) is identical to what the PO release page shows."""
    closed_statuses = {'COMPLETED', 'CLOSED', 'CANCELLED', 'DELIVERED'}
    # Filter values are matched as case-insensitive substrings against the
    # actual `materials.type` column. This handles real DB values like
    # `core_board`, `veneer_sheet`, `packing`, `adhesive`, `glue_formula`.
    aliases = {
        'board':      ['core_board', 'board'],
        'veneer':     ['veneer_sheet', 'veneer'],
        'glue':       ['glue_formula', 'glue_component', 'glue', 'adhesive'],
        'consumable': ['consumable', 'packing', 'adhesive'],
    }
    type_keys = []
    for t in (material_types or []):
        k = t.lower().strip()
        type_keys.extend(aliases.get(k, [k]))
    type_keys = list({k for k in type_keys if k})

    def _type_matches(mtype: str) -> bool:
        if not type_keys: return True
        mt = (mtype or '').lower()
        return any(k in mt for k in type_keys)

    open_pos = rows_to_list(conn.execute("""
        SELECT id, po_number, customer, delivery_date, status, COALESCE(priority,2) AS priority
        FROM purchase_orders
    """).fetchall())
    open_pos = [p for p in open_pos
                if (p.get('status') or '').upper() not in closed_statuses]

    # material_id -> aggregated entry across all POs
    agg = {}
    for po in open_pos:
        # NOTE: get_po_material_readiness opens its own connection — fine, we only
        # call it once per open PO and the read load is small.
        rd = get_po_material_readiness(po['id']) or {}
        for m in rd.get('materials') or []:
            if not _type_matches(m.get('material_type')):
                continue
            mid = m['material_id']
            if mid not in agg:
                agg[mid] = {
                    'material_id':   mid,
                    'material_code': '',  # filled below from materials table
                    'material_name': m.get('material_name') or '',
                    'material_type': m.get('material_type') or '',
                    'uom':           m.get('unit') or '',
                    'unit_cost_thb': float(m.get('unit_cost') or 0),
                    'on_hand':       float(m.get('current_stock') or 0),
                    'required':      0.0,
                    'contributing_pos': [],
                }
            agg[mid]['required'] += float(m.get('required') or 0)
            agg[mid]['contributing_pos'].append({
                'po_id':         po['id'],
                'po_number':     po.get('po_number'),
                'customer':      po.get('customer'),
                'delivery_date': po.get('delivery_date'),
                'status':        po.get('status'),
                'priority':      po.get('priority') or 2,
                'need':          round(float(m.get('required') or 0), 3),
            })

    # Backfill material_code (and any missing data) + FC stock
    if agg:
        ids = list(agg.keys())
        placeholders = ",".join(["?"] * len(ids))
        for r in conn.execute(
            f"SELECT id, code, COALESCE(fc_stock,0) AS fc FROM materials WHERE id IN ({placeholders})",
            ids,
        ).fetchall():
            r = dict(r)
            entry = agg.get(r['id'])
            if entry:
                entry['material_code'] = r.get('code') or ''
                # add FC stock on top of current_stock for total on-hand
                entry['on_hand'] = float(entry['on_hand']) + float(r.get('fc') or 0)

    # Open PRs already raised — subtract so we don't double-request
    # Workflow rank — higher = further along the procurement pipeline.
    STATUS_RANK = {'NEW': 1, 'APPROVED': 2, 'ORDERED': 3, 'PO_ISSUED': 3, 'AWAITING_ARRIVAL': 4}
    out = []
    for mid, entry in agg.items():
        open_pr_rows = conn.execute("""
            SELECT id, qty_requested, status, estimated_arrival, request_number,
                   requested_at, approved_at, ordered_at, po_issued_at, awaiting_since
            FROM purchase_requests
            WHERE material_id = ?
              AND status IN ('NEW','APPROVED','ORDERED','PO_ISSUED','AWAITING_ARRIVAL')
            ORDER BY id ASC
        """, (mid,)).fetchall()
        open_pr_rows = [dict(r) for r in open_pr_rows]
        open_pr = sum(float(r.get('qty_requested') or 0) for r in open_pr_rows)
        # Pick the most informative ETA: earliest non-null
        eta_pick = next((r for r in sorted(open_pr_rows,
            key=lambda x: (x.get('estimated_arrival') is None, x.get('estimated_arrival') or '')) if r.get('estimated_arrival')), None)
        pr_eta  = eta_pick['estimated_arrival'] if eta_pick else None
        pr_refs = [r.get('request_number') for r in open_pr_rows if r.get('request_number')]
        # Latest = furthest-along open PR (highest STATUS_RANK; ties broken by most recent)
        latest_pr = max(open_pr_rows,
            key=lambda r: (STATUS_RANK.get(r.get('status'), 0), r.get('id') or 0),
            default=None) if open_pr_rows else None
        required = round(entry['required'], 3)
        on_hand  = round(float(entry['on_hand']), 3)
        shortfall = required - on_hand - open_pr
        # Safety-stock buffer: how much room above the requirement remains after
        # taking on-hand + any open PR into account.
        buffer = (on_hand + open_pr) - required
        # LOW threshold: less than 20% of required as buffer (or absolute < 50 units
        # for very small required totals where 20% is trivial).
        low_threshold = max(required * 0.20, 50.0)
        if shortfall > 0:
            status = 'SHORT'
        elif (required - on_hand) > 0:
            # Fully covered by stock+PR but PR still in flight
            status = 'PR_PENDING'
        elif buffer < low_threshold and required > 0:
            # Covered, but safety stock thin — planner can pre-order
            status = 'LOW'
        else:
            status = 'OK'

        # Sort contributing POs: earliest delivery first, biggest need next
        contrib = sorted(entry['contributing_pos'],
            key=lambda x: ((x.get('delivery_date') is None), x.get('delivery_date') or '', -x.get('need', 0)))[:10]

        out.append({
            'material_id':       mid,
            'material_code':     entry.get('material_code') or '',
            'material_name':     entry.get('material_name') or '',
            'material_type':     entry.get('material_type') or '',
            'uom':               entry.get('uom') or '',
            'unit_cost_thb':     round(float(entry.get('unit_cost_thb') or 0), 4),
            'on_hand':           on_hand,
            'required':          required,
            'open_pr_qty':       round(open_pr, 3),
            'shortfall':         round(max(shortfall, 0), 3),
            'status':            status,
            'shortfall_cost_thb': round(max(shortfall, 0) * float(entry.get('unit_cost_thb') or 0), 2),
            'buffer_qty':        round(buffer, 3),
            'low_threshold_qty': round(low_threshold, 3),
            'suggested_request_qty': round(max(low_threshold - buffer, 0), 3) if status == 'LOW' else round(max(shortfall, 0), 3),
            'contributing_pos':  contrib,
            'max_priority':      min((p.get('priority') or 2) for p in contrib) if contrib else 2,
            'earliest_delivery': contrib[0]['delivery_date'] if contrib else None,
            'pr_eta':            pr_eta,
            'open_pr_refs':      pr_refs[:5],
            # Latest PR drives the displayed lifecycle status when a PR exists
            'latest_pr_id':        latest_pr['id'] if latest_pr else None,
            'latest_pr_number':    latest_pr['request_number'] if latest_pr else None,
            'latest_pr_status':    latest_pr['status'] if latest_pr else None,
            'latest_pr_requested_at': latest_pr['requested_at'] if latest_pr else None,
            'latest_pr_approved_at':  latest_pr['approved_at'] if latest_pr else None,
            'latest_pr_po_issued_at': (latest_pr['po_issued_at'] or latest_pr['ordered_at']) if latest_pr else None,
            'latest_pr_awaiting_since': latest_pr['awaiting_since'] if latest_pr else None,
            'open_pr_count':     len(open_pr_rows),
        })

    # Order: SHORT first, then PR_PENDING, LOW, then OK; within each tier
    # urgent (priority 1) POs bubble to the top.
    order_key = {'SHORT': 0, 'PR_PENDING': 1, 'LOW': 2, 'OK': 3}
    out.sort(key=lambda r: (order_key.get(r['status'], 9),
                            r.get('max_priority') or 2,
                            r['material_type'], r['material_name']))

    summary = {
        'total_materials':  len(out),
        'materials_short':  sum(1 for x in out if x['status'] == 'SHORT'),
        'materials_pending':sum(1 for x in out if x['status'] == 'PR_PENDING'),
        'materials_low':    sum(1 for x in out if x['status'] == 'LOW'),
        'materials_ok':     sum(1 for x in out if x['status'] == 'OK'),
        'total_shortfall_value_thb': round(sum(x['shortfall_cost_thb'] for x in out), 2),
    }
    return {'summary': summary, 'rows': out}


# ═══════════════════════════════════════════════════════════════
# PR SHIPMENT SCHEDULING + WAREHOUSE RECEIVING
# ═══════════════════════════════════════════════════════════════
def create_pr_shipment(*, pr_id: int, planned_qty: float, planned_arrival: str = None,
                       supplier_ref: str = '', carrier: str = '',
                       notes: str = '', created_by: str = '') -> dict:
    if not pr_id or float(planned_qty) <= 0:
        raise ValueError("pr_id and positive planned_qty are required")
    conn = get_db()
    try:
        pr = conn.execute("SELECT id, status FROM purchase_requests WHERE id=?", (pr_id,)).fetchone()
        if not pr:
            raise ValueError(f"Purchase request {pr_id} not found")
        seq = (conn.execute("SELECT COALESCE(MAX(sequence),0) FROM pr_shipments WHERE pr_id=?",
                            (pr_id,)).fetchone()[0] or 0) + 1
        cur = conn.execute("""
            INSERT INTO pr_shipments
              (pr_id, sequence, planned_qty, planned_arrival, supplier_ref, carrier, notes, created_by)
            VALUES (?,?,?,?,?,?,?,?)
        """, (pr_id, seq, float(planned_qty), planned_arrival, supplier_ref, carrier, notes, created_by))
        conn.commit()
        return {'id': cur.lastrowid, 'pr_id': pr_id, 'sequence': seq, 'status': 'PLANNED'}
    finally:
        conn.close()


def list_pr_shipments(pr_id=None, status=None, only_open: bool = False,
                      include_implicit: bool = False) -> list:
    """Return scheduled shipments. With `include_implicit=True` we also
    synthesize an "UNPLANNED" virtual row for any in-flight PR (APPROVED /
    PO_ISSUED / AWAITING_ARRIVAL / PARTIAL) that has no scheduled shipments
    *or* still has un-scheduled remainder beyond its planned shipments. This
    means the Warehouse receiving page surfaces every PR that may arrive,
    even if Purchasing hasn't broken it into shipment dates yet."""
    conn = get_db()
    q = """
        SELECT s.*, pr.request_number, pr.qty_requested, pr.status AS pr_status,
               pr.estimated_arrival AS pr_eta, pr.supplier_po_ref,
               m.id   AS material_id, m.code AS material_code,
               m.name AS material_name, m.type AS material_type, m.unit AS uom,
               (SELECT COUNT(*) FROM material_documents d
                  WHERE d.purchase_request_id = pr.id AND d.lot_id IS NULL) AS doc_count
        FROM pr_shipments s
        JOIN purchase_requests pr ON pr.id = s.pr_id
        JOIN materials m ON m.id = pr.material_id
        WHERE 1=1
    """
    params = []
    if pr_id:
        q += " AND s.pr_id = ?"; params.append(pr_id)
    if status:
        q += " AND s.status = ?"; params.append(status)
    if only_open:
        q += " AND s.status IN ('PLANNED','PARTIAL')"
    q += " ORDER BY CASE WHEN s.planned_arrival IS NULL THEN 1 ELSE 0 END, s.planned_arrival ASC, s.id ASC LIMIT 2000"
    rows = rows_to_list(conn.execute(q, params).fetchall())

    if include_implicit:
        # Set of PR ids with at least one scheduled shipment row in the result
        # (so we know how much remains unscheduled for each one).
        scheduled_qty_by_pr = {}
        received_qty_by_pr  = {}
        for r in rows:
            scheduled_qty_by_pr[r['pr_id']] = scheduled_qty_by_pr.get(r['pr_id'], 0) + float(r.get('planned_qty') or 0)
            received_qty_by_pr[r['pr_id']]  = received_qty_by_pr.get(r['pr_id'], 0) + float(r.get('received_qty') or 0)

        # All in-flight PRs (status set tells us they're heading toward receipt)
        prq = """
            SELECT pr.id AS pr_id, pr.request_number, pr.qty_requested, pr.status AS pr_status,
                   pr.estimated_arrival AS pr_eta, pr.supplier_po_ref, pr.suggested_supplier,
                   m.id   AS material_id, m.code AS material_code,
                   m.name AS material_name, m.type AS material_type, m.unit AS uom,
                   (SELECT COUNT(*) FROM material_documents d
                      WHERE d.purchase_request_id = pr.id AND d.lot_id IS NULL) AS doc_count,
                   COALESCE((SELECT SUM(received_qty) FROM material_lots ml
                              WHERE ml.purchase_request_id = pr.id), 0) AS already_received_total
            FROM purchase_requests pr
            JOIN materials m ON m.id = pr.material_id
            WHERE pr.status IN ('APPROVED','PO_ISSUED','ORDERED','AWAITING_ARRIVAL')
        """
        prargs = []
        if pr_id:
            prq += " AND pr.id = ?"; prargs.append(pr_id)
        prq += " ORDER BY CASE WHEN pr.estimated_arrival IS NULL THEN 1 ELSE 0 END, pr.estimated_arrival ASC, pr.id ASC"
        prs_inflight = rows_to_list(conn.execute(prq, prargs).fetchall())

        synthetic = []
        for pr in prs_inflight:
            pid = pr['pr_id']
            ordered = float(pr.get('qty_requested') or 0)
            scheduled = float(scheduled_qty_by_pr.get(pid, 0))
            unscheduled = max(0.0, ordered - scheduled)
            if unscheduled <= 1e-6:
                continue   # everything is already on a shipment row
            synthetic.append({
                'id':              None,          # virtual row
                'pr_id':           pid,
                'sequence':        '—',
                'planned_qty':     round(unscheduled, 3),
                'planned_arrival': pr.get('pr_eta'),
                'supplier_ref':    pr.get('supplier_po_ref'),
                'carrier':         '',
                'notes':           '',
                'status':          'UNPLANNED',
                'received_qty':    0.0,
                'received_at':     None,
                'received_by':     None,
                'lot_id':          None,
                'created_at':      None,
                'created_by':      None,
                'request_number':  pr.get('request_number'),
                'qty_requested':   pr.get('qty_requested'),
                'pr_status':       pr.get('pr_status'),
                'pr_eta':          pr.get('pr_eta'),
                'supplier_po_ref': pr.get('supplier_po_ref'),
                'material_id':     pr.get('material_id'),
                'material_code':   pr.get('material_code'),
                'material_name':   pr.get('material_name'),
                'material_type':   pr.get('material_type'),
                'uom':             pr.get('uom'),
                'doc_count':       pr.get('doc_count'),
                'already_received_total': pr.get('already_received_total'),
            })
        rows.extend(synthetic)
        # Re-sort by arrival date so the warehouse view stays chronological
        rows.sort(key=lambda r: (r.get('planned_arrival') is None,
                                 r.get('planned_arrival') or '9999-99-99',
                                 r.get('pr_id') or 0))

    conn.close()
    return rows


def quick_receive_for_pr(*, pr_id: int, received_qty: float, planned_arrival: str = None,
                         supplier_ref: str = '', carrier: str = '',
                         lot_code: str = '', unit_cost: float = 0,
                         expiry_date: str = None, supplier: str = '',
                         supplier_lot_ref: str = '', notes: str = '',
                         received_by: str = '') -> dict:
    """One-shot helper: warehouse receives goods against a PR that had no
    scheduled shipment row. We create the shipment row implicitly with the
    received qty + today's planned_arrival, then immediately call the normal
    receive_pr_shipment so the lot is created and docs auto-attached."""
    if float(received_qty) <= 0:
        raise ValueError("received_qty must be positive")
    ship = create_pr_shipment(
        pr_id=pr_id, planned_qty=float(received_qty),
        planned_arrival=planned_arrival or datemod.today().isoformat(),
        supplier_ref=supplier_ref, carrier=carrier,
        notes=notes or 'Created during walk-in receipt',
        created_by=received_by)
    return receive_pr_shipment(
        shipment_id=ship['id'], received_qty=float(received_qty),
        lot_code=lot_code, unit_cost=unit_cost, expiry_date=expiry_date,
        supplier=supplier, supplier_lot_ref=supplier_lot_ref, notes=notes,
        received_by=received_by)


def split_pr_shipment(*, shipment_id: int, split_qty: float,
                      new_planned_arrival: str = None, new_carrier: str = None,
                      new_supplier_ref: str = None) -> dict:
    """Split one PLANNED shipment into two: the original keeps (planned - split)
    and a brand-new shipment carries `split_qty`. Used when a delivery is
    confirmed to come in two trucks instead of one."""
    if float(split_qty) <= 0:
        raise ValueError("split_qty must be positive")
    conn = get_db()
    try:
        s = conn.execute("SELECT * FROM pr_shipments WHERE id=?", (shipment_id,)).fetchone()
        if not s:
            raise ValueError("Shipment not found")
        s = dict(s)
        if s['status'] != 'PLANNED':
            raise ValueError("Only PLANNED shipments can be split")
        planned = float(s['planned_qty'])
        remaining = float(s.get('received_qty') or 0)
        if float(split_qty) >= (planned - remaining):
            raise ValueError("split_qty must be less than the planned qty of the source shipment")
    finally:
        conn.close()
    # Lower the original
    update_pr_shipment(shipment_id=shipment_id, planned_qty=round(planned - float(split_qty), 3))
    # Create the new shipment
    new = create_pr_shipment(
        pr_id=s['pr_id'], planned_qty=float(split_qty),
        planned_arrival=new_planned_arrival or s.get('planned_arrival'),
        supplier_ref=new_supplier_ref if new_supplier_ref is not None else (s.get('supplier_ref') or ''),
        carrier=new_carrier if new_carrier is not None else (s.get('carrier') or ''),
        notes=f"Split from shipment #{s['sequence']}",
        created_by=s.get('created_by') or '')
    return {'ok': True, 'source_shipment_id': shipment_id, 'new_shipment': new}


def receive_pr_shipment(*, shipment_id: int, received_qty: float, lot_code: str = '',
                        unit_cost: float = 0, expiry_date: str = None,
                        supplier: str = '', supplier_lot_ref: str = '',
                        notes: str = '', received_by: str = '') -> dict:
    """Warehouse marks a planned shipment as received → creates a material_lot
    for the received qty, auto-attaches any PR-scoped supplier docs to it, and
    bumps current_stock. If less than the planned qty is received the shipment
    is marked PARTIAL and the remainder stays open."""
    if float(received_qty) <= 0:
        raise ValueError("received_qty must be positive")
    conn = get_db()
    try:
        s = conn.execute("SELECT * FROM pr_shipments WHERE id=?", (shipment_id,)).fetchone()
        if not s:
            raise ValueError(f"Shipment {shipment_id} not found")
        s = dict(s)
        if s['status'] == 'RECEIVED':
            raise ValueError("Shipment already received")
        pr = conn.execute("SELECT * FROM purchase_requests WHERE id=?", (s['pr_id'],)).fetchone()
        if not pr:
            raise ValueError("Linked purchase request missing")
        pr = dict(pr)
        material_id = pr['material_id']

        # Auto lot code if not supplied
        if not lot_code:
            lot_code = f"LOT-{pr['request_number'] or pr['id']}-S{s['sequence']}-{datemod.today().strftime('%Y%m%d')}"

        # Create the lot
        cur = conn.execute("""
            INSERT INTO material_lots
              (lot_code, material_id, supplier, supplier_lot_ref, received_qty, remaining_qty,
               uom, unit_cost, expiry_date, purchase_request_id, notes)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)
        """, (lot_code, material_id, supplier or s.get('carrier') or '',
              supplier_lot_ref or s.get('supplier_ref') or '',
              float(received_qty), float(received_qty),
              pr.get('uom') or '', float(unit_cost or 0), expiry_date,
              s['pr_id'],
              (notes or '') + f" [Shipment #{s['sequence']} of PR {pr.get('request_number')}]"))
        lot_id = cur.lastrowid

        # Bump warehouse stock
        try:
            conn.execute(
                "UPDATE materials SET current_stock = COALESCE(current_stock,0) + ? WHERE id=?",
                (float(received_qty), material_id))
        except Exception:
            pass

        # Propagate any PR-scoped supplier documents to this lot
        try:
            _attach_pr_docs_to_lot(conn, lot_id, int(s['pr_id']))
        except Exception:
            pass

        # Update shipment row
        new_received = float(s.get('received_qty') or 0) + float(received_qty)
        new_status = 'RECEIVED' if new_received >= float(s['planned_qty']) - 1e-6 else 'PARTIAL'
        conn.execute("""
            UPDATE pr_shipments
            SET received_qty = ?, received_at = datetime('now'),
                received_by = ?, lot_id = COALESCE(lot_id, ?), status = ?
            WHERE id = ?
        """, (new_received, received_by, lot_id, new_status, shipment_id))

        # Decide PR rollup status:
        #   total < requested  →  leave as-is
        #   total == requested →  RECEIVED
        #   total >  requested →  OVER_RECEIVED  (accounting flag)
        total = conn.execute(
            "SELECT COALESCE(SUM(received_qty),0) FROM material_lots WHERE purchase_request_id=?",
            (s['pr_id'],)).fetchone()[0] or 0
        total = float(total)
        requested = float(pr.get('qty_requested') or 0)
        if requested > 0:
            if total > requested + 1e-6 and pr.get('status') != 'OVER_RECEIVED':
                conn.execute("""UPDATE purchase_requests
                    SET status='OVER_RECEIVED', received_at=datetime('now'),
                        notes = COALESCE(notes,'') ||
                                printf(' [OVER_RECEIVED by %.2f units on %s]',
                                       ?, datetime('now'))
                    WHERE id=?""", (total - requested, s['pr_id']))
            elif total >= requested - 1e-6 and pr.get('status') not in ('RECEIVED','OVER_RECEIVED'):
                conn.execute(
                    "UPDATE purchase_requests SET status='RECEIVED', received_at=datetime('now') WHERE id=?",
                    (s['pr_id'],))

        conn.commit()
        return {
            'ok': True, 'shipment_id': shipment_id, 'lot_id': lot_id,
            'shipment_status': new_status, 'lot_code': lot_code,
        }
    finally:
        conn.close()


def update_pr_shipment(*, shipment_id: int, planned_qty=None, planned_arrival=None,
                       supplier_ref=None, carrier=None, notes=None, status=None) -> dict:
    conn = get_db()
    try:
        s = conn.execute("SELECT * FROM pr_shipments WHERE id=?", (shipment_id,)).fetchone()
        if not s: raise ValueError("Shipment not found")
        sets, params = [], []
        for col, val in [('planned_qty', planned_qty), ('planned_arrival', planned_arrival),
                         ('supplier_ref', supplier_ref), ('carrier', carrier),
                         ('notes', notes), ('status', status)]:
            if val is not None:
                sets.append(f"{col}=?"); params.append(val)
        if not sets: return {'ok': True, 'noop': True}
        params.append(shipment_id)
        conn.execute(f"UPDATE pr_shipments SET {', '.join(sets)} WHERE id=?", params)
        conn.commit()
        return {'ok': True, 'shipment_id': shipment_id}
    finally:
        conn.close()


def delete_pr_shipment(shipment_id: int) -> dict:
    conn = get_db()
    try:
        s = conn.execute("SELECT status FROM pr_shipments WHERE id=?", (shipment_id,)).fetchone()
        if not s: raise ValueError("Shipment not found")
        if s['status'] not in ('PLANNED', 'CANCELLED'):
            raise ValueError("Cannot delete a shipment that has already been received")
        conn.execute("DELETE FROM pr_shipments WHERE id=?", (shipment_id,))
        conn.commit()
        return {'ok': True}
    finally:
        conn.close()


# ════════════════════════════════════════════════════════════════
# FORKLIFTS — station-leader managed equipment + oil requests
# ════════════════════════════════════════════════════════════════
def list_forklifts(dept: str = None, status: str = None) -> list:
    conn = get_db()
    try:
        q = "SELECT * FROM forklifts WHERE 1=1"
        params = []
        if dept:   q += " AND LOWER(dept) = LOWER(?)"; params.append(dept)
        if status: q += " AND status = ?"; params.append(status)
        q += " ORDER BY code"
        rows = rows_to_list(conn.execute(q, params).fetchall())
        # Pending-oil counts so the UI can show a badge per forklift
        for r in rows:
            r['open_oil_requests'] = conn.execute(
                "SELECT COUNT(*) FROM forklift_oil_requests WHERE forklift_id=? AND status='PENDING'",
                (r['id'],)).fetchone()[0]
        return rows
    finally:
        conn.close()

def upsert_forklift(*, id=None, code: str, name: str = '', dept: str = '',
                    production_line: str = '', model: str = '',
                    fuel_type: str = 'diesel', status: str = 'active',
                    hours_meter: float = 0, last_service_at=None,
                    notes: str = '', created_by: str = '') -> dict:
    if not code:
        raise ValueError("code is required")
    conn = get_db()
    try:
        if id:
            conn.execute("""
                UPDATE forklifts SET code=?, name=?, dept=?, production_line=?, model=?,
                    fuel_type=?, status=?, hours_meter=?, last_service_at=?, notes=?
                WHERE id=?
            """, (code, name, dept, production_line, model, fuel_type, status,
                  float(hours_meter or 0), last_service_at, notes, id))
            fid = id
        else:
            cur = conn.execute("""
                INSERT INTO forklifts
                  (code, name, dept, production_line, model, fuel_type, status,
                   hours_meter, last_service_at, notes, created_by)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)
            """, (code, name, dept, production_line, model, fuel_type, status,
                  float(hours_meter or 0), last_service_at, notes, created_by))
            fid = cur.lastrowid
        conn.commit()
        return {'ok': True, 'id': fid}
    finally:
        conn.close()

def delete_forklift(forklift_id: int) -> dict:
    conn = get_db()
    try:
        # Soft-retire if there are existing requests; hard-delete otherwise
        n = conn.execute("SELECT COUNT(*) FROM forklift_oil_requests WHERE forklift_id=?",
                        (forklift_id,)).fetchone()[0]
        if n > 0:
            conn.execute("UPDATE forklifts SET status='retired' WHERE id=?", (forklift_id,))
        else:
            conn.execute("DELETE FROM forklifts WHERE id=?", (forklift_id,))
        conn.commit()
        return {'ok': True, 'retired_only': n > 0}
    finally:
        conn.close()

# Legacy defaults (used only if refuel_windows table is empty / disabled).
REFUEL_WINDOW_HOUR    = 11
REFUEL_REQUEST_CUTOFF = 10

# ── Refuel window CRUD ─────────────────────────────────────────────
def list_refuel_windows(active_only: bool = False) -> list:
    conn = get_db()
    try:
        q = "SELECT * FROM refuel_windows"
        if active_only: q += " WHERE active = 1"
        q += " ORDER BY start_hour, start_min, id"
        return rows_to_list(conn.execute(q).fetchall())
    finally:
        conn.close()

def upsert_refuel_window(*, id=None, label: str, start_hour: int, start_min: int = 0,
                         cutoff_hour: int = None, cutoff_min: int = 30,
                         days_of_week: str = 'mon,tue,wed,thu,fri,sat',
                         active: int = 1, notes: str = '') -> dict:
    if cutoff_hour is None:
        cutoff_hour = max(0, int(start_hour) - 1)
    conn = get_db()
    try:
        if id:
            conn.execute("""UPDATE refuel_windows SET label=?, start_hour=?, start_min=?,
                cutoff_hour=?, cutoff_min=?, days_of_week=?, active=?, notes=? WHERE id=?""",
                (label, int(start_hour), int(start_min), int(cutoff_hour), int(cutoff_min),
                 days_of_week, int(active), notes, id))
            wid = id
        else:
            cur = conn.execute("""INSERT INTO refuel_windows
                (label, start_hour, start_min, cutoff_hour, cutoff_min, days_of_week, active, notes)
                VALUES (?,?,?,?,?,?,?,?)""",
                (label, int(start_hour), int(start_min), int(cutoff_hour), int(cutoff_min),
                 days_of_week, int(active), notes))
            wid = cur.lastrowid
        conn.commit()
        return {'ok': True, 'id': wid}
    finally:
        conn.close()

def delete_refuel_window(wid: int) -> dict:
    conn = get_db()
    try:
        conn.execute("DELETE FROM refuel_windows WHERE id=?", (wid,))
        conn.commit()
        return {'ok': True}
    finally:
        conn.close()

def _next_refuel_slot(priority: str = 'NORMAL') -> str:
    """Return ISO date+time string for when this oil request should be fulfilled.
    URGENT  → ASAP (today, now)
    NORMAL  → next available refuel_window honouring cutoff, days_of_week, active.
    Falls back to the legacy 11:00 default if no windows are configured."""
    from datetime import datetime, timedelta
    now = datetime.now()
    if (priority or 'NORMAL').upper() == 'URGENT':
        return now.replace(microsecond=0).isoformat(sep=' ')
    windows = list_refuel_windows(active_only=True)
    if not windows:
        # legacy fallback
        cutoff = now.replace(hour=REFUEL_REQUEST_CUTOFF, minute=30, second=0, microsecond=0)
        target = now.replace(hour=REFUEL_WINDOW_HOUR, minute=0, second=0, microsecond=0)
        if now > cutoff: target += timedelta(days=1)
        return target.isoformat(sep=' ')
    # Look ahead up to 7 days for the next slot whose day-of-week matches and isn't past cutoff
    dow_codes = ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun']
    best = None
    for delta in range(0, 8):
        d = now + timedelta(days=delta)
        dow = dow_codes[d.weekday()]
        for w in windows:
            allowed = set(s.strip().lower() for s in (w.get('days_of_week') or '').split(','))
            if allowed and dow not in allowed:
                continue
            slot_start = d.replace(hour=int(w['start_hour']), minute=int(w['start_min']),
                                   second=0, microsecond=0)
            cutoff = d.replace(hour=int(w['cutoff_hour']), minute=int(w['cutoff_min']),
                               second=0, microsecond=0)
            # Today's slot only counts if we're still before its cutoff
            if delta == 0 and now > cutoff:
                continue
            if best is None or slot_start < best:
                best = slot_start
        if best:
            break
    if best is None:
        # nothing usable — fall back to tomorrow 11:00 default
        target = (now + timedelta(days=1)).replace(hour=REFUEL_WINDOW_HOUR, minute=0,
                                                    second=0, microsecond=0)
        return target.isoformat(sep=' ')
    return best.isoformat(sep=' ')


def create_oil_request(*, forklift_id: int, oil_type: str = 'hydraulic',
                       qty_litres: float, requested_by: str = '',
                       notes: str = '', priority: str = 'NORMAL') -> dict:
    if not forklift_id or float(qty_litres) <= 0:
        raise ValueError("forklift_id and positive qty_litres required")
    prio = (priority or 'NORMAL').upper()
    if prio not in ('NORMAL', 'URGENT'):
        prio = 'NORMAL'
    scheduled = _next_refuel_slot(prio)
    conn = get_db()
    try:
        cur = conn.execute("""
            INSERT INTO forklift_oil_requests
              (forklift_id, oil_type, qty_litres, requested_by, notes, status,
               priority, scheduled_for)
            VALUES (?,?,?,?,?, 'PENDING', ?, ?)
        """, (forklift_id, oil_type, float(qty_litres), requested_by, notes,
              prio, scheduled))
        conn.commit()
        return {'ok': True, 'id': cur.lastrowid, 'status': 'PENDING',
                'priority': prio, 'scheduled_for': scheduled}
    finally:
        conn.close()


def postpone_oil_request(req_id: int, days: int = 1, actor: str = '',
                         reason: str = '') -> dict:
    """Roll an unfulfilled request to the next refueling window (default +1 day)."""
    from datetime import datetime, timedelta
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT scheduled_for, postponed_count FROM forklift_oil_requests WHERE id=?",
            (req_id,)).fetchone()
        if not row:
            raise ValueError("Request not found")
        cur_sched = row[0]
        try:
            base = datetime.fromisoformat(cur_sched) if cur_sched else datetime.now()
        except Exception:
            base = datetime.now()
        new_sched = (base + timedelta(days=int(days or 1))).replace(
            hour=REFUEL_WINDOW_HOUR, minute=0, second=0, microsecond=0).isoformat(sep=' ')
        new_notes_suffix = f"\n[Postponed to {new_sched[:10]} by {actor}: {reason}]" if reason else \
                           f"\n[Postponed to {new_sched[:10]} by {actor}]"
        conn.execute("""UPDATE forklift_oil_requests
                        SET scheduled_for = ?,
                            postponed_count = COALESCE(postponed_count,0) + 1,
                            notes = COALESCE(notes,'') || ?
                        WHERE id = ?""",
                     (new_sched, new_notes_suffix, req_id))
        conn.commit()
        return {'ok': True, 'id': req_id, 'scheduled_for': new_sched}
    finally:
        conn.close()

def list_oil_requests(status: str = None, forklift_id: int = None,
                      priority: str = None, scheduled_date: str = None,
                      limit: int = 200) -> list:
    conn = get_db()
    try:
        q = """SELECT r.*, f.code AS forklift_code, f.name AS forklift_name,
                      f.dept AS forklift_dept, f.production_line AS forklift_line,
                      f.fuel_type AS forklift_fuel
               FROM forklift_oil_requests r
               JOIN forklifts f ON f.id = r.forklift_id
               WHERE 1=1"""
        params = []
        if status:         q += " AND r.status = ?"; params.append(status)
        if forklift_id:    q += " AND r.forklift_id = ?"; params.append(forklift_id)
        if priority:       q += " AND r.priority = ?"; params.append(priority)
        if scheduled_date: q += " AND DATE(r.scheduled_for) = ?"; params.append(scheduled_date)
        # URGENT first, then by scheduled time
        q += """ ORDER BY CASE WHEN r.priority='URGENT' THEN 0 ELSE 1 END,
                          CASE WHEN r.scheduled_for IS NULL THEN 1 ELSE 0 END,
                          r.scheduled_for ASC, r.requested_at ASC
                 LIMIT ?"""
        params.append(limit)
        return rows_to_list(conn.execute(q, params).fetchall())
    finally:
        conn.close()

def update_oil_request_status(req_id: int, status: str, fulfilled_qty: float = None,
                              actor: str = '', notes: str = '',
                              oil_material_id: int = None) -> dict:
    """Mark an oil request fulfilled/cancelled. When fulfilling and an
    oil_material_id is provided, decrement that material's current_stock by
    fulfilled_qty so warehouse oil drum inventory stays accurate."""
    if status not in ('PENDING', 'FULFILLED', 'CANCELLED'):
        raise ValueError("invalid status")
    conn = get_db()
    try:
        sets, params = ["status = ?"], [status]
        if status == 'FULFILLED':
            sets.append("fulfilled_at = datetime('now')")
            sets.append("fulfilled_by = ?"); params.append(actor)
            if fulfilled_qty is not None:
                sets.append("fulfilled_qty = ?"); params.append(float(fulfilled_qty))
            if oil_material_id:
                sets.append("oil_material_id = ?"); params.append(int(oil_material_id))
        if notes:
            sets.append("notes = ?"); params.append(notes)
        params.append(req_id)
        conn.execute(f"UPDATE forklift_oil_requests SET {', '.join(sets)} WHERE id=?", params)
        # Decrement oil drum stock on fulfilment (best-effort)
        if status == 'FULFILLED' and oil_material_id and fulfilled_qty:
            try:
                conn.execute(
                    "UPDATE materials SET current_stock = COALESCE(current_stock,0) - ? WHERE id=?",
                    (float(fulfilled_qty), int(oil_material_id)))
            except Exception:
                pass
        conn.commit()
        return {'ok': True, 'id': req_id, 'status': status}
    finally:
        conn.close()


# ════════════════════════════════════════════════════════════════
# OIL DRUM INVENTORY — materials tagged for forklift fuelling
# ════════════════════════════════════════════════════════════════
def list_oil_drum_materials() -> list:
    """Return materials usable as forklift oil (type=consumable/lubricant or name
    containing 'oil', 'hydraulic', 'engine'). Used by WH refuel modal to pick
    which drum was dispensed and decrement its stock."""
    conn = get_db()
    try:
        rows = rows_to_list(conn.execute("""
            SELECT id, code, name, type, unit, COALESCE(current_stock,0) AS current_stock,
                   COALESCE(reorder_point,0) AS reorder_point,
                   COALESCE(unit_cost, price, 0) AS unit_cost
            FROM materials
            WHERE LOWER(name) LIKE '%oil%' OR LOWER(name) LIKE '%hydraulic%'
               OR LOWER(name) LIKE '%lubric%' OR LOWER(type) = 'lubricant'
            ORDER BY name
        """).fetchall())
        return rows
    finally:
        conn.close()


# ════════════════════════════════════════════════════════════════
# SCRAP / LG BIN — per-station scrap with reason & manager review
# ════════════════════════════════════════════════════════════════
def create_scrap_entry(*, batch_id: int, dept: str, pcs_scrapped: int,
                       reason_code: str, reason_detail: str = '',
                       production_line: str = '', created_by: str = '') -> dict:
    if not batch_id or int(pcs_scrapped) <= 0:
        raise ValueError("batch_id and positive pcs_scrapped required")
    if not (reason_code or '').strip():
        raise ValueError("reason_code is required (use the standard scrap reasons)")
    conn = get_db()
    try:
        bn = conn.execute("SELECT batch_number FROM batches WHERE id=?",
                          (batch_id,)).fetchone()
        bn = bn[0] if bn else ''
        cur = conn.execute("""INSERT INTO scrap_log
            (batch_id, batch_number, dept, production_line, pcs_scrapped,
             reason_code, reason_detail, created_by)
            VALUES (?,?,?,?,?,?,?,?)""",
            (batch_id, bn, (dept or '').lower(), production_line, int(pcs_scrapped),
             reason_code, reason_detail, created_by))
        conn.commit()
        return {'ok': True, 'id': cur.lastrowid, 'batch_number': bn}
    finally:
        conn.close()

def list_scrap_entries(disposition: str = None, dept: str = None) -> list:
    conn = get_db()
    try:
        q = """SELECT s.*, m.unit, p.name AS product_name, p.sku AS product_sku
               FROM scrap_log s
               LEFT JOIN batches b ON b.id = s.batch_id
               LEFT JOIN production_orders po ON po.id = b.prod_order_id
               LEFT JOIN products p ON p.id = po.product_id
               LEFT JOIN materials m ON m.id = NULL  -- placeholder for join uniformity
               WHERE 1=1"""
        params = []
        if disposition: q += " AND s.disposition = ?"; params.append(disposition)
        if dept:        q += " AND s.dept = ?"; params.append(dept.lower())
        q += " ORDER BY s.created_at DESC LIMIT 500"
        return rows_to_list(conn.execute(q, params).fetchall())
    finally:
        conn.close()

def set_scrap_disposition(scrap_id: int, disposition: str, reviewer: str,
                          notes: str = '') -> dict:
    if disposition not in ('PENDING_REVIEW', 'REWORK', 'DOWNGRADE', 'DISPOSE', 'RECYCLE'):
        raise ValueError("invalid disposition")
    conn = get_db()
    try:
        conn.execute("""UPDATE scrap_log
            SET disposition = ?, reviewed_by = ?, reviewed_at = datetime('now'),
                review_notes = ?
            WHERE id = ?""",
            (disposition, reviewer, notes, scrap_id))
        conn.commit()
        return {'ok': True, 'id': scrap_id, 'disposition': disposition}
    finally:
        conn.close()


# ════════════════════════════════════════════════════════════════
# RETURN MATERIAL TO FC — used when FC sent the wrong qty/type
# ════════════════════════════════════════════════════════════════
def return_material_to_fc(*, material_id: int, qty: float, batch_ref: str = '',
                          reason: str = '', requested_by: str = '') -> dict:
    """Lightweight return path: creates an OUTBOUND fc_transfer_request.
    Doesn't move stock by itself — FC re-confirms on the receiving side."""
    if not material_id or float(qty) <= 0:
        raise ValueError("material_id and positive qty required")
    conn = get_db()
    try:
        mat = conn.execute("SELECT id, type FROM materials WHERE id=?", (material_id,)).fetchone()
        if not mat:
            raise ValueError("Material not found")
        rid = _new_fctr_id()
        conn.execute("""
            INSERT INTO fc_transfer_requests
              (request_id, material_id, qty_requested, notes, requested_by,
               direction, batch_ref, status)
            VALUES (?,?,?,?,?, 'outbound', ?, 'PENDING')
        """, (rid, material_id, float(qty),
              (reason or 'Return to FC') + (f' (batch {batch_ref})' if batch_ref else ''),
              requested_by, batch_ref))
        conn.commit()
        return {'ok': True, 'request_id': rid}
    finally:
        conn.close()


def get_glue_mix_station_requirements() -> dict:
    """For every active batch at laminating, compute the glue components needed
    based on its BOM glue recipe + target qty, aggregate across all batches,
    then compare to current glue_mix station stock. Returns a per-component
    shortfall so the operator can request top-ups from WH."""
    # Component label → (recipe field name, ingredient key for material_links)
    fields = [
        ('E0 Glue',          'e0_glue_kg',         'e0_glue'),
        ('Latex G312',       'latex_g312_kg',      'latex_g312'),
        ('Flour',            'flour_kg',           'flour'),
        ('Yellow Pigment',   'yellow_pigment_kg',  'yellow_pigment'),
        ('Hardener',         'hardener_kg',        'hardener'),
        ('Red Pigment',      'red_pigment_kg',     'red_pigment'),
        ('Black Pigment',    'black_pigment_kg',   'black_pigment'),
        ('Titanium dioxide', 'titanium_kg',        'titanium'),
    ]
    conn = get_db()
    try:
        batches = rows_to_list(conn.execute("""
            SELECT id, batch_number, quantity, pcs_actual, current_department
            FROM batches
            WHERE status = 'active' AND LOWER(current_department) IN ('laminating', 'fc')
        """).fetchall())
    finally:
        conn.close()

    agg = {}        # label -> {required_kg, recipes_used, batches, explicit_mat_ids}
    no_recipe = []
    for b in batches:
        try:
            info = get_batch_glue_info(b['id'])
        except Exception:
            continue
        if not info or info.get('error') or not info.get('matched'):
            if info and info.get('glue_code'):
                no_recipe.append({'batch': b['batch_number'], 'glue_code': info['glue_code']})
            continue
        recipe   = info.get('recipe') or {}
        target   = float(info.get('total_kg') or 0)
        recipe_k = float(recipe.get('total_kg') or 0)
        if target <= 0 or recipe_k <= 0:
            continue
        factor = target / recipe_k
        # Parse the explicit ingredient → material_id map (set per recipe).
        try:
            recipe_links = json.loads(recipe.get('material_links') or '{}')
        except Exception:
            recipe_links = {}
        for label, fld, ing_key in fields:
            qty = float(recipe.get(fld) or 0) * factor
            if qty <= 0: continue
            a = agg.setdefault(label, {
                'component':       label,
                'ingredient_key':  ing_key,
                'required_kg':     0.0,
                'batches':         [],
                'recipes':         set(),
                'explicit_mat_ids':set(),
            })
            a['required_kg'] += qty
            a['batches'].append({'batch_number': b['batch_number'], 'recipe': info.get('glue_code'), 'qty': round(qty,3)})
            a['recipes'].add(info.get('glue_code'))
            mid = recipe_links.get(ing_key)
            if mid: a['explicit_mat_ids'].add(int(mid))

    # Pull glue_mix station stock and match by substring
    stock_rows = get_station_stock('glue_mix')
    # Fallback pool: every material in the catalog (so a component the operator
    # has never received into station stock can still be looked up + requested).
    cn = get_db()
    try:
        all_mats = rows_to_list(cn.execute(
            "SELECT id, name, unit, current_stock AS wh_stock FROM materials "
            "WHERE COALESCE(is_active,1)=1").fetchall())
    finally:
        cn.close()

    def _match(rows, label, name_key):
        """Match by exact, then substring, then keyword. `name_key` is the dict
        key that holds the human-readable name on the row."""
        lc = label.lower()
        for s in rows:
            if (s.get(name_key) or '').lower() == lc: return s
        for s in rows:
            nm = (s.get(name_key) or '').lower()
            if nm and (nm in lc or lc in nm): return s
        keys = label.replace(' dioxide','').split()
        for kw in keys:
            kwl = kw.lower()
            for s in rows:
                if kwl in (s.get(name_key) or '').lower(): return s
        return None

    def _stock_for_mat_id(mid):
        """Return a station-stock-shaped row for an explicit material_id.
        Prefers station-stock entry if one exists; otherwise synthesises
        from the materials catalog."""
        for s in stock_rows:
            if s.get('material_id') == mid: return s
        for m in all_mats:
            if m['id'] == mid:
                return {
                    'material_id':   m['id'],
                    'material_name': m['name'],
                    'unit':          m.get('unit') or 'kg',
                    'current_qty':   0,
                    'min_qty':       0,
                    'wh_stock':      m.get('wh_stock') or 0,
                    '__no_station_stock_yet': True,
                }
        return None

    def find_stock(label, explicit_ids):
        # 0th pass: explicit recipe link wins (this is the new "Glue BOM" link).
        # If multiple recipes link the same component to different mat IDs we
        # pick the first; the per-recipe contribution is still right.
        for mid in explicit_ids:
            row = _stock_for_mat_id(mid)
            if row: return row
        # 1st pass: station-stock (has on-hand + min-qty)
        s = _match(stock_rows, label, 'material_name')
        if s: return s
        # 2nd pass: global materials catalog so we can still surface material_id
        # → operator can request from WH even before first receive.
        m = _match(all_mats, label, 'name')
        if not m: return None
        # Synthesize a station-stock-shaped row with on_hand=0 (no records yet)
        return {
            'material_id':   m['id'],
            'material_name': m['name'],
            'unit':          m.get('unit') or 'kg',
            'current_qty':   0,
            'min_qty':       0,
            'wh_stock':      m.get('wh_stock') or 0,
            '__no_station_stock_yet': True,
        }

    out = []
    for label, a in agg.items():
        s = find_stock(label, a.get('explicit_mat_ids') or set())
        on_hand = float((s or {}).get('current_qty') or 0)
        min_qty = float((s or {}).get('min_qty') or 0)
        wh_stock = float((s or {}).get('wh_stock') or 0)
        req = round(a['required_kg'], 3)
        short = max(0.0, req - on_hand)
        # LOW if covered but tight (under min_qty after consumption)
        if short > 0:
            status = 'SHORT'
        elif (on_hand - req) < min_qty:
            status = 'LOW'
        else:
            status = 'OK'
        out.append({
            'component':       label,
            'material_id':     (s or {}).get('material_id'),
            'material_name':   (s or {}).get('material_name'),
            'unit':            (s or {}).get('unit') or 'kg',
            'required_kg':     req,
            'on_hand_kg':      round(on_hand, 3),
            'min_qty':         round(min_qty, 3),
            'wh_stock':        round(wh_stock, 3),
            'shortfall_kg':    round(short, 3),
            'status':          status,
            'recipes':         sorted(list(a['recipes'])),
            'batches':         a['batches'][:10],
            # True when matched against the materials catalog only (no station-
            # stock record yet) — UI shows a hint instead of an error label.
            'no_station_stock_yet': bool((s or {}).get('__no_station_stock_yet')),
        })
    # Order: SHORT first (largest shortfall), then LOW, then OK
    rank = {'SHORT':0,'LOW':1,'OK':2}
    out.sort(key=lambda r: (rank.get(r['status'],9), -r['shortfall_kg'], r['component']))
    summary = {
        'batches_seen':       len(batches),
        'components_total':   len(out),
        'components_short':   sum(1 for r in out if r['status']=='SHORT'),
        'components_low':     sum(1 for r in out if r['status']=='LOW'),
        'components_ok':      sum(1 for r in out if r['status']=='OK'),
        'no_recipe_batches':  no_recipe,
    }
    return {'summary': summary, 'rows': out}


def get_fc_aggregate_requirements() -> dict:
    """For every active batch sitting at FC (pre-laminating), compute the
    boards + veneers FC needs to transfer to laminating to feed it.
    Returns one row per material with:
      • required (sum across all upcoming batches)
      • fc_stock (already at FC)
      • pending_in (qty of OPEN inbound FC transfer requests already raised)
      • shortfall (required - fc_stock - pending_in)
      • contributing batches (batch_number, sku, qty, priority)
    so FC can one-click create the right-sized transfer request.
    """
    conn = get_db()
    try:
        # All active batches currently at FC department
        batches = rows_to_list(conn.execute("""
            SELECT b.id, b.batch_number, b.quantity, b.pcs_actual,
                   po.id AS prod_order_id, po.priority,
                   p.id AS product_id, p.sku, p.name AS product_name,
                   spo.po_number AS sales_po_number
            FROM batches b
            JOIN production_orders po ON po.id = b.prod_order_id
            JOIN products p ON p.id = po.product_id
            LEFT JOIN purchase_orders spo ON spo.id = po.po_id
            WHERE b.status = 'active' AND LOWER(b.current_department) = 'fc'
            ORDER BY COALESCE(po.priority, 2) ASC, b.id ASC
        """).fetchall())

        # SKU id + pallet_qty lookup
        sku_cache = {}
        def _resolve_sku(sku_code):
            if sku_code in sku_cache: return sku_cache[sku_code]
            row = conn.execute("SELECT id, pallet_qty FROM skus WHERE code=?", (sku_code,)).fetchone()
            sku_cache[sku_code] = dict(row) if row else None
            return sku_cache[sku_code]

        # material_id -> aggregator
        agg = {}
        skipped_no_bom = []

        for b in batches:
            sku_row = _resolve_sku(b['sku']) if b.get('sku') else None
            if not sku_row:
                skipped_no_bom.append({'batch_number': b['batch_number'], 'reason': 'no SKU'})
                continue
            pallet_qty = float(sku_row['pallet_qty'] or 1) or 1
            pallets = float(b['quantity'] or 0)
            bom = rows_to_list(conn.execute("""
                SELECT bl.material_id, bl.qty_override, bl.usage_g_per_face,
                       m.code AS material_code, m.name AS material_name,
                       m.type AS material_type, m.unit AS uom,
                       COALESCE(m.fc_stock,0) AS fc_stock,
                       COALESCE(m.current_stock,0) AS wh_stock,
                       COALESCE(m.unit_cost, m.price, 0) AS unit_cost
                FROM bom_lines bl JOIN materials m ON m.id = bl.material_id
                WHERE bl.sku_id = ?
            """, (sku_row['id'],)).fetchall())
            if not bom:
                skipped_no_bom.append({'batch_number': b['batch_number'], 'reason': f"no BOM for {b['sku']}"})
                continue
            for line in bom:
                mtype = (line.get('material_type') or '').lower()
                # FC only transfers boards & veneers
                if 'board' not in mtype and 'veneer' not in mtype:
                    continue
                if line['usage_g_per_face'] is not None:
                    # Not expected for boards/veneers, but stay safe
                    needed = pallets * pallet_qty * float(line['usage_g_per_face']) / 1000.0
                else:
                    qty_per_pallet = float(line['qty_override'] or pallet_qty)
                    needed = pallets * qty_per_pallet
                mid = line['material_id']
                if mid not in agg:
                    agg[mid] = {
                        'material_id':    mid,
                        'material_code':  line['material_code'],
                        'material_name':  line['material_name'],
                        'material_type':  line['material_type'],
                        'uom':            line['uom'],
                        'fc_stock':       float(line['fc_stock'] or 0),
                        'wh_stock':       float(line['wh_stock'] or 0),
                        'unit_cost_thb':  float(line['unit_cost'] or 0),
                        'required':       0.0,
                        'batches':        [],
                    }
                agg[mid]['required'] += needed
                agg[mid]['batches'].append({
                    'batch_id':         b['id'],
                    'batch_number':     b['batch_number'],
                    'sku':              b['sku'],
                    'product_name':     b['product_name'],
                    'priority':         b.get('priority') or 2,
                    'pallets':          pallets,
                    'qty_needed':       round(needed, 3),
                    'sales_po_number':  b.get('sales_po_number'),
                })

        # Open inbound FC transfer requests already raised → subtract so FC doesn't double-request
        out = []
        for mid, entry in agg.items():
            row = conn.execute("""
                SELECT COALESCE(SUM(qty_requested - COALESCE(qty_fulfilled,0)),0) AS qty
                FROM fc_transfer_requests
                WHERE material_id = ? AND direction='inbound'
                  AND status IN ('PENDING','PARTIAL')
            """, (mid,)).fetchone()
            pending_in = float((row[0] if row else 0) or 0)
            req = round(entry['required'], 3)
            fc  = round(float(entry['fc_stock']), 3)
            wh  = round(float(entry['wh_stock']), 3)
            short = req - fc - pending_in
            if short > 0:
                status = 'SHORT' if pending_in == 0 else 'PARTIAL'
            elif (req - fc) > 0:
                status = 'PENDING'    # covered by open transfer
            else:
                status = 'OK'
            wh_short = max(0.0, short - wh)   # how much WH itself can't cover
            # Highest urgency (lowest priority number) among the contributing batches
            max_prio = min((b.get('priority') or 2) for b in entry['batches']) if entry['batches'] else 2
            out.append({
                **{k:v for k,v in entry.items() if k != 'batches'},
                'required':       req,
                'fc_stock':       fc,
                'pending_in':     round(pending_in, 3),
                'wh_stock':       wh,
                'shortfall':      round(max(short, 0), 3),
                'wh_shortfall':   round(wh_short, 3),
                'status':         status,
                'max_priority':   max_prio,
                'suggested_qty':  round(max(short, 0), 3),
                'batches':        entry['batches'],
            })

        order_rank = {'SHORT':0, 'PARTIAL':1, 'PENDING':2, 'OK':3}
        out.sort(key=lambda r: (order_rank.get(r['status'], 9),
                                r.get('max_priority') or 2,
                                r['material_type'], r['material_name']))

        summary = {
            'batches_at_fc':       len(batches),
            'materials_total':     len(out),
            'materials_short':     sum(1 for x in out if x['status']=='SHORT'),
            'materials_partial':   sum(1 for x in out if x['status']=='PARTIAL'),
            'materials_pending':   sum(1 for x in out if x['status']=='PENDING'),
            'materials_ok':        sum(1 for x in out if x['status']=='OK'),
            'wh_shortfall_count':  sum(1 for x in out if x['wh_shortfall'] > 0),
            'skipped':             skipped_no_bom,
        }
        return {'summary': summary, 'rows': out}
    finally:
        conn.close()


# ════════════════════════════════════════════════════════════════
# VCMX — make-to-stock substrate (plywood core + MDF face/back)
# ════════════════════════════════════════════════════════════════
def _vcmx_ensure_paired_records(conn, sku_code: str, sku_name: str,
                                dims: dict = None) -> tuple:
    """Make sure both a materials row (type='vcmx') and a products row exist for
    this SKU. The materials row gets code=sku_code + board_type='VCMX' + dims so
    it surfaces inside the FG BOM Builder base-board picker.
    Returns (material_id, product_id)."""
    dims = dims or {}
    # Narrow lookup: only consider existing VCMX rows so we never overwrite a
    # non-VCMX material that happens to share the SKU code.
    mat = conn.execute(
        "SELECT id FROM materials WHERE type='vcmx' AND (code=? OR name=?)",
        (sku_code, sku_name)).fetchone()
    if mat:
        material_id = mat[0]
        # Keep core attributes in sync (code/board_type/dims)
        conn.execute("""UPDATE materials
                        SET code=?, name=?, type='vcmx', unit='pcs',
                            board_type='VCMX',
                            thickness_mm=COALESCE(?, thickness_mm),
                            width_mm    =COALESCE(?, width_mm),
                            length_mm   =COALESCE(?, length_mm)
                        WHERE id=?""",
                     (sku_code, sku_name,
                      dims.get('thickness_mm'), dims.get('width_mm'),
                      dims.get('length_mm'), material_id))
    else:
        cur = conn.execute(
            """INSERT INTO materials
                 (code, name, type, unit, current_stock, reorder_point, unit_cost,
                  board_type, thickness_mm, width_mm, length_mm)
               VALUES (?, ?, 'vcmx', 'pcs', 0, 0, 0, 'VCMX', ?, ?, ?)""",
            (sku_code, sku_name,
             dims.get('thickness_mm'), dims.get('width_mm'), dims.get('length_mm')))
        material_id = cur.lastrowid
    prod = conn.execute("SELECT id FROM products WHERE sku=?", (sku_code,)).fetchone()
    if prod:
        product_id = prod[0]
    else:
        cur = conn.execute(
            "INSERT INTO products (name, sku, description, unit) "
            "VALUES (?, ?, 'VCMX substrate (plywood core + MDF face/back)', 'pcs')",
            (sku_name, sku_code))
        product_id = cur.lastrowid
    return material_id, product_id


def create_vcmx_bom(*, sku_code: str, sku_name: str, core_material_id: int,
                    face_material_id: int, back_material_id: int,
                    thickness_mm: float, width_mm: float, length_mm: float,
                    pcs_per_pallet: int,
                    glue_material_id: int = None, glue_qty_per_panel: float = 0,
                    labour_cost_per_panel: float = 0, notes: str = '',
                    created_by: str = '') -> dict:
    if not sku_code or not sku_name:
        raise ValueError("sku_code and sku_name required")
    if not (core_material_id and face_material_id and back_material_id):
        raise ValueError("core, face, and back material IDs are all required")
    if not (thickness_mm and width_mm and length_mm):
        raise ValueError("thickness, width and length (mm) are all required")
    if not pcs_per_pallet or int(pcs_per_pallet) <= 0:
        raise ValueError("pcs_per_pallet must be a positive integer")
    conn = get_db()
    try:
        dims = {'thickness_mm': float(thickness_mm),
                'width_mm': float(width_mm),
                'length_mm': float(length_mm)}
        material_id, _ = _vcmx_ensure_paired_records(conn, sku_code, sku_name, dims=dims)
        cur = conn.execute("""
            INSERT INTO vcmx_boms
              (sku_code, sku_name, material_id, core_material_id, face_material_id,
               back_material_id, glue_material_id, glue_qty_per_panel,
               labour_cost_per_panel, notes, created_by,
               thickness_mm, width_mm, length_mm, pcs_per_pallet)
            VALUES (?,?,?,?,?,?,?,?,?,?,?, ?,?,?,?)
        """, (sku_code, sku_name, material_id, core_material_id, face_material_id,
              back_material_id, glue_material_id,
              float(glue_qty_per_panel or 0), float(labour_cost_per_panel or 0),
              notes, created_by,
              float(thickness_mm), float(width_mm), float(length_mm),
              int(pcs_per_pallet)))
        conn.commit()
        return {'id': cur.lastrowid, 'sku_code': sku_code,
                'material_id': material_id}
    finally:
        conn.close()


def update_vcmx_bom(bom_id: int, data: dict) -> dict:
    conn = get_db()
    try:
        cur = conn.execute("SELECT * FROM vcmx_boms WHERE id=?", (bom_id,)).fetchone()
        if not cur: raise ValueError("BOM not found")
        cur = dict(cur)
        fields = ['sku_name','core_material_id','face_material_id','back_material_id',
                  'glue_material_id','glue_qty_per_panel','labour_cost_per_panel',
                  'notes','active','thickness_mm','width_mm','length_mm','pcs_per_pallet']
        sets, params = [], []
        for f in fields:
            if f in data:
                sets.append(f + '=?'); params.append(data[f])
        if sets:
            params.append(bom_id)
            conn.execute(f"UPDATE vcmx_boms SET {', '.join(sets)} WHERE id=?", params)
            conn.commit()
        # Mirror dim changes onto the paired materials row
        if any(k in data for k in ('thickness_mm','width_mm','length_mm','sku_name')):
            bom = dict(conn.execute("SELECT * FROM vcmx_boms WHERE id=?", (bom_id,)).fetchone())
            _vcmx_ensure_paired_records(conn, bom['sku_code'], bom['sku_name'],
                dims={'thickness_mm': bom.get('thickness_mm'),
                      'width_mm':     bom.get('width_mm'),
                      'length_mm':    bom.get('length_mm')})
            conn.commit()
        return {'id': bom_id, 'updated': len(sets)}
    finally:
        conn.close()


def list_vcmx_boms(active_only: bool = False) -> list:
    conn = get_db()
    try:
        q = """SELECT b.*,
                  mc.name AS core_name, mc.id AS core_id,
                  mf.name AS face_name, mf.id AS face_id,
                  mb.name AS back_name, mb.id AS back_id,
                  mg.name AS glue_name,
                  m.current_stock AS fc_stock
               FROM vcmx_boms b
               JOIN materials mc ON mc.id = b.core_material_id
               JOIN materials mf ON mf.id = b.face_material_id
               JOIN materials mb ON mb.id = b.back_material_id
               LEFT JOIN materials mg ON mg.id = b.glue_material_id
               LEFT JOIN materials m  ON m.id  = b.material_id"""
        if active_only:
            q += " WHERE b.active=1"
        q += " ORDER BY b.created_at DESC"
        return rows_to_list(conn.execute(q).fetchall())
    finally:
        conn.close()


def vcmx_check_inputs(bom_id: int, qty_panels: int) -> dict:
    """Peek at FC lot availability for a planned VCMX production qty.
    Returns {ok, shortages: [{material_id, name, required, available, shortfall, uom}]}.
    """
    conn = get_db()
    try:
        bom = conn.execute("SELECT * FROM vcmx_boms WHERE id=?", (bom_id,)).fetchone()
        if not bom: raise ValueError("BOM not found")
        bom = dict(bom)
        needs = [
            (bom['core_material_id'], 1.0),
            (bom['face_material_id'], 1.0),
            (bom['back_material_id'], 1.0),
        ]
        if bom['glue_material_id'] and bom['glue_qty_per_panel']:
            needs.append((bom['glue_material_id'], float(bom['glue_qty_per_panel'])))
        shortages = []
        for mid, per in needs:
            need = per * qty_panels
            mat = dict(conn.execute(
                "SELECT id,name,unit,fc_stock FROM materials WHERE id=?",
                (mid,)).fetchone() or {})
            # Use FC-specific stock (not total current_stock) — VCMX is built
            # at FC so inputs must physically be at the FC station.
            have = float(mat.get('fc_stock') or 0)
            if have + 1e-6 < need:
                shortages.append({
                    'material_id': mid,
                    'name': mat.get('name'),
                    'uom': mat.get('unit') or '',
                    'required': round(need, 3),
                    'available': round(have, 3),
                    'shortfall': round(need - have, 3),
                })
        return {'ok': not shortages, 'shortages': shortages}
    finally:
        conn.close()


def _next_prod_order_number(conn, prefix: str = 'PO') -> str:
    today = datemod.today().strftime("%Y%m%d")
    n = conn.execute(
        "SELECT COUNT(*) FROM production_orders WHERE prod_order_number LIKE ?",
        (f"{prefix}-{today}-%",)).fetchone()[0]
    return f"{prefix}-{today}-{n+1:03d}"


def create_vcmx_production_order(*, vcmx_bom_id: int, quantity: int,
                                 production_line: str = 'P01',
                                 priority: int = 2,
                                 planned_start: str = '', planned_end: str = '',
                                 notes: str = '', created_by: str = '') -> dict:
    if quantity <= 0:
        raise ValueError("quantity must be positive")
    # Inputs check
    chk = vcmx_check_inputs(vcmx_bom_id, quantity)
    if not chk['ok']:
        msg = "Insufficient FC stock: " + ", ".join(
            f"{s['name']} short {s['shortfall']} {s['uom']}"
            for s in chk['shortages'])
        e = ValueError(msg)
        e.shortages = chk['shortages']
        raise e
    conn = get_db()
    try:
        bom = dict(conn.execute("SELECT * FROM vcmx_boms WHERE id=?",
                                (vcmx_bom_id,)).fetchone() or {})
        if not bom: raise ValueError("BOM not found")
        # Ensure paired product exists
        material_id, product_id = _vcmx_ensure_paired_records(
            conn, bom['sku_code'], bom['sku_name'])
        # Update BOM material_id if it was missing
        if bom.get('material_id') is None:
            conn.execute("UPDATE vcmx_boms SET material_id=? WHERE id=?",
                         (material_id, vcmx_bom_id))
        num = _next_prod_order_number(conn, prefix='VCMX')
        cur = conn.execute("""
            INSERT INTO production_orders
              (prod_order_number, product_id, production_line, quantity, status,
               priority, planned_start, planned_end, notes,
               is_vcmx, vcmx_bom_id, is_make_to_stock)
            VALUES (?,?,?,?,?, ?,?,?,?, 1,?,1)
        """, (num, product_id, production_line, int(quantity), 'in_progress',
              int(priority), planned_start, planned_end, notes, vcmx_bom_id))
        order_id = cur.lastrowid
        # Auto-release: create a single batch sitting at the VCMX-Lam station
        batch_num = f"VBTH-{order_id:04d}-001"
        cur = conn.execute(
            "INSERT INTO batches (batch_number,prod_order_id,quantity,current_department,status) "
            "VALUES (?,?,?,?,?)",
            (batch_num, order_id, int(quantity), 'vcmx_lam', 'active'))
        bid = cur.lastrowid
        conn.execute(
            "INSERT INTO batch_movements (batch_id,from_department,to_department,quantity,moved_by,notes) "
            "VALUES (?,?,?,?,?,?)",
            (bid, '', 'vcmx_lam', int(quantity), created_by,
             'VCMX batch released to VCMX-Lam station'))
        conn.commit()
        return {'id': order_id, 'prod_order_number': num,
                'vcmx_bom_id': vcmx_bom_id, 'quantity': quantity,
                'batch_id': bid, 'batch_number': batch_num}
    finally:
        conn.close()


def _fifo_consume_material(conn, material_id: int, qty_needed: float,
                           reason: str = 'vcmx_lam') -> tuple:
    """FIFO-consume from material_lots, decrement both materials.current_stock
    AND materials.fc_stock (VCMX is built at FC so inputs leave the FC counter
    too — current_stock is the total across FC+WH).
    Returns (total_cost, consumed_lots[]) where consumed_lots is a list of
    {lot_id, qty, cost} for downstream traceability writes."""
    lots = conn.execute("""SELECT id, remaining_qty, unit_cost FROM material_lots
                           WHERE material_id=? AND is_active=1 AND remaining_qty>0
                           ORDER BY received_at ASC, id ASC""",
                        (material_id,)).fetchall()
    remaining = float(qty_needed)
    total_cost = 0.0
    consumed = []
    for lot in lots:
        if remaining <= 1e-9: break
        take = min(remaining, float(lot['remaining_qty']))
        cost = take * float(lot['unit_cost'] or 0)
        total_cost += cost
        new_rem = float(lot['remaining_qty']) - take
        conn.execute("UPDATE material_lots SET remaining_qty=? WHERE id=?",
                     (new_rem, lot['id']))
        consumed.append({'lot_id': lot['id'], 'qty': take, 'cost': cost})
        remaining -= take
    if remaining > 1e-6:
        raise ValueError(
            f"Material {material_id}: needed {qty_needed} but only {qty_needed-remaining:.3f} "
            f"available across FIFO lots. Refusing to silently under-consume.")
    # Decrement both total and FC counters (qty leaves the FC station)
    conn.execute(
        "UPDATE materials SET current_stock=MAX(0,current_stock-?), "
        "fc_stock=MAX(0,fc_stock-?) WHERE id=?",
        (float(qty_needed), float(qty_needed), material_id))
    return total_cost, consumed


def _vcmx_recompute_weighted_unit_cost(conn, material_id: int) -> float:
    """Weighted-average unit_cost across all active lots remaining for a VCMX
    SKU. Mirrors the result onto materials.unit_cost for read-only summary use;
    actual FIFO consumption downstream still uses each lot's own unit_cost."""
    row = conn.execute("""SELECT SUM(remaining_qty*unit_cost) AS tcost,
                                  SUM(remaining_qty)           AS tqty
                          FROM material_lots
                          WHERE material_id=? AND is_active=1 AND remaining_qty>0""",
                       (material_id,)).fetchone()
    tqty = float((row['tqty'] if row else 0) or 0)
    tcost = float((row['tcost'] if row else 0) or 0)
    weighted = (tcost / tqty) if tqty > 0 else 0.0
    conn.execute("UPDATE materials SET unit_cost=? WHERE id=?",
                 (weighted, material_id))
    return weighted


def complete_vcmx_batch(*, batch_id: int, qty_produced: int, qty_ncg: int = 0,
                        glue_actual_kg: float = None, operator: str = '',
                        notes: str = '', close_short: bool = False) -> dict:
    """Consume BOM materials FIFO for `qty_produced` panels, create a new
    material_lot at FC for the VCMX SKU with computed unit cost, and log the
    event. Supports partial completions: a batch may be completed in multiple
    events. The batch only flips to 'completed' once total qty_produced across
    all events reaches the order qty, OR when `close_short=True` is passed
    (operator explicitly closing the batch short)."""
    if qty_produced <= 0:
        raise ValueError("qty_produced must be positive")
    conn = get_db()
    try:
        batch = dict(conn.execute("SELECT * FROM batches WHERE id=?",
                                  (batch_id,)).fetchone() or {})
        if not batch: raise ValueError("Batch not found")
        if batch.get('status') == 'completed':
            raise ValueError("Batch already completed")
        po = dict(conn.execute("SELECT * FROM production_orders WHERE id=?",
                               (batch['prod_order_id'],)).fetchone() or {})
        if not po or not po.get('is_vcmx'):
            raise ValueError("Batch is not a VCMX production batch")
        bom = dict(conn.execute("SELECT * FROM vcmx_boms WHERE id=?",
                                (po['vcmx_bom_id'],)).fetchone() or {})
        if not bom: raise ValueError("VCMX BOM not found")

        # Partial-completion guard: don't allow producing more than the order qty
        already = conn.execute(
            "SELECT COALESCE(SUM(qty_produced),0) FROM vcmx_laminating_log WHERE batch_id=?",
            (batch_id,)).fetchone()[0] or 0
        remaining_to_make = int(batch['quantity']) - int(already)
        if qty_produced > remaining_to_make:
            raise ValueError(
                f"qty_produced ({qty_produced}) exceeds remaining batch qty "
                f"({remaining_to_make}). Already produced: {already}/{batch['quantity']}.")

        # Re-validate FC stock at completion (between order creation and now,
        # other consumers could have depleted FC inventory).
        need_list = [(bom['core_material_id'], 1.0 * qty_produced, 'core'),
                     (bom['face_material_id'], 1.0 * qty_produced, 'face'),
                     (bom['back_material_id'], 1.0 * qty_produced, 'back')]
        if bom.get('glue_material_id'):
            glue_qty = float(glue_actual_kg if glue_actual_kg is not None
                             else (bom.get('glue_qty_per_panel') or 0) * qty_produced)
            if glue_qty > 0:
                need_list.append((bom['glue_material_id'], glue_qty, 'glue'))
        shortages = []
        for mid, need, role in need_list:
            have = conn.execute("SELECT fc_stock FROM materials WHERE id=?",
                                (mid,)).fetchone()
            havef = float((have[0] if have else 0) or 0)
            if havef + 1e-6 < need:
                shortages.append(f"{role} {havef}/{need}")
        if shortages:
            raise ValueError(
                "FC stock insufficient at completion time: " + ", ".join(shortages))

        # Consume inputs FIFO + capture per-lot details for traceability
        total_mat_cost = 0.0
        all_consumed = []   # list of (material_id, consumed[]) for batch_material_lots
        for mid in (bom['core_material_id'], bom['face_material_id'],
                    bom['back_material_id']):
            c, consumed = _fifo_consume_material(conn, mid, qty_produced)
            total_mat_cost += c
            all_consumed.append((mid, consumed))
        if bom.get('glue_material_id'):
            glue_qty = float(glue_actual_kg if glue_actual_kg is not None
                             else (bom.get('glue_qty_per_panel') or 0) * qty_produced)
            if glue_qty > 0:
                c, consumed = _fifo_consume_material(
                    conn, bom['glue_material_id'], glue_qty)
                total_mat_cost += c
                all_consumed.append((bom['glue_material_id'], consumed))

        labour_cost = float(bom.get('labour_cost_per_panel') or 0) * qty_produced
        unit_cost = (total_mat_cost + labour_cost) / qty_produced

        # Create output lot at FC for the VCMX SKU
        material_id = bom['material_id']
        if not material_id:
            material_id, _ = _vcmx_ensure_paired_records(
                conn, bom['sku_code'], bom['sku_name'])
        seq = conn.execute(
            "SELECT COALESCE(MAX(id),0) FROM vcmx_laminating_log WHERE batch_id=?",
            (batch_id,)).fetchone()[0] or 0
        suffix = f"-{seq+1}" if already > 0 else ""
        lot_code = f"VCMX-{batch['batch_number']}{suffix}"
        cur = conn.execute("""
            INSERT INTO material_lots
              (lot_code, material_id, supplier, received_qty, remaining_qty,
               uom, unit_cost, notes)
            VALUES (?,?, 'INTERNAL-VCMX', ?, ?, 'pcs', ?, ?)
        """, (lot_code, material_id, qty_produced, qty_produced, unit_cost,
              f"VCMX from batch {batch['batch_number']} (BOM {bom['sku_code']})"))
        output_lot_id = cur.lastrowid

        # Bump both total + FC stock counters for the VCMX SKU (panels land at FC)
        conn.execute(
            "UPDATE materials SET current_stock=current_stock+?, "
            "fc_stock=fc_stock+? WHERE id=?",
            (qty_produced, qty_produced, material_id))

        # Weighted-avg unit cost across all active VCMX lots for this SKU
        _vcmx_recompute_weighted_unit_cost(conn, material_id)

        # Traceability: write batch_material_lots so the consumed input lots
        # are linked to the VCMX batch (lets us drill back from finished panels
        # through VCMX to the original plywood/MDF/glue lots).
        role_for_mid = {
            bom['core_material_id']: 'core',
            bom['face_material_id']: 'face',
            bom['back_material_id']: 'back',
        }
        if bom.get('glue_material_id'):
            role_for_mid[bom['glue_material_id']] = 'glue'
        try:
            for mid, consumed in all_consumed:
                for c in consumed:
                    if c['qty'] <= 0: continue
                    conn.execute("""
                        INSERT INTO batch_material_lots
                          (batch_id, material_id, lot_id, qty_consumed, role,
                           consumed_by, notes)
                        VALUES (?,?,?,?,?,?,?)
                    """, (batch_id, mid, c['lot_id'], c['qty'],
                          role_for_mid.get(mid, ''), operator,
                          f"VCMX-Lam consumption (BOM {bom['sku_code']})"))
        except Exception:
            # Older DBs may not have batch_material_lots; non-fatal for VCMX
            pass

        # Log VCMX completion event
        conn.execute("""
            INSERT INTO vcmx_laminating_log
              (batch_id, prod_order_id, vcmx_bom_id, qty_produced, qty_ncg,
               glue_actual_kg, material_cost, labour_cost, unit_cost,
               output_lot_id, operator, notes)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
        """, (batch_id, po['id'], bom['id'], qty_produced, int(qty_ncg or 0),
              float(glue_actual_kg or 0), total_mat_cost, labour_cost, unit_cost,
              output_lot_id, operator, notes))

        # Partial vs final-completion logic
        new_total = int(already) + int(qty_produced)
        is_final = (new_total >= int(batch['quantity'])) or close_short
        if is_final:
            conn.execute("UPDATE batches SET current_department='fc', status='completed' "
                         "WHERE id=?", (batch_id,))
            conn.execute("INSERT INTO batch_movements "
                         "(batch_id,from_department,to_department,quantity,moved_by,notes) "
                         "VALUES (?,?,?,?,?,?)",
                         (batch_id, batch.get('current_department') or '', 'fc',
                          qty_produced, operator,
                          f"VCMX-Lam final completion — {qty_produced} pcs to FC stock"
                          + (f" (closed short {new_total}/{batch['quantity']})"
                             if new_total < int(batch['quantity']) else '')))
            conn.execute("UPDATE production_orders SET status='completed', actual_end=? "
                         "WHERE id=?", (datemod.today().isoformat(), po['id']))
        else:
            # Partial: leave batch active, log movement for the partial
            conn.execute("INSERT INTO batch_movements "
                         "(batch_id,from_department,to_department,quantity,moved_by,notes) "
                         "VALUES (?,?,?,?,?,?)",
                         (batch_id, 'vcmx_lam', 'fc', qty_produced, operator,
                          f"VCMX-Lam partial completion — {qty_produced} pcs "
                          f"({new_total}/{batch['quantity']} cumulative)"))

        conn.commit()
        return {
            'batch_id': batch_id,
            'qty_produced': qty_produced,
            'qty_remaining': max(0, int(batch['quantity']) - new_total),
            'cumulative_produced': new_total,
            'is_final': bool(is_final),
            'material_cost': round(total_mat_cost, 2),
            'labour_cost':   round(labour_cost, 2),
            'unit_cost':     round(unit_cost, 4),
            'output_lot_id': output_lot_id,
            'output_lot_code': lot_code,
            'vcmx_material_id': material_id,
        }
    finally:
        conn.close()


def list_vcmx_batch_events(batch_id: int) -> list:
    """Return all VCMX completion log events for a batch (for partial-completion UI)."""
    conn = get_db()
    try:
        return rows_to_list(conn.execute(
            "SELECT * FROM vcmx_laminating_log WHERE batch_id=? ORDER BY id ASC",
            (batch_id,)).fetchall())
    finally:
        conn.close()


def list_vcmx_batches(status: str = None) -> list:
    """Open VCMX batches — those for VCMX production orders that haven't been
    completed yet (i.e. still active, not yet logged in vcmx_laminating_log)."""
    conn = get_db()
    try:
        q = """SELECT b.*, po.prod_order_number, po.quantity AS order_qty,
                  po.priority, bom.sku_code, bom.sku_name, bom.id AS bom_id,
                  bom.glue_qty_per_panel,
                  (SELECT COUNT(*) FROM vcmx_laminating_log l WHERE l.batch_id=b.id) AS log_count
               FROM batches b
               JOIN production_orders po ON po.id = b.prod_order_id
               JOIN vcmx_boms bom ON bom.id = po.vcmx_bom_id
               WHERE po.is_vcmx=1"""
        if status == 'open':
            q += " AND b.status='active'"
        elif status == 'completed':
            q += " AND b.status='completed'"
        q += " ORDER BY po.priority ASC, b.created_at DESC LIMIT 500"
        return rows_to_list(conn.execute(q).fetchall())
    finally:
        conn.close()


def auto_generate_purchase_requests_for_po(po_id: int, requested_by: str = '') -> dict:
    """Scan a sales PO's materials needs vs current stock; create PRs for any shortfall."""
    conn = get_db()
    try:
        po = conn.execute("SELECT po_number, delivery_date FROM purchase_orders WHERE id=?", (po_id,)).fetchone()
        if not po:
            return {"error": "PO not found"}
        po = dict(po)
        rows = rows_to_list(conn.execute("""
            SELECT m.id AS material_id, m.code AS material_code, m.name AS material_name,
                   m.type AS material_type, m.unit AS uom,
                   COALESCE(m.fc_stock, 0) + COALESCE(m.current_stock, 0) AS on_hand,
                   SUM(COALESCE(bl.qty_override, bl.usage_g_per_face, 0) * COALESCE(pol.quantity, 0)) AS required
            FROM po_lines pol
            JOIN products p ON p.id = pol.product_id
            JOIN skus s     ON s.code = p.sku
            JOIN bom_lines bl ON bl.sku_id = s.id
            JOIN materials m  ON m.id = bl.material_id
            WHERE pol.po_id = ?
            GROUP BY m.id
        """, (po_id,)).fetchall())
    finally:
        conn.close()
    created = []
    for r in rows:
        need = float(r.get('required') or 0)
        have = float(r.get('on_hand') or 0)
        short = need - have
        if short <= 0:
            continue
        try:
            req_type = 'CONSUMABLE' if (r.get('material_type') or '') in ('consumable',) else 'RAW_MATERIAL'
            res = create_purchase_request(
                request_type=req_type, material_id=r['material_id'],
                qty_requested=round(short, 3), uom=r.get('uom') or '',
                source_po_id=po_id, priority=2,
                needed_by=po.get('delivery_date'),
                notes=f"Auto-generated from sales PO {po['po_number']} (need {need}, have {have})",
                requested_by=requested_by)
            created.append({**res, 'material': r['material_name'], 'short': round(short, 3)})
        except Exception as e:
            created.append({'error': str(e), 'material': r.get('material_name')})
    return {"po_number": po['po_number'], "created": created, "count": len([c for c in created if 'id' in c])}


# ════════════════════════════════════════════════════════════════
# MATERIAL LOTS (FIFO) + DOCUMENTS
# ════════════════════════════════════════════════════════════════
def create_material_lot(*, material_id: int, lot_code: str, received_qty: float,
                        supplier: str = '', supplier_lot_ref: str = '', uom: str = '',
                        unit_cost: float = 0, expiry_date=None, purchase_request_id=None,
                        notes: str = '') -> dict:
    if not material_id or not lot_code or float(received_qty) <= 0:
        raise ValueError("material_id, lot_code and positive received_qty required")
    conn = get_db()
    try:
        cur = conn.execute("""
            INSERT INTO material_lots
            (lot_code, material_id, supplier, supplier_lot_ref, received_qty, remaining_qty,
             uom, unit_cost, expiry_date, purchase_request_id, notes)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)
        """, (lot_code, material_id, supplier, supplier_lot_ref, float(received_qty),
              float(received_qty), uom, float(unit_cost or 0), expiry_date,
              purchase_request_id, notes))
        lot_id = cur.lastrowid
        # bump material stock if column exists
        try:
            conn.execute("UPDATE materials SET current_stock = COALESCE(current_stock,0) + ? WHERE id=?",
                         (float(received_qty), material_id))
        except Exception:
            pass
        # Propagate any supplier-PO documents from the source PR onto this lot
        if purchase_request_id:
            _attach_pr_docs_to_lot(conn, lot_id, int(purchase_request_id))
            # Auto-mark the PR as RECEIVED if its full qty has been delivered
            try:
                received_total = conn.execute(
                    "SELECT COALESCE(SUM(received_qty),0) FROM material_lots WHERE purchase_request_id=?",
                    (int(purchase_request_id),)).fetchone()[0] or 0
                pr = conn.execute("SELECT qty_requested,status FROM purchase_requests WHERE id=?",
                                  (int(purchase_request_id),)).fetchone()
                if pr:
                    req = float(pr['qty_requested'] or 0)
                    got = float(received_total)
                    if req > 0:
                        if got > req + 1e-6 and pr['status'] != 'OVER_RECEIVED':
                            conn.execute("""UPDATE purchase_requests
                                SET status='OVER_RECEIVED', received_at=datetime('now'),
                                    notes = COALESCE(notes,'') ||
                                            printf(' [OVER_RECEIVED by %.2f units]', ?)
                                WHERE id=?""", (got - req, int(purchase_request_id)))
                        elif got >= req - 1e-6 and pr['status'] not in ('RECEIVED','OVER_RECEIVED'):
                            conn.execute("""UPDATE purchase_requests
                                SET status='RECEIVED', received_at=datetime('now') WHERE id=?""",
                                (int(purchase_request_id),))
            except Exception:
                pass
        conn.commit()
        return {"id": lot_id, "lot_code": lot_code}
    finally:
        conn.close()

def list_material_lots(material_id=None, only_active=True) -> list:
    conn = get_db()
    q = """SELECT ml.*, m.code AS material_code, m.name AS material_name, m.type AS material_type,
                  (SELECT COUNT(*) FROM material_documents d WHERE d.lot_id = ml.id) AS doc_count
           FROM material_lots ml JOIN materials m ON m.id = ml.material_id WHERE 1=1"""
    params = []
    if material_id:
        q += " AND ml.material_id = ?"; params.append(material_id)
    if only_active:
        q += " AND ml.is_active = 1"
    q += " ORDER BY ml.material_id, ml.received_at ASC"
    rows = rows_to_list(conn.execute(q, params).fetchall())
    conn.close()
    return rows

def fifo_consume_lots(material_id: int, qty: float, batch_id: int = None,
                      role: str = '', consumed_by: str = '', notes: str = '') -> dict:
    """Consume `qty` from oldest lots first (FIFO). If batch_id, record traceability."""
    if float(qty) <= 0:
        return {"consumed": 0, "lots": []}
    conn = get_db()
    try:
        lots = conn.execute("""
            SELECT id, lot_code, remaining_qty FROM material_lots
            WHERE material_id=? AND is_active=1 AND remaining_qty > 0
            ORDER BY received_at ASC, id ASC
        """, (material_id,)).fetchall()
        remaining = float(qty)
        applied = []
        for lot in lots:
            if remaining <= 0: break
            take = min(remaining, float(lot['remaining_qty']))
            new_rem = float(lot['remaining_qty']) - take
            conn.execute("UPDATE material_lots SET remaining_qty=? WHERE id=?", (new_rem, lot['id']))
            if batch_id:
                conn.execute("""INSERT INTO batch_material_lots
                    (batch_id, material_id, lot_id, qty_consumed, role, consumed_by, notes)
                    VALUES (?,?,?,?,?,?,?)""",
                    (batch_id, material_id, lot['id'], take, role, consumed_by, notes))
            applied.append({"lot_id": lot['id'], "lot_code": lot['lot_code'], "qty": take})
            remaining -= take
        # Bump material stock down
        try:
            conn.execute("UPDATE materials SET current_stock = COALESCE(current_stock,0) - ? WHERE id=?",
                         (float(qty) - remaining, material_id))
        except Exception:
            pass
        conn.commit()
        return {"consumed": float(qty) - remaining, "short": remaining, "lots": applied}
    finally:
        conn.close()


# Document storage helpers (file I/O handled by the API layer)
try:
    from config import DOCS_DIR
except ImportError:
    DOCS_DIR = os.path.join(os.path.dirname(__file__), '..', 'docs_storage')

def register_material_document(*, material_id: int, lot_id, doc_type: str, filename: str,
                               stored_path: str, file_size: int = 0,
                               content_type: str = 'application/pdf',
                               uploaded_by: str = '', notes: str = '',
                               purchase_request_id=None) -> dict:
    conn = get_db()
    try:
        cur = conn.execute("""
            INSERT INTO material_documents
            (material_id, lot_id, doc_type, filename, stored_path, file_size,
             content_type, uploaded_by, notes, purchase_request_id)
            VALUES (?,?,?,?,?,?,?,?,?,?)
        """, (material_id, lot_id, doc_type, filename, stored_path, int(file_size or 0),
              content_type, uploaded_by, notes, purchase_request_id))
        conn.commit()
        return {"id": cur.lastrowid}
    finally:
        conn.close()


def _attach_pr_docs_to_lot(conn, lot_id: int, purchase_request_id: int):
    """Copy every PR-scoped supplier doc (PO, COA, etc.) onto a freshly-received
    lot so the Traceability report finds them under the lot. Picks up docs
    referenced two ways:
      • material_documents.purchase_request_id = this PR (primary owner)
      • pr_document_links — shared documents covering several PRs at once
    Deduplicates so multiple links to the same source doc don't create copies."""
    if not purchase_request_id or not lot_id:
        return
    rows = conn.execute("""
        SELECT id, material_id, doc_type, filename, stored_path, file_size,
               content_type, uploaded_by, notes
        FROM material_documents
        WHERE lot_id IS NULL AND (
            purchase_request_id = ?
            OR id IN (SELECT document_id FROM pr_document_links WHERE pr_id = ?)
        )
    """, (purchase_request_id, purchase_request_id)).fetchall()
    seen = set()
    for d in rows:
        d = dict(d)
        if d['stored_path'] in seen:
            continue
        seen.add(d['stored_path'])
        conn.execute("""
            INSERT INTO material_documents
            (material_id, lot_id, doc_type, filename, stored_path, file_size,
             content_type, uploaded_by, notes, purchase_request_id)
            VALUES (?,?,?,?,?,?,?,?,?,?)
        """, (d['material_id'], lot_id, d['doc_type'], d['filename'],
              d['stored_path'], d['file_size'], d['content_type'],
              d['uploaded_by'], f"(auto-attached from PR #{purchase_request_id}) "+(d['notes'] or ''),
              purchase_request_id))


def link_document_to_prs(document_id: int, pr_ids: list) -> dict:
    """Link an existing document to a set of PR ids (idempotent)."""
    if not document_id or not pr_ids:
        return {'linked': 0}
    conn = get_db()
    try:
        n = 0
        for pr_id in pr_ids:
            try:
                conn.execute(
                    "INSERT OR IGNORE INTO pr_document_links (pr_id, document_id) VALUES (?, ?)",
                    (int(pr_id), int(document_id)))
                n += 1
            except Exception:
                pass
        conn.commit()
        return {'linked': n, 'document_id': document_id}
    finally:
        conn.close()

def list_material_documents(material_id=None, lot_id=None) -> list:
    conn = get_db()
    q = """SELECT d.*, m.code AS material_code, m.name AS material_name,
                  ml.lot_code AS lot_code
           FROM material_documents d JOIN materials m ON m.id = d.material_id
           LEFT JOIN material_lots ml ON ml.id = d.lot_id WHERE 1=1"""
    params = []
    if material_id:
        q += " AND d.material_id = ?"; params.append(material_id)
    if lot_id:
        q += " AND d.lot_id = ?"; params.append(lot_id)
    q += " ORDER BY d.uploaded_at DESC LIMIT 1000"
    rows = rows_to_list(conn.execute(q, params).fetchall())
    conn.close()
    return rows

def get_material_document(doc_id: int) -> dict:
    conn = get_db()
    row = conn.execute("SELECT * FROM material_documents WHERE id=?", (doc_id,)).fetchone()
    conn.close()
    return dict(row) if row else None

def delete_material_document(doc_id: int) -> dict:
    conn = get_db()
    try:
        row = conn.execute("SELECT stored_path FROM material_documents WHERE id=?", (doc_id,)).fetchone()
        conn.execute("DELETE FROM material_documents WHERE id=?", (doc_id,))
        conn.commit()
        return {"ok": True, "stored_path": row['stored_path'] if row else None}
    finally:
        conn.close()


# ════════════════════════════════════════════════════════════════
# TRACEABILITY REPORT — per sales PO
# ════════════════════════════════════════════════════════════════
def get_po_document_trace(po_id: int) -> dict:
    """Document-centric traceability for a sales PO.

    Resolves the PO → its production orders + batches → every BOARD, VENEER and
    GLUE *material* that fed it, and pulls all PDFs (`material_documents`)
    attached to those materials (material-level certs + any lot-level docs).

    Sources of the material links (these are how the factory actually records
    them — not the sparsely-populated batch_material_lots ledger):
      • Veneers — `prod_order_veneer_alloc` (FC grade-mix release, face+back),
        with `production_orders.confirmed_face/back_veneer_id` as a fallback.
      • Boards  — the SKU's BOM base-board line (`bom_lines` seq 1).
      • Glue    — `glue_mix_log.actual_components` (what the glue-mix station
        actually consumed), falling back to the recipe's `material_links`.

    Returns {purchase_order, production_orders[], sections{boards,veneers,glue},
    doc_count}. Each section item: {material_id, material_code, material_name,
    material_type, role, qty, qty_uom, source, documents[]}.
    """
    import json as _json
    conn = get_db()
    try:
        po = conn.execute("SELECT * FROM purchase_orders WHERE id=?", (po_id,)).fetchone()
        if not po:
            return {"error": "PO not found"}
        po = dict(po)

        prod_orders = rows_to_list(conn.execute("""
            SELECT po2.id, po2.prod_order_number, po2.quantity,
                   po2.confirmed_face_veneer_id, po2.confirmed_back_veneer_id,
                   p.sku AS product_sku, p.name AS product_name
            FROM production_orders po2
            JOIN products p ON p.id = po2.product_id
            WHERE po2.po_id = ?
            ORDER BY po2.id
        """, (po_id,)).fetchall())
        po_ids = [r['id'] for r in prod_orders]

        # Glue/station logs reference a batch by its batch_number STRING
        # (see _STATION_LOG_TABLES), not the integer batches.id — collect both.
        batch_numbers = []
        if po_ids:
            qmarks = ",".join("?" * len(po_ids))
            batch_numbers = [r['batch_number'] for r in conn.execute(
                f"SELECT batch_number FROM batches WHERE prod_order_id IN ({qmarks}) AND batch_number IS NOT NULL",
                po_ids
            ).fetchall()]

        # Accumulators keyed by material_id within each section.
        boards, veneers, glue = {}, {}, {}

        def _docs_for(material_id):
            # Traceability cares about QUALITY/cert documents (COA, MSDS,
            # SUPPLIER_CERT, INSPECTION, OTHER…) — NOT purchasing paperwork.
            # The purchasing flow auto-attaches a SUPPLIER_PO/PO doc to a
            # material on every PR, which floods the report with files the
            # user never uploaded; exclude those. De-dupe identical files
            # (same stored_path is registered once per PR) and flag whether
            # the file is actually present on disk so the UI never offers a
            # broken download link.
            rows = conn.execute("""
                SELECT d.id, d.doc_type, d.filename, d.file_size, d.content_type,
                       d.uploaded_at, d.uploaded_by, d.stored_path, ml.lot_code AS lot_code
                FROM material_documents d
                LEFT JOIN material_lots ml ON ml.id = d.lot_id
                WHERE d.material_id = ?
                  AND UPPER(COALESCE(d.doc_type,'')) NOT IN ('SUPPLIER_PO','PO')
                ORDER BY d.uploaded_at DESC
            """, (material_id,)).fetchall()
            out, seen = [], set()
            for r in rows:
                r = dict(r)
                sp = r.pop('stored_path', None)
                if sp in seen:
                    continue
                seen.add(sp)
                r['available'] = bool(sp and os.path.exists(os.path.join(DOCS_DIR, sp)))
                out.append(r)
            return out

        def _add(bucket, material_id, role, qty, uom, source):
            if not material_id:
                return
            ent = bucket.get(material_id)
            if not ent:
                m = conn.execute("SELECT code, name, type FROM materials WHERE id=?",
                                 (material_id,)).fetchone()
                if not m:
                    return
                ent = bucket[material_id] = {
                    "material_id": material_id, "material_code": m['code'],
                    "material_name": m['name'], "material_type": m['type'],
                    "role": role, "qty": 0.0, "qty_uom": uom,
                    "sources": set(), "documents": _docs_for(material_id),
                }
            ent['qty'] += float(qty or 0)
            ent['sources'].add(source)
            if role and role not in (ent['role'] or '').split(', '):
                ent['role'] = (ent['role'] + ', ' + role) if ent['role'] else role

        # ── Boards: base-board BOM line (seq 1) per distinct product SKU ──
        seen_sku = set()
        for r in prod_orders:
            sku_code = r['product_sku']
            if not sku_code or sku_code in seen_sku:
                continue
            seen_sku.add(sku_code)
            sk = conn.execute("SELECT id, pallet_qty FROM skus WHERE code=?", (sku_code,)).fetchone()
            if not sk:
                continue
            board_rows = conn.execute("""
                SELECT bl.material_id, bl.qty_override
                FROM bom_lines bl WHERE bl.sku_id=? AND bl.seq=1 AND bl.material_id IS NOT NULL
            """, (sk['id'],)).fetchall()
            for b in board_rows:
                _add(boards, b['material_id'], 'base_board', 0, 'sheets', 'BOM')

        # ── Veneers: FC grade-mix allocation (face + back) ──
        if po_ids:
            qmarks = ",".join("?" * len(po_ids))
            alloc = conn.execute(f"""
                SELECT material_id, side, qty_allocated
                FROM prod_order_veneer_alloc WHERE prod_order_id IN ({qmarks})
            """, po_ids).fetchall()
            for a in alloc:
                _add(veneers, a['material_id'], a['side'], a['qty_allocated'], 'sheets', 'FC release')
        # Fallback: confirmed primary veneer ids when no alloc rows exist
        if not veneers:
            for r in prod_orders:
                _add(veneers, r['confirmed_face_veneer_id'], 'face', 0, 'sheets', 'FC confirmed')
                _add(veneers, r['confirmed_back_veneer_id'], 'back', 0, 'sheets', 'FC confirmed')

        def _add_recipe_ingredients(recipe_id, source, qty_hint=0):
            """material_links is a JSON object {ingredient_name: material_id} —
            the material ids are the VALUES."""
            if not recipe_id:
                return
            rr = conn.execute("SELECT material_links FROM glue_recipes WHERE id=?",
                              (recipe_id,)).fetchone()
            if not (rr and rr['material_links']):
                return
            try:
                links = _json.loads(rr['material_links']) or {}
            except Exception:
                return
            mids = links.values() if isinstance(links, dict) else links
            for mid in mids:
                try:
                    _add(glue, int(mid), 'glue ingredient', 0, 'kg', source)
                except (TypeError, ValueError):
                    pass

        # ── Glue: what the glue-mix station actually consumed for these batches ──
        # Match via the glue_mix_batches link table (captures shared mixes that
        # span multiple POs) OR the legacy direct batch_id on glue_mix_log.
        if batch_numbers:
            qmarks = ",".join("?" * len(batch_numbers))
            mixes = conn.execute(f"""
                SELECT DISTINCT g.mix_id, g.actual_components, g.recipe_id,
                       g.recipe_code, g.qty_kg
                FROM glue_mix_log g
                WHERE g.batch_id IN ({qmarks})
                   OR g.mix_id IN (
                        SELECT mix_id FROM glue_mix_batches
                        WHERE batch_number IN ({qmarks}))
            """, batch_numbers + batch_numbers).fetchall()
            for mx in mixes:
                comps = []
                if mx['actual_components']:
                    try:
                        comps = _json.loads(mx['actual_components']) or []
                    except Exception:
                        comps = []
                if comps:
                    for c in comps:
                        _add(glue, c.get('material_id'), 'glue ingredient',
                             c.get('kg'), 'kg', 'glue mix')
                else:
                    _add_recipe_ingredients(mx['recipe_id'], 'glue mix (recipe)')

        # Fallback: if no station glue mix was logged yet, surface the glue
        # recipe ingredients the BOM specifies (seq 4/5) so their certs/MSDS
        # still travel with the PO.
        if not glue:
            for sku_code in seen_sku:
                sk = conn.execute("SELECT id FROM skus WHERE code=?", (sku_code,)).fetchone()
                if not sk:
                    continue
                for gl in conn.execute("""
                    SELECT glue_recipe_id FROM bom_lines
                    WHERE sku_id=? AND seq IN (4,5) AND glue_recipe_id IS NOT NULL
                """, (sk['id'],)).fetchall():
                    _add_recipe_ingredients(gl['glue_recipe_id'], 'BOM recipe')

        def _finalise(bucket):
            out = []
            for ent in bucket.values():
                ent['sources'] = ", ".join(sorted(ent['sources']))
                ent['qty'] = round(ent['qty'], 3)
                docs = ent['documents']
                # doc_count = downloadable PDFs; missing_count = recorded but
                # the file isn't present on this server.
                ent['doc_count'] = sum(1 for d in docs if d.get('available'))
                ent['missing_count'] = sum(1 for d in docs if not d.get('available'))
                out.append(ent)
            out.sort(key=lambda e: (e['material_code'] or ''))
            return out

        sections = {
            "boards":  _finalise(boards),
            "veneers": _finalise(veneers),
            "glue":    _finalise(glue),
        }
        doc_count     = sum(it['doc_count']     for sec in sections.values() for it in sec)
        missing_count = sum(it['missing_count'] for sec in sections.values() for it in sec)
        return {
            "purchase_order": po,
            "production_orders": prod_orders,
            "sections": sections,
            "doc_count": doc_count,
            "missing_count": missing_count,
        }
    finally:
        conn.close()


def get_po_document_trace_files(po_id: int) -> list:
    """Flatten a document trace into a de-duplicated list of files for ZIP export.
    Each entry: {section, material_code, material_name, doc_type, filename,
    stored_path, file_size, document_id}. De-dupes by document id (a material
    cert shared across sections is bundled once)."""
    trace = get_po_document_trace(po_id)
    if 'error' in trace:
        return []
    conn = get_db()
    try:
        seen = set()
        files = []
        for section, items in trace['sections'].items():
            for it in items:
                for d in it['documents']:
                    if not d.get('available'):
                        continue  # file not on disk — nothing to bundle
                    did = d['id']
                    if did in seen:
                        continue
                    seen.add(did)
                    row = conn.execute(
                        "SELECT stored_path FROM material_documents WHERE id=?",
                        (did,)).fetchone()
                    if not row:
                        continue
                    files.append({
                        "section": section,
                        "material_code": it['material_code'],
                        "material_name": it['material_name'],
                        "doc_type": d.get('doc_type') or 'OTHER',
                        "filename": d.get('filename') or f"doc_{did}.pdf",
                        "stored_path": row['stored_path'],
                        "file_size": d.get('file_size') or 0,
                        "document_id": did,
                    })
        return files
    finally:
        conn.close()


def get_po_traceability(po_id: int) -> dict:
    conn = get_db()
    try:
        po = conn.execute("SELECT * FROM purchase_orders WHERE id=?", (po_id,)).fetchone()
        if not po:
            return {"error": "PO not found"}
        po = dict(po)
        # Batches tied to this PO via production_orders (column is `po_id`, not `purchase_order_id`)
        batches = rows_to_list(conn.execute("""
            SELECT b.id, b.batch_number, b.quantity, b.pcs_actual,
                   p.sku AS product_sku, p.name AS product_name,
                   po2.id AS prod_order_id
            FROM batches b
            JOIN production_orders po2 ON po2.id = b.prod_order_id
            JOIN products p ON p.id = po2.product_id
            WHERE po2.po_id = ?
            ORDER BY b.id
        """, (po_id,)).fetchall())
        # For each batch, fetch consumed lots + documents
        for b in batches:
            lots = rows_to_list(conn.execute("""
                SELECT bml.qty_consumed, bml.role, bml.consumed_at, bml.consumed_by,
                       ml.id AS lot_id, ml.lot_code, ml.supplier, ml.supplier_lot_ref,
                       ml.received_at, ml.unit_cost, ml.expiry_date,
                       m.id AS material_id, m.code AS material_code, m.name AS material_name,
                       m.type AS material_type
                FROM batch_material_lots bml
                JOIN material_lots ml ON ml.id = bml.lot_id
                JOIN materials m ON m.id = bml.material_id
                WHERE bml.batch_id = ?
                ORDER BY m.type, m.name, bml.consumed_at
            """, (b['id'],)).fetchall())
            for lot in lots:
                lot['documents'] = rows_to_list(conn.execute("""
                    SELECT id, doc_type, filename, file_size, uploaded_at, uploaded_by
                    FROM material_documents WHERE lot_id = ?
                    ORDER BY uploaded_at DESC
                """, (lot['lot_id'],)).fetchall())
            b['lots_consumed'] = lots
        return {"purchase_order": po, "batches": batches}
    finally:
        conn.close()


def get_batch_glue_info(batch_id: int) -> dict:
    """Resolve a batch to its BOM glue line: returns code, total qty needed, recipe match."""
    conn = get_db()
    # Get batch with linked product/sku
    b = conn.execute("""SELECT b.id,b.quantity,b.batch_number,p.sku AS product_sku
                        FROM batches b JOIN production_orders po ON po.id=b.prod_order_id
                        JOIN products p ON p.id=po.product_id WHERE b.id=?""", (batch_id,)).fetchone()
    if not b:
        conn.close(); return {"error": "Batch not found"}
    b = dict(b)
    sku = conn.execute("SELECT id,pallet_qty FROM skus WHERE code=?", (b['product_sku'],)).fetchone()
    if not sku:
        conn.close(); return {"error": "SKU not found", "product_sku": b['product_sku']}
    sku = dict(sku)
    pallet_qty = float(sku['pallet_qty'] or 1) or 1
    qty = float(b['quantity'] or 0)
    # Find glue line in BOM via the new glue_recipe_id column
    glue_lines = rows_to_list(conn.execute("""
        SELECT bl.usage_g_per_face, bl.qty_override, bl.notes,
               gr.id AS recipe_id, gr.recipe_code, gr.name AS recipe_name
        FROM bom_lines bl
        JOIN glue_recipes gr ON gr.id = bl.glue_recipe_id
        WHERE bl.sku_id=? AND bl.glue_recipe_id IS NOT NULL
    """, (sku['id'],)).fetchall())
    if not glue_lines:
        conn.close(); return {"error": "No glue line in BOM", "product_sku": b['product_sku']}
    g = glue_lines[0]
    usage_g = float(g.get('usage_g_per_face') or 0)
    total_kg = round(usage_g / 1000.0 * qty * pallet_qty, 4)
    # Recipe is already known via the join
    recipe_row = conn.execute("SELECT * FROM glue_recipes WHERE id=?",
                              (g['recipe_id'],)).fetchone()
    recipe = row_to_dict(recipe_row) if recipe_row else None
    conn.close()
    return {
        "batch_number": b['batch_number'],
        "batch_quantity": qty, "pallet_qty": pallet_qty,
        "glue_code": g.get('recipe_code'),
        "glue_name": g.get('recipe_name'),
        "usage_g_per_face": usage_g,
        "total_kg": total_kg,
        "bom_notes": g.get('notes') or '',
        "recipe": recipe,
        "matched": recipe is not None,
    }

def log_glue_mix_with_stock(data: dict) -> dict:
    """Log glue mix, capture actual per-ingredient kg + cost, and deduct each
    component from glue_mix station stock.

    Per-ingredient `qty_kg` arrives from the operator (may diverge from the
    recipe to account for humidity / temperature). Cost = qty_kg × materials.price
    at the moment of logging (snapshotted into glue_mix_log so retroactive
    catalog price changes don't rewrite history).
    """
    import json as _json
    conn = get_db()
    conn.execute("PRAGMA foreign_keys = OFF")   # legacy FK on prod_batch
    mid = _new_log_id("MIX")

    components = data.get('components') or []
    # Snapshot ingredient prices + compute cost
    actual_components = []
    total_kg = 0.0
    total_cost = 0.0
    for c in components:
        mat_id = c.get('material_id')
        qty = float(c.get('qty_kg') or 0)
        if qty <= 0: continue
        price = 0.0
        if mat_id:
            row = conn.execute("SELECT price FROM materials WHERE id=?", (int(mat_id),)).fetchone()
            if row: price = float(row[0] or 0)
        cost = qty * price
        total_kg   += qty
        total_cost += cost
        actual_components.append({
            "material_id": int(mat_id) if mat_id else None,
            "name":        c.get('name'),
            "kg":          round(qty, 4),
            "price":       round(price, 4),
            "cost":        round(cost, 4),
        })
    cost_per_kg = (total_cost / total_kg) if total_kg > 0 else 0

    # Resolve recipe_id from recipe_code if provided (so reports can group cleanly)
    recipe_id = None
    if data.get('recipe_code'):
        row = conn.execute("SELECT id FROM glue_recipes WHERE recipe_code=?",
                           (data['recipe_code'],)).fetchone()
        if row: recipe_id = row[0]

    conn.execute(
        """INSERT INTO glue_mix_log
            (mix_id, batch_id, recipe_code, qty_kg, operator_id, operator_name,
             mix_time_min, notes, recipe_id, actual_total_kg, actual_total_cost,
             actual_cost_per_kg, actual_components)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (mid, data['batch_id'], data.get('recipe_code'), data['qty_kg'],
         data.get('operator_id'), data.get('operator_name',''),
         data.get('mix_time_min'), data.get('notes'),
         recipe_id, round(total_kg, 4), round(total_cost, 4),
         round(cost_per_kg, 4), _json.dumps(actual_components)))

    # Link this mix to EVERY batch it served (shared mixes span multiple POs).
    # Falls back to the single primary batch_id when no list is supplied.
    _bns = data.get('batch_numbers') or ([data['batch_id']] if data.get('batch_id') else [])
    for _bn in _bns:
        _bn = str(_bn).strip()
        if _bn:
            conn.execute(
                "INSERT OR IGNORE INTO glue_mix_batches (mix_id, batch_number) VALUES (?,?)",
                (mid, _bn))
    conn.commit(); conn.close()

    # Deduct components from station_stock (separate path so a stock-write
    # failure doesn't lose the cost snapshot above).
    deductions = []
    skipped = []
    for c in actual_components:
        mat_id = c.get('material_id'); qty = c.get('kg') or 0
        if not mat_id or qty <= 0:
            skipped.append({"name": c.get('name'), "reason": "no material mapped"})
            continue
        try:
            log_station_stock_movement({
                "department": "glue_mix", "line_id": "",
                "material_id": int(mat_id), "qty_change": qty,
                "movement_type": "BATCH_USE",
                "batch_ref": data['batch_id'], "reference": mid,
                "notes": f"Glue mix {mid} — {c.get('name','component')}",
                "created_by": data.get('operator_name','') or 'glue_mix',
            })
            deductions.append({"material_id": int(mat_id), "name": c.get('name'),
                               "qty": qty, "cost": c.get('cost')})
        except Exception as e:
            skipped.append({"name": c.get('name'), "reason": str(e)})
    return {
        "mix_id": mid,
        "actual_total_kg":    round(total_kg, 4),
        "actual_total_cost":  round(total_cost, 2),
        "actual_cost_per_kg": round(cost_per_kg, 4),
        "deductions": deductions, "skipped": skipped,
    }

def log_glue_mix(data):
    conn = get_db()
    try:
        conn.execute("PRAGMA foreign_keys = OFF")
        mid = _new_log_id("MIX")
        conn.execute(
            """INSERT INTO glue_mix_log (mix_id,batch_id,recipe_code,qty_kg,operator_id,operator_name,mix_time_min,notes)
               VALUES (?,?,?,?,?,?,?,?)""",
            (mid,data['batch_id'],data['recipe_code'],data['qty_kg'],
             data.get('operator_id'),data.get('operator_name',''),
             data.get('mix_time_min'),data.get('notes')))
        # Link to every batch served (defaults to the single primary batch)
        for _bn in (data.get('batch_numbers') or ([data['batch_id']] if data.get('batch_id') else [])):
            _bn = str(_bn).strip()
            if _bn:
                conn.execute(
                    "INSERT OR IGNORE INTO glue_mix_batches (mix_id, batch_number) VALUES (?,?)",
                    (mid, _bn))
        conn.commit()
        return mid
    finally:
        try: conn.close()
        except Exception: pass

def log_laminating(data):
    conn = get_db()
    try:
        # The legacy FK constraints on laminating_log point at the older
        # prod_batch / production_table / glue_mix_log tables. The live system
        # uses the newer `batches` table (different id format) and the user
        # may log laminating before any glue mix is recorded. Disable FK
        # enforcement for this insert so the production log isn't blocked
        # by referential cruft.
        conn.execute("PRAGMA foreign_keys = OFF")
        lid = _new_log_id("LAM")
        conn.execute(
            """INSERT INTO laminating_log (lam_id,batch_id,table_id,emp_code_1,emp_code_2,glue_mix_ref,pcs_target,pcs_actual,time_minutes,notes)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (lid,data['batch_id'],data['table_id'],data['emp_code_1'],data['emp_code_2'],
             data.get('glue_mix_ref'),data['pcs_target'],data['pcs_actual'],
             data.get('time_minutes',0),data.get('notes')))
        conn.commit()
        return lid
    finally:
        try: conn.close()
        except Exception: pass

def advance_laminating(batch_id):
    conn = get_db()
    try:
        conn.execute("UPDATE prod_batch SET status='COLD_PRESS' WHERE batch_id=? AND status='LAMINATING'",
                     (batch_id,))
        conn.commit()
    finally:
        try: conn.close()
        except Exception: pass

def log_cold_press(data):
    conn = get_db()
    try:
        conn.execute("PRAGMA foreign_keys = OFF")   # legacy FK on prod_batch
        cid = _new_log_id("CP")
        conn.execute(
            """INSERT INTO cold_press_log (cp_id,batch_id,machine_id,operator_id,operator_name,pressure_bar,dwell_min,pcs_in,pcs_out)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (cid,data['batch_id'],data['machine_id'],
             data.get('operator_id'),data.get('operator_name',''),
             data.get('pressure_bar'),data.get('dwell_min'),data['pcs_in'],data['pcs_out']))
        conn.execute("UPDATE prod_batch SET status='REPAIR' WHERE batch_id=? AND status='COLD_PRESS'",
                     (data['batch_id'],))
        conn.commit()
        return cid
    finally:
        try: conn.close()
        except Exception: pass

def log_repair(data):
    conn = get_db()
    try:
        conn.execute("PRAGMA foreign_keys = OFF")
        rid = _new_log_id("REP")
        conn.execute(
            """INSERT INTO repair_log (repair_id,batch_id,table_id,repair_type,emp_code_1,emp_code_2,pcs_repaired,notes)
               VALUES (?,?,?,?,?,?,?,?)""",
            (rid,data['batch_id'],data['table_id'],data['repair_type'],
             data['emp_code_1'],data['emp_code_2'],data['pcs_repaired'],data.get('notes')))
        conn.commit()
        return rid
    finally:
        try: conn.close()
        except Exception: pass

def advance_repair(batch_id):
    conn = get_db()
    try:
        conn.execute("UPDATE prod_batch SET status='SANDING' WHERE batch_id=? AND status='REPAIR'",
                     (batch_id,))
        conn.commit()
    finally:
        try: conn.close()
        except Exception: pass

def log_sanding(data):
    conn = get_db()
    try:
        conn.execute("PRAGMA foreign_keys = OFF")
        sid = _new_log_id("SND")
        conn.execute(
            """INSERT INTO sanding_log (sand_id,batch_id,machine_id,operator_id,operator_name,grit_setting,feed_speed,pcs_in,pcs_out,defect_count,notes)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (sid,data['batch_id'],data['machine_id'],
             data.get('operator_id'),data.get('operator_name',''),
             data['grit_setting'],data.get('feed_speed'),
             data['pcs_in'],data['pcs_out'],data.get('defect_count',0),data.get('notes')))
        conn.execute("UPDATE prod_batch SET status='HOT_PRESS' WHERE batch_id=? AND status='SANDING'",
                     (data['batch_id'],))
        conn.commit()
        return sid
    finally:
        try: conn.close()
        except Exception: pass

def log_hot_press(data):
    conn = get_db()
    try:
        conn.execute("PRAGMA foreign_keys = OFF")
        hid = _new_log_id("HP")
        conn.execute(
            """INSERT INTO hot_press_log (hp_id,batch_id,machine_id,operator_id,operator_name,temp_c,pressure_bar,press_time_min,pcs_in,pcs_out)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (hid,data['batch_id'],data['machine_id'],
             data.get('operator_id'),data.get('operator_name',''),
             data['temp_c'],data['pressure_bar'],data['press_time_min'],
             data['pcs_in'],data['pcs_out']))
        conn.execute("UPDATE prod_batch SET status='GRADING' WHERE batch_id=? AND status='HOT_PRESS'",
                     (data['batch_id'],))
        conn.commit()
        return hid
    finally:
        try: conn.close()
        except Exception: pass

def log_grading(data):
    conn = get_db()
    try:
        conn.execute("PRAGMA foreign_keys = OFF")
        pcs_a = data.get('pcs_grade_a',0)
        pcs_b = data.get('pcs_grade_b',0)
        pcs_ncg = data.get('pcs_ncg',0)
        pcs_rej = data.get('pcs_reject',0)
        if pcs_ncg == 0 and pcs_rej == 0: outcome = 'PASS'
        elif pcs_a + pcs_b == 0: outcome = 'FULL_NCG' if pcs_ncg > 0 else 'REJECT'
        else: outcome = 'PARTIAL_NCG'
        gid = _new_log_id("GRD")
        conn.execute(
            """INSERT INTO grading_log (grade_id,batch_id,grader_id,grader_name,grade_outcome,pcs_grade_a,pcs_grade_b,pcs_ncg,pcs_reject,ncg_reason_code,notes)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (gid,data['batch_id'],data.get('grader_id'),data.get('grader_name',''),
             outcome,pcs_a,pcs_b,pcs_ncg,pcs_rej,
             data.get('ncg_reason_code'),data.get('notes')))
        conn.execute("UPDATE prod_batch SET status='COMPLETE' WHERE batch_id=? AND status='GRADING'",
                     (data['batch_id'],))
        conn.commit()
        backtrack = None
        if pcs_ncg > 0 or pcs_rej > 0:
            row = conn.execute("SELECT * FROM v_ncg_backtrack WHERE batch_id=?",
                               (data['batch_id'],)).fetchone()
            backtrack = row_to_dict(row)
        return {'grade_id': gid, 'outcome': outcome, 'backtrack': backtrack}
    finally:
        try: conn.close()
        except Exception: pass

# ═══════════════════════════════════════════════════════════════
# PRODUCTION MODULE — Reporting Queries
# ═══════════════════════════════════════════════════════════════
def get_daily_production(line_id=None, from_date=None, to_date=None):
    conn = get_db(); params = []
    q = "SELECT * FROM v_daily_production WHERE 1=1"
    if line_id: q += " AND line_id=?"; params.append(line_id)
    if from_date: q += " AND production_date>=?"; params.append(from_date)
    if to_date: q += " AND production_date<=?"; params.append(to_date)
    rows = conn.execute(q + " ORDER BY production_date DESC, line_id", params).fetchall()
    conn.close(); return rows_to_list(rows)

def get_lam_efficacy_report(line_id=None, from_date=None, to_date=None):
    conn = get_db(); params = []
    q = "SELECT * FROM v_lam_efficacy WHERE 1=1"
    if line_id: q += " AND line_id=?"; params.append(line_id)
    if from_date: q += " AND production_date>=?"; params.append(from_date)
    rows = conn.execute(q + " ORDER BY production_date DESC, table_id", params).fetchall()
    conn.close(); return rows_to_list(rows)

def get_sanding_defect_report(line_id=None, from_date=None):
    conn = get_db(); params = []
    q = "SELECT * FROM v_sanding_defect_rate WHERE 1=1"
    if line_id: q += " AND line_id=?"; params.append(line_id)
    rows = conn.execute(q + " ORDER BY defect_rate_pct DESC", params).fetchall()
    conn.close(); return rows_to_list(rows)

def get_ncg_by_reason_report(line_id=None):
    conn = get_db(); params = []
    q = "SELECT * FROM v_ncg_by_reason WHERE 1=1"
    if line_id: q += " AND line_id=?"; params.append(line_id)
    rows = conn.execute(q + " ORDER BY total_ncg_pcs DESC", params).fetchall()
    conn.close(); return rows_to_list(rows)

def get_ncg_backtrack_report(batch_id):
    conn = get_db()
    row = conn.execute("SELECT * FROM v_ncg_backtrack WHERE batch_id=?",
                       (batch_id,)).fetchone()
    conn.close(); return row_to_dict(row)

def get_ncg_backtrack_list(line_id=None, from_date=None, reason_code=None, limit=50):
    conn = get_db(); params = []
    q = "SELECT * FROM v_ncg_backtrack WHERE 1=1"
    if line_id: q += " AND line_id=?"; params.append(line_id)
    if from_date: q += " AND production_date>=?"; params.append(from_date)
    if reason_code: q += " AND ncg_reason_code=?"; params.append(reason_code)
    rows = conn.execute(q + f" ORDER BY graded_at DESC LIMIT {int(limit)}", params).fetchall()
    conn.close(); return rows_to_list(rows)

def get_prod_ai_snapshot(line_id=None, days=30):
    from datetime import date, timedelta
    from_date = (date.today() - timedelta(days=days)).isoformat()
    return {
        'snapshot_date': date.today().isoformat(),
        'line_filter': line_id or 'all',
        'period_days': days,
        'daily_summary':        get_daily_production(line_id, from_date),
        'ncg_backtrack':        get_ncg_backtrack_list(line_id, from_date, limit=20),
        'sanding_defect_rates': get_sanding_defect_report(line_id, from_date),
        'lam_efficacy':         get_lam_efficacy_report(line_id, from_date),
        'ncg_by_reason':        get_ncg_by_reason_report(line_id),
    }

def get_batch_station_logs(batch_id):
    """Return all station logs for a batch, used by the Kanban station log page."""
    conn = get_db()
    glue  = rows_to_list(conn.execute("SELECT * FROM glue_mix_log WHERE batch_id=?",    (batch_id,)).fetchall())
    lam   = rows_to_list(conn.execute("SELECT * FROM laminating_log WHERE batch_id=?",  (batch_id,)).fetchall())
    cp    = rows_to_list(conn.execute("SELECT * FROM cold_press_log WHERE batch_id=?",  (batch_id,)).fetchall())
    rep   = rows_to_list(conn.execute("SELECT * FROM repair_log WHERE batch_id=?",      (batch_id,)).fetchall())
    sand  = rows_to_list(conn.execute("SELECT * FROM sanding_log WHERE batch_id=?",     (batch_id,)).fetchall())
    hp    = rows_to_list(conn.execute("SELECT * FROM hot_press_log WHERE batch_id=?",   (batch_id,)).fetchall())
    grade = rows_to_list(conn.execute("SELECT * FROM grading_log WHERE batch_id=?",     (batch_id,)).fetchall())
    pack  = rows_to_list(conn.execute("SELECT * FROM packing_log WHERE batch_id=?",    (batch_id,)).fetchall())
    conn.close()
    return {'glue_mix':glue,'laminating':lam,'cold_press':cp,'repair':rep,
            'sanding':sand,'hot_press':hp,'grading':grade,'packing':pack}

def get_ncg_reasons():
    conn = get_db()
    rows = conn.execute("SELECT * FROM ncg_reason ORDER BY reason_code").fetchall()
    conn.close(); return rows_to_list(rows)

def save_ncg_issues(grade_id, issues):
    """Save multiple NCG issue rows for a grading entry. issues = [{reason_code, pcs_count, notes}]"""
    conn = get_db()
    conn.execute("DELETE FROM grading_ncg_issues WHERE grade_id=?", (grade_id,))
    for iss in issues:
        if not iss.get('reason_code') or not iss.get('pcs_count'): continue
        conn.execute(
            "INSERT INTO grading_ncg_issues (grade_id, reason_code, pcs_count, notes) VALUES (?,?,?,?)",
            (grade_id, iss['reason_code'], int(iss['pcs_count']), iss.get('notes',''))
        )
    conn.commit(); conn.close()

def get_ncg_issues(grade_id):
    conn = get_db()
    rows = conn.execute(
        "SELECT gi.*, nr.description FROM grading_ncg_issues gi "
        "LEFT JOIN ncg_reason nr ON nr.reason_code=gi.reason_code WHERE gi.grade_id=?",
        (grade_id,)
    ).fetchall()
    conn.close(); return rows_to_list(rows)

def get_batch_full_history(batch_id):
    """Enhanced history: movements + all station logs for a prod_batch."""
    conn = get_db()
    logs = get_batch_station_logs(batch_id)
    # Attach NCG issues to each grading entry
    for g in logs.get('grading', []):
        g['ncg_issues'] = rows_to_list(conn.execute(
            "SELECT * FROM grading_ncg_issues WHERE grade_id=?", (g['grade_id'],)
        ).fetchall())
    conn.close()
    return logs

def log_packing(data: dict) -> str:
    conn = get_db()
    pid = _new_log_id("PKK")
    conn.execute(
        """INSERT INTO packing_log
           (pack_id,batch_id,operator_name,table_id,
            pcs_in,pcs_packed,pcs_held,cartons_count,packaging_sku,notes)
           VALUES (?,?,?,?,?,?,?,?,?,?)""",
        (pid, data['batch_id'],
         data.get('operator_name'), data.get('table_id'),
         data.get('pcs_in', 0), data.get('pcs_packed', 0),
         data.get('pcs_held', 0), data.get('cartons_count', 0),
         data.get('packaging_sku'), data.get('notes'))
    )
    conn.commit(); conn.close(); return pid

# ═══════════════════════════════════════════════════════════════
# AUTH MODULE
# ═══════════════════════════════════════════════════════════════
import hashlib
from datetime import datetime, timedelta

def _hash_pw(pw: str) -> str:
    return hashlib.sha256(pw.encode('utf-8')).hexdigest()

def _new_user_id():
    conn = get_db()
    n = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    conn.close()
    return f"USR-{n+1:06d}"

def _seed_default_admin(conn):
    """On a brand-new database (no users), create the bootstrap admin so a
    fresh install can be logged into. Credentials: admin / admin — DEPLOY.md
    §2.6 instructs changing the password and creating real users immediately.
    Never runs once any user exists (idempotent, never resets a password)."""
    try:
        n = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        if n == 0:
            conn.execute(
                "INSERT INTO users (user_id,username,password_hash,role,display_name,active) "
                "VALUES (?,?,?,?,?,1)",
                ("USR-000001", "admin", _hash_pw("admin"), "MANAGERIAL", "Administrator"))
            conn.commit()
    except Exception:
        pass

def create_user(data: dict) -> dict:
    conn = get_db()
    uid = data.get('user_id') or _new_user_id()
    conn.execute(
        "INSERT INTO users (user_id,username,password_hash,role,display_name) VALUES (?,?,?,?,?)",
        (uid, data['username'], _hash_pw(data['password']), data['role'], data['display_name'])
    )
    conn.commit()
    row = conn.execute(
        "SELECT user_id,username,role,display_name,active,created_at FROM users WHERE user_id=?",
        (uid,)
    ).fetchone()
    conn.close(); return row_to_dict(row)

def get_user_by_username(username: str) -> dict:
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM users WHERE username=? AND active=1", (username,)
    ).fetchone()
    conn.close(); return row_to_dict(row)

def create_session(user_id: str, hours: float = 8.5) -> str:
    conn = get_db()
    token = uuid.uuid4().hex
    expires = (datetime.utcnow() + timedelta(hours=hours)).isoformat()
    conn.execute(
        "INSERT INTO user_sessions (token,user_id,expires_at) VALUES (?,?,?)",
        (token, user_id, expires)
    )
    conn.commit(); conn.close(); return token

def get_session_user(token: str) -> dict:
    conn = get_db()
    row = conn.execute(
        """SELECT u.user_id,u.username,u.role,u.display_name FROM users u
           JOIN user_sessions s ON u.user_id=s.user_id
           WHERE s.token=? AND s.expires_at>? AND u.active=1""",
        (token, datetime.utcnow().isoformat())
    ).fetchone()
    conn.close(); return row_to_dict(row)

def delete_session(token: str):
    conn = get_db()
    conn.execute("DELETE FROM user_sessions WHERE token=?", (token,))
    conn.commit(); conn.close()

def log_login(user_id: str, username: str, role: str, ip_address: str = None):
    """Record a successful login event."""
    import uuid
    log_id = 'LGN-' + uuid.uuid4().hex[:8].upper()
    conn = get_db()
    conn.execute(
        "INSERT INTO login_log (log_id,user_id,username,role,ip_address) VALUES (?,?,?,?,?)",
        (log_id, user_id, username, role, ip_address)
    )
    conn.commit(); conn.close()

def get_login_log(limit: int = 200) -> list:
    """Return recent login events, newest first."""
    conn = get_db()
    rows = conn.execute(
        """SELECT ll.log_id, ll.username, ll.role, ll.ip_address, ll.logged_at,
                  u.display_name, u.active
           FROM login_log ll
           JOIN users u ON u.user_id = ll.user_id
           ORDER BY ll.logged_at DESC LIMIT ?""",
        (limit,)
    ).fetchall()
    conn.close(); return rows_to_list(rows)

def get_users() -> list:
    conn = get_db()
    rows = conn.execute(
        "SELECT user_id,username,role,display_name,active,created_at FROM users ORDER BY created_at"
    ).fetchall()
    conn.close(); return rows_to_list(rows)

def update_user(user_id: str, data: dict) -> dict:
    conn = get_db()
    fields, vals = [], []
    for col in ('display_name','role'):
        if data.get(col) is not None:
            fields.append(f"{col}=?"); vals.append(data[col])
    if 'active' in data and data['active'] is not None:
        fields.append("active=?"); vals.append(1 if data['active'] else 0)
    if data.get('password'):
        fields.append("password_hash=?"); vals.append(_hash_pw(data['password']))
    if fields:
        vals.append(user_id)
        conn.execute(f"UPDATE users SET {','.join(fields)} WHERE user_id=?", vals)
        conn.commit()
    row = conn.execute(
        "SELECT user_id,username,role,display_name,active FROM users WHERE user_id=?",
        (user_id,)
    ).fetchone()
    conn.close(); return row_to_dict(row)

def save_user_departments(user_id: str, departments: list):
    """departments = [{'department': 'HOT_PRESS', 'line_id': 'P02'}, ...]"""
    conn = get_db()
    conn.execute("DELETE FROM user_departments WHERE user_id=?", (user_id,))
    for d in departments:
        conn.execute(
            "INSERT OR IGNORE INTO user_departments (user_id,department,line_id) VALUES (?,?,?)",
            (user_id, d['department'], d.get('line_id'))
        )
    conn.commit(); conn.close()

def get_user_departments(user_id: str) -> list:
    conn = get_db()
    rows = conn.execute(
        "SELECT department,line_id FROM user_departments WHERE user_id=? ORDER BY department,line_id",
        (user_id,)
    ).fetchall()
    conn.close(); return rows_to_list(rows)

# ═══════════════════════════════════════════════════════════════
# SUPPLY WAREHOUSE / CONSUMABLE REQUESTS
# ═══════════════════════════════════════════════════════════════

def _new_req_id() -> str:
    today = datemod.today().strftime('%Y%m%d')
    conn = get_db()
    n = conn.execute(
        "SELECT COUNT(*) FROM consumable_request WHERE request_id LIKE ?",
        (f'REQ-{today}-%',)
    ).fetchone()[0]
    conn.close(); return f"REQ-{today}-{n+1:04d}"

def create_consumable_request(data: dict) -> dict:
    conn = get_db()
    rid = _new_req_id()
    prio = int(data.get('priority') or 2)
    if prio not in (1, 2, 3): prio = 2
    nt = (data.get('needed_time') or '').lower()
    if nt not in ('morning', 'afternoon'): nt = None
    conn.execute(
        """INSERT INTO consumable_request
           (request_id,requested_by,department,line_id,material_id,qty_requested,notes,
            priority, needed_by, needed_time)
           VALUES (?,?,?,?,?,?,?,?,?,?)""",
        (rid, data['requested_by'], data['department'], data.get('line_id'),
         data['material_id'], data['qty_requested'], data.get('notes'),
         prio, data.get('needed_by'), nt)
    )
    conn.commit()
    row = conn.execute(
        """SELECT cr.*,m.name AS material_name,m.unit,m.unit_cost,
                  u.display_name AS requester_name
           FROM consumable_request cr
           JOIN materials m ON cr.material_id=m.id
           JOIN users u ON cr.requested_by=u.user_id
           WHERE cr.request_id=?""",
        (rid,)
    ).fetchone()
    conn.close(); return row_to_dict(row)

def get_consumable_requests(status=None, department=None, requested_by=None,
                            line_id=None, open_only=False) -> list:
    conn = get_db()
    # current_stock + reorder_point are surfaced so the warehouse Supply
    # Queue can show live warehouse stock for each request line, matching
    # what the Raw Materials page displays (no separate fetch needed).
    q = """SELECT cr.*,m.name AS material_name,m.name_th AS material_name_th,
                  m.unit,m.unit_cost,m.type AS material_type,
                  COALESCE(m.current_stock,0)  AS current_stock,
                  COALESCE(m.reorder_point,0)  AS reorder_point,
                  u.display_name AS requester_name,
                  uf.display_name AS fulfiller_name
           FROM consumable_request cr
           JOIN materials m ON cr.material_id=m.id
           JOIN users u ON cr.requested_by=u.user_id
           LEFT JOIN users uf ON cr.fulfilled_by=uf.user_id
           WHERE 1=1"""
    params = []
    if status:      q += " AND cr.status=?";       params.append(status)
    if department:  q += " AND cr.department=?";   params.append(department)
    if requested_by:q += " AND cr.requested_by=?"; params.append(requested_by)
    # line_id='' matches centralised-department requests (no line). A non-empty
    # value matches that line OR the legacy NULL/''. We treat '' as "any".
    if line_id:     q += " AND cr.line_id=?";      params.append(line_id)
    # open_only: anything the station still cares about — not cancelled and not
    # yet fully received. Receipt is tracked via qty_received (there is no
    # 'RECEIVED' status; the status column has a CHECK constraint limited to
    # PENDING/PARTIAL/FULFILLED/CANCELLED). Used by "My Open Requests".
    if open_only:
        q += (" AND cr.status != 'CANCELLED'"
              " AND COALESCE(cr.qty_received,0) < cr.qty_requested")
    rows = conn.execute(q + " ORDER BY cr.created_at DESC", params).fetchall()
    conn.close(); return rows_to_list(rows)


def receive_consumable_request(request_id: str, received_by: str) -> dict:
    """Station confirms physical receipt of a (warehouse-fulfilled) consumable
    request. Deposits the not-yet-received quantity into station_stock for the
    requesting (department, line) and logs a RECEIVE movement, then advances
    the request status. Two-step model: warehouse 'fulfill' already deducted
    WH stock; this is the second hop that makes it visible at the station."""
    conn = get_db()
    req = conn.execute("SELECT * FROM consumable_request WHERE request_id=?",
                       (request_id,)).fetchone()
    if not req:
        conn.close(); raise ValueError("Request not found")
    req = dict(req)

    fulfilled = float(req.get('qty_fulfilled') or 0)
    received  = float(req.get('qty_received') or 0)
    to_receive = round(fulfilled - received, 4)
    if to_receive <= 0:
        conn.close()
        raise ValueError("Nothing to receive — warehouse hasn't fulfilled any "
                         "quantity yet, or it's already been received.")
    conn.close()  # log_station_stock_movement opens its own connection

    # Deposit into station stock (creates the row if first receipt).
    log_station_stock_movement({
        'department':    req['department'],
        'line_id':       req.get('line_id') or '',
        'material_id':   req['material_id'],
        'qty_change':    to_receive,
        'movement_type': 'RECEIVE',
        'reference':     request_id,
        'notes':         f"Received from WH against request {request_id}",
        'created_by':    received_by,
    })

    # Advance the request. We DON'T set a 'RECEIVED' status — the status
    # column's CHECK constraint only allows PENDING/PARTIAL/FULFILLED/
    # CANCELLED. "Fully received / closed" is derived from
    # qty_received >= qty_requested wherever it matters (the open_only filter
    # and the UI badge), so qty_received alone is the source of truth.
    conn = get_db()
    new_received = received + to_receive
    conn.execute("""UPDATE consumable_request
                       SET qty_received=?, received_by=?,
                           received_at=CURRENT_TIMESTAMP
                     WHERE request_id=?""",
                 (new_received, received_by, request_id))
    conn.commit()
    row = row_to_dict(conn.execute(
        "SELECT * FROM consumable_request WHERE request_id=?", (request_id,)).fetchone())
    conn.close()
    return row

def fulfill_consumable_request(request_id: str, qty_to_fulfill: float, fulfilled_by: str) -> dict:
    conn = get_db()
    req = conn.execute("SELECT * FROM consumable_request WHERE request_id=?", (request_id,)).fetchone()
    if not req: conn.close(); raise ValueError("Request not found")
    req = dict(req)
    mat = dict(conn.execute("SELECT * FROM materials WHERE id=?", (req['material_id'],)).fetchone())

    # Stock guard — reject rather than silently clamp when warehouse stock
    # can't cover the issue. Matches fulfill_fc_transfer_request and the
    # glue-mix / VCMX paths, which all raise 'Insufficient ... stock' rather
    # than over-issuing. Without this the old MAX(0, ...) deduction let two
    # simultaneous fulfillments over-issue the same material below zero.
    available = float(mat.get('current_stock') or 0)
    if qty_to_fulfill > available:
        conn.close()
        raise ValueError(
            f"Insufficient WH stock for {mat.get('name','this material')}: "
            f"only {available:g} {mat.get('unit','')} available, "
            f"requested {qty_to_fulfill:g}"
        )

    new_fulfilled = req['qty_fulfilled'] + qty_to_fulfill
    new_status = 'FULFILLED' if new_fulfilled >= req['qty_requested'] else 'PARTIAL'

    conn.execute(
        """UPDATE consumable_request
           SET qty_fulfilled=?,status=?,fulfilled_by=?,fulfilled_at=CURRENT_TIMESTAMP
           WHERE request_id=?""",
        (new_fulfilled, new_status, fulfilled_by, request_id)
    )
    # Deduct from warehouse stock. The guard above ensures current_stock >=
    # qty_to_fulfill at read time; MAX(0, ...) stays as a defensive floor.
    conn.execute(
        "UPDATE materials SET current_stock=MAX(0,current_stock-?) WHERE id=?",
        (qty_to_fulfill, req['material_id'])
    )
    # Write cost ledger entry
    month_year = datemod.today().strftime('%Y-%m')
    unit_cost  = mat['unit_cost']
    total_cost = qty_to_fulfill * unit_cost
    conn.execute(
        """INSERT INTO dept_cost_ledger
           (department,line_id,month_year,material_id,qty,unit_cost,total_cost,request_id)
           VALUES (?,?,?,?,?,?,?,?)""",
        (req['department'], req.get('line_id'), month_year,
         req['material_id'], qty_to_fulfill, unit_cost, total_cost, request_id)
    )
    conn.commit()
    row = conn.execute(
        """SELECT cr.*,m.name AS material_name,m.unit,m.unit_cost,
                  u.display_name AS requester_name,
                  uf.display_name AS fulfiller_name
           FROM consumable_request cr
           JOIN materials m ON cr.material_id=m.id
           JOIN users u ON cr.requested_by=u.user_id
           LEFT JOIN users uf ON cr.fulfilled_by=uf.user_id
           WHERE cr.request_id=?""",
        (request_id,)
    ).fetchone()
    conn.close(); return row_to_dict(row)

def cancel_consumable_request(request_id: str) -> dict:
    conn = get_db()
    conn.execute(
        "UPDATE consumable_request SET status='CANCELLED' WHERE request_id=? AND status IN ('PENDING','PARTIAL')",
        (request_id,)
    )
    conn.commit()
    row = conn.execute("SELECT * FROM consumable_request WHERE request_id=?", (request_id,)).fetchone()
    conn.close(); return row_to_dict(row)


# ═══════════════════════════════════════════════════════════════
# FACTORY ASSISTANT MEMORY  (conversation history + operational knowledge)
# ═══════════════════════════════════════════════════════════════

def fa_save_message(session_id: str, user_id: str, role: str,
                    content: str, tool_calls=None) -> None:
    """Persist one chat turn. tool_calls may be a list/dict (stored as JSON)
    or None."""
    conn = get_db()
    tc = _json.dumps(tool_calls) if tool_calls else None
    conn.execute(
        """INSERT INTO fa_conversations (id, session_id, user_id, role, content, tool_calls)
           VALUES (?,?,?,?,?,?)""",
        (uuid.uuid4().hex, session_id, user_id, role, content, tc))
    conn.commit(); conn.close()


def fa_get_recent_messages(session_id: str, limit: int = 20) -> list:
    """Return the last `limit` messages for a session, in chronological order."""
    if not session_id:
        return []
    conn = get_db()
    rows = conn.execute(
        """SELECT role, content, created_at FROM fa_conversations
           WHERE session_id=? ORDER BY created_at DESC, rowid DESC LIMIT ?""",
        (session_id, int(limit))).fetchall()
    conn.close()
    return list(reversed(rows_to_list(rows)))   # oldest -> newest


# Words too generic to be useful for knowledge keyword-matching.
_FA_STOPWORDS = {
    'the','a','an','and','or','of','to','in','on','for','is','are','was','were',
    'how','what','which','why','when','where','show','give','me','my','our',
    'this','that','these','those','with','from','by','at','it','do','does','did',
    'i','you','we','they','can','should','would','could','please','about','many',
}

def fa_search_knowledge(query_text: str, limit: int = 10,
                        touch: bool = True) -> list:
    """Return up to `limit` knowledge entries relevant to query_text by simple
    keyword match against title+content. When `touch`, bumps last_referenced_at
    on the rows returned (so the viewer surfaces recently-used facts)."""
    conn = get_db()
    words = [w for w in re.findall(r"[a-zA-Z0-9]+", (query_text or "").lower())
             if len(w) > 2 and w not in _FA_STOPWORDS]
    if words:
        # Score = number of distinct query words found in title+content.
        rows = conn.execute(
            "SELECT id, category, title, content, source, confidence, "
            "       created_at, last_referenced_at FROM fa_knowledge").fetchall()
        scored = []
        for r in rows:
            hay = (str(r['title']) + ' ' + str(r['content'])).lower()
            score = sum(1 for w in set(words) if w in hay)
            if score > 0:
                scored.append((score, r))
        scored.sort(key=lambda x: (-x[0],
                                   x[1]['last_referenced_at'] or ''), reverse=False)
        picked = [r for _, r in scored[:limit]]
    else:
        # No usable keywords — fall back to most-recently-referenced.
        picked = conn.execute(
            "SELECT id, category, title, content, source, confidence, "
            "       created_at, last_referenced_at FROM fa_knowledge "
            "ORDER BY last_referenced_at DESC NULLS LAST, created_at DESC "
            f"LIMIT {int(limit)}").fetchall()
    result = rows_to_list(picked)
    if touch and result:
        ids = [r['id'] for r in result]
        ph = ','.join('?' * len(ids))
        conn.execute(
            f"UPDATE fa_knowledge SET last_referenced_at=datetime('now') WHERE id IN ({ph})",
            ids)
        conn.commit()
    conn.close()
    return result


def fa_add_knowledge(category: str, title: str, content: str,
                     source: str, confidence: str = 'medium') -> dict:
    """Insert a knowledge entry. source is 'assistant_observed' or
    'manager_input'. Returns {id}."""
    valid_cat = {'line_behaviour','supplier','seasonal','ncg_pattern','material','general'}
    category = (category or 'general').strip().lower()
    if category not in valid_cat:
        category = 'general'
    confidence = (confidence or 'medium').strip().lower()
    if confidence not in {'low','medium','high'}:
        confidence = 'medium'
    if source not in {'assistant_observed','manager_input'}:
        source = 'manager_input'
    if not (title or '').strip() or not (content or '').strip():
        raise ValueError("title and content are required")
    kid = uuid.uuid4().hex
    conn = get_db()
    conn.execute(
        """INSERT INTO fa_knowledge (id, category, title, content, source, confidence)
           VALUES (?,?,?,?,?,?)""",
        (kid, category, title.strip(), content.strip(), source, confidence))
    conn.commit(); conn.close()
    return {"saved": True, "id": kid}


def fa_list_knowledge() -> list:
    """All knowledge entries, most-recently-referenced first (then newest)."""
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM fa_knowledge "
        "ORDER BY last_referenced_at DESC NULLS LAST, created_at DESC").fetchall()
    conn.close(); return rows_to_list(rows)


# ═══════════════════════════════════════════════════════════════
# FC TRANSFER REQUESTS  (FC station requests raw materials from WH)
# ═══════════════════════════════════════════════════════════════

def _new_fctr_id() -> str:
    today = datemod.today().strftime('%Y%m%d')
    conn = get_db()
    n = conn.execute(
        "SELECT COUNT(*) FROM fc_transfer_requests WHERE request_id LIKE ?",
        (f'FCTR-{today}-%',)
    ).fetchone()[0]
    conn.close(); return f"FCTR-{today}-{n+1:04d}"


def _fctr_row_query():
    return """
        SELECT tr.*,
               m.name AS material_name, m.unit, m.unit_cost,
               m.type AS material_type,
               m.current_stock AS wh_stock, m.fc_stock,
               u.display_name AS requester_name,
               uf.display_name AS fulfiller_name
        FROM fc_transfer_requests tr
        JOIN materials m ON m.id = tr.material_id
        JOIN users u ON u.user_id = tr.requested_by
        LEFT JOIN users uf ON uf.user_id = tr.fulfilled_by
    """


def get_fc_transfer_requests(status: str = None, direction: str = None) -> list:
    conn = get_db()
    q = _fctr_row_query() + " WHERE 1=1"
    params = []
    if status:
        q += " AND tr.status=?"; params.append(status)
    if direction:
        q += " AND COALESCE(tr.direction,'inbound')=?"; params.append(direction)
    rows = conn.execute(q + " ORDER BY tr.created_at DESC", params).fetchall()
    conn.close(); return rows_to_list(rows)


def create_fc_transfer_request(data: dict) -> dict:
    """Inbound: WH → FC station (FC requests materials from WH)."""
    conn = get_db()
    mat = conn.execute(
        "SELECT id, type FROM materials WHERE id=?", (data['material_id'],)
    ).fetchone()
    if not mat:
        conn.close(); raise ValueError("Material not found")
    if dict(mat)['type'] not in ('veneer_sheet', 'core_board'):
        conn.close(); raise ValueError("FC transfers only allowed for veneers and core boards")

    rid = _new_fctr_id()
    prio = int(data.get('priority') or 2)
    if prio not in (1, 2, 3): prio = 2
    nt = (data.get('needed_time') or '').lower()
    if nt not in ('morning', 'afternoon'): nt = None
    conn.execute(
        """INSERT INTO fc_transfer_requests
           (request_id, material_id, qty_requested, notes, requested_by, direction,
            priority, needed_by, needed_time)
           VALUES (?,?,?,?,?,?,?,?,?)""",
        (rid, data['material_id'], data['qty_requested'],
         data.get('notes', ''), data['requested_by'], 'inbound',
         prio, data.get('needed_by'), nt)
    )
    conn.commit()
    row = conn.execute(_fctr_row_query() + " WHERE tr.request_id=?", (rid,)).fetchone()
    conn.close(); return row_to_dict(row)


def create_fc_return_request(data: dict) -> dict:
    """Outbound: FC station → WH (FC requests to return materials to WH). Stock stays at FC until WH confirms pickup."""
    conn = get_db()
    mat = conn.execute(
        "SELECT id, type, fc_stock FROM materials WHERE id=?", (data['material_id'],)
    ).fetchone()
    if not mat:
        conn.close(); raise ValueError("Material not found")
    mat = dict(mat)
    if mat['type'] not in ('veneer_sheet', 'core_board'):
        conn.close(); raise ValueError("FC returns only allowed for veneers and core boards")
    if float(mat.get('fc_stock') or 0) < float(data['qty_requested']):
        conn.close(); raise ValueError(
            f"Insufficient FC stock: only {mat.get('fc_stock', 0)} available"
        )

    rid = _new_fctr_id()
    conn.execute(
        """INSERT INTO fc_transfer_requests
           (request_id, material_id, qty_requested, notes, requested_by, direction)
           VALUES (?,?,?,?,?,?)""",
        (rid, data['material_id'], data['qty_requested'],
         data.get('notes', ''), data['requested_by'], 'outbound')
    )
    conn.commit()
    row = conn.execute(_fctr_row_query() + " WHERE tr.request_id=?", (rid,)).fetchone()
    conn.close(); return row_to_dict(row)


def fulfill_fc_transfer_request(request_id: str, qty_to_fulfill: float, fulfilled_by: str) -> dict:
    """
    Inbound (WH→FC): WH issues stock — deducts WH current_stock, adds to fc_stock.
    Outbound (FC→WH): WH picks up from FC — deducts fc_stock, adds to WH current_stock.
    """
    conn = get_db()
    req = conn.execute(
        "SELECT * FROM fc_transfer_requests WHERE request_id=?", (request_id,)
    ).fetchone()
    if not req:
        conn.close(); raise ValueError("FC transfer request not found")
    req = dict(req)

    direction = req.get('direction') or 'inbound'
    mat = dict(conn.execute(
        "SELECT current_stock, fc_stock FROM materials WHERE id=?", (req['material_id'],)
    ).fetchone())

    if direction == 'inbound':
        # WH → FC: validate WH stock
        available = float(mat['current_stock'] or 0)
        if qty_to_fulfill > available:
            conn.close(); raise ValueError(f"Insufficient WH stock: only {available} available")
        conn.execute(
            "UPDATE materials SET current_stock=MAX(0,current_stock-?), fc_stock=fc_stock+? WHERE id=?",
            (qty_to_fulfill, qty_to_fulfill, req['material_id'])
        )
    else:
        # FC → WH: validate FC stock
        available = float(mat['fc_stock'] or 0)
        if qty_to_fulfill > available:
            conn.close(); raise ValueError(f"Insufficient FC stock: only {available} available")
        conn.execute(
            "UPDATE materials SET fc_stock=MAX(0,fc_stock-?), current_stock=current_stock+? WHERE id=?",
            (qty_to_fulfill, qty_to_fulfill, req['material_id'])
        )

    new_fulfilled = req['qty_fulfilled'] + qty_to_fulfill
    new_status = 'FULFILLED' if new_fulfilled >= req['qty_requested'] else 'PARTIAL'
    conn.execute(
        """UPDATE fc_transfer_requests
           SET qty_fulfilled=?, status=?, fulfilled_by=?, fulfilled_at=CURRENT_TIMESTAMP
           WHERE request_id=?""",
        (new_fulfilled, new_status, fulfilled_by, request_id)
    )
    conn.commit()
    row = conn.execute(_fctr_row_query() + " WHERE tr.request_id=?", (request_id,)).fetchone()
    conn.close(); return row_to_dict(row)


def cancel_fc_transfer_request(request_id: str) -> dict:
    conn = get_db()
    conn.execute(
        "UPDATE fc_transfer_requests SET status='CANCELLED' WHERE request_id=? AND status IN ('PENDING','PARTIAL')",
        (request_id,)
    )
    conn.commit()
    row = conn.execute(_fctr_row_query() + " WHERE tr.request_id=?", (request_id,)).fetchone()
    conn.close(); return row_to_dict(row)


def get_fc_stock_materials() -> list:
    """All materials that are eligible for FC station (veneers + core boards), with both stock levels."""
    conn = get_db()
    rows = conn.execute("""
        SELECT id, code, name, type, unit,
               current_stock AS wh_stock,
               fc_stock,
               reorder_point, unit_cost, supplier,
               species, grade, face_back, cut_type, matching
        FROM materials
        WHERE type IN ('veneer_sheet', 'core_board')
        ORDER BY type, name
    """).fetchall()
    conn.close(); return rows_to_list(rows)


def adjust_fc_stock(material_id: int, qty_delta: float, adjusted_by: str) -> dict:
    """Manual FC stock adjustment (positive = add, negative = deduct)."""
    conn = get_db()
    conn.execute(
        "UPDATE materials SET fc_stock=MAX(0, fc_stock+?) WHERE id=?",
        (qty_delta, material_id)
    )
    conn.commit()
    row = conn.execute("SELECT * FROM materials WHERE id=?", (material_id,)).fetchone()
    conn.close(); return row_to_dict(row)


# ═══════════════════════════════════════════════════════════════
# VENEER RE-GRADING
# ═══════════════════════════════════════════════════════════════

def _new_regrade_id() -> str:
    today = datemod.today().strftime('%Y%m%d')
    conn = get_db()
    n = conn.execute(
        "SELECT COUNT(*) FROM veneer_regrade_log WHERE record_id LIKE ?",
        (f'RGR-{today}-%',)
    ).fetchone()[0]
    conn.close(); return f"RGR-{today}-{n+1:04d}"


def create_veneer_regrade(data: dict) -> dict:
    """
    Re-grade a veneer within FC station: reclassify from_material → to_material.
    Both source and destination are always fc_stock — regrading is an in-station operation.
    To return veneers to WH, use create_fc_return_request() instead.
    """
    conn = get_db()
    from_mat = row_to_dict(conn.execute(
        "SELECT * FROM materials WHERE id=?", (data['from_material_id'],)
    ).fetchone())
    to_mat = conn.execute(
        "SELECT id FROM materials WHERE id=?", (data['to_material_id'],)
    ).fetchone()
    if not from_mat or not to_mat:
        conn.close(); raise ValueError("Material not found")

    qty = float(data['qty'])
    # Regrading always operates on FC station stock
    src_stock = float(from_mat.get('fc_stock') or 0)
    if qty > src_stock:
        conn.close()
        raise ValueError(f"Insufficient FC stock: only {src_stock} available")

    # Deduct from source fc_stock, add to target fc_stock
    conn.execute("UPDATE materials SET fc_stock=MAX(0,fc_stock-?) WHERE id=?",
                 (qty, data['from_material_id']))
    conn.execute("UPDATE materials SET fc_stock=fc_stock+? WHERE id=?",
                 (qty, data['to_material_id']))

    rid = _new_regrade_id()
    conn.execute(
        """INSERT INTO veneer_regrade_log
           (record_id, from_material_id, to_material_id, qty, from_location, to_location, graded_by, notes)
           VALUES (?,?,?,?,?,?,?,?)""",
        (rid, data['from_material_id'], data['to_material_id'], qty,
         'fc_station', 'fc_station', data['graded_by'], data.get('notes', ''))
    )
    conn.commit()
    row = conn.execute("""
        SELECT r.*,
               fm.name AS from_material_name, fm.code AS from_material_code,
               fm.grade AS from_grade, fm.species AS from_species,
               tm.name AS to_material_name, tm.code AS to_material_code,
               tm.grade AS to_grade, tm.species AS to_species,
               u.display_name AS graded_by_name
        FROM veneer_regrade_log r
        JOIN materials fm ON fm.id = r.from_material_id
        JOIN materials tm ON tm.id = r.to_material_id
        LEFT JOIN users u ON u.user_id = r.graded_by
        WHERE r.record_id=?
    """, (rid,)).fetchone()
    conn.close(); return row_to_dict(row)


def get_veneer_regrade_log(material_id: int = None, limit: int = 50) -> list:
    conn = get_db()
    q = """
        SELECT r.*,
               fm.name AS from_material_name, fm.code AS from_material_code,
               fm.grade AS from_grade, fm.species AS from_species,
               tm.name AS to_material_name, tm.code AS to_material_code,
               tm.grade AS to_grade, tm.species AS to_species,
               u.display_name AS graded_by_name
        FROM veneer_regrade_log r
        JOIN materials fm ON fm.id = r.from_material_id
        JOIN materials tm ON tm.id = r.to_material_id
        LEFT JOIN users u ON u.user_id = r.graded_by
        WHERE 1=1
    """
    params = []
    if material_id:
        q += " AND (r.from_material_id=? OR r.to_material_id=?)"
        params += [material_id, material_id]
    rows = conn.execute(q + " ORDER BY r.created_at DESC LIMIT ?", params + [limit]).fetchall()
    conn.close(); return rows_to_list(rows)


# ═══════════════════════════════════════════════════════════════
# PRODUCTION ORDER VENEER GRADE-MIX ALLOCATION
# ═══════════════════════════════════════════════════════════════

def save_veneer_alloc_and_confirm(prod_order_id: int, face_alloc: list, back_alloc: list,
                                   deduct_fc_stock: bool = True) -> dict:
    """
    Save grade-mix veneer allocation for a production order and mark fc_confirmed.
    Each alloc item: {material_id: int, qty_allocated: float}
    If deduct_fc_stock=True, removes allocated qty from materials.fc_stock.
    Sets confirmed_face_veneer_id = largest face allocation's material.
    """
    conn = get_db()

    def _validate_and_total(alloc, side):
        if not alloc:
            return 0.0
        total = 0.0
        for item in alloc:
            mid = item['material_id']
            qty = float(item['qty_allocated'])
            if qty <= 0:
                continue
            mat = conn.execute(
                "SELECT id, fc_stock, name FROM materials WHERE id=?", (mid,)
            ).fetchone()
            if not mat:
                conn.close(); raise ValueError(f"Material {mid} not found")
            if deduct_fc_stock and float(mat[1] or 0) < qty:
                conn.close()
                raise ValueError(
                    f"Insufficient FC stock for {mat[2]}: need {qty}, have {mat[1] or 0}"
                )
            total += qty
        return total

    _validate_and_total(face_alloc, 'face')
    _validate_and_total(back_alloc, 'back')

    # Clear old allocations
    conn.execute("DELETE FROM prod_order_veneer_alloc WHERE prod_order_id=?", (prod_order_id,))

    primary_face_id = None
    primary_back_id = None

    for side, alloc in [('face', face_alloc), ('back', back_alloc)]:
        total_qty = sum(float(i['qty_allocated']) for i in alloc if float(i.get('qty_allocated', 0)) > 0)
        best_id, best_qty = None, 0
        for item in alloc:
            qty = float(item.get('qty_allocated', 0))
            if qty <= 0:
                continue
            mid = item['material_id']
            pct = round(qty / total_qty * 100, 1) if total_qty else 0
            conn.execute(
                """INSERT OR REPLACE INTO prod_order_veneer_alloc
                   (prod_order_id, side, material_id, qty_allocated, pct_of_total)
                   VALUES (?,?,?,?,?)""",
                (prod_order_id, side, mid, qty, pct)
            )
            if deduct_fc_stock:
                conn.execute(
                    "UPDATE materials SET fc_stock=MAX(0,fc_stock-?) WHERE id=?",
                    (qty, mid)
                )
            if qty > best_qty:
                best_qty = qty; best_id = mid
        if side == 'face':
            primary_face_id = best_id
        else:
            primary_back_id = best_id

    # Mark production order confirmed with primary veneer IDs
    conn.execute("""
        UPDATE production_orders
        SET confirmed_face_veneer_id=?, confirmed_back_veneer_id=?, fc_confirmed=1
        WHERE id=?
    """, (primary_face_id, primary_back_id, prod_order_id))

    conn.commit()

    # Return full allocation with material details
    alloc_rows = rows_to_list(conn.execute("""
        SELECT a.side, a.material_id, a.qty_allocated, a.pct_of_total,
               m.name AS material_name, m.code AS material_code,
               m.grade, m.species, m.fc_stock, m.unit
        FROM prod_order_veneer_alloc a
        JOIN materials m ON m.id = a.material_id
        WHERE a.prod_order_id=?
        ORDER BY a.side, a.qty_allocated DESC
    """, (prod_order_id,)).fetchall())

    conn.close()
    return {'prod_order_id': prod_order_id, 'allocations': alloc_rows,
            'primary_face_id': primary_face_id, 'primary_back_id': primary_back_id}


def get_veneer_alloc(prod_order_id: int) -> list:
    conn = get_db()
    rows = rows_to_list(conn.execute("""
        SELECT a.side, a.material_id, a.qty_allocated, a.pct_of_total,
               m.name AS material_name, m.code AS material_code,
               m.grade, m.species, m.fc_stock, m.unit
        FROM prod_order_veneer_alloc a
        JOIN materials m ON m.id = a.material_id
        WHERE a.prod_order_id=?
        ORDER BY a.side, a.qty_allocated DESC
    """, (prod_order_id,)).fetchall())
    conn.close(); return rows


def get_dept_cost_summary(month_year=None) -> list:
    conn = get_db()
    my = month_year or datemod.today().strftime('%Y-%m')
    rows = conn.execute(
        """SELECT dcl.department, dcl.line_id, dcl.month_year,
                  ROUND(SUM(dcl.total_cost),2) AS total_cost,
                  SUM(dcl.qty) AS total_qty,
                  COUNT(DISTINCT dcl.request_id) AS request_count,
                  GROUP_CONCAT(DISTINCT m.name) AS materials_used
           FROM dept_cost_ledger dcl
           JOIN materials m ON dcl.material_id=m.id
           WHERE dcl.month_year=?
           GROUP BY dcl.department,dcl.line_id,dcl.month_year
           ORDER BY total_cost DESC""",
        (my,)
    ).fetchall()
    conn.close(); return rows_to_list(rows)

def get_dept_cost_detail(month_year=None, department=None) -> list:
    conn = get_db()
    my = month_year or datemod.today().strftime('%Y-%m')
    q  = """SELECT dcl.*,m.name AS material_name,m.unit,
                   u.display_name AS requester_name
            FROM dept_cost_ledger dcl
            JOIN materials m ON dcl.material_id=m.id
            JOIN consumable_request cr ON dcl.request_id=cr.request_id
            JOIN users u ON cr.requested_by=u.user_id
            WHERE dcl.month_year=?"""
    params = [my]
    if department: q += " AND dcl.department=?"; params.append(department)
    rows = conn.execute(q + " ORDER BY dcl.created_at DESC", params).fetchall()
    conn.close(); return rows_to_list(rows)

def get_consumable_materials() -> list:
    """All active materials available for consumable requests."""
    conn = get_db()
    rows = conn.execute(
        "SELECT id,name,type,unit,current_stock,unit_cost FROM materials ORDER BY type,name"
    ).fetchall()
    conn.close(); return rows_to_list(rows)
