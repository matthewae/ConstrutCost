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
`hitung` juga boleh mengembalikan daftar item (pembesian: satu item per diameter tulangan).
Untuk menambah pekerjaan baru: tambah satu Rule di sini + data harganya di database/seed_data.py.
Nomor rumus mengacu pada BAB II subbab 2.4.9.
"""

import math
import re
from dataclasses import dataclass
from typing import Callable

import elemen_lain
from klasifikasi import ElementType as T

from . import fondasi_kolom, penulangan, tanah
from .konteks import Konteks
from .parameter import FONDASI_FOOTPLATE, FONDASI_MODEL, ParameterEstimasi
from .sifat import balok_sloof, bukan_beton, dinding_pasangan, kolom_struktur, pekerjaan_tanah, sumuran_model


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


def _pembesian(nama_rasio):
    """Pembesian rinci per diameter dari tipe penulangan elemen (Rumus 2.30 - 2.33).
    Bila penampang/panjang elemen tidak diketahui, kembali ke asumsi rasio kg/m³."""

    def f(e, p):
        items = penulangan.dari_model(e, None, p.batas_kemiringan_dak)  # tulangan yang dimodelkan didahulukan
        if items:
            return items
        items = penulangan.hitung(e, e.get("penulangan"), p.batas_kemiringan_dak)
        if items:
            return items
        nilai, rumus = _besi(nama_rasio)(e, p)
        kelompok = {
            "rasio_besi_kolom": "KOLOM", "rasio_besi_balok": "BALOK", "rasio_besi_sloof": "SLOOF",
            "rasio_besi_fondasi": "FONDASI",
        }.get(nama_rasio, "DAK" if e.get("kelas") == "ROOF" else "PELAT")
        return [penulangan.ItemBesi(
            penulangan.KODE_PEKERJAAN[kelompok], nilai,
            rumus + " (tulangan rinci tidak dihitung: penampang tidak lengkap atau terlalu kecil untuk "
            "beton bertulang, dipakai asumsi rasio)",
            f"Pembesian (asumsi {getattr(p, nama_rasio):.0f} kg/m³)", None,
        )]

    return f


def _pembesian_tangga(e, p):
    items = penulangan.dari_model(e, "BSI.TANGGA", p.batas_kemiringan_dak)
    return items or _besi("rasio_besi_tangga")(e, p)


def _bekisting_kolom(e, p):
    # luas selimut kolom = keliling penampang x tinggi
    b, h, t = e["lebar"], e["tebal"], e["tinggi"]
    nilai = 2 * (b + h) * t
    return nilai, f"A = 2 × (b + h) × H = 2 × ({_n(b)} + {_n(h)}) × {_n(t)} = {_n(nilai)} m²"


def _bekisting_balok(e, p):
    # dua sisi + alas balok (sisi atas tertutup bekisting pelat). Bila balok dicor bersama pelat,
    # tinggi sisi yang dibekisting = h - t_pelat (bagian setinggi pelat tertutup bekisting pelat).
    b, h, L = e["lebar"], e["tinggi"], e["panjang"]
    sisi = e.get("pelat_sisi")
    if sisi is not None:  # relasi geometri: per sisi, dan alas yang duduk di atas pasangan dinding
        L_alas = max(L - min(e.get("alas_ditopang") or 0.0, L), 0.0)
        s1, s2 = h - (sisi[0] or 0.0), h - (sisi[1] or 0.0)
        nilai = b * L_alas + (s1 + s2) * L
        ket = []
        if L_alas < L - 1e-6:
            ket.append(f"alas {_n(L - L_alas)} m duduk di atas pasangan dinding, tanpa bekisting alas")
        if any(sisi):
            ket.append("pelat dicor bersama: " + " & ".join(
                f"sisi {i} t = {_n(t, 2)}" for i, t in enumerate(sisi, 1) if t))
        if not all(sisi):
            ket.append("sisi tanpa pelat setinggi penuh")
        return nilai, (
            f"A = b × L_alas + (h₁ + h₂) × L = {_n(b)} × {_n(L_alas)} + ({_n(s1)} + {_n(s2)}) × {_n(L)} "
            f"= {_n(nilai)} m² ({'; '.join(ket)})"
        )
    t = e.get("tebal_pelat_monolit")
    if t:
        nilai = (b + 2 * (h - t)) * L
        return nilai, (
            f"A = (b + 2(h − t_pelat)) × L = ({_n(b)} + 2 × ({_n(h)} − {_n(t)})) × {_n(L)} = {_n(nilai)} m² "
            "(balok dicor bersama pelat)"
        )
    nilai = (b + 2 * h) * L
    return nilai, f"A = (b + 2h) × L = ({_n(b)} + 2 × {_n(h)}) × {_n(L)} = {_n(nilai)} m²"


def _bekisting_sloof_balok(e, p):
    # balok bernama sloof: dua sisi tegak (alas di atas pasir/batu kali)
    h, L = e["tinggi"], e["panjang"]
    nilai = 2 * h * L
    return nilai, f"A = 2 × h × L = 2 × {_n(h)} × {_n(L)} = {_n(nilai)} m²"


# ---------------------------------------------------------------- sloof turunan


def _ukuran_sloof_turunan(e):
    b, h, ket = e["sloof_turunan"]
    return b, h, e["panjang"], ket


def _beton_sloof_turunan(e, p):
    b, h, L, ket = _ukuran_sloof_turunan(e)
    nilai = b * h * L
    return nilai, (
        f"V = b × h × L = {_n(b, 2)} × {_n(h, 2)} × {_n(L)} = {_n(nilai)} m³ "
        f"(sloof {_cm(b)}/{_cm(h)} di bawah dinding, ukuran {ket}; panjang = panjang dinding)"
    )


def _bekisting_sloof_turunan(e, p):
    b, h, L, _ = _ukuran_sloof_turunan(e)
    nilai = 2 * h * L
    return nilai, f"A = 2 × h × L = 2 × {_n(h, 2)} × {_n(L)} = {_n(nilai)} m² (dua sisi sloof)"


def _pembesian_sloof_turunan(e, p):
    items = penulangan.hitung(e, e.get("penulangan"), p.batas_kemiringan_dak)
    if items:
        return items
    b, h, L, _ = _ukuran_sloof_turunan(e)
    v = b * h * L
    nilai = v * p.rasio_besi_sloof
    return [penulangan.ItemBesi(
        penulangan.KODE_PEKERJAAN["SLOOF"], nilai,
        f"Berat = V_sloof × rasio = {_n(v)} m³ × {_n(p.rasio_besi_sloof, 0)} kg/m³ = {_n(nilai, 2)} kg",
        f"Pembesian (asumsi {p.rasio_besi_sloof:.0f} kg/m³)", None,
    )]


def _tanah_sloof_turunan(e, p):
    b, _, L, _ = _ukuran_sloof_turunan(e)
    return tanah.pasir_sloof(b, L, p)


def _cm(x: float) -> str:
    return f"{x * 100:g}".replace(".", ",")


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


def _cat_interior(e, p):
    # dinding luar: satu sisi dicat eksterior (aturan CAT.EKSTERIOR), sisanya cat interior
    sisi = p.jumlah_sisi_cat - (1 if e.get("eksternal") and p.jumlah_sisi_cat >= 2 else 0)
    kotor = e["luas"] * sisi
    tertutup = min(elemen_lain.jumlah_tertutup(e, "dalam"), kotor)  # bidang yang dilapis cladding tidak dicat
    nilai = kotor - tertutup
    bukaan = e.get("luas_bukaan") or 0.0
    catatan = f"; luas bukaan {_n(bukaan, 2)} m² sudah dikurangkan" if bukaan else ""
    luar = " (dinding luar: sisi luar dicat eksterior)" if sisi < p.jumlah_sisi_cat else ""
    if tertutup > 0:
        return nilai, (
            f"A_cat interior = A_dinding bersih × {sisi} sisi − A_cladding = {_n(e['luas'])} × {sisi} − "
            f"{_n(tertutup, 2)} = {_n(nilai)} m²{luar}{catatan}"
        )
    return nilai, (
        f"A_cat interior = A_dinding bersih × {sisi} sisi = {_n(e['luas'])} × {sisi} = {_n(nilai)} m²{luar}{catatan}"
    )


def _cat_eksterior(e, p):
    tertutup = min(elemen_lain.jumlah_tertutup(e, "luar"), e["luas"])
    nilai = e["luas"] - tertutup
    if tertutup > 0:
        return nilai, (f"A_cat eksterior = A_dinding bersih − A_cladding = {_n(e['luas'])} − {_n(tertutup, 2)} = "
                       f"{_n(nilai)} m² (bidang yang dilapis cladding tidak dicat)")
    return nilai, f"A_cat eksterior = A_dinding bersih × 1 sisi luar = {_n(nilai)} m²"


# ---------------------------------------------------------------- tangga & railing


def _bekisting_tangga(e, p):
    # bidang miring bawah pelat tangga + bidang tegak anak tangga (riser)
    L, B, H = e["panjang"], e["lebar"], e["tinggi"]
    miring = math.hypot(L, H)
    nilai = B * miring + B * H
    return nilai, (
        f"A = B × √(L² + H²) + B × H = {_n(B, 2)} × √({_n(L, 2)}² + {_n(H, 2)}²) + {_n(B, 2)} × {_n(H, 2)} "
        f"= {_n(B * miring)} + {_n(B * H)} = {_n(nilai)} m² (bidang bawah miring + anak tangga)"
    )


_RAILING_TANGGA = re.compile(r"(?<![a-z])(tangga|stair|hand\s*-?\s*rail)", re.IGNORECASE)


def _railing_tangga(e, k, p):
    # railing tangga: PredefinedType HANDRAIL, nama menyebut tangga, atau miring (tinggi bbox > 1,2 m)
    if (e.get("predefined_type") or "") == "HANDRAIL" or _RAILING_TANGGA.search(e.get("nama") or ""):
        return True
    return (e.get("tinggi") or 0) > 1.2


def _railing_pengaman(e, k, p):
    return not _railing_tangga(e, k, p)


def _panjang_railing(e, p):
    return e["panjang"], f"L = panjang railing = {_n(e['panjang'])} m'"


# ---------------------------------------------------------------- pekerjaan persiapan


def _bersih_lahan(sumber):
    def f(e, p):
        return e["luas"], f"A = luas tapak lantai dasar ({sumber}) = {_n(e['luas'])} m²"

    return f


def _bowplank(e, p):
    L, tambah, keliling = e["porsi_bowplank"]
    nilai = L + tambah
    return nilai, (
        f"L = L_dinding + 8a × L_dinding / K = {_n(L)} + 8 × {_n(p.jarak_bowplank, 2)} × {_n(L)} / {_n(keliling)} "
        f"= {_n(nilai)} m' (K = keliling dinding luar lantai dasar {_n(keliling)} m; bowplank berjarak a dari as dinding)"
    )


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


def _ukuran_pintu(e) -> str:
    if e.get("lebar") and e.get("tinggi"):
        return f" (pintu {_n(e['lebar'], 2)} × {_n(e['tinggi'], 2)} m)"
    return ""


def _kusen_pintu(e, p):
    # keliling kusen pintu: dua tiang + satu ambang atas
    b, h = e["lebar"], e["tinggi"]
    nilai = 2 * h + b
    return nilai, f"L = 2 × H + B = 2 × {_n(h, 2)} + {_n(b, 2)} = {_n(nilai)} m'"


def _kunci_pintu(e, p):
    return 1.0, f"Jumlah = 1 buah per daun pintu{_ukuran_pintu(e)}"


def _engsel_pintu(e, p):
    n = float(p.jumlah_engsel_pintu)
    return n, f"Jumlah = {p.jumlah_engsel_pintu} buah per daun pintu{_ukuran_pintu(e)}"


def _luas_bukaan(e, p):  # pintu / jendela: lebar x tinggi
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


def _dan(*syarat):
    """Gabungan beberapa syarat: semuanya harus terpenuhi."""
    return lambda e, k, p: all(s(e, k, p) for s in syarat)


def _beton(e, k, p):
    # elemen benar-benar beton bertulang (bukan lapisan finishing, profil baja, atau kayu)
    return bukan_beton(e) is None


def _pelat_struktur(e, k, p):
    # pelat beton bertulang; rabat beton / lantai kerja dihitung terpisah (LTK.LANTAI)
    return bukan_beton(e) is None and not e.get("rabat")


def _rabat(e, k, p):
    return bool(e.get("rabat"))


def _tanah_model(kode):
    return lambda e, k, p: pekerjaan_tanah(e) == kode


def _volume_model(uraian):
    def f(e, p):
        return e["volume"], f"V = volume {uraian} dari model = {_n(e['volume'])} m³"

    return f


def _luas_keramik_dinding(e, p):
    return e["luas"], f"A = luas keramik dinding dari model = {_n(e['luas'])} m²"


def _volume_rabat(e, p):
    if e.get("volume"):
        return e["volume"], f"V = volume rabat dari model = {_n(e['volume'])} m³"
    t = e.get("tebal") or p.tebal_lantai_kerja
    v = e["luas"] * t
    return v, f"V = A × t = {_n(e['luas'])} × {_n(t, 2)} = {_n(v)} m³"


def _kolom_struktur(e, k, p):
    # satu fondasi turunan per kolom fisik (pedestal + kolom di atasnya = satu kolom, lihat konteks)
    return kolom_struktur(e) and e.get("fondasi_kolom", True)


def _pasangan(e, k, p):
    # dinding pasangan bata (bukan partisi ringan) yang memerlukan fondasi/sloof di lantai dasar
    return dinding_pasangan(e)


def _sloof(e, k, p):
    return balok_sloof(e)


def _bukan_sloof(e, k, p):
    return not balok_sloof(e)


def _sloof_turunan(e, k, p):
    return bool(e.get("sloof_turunan"))


def _sloof_di_atas_tanah(e, k, p):
    # sloof di atas tanah (bukan di atas batu kali) memerlukan urugan pasir di bawahnya
    return not k.sloof_di_atas_batu_kali


def _menerus_batu_kali(e, k, p):
    return (e.get("predefined_type") or "") in FONDASI_MENERUS and not e.get("menerus_beton")


def _fondasi_beton(e, k, p):
    # footplate / pile cap, atau fondasi menerus yang ditetapkan beton bertulang (sumuran dihitung tersendiri)
    pre = e.get("predefined_type") or ""
    if pre in FONDASI_MENERUS:
        return bool(e.get("menerus_beton"))
    return pre not in SLOOF and not sumuran_model(e)


def _sumuran_model(e, k, p):
    return sumuran_model(e)


def _besi_model_saja(e, p):
    # sumuran masif (beton siklop) tidak bertulang; hanya stek/tulangan yang dimodelkan yang dihitung
    return penulangan.dari_model(e, None, p.batas_kemiringan_dak)


def _tanah_sumuran_model(e, p):
    return tanah.sumuran_model(e["volume"], e.get("tebal") or e.get("tinggi") or 0.0, p)


def _dinding_luar(e, k, p):
    return bool(e.get("eksternal")) and p.jumlah_sisi_cat >= 2


def _bowplank_ada(e, k, p):
    return bool(e.get("porsi_bowplank"))


def _ruang_dasar_tanpa_pelat(e, k, p):
    return e.get("di_lantai_dasar", False) and not k.ada_pelat_dasar


def catatan_bukan_beton(e, k, p) -> str | None:
    """Peringatan untuk elemen yang tidak dihitung sebagai beton (ditampilkan ke pengguna)."""
    kelas = e.get("kelas")
    if kelas == T.ROOF.value and _atap_miring(e, k, p):
        return None  # atap miring memang tidak dihitung sebagai beton
    if kelas not in (T.COLUMN.value, T.BEAM.value, T.SLAB.value, T.ROOF.value, T.STAIR.value):
        return None
    alasan = bukan_beton(e)
    if alasan is None:
        return None
    label = {"COLUMN": "Kolom", "BEAM": "Balok", "SLAB": "Pelat", "ROOF": "Dak", "STAIR": "Tangga"}[kelas]
    if elemen_lain.rangka_atap_nonbeton(e, alasan):
        alasan += "; dianggap bagian rangka atap (sudah termasuk Rangka Atap per m² luas atap)"
    return f"{label} '{e.get('nama')}' tidak dihitung sebagai beton bertulang: {alasan}."


def _nonbeton(e, k, p) -> bool:
    """Elemen struktur yang tidak dihitung sebagai beton bertulang tetap masuk RAB (elemen_lain.item_nonbeton),
    kecuali objek kolom ganda, atap miring (rangka + penutup), dan pelat lapisan finishing bila penutup lantai sudah
    dihitung dari sumber lain: penutup lantai, ruang, atau luas pelat struktur (menghindari hitung ganda)."""
    alasan = bukan_beton(e)
    if alasan is None or (e.get("info_kolom") or {}).get("duplikat"):
        return False
    if e.get("kelas") == T.ROOF.value and _atap_miring(e, k, p):
        return False
    if elemen_lain.lapisan_finishing(e, alasan) and k.sumber_lantai is not None:
        return False  # penutup lantai sudah dihitung dari penutup lantai / ruang / pelat struktur
    if elemen_lain.rangka_atap_nonbeton(e, alasan):
        return False  # gording / kuda-kuda kayu di lantai atap: termasuk rangka atap per m²
    return True


def _pre(*nilai):
    return lambda e, k, p: (e.get("predefined_type") or "") in nilai


def _bukan_pre(*nilai):
    return lambda e, k, p: (e.get("predefined_type") or "") not in nilai


def _fondasi_turunan(e, k: Konteks, p):
    # model tidak memuat fondasi -> fondasi diturunkan dari elemen di lantai dasar (Batasan no. 8)
    return e.get("di_lantai_dasar", False) and not k.ada_fondasi_model


def _jenis_fondasi(*jenis):
    return lambda e, k, p: p.fondasi_kolom_jenis in jenis


# sumuran turunan hanya di bawah kolom struktur; kolom praktis berdiri di atas sloof/fondasi menerus. Pilihan
# jenis fondasi footplate / cakar ayam menurunkan fondasinya sendiri (rules/fondasi_kolom.py).
_sumuran_turunan = _dan(_fondasi_turunan, _kolom_struktur, _jenis_fondasi(FONDASI_MODEL))
# batu kali turunan hanya di bawah dinding pasangan (partisi ringan tidak berfondasi); cakar ayam tanpa batu kali
_batu_kali_turunan = _dan(_fondasi_turunan, _pasangan, _jenis_fondasi(FONDASI_MODEL, FONDASI_FOOTPLATE))


def _fondasi_pilihan(e, k, p):
    return bool(e.get("fondasi_pilihan"))


def _pelat_cakar(e, k, p):
    return bool(e.get("luas_cakar"))


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


# ---------------------------------------------------------------- pekerjaan tanah (KF-4)


def _tanah_batu_kali_dinding(e, p):
    nilai, _ = _batu_kali_dinding(e, p)
    return tanah.fondasi_menerus(p.batu_kali_lebar_bawah, p.batu_kali_tinggi, e["panjang"], nilai, p)


def _tanah_fondasi_menerus(e, p):
    return tanah.fondasi_menerus(e["lebar"], e["tebal"], e["panjang"], e["volume"], p)


def _tanah_footplate(e, p):
    return tanah.footplate(e.get("panjang"), e.get("lebar"), e["tebal"], e["volume"], p)


def _tanah_sumuran(e, p):
    return tanah.sumuran(p.sumuran_diameter, p.sumuran_kedalaman, p.sumuran_jumlah_tiang,
                         p.poer_panjang, p.poer_lebar, p.poer_tebal, p)


def _tanah_tiang(e, p):
    return tanah.tiang(e["volume"], e.get("panjang") or 0.0)


def _tanah_sloof(e, p):
    return tanah.pasir_sloof(e["lebar"], e["panjang"], p)


def _tanah_lantai(rabat):
    return lambda e, p: tanah.lantai_dasar(e["luas"], p, rabat)


def _pelat_dasar(e, k, p):
    # pelat di atas tanah: BASESLAB atau pelat lantai pada lantai dasar
    return (e.get("predefined_type") or "") == "BASESLAB" or e.get("di_lantai_dasar", False)


def _lantai_tanpa_pelat(sumber):
    # lantai dasar tanpa pelat beton: urugan pasir + rabat beton di bawah keramik
    return lambda e, k, p: e.get("di_lantai_dasar", False) and not k.ada_pelat_dasar and k.sumber_lantai == sumber


# ---------------------------------------------------------------- basis aturan

RULES = [
    # ===== Kolom (Rumus 2.10) =====
    Rule("BTN.KOLOM", T.COLUMN, _volume(), ("volume",), syarat=_beton, keterangan="Volume beton kolom"),
    Rule("BSI.KOLOM", T.COLUMN, _pembesian("rasio_besi_kolom"), ("volume",), syarat=_beton,
         keterangan="Pembesian per diameter"),
    Rule("BSK.KOLOM", T.COLUMN, _bekisting_kolom, ("lebar", "tebal", "tinggi"), syarat=_beton,
         keterangan="Bekisting kolom"),
    # Fondasi sumuran di bawah kolom struktur lantai dasar (Rumus 2.36 - 2.39)
    Rule("BTN.SUMURAN", T.COLUMN, _sumuran, syarat=_sumuran_turunan, keterangan="Fondasi sumuran (turunan)"),
    # Pilihan jenis fondasi kolom (Parameter Aturan): footplate turunan atau pipa cakar ayam di bawah kolom
    Rule("FDN.KOLOM", T.COLUMN, fondasi_kolom.item_kolom, syarat=_fondasi_pilihan,
         keterangan="Fondasi kolom sesuai pilihan jenis fondasi"),
    # Pelat cakar ayam (sistem Sedijatmo) di bawah bidang lantai dasar dan tapak dinding lantai dasar
    *[
        Rule("BTN.CAKAR.PELAT", kelas, fondasi_kolom.item_pelat, syarat=_pelat_cakar,
             keterangan="Pelat fondasi cakar ayam (pilihan jenis fondasi)")
        for kelas in (T.SLAB, T.FLOOR, T.SPACE, T.WALL)
    ],
    # ===== Balok (Rumus 2.9) =====
    Rule("BTN.BALOK", T.BEAM, _volume(), ("volume",), syarat=_dan(_beton, _bukan_sloof)),
    Rule("BSI.BALOK", T.BEAM, _pembesian("rasio_besi_balok"), ("volume",), syarat=_dan(_beton, _bukan_sloof)),
    Rule("BSK.BALOK", T.BEAM, _bekisting_balok, ("lebar", "tinggi", "panjang"), syarat=_dan(_beton, _bukan_sloof)),
    # balok yang dimodelkan sebagai sloof (nama "sloof", "tie beam", ...)
    Rule("BTN.SLOOF", T.BEAM, _volume(), ("volume",), syarat=_dan(_beton, _sloof), keterangan="Sloof (balok)"),
    Rule("BSI.SLOOF", T.BEAM, _pembesian("rasio_besi_sloof"), ("volume",), syarat=_dan(_beton, _sloof)),
    Rule("BSK.SLOOF", T.BEAM, _bekisting_sloof_balok, ("tinggi", "panjang"), syarat=_dan(_beton, _sloof)),
    # ===== Pelat lantai (Rumus 2.11 / 2.37) =====
    Rule("BTN.PELAT", T.SLAB, _volume(), ("volume",), syarat=_pelat_struktur),
    Rule("BSI.PELAT", T.SLAB, _pembesian("rasio_besi_pelat"), ("volume",), syarat=_pelat_struktur),
    Rule("BSK.PELAT", T.SLAB, _luas("luas bidang bawah pelat"), ("luas",), syarat=_dan(_pelat_struktur, _pelat_melayang)),
    Rule("LTK.LANTAI", T.SLAB, _volume_rabat, ("luas",), syarat=_rabat,
         keterangan="Rabat beton / lantai kerja (pelat tidak bertulang)"),
    # ===== Urugan, lantai kerja, aanstamping & keramik dinding yang dimodelkan (menggantikan versi turunan) =====
    *[
        Rule(kode, T.EARTHWORK, _volume_model(uraian), ("volume",), syarat=_tanah_model(kode),
             keterangan=f"{uraian.capitalize()} (dimodelkan)")
        for kode, uraian in (
            ("TNH.PASIR.FONDASI", "urugan pasir bawah fondasi"),
            ("TNH.PASIR.SLOOF", "urugan pasir bawah sloof"),
            ("TNH.PASIR.LANTAI", "urugan pasir bawah lantai"),
            ("LTK.FONDASI", "lantai kerja bawah fondasi"),
            ("LTK.LANTAI", "lantai kerja / rabat bawah lantai"),
            ("FDN.AANSTAMPING", "pasangan batu kosong (aanstamping)"),
        )
    ],
    Rule("KRM.DINDING", T.WALL_TILE, _luas_keramik_dinding, ("luas",), keterangan="Keramik dinding (dimodelkan)"),
    # ===== Elemen lain dari model: cladding, kisi, roster, lisplang, nok, talang, waterproofing, lansekap, sanitair =====
    Rule("LAINNYA", T.LAINNYA, elemen_lain.item, keterangan="Elemen lain dari model"),
    # ===== Kolom / balok / tangga / pelat / dak bukan beton bertulang: baja per kg, kayu per m³, finishing = lantai =====
    *[Rule("NONBETON", kelas, elemen_lain.item_nonbeton, syarat=_nonbeton, keterangan="Elemen struktur bukan beton")
      for kelas in (T.COLUMN, T.BEAM, T.STAIR, T.SLAB, T.ROOF)],
    # ===== Atap miring: rangka baja ringan + genteng (Rumus 2.22 / 2.23 / 2.42) =====
    Rule("ATP.RANGKA", T.ROOF, _luas_atap, ("luas",), syarat=_atap_miring, keterangan="Rangka atap baja ringan per m² luas atap"),
    Rule("ATP.PENUTUP", T.ROOF, _luas_atap, ("luas",), syarat=_atap_miring, keterangan="Penutup atap genteng"),
    # ===== Atap datar: dak beton =====
    Rule("BTN.DAK", T.ROOF, _volume(), ("volume",), syarat=_dan(_dak, _beton)),
    Rule("BSI.DAK", T.ROOF, _pembesian("rasio_besi_pelat"), ("volume",), syarat=_dan(_dak, _beton)),
    Rule("BSK.DAK", T.ROOF, _luas("luas bidang bawah dak"), ("luas",), syarat=_dan(_dak, _beton)),
    # ===== Dinding (Rumus 2.17 - 2.19) =====
    Rule("DND.BATA", T.WALL, _luas_dinding, ("luas",), keterangan="Pasangan dinding bata (m²)"),
    Rule("PLS.DINDING", T.WALL, _luas_dinding_kali("jumlah_sisi_plester", "plester"), ("luas",)),
    Rule("ACI.DINDING", T.WALL, _luas_dinding_kali("jumlah_sisi_plester", "acian"), ("luas",)),
    Rule("CAT.DINDING", T.WALL, _cat_interior, ("luas",)),
    Rule("CAT.EKSTERIOR", T.WALL, _cat_eksterior, ("luas",), syarat=_dinding_luar, keterangan="Cat sisi luar dinding luar"),
    # Fondasi batu kali di bawah dinding pasangan lantai dasar (Rumus 2.34)
    Rule("FDN.BATUKALI", T.WALL, _batu_kali_dinding, ("panjang",), syarat=_batu_kali_turunan,
         keterangan="Fondasi batu kali (turunan)"),
    # Sloof di atas fondasi batu kali / di antara footplate bila sloof tidak dimodelkan
    Rule("BTN.SLOOF", T.WALL, _beton_sloof_turunan, ("panjang",), syarat=_sloof_turunan, keterangan="Sloof (turunan)"),
    Rule("BSI.SLOOF", T.WALL, _pembesian_sloof_turunan, ("panjang",), syarat=_sloof_turunan),
    Rule("BSK.SLOOF", T.WALL, _bekisting_sloof_turunan, ("panjang",), syarat=_sloof_turunan),
    # ===== Fondasi yang dimodelkan =====
    Rule("FDN.BATUKALI", T.FOOTING, _volume(), ("volume",), syarat=_menerus_batu_kali,
         keterangan="Fondasi menerus = batu kali"),
    Rule("BTN.SLOOF", T.FOOTING, _volume(), ("volume",), syarat=_pre(*SLOOF)),
    Rule("BSI.SLOOF", T.FOOTING, _pembesian("rasio_besi_sloof"), ("volume",), syarat=_pre(*SLOOF)),
    Rule("BSK.SLOOF", T.FOOTING, _bekisting_sisi, ("tebal", "panjang"), syarat=_pre(*SLOOF)),
    Rule("BTN.FONDASI", T.FOOTING, _volume(), ("volume",), syarat=_fondasi_beton,
         keterangan="Footplate / pile cap / fondasi menerus beton"),
    Rule("BSI.FONDASI", T.FOOTING, _pembesian("rasio_besi_fondasi"), ("volume",), syarat=_fondasi_beton),
    Rule("BSK.FONDASI", T.FOOTING, _bekisting_keliling, ("keliling", "tebal"), syarat=_fondasi_beton),
    Rule("BTN.SUMURAN", T.PILE, _volume(), ("volume",)),
    # sumuran / tiang bor yang dimodelkan sebagai IfcFooting: analisa sumuran (HSPK 2.2.2.2.6), tanpa bekisting
    Rule("BTN.SUMURAN", T.FOOTING, _volume(), ("volume",), syarat=_sumuran_model,
         keterangan="Fondasi sumuran (dimodelkan)"),
    Rule("BSI.FONDASI", T.FOOTING, _besi_model_saja, syarat=_sumuran_model, keterangan="Stek / tulangan sumuran model"),
    # ===== Pintu (susunan HSPK: daun + kusen + kunci + engsel) & jendela =====
    Rule("PTU.DAUN", T.DOOR, _luas_bukaan, ("luas",), keterangan="Luas daun pintu"),
    Rule("PTU.KUSEN", T.DOOR, _kusen_pintu, ("lebar", "tinggi")),
    Rule("PTU.KUNCI", T.DOOR, _kunci_pintu),
    Rule("PTU.ENGSEL", T.DOOR, _engsel_pintu),
    Rule("JDL.JENDELA", T.WINDOW, _luas_bukaan, ("luas",)),
    # ===== Lantai (Rumus 2.12 - 2.13): sumber dipilih preprocessor =====
    Rule("KRM.LANTAI", T.FLOOR, _luas("luas penutup lantai"), ("luas",), syarat=_sumber_lantai("covering")),
    Rule("KRM.LANTAI", T.SPACE, _luas("luas lantai ruang"), ("luas",), syarat=_sumber_lantai("ruang")),
    Rule("KRM.LANTAI", T.SLAB, _luas("asumsi: luas keramik = luas pelat"), ("luas",),
         syarat=_dan(_sumber_lantai("pelat"), _beton)),
    # ===== Keramik dinding ruang basah (Rumus 2.14 - 2.15) =====
    Rule("KRM.DINDING", T.SPACE, _keramik_dinding, ("keliling",), syarat=_ruang_basah),
    # ===== Pekerjaan tanah (KF-4): diturunkan dari fondasi & lantai dasar =====
    Rule("TNH.FONDASI", T.WALL, _tanah_batu_kali_dinding, ("panjang",), syarat=_batu_kali_turunan,
         keterangan="Galian & urugan fondasi batu kali"),
    Rule("TNH.FONDASI", T.FOOTING, _tanah_fondasi_menerus, ("lebar", "tebal", "panjang", "volume"),
         syarat=_menerus_batu_kali),
    Rule("TNH.FONDASI", T.FOOTING, _tanah_footplate, ("tebal", "volume"), syarat=_fondasi_beton),
    Rule("TNH.FONDASI", T.COLUMN, _tanah_sumuran, syarat=_sumuran_turunan, keterangan="Galian sumuran (turunan)"),
    Rule("TNH.FONDASI", T.PILE, _tanah_tiang, ("volume",)),
    Rule("TNH.FONDASI", T.FOOTING, _tanah_sumuran_model, ("volume",), syarat=_sumuran_model),
    Rule("TNH.SLOOF", T.FOOTING, _tanah_sloof, ("lebar", "panjang"), syarat=_dan(_pre(*SLOOF), _sloof_di_atas_tanah)),
    Rule("TNH.SLOOF", T.BEAM, _tanah_sloof, ("lebar", "panjang"), syarat=_dan(_beton, _sloof, _sloof_di_atas_tanah)),
    Rule("TNH.SLOOF", T.WALL, _tanah_sloof_turunan, ("panjang",), syarat=_dan(_sloof_turunan, _sloof_di_atas_tanah)),
    Rule("TNH.LANTAI", T.SLAB, _tanah_lantai(False), ("luas",), syarat=_dan(_pelat_dasar, _beton)),
    Rule("TNH.LANTAI", T.FLOOR, _tanah_lantai(True), ("luas",), syarat=_lantai_tanpa_pelat("covering")),
    Rule("TNH.LANTAI", T.SPACE, _tanah_lantai(True), ("luas",), syarat=_lantai_tanpa_pelat("ruang")),
    # ===== Plafon (Rumus 2.16): sumber dipilih preprocessor =====
    *[
        Rule(kode, kelas, _luas(ket), ("luas",),
             syarat=_dan(_sumber_plafon(sumber), _beton) if kelas == T.SLAB else _sumber_plafon(sumber))
        for kode in ("PLF.RANGKA", "PLF.GYPSUM")
        for kelas, sumber, ket in (
            (T.CEILING, "covering", "luas plafon dari model"),
            (T.SPACE, "ruang", "luas plafon = luas lantai ruang"),
            (T.SLAB, "pelat", "asumsi: luas plafon = luas pelat"),
        )
    ],
    # ===== Tangga beton & railing =====
    Rule("BTN.TANGGA", T.STAIR, _volume(), ("volume",), syarat=_beton, keterangan="Beton tangga"),
    Rule("BSK.TANGGA", T.STAIR, _bekisting_tangga, ("panjang", "lebar", "tinggi"), syarat=_beton),
    Rule("BSI.TANGGA", T.STAIR, _pembesian_tangga, ("volume",), syarat=_beton),
    Rule("RLG.TANGGA", T.RAILING, _panjang_railing, ("panjang",), syarat=_railing_tangga, keterangan="Railing tangga"),
    Rule("RLG.PENGAMAN", T.RAILING, _panjang_railing, ("panjang",), syarat=_railing_pengaman,
         keterangan="Railing pengaman balkon / void"),
    # ===== Pekerjaan persiapan: pembersihan lahan (luas tapak) & bowplank (keliling luar + 8a) =====
    Rule("PSP.BERSIH", T.SLAB, _bersih_lahan("pelat lantai dasar"), ("luas",), syarat=_dan(_pelat_dasar, _beton),
         keterangan="Pembersihan lahan"),
    Rule("PSP.BERSIH", T.SPACE, _bersih_lahan("luas ruang lantai dasar"), ("luas",), syarat=_ruang_dasar_tanpa_pelat,
         keterangan="Pembersihan lahan"),
    Rule("PSP.BOWPLANK", T.WALL, _bowplank, syarat=_bowplank_ada, keterangan="Pengukuran & bowplank"),
]
