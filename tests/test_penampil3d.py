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
    meja = next(x for x in peta.values() if x["nama"] == "Meja Kerja")
    assert meja["baris"] == 1 and meja["total"] == 0  # perabot masuk RAB sebagai pekerjaan dari model, harga diisi


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

        d.pilih(meja)  # perabot: masuk RAB sebagai pekerjaan dari model dengan harga 0 (harga diisi pengguna)
        assert d.panel.stack.currentIndex() == 1 and d.panel._data["total"] == 0
        assert d.panel._data["utama"]["baris"][0]["kode"].startswith("LAIN|IfcFurniture|")
        assert d.cari_elemen("Dinding", "Dinding Bata")  # cari lewat combo Jenis -> Nama elemen
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


def _jendela(hal):
    from PySide6.QtWidgets import QMainWindow

    from gui import tema

    w = QMainWindow()
    w.toast = tema.Toast(w)
    w.setCentralWidget(hal)
    w.resize(1300, 820)
    w.show()
    return w


def test_mode_3d_di_halaman_estimasi_kembali_dan_urungkan(qapp, proyek):
    from database.biaya_repository import ringkasan_biaya
    from database.material import SLOT
    from gui.estimasi_page import EstimasiPage

    pid, _path, _m = proyek
    hal = EstimasiPage(pid, "Uji 3D")
    w = _jendela(hal)
    try:
        assert hal.btn_3d.isEnabled() and not hal.mode_3d
        hal._buka_3d()
        d = hal._dialog_3d
        assert hal.mode_3d and d.isVisible() and d.halaman is hal and not hal.halaman_rab.isVisible()
        assert not d.btn_urungkan.isEnabled()  # belum ada perubahan
        dinding = _gid(d._peta, "Dinding Bata Y1")
        d.pilih(dinding)
        lama = ringkasan_biaya(pid)["langsung"]
        slot = d.panel._data["slot"]
        kode = next(iter(slot))
        lain = next(o.kunci for o in SLOT[kode].opsi if o.kunci != slot[kode]["kunci"])
        d._ganti_bahan(d.panel._data["utama"]["elemen_id"], kode, lain, "Dinding Bata Y1")
        assert hal.riwayat.count() == 1 and ringkasan_biaya(pid)["langsung"] != pytest.approx(lama)
        assert d.btn_urungkan.isEnabled() and "Ganti bahan" in d.btn_urungkan.toolTip()
        d.btn_urungkan.click()  # tombol Urungkan di mode 3D memakai riwayat halaman
        assert ringkasan_biaya(pid)["langsung"] == pytest.approx(lama)
        assert d.panel._data["slot"][kode]["kunci"] == slot[kode]["kunci"]  # panel ikut diperbarui
        assert d.btn_ulangi.isEnabled()
        d.btn_ulangi.click()
        assert ringkasan_biaya(pid)["langsung"] != pytest.approx(lama)
        d.btn_kembali.click()  # Kembali ke RAB
        assert not hal.mode_3d and hal.halaman_rab.isVisible()
        hal._esc()  # Esc di tabel RAB = kembali ke daftar proyek (sinyal), bukan masuk 3D
        hal._buka_3d()  # masuk lagi: widget yang sama, tanpa membaca ulang IFC
        assert hal._dialog_3d is d and hal.mode_3d
        d.pilih(dinding)
        hal._esc()  # Esc pertama: batal pilih
        assert hal.mode_3d and d._pilih == ""
        hal._esc()  # Esc kedua: kembali ke RAB
        assert not hal.mode_3d
        hal._buka_3d()
        d.pilih(dinding)
        d.panel.btn_tabel.click()  # Lihat di Tabel RAB: keluar dari mode 3D, tabel Per Elemen tersaring
        assert not hal.mode_3d and hal.mode == hal.MODE_DETAIL
        assert hal.saring.jenis_terpilih() == {"Dinding"} and hal.saring.ringkasan() == "Dinding Bata Y1"
        assert {r["nama_elemen"] for r in hal._data if hal.saring.cocok(r)} == {"Dinding Bata Y1"}
    finally:
        w.close()
        hal.deleteLater()


