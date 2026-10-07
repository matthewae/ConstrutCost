"""
KF-5 Manajemen Harga Satuan (UC-04).

Dua tingkat harga, mengikuti susunan AHSP:
1. Harga satuan dasar (tabel sumber_daya): bahan, upah, dan alat, beserta merk.
   Mengubah harga di sini otomatis berlaku pada semua analisa pekerjaan yang memakainya.
2. Analisa harga satuan pekerjaan (tabel komponen_harga): koefisien x harga dasar,
   dijumlah per bahan (A), upah (B), alat (C), ditambah Biaya Umum & Keuntungan.

Hasil estimasi proyek menyimpan subtotal; `terapkan_ke_estimasi()` menghitung ulang
subtotal dengan harga terbaru tanpa mengubah volume (termasuk volume yang diedit manual).
"""

from database.estimasi_repository import BUK_RATE, _connect

TIPE = ("bahan", "upah", "alat")
LABEL_TIPE = {"bahan": "Bahan", "upah": "Upah", "alat": "Alat"}


class HargaTidakValid(ValueError):
    """Input harga / sumber daya ditolak. Pesannya siap ditampilkan ke pengguna."""


def _validasi_harga(harga) -> float:
    try:
        nilai = float(harga)
    except (TypeError, ValueError):
        raise HargaTidakValid("Harga harus berupa angka.") from None
    if nilai <= 0:
        raise HargaTidakValid("Harga harus lebih besar dari nol.")
    return nilai


# ---------------------------------------------------------------- harga dasar


def daftar_sumber_daya(tipe: str | None = None) -> list:
    """Semua sumber daya beserta jumlah pekerjaan yang memakainya."""
    sql = """
        SELECT sd.*,
               (SELECT COUNT(DISTINCT kh.pekerjaan_id) FROM komponen_harga kh
                 WHERE kh.sumber_daya_id = sd.id) AS jumlah_pekerjaan
        FROM sumber_daya sd
    """
    args = ()
    if tipe:
        sql += " WHERE sd.tipe = ?"
        args = (tipe,)
    sql += " ORDER BY CASE sd.tipe WHEN 'bahan' THEN 0 WHEN 'upah' THEN 1 ELSE 2 END, sd.nama"
    conn = _connect()
    try:
        return [dict(r) for r in conn.execute(sql, args)]
    finally:
        conn.close()


def ambil_sumber_daya(sumber_daya_id: int) -> dict | None:
    conn = _connect()
    try:
        r = conn.execute("SELECT * FROM sumber_daya WHERE id = ?", (sumber_daya_id,)).fetchone()
        return dict(r) if r else None
    finally:
        conn.close()


def _simpan_harga(conn, sumber_daya_id: int, harga: float, merk, diubah_manual: int):
    lama = conn.execute(
        "SELECT harga, merk FROM sumber_daya WHERE id = ?", (sumber_daya_id,)
    ).fetchone()
    if lama is None:
        raise HargaTidakValid("Sumber daya tidak ditemukan.")
    conn.execute(
        """UPDATE sumber_daya SET harga = ?, merk = ?, diubah_manual = ?,
               tanggal_diubah = CURRENT_TIMESTAMP WHERE id = ?""",
        (harga, merk, diubah_manual, sumber_daya_id),
    )
    conn.execute(
        "UPDATE komponen_harga SET harga_satuan = ? WHERE sumber_daya_id = ?",
        (harga, sumber_daya_id),
    )
    if lama["harga"] != harga or (lama["merk"] or None) != (merk or None):
        conn.execute(
            """INSERT INTO riwayat_harga (sumber_daya_id, harga_lama, harga_baru, merk_lama, merk_baru)
               VALUES (?,?,?,?,?)""",
            (sumber_daya_id, lama["harga"], harga, lama["merk"], merk),
        )


def ubah_sumber_daya(sumber_daya_id: int, harga, merk: str | None = None) -> None:
    """Simpan harga & merk baru (UC-04 langkah 5-7). Harga harus > 0."""
    nilai = _validasi_harga(harga)
    merk = (merk or "").strip() or None
    conn = _connect()
    try:
        _simpan_harga(conn, sumber_daya_id, nilai, merk, diubah_manual=1)
        conn.commit()
    finally:
        conn.close()


def kembalikan_harga_bawaan(sumber_daya_id: int) -> None:
    conn = _connect()
    try:
        r = conn.execute(
            "SELECT harga_bawaan, merk FROM sumber_daya WHERE id = ?", (sumber_daya_id,)
        ).fetchone()
        if r is None or r["harga_bawaan"] is None:
            raise HargaTidakValid("Sumber daya ini tidak punya harga bawaan.")
        _simpan_harga(conn, sumber_daya_id, r["harga_bawaan"], r["merk"], diubah_manual=0)
        conn.commit()
    finally:
        conn.close()


