"""
Tipe penulangan per proyek (tabel tipe_penulangan) dan rekap kebutuhan besi per diameter.

Saat estimasi dijalankan, elemen struktur dikelompokkan menurut kelompok + penampang
(rules/penulangan.kunci_tipe). Setiap kelompok baru mendapat konfigurasi bawaan. Konfigurasi
yang sudah diubah pengguna (diubah = 1) dipertahankan saat estimasi diulang.
"""

import math
from dataclasses import fields

from aktivitas import catat
from database.estimasi_repository import _connect
from rules.penulangan import (
    AWALAN_KODE,
    LINIER,
    URUTAN,
    Penulangan,
    PenulanganTidakValid,
    bawaan,
    berat_per_m,
    jenis_baja,
    kunci_tipe,
    label_d,
    label_tipe,
    validasi,
    PANJANG_BATANG,
)

_KOLOM_KONFIG = [f.name for f in fields(Penulangan) if f.name != "kelompok"]

__all__ = [
    "PenulanganTidakValid",
    "daftar_tipe",
    "kebutuhan_besi",
    "pasang_tipe",
    "rapikan_tipe",
    "ubah_tipe",
    "kembalikan_tipe_bawaan",
]


def ke_penulangan(row) -> Penulangan:
    return Penulangan(row["kelompok"], **{k: row[k] for k in _KOLOM_KONFIG})


def pasang_tipe(conn, proyek_id: int, elemen: list, batas_kemiringan_dak: float = 5.0) -> None:
    """Isi el['tipe_id'] dan el['penulangan'] untuk setiap elemen struktur (diubah di tempat).
    Tipe baru dibuat dengan konfigurasi bawaan. Tidak melakukan commit."""
    ada = {
        (r["kelompok"], r["b_cm"], r["h_cm"]): r
        for r in conn.execute("SELECT * FROM tipe_penulangan WHERE proyek_id = ?", (proyek_id,))
    }
    for el in elemen:
        kunci = kunci_tipe(el, batas_kemiringan_dak)
        if kunci is None:
            el["tipe_id"], el["penulangan"] = None, None
            continue
        row = ada.get(kunci)
        if row is None:
            kelompok, b_cm, h_cm = kunci
            p = bawaan(kelompok, b_cm / 100 or None, h_cm / 100)
            cur = conn.execute(
                f"INSERT INTO tipe_penulangan (proyek_id, kelompok, kode, b_cm, h_cm, {', '.join(_KOLOM_KONFIG)}) "
                f"VALUES (?,?,?,?,?{', ?' * len(_KOLOM_KONFIG)})",
                (proyek_id, kelompok, "?", b_cm, h_cm, *[getattr(p, k) for k in _KOLOM_KONFIG]),
            )
            row = conn.execute("SELECT * FROM tipe_penulangan WHERE id = ?", (cur.lastrowid,)).fetchone()
            ada[kunci] = row
        el["tipe_id"] = row["id"]
        el["penulangan"] = ke_penulangan(row)


def rapikan_tipe(conn, proyek_id: int) -> None:
    """Hapus tipe yang tidak dipakai elemen mana pun (kecuali yang diubah pengguna), lalu beri
    kode berurutan per kelompok: penampang terbesar = K1, B1, ... Tidak melakukan commit."""
    conn.execute(
        """DELETE FROM tipe_penulangan WHERE proyek_id = ? AND COALESCE(diubah, 0) = 0
           AND id NOT IN (SELECT tipe_id FROM elemen_proyek WHERE proyek_id = ? AND tipe_id IS NOT NULL)""",
        (proyek_id, proyek_id),
    )
    rows = conn.execute(
        "SELECT id, kelompok FROM tipe_penulangan WHERE proyek_id = ? ORDER BY kelompok, b_cm * h_cm DESC, h_cm DESC, b_cm DESC",
        (proyek_id,),
    ).fetchall()
    nomor = {}
    for r in rows:
        nomor[r["kelompok"]] = nomor.get(r["kelompok"], 0) + 1
        conn.execute(
            "UPDATE tipe_penulangan SET kode = ? WHERE id = ?",
            (f"{AWALAN_KODE[r['kelompok']]}{nomor[r['kelompok']]}", r["id"]),
        )


