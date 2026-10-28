"""
Pilihan material per pekerjaan (combo box di dialog Pilihan Material).

Rule engine menghitung volume pekerjaan tanpa peduli bahannya: dinding tetap m², kolom tetap m³.
Bahan yang dipilih menentukan analisa HSPK yang dipakai, sehingga harga satuan dan kebutuhan bahannya
(jumlah bata, semen, pasir, ...) ikut berubah, misalnya:

    Pasangan dinding  ->  bata ringan 60x20x10 (8,75 buah/m², mortar siap pakai)   [bawaan]
                          bata merah 1/2 batu 1SP:4PP (71,91 buah/m², semen 11,5 kg, pasir 0,043 m³)
                          batako 20x40x10, conblock HB10, ...

Setiap pilihan adalah satu pekerjaan di database (varian). Pilihan bawaan memakai kode slot itu sendiri
(mis. "DND.BATA"); pilihan lain memakai "kode slot~kunci" (mis. "DND.BATA~merah"). Pilihan disimpan per
proyek (kolom proyek.material, JSON {slot: kunci}); slot yang tidak disimpan memakai pilihan bawaan.
Mengganti pilihan hanya mengganti pekerjaan pada baris hasil yang sudah ada: volume, termasuk volume yang
diedit manual, tidak berubah.
"""

from dataclasses import dataclass

PEMISAH = "~"


@dataclass(frozen=True)
class Opsi:
    kunci: str
    label: str  # teks di combo box
    kode_hspk: str
    nama: str  # nama pekerjaan di RAB
    catatan: str = ""  # ditampilkan di Harga Satuan dan dialog Pilihan Material


@dataclass(frozen=True)
class Slot:
    kode: str  # kode pekerjaan keluaran rule engine
    judul: str  # label di dialog
    kelompok: str  # judul kelompok di dialog
    opsi: tuple
    bawaan: str  # kunci pilihan bawaan

    def cari(self, kunci: str) -> Opsi:
        return next((o for o in self.opsi if o.kunci == kunci), self.opsi_bawaan)

    @property
    def opsi_bawaan(self) -> Opsi:
        return next(o for o in self.opsi if o.kunci == self.bawaan)


def kode_varian(slot: str, kunci: str) -> str:
    """Kode pekerjaan untuk pilihan `kunci` pada slot: kode slot itu sendiri untuk pilihan bawaan."""
    s = SLOT[slot]
    return slot if kunci == s.bawaan else f"{slot}{PEMISAH}{kunci}"


def kode_dasar(kode: str) -> str:
    """'BTN.KOLOM~rm25' -> 'BTN.KOLOM' (kode keluaran rule engine)."""
    return (kode or "").split(PEMISAH)[0]


# ---------------------------------------------------------------- daftar pilihan

# Catatan data HSPK 2027 yang perlu diverifikasi estimator sebelum pilihan itu dipakai untuk penawaran.
_MORTAR = (
    "Harga dasar 'Mortar siap pakai' di HSPK 2027 tercatat Rp 42.800/kg, sedangkan 'Mortar Perekat Bata Ringan' "
    "Rp 198.210/zak 40 kg (± Rp 4.955/kg). Kemungkinan harga per zak tercatat per kg; periksa harga mortar di "
    "Harga Satuan sebelum dipakai untuk penawaran."
)
_CAT_EKSTERIOR = (
    "harga dasar cat penutup eksterior di HSPK 2027 tercatat Rp 1.624.000/kg (kemungkinan harga per pail), "
    "sehingga analisa 3.8.10.2 sekitar 6 kali harga cat interior."
)

_MUTU_BETON = (
    ("m20", "f'c 20 MPa, campuran manual", "2.2.1.4.5", "f'c 20 MPa"),
    ("m21", "f'c 21 MPa, campuran manual", "2.2.1.4.6", "f'c 21 MPa"),
    ("s20", "f'c 20 MPa, molen (semi mekanis)", "2.2.1.5.4", "f'c 20 MPa (Molen)"),
    ("s25", "f'c 25 MPa, molen (semi mekanis)", "2.2.1.5.6", "f'c 25 MPa (Molen)"),
    ("s30", "f'c 30 MPa, molen (semi mekanis)", "2.2.1.5.8", "f'c 30 MPa (Molen)"),
    ("rm20", "f'c 20 MPa, ready mix", "2.2.1.6.4", "f'c 20 MPa (Ready Mix)"),
    ("rm25", "f'c 25 MPa, ready mix", "2.2.1.6.6", "f'c 25 MPa (Ready Mix)"),
    ("rm30", "f'c 30 MPa, ready mix", "2.2.1.6.8", "f'c 30 MPa (Ready Mix)"),
)


