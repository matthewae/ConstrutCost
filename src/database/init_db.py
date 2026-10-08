import sqlite3
import sys
from datetime import date
from pathlib import Path

if __package__ in (None, ""):  # dijalankan langsung: python src/database/init_db.py
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from database.estimasi_repository import DB_PATH

SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"

# Kolom yang ditambahkan setelah versi awal skema. Database lama dilengkapi lewat
# ALTER TABLE supaya data proyek yang sudah ada tidak hilang.
KOLOM_TAMBAHAN = {
    "proyek": {"lokasi": "TEXT", "pemilik": "TEXT", "tahun_anggaran": "INTEGER", "parameter": "TEXT"},
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
        "dimensi_manual": "INTEGER DEFAULT 0",
        "tipe_id": "INTEGER",
    },
    "hasil_estimasi": {"rumus": "TEXT", "uraian": "TEXT", "diameter": "REAL", "harga_manual": "REAL", "catatan": "TEXT"},
    "komponen_harga": {"sumber_daya_id": "INTEGER REFERENCES sumber_daya(id)"},
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


def cadangkan_database(simpan: int = 7, folder: Path | None = None) -> Path | None:
    """Salinan cadangan harian database (KF-14 / KNF-8) di folder `cadangan`, disimpan `simpan` hari
    terakhir. Memakai API backup SQLite agar salinan konsisten. Return path cadangan bila dibuat."""
    from lokasi import folder_cadangan

    if not DB_PATH.is_file():
        return None
    folder = Path(folder or folder_cadangan())
    folder.mkdir(parents=True, exist_ok=True)
    tujuan = folder / f"coststruct-{date.today():%Y%m%d}.db"
    if tujuan.is_file():
        return None
    sumber, salinan = sqlite3.connect(DB_PATH, timeout=10), sqlite3.connect(tujuan)
    try:
        sumber.backup(salinan)
    finally:
        salinan.close()
        sumber.close()
    for lama in sorted(folder.glob("coststruct-*.db"))[:-simpan]:
        lama.unlink(missing_ok=True)
    return tujuan


def siapkan_database():
    """Skema + data master pekerjaan & harga. Dipanggil saat aplikasi dibuka."""
    from database.seed_data import seed_pekerjaan

    init_db()
    seed_pekerjaan()


if __name__ == "__main__":
    init_db()
    print(f"Database siap di: {DB_PATH}")
