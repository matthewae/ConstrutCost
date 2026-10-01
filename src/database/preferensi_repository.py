"""
Preferensi pengguna (KF-10) di tabel preferensi_pengguna (kunci, nilai).
"""

from database.estimasi_repository import _connect


def _pastikan_tabel(conn):
    conn.execute("CREATE TABLE IF NOT EXISTS preferensi_pengguna (kunci TEXT PRIMARY KEY, nilai TEXT)")


def get_pref(kunci: str, default=None):
    conn = _connect()
    try:
        _pastikan_tabel(conn)
        row = conn.execute("SELECT nilai FROM preferensi_pengguna WHERE kunci = ?", (kunci,)).fetchone()
        return row["nilai"] if row else default
    finally:
        conn.close()


def set_pref(kunci: str, nilai: str) -> None:
    conn = _connect()
    try:
        _pastikan_tabel(conn)
        conn.execute("INSERT OR REPLACE INTO preferensi_pengguna (kunci, nilai) VALUES (?, ?)", (kunci, nilai))
        conn.commit()
    finally:
        conn.close()
