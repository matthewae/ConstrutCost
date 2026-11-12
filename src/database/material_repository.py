"""
Pilihan material per proyek dan per elemen (database/material.py) serta pengaruhnya ke hasil estimasi.

- Proyek : proyek.material, JSON {slot: kunci}, hanya slot yang berbeda dari bawaan.
- Elemen : elemen_proyek.material, JSON {slot: kunci}, menimpa pilihan proyek untuk elemen itu saja
           (mis. semua dinding bata ringan, tetapi "Dinding A" bata merah).
"""

import json

from aktivitas import catat
from bahan_bekisting import (
    KAYU,
    KAYU_BAWAAN,
    KODE_BEKISTING,
    SLOT_KAYU,
    SLOT_TRIPLEK,
    TRIPLEK,
    TRIPLEK_BAWAAN,
    cari,
    ganti_komponen,
    kode_varian_bekisting,
    koefisien,
    nama_pendek,
    urai_varian,
)
from database.estimasi_repository import BUK_RATE, _connect
from database.material import SLOT, SLOT_BAHAN, kode_varian, pilihan_lengkap, varian_terpilih


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
    """Pilihan khusus elemen yang sah: {slot: kunci} (termasuk kayu / triplek bekisting elemen itu)."""
    return {k: v for k, v in _baca(teks).items() if k in SLOT and any(o.kunci == v for o in SLOT[k].opsi)}


def _bahan_bekisting_proyek(kode_proyek_peta: dict, kode_ke_id: dict) -> tuple:
    """(kayu, triplek) bekisting proyek, dibaca dari varian yang dipetakan untuk pekerjaan bekisting."""
    id_ke_kode = {v: k for k, v in kode_ke_id.items()}
    for kode in KODE_BEKISTING:
        urai = urai_varian(id_ke_kode.get(kode_proyek_peta.get(kode), ""))
        if urai:
            return urai[1], urai[2]
    return KAYU_BAWAAN, TRIPLEK_BAWAAN


def kode_elemen(kode_proyek_peta: dict, kode_ke_id: dict, material_elemen: str | None, conn=None) -> dict:
    """Peta kode -> pekerjaan_id untuk satu elemen: peta proyek ditimpa pilihan khusus elemen. Kayu / triplek
    bekisting khusus elemen mengarahkan semua pekerjaan bekisting elemen itu ke variannya (dibuat bila perlu)."""
    khusus = pilihan_elemen(material_elemen)
    if not khusus:
        return kode_proyek_peta
    peta = dict(kode_proyek_peta)
    for slot, kunci in khusus.items():
        if slot in SLOT_BAHAN:
            continue
        pid = kode_ke_id.get(kode_varian(slot, kunci))
        if pid is not None:
            peta[slot] = pid
    if any(k in khusus for k in SLOT_BAHAN):
        kayu, triplek = _bahan_bekisting_proyek(kode_proyek_peta, kode_ke_id)
        kayu, triplek = khusus.get(SLOT_KAYU, kayu), khusus.get(SLOT_TRIPLEK, triplek)
        for kode in KODE_BEKISTING:
            varian = kode_varian_bekisting(kode, kayu, triplek)
            if varian not in kode_ke_id and conn is not None:
                pastikan_varian_bekisting(conn, varian, kode_ke_id)
            if varian in kode_ke_id:
                peta[kode] = kode_ke_id[varian]
    return peta


def kode_proyek(conn, proyek_id: int, kode_ke_id: dict) -> dict:
    """Peta kode keluaran rule -> pekerjaan_id untuk proyek ini: slot yang dipilih bukan bawaan diarahkan
    ke pekerjaan variannya. Dipakai setiap kali hasil rule engine disimpan."""
    peta = dict(kode_ke_id)
    for kode, varian in varian_terpilih(muat_pilihan(proyek_id, conn)).items():
        if varian not in kode_ke_id and urai_varian(varian):
            pastikan_varian_bekisting(conn, varian, kode_ke_id)
        if varian in kode_ke_id:
            peta[kode] = kode_ke_id[varian]
    return peta


