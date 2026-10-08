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

import re

from rules.penulangan import URUTAN, label_tipe

URUTAN_KATEGORI = [
    "Tanah", "Fondasi", "Beton", "Dinding", "Lantai", "Pintu & Jendela", "Atap", "Plafon", "Cat", "Air Limbah",
]
_AWALAN_STRUKTUR = ("BTN.", "BSK.", "BSI.")
_URUTAN_ITEM = {"BTN": 0, "BSK": 1, "BSI": 2}


def cocok_saring(r: dict, saring) -> bool:
    """True bila baris hasil `r` termasuk item RAB rinci dengan penyaring `saring` (lihat susun_rinci)."""
    if not saring:
        return True
    if saring[0] == "tipe":
        return _per_tipe(r) and r.get("tipe_id") == saring[1] and (saring[2] is None or r.get("uraian") == saring[2])
    if saring[0] == "elemen":
        return not _per_tipe(r) and nama_tipe_elemen(r.get("nama_elemen")) == saring[1]
    return not _per_tipe(r)


def urutan_kategori(k: str):
    return (URUTAN_KATEGORI.index(k) if k in URUTAN_KATEGORI else len(URUTAN_KATEGORI), k)


def _per_tipe(r) -> bool:
    kode = r.get("kode_ahsp") or ""
    return bool(r.get("tipe_id")) and kode.startswith(_AWALAN_STRUKTUR) and kode != "BTN.SUMURAN"


def nama_tipe_elemen(nama) -> str:
    """'Basic Wall:Exterior - Brick on Block:347125' -> 'Basic Wall:Exterior - Brick on Block'
    (nomor id unik Revit dibuang agar elemen bertipe sama terkumpul)."""
    nama = re.sub(r":\d+$", "", (nama or "").strip())
    if not nama:
        return "(tanpa nama elemen)"
    return nama if len(nama) <= 60 else nama[:59] + "…"


def _label_item(r) -> str:
    # pembesian rinci memakai uraian tulangan; pekerjaan lain memakai nama pekerjaan
    return r["uraian"] if r.get("uraian") and r.get("diameter") else r["nama_pekerjaan"]


def susun_rinci(baris: list, per_tipe_elemen: bool = False) -> list:
    """Return [{'kategori', 'total', 'grup': [{'judul', 'tipe_id', 'jumlah_elemen', 'items', 'total'}]}].
    Grup tanpa judul (judul None) berisi pekerjaan yang tidak dikelompokkan per tipe.
    Item: {'label', 'kode', 'pekerjaan_id', 'satuan', 'volume', 'jumlah', 'harga'}.

    per_tipe_elemen=True (mode/sheet RAB Rinci): pekerjaan non-struktur juga dirinci, satu grup per
    pekerjaan berisi baris per tipe elemen IFC, mis. "Pasangan Dinding Bata" -> "Basic Wall:Exterior -
    Brick on Block — 16 buah", "Basic Wall:Interior 100mm — 9 buah"."""
    if per_tipe_elemen:
        return _susun_rinci_per_tipe_elemen(baris)
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
            # penyaring baris hasil yang membentuk item ini (panel rincian & "Pakai Harga Ini" hanya ke baris itu)
            "saring": ("tipe", kunci_grup, r.get("uraian") if r.get("diameter") else None)
            if kunci_grup is not None else ("lain",),
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


def _susun_rinci_per_tipe_elemen(baris: list) -> list:
    """Seperti susun_rinci, tetapi pekerjaan non-struktur dipecah per tipe elemen IFC (lihat docstring)."""
    struktur = [r for r in baris if _per_tipe(r)]
    hasil = {k["kategori"]: k for k in susun_rinci(struktur)}
    lain = {}
    for r in baris:
        if _per_tipe(r):
            continue
        g = lain.setdefault(r["kategori"], {}).setdefault(r["pekerjaan_id"], {
            "judul": r["nama_pekerjaan"], "kode": r["kode_ahsp"] or "", "satuan": r["satuan"], "items": {}})
        it = g["items"].setdefault(nama_tipe_elemen(r.get("nama_elemen")), {"n": 0, "volume": 0.0, "jumlah": 0.0})
        it["n"] += 1
        it["volume"] += r["volume_pekerjaan"]
        it["jumlah"] += r["subtotal_biaya"]
    for kat, per_pek in lain.items():
        k = hasil.setdefault(kat, {"kategori": kat, "grup": [], "total": 0.0})
        for pid, g in sorted(per_pek.items(), key=lambda x: x[1]["judul"]):
            items = []
            for nama, it in sorted(g["items"].items(), key=lambda x: (-x[1]["volume"], x[0])):
                items.append({
                    "label": f"{nama} — {it['n']} buah", "kode": g["kode"], "pekerjaan_id": pid,
                    "satuan": g["satuan"], "volume": it["volume"], "jumlah": it["jumlah"],
                    "harga": it["jumlah"] / it["volume"] if it["volume"] else 0.0, "diameter": None,
                    "saring": ("elemen", nama),
                })
            total = sum(i["jumlah"] for i in items)
            k["grup"].append({"judul": g["judul"], "tipe_id": None, "jumlah_elemen": sum(v["n"] for v in g["items"].values()),
                              "items": items, "total": total})
            k["total"] += total
    return [hasil[k] for k in sorted(hasil, key=urutan_kategori)]


# ---------------------------------------------------------------- KF-12 rekap per lantai

TANPA_LANTAI = "Tanpa lantai"


def daftar_lantai(baris: list) -> list:
    """Nama lantai urut elevasi (terendah dulu); baris tanpa lantai di akhir."""
    elev = {}
    for r in baris:
        nama = r.get("lantai") or TANPA_LANTAI
        e = r.get("elevasi_lantai")
        if nama not in elev or (e is not None and (elev[nama] is None or e < elev[nama])):
            elev[nama] = e
    return sorted(elev, key=lambda n: (n == TANPA_LANTAI, elev[n] if elev[n] is not None else float("inf"), n))


def rekap_per_lantai(baris: list) -> list:
    """KF-12: biaya per lantai, dirinci per kategori pekerjaan.
    Return [{'lantai', 'elevasi', 'jumlah_elemen', 'total', 'kategori': [{'kategori', 'total'}]}]."""
    data = {}
    for r in baris:
        nama = r.get("lantai") or TANPA_LANTAI
        d = data.setdefault(nama, {"lantai": nama, "elevasi": r.get("elevasi_lantai"), "elemen": set(), "kat": {}})
        if r.get("elemen_id"):
            d["elemen"].add(r["elemen_id"])
        d["kat"][r["kategori"]] = d["kat"].get(r["kategori"], 0.0) + r["subtotal_biaya"]
    hasil = []
    for nama in daftar_lantai(baris):
        d = data[nama]
        kat = [{"kategori": k, "total": d["kat"][k]} for k in sorted(d["kat"], key=urutan_kategori)]
        hasil.append({
            "lantai": nama,
            "elevasi": d["elevasi"],
            "jumlah_elemen": len(d["elemen"]),
            "total": sum(k["total"] for k in kat),
            "kategori": kat,
        })
    return hasil
