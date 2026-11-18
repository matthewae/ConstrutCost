"""Komponen antarmuka bersama: ikon, kepala dialog, teks tabel kosong, kotak pesan, dialog responsif."""

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(scope="module")
def app():
    from PySide6.QtWidgets import QApplication

    from gui import tema

    a = QApplication.instance() or QApplication([])
    tema.terapkan(a, "hitam_kuning")
    return a


@pytest.mark.parametrize("nama", ["cari", "panel", "info", "galat", "sukses", "tanya", "peringatan", "folder",
                                  "parameter", "dimensi", "kubus", "besi", "kalender", "import", "tutup", "rupiah",
                                  "persen", "ciut", "lebar"])
def test_ikon_baru_tergambar(app, nama):
    from PySide6.QtGui import QColor

    from gui import tema

    img = tema.ikon(nama, "#ffffff").pixmap(40, 40).toImage()
    assert any(QColor(img.pixel(x, y)).alpha() > 0 for x in range(40) for y in range(40)), nama


def test_kepala_dialog(app):
    from gui import tema

    w, judul, sub = tema.kepala_dialog("Info Proyek", "Kop laporan RAB.", "file")
    assert judul.text() == "Info Proyek" and judul.objectName() == "judulDialog"
    assert sub.text() == "Kop laporan RAB." and not sub.isHidden()
    w2, _, kosong = tema.kepala_dialog("Tanpa keterangan")
    assert kosong.isHidden()
    w.deleteLater()
    w2.deleteLater()


def test_teks_tabel_kosong_mengikuti_isi(app):
    from PySide6.QtWidgets import QTableWidget

    from gui import tema

    t = QTableWidget(0, 2)
    tema.pasang_teks_kosong(t, "Belum ada data", "Tambah baris.")
    t.resize(400, 300)
    t.show()
    app.processEvents()
    assert t._teks_kosong.label.isVisible()
    t.setRowCount(1)
    app.processEvents()
    assert not t._teks_kosong.label.isVisible()
    t.setRowCount(0)
    app.processEvents()
    assert t._teks_kosong.label.isVisible()
    t.close()


def test_kotak_pesan_memakai_lencana_tema(app):
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QMessageBox

    kotak = QMessageBox(QMessageBox.Question, "Hapus", "Hapus proyek?")
    QTimer.singleShot(50, lambda: kotak.done(0))
    kotak.exec()
    assert kotak.property("_dihias")
    assert not kotak.iconPixmap().isNull()


def test_dialog_export_responsif(app, db_sementara):
    from database.proyek_repository import create_proyek
    from gui.export_dialog import ExportDialog

    pid = create_proyek("Uji", None)
    d = ExportDialog(pid, "Uji")
    d.show()
    d.setMinimumWidth(700)
    d.resize(1100, 700)
    app.processEvents()
    g = d._grid_kartu
    assert [g.getItemPosition(g.indexOf(k))[:2] for k in d._kartu_ringkas] == [(0, 0), (0, 1), (0, 2), (0, 3)]
    d.resize(760, 700)
    app.processEvents()
    assert [g.getItemPosition(g.indexOf(k))[:2] for k in d._kartu_ringkas] == [(0, 0), (0, 1), (1, 0), (1, 1)]
    f = d._grid_info
    assert {f.getItemPosition(f.indexOf(kanan))[1] for _, kanan in d._isian_info} == {1}  # satu kolom isian
    d.close()
    d.deleteLater()


def test_pengaturan_status_perubahan(app, db_sementara):
    from gui.pengaturan_page import PengaturanPage

    h = PengaturanPage()
    assert h.label_status.text() == "Tersimpan"
    h.cek_excel.setChecked(not h.cek_excel.isChecked())
    assert "belum disimpan" in h.label_status.text()
    assert h.btn_simpan.isEnabled()
    h.deleteLater()


