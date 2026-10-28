"""
Pilihan material per proyek (database/material.py) dan pengaruhnya ke hasil estimasi.

Pilihan disimpan di proyek.material sebagai JSON {slot: kunci}, hanya slot yang berbeda dari bawaan.
"""

import json

from aktivitas import catat
from database.estimasi_repository import BUK_RATE, _connect
from database.material import SLOT, kode_varian, pilihan_lengkap, varian_terpilih


def _baca(teks: str | None) -> dict:
    try:
        data = json.loads(teks or "{}")
    except (ValueError, TypeError):
        return {}
    return data if isinstance(data, dict) else {}


def muat_pilihan(proyek_id: int, conn=None) -> dict:
    """{slot: kunci} lengkap (slot yang tidak disimpan = pilihan bawaan)."""
    tutup = conn is None
    conn = conn or _connect()
    try:
        row = conn.execute("SELECT material FROM proyek WHERE id = ?", (proyek_id,)).fetchone()
    finally:
        if tutup:
            conn.close()
    return pilihan_lengkap(_baca(row["material"] if row else None))


def kode_proyek(conn, proyek_id: int, kode_ke_id: dict) -> dict:
    """Peta kode keluaran rule -> pekerjaan_id untuk proyek ini: slot yang dipilih bukan bawaan diarahkan
    ke pekerjaan variannya. Dipakai setiap kali hasil rule engine disimpan."""
    peta = dict(kode_ke_id)
    for kode, varian in varian_terpilih(muat_pilihan(proyek_id, conn)).items():
        if varian in kode_ke_id:
            peta[kode] = kode_ke_id[varian]
    return peta


def harga_satuan(conn, pekerjaan_id: int) -> float:
    h = conn.execute(
        "SELECT COALESCE(SUM(koefisien * harga_satuan), 0) FROM komponen_harga WHERE pekerjaan_id = ?",
        (pekerjaan_id,),
    ).fetchone()[0]
    return h * (1 + BUK_RATE)


def simpan_pilihan(proyek_id: int, pilihan: dict) -> dict:
    """Simpan pilihan material proyek lalu ganti pekerjaan pada baris hasil yang sudah ada.

    Volume (termasuk yang diedit manual), harga satuan khusus, dan catatan baris tidak berubah; subtotal
    dihitung ulang dengan harga satuan pilihan baru. Return {"berubah": [slot], "baris": jumlah baris}."""
    tidak_dikenal = [k for k in pilihan if k not in SLOT]
    if tidak_dikenal:
        raise ValueError(f"Pilihan material tidak dikenal: {', '.join(tidak_dikenal)}")
    baru = pilihan_lengkap(pilihan)
    conn = _connect()
    try:
        lama = muat_pilihan(proyek_id, conn)
        berubah = [k for k in SLOT if baru[k] != lama[k]]
        id_kode = {r["kode_ahsp"]: r["id"] for r in conn.execute("SELECT id, kode_ahsp FROM pekerjaan")}
        n = 0
        for slot in berubah:
            tujuan = id_kode.get(kode_varian(slot, baru[slot]))
            if tujuan is None:
                raise ValueError(f"Pekerjaan untuk pilihan '{baru[slot]}' belum ada. Muat ulang aplikasi.")
            asal = [id_kode[k] for k in (kode_varian(slot, o.kunci) for o in SLOT[slot].opsi) if k in id_kode]
            harga = harga_satuan(conn, tujuan)
            tanda = ", ".join("?" * len(asal))
            n += conn.execute(
                f"""UPDATE hasil_estimasi SET pekerjaan_id = ?,
                        subtotal_biaya = volume_pekerjaan * COALESCE(harga_manual, ?)
                    WHERE proyek_id = ? AND pekerjaan_id IN ({tanda})""",
                (tujuan, harga, proyek_id, *asal),
            ).rowcount
        simpan = {k: v for k, v in baru.items() if v != SLOT[k].bawaan}
        conn.execute(
            "UPDATE proyek SET material = ?, tanggal_diubah = CURRENT_TIMESTAMP WHERE id = ?",
            (json.dumps(simpan, ensure_ascii=False) if simpan else None, proyek_id),
        )
        conn.commit()
    finally:
        conn.close()
    if berubah:
        ringkas = "; ".join(f"{SLOT[k].judul}: {SLOT[k].cari(baru[k]).label}" for k in berubah)
        catat("material", f"Pilihan material diubah ({n} baris RAB): {ringkas}", proyek_id)
    return {"berubah": berubah, "baris": n}


def ringkasan_opsi(conn=None) -> dict:
    """{kode varian: {"harga": harga satuan, "bahan": [(nama, satuan, koefisien)]}} untuk semua pilihan,
    dari harga dan komponen yang berlaku di database (dipakai combo box dialog Pilihan Material)."""
    tutup = conn is None
    conn = conn or _connect()
    try:
        hasil = {}
        for slot in SLOT.values():
            for o in slot.opsi:
                kode = kode_varian(slot.kode, o.kunci)
                p = conn.execute("SELECT id, satuan FROM pekerjaan WHERE kode_ahsp = ?", (kode,)).fetchone()
                if p is None:
                    continue
                bahan = [
                    (r["nama_komponen"], r["satuan"], r["koefisien"])
                    for r in conn.execute(
                        "SELECT nama_komponen, satuan, koefisien FROM komponen_harga "
                        "WHERE pekerjaan_id = ? AND tipe = 'bahan' ORDER BY id", (p["id"],)
                    )
                ]
                hasil[kode] = {"harga": harga_satuan(conn, p["id"]), "satuan": p["satuan"], "bahan": bahan}
        return hasil
    finally:
        if tutup:
            conn.close()