# ---------------------------------------------------------------- varian bahan bekisting


def pastikan_varian_bekisting(conn, kode: str, id_kode: dict | None = None) -> int | None:
    """id pekerjaan bekisting untuk kode "BSK.KOLOM~kayu+triplek"; dibuat dari pekerjaan bawaannya saat pertama
    dipilih (kayu, triplek, dan paku diganti; koefisien, upah, dan bahan lain sama)."""
    ada = conn.execute("SELECT id FROM pekerjaan WHERE kode_ahsp = ?", (kode,)).fetchone()
    if ada:
        if id_kode is not None:
            id_kode[kode] = ada["id"]
        return ada["id"]
    urai = urai_varian(kode)
    dasar = conn.execute("SELECT * FROM pekerjaan WHERE kode_ahsp = ?", (urai[0],)).fetchone() if urai else None
    if dasar is None:
        return None
    _kode, kayu, triplek = urai
    bk, bt = cari(KAYU, kayu, KAYU_BAWAAN), cari(TRIPLEK, triplek, TRIPLEK_BAWAAN)
    pid = conn.execute(
        "INSERT INTO pekerjaan (kode_ahsp, nama_pekerjaan, kategori, satuan, catatan) VALUES (?,?,?,?,?)",
        (kode, f"{dasar['nama_pekerjaan']} ({nama_pendek(bk)}, {nama_pendek(bt)})", dasar["kategori"],
         dasar["satuan"], dasar["catatan"]),
    ).lastrowid
    susun_varian_bekisting(conn, kode, pid)
    if id_kode is not None:
        id_kode[kode] = pid
    return pid


def susun_varian_bekisting(conn, kode: str, pid: int) -> None:
    """Komponen varian bekisting = analisa HSPK-nya dengan kayu, triplek, dan paku pilihan (bahan_bekisting).
    Harga mengikuti harga dasar di database (perubahan harga pengguna ikut terpakai)."""
    from database.seed_data import ANALISA, PEMETAAN, SUMBER

    dasar_kode, kayu, triplek = urai_varian(kode)
    hspk = PEMETAAN[dasar_kode][3]
    _sheet, uraian, _f, asal = ANALISA[hspk]
    komponen, ganti = ganti_komponen(asal, kayu, triplek)
    conn.execute("DELETE FROM komponen_harga WHERE pekerjaan_id = ?", (pid,))
    for tipe, nama, satuan, koef, harga in komponen:
        sd = conn.execute("SELECT id, harga FROM sumber_daya WHERE tipe = ? AND lower(nama) = lower(?) "
                          "AND lower(satuan) = lower(?)", (tipe, nama, satuan)).fetchone()
        if sd is None:
            sid = conn.execute(
                "INSERT INTO sumber_daya (tipe, nama, satuan, harga, harga_bawaan, sumber) VALUES (?,?,?,?,?,?)",
                (tipe, nama, satuan, harga, harga, "HSPK (bahan bekisting)")).lastrowid
        else:
            sid, harga = sd["id"], sd["harga"]
        conn.execute(
            "INSERT INTO komponen_harga (pekerjaan_id, tipe, nama_komponen, satuan, koefisien, harga_satuan, "
            "sumber_daya_id) VALUES (?,?,?,?,?,?,?)", (pid, tipe, nama, satuan, koef, harga, sid))
    catatan = f"{SUMBER} · {hspk} · {uraian}"
    if ganti:
        catatan += " · Bahan bekisting disesuaikan: " + "; ".join(ganti)
    conn.execute("UPDATE pekerjaan SET catatan = ? WHERE id = ?", (catatan, pid))


