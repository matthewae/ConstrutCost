"""
Pipeline KF-1 s.d. KF-4:  file IFC -> validasi -> elemen_proyek -> rule engine -> hasil_estimasi.
KF-19: dimensi satu elemen diubah pengguna -> rule engine dijalankan ulang untuk elemen itu saja.
Penulangan: tipe elemen (K1, B1, P1, ...) ditetapkan sebelum rule engine; mengubah konfigurasi
tipe menghitung ulang pembesian seluruh proyek (hitung_ulang_penulangan).
"""

import json
from pathlib import Path

from aktivitas import catat
import elemen_lain
from database.estimasi_repository import BUK_RATE, _connect
from database.init_db import pastikan_skema
from database.material_repository import kode_elemen, kode_proyek
from database.parameter_repository import muat_parameter
from database.penulangan_repository import pasang_tipe, rapikan_tipe
from database.seed_data import seed_pekerjaan
from ifc_reader import buka_dan_validasi, ekstrak_elemen
from klasifikasi import ElementType
from rules import proses_semua, siapkan_konteks, terapkan_rules
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
    "eksternal",
    "sumber_volume",
    "sumber_dimensi",
    "tipe_id",
    "material",
    "besi_model",
    "kolom_grup",
    "info_kolom",
    "info_balok",
    "info_fondasi",
    "di_luar_bangunan",
    "info_lain",
)
_KOLOM_JSON = ("sumber_dimensi", "besi_model", "info_kolom", "info_balok", "info_fondasi", "info_lain")
RULES_PEMBESIAN = [r for r in RULES if r.kode.startswith("BSI.")]


def _harga_dan_kode(conn, proyek_id: int):
    """harga satuan per pekerjaan_id (jumlah komponen x (1 + BUK), sama dengan
    get_harga_satuan_pekerjaan()) dan peta kode keluaran rule -> pekerjaan_id, dengan pilihan material
    proyek (mis. DND.BATA -> pekerjaan 'DND.BATA~merah' bila proyek memilih bata merah)."""
    harga = {
        r["pekerjaan_id"]: r["h"] * (1 + BUK_RATE)
        for r in conn.execute(
            "SELECT pekerjaan_id, SUM(koefisien*harga_satuan) AS h FROM komponen_harga GROUP BY pekerjaan_id"
        )
    }
    kode_ke_id = {r["kode_ahsp"]: r["id"] for r in conn.execute("SELECT id, kode_ahsp FROM pekerjaan")}
    return harga, (kode_proyek(conn, proyek_id, kode_ke_id), kode_ke_id)


def _simpan_hasil(conn, proyek_id, elemen_id, hasil, harga, kode, peringatan, material=None) -> int:
    """`kode` = (peta kode proyek, peta kode_ahsp -> id) dari _harga_dan_kode; `material` = pilihan
    material khusus elemen (JSON elemen_proyek.material) yang menimpa pilihan proyek."""
    peta = kode_elemen(*kode, material, conn)
    n = 0
    for h in hasil:
        pid = peta.get(h.kode)
        if pid is None and h.kode.startswith("LAIN|"):
            pid = _pekerjaan_lain(conn, h.kode, kode[1])
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


def _pekerjaan_lain(conn, kode: str, kode_ke_id: dict) -> int:
    """Pekerjaan untuk elemen model tanpa padanan analisa HSPK (elemen_lain.py): dibuat sekali, tanpa komponen
    (harga 0) sehingga muncul di peringatan "belum punya harga satuan" dan harganya diisi pengguna."""
    from elemen_lain import pekerjaan_lain

    if kode not in kode_ke_id:
        nama, kategori, satuan = pekerjaan_lain(kode)
        kode_ke_id[kode] = conn.execute(
            "INSERT INTO pekerjaan (kode_ahsp, nama_pekerjaan, kategori, satuan, catatan) VALUES (?,?,?,?,?)",
            (kode, nama, kategori, satuan, "Elemen dari model IFC tanpa padanan analisa HSPK: isi harga satuannya "
                                           "(Harga Satuan) atau harga khusus baris di tabel RAB."),
        ).lastrowid
    return kode_ke_id[kode]


