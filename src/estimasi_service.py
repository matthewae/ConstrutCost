"""
Pipeline KF-1 s.d. KF-4:  file IFC -> validasi -> elemen_proyek -> rule engine -> hasil_estimasi.
KF-19: dimensi satu elemen diubah pengguna -> rule engine dijalankan ulang untuk elemen itu saja.
Penulangan: tipe elemen (K1, B1, P1, ...) ditetapkan sebelum rule engine; mengubah konfigurasi
tipe menghitung ulang pembesian seluruh proyek (hitung_ulang_penulangan).
"""

import json

from database.estimasi_repository import BUK_RATE, _connect
from database.init_db import pastikan_skema
from database.penulangan_repository import pasang_tipe, rapikan_tipe
from database.seed_data import seed_pekerjaan
from ifc_reader import buka_dan_validasi, ekstrak_elemen
from klasifikasi import ElementType
from rules import PARAMETER_DEFAULT, proses_semua, siapkan_konteks, terapkan_rules
from rules.definitions import RULES
from rules.dimensi import DimensiTidakValid, kolom_dimensi, turunkan_dari, validasi

_KOLOM_ELEMEN = (
    "global_id",
    "ifc_type",
    "kelas",
    "predefined_type",
    "nama",
    "lantai",
    "elevasi_lantai",
    "panjang",
    "lebar",
    "tinggi",
    "tebal",
    "luas",
    "volume",
    "keliling",
    "kemiringan",
    "luas_bukaan",
    "sumber_volume",
    "sumber_dimensi",
    "tipe_id",
)
RULES_PEMBESIAN = [r for r in RULES if r.kode.startswith("BSI.")]


def _harga_dan_kode(conn):
    """harga satuan per pekerjaan_id (jumlah komponen x (1 + BUK), sama dengan
    get_harga_satuan_pekerjaan()) dan peta kode_ahsp -> pekerjaan_id."""
    harga = {
        r["pekerjaan_id"]: r["h"] * (1 + BUK_RATE)
        for r in conn.execute(
            "SELECT pekerjaan_id, SUM(koefisien*harga_satuan) AS h FROM komponen_harga GROUP BY pekerjaan_id"
        )
    }
    kode_ke_id = {r["kode_ahsp"]: r["id"] for r in conn.execute("SELECT id, kode_ahsp FROM pekerjaan")}
    return harga, kode_ke_id


def _simpan_hasil(conn, proyek_id, elemen_id, hasil, harga, kode_ke_id, peringatan) -> int:
    n = 0
    for h in hasil:
        pid = kode_ke_id.get(h.kode)
        if pid is None:
            peringatan.append(f"Kode pekerjaan '{h.kode}' belum ada di tabel pekerjaan (jalankan seed).")
            continue
        conn.execute(
            """INSERT INTO hasil_estimasi
                   (proyek_id, elemen_id, pekerjaan_id, volume_pekerjaan, subtotal_biaya, rumus, uraian, diameter)
               VALUES (?,?,?,?,?,?,?,?)""",
            (proyek_id, elemen_id, pid, h.volume, h.volume * harga.get(pid, 0.0), h.rumus,
             h.uraian or None, h.diameter),
        )
        n += 1
    return n


