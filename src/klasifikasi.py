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
- IfcBuildingElementProxy urugan pasir / lantai kerja / aanstamping -> EARTHWORK (pekerjaan yang dimodelkan
  menggantikan versi turunan); proxy lain dilaporkan sebagai tidak dihitung.
- IfcCovering keramik dinding (CLADDING bernama keramik dinding / backsplash) -> WALL_TILE.
- Semua IfcElement lain yang punya bentuk -> LAINNYA (cladding, kisi, roster, lisplang, nok, talang, waterproofing,
  beton lansekap, media tanam, sanitair, atau elemen tanpa padanan HSPK; lihat elemen_lain.py), kecuali batang
  rangka atap dan penutup atap IfcCovering ROOFING yang sudah termasuk pekerjaan rangka / penutup atap per m²,
  serta bagian dari elemen yang sudah dihitung.
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
    EARTHWORK = "EARTHWORK"  # urugan pasir, lantai kerja, aanstamping yang dimodelkan
    WALL_TILE = "WALL_TILE"  # keramik dinding yang dimodelkan sebagai IfcCovering
    LAINNYA = "LAINNYA"  # cladding, kisi, lisplang, nok, talang, waterproofing, lansekap, sanitair, ... (elemen_lain.py)
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
    ElementType.EARTHWORK: "Urugan & lantai kerja",
    ElementType.WALL_TILE: "Keramik dinding",
    ElementType.LAINNYA: "Elemen lain (fasad, atap, lansekap, sanitair)",
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
    "IfcBuildingElementProxy",
    "IfcElement",  # sisanya: elemen lain (elemen_lain.py)
]

# Entitas bangunan yang tidak dihitung rule engine: dilaporkan ke pengguna (ringkasan import & peringatan)
# beserta contoh namanya, supaya pengguna bisa menilai apakah pekerjaannya perlu ditambahkan manual.
# Semua IfcElement yang tidak dihitung dilaporkan; label menurut kelas IFC (kelas induk dicocokkan berurutan).
TIPE_TIDAK_DIHITUNG = {
    "IfcMember": "batang rangka",
    "IfcPlate": "plat / panel",
    "IfcCurtainWall": "dinding tirai",
    "IfcRamp": "ramp",
    "IfcBuildingElementProxy": "elemen generik",
    "IfcCovering": "penutup lain",
    "IfcShadingDevice": "peneduh / roster",
    "IfcReinforcingMesh": "jaring tulangan (wiremesh)",
    "IfcPipeSegment": "pipa / talang",
    "IfcFlowSegment": "pipa / saluran",
    "IfcFlowTerminal": "perlengkapan MEP / sanitair",
    "IfcDistributionElement": "elemen MEP",
    "IfcFurnishingElement": "perabot",
    "IfcBuildingElement": "elemen bangunan lain",
    "IfcElement": "elemen lain",
}
# Bukan pekerjaan fisik tersendiri: lubang/tonjolan, elemen virtual, tulangan (dibaca terpisah), rakitan.
_TIDAK_DILAPORKAN = ("IfcFeatureElement", "IfcVirtualElement", "IfcReinforcingBar", "IfcElementAssembly")
# Keterangan tambahan supaya pengguna tidak menghitung ganda.
_CATATAN_TIDAK_DIHITUNG = {}
_CATATAN_TERMASUK = {
    "rangka_atap": "sudah termasuk pekerjaan rangka atap per m² luas atap (bukan hitung ganda)",
    "penutup_atap": "sudah termasuk pekerjaan penutup atap per m² luas atap",
    "bagian_tangga": "sudah termasuk pekerjaan tangga",
}
# Catatan menurut nama elemen: pekerjaan yang sebenarnya sudah dihitung dari elemen lain (jangan ditambah lagi).
_CATATAN_NAMA = []  # talang, waterproofing, cladding, dll. kini dihitung otomatis (elemen_lain.py)