def test_pengaturan_isi_kebutuhan_bahan(app, db_sementara):
    """KF-10/KF-17: bawaan isi dokumen 'Kebutuhan bahan proyek & per elemen' diatur dari halaman Pengaturan,
    tersimpan, dipakai dialog Export, dan kembali dicentang saat Reset ke Default."""
    from database.preferensi_repository import muat_preferensi, reset_preferensi
    from database.proyek_repository import create_proyek
    from gui.export_dialog import ExportDialog
    from gui.pengaturan_page import PengaturanPage

    h = PengaturanPage()
    assert h.cek_bahan.isChecked()
    h.cek_bahan.setChecked(False)
    assert "belum disimpan" in h.label_status.text()
    h._simpan()
    assert muat_preferensi().isi_bahan is False

    h2 = PengaturanPage()  # dibuka ulang: nilai tersimpan tampil
    assert not h2.cek_bahan.isChecked()
    h2.cek_rekap.setChecked(not h2.cek_rekap.isChecked())  # simpan pengaturan lain tidak mengubah isi_bahan
    h2._simpan()
    assert muat_preferensi().isi_bahan is False
    d = ExportDialog(create_proyek("Uji", None), "Uji")  # pilihan awal dialog Export mengikuti Pengaturan
    assert not d.cek_bahan.isChecked()
    d.deleteLater()

    reset_preferensi()
    h3 = PengaturanPage()
    assert h3.cek_bahan.isChecked()
    for w in (h, h2, h3):
        w.deleteLater()


def test_splash_indikator_tahap(app):
    from gui.splash_screen import SplashScreen

    s = SplashScreen()
    assert [l.property("nama") for l in s.langkah] == ["Database", "Data proyek", "Antarmuka"]
    s._perbarui_langkah(1, "Memuat data proyek tersimpan...")
    teks = [l.text() for l in s.langkah]
    assert "✓" in teks[0] and "●" in teks[1] and "●" in teks[2]
    assert s.langkah[1].toolTip() == "Memuat data proyek tersimpan..."
    s._perbarui_langkah(3)  # "Siap.": semua tahap selesai
    assert all("✓" in l.text() for l in s.langkah)
    s.deleteLater()


def test_gaya_fusion_terpasang_sekali(app):
    """Windows: gaya bawaan windows11 mengabaikan sebagian stylesheet, jadi aplikasi selalu memakai Fusion."""
    from gui import tema

    assert str(app.property("gaya_dasar")).lower() == "fusion"
    gaya = app.style()
    tema.terapkan(app, "terang_emas")  # ganti tema: stylesheet baru, gaya dasar tidak dibuat ulang
    tema.terapkan(app, "hitam_kuning")
    assert str(app.property("gaya_dasar")).lower() == "fusion"
    assert app.style() is not None and gaya is not None


def test_dialog_import_tombol_selalu_terlihat(app):
    """Model dengan banyak jenis elemen di layar pendek: ringkasan digulir, tombol Import tetap di dalam
    dialog (tidak perlu menggeser jendela)."""
    from ifc_reader import InfoFileIFC
    from klasifikasi import ElementType
    from gui.import_dialog import RingkasanImportDialog

    info = InfoFileIFC(
        path="rumah.ifc", nama_file="Rumah_Tipe90_2Lantai_Carport.ifc", ukuran_byte=12_000_000, skema="IFC4",
        aplikasi=None, satuan_panjang="meter",
        lantai=[("00 FONDASI", -1.7), ("01 LANTAI 1", 0.0), ("02 LANTAI 2", 3.5), ("03 ATAP", 6.8)],
        jumlah_per_kelas={k: 10 for k in ElementType if k != ElementType.UNKNOWN},
        tidak_dihitung={
            "batang rangka (IfcMember)": {"jumlah": 94, "contoh": ["Rangka Carport 50x50"], "catatan": None},
            "elemen generik (IfcBuildingElementProxy)": {"jumlah": 50, "contoh": ["Kitchen Set"], "catatan": None},
        },
    )
    d = RingkasanImportDialog(info)
    tinggi_layar = app.primaryScreen().availableGeometry().height()
    assert d.height() <= int(tinggi_layar * 0.88)
    d.show()
    app.processEvents()
    bawah = d.btn_import.mapTo(d, d.btn_import.rect().bottomLeft()).y()
    assert 0 < bawah <= d.height()
    assert d.edit_nama.isVisible() and d.btn_import.isEnabled()
    # isi ringkasan lebih tinggi dari ruang yang tersedia -> digulir
    assert d.gulir.verticalScrollBar().maximum() > 0
    d.close()
    d.deleteLater()


