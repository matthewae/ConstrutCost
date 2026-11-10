"""
Kebutuhan biaya satu elemen yang dipilih di penampil 3D, beserta elemen yang ikut dibangun bersamanya.

Kolom   : kolom terpilih + segmen kolom yang sama (pedestal / potongan) + fondasi di bawah kolom fisik itu
          (footplate / sumuran / poer, relasi `info_fondasi`) + pekerjaan tanah yang dimodelkan tepat di bawah
          fondasi (lantai kerja, urugan pasir). Fondasi turunan (pilihan jenis fondasi / sumuran turunan) sudah
          menjadi baris kolom itu sendiri.
Fondasi : fondasi terpilih + fondasi lain di titik kolom yang sama (sumuran + poer) + pekerjaan tanah di bawahnya.
Dinding : dinding terpilih (pasangan, plester, acian, cat, fondasi/sloof turunan) + sloof dan fondasi menerus
          (batu kali) tepat di bawahnya + pekerjaan tanah di bawah fondasi itu.
Lainnya : elemen itu saja.

Relasi "tepat di bawah" memakai kotak pembatas koordinat dunia dari model 3D (model3d.py). Semua biaya diambil
dari hasil estimasi yang tersimpan (termasuk edit volume, harga khusus, dan pilihan material), sehingga angka di
penampil 3D sama dengan tabel RAB.
"""

import json

from database.estimasi_repository import _connect
from klasifikasi import LABEL, ElementType
from kolom import LABEL_FUNGSI
from rab_rinci import urutan_kategori
from rules.sifat import balok_sloof

_TOL_BAWAH_DINDING = 0.60  # m, sloof / batu kali boleh sedikit di bawah kaki dinding
URUT_PERAN = ("Pedestal (bagian kolom ini)", "Segmen kolom yang sama", "Sloof di bawah dinding",
              "Fondasi di bawah kolom", "Fondasi lain di titik kolom yang sama", "Fondasi menerus di bawah dinding",
              "Pekerjaan tanah di bawah fondasi")


def _json(teks):
    try:
        return json.loads(teks) if teks else None
    except ValueError:
        return None


def peta_biaya(proyek_id: int) -> dict:
    """{global_id: {'id', 'nama', 'kelas', 'lantai', 'total', 'baris', 'kolom_grup', 'info_kolom', 'info_fondasi',
    'predefined_type'}} untuk semua elemen proyek (dipakai pewarnaan & teks sorot penampil 3D)."""
    conn = _connect()
    try:
        rows = conn.execute(
            """SELECT ep.id, ep.global_id, ep.nama, ep.kelas, ep.lantai, ep.predefined_type, ep.kolom_grup,
                      ep.info_kolom, ep.info_fondasi, COALESCE(SUM(he.subtotal_biaya), 0) AS total,
                      COUNT(he.id) AS baris
               FROM elemen_proyek ep LEFT JOIN hasil_estimasi he ON he.elemen_id = ep.id
               WHERE ep.proyek_id = ? GROUP BY ep.id""", (proyek_id,)).fetchall()
    finally:
        conn.close()
    hasil = {}
    for r in rows:
        d = dict(r)
        d["info_kolom"] = _json(d["info_kolom"])
        d["info_fondasi"] = _json(d["info_fondasi"])
        hasil[r["global_id"]] = d
    return hasil


def _bawah(atas, bawah, toleransi: float) -> bool:
    from model3d import di_bawah

    return di_bawah(atas, bawah, toleransi)


def _di_bawah_dinding(dinding, x) -> bool:
    """Sloof / fondasi menerus di bawah dinding: denah menutup >= 50% denah yang lebih kecil, puncaknya di antara
    kaki dinding dan 60 cm di bawahnya."""
    dx = min(dinding[3], x[3]) - max(dinding[0], x[0])
    dy = min(dinding[4], x[4]) - max(dinding[1], x[1])
    if dx <= 0 or dy <= 0:
        return False
    kecil = min((dinding[3] - dinding[0]) * (dinding[4] - dinding[1]), (x[3] - x[0]) * (x[4] - x[1]))
    return kecil > 0 and dx * dy >= 0.5 * kecil and dinding[2] - _TOL_BAWAH_DINDING <= x[5] <= dinding[2] + 0.05


