"""
Penulangan rinci per tipe elemen (KF-4, Rumus 2.30 - 2.33).

Elemen struktur dikelompokkan menjadi TIPE berdasarkan penampangnya, seperti daftar tipe pada
gambar kerja dan sheet "Perhitungan Besi" RAB konsultan: Kolom K1 20/25, Balok B1 15/20,
Sloof S1 20/30, Pelat P1 t = 12 cm, dan seterusnya. Setiap tipe punya konfigurasi tulangan
(mis. 6 D13 + sengkang Ø10-150) yang dapat diubah pengguna. Kebutuhan besi dihitung per
diameter:

    W_m     = π d² / 4 × 7850 × 10⁻⁶                       (Rumus 2.30 - 2.31, kg/m')
    L_eff   = L_batang + ΔL_kait (+ lewatan bila > 12 m)    (Rumus 2.32)
    W_total = Σ (W_m × L_eff × n) × 1,05                    (Rumus 2.33, 5% sisa potongan)

Konvensi: diameter < 12 mm dianggap baja polos BjTP (simbol Ø), ≥ 12 mm baja ulir/sirip BjTS
(simbol D). Harga satuan mengikuti item HSPK yang sesuai (lihat database/seed_data.py).
Model IFC arsitektur umumnya tidak memuat IfcReinforcingBar, sehingga konfigurasi tulangan
diambil dari tipe (bawaan di bawah, bisa diubah per proyek).
"""

import math
from dataclasses import dataclass

KOLOM, BALOK, SLOOF, PELAT, DAK, FONDASI = "KOLOM", "BALOK", "SLOOF", "PELAT", "DAK", "FONDASI"
LINIER = (KOLOM, BALOK, SLOOF)  # tulangan memanjang + sengkang
BIDANG = (PELAT, DAK, FONDASI)  # tulangan anyaman dua arah
URUTAN = (FONDASI, SLOOF, KOLOM, BALOK, PELAT, DAK)

NAMA_KELOMPOK = {
    KOLOM: "Kolom", BALOK: "Balok", SLOOF: "Sloof", PELAT: "Pelat Lantai",
    DAK: "Pelat Atap (Dak)", FONDASI: "Fondasi Telapak",
}
AWALAN_KODE = {KOLOM: "K", BALOK: "B", SLOOF: "S", PELAT: "P", DAK: "D", FONDASI: "F"}
KODE_PEKERJAAN = {
    KOLOM: "BSI.KOLOM", BALOK: "BSI.BALOK", SLOOF: "BSI.SLOOF",
    PELAT: "BSI.PELAT", DAK: "BSI.DAK", FONDASI: "BSI.FONDASI",
}

DIAMETER_STANDAR = (6, 8, 10, 12, 13, 16, 19, 22, 25)  # mm
DENSITAS_BAJA = 7850  # kg/m³, SNI 07-2052-2002
FAKTOR_SISA = 1.05  # Rumus 2.33
BATAS_ULIR = 12  # mm
PANJANG_BATANG = 12.0  # m, panjang batang di pasaran
KAIT_UTAMA = 12  # × d, kait standar 90° (SNI 2847:2019 ps. 25.3.1)
LEWATAN = 40  # × d, sambungan lewatan per 12 m (disederhanakan)
KAIT_SENGKANG_MIN = 0.075  # m, kait 135° = 6d ≥ 75 mm (SNI 2847:2019 ps. 25.3.2)

# Batas wajar elemen beton bertulang. Di bawah batas ini elemen dianggap bukan beton bertulang
# (mis. lapisan finishing yang dimodelkan sebagai IfcSlab, gording kayu/baja sebagai IfcBeam):
# tulangan rinci tidak dihitung dan rule engine memakai asumsi rasio kg/m³.
TEBAL_MIN_BIDANG = 0.07  # m
PENAMPANG_MIN_LINIER = 0.10  # m, sisi terkecil kolom/balok/sloof (2 x selimut + tulangan)

# Selimut beton (SNI 2847:2019 Tabel 20.6.1.3.1): balok/kolom 40 mm, pelat 20 mm,
# sloof bersentuhan tanah ≤ D16 40 mm, fondasi dicor langsung di atas tanah 75 mm.
SELIMUT = {KOLOM: 0.040, BALOK: 0.040, SLOOF: 0.040, PELAT: 0.020, DAK: 0.020, FONDASI: 0.075}


def berat_per_m(d_mm: float) -> float:
    """Rumus 2.30 - 2.31: berat tulangan per meter (kg/m')."""
    return math.pi * d_mm**2 / 4 * DENSITAS_BAJA * 1e-6


def ulir(d_mm: float) -> bool:
    return d_mm >= BATAS_ULIR


