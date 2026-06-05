import sqlite3, os
DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'erp.db')
conn = sqlite3.connect(DB_PATH)
row = conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='user_sessions'").fetchone()
print("user_sessions DDL:", row[0] if row else "NOT FOUND")
row2 = conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='users'").fetchone()
print("users DDL:", row2[0] if row2 else "NOT FOUND")
conn.close()
