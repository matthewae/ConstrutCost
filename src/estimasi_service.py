"""
Pipeline KF-2 + KF-3 + KF-4:  file IFC -> elemen_proyek -> rule engine -> hasil_estimasi.
"""

from database.estimasi_repository import _connect, BUK_RATE
from database.seed_data import seed_pekerjaan
from ifc_reader import extract_elements
from rules import terapkan_rules


def jalankan_estimasi(proyek_id: int) -> dict:
    """Parse ulang IFC proyek dan isi elemen_proyek + hasil_estimasi.
    PERHATIAN: menimpa hasil sebelumnya, termasuk edit manual (KF-19 bisa memperhalus ini nanti)."""
    seed_pekerjaan()  # idempotent: memastikan master pekerjaan/harga ada
    conn = _connect()
    try:
        row = conn.execute("SELECT path_file_ifc FROM proyek WHERE id = ?", (proyek_id,)).fetchone()
        if not row or not row["path_file_ifc"]:
            raise ValueError("Proyek ini tidak punya path file IFC.")

        elemen, peringatan = extract_elements(row["path_file_ifc"])

        # harga satuan = jumlah komponen x (1 + BUK), sama dengan get_harga_satuan_pekerjaan()
        harga = {r["pekerjaan_id"]: r["h"] * (1 + BUK_RATE) for r in conn.execute(
            "SELECT pekerjaan_id, SUM(koefisien*harga_satuan) AS h FROM komponen_harga GROUP BY pekerjaan_id")}
        kode_ke_id = {r["kode_ahsp"]: r["id"] for r in conn.execute("SELECT id, kode_ahsp FROM pekerjaan")}

        conn.execute("DELETE FROM hasil_estimasi WHERE proyek_id = ?", (proyek_id,))
        conn.execute("DELETE FROM elemen_proyek WHERE proyek_id = ?", (proyek_id,))

        n_hasil = 0
        for el in elemen:
            cur = conn.execute(
                """INSERT INTO elemen_proyek (proyek_id, global_id, ifc_type, predefined_type, nama, lantai,
                                              panjang, luas, volume, sumber_volume)
                   VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (proyek_id, el["global_id"], el["ifc_type"], el["predefined_type"], el["nama"], el["lantai"],
                 el["panjang"], el["luas"], el["volume"], el["sumber_volume"]))
            elemen_id = cur.lastrowid

            hasil, dilewati = terapkan_rules(el)
            peringatan.extend(dilewati)
            for h in hasil:
                pid = kode_ke_id.get(h.kode)
                if pid is None:
                    peringatan.append(f"Kode pekerjaan '{h.kode}' belum ada di tabel pekerjaan (jalankan seed).")
                    continue
                conn.execute(
                    """INSERT INTO hasil_estimasi (proyek_id, elemen_id, pekerjaan_id, volume_pekerjaan, subtotal_biaya)
                       VALUES (?,?,?,?,?)""",
                    (proyek_id, elemen_id, pid, h.volume, h.volume * harga.get(pid, 0.0)))
                n_hasil += 1

        conn.execute("UPDATE proyek SET tanggal_diubah = CURRENT_TIMESTAMP WHERE id = ?", (proyek_id,))
        conn.commit()
        return {"elemen": len(elemen), "baris_hasil": n_hasil, "peringatan": peringatan}
    finally:
        conn.close()