def label_d(d_mm: float) -> str:
    return f"{'D' if ulir(d_mm) else 'Ø'}{d_mm:g}"


def jenis_baja(d_mm: float) -> str:
    return "Ulir (BjTS)" if ulir(d_mm) else "Polos (BjTP)"


def kode_pekerjaan(kelompok: str, d_mm: float) -> str:
    return f"{KODE_PEKERJAAN[kelompok]}.{'U' if ulir(d_mm) else 'P'}"


def _n(x: float, d: int = 3) -> str:
    return f"{x:,.{d}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _cm(x: float) -> str:
    return f"{x * 100:.0f}"


@dataclass
class Penulangan:
    kelompok: str
    n_utama: int = 0  # linier: jumlah tulangan memanjang
    d_utama: float = 0.0  # mm
    jarak_utama: float = 0.0  # m, bidang: jarak antar tulangan
    lapis: int = 1  # bidang: 1 = bawah saja, 2 = atas & bawah
    d_sengkang: float = 0.0  # mm, linier
    jarak_sengkang: float = 0.0  # m, linier
    selimut: float = 0.04  # m

    def ringkas(self) -> str:
        if self.kelompok in LINIER:
            return (
                f"{self.n_utama} {label_d(self.d_utama)}, sengkang "
                f"{label_d(self.d_sengkang)}-{self.jarak_sengkang * 1000:.0f}"
            )
        lapis = "2 lapis (atas & bawah)" if self.lapis == 2 else "1 lapis"
        return f"{label_d(self.d_utama)}-{self.jarak_utama * 1000:.0f} dua arah, {lapis}"


def label_tipe(kelompok: str, kode: str, b: float | None, h: float | None) -> str:
    """mis. 'Kolom K1 (20/25)', 'Pelat Lantai P1 (t = 12 cm)'."""
    nama = NAMA_KELOMPOK.get(kelompok, kelompok)
    if kelompok in LINIER and b and h:
        return f"{nama} {kode} ({_cm(b)}/{_cm(h)})"
    if h:
        return f"{nama} {kode} (t = {_cm(h)} cm)"
    return f"{nama} {kode}"


# ---------------------------------------------------------------- elemen -> kelompok


def ukuran_elemen(e: dict, batas_kemiringan_dak: float = 5.0):
    """(kelompok, b, h, L) elemen struktur bertulang, atau None.
    Linier: b x h = penampang, L = panjang/tinggi batang. Bidang: h = tebal, b & L = None."""
    kelas, pre = e.get("kelas"), e.get("predefined_type") or ""
    if kelas == "COLUMN":
        return KOLOM, e.get("lebar"), e.get("tebal"), e.get("tinggi")
    if kelas == "BEAM":
        return BALOK, e.get("lebar"), e.get("tinggi"), e.get("panjang")
    if kelas == "FOOTING" and pre == "FOOTING_BEAM":
        return SLOOF, e.get("lebar"), e.get("tebal"), e.get("panjang")
    if kelas == "FOOTING" and pre != "STRIP_FOOTING":
        return FONDASI, None, e.get("tebal"), None
    if kelas == "SLAB":
        return PELAT, None, e.get("tebal"), None
    if kelas == "ROOF":
        teta = e.get("kemiringan")
        if teta is not None and teta < batas_kemiringan_dak:
            return DAK, None, e.get("tebal"), None
    return None


def kunci_tipe(e: dict, batas_kemiringan_dak: float = 5.0):
    """Kunci pengelompokan tipe: (kelompok, b cm, h cm). None bila penampang tidak diketahui."""
    u = ukuran_elemen(e, batas_kemiringan_dak)
    if u is None:
        return None
    kelompok, b, h, _ = u
    if not bertulang(kelompok, b, h):
        return None
    if kelompok in LINIER:
        return kelompok, round(b * 100), round(h * 100)
    return kelompok, 0, round(h * 100)


def bertulang(kelompok: str, b, h) -> bool:
    """Penampang cukup besar untuk beton bertulang (lihat TEBAL_MIN_BIDANG, PENAMPANG_MIN_LINIER)."""
    if not h or h <= 0:
        return False
    if kelompok in LINIER:
        return bool(b) and min(b, h) >= PENAMPANG_MIN_LINIER - 1e-9
    return h >= TEBAL_MIN_BIDANG - 1e-9