def _catatan(tipe: str, entitas) -> str | None:
    nama = [getattr(e, "Name", None) or "" for e in entitas]
    isi = [_CATATAN_TIDAK_DIHITUNG[tipe]] if tipe in _CATATAN_TIDAK_DIHITUNG else []
    isi += [teks for pola, teks in _CATATAN_NAMA if any(pola.search(n) for n in nama)]
    return "; ".join(isi) or None


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
                "jumlah": len(entitas), "contoh": _contoh(entitas), "catatan": _catatan(tipe, entitas),
            }

    from elemen_lain import LABEL_TERMASUK, TERMASUK, kenali

    dihitung = {entity.id() for entity, _t, _k in kumpulkan_elemen(model)}
    per_tipe, termasuk = {}, {}
    for e in model.by_type("IfcElement"):
        if e.id() in dihitung or any(e.is_a(t) for t in _TIDAK_DILAPORKAN):
            continue
        if any(rel.RelatedObjects for rel in getattr(e, "IsDecomposedBy", None) or ()):
            continue  # dihitung/dilaporkan dari bagiannya (mis. IfcRoof dipecah menjadi IfcSlab)
        tipe = next(t for t in TIPE_TIDAK_DIHITUNG if e.is_a(t))
        jenis = kenali(e) if getattr(e, "Representation", None) is not None else None
        if jenis in TERMASUK:  # sudah termasuk pekerjaan lain (rangka atap, penutup atap, bagian tangga)
            termasuk.setdefault((jenis, tipe), []).append(e)
        else:
            per_tipe.setdefault(tipe, []).append(e)
    for (jenis, tipe), entitas in termasuk.items():
        hasil[f"{LABEL_TERMASUK[jenis].lower()} ({tipe})"] = {
            "jumlah": len(entitas), "contoh": _contoh(entitas), "catatan": _CATATAN_TERMASUK[jenis]}
    for tipe, label in TIPE_TIDAK_DIHITUNG.items():
        tambah(label, tipe, per_tipe.get(tipe, []))
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
# Pekerjaan tanah / fondasi yang dimodelkan sebagai elemen generik (dikenali dari ObjectType atau nama).
POLA_TANAH = re.compile(
    r"urug\w*[\s_]*pasir|pasir[\s_]*urug|sand[\s_]*(bed|fill)|lantai[\s_]*kerja|lean[\s_]*concrete|blinding"
    r"|aanstamping|anstamping|batu[\s_]*kosong|hardcore",
    re.IGNORECASE,
)
POLA_KERAMIK_DINDING = re.compile(r"keramik[\s_]*dinding|dinding[\s_]*keramik|backsplash|wall[\s_]*til", re.IGNORECASE)
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
        if pre in _COVERING:
            return _COVERING[pre]
        teks = f"{getattr(entity, 'ObjectType', None) or ''} {entity.Name or ''}"
        return ElementType.WALL_TILE if POLA_KERAMIK_DINDING.search(teks) else None
    if tipe_ifc == "IfcBuildingElementProxy":
        teks = f"{getattr(entity, 'ObjectType', None) or ''} {entity.Name or ''}"
        return ElementType.EARTHWORK if POLA_TANAH.search(teks) else None
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
    if tipe_ifc == "IfcElement":
        return _elemen_lain(entity)
    return None


def _elemen_lain(entity):
    """LAINNYA untuk IfcElement berbentuk yang belum masuk kelas lain, kecuali yang sudah termasuk pekerjaan lain
    (rangka / penutup atap) atau bukan pekerjaan fisik tersendiri (lubang, elemen virtual, tulangan, rakitan)."""
    from elemen_lain import TERMASUK, kenali

    if any(entity.is_a(t) for t in _TIDAK_DILAPORKAN) or getattr(entity, "Representation", None) is None:
        return None
    if any(rel.RelatedObjects for rel in getattr(entity, "IsDecomposedBy", None) or ()):
        return None  # dihitung dari bagiannya
    return None if kenali(entity) in TERMASUK else ElementType.LAINNYA


def kumpulkan_elemen(model):
    """Generator (entity, tipe_ifc, ElementType) untuk semua entitas yang dihitung. Tanpa duplikat."""
    sudah = set()
    for tipe_ifc in TIPE_IFC_DIBACA:
        for entity in model.by_type(tipe_ifc):
            if entity.id() in sudah:
                continue
            if tipe_ifc == "IfcElement":
                induk = element_util.get_aggregate(entity)
                if induk is not None and induk.id() in sudah:
                    continue  # bagian elemen yang sudah dihitung (mis. baluster railing, anak tangga)
            kelas = klasifikasi(entity, tipe_ifc)
            if kelas is None:
                continue
            sudah.add(entity.id())
            yield entity, tipe_ifc, kelas