def test_ubah_jenis_elemen_dari_3d_dan_dialog_tabel_dengan_urungkan(qapp, proyek, monkeypatch):
    """Koreksi jenis elemen lain: combo di panel Model 3D, dialog Koreksi Jenis Elemen Lain dari tabel RAB, dan
    tombol Ubah Jenis di panel Rincian; semuanya masuk riwayat urungkan yang sama."""
    from PySide6.QtWidgets import QComboBox

    from database.biaya_repository import ringkasan_biaya
    from database.estimasi_repository import get_hasil_estimasi_by_proyek
    from gui.estimasi_page import EstimasiPage
    from gui.jenis_dialog import JenisElemenDialog

    pid, _path, m = proyek
    hal = EstimasiPage(pid, "Uji 3D")
    w = _jendela(hal)
    try:
        hal._buka_3d()
        d = hal._dialog_3d
        meja = next(e.gid for e in m.elemen if e.nama == "Meja Kerja")
        d.pilih(meja)
        assert d.panel._data["jenis"] == {"elemen_id": d._peta[meja]["id"], "kunci": "lain", "otomatis": "lain",
                                          "manual": False}
        combo = [c for c in d.panel.findChildren(QComboBox) if c.findData("tidak_dihitung") >= 0]
        assert len(combo) == 1 and combo[0].currentData() == "lain"
        lama = ringkasan_biaya(pid)["langsung"]
        eid = d._peta[meja]["id"]
        d._ubah_jenis(eid, "sanitair:SNT.WASTAFEL", "Meja Kerja")  # sama dengan memilih di combo
        assert hal.riwayat.count() == 1 and "Ubah jenis" in d.btn_urungkan.toolTip()
        assert ringkasan_biaya(pid)["langsung"] > lama  # wastafel punya harga HSPK, perabot harga 0
        assert d.panel._data["jenis"]["kunci"] == "sanitair:SNT.WASTAFEL" and d.panel._data["jenis"]["manual"]
        assert [r["kode"] for b in d.panel._data["bagian"] for r in b["baris"]] == ["SNT.WASTAFEL"]
        d._ubah_jenis(eid, "tidak_dihitung", "Meja Kerja")
        assert d.panel.stack.currentIndex() == 1 and d.panel._data is None  # panel "Tidak dihitung" + combo jenis
        assert any(c.findData("tidak_dihitung") >= 0 and c.currentData() == "tidak_dihitung"
                   for c in d.panel.findChildren(QComboBox))
        d.btn_urungkan.click()
        d.btn_urungkan.click()
        assert ringkasan_biaya(pid)["langsung"] == pytest.approx(lama)
        d.btn_kembali.click()

        # dialog dari tabel RAB (menu Proyek / tombol Ubah Jenis Elemen di panel Rincian)
        dibuka = {}

        def jalankan(self):
            dibuka["pilih"] = self.tabel.currentRow()
            cb = self._combo[eid]
            cb.setCurrentIndex(cb.findData("tidak_dihitung"))
            assert self.perubahan == {eid: "tidak_dihitung"} and self.btn_simpan.isEnabled()
            return JenisElemenDialog.Accepted
        monkeypatch.setattr(JenisElemenDialog, "exec", jalankan)
        hal.panel.minta_jenis_elemen.emit(eid)
        assert dibuka["pilih"] >= 0  # baris elemen itu langsung disorot
        assert not any(r["elemen_id"] == eid for r in map(dict, get_hasil_estimasi_by_proyek(pid)))
        assert hal.riwayat.count() >= 1
        hal.riwayat.undo()
        assert any(r["elemen_id"] == eid for r in map(dict, get_hasil_estimasi_by_proyek(pid)))
        assert ringkasan_biaya(pid)["langsung"] == pytest.approx(lama)
    finally:
        w.close()
        hal.deleteLater()


