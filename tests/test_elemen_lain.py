"""Semua elemen model masuk RAB (elemen_lain.py): cladding, kisi, roster, lisplang, nok, talang, waterproofing,
beton lansekap, media tanam, sanitair, elemen tanpa padanan HSPK (harga 0), struktur baja/kayu; batang rangka atap
tidak dihitung ganda; cat dinding di balik cladding dikurangi."""

import numpy as np
import pytest

from conftest import AC20


def _model(tmp_path):
    """Satu lantai: dinding luar Y1 4 m dengan cladding batu 2 x 3 m menempel di muka luarnya (berjarak 5 cm,
    rata muka kolom), panel WPC + rangka hollow, kisi, lisplang, talang, rantai hujan, nok, waterproofing, planter
    beton + media tanam, kloset, kasau baja ringan (rangka atap), meja, dan balok baja WF."""
    import ifcopenshell.api as api

    f = api.run("project.create_file", version="IFC4")
    proj = api.run("root.create_entity", f, ifc_class="IfcProject", name="Uji Elemen Lain")
    api.run("unit.assign_unit", f, length={"is_metric": True, "raw": "METERS"},
            area={"is_metric": True, "raw": "METERS"}, volume={"is_metric": True, "raw": "METERS"})
    ctx = api.run("context.add_context", f, context_type="Model")
    body = api.run("context.add_context", f, context_type="Model", context_identifier="Body",
                   target_view="MODEL_VIEW", parent=ctx)
    site = api.run("root.create_entity", f, ifc_class="IfcSite")
    gedung = api.run("root.create_entity", f, ifc_class="IfcBuilding")
    lt1 = api.run("root.create_entity", f, ifc_class="IfcBuildingStorey", name="01 Lantai 1")
    lt1.Elevation = 0.0
    atap = api.run("root.create_entity", f, ifc_class="IfcBuildingStorey", name="02 Atap")
    atap.Elevation = 3.0
    api.run("aggregate.assign_object", f, products=[site], relating_object=proj)
    api.run("aggregate.assign_object", f, products=[gedung], relating_object=site)
    api.run("aggregate.assign_object", f, products=[lt1, atap], relating_object=gedung)

    def kotak(kelas, nama, x, y, z0, z1, bx, by, lantai=lt1, pre=None, pset=None, bahan=None):
        el = api.run("root.create_entity", f, ifc_class=kelas, name=nama, predefined_type=pre)
        profil = f.create_entity("IfcRectangleProfileDef", ProfileType="AREA", XDim=bx, YDim=by)
        rep = api.run("geometry.add_profile_representation", f, context=body, profile=profil, depth=z1 - z0)
        api.run("geometry.assign_representation", f, product=el, representation=rep)
        m = np.eye(4)
        m[:3, 3] = (x, y, z0)
        api.run("geometry.edit_object_placement", f, product=el, matrix=m)
        for nama_set, isi in (pset or {}).items():
            ps = api.run("pset.add_pset", f, product=el, name=nama_set)
            api.run("pset.edit_pset", f, pset=ps, properties=isi)
        if bahan:
            mat = api.run("material.add_material", f, name=bahan)
            api.run("material.assign_material", f, products=[el], type="IfcMaterial", material=mat)
        api.run("spatial.assign_container", f, products=[el], relating_structure=lantai)
        return el

    dinding = kotak("IfcWall", "Dinding Luar Y1", 2.0, 0.0, 0.0, 3.0, 4.0, 0.15,
                    pset={"Pset_WallCommon": {"IsExternal": True}})
    dinding.PredefinedType = "STANDARD"
    # cladding batu di muka luar (y = -0,075 - 0,05 celah), 2 m x 3 m
    kotak("IfcCovering", "Cladding Fasad Depan", 1.0, -0.14, 0.0, 3.0, 2.0, 0.03, pre="CLADDING",
          pset={"Pset_CoveringCommon": {"IsExternal": True}}, bahan="Batu alam travertine 30x60")
    kotak("IfcCovering", "Cladding WPC Kolom Carport", 6.0, 3.0, 0.0, 3.0, 0.34, 0.34, pre="CLADDING",
          bahan="Panel WPC motif kayu + rangka hollow")
    kotak("IfcShadingDevice", "Kisi-kisi Fasad", 2.0, -2.0, 0.5, 3.0, 1.2, 0.08, pre="USERDEFINED",
          bahan="WPC 40x80 + rangka hollow 40x40")
    kotak("IfcPlate", "Listplank WPC Depan", 2.0, -1.0, 3.0, 3.2, 6.0, 0.025, lantai=atap, pre="SHEET")
    kotak("IfcPipeSegment", "Talang Atap Depan", 2.0, -1.2, 2.9, 3.0, 6.0, 0.15, lantai=atap, pre="GUTTER")
    kotak("IfcPipeSegment", "Rantai Hujan Depan", -1.0, -1.2, 0.0, 2.9, 0.04, 0.04, pre="USERDEFINED")
    kotak("IfcCovering", "Genteng Nok Bubungan", 2.0, 1.0, 4.5, 4.6, 5.0, 0.25, lantai=atap, pre="ROOFING")
    kotak("IfcCovering", "Waterproofing Dak", 2.0, 5.0, 3.0, 3.003, 4.0, 3.0, lantai=atap, pre="MEMBRANE")
    kotak("IfcBuildingElementProxy", "Planter Box Beton", 8.0, 0.0, 0.0, 0.6, 2.0, 0.5, pre="USERDEFINED",
          bahan="Beton K-175 t=8cm + wiremesh M8 + waterproofing")
    kotak("IfcBuildingElementProxy", "Media Tanam Planter", 8.0, 0.0, 0.08, 0.55, 1.84, 0.34, pre="USERDEFINED",
          bahan="Tanah taman + kompos")
    kotak("IfcSanitaryTerminal", "Kloset Duduk WC", 1.0, 2.0, 0.0, 0.4, 0.4, 0.6, pre="TOILETPAN")
    kotak("IfcMember", "Kasau C75 Bidang Kiri", 2.0, 1.0, 3.5, 3.6, 0.04, 6.0, lantai=atap, pre="RAFTER")
    kotak("IfcFurniture", "Lemari Pakaian", 3.0, 2.0, 0.0, 2.0, 1.2, 0.6)
    kotak("IfcBeam", "M_W-Wide Flange:W310X60:1", 2.0, 8.0, 2.7, 3.0, 4.0, 0.165, pre="BEAM",
          bahan="Metal - Steel - 345 MPa")
    path = tmp_path / "lain.ifc"
    f.write(str(path))
    return path


