"""
Seed master pekerjaan + komponen_harga (AHSP).

SUMBER DATA
- HSPK Kota Bandung 2027 (bab 6.2 Sistem Air Limbah): tarif upah (Pekerja, Tukang batu, Kepala tukang,
  Mandor), harga Beton / Tulangan, dan 15 item pekerjaan air limbah lengkap dengan koefisiennya.
  Harga satuan HSPK = (jumlah A+B+C) + Biaya Umum & Keuntungan 10% -> lihat BUK_RATE di estimasi_repository.
- Item bertanda [PLACEHOLDER] / "proxy" TIDAK ada di dokumen HSPK tersebut (bata, semen, pasir, cat, genteng,
  tarif tukang besi/cat) dan koefisien pekerjaan struktural masih asumsi tipikal AHSP.
  Ganti setelah ada bab HSPK/AHSP pekerjaan beton, dinding, atap, dan finishing.
- Bekisting, batu kali, keramik, plafon: koefisien mengacu SNI 7394:2008 / SNI 2836:2008 / AHSP dan masih
  perlu diverifikasi. Kebutuhan keramik & genteng per m2 diturunkan dari rumus BAB II (rules/parameter.py).

Naikkan SEED_VERSI setiap kali isi SEED diubah; seed otomatis diperbarui saat aplikasi berjalan.
Komponen yang sudah diedit pengguna (diubah_manual = 1) tidak ditimpa.
"""

from database.estimasi_repository import _connect
from rules.parameter import PARAMETER_DEFAULT as _P

SEED_VERSI = "3-kf234-lingkup-rumah"

# --- Tarif upah HSPK Kota Bandung 2027 (Rp/OH) ---
UPAH = {
    "Pekerja": 206513.24,
    "Tukang batu": 217045.42,
    "Kepala tukang": 260413.20,
    "Mandor": 308530.78,
}
_PROXY = UPAH[
    "Tukang batu"
]  # tarif tukang besi/cat/atap tidak ada di dokumen -> pakai tarif tukang batu


def _upah(
    pekerja, tukang, kepala, mandor, nama_tukang="Tukang batu", harga_tukang=None
):
    return [
        ("upah", "Pekerja", "OH", pekerja, UPAH["Pekerja"]),
        ("upah", nama_tukang, "OH", tukang, harga_tukang or UPAH["Tukang batu"]),
        ("upah", "Kepala tukang", "OH", kepala, UPAH["Kepala tukang"]),
        ("upah", "Mandor", "OH", mandor, UPAH["Mandor"]),
    ]


# ============================================================
# A. Pekerjaan struktural (dipakai rule engine dari IFC)
# ============================================================
_CAT_STRUKTUR = (
    "Harga upah + Beton/Tulangan: HSPK Bandung 2027 (6.2.4.1). "
    "Koefisien: ASUMSI tipikal AHSP, belum diverifikasi."
)
_BETON = [("bahan", "Beton (HSPK 6.2.4.1)", "m3", 1.0, 1300000.00)] + _upah(
    1.65, 0.275, 0.028, 0.083
)
_BESI = [("bahan", "Tulangan (HSPK 6.2.4.1)", "kg", 1.05, 35000.00)] + _upah(
    0.007, 0.007, 0.0007, 0.0004, "Tukang besi (proxy tarif Tukang batu)", _PROXY
)

_KOEF_SNI = "Koefisien: acuan SNI 7394:2008 / AHSP, perlu diverifikasi. Bahan [PLACEHOLDER]."
_TUKANG_KAYU = "Tukang kayu (proxy tarif Tukang batu)"


def _bekisting(kayu, paku, minyak, balok_kayu, plywood, dolken, upah):
    bahan = [
        ("bahan", "Kayu kelas III [PLACEHOLDER]", "m3", kayu, 3000000),
        ("bahan", "Paku 5-12 cm [PLACEHOLDER]", "kg", paku, 20000),
        ("bahan", "Minyak bekisting [PLACEHOLDER]", "liter", minyak, 25000),
    ]
    if balok_kayu:
        bahan.append(("bahan", "Balok kayu kelas II [PLACEHOLDER]", "m3", balok_kayu, 5000000))
    if plywood:
        bahan.append(("bahan", "Plywood 9 mm [PLACEHOLDER]", "lembar", plywood, 150000))
    if dolken:
        bahan.append(("bahan", "Dolken kayu galam 8-10/400 [PLACEHOLDER]", "batang", dolken, 25000))
    return bahan + _upah(*upah, _TUKANG_KAYU, _PROXY)


