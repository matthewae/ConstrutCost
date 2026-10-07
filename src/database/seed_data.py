"""
Seed master pekerjaan + harga satuan (AHSP) dari HSPK Kota Bandung 2027.

SUMBER DATA
- src/database/hspk_bandung_2027.py, hasil impor otomatis workbook
  "HSPK Kota Bandung 2027 (update setelah rapat 27 Agustus)" lewat tools/impor_hspk.py:
    HSD  : seluruh harga satuan dasar upah, material, dan peralatan -> tabel sumber_daya
    AHSP : analisa harga satuan pekerjaan (koefisien x harga dasar)
- PEMETAAN di bawah menentukan item HSPK mana yang dipakai setiap kode pekerjaan aplikasi
  (kode yang dipakai rule engine). Pilihan disesuaikan dengan rumah tinggal <= 2 lantai:
  beton f'c 20 MPa manual, tulangan BjTS < 12 mm manual, bekisting 3 kali pakai, dinding
  1/2 bata 1SP:4PP, keramik lantai 40x40, rangka atap baja ringan pelana, genteng beton.
  Ganti kode HSPK di PEMETAAN untuk memakai item lain (mis. genteng keramik, f'c 25 MPa).

Harga satuan pekerjaan = sum(koefisien x harga dasar) x (1 + BUK 10%); hasilnya sama dengan
harga F di dokumen HSPK (diuji di tests/test_hspk.py).

Naikkan SEED_VERSI setiap kali isi seed diubah; seed otomatis diperbarui saat aplikasi berjalan.
Harga dasar yang diubah pengguna dan komponen tambahan pengguna tidak ditimpa.
"""

from database.estimasi_repository import _connect
from database.hspk_bandung_2027 import AHSP, HSD, SUMBER
from database.init_db import pastikan_skema

SEED_VERSI = "6-hspk-bdg-2027-penulangan-per-diameter"

SUMBER_HSPK = "HSPK Kota Bandung 2027"

