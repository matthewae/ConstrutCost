"""
Bahan bekisting: jenis kayu rangka, triplek / plywood, dan paku yang dipakai pada semua analisa bekisting.

Analisa bekisting HSPK Kota Bandung 2027 (2.2.1.3.x) memakai kayu balok 6/12 kelas II (Rp 5,56 jt/m³), plywood
12 mm (Rp 265.468/lembar), dan paku 12 cm (pelat: paku 4 inch). Untuk rumah tinggal, bekisting cukup memakai bahan
yang lebih murah. Karena itu kayu dan triplek dapat dipilih per proyek (dialog Ganti Bahan, kelompok Bekisting).
Bawaannya adalah pilihan termurah di HSPK: kaso 5/7 dan tripleks 9 mm.

Koefisien analisa (m³ kayu, lembar triplek, kg paku per m² bekisting) tetap mengikuti HSPK. Yang diganti hanya
jenis bahan dan harganya.

Ukuran paku ditentukan menurut KEGUNAANNYA; paku tidak boleh lebih panjang dari tebal bahan yang disambung (tembus):

1. Paku sambungan rangka (kayu ke kayu: tiang, gelagar, klem): koefisien paku HSPK (0,4 kg/m²) dipakai untuk ini.
       panjang minimum  = 1,5 × tebal kayu   (sepertiga panjang paku tertanam di kayu kedua)
       panjang maksimum = 2 × tebal kayu     (dua kayu yang disambung; paku tidak tembus)
   Kaso 5/7 → 7,5 s.d. 10 cm → paku 10 cm (4 inch). Balok 6/12 → 9 s.d. 12 cm → paku 10 cm (12 cm juga tidak
   tembus, tetapi di HSPK paku 12 cm hanya berharga per buah).
2. Paku triplek ke rangka: koefisien 0,03 kg/m² seperti "Paku Tripleks" pada analisa HSPK pemasangan kayu lapis
   (3.5.2.3.x).
       panjang minimum  = 3 × tebal triplek          (2/3 panjang paku tertanam di rangka)
       panjang maksimum = tebal triplek + tebal kayu (paku tidak tembus keluar rangka)
   Plywood 12 mm + balok 6/12 (tebal 7,2 cm) → 3,6 s.d. 7,2 cm → paku 5 cm; paku 12 cm akan tembus ± 4,8 cm.
   Tripleks 9 mm + kaso 5/7 (tebal 5,9 cm) → 2,7 s.d. 5,9 cm → paku 5 cm.

Dari ukuran paku per kg di HSPK, dipilih yang termurah di antara batas itu.

Catatan data HSPK: analisa bekisting kolom/balok/sloof memakai "Paku 12 cm" 0,4 kg/m² dengan harga Rp 1.200,
sedangkan daftar harga dasar HSPK mencatat Paku 12 cm Rp 1.200 per buah, bukan per kg.
"""

from dataclasses import dataclass

# Pekerjaan bekisting keluaran rule engine (semuanya memakai analisa HSPK 2.2.1.3.x)
KODE_BEKISTING = (
    "BSK.FONDASI", "BSK.CAKAR.PELAT", "BSK.CAKAR.PIPA", "BSK.SLOOF", "BSK.KOLOM", "BSK.BALOK", "BSK.PELAT",
    "BSK.DAK", "BSK.TANGGA", "LSK.BEKISTING",
)
SLOT_KAYU, SLOT_TRIPLEK = "BSK.KAYU", "BSK.TRIPLEK"
PEMISAH_BAHAN = "+"


@dataclass(frozen=True)
class Bahan:
    kunci: str
    label: str  # teks di combo box
    nama: str  # nama harga dasar HSPK
    satuan: str
    tebal: float  # cm (kayu: tebal rangka; triplek: tebal papan)
    harga: float  # harga dasar HSPK 2027 (untuk urutan & aturan paku; harga di database yang dipakai RAB)


