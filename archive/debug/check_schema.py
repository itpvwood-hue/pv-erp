import sqlite3
conn = sqlite3.connect('erp.db')
for tbl in ['skus', 'batches', 'laminating_records', 'grading_records', 'sanding_records', 'repair_records']:
    print(f'\n=== {tbl} ===')
    for row in conn.execute(f'PRAGMA table_info({tbl})').fetchall():
        print(f'  {row[1]:25} {row[2]:15} {"NOT NULL" if row[3] else ""}  {"PK" if row[5] else ""}')
conn.close()
