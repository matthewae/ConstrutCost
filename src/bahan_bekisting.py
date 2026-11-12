"""
Bahan bekisting: jenis kayu rangka, triplek / plywood, dan paku yang dipakai pada semua analisa bekisting.

Analisa bekisting HSPK Kota Bandung 2027 (2.2.1.3.x) memakai kayu balok 6/12 kelas II (Rp 5,56 jt/m³), plywood
12 mm (Rp 265.468/lembar), dan paku 12 cm (pelat: paku 4 inch). Untuk rumah tinggal, bekisting cukup memakai bahan
yang lebih murah. Karena itu kayu dan triplek dapat dipilih per proyek (dialog Ganti Bahan, kelompok Bekisting).
Bawaannya adalah pilihan termurah di HSPK: kaso 5/7 dan tripleks 9 mm.

Koefisien analisa (m³ kayu, lembar triplek, kg paku per m² bekisting) tetap mengikuti HSPK. Yang diganti hanya
jenis bahan dan harganya.

Panjang paku dihitung dari tebal bekisting. Paku menembus triplek dan masuk ke rangka kayu:

    panjang minimum  = 3 × tebal triplek           (2/3 panjang paku tertanam di rangka)
    panjang maksimum = tebal triplek + tebal kayu  (paku tidak tembus keluar rangka)

Dipilih ukuran standar HSPK (per kg) di antara batas itu yang harganya paling murah. Contoh: plywood 12 mm + balok
6/12 (tebal 7,2 cm) → 3,6 s.d. 7,2 cm → paku 5 cm (2 inch); paku 12 cm terlalu panjang. Tripleks 9 mm + kaso 5/7
(tebal 5,9 cm) → 2,7 s.d. 5,9 cm → paku 5 cm.

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


def paku(tebal_triplek: float, tebal_kayu: float) -> tuple:
    """(panjang cm, nama harga dasar, panjang minimum, panjang maksimum) paku bekisting dari tebal triplek dan tebal
    rangka kayu (cm). Bila tidak ada ukuran di antara batas, dipakai ukuran terpendek yang >= panjang minimum."""
    minimum = round(3.0 * tebal_triplek, 2)
    maksimum = round(tebal_triplek + tebal_kayu, 2)
    calon = [p for p in PAKU if minimum <= p[0] <= maksimum]
    if not calon:
        calon = [min((p for p in PAKU if p[0] >= minimum), key=lambda p: p[0], default=PAKU[-1])]
    panjang, nama, _harga = min(calon, key=lambda p: (p[2], p[0]))
    return panjang, nama, minimum, maksimum


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
    dipilih. Return (komponen baru, catatan perubahan)."""
    bk, bt = cari(KAYU, kayu, KAYU_BAWAAN), cari(TRIPLEK, triplek, TRIPLEK_BAWAAN)
    panjang, nama_paku, minimum, maksimum = paku(bt.tebal, bk.tebal)
    harga_paku = next(p[2] for p in PAKU if p[1] == nama_paku)
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
                catatan.append(f"{nama} → {nama_paku} ({_cm(panjang)} cm; tebal bekisting {_cm(maksimum)} cm, "
                               f"paku {_cm(minimum)}–{_cm(maksimum)} cm)")
            baru.append((tipe, nama_paku, "kg", koef, harga_paku))
        else:
            baru.append((tipe, nama, satuan, koef, harga))
    return baru, catatan


def _cm(x: float) -> str:
    return f"{x:.1f}".rstrip("0").rstrip(".").replace(".", ",")
