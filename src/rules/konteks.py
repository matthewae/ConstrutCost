"""
Preprocessor rule engine: membaca kumpulan elemen satu model sekaligus lalu menetapkan fakta
tingkat bangunan yang dibutuhkan aturan, misalnya:
- lantai mana yang merupakan lantai dasar (untuk fondasi turunan),
- apakah model sudah memodelkan fondasi / sloof sendiri (agar elemen turunan tidak dihitung ganda),
- dari mana luas lantai dan plafon diambil (penutup lantai/plafon -> ruang -> pelat),
- jenis fondasi menerus yang dimodelkan (batu kali atau beton bertulang),
- jumlah lantai (ukuran sloof turunan), tebal pelat yang dicor bersama balok, dan keliling dinding luar
  lantai dasar (bowplank).

Fakta per elemen ditulis langsung ke dict elemen (diubah di tempat) supaya bisa dibaca aturan dan
pengelompokan tipe penulangan: `di_lantai_dasar`, `menerus_beton`, `balok_sloof`, `sloof_turunan`,
`tebal_pelat_monolit`, `porsi_bowplank`.
"""

from dataclasses import dataclass
from statistics import median

from klasifikasi import ElementType

from .parameter import MENERUS_BATU_KALI, MENERUS_BETON, PARAMETER_DEFAULT, ukuran_sloof
from .sifat import balok_sloof, beton, dinding_pasangan, menerus_beton_dari_nama

# Lantai dengan elevasi di bawah batas ini dianggap level fondasi, bukan lantai dasar.
BATAS_ELEVASI_FONDASI = -0.5  # m
# Balok ring / latei (b <= 15 cm dan h <= 20 cm) umumnya tidak dicor bersama pelat.
RING_BALOK = (0.15, 0.20)


@dataclass(frozen=True)
class Konteks:
    ada_fondasi_model: bool
    elevasi_lantai_dasar: float | None
    sumber_lantai: str | None  # "covering" | "ruang" | "pelat" | None
    sumber_plafon: str | None  # "covering" | "ruang" | "pelat" | None
    ada_pelat_dasar: bool = False  # lantai dasar sudah berupa pelat beton (tidak perlu rabat beton)
    jumlah_lantai: int = 1
    ada_sloof_model: bool = False  # sloof dimodelkan (IfcFooting FOOTING_BEAM atau balok bernama sloof)
    ada_menerus_beton: bool = False  # fondasi menerus model = beton bertulang (berfungsi sebagai sloof)
    sloof_di_atas_batu_kali: bool = False  # sloof duduk di atas batu kali (tanpa urugan pasir di bawahnya)
    tebal_pelat_monolit: float | None = None  # m, tebal tipikal pelat/dak beton yang dicor bersama balok
    keliling_luar_dasar: float = 0.0  # m, panjang dinding luar lantai dasar
    ada_info_dinding_luar: bool = False  # model menandai dinding luar (Pset_WallCommon.IsExternal)


def _ada(elemen, kelas: ElementType) -> bool:
    return any(e["kelas"] == kelas.value for e in elemen)


def _menerus(e) -> bool:
    return e["kelas"] == ElementType.FOOTING.value and (e.get("predefined_type") or "") == "STRIP_FOOTING"


def _jenis_menerus(e, parameter) -> bool:
    """True bila fondasi menerus ini beton bertulang."""
    if parameter.fondasi_menerus_jenis == MENERUS_BETON:
        return True
    if parameter.fondasi_menerus_jenis == MENERUS_BATU_KALI:
        return False
    return menerus_beton_dari_nama(e.get("nama"))