def jalankan_estimasi(proyek_id: int, model=None, progress=None, parameter=PARAMETER_DEFAULT) -> dict:
    """Parse IFC proyek lalu isi elemen_proyek + hasil_estimasi.

    `model`    : ifcopenshell.file yang sudah dibuka saat validasi (KF-1), supaya file tidak dibaca dua kali.
                 Bila None, file dibuka dan divalidasi ulang dari path proyek.
    `progress` : callable(i, n, teks) untuk indikator proses.

    PERHATIAN: menimpa hasil sebelumnya, termasuk edit volume (KF-6) dan dimensi (KF-19) manual.
    """
    conn = _connect()
    try:
        pastikan_skema(conn)
    finally:
        conn.close()
    seed_pekerjaan()  # idempotent: memastikan master pekerjaan/harga ada

    conn = _connect()
    try:
        row = conn.execute(
            "SELECT path_file_ifc FROM proyek WHERE id = ?", (proyek_id,)
        ).fetchone()
        if not row or not row["path_file_ifc"]:
            raise ValueError("Proyek ini tidak punya path file IFC.")
        if model is None:
            model = buka_dan_validasi(row["path_file_ifc"], terisolasi=True).model

        elemen, peringatan = ekstrak_elemen(model, progress)
        harga, kode_ke_id = _harga_dan_kode(conn)

        conn.execute("DELETE FROM hasil_estimasi WHERE proyek_id = ?", (proyek_id,))
        conn.execute("DELETE FROM elemen_proyek WHERE proyek_id = ?", (proyek_id,))
        pasang_tipe(conn, proyek_id, elemen, parameter.batas_kemiringan_dak)
        konteks, keluaran, dilewati = proses_semua(elemen, parameter)
        peringatan.extend(dilewati)

        kolom = ", ".join(_KOLOM_ELEMEN)
        tanda = ", ".join("?" * (len(_KOLOM_ELEMEN) + 1))
        n_hasil = 0
        for el, hasil in keluaran:
            nilai = [
                json.dumps(el[k], ensure_ascii=False) if k == "sumber_dimensi" else el[k]
                for k in _KOLOM_ELEMEN
            ]
            cur = conn.execute(
                f"INSERT INTO elemen_proyek (proyek_id, {kolom}) VALUES ({tanda})",
                (proyek_id, *nilai),
            )
            n_hasil += _simpan_hasil(conn, proyek_id, cur.lastrowid, hasil, harga, kode_ke_id, peringatan)

        rapikan_tipe(conn, proyek_id)
        conn.execute(
            "UPDATE proyek SET tanggal_diubah = CURRENT_TIMESTAMP WHERE id = ?",
            (proyek_id,),
        )
        conn.commit()
        return {
            "elemen": len(elemen),
            "baris_hasil": n_hasil,
            "peringatan": peringatan,
            "konteks": konteks,
        }
    finally:
        conn.close()


def _baris_ke_elemen(row) -> dict:
    el = dict(row)
    try:
        el["sumber_dimensi"] = json.loads(el.get("sumber_dimensi") or "{}")
    except ValueError:
        el["sumber_dimensi"] = {}
    return el


def ambil_elemen(elemen_id: int) -> dict | None:
    """Satu baris elemen_proyek (sumber_dimensi sudah berupa dict)."""
    conn = _connect()
    try:
        row = conn.execute("SELECT * FROM elemen_proyek WHERE id = ?", (elemen_id,)).fetchone()
        return _baris_ke_elemen(row) if row else None
    finally:
        conn.close()