def elemen_terkait(gid: str, peta: dict, kotak: dict | None = None) -> list:
    """[(gid, peran)] elemen yang ikut dibangun bersama elemen terpilih (tanpa elemen itu sendiri)."""
    e = peta.get(gid)
    if e is None:
        return []
    kotak = kotak or {}
    hasil, sudah = [], {gid}

    def tambah(g, peran):
        if g not in sudah and g in peta:
            sudah.add(g)
            hasil.append((g, peran))

    def tanah_di_bawah(fondasi_gids):
        for f in fondasi_gids:
            kf = kotak.get(f)
            if not kf:
                continue
            for g, x in peta.items():
                if x["kelas"] == ElementType.EARTHWORK.value and g in kotak and _bawah(kf, kotak[g], 0.15):
                    tambah(g, "Pekerjaan tanah di bawah fondasi")

    kelas = e["kelas"]
    if kelas == ElementType.COLUMN.value:
        grup = e.get("kolom_grup") or gid
        for g, x in peta.items():
            if x.get("kolom_grup") == grup and g != gid:
                peran = (x.get("info_kolom") or {}).get("peran")
                tambah(g, "Pedestal (bagian kolom ini)" if peran == "pedestal" else "Segmen kolom yang sama")
        fondasi = [g for g, x in peta.items() if (x.get("info_fondasi") or {}).get("kolom") == grup]
        for g in fondasi:
            tambah(g, "Fondasi di bawah kolom")
        tanah_di_bawah(fondasi)
    elif kelas in (ElementType.FOOTING.value, ElementType.PILE.value):
        grup = (e.get("info_fondasi") or {}).get("kolom")
        fondasi = [gid]
        if grup:
            for g, x in peta.items():
                if (x.get("info_fondasi") or {}).get("kolom") == grup:
                    tambah(g, "Fondasi lain di titik kolom yang sama")
                    fondasi.append(g)
        tanah_di_bawah(fondasi)
    elif kelas == ElementType.WALL.value and gid in kotak:
        kd = kotak[gid]
        fondasi = []
        for g, x in peta.items():
            if g in kotak and g != gid and _di_bawah_dinding(kd, kotak[g]):
                if x["kelas"] == ElementType.BEAM.value and balok_sloof({"kelas": "BEAM", "nama": x.get("nama")}):
                    tambah(g, "Sloof di bawah dinding")
                elif x["kelas"] == ElementType.FOOTING.value and (x.get("predefined_type") or "") in (
                        "STRIP_FOOTING", "FOOTING_BEAM"):
                    tambah(g, "Fondasi menerus di bawah dinding" if x["predefined_type"] == "STRIP_FOOTING"
                           else "Sloof di bawah dinding")
                    fondasi.append(g)
        # fondasi menerus di bawah sloof (sloof di antara dinding dan batu kali)
        for g, peran in list(hasil):
            if peran == "Sloof di bawah dinding" and g in kotak:
                for g2, x in peta.items():
                    if x["kelas"] == ElementType.FOOTING.value and (x.get("predefined_type") or "") == "STRIP_FOOTING" \
                            and g2 in kotak and _di_bawah_dinding(kotak[g], kotak[g2]):
                        tambah(g2, "Fondasi menerus di bawah dinding")
                        fondasi.append(g2)
        tanah_di_bawah(fondasi)
    return hasil


