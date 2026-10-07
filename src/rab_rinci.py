"""
Penyusunan RAB rinci per tipe elemen, seperti RAB konsultan (mis. RAP SMK N 6 Bandung):

    II. PEKERJAAN BETON
        1  Kolom K1 (20/25) — 12 buah
             - Beton Kolom f'c 20 MPa                    m3
             - Bekisting Kolom                           m2
             - Tulangan utama 6 D13                      kg
             - Sengkang Ø10-150                          kg
        2  Balok B1 (15/20) — 8 buah
             ...
    III. PEKERJAAN DINDING
        1  Pasangan Dinding Bata Merah ...              m2

Baris beton, bekisting, dan pembesian elemen yang punya tipe penulangan dikelompokkan per tipe.
Pekerjaan lain digabung per pekerjaan seperti rekap biasa. Dipakai halaman Hasil Estimasi dan export.
"""

from rules.penulangan import URUTAN, label_tipe

URUTAN_KATEGORI = [
    "Tanah", "Fondasi", "Beton", "Dinding", "Lantai", "Pintu & Jendela", "Atap", "Plafon", "Cat", "Air Limbah",
]
_AWALAN_STRUKTUR = ("BTN.", "BSK.", "BSI.")
_URUTAN_ITEM = {"BTN": 0, "BSK": 1, "BSI": 2}


def urutan_kategori(k: str):
    return (URUTAN_KATEGORI.index(k) if k in URUTAN_KATEGORI else len(URUTAN_KATEGORI), k)


def _per_tipe(r) -> bool:
    kode = r.get("kode_ahsp") or ""
    return bool(r.get("tipe_id")) and kode.startswith(_AWALAN_STRUKTUR) and kode != "BTN.SUMURAN"


def _label_item(r) -> str:
    # pembesian rinci memakai uraian tulangan; pekerjaan lain memakai nama pekerjaan
    return r["uraian"] if r.get("uraian") and r.get("diameter") else r["nama_pekerjaan"]


def susun_rinci(baris: list) -> list:
    """Return [{'kategori', 'total', 'grup': [{'judul', 'tipe_id', 'jumlah_elemen', 'items', 'total'}]}].
    Grup tanpa judul (judul None) berisi pekerjaan yang tidak dikelompokkan per tipe.
    Item: {'label', 'kode', 'pekerjaan_id', 'satuan', 'volume', 'jumlah', 'harga'}."""
    kategori = {}
    for r in baris:
        kat = kategori.setdefault(r["kategori"], {})
        if _per_tipe(r):
            kunci_grup = r["tipe_id"]
        else:
            kunci_grup = None
        g = kat.setdefault(kunci_grup, {
            "judul": None, "tipe_id": kunci_grup, "elemen": set(), "items": {},
            "urut": (URUTAN.index(r["kelompok_tipe"]), int((r.get("kode_tipe") or "X0")[1:] or 0))
            if kunci_grup is not None and r.get("kelompok_tipe") in URUTAN else (99, 0),
        })
        if kunci_grup is not None:
            g["judul_dasar"] = label_tipe(
                r["kelompok_tipe"], r["kode_tipe"], (r["tipe_b_cm"] or 0) / 100 or None, (r["tipe_h_cm"] or 0) / 100
            )
            g["elemen"].add(r["elemen_id"])
            kunci_item = (r["pekerjaan_id"], r.get("uraian") if r.get("diameter") else None)
        else:
            kunci_item = (r["pekerjaan_id"], None)
        it = g["items"].setdefault(kunci_item, {
            "label": _label_item(r) if kunci_grup is not None else r["nama_pekerjaan"],
            "kode": r["kode_ahsp"] or "",
            "pekerjaan_id": r["pekerjaan_id"],
            "satuan": r["satuan"],
            "volume": 0.0,
            "jumlah": 0.0,
            "diameter": r.get("diameter") if kunci_grup is not None else None,
        })
        it["volume"] += r["volume_pekerjaan"]
        it["jumlah"] += r["subtotal_biaya"]

    hasil = []
    for nama in sorted(kategori, key=urutan_kategori):
        grup = []
        for g in sorted(kategori[nama].values(), key=lambda g: g["urut"]):
            items = list(g["items"].values())
            for it in items:
                it["harga"] = it["jumlah"] / it["volume"] if it["volume"] else 0.0
            if g["tipe_id"] is not None:
                items.sort(key=lambda it: (
                    _URUTAN_ITEM.get(it["kode"][:3], 9),
                    0 if it["label"].startswith("Tulangan") else 1,
                    -(it["diameter"] or 0),
                ))
                n = len(g["elemen"])
                judul = f"{g['judul_dasar']} — {n} buah"
            else:
                items.sort(key=lambda it: it["label"])
                judul = None
            grup.append({
                "judul": judul,
                "tipe_id": g["tipe_id"],
                "jumlah_elemen": len(g["elemen"]),
                "items": items,
                "total": sum(it["jumlah"] for it in items),
            })
        hasil.append({"kategori": nama, "grup": grup, "total": sum(g["total"] for g in grup)})
    return hasil
