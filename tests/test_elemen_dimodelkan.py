"""Pekerjaan yang dimodelkan langsung di IFC menggantikan asumsi/turunan (model > turunan):
tulangan IfcReinforcingBar, rabat beton, bordes tangga, urugan pasir / lantai kerja / aanstamping,
keramik dinding, serta laporan elemen IFC yang tidak dihitung."""

import json

import pytest

from rules import PARAMETER_DEFAULT as P
from rules import proses_semua, terapkan_rules
from rules.penulangan import berat_per_m


def _el(kelas, **kw):
    dasar = dict(kelas=kelas, nama=f"{kelas}-1", predefined_type=None, lantai=None, elevasi_lantai=0.0)
    dasar.update(kw)
    return dasar


def _total(elemen):
    _, keluaran, dilewati = proses_semua(elemen, P)
    total = {}
    for _e, hasil in keluaran:
        for h in hasil:
            total[h.kode] = total.get(h.kode, 0) + h.volume
    return total, dilewati


# ---------------------------------------------------------------- model IFC sintetis


def _model(tmp_path):
    """Satu lantai: pelat lantai 2 bertulang (tulangan via HostGlobalId & agregasi), satu batang lepas,
    rabat, bordes, urugan pasir / lantai kerja / aanstamping (proxy), keramik dinding (covering),
    ruang KM, talang (IfcPipeSegment), dan roster (IfcShadingDevice)."""
    import ifcopenshell.api as api

    f = api.run("project.create_file", version="IFC4")
    proj = api.run("root.create_entity", f, ifc_class="IfcProject", name="Uji")
    api.run("unit.assign_unit", f, length={"is_metric": True, "raw": "METERS"},
            area={"is_metric": True, "raw": "METERS"}, volume={"is_metric": True, "raw": "METERS"})
    model = api.run("context.add_context", f, context_type="Model")
    body = api.run("context.add_context", f, context_type="Model", context_identifier="Body",
                   target_view="MODEL_VIEW", parent=model)
    site = api.run("root.create_entity", f, ifc_class="IfcSite")
    gedung = api.run("root.create_entity", f, ifc_class="IfcBuilding")
    lt1 = api.run("root.create_entity", f, ifc_class="IfcBuildingStorey", name="Lantai 1")
    lt1.Elevation = 0.0
    lt2 = api.run("root.create_entity", f, ifc_class="IfcBuildingStorey", name="Lantai 2")
    lt2.Elevation = 3.5
    api.run("aggregate.assign_object", f, products=[site], relating_object=proj)
    api.run("aggregate.assign_object", f, products=[gedung], relating_object=site)
    api.run("aggregate.assign_object", f, products=[lt1, lt2], relating_object=gedung)

    def pelat(nama, pre, tebal, luas, lantai):
        s = api.run("root.create_entity", f, ifc_class="IfcSlab", name=nama, predefined_type=pre)
        rep = api.run("geometry.add_slab_representation", f, context=body, depth=tebal,
                      polyline=[(0.0, 0.0), (luas / 2, 0.0), (luas / 2, 2.0), (0.0, 2.0)])
        api.run("geometry.assign_representation", f, product=s, representation=rep)
        q = api.run("pset.add_qto", f, product=s, name="Qto_SlabBaseQuantities")
        api.run("pset.edit_qto", f, qto=q, properties={"Depth": tebal, "NetArea": luas, "NetVolume": luas * tebal,
                                                         "Perimeter": luas / 2 * 2 + 4})
        api.run("spatial.assign_container", f, products=[s], relating_structure=lantai)
        return s

    pelat2 = pelat("Pelat Lantai 2 t=12cm", "FLOOR", 0.12, 20.0, lt2)
    pelat("Rabat Beton Lantai Kerja t=7cm - Ruang Tamu", "BASESLAB", 0.07, 30.0, lt1)
    pelat("Bordes Tangga t=15cm", "LANDING", 0.15, 2.4, lt1)

    def batang(d, panjang, nama):
        b = api.run("root.create_entity", f, ifc_class="IfcReinforcingBar", name=nama)
        b.NominalDiameter = d
        b.BarLength = panjang
        api.run("spatial.assign_container", f, products=[b], relating_structure=lt2)
        return b

    for i in range(10):  # D10 via properti HostGlobalId (eksportir non-standar)
        b = batang(0.010, 4.0, f"Tulangan D10 P2-{i}")
        ps = api.run("pset.add_pset", f, product=b, name="Pset_Penulangan")
        api.run("pset.edit_pset", f, pset=ps, properties={"HostGlobalId": pelat2.GlobalId})
    d13 = [batang(0.013, 5.0, f"Tulangan D13 P2-{i}") for i in range(4)]  # D13 via agregasi standar IFC
    api.run("aggregate.assign_object", f, products=d13, relating_object=pelat2)
    batang(0.008, 1.0, "Sengkang lepas")  # tanpa induk

    def proxy(nama, tipe, volume, luas):
        p = api.run("root.create_entity", f, ifc_class="IfcBuildingElementProxy", name=nama,
                    predefined_type="USERDEFINED")
        p.ObjectType = tipe
        q = api.run("pset.add_qto", f, product=p, name="Qto_Kuantitas")
        api.run("pset.edit_qto", f, qto=q, properties={"NetVolume": volume, "NetSurfaceArea": luas})
        api.run("spatial.assign_container", f, products=[p], relating_structure=lt1)

    proxy("Urugan Pasir Bawah Fondasi t=5cm XA-12", "URUGAN_PASIR", 0.10, 2.0)
    proxy("Urugan Pasir Bawah Lantai t=10cm - Ruang Tamu", "URUGAN_PASIR", 3.0, 30.0)
    proxy("Lantai Kerja FP1 A1", "LANTAI_KERJA", 0.05, 1.0)
    proxy("Aanstamping Batu Kosong t=15cm XA-12", "AANSTAMPING", 0.30, 2.0)
    proxy("Kolam Refleksi Beton", "KOLAM", 2.0, 5.0)

    kd = api.run("root.create_entity", f, ifc_class="IfcCovering", name="Keramik Dinding 30x60 (H=1,50) - KM",
                 predefined_type="CLADDING")
    q = api.run("pset.add_qto", f, product=kd, name="Qto_CoveringBaseQuantities")
    api.run("pset.edit_qto", f, qto=q, properties={"NetArea": 8.4})
    km = api.run("root.create_entity", f, ifc_class="IfcSpace", name="KM", predefined_type="INTERNAL")
    q = api.run("pset.add_qto", f, product=km, name="Qto_SpaceBaseQuantities")
    api.run("pset.edit_qto", f, qto=q, properties={"NetFloorArea": 3.0, "NetPerimeter": 7.0})
    talang = api.run("root.create_entity", f, ifc_class="IfcPipeSegment", name="Talang Box Galvalum",
                     predefined_type="GUTTER")
    roster = api.run("root.create_entity", f, ifc_class="IfcShadingDevice", name="Fasad Roster Beton")
    api.run("spatial.assign_container", f, products=[kd, talang, roster], relating_structure=lt1)
    api.run("aggregate.assign_object", f, products=[km], relating_object=lt1)

    path = tmp_path / "dimodelkan.ifc"
    f.write(str(path))
    return path


