import sqlite3
conn = sqlite3.connect('erp.db')
rows = conn.execute("SELECT name, type FROM sqlite_master WHERE type IN ('table','view') ORDER BY name").fetchall()
for r in rows:
    print(r[1], r[0])
conn.close()