_BSK_KOLOM = _bekisting(0.040, 0.40, 0.20, 0.015, 0.35, 2.0, (0.66, 0.33, 0.033, 0.033))
_BSK_BALOK = _bekisting(0.040, 0.40, 0.20, 0.018, 0.35, 2.0, (0.66, 0.33, 0.033, 0.033))
_BSK_PELAT = _bekisting(0.040, 0.40, 0.20, 0.015, 0.35, 6.0, (0.66, 0.33, 0.033, 0.033))
_BSK_FONDASI = _bekisting(0.040, 0.30, 0.10, 0, 0, 0, (0.52, 0.26, 0.026, 0.026))

_KOEF_KRM_LANTAI = round(_P.kebutuhan_per_m2(_P.keramik_lantai, _P.sisa_keramik_lantai), 4)
_KOEF_KRM_DINDING = round(_P.kebutuhan_per_m2(_P.keramik_dinding, _P.sisa_keramik_dinding), 4)
_KOEF_GENTENG = round(_P.kebutuhan_per_m2(_P.genteng_efektif, _P.sisa_genteng), 4)

SEED = {
    # ---------------- Fondasi ----------------
    "FDN.BATUKALI": (
        "Pasangan Fondasi Batu Kali 1PC : 4PP",
        "Fondasi",
        "m3",
        "Koefisien: SNI 2836:2008 (batu kali 1:4). Upah HSPK. Bahan [PLACEHOLDER].",
        [
            ("bahan", "Batu belah [PLACEHOLDER]", "m3", 1.20, 280000),
            ("bahan", "Semen PC [PLACEHOLDER]", "kg", 163, 1500),
            ("bahan", "Pasir pasang [PLACEHOLDER]", "m3", 0.52, 300000),
        ]
        + _upah(1.50, 0.75, 0.075, 0.075),
    ),
    "BTN.SUMURAN": ("Beton Fondasi Sumuran + Poer", "Fondasi", "m3", _CAT_STRUKTUR, _BETON),
    "BSI.SUMURAN": ("Pembesian Fondasi Sumuran", "Fondasi", "kg", _CAT_STRUKTUR, _BESI),
    "BTN.FONDASI": ("Beton Fondasi Telapak (Footplate)", "Fondasi", "m3", _CAT_STRUKTUR, _BETON),
    "BSI.FONDASI": ("Pembesian Fondasi Telapak", "Fondasi", "kg", _CAT_STRUKTUR, _BESI),
    "BSK.FONDASI": ("Bekisting Fondasi Telapak", "Fondasi", "m2", _KOEF_SNI, _BSK_FONDASI),
    "BTN.SLOOF": ("Beton Sloof", "Fondasi", "m3", _CAT_STRUKTUR, _BETON),
    "BSI.SLOOF": ("Pembesian Sloof", "Fondasi", "kg", _CAT_STRUKTUR, _BESI),
    "BSK.SLOOF": ("Bekisting Sloof", "Fondasi", "m2", _KOEF_SNI, _BSK_FONDASI),
    # ---------------- Struktur beton ----------------
    "BTN.KOLOM": ("Beton Kolom", "Beton", "m3", _CAT_STRUKTUR, _BETON),
    "BTN.BALOK": ("Beton Balok", "Beton", "m3", _CAT_STRUKTUR, _BETON),
    "BTN.PELAT": ("Beton Pelat Lantai", "Beton", "m3", _CAT_STRUKTUR, _BETON),
    "BTN.DAK": ("Beton Pelat Atap (Dak)", "Beton", "m3", _CAT_STRUKTUR, _BETON),
    "BSI.KOLOM": ("Pembesian Kolom", "Beton", "kg", _CAT_STRUKTUR, _BESI),
    "BSI.BALOK": ("Pembesian Balok", "Beton", "kg", _CAT_STRUKTUR, _BESI),
    "BSI.PELAT": ("Pembesian Pelat Lantai", "Beton", "kg", _CAT_STRUKTUR, _BESI),
    "BSI.DAK": ("Pembesian Pelat Atap (Dak)", "Beton", "kg", _CAT_STRUKTUR, _BESI),
    "BSK.KOLOM": ("Bekisting Kolom", "Beton", "m2", _KOEF_SNI, _BSK_KOLOM),
    "BSK.BALOK": ("Bekisting Balok", "Beton", "m2", _KOEF_SNI, _BSK_BALOK),
    "BSK.PELAT": ("Bekisting Pelat Lantai", "Beton", "m2", _KOEF_SNI, _BSK_PELAT),
    "BSK.DAK": ("Bekisting Pelat Atap (Dak)", "Beton", "m2", _KOEF_SNI, _BSK_PELAT),
    # ---------------- Dinding ----------------
    "DND.BATA": (
        "Pasangan Dinding Bata Merah 1/2 Bata",
        "Dinding",
        "m2",
        "Upah: HSPK. Bahan [PLACEHOLDER], koefisien asumsi.",
        [
            ("bahan", "Bata merah [PLACEHOLDER]", "buah", 70, 900),
            ("bahan", "Semen PC [PLACEHOLDER]", "kg", 11.5, 1500),
            ("bahan", "Pasir pasang [PLACEHOLDER]", "m3", 0.043, 300000),
        ]
        + _upah(0.3, 0.1, 0.01, 0.015),
    ),
    "PLS.DINDING": (
        "Plesteran + Acian Dinding",
        "Dinding",
        "m2",
        "Upah: HSPK. Bahan [PLACEHOLDER], koefisien asumsi.",
        [
            ("bahan", "Semen PC [PLACEHOLDER]", "kg", 6.24, 1500),
            ("bahan", "Pasir pasang [PLACEHOLDER]", "m3", 0.024, 300000),
        ]
        + _upah(0.3, 0.15, 0.015, 0.015),
    ),
    "KRM.DINDING": (
        "Pasangan Keramik Dinding 20x25 (Ruang Basah)",
        "Dinding",
        "m2",
        f"Kebutuhan keramik = 1/(0,20 x 0,25) x 1,10 = {_KOEF_KRM_DINDING} buah/m2 (Rumus 2.15). "
        "Koefisien lain acuan AHSP, perlu diverifikasi. Bahan [PLACEHOLDER].",
        [
            ("bahan", "Keramik dinding 20x25 [PLACEHOLDER]", "buah", _KOEF_KRM_DINDING, 3500),
            ("bahan", "Semen PC [PLACEHOLDER]", "kg", 9.3, 1500),
            ("bahan", "Pasir pasang [PLACEHOLDER]", "m3", 0.018, 300000),
            ("bahan", "Semen warna [PLACEHOLDER]", "kg", 1.94, 3000),
        ]
        + _upah(0.9, 0.45, 0.045, 0.045),
    ),
    # ---------------- Lantai ----------------
    "KRM.LANTAI": (
        "Pasangan Keramik Lantai 40x40",
        "Lantai",
        "m2",
        f"Kebutuhan keramik = 1/(0,40 x 0,40) x 1,05 = {_KOEF_KRM_LANTAI} buah/m2 (Rumus 2.13). "
        "Koefisien lain acuan AHSP, perlu diverifikasi. Bahan [PLACEHOLDER].",
        [
            ("bahan", "Keramik lantai 40x40 [PLACEHOLDER]", "buah", _KOEF_KRM_LANTAI, 12000),
            ("bahan", "Semen PC [PLACEHOLDER]", "kg", 10, 1500),
            ("bahan", "Pasir pasang [PLACEHOLDER]", "m3", 0.045, 300000),
            ("bahan", "Semen warna [PLACEHOLDER]", "kg", 1.62, 3000),
        ]
        + _upah(0.62, 0.31, 0.031, 0.031),
    ),
    # ---------------- Pintu & jendela ----------------
    "PTU.PINTU": (
        "Pintu Lengkap (Kusen + Daun + Kunci & Engsel)",
        "Pintu & Jendela",
        "unit",
        "Harga borongan per unit [PLACEHOLDER], koefisien upah asumsi.",
        [("bahan", "Pintu panel + kusen + kunci & engsel [PLACEHOLDER]", "unit", 1.0, 2500000)]
        + _upah(0.5, 1.0, 0.1, 0.025, _TUKANG_KAYU, _PROXY),
    ),
    "JDL.JENDELA": (
        "Jendela Lengkap (Kusen + Kaca)",
        "Pintu & Jendela",
        "m2",
        "Harga per m2 bukaan [PLACEHOLDER], koefisien upah asumsi.",
        [("bahan", "Jendela kusen aluminium + kaca 5 mm [PLACEHOLDER]", "m2", 1.0, 750000)]
        + _upah(0.2, 0.4, 0.04, 0.01, "Tukang (proxy tarif Tukang batu)", _PROXY),
    ),
    # ---------------- Atap ----------------
    "ATP.RANGKA": (
        "Rangka Atap Baja Ringan",
        "Atap",
        "m2",
        "Dihitung per m2 luas atap miring. Harga rangka terpasang [PLACEHOLDER].",
        [("bahan", "Rangka baja ringan kanal C + reng + sekrup [PLACEHOLDER]", "m2", 1.0, 120000)]
        + _upah(0.10, 0.10, 0.01, 0.005, "Tukang (proxy tarif Tukang batu)", _PROXY),
    ),
    "ATP.PENUTUP": (
        "Penutup Atap Genteng",
        "Atap",
        "m2",
        f"Kebutuhan genteng = 1/(0,30 x 0,33) x 1,05 = {_KOEF_GENTENG} buah/m2 (Rumus 2.42). "
        "Upah: HSPK (tarif tukang = proxy). Bahan [PLACEHOLDER].",
        [("bahan", "Genteng beton [PLACEHOLDER]", "buah", _KOEF_GENTENG, 9000)]
        + _upah(0.05, 0.1, 0.01, 0.005, "Tukang (proxy tarif Tukang batu)", _PROXY),
    ),
    # ---------------- Plafon ----------------
    "PLF.GYPSUM": (
        "Plafon Gypsum 9 mm Rangka Hollow",
        "Plafon",
        "m2",
        "Gypsum 1,2 x 2,4 m: 1/2,88 x 1,05 = 0,3646 lembar/m2. Bahan [PLACEHOLDER], upah asumsi.",
        [
            ("bahan", "Gypsum board 9 mm 1,2 x 2,4 m [PLACEHOLDER]", "lembar", 0.3646, 75000),
            ("bahan", "Rangka hollow galvalum + aksesoris [PLACEHOLDER]", "m2", 1.0, 55000),
        ]
        + _upah(0.10, 0.10, 0.01, 0.005, "Tukang (proxy tarif Tukang batu)", _PROXY),
    ),
    # ---------------- Cat ----------------
    "CAT.DINDING": (
        "Cat Dasar Dinding",
        "Cat",
        "m2",
        "Upah: HSPK (tarif tukang = proxy). Bahan [PLACEHOLDER].",
        [
            ("bahan", "Cat dasar [PLACEHOLDER]", "kg", 0.1, 45000),
            ("upah", "Tukang cat (proxy tarif Tukang batu)", "OH", 0.02, _PROXY),
            ("upah", "Pekerja", "OH", 0.01, UPAH["Pekerja"]),
            ("upah", "Kepala tukang", "OH", 0.002, UPAH["Kepala tukang"]),
            ("upah", "Mandor", "OH", 0.001, UPAH["Mandor"]),
        ],
    ),
}

