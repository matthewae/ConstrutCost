"""
KF-7: parameter aturan (asumsi teknis rule engine) disimpan per proyek.

Setiap proyek memakai PARAMETER_DEFAULT (rules/parameter.py) kecuali nilai yang diubah pengguna,
yang disimpan sebagai JSON di kolom proyek.parameter. Dengan begitu file proyek dan estimasi ulang
selalu memakai asumsi yang sama (KNF-3 konsistensi hasil).
"""

import json
from dataclasses import fields, replace

from aktivitas import catat
from database.estimasi_repository import _connect
from rules.parameter import PARAMETER_DEFAULT, ParameterEstimasi

# (kunci, label, satuan, minimum, maksimum, desimal) per kelompok, untuk dialog Parameter Aturan
PARAMETER_EDIT = {
    "Fondasi batu kali (turunan dinding lantai dasar)": [
        ("batu_kali_lebar_atas", "Lebar atas", "m", 0.15, 1.5, 2),
        ("batu_kali_lebar_bawah", "Lebar bawah", "m", 0.2, 2.0, 2),
        ("batu_kali_tinggi", "Tinggi", "m", 0.3, 2.0, 2),
    ],
    "Fondasi sumuran (turunan kolom lantai dasar)": [
        ("sumuran_diameter", "Diameter sumuran", "m", 0.4, 2.0, 2),
        ("sumuran_kedalaman", "Kedalaman sumuran", "m", 0.5, 6.0, 2),
        ("sumuran_jumlah_tiang", "Jumlah sumuran per kolom", "buah", 1, 4, 0),
        ("poer_panjang", "Panjang poer", "m", 0.4, 3.0, 2),
        ("poer_lebar", "Lebar poer", "m", 0.4, 3.0, 2),
        ("poer_tebal", "Tebal poer", "m", 0.15, 1.0, 2),
    ],
    "Pekerjaan tanah": [
        ("ruang_kerja_galian", "Ruang kerja galian tiap sisi", "m", 0.0, 0.5, 2),
        ("tebal_pasir_fondasi", "Pasir bawah fondasi", "m", 0.0, 0.3, 2),
        ("tebal_pasir_sloof", "Pasir bawah sloof", "m", 0.0, 0.3, 2),
        ("tebal_pasir_lantai", "Pasir bawah lantai", "m", 0.0, 0.3, 2),
        ("tebal_lantai_kerja", "Lantai kerja / rabat", "m", 0.0, 0.2, 2),
        ("kedalaman_fondasi_telapak", "Kedalaman dasar footplate", "m", 0.5, 4.0, 2),
    ],
    "Pembesian bila penampang tidak diketahui": [
        ("rasio_besi_kolom", "Rasio besi kolom", "kg/m³", 50, 400, 0),
        ("rasio_besi_balok", "Rasio besi balok", "kg/m³", 50, 400, 0),
        ("rasio_besi_sloof", "Rasio besi sloof", "kg/m³", 50, 400, 0),
        ("rasio_besi_pelat", "Rasio besi pelat", "kg/m³", 30, 300, 0),
        ("rasio_besi_fondasi", "Rasio besi fondasi", "kg/m³", 30, 300, 0),
    ],
    "Dinding, atap, dan pintu": [
        ("jumlah_sisi_plester", "Sisi plester & acian", "sisi", 1, 2, 0),
        ("jumlah_sisi_cat", "Sisi cat", "sisi", 1, 2, 0),
        ("batas_kemiringan_dak", "Batas kemiringan dak datar", "°", 0, 15, 1),
        ("jumlah_engsel_pintu", "Engsel per daun pintu", "buah", 2, 4, 0),
    ],
}
_SPEK = {k: (label, sat, lo, hi, d) for grup in PARAMETER_EDIT.values() for k, label, sat, lo, hi, d in grup}
_TIPE = {f.name: f.type for f in fields(ParameterEstimasi)}


class ParameterTidakValid(ValueError):
    """Nilai parameter ditolak. Pesannya siap ditampilkan ke pengguna."""


def _ke_param(perubahan: dict) -> ParameterEstimasi:
    bersih = {k: v for k, v in perubahan.items() if k in _SPEK}
    return replace(PARAMETER_DEFAULT, **bersih)


def parameter_dari_json(teks: str | None) -> ParameterEstimasi:
    try:
        return _ke_param(json.loads(teks or "{}"))
    except (ValueError, TypeError):
        return PARAMETER_DEFAULT


def muat_parameter(proyek_id: int) -> ParameterEstimasi:
    conn = _connect()
    try:
        row = conn.execute("SELECT parameter FROM proyek WHERE id = ?", (proyek_id,)).fetchone()
    finally:
        conn.close()
    return parameter_dari_json(row["parameter"] if row else None)


def perubahan_parameter(proyek_id: int) -> dict:
    """Parameter proyek yang berbeda dari bawaan."""
    p = muat_parameter(proyek_id)
    return {k: getattr(p, k) for k in _SPEK if getattr(p, k) != getattr(PARAMETER_DEFAULT, k)}


def validasi_parameter(nilai: dict) -> dict:
    hasil = {}
    for k, v in nilai.items():
        if k not in _SPEK:
            raise ParameterTidakValid(f"Parameter '{k}' tidak dikenal.")
        label, sat, lo, hi, d = _SPEK[k]
        try:
            v = float(v)
        except (TypeError, ValueError):
            raise ParameterTidakValid(f"{label} harus berupa angka.") from None
        if not lo <= v <= hi:
            raise ParameterTidakValid(f"{label} harus {lo:g} sampai {hi:g} {sat}.")
        hasil[k] = int(round(v)) if _TIPE[k] in (int, "int") else v
    p = _ke_param(hasil)
    if p.batu_kali_lebar_atas > p.batu_kali_lebar_bawah:
        raise ParameterTidakValid("Lebar atas batu kali tidak boleh lebih besar dari lebar bawah.")
    return hasil


def simpan_parameter(proyek_id: int, nilai: dict) -> None:
    """Simpan parameter proyek; hanya nilai yang berbeda dari bawaan yang disimpan."""
    bersih = validasi_parameter(nilai)
    beda = {k: v for k, v in bersih.items() if v != getattr(PARAMETER_DEFAULT, k)}
    conn = _connect()
    try:
        conn.execute(
            "UPDATE proyek SET parameter = ?, tanggal_diubah = CURRENT_TIMESTAMP WHERE id = ?",
            (json.dumps(beda) if beda else None, proyek_id),
        )
        conn.commit()
        teks = ", ".join(f"{_SPEK[k][0].lower()} {v:g} {_SPEK[k][1]}" for k, v in beda.items()) or "semua nilai bawaan"
        catat("parameter", f"Parameter aturan disimpan: {teks}", proyek_id)
    finally:
        conn.close()
