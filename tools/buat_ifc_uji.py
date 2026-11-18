#!/usr/bin/env python3
"""File uji KNF-1: rumah tinggal 3 lantai ~50 MB. Elemen struktur tanpa Qto (jalur geometri, kasus terberat)
ditambah perabot bermesh padat (penyebab umum ukuran file besar pada model rumah dari Revit/ArchiCAD).

    python tools/buat_ifc_uji.py rumah_50mb.ifc 50
"""
import sys, numpy as np
import ifcopenshell.api as api

def main(path, target_mb=50):
    f = api.run("project.create_file", version="IFC4")
    proj = api.run("root.create_entity", f, ifc_class="IfcProject", name="Rumah Uji 50MB")
    api.run("unit.assign_unit", f, length={"is_metric": True, "raw": "METERS"}, area={"is_metric": True, "raw": "METERS"},
            volume={"is_metric": True, "raw": "METERS"})
    model = api.run("context.add_context", f, context_type="Model")
    body = api.run("context.add_context", f, context_type="Model", context_identifier="Body", target_view="MODEL_VIEW", parent=model)
    site = api.run("root.create_entity", f, ifc_class="IfcSite"); gedung = api.run("root.create_entity", f, ifc_class="IfcBuilding")
    api.run("aggregate.assign_object", f, products=[site], relating_object=proj)
    api.run("aggregate.assign_object", f, products=[gedung], relating_object=site)
    rng = np.random.default_rng(1)

    def tempat(el, x, y, z, rot=0):
        m = np.eye(4); c, s = np.cos(rot), np.sin(rot)
        m[:3, :3] = [[c, -s, 0], [s, c, 0], [0, 0, 1]]; m[:3, 3] = (x, y, z)
        api.run("geometry.edit_object_placement", f, product=el, matrix=m)

    def kotak(kelas, nama, L, T, H, x, y, z, rot=0, **kw):
        el = api.run("root.create_entity", f, ifc_class=kelas, name=nama, **kw)
        rep = api.run("geometry.add_wall_representation", f, context=body, length=L, height=H, thickness=T)
        api.run("geometry.assign_representation", f, product=el, representation=rep)
        tempat(el, x, y, z, rot); return el

    lantai = []
    for i, nama in enumerate(["Lantai 1", "Lantai 2", "Lantai 3"]):
        st = api.run("root.create_entity", f, ifc_class="IfcBuildingStorey", name=nama); st.Elevation = i * 3.5
        api.run("aggregate.assign_object", f, products=[st], relating_object=gedung); lantai.append(st)
        isi = []
        z = i * 3.5
        for gx in range(6):
            for gy in range(5):
                isi.append(kotak("IfcColumn", f"K1 30x30 L{i+1}-{gx}{gy}", 0.3, 0.3, 3.5, gx * 3.0, gy * 3.0, z))
        for gy in range(5):
            for gx in range(5):
                isi.append(kotak("IfcBeam", f"B1 25x40 X L{i+1}", 3.0, 0.25, 0.4, gx * 3.0, gy * 3.0, z + 3.1))
        for gx in range(6):
            for gy in range(4):
                isi.append(kotak("IfcBeam", f"B1 25x40 Y L{i+1}", 3.0, 0.25, 0.4, gx * 3.0, gy * 3.0, z + 3.1, np.pi / 2))
        for k in range(40):
            isi.append(kotak("IfcWall", f"Dinding bata L{i+1}-{k}", 3.0, 0.15, 3.1, (k % 5) * 3.0, (k // 5) % 5 * 3.0 + 0.1, z))
        for k in range(6):
            sl = api.run("root.create_entity", f, ifc_class="IfcSlab", name=f"Pelat 12 cm L{i+1}-{k}", predefined_type="FLOOR")
            rep = api.run("geometry.add_slab_representation", f, context=body, depth=0.12,
                          polyline=[(0.0, 0.0), (7.5, 0.0), (7.5, 5.0), (0.0, 5.0)])
            api.run("geometry.assign_representation", f, product=sl, representation=rep)
            tempat(sl, (k % 2) * 7.5, (k // 2) * 5.0, z); isi.append(sl)
        for k in range(12):
            d = api.run("root.create_entity", f, ifc_class="IfcDoor", name=f"Pintu P1 L{i+1}-{k}")
            d.OverallWidth, d.OverallHeight = 0.9, 2.1; isi.append(d)
            w = api.run("root.create_entity", f, ifc_class="IfcWindow", name=f"Jendela J1 L{i+1}-{k}")
            w.OverallWidth, w.OverallHeight = 1.2, 1.2; isi.append(w)
        api.run("spatial.assign_container", f, products=isi, relating_structure=st)

    # perabot bermesh padat sampai ukuran target
    titik_per = 6000
    k = 0
    while True:
        pts = rng.random((titik_per, 3)).round(4).tolist()
        idx = (rng.integers(1, titik_per + 1, (titik_per * 2, 3))).tolist()
        pl = f.createIfcCartesianPointList3D(pts)
        fs = f.createIfcTriangulatedFaceSet(pl, None, None, idx, None)
        rep = f.createIfcShapeRepresentation(body, "Body", "Tessellation", [fs])
        fur = api.run("root.create_entity", f, ifc_class="IfcFurniture", name=f"Perabot {k}")
        fur.Representation = f.createIfcProductDefinitionShape(None, None, [rep])
        api.run("spatial.assign_container", f, products=[fur], relating_structure=lantai[k % 3])
        k += 1
        if k % 20 == 0:
            f.write(path)
            import os
            if os.path.getsize(path) >= target_mb * 1e6:
                break
    print(path, k, "perabot")

if __name__ == "__main__":
    main(sys.argv[1], float(sys.argv[2]) if len(sys.argv) > 2 else 50)
