"""
cleanup.py
1. Delete all test material rows (id 19-36, no real code)
2. Delete all test products (VNR-* prefix) and their BOM rows
3. Reclassify consumable → packing for packing materials
4. Remove edge_banding type (those rows already deleted)
5. Add 'packing' as a valid category in the UI (handled in frontend)
"""
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "erp.db"
conn = sqlite3.connect(DB_PATH)
conn.execute("PRAGMA foreign_keys = OFF")  # allow cascade-less deletes

# ── 1. Delete test BOM rows (linked to test products) ─────────────────────────
test_prod_ids = [9,10,11,12,13,14,15,16]
cur = conn.execute(f"DELETE FROM bom WHERE product_id IN ({','.join(str(i) for i in test_prod_ids)})")
print(f"Deleted {cur.rowcount} test BOM rows")

# ── 2. Delete test orders linked to test products ─────────────────────────────
for tbl in ['orders','production_orders']:
    try:
        cur = conn.execute(f"DELETE FROM {tbl} WHERE product_id IN ({','.join(str(i) for i in test_prod_ids)})")
        print(f"Deleted {cur.rowcount} rows from {tbl}")
    except Exception as e:
        print(f"  {tbl}: {e}")

# ── 3. Delete test products (VNR-* prefix) ────────────────────────────────────
cur = conn.execute("DELETE FROM products WHERE sku LIKE 'VNR-%'")
print(f"Deleted {cur.rowcount} test products (VNR-*)")

# ── 4. Delete test materials (id 19-36, no code) ─────────────────────────────
cur = conn.execute("DELETE FROM materials WHERE id BETWEEN 19 AND 36")
print(f"Deleted {cur.rowcount} test material rows (id 19-36)")

# ── 5. Retype consumables: packing vs non-packing ────────────────────────────
# CON-PAK-* and packing-related codes → type='packing'
packing_codes = [
    'CON-PAK-001','CON-PAK-002','CON-PAK-003','CON-PAK-004','CON-PAK-005',
    'CON-PAK-006','CON-PAK-007','CON-PAK-008','CON-PAK-009','CON-PAK-010',
    'CON-PAK-011','CON-PAK-012',
    'KT125',          # bottom liner
]
# also Thai-coded packing items
thai_packing = ['05-1พต003','05-1ฟย001','05-1กล232','05-1กล059','05-1ลพ001']

all_packing = packing_codes + thai_packing
placeholders = ','.join('?' for _ in all_packing)
cur = conn.execute(f"UPDATE materials SET type='packing' WHERE code IN ({placeholders})", all_packing)
print(f"Retyped {cur.rowcount} consumables -> packing")

# Anything still 'consumable' stays consumable (non-packing items like pallets, nails etc)
# Check what's left
remaining = conn.execute("SELECT code, name FROM materials WHERE type='consumable'").fetchall()
print(f"Remaining 'consumable' type: {len(remaining)}")
for r in remaining:
    print(f"  {r[0]} | {(r[1] or '').encode('ascii','replace').decode()[:50]}")

# ── 6. Move anything still 'packing' type from old packaging → packing ───────
cur = conn.execute("UPDATE materials SET type='packing' WHERE type='packaging'")
print(f"Retyped {cur.rowcount} old 'packaging' -> 'packing'")

conn.commit()

# ── 7. Verify final state ─────────────────────────────────────────────────────
print("\nFinal material type counts:")
for r in conn.execute("SELECT type, COUNT(*) n FROM materials GROUP BY type ORDER BY n DESC").fetchall():
    print(f"  {r[0]:<20} {r[1]}")

print(f"\nProducts total: {conn.execute('SELECT COUNT(*) FROM products').fetchone()[0]}")
print(f"Materials total: {conn.execute('SELECT COUNT(*) FROM materials').fetchone()[0]}")
print(f"BOM rows total: {conn.execute('SELECT COUNT(*) FROM bom').fetchone()[0]}")

conn.execute("PRAGMA foreign_keys = ON")
conn.close()
print("\nDone.")
