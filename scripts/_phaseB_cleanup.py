"""Phase B cleanup migration — atomic, idempotent.

End state:
- All glue_formula placeholder material rows removed.
- All 'Glue N' BOM links go through bom.glue_recipe_id / bom_lines.glue_recipe_id.
- Garbage / empty glue_recipes deleted (with their FG products + BOM lines).
- Duplicate Glue 2 merged.
- Legacy compound_skus / compound_lines tables + compound_cost view dropped.
- core_bom, bom_full, bom_cost_summary views recreated for the new schema.

Run from project root:  python scripts/_phaseB_cleanup.py
"""
import os, sys, io, sqlite3

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'erp.db')

c = sqlite3.connect(DB_PATH)
c.execute('PRAGMA foreign_keys = OFF')


def has_table(name):
    return bool(c.execute(
        "SELECT name FROM sqlite_master WHERE type IN ('table','view') AND name=?",
        (name,)).fetchone())


# ─────────────────────────────────────────────────────────────────
# Step 1 — Drop garbage glue_recipes + their FG products + BOMs
# ─────────────────────────────────────────────────────────────────
# Garbage = (a) recipes with 0 total_kg and 0 BOM refs (empty placeholders),
#           (b) recipes with 0 total_kg AND no material_links (truly empty)
# A recipe with kg amounts + links is KEEP even if not referenced.
garbage_rids = []
import json
for r in c.execute('SELECT id, recipe_code, total_kg, material_links FROM glue_recipes'):
    try:
        links = json.loads(r[3] or '{}')
    except Exception:
        links = {}
    if float(r[2] or 0) == 0 and not links:
        garbage_rids.append(r[0])
print('Step 1: garbage recipes (no kg + no links): ' + str(garbage_rids))

# FG products to delete: those whose BOM links to a garbage recipe
prob_fg_ids = set()
if garbage_rids:
    ph = ','.join('?' for _ in garbage_rids)
    for r in c.execute('SELECT DISTINCT product_id FROM bom WHERE glue_recipe_id IN (' + ph + ')',
                       garbage_rids):
        prob_fg_ids.add(r[0])
print('Step 1: FG products to delete: ' + str(sorted(prob_fg_ids)))

del_counts = {'bom_lines':0, 'bom':0, 'products':0, 'po_lines':0, 'orders':0,
              'production_orders':0}
for fid in prob_fg_ids:
    cur = c.execute('DELETE FROM bom_lines WHERE sku_id IN (SELECT id FROM bom WHERE product_id=?)', (fid,))
    del_counts['bom_lines'] += cur.rowcount
    cur = c.execute('DELETE FROM bom WHERE product_id=?', (fid,))
    del_counts['bom'] += cur.rowcount
    for tbl in ('po_lines', 'orders', 'production_orders'):
        try:
            cur = c.execute('DELETE FROM ' + tbl + ' WHERE product_id=?', (fid,))
            del_counts[tbl] += cur.rowcount
        except sqlite3.OperationalError:
            pass
    cur = c.execute('DELETE FROM products WHERE id=?', (fid,))
    del_counts['products'] += cur.rowcount
print('Step 1: cascade delete: ' + str(del_counts))

for rid in garbage_rids:
    c.execute('DELETE FROM glue_recipes WHERE id=?', (rid,))
print('Step 1: deleted ' + str(len(garbage_rids)) + ' garbage recipes')


# ─────────────────────────────────────────────────────────────────
# Step 2 — Delete garbage placeholder materials with fake prices
# ─────────────────────────────────────────────────────────────────
# Glue 18 / Glue 25 had fake hand-edited prices (980 / 1450) and no real recipe.
# Duplicate Glue 2: keep id 29 (the one with stock), delete id 100 (zero stock).
garbage_mat_ids = []
for r in c.execute('''SELECT id, code, name, price FROM materials
                       WHERE type='glue_formula'
                         AND (
                            (code IN ('Glue 18','Glue 25'))
                            OR (code='Glue 2' AND current_stock=0)
                         )'''):
    garbage_mat_ids.append(r[0])
print('Step 2: garbage placeholder material ids: ' + str(garbage_mat_ids))
if garbage_mat_ids:
    ph = ','.join('?' for _ in garbage_mat_ids)
    for tbl, col in [('compound_lines','material_id'), ('compound_skus','base_material_id'),
                     ('consumable_request','material_id'), ('purchase_requests','material_id'),
                     ('station_stock','material_id'), ('station_stock_movements','material_id'),
                     ('material_documents','material_id'), ('material_lots','material_id'),
                     ('material_movements','material_id'), ('batch_material_lots','material_id')]:
        if has_table(tbl):
            try:
                cur = c.execute('DELETE FROM ' + tbl + ' WHERE ' + col + ' IN (' + ph + ')', garbage_mat_ids)
                if cur.rowcount: print('  cleaned ' + str(cur.rowcount) + ' from ' + tbl)
            except sqlite3.OperationalError:
                pass
    cur = c.execute('DELETE FROM materials WHERE id IN (' + ph + ')', garbage_mat_ids)
    print('Step 2: deleted ' + str(cur.rowcount) + ' garbage placeholder material rows')


