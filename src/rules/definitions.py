"""
Basis aturan IF-THEN (KF-3) dan rumus kuantitas pekerjaan / QTO (KF-4).

Bentuk umum satu aturan:

    IF   kelas elemen == X  AND  syarat(elemen, konteks) terpenuhi
    THEN kuantitas pekerjaan <kode_ahsp> = hitung(elemen, parameter)

- `kelas`  : hasil klasifikasi KF-2 (lihat klasifikasi.ElementType).
- `butuh`  : dimensi yang wajib ada; bila kosong aturan dilewati dan dicatat sebagai peringatan.
- `syarat` : kondisi tambahan (PredefinedType, lantai dasar, sumber luas, ...). Bila tidak
             terpenuhi aturan diam-diam tidak berlaku.
- `hitung` : mengembalikan (kuantitas, uraian). Uraian berisi rumus + angka yang dipakai
             sehingga setiap kuantitas bisa ditelusuri (dasar KF-18).

Satu elemen dapat memicu banyak pekerjaan (mis. kolom -> beton + pembesian + bekisting).
Untuk menambah pekerjaan baru: tambah satu Rule di sini + data harganya di database/seed_data.py.
Nomor rumus mengacu pada BAB II subbab 2.4.9.
"""

import math
import re
from dataclasses import dataclass
from typing import Callable

from klasifikasi import ElementType as T

from .konteks import Konteks
from .parameter import ParameterEstimasi


@dataclass(frozen=True)
class Rule:
    kode: str  # = pekerjaan.kode_ahsp
    kelas: T
    hitung: Callable  # (elemen, parameter) -> (kuantitas, uraian)
    butuh: tuple = ()
    syarat: Callable | None = None  # (elemen, konteks, parameter) -> bool
    keterangan: str = ""


# ---------------------------------------------------------------- format angka


def _n(x: float, d: int = 3) -> str:
    """Format angka Indonesia untuk uraian: 1.234,567"""
    return f"{x:,.{d}f}".replace(",", "X").replace(".", ",").replace("X", ".")


# ---------------------------------------------------------------- rumus


def _volume(simbol="V"):
    def f(e, p):
        return e["volume"], f"{simbol} = {_n(e['volume'])} m³ (volume elemen dari model)"

    return f


def _besi(nama_rasio):
    def f(e, p):
        rasio = getattr(p, nama_rasio)
        nilai = e["volume"] * rasio
        return nilai, f"Berat = V × rasio = {_n(e['volume'])} m³ × {_n(rasio, 0)} kg/m³ = {_n(nilai, 2)} kg"

    return f


def _bekisting_kolom(e, p):
    # luas selimut kolom = keliling penampang x tinggi
    b, h, t = e["lebar"], e["tebal"], e["tinggi"]
    nilai = 2 * (b + h) * t
    return nilai, f"A = 2 × (b + h) × H = 2 × ({_n(b)} + {_n(h)}) × {_n(t)} = {_n(nilai)} m²"


def _bekisting_balok(e, p):
    # dua sisi + alas balok (sisi atas tertutup bekisting pelat)
    b, h, L = e["lebar"], e["tinggi"], e["panjang"]
    nilai = (b + 2 * h) * L
    return nilai, f"A = (b + 2h) × L = ({_n(b)} + 2 × {_n(h)}) × {_n(L)} = {_n(nilai)} m²"


def _bekisting_sisi(e, p):
    # sloof: dua sisi tegak
    h, L = e["tebal"], e["panjang"]
    nilai = 2 * h * L
    return nilai, f"A = 2 × h × L = 2 × {_n(h)} × {_n(L)} = {_n(nilai)} m²"


def _bekisting_keliling(e, p):
    # fondasi telapak: sisi tegak sekeliling
    k, t = e["keliling"], e["tebal"]
    nilai = k * t
    return nilai, f"A = keliling × tebal = {_n(k)} × {_n(t)} = {_n(nilai)} m²"


def _luas(keterangan="luas dari model"):
    def f(e, p):
        return e["luas"], f"A = {_n(e['luas'])} m² ({keterangan})"

    return f


