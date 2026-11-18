"""
Bahan habis pakai dan bahan yang dipakai berulang.

Analisa bekisting HSPK Kota Bandung 2027 (2.2.1.3.1 s.d. 2.2.1.3.7) berjudul "(3 kali pakai)". Koefisien kayu,
triplek / plywood, dan dolken (perancah) di analisa itu adalah kebutuhan satu set bekisting dibagi 3 pemakaian,
sedangkan paku dan minyak bekisting habis pada setiap pemakaian. Contoh bekisting kolom per m²:

    Plywood 12 mm   0,127 lembar   satu set ≈ 0,381 lembar/m² (1 lembar 122 × 244 cm + sisa potong), dibagi 3
    Kayu balok      0,00465 m³     dibagi 3
    Dolken          0,65 batang    dibagi 3
    Paku 12 cm      0,4 kg         habis setiap pemakaian
    Minyak          0,2 liter      habis setiap pemakaian

Jadi RAB dan Kebutuhan Bahan sudah memperhitungkan pemakaian berulang. Kebutuhan kayu/triplek/dolken adalah jumlah
yang dibeli, dengan anggapan bekisting dibongkar lalu dipasang lagi 3 kali (mis. lantai 1 → lantai 2 → lantai 3).
Bila tanpa pemakaian ulang, dibutuhkan 3 kali lipat.

Modul ini menandai komponen analisa yang dipakai berulang, agar Kebutuhan Bahan dan export dapat menampilkannya
terpisah dari bahan habis pakai (bahan yang tertanam di bangunan atau habis saat dipakai).

Aturan:
1. Jumlah pemakaian dibaca dari judul analisa HSPK pekerjaannya, mis. "(3 kali pakai)" atau "(10 - 12 kali pakai)"
   (diambil angka terkecil).
2. Pada pekerjaan dengan pemakaian ≥ 2, bahan bekisting/perancah (kayu, kaso, balok, papan, triplek, plywood,
   multiplek, dolken, bambu) dipakai berulang. Paku, minyak bekisting, formtie / spacer, kawat, dan lem habis pakai.
3. Komponen "Bekisting" di analisa lain (mis. sumur resapan HSPK 6.2.4.1) dianggap mengikuti analisa bekisting HSPK:
   3 kali pakai.
4. Kayu di kusen, rangka atap, plafon, lisplang, dan sejenisnya terpasang permanen: habis pakai.
"""

import re

PAKAI_HSPK = 3  # pemakaian bekisting pada analisa HSPK 2.2.1.3.x
_POLA_PAKAI = re.compile(r"(\d+)\s*(?:-\s*\d+\s*)?kali\s*pakai", re.IGNORECASE)
KATA_BERULANG = ("kayu", "kaso", "balok", "papan", "plywood", "triplek", "multiplek", "multiplex", "phenol",
                 "dolken", "bambu", "perancah", "scaffold")
_HABIS = re.compile(r"paku|minyak|formtie|spacer|penjaga jarak|kawat|\blem\b|sekrup|skrup|\bbaut\b")


def jumlah_pakai(teks: str | None) -> int:
    """'Pemasangan 1 m2 bekisting untuk kolom (3 kali pakai)' -> 3; '( 10 - 12 kali pakai )' -> 10; lainnya -> 0."""
    m = _POLA_PAKAI.search(teks or "")
    return int(m.group(1)) if m else 0


def pakai_komponen(nama_bahan: str, pakai_pekerjaan: int) -> int:
    """Berapa kali bahan ini dipakai pada pekerjaannya: n (≥ 2) bila dipakai berulang, 0 bila habis pakai."""
    n = " ".join(nama_bahan.lower().split())
    if _HABIS.search(n):
        return 0
    if n.startswith("bekisting"):  # komponen bekisting di analisa lain
        return max(pakai_pekerjaan, PAKAI_HSPK)
    if pakai_pekerjaan >= 2 and any(k in n for k in KATA_BERULANG):
        return pakai_pekerjaan
    return 0


def label_pakai(pakai: int) -> str:
    return f"dipakai {pakai}×" if pakai else "habis pakai"