def _ganti_bekisting(conn, syarat: str, args: tuple, kayu: str, triplek: str, id_kode: dict) -> int:
    """Arahkan baris semua pekerjaan bekisting ke varian kayu & triplek pilihan."""
    n = 0
    for kode in KODE_BEKISTING:
        asal = [i for k, i in id_kode.items() if k == kode or k.startswith(kode + "~")]
        if not asal:
            continue
        tujuan = pastikan_varian_bekisting(conn, kode_varian_bekisting(kode, kayu, triplek), id_kode)
        if tujuan is None:
            continue
        n += conn.execute(
            f"""UPDATE hasil_estimasi SET pekerjaan_id = ?,
                    subtotal_biaya = volume_pekerjaan * COALESCE(harga_manual, ?)
                WHERE {syarat} AND pekerjaan_id IN ({", ".join("?" * len(asal))})""",
            (tujuan, harga_satuan(conn, tujuan), *args, *asal),
        ).rowcount
    return n


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
        if any(k in SLOT_BAHAN for k in berubah):
            khusus = [e for e, m in elemen_khusus.items() if any(k in m for k in SLOT_BAHAN)]
            syarat = "proyek_id = ?"
            if khusus:
                syarat += f" AND (elemen_id IS NULL OR elemen_id NOT IN ({', '.join('?' * len(khusus))}))"
            n += _ganti_bekisting(conn, syarat, (proyek_id, *khusus), baru[SLOT_KAYU], baru[SLOT_TRIPLEK], id_kode)
        for slot in berubah:
            if slot in SLOT_BAHAN:
                continue
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
            """SELECT p.id, p.kode_ahsp, p.satuan, SUM(he.volume_pekerjaan) AS v FROM hasil_estimasi he
               JOIN pekerjaan p ON p.id = he.pekerjaan_id WHERE he.elemen_id = ? GROUP BY p.kode_ahsp""",
            (elemen_id,),
        ):
            slot = r["kode_ahsp"].split("~")[0]
            if slot in SLOT:
                d = hasil.setdefault(slot, {"kunci": khusus.get(slot, proyek[slot]), "khusus": slot in khusus,
                                            "volume": 0.0, "satuan": r["satuan"]})
                d["volume"] += r["v"] or 0.0
            elif urai_varian(r["kode_ahsp"]):  # bekisting: kayu (m³) & triplek (lembar) elemen ini
                kom = conn.execute("SELECT tipe, nama_komponen, satuan, koefisien FROM komponen_harga "
                                   "WHERE pekerjaan_id = ?", (r["id"],)).fetchall()
                koef = koefisien([(k["tipe"], k["nama_komponen"], k["satuan"], k["koefisien"]) for k in kom])
                for sl, kf, sat in ((SLOT_KAYU, koef[0], "m3"), (SLOT_TRIPLEK, koef[1], "lembar")):
                    if kf > 0:
                        d = hasil.setdefault(sl, {"kunci": khusus.get(sl, proyek[sl]), "khusus": sl in khusus,
                                                  "volume": 0.0, "satuan": sat})
                        d["volume"] += (r["v"] or 0.0) * kf
        return dict(sorted(hasil.items(), key=lambda x: list(SLOT).index(x[0])))
    finally:
        conn.close()


def simpan_material_elemen(elemen_id: int, pilihan: dict) -> dict:
    """Pilihan khusus satu elemen. Slot yang pilihannya sama dengan pilihan proyek tidak disimpan sebagai
    pilihan khusus (elemen kembali mengikuti proyek). Baris RAB elemen ini langsung diganti pekerjaannya;
    volume, harga khusus, dan catatan tetap. Return {"berubah": [slot], "baris": n}."""
    return simpan_material_elemen_banyak([elemen_id], pilihan)


