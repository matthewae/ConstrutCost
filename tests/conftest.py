from pathlib import Path

import numpy as np
import pytest

DATA = Path(__file__).resolve().parents[1] / "data"
AC20 = DATA / "AC20-FZK-Haus.ifc"  # ArchiCAD, IFC4, BaseQuantities, atap miring 30 derajat
DUPLEX = DATA / "Duplex_A_20110907.ifc"  # Revit 2011, IFC2x3, PSet_Revit_Dimensions, fondasi menerus
STRUKTURAL = DATA / "SampleStructuralModel.ifc"  # Revit 2025, IFC4, satuan panjang milimeter


@pytest.fixture(scope="session")
def ekstrak_cache():
    """Ekstraksi tiap file contoh cukup sekali per sesi pengujian."""
    from ifc_reader import buka_dan_validasi, ekstrak_elemen

    cache = {}

    def ambil(path):
        if path not in cache:
            info = buka_dan_validasi(path)
            cache[path] = (info, *ekstrak_elemen(info.model))
        return cache[path]

    return ambil


@pytest.fixture
def ifc_sintetis(tmp_path):
    """Model kecil buatan sendiri: satuan mm, satu lantai, satu dinding diputar 90 derajat tanpa Qto
    (memaksa jalur geometri), plus satu pelat atap miring tanpa Qto."""
    import ifcopenshell.api as api

    f = api.run("project.create_file", version="IFC4")
    proj = api.run("root.create_entity", f, ifc_class="IfcProject", name="Uji")
    api.run(
        "unit.assign_unit",
        f,
        length={"is_metric": True, "raw": "MILLIMETERS"},
        area={"is_metric": True, "raw": "METERS"},
        volume={"is_metric": True, "raw": "METERS"},
    )
    model = api.run("context.add_context", f, context_type="Model")
    body = api.run(
        "context.add_context", f, context_type="Model", context_identifier="Body",
        target_view="MODEL_VIEW", parent=model,
    )
    site = api.run("root.create_entity", f, ifc_class="IfcSite")
    gedung = api.run("root.create_entity", f, ifc_class="IfcBuilding")
    lantai = api.run("root.create_entity", f, ifc_class="IfcBuildingStorey", name="Lantai 1")
    lantai.Elevation = 0.0
    api.run("aggregate.assign_object", f, products=[site], relating_object=proj)
    api.run("aggregate.assign_object", f, products=[gedung], relating_object=site)
    api.run("aggregate.assign_object", f, products=[lantai], relating_object=gedung)

    dinding = api.run("root.create_entity", f, ifc_class="IfcWall", name="Dinding sumbu Y")
    rep = api.run("geometry.add_wall_representation", f, context=body, length=5, height=3, thickness=0.2)
    api.run("geometry.assign_representation", f, product=dinding, representation=rep)
    putar_90 = np.eye(4)
    putar_90[:3, :3] = [[0, -1, 0], [1, 0, 0], [0, 0, 1]]
    api.run("geometry.edit_object_placement", f, product=dinding, matrix=putar_90)

    atap = api.run("root.create_entity", f, ifc_class="IfcSlab", name="Atap miring", predefined_type="ROOF")
    rep = api.run(
        "geometry.add_slab_representation", f, context=body, depth=0.1,
        polyline=[(0.0, 0.0), (6.0, 0.0), (6.0, 4.0), (0.0, 4.0)],
    )
    api.run("geometry.assign_representation", f, product=atap, representation=rep)
    miring = np.eye(4)
    sudut = np.radians(30)
    miring[:3, :3] = [[1, 0, 0], [0, np.cos(sudut), -np.sin(sudut)], [0, np.sin(sudut), np.cos(sudut)]]
    miring[2, 3] = 3.0
    api.run("geometry.edit_object_placement", f, product=atap, matrix=miring)

    api.run("spatial.assign_container", f, products=[dinding, atap], relating_structure=lantai)
    path = tmp_path / "sintetis.ifc"
    f.write(str(path))
    return path


@pytest.fixture
def db_sementara(tmp_path, monkeypatch):
    import database.estimasi_repository as er
    import database.init_db as idb

    path = tmp_path / "uji.db"
    monkeypatch.setattr(er, "DB_PATH", path)
    monkeypatch.setattr(idb, "DB_PATH", path)
    idb.init_db()
    return path
