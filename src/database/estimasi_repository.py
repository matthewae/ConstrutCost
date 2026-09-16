"""
Data access layer untuk hasil_estimasi (QTO & RAB per proyek).
"""

import sqlite3
from pathlib import Path

DB_PATH = Path("data/coststruct.db")


def _connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def get_hasil_estimasi_by_proyek(proyek_id: int):
    """Ambil hasil estimasi satu proyek, digabung dengan info pekerjaan & elemen."""
    conn = _connect()
    try:
        rows = conn.execute(
            """
            SELECT
                he.id AS hasil_id,
                he.pekerjaan_id,
                he.elemen_id,
                he.volume_pekerjaan,
                he.subtotal_biaya,
                he.diedit_manual,
                p.nama_pekerjaan,
                p.kategori,
                p.satuan,
                ep.nama AS nama_elemen,
                ep.lantai
            FROM hasil_estimasi he
            JOIN pekerjaan p ON p.id = he.pekerjaan_id
            LEFT JOIN elemen_proyek ep ON ep.id = he.elemen_id
            WHERE he.proyek_id = ?
            ORDER BY p.kategori, p.nama_pekerjaan
            """,
            (proyek_id,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_harga_satuan_pekerjaan(pekerjaan_id: int) -> float:
    """Harga satuan AHSP: total (koefisien x harga_satuan) semua komponen bahan/upah/alat."""
    conn = _connect()
    try:
        row = conn.execute(
            """
            SELECT COALESCE(SUM(koefisien * harga_satuan), 0) AS harga
            FROM komponen_harga
            WHERE pekerjaan_id = ?
            """,
            (pekerjaan_id,),
        ).fetchone()
        return row["harga"] if row else 0.0
    finally:
        conn.close()


def update_volume_estimasi(hasil_id: int, pekerjaan_id: int, volume_baru: float) -> float:
    """Update volume hasil edit manual user, hitung ulang subtotal_biaya otomatis
    (UC-03: recalculate terjadi otomatis saat volume diedit).

    Return subtotal_biaya baru supaya UI bisa langsung update tanpa query ulang.
    """
    harga_satuan = get_harga_satuan_pekerjaan(pekerjaan_id)
    subtotal_baru = volume_baru * harga_satuan

    conn = _connect()
    try:
        conn.execute(
            """
            UPDATE hasil_estimasi
            SET volume_pekerjaan = ?, subtotal_biaya = ?, diedit_manual = 1
            WHERE id = ?
            """,
            (volume_baru, subtotal_baru, hasil_id),
        )
        conn.commit()
        return subtotal_baru
    finally:
        conn.close()


def get_total_rab(proyek_id: int) -> float:
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT COALESCE(SUM(subtotal_biaya), 0) AS total FROM hasil_estimasi WHERE proyek_id = ?",
            (proyek_id,),
        ).fetchone()
        return row["total"] if row else 0.0
    finally:
        conn.close()