# ---------------------------------------------------------------- tulangan model


def test_baca_tulangan_per_induk_dan_diameter(tmp_path):
    import ifcopenshell

    from ifc_reader import baca_tulangan

    m = ifcopenshell.open(str(_model(tmp_path)))
    per_host, (lepas_n, lepas_berat) = baca_tulangan(m, 1.0)
    pelat2 = next(s for s in m.by_type("IfcSlab") if s.Name.startswith("Pelat Lantai 2"))
    data = per_host[pelat2.GlobalId]
    assert data["10"]["n"] == 10 and data["10"]["panjang"] == pytest.approx(40.0)
    assert data["13"]["n"] == 4 and data["13"]["berat"] == pytest.approx(20.0 * berat_per_m(13))
    assert lepas_n == 1 and lepas_berat == pytest.approx(berat_per_m(8))


def test_pembesian_memakai_tulangan_model_bukan_asumsi():
    model = {"10": {"berat": 24.66, "panjang": 40.0, "n": 10}, "13": {"berat": 20.84, "panjang": 20.0, "n": 4}}
    pelat = _el("SLAB", nama="Pelat Lantai 2", elevasi_lantai=3.5, tebal=0.12, luas=20.0, volume=2.4,
                besi_model=model)
    hasil, _ = terapkan_rules(pelat)
    besi = {h.kode: h for h in hasil if h.kode.startswith("BSI.")}
    assert set(besi) == {"BSI.PELAT.P", "BSI.PELAT.U"}
    assert besi["BSI.PELAT.P"].volume == pytest.approx(24.66 * 1.05)
    assert besi["BSI.PELAT.U"].volume == pytest.approx(20.84 * 1.05)
    assert "dari model IFC" in besi["BSI.PELAT.U"].rumus and besi["BSI.PELAT.U"].diameter == 13
    tanpa_model = {h.kode for h in terapkan_rules({**pelat, "besi_model": None})[0] if h.kode.startswith("BSI.")}
    assert tanpa_model  # tanpa tulangan model kembali ke tipe penulangan

    tangga = _el("STAIR", nama="Anak Tangga 1A", panjang=2.7, lebar=1.0, tinggi=1.6, volume=0.65,
                 besi_model={"13": {"berat": 16.0, "panjang": 15.4, "n": 6}})
    h = {x.kode: x for x in terapkan_rules(tangga)[0]}
    assert h["BSI.TANGGA"].volume == pytest.approx(16.0 * 1.05)


