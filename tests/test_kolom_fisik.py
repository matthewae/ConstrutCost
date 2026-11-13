"""Kolom fisik dan fungsi kolom (kolom.py): pedestal + kolom di atasnya = satu kolom, kolom kanopi/carport dan
kolom arsitektur dipisah dari kolom struktur utama, objek kolom ganda tidak dihitung dua kali."""

import os

import pytest

from kolom import (
    FUNGSI_ARSITEKTUR,
    FUNGSI_KANOPI,
    FUNGSI_PRAKTIS,
    FUNGSI_UTAMA,
    Segmen,
    analisis,
    teks_ringkasan,
)
from rules import PARAMETER_DEFAULT as P
from rules import proses_semua
from rules.penulangan import KAIT_UTAMA, LEWATAN, Penulangan, berat_per_m, hitung

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(scope="module")
def app():
    from PySide6.QtWidgets import QApplication

    from gui import tema

    a = QApplication.instance() or QApplication([])
    tema.terapkan(a, "hitam_kuning")
    return a


# denah bangunan 10 x 10 m dengan dinding keliling di lantai 1
DINDING = {"Lantai 1": [(0, -0.07, 0, 10, 0.07, 3), (0, 9.93, 0, 10, 10.07, 3),
                        (-0.07, 0, 0, 0.07, 10, 3), (9.93, 0, 0, 10.07, 10, 3)]}


def _seg(gid, x, y, z0, z1, sisi=0.30, lantai="Lantai 1", nama=None, lb=True, teks=None):
    h = sisi / 2
    return Segmen(gid, nama or gid, (x - h, y - h, z0, x + h, y + h, z1), teks or nama or gid, lb, lantai)


def test_pedestal_dan_kolom_di_atasnya_satu_kolom():
    seg = [_seg("PD-A1", 0, 0, -1.2, -0.1, lantai="00 Fondasi", nama="Pedestal PD-1 30x30 A1"),
           _seg("K-A1", 0, 0, -0.1, 4.65, nama="Kolom KA 30x30 A1"),
           _seg("PD-B1", 5, 0, -1.2, -0.1, lantai="00 Fondasi", nama="Pedestal PD-1 30x30 B1"),
           _seg("K-B1", 5, 0, -0.1, 3.5, nama="Kolom KB 30x30 B1")]
    h = analisis(seg, DINDING, elev_dasar=0.0)
    r = h.ringkasan
    assert r["objek"] == 4 and r["fisik"] == 2 and r["digabung"] == 2
    assert r["per_fungsi"][FUNGSI_UTAMA] == 2
    assert h.info["PD-A1"]["grup"] == h.info["K-A1"]["grup"] == "K-A1"  # wakil = segmen di atas tanah
    assert h.info["PD-A1"]["peran"] == "pedestal" and (h.info["PD-A1"]["urut"], h.info["PD-A1"]["n"]) == (1, 2)
    assert h.info["K-A1"]["peran"] == "kolom" and h.info["K-A1"]["urut"] == 2
    assert "2 kolom struktur utama" in teks_ringkasan(r) and "Pedestal PD-1 30x30 A1 + Kolom KA" in teks_ringkasan(r)


def test_kolom_lantai_1_dan_2_tetap_dua_kolom_tetapi_potongan_satu_lantai_digabung():
    seg = [_seg("L1", 2, 2, 0.0, 3.5), _seg("L2", 2, 2, 3.5, 7.0, lantai="Lantai 2"),
           _seg("P-bawah", 8, 2, 0.0, 1.5), _seg("P-atas", 8, 2, 1.5, 3.5)]  # dipotong saat pemodelan
    h = analisis(seg, DINDING, elev_dasar=0.0)
    assert h.ringkasan["fisik"] == 3
    assert h.info["L1"]["grup"] != h.info["L2"]["grup"]  # volume kolom diukur per lantai
    assert h.info["P-bawah"]["grup"] == h.info["P-atas"]["grup"]


def test_kolom_tertanam_di_pedestal_digabung_dan_tumpangnya_dilaporkan():
    seg = [_seg("PD", 0, 0, -1.2, -0.1, lantai="00 Fondasi", sisi=0.4, nama="Pedestal 40x40"),
           _seg("K", 0, 0, -0.4, 3.5, nama="Kolom 30x30")]  # kolom turun 30 cm ke dalam pedestal
    r = analisis(seg, DINDING, elev_dasar=0.0).ringkasan
    assert r["fisik"] == 1 and r["duplikat"] == 0 and r["tumpang"] == 1
    assert r["volume_tumpang"] == pytest.approx(0.3 * 0.3 * 0.3)
    assert "terhitung dua kali" in teks_ringkasan(r)


