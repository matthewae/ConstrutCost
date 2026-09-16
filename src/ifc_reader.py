import ifcopenshell
import ifcopenshell.util.element as element_util
import ifcopenshell.util.unit as unit_util
import ifcopenshell.util.shape as shape_util
import ifcopenshell.geom as geom

model = ifcopenshell.open("data/Duplex_A_20110907.ifc")

PSET_CANDIDATES = {
    "IfcWall": ["Qto_WallBaseQuantities", "PSet_Revit_Dimensions"],
    "IfcSlab": ["Qto_SlabBaseQuantities", "PSet_Revit_Dimensions"],
    "IfcBeam": ["Qto_BeamBaseQuantities", "PSet_Revit_Dimensions"],
    "IfcFooting": ["Qto_FootingBaseQuantities", "PSet_Revit_Dimensions"],
    "IfcColumn": ["Qto_ColumnBaseQuantities", "PSet_Revit_Dimensions"],
}

settings = geom.settings()
settings.set(settings.USE_WORLD_COORDS, True)

def get_dimension(element, prop_name, pset_candidates):
    psets = element_util.get_psets(element)
    for pset_name in pset_candidates:
        if pset_name in psets and prop_name in psets[pset_name]:
            value = psets[pset_name][prop_name]
            if value is not None:
                return value
    return None

def get_volume_from_geometry(element):
    """Fallback: hitung volume langsung dari mesh 3D kalau tidak ada di property set."""
    try:
        shape = geom.create_shape(settings, element)
        return shape_util.get_volume(shape.geometry)
    except Exception as e:
        print(f"  [!] Gagal hitung geometri untuk {element.GlobalId}: {e}")
        return None

def extract_elements(model, ifc_type):
    candidates = PSET_CANDIDATES.get(ifc_type, ["PSet_Revit_Dimensions"])
    results = []
    for elem in model.by_type(ifc_type):
        volume = get_dimension(elem, "Volume", candidates)
        source = "pset"
        if volume is None:
            volume = get_volume_from_geometry(elem)
            source = "geometry" if volume is not None else "gagal"

        results.append({
            "id": elem.GlobalId,
            "name": elem.Name,
            "type": ifc_type,
            "length": get_dimension(elem, "Length", candidates),
            "area": get_dimension(elem, "Area", candidates),
            "volume": volume,
            "volume_source": source,
        })
    return results

# --- Jalankan untuk semua tipe, tampilkan yang tadinya bolong ---
for ifc_type in ["IfcColumn", "IfcBeam", "IfcSlab", "IfcWall", "IfcFooting"]:
    data = extract_elements(model, ifc_type)
    from_geom = [d for d in data if d["volume_source"] == "geometry"]
    failed = [d for d in data if d["volume_source"] == "gagal"]
    print(f"{ifc_type}: {len(data)} elemen | {len(from_geom)} dari geometri | {len(failed)} gagal total")
    for d in from_geom:
        print(f"   -> {d['name'][:40]}: volume dihitung dari mesh = {d['volume']}")

for slab in model.by_type("IfcSlab"):
    print(f"{slab.Name[:50]:50} | PredefinedType: {slab.PredefinedType}")