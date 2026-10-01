"""
Seed master pekerjaan + komponen_harga (AHSP).

SUMBER DATA
- HSPK Kota Bandung 2027 (bab 6.2 Sistem Air Limbah): tarif upah (Pekerja, Tukang batu, Kepala tukang,
  Mandor), harga Beton / Tulangan, dan 15 item pekerjaan air limbah lengkap dengan koefisiennya.
  Harga satuan HSPK = (jumlah A+B+C) + Biaya Umum & Keuntungan 10% -> lihat BUK_RATE di estimasi_repository.
- Item bertanda [PLACEHOLDER] / "proxy" TIDAK ada di dokumen HSPK tersebut (bata, semen, pasir, cat, genteng,
  tarif tukang besi/cat) dan koefisien pekerjaan struktural masih asumsi tipikal AHSP.
  Ganti setelah ada bab HSPK/AHSP pekerjaan beton, dinding, atap, dan finishing.

Naikkan SEED_VERSI setiap kali isi SEED diubah; seed otomatis diperbarui saat aplikasi berjalan.
Komponen yang sudah diedit pengguna (diubah_manual = 1) tidak ditimpa.
"""

from database.estimasi_repository import _connect

SEED_VERSI = "2-hspk-bdg-2027"

# --- Tarif upah HSPK Kota Bandung 2027 (Rp/OH) ---
UPAH = {
    "Pekerja": 206513.24,
    "Tukang batu": 217045.42,
    "Kepala tukang": 260413.20,
    "Mandor": 308530.78,
}
_PROXY = UPAH["Tukang batu"]  # tarif tukang besi/cat/atap tidak ada di dokumen -> pakai tarif tukang batu


def _upah(pekerja, tukang, kepala, mandor, nama_tukang="Tukang batu", harga_tukang=None):
    return [
        ("upah", "Pekerja", "OH", pekerja, UPAH["Pekerja"]),
        ("upah", nama_tukang, "OH", tukang, harga_tukang or UPAH["Tukang batu"]),
        ("upah", "Kepala tukang", "OH", kepala, UPAH["Kepala tukang"]),
        ("upah", "Mandor", "OH", mandor, UPAH["Mandor"]),
    ]


# ============================================================
# A. Pekerjaan struktural (dipakai rule engine dari IFC)
# ============================================================
_CAT_STRUKTUR = ("Harga upah + Beton/Tulangan: HSPK Bandung 2027 (6.2.4.1). "
                 "Koefisien: ASUMSI tipikal AHSP, belum diverifikasi.")
_BETON = [("bahan", "Beton (HSPK 6.2.4.1)", "m3", 1.0, 1300000.00)] + _upah(1.65, 0.275, 0.028, 0.083)
_BESI = ([("bahan", "Tulangan (HSPK 6.2.4.1)", "kg", 1.05, 35000.00)]
         + _upah(0.007, 0.007, 0.0007, 0.0004, "Tukang besi (proxy tarif Tukang batu)", _PROXY))

SEED = {
    "BTN.KOLOM":   ("Beton Kolom", "Beton", "m3", _CAT_STRUKTUR, _BETON),
    "BTN.BALOK":   ("Beton Balok", "Beton", "m3", _CAT_STRUKTUR, _BETON),
    "BTN.PELAT":   ("Beton Pelat Lantai", "Beton", "m3", _CAT_STRUKTUR, _BETON),
    "BTN.FONDASI": ("Beton Fondasi", "Fondasi", "m3", _CAT_STRUKTUR, _BETON),
    "BSI.KOLOM":   ("Pembesian Kolom", "Beton", "kg", _CAT_STRUKTUR, _BESI),
    "BSI.BALOK":   ("Pembesian Balok", "Beton", "kg", _CAT_STRUKTUR, _BESI),
    "BSI.PELAT":   ("Pembesian Pelat", "Beton", "kg", _CAT_STRUKTUR, _BESI),
    "BSI.FONDASI": ("Pembesian Fondasi", "Fondasi", "kg", _CAT_STRUKTUR, _BESI),
    "DND.BATA": ("Pasangan Dinding Bata Merah 1/2 Bata", "Dinding", "m2",
                 "Upah: HSPK. Bahan [PLACEHOLDER], koefisien asumsi.", [
        ("bahan", "Bata merah [PLACEHOLDER]", "buah", 70, 900),
        ("bahan", "Semen PC [PLACEHOLDER]", "kg", 11.5, 1500),
        ("bahan", "Pasir pasang [PLACEHOLDER]", "m3", 0.043, 300000)] + _upah(0.3, 0.1, 0.01, 0.015)),
    "PLS.DINDING": ("Plesteran + Acian Dinding", "Dinding", "m2",
                    "Upah: HSPK. Bahan [PLACEHOLDER], koefisien asumsi.", [
        ("bahan", "Semen PC [PLACEHOLDER]", "kg", 6.24, 1500),
        ("bahan", "Pasir pasang [PLACEHOLDER]", "m3", 0.024, 300000)] + _upah(0.3, 0.15, 0.015, 0.015)),
    "CAT.DINDING": ("Cat Dasar Dinding", "Cat", "m2",
                    "Upah: HSPK (tarif tukang = proxy). Bahan [PLACEHOLDER].", [
        ("bahan", "Cat dasar [PLACEHOLDER]", "kg", 0.1, 45000),
        ("upah", "Tukang cat (proxy tarif Tukang batu)", "OH", 0.02, _PROXY),
        ("upah", "Pekerja", "OH", 0.01, UPAH["Pekerja"]),
        ("upah", "Kepala tukang", "OH", 0.002, UPAH["Kepala tukang"]),
        ("upah", "Mandor", "OH", 0.001, UPAH["Mandor"])]),
    "ATP.PENUTUP": ("Penutup Atap", "Atap", "m2",
                    "Upah: HSPK (tarif tukang = proxy). Bahan [PLACEHOLDER].", [
        ("bahan", "Penutup atap [PLACEHOLDER]", "m2", 1.05, 90000)]
        + _upah(0.05, 0.1, 0.01, 0.005, "Tukang (proxy tarif Tukang batu)", _PROXY)),
}