# ============================================================
# B. HSPK Kota Bandung 2027 - 6.2 Sistem Air Limbah (data asli dokumen)
#    kode -> (uraian, satuan, (koef Pekerja, T.batu, K.tukang, Mandor), [bahan], harga satuan HSPK)
# ============================================================
HSPK_AIR_LIMBAH = {
    "HSPK-6.2.1.1": (
        "Pemasangan 1 set STP fiberglass kap. 2 m3",
        "set",
        (1.324, 2.211, 0.221, 0.066),
        [("STP fiberglass kap. 2 m3", "unit", 1.500, 17387500.00)],
        29603722.83,
    ),
    "HSPK-6.2.1.2": (
        "Pemasangan 1 set STP fiberglass kap. 5 m3",
        "set",
        (3.304, 5.518, 0.552, 0.166),
        [("STP fiberglass kap. 5 m3", "unit", 1.500, 34882000.00)],
        59837734.63,
    ),
    "HSPK-6.2.1.3": (
        "Pemasangan 1 set STP fiberglass kap. 10 m3",
        "set",
        (6.667, 11.133, 1.113, 0.334),
        [("STP fiberglass kap. 10 m3", "unit", 1.500, 56817000.00)],
        98352737.56,
    ),
    "HSPK-6.2.1.4": (
        "Pemasangan 1 set STP fiberglass kap. 30 m3",
        "set",
        (19.896, 33.226, 3.323, 0.997),
        [("STP fiberglass kap. 30 m3", "unit", 1.500, 158000000.00)],
        274442626.48,
    ),
    "HSPK-6.2.1.5": (
        "Pemasangan 1 set STP precast kap. 30 m3",
        "set",
        (28.646, 47.839, 4.784, 1.435),
        [("STP precast kap. 30 m3", "unit", 1.100, 176091000.00)],
        232856439.79,
    ),
    "HSPK-6.2.1.6": (
        "Pemasangan 1 set STP fiberglass kap. 1 m3",
        "set",
        (0.662, 1.105, 0.111, 0.033),
        [("STP fiberglass kap. 1 m3", "unit", 1.500, 158000000.00)],
        261157197.77,
    ),
    "HSPK-6.2.1.7": (
        "Pemasangan 1 set BioFilter Anaerobic Aerobic Clarifier Packed kap. 50 m3",
        "set",
        (19.895, 33.225, 3.323, 1.108),
        [
            (
                "BioFilter Anaerobic Aerobic Clarifier Packed kap. 50 m3",
                "unit",
                1.050,
                555000000.00,
            )
        ],
        654804832.17,
    ),
    "HSPK-6.2.2.1": (
        "Pemasangan 1 unit pompa sump pit air kotor 100 m3/jam, submersible cutter pump",
        "unit",
        (0.442, 0.738, 0.074, 0.022),
        [("Submersible cutter pump kap. 100 lpm", "unit", 1.025, 8906913.00)],
        10347812.70,
    ),
    "HSPK-6.2.2.2": (
        "Pemasangan 1 unit Pompa Submersible Cutter Pump kap. 75 LPM",
        "unit",
        (0.44, 0.736, 0.074, 0.025),
        [("Pompa Submersible Cutter Pump kap. 75 LPM", "unit", 1.025, 4915068.00)],
        5847093.78,
    ),
    "HSPK-6.2.2.3": (
        "Pemasangan 1 unit Pompa Submersible Cutter Pump kap. 100 LPM",
        "unit",
        (0.445, 0.744, 0.074, 0.025),
        [("Pompa Submersible Cutter Pump kap. 100 LPM", "unit", 1.025, 7479300.00)],
        8741311.18,
    ),
    "HSPK-6.2.3.1": (
        "Pemasangan 1 unit grease trap portable fiberglass, kap. 30 Liter",
        "unit",
        (0.250, 0.418, 0.042, 0.013),
        [("Grease trap portable fiberglass kap. 30 Liter", "unit", 1.025, 1161875.00)],
        1483045.77,
    ),
    "HSPK-6.2.3.2": (
        "Pemasangan 1 unit grease trap portable stainless, kap. 30 Liter",
        "unit",
        (0.250, 0.418, 0.042, 0.013),
        [("Grease trap portable stainless kap. 30 Liter", "unit", 1.025, 880000.00)],
        1165231.71,
    ),
    "HSPK-6.2.3.3": (
        "Pemasangan 1 unit grease trap central fiberglass, kap. 5 m3",
        "unit",
        (1.042, 1.740, 0.174, 0.052),
        [("Grease trap central fiberglass kap. 5 m3", "unit", 1.025, 19754000.00)],
        22992256.46,
    ),
    "HSPK-6.2.4.1": (
        "Pemasangan 1 buah Sumur Resapan Air Limbah dia. 80 cm, t=100 cm (dengan tutup beton)",
        "buah",
        (0.121, 0.203, 0.02, 0.006),
        [
            ("Galian tanah biasa", "m3", 1.327, 180000.00),
            ("Urukan tanah", "m3", 0.130, 220335.00),
            ("Buis beton dia. 80 cm", "buah", 1.000, 272900.00),
            ("Tali ijuk", "kg", 4.5, 72150.00),
            ("Kerikil", "m3", 0.502, 427350.00),
            ("Tutup beton bertulang - Beton", "m3", 0.05, 1300000.00),
            ("Tutup beton bertulang - Tulangan", "kg", 5.024, 35000.00),
            ("Tutup beton bertulang - Bekisting", "m2", 0.502, 3052500.00),
            ("Pipa PVC 4 inci", "m'", 1.2, 87500.00),
        ],
        3337302.12,
    ),
    "HSPK-6.2.4.2": (
        "Pemasangan 1 buah Sumur Resapan Air Limbah dia. 80 cm, t=100 cm (tanpa tutup beton)",
        "buah",
        (0.121, 0.203, 0.02, 0.006),
        [
            ("Galian tanah biasa", "m3", 1.327, 180000.00),
            ("Urukan tanah", "m2", 0.025, 220335.00),
            ("Buis beton dia. 80 cm", "buah", 1.000, 272900.00),
            ("Tali ijuk", "kg", 4.5, 72150.00),
            ("Kerikil", "m3", 0.502, 427350.00),
            ("Pipa PVC 4 inci", "m'", 1.2, 87500.00),
        ],
        1361338.93,
    ),
}