def simpan_material_elemen_banyak(elemen_ids: list, pilihan: dict) -> dict:
    """Pilihan khusus untuk beberapa elemen sekaligus (mis. semua kolom yang tersaring di Kebutuhan Bahan), dalam
    satu transaksi. Kayu / triplek bekisting juga dapat dipilih per elemen. Return {"berubah": [slot], "baris": n,
    "elemen": jumlah elemen yang berubah}."""
    tidak_dikenal = [k for k in pilihan if k not in SLOT]
    if tidak_dikenal:
        raise ValueError(f"Pilihan material tidak dikenal: {', '.join(tidak_dikenal)}")
    conn = _connect()
    berubah_semua, n, n_elemen, proyek_id, nama = [], 0, 0, None, []
    try:
        id_kode = {r["kode_ahsp"]: r["id"] for r in conn.execute("SELECT id, kode_ahsp FROM pekerjaan")}
        proyek_cache = {}
        for elemen_id in dict.fromkeys(elemen_ids):
            el = conn.execute("SELECT proyek_id, nama, material FROM elemen_proyek WHERE id = ?",
                              (elemen_id,)).fetchone()
            if el is None:
                raise ValueError("Elemen tidak ditemukan. Muat ulang hasil estimasi.")
            proyek_id = el["proyek_id"]
            if proyek_id not in proyek_cache:
                proyek_cache[proyek_id] = muat_pilihan(proyek_id, conn)
            proyek = proyek_cache[proyek_id]
            lama = {**proyek, **pilihan_elemen(el["material"])}
            khusus = {**pilihan_elemen(el["material"]), **pilihan}
            khusus = {k: v for k, v in khusus.items() if v != proyek[k] and any(o.kunci == v for o in SLOT[k].opsi)}
            baru = {**proyek, **khusus}
            berubah = [k for k in SLOT if baru[k] != lama[k]]
            if not berubah:
                continue
            for k in berubah:
                if k not in SLOT_BAHAN:
                    n += _ganti_baris(conn, "elemen_id = ?", (elemen_id,), k, baru[k], id_kode)
            if any(k in SLOT_BAHAN for k in berubah):
                n += _ganti_bekisting(conn, "elemen_id = ?", (elemen_id,), baru[SLOT_KAYU], baru[SLOT_TRIPLEK],
                                      id_kode)
            conn.execute("UPDATE elemen_proyek SET material = ? WHERE id = ?",
                         (json.dumps(khusus, ensure_ascii=False) if khusus else None, elemen_id))
            berubah_semua += [k for k in berubah if k not in berubah_semua]
            n_elemen += 1
            nama.append(el["nama"] or str(elemen_id))
            ringkas = "; ".join(f"{SLOT[k].judul}: {SLOT[k].cari(baru[k]).label}" for k in berubah)
        if proyek_id is not None and n_elemen:
            conn.execute("UPDATE proyek SET tanggal_diubah = CURRENT_TIMESTAMP WHERE id = ?", (proyek_id,))
        conn.commit()
    finally:
        conn.close()
    if n_elemen:
        siapa = nama[0] if n_elemen == 1 else f"{n_elemen} elemen ({nama[0]}, ...)"
        catat("material", f"Material elemen {siapa} diubah: {ringkas}", proyek_id)
    return {"berubah": berubah_semua, "baris": n, "elemen": n_elemen}


def ringkasan_opsi(conn=None) -> dict:
    """{kode varian: {"harga": harga satuan, "bahan": [(nama, satuan, koefisien)]}} untuk semua pilihan,
    dari harga dan komponen yang berlaku di database (dipakai combo box dialog Pilihan Material)."""
    tutup = conn is None
    conn = conn or _connect()
    try:
        hasil = {}
        for slot in SLOT.values():
            if slot.kode in SLOT_BAHAN:  # harga dasar kayu / triplek (sudah termasuk BUK, seperti harga pekerjaan)
                for o, b in zip(slot.opsi, KAYU if slot.kode == SLOT_KAYU else TRIPLEK, strict=True):
                    sd = conn.execute("SELECT harga, satuan FROM sumber_daya WHERE tipe = 'bahan' AND lower(nama) = "
                                      "lower(?) AND lower(satuan) = lower(?)", (b.nama, b.satuan)).fetchone()
                    harga = sd["harga"] if sd else b.harga
                    hasil[kode_varian(slot.kode, o.kunci)] = {"harga": harga * (1 + BUK_RATE), "satuan": b.satuan,
                                                               "bahan": [(b.nama, b.satuan, 1.0)], "dasar": harga}
                continue
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