# ─────────────────────────────────────────────────────────────────
# Step 3 — Drop dependent views before rebuilding bom_lines
# ─────────────────────────────────────────────────────────────────
for v in ('bom_cost_summary', 'bom_full', 'core_bom'):
    c.execute('DROP VIEW IF EXISTS ' + v)
print('Step 3: dropped views (will recreate at end)')


# ─────────────────────────────────────────────────────────────────
# Step 4 — Rebuild bom + bom_lines with nullable material_id
# ─────────────────────────────────────────────────────────────────
def make_nullable_bom_lines():
    """Recreate bom_lines so material_id is nullable, dropping UNIQUE on material_id."""
    cols = c.execute('PRAGMA table_info(bom_lines)').fetchall()
    if not any(col[1] == 'material_id' and col[3] == 1 for col in cols):
        return False
    c.execute('DROP TABLE IF EXISTS bom_lines_tmp')
    c.executescript('''
        CREATE TABLE bom_lines_tmp (
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
            UNIQUE (sku_id, seq),
            CHECK (NOT (qty_override IS NOT NULL AND usage_g_per_face IS NOT NULL)),
            CHECK (material_id IS NOT NULL OR glue_recipe_id IS NOT NULL)
        );
        INSERT INTO bom_lines_tmp
          SELECT id, sku_id, material_id, glue_recipe_id, group_id, seq, qty_override,
                 usage_g_per_face, qty_unit, notes, created_at, updated_at FROM bom_lines;
        DROP TABLE bom_lines;
        ALTER TABLE bom_lines_tmp RENAME TO bom_lines;
        CREATE INDEX IF NOT EXISTS idx_bl_sku         ON bom_lines(sku_id);
        CREATE INDEX IF NOT EXISTS idx_bl_glue_recipe ON bom_lines(glue_recipe_id);
    ''')
    return True


def make_nullable_bom():
    cols = c.execute('PRAGMA table_info(bom)').fetchall()
    if not any(col[1] == 'material_id' and col[3] == 1 for col in cols):
        return False
    c.execute('DROP TABLE IF EXISTS bom_tmp')
    c.executescript('''
        CREATE TABLE bom_tmp (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER NOT NULL,
            material_id INTEGER,
            glue_recipe_id INTEGER,
            quantity_per_unit REAL NOT NULL,
            waste_factor REAL DEFAULT 0.05,
            notes TEXT,
            veneer_role TEXT DEFAULT '',
            FOREIGN KEY (product_id)     REFERENCES products(id)       ON DELETE CASCADE,
            FOREIGN KEY (material_id)    REFERENCES materials(id),
            FOREIGN KEY (glue_recipe_id) REFERENCES glue_recipes(id)
        );
        INSERT INTO bom_tmp (id, product_id, material_id, glue_recipe_id, quantity_per_unit, waste_factor, notes, veneer_role)
          SELECT id, product_id, material_id, glue_recipe_id, quantity_per_unit, waste_factor, notes, veneer_role FROM bom;
        DROP TABLE bom;
        ALTER TABLE bom_tmp RENAME TO bom;
        CREATE INDEX IF NOT EXISTS idx_bom_product      ON bom(product_id);
        CREATE INDEX IF NOT EXISTS idx_bom_glue_recipe  ON bom(glue_recipe_id);
    ''')
    return True

if make_nullable_bom():
    print('Step 4: rebuilt bom (material_id nullable)')
if make_nullable_bom_lines():
    print('Step 4: rebuilt bom_lines (material_id nullable)')


# ─────────────────────────────────────────────────────────────────
# Step 5 — NULL placeholder material_id refs + delete placeholders
# ─────────────────────────────────────────────────────────────────
gids = [r[0] for r in c.execute(
    "SELECT id FROM materials WHERE type='glue_formula'").fetchall()]
