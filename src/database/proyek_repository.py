"""
Data access layer untuk tabel proyek (KF-7, KF-9).
"""

from pathlib import Path

from database.estimasi_repository import _connect


class ProyekTidakValid(ValueError):
    """Isian info proyek ditolak (KF-14). Pesannya siap ditampilkan ke pengguna."""


def get_all_proyek():
    conn = _connect()
    try:
        rows = conn.execute(
            """
            SELECT p.id, p.nama_proyek, p.path_file_ifc, p.tanggal_dibuat, p.tanggal_diubah,
                   p.lokasi, p.pemilik, p.tahun_anggaran,
                   (SELECT COUNT(*) FROM elemen_proyek e WHERE e.proyek_id = p.id) AS jumlah_elemen,
                   (SELECT COALESCE(SUM(h.subtotal_biaya), 0) FROM hasil_estimasi h
                     WHERE h.proyek_id = p.id) AS subtotal_rab
            FROM proyek p
            ORDER BY p.tanggal_diubah DESC, p.id DESC
            """
        ).fetchall()
        hasil = [dict(r) for r in rows]
        biaya = {}
        for b in conn.execute("SELECT * FROM biaya_tidak_langsung ORDER BY urutan, id"):
            biaya.setdefault(b["proyek_id"], []).append(dict(b))
    finally:
        conn.close()
    from database.biaya_repository import hitung_ringkasan

    for p in hasil:
        # KF-13: total RAB = biaya langsung + biaya tidak langsung + PPN
        p["total_rab"] = hitung_ringkasan(p["subtotal_rab"], biaya.get(p["id"], []))["total"] if p["subtotal_rab"] else 0.0
    return hasil


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
        conn.execute("DELETE FROM tipe_penulangan WHERE proyek_id = ?", (proyek_id,))
        conn.execute("DELETE FROM biaya_tidak_langsung WHERE proyek_id = ?", (proyek_id,))
        conn.execute("DELETE FROM proyek WHERE id = ?", (proyek_id,))
        conn.commit()
    finally:
        conn.close()

def ubah_info_proyek(proyek_id: int, nama: str, lokasi: str = "", pemilik: str = "",
                     tahun: int | None = None, path_ifc: str | None = None) -> None:
    """KF-9: ubah nama, lokasi, pemilik/instansi, tahun anggaran, dan file IFC proyek."""
    nama = " ".join((nama or "").split())
    if not nama:
        raise ProyekTidakValid("Nama proyek tidak boleh kosong.")
    if len(nama) > 120:
        raise ProyekTidakValid("Nama proyek maksimal 120 karakter.")
    if tahun is not None and not 2000 <= int(tahun) <= 2100:
        raise ProyekTidakValid("Tahun anggaran harus 2000 sampai 2100.")
    if path_ifc:
        f = Path(path_ifc)
        if f.suffix.lower() != ".ifc":
            raise ProyekTidakValid("File model harus berekstensi .ifc.")
        if not f.is_file():
            raise ProyekTidakValid(f"File IFC tidak ditemukan:\n{path_ifc}")
    conn = _connect()
    try:
        conn.execute(
            """UPDATE proyek SET nama_proyek = ?, lokasi = ?, pemilik = ?, tahun_anggaran = ?,
                   path_file_ifc = ?, tanggal_diubah = CURRENT_TIMESTAMP WHERE id = ?""",
            (nama, " ".join((lokasi or "").split()) or None, " ".join((pemilik or "").split()) or None,
             int(tahun) if tahun else None, path_ifc or None, proyek_id),
        )
        conn.commit()
    finally:
        conn.close()