def jalankan_estimasi(proyek_id: int, model=None, progress=None, parameter=None) -> dict:
    """Parse IFC proyek lalu isi elemen_proyek + hasil_estimasi.

    `model`    : ifcopenshell.file yang sudah dibuka saat validasi (KF-1), supaya file tidak dibaca dua kali.
                 Bila None, file dibuka dan divalidasi ulang dari path proyek.
    `progress` : callable(i, n, teks) untuk indikator proses.

    `parameter`: asumsi rule engine; None = parameter tersimpan di proyek (KF-7).

    PERHATIAN: menimpa hasil sebelumnya, termasuk edit volume (KF-6) dan dimensi (KF-19) manual.
    """
    conn = _connect()
    try:
        pastikan_skema(conn)
    finally:
        conn.close()
    seed_pekerjaan()  # idempotent: memastikan master pekerjaan/harga ada
    parameter = parameter or muat_parameter(proyek_id)

    conn = _connect()
    try:
        row = conn.execute(
            "SELECT path_file_ifc FROM proyek WHERE id = ?", (proyek_id,)
        ).fetchone()
        if not row or not row["path_file_ifc"]:
            raise ValueError("Proyek ini tidak punya path file IFC.")
        if model is None:
            model = buka_dan_validasi(row["path_file_ifc"], terisolasi=True).model

        # koreksi jenis elemen lain oleh pengguna tetap berlaku setelah IFC dibaca ulang (dicocokkan lewat GlobalId)
        jenis_manual = {}
        for r in conn.execute("SELECT global_id, info_lain FROM elemen_proyek WHERE proyek_id = ? AND kelas = ? "
                              "AND info_lain LIKE '%\"manual\"%'", (proyek_id, ElementType.LAINNYA.value)):
            try:
                pilihan = (json.loads(r["info_lain"]) or {}).get("manual")
            except ValueError:
                pilihan = None
            if pilihan:
                jenis_manual[r["global_id"]] = pilihan
        elemen, peringatan = (ekstrak_elemen(model, progress, jenis_manual=jenis_manual) if jenis_manual
                              else ekstrak_elemen(model, progress))
        harga, kode_ke_id = _harga_dan_kode(conn, proyek_id)
        # pilihan material khusus elemen tetap berlaku setelah IFC dibaca ulang (dicocokkan lewat GlobalId)
        material_lama = {
            r["global_id"]: r["material"] for r in conn.execute(
                "SELECT global_id, material FROM elemen_proyek WHERE proyek_id = ? AND material IS NOT NULL",
                (proyek_id,),
            )
        }
        for el in elemen:
            el["material"] = material_lama.get(el["global_id"])

        # item tambahan dari katalog (tanpa elemen) tidak dihasilkan rule engine, jadi dipertahankan
        conn.execute("DELETE FROM hasil_estimasi WHERE proyek_id = ? AND COALESCE(item_tambahan, 0) = 0", (proyek_id,))
        conn.execute("DELETE FROM elemen_proyek WHERE proyek_id = ?", (proyek_id,))
        siapkan_konteks(elemen, parameter)  # fakta per elemen dipakai pengelompokan tipe (pelat dasar, sloof)
        pasang_tipe(conn, proyek_id, elemen, parameter.batas_kemiringan_dak)
        konteks, keluaran, dilewati = proses_semua(elemen, parameter)
        peringatan.extend(dilewati)

        kolom = ", ".join(_KOLOM_ELEMEN)
        tanda = ", ".join("?" * (len(_KOLOM_ELEMEN) + 1))
        n_hasil = 0
        for el, hasil in keluaran:
            nilai = [
                json.dumps(el[k], ensure_ascii=False) if k in _KOLOM_JSON and el.get(k) is not None else el.get(k)
                for k in _KOLOM_ELEMEN
            ]
            cur = conn.execute(
                f"INSERT INTO elemen_proyek (proyek_id, {kolom}) VALUES ({tanda})",
                (proyek_id, *nilai),
            )
            n_hasil += _simpan_hasil(conn, proyek_id, cur.lastrowid, hasil, harga, kode_ke_id, peringatan,
                                    el.get("material"))

        rapikan_tipe(conn, proyek_id)
        conn.execute(
            "UPDATE proyek SET tanggal_diubah = CURRENT_TIMESTAMP WHERE id = ?",
            (proyek_id,),
        )
        conn.commit()
        catat("estimasi", f"Estimasi dari IFC {Path(row['path_file_ifc']).name}: {len(elemen)} elemen, {n_hasil} item pekerjaan", proyek_id)
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
    for k in ("besi_model", "info_kolom", "info_balok", "info_fondasi", "info_lain"):
        try:
            el[k] = json.loads(el[k]) if el.get(k) else None
        except ValueError:
            el[k] = None
    return el