# kode aplikasi -> (nama pekerjaan di RAB, kategori, satuan, kode HSPK)
PEMETAAN = {
    # ---------------- Fondasi ----------------
    "FDN.BATUKALI": ("Pasangan Fondasi Batu Belah 1SP : 4PP", "Fondasi", "m3", "2.2.2.1.6"),
    "BTN.SUMURAN": ("Fondasi Sumuran Beton Masif", "Fondasi", "m3", "2.2.2.2.6"),
    "BTN.FONDASI": ("Beton Fondasi Telapak f'c 20 MPa", "Fondasi", "m3", "2.2.1.4.5"),
    "BSI.FONDASI": ("Pembesian Fondasi Telapak (Asumsi Rasio kg/m³)", "Fondasi", "kg", "2.2.1.1.1a"),
    "BSK.FONDASI": ("Bekisting Fondasi Telapak", "Fondasi", "m2", "2.2.1.3.1"),
    "BTN.SLOOF": ("Beton Sloof f'c 20 MPa", "Fondasi", "m3", "2.2.1.4.5"),
    "BSI.SLOOF": ("Pembesian Sloof (Asumsi Rasio kg/m³)", "Fondasi", "kg", "2.2.1.1.3a"),
    "BSK.SLOOF": ("Bekisting Sloof", "Fondasi", "m2", "2.2.1.3.2"),
    # ---------------- Struktur beton ----------------
    "BTN.KOLOM": ("Beton Kolom f'c 20 MPa", "Beton", "m3", "2.2.1.4.5"),
    "BTN.BALOK": ("Beton Balok f'c 20 MPa", "Beton", "m3", "2.2.1.4.5"),
    "BTN.PELAT": ("Beton Pelat Lantai f'c 20 MPa", "Beton", "m3", "2.2.1.4.5"),
    "BTN.DAK": ("Beton Pelat Atap (Dak) f'c 20 MPa", "Beton", "m3", "2.2.1.4.5"),
    "BSI.KOLOM": ("Pembesian Kolom (Asumsi Rasio kg/m³)", "Beton", "kg", "2.2.1.1.3a"),
    "BSI.BALOK": ("Pembesian Balok (Asumsi Rasio kg/m³)", "Beton", "kg", "2.2.1.1.3a"),
    "BSI.PELAT": ("Pembesian Pelat Lantai (Asumsi Rasio kg/m³)", "Beton", "kg", "2.2.1.1.1a"),
    "BSI.DAK": ("Pembesian Pelat Atap (Dak) (Asumsi Rasio kg/m³)", "Beton", "kg", "2.2.1.1.1a"),
    "BSK.KOLOM": ("Bekisting Kolom", "Beton", "m2", "2.2.1.3.3"),
    "BSK.BALOK": ("Bekisting Balok", "Beton", "m2", "2.2.1.3.4"),
    "BSK.PELAT": ("Bekisting Pelat Lantai", "Beton", "m2", "2.2.1.3.5"),
    "BSK.DAK": ("Bekisting Pelat Atap (Dak)", "Beton", "m2", "2.2.1.3.5"),
    # ---------------- Dinding ----------------
    "DND.BATA": ("Pasangan Dinding Bata Merah 1/2 Batu 1SP : 4PP", "Dinding", "m2", "3.6.1.8"),
    "PLS.DINDING": ("Plesteran 1SP : 4PP Tebal 15 mm", "Dinding", "m2", "3.7.4"),
    "ACI.DINDING": ("Acian Dinding", "Dinding", "m2", "3.7.8"),
    "KRM.DINDING": ("Pasangan Keramik Dinding 20x20 cm (Ruang Basah)", "Dinding", "m2", "3.10.1.4"),
    # ---------------- Lantai ----------------
    "KRM.LANTAI": ("Pasangan Keramik Lantai 40x40 cm Polished", "Lantai", "m2", "3.9.8.6"),
    # ---------------- Pintu & jendela ----------------
    "PTU.DAUN": ("Daun Pintu Panel Kayu Kelas I/II", "Pintu & Jendela", "m2", "3.11.1.11"),
    "PTU.KUSEN": ("Kusen Pintu Kayu Kelas II/III 6x15 cm", "Pintu & Jendela", "m'", "3.11.3.5"),
    "PTU.KUNCI": ("Kunci Tanam Pintu", "Pintu & Jendela", "buah", "3.11.4.2"),
    "PTU.ENGSEL": ("Engsel Pintu", "Pintu & Jendela", "buah", "3.11.4.5"),
    "JDL.JENDELA": ("Jendela Kaca 6 mm Rangka Aluminium", "Pintu & Jendela", "m2", "3.11.1.6"),
    # ---------------- Atap ----------------
    "ATP.RANGKA": ("Rangka Atap Pelana Baja Ringan C75", "Atap", "m2", "2.1.1.1"),
    "ATP.PENUTUP": ("Penutup Atap Genteng Beton", "Atap", "m2", "3.1.1.4"),
    # ---------------- Plafon ----------------
    "PLF.RANGKA": ("Rangka Plafon Besi Hollow 40.40 Modul 60x60 cm", "Plafon", "m2", "3.5.3.1"),
    "PLF.GYPSUM": ("Plafon Papan Gypsum Tebal 9 mm", "Plafon", "m2", "3.5.2.1"),
    # ---------------- Cat ----------------
    "CAT.DINDING": ("Pengecatan Tembok Baru (1 Lapis Cat Dasar, 2 Lapis Cat Penutup)", "Cat", "m2", "3.8.10.1"),
}

