"""Penampil Model 3D: geometri dari IFC (model3d.py), kebutuhan biaya elemen terpilih beserta elemen di bawahnya
(biaya_elemen.py), dan jendela 3D + panel biaya (gui/penampil3d.py)."""

import os

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication

    from gui import tema

    app = QApplication.instance() or QApplication([])
    tema.terapkan(app, "hitam_kuning")
    if getattr(app, "_terjemahan_qt", None) is None:
        # seperti aplikasi sungguhan (splash_screen): penerjemah Python terpasang saat QML dimuat
        from gui.galat import pasang_terjemahan

        pasang_terjemahan(app)
    return app


def _model(tmp_path):
    """Kolom K1 = pedestal (lantai Fondasi) + kolom (Lantai 1) di atas footplate F1 dan lantai kerja; kolom K2;
    dinding Y1 di atas sloof S1; meja (perabot, tidak dihitung)."""
    import ifcopenshell.api as api

    f = api.run("project.create_file", version="IFC4")
    proj = api.run("root.create_entity", f, ifc_class="IfcProject", name="Uji 3D")
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

    def kotak(kelas, nama, x, y, z0, z1, bx, by, lantai, pre=None, pset=None):
        el = api.run("root.create_entity", f, ifc_class=kelas, name=nama, predefined_type=pre)
        profil = f.create_entity("IfcRectangleProfileDef", ProfileType="AREA", XDim=bx, YDim=by)
        rep = api.run("geometry.add_profile_representation", f, context=body, profile=profil, depth=z1 - z0)
        api.run("geometry.assign_representation", f, product=el, representation=rep)
        m = np.eye(4)
        m[:3, 3] = (x, y, z0)
        api.run("geometry.edit_object_placement", f, product=el, matrix=m)
        if pset:
            ps = api.run("pset.add_pset", f, product=el, name=pset[0])
            api.run("pset.edit_pset", f, pset=ps, properties=pset[1])
        api.run("spatial.assign_container", f, products=[el], relating_structure=lantai)
        return el

    beban = ("Pset_ColumnCommon", {"LoadBearing": True})
    for g, x in (("1", 0.0), ("2", 4.0)):
        kotak("IfcFooting", f"Footplate F1 {g}", x, 0, -1.2, -0.95, 1.0, 1.0, fond, "PAD_FOOTING")
        kotak("IfcBuildingElementProxy", f"Lantai Kerja LK {g}", x, 0, -1.25, -1.2, 1.1, 1.1, fond)
        kotak("IfcColumn", f"Pedestal PD-1 30x30 K{g}", x, 0, -0.95, -0.1, 0.3, 0.3, fond, "COLUMN", beban)
        kotak("IfcColumn", f"Kolom K{g} 30x30", x, 0, -0.1, 3.5, 0.3, 0.3, lt1, "COLUMN", beban)
    kotak("IfcBeam", "Sloof S1 20x30", 2.0, 0, -0.4, -0.1, 3.7, 0.2, fond, "BEAM")
    kotak("IfcWall", "Dinding Bata Y1", 2.0, 0, -0.1, 3.0, 3.7, 0.15, lt1)
    kotak("IfcFurniture", "Meja Kerja", 2.0, 2.0, -0.1, 0.65, 1.2, 0.6, lt1)
    path = tmp_path / "uji3d.ifc"
    f.write(str(path))
    return path


@pytest.fixture
def proyek(db_sementara, tmp_path):
    from database.proyek_repository import create_proyek
    from estimasi_service import jalankan_estimasi
    from model3d import muat_model3d

    path = _model(tmp_path)
    pid = create_proyek("Uji 3D", str(path))
    jalankan_estimasi(pid)
    return pid, path, muat_model3d(str(path))


def _gid(peta, awalan):
    return next(g for g, x in peta.items() if (x["nama"] or "").startswith(awalan))


# ---------------------------------------------------------------- geometri