def ambil_elemen(elemen_id: int) -> dict | None:
    """Satu baris elemen_proyek (sumber_dimensi sudah berupa dict)."""
    conn = _connect()
    try:
        row = conn.execute("SELECT * FROM elemen_proyek WHERE id = ?", (elemen_id,)).fetchone()
        return _baris_ke_elemen(row) if row else None
    finally:
        conn.close()


def hitung_ulang_elemen(elemen_id: int, dimensi: dict, parameter=None) -> dict:
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
        parameter = parameter or muat_parameter(el["proyek_id"])
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
        if berubah:
            el["besi_model"] = None  # tulangan model tidak lagi cocok dengan dimensi baru: pakai tipe penulangan

        # konteks bangunan (lantai dasar, sumber lantai/plafon) dari seluruh elemen proyek
        semua = [
            el if r["id"] == elemen_id else _baris_ke_elemen(r)
            for r in conn.execute("SELECT * FROM elemen_proyek WHERE proyek_id = ?", (el["proyek_id"],))
        ]
        konteks = siapkan_konteks(semua, parameter)
        pasang_tipe(conn, el["proyek_id"], [el], parameter.batas_kemiringan_dak)  # penampang bisa berubah
        hasil, dilewati = terapkan_rules(el, konteks, parameter)

        harga, kode_ke_id = _harga_dan_kode(conn, el["proyek_id"])
        kolom = [k for k in ("panjang", "lebar", "tinggi", "tebal", "luas", "volume", "keliling",
                             "kemiringan", "luas_bukaan") if k in gabung]
        conn.execute(
            f"UPDATE elemen_proyek SET {', '.join(f'{k} = ?' for k in kolom)}, sumber_volume = ?, "
            "sumber_dimensi = ?, dimensi_manual = 1, tipe_id = ?, besi_model = ? WHERE id = ?",
            (*[el[k] for k in kolom], el.get("sumber_volume"),
             json.dumps(el["sumber_dimensi"], ensure_ascii=False), el["tipe_id"],
             json.dumps(el["besi_model"]) if el.get("besi_model") else None, elemen_id),
        )
        khusus = _simpan_khusus(conn, "elemen_id = ?", (elemen_id,))  # KF-6: harga khusus & catatan tetap
        conn.execute("DELETE FROM hasil_estimasi WHERE elemen_id = ?", (elemen_id,))
        n = _simpan_hasil(conn, el["proyek_id"], elemen_id, hasil, harga, kode_ke_id, dilewati, el.get("material"))
        _pulihkan_khusus(conn, khusus)
        rapikan_tipe(conn, el["proyek_id"])
        conn.execute(
            "UPDATE proyek SET tanggal_diubah = CURRENT_TIMESTAMP WHERE id = ?", (el["proyek_id"],)
        )
        conn.commit()
        catat("dimensi", f"Ubah dimensi {el.get('nama') or elemen_id}: {', '.join(berubah)}; QTO elemen dihitung ulang", el["proyek_id"])
        return {"baris": n, "dilewati": dilewati, "berubah": berubah}
    finally:
        conn.close()


