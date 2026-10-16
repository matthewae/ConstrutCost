"""
KF-2: klasifikasi entitas IFC ke tipe elemen bangunan (ElementType pada class diagram).

Satu entitas IFC hanya masuk ke satu kelas. Aturan khusus:
- IfcSlab yang menjadi bagian (agregasi) dari IfcRoof, atau ber-PredefinedType ROOF -> ROOF.
- IfcRoof yang sudah dipecah menjadi IfcSlab tidak dihitung lagi (menghindari hitung ganda);
  IfcRoof tanpa pecahan tetapi punya geometri sendiri -> ROOF.
- IfcCovering CEILING -> CEILING (plafon), FLOORING -> FLOOR (penutup lantai); jenis lain diabaikan.
- IfcSpace EXTERNAL / GFA diabaikan karena bukan ruang dalam bangunan.
- IfcStairFlight -> STAIR; IfcStair hanya bila tidak dipecah menjadi bagian (bagian dihitung sendiri).
- IfcRailing -> RAILING.
"""

import re
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
    STAIR = "STAIR"
    RAILING = "RAILING"
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
    ElementType.STAIR: "Tangga",
    ElementType.RAILING: "Railing",
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
    "IfcStairFlight",
    "IfcStair",
    "IfcRailing",
]

# Entitas bangunan yang tidak dihitung rule engine: dilaporkan ke pengguna (ringkasan import & peringatan)
# beserta contoh namanya, supaya pengguna bisa menilai apakah pekerjaannya perlu ditambahkan manual.
TIPE_TIDAK_DIHITUNG = {
    "IfcMember": "batang rangka",
    "IfcPlate": "plat / panel",
    "IfcCurtainWall": "dinding tirai",
    "IfcRamp": "ramp",
    "IfcBuildingElementProxy": "elemen generik",
}
# Keterangan tambahan supaya pengguna tidak menghitung ganda.
_CATATAN_TIDAK_DIHITUNG = {
    "IfcMember": "rangka atap baja ringan sudah dihitung per m² luas atap",
}


def _nama_tipe(nama) -> str:
    # 'Rangka Carport 50x50:123456' -> 'Rangka Carport 50x50' (id unik Revit dibuang)
    return re.sub(r":\d+$", "", (nama or "").strip()) or "(tanpa nama)"


def _contoh(entitas, n=3) -> list:
    hitung = {}
    for e in entitas:
        k = _nama_tipe(getattr(e, "Name", None))
        hitung[k] = hitung.get(k, 0) + 1
    return [k for k, _ in sorted(hitung.items(), key=lambda x: -x[1])[:n]]


def hitung_tidak_dihitung(model) -> dict:
    """{'94 batang rangka (IfcMember)': {'jumlah', 'contoh', 'catatan'}, ...} untuk entitas bangunan yang
    tidak dihitung rule engine, termasuk IfcCovering selain plafon/penutup lantai (mis. CLADDING)."""
    hasil = {}

    def tambah(label, tipe, entitas):
        if entitas:
            hasil[f"{label} ({tipe})"] = {
                "jumlah": len(entitas), "contoh": _contoh(entitas), "catatan": _CATATAN_TIDAK_DIHITUNG.get(tipe),
            }

    for tipe, label in TIPE_TIDAK_DIHITUNG.items():
        try:
            entitas = model.by_type(tipe)
        except Exception:  # tipe tidak ada di skema file
            entitas = []
        tambah(label, tipe, entitas)
    tambah("penutup lain", "IfcCovering",
           [c for c in model.by_type("IfcCovering") if predefined_type(c) not in _COVERING])
    return hasil


def teks_tidak_dihitung(data: dict) -> str:
    """Satu kalimat ringkas: '94 batang rangka (IfcMember, mis. 'A', 'B'; rangka atap ... ), 50 elemen ...'."""
    bagian = []
    for label, d in data.items():
        tipe = label[label.rfind("(") + 1:-1]
        nama = label[:label.rfind("(")].strip()
        isi = [tipe]
        if d["contoh"]:
            isi.append("mis. " + ", ".join(f"'{c}'" for c in d["contoh"]))
        teks = f"{d['jumlah']} {nama} ({'; '.join([', '.join(isi[:2])] + ([d['catatan']] if d['catatan'] else []))})"
        bagian.append(teks)
    return "; ".join(bagian)


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
    if tipe_ifc == "IfcStairFlight":
        return ElementType.STAIR
    if tipe_ifc == "IfcStair":
        # tangga yang dipecah menjadi IfcStairFlight / IfcSlab (bordes) dihitung dari bagiannya
        if _atap_dipecah(entity) or entity.Representation is None:
            return None
        return ElementType.STAIR
    if tipe_ifc == "IfcRailing":
        return ElementType.RAILING
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