def test_model3d_geometri_lantai_dan_koordinat(tmp_path):
    from model3d import muat_model3d

    m = muat_model3d(str(_model(tmp_path)))
    nama = {e.nama: e for e in m.elemen}
    assert len(m.elemen) == 11 and "Meja Kerja" in nama  # perabot ikut ditampilkan, walau tidak dihitung
    assert [n for n, _z in m.lantai] == ["00 Fondasi", "01 Lantai 1"]
    f = nama["Footplate F1 1"]
    assert f.lantai == "00 Fondasi" and f.elevasi == pytest.approx(-1.2)
    assert f.kotak[2] == pytest.approx(-1.2, abs=1e-6) and f.kotak[5] == pytest.approx(-0.95, abs=1e-6)  # IFC dunia
    assert len(f.posisi) % 3 == 0 and f.posisi.shape == f.normal.shape
    assert np.allclose(np.linalg.norm(f.normal, axis=1), 1.0, atol=1e-5)
    mn, mx = m.batas()
    assert mn[1] == pytest.approx(0.0, abs=1e-5)  # muka terbawah (lantai kerja -1,25) digeser ke y = 0
    assert mx[1] == pytest.approx(3.5 + 1.25, abs=1e-4)  # Y ke atas: puncak kolom
    # IFC (x, y, z) -> tampilan (x, z, -y): meja di y = +2 IFC berada di z negatif
    assert nama["Meja Kerja"].batas()[1][2] < 0


def test_segitiga_rata_membuang_segitiga_tanpa_luas():
    from model3d import ke_y_atas, segitiga_rata

    v = np.array([[0, 0, 0], [1, 0, 0], [0, 1, 0], [2, 0, 0]], float)
    pos, nrm = segitiga_rata(v, np.array([0, 1, 2, 0, 1, 3]))  # segitiga kedua segaris
    assert pos.shape == (3, 3) and np.allclose(nrm, [0, 0, 1])
    assert np.allclose(ke_y_atas(np.array([[1.0, 2.0, 3.0]]), (1, 1, 1)), [[0, 2, -1]])


def test_di_bawah_untuk_lantai_kerja():
    from model3d import di_bawah

    fondasi = (-0.5, -0.5, -1.2, 0.5, 0.5, -0.95)
    assert di_bawah(fondasi, (-0.55, -0.55, -1.25, 0.55, 0.55, -1.2))
    assert not di_bawah(fondasi, (-0.55, -0.55, -2.0, 0.55, 0.55, -1.9))  # terlalu jauh di bawah
    assert not di_bawah(fondasi, (3.0, 3.0, -1.25, 4.0, 4.0, -1.2))  # tidak bertumpuk di denah


# ---------------------------------------------------------------- biaya elemen


def test_kolom_menampilkan_pedestal_fondasi_dan_tanah_di_bawahnya(proyek):
    from biaya_elemen import URUT_PERAN, peta_biaya, rincian

    pid, _path, m = proyek
    peta = peta_biaya(pid)
    kotak = {e.gid: e.kotak for e in m.elemen}
    k1 = _gid(peta, "Kolom K1")
    r = rincian(pid, k1, kotak, True, peta)
    peran = {b["judul"]: b["peran"] for b in r["bagian"][1:]}
    assert peran == {"Pedestal PD-1 30x30 K1": "Pedestal (bagian kolom ini)",
                     "Footplate F1 1": "Fondasi di bawah kolom",
                     "Lantai Kerja LK 1": "Pekerjaan tanah di bawah fondasi"}
    assert r["bagian"][0]["judul"] == "Kolom K1 30x30" and r["bagian"][0]["peran"] == "Elemen terpilih"
    urut = [URUT_PERAN.index(b["peran"]) for b in r["bagian"][1:]]
    assert urut == sorted(urut)  # pedestal -> fondasi -> tanah
    assert r["total"] == pytest.approx(sum(peta[g]["total"] for g in [k1, *r["terkait"]]))
    assert r["total"] > r["total_utama"] > 0
    # tanpa elemen terkait: hanya kolom itu sendiri
    sendiri = rincian(pid, k1, kotak, False, peta)
    assert len(sendiri["bagian"]) == 1 and sendiri["total"] == pytest.approx(r["total_utama"])
    # fondasi K2 tidak ikut di K1
    assert not any("2" in j for j in peran)