def test_kolom_kanopi_carport_dari_nama_dan_dari_letak_di_luar_bangunan():
    seg = [_seg("A1", 0, 0, 0, 3.5, nama="Kolom KA 30x30 A1"),
           _seg("CP1", 0, -5.4, 0, 3.5, nama="Kolom KA 30x30 CP1 (carport)"),
           _seg("CP2", 4.5, -5.4, 0, 3.5, nama="Kolom KB 30x30 CP2"),  # tanpa kata kunci, di luar selubung dinding
           _seg("PD-CP2", 4.5, -5.4, -1.0, 0, lantai="00 Fondasi", nama="Pedestal PD-1 30x30 CP2"),
           _seg("T1", 5, 10.2, 0, 3.5, nama="Kolom Teras Belakang"),
           _seg("TENGAH", 5, 5, 0, 3.5, nama="Kolom K1 tengah")]
    h = analisis(seg, DINDING, elev_dasar=0.0)
    f = {g: h.info[g]["fungsi"] for g in h.info}
    assert f["A1"] == f["TENGAH"] == FUNGSI_UTAMA  # kolom di tepi selubung dinding tetap kolom utama
    assert f["CP1"] == f["CP2"] == f["PD-CP2"] == f["T1"] == FUNGSI_KANOPI
    assert h.ringkasan["per_fungsi"] == {FUNGSI_UTAMA: 2, FUNGSI_KANOPI: 3, FUNGSI_PRAKTIS: 0, FUNGSI_ARSITEKTUR: 0}


def test_kolom_menerus_antarlantai_tetap_kolom_utama():
    """Lantai 1 terbuka (carport di bawah lantai 2) dan sudut lantai atas tanpa dinding: kolom di luar selubung
    dinding lantainya tetapi memikul kolom lantai di atasnya / berdiri di atas kolom lantai bawah = kolom utama."""
    dinding = {"Lantai 1": [(0, -0.07, 0, 6, 0.07, 3), (0, 9.93, 0, 6, 10.07, 3), (-0.07, 0, 0, 0.07, 10, 3)],
               "Lantai 2": [(0, -0.07, 3.5, 6, 0.07, 6.5), (-0.07, 0, 3.5, 0.07, 10, 6.5)]}
    seg = [_seg("D1-L1", 10, 0, 0, 3.5, nama="Kolom K1 Lt.1 D1 (carport)"),  # carport di bawah lantai 2
           _seg("D1-L2", 10, 0, 3.5, 7.0, lantai="Lantai 2", nama="Kolom K1 Lt.2 D1"),
           _seg("D3-L2", 10, 10, 3.5, 7.0, lantai="Lantai 2", nama="Kolom K3 Lt.2 D3"),  # sudut tanpa dinding
           _seg("D3-L1", 10, 10, 0, 3.5, nama="Kolom K1 Lt.1 D3"),
           _seg("CP", 3, -6, 0, 3.5, nama="Kolom K2 30x30 CP"),  # satu lantai, di luar selubung bangunan
           _seg("TAMAN", 3, 8, 0, 3.0, nama="Kolom KP 30x30 Dinding Taman")]
    h = analisis(seg, dinding, elev_dasar=0.0)
    f = {g: v["fungsi"] for g, v in h.info.items()}
    assert f["D1-L1"] == f["D1-L2"] == f["D3-L1"] == f["D3-L2"] == FUNGSI_UTAMA
    assert h.info["D1-L1"]["menerus"] and h.info["D1-L1"]["grup"] != h.info["D1-L2"]["grup"]
    assert f["CP"] == f["TAMAN"] == FUNGSI_KANOPI


def test_selubung_bangunan_membedakan_perkerasan_luar():
    h = analisis([_seg("A1", 0, 0, 0, 3.5)], DINDING, elev_dasar=0.0)
    assert h.di_luar((0, -6, -0.2, 6, -1, -0.1)) is True  # carport / jalan masuk di depan bangunan
    assert h.di_luar((1, 1, -0.1, 9, 9, -0.03)) is False  # rabat di dalam bangunan
    assert analisis([], {}, None).di_luar((0, 0, 0, 1, 1, 1)) is None  # tanpa dinding: tidak diketahui