def _luas_dinding_kali(nama_sisi, nama):
    def f(e, p):
        sisi = getattr(p, nama_sisi)
        nilai = e["luas"] * sisi
        bukaan = e.get("luas_bukaan") or 0.0
        catatan = f"; luas bukaan {_n(bukaan, 2)} m² sudah dikurangkan" if bukaan else ""
        return nilai, (
            f"A_{nama} = A_dinding bersih × {sisi} sisi = {_n(e['luas'])} × {sisi} = {_n(nilai)} m²{catatan}"
        )

    return f


def _luas_dinding(e, p):
    bukaan = e.get("luas_bukaan") or 0.0
    catatan = f" (bukaan pintu/jendela {_n(bukaan, 2)} m² sudah dikurangkan)" if bukaan else ""
    return e["luas"], f"A = luas satu sisi dinding = {_n(e['luas'])} m²{catatan}"


def _luas_atap(e, p):
    teta = e.get("kemiringan")
    if teta is None:
        return e["luas"], f"A miring = {_n(e['luas'])} m²"
    proyeksi = e["luas"] * math.cos(math.radians(teta))
    return e["luas"], (
        f"A = A_proyeksi / cos θ = {_n(proyeksi)} / cos {_n(teta, 1)}° = {_n(e['luas'])} m²"
    )


def _batu_kali_dinding(e, p):
    ba, bb, h, L = p.batu_kali_lebar_atas, p.batu_kali_lebar_bawah, p.batu_kali_tinggi, e["panjang"]
    nilai = (ba + bb) / 2 * h * L
    return nilai, (
        f"V = (B_atas + B_bawah)/2 × H × L = ({_n(ba, 2)} + {_n(bb, 2)})/2 × {_n(h, 2)} × {_n(L)} "
        f"= {_n(nilai)} m³ (dimensi penampang = asumsi)"
    )


def _volume_sumuran(p: ParameterEstimasi):
    v_tiang = math.pi * p.sumuran_diameter**2 / 4 * p.sumuran_kedalaman
    v_poer = p.poer_panjang * p.poer_lebar * p.poer_tebal
    return p.sumuran_jumlah_tiang * v_tiang + v_poer, v_tiang, v_poer


def _sumuran(e, p):
    total, v_tiang, v_poer = _volume_sumuran(p)
    return total, (
        f"V = n × (π d²/4 × H) + P × L × T = {p.sumuran_jumlah_tiang} × "
        f"(π × {_n(p.sumuran_diameter, 2)}²/4 × {_n(p.sumuran_kedalaman, 2)}) + "
        f"{_n(p.poer_panjang, 2)} × {_n(p.poer_lebar, 2)} × {_n(p.poer_tebal, 2)} = {_n(total)} m³ "
        f"(1 titik kolom, dimensi = asumsi)"
    )


def _besi_sumuran(e, p):
    total, _, _ = _volume_sumuran(p)
    nilai = total * p.rasio_besi_sumuran
    return nilai, (
        f"Berat = V_sumuran × rasio = {_n(total)} m³ × {_n(p.rasio_besi_sumuran, 0)} kg/m³ = {_n(nilai, 2)} kg"
    )


def _satu_unit(e, p):
    ukuran = ""
    if e.get("lebar") and e.get("tinggi"):
        ukuran = f" ({_n(e['lebar'], 2)} × {_n(e['tinggi'], 2)} m)"
    return 1.0, f"Jumlah = 1 unit{ukuran}"


def _luas_bukaan(e, p):
    if e.get("lebar") and e.get("tinggi"):
        return e["luas"], f"A = lebar × tinggi = {_n(e['lebar'], 2)} × {_n(e['tinggi'], 2)} = {_n(e['luas'])} m²"
    return e["luas"], f"A = {_n(e['luas'])} m²"


def cari_ruang_basah(nama: str | None, p: ParameterEstimasi):
    """(kata_kunci, tinggi_keramik) bila nama ruang menandakan ruang basah, selain itu None."""
    teks = (nama or "").lower()
    for kunci, tinggi in p.tinggi_keramik_dinding.items():
        if re.search(rf"(?<![a-z]){re.escape(kunci)}(?![a-z])", teks):
            return kunci, tinggi
    return None