def test_fondasi_dan_dinding_menampilkan_elemen_di_bawahnya(proyek):
    from biaya_elemen import elemen_terkait, peta_biaya

    pid, _path, m = proyek
    peta = peta_biaya(pid)
    kotak = {e.gid: e.kotak for e in m.elemen}
    f1 = elemen_terkait(_gid(peta, "Footplate F1 1"), peta, kotak)
    assert [(peta[g]["nama"], p) for g, p in f1] == [("Lantai Kerja LK 1", "Pekerjaan tanah di bawah fondasi")]
    dinding = elemen_terkait(_gid(peta, "Dinding Bata Y1"), peta, kotak)
    assert ("Sloof S1 20x30", "Sloof di bawah dinding") in [(peta[g]["nama"], p) for g, p in dinding]


def test_peta_biaya_sama_dengan_hasil_estimasi(proyek):
    from biaya_elemen import peta_biaya
    from database.estimasi_repository import get_hasil_estimasi_by_proyek

    pid, _path, _m = proyek
    peta = peta_biaya(pid)
    total_rab = sum(r["subtotal_biaya"] for r in get_hasil_estimasi_by_proyek(pid))
    assert sum(x["total"] for x in peta.values()) == pytest.approx(total_rab)
    assert "Meja Kerja" not in {x["nama"] for x in peta.values()}  # perabot tidak masuk RAB


# ---------------------------------------------------------------- objek Qt


def test_backend_kamera_memilih_putaran_terdekat_dan_zoom(qapp):
    from PySide6.QtGui import QVector3D

    from gui.penampil3d import Backend

    b = Backend()
    b._rotasi = QVector3D(-30, 350, 0)
    b.kamera(rotasi=QVector3D(-28, -35, 0), animasi=False)
    assert b.rotasi.y() == pytest.approx(325)  # bukan berputar balik 385 derajat
    j = b.jarak
    b.zoom(120)
    assert b.jarak < j
    b.zoom(-240)
    assert b.jarak > j
    assert b.jarak_muat(10) > b.jarak_muat(5) > 0


def test_adegan_hanya_mengirim_baris_yang_berubah(qapp):
    from PySide6.QtGui import QColor

    from gui.penampil3d import AdeganModel

    a = AdeganModel()
    a.atur([("a", None), ("b", None)])
    k = {"warna": QColor("#ff0000"), "buram": 1.0, "tampil": True, "klik": True, "sinar": 0.0}
    terima = []
    a.dataChanged.connect(lambda i, j, peran: terima.append((i.row(), j.row())))
    assert a.perbarui({"a": k, "b": dict(k)}) == 2
    assert a.perbarui({"a": k, "b": dict(k)}) == 0  # tidak ada perubahan: QML tidak diganggu
    assert a.perbarui({"b": {**k, "tampil": False}}) == 1 and terima[-1] == (1, 1)
    assert a.data(a.index(1), AdeganModel.TAMPIL) is False and a.data(a.index(0), AdeganModel.GID) == "a"


def test_skala_biaya_dan_peringkat():
    from gui.penampil3d import SKALA_BIAYA, peringkat_biaya, warna_skala

    assert warna_skala(0).name() == SKALA_BIAYA[0] and warna_skala(1).name() == SKALA_BIAYA[-1]
    p = peringkat_biaya({"a": {"total": 10.0}, "b": {"total": 0.0}, "c": {"total": 50.0}, "d": {"total": 20.0}})
    assert p == {"a": 0.0, "d": 0.5, "c": 1.0}  # elemen tanpa biaya tidak diberi peringkat


