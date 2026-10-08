"""
KF-13 Ringkasan biaya: biaya langsung (per pekerjaan / kategori), biaya tidak langsung, PPN.

    A. Biaya langsung               = Σ (volume x harga satuan)      (BUK 10% sudah di harga satuan)
    B. Biaya tidak langsung         = Σ item (persen x A, atau nilai Rp)
       Jumlah                       = A + B
       PPN 11%                      = 11% x (A + B)                     (KF-11)
       Total                        = A + B + PPN, dibulatkan ke bawah per Rp 1.000
"""

import math

from database.estimasi_repository import BUK_RATE, PPN_RATE, _connect
from terbilang import terbilang

JENIS = ("persen", "nilai")
# Usulan uraian biaya tidak langsung (nilai diisi pengguna sesuai kontrak / ketentuan proyek).
USULAN = (
    "Biaya perencanaan teknis",
    "Biaya pengawasan konstruksi",
    "Biaya pengelolaan kegiatan / operasional",
    "Biaya perizinan (PBG / SLF)",
    "Biaya penerapan SMKK",
    "Biaya administrasi & dokumentasi",
)


class BiayaTidakValid(ValueError):
    """Isian biaya tidak langsung ditolak. Pesannya siap ditampilkan ke pengguna."""


def _validasi(uraian: str, jenis: str, nilai) -> tuple:
    uraian = " ".join((uraian or "").split())
    if not uraian:
        raise BiayaTidakValid("Uraian biaya tidak boleh kosong.")
    if jenis not in JENIS:
        raise BiayaTidakValid("Jenis biaya harus persen atau nilai rupiah.")
    try:
        nilai = float(nilai)
    except (TypeError, ValueError):
        raise BiayaTidakValid("Nilai biaya harus berupa angka.") from None
    if math.isnan(nilai) or nilai <= 0:
        raise BiayaTidakValid("Nilai biaya harus lebih besar dari nol.")
    if jenis == "persen" and nilai > 100:
        raise BiayaTidakValid("Persentase tidak boleh lebih dari 100%.")
    return uraian, jenis, nilai


def daftar_biaya(proyek_id: int) -> list:
    conn = _connect()
    try:
        return [dict(r) for r in conn.execute(
            "SELECT * FROM biaya_tidak_langsung WHERE proyek_id = ? ORDER BY urutan, id", (proyek_id,)
        )]
    finally:
        conn.close()


def tambah_biaya(proyek_id: int, uraian: str, jenis: str, nilai) -> int:
    uraian, jenis, nilai = _validasi(uraian, jenis, nilai)
    conn = _connect()
    try:
        urutan = conn.execute(
            "SELECT COALESCE(MAX(urutan), 0) + 1 FROM biaya_tidak_langsung WHERE proyek_id = ?", (proyek_id,)
        ).fetchone()[0]
        bid = conn.execute(
            "INSERT INTO biaya_tidak_langsung (proyek_id, uraian, jenis, nilai, urutan) VALUES (?,?,?,?,?)",
            (proyek_id, uraian, jenis, nilai, urutan),
        ).lastrowid
        conn.commit()
        return bid
    finally:
        conn.close()


def ubah_biaya(biaya_id: int, uraian: str, jenis: str, nilai) -> None:
    uraian, jenis, nilai = _validasi(uraian, jenis, nilai)
    conn = _connect()
    try:
        conn.execute(
            "UPDATE biaya_tidak_langsung SET uraian = ?, jenis = ?, nilai = ? WHERE id = ?",
            (uraian, jenis, nilai, biaya_id),
        )
        conn.commit()
    finally:
        conn.close()


def hapus_biaya(biaya_id: int) -> None:
    conn = _connect()
    try:
        conn.execute("DELETE FROM biaya_tidak_langsung WHERE id = ?", (biaya_id,))
        conn.commit()
    finally:
        conn.close()


def hitung_ringkasan(langsung: float, biaya: list) -> dict:
    """Ringkasan dari biaya langsung dan daftar biaya tidak langsung (fungsi murni)."""
    item = []
    for b in biaya:
        rp = langsung * b["nilai"] / 100 if b["jenis"] == "persen" else b["nilai"]
        item.append({**b, "jumlah": rp})
    tidak_langsung = sum(i["jumlah"] for i in item)
    jumlah = langsung + tidak_langsung
    ppn = jumlah * PPN_RATE
    total = jumlah + ppn
    dibulatkan = math.floor(total / 1000 + 1e-9) * 1000
    return {
        "langsung": langsung,
        "buk": langsung * BUK_RATE / (1 + BUK_RATE),  # porsi BUK di dalam harga satuan (informasi)
        "item_tidak_langsung": item,
        "tidak_langsung": tidak_langsung,
        "jumlah": jumlah,
        "ppn": ppn,
        "total": total,
        "dibulatkan": dibulatkan,
        "terbilang": terbilang(dibulatkan) + " rupiah",
    }


def ringkasan_biaya(proyek_id: int) -> dict:
    conn = _connect()
    try:
        langsung = conn.execute(
            "SELECT COALESCE(SUM(subtotal_biaya), 0) FROM hasil_estimasi WHERE proyek_id = ?", (proyek_id,)
        ).fetchone()[0]
    finally:
        conn.close()
    return hitung_ringkasan(langsung, daftar_biaya(proyek_id))
