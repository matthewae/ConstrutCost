"""
Katalog HSPK lengkap (bab 1-10) dan item tambahan RAB dari katalog.

Rule engine hanya menghitung pekerjaan yang bisa diturunkan dari model IFC (struktur, dinding, lantai,
atap, plafon, cat, pintu & jendela, tanah). Pekerjaan lain yang tetap ada di RAB rumah tinggal, misalnya
instalasi listrik, plambing, sanitair (kloset, wastafel), lisplang, atau pagar, ditambahkan pengguna dari
katalog: pilih item HSPK, isi volume dan lantainya.

Pekerjaan katalog dibuat di tabel pekerjaan saat pertama kali dipakai (kode "HSPK-<kode>"), lengkap dengan
komponen analisanya, sehingga harga dasar yang diubah pengguna (KF-5) juga berlaku untuk item ini.
Item tambahan disimpan di hasil_estimasi dengan elemen_id NULL dan item_tambahan = 1; estimasi ulang dari
IFC tidak menghapusnya.
"""

import re

from aktivitas import catat
from database.estimasi_repository import BUK_RATE, NilaiTidakValid, _connect
from database.hspk_bandung_2027 import AHSP, BAB, SATUAN, SUMBER

AWALAN = "HSPK-"

# sheet HSPK -> kategori RAB aplikasi (bagian lain memakai nama sheetnya sendiri)
_KATEGORI_SHEET = {
    "Persiapan": "Persiapan",
    "Galian Tanah": "Tanah",
    "Timbunan Pemadatan": "Tanah",
    "Beton": "Beton",
    "Pondasi": "Fondasi",
    "Rangka Atap": "Atap",
    "Penutup Atap": "Atap",
    "Plafon": "Plafon",
    "Pasangan Dinding": "Dinding",
    "Plesteran Dan Acian": "Dinding",
    "Pengecatan dan Pelituran": "Cat",
    "PENGECATAN (BARU)": "Cat",
    "Penutup Lantai dan Dinding": "Lantai",
    "Pintu dan Jendela": "Pintu & Jendela",
    "Sistem Air Limbah": "Air Limbah",
    "Perpipaan dan proteksi kebakar": "Perpipaan & Proteksi Kebakaran",
    "Strutur Risha": "Struktur RISHA",
    "BAJA": "Struktur Baja",
    "LANSEKAP BARU": "Lansekap",
}


def kode_dasar(kode: str) -> str:
    """'3.8.10.1@Pengecatan' -> '3.8.10.1'."""
    return kode.split("@")[0]


def kategori(kode: str) -> str:
    sheet = AHSP[kode][0].strip()
    return _KATEGORI_SHEET.get(sheet) or sheet.title()


def _urut_kode(kode: str):
    """Urut alami: 2.2.1.1.1 < 2.2.1.1.1a < 2.2.1.1.2 < 2.2.1.1.10; varian "@sheet" setelah kode polosnya."""
    return [(0, int(x), "") if x.isdigit() else (1, 0, x) for x in re.findall(r"\d+|[^\d.]+", kode)]


def daftar_katalog() -> list:
    """Seluruh analisa HSPK: [{'kode', 'uraian', 'satuan', 'bab', 'judul_bab', 'kategori', 'harga'}],
    urut kode. 'harga' = harga satuan F dokumen HSPK (sudah termasuk biaya umum & keuntungan)."""
    hasil = []
    for kode in sorted(AHSP, key=_urut_kode):
        sheet, uraian, f, _komp = AHSP[kode]
        bab = kode_dasar(kode).split(".")[0]
        hasil.append({
            "kode": kode, "uraian": uraian, "satuan": SATUAN.get(kode) or "", "bab": bab,
            "judul_bab": BAB.get(bab, ""), "kategori": kategori(kode), "harga": f,
        })
    return hasil


def cari_katalog(data: list, kata: str = "", bab: str | None = None) -> list:
    """Saring katalog: semua kata (tanpa membedakan huruf besar) harus ada di kode atau uraian."""
    kata_kata = kata.lower().split()
    return [
        d for d in data
        if (bab is None or d["bab"] == bab)
        and all(k in f"{d['kode']} {d['uraian']}".lower() for k in kata_kata)
    ]


def _kunci(tipe: str, nama: str, satuan: str):
    return tipe, " ".join(nama.split()).lower(), " ".join(satuan.split()).lower()