for _kode, (_uraian, _sat, _lab, _bahan, _f) in HSPK_AIR_LIMBAH.items():
    SEED[_kode] = (
        _uraian,
        "Air Limbah",
        _sat,
        "HSPK Kota Bandung 2027, "
        + _kode.replace("HSPK-", "bab ")
        + ". Data asli dokumen.",
        _upah(*_lab) + [("bahan", n, s, k, h) for n, s, k, h in _bahan],
    )

HARGA_HSPK_REFERENSI = {k: v[4] for k, v in HSPK_AIR_LIMBAH.items()}  # untuk verifikasi


def seed_pekerjaan():
    """Idempotent. Hanya bekerja bila SEED_VERSI di database berbeda."""
    conn = _connect()
    try:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS preferensi_pengguna (kunci TEXT PRIMARY KEY, nilai TEXT)"
        )
        row = conn.execute(
            "SELECT nilai FROM preferensi_pengguna WHERE kunci = 'seed_versi'"
        ).fetchone()
        if row and row["nilai"] == SEED_VERSI:
            return

        for kode, (nama, kategori, satuan, catatan, komponen) in SEED.items():
            ada = conn.execute(
                "SELECT id FROM pekerjaan WHERE kode_ahsp = ?", (kode,)
            ).fetchone()
            if ada:
                pid = ada["id"]
                conn.execute(
                    "UPDATE pekerjaan SET nama_pekerjaan=?, kategori=?, satuan=?, catatan=? WHERE id=?",
                    (nama, kategori, satuan, catatan, pid),
                )
                if conn.execute(
                    "SELECT 1 FROM komponen_harga WHERE pekerjaan_id=? AND diubah_manual=1 LIMIT 1",
                    (pid,),
                ).fetchone():
                    continue  # jangan timpa edit pengguna (KF-5)
                conn.execute(
                    "DELETE FROM komponen_harga WHERE pekerjaan_id = ?", (pid,)
                )
            else:
                pid = conn.execute(
                    "INSERT INTO pekerjaan (kode_ahsp, nama_pekerjaan, kategori, satuan, catatan) VALUES (?,?,?,?,?)",
                    (kode, nama, kategori, satuan, catatan),
                ).lastrowid
            for tipe, nm, sk, koef, harga in komponen:
                conn.execute(
                    "INSERT INTO komponen_harga (pekerjaan_id, tipe, nama_komponen, satuan, koefisien, harga_satuan) "
                    "VALUES (?,?,?,?,?,?)",
                    (pid, tipe, nm, sk, koef, harga),
                )

        conn.execute(
            "INSERT OR REPLACE INTO preferensi_pengguna (kunci, nilai) VALUES ('seed_versi', ?)",
            (SEED_VERSI,),
        )
        conn.commit()
    finally:
        conn.close()
