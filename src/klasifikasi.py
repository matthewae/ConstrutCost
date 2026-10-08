"""
KF-2: klasifikasi entitas IFC ke tipe elemen bangunan (ElementType pada class diagram).

Satu entitas IFC hanya masuk ke satu kelas. Aturan khusus:
- IfcSlab yang menjadi bagian (agregasi) dari IfcRoof, atau ber-PredefinedType ROOF -> ROOF.
- IfcRoof yang sudah dipecah menjadi IfcSlab tidak dihitung lagi (menghindari hitung ganda);
  IfcRoof tanpa pecahan tetapi punya geometri sendiri -> ROOF.
- IfcCovering CEILING -> CEILING (plafon), FLOORING -> FLOOR (penutup lantai); jenis lain diabaikan.
- IfcSpace EXTERNAL / GFA diabaikan karena bukan ruang dalam bangunan.
"""

from enum import Enum

import ifcopenshell.util.element as element_util


class ElementType(str, Enum):
    COLUMN = "COLUMN"
    BEAM = "BEAM"
    SLAB = "SLAB"
    ROOF = "ROOF"
    WALL = "WALL"
    FOOTING = "FOOTING"
    PILE = "PILE"
    DOOR = "DOOR"
    WINDOW = "WINDOW"
    FLOOR = "FLOOR"
    CEILING = "CEILING"
    SPACE = "SPACE"
    UNKNOWN = "UNKNOWN"


LABEL = {
    ElementType.COLUMN: "Kolom",
    ElementType.BEAM: "Balok",
    ElementType.SLAB: "Pelat lantai",
    ElementType.ROOF: "Atap",
    ElementType.WALL: "Dinding",
    ElementType.FOOTING: "Fondasi",
    ElementType.PILE: "Tiang / sumuran",
    ElementType.DOOR: "Pintu",
    ElementType.WINDOW: "Jendela",
    ElementType.FLOOR: "Penutup lantai",
    ElementType.CEILING: "Plafon",
    ElementType.SPACE: "Ruang",
    ElementType.UNKNOWN: "Tidak dikenal",
}

# Urutan pembacaan entitas IFC (by_type sudah mencakup subtipe, mis. IfcWallStandardCase).
TIPE_IFC_DIBACA = [
    "IfcFooting",
    "IfcPile",
    "IfcColumn",
    "IfcBeam",
    "IfcSlab",
    "IfcRoof",
    "IfcWall",
    "IfcDoor",
    "IfcWindow",
    "IfcCovering",
    "IfcSpace",
]

_LANGSUNG = {
    "IfcFooting": ElementType.FOOTING,
    "IfcPile": ElementType.PILE,
    "IfcColumn": ElementType.COLUMN,
    "IfcBeam": ElementType.BEAM,
    "IfcWall": ElementType.WALL,
    "IfcDoor": ElementType.DOOR,
    "IfcWindow": ElementType.WINDOW,
}
_COVERING = {"CEILING": ElementType.CEILING, "FLOORING": ElementType.FLOOR}
_SPACE_DIABAIKAN = {"EXTERNAL", "GFA"}


def predefined_type(entity):
    """PredefinedType (IFC4) / ShapeType (IfcRoof IFC2x3), dalam huruf besar, atau None."""
    for attr in ("PredefinedType", "ShapeType"):
        try:
            nilai = getattr(entity, attr)
        except AttributeError:
            continue
        return str(nilai).upper() if nilai else None
    return None


def _induk_atap(entity) -> bool:
    induk = element_util.get_aggregate(entity)
    return induk is not None and induk.is_a("IfcRoof")


def _atap_dipecah(roof) -> bool:
    return any(rel.RelatedObjects for rel in getattr(roof, "IsDecomposedBy", []) or [])


def klasifikasi(entity, tipe_ifc: str):
    """Return ElementType untuk entitas, atau None bila entitas tidak dihitung."""
    if tipe_ifc in _LANGSUNG:
        return _LANGSUNG[tipe_ifc]
    pre = predefined_type(entity)
    if tipe_ifc == "IfcSlab":
        if pre == "ROOF" or _induk_atap(entity):
            return ElementType.ROOF
        return ElementType.SLAB
    if tipe_ifc == "IfcRoof":
        if _atap_dipecah(entity) or entity.Representation is None:
            return None
        return ElementType.ROOF
    if tipe_ifc == "IfcCovering":
        return _COVERING.get(pre)
    if tipe_ifc == "IfcSpace":
        return None if pre in _SPACE_DIABAIKAN else ElementType.SPACE
    return None


def kumpulkan_elemen(model):
    """Generator (entity, tipe_ifc, ElementType) untuk semua entitas yang dihitung. Tanpa duplikat."""
    sudah = set()
    for tipe_ifc in TIPE_IFC_DIBACA:
        for entity in model.by_type(tipe_ifc):
            if entity.id() in sudah:
                continue
            kelas = klasifikasi(entity, tipe_ifc)
            if kelas is None:
                continue
            sudah.add(entity.id())
            yield entity, tipe_ifc, kelas