# Pembesian rinci per jenis baja (rules/penulangan.py): Ø < 12 mm = baja polos BjTP, D >= 12 mm =
# baja ulir/sirip BjTS. Kolom/balok/sloof memakai analisa penulangan kolom-balok, pelat/dak/fondasi
# telapak memakai analisa penulangan slab.
for _grup, _nama, _kategori, _hspk_p, _hspk_u in (
    ("KOLOM", "Kolom", "Beton", "2.2.1.1.3", "2.2.1.1.4a"),
    ("BALOK", "Balok", "Beton", "2.2.1.1.3", "2.2.1.1.4a"),
    ("SLOOF", "Sloof", "Fondasi", "2.2.1.1.3", "2.2.1.1.4a"),
    ("PELAT", "Pelat Lantai", "Beton", "2.2.1.1.1", "2.2.1.1.2a"),
    ("DAK", "Pelat Atap (Dak)", "Beton", "2.2.1.1.1", "2.2.1.1.2a"),
    ("FONDASI", "Fondasi Telapak", "Fondasi", "2.2.1.1.1", "2.2.1.1.2a"),
):
    PEMETAAN[f"BSI.{_grup}.P"] = (f"Pembesian {_nama} Besi Polos (BjTP) Ø < 12 mm", _kategori, "kg", _hspk_p)
    PEMETAAN[f"BSI.{_grup}.U"] = (f"Pembesian {_nama} Besi Ulir (BjTS) D ≥ 12 mm", _kategori, "kg", _hspk_u)

# Bab 6.2 Sistem Air Limbah (data asli, di luar lingkup rule engine; tersedia untuk input manual)
for _kode in [k for k in AHSP if k.startswith("6.2.")]:
    _sheet, _uraian, _f, _komp = AHSP[_kode]
    _satuan = "set" if "set" in _uraian.lower() else ("buah" if "buah" in _uraian.lower() else "unit")
    PEMETAAN[f"HSPK-{_kode}"] = (_uraian, "Air Limbah", _satuan, _kode)


def _kunci(tipe: str, nama: str, satuan: str):
    return tipe, " ".join(nama.split()).lower(), " ".join(satuan.split()).lower()


def _seed_sumber_daya(conn) -> dict:
    """Masukkan / perbarui seluruh harga dasar HSPK. Return {kunci: (id, harga)}.

    Kunci = (tipe, nama, satuan) tanpa membedakan huruf besar/kecil, sehingga 'Semen Portland (PC)'
    dan 'Semen portland (PC)' adalah satu bahan. Bila ada nama ganda, harga pertama yang dipakai.
    Harga yang diubah pengguna (diubah_manual = 1) tidak ditimpa; harga_bawaan tetap diperbarui.
    """
    ada = {
        _kunci(r["tipe"], r["nama"], r["satuan"]): r
        for r in conn.execute("SELECT id, tipe, nama, satuan, harga, diubah_manual FROM sumber_daya")
    }
    peta = {}

    def simpan(tipe, nama, satuan, harga):
        k = _kunci(tipe, nama, satuan)
        if k in peta:
            return
        r = ada.get(k)
        if r is None:
            sid = conn.execute(
                "INSERT INTO sumber_daya (tipe, nama, satuan, harga, harga_bawaan, sumber) VALUES (?,?,?,?,?,?)",
                (tipe, " ".join(nama.split()), " ".join(satuan.split()), harga, harga, SUMBER_HSPK),
            ).lastrowid
            peta[k] = (sid, harga)
        elif r["diubah_manual"]:
            conn.execute("UPDATE sumber_daya SET harga_bawaan=?, sumber=? WHERE id=?", (harga, SUMBER_HSPK, r["id"]))
            peta[k] = (r["id"], r["harga"])
        else:
            conn.execute(
                "UPDATE sumber_daya SET harga=?, harga_bawaan=?, sumber=? WHERE id=?",
                (harga, harga, SUMBER_HSPK, r["id"]),
            )
            peta[k] = (r["id"], harga)

    for tipe, nama, satuan, harga in HSD:
        simpan(tipe, nama, satuan, harga)
    # Komponen analisa yang tidak tercantum di daftar HSD ikut ditambahkan. Analisa yang dipakai
    # aplikasi diproses lebih dulu: bila nama yang sama punya harga berbeda di analisa lain
    # (mis. 'Pasir beton' per kg), harga milik analisa yang dipakai yang menang.
    dipakai = [kode for _n, _k, _s, kode in PEMETAAN.values()]
    for kode in dipakai + [k for k in AHSP if k not in set(dipakai)]:
        for tipe, nama, satuan, _koef, harga in AHSP[kode][3]:
            simpan(tipe, nama, satuan, harga)
    return peta