def _keramik_dinding(e, p):
    kunci, tinggi = cari_ruang_basah(e["nama"], p)
    nilai = e["keliling"] * tinggi
    return nilai, (
        f"A = keliling ruang × tinggi keramik = {_n(e['keliling'])} × {_n(tinggi, 2)} = {_n(nilai)} m² "
        f"(ruang basah: '{kunci}')"
    )


# ---------------------------------------------------------------- syarat


def _pre(*nilai):
    return lambda e, k, p: (e.get("predefined_type") or "") in nilai


def _bukan_pre(*nilai):
    return lambda e, k, p: (e.get("predefined_type") or "") not in nilai


def _fondasi_turunan(e, k: Konteks, p):
    # model tidak memuat fondasi -> fondasi diturunkan dari elemen di lantai dasar (Batasan no. 8)
    return e.get("di_lantai_dasar", False) and not k.ada_fondasi_model


def _atap_miring(e, k, p):
    teta = e.get("kemiringan")
    return teta is None or teta >= p.batas_kemiringan_dak


def _dak(e, k, p):
    return not _atap_miring(e, k, p)


def _sumber_lantai(nilai):
    return lambda e, k, p: k.sumber_lantai == nilai


def _sumber_plafon(nilai):
    return lambda e, k, p: k.sumber_plafon == nilai


def _pelat_melayang(e, k, p):
    # pelat di atas tanah (BASESLAB / lantai dasar) tidak memerlukan bekisting bawah
    return (e.get("predefined_type") or "") != "BASESLAB" and not e.get("di_lantai_dasar", False)


def _ruang_basah(e, k, p):
    return cari_ruang_basah(e.get("nama"), p) is not None


FONDASI_MENERUS = ("STRIP_FOOTING",)
SLOOF = ("FOOTING_BEAM",)


# ---------------------------------------------------------------- basis aturan

