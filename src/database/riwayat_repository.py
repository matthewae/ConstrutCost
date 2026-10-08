"""
KF-6 undo/redo: potret (snapshot) seluruh data hasil estimasi satu proyek.

Setiap perubahan di halaman Hasil Estimasi (edit volume, harga satuan, catatan, ubah dimensi,
tipe penulangan, biaya tidak langsung, hitung ulang) dicatat sebagai pasangan potret sebelum &
sesudah. Urungkan = pulihkan potret sebelum, Ulangi = pulihkan potret sesudah. Data satu rumah
tinggal hanya ratusan baris, sehingga potret penuh tetap ringan dan selalu konsisten, termasuk
untuk perubahan yang menyentuh banyak tabel sekaligus (mis. hitung ulang pembesian).
"""

from database.estimasi_repository import _connect

# urutan hapus: anak dulu (hasil -> elemen); urutan isi: kebalikannya
TABEL = ("biaya_tidak_langsung", "tipe_penulangan", "elemen_proyek", "hasil_estimasi")
_URUT_HAPUS = ("hasil_estimasi", "elemen_proyek", "tipe_penulangan", "biaya_tidak_langsung")
# kolom baris proyek yang ikut dipotret (parameter aturan KF-7, info proyek KF-9)
KOLOM_PROYEK = ("nama_proyek", "path_file_ifc", "lokasi", "pemilik", "tahun_anggaran", "parameter")


def potret_proyek(proyek_id: int) -> dict:
    conn = _connect()
    try:
        hasil = {
            t: [dict(r) for r in conn.execute(f"SELECT * FROM {t} WHERE proyek_id = ? ORDER BY id", (proyek_id,))]
            for t in TABEL
        }
        row = conn.execute(f"SELECT {', '.join(KOLOM_PROYEK)} FROM proyek WHERE id = ?", (proyek_id,)).fetchone()
        hasil["proyek"] = dict(row) if row else {}
        return hasil
    finally:
        conn.close()


def pulihkan_proyek(proyek_id: int, potret: dict) -> None:
    """Kembalikan data proyek persis seperti potret (id baris dipertahankan). Satu transaksi."""
    conn = _connect()
    try:
        conn.execute("BEGIN")
        for t in _URUT_HAPUS:
            conn.execute(f"DELETE FROM {t} WHERE proyek_id = ?", (proyek_id,))
        for t in TABEL:
            for row in potret.get(t, []):
                kolom = list(row)
                conn.execute(
                    f"INSERT INTO {t} ({', '.join(kolom)}) VALUES ({', '.join('?' * len(kolom))})",
                    [row[k] for k in kolom],
                )
        info = potret.get("proyek") or {}
        if info:
            conn.execute(
                f"UPDATE proyek SET {', '.join(f'{k} = ?' for k in info)} WHERE id = ?",
                (*info.values(), proyek_id),
            )
        conn.execute("UPDATE proyek SET tanggal_diubah = CURRENT_TIMESTAMP WHERE id = ?", (proyek_id,))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def sama(a: dict, b: dict) -> bool:
    return a == b