def test_dialog_jenis_elemen_daftar_saring_dan_kembali_otomatis(qapp, proyek):
    from estimasi_service import ubah_jenis_elemen
    from gui.jenis_dialog import JenisElemenDialog

    pid, _path, _m = proyek
    d0 = JenisElemenDialog(pid)
    meja = next(x for x in d0._data if x["nama"] == "Meja Kerja")
    assert not d0.btn_simpan.isEnabled() and not d0.btn_otomatis.isEnabled()
    d0.deleteLater()
    ubah_jenis_elemen(pid, {meja["id"]: "tidak_dihitung"})
    d = JenisElemenDialog(pid, pilih=meja["id"])
    try:
        x = next(x for x in d._data if x["id"] == meja["id"])
        assert x["manual"] and x["jenis"] == "tidak_dihitung" and x["baris"] == 0
        assert "1 dikoreksi" in d.label_jumlah.text() and d.btn_otomatis.isEnabled()
        d.cari.setText("tidak ada yang cocok")
        assert all(d.tabel.isRowHidden(i) for i in range(d.tabel.rowCount()))
        d.cari.setText("meja")
        assert sum(not d.tabel.isRowHidden(i) for i in range(d.tabel.rowCount())) == 1
        d._semua_otomatis()
        assert d.perubahan == {meja["id"]: None} and d.btn_simpan.isEnabled()
    finally:
        d.deleteLater()


def test_perubahan_dua_arah_antara_mode_3d_tabel_dan_export(qapp, proyek, tmp_path):
    """Perubahan di mode 3D ikut ke tabel RAB dan export; perubahan di tabel ikut terlihat di mode 3D."""
    from database.biaya_repository import ringkasan_biaya
    from database.estimasi_repository import update_volume_estimasi
    from database.material import SLOT
    from export_service import OpsiExport, ambil_data_export, export_excel
    from gui.estimasi_page import EstimasiPage

    pid, _path, _m = proyek
    hal = EstimasiPage(pid, "Uji 3D")
    w = _jendela(hal)
    try:
        hal._buka_3d()
        d = hal._dialog_3d
        dinding = _gid(d._peta, "Dinding Bata Y1")
        d.pilih(dinding)
        slot = d.panel._data["slot"]
        kode = next(iter(slot))
        lain = next(o for o in SLOT[kode].opsi if o.kunci != slot[kode]["kunci"])
        d._ganti_bahan(d.panel._data["utama"]["elemen_id"], kode, lain.kunci, "Dinding Bata Y1")
        total_3d = d.panel._data["total"]
        hal.tutup_3d()
        # 1) tabel RAB sudah memuat bahan baru (tanpa muat ulang manual)
        baris = [r for r in hal._data if r["elemen_id"] == d.panel._data["utama"]["elemen_id"]]
        assert any(r["nama_pekerjaan"] == lain.nama for r in baris)
        assert sum(r["subtotal_biaya"] for r in baris) == pytest.approx(d.panel._data["utama"]["total"])
        # 2) export memakai data yang sama
        data = ambil_data_export(pid)
        assert data["ringkasan"]["langsung"] == pytest.approx(ringkasan_biaya(pid)["langsung"]) \
            if "ringkasan" in data else True
        xlsx = export_excel(tmp_path / "rab.xlsx", data, {}, OpsiExport())
        from openpyxl import load_workbook

        isi = " ".join(str(c.value) for ws in load_workbook(xlsx).worksheets for row in ws.iter_rows() for c in row
                       if c.value)
        assert lain.nama in isi
        # 3) perubahan di tabel (edit volume) terlihat saat masuk mode 3D lagi
        r0 = baris[0]
        update_volume_estimasi(r0["hasil_id"], r0["pekerjaan_id"], r0["volume_pekerjaan"] * 2)
        hal.muat()
        hal._buka_3d()
        d.pilih(dinding)
        assert d.panel._data["total"] > total_3d
        assert any(b["diedit_manual"] for b in d.panel._data["utama"]["baris"])
    finally:
        w.close()
        hal.deleteLater()


