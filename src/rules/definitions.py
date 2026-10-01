"""
Daftar aturan IF-THEN (KF-3). Satu elemen IFC bisa memicu BANYAK pekerjaan.

  IF  ifc_type == X  AND  predefined_type memenuhi filter
  THEN volume_pekerjaan = <basis elemen> x faktor   ->  pekerjaan dengan kode_ahsp tertentu

basis  : 'volume' (m3) | 'luas' (m2) | 'panjang' (m)
faktor : pengali. Contoh: pembesian = volume beton x rasio kg/m3; plester 2 sisi = luas x 2.
Untuk menambah pekerjaan baru cukup tambah satu baris Rule di sini (+ seed di seed_data.py).
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Rule:
    ifc_type: str
    kode: str                      # = pekerjaan.kode_ahsp
    basis: str
    faktor: float = 1.0
    hanya_predefined: tuple = ()   # kosong = semua tipe
    kecuali_predefined: tuple = ()
    keterangan: str = ""


ATAP = ("ROOF",)

RULES = [
    # --- Kolom ---
    Rule("IfcColumn", "BTN.KOLOM", "volume", keterangan="Volume beton kolom"),
    Rule("IfcColumn", "BSI.KOLOM", "volume", 150.0, keterangan="Pembesian = vol beton x 150 kg/m3 (asumsi)"),
    # --- Balok ---
    Rule("IfcBeam", "BTN.BALOK", "volume"),
    Rule("IfcBeam", "BSI.BALOK", "volume", 130.0, keterangan="asumsi 130 kg/m3"),
    # --- Pelat lantai (slab selain atap) ---
    Rule("IfcSlab", "BTN.PELAT", "volume", kecuali_predefined=ATAP),
    Rule("IfcSlab", "BSI.PELAT", "volume", 90.0, kecuali_predefined=ATAP, keterangan="asumsi 90 kg/m3"),
    # --- Atap (slab ROOF) ---
    Rule("IfcSlab", "ATP.PENUTUP", "luas", hanya_predefined=ATAP, keterangan="Luas penutup atap"),
    # --- Dinding ---
    Rule("IfcWall", "DND.BATA", "luas", keterangan="Pasangan dinding bata (m2)"),
    Rule("IfcWall", "PLS.DINDING", "luas", 2.0, keterangan="Plester + aci, 2 sisi"),
    Rule("IfcWall", "CAT.DINDING", "luas", 2.0, keterangan="Cat dasar, 2 sisi"),
    # --- Fondasi ---
    Rule("IfcFooting", "BTN.FONDASI", "volume"),
    Rule("IfcFooting", "BSI.FONDASI", "volume", 80.0, keterangan="asumsi 80 kg/m3"),
]