# ---------------------------------------------------------------- rabat & bordes


def test_rabat_bukan_pelat_struktural_dan_bordes_berbekisting():
    dinding = _el("WALL", nama="Dinding", panjang=5.0, tinggi=3.0, tebal=0.15, luas=15.0, volume=2.25)
    rabat = _el("SLAB", nama="Rabat Beton Lantai Kerja t=7cm - Ruang Tamu", predefined_type="BASESLAB",
                tebal=0.07, luas=30.0, volume=2.1)
    wiremesh = _el("SLAB", nama="Rabat Beton Bertulang Wiremesh Carport", predefined_type="BASESLAB",
                   tebal=0.10, luas=20.0, volume=2.0)
    bordes = _el("SLAB", nama="Bordes Tangga t=15cm", predefined_type="LANDING", tebal=0.15, luas=2.4,
                 volume=0.36)
    total, _ = _total([dinding, rabat, wiremesh, bordes])
    assert total["LTK.LANTAI"] == pytest.approx(2.1)  # rabat: volume model, harga rabat beton
    assert total["BTN.PELAT"] == pytest.approx(2.0 + 0.36)  # hanya rabat bertulang wiremesh + bordes
    assert total["BSK.PELAT"] == pytest.approx(2.4)  # bordes menggantung: berbekisting
    _, keluaran, _ = proses_semua([dinding, rabat, wiremesh, bordes], P)
    per = {e["nama"]: {h.kode for h in hasil} for e, hasil in keluaran}
    assert not any(k.startswith(("BSI.", "BSK.", "BTN.")) for k in per[rabat["nama"]])
    assert "TNH.LANTAI" not in per[bordes["nama"]] and "PSP.BERSIH" not in per[bordes["nama"]]


# ---------------------------------------------------------------- urugan, lantai kerja, keramik dinding


def _fondasi_dan_ruang():
    footplate = _el("FOOTING", nama="Footplate FP1", predefined_type="PAD_FOOTING", panjang=1.0, lebar=1.0,
                    tebal=0.3, volume=0.3, keliling=4.0)
    km = _el("SPACE", nama="KM", luas=3.0, keliling=7.0)
    lantai = _el("SLAB", nama="Lantai dasar", predefined_type="BASESLAB", tebal=0.12, luas=40.0, volume=4.8)
    return [footplate, km, lantai]


def test_tanpa_model_urugan_tetap_diturunkan():
    total, _ = _total(_fondasi_dan_ruang())
    assert total["TNH.PASIR.LANTAI"] > 0 and total["LTK.FONDASI"] > 0 and total["KRM.DINDING"] > 0
    assert "FDN.AANSTAMPING" not in total


def test_urugan_lantai_kerja_aanstamping_dan_keramik_dari_model():
    model = [
        _el("EARTHWORK", nama="Urugan Pasir Bawah Lantai t=10cm", predefined_type="URUGAN_PASIR", volume=4.0, luas=40),
        _el("EARTHWORK", nama="Urugan Pasir Bawah Fondasi t=5cm", predefined_type="URUGAN_PASIR", volume=0.1, luas=2),
        _el("EARTHWORK", nama="Lantai Kerja FP1", predefined_type="LANTAI_KERJA", volume=0.05, luas=1),
        _el("EARTHWORK", nama="Aanstamping Batu Kosong t=15cm", predefined_type="AANSTAMPING", volume=0.3, luas=2),
        _el("WALL_TILE", nama="Keramik Dinding 30x60 - KM", luas=8.4),
    ]
    total, _ = _total(_fondasi_dan_ruang() + model)
    # versi model menggantikan turunan (bukan dijumlahkan)
    assert total["TNH.PASIR.LANTAI"] == pytest.approx(4.0)
    assert total["TNH.PASIR.FONDASI"] == pytest.approx(0.1)
    assert total["LTK.FONDASI"] == pytest.approx(0.05)
    assert total["FDN.AANSTAMPING"] == pytest.approx(0.3)
    assert total["KRM.DINDING"] == pytest.approx(8.4)