def ubah_jenis_elemen(proyek_id: int, perubahan: dict, parameter=None) -> dict:
    """Koreksi jenis elemen lain (kelas LAINNYA) oleh pengguna, mis. panel yang terbaca kisi menjadi cladding,
    atau perabot yang dikecualikan dari RAB. `perubahan` = {elemen_id: kunci elemen_lain.pilihan_jenis(), atau
    None untuk kembali ke jenis otomatis}.

    Tanpa membaca file IFC: info elemen disusun ulang dari teks, nama tipe, dan angka Pset yang tersimpan. Yang
    dihitung ulang hanya elemen yang berubah dan dinding yang tertutup elemen itu (cat di balik cladding). Harga
    khusus dan catatan dipertahankan; volume yang diedit manual pada dinding terdampak juga dipertahankan,
    sedangkan baris elemen yang jenisnya berubah dihitung baru. Pilihan disimpan di info_lain (`manual`) dan
    dipakai lagi saat IFC dibaca ulang. Return {"berubah": [elemen_id], "dinding": n, "baris": n}."""
    parameter = parameter or muat_parameter(proyek_id)
    conn = _connect()
    try:
        semua = [_baris_ke_elemen(r) for r in conn.execute(
            "SELECT * FROM elemen_proyek WHERE proyek_id = ? ORDER BY id", (proyek_id,)
        )]
        per_id = {e["id"]: e for e in semua}
        berubah = []
        for eid, pilihan in perubahan.items():
            el = per_id.get(int(eid))
            if el is None or el["kelas"] != ElementType.LAINNYA.value:
                continue
            lama_info = el.get("info_lain") or {}
            baru = elemen_lain.ganti_jenis(lama_info, pilihan, el.get("nama"))
            if (elemen_lain.kunci_pilihan(baru) == elemen_lain.kunci_pilihan(lama_info)
                    and baru.get("manual") == lama_info.get("manual")):
                continue
            el["info_lain"] = baru
            berubah.append(el)
        if not berubah:
            return {"berubah": [], "dinding": 0, "baris": 0}

        gid_berubah = {e["global_id"] for e in berubah}
        aktif = {e["global_id"] for e in semua
                 if e["kelas"] == ElementType.LAINNYA.value and elemen_lain.jenis_tertutup(e.get("info_lain"))}
        dinding = []
        for w in semua:
            tutup = (w.get("info_lain") or {}).get("tutup") or {}
            if w["kelas"] == ElementType.WALL.value and gid_berubah & set(tutup):
                w["info_lain"] = elemen_lain.hitung_tertutup(w["info_lain"], aktif)
                dinding.append(w)

        konteks = siapkan_konteks(semua, parameter)
        harga, kode_ke_id = _harga_dan_kode(conn, proyek_id)
        hitung = berubah + dinding
        ids = tuple(e["id"] for e in hitung)
        tanda = ", ".join("?" * len(ids))
        khusus = _simpan_khusus(conn, f"elemen_id IN ({tanda})", ids)
        manual = _simpan_volume_manual(conn, [w["id"] for w in dinding])
        conn.execute(f"DELETE FROM hasil_estimasi WHERE elemen_id IN ({tanda})", ids)
        n, catatan = 0, []
        for el in hitung:
            conn.execute("UPDATE elemen_proyek SET info_lain = ? WHERE id = ?",
                         (json.dumps(el["info_lain"], ensure_ascii=False), el["id"]))
            hasil, _dilewati = terapkan_rules(el, konteks, parameter)
            n += _simpan_hasil(conn, proyek_id, el["id"], hasil, harga, kode_ke_id, catatan, el.get("material"))
        _pulihkan_khusus(conn, khusus)
        _pulihkan_volume_manual(conn, manual)
        conn.execute("UPDATE proyek SET tanggal_diubah = CURRENT_TIMESTAMP WHERE id = ?", (proyek_id,))
        conn.commit()
        teks = "; ".join(f"{e.get('nama') or e['id']} → {elemen_lain.label_pilihan(elemen_lain.kunci_pilihan(e['info_lain']))}"
                         for e in berubah[:5])
        catat("jenis", f"Ubah jenis {len(berubah)} elemen: {teks}" + (" …" if len(berubah) > 5 else "")
              + (f"; cat {len(dinding)} dinding di baliknya dihitung ulang" if dinding else ""), proyek_id)
        return {"berubah": [e["id"] for e in berubah], "dinding": len(dinding), "baris": n}
    finally:
        conn.close()


def daftar_elemen_lain(proyek_id: int) -> list:
    """Elemen kelas LAINNYA proyek untuk dialog koreksi jenis: id, nama, kelas IFC, lantai, jenis dipakai,
    jenis otomatis, dimensi utama, dan subtotal biaya."""
    conn = _connect()
    try:
        rows = conn.execute(
            """SELECT ep.id, ep.global_id, ep.nama, ep.ifc_type, ep.lantai, ep.luas, ep.panjang, ep.volume,
                      ep.info_lain, COALESCE(SUM(he.subtotal_biaya), 0) AS biaya, COUNT(he.id) AS baris
               FROM elemen_proyek ep LEFT JOIN hasil_estimasi he ON he.elemen_id = ep.id
               WHERE ep.proyek_id = ? AND ep.kelas = ? GROUP BY ep.id ORDER BY ep.lantai, ep.nama""",
            (proyek_id, ElementType.LAINNYA.value)).fetchall()
    finally:
        conn.close()
    hasil = []
    for r in rows:
        d = dict(r)
        try:
            i = json.loads(d.pop("info_lain") or "{}") or {}
        except ValueError:
            i = {}
        d["jenis"] = elemen_lain.kunci_pilihan(i)
        d["jenis_otomatis"] = i.get("jenis_otomatis") or d["jenis"]
        d["manual"] = bool(i.get("manual"))
        hasil.append(d)
    return hasil


