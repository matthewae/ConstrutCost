"""
Pipeline KF-1 s.d. KF-4:  file IFC -> validasi -> elemen_proyek -> rule engine -> hasil_estimasi.
"""

import json

from database.estimasi_repository import BUK_RATE, _connect
from database.init_db import pastikan_skema
from database.seed_data import seed_pekerjaan
from ifc_reader import buka_dan_validasi, ekstrak_elemen
from rules import PARAMETER_DEFAULT, proses_semua

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
)


def jalankan_estimasi(proyek_id: int, model=None, progress=None, parameter=PARAMETER_DEFAULT) -> dict:
    """Parse IFC proyek lalu isi elemen_proyek + hasil_estimasi.

    `model`    : ifcopenshell.file yang sudah dibuka saat validasi (KF-1), supaya file tidak dibaca dua kali.
                 Bila None, file dibuka dan divalidasi ulang dari path proyek.
    `progress` : callable(i, n, teks) untuk indikator proses.

    PERHATIAN: menimpa hasil sebelumnya, termasuk edit manual (KF-19 bisa memperhalus ini nanti).
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
        konteks, keluaran, dilewati = proses_semua(elemen, parameter)
        peringatan.extend(dilewati)

        # harga satuan = jumlah komponen x (1 + BUK), sama dengan get_harga_satuan_pekerjaan()
        harga = {
            r["pekerjaan_id"]: r["h"] * (1 + BUK_RATE)
            for r in conn.execute(
                "SELECT pekerjaan_id, SUM(koefisien*harga_satuan) AS h FROM komponen_harga GROUP BY pekerjaan_id"
            )
        }
        kode_ke_id = {
            r["kode_ahsp"]: r["id"]
            for r in conn.execute("SELECT id, kode_ahsp FROM pekerjaan")
        }

        conn.execute("DELETE FROM hasil_estimasi WHERE proyek_id = ?", (proyek_id,))
        conn.execute("DELETE FROM elemen_proyek WHERE proyek_id = ?", (proyek_id,))

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
            elemen_id = cur.lastrowid

            for h in hasil:
                pid = kode_ke_id.get(h.kode)
                if pid is None:
                    peringatan.append(
                        f"Kode pekerjaan '{h.kode}' belum ada di tabel pekerjaan (jalankan seed)."
                    )
                    continue
                conn.execute(
                    """INSERT INTO hasil_estimasi
                           (proyek_id, elemen_id, pekerjaan_id, volume_pekerjaan, subtotal_biaya, rumus)
                       VALUES (?,?,?,?,?,?)""",
                    (proyek_id, elemen_id, pid, h.volume, h.volume * harga.get(pid, 0.0), h.rumus),
                )
                n_hasil += 1

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