def daftar_tipe(proyek_id: int) -> list:
    """Tipe penulangan proyek beserta jumlah elemen dan ringkasan, urut fondasi -> dak."""
    conn = _connect()
    try:
        rows = conn.execute(
            """SELECT tp.*, (SELECT COUNT(*) FROM elemen_proyek ep WHERE ep.tipe_id = tp.id) AS jumlah_elemen,
                      (SELECT COALESCE(SUM(h.volume_pekerjaan), 0) FROM hasil_estimasi h
                         JOIN elemen_proyek ep ON ep.id = h.elemen_id
                        WHERE ep.tipe_id = tp.id AND h.diameter IS NOT NULL) AS berat_besi
               FROM tipe_penulangan tp WHERE tp.proyek_id = ?""",
            (proyek_id,),
        ).fetchall()
    finally:
        conn.close()
    hasil = []
    for r in rows:
        d = dict(r)
        p = ke_penulangan(r)
        d["penulangan"] = p
        d["ringkas"] = p.ringkas()
        d["label"] = label_tipe(r["kelompok"], r["kode"], r["b_cm"] / 100, r["h_cm"] / 100)
        hasil.append(d)
    hasil.sort(key=lambda d: (URUTAN.index(d["kelompok"]), int(d["kode"][1:] or 0)))
    return hasil


def ubah_tipe(tipe_id: int, p: Penulangan) -> None:
    """Simpan konfigurasi tulangan baru (validasi dulu). Hitung ulang dilakukan pemanggil."""
    validasi(p)
    conn = _connect()
    try:
        conn.execute(
            f"UPDATE tipe_penulangan SET {', '.join(f'{k} = ?' for k in _KOLOM_KONFIG)}, diubah = 1 WHERE id = ?",
            (*[getattr(p, k) for k in _KOLOM_KONFIG], tipe_id),
        )
        conn.commit()
        _catat_tipe(conn, tipe_id, f"diubah menjadi {p.ringkas()}")
    finally:
        conn.close()


def _catat_tipe(conn, tipe_id: int, pesan: str) -> None:
    r = conn.execute("SELECT * FROM tipe_penulangan WHERE id = ?", (tipe_id,)).fetchone()
    if r:
        label = label_tipe(r["kelompok"], r["kode"], r["b_cm"] / 100, r["h_cm"] / 100)
        catat("penulangan", f"Tipe {label} {pesan}", r["proyek_id"])


def kembalikan_tipe_bawaan(tipe_id: int) -> Penulangan:
    conn = _connect()
    try:
        r = conn.execute("SELECT * FROM tipe_penulangan WHERE id = ?", (tipe_id,)).fetchone()
        if r is None:
            raise PenulanganTidakValid("Tipe penulangan tidak ditemukan.")
        b = r["b_cm"] / 100 if r["kelompok"] in LINIER else None
        p = bawaan(r["kelompok"], b, r["h_cm"] / 100)
        conn.execute(
            f"UPDATE tipe_penulangan SET {', '.join(f'{k} = ?' for k in _KOLOM_KONFIG)}, diubah = 0 WHERE id = ?",
            (*[getattr(p, k) for k in _KOLOM_KONFIG], tipe_id),
        )
        conn.commit()
        _catat_tipe(conn, tipe_id, f"kembali ke bawaan {p.ringkas()}")
        return p
    finally:
        conn.close()


def kebutuhan_besi(proyek_id: int) -> list:
    """Rekap kebutuhan besi per diameter: berat (kg, termasuk sisa 5%), panjang (m'), dan jumlah
    batang 12 m yang perlu dibeli. Hanya pembesian rinci (yang memakai rasio tidak berdiameter)."""
    conn = _connect()
    try:
        rows = conn.execute(
            """SELECT diameter, SUM(volume_pekerjaan) AS berat FROM hasil_estimasi
               WHERE proyek_id = ? AND diameter IS NOT NULL GROUP BY diameter ORDER BY diameter""",
            (proyek_id,),
        ).fetchall()
    finally:
        conn.close()
    hasil = []
    for r in rows:
        d, berat = r["diameter"], r["berat"]
        wm = berat_per_m(d)
        panjang = berat / wm
        hasil.append({
            "diameter": d,
            "label": label_d(d),
            "jenis": jenis_baja(d),
            "berat_per_m": wm,
            "panjang": panjang,
            "berat": berat,
            "batang": math.ceil(panjang / PANJANG_BATANG - 1e-9),
        })
    return hasil
