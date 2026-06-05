"""
migrate_materials_schema.py
----------------------------
Adds material-type-specific attribute columns to the materials table:
  Base boards : acc_code, board_type, glue_type, fsc
  Veneers     : acc_code, species, cut_type, matching, grade, face_back, fsc
  (acc_code and fsc are shared; thickness_mm/width_mm/length_mm already exist)
"""
import sqlite3
from pathlib import Path

DB = Path(__file__).parent.parent / 'erp.db'
conn = sqlite3.connect(DB)
conn.execute('PRAGMA journal_mode=WAL')

new_cols = [
    ('acc_code',   'TEXT'),   # accounting / ERP ledger code
    ('board_type', 'TEXT'),   # MDF FS / PlatformQS / Plywood ...
    ('glue_type',  'TEXT'),   # E1 / E2 / CARB P2
    ('fsc',        'TEXT'),   # FSC CW / FSC 100% / -
    ('species',    'TEXT'),   # R.OAK / WALNUT / W.BIRCH ...
    ('cut_type',   'TEXT'),   # PC / RC / RIFT / QC
    ('matching',   'TEXT'),   # BM / PM / SM / Z
    ('grade',      'TEXT'),   # A / AA / B / SOUND ...
    ('face_back',  'TEXT'),   # Face / Back / None
]

for col, ctype in new_cols:
    try:
        conn.execute(f'ALTER TABLE materials ADD COLUMN {col} {ctype}')
        print(f'  + materials.{col}')
    except Exception:
        print(f'  · materials.{col} already exists')

conn.commit()
conn.close()
print('Schema migration complete.')
