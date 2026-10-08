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
                                  "persen"])
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