@pytest.fixture
def ekstrak(tmp_path):
    from ifc_reader import buka_dan_validasi, ekstrak_elemen

    info = buka_dan_validasi(_model(tmp_path))
    elemen, peringatan = ekstrak_elemen(info.model)
    return info, elemen, peringatan


def _per_nama(elemen):
    return {e["nama"]: e for e in elemen}


def test_jenis_elemen_lain_dikenali(ekstrak):
    info, elemen, _p = ekstrak
    jenis = {e["nama"]: (e.get("info_lain") or {}).get("jenis") for e in elemen if e["kelas"] == "LAINNYA"}
    assert jenis == {
        "Cladding Fasad Depan": "cladding_batu", "Cladding WPC Kolom Carport": "cladding_panel",
        "Kisi-kisi Fasad": "kisi", "Listplank WPC Depan": "lisplang", "Talang Atap Depan": "talang",
        "Rantai Hujan Depan": "talang_tegak", "Genteng Nok Bubungan": "nok", "Waterproofing Dak": "waterproofing",
        "Planter Box Beton": "beton_lansekap", "Media Tanam Planter": "media_tanam", "Kloset Duduk WC": "sanitair",
        "Lemari Pakaian": "lain",
    }
    # batang rangka atap tidak dihitung per batang: sudah termasuk rangka atap per m²
    assert "Kasau C75 Bidang Kiri" not in {e["nama"] for e in elemen}
    assert list(info.tidak_dihitung) == ["batang rangka atap (IfcMember)"]
    assert "rangka atap per m² luas atap" in info.tidak_dihitung["batang rangka atap (IfcMember)"]["catatan"]


def test_volume_dan_pekerjaan_elemen_lain(ekstrak):
    from rules import proses_semua

    _info, elemen, _p = ekstrak
    _k, keluaran, _d = proses_semua(elemen)
    per = {}
    for el, hasil in keluaran:
        for h in hasil:
            per.setdefault(el["nama"], {})[h.kode] = h.volume
    assert per["Cladding Fasad Depan"] == {"CLD.BATU": pytest.approx(6.0, rel=0.02)}
    assert per["Cladding WPC Kolom Carport"]["CLD.PANEL"] > 0
    assert per["Cladding WPC Kolom Carport"]["CLD.RANGKA"] == per["Cladding WPC Kolom Carport"]["CLD.PANEL"]
    assert set(per["Kisi-kisi Fasad"]) == {"CLD.KISI", "CLD.RANGKA"}
    assert per["Listplank WPC Depan"] == {"ATP.LISPLANG": pytest.approx(6.0, rel=0.02)}
    assert per["Talang Atap Depan"] == {"ATP.TALANG": pytest.approx(6.0, rel=0.02)}
    assert per["Rantai Hujan Depan"] == {"ATP.TALANG_TEGAK": pytest.approx(2.9, rel=0.02)}
    assert per["Genteng Nok Bubungan"] == {"ATP.NOK": pytest.approx(5.0, rel=0.02)}
    assert per["Waterproofing Dak"] == {"WTP.LAPISAN": pytest.approx(12.0, rel=0.02)}
    planter = per["Planter Box Beton"]
    assert planter["LSK.BETON"] == pytest.approx(0.6, rel=0.02)  # kotak pejal 2 x 0,5 x 0,6
    assert set(planter) == {"LSK.BETON", "LSK.BEKISTING", "LSK.WIREMESH", "WTP.LAPISAN"}
    assert per["Media Tanam Planter"] == {"LSK.MEDIA_TANAM": pytest.approx(1.84 * 0.34 * 0.47, rel=0.02)}
    assert per["Kloset Duduk WC"] == {"SNT.KLOSET_DUDUK": 1.0}
    lemari = per["Lemari Pakaian"]
    assert list(lemari) == ["LAIN|IfcFurniture|Lemari Pakaian"] and lemari["LAIN|IfcFurniture|Lemari Pakaian"] == 1
    # balok baja WF: per kg (V x 7.850), bukan "tidak dihitung"
    wf = per["M_W-Wide Flange:W310X60:1"]
    assert wf == {"BJA.PROFIL": pytest.approx(4.0 * 0.165 * 0.3 * 7850, rel=0.02)}


