"""
Data access layer untuk tabel proyek (KF-7, KF-9).
"""

from database.estimasi_repository import _connect


def get_all_proyek():
    conn = _connect()
    try:
        rows = conn.execute(
            """
            SELECT p.id, p.nama_proyek, p.path_file_ifc, p.tanggal_dibuat, p.tanggal_diubah,
                   (SELECT COUNT(*) FROM elemen_proyek e WHERE e.proyek_id = p.id) AS jumlah_elemen,
                   (SELECT COALESCE(SUM(h.subtotal_biaya), 0) FROM hasil_estimasi h
                     WHERE h.proyek_id = p.id) AS subtotal_rab
            FROM proyek p
            ORDER BY p.tanggal_diubah DESC, p.id DESC
            """
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_proyek(proyek_id: int) -> dict | None:
    return next((p for p in get_all_proyek() if p["id"] == proyek_id), None)


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