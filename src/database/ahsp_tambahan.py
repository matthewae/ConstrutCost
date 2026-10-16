"""
Analisa harga satuan yang tidak ada di workbook HSPK Kota Bandung 2027 tetapi dibutuhkan rule engine.

Koefisien mengikuti SNI 2835:2008 "Tata cara perhitungan harga satuan pekerjaan tanah untuk
konstruksi bangunan gedung dan perumahan"; harga dasar (upah & bahan) diambil dari daftar HSD
HSPK Kota Bandung 2027 supaya konsisten dengan analisa lain. Format sama dengan AHSP di
hspk_bandung_2027.py: kode -> (sheet, uraian, harga F, [(tipe, nama, satuan, koefisien, harga)]).
Koefisien dapat disesuaikan pengguna lewat menu Harga Satuan -> Analisa Pekerjaan.
"""

from database.hspk_bandung_2027 import HSD

BUK = 0.10
SHEET = "Pekerjaan Tanah (SNI 2835:2008)"
SHEET_PERSIAPAN = "Pekerjaan Persiapan (SNI 2835:2008)"


def _harga(tipe: str, nama: str, satuan: str) -> float:
    for t, n, s, h in HSD:
        if t == tipe and n == nama and s == satuan:
            return h
    raise KeyError(f"Harga dasar '{nama}' tidak ada di HSD")


def _analisa(uraian: str, komponen: list, sheet: str = SHEET) -> tuple:
    komp = [(t, n, s, k, _harga(t, n, s)) for t, n, s, k in komponen]
    return sheet, uraian, sum(k * h for *_, k, h in komp) * (1 + BUK), komp


AHSP_TAMBAHAN = {
    # SNI 2835:2008 butir 6.9
    "SNI-2835-6.9": _analisa("1 m3 urugan tanah kembali", [
        ("upah", "Pekerja", "OH", 0.192),
        ("upah", "Mandor", "OH", 0.019),
    ]),
    # SNI 2835:2008 butir 6.11
    "SNI-2835-6.11": _analisa("1 m3 urugan pasir", [
        ("upah", "Pekerja", "OH", 0.300),
        ("upah", "Mandor", "OH", 0.010),
        ("bahan", "Pasir urug (quarry - lokasi pekerjaan)", "m3", 1.200),
    ]),
    # Pekerjaan persiapan (tidak ada di workbook HSPK). Koefisien acuan analisa pekerjaan persiapan
    # SNI 2835:2008 / AHSP bidang Cipta Karya; dapat disesuaikan di Harga Satuan -> Analisa Pekerjaan.
    "SNI-2835-BERSIH": _analisa("Pembersihan 1 m2 lapangan dan perataan", [
        ("upah", "Pekerja", "OH", 0.100),
        ("upah", "Mandor", "OH", 0.050),
    ], SHEET_PERSIAPAN),
    "SNI-2835-BOWPLANK": _analisa("Pengukuran dan pemasangan 1 m' bouwplank", [
        ("bahan", "Kayu kaso 5/7 kelas III", "m3", 0.012),
        ("bahan", "Paku 5 dan 7 cm", "kg", 0.020),
        ("bahan", "Kayu papan kelas III", "m3", 0.007),
        ("upah", "Pekerja", "OH", 0.100),
        ("upah", "Tukang kayu", "OH", 0.100),
        ("upah", "Kepala tukang", "OH", 0.010),
        ("upah", "Mandor", "OH", 0.005),
    ], SHEET_PERSIAPAN),
}
