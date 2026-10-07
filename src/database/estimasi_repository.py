"""
Data access layer untuk hasil_estimasi (QTO & RAB per proyek).
"""

import sqlite3
from pathlib import Path

# Selalu <root proyek>/data/coststruct.db, tidak bergantung pada folder tempat aplikasi dijalankan.
DB_PATH = Path(__file__).resolve().parents[2] / "data" / "coststruct.db"

# Biaya Umum & Keuntungan (overhead + profit). HSPK Kota Bandung 2027 memakai 10% (rentang 10%-15%).
# Harga satuan pekerjaan = (jumlah bahan + upah + alat) x (1 + BUK_RATE).
BUK_RATE = 0.10

# KF-11: PPN 11% otomatis pada total biaya, tanpa opsi ubah oleh pengguna.
PPN_RATE = 0.11


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
                he.rumus,
                he.uraian,
                he.diameter,
                p.kode_ahsp,
                p.nama_pekerjaan,
                p.kategori,
                p.satuan,
                ep.nama AS nama_elemen,
                ep.lantai,
                ep.kelas,
                ep.ifc_type,
                ep.global_id,
                ep.panjang,
                ep.lebar,
                ep.tinggi,
                ep.tebal,
                ep.luas,
                ep.volume AS volume_elemen,
                ep.keliling,
                ep.kemiringan,
                ep.luas_bukaan,
                ep.sumber_dimensi,
                COALESCE(ep.dimensi_manual, 0) AS dimensi_manual,
                ep.tipe_id,
                tp.kode AS kode_tipe,
                tp.kelompok AS kelompok_tipe,
                tp.b_cm AS tipe_b_cm,
                tp.h_cm AS tipe_h_cm
            FROM hasil_estimasi he
            JOIN pekerjaan p ON p.id = he.pekerjaan_id
            LEFT JOIN elemen_proyek ep ON ep.id = he.elemen_id
            LEFT JOIN tipe_penulangan tp ON tp.id = ep.tipe_id
            WHERE he.proyek_id = ?
            ORDER BY p.kategori, p.nama_pekerjaan, ep.lantai, ep.nama
            """,
            (proyek_id,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_harga_satuan_pekerjaan(pekerjaan_id: int) -> float:
    """Harga satuan AHSP/HSPK: total (koefisien x harga_satuan) komponen bahan/upah/alat + BUK."""
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
        jumlah = row["harga"] if row else 0.0
        return jumlah * (1 + BUK_RATE)
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