def test_cari_elemen_lewat_combo_jenis_dan_nama(qapp, proyek, monkeypatch):
    """Pencarian 3D memakai dua combo: Jenis elemen (Kolom, Balok, ...) lalu Nama elemen jenis itu, per lantai.
    Klik elemen di 3D ikut ditampilkan di combo; nama kembar di satu lantai diberi nomor menurut letaknya."""
    from PySide6.QtCore import Qt

    from gui.penampil3d import Penampil3D, urut_alami

    pid, _path, m = proyek
    d = Penampil3D(pid, "Uji 3D", m)
    try:
        peta = d._peta
        k1, k2, dinding = (_gid(peta, a) for a in ("Kolom K1", "Kolom K2", "Dinding Bata Y1"))
        cj, ce = d.combo_jenis, d.combo_elemen
        jenis = [cj.itemData(i) for i in range(cj.count())]
        assert jenis[0] is None and cj.itemText(0) == f"Semua jenis elemen ({len(m.elemen)})"
        assert {"Kolom", "Balok", "Dinding", "Fondasi"} <= set(jenis)
        assert jenis.index("Fondasi") < jenis.index("Kolom") < jenis.index("Balok") < jenis.index("Dinding")
        assert cj.itemText(cj.findData("Kolom")) == "Kolom (4)"  # 2 pedestal + 2 kolom

        cj.setCurrentIndex(cj.findData("Kolom"))  # seperti dipilih pengguna
        teks = [ce.itemText(i) for i in range(ce.count())]
        assert teks == ["Pilih elemen (4)", "00 Fondasi", "Pedestal PD-1 30x30 K1", "Pedestal PD-1 30x30 K2",
                        "01 Lantai 1", "Kolom K1 30x30", "Kolom K2 30x30"]
        judul = ce.model().item(1)
        assert judul.flags() == Qt.NoItemFlags and ce.itemData(1) is None  # judul lantai tidak dapat dipilih
        i = ce.findData(k2)
        ce.setCurrentIndex(i)
        ce.activated.emit(i)
        assert d._pilih == k2 and d.panel.stack.currentIndex() == 1 and d.panel._data["total"] > 0

        d.pilih(dinding)  # klik di 3D: saringan jenis ikut pindah ke Dinding, nama terpilih ditampilkan
        assert cj.currentData() == "Dinding" and ce.currentData() == dinding
        cj.setCurrentIndex(0)  # Semua jenis: elemen terpilih tetap ditampilkan, nama diberi keterangan jenis
        assert ce.currentData() == dinding and ce.currentText() == "Dinding Bata Y1  ·  Dinding"
        d.pilih("")
        assert ce.currentIndex() == 0

        pesan = []
        monkeypatch.setattr(d, "toast", lambda teks, jenis="sukses": pesan.append(teks))
        d.combo_lantai.setCurrentIndex(1)  # s.d. 00 Fondasi: Kolom K1 (Lantai 1) tersembunyi
        assert d.cari_elemen("Kolom", "Kolom K1") and d._pilih == k1
        assert pesan and "tersembunyi" in pesan[0]
        d.combo_lantai.setCurrentIndex(0)
        assert not d.cari_elemen("Kolom", "Tidak ada")

        peta[k1]["nama"] = peta[k2]["nama"] = "Kolom K 30x30"  # nama kembar di lantai yang sama
        d._siapkan_cari()
        assert cj.currentData() == "Kolom"  # pilihan jenis dipertahankan saat daftar disusun ulang
        assert ce.itemText(ce.findData(k1)) == "Kolom K 30x30  #1"  # x = 0 m
        assert ce.itemText(ce.findData(k2)) == "Kolom K 30x30  #2"  # x = 4 m
        assert sorted(["K10", "K2", "K1"], key=urut_alami) == ["K1", "K2", "K10"]

        d.fokus_cari()  # Ctrl+F membuka daftar jenis
        assert d.combo_jenis.hasFocus() or not d.isVisible()
        d.combo_jenis.hidePopup()
    finally:
        d.close()
        d.deleteLater()


def test_file_ifc_hilang_memberi_pesan(qapp, db_sementara, monkeypatch):
    from PySide6.QtWidgets import QMessageBox

    from gui import penampil3d

    pesan = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: pesan.append(a[2]))
    assert penampil3d.buka_penampil(None, 1, "x", "/tidak/ada/model.ifc") is None
    assert "tidak ditemukan" in pesan[0]


