"""
Pekerjaan tanah (KF-4): galian, urugan pasir, lantai kerja, dan urugan tanah kembali.

Volume diturunkan dari fondasi yang sudah dihitung rule engine (batu kali, footplate, sumuran,
sloof) dan dari lantai dasar, mengikuti cara hitung RAB konsultan:

    Fondasi batu kali  : galian  = (B_bawah + 2 rk) × (H + t_pasir) × L
                         pasir   = B_bawah × t_pasir × L
                         urugan kembali = galian − V_batu_kali − V_pasir
    Footplate          : galian  = (P + 2 rk) × (B + 2 rk) × D,   D = kedalaman dasar + t_lantai_kerja
                         lantai kerja = P × B × t_lantai_kerja
                         urugan kembali = galian − V_footplate − V_lantai_kerja
    Sumuran + poer     : galian  = π d²/4 × H_sumuran + (P + 2 rk)(L + 2 rk) × T_poer
                         urugan kembali = galian poer − V_poer
    Sloof              : pasir   = b × t_pasir × L
    Lantai dasar       : pasir   = A × t_pasir;  rabat beton = A × t_lantai_kerja bila lantai dasar
                         bukan pelat beton

rk = ruang kerja galian tiap sisi. Semua angka asumsi ada di rules/parameter.py.
Item galian dipilih menurut kedalaman (HSPK 1.2.1.1.1 / 1.2.1.1.4 / 1.2.1.1.6).
"""

import math

from .item import ItemHasil


def _n(x: float, d: int = 3) -> str:
    return f"{x:,.{d}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def kode_galian(kedalaman: float) -> str:
    if kedalaman <= 1.0 + 1e-9:
        return "TNH.GALIAN.1"
    if kedalaman <= 2.0 + 1e-9:
        return "TNH.GALIAN.2"
    return "TNH.GALIAN.3"


def _urug_kembali(galian: float, terisi: float, rincian: str) -> ItemHasil | None:
    sisa = galian - terisi
    if sisa <= 1e-9:
        return None
    return ItemHasil(
        "TNH.URUG.KEMBALI", sisa,
        f"V = V_galian − V_terisi = {_n(galian)} − ({rincian}) = {_n(sisa)} m³",
    )


def fondasi_menerus(B: float, H: float, L: float, V_fondasi: float, p) -> list:
    """Galian, urugan pasir, dan urugan kembali fondasi batu kali (menerus)."""
    rk, tp = p.ruang_kerja_galian, p.tebal_pasir_fondasi
    lebar = B + 2 * rk
    dalam = H + tp
    galian = lebar * dalam * L
    pasir = B * tp * L
    out = [
        ItemHasil(kode_galian(dalam), galian,
                  f"V = (B_bawah + 2 × rk) × (H + t_pasir) × L = ({_n(B, 2)} + 2 × {_n(rk, 2)}) × "
                  f"({_n(H, 2)} + {_n(tp, 2)}) × {_n(L)} = {_n(galian)} m³"),
        ItemHasil("TNH.PASIR.FONDASI", pasir,
                  f"V = B_bawah × t_pasir × L = {_n(B, 2)} × {_n(tp, 2)} × {_n(L)} = {_n(pasir)} m³"),
    ]
    urug = _urug_kembali(galian, V_fondasi + pasir, f"batu kali {_n(V_fondasi)} + pasir {_n(pasir)}")
    return out + ([urug] if urug else [])


def footplate(P: float | None, B: float | None, t: float, V_fondasi: float, p) -> list:
    """Galian, lantai kerja, dan urugan kembali fondasi telapak."""
    rk, lk = p.ruang_kerja_galian, p.tebal_lantai_kerja
    if P and B:
        alas = P * B
        luas_galian = (P + 2 * rk) * (B + 2 * rk)
        uraian_luas = f"(P + 2 rk) × (B + 2 rk) = ({_n(P, 2)} + {_n(2 * rk, 2)}) × ({_n(B, 2)} + {_n(2 * rk, 2)})"
    else:  # bentuk tidak reguler: luas alas dari volume / tebal
        alas = V_fondasi / t
        sisi = math.sqrt(alas)
        luas_galian = (sisi + 2 * rk) ** 2
        uraian_luas = f"(√A + 2 rk)² = ({_n(sisi, 2)} + {_n(2 * rk, 2)})²"
    dalam = max(p.kedalaman_fondasi_telapak, t) + lk
    galian = luas_galian * dalam
    v_lk = alas * lk
    out = [
        ItemHasil(kode_galian(dalam), galian,
                  f"V = {uraian_luas} × D = {_n(luas_galian)} × {_n(dalam, 2)} = {_n(galian)} m³ "
                  f"(D = kedalaman dasar fondasi + lantai kerja)"),
        ItemHasil("LTK.FONDASI", v_lk, f"V = A_alas × t = {_n(alas)} × {_n(lk, 2)} = {_n(v_lk)} m³"),
    ]
    urug = _urug_kembali(galian, V_fondasi + v_lk, f"footplate {_n(V_fondasi)} + lantai kerja {_n(v_lk)}")
    return out + ([urug] if urug else [])


def sumuran(d: float, H: float, n: int, P: float, L: float, T: float, p) -> list:
    """Galian sumuran (+ lubang poer) dan urugan kembali sekitar poer, per titik kolom."""
    rk = p.ruang_kerja_galian
    v_tiang = n * math.pi * d**2 / 4 * H
    v_lubang_poer = (P + 2 * rk) * (L + 2 * rk) * T
    galian = v_tiang + v_lubang_poer
    out = [ItemHasil(
        kode_galian(H + T), galian,
        f"V = n × π d²/4 × H + (P + 2 rk)(L + 2 rk) × T = {n} × π × {_n(d, 2)}²/4 × {_n(H, 2)} + "
        f"{_n(P + 2 * rk, 2)} × {_n(L + 2 * rk, 2)} × {_n(T, 2)} = {_n(galian)} m³",
    )]
    v_poer = P * L * T
    urug = _urug_kembali(v_lubang_poer, v_poer, f"poer {_n(v_poer)}")
    if urug:
        urug.rumus = urug.rumus.replace("V_galian", "V_galian poer")
        out.append(urug)
    return out


def tiang(V: float, panjang: float) -> list:
    return [ItemHasil(kode_galian(panjang), V, f"V = volume tiang = {_n(V)} m³ (kedalaman {_n(panjang, 2)} m)")]


def pasir_sloof(b: float, L: float, p) -> list:
    v = b * p.tebal_pasir_sloof * L
    return [ItemHasil("TNH.PASIR.SLOOF", v,
                      f"V = b × t_pasir × L = {_n(b, 2)} × {_n(p.tebal_pasir_sloof, 2)} × {_n(L)} = {_n(v)} m³")]


def lantai_dasar(A: float, p, rabat: bool) -> list:
    v = A * p.tebal_pasir_lantai
    out = [ItemHasil("TNH.PASIR.LANTAI", v,
                     f"V = A × t_pasir = {_n(A)} × {_n(p.tebal_pasir_lantai, 2)} = {_n(v)} m³")]
    if rabat:
        r = A * p.tebal_lantai_kerja
        out.append(ItemHasil("LTK.LANTAI", r,
                             f"V = A × t_rabat = {_n(A)} × {_n(p.tebal_lantai_kerja, 2)} = {_n(r)} m³ "
                             "(lantai dasar tidak dimodelkan sebagai pelat beton)"))
    return out