# ---------------------------------------------------------------- IFC: klasifikasi, ekstraksi, laporan


def test_ekstraksi_model_lengkap_dan_laporan_tidak_dihitung(tmp_path):
    import ifcopenshell

    from ifc_reader import ekstrak_elemen

    m = ifcopenshell.open(str(_model(tmp_path)))
    elemen, peringatan = ekstrak_elemen(m)
    per_nama = {e["nama"]: e for e in elemen}
    urug = per_nama["Urugan Pasir Bawah Lantai t=10cm - Ruang Tamu"]
    assert urug["kelas"] == "EARTHWORK" and urug["predefined_type"] == "URUGAN_PASIR"
    assert urug["volume"] == pytest.approx(3.0)
    assert per_nama["Keramik Dinding 30x60 (H=1,50) - KM"]["kelas"] == "WALL_TILE"
    assert per_nama["Keramik Dinding 30x60 (H=1,50) - KM"]["luas"] == pytest.approx(8.4)
    assert "Kolam Refleksi Beton" not in per_nama  # proxy lain: dilaporkan, bukan dihitung
    assert per_nama["Pelat Lantai 2 t=12cm"]["besi_model"]["13"]["n"] == 4

    teks = " ".join(peringatan)
    assert "1 batang tulangan model" in teks
    assert "pipa / talang (IfcPipeSegment" in teks and "'Talang Box Galvalum'" in teks
    assert "peneduh / roster (IfcShadingDevice" in teks
    assert "elemen generik (IfcBuildingElementProxy, mis. 'Kolam Refleksi Beton'" in teks
    assert "Urugan Pasir" not in teks and "Keramik Dinding" not in teks

    total, _ = _total(elemen)
    assert total["KRM.DINDING"] == pytest.approx(8.4)  # dari covering, bukan keliling ruang KM
    assert total["LTK.LANTAI"] == pytest.approx(30.0 * 0.07)
    assert total["FDN.AANSTAMPING"] == pytest.approx(0.30)


def test_tulangan_model_tersimpan_dan_ikut_hitung_ulang(db_sementara, tmp_path):
    from database.estimasi_repository import _connect
    from database.proyek_repository import create_proyek
    from estimasi_service import hitung_ulang_dari_elemen, hitung_ulang_elemen, jalankan_estimasi

    pid = create_proyek(nama_proyek="Uji", path_file_ifc=str(_model(tmp_path)))
    jalankan_estimasi(pid)

    def besi_pelat2():
        conn = _connect()
        try:
            row = conn.execute("SELECT id, besi_model FROM elemen_proyek WHERE nama LIKE 'Pelat Lantai 2%'").fetchone()
            berat = conn.execute(
                "SELECT SUM(h.volume_pekerjaan) FROM hasil_estimasi h JOIN pekerjaan p ON p.id = h.pekerjaan_id "
                "WHERE h.elemen_id = ? AND p.kode_ahsp LIKE 'BSI.%'", (row["id"],)).fetchone()[0]
            return row["id"], (json.loads(row["besi_model"]) if row["besi_model"] else None), berat
        finally:
            conn.close()

    eid, model, berat = besi_pelat2()
    harap = (40.0 * berat_per_m(10) + 20.0 * berat_per_m(13)) * 1.05
    assert model["10"]["n"] == 10 and berat == pytest.approx(harap)
    hitung_ulang_dari_elemen(pid)  # mis. setelah parameter aturan diubah
    assert besi_pelat2()[2] == pytest.approx(harap)
    hitung_ulang_elemen(eid, {"tebal": 0.15})  # dimensi diubah: tulangan model tidak lagi berlaku
    _, model, berat = besi_pelat2()
    assert model is None and berat and berat != pytest.approx(harap)