def test_atur_lebar_baru_tidak_ditimpa_penjaga_lebar_lama(app):
    """Pindah tab (mis. Per Elemen -> Kebutuhan Bahan) memanggil atur_lebar lagi pada tabel yang sama. periksa()
    dari penjaga lebar minimum susunan lama yang masih antre tidak boleh mengubah kolom itu menjadi Interactive
    selebar minimum lamanya (kolom NO menjadi 170 px dan kolom JUMLAH terdorong keluar layar)."""
    from PySide6.QtWidgets import QHeaderView, QTableWidget, QTableWidgetItem

    from gui import tema

    t = QTableWidget(3, 4)
    t.resize(300, 200)
    t.show()
    for c in range(4):
        t.setItem(0, c, QTableWidgetItem("x"))
    tema.atur_lebar(t, 0, isi_konten=(1, 2, 3), minimum=170)  # susunan lama: kolom 0 melebar, minimum 170
    tema.atur_lebar(t, 1, isi_konten=(0, 2, 3), minimum=60)  # susunan baru sebelum periksa() lama berjalan
    for _ in range(5):
        app.processEvents()
    h = t.horizontalHeader()
    assert h.sectionResizeMode(0) == QHeaderView.ResizeToContents
    assert h.sectionSize(0) < 170
    t.close()
    t.deleteLater()


def test_sidebar_bisa_diciutkan_dan_diingat(app, db_sementara):
    """Sidebar diciutkan (ikon saja, nama menu jadi tooltip), dilebarkan lagi, dan pilihannya diingat."""
    from database.preferensi_repository import get_pref
    from gui.main_window import MainWindow

    w = MainWindow()
    try:
        assert not w.sidebar_ciut and w.sidebar.width() == w.LEBAR_SIDEBAR
        assert w.btn_lebar.isHidden() and not w._teks_merek.isHidden()
        w.atur_sidebar(True, animasi=False)
        assert w.sidebar_ciut and w.sidebar.width() == w.LEBAR_SIDEBAR_CIUT == w.lebar_sidebar
        nav = w.grup_nav.buttons()
        assert all(b.text() == "" and b.toolTip() for b in nav) and w._teks_merek.isHidden()
        assert not w.btn_lebar.isHidden() and w._teks_zona.isHidden()
        assert get_pref("sidebar_ciut") == "1"
    finally:
        w.close()
        w.deleteLater()
    w2 = MainWindow()  # dibuka lagi: tetap ciut
    try:
        assert w2.sidebar_ciut and w2.sidebar.width() == w2.LEBAR_SIDEBAR_CIUT
        w2.btn_lebar.click()  # dengan animasi
        from PySide6.QtCore import QCoreApplication, QElapsedTimer

        t = QElapsedTimer()
        t.start()
        while w2._anim_sidebar is not None and t.elapsed() < 3000:
            QCoreApplication.processEvents()
        assert not w2.sidebar_ciut and w2.sidebar.width() == w2.LEBAR_SIDEBAR
        assert all(b.text().strip() for b in w2.grup_nav.buttons())
        assert get_pref("sidebar_ciut") == "0"
    finally:
        w2.close()
        w2.deleteLater()


def test_logo_dari_gambar_dan_teks_merek(app):
    from gui import tema

    assert tema.LOGO_EMBLEM.is_file()
    pm = tema._emblem(40)
    assert not pm.isNull() and max(pm.width(), pm.height()) == 40
    assert "Struct" in tema.teks_merek() and "Cost" in tema.teks_merek()
    assert not tema.ikon_aplikasi().isNull()


def test_dialog_ganti_bahan_menandai_pilihan_yang_diubah(app, db_sementara):
    from database.proyek_repository import create_proyek
    from gui.material_dialog import MaterialDialog

    pid = create_proyek("Uji Bahan", "uji.ifc")
    d = MaterialDialog(pid, None)
    try:
        kode, cb = next(iter(d.combo.items()))
        label = d._label_slot[kode]
        assert not cb.property("berubah") and not label.text().startswith("●")
        cb.setCurrentIndex((cb.currentIndex() + 1) % cb.count())
        assert cb.property("berubah") and label.text().startswith("● ")
        assert d.btn_simpan.isEnabled()
        d._bawaan()
        assert not cb.property("berubah") and not label.text().startswith("●")
    finally:
        d.deleteLater()