def _beton(kode: str, judul: str, awalan: str) -> Slot:
    return Slot(kode, judul, "Mutu beton", tuple(
        Opsi(k, label, hspk, f"{awalan} {mutu}") for k, label, hspk, mutu in _MUTU_BETON
    ), "m20")


_DAFTAR = [
    # ---------------- Struktur beton ----------------
    _beton("BTN.KOLOM", "Kolom", "Beton Kolom"),
    _beton("BTN.BALOK", "Balok", "Beton Balok"),
    _beton("BTN.PELAT", "Pelat lantai", "Beton Pelat Lantai"),
    _beton("BTN.DAK", "Pelat atap (dak)", "Beton Pelat Atap (Dak)"),
    _beton("BTN.SLOOF", "Sloof", "Beton Sloof"),
    _beton("BTN.FONDASI", "Fondasi telapak / menerus", "Beton Fondasi Telapak / Menerus"),
    _beton("BTN.TANGGA", "Tangga", "Beton Tangga"),
    # ---------------- Fondasi ----------------
    Slot("FDN.BATUKALI", "Fondasi batu kali", "Fondasi", (
        Opsi("1:4", "Batu belah 1SP : 4PP", "2.2.2.1.6", "Pasangan Fondasi Batu Belah 1SP : 4PP"),
        Opsi("1:3", "Batu belah 1SP : 3PP", "2.2.2.1.4", "Pasangan Fondasi Batu Belah 1SP : 3PP"),
        Opsi("1:5", "Batu belah 1SP : 5PP", "2.2.2.1.8", "Pasangan Fondasi Batu Belah 1SP : 5PP"),
        Opsi("1:6", "Batu belah 1SP : 6PP", "2.2.2.1.10", "Pasangan Fondasi Batu Belah 1SP : 6PP"),
    ), "1:4"),
    # ---------------- Dinding ----------------
    Slot("DND.BATA", "Pasangan dinding", "Dinding", (
        Opsi("ringan10", "Bata ringan 60×20×10 cm, mortar siap pakai", "3.6.4.2",
             "Pasangan Dinding Bata Ringan 60x20x10 cm", _MORTAR),
        Opsi("ringan7", "Bata ringan 60×20×7,5 cm, mortar siap pakai", "3.6.4.1",
             "Pasangan Dinding Bata Ringan 60x20x7,5 cm", _MORTAR),
        Opsi("ringan20", "Bata ringan 60×20×20 cm, mortar siap pakai", "3.6.4.3",
             "Pasangan Dinding Bata Ringan 60x20x20 cm", _MORTAR),
        Opsi("merah", "Bata merah ½ batu, 1SP : 4PP", "3.6.1.8", "Pasangan Dinding Bata Merah 1/2 Batu 1SP : 4PP"),
        Opsi("merah6", "Bata merah ½ batu, 1SP : 6PP", "3.6.1.10", "Pasangan Dinding Bata Merah 1/2 Batu 1SP : 6PP"),
        Opsi("merah1", "Bata merah 1 batu, 1SP : 4PP", "3.6.1.3", "Pasangan Dinding Bata Merah 1 Batu 1SP : 4PP"),
        Opsi("batako", "Batako 20×40×10 cm, 1SP : 4PP", "3.6.5.2", "Pasangan Dinding Batako 1SP : 4PP"),
        Opsi("hb10", "Conblock HB10, 1SP : 4PP", "3.6.2.6", "Pasangan Dinding Conblock HB10 1SP : 4PP"),
    ), "ringan10"),
    Slot("PLS.DINDING", "Plesteran", "Dinding", (
        Opsi("1:4", "Plesteran 1SP : 4PP tebal 15 mm", "3.7.4", "Plesteran 1SP : 4PP Tebal 15 mm"),
        Opsi("1:2", "Plesteran 1SP : 2PP tebal 15 mm", "3.7.2", "Plesteran 1SP : 2PP Tebal 15 mm"),
        Opsi("1:3", "Plesteran 1SP : 3PP tebal 15 mm", "3.7.3", "Plesteran 1SP : 3PP Tebal 15 mm"),
        Opsi("1:5", "Plesteran 1SP : 5PP tebal 15 mm", "3.7.5", "Plesteran 1SP : 5PP Tebal 15 mm"),
        Opsi("1:6", "Plesteran 1SP : 6PP tebal 15 mm", "3.7.6", "Plesteran 1SP : 6PP Tebal 15 mm"),
        Opsi("instan", "Plesteran semen instan tebal 10 mm", "3.7.7", "Plesteran Semen Instan Tebal 10 mm"),
    ), "1:4"),
    Slot("KRM.DINDING", "Keramik dinding ruang basah", "Dinding", (
        Opsi("20x20", "Keramik 20×20 cm", "3.10.1.4", "Pasangan Keramik Dinding 20x20 cm (Ruang Basah)"),
        Opsi("10x20", "Keramik 10×20 cm", "3.10.1.3", "Pasangan Keramik Dinding 10x20 cm (Ruang Basah)"),
        Opsi("por20", "Porselen 20×20 cm", "3.10.3.3", "Pasangan Porselen Dinding 20x20 cm (Ruang Basah)"),
        Opsi("ht30", "Homogeneous tile 30×30 cm", "3.10.2.1", "Pasangan Homogeneous Tile Dinding 30x30 cm (Ruang Basah)"),
        Opsi("ht60", "Homogeneous tile 60×60 cm", "3.10.2.3", "Pasangan Homogeneous Tile Dinding 60x60 cm (Ruang Basah)"),
    ), "20x20"),
    # ---------------- Lantai ----------------
    Slot("KRM.LANTAI", "Penutup lantai", "Lantai", (
        Opsi("k40", "Keramik 40×40 cm polished", "3.9.8.6", "Pasangan Keramik Lantai 40x40 cm Polished"),
        Opsi("k40u", "Keramik 40×40 cm unpolished", "3.9.8.14", "Pasangan Keramik Lantai 40x40 cm Unpolished"),
        Opsi("k30", "Keramik 30×30 cm polished", "3.9.8.4", "Pasangan Keramik Lantai 30x30 cm Polished"),
        Opsi("k30u", "Keramik 30×30 cm unpolished", "3.9.8.12", "Pasangan Keramik Lantai 30x30 cm Unpolished"),
        Opsi("k3060", "Keramik 30×60 cm polished", "3.9.8.5", "Pasangan Keramik Lantai 30x60 cm Polished"),
        Opsi("k20", "Keramik 20×20 cm polished", "3.9.8.1", "Pasangan Keramik Lantai 20x20 cm Polished"),
        Opsi("ht40", "Homogeneous tile 40×40 cm polished", "3.9.4.2", "Pasangan Homogeneous Tile Lantai 40x40 cm"),
        Opsi("ht60", "Homogeneous tile 60×60 cm polished", "3.9.4.3", "Pasangan Homogeneous Tile Lantai 60x60 cm"),
        Opsi("gr40", "Granit 40×40 cm", "3.9.5.2", "Pasangan Lantai Granit 40x40 cm"),
        Opsi("gr60", "Granit 60×60 cm", "3.9.5.3", "Pasangan Lantai Granit 60x60 cm"),
        Opsi("teraso", "Ubin teraso 40×40 cm", "3.9.3.2", "Pasangan Lantai Ubin Teraso 40x40 cm"),
        Opsi("vinyl", "Vinyl 30×30 cm", "3.9.9.7", "Pemasangan Lantai Vinyl 30x30 cm"),
        Opsi("parket", "Parket kayu solid", "3.9.9.4", "Pemasangan Lantai Parket Kayu Solid"),
    ), "k40"),
    # ---------------- Atap ----------------
    Slot("ATP.RANGKA", "Rangka atap", "Atap", (
        Opsi("c75", "Baja ringan C75, atap pelana", "2.1.1.1", "Rangka Atap Pelana Baja Ringan C75"),
        Opsi("c75jurai", "Baja ringan C75, atap jurai / limasan", "2.1.1.2", "Rangka Atap Jurai / Limasan Baja Ringan C75"),
        Opsi("kayugb", "Kayu kelas II untuk genteng beton", "2.1.2.5", "Rangka Atap Kayu Kelas II (Genteng Beton)"),
        Opsi("kayugk", "Kayu kelas II untuk genteng keramik", "2.1.2.4", "Rangka Atap Kayu Kelas II (Genteng Keramik)"),
    ), "c75"),
    Slot("ATP.PENUTUP", "Penutup atap", "Atap", (
        Opsi("beton", "Genteng beton", "3.1.1.4", "Penutup Atap Genteng Beton"),
        Opsi("plk", "Genteng palentong kecil", "3.1.1.1", "Penutup Atap Genteng Palentong Kecil"),
        Opsi("plb", "Genteng palentong besar", "3.1.1.3", "Penutup Atap Genteng Palentong Besar"),
        Opsi("kodok", "Genteng kodok glazur", "3.1.1.2", "Penutup Atap Genteng Kodok Glazur"),
        Opsi("metal", "Genteng metal lembaran", "3.1.3.7", "Penutup Atap Metal Lembaran"),
        Opsi("metal04", "Atap metal menerus tebal 0,4 mm", "3.1.3.8", "Penutup Atap Metal Menerus 0,4 mm"),
        Opsi("seng", "Seng gelombang 105×180 cm", "3.1.3.1", "Penutup Atap Seng Gelombang"),
        Opsi("serat", "Serat semen gelombang 105×210 cm", "3.1.2.8", "Penutup Atap Serat Semen Gelombang"),
        Opsi("bitumen", "Aspal / bitumen", "3.1.3.6", "Penutup Atap Aspal / Bitumen"),
        Opsi("upvc", "UPVC", "3.1.3.5", "Penutup Atap UPVC"),
    ), "beton"),
    # ---------------- Plafon ----------------
    Slot("PLF.RANGKA", "Rangka plafon", "Plafon", (
        Opsi("hollow", "Besi hollow 40.40, modul 60×60 cm", "3.5.3.1", "Rangka Plafon Besi Hollow 40.40 Modul 60x60 cm"),
        Opsi("kayu50", "Kayu kelas II/III, modul 50×100 cm", "3.5.3.2", "Rangka Plafon Kayu Kelas II/III 50x100 cm"),
        Opsi("kayu60", "Kayu kelas II/III, modul 60×100 cm", "3.5.3.3", "Rangka Plafon Kayu Kelas II/III 60x100 cm"),
    ), "hollow"),
    Slot("PLF.GYPSUM", "Penutup plafon", "Plafon", (
        Opsi("gypsum", "Papan gypsum 9 mm", "3.5.2.1", "Plafon Papan Gypsum Tebal 9 mm"),
        Opsi("grc", "Serat semen / GRC 4–6 mm", "3.5.2.2", "Plafon Serat Semen / GRC"),
        Opsi("triplek", "Kayu lapis 4 mm", "3.5.2.3.2", "Plafon Kayu Lapis Tebal 4 mm"),
        Opsi("lambri", "Lambrisering kayu 9 mm", "3.5.2.4", "Plafon Lambrisering Kayu Tebal 9 mm"),
        Opsi("spandrel", "Aluminium spandrel", "3.5.2.7", "Plafon Aluminium Spandrel"),
        Opsi("akustik", "Akustik 60×120 cm", "3.5.1.3", "Plafon Akustik 60x120 cm"),
    ), "gypsum"),
    # ---------------- Cat ----------------
    Slot("CAT.DINDING", "Cat dinding interior", "Cat", (
        Opsi("baru", "Cat tembok baru (1 cat dasar + 2 cat penutup)", "3.8.10.1",
             "Pengecatan Tembok Baru Interior (1 Lapis Cat Dasar, 2 Lapis Cat Penutup)"),
        Opsi("air", "Cat berbasis air (water-based), 2 lapis", "3.8.23.1", "Pengecatan Dinding Cat Berbasis Air, 2 Lapis"),
        Opsi("kapur", "Labur kapur (pemutih)", "3.8.12", "Pelaburan Tembok dengan Kapur"),
    ), "baru"),
    Slot("CAT.EKSTERIOR", "Cat dinding eksterior", "Cat", (
        Opsi("interior", "Analisa cat interior 3.8.10.1 (sementara)", "3.8.10.1",
             "Pengecatan Tembok Baru Eksterior (1 Lapis Cat Dasar, 2 Lapis Cat Penutup)",
             "Sementara memakai analisa cat interior 3.8.10.1: " + _CAT_EKSTERIOR + " Ganti pilihan atau komponen "
             "di Analisa Pekerjaan bila harga cat eksterior sudah diverifikasi."),
        Opsi("hspk", "Analisa cat eksterior HSPK 3.8.10.2", "3.8.10.2",
             "Pengecatan Tembok Baru Eksterior (Analisa HSPK 3.8.10.2)", _CAT_EKSTERIOR),
        Opsi("air", "Cat berbasis air (water-based), 2 lapis", "3.8.23.1", "Pengecatan Eksterior Cat Berbasis Air, 2 Lapis"),
        Opsi("mineral", "Breathable mineral paint, 2 lapis", "3.8.23.11", "Pengecatan Eksterior Breathable Mineral Paint, 2 Lapis"),
    ), "interior"),
    # ---------------- Pintu & jendela ----------------
    Slot("PTU.DAUN", "Daun pintu", "Pintu & jendela", (
        Opsi("panel", "Panel kayu kelas I/II", "3.11.1.11", "Daun Pintu Panel Kayu Kelas I/II"),
        Opsi("plywood", "Plywood rangkap, rangka kayu kelas II", "3.11.1.12", "Daun Pintu Plywood Rangkap"),
        Opsi("plyexpose", "Plywood rangkap, rangka ekspos kayu kelas I/II", "3.11.1.13", "Daun Pintu Plywood Rangka Ekspos"),
        Opsi("kaca", "Kaca 6 mm rangka aluminium", "3.11.1.5", "Daun Pintu Kaca 6 mm Rangka Aluminium"),
        Opsi("klamp", "Klamp standar kayu kelas II", "3.11.1.7", "Daun Pintu Klamp Kayu Kelas II"),
        Opsi("pvc", "Pintu lipat PVC", "3.11.1.3", "Pintu Lipat PVC"),
        Opsi("ew", "Engineering wood", "3.11.1.17", "Daun Pintu Engineering Wood"),
        Opsi("besi", "Pelat baja 2 mm rangkap", "3.11.1.15", "Daun Pintu Besi Pelat Baja 2 mm"),
    ), "panel"),
    Slot("PTU.KUSEN", "Kusen pintu", "Pintu & jendela", (
        Opsi("k2_615", "Kayu kelas II/III 6×15 cm", "3.11.3.5", "Kusen Pintu Kayu Kelas II/III 6x15 cm"),
        Opsi("k2_612", "Kayu kelas II/III 6×12 cm", "3.11.3.4", "Kusen Pintu Kayu Kelas II/III 6x12 cm"),
        Opsi("k1_615", "Kayu kelas I 6×15 cm", "3.11.3.3", "Kusen Pintu Kayu Kelas I 6x15 cm"),
        Opsi("k1_612", "Kayu kelas I 6×12 cm", "3.11.3.2", "Kusen Pintu Kayu Kelas I 6x12 cm"),
        Opsi("alu", "Aluminium", "3.11.3.1", "Kusen Pintu Aluminium"),
    ), "k2_615"),
    Slot("PTU.KUNCI", "Kunci pintu", "Pintu & jendela", (
        Opsi("biasa", "Kunci tanam biasa", "3.11.4.2", "Kunci Tanam Pintu"),
        Opsi("silinder", "Kunci tanam silinder", "3.11.4.4", "Kunci Tanam Silinder"),
        Opsi("antik", "Kunci tanam antik", "3.11.4.1", "Kunci Tanam Antik"),
        Opsi("km", "Kunci tanam kamar mandi", "3.11.4.3", "Kunci Tanam Kamar Mandi"),
    ), "biasa"),
    Slot("JDL.JENDELA", "Jendela", "Pintu & jendela", (
        Opsi("alu", "Kaca 6 mm rangka aluminium", "3.11.1.6", "Jendela Kaca 6 mm Rangka Aluminium"),
        Opsi("nako", "Nako aluminium, kaca 5 mm", "3.11.2.1", "Jendela Nako Aluminium Kaca 5 mm"),
        Opsi("kayu", "Daun jendela kaca, kayu kelas I/II", "3.11.1.9", "Jendela Kaca Rangka Kayu Kelas I/II"),
    ), "alu"),
]

SLOT = {s.kode: s for s in _DAFTAR}
KELOMPOK = list(dict.fromkeys(s.kelompok for s in _DAFTAR))


def pilihan_lengkap(tersimpan: dict | None) -> dict:
    """{slot: kunci} untuk semua slot; kunci yang tidak dikenal kembali ke pilihan bawaan."""
    tersimpan = tersimpan or {}
    return {
        k: (tersimpan[k] if any(o.kunci == tersimpan.get(k) for o in s.opsi) else s.bawaan)
        for k, s in SLOT.items()
    }


def varian_terpilih(pilihan: dict) -> dict:
    """{kode keluaran rule: kode pekerjaan varian} untuk slot yang tidak memakai pilihan bawaan."""
    return {k: kode_varian(k, v) for k, v in pilihan_lengkap(pilihan).items() if v != SLOT[k].bawaan}