def pastikan_pekerjaan(kode_hspk: str, conn=None) -> int:
    """id pekerjaan "HSPK-<kode>" (dibuat bila belum ada, dengan komponen analisanya). Komponen dirujukkan
    ke sumber daya bernama sama; bila harganya berbeda dari harga di analisa ini, dipakai/dibuat varian
    "nama (sheet)" seperti seed, agar harga satuan sama dengan harga F dokumen."""
    if kode_hspk not in AHSP:
        raise NilaiTidakValid(f"Kode HSPK '{kode_hspk}' tidak ada di katalog.")
    tutup = conn is None
    conn = conn or _connect()
    try:
        kode = AWALAN + kode_hspk
        row = conn.execute("SELECT id FROM pekerjaan WHERE kode_ahsp = ?", (kode,)).fetchone()
        if row:
            return row["id"]
        sheet, uraian, f, komponen = AHSP[kode_hspk]
        pid = conn.execute(
            "INSERT INTO pekerjaan (kode_ahsp, nama_pekerjaan, kategori, satuan, catatan) VALUES (?,?,?,?,?)",
            (kode, uraian, kategori(kode_hspk), SATUAN.get(kode_hspk) or "unit",
             f"{SUMBER} · {kode_dasar(kode_hspk)} · item katalog (harga satuan dokumen Rp {f:,.0f})".replace(",", ".")),
        ).lastrowid
        ada = {
            _kunci(r["tipe"], r["nama"], r["satuan"]): r
            for r in conn.execute("SELECT id, tipe, nama, satuan, harga, harga_bawaan FROM sumber_daya")
        }
        for tipe, nama, satuan, koef, harga in komponen:
            nama_pakai = " ".join(nama.split())
            r = ada.get(_kunci(tipe, nama_pakai, satuan))
            if r is not None and abs((r["harga_bawaan"] if r["harga_bawaan"] is not None else r["harga"]) - harga) > 0.005:
                nama_pakai = f"{nama_pakai} ({sheet.strip()})"  # varian harga khusus sheet ini
                r = ada.get(_kunci(tipe, nama_pakai, satuan))
            if r is None:
                sid = conn.execute(
                    "INSERT INTO sumber_daya (tipe, nama, satuan, harga, harga_bawaan, sumber) VALUES (?,?,?,?,?,?)",
                    (tipe, nama_pakai, " ".join(satuan.split()), harga, harga, "HSPK Kota Bandung 2027"),
                ).lastrowid
                harga_pakai = harga
                ada[_kunci(tipe, nama_pakai, satuan)] = {"id": sid, "harga": harga, "harga_bawaan": harga}
            else:
                sid, harga_pakai = r["id"], r["harga"]
            conn.execute(
                "INSERT INTO komponen_harga (pekerjaan_id, tipe, nama_komponen, satuan, koefisien, harga_satuan, "
                "sumber_daya_id) VALUES (?,?,?,?,?,?,?)",
                (pid, tipe, nama_pakai, satuan, koef, harga_pakai, sid),
            )
        if tutup:
            conn.commit()
        return pid
    finally:
        if tutup:
            conn.close()


def tambah_item(proyek_id: int, kode_hspk: str, volume: float, lantai: str | None = None,
                catatan: str | None = None) -> int:
    """Tambahkan satu item katalog ke RAB proyek. Return id baris hasil_estimasi."""
    if volume is None or volume <= 0:
        raise NilaiTidakValid("Volume item tambahan harus lebih dari 0.")
    conn = _connect()
    try:
        pid = pastikan_pekerjaan(kode_hspk, conn)
        harga = conn.execute(
            "SELECT COALESCE(SUM(koefisien * harga_satuan), 0) FROM komponen_harga WHERE pekerjaan_id = ?", (pid,)
        ).fetchone()[0] * (1 + BUK_RATE)
        satuan = SATUAN.get(kode_hspk) or "unit"
        hid = conn.execute(
            """INSERT INTO hasil_estimasi (proyek_id, elemen_id, pekerjaan_id, volume_pekerjaan, subtotal_biaya,
                   rumus, catatan, lantai, item_tambahan)
               VALUES (?, NULL, ?, ?, ?, ?, ?, ?, 1)""",
            (proyek_id, pid, volume, volume * harga,
             f"Item tambahan dari katalog HSPK {kode_dasar(kode_hspk)}: volume diisi pengguna = {volume:g} {satuan}",
             (catatan or "").strip() or None, (lantai or "").strip() or None),
        ).lastrowid
        conn.execute("UPDATE proyek SET tanggal_diubah = CURRENT_TIMESTAMP WHERE id = ?", (proyek_id,))
        conn.commit()
    finally:
        conn.close()
    catat("edit", f"Item tambahan {kode_dasar(kode_hspk)} {AHSP[kode_hspk][1][:60]}: {volume:g} {satuan}"
                  + (f" ({lantai})" if lantai else ""), proyek_id)
    return hid


def hapus_item(hasil_id: int) -> None:
    """Hapus satu item tambahan. Baris hasil rule engine tidak bisa dihapus lewat fungsi ini."""
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT proyek_id, COALESCE(item_tambahan, 0) AS t FROM hasil_estimasi WHERE id = ?", (hasil_id,)
        ).fetchone()
        if row is None or not row["t"]:
            raise NilaiTidakValid("Hanya item tambahan dari katalog yang bisa dihapus.")
        conn.execute("DELETE FROM hasil_estimasi WHERE id = ?", (hasil_id,))
        conn.commit()
    finally:
        conn.close()
    catat("edit", f"Item tambahan dihapus (baris {hasil_id})", row["proyek_id"])
