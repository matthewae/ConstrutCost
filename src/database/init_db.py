import sqlite3
import sys
from pathlib import Path

if __package__ in (None, ""):  # dijalankan langsung: python src/database/init_db.py
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from database.estimasi_repository import DB_PATH

SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"

# Kolom yang ditambahkan setelah versi awal skema. Database lama dilengkapi lewat
# ALTER TABLE supaya data proyek yang sudah ada tidak hilang.
KOLOM_TAMBAHAN = {
    "elemen_proyek": {
        "kelas": "TEXT",
        "lebar": "REAL",
        "tinggi": "REAL",
        "tebal": "REAL",
        "keliling": "REAL",
        "kemiringan": "REAL",
        "luas_bukaan": "REAL",
        "elevasi_lantai": "REAL",
        "sumber_dimensi": "TEXT",
    },
    "hasil_estimasi": {"rumus": "TEXT"},
}


def pastikan_skema(conn) -> None:
    """Idempotent: buat tabel yang belum ada lalu tambahkan kolom yang belum ada."""
    conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    for tabel, kolom in KOLOM_TAMBAHAN.items():
        ada = {r[1] for r in conn.execute(f"PRAGMA table_info({tabel})")}
        for nama, tipe in kolom.items():
            if nama not in ada:
                conn.execute(f"ALTER TABLE {tabel} ADD COLUMN {nama} {tipe}")
    conn.commit()


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    try:
        pastikan_skema(conn)
    finally:
        conn.close()


if __name__ == "__main__":
    init_db()
    print(f"Database siap di: {DB_PATH}")
