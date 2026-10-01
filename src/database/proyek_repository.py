"""
Data access layer untuk tabel proyek (KF-7, KF-9).
"""

from database.estimasi_repository import _connect


def get_all_proyek():
    conn = _connect()
    try:
        rows = conn.execute(
            """
            SELECT id, nama_proyek, path_file_ifc, tanggal_dibuat, tanggal_diubah
            FROM proyek
            ORDER BY tanggal_diubah DESC, id DESC
            """
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def create_proyek(nama_proyek: str, path_file_ifc: str | None = None) -> int:
    """Buat proyek baru dan kembalikan id-nya."""
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


def delete_proyek(proyek_id: int) -> None:
    """Hapus proyek beserta elemen & hasil estimasinya."""
    conn = _connect()
    try:
        conn.execute("DELETE FROM hasil_estimasi WHERE proyek_id = ?", (proyek_id,))
        conn.execute("DELETE FROM elemen_proyek WHERE proyek_id = ?", (proyek_id,))
        conn.execute("DELETE FROM proyek WHERE id = ?", (proyek_id,))
        conn.commit()
    finally:
        conn.close()