def hitung_ulang_elemen(elemen_id: int, dimensi: dict, parameter=PARAMETER_DEFAULT) -> dict:
    """KF-19 / UC-03: simpan dimensi baru satu elemen lalu hitung ulang QTO & biayanya.

    `dimensi` berisi dimensi primer dan/atau turunan (lihat rules/dimensi.py). Dimensi turunan
    yang tidak diisi dan dipengaruhi dimensi yang diubah dihitung ulang dengan asumsi bentuk
    reguler; yang tidak terpengaruh tetap memakai nilai dari model. Hanya baris
    hasil_estimasi milik elemen ini yang diganti (termasuk volume yang sebelumnya diedit manual);
    elemen lain tidak tersentuh.

    Return {"baris": jumlah item pekerjaan baru, "dilewati": [...], "berubah": [kunci dimensi]}.
    Melempar DimensiTidakValid bila nilai tidak valid.
    """
    conn = _connect()
    try:
        row = conn.execute("SELECT * FROM elemen_proyek WHERE id = ?", (elemen_id,)).fetchone()
        if row is None:
            raise DimensiTidakValid("Elemen tidak ditemukan. Muat ulang hasil estimasi.")
        el = _baris_ke_elemen(row)
        try:
            kelas = ElementType(el["kelas"])
        except ValueError:
            raise DimensiTidakValid("Dimensi elemen jenis ini tidak dapat diubah.") from None

        baru = validasi(kelas, dimensi)
        primer, turunan = kolom_dimensi(kelas)
        gabung = {k: el.get(k) for k in (*primer, *turunan)}
        gabung.update(baru)
        # turunan yang tidak diisi pengguna mengikuti dimensi yang diubah
        for k, v in turunkan_dari(kelas, gabung, [k for k, v in baru.items() if v is not None]).items():
            if k not in baru or baru[k] is None:
                gabung[k] = v

        berubah = [
            k for k, v in gabung.items()
            if v is not None and (el.get(k) is None or abs(v - el[k]) > 1e-9)
        ]
        el.update(gabung)
        for k in berubah:
            el["sumber_dimensi"][k] = "manual"
        if "volume" in berubah:
            el["sumber_volume"] = "manual"

        # konteks bangunan (lantai dasar, sumber lantai/plafon) dari seluruh elemen proyek
        semua = [
            el if r["id"] == elemen_id else dict(r)
            for r in conn.execute("SELECT * FROM elemen_proyek WHERE proyek_id = ?", (el["proyek_id"],))
        ]
        konteks = siapkan_konteks(semua)
        pasang_tipe(conn, el["proyek_id"], [el], parameter.batas_kemiringan_dak)  # penampang bisa berubah
        hasil, dilewati = terapkan_rules(el, konteks, parameter)

        harga, kode_ke_id = _harga_dan_kode(conn)
        kolom = [k for k in ("panjang", "lebar", "tinggi", "tebal", "luas", "volume", "keliling",
                             "kemiringan", "luas_bukaan") if k in gabung]
        conn.execute(
            f"UPDATE elemen_proyek SET {', '.join(f'{k} = ?' for k in kolom)}, sumber_volume = ?, "
            "sumber_dimensi = ?, dimensi_manual = 1, tipe_id = ? WHERE id = ?",
            (*[el[k] for k in kolom], el.get("sumber_volume"),
             json.dumps(el["sumber_dimensi"], ensure_ascii=False), el["tipe_id"], elemen_id),
        )
        conn.execute("DELETE FROM hasil_estimasi WHERE elemen_id = ?", (elemen_id,))
        n = _simpan_hasil(conn, el["proyek_id"], elemen_id, hasil, harga, kode_ke_id, dilewati)
        rapikan_tipe(conn, el["proyek_id"])
        conn.execute(
            "UPDATE proyek SET tanggal_diubah = CURRENT_TIMESTAMP WHERE id = ?", (el["proyek_id"],)
        )
        conn.commit()
        return {"baris": n, "dilewati": dilewati, "berubah": berubah}
    finally:
        conn.close()


def hitung_ulang_penulangan(proyek_id: int, parameter=PARAMETER_DEFAULT) -> dict:
    """Hitung ulang seluruh pembesian proyek dari elemen tersimpan setelah tipe penulangan diubah.
    Pekerjaan lain (beton, bekisting, dinding, ...) dan edit volumenya tidak tersentuh; baris
    pembesian yang volumenya diedit manual diganti hasil perhitungan baru.
    Return {"baris": jumlah baris pembesian, "berat": total kg}."""
    conn = _connect()
    try:
        semua = [_baris_ke_elemen(r) for r in conn.execute(
            "SELECT * FROM elemen_proyek WHERE proyek_id = ?", (proyek_id,)
        )]
        konteks = siapkan_konteks(semua)
        pasang_tipe(conn, proyek_id, semua, parameter.batas_kemiringan_dak)
        harga, kode_ke_id = _harga_dan_kode(conn)
        conn.execute(
            """DELETE FROM hasil_estimasi WHERE proyek_id = ? AND pekerjaan_id IN
                   (SELECT id FROM pekerjaan WHERE kode_ahsp LIKE 'BSI.%')""",
            (proyek_id,),
        )
        n, berat, catatan = 0, 0.0, []
        for el in semua:
            conn.execute("UPDATE elemen_proyek SET tipe_id = ? WHERE id = ?", (el["tipe_id"], el["id"]))
            hasil, _ = terapkan_rules(el, konteks, parameter, RULES_PEMBESIAN)
            n += _simpan_hasil(conn, proyek_id, el["id"], hasil, harga, kode_ke_id, catatan)
            berat += sum(h.volume for h in hasil)
        rapikan_tipe(conn, proyek_id)
        conn.execute("UPDATE proyek SET tanggal_diubah = CURRENT_TIMESTAMP WHERE id = ?", (proyek_id,))
        conn.commit()
        return {"baris": n, "berat": berat}
    finally:
        conn.close()