def test_panel_biaya_urutan_pekerjaan_dan_per_bagian(qapp, proyek):
    from PySide6.QtWidgets import QComboBox

    from biaya_elemen import peta_biaya, rincian
    from database.material_repository import ringkasan_opsi
    from gui.penampil3d import PanelBiaya3D, _Baris

    pid, _path, m = proyek
    peta = peta_biaya(pid)
    kotak = {e.gid: e.kotak for e in m.elemen}
    data = rincian(pid, _gid(peta, "Dinding Bata Y1"), kotak, True, peta)
    p = PanelBiaya3D()
    assert p.stack.currentIndex() == 0  # belum ada yang dipilih
    p.tampilkan(data, ringkasan_opsi(), True)
    n_baris = sum(len(b["baris"]) for b in data["bagian"])
    assert p.stack.currentIndex() == 1 and len(p.konten.findChildren(_Baris)) == n_baris
    combo = [c for c in p.konten.findChildren(QComboBox)]
    assert len(combo) == len(data["slot"]) >= 1  # pasangan dinding, plesteran, cat, ...
    minta = []
    p.minta_bahan.connect(lambda *a: minta.append(a))
    combo[0].setCurrentIndex((combo[0].currentIndex() + 1) % combo[0].count())
    assert not minta  # ditunda sampai sinyal combo selesai (panel dibangun ulang)
    qapp.processEvents()
    assert minta and minta[0][0] == data["utama"]["elemen_id"]
    p._ganti_mode(PanelBiaya3D.PER_BAGIAN)
    assert len(p.konten.findChildren(_Baris)) == n_baris  # isi sama, hanya pengelompokannya
    p.tidak_dihitung("Meja Kerja", "Furniture", "01 Lantai 1", "tidak dihitung")
    assert p.btn_tabel.isHidden()
    p.kosong()
    assert p.stack.currentIndex() == 0


def test_jendela_3d_pilih_warna_saring_dan_ganti_bahan(qapp, proyek):
    from database.biaya_repository import ringkasan_biaya
    from database.material import SLOT
    from gui.penampil3d import TAMPIL_STRUKTUR, TAMPIL_TEMBUS, WARNA_PILIH, WARNA_TERKAIT, Penampil3D

    pid, _path, m = proyek
    d = Penampil3D(pid, "Uji 3D", m)  # tanpa macet walau penerjemah Python terpasang (gui/galat.py)
    try:
        assert d.galat_qml == []
        from PySide6.QtCore import QCoreApplication

        assert QCoreApplication.translate("QLineEdit", "Select All") == "Pilih Semua"  # dipasang kembali
        peta = d._peta
        k1, pd1, f1, lk1 = (_gid(peta, a) for a in ("Kolom K1", "Pedestal PD-1 30x30 K1", "Footplate F1 1",
                                                     "Lantai Kerja LK 1"))
        dinding, meja = _gid(peta, "Dinding Bata Y1"), next(e.gid for e in m.elemen if e.nama == "Meja Kerja")
        d.pilih(k1)
        assert d.panel.stack.currentIndex() == 1
        assert d.adegan.keadaan(k1)["warna"].name() == WARNA_PILIH
        assert {d.adegan.keadaan(g)["warna"].name() for g in (pd1, f1, lk1)} == {WARNA_TERKAIT}
        d._atur_terkait(False)  # "Termasuk pedestal, fondasi ..." dimatikan
        assert d.adegan.keadaan(f1)["warna"].name() != WARNA_TERKAIT
        d._atur_terkait(True)

        d.combo_lantai.setCurrentIndex(1)  # s.d. 00 Fondasi: lantai 1 disembunyikan
        assert not d.adegan.keadaan(k1)["tampil"] and d.adegan.keadaan(pd1)["tampil"]
        d.combo_lantai.setCurrentIndex(0)
        d.combo_tampil.setCurrentIndex(d.combo_tampil.findData(TAMPIL_STRUKTUR))
        assert not d.adegan.keadaan(dinding)["tampil"] and d.adegan.keadaan(k1)["tampil"]
        d.combo_tampil.setCurrentIndex(d.combo_tampil.findData(TAMPIL_TEMBUS))
        kd = d.adegan.keadaan(dinding)
        assert kd["tampil"] and kd["buram"] < 0.5 and not kd["klik"]  # klik menembus ke kolom di baliknya
        d.combo_tampil.setCurrentIndex(0)

        d.pilih(meja)  # ada di model, tidak masuk RAB
        assert d.panel.stack.currentIndex() == 1 and d.panel.btn_tabel.isHidden()
        d.cari.setText("dinding bata")
        d._cari_enter()
        assert d._pilih == dinding

        lama = ringkasan_biaya(pid)["langsung"]
        slot = d.panel._data["slot"]
        kode = next(iter(slot))
        lain = next(o.kunci for o in SLOT[kode].opsi if o.kunci != slot[kode]["kunci"])
        d._ganti_bahan(d.panel._data["utama"]["elemen_id"], kode, lain, "Dinding Bata Y1")
        assert ringkasan_biaya(pid)["langsung"] != pytest.approx(lama)
        assert d.panel._data["slot"][kode]["kunci"] == lain and d.panel._data["slot"][kode]["khusus"]

        d.pilih("")
        assert d.panel.stack.currentIndex() == 0 and d.adegan.keadaan(k1)["warna"].name() != WARNA_PILIH
    finally:
        d.close()
        d.deleteLater()


