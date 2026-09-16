"""
Data access layer untuk tabel `proyek`.
Dipisah dari gui/ supaya UI tidak langsung berurusan dengan SQL,
dan gampang dites/diganti nanti.
"""

import sqlite3
from pathlib import Path

DB_PATH = Path("data/coststruct.db")


def _connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def get_all_proyek():
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT * FROM proyek ORDER BY tanggal_diubah DESC"
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_proyek_by_id(proyek_id: int):
    conn = _connect()
    try:
        row = conn.execute("SELECT * FROM proyek WHERE id = ?", (proyek_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def create_proyek(nama_proyek: str, path_file_ifc: str | None = None) -> int:
    conn = _connect()
    try:
        cur = conn.execute(
            "INSERT INTO proyek (nama_proyek, path_file_ifc) VALUES (?, ?)",
            (nama_proyek, path_file_ifc),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def update_proyek_timestamp(proyek_id: int):
    conn = _connect()
    try:
        conn.execute(
            "UPDATE proyek SET tanggal_diubah = CURRENT_TIMESTAMP WHERE id = ?",
            (proyek_id,),
        )
        conn.commit()
    finally:
        conn.close()


def delete_proyek(proyek_id: int):
    conn = _connect()
    try:
        conn.execute("DELETE FROM hasil_estimasi WHERE proyek_id = ?", (proyek_id,))
        conn.execute("DELETE FROM elemen_proyek WHERE proyek_id = ?", (proyek_id,))
        conn.execute("DELETE FROM proyek WHERE id = ?", (proyek_id,))
        conn.commit()
    finally:
        conn.close()