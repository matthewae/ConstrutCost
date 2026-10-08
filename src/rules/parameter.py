"""
Parameter asumsi teknis yang dipakai rule engine (KF-3/KF-4).

Semua angka di sini adalah ASUMSI tipikal rumah tinggal <= 2 lantai pada kondisi tanah normal
(Batasan Masalah no. 6-8). Angka dikumpulkan di satu tempat supaya mudah diverifikasi,
dikutip di laporan, dan nantinya diubah lewat menu pengaturan.
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ParameterEstimasi:
    # --- Rasio pembesian (kg besi per m3 beton), asumsi tipikal rumah tinggal ---
    rasio_besi_kolom: float = 150.0
    rasio_besi_balok: float = 130.0
    rasio_besi_sloof: float = 120.0
    rasio_besi_pelat: float = 90.0
    rasio_besi_fondasi: float = 80.0

    # --- Fondasi batu kali di bawah dinding lantai dasar (Rumus 2.34) ---
    batu_kali_lebar_atas: float = 0.30  # m
    batu_kali_lebar_bawah: float = 0.70  # m
    batu_kali_tinggi: float = 0.80  # m

    # --- Fondasi sumuran di bawah kolom lantai dasar (Rumus 2.36 - 2.39) ---
    sumuran_diameter: float = 1.00  # m, sama dengan item HSPK 2.2.2.2.6 (sumuran diameter 100 cm masif)
    sumuran_kedalaman: float = 2.00  # m
    sumuran_jumlah_tiang: int = 1  # tiang per titik kolom
    poer_panjang: float = 0.80  # m, pelat penutup (pile cap) di atas sumuran
    poer_lebar: float = 0.80  # m
    poer_tebal: float = 0.25  # m

    # --- Pekerjaan tanah (KF-4): galian, urugan pasir, lantai kerja, urugan kembali ---
    ruang_kerja_galian: float = 0.10  # m, kelonggaran galian tiap sisi fondasi
    tebal_pasir_fondasi: float = 0.05  # m, urugan pasir bawah fondasi batu kali
    tebal_pasir_sloof: float = 0.05  # m, urugan pasir bawah sloof
    tebal_pasir_lantai: float = 0.05  # m, urugan pasir bawah lantai dasar
    tebal_lantai_kerja: float = 0.05  # m, lantai kerja f'c 7,5 MPa bawah footplate / rabat lantai
    kedalaman_fondasi_telapak: float = 1.00  # m, muka tanah ke dasar footplate (tanpa lantai kerja)

    # --- Dinding ---
    jumlah_sisi_plester: int = 2  # plester dan acian dua sisi
    jumlah_sisi_cat: int = 2  # cat dasar dua sisi (Rumus 2.17 - 2.19)

    # --- Atap ---
    # Pelat atap dengan kemiringan di bawah batas ini dianggap dak beton datar,
    # di atasnya dianggap atap miring berangka baja ringan + genteng.
    batas_kemiringan_dak: float = 5.0  # derajat

    # --- Pintu ---
    jumlah_engsel_pintu: int = 3  # per daun pintu

    # --- Ukuran material untuk Rumus 2.13, 2.15, 2.42 (informasi kebutuhan buah per m2;
    #     harga memakai koefisien HSPK) ---
    keramik_lantai: tuple = (0.40, 0.40)  # m
    sisa_keramik_lantai: float = 0.05  # +5% patahan & sisa
    keramik_dinding: tuple = (0.20, 0.20)  # m, sama dengan item HSPK 3.10.1.4
    sisa_keramik_dinding: float = 0.10  # +10%
    genteng_efektif: tuple = (0.30, 0.33)  # m, ukuran efektif (setelah overlap)
    sisa_genteng: float = 0.05

    # --- Keramik dinding pada ruang basah (Rumus 2.14) ---
    # kata kunci nama ruang (huruf kecil) -> tinggi pasangan keramik (m)
    tinggi_keramik_dinding: dict = field(
        default_factory=lambda: {
            "kamar mandi": 1.50,
            "km": 1.50,
            "wc": 1.50,
            "toilet": 1.50,
            "bathroom": 1.50,
            "bath": 1.50,
            "dapur": 0.60,
            "pantry": 0.60,
            "kitchen": 0.60,
        }
    )

    def kebutuhan_per_m2(self, ukuran: tuple, sisa: float) -> float:
        """Jumlah buah per m2 = 1 / (p x l) x (1 + sisa)."""
        p, l = ukuran
        return (1.0 / (p * l)) * (1.0 + sisa)


PARAMETER_DEFAULT = ParameterEstimasi()