def test_kolom_arsitektur_praktis_dan_baja():
    seg = [_seg("DEKOR", 3, 3, 0, 3.5, nama="Kolom Dekoratif Fasad 40x40", sisi=0.4),
           _seg("NLB", 6, 3, 0, 3.5, nama="Kolom Bulat D30", lb=False),  # Pset_ColumnCommon.LoadBearing = FALSE
           _seg("KP", 3, 6, 0, 3.0, nama="Kolom Praktis 13/13", sisi=0.13),
           _seg("HSS", 6, 6, 0, 3.0, nama="HSS Square-Column 100x100", sisi=0.10)]
    f = {g: v["fungsi"] for g, v in analisis(seg, DINDING, elev_dasar=0.0).info.items()}
    assert f == {"DEKOR": FUNGSI_ARSITEKTUR, "NLB": FUNGSI_ARSITEKTUR, "KP": FUNGSI_PRAKTIS, "HSS": FUNGSI_UTAMA}


def test_objek_kolom_ganda_dihitung_sekali():
    seg = [_seg("STR", 2, 2, 0, 3.5, nama="Kolom Struktur 30x30"),
           _seg("ARS", 2, 2, 0, 3.5, sisi=0.40, nama="Kolom Arsitektur Pembungkus 40x40", lb=False),
           _seg("SALIN", 7, 7, 0, 3.5), _seg("SALIN-2", 7, 7, 0, 3.5)]
    h = analisis(seg, DINDING, elev_dasar=0.0)
    assert h.ringkasan["fisik"] == 2 and h.ringkasan["duplikat"] == 2
    assert h.info["ARS"]["duplikat"] == "STR"  # yang memikul beban dipertahankan
    assert h.info["SALIN-2"]["duplikat"] == "SALIN"
    assert "objek ganda" in teks_ringkasan(h.ringkasan)


# ---------------------------------------------------------------- dampak pada perhitungan


def _kolom(gid, info, **kw):
    e = dict(kelas="COLUMN", nama=gid, global_id=gid, predefined_type="COLUMN", lantai="Lantai 1",
             elevasi_lantai=0.0, lebar=0.3, tebal=0.3, tinggi=3.0, volume=0.27, kolom_grup=info["grup"],
             info_kolom=info)
    e.update(kw)
    return e


def test_tulangan_menerus_di_sambungan_pedestal_dan_kolom():
    p = Penulangan("KOLOM", 8, 13, d_sengkang=8, jarak_sengkang=0.15, selimut=0.04)
    tunggal = dict(kelas="COLUMN", lebar=0.3, tebal=0.3, tinggi=3.0)
    pedestal = dict(tunggal, tinggi=1.0, info_kolom={"urut": 1, "n": 2, "grup": "K"})
    kolom = dict(tunggal, info_kolom={"urut": 2, "n": 2, "grup": "K"})
    wm = berat_per_m(13)
    utama = {nama: hitung(e, p)[0].berat for nama, e in (("tunggal", tunggal), ("pedestal", pedestal), ("kolom", kolom))}
    d = 0.013
    assert utama["tunggal"] == pytest.approx(8 * (3.0 + 2 * KAIT_UTAMA * d) * wm * 1.05)
    assert utama["pedestal"] == pytest.approx(8 * (1.0 + KAIT_UTAMA * d) * wm * 1.05)  # kait hanya di ujung bawah
    assert utama["kolom"] == pytest.approx(8 * (3.0 + KAIT_UTAMA * d + LEWATAN * d) * wm * 1.05)  # + lewatan 40d
    assert "sambungan dengan segmen kolom bawah" in hitung(kolom, p)[0].rumus
    sengkang = {nama: hitung(e, p)[1] for nama, e in (("pedestal", pedestal), ("kolom", kolom))}
    assert "= 7 buah" in sengkang["pedestal"].rumus and "= 20 buah" in sengkang["kolom"].rumus  # 6+1, 20 (tanpa +1)


def test_fondasi_turunan_satu_per_kolom_fisik_dan_kolom_arsitektur_tanpa_fondasi():
    grup = {"grup": "K-A1", "fungsi": FUNGSI_UTAMA, "n": 2, "duplikat": None}
    elemen = [
        # pedestal dan kolom di lantai yang sama (umum pada model Revit), tanpa fondasi dimodelkan
        _kolom("PD-A1", {**grup, "urut": 1, "peran": "pedestal"}, tinggi=1.0, volume=0.09),
        _kolom("K-A1", {**grup, "urut": 2, "peran": "kolom"}),
        _kolom("DEKOR", {"grup": "DEKOR", "fungsi": FUNGSI_ARSITEKTUR, "urut": 1, "n": 1, "duplikat": None}),
        _kolom("SALIN", {"grup": "K-A1", "fungsi": FUNGSI_UTAMA, "urut": 0, "n": 2, "duplikat": "K-A1",
                         "nama_duplikat": "K-A1"}),
    ]
    _, keluaran, dilewati = proses_semua(elemen, P)
    kode = {e["global_id"]: {h.kode for h in hasil} for e, hasil in keluaran}
    assert "BTN.SUMURAN" in kode["PD-A1"] and "BTN.SUMURAN" not in kode["K-A1"]  # sekali per kolom fisik
    assert "BTN.SUMURAN" not in kode["DEKOR"] and "BTN.KOLOM" in kode["DEKOR"]
    assert not kode["SALIN"]  # objek ganda: volume sudah dihitung pada kolom aslinya
    assert any("SALIN" in d and "objek ganda" in d for d in dilewati)


