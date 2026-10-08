"""
Data access layer untuk hasil_estimasi (QTO & RAB per proyek).
"""

import sqlite3

from lokasi import path_database

# KNF-8: <root proyek>/data/coststruct.db saat dijalankan dari kode sumber, %APPDATA%\CostStruct\coststruct.db
# saat dijalankan sebagai .exe (lihat lokasi.py). Tidak bergantung pada folder kerja aplikasi.
DB_PATH = path_database()

# Biaya Umum & Keuntungan (overhead + profit). HSPK Kota Bandung 2027 memakai 10% (rentang 10%-15%).
# Harga satuan pekerjaan = (jumlah bahan + upah + alat) x (1 + BUK_RATE).
BUK_RATE = 0.10

# KF-11: PPN 11% otomatis pada total biaya, tanpa opsi ubah oleh pengguna.
PPN_RATE = 0.11


def _connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)  # folder %APPDATA%\CostStruct pada pemakaian pertama
    conn = sqlite3.connect(DB_PATH, timeout=10)  # tunggu bila database sedang ditulis proses lain
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
                he.harga_manual,
                he.catatan,
                p.kode_ahsp,
                p.nama_pekerjaan,
                p.kategori,
                p.satuan,
                ep.nama AS nama_elemen,
                ep.lantai,
                ep.elevasi_lantai,
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


class NilaiTidakValid(ValueError):
    """Isian edit hasil estimasi ditolak (KF-14). Pesannya siap ditampilkan ke pengguna."""


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
    if volume_baru < 0:
        raise NilaiTidakValid("Volume tidak boleh negatif.")
    conn = _connect()
    try:
        row = conn.execute("SELECT harga_manual FROM hasil_estimasi WHERE id = ?", (hasil_id,)).fetchone()
    finally:
        conn.close()
    harga_satuan = row["harga_manual"] if row and row["harga_manual"] else get_harga_satuan_pekerjaan(pekerjaan_id)
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
        _catat_baris(hasil_id, f"Volume diubah menjadi {volume_baru:g}")
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

# ---------------------------------------------------------------- KF-6 edit harga & catatan


def ubah_harga_baris(hasil_ids, harga: float | None) -> None:
    """Pakai harga satuan khusus untuk baris hasil tertentu (mis. harga negosiasi proyek ini).
    harga None = kembali ke harga master (analisa harga satuan). Subtotal dihitung ulang."""
    if harga is not None and (harga != harga or harga <= 0):
        raise NilaiTidakValid("Harga satuan harus lebih besar dari nol.")
    conn = _connect()
    try:
        for hid in hasil_ids:
            r = conn.execute("SELECT pekerjaan_id, volume_pekerjaan FROM hasil_estimasi WHERE id = ?", (hid,)).fetchone()
            if r is None:
                continue
            h = harga if harga is not None else conn.execute(
                "SELECT COALESCE(SUM(koefisien * harga_satuan), 0) FROM komponen_harga WHERE pekerjaan_id = ?",
                (r["pekerjaan_id"],),
            ).fetchone()[0] * (1 + BUK_RATE)
            conn.execute(
                "UPDATE hasil_estimasi SET harga_manual = ?, subtotal_biaya = ? WHERE id = ?",
                (harga, r["volume_pekerjaan"] * h, hid),
            )
        conn.commit()
    finally:
        conn.close()
    if hasil_ids:
        teks = f"Harga satuan khusus Rp {harga:,.0f}".replace(",", ".") if harga is not None else "Kembali ke harga master"
        _catat_baris(hasil_ids[0], f"{teks} ({len(hasil_ids)} baris)")


def ubah_catatan(hasil_id: int, catatan: str) -> None:
    teks = " ".join((catatan or "").split())
    if len(teks) > 500:
        raise NilaiTidakValid("Catatan maksimal 500 karakter.")
    conn = _connect()
    try:
        conn.execute("UPDATE hasil_estimasi SET catatan = ? WHERE id = ?", (teks or None, hasil_id))
        conn.commit()
    finally:
        conn.close()
    _catat_baris(hasil_id, f"Catatan: {teks}" if teks else "Catatan dihapus")


def _catat_baris(hasil_id: int, pesan: str) -> None:
    """KF-15: catat edit hasil estimasi beserta nama pekerjaan & elemennya."""
    from aktivitas import catat

    conn = _connect()
    try:
        r = conn.execute(
            """SELECT h.proyek_id, p.nama_pekerjaan, e.nama FROM hasil_estimasi h
               JOIN pekerjaan p ON p.id = h.pekerjaan_id LEFT JOIN elemen_proyek e ON e.id = h.elemen_id
               WHERE h.id = ?""",
            (hasil_id,),
        ).fetchone()
    finally:
        conn.close()
    if r:
        catat("edit", f"{r['nama_pekerjaan']} · {r['nama'] or '-'}: {pesan}", r["proyek_id"])