print('Step 5: glue_formula placeholders remaining: ' + str(len(gids)))
if gids:
    ph = ','.join('?' for _ in gids)
    for tbl in ('bom', 'bom_lines'):
        cur = c.execute(
            'UPDATE ' + tbl + ' SET material_id=NULL '
            'WHERE material_id IN (' + ph + ') AND glue_recipe_id IS NOT NULL', gids)
        print('  ' + tbl + ': NULLed ' + str(cur.rowcount) + ' refs')
    for tbl, col in [('compound_lines','material_id'),
                     ('station_stock','material_id'), ('station_stock_movements','material_id'),
                     ('consumable_request','material_id'), ('purchase_requests','material_id'),
                     ('material_documents','material_id'), ('material_lots','material_id'),
                     ('material_movements','material_id'), ('batch_material_lots','material_id')]:
        if has_table(tbl):
            try:
                cur = c.execute('DELETE FROM ' + tbl + ' WHERE ' + col + ' IN (' + ph + ')', gids)
                if cur.rowcount: print('  cleaned ' + str(cur.rowcount) + ' from ' + tbl)
            except sqlite3.OperationalError:
                pass
    cur = c.execute('DELETE FROM materials WHERE id IN (' + ph + ')', gids)
    print('Step 5: deleted ' + str(cur.rowcount) + ' placeholder material rows')


# ─────────────────────────────────────────────────────────────────
# Step 6 — Drop legacy compound_* tables + view
# ─────────────────────────────────────────────────────────────────
c.execute('DROP VIEW IF EXISTS compound_cost')
c.execute('DROP TABLE IF EXISTS compound_lines')
c.execute('DROP TABLE IF EXISTS compound_skus')
print('Step 6: dropped compound_cost / compound_lines / compound_skus')


# ─────────────────────────────────────────────────────────────────
# Step 7 — Recreate views
# ─────────────────────────────────────────────────────────────────
c.execute('''
    CREATE VIEW core_bom AS
    SELECT s.code AS sku_code, s.name AS sku_name, s.pallet_qty,
           bl.seq,
           COALESCE(m.code, gr.recipe_code, '')   AS mat_code,
           COALESCE(m.name_th, '')                AS name_th,
           COALESCE(m.name, gr.name, '')          AS mat_name,
           COALESCE(m.unit, 'kg')                 AS unit,
           COALESCE(m.price, 0)                   AS unit_price,
           CASE WHEN bl.usage_g_per_face IS NOT NULL THEN s.pallet_qty
                ELSE COALESCE(bl.qty_override, s.pallet_qty) END AS qty,
           CASE WHEN bl.usage_g_per_face IS NOT NULL
                THEN COALESCE(bl.qty_unit, 'g/face')
                ELSE COALESCE(bl.qty_unit, m.unit, 'kg') END AS qty_unit,
           bl.usage_g_per_face,
           ROUND(CASE WHEN bl.usage_g_per_face IS NOT NULL
                THEN COALESCE(m.price, 0) * (bl.usage_g_per_face / 1000.0) * s.pallet_qty
                ELSE COALESCE(m.price, 0) * COALESCE(bl.qty_override, s.pallet_qty) END, 4) AS line_cost,
           sp.name AS supplier,
           bl.id   AS bom_line_id
    FROM bom_lines bl
    JOIN      skus       s  ON s.id  = bl.sku_id
    JOIN      bom_groups bg ON bg.id = bl.group_id
    LEFT JOIN materials    m  ON m.id  = bl.material_id
    LEFT JOIN glue_recipes gr ON gr.id = bl.glue_recipe_id
    LEFT JOIN suppliers    sp ON sp.id = m.supplier_id
    ORDER BY s.code, bl.seq
''')
c.execute('''
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
''')
c.execute('''
    CREATE VIEW bom_cost_summary AS
    SELECT sku_code, sku_name, pallet_qty, section,
        ROUND(SUM(line_cost), 4) AS section_total
    FROM bom_full
    GROUP BY sku_code, section
''')
print('Step 7: recreated core_bom + bom_full + bom_cost_summary')


c.commit()

print()
print('FINAL STATE:')
print('  glue_formula materials: ' + str(c.execute("SELECT COUNT(*) FROM materials WHERE type='glue_formula'").fetchone()[0]))
print('  glue_recipes:           ' + str(c.execute('SELECT COUNT(*) FROM glue_recipes').fetchone()[0]))
print('  bom rows:               ' + str(c.execute('SELECT COUNT(*) FROM bom').fetchone()[0]))
print('  bom_lines:              ' + str(c.execute('SELECT COUNT(*) FROM bom_lines').fetchone()[0]))
print('  bom_lines material-link:' + str(c.execute('SELECT COUNT(*) FROM bom_lines WHERE material_id IS NOT NULL').fetchone()[0]))
print('  bom_lines glue-link:    ' + str(c.execute('SELECT COUNT(*) FROM bom_lines WHERE glue_recipe_id IS NOT NULL').fetchone()[0]))
print('  bom glue-link:          ' + str(c.execute('SELECT COUNT(*) FROM bom WHERE glue_recipe_id IS NOT NULL').fetchone()[0]))
print('  core_bom rows:          ' + str(c.execute('SELECT COUNT(*) FROM core_bom').fetchone()[0]))
print('  compound_skus dropped:  ' + str(not has_table('compound_skus')))
c.close()