def _dimensi(r) -> str:
    def cm(x):
        return f"{x * 100:.0f}".replace(".", ",")

    def m(x, d=2):
        return f"{x:,.{d}f}".replace(",", "X").replace(".", ",").replace("X", ".")

    k = r["kelas"]
    b, h, t, L, A, V = r["lebar"], r["tinggi"], r["tebal"], r["panjang"], r["luas"], r["volume"]
    bagian = []
    if k == "COLUMN" and r["lebar"] and r["tebal"]:
        bagian.append(f"{cm(b)}/{cm(t)} cm" + (f", tinggi {m(h)} m" if h else ""))
    elif k == "BEAM" and b and h:
        bagian.append(f"{cm(b)}/{cm(h)} cm" + (f", panjang {m(L)} m" if L else ""))
    elif k == "WALL":
        if L:
            bagian.append(f"panjang {m(L)} m")
        if h:
            bagian.append(f"tinggi {m(h)} m")
        if t:
            bagian.append(f"tebal {cm(t)} cm")
    elif k in ("SLAB", "ROOF", "FLOOR", "CEILING", "SPACE", "WALL_TILE") and A:
        bagian.append(f"luas {m(A)} m²" + (f", tebal {cm(t)} cm" if t and k in ("SLAB", "ROOF") else ""))
    elif k == "FOOTING" and L and b and (r["predefined_type"] or "") == "CAISSON_FOUNDATION":
        bagian.append(f"Ø {m(L)} m" + (f", kedalaman {m(t)} m" if t else ""))
    elif k == "FOOTING" and L and b:
        bagian.append(f"{m(L)} × {m(b)} m" + (f", tebal {m(t)} m" if t else ""))
    if V and k in ("COLUMN", "BEAM", "SLAB", "FOOTING", "PILE", "STAIR", "EARTHWORK"):
        bagian.append(f"volume {m(V, 3)} m³")
    return " · ".join(bagian)


def _bagian(conn, elemen_id: int, peran: str) -> dict:
    r = conn.execute("SELECT * FROM elemen_proyek WHERE id = ?", (elemen_id,)).fetchone()
    baris = [dict(x) for x in conn.execute(
        """SELECT he.id AS hasil_id, he.volume_pekerjaan AS volume, he.subtotal_biaya AS jumlah, he.rumus, he.uraian,
                  he.diameter, he.diedit_manual, he.harga_manual, p.kode_ahsp AS kode, p.nama_pekerjaan AS nama,
                  p.kategori, p.satuan
           FROM hasil_estimasi he JOIN pekerjaan p ON p.id = he.pekerjaan_id WHERE he.elemen_id = ?""",
        (elemen_id,))]
    for b in baris:
        b["harga"] = b["jumlah"] / b["volume"] if b["volume"] else 0.0
    baris.sort(key=lambda b: (urutan_kategori(b["kategori"]), b["kode"], -(b["diameter"] or 0)))
    info_kolom = _json(r["info_kolom"]) or {}
    kelas = r["kelas"]
    label = LABEL.get(ElementType(kelas), kelas) if kelas in ElementType._value2member_map_ else kelas
    if kelas == "COLUMN" and info_kolom.get("fungsi"):
        label = LABEL_FUNGSI.get(info_kolom["fungsi"], label)
    return {
        "elemen_id": elemen_id, "gid": r["global_id"], "judul": r["nama"] or r["ifc_type"], "peran": peran,
        "kelas": kelas, "label_kelas": label, "lantai": r["lantai"], "ifc_type": r["ifc_type"],
        "dimensi": _dimensi(r), "baris": baris, "total": sum(b["jumlah"] for b in baris),
    }


def rincian(proyek_id: int, gid: str, kotak: dict | None = None, termasuk_terkait: bool = True,
            peta: dict | None = None) -> dict | None:
    """Rincian kebutuhan biaya elemen `gid` (+ elemen terkait). None bila elemen tidak dihitung aplikasi.
    {'utama': bagian, 'bagian': [bagian...], 'total', 'total_utama', 'terkait': [gid], 'slot': {...}}."""
    from database.material_repository import material_elemen

    peta = peta or peta_biaya(proyek_id)
    e = peta.get(gid)
    if e is None:
        return None
    terkait = sorted(elemen_terkait(gid, peta, kotak), key=lambda x: URUT_PERAN.index(x[1]) if x[1] in URUT_PERAN else 9)
    conn = _connect()
    try:
        utama = _bagian(conn, e["id"], "Elemen terpilih")
        bagian = [utama] + ([_bagian(conn, peta[g]["id"], peran) for g, peran in terkait] if termasuk_terkait else [])
    finally:
        conn.close()
    return {
        "utama": utama,
        "bagian": bagian,
        "total_utama": utama["total"],
        "total": sum(b["total"] for b in bagian),
        "terkait": [g for g, _p in terkait],
        "ada_terkait": bool(terkait),
        "slot": material_elemen(e["id"]),
    }
