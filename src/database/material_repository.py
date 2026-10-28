"""
Pilihan material per proyek dan per elemen (database/material.py) serta pengaruhnya ke hasil estimasi.

- Proyek : proyek.material, JSON {slot: kunci}, hanya slot yang berbeda dari bawaan.
- Elemen : elemen_proyek.material, JSON {slot: kunci}, menimpa pilihan proyek untuk elemen itu saja
           (mis. semua dinding bata ringan, tetapi "Dinding A" bata merah).
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


def pilihan_elemen(teks: str | None) -> dict:
    """Pilihan khusus elemen yang sah: {slot: kunci}."""
    return {k: v for k, v in _baca(teks).items() if k in SLOT and any(o.kunci == v for o in SLOT[k].opsi)}


def kode_elemen(kode_proyek_peta: dict, kode_ke_id: dict, material_elemen: str | None) -> dict:
    """Peta kode -> pekerjaan_id untuk satu elemen: peta proyek ditimpa pilihan khusus elemen."""
    khusus = pilihan_elemen(material_elemen)
    if not khusus:
        return kode_proyek_peta
    peta = dict(kode_proyek_peta)
    for slot, kunci in khusus.items():
        pid = kode_ke_id.get(kode_varian(slot, kunci))
        if pid is not None:
            peta[slot] = pid
    return peta


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
        elemen_khusus = {
            r["id"]: pilihan_elemen(r["material"])
            for r in conn.execute(
                "SELECT id, material FROM elemen_proyek WHERE proyek_id = ? AND material IS NOT NULL", (proyek_id,)
            )
        }
        n = 0
        for slot in berubah:
            khusus = [e for e, m in elemen_khusus.items() if slot in m]  # elemen dengan pilihan sendiri tetap
            syarat = "proyek_id = ?"
            if khusus:
                syarat += f" AND (elemen_id IS NULL OR elemen_id NOT IN ({', '.join('?' * len(khusus))}))"
            n += _ganti_baris(conn, syarat, (proyek_id, *khusus), slot, baru[slot], id_kode)
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


def _ganti_baris(conn, syarat: str, args: tuple, slot: str, kunci: str, id_kode: dict) -> int:
    tujuan = id_kode.get(kode_varian(slot, kunci))
    if tujuan is None:
        raise ValueError(f"Pekerjaan untuk pilihan '{kunci}' belum ada. Muat ulang aplikasi.")
    asal = [id_kode[k] for k in (kode_varian(slot, o.kunci) for o in SLOT[slot].opsi) if k in id_kode]
    return conn.execute(
        f"""UPDATE hasil_estimasi SET pekerjaan_id = ?,
                subtotal_biaya = volume_pekerjaan * COALESCE(harga_manual, ?)
            WHERE {syarat} AND pekerjaan_id IN ({", ".join("?" * len(asal))})""",
        (tujuan, harga_satuan(conn, tujuan), *args, *asal),
    ).rowcount


def material_elemen(elemen_id: int) -> dict:
    """Slot material yang dipakai baris RAB satu elemen: {slot: {"kunci", "khusus", "volume", "satuan"}}.
    "khusus" = pilihan khusus elemen (bukan pilihan proyek)."""
    conn = _connect()
    try:
        el = conn.execute("SELECT proyek_id, material FROM elemen_proyek WHERE id = ?", (elemen_id,)).fetchone()
        if el is None:
            return {}
        proyek = muat_pilihan(el["proyek_id"], conn)
        khusus = pilihan_elemen(el["material"])
        hasil = {}
        for r in conn.execute(
            """SELECT p.kode_ahsp, p.satuan, SUM(he.volume_pekerjaan) AS v FROM hasil_estimasi he
               JOIN pekerjaan p ON p.id = he.pekerjaan_id WHERE he.elemen_id = ? GROUP BY p.kode_ahsp""",
            (elemen_id,),
        ):
            slot = r["kode_ahsp"].split("~")[0]
            if slot in SLOT:
                d = hasil.setdefault(slot, {"kunci": khusus.get(slot, proyek[slot]), "khusus": slot in khusus,
                                            "volume": 0.0, "satuan": r["satuan"]})
                d["volume"] += r["v"] or 0.0
        return dict(sorted(hasil.items(), key=lambda x: list(SLOT).index(x[0])))
    finally:
        conn.close()


def simpan_material_elemen(elemen_id: int, pilihan: dict) -> dict:
    """Pilihan khusus satu elemen. Slot yang pilihannya sama dengan pilihan proyek tidak disimpan sebagai
    pilihan khusus (elemen kembali mengikuti proyek). Baris RAB elemen ini langsung diganti pekerjaannya;
    volume, harga khusus, dan catatan tetap. Return {"berubah": [slot], "baris": n}."""
    tidak_dikenal = [k for k in pilihan if k not in SLOT]
    if tidak_dikenal:
        raise ValueError(f"Pilihan material tidak dikenal: {', '.join(tidak_dikenal)}")
    conn = _connect()
    try:
        el = conn.execute("SELECT proyek_id, nama, material FROM elemen_proyek WHERE id = ?", (elemen_id,)).fetchone()
        if el is None:
            raise ValueError("Elemen tidak ditemukan. Muat ulang hasil estimasi.")
        proyek = muat_pilihan(el["proyek_id"], conn)
        lama = {**proyek, **pilihan_elemen(el["material"])}
        khusus = {**pilihan_elemen(el["material"]), **pilihan}
        khusus = {k: v for k, v in khusus.items() if v != proyek[k] and any(o.kunci == v for o in SLOT[k].opsi)}
        baru = {**proyek, **khusus}
        id_kode = {r["kode_ahsp"]: r["id"] for r in conn.execute("SELECT id, kode_ahsp FROM pekerjaan")}
        berubah = [k for k in SLOT if baru[k] != lama[k]]
        n = sum(_ganti_baris(conn, "elemen_id = ?", (elemen_id,), k, baru[k], id_kode) for k in berubah)
        conn.execute("UPDATE elemen_proyek SET material = ? WHERE id = ?",
                     (json.dumps(khusus, ensure_ascii=False) if khusus else None, elemen_id))
        conn.execute("UPDATE proyek SET tanggal_diubah = CURRENT_TIMESTAMP WHERE id = ?", (el["proyek_id"],))
        conn.commit()
    finally:
        conn.close()
    if berubah:
        ringkas = "; ".join(f"{SLOT[k].judul}: {SLOT[k].cari(baru[k]).label}" for k in berubah)
        catat("material", f"Material elemen {el['nama'] or elemen_id} diubah: {ringkas}", el["proyek_id"])
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