def test_tipe_kolom_kanopi_terpisah_dari_kolom_utama():
    from rules.penulangan import KOLOM_ARSITEKTUR, KOLOM_KANOPI, bawaan, kunci_tipe, label_tipe

    utama = _kolom("A1", {"grup": "A1", "fungsi": FUNGSI_UTAMA, "urut": 1, "n": 1})
    kanopi = _kolom("CP1", {"grup": "CP1", "fungsi": FUNGSI_KANOPI, "urut": 1, "n": 1})
    ars = _kolom("D1", {"grup": "D1", "fungsi": FUNGSI_ARSITEKTUR, "urut": 1, "n": 1})
    assert kunci_tipe(utama) == ("KOLOM", 30, 30)
    assert kunci_tipe(kanopi) == (KOLOM_KANOPI, 30, 30)
    assert kunci_tipe(ars) == (KOLOM_ARSITEKTUR, 30, 30)
    assert label_tipe(KOLOM_KANOPI, "C1", 0.3, 0.3) == "Kolom Sekunder C1 (30/30)"
    assert bawaan(KOLOM_ARSITEKTUR, 0.3, 0.3).ringkas() == "4 Ø10, sengkang Ø6-150"  # non-struktural: minimum
    assert bawaan(KOLOM_KANOPI, 0.3, 0.3).ringkas() == bawaan("KOLOM", 0.3, 0.3).ringkas()


# ---------------------------------------------------------------- model IFC sintetis


def _model(tmp_path):
    """Denah 4,5 x 3,6 m: 4 kolom grid A1-B2 masing-masing pedestal (lantai Fondasi) + kolom (Lantai 1),
    2 kolom carport di luar dinding (tanpa kata kunci), dan dinding keliling."""
    import numpy as np
    import ifcopenshell.api as api

    f = api.run("project.create_file", version="IFC4")
    proj = api.run("root.create_entity", f, ifc_class="IfcProject", name="Uji Kolom")
    api.run("unit.assign_unit", f, length={"is_metric": True, "raw": "METERS"},
            area={"is_metric": True, "raw": "METERS"}, volume={"is_metric": True, "raw": "METERS"})
    ctx = api.run("context.add_context", f, context_type="Model")
    body = api.run("context.add_context", f, context_type="Model", context_identifier="Body",
                   target_view="MODEL_VIEW", parent=ctx)
    site = api.run("root.create_entity", f, ifc_class="IfcSite")
    gedung = api.run("root.create_entity", f, ifc_class="IfcBuilding")
    fond = api.run("root.create_entity", f, ifc_class="IfcBuildingStorey", name="00 Fondasi")
    fond.Elevation = -1.2
    lt1 = api.run("root.create_entity", f, ifc_class="IfcBuildingStorey", name="01 Lantai 1")
    lt1.Elevation = 0.0
    api.run("aggregate.assign_object", f, products=[site], relating_object=proj)
    api.run("aggregate.assign_object", f, products=[gedung], relating_object=site)
    api.run("aggregate.assign_object", f, products=[fond, lt1], relating_object=gedung)
    profil = f.create_entity("IfcRectangleProfileDef", ProfileType="AREA", XDim=0.3, YDim=0.3)

    def tempat(el, x, y, z):
        m = np.eye(4)
        m[:3, 3] = (x, y, z)
        api.run("geometry.edit_object_placement", f, product=el, matrix=m)

    def kolom(nama, x, y, z0, z1, lantai):
        c = api.run("root.create_entity", f, ifc_class="IfcColumn", name=nama, predefined_type="COLUMN")
        rep = api.run("geometry.add_profile_representation", f, context=body, profile=profil, depth=z1 - z0)
        api.run("geometry.assign_representation", f, product=c, representation=rep)
        tempat(c, x, y, z0)
        ps = api.run("pset.add_pset", f, product=c, name="Pset_ColumnCommon")
        api.run("pset.edit_pset", f, pset=ps, properties={"LoadBearing": True})
        api.run("spatial.assign_container", f, products=[c], relating_structure=lantai)

    for g, (x, y) in {"A1": (0, 0), "B1": (4.5, 0), "A2": (0, 3.6), "B2": (4.5, 3.6),
                      "CP1": (0, -5.4), "CP2": (4.5, -5.4)}.items():
        kolom(f"Pedestal PD-1 30x30 {g}", x, y, -1.2, -0.1, fond)
        kolom(f"Kolom K 30x30 {g}", x, y, -0.1, 3.5, lt1)

    for nama, (x0, y0, x1, y1) in {"Y1": (0, 0, 4.5, 0), "Y2": (0, 3.6, 4.5, 3.6), "XA": (0, 0, 0, 3.6),
                                   "XB": (4.5, 0, 4.5, 3.6)}.items():
        w = api.run("root.create_entity", f, ifc_class="IfcWall", name=f"Dinding {nama}")
        panjang = ((x1 - x0) ** 2 + (y1 - y0) ** 2) ** 0.5
        rep = api.run("geometry.add_wall_representation", f, context=body, length=panjang, height=3.0, thickness=0.15)
        api.run("geometry.assign_representation", f, product=w, representation=rep)
        m = np.eye(4)
        if x0 == x1:  # dinding arah Y
            m[:2, :2] = [[0, -1], [1, 0]]
        m[:3, 3] = (x0, y0, 0)
        api.run("geometry.edit_object_placement", f, product=w, matrix=m)
        api.run("spatial.assign_container", f, products=[w], relating_structure=lt1)
    path = tmp_path / "kolom.ifc"
    f.write(str(path))
    return path