def _bersihkan_usang(conn, id_dipakai: set, kode_aktif: set) -> None:
    """Hapus data seed versi lama yang tidak dipakai lagi (mis. harga [PLACEHOLDER]).
    Yang diubah / ditambah pengguna, atau masih dirujuk hasil estimasi proyek, dipertahankan."""
    for r in conn.execute("SELECT id, kode_ahsp FROM pekerjaan").fetchall():
        if r["kode_ahsp"] in kode_aktif:
            continue
        if conn.execute("SELECT 1 FROM hasil_estimasi WHERE pekerjaan_id = ? LIMIT 1", (r["id"],)).fetchone():
            continue
        conn.execute("DELETE FROM komponen_harga WHERE pekerjaan_id = ?", (r["id"],))
        conn.execute("DELETE FROM pekerjaan WHERE id = ?", (r["id"],))
    calon = conn.execute(
        """SELECT id FROM sumber_daya sd
           WHERE harga_bawaan IS NOT NULL AND COALESCE(diubah_manual, 0) = 0
             AND NOT EXISTS (SELECT 1 FROM komponen_harga kh WHERE kh.sumber_daya_id = sd.id)"""
    ).fetchall()
    for r in calon:
        if r["id"] not in id_dipakai:
            conn.execute("DELETE FROM riwayat_harga WHERE sumber_daya_id = ?", (r["id"],))
            conn.execute("DELETE FROM sumber_daya WHERE id = ?", (r["id"],))


def seed_pekerjaan():
    """Idempotent. Hanya bekerja bila SEED_VERSI di database berbeda."""
    conn = _connect()
    try:
        pastikan_skema(conn)
        row = conn.execute(
            "SELECT nilai FROM preferensi_pengguna WHERE kunci = 'seed_versi'"
        ).fetchone()
        if row and row["nilai"] == SEED_VERSI:
            return

        peta = _seed_sumber_daya(conn)
        for kode, (nama, kategori, satuan, kode_hspk) in PEMETAAN.items():
            _sheet, uraian, harga_f, komponen = AHSP[kode_hspk]
            catatan = f"{SUMBER} · {kode_hspk} · {uraian} (harga satuan dokumen Rp {harga_f:,.0f})".replace(",", ".")
            ada = conn.execute("SELECT id FROM pekerjaan WHERE kode_ahsp = ?", (kode,)).fetchone()
            if ada:
                pid = ada["id"]
                conn.execute(
                    "UPDATE pekerjaan SET nama_pekerjaan=?, kategori=?, satuan=?, catatan=? WHERE id=?",
                    (nama, kategori, satuan, catatan, pid),
                )
                conn.execute(
                    "DELETE FROM komponen_harga WHERE pekerjaan_id = ? AND COALESCE(diubah_manual, 0) = 0",
                    (pid,),
                )
            else:
                pid = conn.execute(
                    "INSERT INTO pekerjaan (kode_ahsp, nama_pekerjaan, kategori, satuan, catatan) VALUES (?,?,?,?,?)",
                    (kode, nama, kategori, satuan, catatan),
                ).lastrowid
            for tipe, nm, sk, koef, _harga in komponen:
                sid, harga = peta[_kunci(tipe, nm, sk)]
                conn.execute(
                    "INSERT INTO komponen_harga (pekerjaan_id, tipe, nama_komponen, satuan, koefisien, "
                    "harga_satuan, sumber_daya_id) VALUES (?,?,?,?,?,?,?)",
                    (pid, tipe, nm, sk, koef, harga, sid),
                )

        _bersihkan_usang(conn, {sid for sid, _ in peta.values()}, set(PEMETAAN))
        conn.execute(
            "INSERT OR REPLACE INTO preferensi_pengguna (kunci, nilai) VALUES ('seed_versi', ?)",
            (SEED_VERSI,),
        )
        conn.commit()
    finally:
        conn.close()