def test_cat_dinding_di_balik_cladding_dikurangi(ekstrak):
    from rules import proses_semua

    _info, elemen, _p = ekstrak
    w = _per_nama(elemen)["Dinding Luar Y1"]
    assert w["info_lain"]["tertutup_luar"] == pytest.approx(6.0, rel=0.02)
    assert w["info_lain"]["cladding"] == ["Cladding Fasad Depan"]
    _k, keluaran, _d = proses_semua(elemen)
    hasil = {h.kode: h for el, hs in keluaran if el["nama"] == "Dinding Luar Y1" for h in hs}
    assert hasil["CAT.EKSTERIOR"].volume == pytest.approx(w["luas"] - 6.0, rel=0.02)
    assert "cladding" in hasil["CAT.EKSTERIOR"].rumus
    assert hasil["PLS.DINDING"].volume == pytest.approx(w["luas"] * 2)  # plester tetap (dasar pemasangan cladding)


def test_estimasi_elemen_tanpa_analisa_masuk_rab_dengan_harga_nol(db_sementara, tmp_path):
    from database.estimasi_repository import _connect, get_hasil_estimasi_by_proyek
    from database.proyek_repository import create_proyek
    from estimasi_service import hitung_ulang_dari_elemen, jalankan_estimasi

    pid = create_proyek("Uji Lain", str(_model(tmp_path)))
    r = jalankan_estimasi(pid)
    assert not any("belum ada di tabel pekerjaan" in p for p in r["peringatan"])
    assert any("belum punya padanan analisa HSPK" in p and "Lemari Pakaian" in p for p in r["peringatan"])
    rows = [dict(x) for x in get_hasil_estimasi_by_proyek(pid)]
    lemari = [x for x in rows if x["kode_ahsp"].startswith("LAIN|")]
    assert len(lemari) == 1 and lemari[0]["subtotal_biaya"] == 0 and lemari[0]["kategori"] == "Lain-lain"
    assert {x["kategori"] for x in rows} >= {"Fasad", "Atap", "Lansekap", "Sanitair", "Struktur Baja"}
    assert all(x["subtotal_biaya"] > 0 for x in rows if not x["kode_ahsp"].startswith("LAIN|"))
    # dihitung ulang dari elemen tersimpan (info_lain tersimpan di database): hasilnya sama
    sebelum = sorted((x["kode_ahsp"], round(x["volume_pekerjaan"], 6)) for x in rows)
    hitung_ulang_dari_elemen(pid)
    sesudah = sorted((x["kode_ahsp"], round(x["volume_pekerjaan"], 6))
                     for x in map(dict, get_hasil_estimasi_by_proyek(pid)))
    assert sesudah == sebelum
    conn = _connect()
    assert conn.execute("SELECT COUNT(*) FROM pekerjaan WHERE kode_ahsp LIKE 'LAIN|%'").fetchone()[0] == 1
    conn.close()


def test_teks_tebal_dan_pengenalan_dari_nama_lebih_dulu():
    from elemen_lain import berat_jaring, tebal_dari_teks

    assert tebal_dari_teks("Beton K-175 t=12 cm") == pytest.approx(0.12)
    assert tebal_dari_teks("t=80 mm") == pytest.approx(0.08)
    assert tebal_dari_teks("tanpa keterangan") is None
    assert berat_jaring(8, 150) == pytest.approx(5.26, abs=0.01)  # Ø8-150 dua arah


def test_batang_rangka_atap_ac20_tampil_sebagai_bagian_rangka_atap(db_sementara):
    """Model ArchiCAD (Jerman): batang 'Sparren' di lantai 'Dachgeschoss' = rangka atap; di penampil 3D
    diklik -> baris Rangka Atap pada atap di atasnya."""
    from biaya_elemen import peta_biaya, rincian_termasuk
    from database.proyek_repository import create_proyek
    from estimasi_service import jalankan_estimasi
    from model3d import muat_model3d

    pid = create_proyek("AC20", str(AC20))
    jalankan_estimasi(pid)
    m = muat_model3d(str(AC20))
    sparren = [e for e in m.elemen if e.nama.startswith("Sparren")]
    assert sparren and all(e.termasuk == "rangka_atap" for e in sparren)
    peta = peta_biaya(pid)
    data = rincian_termasuk(pid, "rangka_atap", sparren[0].kotak, peta, {e.gid: e.kotak for e in m.elemen})
    assert data and data["total"] > 0
    assert {r["kode"].split("~")[0] for b in data["bagian"] for r in b["baris"]} == {"ATP.RANGKA"}
