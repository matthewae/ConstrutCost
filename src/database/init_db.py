import sqlite3
from pathlib import Path

DB_PATH = Path("data/coststruct.db")
SCHEMA_PATH = Path("src/database/schema.sql")

def init_db():
    DB_PATH.parent.mkdir(exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    with open(SCHEMA_PATH, "r") as f:
        conn.executescript(f.read())
    conn.commit()
    conn.close()
    print(f"Database berhasil dibuat di: {DB_PATH}")

if __name__ == "__main__":
    init_db()