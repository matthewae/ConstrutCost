"""
KF-19: dimensi elemen yang bisa diubah pengguna dan cara menurunkan luas / volume darinya.

Setiap kelas elemen punya dimensi PRIMER (diisi pengguna, mis. panjang & lebar pelat) dan dimensi
TURUNAN (luas, volume, keliling) yang dihitung ulang dengan asumsi bentuk reguler (Batasan Masalah
no. 7), sesuai rumus BAB II:
    pelat   : A = L x B,  V = A x t                       (Rumus 2.11)
    atap    : A = (L x B) / cos θ, V = A x t               (Rumus 2.22)
    dinding : A = L x H - A_bukaan, V = A x t              (Rumus 2.17, 2.40)
    kolom   : V = b x h x H                                (Rumus 2.10)
    balok   : V = L x b x h                                (Rumus 2.9)
    fondasi : V = L x B x t
    tiang   : V = π d²/4 x L                               (Rumus 2.36)
    pintu / jendela / penutup lantai / plafon / ruang: A = L x B (atau B x H)
"""

import math

from klasifikasi import ElementType as T

SATUAN = {
    "panjang": "m", "lebar": "m", "tinggi": "m", "tebal": "m", "keliling": "m",
    "luas": "m²", "luas_bukaan": "m²", "volume": "m³", "kemiringan": "°",
}
LABEL = {
    "panjang": "Panjang (L)",
    "lebar": "Lebar (B)",
    "tinggi": "Tinggi (H)",
    "tebal": "Tebal (t)",
    "luas": "Luas (A)",
    "volume": "Volume (V)",
    "keliling": "Keliling",
    "kemiringan": "Kemiringan (θ)",
    "luas_bukaan": "Luas bukaan pintu/jendela",
}
LABEL_KHUSUS = {
    T.COLUMN: {"lebar": "Lebar penampang (b)", "tebal": "Tinggi penampang (h)", "tinggi": "Tinggi kolom (H)"},
    T.BEAM: {"lebar": "Lebar balok (b)", "tinggi": "Tinggi balok (h)"},
    T.ROOF: {"panjang": "Panjang proyeksi (L)", "lebar": "Lebar proyeksi (B)", "luas": "Luas bidang miring (A)"},
    T.PILE: {"lebar": "Diameter (d)", "panjang": "Panjang tiang (L)"},
    T.WALL: {"luas": "Luas bersih satu sisi (A)"},
}

# kelas -> (dimensi primer, dimensi turunan)
DIMENSI = {
    T.SLAB: (("panjang", "lebar", "tebal"), ("luas", "volume", "keliling")),
    T.ROOF: (("panjang", "lebar", "tebal", "kemiringan"), ("luas", "volume", "keliling")),
    T.WALL: (("panjang", "tinggi", "tebal", "luas_bukaan"), ("luas", "volume")),
    T.COLUMN: (("lebar", "tebal", "tinggi"), ("volume",)),
    T.BEAM: (("panjang", "lebar", "tinggi"), ("volume",)),
    T.FOOTING: (("panjang", "lebar", "tebal"), ("volume", "keliling")),
    T.PILE: (("panjang", "lebar"), ("volume",)),
    T.DOOR: (("lebar", "tinggi"), ("luas",)),
    T.WINDOW: (("lebar", "tinggi"), ("luas",)),
    T.FLOOR: (("panjang", "lebar"), ("luas", "keliling")),
    T.CEILING: (("panjang", "lebar"), ("luas", "keliling")),
    T.SPACE: (("panjang", "lebar", "tinggi"), ("luas", "keliling")),
}
# dimensi yang boleh bernilai nol
BOLEH_NOL = {"kemiringan", "luas_bukaan"}


class DimensiTidakValid(ValueError):
    """Nilai dimensi ditolak. Pesannya siap ditampilkan ke pengguna."""


def label(kelas: T, kunci: str) -> str:
    return LABEL_KHUSUS.get(kelas, {}).get(kunci, LABEL[kunci])


def kolom_dimensi(kelas: T):
    """(primer, turunan) untuk kelas elemen; kelas tanpa dimensi -> ((), ())."""
    return DIMENSI.get(kelas, ((), ()))