def _simpan_volume_manual(conn, elemen_ids: list) -> dict:
    """Volume baris yang diedit manual (KF-6) untuk elemen yang akan dihitung ulang, kunci (elemen, pekerjaan,
    uraian)."""
    if not elemen_ids:
        return {}
    tanda = ", ".join("?" * len(elemen_ids))
    return {
        (r["elemen_id"], r["pekerjaan_id"], r["uraian"]): r["volume_pekerjaan"]
        for r in conn.execute(
            f"SELECT elemen_id, pekerjaan_id, uraian, volume_pekerjaan FROM hasil_estimasi "
            f"WHERE elemen_id IN ({tanda}) AND diedit_manual = 1", tuple(elemen_ids))
    }


def _pulihkan_volume_manual(conn, simpan: dict) -> None:
    """Pasang kembali volume manual ke baris baru yang sama; subtotal mengikuti harga satuan baris itu."""
    for (eid, pid, uraian), volume in simpan.items():
        conn.execute(
            """UPDATE hasil_estimasi SET
                   subtotal_biaya = CASE WHEN volume_pekerjaan > 0 THEN subtotal_biaya / volume_pekerjaan * ?
                                         ELSE subtotal_biaya END,
                   volume_pekerjaan = ?, diedit_manual = 1
               WHERE elemen_id = ? AND pekerjaan_id = ? AND uraian IS ?""",
            (volume, volume, eid, pid, uraian),
        )


def _simpan_khusus(conn, syarat: str, args: tuple) -> dict:
    """KF-6: harga satuan khusus & catatan baris hasil yang akan dihitung ulang, agar bisa dipulihkan.
    Kunci (elemen_id, pekerjaan_id, uraian)."""
    return {
        (r["elemen_id"], r["pekerjaan_id"], r["uraian"]): (r["harga_manual"], r["catatan"])
        for r in conn.execute(
            "SELECT elemen_id, pekerjaan_id, uraian, harga_manual, catatan FROM hasil_estimasi "
            f"WHERE ({syarat}) AND (harga_manual IS NOT NULL OR catatan IS NOT NULL)",
            args,
        )
    }


def _pulihkan_khusus(conn, simpan: dict) -> None:
    """Pasang kembali harga khusus & catatan ke baris baru dengan elemen, pekerjaan, dan uraian sama.
    Bila uraian berubah (mis. tulangan 6 D13 -> 4 D16 setelah tipe penulangan diubah), dipasang ke baris
    elemen & pekerjaan yang sama, karena harga khusus berlaku per satuan pekerjaan."""
    for (eid, pid, uraian), (hm, catatan) in simpan.items():
        cur = conn.execute(
            """UPDATE hasil_estimasi SET harga_manual = ?, catatan = ?,
                   subtotal_biaya = CASE WHEN ? IS NULL THEN subtotal_biaya ELSE volume_pekerjaan * ? END
               WHERE elemen_id = ? AND pekerjaan_id = ? AND uraian IS ?""",
            (hm, catatan, hm, hm, eid, pid, uraian),
        )
        if cur.rowcount == 0:
            conn.execute(
                """UPDATE hasil_estimasi SET harga_manual = COALESCE(harga_manual, ?),
                       catatan = COALESCE(catatan, ?),
                       subtotal_biaya = CASE WHEN ? IS NULL THEN subtotal_biaya ELSE volume_pekerjaan * ? END
                   WHERE elemen_id = ? AND pekerjaan_id = ? AND harga_manual IS NULL""",
                (hm, catatan, hm, hm, eid, pid),
            )


