"""
Patch: Integrate bulk upload into Materials and BOM pages.
- Adds mode param (add/replace) to upload endpoints
- Adds export endpoints for materials and BOM
- Run once from execution/
"""
import re

MAIN_PATH = 'main.py'

with open(MAIN_PATH, 'r', encoding='utf-8') as f:
    src = f.read()

# ── 1. Add mode param to upload/inventory ────────────────────────────────────
OLD_INV = '''@app.post("/api/upload/inventory")
async def upload_inventory(file: UploadFile = File(...)):
    content = await file.read()
    try:
        text = content.decode('utf-8-sig')
    except Exception:
        text = content.decode('latin-1')
    reader = csv.DictReader(io.StringIO(text))
    results = []; errors = []
    required = {'name'}
    for i, row in enumerate(reader, 1):
        row = {k.strip().lower().replace(' ','_'): v.strip() for k,v in row.items()}
        if not row.get('name'):
            errors.append(f"Row {i}: missing 'name'"); continue
        try:
            r = bulk_upsert_material(row)
            results.append(r)
        except Exception as e:
            errors.append(f"Row {i} ({row.get('name','')}): {str(e)}")
    return {"processed": len(results), "errors": errors, "results": results}'''

NEW_INV = '''@app.post("/api/upload/inventory")
async def upload_inventory(file: UploadFile = File(...), mode: str = "add"):
    """mode=add: upsert (default). mode=replace: delete rows by code then re-insert."""
    content = await file.read()
    try:
        text = content.decode('utf-8-sig')
    except Exception:
        text = content.decode('latin-1')
    rows_csv = list(csv.DictReader(io.StringIO(text)))
    rows_csv = [{k.strip().lower().replace(' ','_'): v.strip() for k,v in r.items()} for r in rows_csv]
    if mode == "replace":
        import sqlite3 as _sq
        from database import DB_PATH as _dp, get_db as _gdb
        conn = _gdb()
        codes = [r['code'] for r in rows_csv if r.get('code')]
        if codes:
            ph = ','.join('?' for _ in codes)
            conn.execute(f"DELETE FROM materials WHERE code IN ({ph})", codes)
            conn.commit()
        conn.close()
    results = []; errors = []
    for i, row in enumerate(rows_csv, 1):
        if not row.get('name'):
            errors.append(f"Row {i}: missing 'name'"); continue
        try:
            r = bulk_upsert_material(row)
            results.append(r)
        except Exception as e:
            errors.append(f"Row {i} ({row.get('name','')}): {str(e)}")
    return {"processed": len(results), "errors": errors, "results": results, "mode": mode}'''

assert OLD_INV in src, "upload/inventory not found"
src = src.replace(OLD_INV, NEW_INV, 1)
print("✓ upload/inventory patched")

# ── 2. Add mode param to upload/bom ─────────────────────────────────────────
OLD_BOM_UPLOAD = '@app.post("/api/upload/bom")\nasync def upload_bom(file: UploadFile = File(...)):'
NEW_BOM_UPLOAD = '@app.post("/api/upload/bom")\nasync def upload_bom(file: UploadFile = File(...), mode: str = "add"):'
assert OLD_BOM_UPLOAD in src, "upload/bom signature not found"
src = src.replace(OLD_BOM_UPLOAD, NEW_BOM_UPLOAD, 1)