def test_grafis_3d_tidak_tersedia_memberi_pesan_dan_panel_tetap_jalan(qapp, proyek, monkeypatch):
    """KNF-11: bila Qt Quick tidak memakai API grafis 3D (driver tanpa Direct3D 11 / OpenGL 3.3), jendela 3D
    menampilkan pesan, tidak berhenti, dan panel biaya tetap dapat dipakai lewat pencarian."""
    from gui.penampil3d import Penampil3D

    pid, _path, m = proyek
    monkeypatch.setattr(Penampil3D, "render_3d_aktif", lambda self: False)
    d = Penampil3D(pid, "Uji 3D", m)
    try:
        d._cek_render()
        assert d._label_galat is not None and "tidak dapat digambar" in d._label_galat.text()
        d._cek_render()  # dipanggil lagi (mis. jendela ditampilkan ulang): pesan tidak bertumpuk
        assert sum(1 for c in d.quick.children() if c is d._label_galat) == 1
        assert d.cari_elemen("Kolom", "Kolom K1")
        assert d._pilih and d.panel.stack.currentIndex() == 1 and d.panel._data["total"] > 0
    finally:
        d.close()
        d.deleteLater()


# ---------------------------------------------------------------- besi beton 3D


def _model_besi(tmp_path):
    """Model uji + 4 besi D13 tegak di sudut Kolom K1 (IfcReinforcingBar ekstrusi, induk lewat HostGlobalId)."""
    import ifcopenshell
    import ifcopenshell.api as api

    path = _model(tmp_path)
    f = ifcopenshell.open(str(path))
    body = next(c for c in f.by_type("IfcGeometricRepresentationSubContext") if c.ContextIdentifier == "Body")
    kolom = next(c for c in f.by_type("IfcColumn") if c.Name == "Kolom K1 30x30")
    lantai = kolom.ContainedInStructure[0].RelatingStructure
    for i, (dx, dy) in enumerate(((-0.1, -0.1), (0.1, -0.1), (0.1, 0.1), (-0.1, 0.1))):
        bar = api.run("root.create_entity", f, ifc_class="IfcReinforcingBar", name=f"Tulangan D13 K1-{i + 1}")
        bar.NominalDiameter = 0.013
        profil = f.create_entity("IfcCircleProfileDef", ProfileType="AREA", Radius=0.0065)
        rep = api.run("geometry.add_profile_representation", f, context=body, profile=profil, depth=3.6)
        api.run("geometry.assign_representation", f, product=bar, representation=rep)
        m = np.eye(4)
        m[:3, 3] = (dx, dy, -0.1)
        api.run("geometry.edit_object_placement", f, product=bar, matrix=m)
        ps = api.run("pset.add_pset", f, product=bar, name="CostStruct_Tulangan")
        api.run("pset.edit_pset", f, pset=ps, properties={"HostGlobalId": kolom.GlobalId})
        api.run("spatial.assign_container", f, products=[bar], relating_structure=lantai)
    f.write(str(path))
    return path, kolom.GlobalId


def test_tabung_besi_segi_enam():
    from model3d import tabung

    pos, nrm = tabung(np.array([[0.0, 0, 0], [1, 1, 1]]), np.array([[0.0, 0, 2], [1, 1, 1]]), np.array([0.01, 0.01]))
    assert pos.shape == (6 * 6, 3)  # segmen kedua (panjang nol) dibuang; 6 sisi x 2 segitiga x 3 titik
    assert np.allclose(np.linalg.norm(nrm, axis=1), 1.0)
    assert np.allclose(np.hypot(pos[:, 0], pos[:, 1]), 0.01)  # semua titik di permukaan tabung r = 1 cm
    assert pos[:, 2].min() == pytest.approx(0) and pos[:, 2].max() == pytest.approx(2)


def test_besi_dikelompokkan_per_elemen_induk(tmp_path):
    from model3d import muat_besi, muat_model3d

    path, k1 = _model_besi(tmp_path)
    m = muat_model3d(str(path))
    besi = muat_besi(str(path), m.geser)
    assert [(b.gid, b.host, b.n_batang) for b in besi] == [(f"besi:{k1}", k1, 4)]
    b = besi[0]
    assert b.kotak[2] == pytest.approx(-0.1, abs=0.001) and b.kotak[5] == pytest.approx(3.5, abs=0.001)
    assert b.kotak[3] - b.kotak[0] == pytest.approx(0.2 + 0.013, abs=0.002)  # 4 besi di sudut, jarak 20 cm + diameter
    assert all(e.ifc != "IfcReinforcingBar" for e in m.elemen)  # besi tidak ikut dimuat di tampilan biasa