# ============================================================
# B. HSPK Kota Bandung 2027 - 6.2 Sistem Air Limbah (data asli dokumen)
#    kode -> (uraian, satuan, (koef Pekerja, T.batu, K.tukang, Mandor), [bahan], harga satuan HSPK)
# ============================================================
HSPK_AIR_LIMBAH = {
    "HSPK-6.2.1.1": ("Pemasangan 1 set STP fiberglass kap. 2 m3", "set", (1.324, 2.211, 0.221, 0.066),
                     [("STP fiberglass kap. 2 m3", "unit", 1.500, 17387500.00)], 29603722.83),
    "HSPK-6.2.1.2": ("Pemasangan 1 set STP fiberglass kap. 5 m3", "set", (3.304, 5.518, 0.552, 0.166),
                     [("STP fiberglass kap. 5 m3", "unit", 1.500, 34882000.00)], 59837734.63),
    "HSPK-6.2.1.3": ("Pemasangan 1 set STP fiberglass kap. 10 m3", "set", (6.667, 11.133, 1.113, 0.334),
                     [("STP fiberglass kap. 10 m3", "unit", 1.500, 56817000.00)], 98352737.56),
    "HSPK-6.2.1.4": ("Pemasangan 1 set STP fiberglass kap. 30 m3", "set", (19.896, 33.226, 3.323, 0.997),
                     [("STP fiberglass kap. 30 m3", "unit", 1.500, 158000000.00)], 274442626.48),
    "HSPK-6.2.1.5": ("Pemasangan 1 set STP precast kap. 30 m3", "set", (28.646, 47.839, 4.784, 1.435),
                     [("STP precast kap. 30 m3", "unit", 1.100, 176091000.00)], 232856439.79),
    "HSPK-6.2.1.6": ("Pemasangan 1 set STP fiberglass kap. 1 m3", "set", (0.662, 1.105, 0.111, 0.033),
                     [("STP fiberglass kap. 1 m3", "unit", 1.500, 158000000.00)], 261157197.77),
    "HSPK-6.2.1.7": ("Pemasangan 1 set BioFilter Anaerobic Aerobic Clarifier Packed kap. 50 m3", "set",
                     (19.895, 33.225, 3.323, 1.108),
                     [("BioFilter Anaerobic Aerobic Clarifier Packed kap. 50 m3", "unit", 1.050, 555000000.00)],
                     654804832.17),
    "HSPK-6.2.2.1": ("Pemasangan 1 unit pompa sump pit air kotor 100 m3/jam, submersible cutter pump", "unit",
                     (0.442, 0.738, 0.074, 0.022),
                     [("Submersible cutter pump kap. 100 lpm", "unit", 1.025, 8906913.00)], 10347812.70),
    "HSPK-6.2.2.2": ("Pemasangan 1 unit Pompa Submersible Cutter Pump kap. 75 LPM", "unit",
                     (0.44, 0.736, 0.074, 0.025),
                     [("Pompa Submersible Cutter Pump kap. 75 LPM", "unit", 1.025, 4915068.00)], 5847093.78),
    "HSPK-6.2.2.3": ("Pemasangan 1 unit Pompa Submersible Cutter Pump kap. 100 LPM", "unit",
                     (0.445, 0.744, 0.074, 0.025),
                     [("Pompa Submersible Cutter Pump kap. 100 LPM", "unit", 1.025, 7479300.00)], 8741311.18),
    "HSPK-6.2.3.1": ("Pemasangan 1 unit grease trap portable fiberglass, kap. 30 Liter", "unit",
                     (0.250, 0.418, 0.042, 0.013),
                     [("Grease trap portable fiberglass kap. 30 Liter", "unit", 1.025, 1161875.00)], 1483045.77),
    "HSPK-6.2.3.2": ("Pemasangan 1 unit grease trap portable stainless, kap. 30 Liter", "unit",
                     (0.250, 0.418, 0.042, 0.013),
                     [("Grease trap portable stainless kap. 30 Liter", "unit", 1.025, 880000.00)], 1165231.71),
    "HSPK-6.2.3.3": ("Pemasangan 1 unit grease trap central fiberglass, kap. 5 m3", "unit",
                     (1.042, 1.740, 0.174, 0.052),
                     [("Grease trap central fiberglass kap. 5 m3", "unit", 1.025, 19754000.00)], 22992256.46),
    "HSPK-6.2.4.1": ("Pemasangan 1 buah Sumur Resapan Air Limbah dia. 80 cm, t=100 cm (dengan tutup beton)", "buah",
                     (0.121, 0.203, 0.02, 0.006),
                     [("Galian tanah biasa", "m3", 1.327, 180000.00),
                      ("Urukan tanah", "m3", 0.130, 220335.00),
                      ("Buis beton dia. 80 cm", "buah", 1.000, 272900.00),
                      ("Tali ijuk", "kg", 4.5, 72150.00),
                      ("Kerikil", "m3", 0.502, 427350.00),
                      ("Tutup beton bertulang - Beton", "m3", 0.05, 1300000.00),
                      ("Tutup beton bertulang - Tulangan", "kg", 5.024, 35000.00),
                      ("Tutup beton bertulang - Bekisting", "m2", 0.502, 3052500.00),
                      ("Pipa PVC 4 inci", "m'", 1.2, 87500.00)], 3337302.12),
    "HSPK-6.2.4.2": ("Pemasangan 1 buah Sumur Resapan Air Limbah dia. 80 cm, t=100 cm (tanpa tutup beton)", "buah",
                     (0.121, 0.203, 0.02, 0.006),
                     [("Galian tanah biasa", "m3", 1.327, 180000.00),
                      ("Urukan tanah", "m2", 0.025, 220335.00),
                      ("Buis beton dia. 80 cm", "buah", 1.000, 272900.00),
                      ("Tali ijuk", "kg", 4.5, 72150.00),
                      ("Kerikil", "m3", 0.502, 427350.00),
                      ("Pipa PVC 4 inci", "m'", 1.2, 87500.00)], 1361338.93),
}