def bawaan(kelompok: str, b: float | None, h: float | None) -> Penulangan:
    """Konfigurasi awal tipikal rumah tinggal <= 2 lantai (asumsi, dapat diubah pengguna).
    Mengacu praktik RAB konsultan (mis. RAP SMK N 6 Bandung: kolom 20/25 = 6 D13 + Ø10-150,
    ring balok 15/20 = 4 Ø10 + Ø8-150) dan batas minimum SNI 2847:2019."""
    c = SELIMUT[kelompok]
    b = b or 0.0
    h = h or 0.0
    if kelompok == KOLOM:
        if min(b, h) <= 0.15:  # kolom praktis
            return Penulangan(KOLOM, 4, 10, d_sengkang=6, jarak_sengkang=0.15, selimut=c)
        if b * h <= 0.04 + 1e-9:
            return Penulangan(KOLOM, 4, 13, d_sengkang=8, jarak_sengkang=0.15, selimut=c)
        if b * h <= 0.0625 + 1e-9:
            return Penulangan(KOLOM, 6, 13, d_sengkang=10, jarak_sengkang=0.15, selimut=c)
        return Penulangan(KOLOM, 8, 16, d_sengkang=10, jarak_sengkang=0.15, selimut=c)
    if kelompok == BALOK:
        if b <= 0.15 and h <= 0.20 + 1e-9:  # ring balok / balok latei
            return Penulangan(BALOK, 4, 10, d_sengkang=8, jarak_sengkang=0.15, selimut=c)
        if h <= 0.30 + 1e-9:
            return Penulangan(BALOK, 4, 13, d_sengkang=8, jarak_sengkang=0.15, selimut=c)
        if h <= 0.40 + 1e-9:
            return Penulangan(BALOK, 6, 13, d_sengkang=10, jarak_sengkang=0.15, selimut=c)
        return Penulangan(BALOK, 6, 16, d_sengkang=10, jarak_sengkang=0.15, selimut=c)
    if kelompok == SLOOF:
        if b * h <= 0.03 + 1e-9:
            return Penulangan(SLOOF, 4, 13, d_sengkang=8, jarak_sengkang=0.15, selimut=c)
        if b * h <= 0.05 + 1e-9:
            return Penulangan(SLOOF, 6, 13, d_sengkang=10, jarak_sengkang=0.15, selimut=c)
        return Penulangan(SLOOF, 6, 16, d_sengkang=10, jarak_sengkang=0.15, selimut=c)
    if kelompok in (PELAT, DAK):
        if h <= 0.15 + 1e-9:
            return Penulangan(kelompok, d_utama=10, jarak_utama=0.15, lapis=2, selimut=c)
        return Penulangan(kelompok, d_utama=13, jarak_utama=0.15, lapis=2, selimut=c)
    if kelompok == FONDASI:
        if h <= 0.30 + 1e-9:
            return Penulangan(FONDASI, d_utama=13, jarak_utama=0.15, lapis=1, selimut=c)
        return Penulangan(FONDASI, d_utama=16, jarak_utama=0.15, lapis=2, selimut=c)
    raise ValueError(f"Kelompok penulangan tidak dikenal: {kelompok}")


# ---------------------------------------------------------------- validasi


class PenulanganTidakValid(ValueError):
    """Konfigurasi tulangan ditolak. Pesannya siap ditampilkan ke pengguna."""


def validasi(p: Penulangan) -> None:
    def cek_d(d, nama):
        if not 6 <= d <= 32:
            raise PenulanganTidakValid(f"Diameter {nama} harus 6 - 32 mm.")

    if not 0.015 <= p.selimut <= 0.10:
        raise PenulanganTidakValid("Selimut beton harus 15 - 100 mm.")
    cek_d(p.d_utama, "tulangan utama")
    if p.kelompok in LINIER:
        if not 2 <= p.n_utama <= 40:
            raise PenulanganTidakValid("Jumlah tulangan utama harus 2 - 40 batang.")
        cek_d(p.d_sengkang, "sengkang")
        if not 0.05 <= p.jarak_sengkang <= 0.30:
            raise PenulanganTidakValid("Jarak sengkang harus 50 - 300 mm.")
    else:
        if not 0.05 <= p.jarak_utama <= 0.40:
            raise PenulanganTidakValid("Jarak tulangan harus 50 - 400 mm.")
        if p.lapis not in (1, 2):
            raise PenulanganTidakValid("Jumlah lapis tulangan harus 1 atau 2.")


# ---------------------------------------------------------------- hitung


@dataclass
class ItemBesi:
    kode: str  # kode pekerjaan, mis. BSI.KOLOM.U
    berat: float  # kg, sudah termasuk sisa 5%
    rumus: str
    uraian: str  # mis. "Tulangan utama 6 D13"
    diameter: float  # mm


def _rumus_wm(d: float) -> str:
    return f"W_m {label_d(d)} = π × {d:g}² / 4 × 7850 × 10⁻⁶ = {_n(berat_per_m(d))} kg/m'"