def tambah_sumber_daya(tipe: str, nama: str, satuan: str, harga, merk: str | None = None) -> int:
    """UC-04 skenario alternatif: tambah material / upah / alat baru."""
    if tipe not in TIPE:
        raise HargaTidakValid("Jenis harus bahan, upah, atau alat.")
    nama, satuan = (nama or "").strip(), (satuan or "").strip()
    if not nama:
        raise HargaTidakValid("Nama wajib diisi.")
    if not satuan:
        raise HargaTidakValid("Satuan wajib diisi.")
    nilai = _validasi_harga(harga)
    conn = _connect()
    try:
        if conn.execute(
            "SELECT 1 FROM sumber_daya WHERE tipe=? AND lower(nama)=lower(?) AND lower(satuan)=lower(?)",
            (tipe, nama, satuan),
        ).fetchone():
            raise HargaTidakValid(f"{LABEL_TIPE[tipe]} '{nama}' ({satuan}) sudah ada di daftar.")
        sid = conn.execute(
            """INSERT INTO sumber_daya (tipe, nama, satuan, harga, harga_bawaan, merk, sumber, diubah_manual)
               VALUES (?,?,?,?,NULL,?,'Pengguna',1)""",
            (tipe, nama, satuan, nilai, (merk or "").strip() or None),
        ).lastrowid
        conn.commit()
        return sid
    finally:
        conn.close()


def hapus_sumber_daya(sumber_daya_id: int) -> None:
    """Hanya sumber daya tambahan pengguna yang belum dipakai pekerjaan mana pun."""
    conn = _connect()
    try:
        r = conn.execute(
            "SELECT harga_bawaan FROM sumber_daya WHERE id = ?", (sumber_daya_id,)
        ).fetchone()
        if r is None:
            return
        if r["harga_bawaan"] is not None:
            raise HargaTidakValid("Harga dasar bawaan tidak bisa dihapus.")
        if conn.execute(
            "SELECT 1 FROM komponen_harga WHERE sumber_daya_id = ? LIMIT 1", (sumber_daya_id,)
        ).fetchone():
            raise HargaTidakValid("Masih dipakai di analisa pekerjaan. Hapus komponennya terlebih dahulu.")
        conn.execute("DELETE FROM riwayat_harga WHERE sumber_daya_id = ?", (sumber_daya_id,))
        conn.execute("DELETE FROM sumber_daya WHERE id = ?", (sumber_daya_id,))
        conn.commit()
    finally:
        conn.close()


def pekerjaan_pemakai(sumber_daya_id: int) -> list:
    """Pekerjaan yang analisanya memakai sumber daya ini."""
    conn = _connect()
    try:
        return [
            dict(r)
            for r in conn.execute(
                """SELECT DISTINCT p.id, p.kode_ahsp, p.nama_pekerjaan, kh.koefisien
                   FROM komponen_harga kh JOIN pekerjaan p ON p.id = kh.pekerjaan_id
                   WHERE kh.sumber_daya_id = ? ORDER BY p.kategori, p.nama_pekerjaan""",
                (sumber_daya_id,),
            )
        ]
    finally:
        conn.close()


def riwayat_harga(sumber_daya_id: int, batas: int = 20) -> list:
    conn = _connect()
    try:
        return [
            dict(r)
            for r in conn.execute(
                "SELECT * FROM riwayat_harga WHERE sumber_daya_id = ? ORDER BY id DESC LIMIT ?",
                (sumber_daya_id, batas),
            )
        ]
    finally:
        conn.close()


# ---------------------------------------------------------------- analisa pekerjaan


def daftar_pekerjaan() -> list:
    """Harga satuan setiap pekerjaan: A (bahan), B (upah), C (alat), BUK, dan harga satuan."""
    conn = _connect()
    try:
        rows = conn.execute(
            """
            SELECT p.id, p.kode_ahsp, p.nama_pekerjaan, p.kategori, p.satuan, p.catatan,
                   COALESCE(SUM(CASE WHEN kh.tipe='bahan' THEN kh.koefisien*kh.harga_satuan END), 0) AS bahan,
                   COALESCE(SUM(CASE WHEN kh.tipe='upah'  THEN kh.koefisien*kh.harga_satuan END), 0) AS upah,
                   COALESCE(SUM(CASE WHEN kh.tipe='alat'  THEN kh.koefisien*kh.harga_satuan END), 0) AS alat,
                   COUNT(kh.id) AS jumlah_komponen
            FROM pekerjaan p
            LEFT JOIN komponen_harga kh ON kh.pekerjaan_id = p.id
            GROUP BY p.id
            ORDER BY p.kategori, p.nama_pekerjaan
            """
        ).fetchall()
    finally:
        conn.close()
    hasil = []
    for r in rows:
        d = dict(r)
        d["jumlah_abc"] = d["bahan"] + d["upah"] + d["alat"]
        d["buk"] = d["jumlah_abc"] * BUK_RATE
        d["harga_satuan"] = d["jumlah_abc"] + d["buk"]
        hasil.append(d)
    return hasil