for _kode, (_uraian, _sat, _lab, _bahan, _f) in HSPK_AIR_LIMBAH.items():
    SEED[_kode] = (_uraian, "Air Limbah", _sat,
                   "HSPK Kota Bandung 2027, " + _kode.replace("HSPK-", "bab ") + ". Data asli dokumen.",
                   _upah(*_lab) + [("bahan", n, s, k, h) for n, s, k, h in _bahan])

HARGA_HSPK_REFERENSI = {k: v[4] for k, v in HSPK_AIR_LIMBAH.items()}  # untuk verifikasi


def seed_pekerjaan():
    """Idempotent. Hanya bekerja bila SEED_VERSI di database berbeda."""
    conn = _connect()
    try:
        conn.execute("CREATE TABLE IF NOT EXISTS preferensi_pengguna (kunci TEXT PRIMARY KEY, nilai TEXT)")
        row = conn.execute("SELECT nilai FROM preferensi_pengguna WHERE kunci = 'seed_versi'").fetchone()
        if row and row["nilai"] == SEED_VERSI:
            return

        for kode, (nama, kategori, satuan, catatan, komponen) in SEED.items():
            ada = conn.execute("SELECT id FROM pekerjaan WHERE kode_ahsp = ?", (kode,)).fetchone()
            if ada:
                pid = ada["id"]
                conn.execute(
                    "UPDATE pekerjaan SET nama_pekerjaan=?, kategori=?, satuan=?, catatan=? WHERE id=?",
                    (nama, kategori, satuan, catatan, pid))
                if conn.execute("SELECT 1 FROM komponen_harga WHERE pekerjaan_id=? AND diubah_manual=1 LIMIT 1",
                                (pid,)).fetchone():
                    continue  # jangan timpa edit pengguna (KF-5)
                conn.execute("DELETE FROM komponen_harga WHERE pekerjaan_id = ?", (pid,))
            else:
                pid = conn.execute(
                    "INSERT INTO pekerjaan (kode_ahsp, nama_pekerjaan, kategori, satuan, catatan) VALUES (?,?,?,?,?)",
                    (kode, nama, kategori, satuan, catatan)).lastrowid
            for tipe, nm, sk, koef, harga in komponen:
                conn.execute(
                    "INSERT INTO komponen_harga (pekerjaan_id, tipe, nama_komponen, satuan, koefisien, harga_satuan) "
                    "VALUES (?,?,?,?,?,?)", (pid, tipe, nm, sk, koef, harga))

        conn.execute("INSERT OR REPLACE INTO preferensi_pengguna (kunci, nilai) VALUES ('seed_versi', ?)",
                     (SEED_VERSI,))
        conn.commit()
    finally:
        conn.close()