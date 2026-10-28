"""
Sifat elemen yang dipakai bersama preprocessor dan basis aturan.

`bukan_beton(e)` mengenali elemen yang di model IFC terklasifikasi sebagai pelat/balok/kolom tetapi
bukan beton bertulang, sehingga tidak boleh dihitung sebagai beton + besi + bekisting:

- pelat (dan dak) yang terlalu tipis, mis. lapisan keramik/parket 1-2 cm yang dimodelkan sebagai IfcSlab;
- balok/kolom profil baja (WF, IWF, UB, kanal C, hollow, ...), dikenali dari nama profil atau dari
  volume yang jauh lebih kecil dari b x h x L (penampang berongga, bukan persegi pejal);
- balok/kolom yang penampangnya terlalu kecil untuk beton bertulang (mis. gording kayu 8/16);
- pelat/balok/kolom yang namanya menunjukkan kayu atau finishing (mis. "Wood Joist", "Parket").

Batas yang dipakai sama dengan batas wajar beton bertulang di rules/penulangan.py.
"""

import re

from .penulangan import PENAMPANG_MIN_LINIER, TEBAL_MIN_BIDANG

# Isi penampang minimum (V / (b x h x L)). Persegi pejal = 1, lingkaran = 0,785; profil baja WF umumnya < 0,2.
ISI_MIN_BETON = 0.5

_PROFIL_BAJA = re.compile(
    r"(?<![a-z0-9])("
    r"w\d+\s*x\s*\d+|wf|iwf|h-?beam|wide\s*flange|ub|uc|he[abm]|ipe|unp|cnp|lip\s*channel|"
    r"hollow|hss|rhs|shs|chs|steel|baja"
    r")(?![a-z])",
    re.IGNORECASE,
)

# Elemen kayu / finishing (lantai papan, parket, rangka kayu) yang dimodelkan sebagai pelat/balok/kolom.
_KAYU = re.compile(
    r"(?<![a-z])(kayu|wood|timber|joist|parket|parquet|vinyl|carpet|karpet|laminate)(?![a-z])",
    re.IGNORECASE,
)

KELAS_LINIER = ("COLUMN", "BEAM")
KELAS_BIDANG = ("SLAB", "ROOF")
# Tangga beton (pelat miring 10-15 cm + anak tangga) mengisi ± 11-20% kotak L x B x H. Tangga kayu (pijakan
# papan) dan baja (ibu tangga kanal + pelat bordes) hanya ± 0,5-3%.
ISI_MIN_TANGGA = 0.06


def _cm(x: float) -> str:
    return f"{x * 100:.1f}".replace(".", ",")


def tebal_bidang(e: dict) -> float | None:
    t = e.get("tebal")
    if t:
        return t
    if e.get("volume") and e.get("luas"):
        return e["volume"] / e["luas"]
    return None


def penampang_linier(e: dict):
    """(b, h, L) kolom/balok, atau None bila salah satu tidak diketahui."""
    if e.get("kelas") == "COLUMN":
        b, h, L = e.get("lebar"), e.get("tebal"), e.get("tinggi")
    else:
        b, h, L = e.get("lebar"), e.get("tinggi"), e.get("panjang")
    if b and h and L:
        return b, h, L
    return None


def bukan_beton(e: dict) -> str | None:
    """Alasan elemen tidak dihitung sebagai beton bertulang, atau None bila elemen dianggap beton."""
    kelas = e.get("kelas")
    if kelas in KELAS_LINIER + KELAS_BIDANG + ("STAIR",) and _KAYU.search(e.get("nama") or ""):
        return "nama elemen menunjukkan bahan kayu/finishing, bukan beton"
    if kelas == "STAIR":
        if _PROFIL_BAJA.search(e.get("nama") or ""):
            return "nama elemen menunjukkan tangga baja"
        L, B, H, v = e.get("panjang"), e.get("lebar"), e.get("tinggi"), e.get("volume")
        if L and B and H and v and v / (L * B * H) < ISI_MIN_TANGGA:
            return (f"volume hanya {v / (L * B * H) * 100:.0f}% dari L × B × H, kemungkinan tangga baja/kayu "
                    "(ibu tangga + pijakan)")
        return None
    if kelas in KELAS_BIDANG:
        t = tebal_bidang(e)
        if t is not None and t < TEBAL_MIN_BIDANG - 1e-9:
            return f"tebal {_cm(t)} cm < {_cm(TEBAL_MIN_BIDANG)} cm, dianggap lapisan finishing/penutup"
        return None
    if kelas not in KELAS_LINIER:
        return None
    if _PROFIL_BAJA.search(e.get("nama") or ""):
        return "nama elemen menunjukkan profil baja"
    u = penampang_linier(e)
    if u is None:
        return None
    b, h, L = u
    if min(b, h) < PENAMPANG_MIN_LINIER - 1e-9:
        return f"penampang {_cm(b)}/{_cm(h)} cm terlalu kecil untuk beton bertulang (kayu/baja)"
    v = e.get("volume")
    if v:
        isi = v / (b * h * L)
        if isi < ISI_MIN_BETON:
            return (f"volume hanya {isi * 100:.0f}% dari b × h × L, penampang berongga "
                    "(kemungkinan profil baja)")
    return None


def beton(e: dict) -> bool:
    return bukan_beton(e) is None


def kolom_struktur(e: dict) -> bool:
    """Kolom yang memikul beban ke fondasi. Kolom praktis (sisi terkecil ≤ 15 cm, di dalam pasangan
    dinding) berdiri di atas sloof/fondasi menerus sehingga tidak mendapat fondasi sumuran sendiri.
    Bila penampang tidak diketahui, kolom dianggap kolom struktur (aman: fondasi tetap dihitung)."""
    b, h = e.get("lebar"), e.get("tebal")
    if b and h:
        return min(b, h) > 0.15 + 1e-9
    return True


# Balok yang dimodelkan sebagai sloof (Revit sering memodelkan sloof sebagai Structural Framing = IfcBeam).
_SLOOF = re.compile(r"(?<![a-z])(sloof|tie\s*-?\s*beam|ground\s*beam|footing\s*beam|grade\s*beam)(?![a-z])",
                    re.IGNORECASE)
_MENERUS_BATU = re.compile(r"(?<![a-z])(batu|stone|rubble|masonry)(?![a-z])", re.IGNORECASE)
_MENERUS_BETON = re.compile(r"(?<![a-z])(beton|concrete|bertulang|reinforced|footing)(?![a-z])", re.IGNORECASE)

# Dinding pasangan (bata) minimum: 1/2 bata tanpa plester ±11 cm. Partisi ringan (gypsum, GRC) lebih tipis
# dan tidak mendapat fondasi/sloof turunan.
TEBAL_MIN_PASANGAN = 0.10  # m


def balok_sloof(e: dict) -> bool:
    """Balok yang namanya menunjukkan sloof (dihitung sebagai sloof, bukan balok)."""
    return e.get("kelas") == "BEAM" and bool(_SLOOF.search(e.get("nama") or ""))


def dinding_pasangan(e: dict) -> bool:
    t = e.get("tebal")
    return t is None or t >= TEBAL_MIN_PASANGAN - 1e-9


def menerus_beton_dari_nama(nama: str | None) -> bool:
    """Fondasi menerus dari model: beton bertulang bila namanya menyebut beton/concrete/footing dan tidak
    menyebut batu. Tanpa petunjuk = pasangan batu kali (praktik rumah tinggal)."""
    teks = nama or ""
    if _MENERUS_BATU.search(teks):
        return False
    return bool(_MENERUS_BETON.search(teks))
