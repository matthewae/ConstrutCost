"""
Preprocessor rule engine: membaca kumpulan elemen satu model sekaligus lalu menetapkan fakta
tingkat bangunan yang dibutuhkan aturan, misalnya:
- lantai mana yang merupakan lantai dasar (untuk fondasi turunan),
- apakah model sudah memodelkan fondasi sendiri (agar fondasi turunan tidak dihitung ganda),
- dari mana luas lantai dan plafon diambil (penutup lantai/plafon -> ruang -> pelat).
"""

from dataclasses import dataclass

from klasifikasi import ElementType

# Lantai dengan elevasi di bawah batas ini dianggap level fondasi, bukan lantai dasar.
BATAS_ELEVASI_FONDASI = -0.5  # m


@dataclass(frozen=True)
class Konteks:
    ada_fondasi_model: bool
    elevasi_lantai_dasar: float | None
    sumber_lantai: str | None  # "covering" | "ruang" | "pelat" | None
    sumber_plafon: str | None  # "covering" | "ruang" | "pelat" | None
    ada_pelat_dasar: bool = False  # lantai dasar sudah berupa pelat beton (tidak perlu rabat beton)


def _ada(elemen, kelas: ElementType) -> bool:
    return any(e["kelas"] == kelas.value for e in elemen)


def siapkan_konteks(elemen: list) -> Konteks:
    """Bangun Konteks dan tandai setiap elemen dengan `di_lantai_dasar` (diubah di tempat)."""
    elev_struktur = {
        e["elevasi_lantai"]
        for e in elemen
        if e["elevasi_lantai"] is not None
        and e["kelas"] in (ElementType.WALL.value, ElementType.COLUMN.value, ElementType.SLAB.value)
    }
    di_atas_fondasi = [x for x in elev_struktur if x >= BATAS_ELEVASI_FONDASI]
    calon = di_atas_fondasi or list(elev_struktur)
    elev_dasar = min(calon) if calon else None

    for e in elemen:
        e["di_lantai_dasar"] = (
            elev_dasar is not None
            and e["elevasi_lantai"] is not None
            and abs(e["elevasi_lantai"] - elev_dasar) < 1e-6
        )

    ada_ruang = _ada(elemen, ElementType.SPACE)
    ada_pelat = _ada(elemen, ElementType.SLAB)

    def sumber(kelas_covering):
        if _ada(elemen, kelas_covering):
            return "covering"
        if ada_ruang:
            return "ruang"
        if ada_pelat:
            return "pelat"
        return None

    return Konteks(
        ada_fondasi_model=_ada(elemen, ElementType.FOOTING) or _ada(elemen, ElementType.PILE),
        elevasi_lantai_dasar=elev_dasar,
        sumber_lantai=sumber(ElementType.FLOOR),
        sumber_plafon=sumber(ElementType.CEILING),
        ada_pelat_dasar=any(
            e["kelas"] == ElementType.SLAB.value
            and ((e.get("predefined_type") or "") == "BASESLAB" or e["di_lantai_dasar"])
            for e in elemen
        ),
    )