RULES = [
    # ===== Kolom (Rumus 2.10) =====
    Rule("BTN.KOLOM", T.COLUMN, _volume(), ("volume",), keterangan="Volume beton kolom"),
    Rule("BSI.KOLOM", T.COLUMN, _besi("rasio_besi_kolom"), ("volume",), keterangan="Pembesian (rasio asumsi)"),
    Rule("BSK.KOLOM", T.COLUMN, _bekisting_kolom, ("lebar", "tebal", "tinggi"), keterangan="Bekisting kolom"),
    # Fondasi sumuran di bawah kolom lantai dasar (Rumus 2.36 - 2.39)
    Rule("BTN.SUMURAN", T.COLUMN, _sumuran, syarat=_fondasi_turunan, keterangan="Fondasi sumuran (turunan)"),
    Rule("BSI.SUMURAN", T.COLUMN, _besi_sumuran, syarat=_fondasi_turunan, keterangan="Pembesian sumuran (turunan)"),
    # ===== Balok (Rumus 2.9) =====
    Rule("BTN.BALOK", T.BEAM, _volume(), ("volume",)),
    Rule("BSI.BALOK", T.BEAM, _besi("rasio_besi_balok"), ("volume",)),
    Rule("BSK.BALOK", T.BEAM, _bekisting_balok, ("lebar", "tinggi", "panjang")),
    # ===== Pelat lantai (Rumus 2.11 / 2.37) =====
    Rule("BTN.PELAT", T.SLAB, _volume(), ("volume",)),
    Rule("BSI.PELAT", T.SLAB, _besi("rasio_besi_pelat"), ("volume",)),
    Rule("BSK.PELAT", T.SLAB, _luas("luas bidang bawah pelat"), ("luas",), syarat=_pelat_melayang),
    # ===== Atap miring: rangka baja ringan + genteng (Rumus 2.22 / 2.23 / 2.42) =====
    Rule("ATP.RANGKA", T.ROOF, _luas_atap, ("luas",), syarat=_atap_miring, keterangan="Rangka atap baja ringan per m² luas atap"),
    Rule("ATP.PENUTUP", T.ROOF, _luas_atap, ("luas",), syarat=_atap_miring, keterangan="Penutup atap genteng"),
    # ===== Atap datar: dak beton =====
    Rule("BTN.DAK", T.ROOF, _volume(), ("volume",), syarat=_dak),
    Rule("BSI.DAK", T.ROOF, _besi("rasio_besi_pelat"), ("volume",), syarat=_dak),
    Rule("BSK.DAK", T.ROOF, _luas("luas bidang bawah dak"), ("luas",), syarat=_dak),
    # ===== Dinding (Rumus 2.17 - 2.19) =====
    Rule("DND.BATA", T.WALL, _luas_dinding, ("luas",), keterangan="Pasangan dinding bata (m²)"),
    Rule("PLS.DINDING", T.WALL, _luas_dinding_kali("jumlah_sisi_plester", "plester"), ("luas",)),
    Rule("CAT.DINDING", T.WALL, _luas_dinding_kali("jumlah_sisi_cat", "cat"), ("luas",)),
    # Fondasi batu kali di bawah dinding lantai dasar (Rumus 2.34)
    Rule("FDN.BATUKALI", T.WALL, _batu_kali_dinding, ("panjang",), syarat=_fondasi_turunan, keterangan="Fondasi batu kali (turunan)"),
    # ===== Fondasi yang dimodelkan =====
    Rule("FDN.BATUKALI", T.FOOTING, _volume(), ("volume",), syarat=_pre(*FONDASI_MENERUS), keterangan="Fondasi menerus = batu kali"),
    Rule("BTN.SLOOF", T.FOOTING, _volume(), ("volume",), syarat=_pre(*SLOOF)),
    Rule("BSI.SLOOF", T.FOOTING, _besi("rasio_besi_sloof"), ("volume",), syarat=_pre(*SLOOF)),
    Rule("BSK.SLOOF", T.FOOTING, _bekisting_sisi, ("tebal", "panjang"), syarat=_pre(*SLOOF)),
    Rule("BTN.FONDASI", T.FOOTING, _volume(), ("volume",), syarat=_bukan_pre(*FONDASI_MENERUS, *SLOOF), keterangan="Footplate / pile cap"),
    Rule("BSI.FONDASI", T.FOOTING, _besi("rasio_besi_fondasi"), ("volume",), syarat=_bukan_pre(*FONDASI_MENERUS, *SLOOF)),
    Rule("BSK.FONDASI", T.FOOTING, _bekisting_keliling, ("keliling", "tebal"), syarat=_bukan_pre(*FONDASI_MENERUS, *SLOOF)),
    Rule("BTN.SUMURAN", T.PILE, _volume(), ("volume",)),
    Rule("BSI.SUMURAN", T.PILE, _besi("rasio_besi_sumuran"), ("volume",)),
    # ===== Pintu & jendela =====
    Rule("PTU.PINTU", T.DOOR, _satu_unit, keterangan="Jumlah elemen pintu"),
    Rule("JDL.JENDELA", T.WINDOW, _luas_bukaan, ("luas",)),
    # ===== Lantai (Rumus 2.12 - 2.13): sumber dipilih preprocessor =====
    Rule("KRM.LANTAI", T.FLOOR, _luas("luas penutup lantai"), ("luas",), syarat=_sumber_lantai("covering")),
    Rule("KRM.LANTAI", T.SPACE, _luas("luas lantai ruang"), ("luas",), syarat=_sumber_lantai("ruang")),
    Rule("KRM.LANTAI", T.SLAB, _luas("asumsi: luas keramik = luas pelat"), ("luas",), syarat=_sumber_lantai("pelat")),
    # ===== Keramik dinding ruang basah (Rumus 2.14 - 2.15) =====
    Rule("KRM.DINDING", T.SPACE, _keramik_dinding, ("keliling",), syarat=_ruang_basah),
    # ===== Plafon (Rumus 2.16): sumber dipilih preprocessor =====
    Rule("PLF.GYPSUM", T.CEILING, _luas("luas plafon dari model"), ("luas",), syarat=_sumber_plafon("covering")),
    Rule("PLF.GYPSUM", T.SPACE, _luas("luas plafon = luas lantai ruang"), ("luas",), syarat=_sumber_plafon("ruang")),
    Rule("PLF.GYPSUM", T.SLAB, _luas("asumsi: luas plafon = luas pelat"), ("luas",), syarat=_sumber_plafon("pelat")),
]