def turunkan(kelas: T, d: dict) -> dict:
    """Hitung dimensi turunan dari dimensi primer. Hanya nilai yang semua masukannya ada
    yang dikembalikan, sehingga elemen berbentuk tidak reguler tetap bisa diisi manual."""

    def ada(*k):
        return all(d.get(x) is not None and (d[x] > 0 or (x in BOLEH_NOL and d[x] >= 0)) for x in k)

    h = {}
    if kelas in (T.SLAB, T.FLOOR, T.CEILING, T.SPACE, T.FOOTING) and ada("panjang", "lebar"):
        h["keliling"] = 2 * (d["panjang"] + d["lebar"])
    if kelas in (T.SLAB, T.FLOOR, T.CEILING, T.SPACE) and ada("panjang", "lebar"):
        h["luas"] = d["panjang"] * d["lebar"]
    if kelas == T.SLAB and ada("tebal") and "luas" in h:
        h["volume"] = h["luas"] * d["tebal"]
    if kelas == T.ROOF and ada("panjang", "lebar"):
        h["keliling"] = 2 * (d["panjang"] + d["lebar"])
        teta = d.get("kemiringan") or 0.0
        if not 0 <= teta < 90:
            raise DimensiTidakValid("Kemiringan atap harus 0° sampai kurang dari 90°.")
        h["luas"] = d["panjang"] * d["lebar"] / math.cos(math.radians(teta))
        if ada("tebal"):
            h["volume"] = h["luas"] * d["tebal"]
    if kelas == T.WALL and ada("panjang", "tinggi"):
        luas = d["panjang"] * d["tinggi"] - (d.get("luas_bukaan") or 0.0)
        if luas <= 0:
            raise DimensiTidakValid("Luas bukaan lebih besar dari luas dinding.")
        h["luas"] = luas
        if ada("tebal"):
            h["volume"] = luas * d["tebal"]
    if kelas == T.COLUMN and ada("lebar", "tebal", "tinggi"):
        h["volume"] = d["lebar"] * d["tebal"] * d["tinggi"]
    if kelas == T.BEAM and ada("panjang", "lebar", "tinggi"):
        h["volume"] = d["panjang"] * d["lebar"] * d["tinggi"]
    if kelas == T.FOOTING and ada("panjang", "lebar", "tebal"):
        h["volume"] = d["panjang"] * d["lebar"] * d["tebal"]
    if kelas == T.PILE and ada("panjang", "lebar"):
        h["volume"] = math.pi * d["lebar"] ** 2 / 4 * d["panjang"]
    if kelas in (T.DOOR, T.WINDOW) and ada("lebar", "tinggi"):
        h["luas"] = d["lebar"] * d["tinggi"]
    return h


def validasi(kelas: T, d: dict) -> dict:
    """Periksa nilai masukan pengguna (UC-03 skenario alternatif A). Return dict float."""
    primer, turunan = kolom_dimensi(kelas)
    if not primer:
        raise DimensiTidakValid("Dimensi elemen jenis ini tidak dapat diubah.")
    hasil = {}
    for k, v in d.items():
        if k not in primer and k not in turunan:
            raise DimensiTidakValid(f"Dimensi '{k}' tidak berlaku untuk elemen ini.")
        if v is None:
            hasil[k] = None
            continue
        try:
            nilai = float(v)
        except (TypeError, ValueError):
            raise DimensiTidakValid(f"{label(kelas, k)} harus berupa angka.") from None
        if math.isnan(nilai) or nilai < 0 or (nilai == 0 and k not in BOLEH_NOL):
            raise DimensiTidakValid(f"{label(kelas, k)} harus lebih besar dari nol.")
        hasil[k] = nilai
    return hasil


# dimensi primer yang memengaruhi tiap dimensi turunan
GANTUNG = {
    "luas": {"panjang", "lebar", "tinggi", "luas_bukaan", "kemiringan"},
    "keliling": {"panjang", "lebar"},
}
BERLAPIS = (T.SLAB, T.ROOF, T.WALL)  # volume = luas x tebal


def turunkan_dari(kelas: T, d: dict, diubah) -> dict:
    """Seperti turunkan(), tetapi hanya dimensi turunan yang dipengaruhi dimensi `diubah`.

    Dengan begitu nilai dari model IFC yang tidak terkait tetap dipakai. Contohnya, bila hanya
    tebal dinding yang diubah, luas Qto dinding tetap dan volumenya menjadi luas x tebal baru.
    Pada pelat/atap/dinding, luas yang diisi langsung juga menghitung ulang volume."""
    diubah = set(diubah)
    primer, turunan = kolom_dimensi(kelas)
    if not diubah & (set(primer) | {"luas"}):
        return {}
    h = turunkan(kelas, d) if diubah & set(primer) else {}
    out = {k: v for k, v in h.items() if k in GANTUNG and diubah & GANTUNG[k]}
    if "volume" in turunan:
        if kelas in BERLAPIS:
            luas = out.get("luas", d.get("luas"))
            tebal = d.get("tebal")
            if diubah & (GANTUNG["luas"] | {"luas", "tebal"}) and luas and tebal and luas > 0 and tebal > 0:
                out["volume"] = luas * tebal
        elif "volume" in h:
            out["volume"] = h["volume"]
    return out