# Also replace the return line to include mode
OLD_BOM_RET = '    return {"processed": len(results), "errors": errors, "results": results}\n\n@app.get("/api/upload/template/inventory")'
NEW_BOM_RET = '''    return {"processed": len(results), "errors": errors, "results": results, "mode": mode}

@app.get("/api/export/materials")
def export_materials():
    """Export all materials as CSV."""
    from database import get_all_materials, get_db as _gdb
    conn = _gdb()
    rows = conn.execute("""
        SELECT code, name, type, unit,
               COALESCE(current_stock,0) as current_stock,
               COALESCE(reorder_point,0) as reorder_point,
               COALESCE(price,0) as unit_cost
        FROM materials WHERE type != 'glue_formula' ORDER BY type, code
    """).fetchall()
    conn.close()
    lines = ["code,name,type,unit,current_stock,reorder_point,unit_cost"]
    for r in rows:
        def esc(v): return '"'+str(v or '').replace('"','""')+'"'
        lines.append(f"{esc(r[0])},{esc(r[1])},{esc(r[2])},{esc(r[3])},{r[4]},{r[5]},{r[6]}")
    content = "\\n".join(lines) + "\\n"
    return Response(content=content.encode("utf-8"), media_type="text/csv",
                    headers={"Content-Disposition": "attachment; filename=materials_export.csv"})

@app.get("/api/export/bom")
def export_bom():
    """Export all BOM as flat CSV (one row per FG SKU)."""
    from database import get_structured_bom
    skus = get_structured_bom()
    lines = ["product_sku,sku_name,pieces_per_unit,thickness_mm,width_mm,length_mm,"
             "base_board_code,base_board_qty,"
             "face_veneer_code,face_veneer_qty,"
             "face_glue_code,face_glue_usage_g,"
             "back_veneer_code,back_veneer_qty,"
             "back_glue_code,back_glue_usage_g,"
             "packing_sku_code"]
    def v(x): return str(x) if x is not None else ""
    def esc(x): return '"'+str(x or '').replace('"','""')+'"'
    for s in skus:
        bb = s.get('base_board') or {}
        fv = s.get('face_veneer') or {}
        bv = s.get('back_veneer') or {}
        fg = s.get('face_glue') or {}
        bg = s.get('back_glue') or {}
        pk = s.get('packing') or {}
        lines.append(",".join([
            esc(s['sku_code']), esc(s['sku_name']), v(s['pallet_qty']),
            v(s.get('thickness_mm','')), v(s.get('width_mm','')), v(s.get('length_mm','')),
            esc(bb.get('code','')), v(bb.get('qty','')),
            esc(fv.get('code','')), v(fv.get('qty','')),
            esc(fg.get('code','')), v(fg.get('usage_g_per_face','')),
            esc(bv.get('code','')), v(bv.get('qty','')),
            esc(bg.get('code','')), v(bg.get('usage_g_per_face','')),
            esc(pk.get('code','')),
        ]))
    content = "\\n".join(lines) + "\\n"
    return Response(content=content.encode("utf-8"), media_type="text/csv",
                    headers={"Content-Disposition": "attachment; filename=bom_export.csv"})

@app.get("/api/upload/template/inventory")'''

assert OLD_BOM_RET in src, "bom upload return not found"
src = src.replace(OLD_BOM_RET, NEW_BOM_RET, 1)
print("✓ upload/bom patched + export routes added")

# ── 3. Add mode handling inside upload/bom (replace existing SKU lines) ──────
# Insert replace logic right after the DictReader call in upload_bom
OLD_BOM_READER = '''async def upload_bom(file: UploadFile = File(...), mode: str = "add"):
    content = await file.read()
    try:
        text = content.decode('utf-8-sig')
    except Exception:
        text = content.decode('latin-1')
    reader = csv.DictReader(io.StringIO(text))
    results = []; errors = []
    for i, row in enumerate(reader, 1):
        row = {k.strip().lower().replace(' ','_'): v.strip() for k,v in row.items()}
        sku = row.get('product_sku', '').strip()'''

NEW_BOM_READER = '''async def upload_bom(file: UploadFile = File(...), mode: str = "add"):
    content = await file.read()
    try:
        text = content.decode('utf-8-sig')
    except Exception:
        text = content.decode('latin-1')
    all_rows_raw = list(csv.DictReader(io.StringIO(text)))
    if mode == "replace":
        from database import get_db as _gdb
        conn = _gdb()
        skus_in_csv = [r.get('product_sku','').strip() for r in all_rows_raw if r.get('product_sku','').strip()]
        for sku_code in set(skus_in_csv):
            prod = conn.execute("SELECT id FROM products WHERE sku=?", (sku_code,)).fetchone()
            if prod:
                conn.execute("DELETE FROM bom WHERE product_id=?", (prod['id'],))
        conn.commit(); conn.close()
    results = []; errors = []
    for i, row in enumerate(all_rows_raw, 1):
        row = {k.strip().lower().replace(' ','_'): v.strip() for k,v in row.items()}
        sku = row.get('product_sku', '').strip()'''

assert OLD_BOM_READER in src, "bom reader block not found"
src = src.replace(OLD_BOM_READER, NEW_BOM_READER, 1)
print("✓ upload/bom replace mode added")

with open(MAIN_PATH, 'w', encoding='utf-8') as f:
    f.write(src)
print("main.py saved.")
