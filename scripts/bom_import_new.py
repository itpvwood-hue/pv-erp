"""
BOM Import — pv_erp_bom_migration.zip
Imports: 40 new FG SKUs, 49 new materials, 10 packing SKUs,
         5 compound SKUs, 91 packing lines, 121 BOM lines
Run from: execution/
"""

import sqlite3, csv, io, zipfile, os, sys

ZIP_PATH = r"C:\Users\PV_Natthapat\Downloads\pv_erp_bom_migration.zip"
DB_PATH  = os.path.join(os.path.dirname(__file__), '..', 'erp.db')

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn

def read_csv(z, name):
    data = z.read('pv_erp_migration/data_ds/' + name).decode('utf-8-sig')
    return list(csv.DictReader(io.StringIO(data)))

def to_f(v):
    try: return float(v) if v and str(v).strip() else None
    except: return None

def to_i(v, default=0):
    try: return int(float(v)) if v and str(v).strip() else default
    except: return default

def main():
    conn = get_db()

    with zipfile.ZipFile(ZIP_PATH, 'r') as z:
        materials     = read_csv(z, 'scraped_materials.csv')
        compound_skus = read_csv(z, 'scraped_compound_skus.csv')
        compound_lines= read_csv(z, 'scraped_compound_lines.csv')
        packing_skus  = read_csv(z, 'scraped_packing_skus.csv')
        packing_lines = read_csv(z, 'scraped_packing_lines.csv')
        board_skus    = read_csv(z, 'scraped_board_skus.csv')
        bom_lines     = read_csv(z, 'scraped_bom_lines.csv')

    # ── Step 1: Materials ───────────────────────────────────────────────────
    print("Step 1: Importing materials ...")
    ins = skip = 0
    for m in materials:
        code = m['code'].strip()
        if not code:
            continue
        existing = conn.execute("SELECT id FROM materials WHERE code=?", (code,)).fetchone()
        if existing:
            skip += 1
            continue
        # Determine type from code prefix
        c = code.upper()
        if c.startswith('BMC'):
            mat_type = 'core_board'
        elif c.startswith('X'):
            mat_type = 'veneer_sheet'
        elif c.startswith('GLUE') or c.startswith('GLU') or 'GLUE' in c.upper():
            mat_type = 'glue_formula'
        elif c.startswith('CON-PAK') or c.startswith('PKG') or c.startswith('PAK'):
            mat_type = 'packing'
        else:
            mat_type = 'other'
        conn.execute("""
            INSERT INTO materials (code, name, type, unit, price, is_active)
            VALUES (?,?,?,?,?,1)
        """, (code,
              m.get('description','') or m.get('name_th','') or code,
              mat_type,
              m.get('unit','sheet') or 'sheet',
              to_f(m.get('price','')) or 0))
        ins += 1
    conn.commit()
    print(f"  Materials: {ins} inserted, {skip} already exist")

    # ── Step 2: Compound SKUs (glue formulas) ──────────────────────────────
    print("Step 2: Importing compound SKUs ...")
    ins = skip = 0
    for c in compound_skus:
        code = c['code'].strip()
        if not code:
            continue
        existing = conn.execute("SELECT id FROM compound_skus WHERE code=?", (code,)).fetchone()
        if existing:
            skip += 1
            continue
        conn.execute("""
            INSERT INTO compound_skus (code, name, batch_kg, notes, is_active)
            VALUES (?,?,?,?,1)
        """, (code, c.get('name','') or code, to_f(c.get('batch_kg','')), c.get('notes','')))
        ins += 1
    conn.commit()
    print(f"  Compound SKUs: {ins} inserted, {skip} already exist")

    # ── Step 3: Compound lines ──────────────────────────────────────────────
    print("Step 3: Importing compound lines ...")
    ins = skip = err = 0
    for cl in compound_lines:
        csk_code = cl['compound_sku_code'].strip()
        mat_code = cl['material_code'].strip()
        csk = conn.execute("SELECT id FROM compound_skus WHERE code=?", (csk_code,)).fetchone()
        mat = conn.execute("SELECT id FROM materials WHERE code=?", (mat_code,)).fetchone()
        if not csk or not mat:
            print(f"  WARN: compound line {csk_code}/{mat_code} not found, skipping")
            err += 1
            continue
        existing = conn.execute(
            "SELECT id FROM compound_lines WHERE compound_sku_id=? AND material_id=?",
            (csk['id'], mat['id'])).fetchone()
        if existing:
            skip += 1
            continue
        conn.execute("""
            INSERT INTO compound_lines (compound_sku_id, material_id, ratio, unit, notes)
            VALUES (?,?,?,?,?)
        """, (csk['id'], mat['id'], to_f(cl.get('ratio','')), cl.get('unit',''), cl.get('notes','')))
        ins += 1
    conn.commit()
    print(f"  Compound lines: {ins} inserted, {skip} exist, {err} errors")

    # ── Step 4: Packing SKUs ────────────────────────────────────────────────
    print("Step 4: Importing packing SKUs ...")
    ins = skip = 0
    for p in packing_skus:
        code = p['code'].strip()
        if not code:
            continue
        existing = conn.execute("SELECT id FROM packing_skus WHERE code=?", (code,)).fetchone()
        if existing:
            skip += 1
            continue
        conn.execute("""
            INSERT INTO packing_skus (code, name, customer, notes, is_active)
            VALUES (?,?,?,?,1)
        """, (code, p.get('name','') or code, p.get('customer',''), p.get('notes','')))
        ins += 1
    conn.commit()
    print(f"  Packing SKUs: {ins} inserted, {skip} already exist")

    # ── Step 5: Packing lines ───────────────────────────────────────────────
    print("Step 5: Importing packing lines ...")
    ins = skip = err = 0
    for pl in packing_lines:
        psk_code = pl['packing_sku_code'].strip()
        mat_code = pl['material_code'].strip()
        psk = conn.execute("SELECT id FROM packing_skus WHERE code=?", (psk_code,)).fetchone()
        mat = conn.execute("SELECT id FROM materials WHERE code=?", (mat_code,)).fetchone()
        if not psk or not mat:
            print(f"  WARN: packing line {psk_code}/{mat_code} not resolved, skipping")
            err += 1
            continue
        existing = conn.execute(
            "SELECT id FROM packing_lines WHERE packing_sku_id=? AND material_id=?",
            (psk['id'], mat['id'])).fetchone()
        if existing:
            skip += 1
            continue
        conn.execute("""
            INSERT INTO packing_lines (packing_sku_id, material_id, seq, qty, qty_unit, notes)
            VALUES (?,?,?,?,?,?)
        """, (psk['id'], mat['id'], to_i(pl.get('seq',0)), to_f(pl.get('qty','')) or 1,
              pl.get('qty_unit',''), pl.get('notes','')))
        ins += 1
    conn.commit()
    print(f"  Packing lines: {ins} inserted, {skip} exist, {err} errors")

    # ── Step 6: FG SKUs ─────────────────────────────────────────────────────
    print("Step 6: Importing FG SKUs ...")
    ins = skip = 0
    grp = conn.execute("SELECT id FROM bom_groups WHERE name='Core Materials'").fetchone()
    grp_id = grp[0] if grp else 1

    for s in board_skus:
        code = s['code'].strip()
        if not code:
            continue
        existing = conn.execute("SELECT id FROM skus WHERE code=?", (code,)).fetchone()
        if existing:
            skip += 1
            continue

        # Resolve packing_sku_id
        packing_id = None
        psk_code = s.get('packing_sku_code','').strip()
        if psk_code:
            row = conn.execute("SELECT id FROM packing_skus WHERE code=?", (psk_code,)).fetchone()
            if row:
                packing_id = row[0]

        conn.execute("""
            INSERT INTO skus (code, name, thickness_mm, width_mm, length_mm,
                              pallet_qty, packing_sku_id, is_active)
            VALUES (?,?,?,?,?,?,?,1)
        """, (code, s.get('name','') or code,
              to_f(s.get('thickness_mm','')),
              to_f(s.get('width_mm','')),
              to_f(s.get('length_mm','')),
              to_i(s.get('pallet_qty',''), 0),
              packing_id))
        ins += 1

    conn.commit()
    print(f"  FG SKUs: {ins} inserted, {skip} already exist")

    # ── Step 7: BOM lines ───────────────────────────────────────────────────
    print("Step 7: Importing BOM lines ...")
    ins = skip = err = 0

    for bl in bom_lines:
        sku_code = bl['sku_code'].strip()
        mat_code = bl['material_code'].strip()
        seq_raw  = to_i(bl.get('seq', 0))
        qty_ov   = to_f(bl.get('qty_override',''))
        usage_g  = to_f(bl.get('usage_g_per_face',''))
        qty_unit = bl.get('qty_unit','')

        sku_row = conn.execute("SELECT id FROM skus WHERE code=?", (sku_code,)).fetchone()
        mat_row = conn.execute("SELECT id, type FROM materials WHERE code=?", (mat_code,)).fetchone()

        if not sku_row:
            print(f"  WARN: SKU {sku_code} not found, skipping")
            err += 1
            continue
        if not mat_row:
            print(f"  WARN: material {mat_code} not found, skipping")
            err += 1
            continue

        sku_id = sku_row[0]
        mat_id = mat_row[0]
        mat_type = mat_row[1]

        # Remap seq: new CSVs use seq 1=board, 2=veneer, 3=glue
        # DB convention: 1=board, 2=face_veneer, 3=back_veneer, 4=face_glue, 5=back_glue
        if usage_g is not None and seq_raw == 3:
            seq = 4   # remap CSV seq 3 (glue) -> DB seq 4 (face_glue)
        else:
            seq = seq_raw

        existing = conn.execute(
            "SELECT id FROM bom_lines WHERE sku_id=? AND material_id=?",
            (sku_id, mat_id)).fetchone()
        if existing:
            skip += 1
            continue

        conn.execute("""
            INSERT INTO bom_lines
              (sku_id, material_id, group_id, seq, qty_override, usage_g_per_face, qty_unit, notes)
            VALUES (?,?,?,?,?,?,?,?)
        """, (sku_id, mat_id, grp_id, seq, qty_ov, usage_g, qty_unit, bl.get('notes','')))
        ins += 1

    conn.commit()
    print(f"  BOM lines: {ins} inserted, {skip} exist, {err} errors")

    # ── Step 8: Sync to legacy products table ──────────────────────────────
    print("Step 8: Syncing FG SKUs to products table ...")
    ins = skip = 0
    for s in board_skus:
        code = s['code'].strip()
        name = s.get('name','') or code
        if not code:
            continue
        existing = conn.execute("SELECT id FROM products WHERE sku=?", (code,)).fetchone()
        if existing:
            skip += 1
            continue
        conn.execute("INSERT INTO products (name, sku) VALUES (?,?)", (name, code))
        ins += 1
    conn.commit()
    print(f"  Products: {ins} inserted, {skip} already exist")

    # ── Summary ─────────────────────────────────────────────────────────────
    print()
    print("=== Final counts ===")
    for tbl in ('materials','compound_skus','compound_lines','packing_skus','packing_lines','skus','bom_lines','products'):
        n = conn.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()[0]
        print(f"  {tbl:20s}: {n}")

    conn.close()
    print("\nDone.")

if __name__ == '__main__':
    main()