# Kayu rangka bekisting, urut dari yang termurah (harga dasar HSPK 2027)
KAYU = (
    Bahan("kaso57", "Kaso 5/7 kayu kelas II", "Kaso 5/7 kayu kelas II", "m3", 5.0, 2_497_500.0),
    Bahan("kaso57k3", "Kaso 5/7 kayu kelas III", "Kayu kaso 5/7 kelas III", "m3", 5.0, 2_845_931.0),
    Bahan("sengon", "Balok kayu sengon", "Kayu sengon (balok)", "m3", 6.0, 4_150_000.0),
    Bahan("borneo", "Balok kayu borneo", "Kayu Balok Borneo", "M3", 6.0, 5_400_000.0),
    Bahan("balok612k2", "Balok 6/12 kayu kelas II (analisa HSPK)", "Kayu balok 6/12 kelas II", "m3", 6.0,
          5_555_555.556),
    Bahan("balok612k1", "Balok 6/12 kayu kelas I", "Kayu balok 6/12 kelas I", "m3", 6.0, 6_250_000.0),
)
# Triplek / plywood bekisting, urut dari yang termurah
TRIPLEK = (
    Bahan("t9", "Tripleks 9 mm", "Tripleks t=9mm", "lembar", 0.9, 150_000.0),
    Bahan("p9", "Plywood 9 mm", "Plywood 9 mm (120x240)", "lembar", 0.9, 160_000.0),
    Bahan("m9", "Multiplek 9 mm", "Multiplek tebal 9 mm", "lembar", 0.9, 175_000.0),
    Bahan("m12", "Multiplek 12 mm", "Multiplek tebal 12 mm", "lembar", 1.2, 239_233.0),
    Bahan("p12", "Plywood 12 mm (analisa HSPK)", "Plywood 12 mm", "lembar", 1.2, 265_468.0),
    Bahan("m18", "Multiplek 18 mm", "Multiplek tebal 18 mm", "lembar", 1.8, 309_058.0),
)
KAYU_BAWAAN, TRIPLEK_BAWAAN = "kaso57", "t9"

KOEF_PAKU_TRIPLEK = 0.03  # kg/m², "Paku Tripleks" pada analisa HSPK pemasangan kayu lapis 3.5.2.3.x

# Paku per kg di HSPK 2027: (panjang cm, nama harga dasar, harga per kg)
PAKU = (
    (3.0, "Paku 3 cm", 37_500.0),
    (5.0, "Paku 2 inch", 21_900.0),
    (7.0, "Paku 5 dan 7 cm", 38_000.0),
    (10.0, "Paku 4 inch", 22_200.0),
    (12.7, "Paku biasa 5 inchi", 26_000.0),
)

# Komponen analisa HSPK yang diganti. Bekisting fondasi & sloof HSPK (2.2.1.3.1/2) memakai papan kayu kelas III
# sebagai muka bekisting tanpa triplek: papan & pakunya tidak diganti.
KAYU_HSPK = tuple(dict.fromkeys(("Kayu balok 6/12 kelas II", *(b.nama for b in KAYU))))
TRIPLEK_HSPK = tuple(dict.fromkeys(("Plywood 12 mm", *(b.nama for b in TRIPLEK))))


def nama_pendek(b: Bahan) -> str:
    return b.label.replace(" (analisa HSPK)", "")


def koefisien(komponen: list) -> tuple:
    """(m³ kayu, lembar triplek) per satuan pekerjaan dari komponen analisa bekisting."""
    kayu = sum(k for t, n, _s, k, *_ in komponen if t == "bahan" and n in KAYU_HSPK)
    triplek = sum(k for t, n, _s, k, *_ in komponen if t == "bahan" and n in TRIPLEK_HSPK)
    return kayu, triplek


def cari(daftar: tuple, kunci: str | None, bawaan: str) -> Bahan:
    return next((b for b in daftar if b.kunci == kunci), next(b for b in daftar if b.kunci == bawaan))


def _pilih_paku(minimum: float, maksimum: float) -> tuple:
    """Ukuran paku per kg termurah di antara batas; bila tidak ada, yang terpanjang <= maksimum (tidak tembus)."""
    calon = [p for p in PAKU if minimum <= p[0] <= maksimum]
    if not calon:
        calon = [max((p for p in PAKU if p[0] <= maksimum), key=lambda p: p[0], default=PAKU[0])]
    panjang, nama, _harga = min(calon, key=lambda p: (p[2], p[0]))
    return panjang, nama, minimum, maksimum


def paku(tebal_triplek: float, tebal_kayu: float) -> tuple:
    """Paku triplek ke rangka: (panjang cm, nama harga dasar, panjang minimum, panjang maksimum) dari tebal triplek dan
    tebal rangka kayu (cm): 3 × tebal triplek s.d. tebal triplek + tebal kayu."""
    return _pilih_paku(round(3.0 * tebal_triplek, 2), round(tebal_triplek + tebal_kayu, 2))


def paku_rangka(tebal_kayu: float) -> tuple:
    """Paku sambungan rangka kayu ke kayu: 1,5 × tebal kayu s.d. 2 × tebal kayu (dua kayu disambung, tidak tembus)."""
    return _pilih_paku(round(1.5 * tebal_kayu, 2), round(2.0 * tebal_kayu, 2))


