"""
Seed data for PVWood ERP demo.
Run once from the project root:  python scripts/seed_data.py
Creates realistic veneer factory data.
"""

import sys, os
# database.py lives in ../execution relative to this file
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'execution'))

from database import init_db, get_db
from datetime import date, timedelta
import random

def seed():
    init_db()
    conn = get_db()
    cur = conn.cursor()

    # Clear existing data
    cur.executescript("""
        DELETE FROM reports;
        DELETE FROM production_logs;
        DELETE FROM orders;
        DELETE FROM bom;
        DELETE FROM machines;
        DELETE FROM products;
        DELETE FROM materials;
    """)

    # ── Materials ────────────────────────────────────────────
    materials = [
        # Core boards
        ("MDF 18mm 4x8ft", "core_board", "sheet", 450, 100, 285, "Thai MDF Co."),
        ("MDF 12mm 4x8ft", "core_board", "sheet", 320, 80, 220, "Thai MDF Co."),
        ("Plywood 15mm 4x8ft", "core_board", "sheet", 180, 60, 340, "Wood Plus Ltd."),
        ("Particle Board 18mm", "core_board", "sheet", 600, 120, 195, "Wood Plus Ltd."),
        # Veneer sheets
        ("Oak Natural Veneer 4x8ft", "veneer_sheet", "sheet", 280, 80, 420, "Euro Veneer Import"),
        ("Walnut Veneer 4x8ft", "veneer_sheet", "sheet", 150, 50, 580, "Euro Veneer Import"),
        ("Maple Veneer 4x8ft", "veneer_sheet", "sheet", 200, 60, 380, "Euro Veneer Import"),
        ("Cherry Veneer 4x8ft", "veneer_sheet", "sheet", 90, 40, 650, "Euro Veneer Import"),
        ("Teak Veneer 4x8ft", "veneer_sheet", "sheet", 60, 30, 890, "Thai Teak Supply"),
        ("White Oak Veneer 4x8ft", "veneer_sheet", "sheet", 110, 40, 490, "Euro Veneer Import"),
        # Adhesives
        ("PVA Wood Glue 20kg", "adhesive", "drum", 85, 20, 1250, "Chem Thai Co."),
        ("Contact Cement 18L", "adhesive", "can", 40, 15, 980, "Chem Thai Co."),
        ("Hot Press Adhesive 25kg", "adhesive", "bag", 55, 15, 1450, "Adhesive Pro"),
        # Edge banding
        ("Oak Edge Banding 22mm 100m", "edge_banding", "roll", 120, 30, 380, "Edge Pro"),
        ("Walnut Edge Banding 22mm 100m", "edge_banding", "roll", 65, 20, 520, "Edge Pro"),
        ("Maple Edge Banding 22mm 100m", "edge_banding", "roll", 80, 25, 360, "Edge Pro"),
        ("PVC White Edge 22mm 100m", "edge_banding", "roll", 200, 50, 180, "Edge Pro"),
        ("Cherry Edge Banding 22mm 100m", "edge_banding", "roll", 35, 15, 580, "Edge Pro"),
    ]
    cur.executemany(
        "INSERT INTO materials (name,type,unit,current_stock,reorder_point,unit_cost,supplier) VALUES (?,?,?,?,?,?,?)",
        materials
    )
    conn.commit()

    # Get material IDs
    mats = {row['name']: row['id'] for row in conn.execute("SELECT id, name FROM materials").fetchall()}

    # ── Products ─────────────────────────────────────────────
    products = [
        ("Oak MDF Panel 18mm", "VNR-OAK-18", "Natural oak veneer on 18mm MDF core, sanded & trimmed", "sheet", 1850),
        ("Oak MDF Panel 12mm", "VNR-OAK-12", "Natural oak veneer on 12mm MDF core", "sheet", 1550),
        ("Walnut MDF Panel 18mm", "VNR-WAL-18", "Walnut veneer on 18mm MDF core, premium grade", "sheet", 2400),
        ("Maple Plywood Panel", "VNR-MAP-PLY", "Maple veneer on 15mm plywood core, furniture grade", "sheet", 2100),
        ("Cherry MDF Panel 18mm", "VNR-CHR-18", "Cherry veneer on 18mm MDF, high-end finish", "sheet", 2800),
        ("Teak Particle Board Panel", "VNR-TEK-PB", "Teak veneer on 18mm particle board, export grade", "sheet", 3200),
        ("White Oak MDF Panel", "VNR-WOK-18", "White oak veneer on 18mm MDF, modern style", "sheet", 2050),
        ("Walnut Plywood Panel", "VNR-WAL-PLY", "Walnut veneer on 15mm plywood, cabinet grade", "sheet", 2650),
    ]
    cur.executemany(
        "INSERT INTO products (name,sku,description,unit,selling_price) VALUES (?,?,?,?,?)",
        products
    )
    conn.commit()

    prods = {row['name']: row['id'] for row in conn.execute("SELECT id, name FROM products").fetchall()}

    # ── BOM Entries ──────────────────────────────────────────
    # (product_id, material_id, qty_per_unit, waste_factor)
    bom_entries = [
        # Oak MDF 18mm: 1 MDF sheet + 1 oak veneer + adhesive + edge banding
        (prods["Oak MDF Panel 18mm"], mats["MDF 18mm 4x8ft"], 1.0, 0.02, "One core sheet per panel"),
        (prods["Oak MDF Panel 18mm"], mats["Oak Natural Veneer 4x8ft"], 1.0, 0.08, "Allow 8% veneer waste"),
        (prods["Oak MDF Panel 18mm"], mats["Hot Press Adhesive 25kg"], 0.04, 0.05, "40g adhesive per sheet"),
        (prods["Oak MDF Panel 18mm"], mats["Oak Edge Banding 22mm 100m"], 0.05, 0.10, "~5m edge per 4x8 panel"),

        # Oak MDF 12mm
        (prods["Oak MDF Panel 12mm"], mats["MDF 12mm 4x8ft"], 1.0, 0.02, ""),
        (prods["Oak MDF Panel 12mm"], mats["Oak Natural Veneer 4x8ft"], 1.0, 0.08, ""),
        (prods["Oak MDF Panel 12mm"], mats["Hot Press Adhesive 25kg"], 0.04, 0.05, ""),
        (prods["Oak MDF Panel 12mm"], mats["Oak Edge Banding 22mm 100m"], 0.05, 0.10, ""),

        # Walnut MDF 18mm
        (prods["Walnut MDF Panel 18mm"], mats["MDF 18mm 4x8ft"], 1.0, 0.02, ""),
        (prods["Walnut MDF Panel 18mm"], mats["Walnut Veneer 4x8ft"], 1.0, 0.08, "Walnut requires careful handling"),
        (prods["Walnut MDF Panel 18mm"], mats["Hot Press Adhesive 25kg"], 0.04, 0.05, ""),
        (prods["Walnut MDF Panel 18mm"], mats["Walnut Edge Banding 22mm 100m"], 0.05, 0.10, ""),

        # Maple Plywood
        (prods["Maple Plywood Panel"], mats["Plywood 15mm 4x8ft"], 1.0, 0.03, ""),
        (prods["Maple Plywood Panel"], mats["Maple Veneer 4x8ft"], 1.0, 0.07, ""),
        (prods["Maple Plywood Panel"], mats["Hot Press Adhesive 25kg"], 0.04, 0.05, ""),
        (prods["Maple Plywood Panel"], mats["Maple Edge Banding 22mm 100m"], 0.05, 0.10, ""),

        # Cherry MDF 18mm
        (prods["Cherry MDF Panel 18mm"], mats["MDF 18mm 4x8ft"], 1.0, 0.02, ""),
        (prods["Cherry MDF Panel 18mm"], mats["Cherry Veneer 4x8ft"], 1.0, 0.08, ""),
        (prods["Cherry MDF Panel 18mm"], mats["Hot Press Adhesive 25kg"], 0.04, 0.05, ""),
        (prods["Cherry MDF Panel 18mm"], mats["Cherry Edge Banding 22mm 100m"], 0.05, 0.10, ""),

        # Teak Particle Board
        (prods["Teak Particle Board Panel"], mats["Particle Board 18mm"], 1.0, 0.02, ""),
        (prods["Teak Particle Board Panel"], mats["Teak Veneer 4x8ft"], 1.0, 0.10, "Teak veneer has higher waste"),
        (prods["Teak Particle Board Panel"], mats["Hot Press Adhesive 25kg"], 0.05, 0.05, ""),
        (prods["Teak Particle Board Panel"], mats["Oak Edge Banding 22mm 100m"], 0.05, 0.10, ""),

        # White Oak MDF
        (prods["White Oak MDF Panel"], mats["MDF 18mm 4x8ft"], 1.0, 0.02, ""),
        (prods["White Oak MDF Panel"], mats["White Oak Veneer 4x8ft"], 1.0, 0.08, ""),
        (prods["White Oak MDF Panel"], mats["Hot Press Adhesive 25kg"], 0.04, 0.05, ""),
        (prods["White Oak MDF Panel"], mats["Oak Edge Banding 22mm 100m"], 0.05, 0.10, ""),

        # Walnut Plywood
        (prods["Walnut Plywood Panel"], mats["Plywood 15mm 4x8ft"], 1.0, 0.03, ""),
        (prods["Walnut Plywood Panel"], mats["Walnut Veneer 4x8ft"], 1.0, 0.08, ""),
        (prods["Walnut Plywood Panel"], mats["Hot Press Adhesive 25kg"], 0.04, 0.05, ""),
        (prods["Walnut Plywood Panel"], mats["Walnut Edge Banding 22mm 100m"], 0.05, 0.10, ""),
    ]
    cur.executemany(
        "INSERT INTO bom (product_id,material_id,quantity_per_unit,waste_factor,notes) VALUES (?,?,?,?,?)",
        bom_entries
    )
    conn.commit()

    # ── Machines ─────────────────────────────────────────────
    machines = [
        ("Hot Press Line 1", "hot_press", 120, "active", "2025-12-15", "2026-04-15"),
        ("Hot Press Line 2", "hot_press", 120, "active", "2026-01-20", "2026-05-20"),
        ("Cold Press Line 1", "cold_press", 80, "active", "2026-02-10", "2026-06-10"),
        ("CNC Trimmer 1", "trimmer", 200, "active", "2026-01-05", "2026-04-05"),
        ("CNC Trimmer 2", "trimmer", 200, "maintenance", "2026-03-01", "2026-04-20"),
        ("Wide Belt Sander 1", "sander", 180, "active", "2026-02-28", "2026-05-28"),
        ("Edge Bander 1", "edge_bander", 150, "active", "2026-01-15", "2026-04-30"),
        ("Edge Bander 2", "edge_bander", 150, "active", "2026-02-20", "2026-05-20"),
    ]
    cur.executemany(
        "INSERT INTO machines (name,type,capacity_per_shift,status,last_maintenance,next_maintenance) VALUES (?,?,?,?,?,?)",
        machines
    )
    conn.commit()

    machs = {row['name']: row['id'] for row in conn.execute("SELECT id, name FROM machines").fetchall()}

    # ── Orders ───────────────────────────────────────────────
    today = date.today()
    orders = [
        ("ORD-2026-001", "Siam Furniture Co.", prods["Oak MDF Panel 18mm"], 500, 320, (today + timedelta(days=5)).isoformat(), "in_progress", 1, "Rush order — furniture expo"),
        ("ORD-2026-002", "Bangkok Interiors", prods["Walnut MDF Panel 18mm"], 200, 80, (today + timedelta(days=10)).isoformat(), "in_progress", 2, ""),
        ("ORD-2026-003", "CM Cabinet Works", prods["Maple Plywood Panel"], 350, 0, (today + timedelta(days=14)).isoformat(), "pending", 3, "Standard order"),
        ("ORD-2026-004", "Export Pacific Ltd.", prods["Teak Particle Board Panel"], 1000, 0, (today + timedelta(days=21)).isoformat(), "pending", 2, "Export to Japan"),
        ("ORD-2026-005", "Luxury Homes Dev.", prods["Cherry MDF Panel 18mm"], 150, 50, (today + timedelta(days=7)).isoformat(), "in_progress", 1, "High-end residential project"),
        ("ORD-2026-006", "Office Fit Co.", prods["White Oak MDF Panel"], 400, 0, (today + timedelta(days=18)).isoformat(), "pending", 3, "Office renovation"),
        ("ORD-2026-007", "Siam Furniture Co.", prods["Oak MDF Panel 12mm"], 600, 150, (today + timedelta(days=12)).isoformat(), "in_progress", 2, "Second batch"),
        ("ORD-2026-008", "Phuket Villas Ltd.", prods["Walnut Plywood Panel"], 80, 0, (today + timedelta(days=30)).isoformat(), "pending", 4, "Villa project"),
    ]
    cur.executemany(
        "INSERT INTO orders (order_number,customer,product_id,quantity,produced_qty,due_date,status,priority,notes) VALUES (?,?,?,?,?,?,?,?,?)",
        orders
    )
    conn.commit()

    order_ids = {row['order_number']: row['id'] for row in conn.execute("SELECT id, order_number FROM orders").fetchall()}

    # ── Production Logs (last 7 days) ─────────────────────────
    random.seed(42)
    shifts = ["morning", "afternoon"]
    log_entries = []

    for day_offset in range(7, 0, -1):
        log_date = (today - timedelta(days=day_offset)).isoformat()
        # Morning shift: Hot Press Line 1 — Oak panels
        planned = 60
        actual = random.randint(48, 62)
        downtime = max(0, (60 - actual) * 4)
        log_entries.append((
            log_date, "morning",
            prods["Oak MDF Panel 18mm"], machs["Hot Press Line 1"],
            order_ids["ORD-2026-001"], planned, actual, downtime,
            "Minor adhesive feed issue" if downtime > 20 else "",
            4, '{"1": ' + str(round(actual*1.02, 1)) + ', "5": ' + str(round(actual*1.08, 1)) + '}',
            ""
        ))
        # Afternoon: Hot Press Line 1 — Oak panels
        planned = 58
        actual = random.randint(44, 60)
        downtime = max(0, (58 - actual) * 4)
        log_entries.append((
            log_date, "afternoon",
            prods["Oak MDF Panel 18mm"], machs["Hot Press Line 1"],
            order_ids["ORD-2026-001"], planned, actual, downtime,
            "Temperature calibration" if downtime > 25 else "",
            3, '{}', ""
        ))
        # Morning: Hot Press Line 2 — Walnut panels
        planned = 30
        actual = random.randint(22, 32)
        downtime = max(0, (30 - actual) * 5)
        log_entries.append((
            log_date, "morning",
            prods["Walnut MDF Panel 18mm"], machs["Hot Press Line 2"],
            order_ids["ORD-2026-002"], planned, actual, downtime,
            "" , 3, '{}', ""
        ))
        # Afternoon: Edge Bander 1 — Oak panels
        planned = 80
        actual = random.randint(65, 85)
        log_entries.append((
            log_date, "afternoon",
            prods["Oak MDF Panel 18mm"], machs["Edge Bander 1"],
            order_ids["ORD-2026-001"], planned, actual, 0, "", 2, '{}', ""
        ))
        # Morning: Cherry panels
        planned = 20
        actual = random.randint(14, 22)
        downtime = max(0, (20 - actual) * 6)
        log_entries.append((
            log_date, "morning",
            prods["Cherry MDF Panel 18mm"], machs["Hot Press Line 2"],
            order_ids["ORD-2026-005"], planned, actual, downtime,
            "Veneer alignment check" if downtime > 15 else "",
            2, '{}', ""
        ))

    cur.executemany(
        """INSERT INTO production_logs
           (log_date,shift,product_id,machine_id,order_id,planned_qty,actual_qty,
            downtime_minutes,downtime_reason,operator_count,material_usage,notes)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
        log_entries
    )
    conn.commit()
    conn.close()

    print("Seed data loaded successfully:")
    print(f"  - {len(materials)} materials")
    print(f"  - {len(products)} products")
    print(f"  - {len(bom_entries)} BOM entries")
    print(f"  - {len(machines)} machines")
    print(f"  - {len(orders)} orders")
    print(f"  - {len(log_entries)} production log entries (last 7 days)")


if __name__ == "__main__":
    seed()