def analisa_pekerjaan(pekerjaan_id: int) -> list:
    conn = _connect()
    try:
        return [
            dict(r)
            for r in conn.execute(
                """
                SELECT kh.id, kh.tipe, kh.nama_komponen, kh.satuan, kh.koefisien, kh.harga_satuan,
                       kh.koefisien * kh.harga_satuan AS jumlah, kh.diubah_manual, kh.sumber_daya_id,
                       sd.merk, sd.sumber
                FROM komponen_harga kh
                LEFT JOIN sumber_daya sd ON sd.id = kh.sumber_daya_id
                WHERE kh.pekerjaan_id = ?
                ORDER BY CASE kh.tipe WHEN 'bahan' THEN 0 WHEN 'upah' THEN 1 ELSE 2 END, kh.id
                """,
                (pekerjaan_id,),
            )
        ]
    finally:
        conn.close()


def tambah_komponen(pekerjaan_id: int, sumber_daya_id: int, koefisien) -> int:
    """Tambah bahan/upah/alat ke analisa pekerjaan (mis. sewa alat). Koefisien harus > 0."""
    try:
        koef = float(koefisien)
    except (TypeError, ValueError):
        raise HargaTidakValid("Koefisien harus berupa angka.") from None
    if koef <= 0:
        raise HargaTidakValid("Koefisien harus lebih besar dari nol.")
    conn = _connect()
    try:
        sd = conn.execute("SELECT * FROM sumber_daya WHERE id = ?", (sumber_daya_id,)).fetchone()
        if sd is None:
            raise HargaTidakValid("Sumber daya tidak ditemukan.")
        if conn.execute(
            "SELECT 1 FROM komponen_harga WHERE pekerjaan_id = ? AND sumber_daya_id = ?",
            (pekerjaan_id, sumber_daya_id),
        ).fetchone():
            raise HargaTidakValid(f"'{sd['nama']}' sudah ada di analisa pekerjaan ini.")
        kid = conn.execute(
            """INSERT INTO komponen_harga (pekerjaan_id, tipe, nama_komponen, satuan, koefisien,
                   harga_satuan, diubah_manual, sumber_daya_id) VALUES (?,?,?,?,?,?,1,?)""",
            (pekerjaan_id, sd["tipe"], sd["nama"], sd["satuan"], koef, sd["harga"], sd["id"]),
        ).lastrowid
        conn.commit()
        return kid
    finally:
        conn.close()


def hapus_komponen(komponen_id: int) -> None:
    """Hanya komponen tambahan pengguna; komponen bawaan AHSP dijaga tetap utuh."""
    conn = _connect()
    try:
        r = conn.execute(
            "SELECT diubah_manual FROM komponen_harga WHERE id = ?", (komponen_id,)
        ).fetchone()
        if r is None:
            return
        if not r["diubah_manual"]:
            raise HargaTidakValid("Komponen bawaan AHSP tidak bisa dihapus.")
        conn.execute("DELETE FROM komponen_harga WHERE id = ?", (komponen_id,))
        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------- penerapan ke estimasi


def terapkan_ke_estimasi(proyek_id: int | None = None) -> int:
    """Hitung ulang subtotal hasil estimasi dengan harga satuan terbaru (UC-04 langkah 9-10).
    Volume tidak diubah. Return jumlah baris yang diperbarui."""
    sql = """
        UPDATE hasil_estimasi
        SET subtotal_biaya = volume_pekerjaan * (1 + ?) * COALESCE(
            (SELECT SUM(kh.koefisien * kh.harga_satuan) FROM komponen_harga kh
              WHERE kh.pekerjaan_id = hasil_estimasi.pekerjaan_id), 0)
    """
    args = [BUK_RATE]
    if proyek_id is not None:
        sql += " WHERE proyek_id = ?"
        args.append(proyek_id)
    conn = _connect()
    try:
        n = conn.execute(sql, args).rowcount
        if proyek_id is None:
            conn.execute(
                "UPDATE proyek SET tanggal_diubah = CURRENT_TIMESTAMP "
                "WHERE id IN (SELECT DISTINCT proyek_id FROM hasil_estimasi)"
            )
        else:
            conn.execute("UPDATE proyek SET tanggal_diubah = CURRENT_TIMESTAMP WHERE id = ?", (proyek_id,))
        conn.commit()
        return n
    finally:
        conn.close()


def jumlah_estimasi_kedaluwarsa(toleransi: float = 0.5) -> int:
    """Banyak baris hasil estimasi yang subtotalnya tidak lagi sesuai harga satuan terbaru."""
    conn = _connect()
    try:
        return conn.execute(
            """
            SELECT COUNT(*) FROM hasil_estimasi he
            WHERE ABS(he.subtotal_biaya - he.volume_pekerjaan * (1 + ?) * COALESCE(
                (SELECT SUM(kh.koefisien * kh.harga_satuan) FROM komponen_harga kh
                  WHERE kh.pekerjaan_id = he.pekerjaan_id), 0)) > ?
            """,
            (BUK_RATE, toleransi),
        ).fetchone()[0]
    finally:
        conn.close()