def _linier(kelompok, b, h, L, p: Penulangan) -> list:
    out = []
    # tulangan utama (Rumus 2.32 - 2.33)
    d = p.d_utama
    kait = 2 * KAIT_UTAMA * d / 1000
    leff = L + kait
    sambungan = max(0, math.ceil(leff / PANJANG_BATANG) - 1)
    lewatan = sambungan * LEWATAN * d / 1000
    leff += lewatan
    wm = berat_per_m(d)
    berat = p.n_utama * leff * wm * FAKTOR_SISA
    tambah = f" + {sambungan} × {LEWATAN}d" if sambungan else ""
    out.append(ItemBesi(
        kode_pekerjaan(kelompok, d), berat,
        f"{_rumus_wm(d)}; L_eff = L + 2 × {KAIT_UTAMA}d{tambah} = {_n(L)} + {_n(kait + lewatan)} = {_n(leff)} m; "
        f"W = n × L_eff × W_m × 1,05 = {p.n_utama} × {_n(leff)} × {_n(wm)} × 1,05 = {_n(berat, 2)} kg",
        f"Tulangan utama {p.n_utama} {label_d(d)}", d,
    ))
    # sengkang
    ds, s, c = p.d_sengkang, p.jarak_sengkang, p.selimut
    bi, hi = max(b - 2 * c, b / 2), max(h - 2 * c, h / 2)
    kait_s = 2 * max(6 * ds / 1000, KAIT_SENGKANG_MIN)
    panjang = 2 * bi + 2 * hi + kait_s
    jumlah = math.floor(L / s + 1e-9) + 1
    wm = berat_per_m(ds)
    berat = jumlah * panjang * wm * FAKTOR_SISA
    out.append(ItemBesi(
        kode_pekerjaan(kelompok, ds), berat,
        f"{_rumus_wm(ds)}; n = L / s + 1 = {_n(L)} / {_n(s, 2)} + 1 = {jumlah} buah; "
        f"panjang 1 sengkang = 2(b - 2c) + 2(h - 2c) + kait = 2 × {_n(bi)} + 2 × {_n(hi)} + {_n(kait_s)} "
        f"= {_n(panjang)} m; W = {jumlah} × {_n(panjang)} × {_n(wm)} × 1,05 = {_n(berat, 2)} kg",
        f"Sengkang {label_d(ds)}-{s * 1000:.0f}", ds,
    ))
    return out


def _bidang(kelompok, e, h, p: Penulangan) -> list:
    d, s, c = p.d_utama, p.jarak_utama, p.selimut
    wm = berat_per_m(d)
    kait = 2 * KAIT_UTAMA * d / 1000
    P, B = e.get("panjang"), e.get("lebar")
    if P and B and P > 0 and B > 0:
        # persegi: hitung batang tiap arah
        nx = math.floor(max(B - 2 * c, 0) / s + 1e-9) + 1
        ny = math.floor(max(P - 2 * c, 0) / s + 1e-9) + 1
        lx, ly = max(P - 2 * c, 0) + kait, max(B - 2 * c, 0) + kait
        panjang = (nx * lx + ny * ly) * p.lapis
        uraian_l = (
            f"arah L: {nx} × {_n(lx)} m, arah B: {ny} × {_n(ly)} m, × {p.lapis} lapis = {_n(panjang)} m"
        )
    else:
        # bentuk tidak reguler: panjang tulangan per m² = 1/s tiap arah
        A = e.get("luas") or 0.0
        if not A and e.get("volume") and h:
            A = e["volume"] / h
        if A <= 0:
            return []
        panjang = 2 * A / s * p.lapis
        uraian_l = f"2 arah × A / s × lapis = 2 × {_n(A)} / {_n(s, 2)} × {p.lapis} = {_n(panjang)} m"
    berat = panjang * wm * FAKTOR_SISA
    lapis = "atas & bawah" if p.lapis == 2 else "1 lapis"
    return [ItemBesi(
        kode_pekerjaan(kelompok, d), berat,
        f"{_rumus_wm(d)}; panjang total {uraian_l}; W = {_n(panjang)} × {_n(wm)} × 1,05 = {_n(berat, 2)} kg",
        f"Tulangan {label_d(d)}-{s * 1000:.0f} dua arah, {lapis}", d,
    )]


def hitung(e: dict, penulangan: Penulangan | None = None, batas_kemiringan_dak: float = 5.0) -> list:
    """Daftar ItemBesi untuk satu elemen; [] bila dimensinya tidak cukup (pakai rasio)."""
    u = ukuran_elemen(e, batas_kemiringan_dak)
    if u is None:
        return []
    kelompok, b, h, L = u
    if not bertulang(kelompok, b, h):
        return []
    p = penulangan or bawaan(kelompok, b, h)
    if kelompok in LINIER:
        if not (L and L > 0):
            return []
        return _linier(kelompok, b, h, L, p)
    return _bidang(kelompok, e, h, p)