def test_halaman_estimasi_membuka_model_3d_dengan_urungkan(qapp, proyek):
    from database.biaya_repository import ringkasan_biaya
    from database.material import SLOT
    from gui.estimasi_page import EstimasiPage

    pid, _path, _m = proyek
    hal = EstimasiPage(pid, "Uji 3D")
    try:
        assert hal.btn_3d.isEnabled()
        hal._buka_3d()
        d = hal._dialog_3d
        assert d is not None and d.isVisible() and d.halaman is hal
        dinding = _gid(d._peta, "Dinding Bata Y1")
        d.pilih(dinding)
        lama = ringkasan_biaya(pid)["langsung"]
        slot = d.panel._data["slot"]
        kode = next(iter(slot))
        lain = next(o.kunci for o in SLOT[kode].opsi if o.kunci != slot[kode]["kunci"])
        d._ganti_bahan(d.panel._data["utama"]["elemen_id"], kode, lain, "Dinding Bata Y1")
        assert hal.riwayat.count() == 1 and ringkasan_biaya(pid)["langsung"] != pytest.approx(lama)
        d.urungkan()  # Ctrl+Z di jendela 3D memakai riwayat halaman
        assert ringkasan_biaya(pid)["langsung"] == pytest.approx(lama)
        assert d.panel._data["slot"][kode]["kunci"] == slot[kode]["kunci"]  # panel ikut diperbarui
        d.panel.btn_tabel.click()  # Lihat di Tabel RAB
        assert hal.mode == hal.MODE_DETAIL and hal.kolom_cari.text() == "Dinding Bata Y1"
        d.close()
        hal._buka_3d()  # dibuka lagi: jendela yang sama, tanpa membaca ulang IFC
        assert hal._dialog_3d is d and d.isVisible()
    finally:
        if hal._dialog_3d is not None:
            hal._dialog_3d.close()
        hal.deleteLater()


def test_file_ifc_hilang_memberi_pesan(qapp, db_sementara, monkeypatch):
    from PySide6.QtWidgets import QMessageBox

    from gui import penampil3d

    pesan = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: pesan.append(a[2]))
    assert penampil3d.buka_penampil(None, 1, "x", "/tidak/ada/model.ifc") is None
    assert "tidak ditemukan" in pesan[0]