def test_dialog_import_menghitung_kolom_fisik(tmp_path):
    from ifc_reader import buka_dan_validasi
    from klasifikasi import ElementType

    info = buka_dan_validasi(_model(tmp_path))
    rk = info.ringkasan_kolom
    assert rk["objek"] == 12 and rk["fisik"] == 6 and rk["digabung"] == 6
    assert rk["per_fungsi"][FUNGSI_UTAMA] == 4 and rk["per_fungsi"][FUNGSI_KANOPI] == 2
    assert info.jumlah_per_kelas[ElementType.COLUMN] == 12  # objek IFC (= elemen yang diekstrak)


def test_dialog_import_menampilkan_kolom_per_fungsi(app, tmp_path):
    from ifc_reader import buka_dan_validasi
    from gui.import_dialog import RingkasanImportDialog
    from PySide6.QtWidgets import QLabel, QTableWidget

    d = RingkasanImportDialog(buka_dan_validasi(_model(tmp_path)))
    t = d.findChild(QTableWidget)
    baris = {t.item(r, 0).text(): int(t.item(r, 2).text()) for r in range(t.rowCount())}
    assert baris["Kolom struktur utama"] == 4 and baris["Kolom sekunder (kanopi / carport / teras / taman)"] == 2
    assert not any(k == "Kolom" for k in baris)  # tidak ada lagi "12 kolom"
    teks = " ".join(w.text() for w in d.findChildren(QLabel))
    assert "12 objek IfcColumn: 6 segmen kolom (pedestal / potongan kolom) digabung" in teks
    d.close()
    d.deleteLater()


def test_estimasi_tipe_kolom_dihitung_per_kolom_fisik(db_sementara, tmp_path):
    from database.penulangan_repository import daftar_tipe
    from database.proyek_repository import create_proyek
    from estimasi_service import ambil_elemen, jalankan_estimasi

    pid = create_proyek("Uji Kolom", str(_model(tmp_path)))
    r = jalankan_estimasi(pid)
    assert any(p.startswith("Kolom: 4 kolom struktur utama, 2 kolom sekunder") for p in r["peringatan"])
    tipe = {t["label"]: t["jumlah_elemen"] for t in daftar_tipe(pid) if t["kelompok"].startswith("KOLOM")}
    assert tipe == {"Kolom K1 (30/30)": 4, "Kolom Sekunder C1 (30/30)": 2}
    # info kolom tersimpan dan dibaca kembali (hitung ulang dimensi memakai pengelompokan yang sama)
    from database.estimasi_repository import _connect

    conn = _connect()
    eid = conn.execute("SELECT id FROM elemen_proyek WHERE nama = 'Pedestal PD-1 30x30 A1'").fetchone()["id"]
    conn.close()
    el = ambil_elemen(eid)
    assert el["info_kolom"]["peran"] == "pedestal" and el["kolom_grup"] == el["info_kolom"]["grup"]