def siapkan_konteks(elemen: list, parameter=None) -> Konteks:
    """Bangun Konteks dan tulis fakta per elemen (diubah di tempat)."""
    parameter = parameter or PARAMETER_DEFAULT
    struktur = (ElementType.WALL.value, ElementType.COLUMN.value, ElementType.SLAB.value)
    elev_struktur = {
        e["elevasi_lantai"]
        for e in elemen
        if e["elevasi_lantai"] is not None and e["kelas"] in struktur
    }
    di_atas_fondasi = [x for x in elev_struktur if x >= BATAS_ELEVASI_FONDASI]
    calon = di_atas_fondasi or list(elev_struktur)
    elev_dasar = min(calon) if calon else None
    # jumlah lantai = level yang memuat dinding/kolom (level dak/atap yang hanya berisi pelat tidak dihitung)
    jumlah_lantai = max(1, len({
        e["elevasi_lantai"] for e in elemen
        if e["elevasi_lantai"] is not None and e["elevasi_lantai"] >= BATAS_ELEVASI_FONDASI
        and e["kelas"] in (ElementType.WALL.value, ElementType.COLUMN.value)
    }))

    for e in elemen:
        e["di_lantai_dasar"] = (
            elev_dasar is not None
            and e["elevasi_lantai"] is not None
            and abs(e["elevasi_lantai"] - elev_dasar) < 1e-6
        )

    ada_ruang = _ada(elemen, ElementType.SPACE)
    # lapisan finishing yang dimodelkan sebagai IfcSlab bukan sumber luas lantai/plafon
    ada_pelat = any(e["kelas"] == ElementType.SLAB.value and beton(e) for e in elemen)

    def sumber(kelas_covering):
        if _ada(elemen, kelas_covering):
            return "covering"
        if ada_ruang:
            return "ruang"
        if ada_pelat:
            return "pelat"
        return None

    # ---- fondasi menerus dan sloof yang dimodelkan
    ada_fondasi_model = _ada(elemen, ElementType.FOOTING) or _ada(elemen, ElementType.PILE)
    for e in elemen:
        if _menerus(e):
            e["menerus_beton"] = _jenis_menerus(e, parameter)
    ada_menerus_beton = any(e.get("menerus_beton") for e in elemen if _menerus(e))
    ada_menerus_batu = any(not e.get("menerus_beton") for e in elemen if _menerus(e))
    for e in elemen:
        if e["kelas"] == ElementType.BEAM.value:
            e["balok_sloof"] = balok_sloof(e)
    ada_sloof_model = any(
        (e["kelas"] == ElementType.FOOTING.value and (e.get("predefined_type") or "") == "FOOTING_BEAM")
        or balok_sloof(e)
        for e in elemen
    )

    # ---- sloof turunan: di bawah dinding pasangan lantai dasar bila sloof belum dimodelkan dan
    #      fondasi menerus model bukan beton bertulang (fondasi menerus beton sudah berfungsi sebagai sloof)
    perlu_sloof = not ada_sloof_model and not ada_menerus_beton
    b_sloof, h_sloof, ket_sloof = ukuran_sloof(parameter, jumlah_lantai)
    for e in elemen:
        if e["kelas"] != ElementType.WALL.value:
            continue
        e["sloof_turunan"] = (
            [b_sloof, h_sloof, ket_sloof]
            if perlu_sloof and e["di_lantai_dasar"] and dinding_pasangan(e) and e.get("panjang")
            else None
        )

    # ---- tebal pelat yang dicor bersama balok (bekisting sisi balok = h - t)
    tebal = [
        e["tebal"]
        for e in elemen
        if e.get("tebal") and beton(e)
        and (
            (e["kelas"] == ElementType.SLAB.value and not e["di_lantai_dasar"]
             and (e.get("predefined_type") or "") != "BASESLAB")
            or (e["kelas"] == ElementType.ROOF.value and e.get("kemiringan") is not None
                and e["kemiringan"] < parameter.batas_kemiringan_dak)
        )
    ]
    t_monolit = median(tebal) if tebal and parameter.bekisting_balok_monolit else None
    for e in elemen:
        if e["kelas"] != ElementType.BEAM.value:
            continue
        b, h = e.get("lebar"), e.get("tinggi")
        ring = b and h and b <= RING_BALOK[0] + 1e-9 and h <= RING_BALOK[1] + 1e-9
        e["tebal_pelat_monolit"] = (
            t_monolit
            if t_monolit and h and not ring and not balok_sloof(e) and h - t_monolit >= 0.5 * h - 1e-9
            else None
        )

    # ---- bowplank: keliling dinding luar lantai dasar + 8a (berlaku untuk denah siku apa pun)
    luar = [
        e for e in elemen
        if e["kelas"] == ElementType.WALL.value and e["di_lantai_dasar"] and e.get("eksternal")
        and dinding_pasangan(e) and e.get("panjang")
    ]
    keliling = sum(e["panjang"] for e in luar)
    tambahan = 8 * parameter.jarak_bowplank
    id_luar = {id(e) for e in luar}
    for e in elemen:
        if e["kelas"] == ElementType.WALL.value:
            e["porsi_bowplank"] = (
                [e["panjang"], tambahan * e["panjang"] / keliling, keliling]
                if id(e) in id_luar and keliling else None
            )

    return Konteks(
        ada_fondasi_model=ada_fondasi_model,
        elevasi_lantai_dasar=elev_dasar,
        sumber_lantai=sumber(ElementType.FLOOR),
        sumber_plafon=sumber(ElementType.CEILING),
        ada_pelat_dasar=any(
            e["kelas"] == ElementType.SLAB.value
            and ((e.get("predefined_type") or "") == "BASESLAB" or e["di_lantai_dasar"])
            and beton(e)
            for e in elemen
        ),
        jumlah_lantai=jumlah_lantai,
        ada_sloof_model=ada_sloof_model,
        ada_menerus_beton=ada_menerus_beton,
        sloof_di_atas_batu_kali=not ada_fondasi_model or ada_menerus_batu,
        tebal_pelat_monolit=t_monolit,
        keliling_luar_dasar=keliling,
        ada_info_dinding_luar=any(
            e.get("eksternal") is not None for e in elemen if e["kelas"] == ElementType.WALL.value
        ),
    )