def test_mode_besi_beton_di_penampil(qapp, db_sementara, tmp_path, monkeypatch):
    from PySide6.QtWidgets import QMessageBox

    from database.proyek_repository import create_proyek
    from estimasi_service import jalankan_estimasi
    from gui.penampil3d import TAMPIL_BESI, WARNA_PILIH, Penampil3D
    from model3d import muat_model3d

    path, k1 = _model_besi(tmp_path)
    pid = create_proyek("Uji Besi", str(path))
    jalankan_estimasi(pid)
    d = Penampil3D(pid, "Uji Besi", muat_model3d(str(path)))
    d.path_ifc = str(path)
    try:
        assert d._besi is None  # dibaca saat mode besi pertama kali dipilih
        d.combo_tampil.setCurrentIndex(d.combo_tampil.findData(TAMPIL_BESI))
        gid = f"besi:{k1}"
        assert list(d._besi) == [gid] and d.adegan_besi.keadaan(gid)["tampil"]
        dinding = _gid(d._peta, "Dinding Bata Y1")
        assert not d.adegan.keadaan(dinding)["tampil"]  # mode besi: hanya beton (tembus pandang) + besi
        kk = d.adegan.keadaan(k1)
        assert kk["tampil"] and kk["buram"] < 0.5 and not kk["klik"]
        d.pilih(gid)  # klik besi -> elemen induknya, pembesian ada di rinciannya
        assert d._pilih == k1 and d.adegan_besi.keadaan(gid)["warna"].name() == WARNA_PILIH
        kode = {r["kode"] for b in d.panel._data["bagian"] for r in b["baris"]}
        assert any(k.startswith("BSI.KOLOM") for k in kode)
        assert "4 batang dimodelkan" in d.panel._pesan
        d.combo_tampil.setCurrentIndex(0)
        assert not d.adegan_besi.keadaan(gid)["tampil"]  # besi hanya tampil di mode besi
    finally:
        d.close()
        d.deleteLater()

    # model tanpa besi beton: pesan, pilihan kembali ke tampilan sebelumnya
    pid2 = create_proyek("Tanpa Besi", str(_model(tmp_path / "x" if (tmp_path / "x").mkdir() is None else tmp_path)))
    pesan = []
    monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: pesan.append(a[2]))
    jalankan_estimasi(pid2)
    from database.proyek_repository import get_proyek

    p2 = get_proyek(pid2)["path_file_ifc"]
    d2 = Penampil3D(pid2, "Tanpa Besi", muat_model3d(p2))
    d2.path_ifc = p2
    try:
        d2.combo_tampil.setCurrentIndex(d2.combo_tampil.findData(TAMPIL_BESI))
        assert pesan and "tidak memuat besi beton" in pesan[0]
        assert d2.combo_tampil.currentData() != TAMPIL_BESI
    finally:
        d2.close()
        d2.deleteLater()


def test_struktur_saja_dengan_saringan_lantai_menyembunyikan_rangka_atap(qapp, db_sementara):
    """Rangka atap ikut tampil di mode Struktur saja, tetapi saringan "s.d. lantai" tetap berlaku: batang rangka
    atap di lantai atap tidak boleh melayang di atas denah lantai 1."""
    from conftest import AC20
    from database.proyek_repository import create_proyek
    from estimasi_service import jalankan_estimasi
    from gui.penampil3d import TAMPIL_STRUKTUR, Penampil3D
    from model3d import muat_model3d

    pid = create_proyek("AC20", str(AC20))
    jalankan_estimasi(pid)
    m = muat_model3d(str(AC20))
    rangka = [e for e in m.elemen if e.termasuk == "rangka_atap"]
    assert rangka
    d = Penampil3D(pid, "AC20", m)
    try:
        d.combo_tampil.setCurrentIndex(d.combo_tampil.findData(TAMPIL_STRUKTUR))
        assert all(d.adegan.keadaan(e.gid)["tampil"] for e in rangka)  # semua lantai: rangka atap tampil
        d.combo_lantai.setCurrentIndex(1)  # lantai terbawah saja
        batas = d.combo_lantai.currentData()
        di_atas = [e for e in rangka if e.elevasi is not None and e.elevasi > batas + 0.01]
        assert di_atas and not any(d.adegan.keadaan(e.gid)["tampil"] for e in di_atas)
    finally:
        d.close()
        d.deleteLater()