def kode_varian_bekisting(kode: str, kayu: str, triplek: str) -> str:
    """Kode pekerjaan bekisting untuk pasangan kayu & triplek: kode itu sendiri untuk bahan bawaan."""
    if kayu == KAYU_BAWAAN and triplek == TRIPLEK_BAWAAN:
        return kode
    return f"{kode}~{kayu}{PEMISAH_BAHAN}{triplek}"


def urai_varian(kode: str) -> tuple | None:
    """'BSK.KOLOM~sengon+m12' -> ('BSK.KOLOM', 'sengon', 'm12'); kode bekisting bawaan -> (kode, bawaan, bawaan);
    kode lain -> None."""
    dasar, _, sisa = kode.partition("~")
    if dasar not in KODE_BEKISTING:
        return None
    if not sisa:
        return dasar, KAYU_BAWAAN, TRIPLEK_BAWAAN
    kayu, _, triplek = sisa.partition(PEMISAH_BAHAN)
    if not any(b.kunci == kayu for b in KAYU) or not any(b.kunci == triplek for b in TRIPLEK):
        return None
    return dasar, kayu, triplek


def ganti_komponen(komponen: list, kayu: str, triplek: str) -> tuple:
    """Komponen analisa bekisting HSPK [(tipe, nama, satuan, koef, harga)] dengan kayu, triplek, dan paku yang
    dipilih: paku HSPK menjadi paku sambungan rangka (ukuran dari tebal kayu), ditambah paku triplek ke rangka
    (ukuran dari tebal triplek + kayu). Return (komponen baru, catatan perubahan)."""
    bk, bt = cari(KAYU, kayu, KAYU_BAWAAN), cari(TRIPLEK, triplek, TRIPLEK_BAWAAN)
    panjang, nama_paku, minimum, maksimum = paku_rangka(bk.tebal)
    harga_paku = next(p[2] for p in PAKU if p[1] == nama_paku)
    p_trip = paku(bt.tebal, bk.tebal)
    ada_triplek = any(t == "bahan" and n in TRIPLEK_HSPK for t, n, *_ in komponen)
    baru, catatan = [], []
    for tipe, nama, satuan, koef, harga, *_ in komponen:
        if tipe == "bahan" and nama in KAYU_HSPK:
            if nama != bk.nama:
                catatan.append(f"{nama} → {bk.nama}")
            baru.append((tipe, bk.nama, bk.satuan, koef, bk.harga))
        elif tipe == "bahan" and nama in TRIPLEK_HSPK:
            if nama != bt.nama:
                catatan.append(f"{nama} → {bt.nama}")
            baru.append((tipe, bt.nama, bt.satuan, koef, bt.harga))
        elif tipe == "bahan" and ada_triplek and nama.lower().startswith("paku"):
            if nama != nama_paku:
                catatan.append(f"{nama} → {nama_paku} {_cm(panjang)} cm untuk sambungan rangka {nama_pendek(bk)} "
                               f"(paku {_cm(minimum)}–{_cm(maksimum)} cm agar tidak tembus)")
            baru.append((tipe, nama_paku, "kg", koef, harga_paku))
        else:
            baru.append((tipe, nama, satuan, koef, harga))
    if ada_triplek:  # paku triplek ke rangka
        harga_trip = next(p[2] for p in PAKU if p[1] == p_trip[1])
        catatan.append(f"+ {p_trip[1]} {_cm(p_trip[0])} cm {_cm(KOEF_PAKU_TRIPLEK, 2)} kg/m² untuk triplek ke rangka "
                       f"(tebal bekisting {_cm(p_trip[3])} cm, paku {_cm(p_trip[2])}–{_cm(p_trip[3])} cm)")
        sama = next((i for i, k in enumerate(baru) if k[0] == "bahan" and k[1] == p_trip[1]), None)
        if sama is None:
            baru.append(("bahan", p_trip[1], "kg", KOEF_PAKU_TRIPLEK, harga_trip))
        else:  # ukuran sama dengan paku rangka: koefisien dijumlahkan
            t, n, sat, k, h = baru[sama]
            baru[sama] = (t, n, sat, k + KOEF_PAKU_TRIPLEK, h)
    return baru, catatan


def _cm(x: float, desimal: int = 1) -> str:
    return f"{x:.{desimal}f}".rstrip("0").rstrip(".").replace(".", ",")