def hitung_ulang_penulangan(proyek_id: int, parameter=None) -> dict:
    """Hitung ulang seluruh pembesian proyek dari elemen tersimpan setelah tipe penulangan diubah.
    Pekerjaan lain (beton, bekisting, dinding, ...) dan edit volumenya tidak tersentuh; baris
    pembesian yang volumenya diedit manual diganti hasil perhitungan baru.
    Return {"baris": jumlah baris pembesian, "berat": total kg}."""
    parameter = parameter or muat_parameter(proyek_id)
    conn = _connect()
    try:
        semua = [_baris_ke_elemen(r) for r in conn.execute(
            "SELECT * FROM elemen_proyek WHERE proyek_id = ?", (proyek_id,)
        )]
        konteks = siapkan_konteks(semua, parameter)
        pasang_tipe(conn, proyek_id, semua, parameter.batas_kemiringan_dak)
        harga, kode_ke_id = _harga_dan_kode(conn, proyek_id)
        syarat_bsi = "proyek_id = ? AND pekerjaan_id IN (SELECT id FROM pekerjaan WHERE kode_ahsp LIKE 'BSI.%')"
        khusus = _simpan_khusus(conn, syarat_bsi, (proyek_id,))  # KF-6: harga khusus & catatan tetap
        conn.execute(f"DELETE FROM hasil_estimasi WHERE {syarat_bsi}", (proyek_id,))
        n, berat, catatan = 0, 0.0, []
        for el in semua:
            conn.execute("UPDATE elemen_proyek SET tipe_id = ? WHERE id = ?", (el["tipe_id"], el["id"]))
            hasil, _ = terapkan_rules(el, konteks, parameter, RULES_PEMBESIAN)
            n += _simpan_hasil(conn, proyek_id, el["id"], hasil, harga, kode_ke_id, catatan, el.get("material"))
            berat += sum(h.volume for h in hasil)
        _pulihkan_khusus(conn, khusus)
        rapikan_tipe(conn, proyek_id)
        conn.execute("UPDATE proyek SET tanggal_diubah = CURRENT_TIMESTAMP WHERE id = ?", (proyek_id,))
        conn.commit()
        catat("penulangan", f"Pembesian dihitung ulang: {n} baris, total {round(berat)} kg", proyek_id)
        return {"baris": n, "berat": berat}
    finally:
        conn.close()


def hitung_ulang_dari_elemen(proyek_id: int, parameter=None) -> dict:
    """KF-7: jalankan ulang seluruh rule engine dari elemen tersimpan (tanpa membaca file IFC),
    mis. setelah parameter aturan proyek diubah. Dimensi yang diubah pengguna (KF-19) tetap dipakai.
    Harga satuan khusus dan catatan (KF-6) dipertahankan untuk item yang sama; volume yang diedit
    manual diganti hasil perhitungan baru. Return {"baris", "peringatan", "manual_diganti"}."""
    parameter = parameter or muat_parameter(proyek_id)
    conn = _connect()
    try:
        semua = [_baris_ke_elemen(r) for r in conn.execute(
            "SELECT * FROM elemen_proyek WHERE proyek_id = ? ORDER BY id", (proyek_id,)
        )]
        simpan = _simpan_khusus(conn, "proyek_id = ?", (proyek_id,))
        manual = conn.execute(
            "SELECT COUNT(*) FROM hasil_estimasi WHERE proyek_id = ? AND diedit_manual = 1", (proyek_id,)
        ).fetchone()[0]
        siapkan_konteks(semua, parameter)
        pasang_tipe(conn, proyek_id, semua, parameter.batas_kemiringan_dak)
        konteks, keluaran, peringatan = proses_semua(semua, parameter)
        harga, kode_ke_id = _harga_dan_kode(conn, proyek_id)
        # item tambahan dari katalog (tanpa elemen) tidak dihasilkan rule engine, jadi dipertahankan
        conn.execute("DELETE FROM hasil_estimasi WHERE proyek_id = ? AND COALESCE(item_tambahan, 0) = 0", (proyek_id,))
        n = 0
        for el, hasil in keluaran:
            conn.execute("UPDATE elemen_proyek SET tipe_id = ? WHERE id = ?", (el["tipe_id"], el["id"]))
            n += _simpan_hasil(conn, proyek_id, el["id"], hasil, harga, kode_ke_id, peringatan, el.get("material"))
        _pulihkan_khusus(conn, simpan)
        rapikan_tipe(conn, proyek_id)
        conn.execute("UPDATE proyek SET tanggal_diubah = CURRENT_TIMESTAMP WHERE id = ?", (proyek_id,))
        conn.commit()
        catat("estimasi", f"Hitung ulang dari elemen tersimpan: {n} item pekerjaan, {manual} volume manual diganti", proyek_id)
        return {"baris": n, "peringatan": peringatan, "manual_diganti": manual}
    finally:
        conn.close()
