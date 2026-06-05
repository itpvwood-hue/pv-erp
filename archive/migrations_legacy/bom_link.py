"""
bom_link.py — Link the proper BOM module into the ERP frontend tables.

1. Fix material types for the 111 imported materials
2. Upsert all 77 skus -> products table
3. Sync bom_lines -> bom table (linking product_id + material_id)

Run: python bom_link.py
"""
import sqlite3, os, re
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "erp.db"
conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row
conn.execute("PRAGMA foreign_keys = ON")
conn.execute("PRAGMA journal_mode = WAL")

print(f"Connected to {DB_PATH}\n")

# ── Step 1: Fix material types based on code prefix ────────────────────────────
print("Step 1: Fixing material types ...")

def infer_type(code, unit):
    c = (code or '').upper()
    u = (unit or '').lower()
    if re.match(r'^(BMC|BVC|BXC|BF1|BPC|BSC)', c): return 'core_board'
    if c.startswith('X') and len(c) >= 6:           return 'veneer_sheet'
    if re.match(r'^GLUE-', c, re.IGNORECASE):       return 'adhesive'
    if re.match(r'^(UREA|LATEX|WHEAT|TITAN|OXIDE|FLUOR)', c): return 'adhesive'
    if re.match(r'^CON-PAK', c):                    return 'packaging'
    if u == 'pallet':                               return 'packaging'
    if u == 'face' or u == 'sheet':                 return 'veneer_sheet'
    return 'consumable'

rows = conn.execute("SELECT id, code, unit, type FROM materials WHERE type='other'").fetchall()
updated = 0
for r in rows:
    new_type = infer_type(r['code'], r['unit'])
    conn.execute("UPDATE materials SET type=? WHERE id=?", (new_type, r['id']))
    updated += 1

conn.commit()
print(f"  Updated {updated} material types")

# Verify
for t in ['core_board','veneer_sheet','adhesive','packaging','consumable']:
    n = conn.execute("SELECT COUNT(*) FROM materials WHERE type=?", (t,)).fetchone()[0]
    print(f"    {t:<15}: {n}")

# ── Step 2: Upsert skus -> products ────────────────────────────────────────────
print("\nStep 2: Syncing skus -> products table ...")

skus = conn.execute("""
    SELECT s.code, s.name, s.thickness_mm, s.width_mm, s.length_mm, s.pallet_qty
    FROM skus s WHERE s.is_active=1
""").fetchall()

ins = upd = 0
for s in skus:
    existing = conn.execute("SELECT id FROM products WHERE sku=?", (s['code'],)).fetchone()
    # Build a clean name if the sku name is long/technical
    name = s['name']
    # unit = pallet
    if existing:
        conn.execute("""UPDATE products SET name=?, description=?, unit=?
            WHERE sku=?""",
            (name, f"{s['thickness_mm']}mm × {s['width_mm']}×{s['length_mm']} — {s['pallet_qty']}pcs/pallet",
             'pallet', s['code']))
        upd += 1
    else:
        conn.execute("""INSERT INTO products (sku, name, description, unit, selling_price)
            VALUES (?,?,?,?,0)""",
            (s['code'], name,
             f"{s['thickness_mm']}mm × {s['width_mm']}×{s['length_mm']} — {s['pallet_qty']}pcs/pallet",
             'pallet'))
        ins += 1

conn.commit()
print(f"  Products: +{ins} inserted, ~{upd} updated  (total: {conn.execute('SELECT COUNT(*) FROM products').fetchone()[0]})")

# ── Step 3: Sync bom_lines -> bom table ────────────────────────────────────────
print("\nStep 3: Syncing bom_lines -> bom table ...")

# Get all bom_lines with sku_code + material_code
bom_lines = conn.execute("""
    SELECT bl.id, bl.seq, bl.qty_override, bl.usage_g_per_face, bl.qty_unit, bl.notes,
           s.code as sku_code, s.pallet_qty,
           m.code as mat_code,
           bl.group_id
    FROM bom_lines bl
    JOIN skus      s ON s.id = bl.sku_id
    JOIN materials m ON m.id = bl.material_id
""").fetchall()

ins = upd = skipped = 0
for bl in bom_lines:
    # Get product_id from products table
    prod = conn.execute("SELECT id FROM products WHERE sku=?", (bl['sku_code'],)).fetchone()
    mat  = conn.execute("SELECT id FROM materials WHERE code=?", (bl['mat_code'],)).fetchone()
    if not prod or not mat:
        skipped += 1; continue

    prod_id = prod[0]; mat_id = mat[0]

    # Determine qty and veneer_role
    if bl['usage_g_per_face'] is not None:
        qty = bl['usage_g_per_face'] / 1000.0  # store as kg per face
        veneer_role = ''
    else:
        qty = bl['qty_override'] if bl['qty_override'] else bl['pallet_qty']
        veneer_role = ''

    # Set veneer_role based on seq (seq 2 = face, seq 3 = back in standard layout)
    mat_code = bl['mat_code'].upper()
    if mat_code.startswith('X'):  # it's a veneer
        veneer_role = 'face' if bl['seq'] == 2 else 'back' if bl['seq'] == 3 else ''

    notes = bl['notes'] or ''

    existing = conn.execute(
        "SELECT id FROM bom WHERE product_id=? AND material_id=? AND veneer_role=?",
        (prod_id, mat_id, veneer_role)).fetchone()

    if existing:
        conn.execute("""UPDATE bom SET quantity_per_unit=?, waste_factor=?, notes=?
            WHERE id=?""", (qty, 0.05, notes, existing[0]))
        upd += 1
    else:
        conn.execute("""INSERT INTO bom (product_id, material_id, quantity_per_unit, waste_factor, veneer_role, notes)
            VALUES (?,?,?,?,?,?)""", (prod_id, mat_id, qty, 0.05, veneer_role, notes))
        ins += 1

conn.commit()
print(f"  BOM entries: +{ins} inserted, ~{upd} updated, {skipped} skipped")
print(f"  Total BOM rows: {conn.execute('SELECT COUNT(*) FROM bom').fetchone()[0]}")

# ── Verify ─────────────────────────────────────────────────────────────────────
print("\nVerification:")
print(f"  products: {conn.execute('SELECT COUNT(*) FROM products').fetchone()[0]}")
print(f"  materials: {conn.execute('SELECT COUNT(*) FROM materials').fetchone()[0]}")
print(f"  bom: {conn.execute('SELECT COUNT(*) FROM bom').fetchone()[0]}")

# Sample BOM for first real SKU
sample_sku = conn.execute("SELECT sku FROM products WHERE sku LIKE '4%' LIMIT 1").fetchone()
if sample_sku:
    sku = sample_sku[0]
    lines = conn.execute("""
        SELECT m.code, m.type, b.quantity_per_unit, b.veneer_role
        FROM bom b JOIN materials m ON m.id=b.material_id
        JOIN products p ON p.id=b.product_id WHERE p.sku=?
    """, (sku,)).fetchall()
    print(f"\n  Sample BOM for {sku} ({len(lines)} lines):")
    for l in lines:
        print(f"    {l['code']:<16} {l['type']:<14} qty={l['quantity_per_unit']} role={l['veneer_role']}")

conn.close()
print("\nDone — restart the server to pick up changes.")
