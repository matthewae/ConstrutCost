"""
Seed master pekerjaan + komponen_harga (AHSP).
!! SEMUA KOEFISIEN & HARGA DI SINI CONTOH/PLACEHOLDER !!
Ganti dengan AHSP Cipta Karya/SNI resmi + harga satuan dasar (HSD) kota Anda,
atau edit lewat fitur KF-5. Fungsi ini aman dipanggil berulang (idempotent).
"""

from database.estimasi_repository import _connect

# kode: (nama, kategori, satuan, [(tipe, komponen, satuan, koefisien, harga)])
SEED = {
    "BTN.KOLOM":   ("Beton Kolom K-225", "Beton", "m3", [
        ("bahan", "Semen PC 50kg", "kg", 371, 1500), ("bahan", "Pasir beton", "kg", 698, 300),
        ("bahan", "Split 2/3", "kg", 1047, 350), ("upah", "Pekerja", "OH", 1.65, 120000),
        ("upah", "Tukang batu", "OH", 0.275, 150000)]),
    "BTN.BALOK":   ("Beton Balok K-225", "Beton", "m3", [
        ("bahan", "Semen PC 50kg", "kg", 371, 1500), ("bahan", "Pasir beton", "kg", 698, 300),
        ("bahan", "Split 2/3", "kg", 1047, 350), ("upah", "Pekerja", "OH", 1.65, 120000),
        ("upah", "Tukang batu", "OH", 0.275, 150000)]),
    "BTN.PELAT":   ("Beton Pelat Lantai K-225", "Beton", "m3", [
        ("bahan", "Semen PC 50kg", "kg", 371, 1500), ("bahan", "Pasir beton", "kg", 698, 300),
        ("bahan", "Split 2/3", "kg", 1047, 350), ("upah", "Pekerja", "OH", 1.65, 120000),
        ("upah", "Tukang batu", "OH", 0.275, 150000)]),
    "BTN.FONDASI": ("Beton Fondasi K-225", "Fondasi", "m3", [
        ("bahan", "Semen PC 50kg", "kg", 371, 1500), ("bahan", "Pasir beton", "kg", 698, 300),
        ("bahan", "Split 2/3", "kg", 1047, 350), ("upah", "Pekerja", "OH", 1.65, 120000),
        ("upah", "Tukang batu", "OH", 0.275, 150000)]),
    "BSI.KOLOM":   ("Pembesian Kolom", "Beton", "kg", []),
    "BSI.BALOK":   ("Pembesian Balok", "Beton", "kg", []),
    "BSI.PELAT":   ("Pembesian Pelat", "Beton", "kg", []),
    "BSI.FONDASI": ("Pembesian Fondasi", "Fondasi", "kg", []),
    "DND.BATA":    ("Pasangan Dinding Bata Merah 1/2 Bata", "Dinding", "m2", [
        ("bahan", "Bata merah", "buah", 70, 900), ("bahan", "Semen PC 50kg", "kg", 11.5, 1500),
        ("bahan", "Pasir pasang", "m3", 0.043, 300000), ("upah", "Pekerja", "OH", 0.3, 120000),
        ("upah", "Tukang batu", "OH", 0.1, 150000)]),
    "PLS.DINDING": ("Plesteran + Acian Dinding", "Dinding", "m2", [
        ("bahan", "Semen PC 50kg", "kg", 6.24, 1500), ("bahan", "Pasir pasang", "m3", 0.024, 300000),
        ("upah", "Pekerja", "OH", 0.3, 120000), ("upah", "Tukang batu", "OH", 0.15, 150000)]),
    "CAT.DINDING": ("Cat Dasar Dinding", "Cat", "m2", [
        ("bahan", "Cat dasar", "kg", 0.1, 45000), ("upah", "Tukang cat", "OH", 0.02, 150000),
        ("upah", "Pekerja", "OH", 0.01, 120000)]),
    "ATP.PENUTUP": ("Penutup Atap", "Atap", "m2", [
        ("bahan", "Genteng/penutup atap", "m2", 1.05, 90000), ("upah", "Tukang", "OH", 0.1, 150000),
        ("upah", "Pekerja", "OH", 0.05, 120000)]),
}
# Besi tulangan: harga per kg (pekerjaan kg) -> 1 kg besi + upah
_BESI = [("bahan", "Besi beton + kawat bendrat", "kg", 1.05, 14000),
         ("upah", "Tukang besi", "OH", 0.007, 150000), ("upah", "Pekerja", "OH", 0.007, 120000)]
for k in ("BSI.KOLOM", "BSI.BALOK", "BSI.PELAT", "BSI.FONDASI"):
    SEED[k] = SEED[k][:3] + (_BESI,)


def seed_pekerjaan():
    conn = _connect()
    try:
        for kode, (nama, kat, sat, komponen) in SEED.items():
            cur = conn.execute(
                "INSERT OR IGNORE INTO pekerjaan (kode_ahsp, nama_pekerjaan, kategori, satuan) VALUES (?,?,?,?)",
                (kode, nama, kat, sat))
            if cur.rowcount:  # baru dibuat -> isi komponennya
                for tipe, nm, sk, koef, harga in komponen:
                    conn.execute(
                        "INSERT INTO komponen_harga (pekerjaan_id, tipe, nama_komponen, satuan, koefisien, harga_satuan) "
                        "VALUES (?,?,?,?,?,?)", (cur.lastrowid, tipe, nm, sk, koef, harga))
        conn.commit()
    finally:
        conn.close()
