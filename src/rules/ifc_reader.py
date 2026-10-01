"""
Parser IFC -> daftar elemen struktural (siap disimpan ke tabel elemen_proyek).
Dipanggil dari estimasi_service.jalankan_estimasi(), TIDAK lagi berjalan otomatis saat di-import.
"""

import ifcopenshell
import ifcopenshell.geom as geom
import ifcopenshell.util.element as element_util
import ifcopenshell.util.shape as shape_util
import ifcopenshell.util.unit as unit_util

STRUCTURAL_TYPES = ["IfcColumn", "IfcBeam", "IfcSlab", "IfcWall", "IfcFooting"]

PSET_CANDIDATES = {
    "IfcWall": ["Qto_WallBaseQuantities", "PSet_Revit_Dimensions"],
    "IfcSlab": ["Qto_SlabBaseQuantities", "PSet_Revit_Dimensions"],
    "IfcBeam": ["Qto_BeamBaseQuantities", "PSet_Revit_Dimensions"],
    "IfcFooting": ["Qto_FootingBaseQuantities", "PSet_Revit_Dimensions"],
    "IfcColumn": ["Qto_ColumnBaseQuantities", "PSet_Revit_Dimensions"],
}


def _get_dimension(element, prop_name, pset_candidates):
    psets = element_util.get_psets(element)
    for pset_name in pset_candidates:
        if pset_name in psets and prop_name in psets[pset_name]:
            value = psets[pset_name][prop_name]
            if value is not None:
                return value
    return None


def _volume_from_geometry(element, settings):
    """Fallback: volume dari mesh 3D. Hasil geometri IfcOpenShell SUDAH dalam meter."""
    try:
        shape = geom.create_shape(settings, element)
        return shape_util.get_volume(shape.geometry)
    except Exception:
        return None


def _nama_lantai(element):
    storey = element_util.get_container(element)
    while storey is not None and not storey.is_a("IfcBuildingStorey"):
        storey = element_util.get_container(storey)
    return storey.Name if storey is not None else None


def extract_elements(ifc_path: str):
    """
    Return (elemen, peringatan).
    Semua nilai sudah dikonversi ke METER / m2 / m3, jadi pset & geometri konsisten.
    """
    model = ifcopenshell.open(ifc_path)
    skala = unit_util.calculate_unit_scale(model)  # meter per 1 satuan panjang proyek

    settings = geom.settings()
    settings.set(settings.USE_WORLD_COORDS, True)

    elemen, peringatan = [], []
    for ifc_type in STRUCTURAL_TYPES:
        kandidat = PSET_CANDIDATES[ifc_type]
        for el in model.by_type(ifc_type):
            panjang = _get_dimension(el, "Length", kandidat)
            luas = _get_dimension(el, "Area", kandidat)
            volume = _get_dimension(el, "Volume", kandidat)

            panjang = panjang * skala if panjang is not None else None
            luas = luas * skala**2 if luas is not None else None
            if volume is not None:
                volume, sumber = volume * skala**3, "pset"
            else:
                volume = _volume_from_geometry(el, settings)
                sumber = "geometry" if volume is not None else "gagal"
                if volume is None:
                    peringatan.append(f"Volume gagal dihitung: {el.is_a()} {el.Name} ({el.GlobalId})")

            elemen.append({
                "global_id": el.GlobalId,
                "ifc_type": ifc_type,
                "predefined_type": getattr(el, "PredefinedType", None),
                "nama": el.Name,
                "lantai": _nama_lantai(el),
                "panjang": panjang,
                "luas": luas,
                "volume": volume,
                "sumber_volume": sumber,
            })
    return elemen, peringatan
