"""KF-6 Edit hasil estimasi: harga satuan & catatan per baris, undo/redo, pratinjau."""

import os
import sqlite3

import pytest

from conftest import AC20


@pytest.fixture
def proyek(db_sementara):
    from database.proyek_repository import create_proyek
    from estimasi_service import jalankan_estimasi

    pid = create_proyek("AC20", str(AC20))
    jalankan_estimasi(pid)
    conn = sqlite3.connect(db_sementara)
    conn.row_factory = sqlite3.Row
    yield pid, conn
    conn.close()


def _baris(conn, kode):
    return conn.execute(
        "SELECT h.* FROM hasil_estimasi h JOIN pekerjaan p ON p.id = h.pekerjaan_id WHERE p.kode_ahsp = ? ORDER BY h.id",
        (kode,),
    ).fetchall()


@pytest.fixture(scope="module")
def qapp():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def test_harga_khusus_baris_tidak_ditimpa_terapkan_harga(proyek):
    from database.estimasi_repository import NilaiTidakValid, ubah_harga_baris, update_volume_estimasi
    from database.harga_repository import jumlah_estimasi_kedaluwarsa, terapkan_ke_estimasi

    pid, conn = proyek
    b = _baris(conn, "DND.BATA")[0]
    ubah_harga_baris([b["id"]], 400_000)
    r = conn.execute("SELECT * FROM hasil_estimasi WHERE id = ?", (b["id"],)).fetchone()
    assert r["harga_manual"] == 400_000
    assert r["subtotal_biaya"] == pytest.approx(b["volume_pekerjaan"] * 400_000)

    # edit volume memakai harga khusus
    sub = update_volume_estimasi(b["id"], b["pekerjaan_id"], 10.0)
    assert sub == pytest.approx(4_000_000)
    # "Terapkan harga terbaru" tidak menimpa harga khusus
    terapkan_ke_estimasi(pid)
    assert conn.execute("SELECT subtotal_biaya FROM hasil_estimasi WHERE id = ?", (b["id"],)).fetchone()[0] == pytest.approx(4_000_000)
    assert jumlah_estimasi_kedaluwarsa() == 0

    # kembali ke harga master
    ubah_harga_baris([b["id"]], None)
    r = conn.execute("SELECT * FROM hasil_estimasi WHERE id = ?", (b["id"],)).fetchone()
    assert r["harga_manual"] is None
    assert r["subtotal_biaya"] == pytest.approx(10.0 * 370956, rel=1e-4)  # HSPK 3.6.4.2 bata ringan 10 cm (bawaan)

    with pytest.raises(NilaiTidakValid, match="lebih besar dari nol"):
        ubah_harga_baris([b["id"]], 0)
    with pytest.raises(NilaiTidakValid, match="negatif"):
        update_volume_estimasi(b["id"], b["pekerjaan_id"], -1)


def test_catatan(proyek):
    from database.estimasi_repository import NilaiTidakValid, get_hasil_estimasi_by_proyek, ubah_catatan

    pid, conn = proyek
    hid = _baris(conn, "DND.BATA")[0]["id"]
    ubah_catatan(hid, "  sesuai   gambar revisi 2 ")
    r = next(x for x in get_hasil_estimasi_by_proyek(pid) if x["hasil_id"] == hid)
    assert r["catatan"] == "sesuai gambar revisi 2"
    ubah_catatan(hid, "")
    assert conn.execute("SELECT catatan FROM hasil_estimasi WHERE id = ?", (hid,)).fetchone()[0] is None
    with pytest.raises(NilaiTidakValid):
        ubah_catatan(hid, "x" * 501)


def test_potret_dan_pulihkan_proyek(proyek):
    from database.biaya_repository import tambah_biaya
    from database.riwayat_repository import potret_proyek, pulihkan_proyek
    from estimasi_service import hitung_ulang_elemen

    pid, conn = proyek
    awal = potret_proyek(pid)
    el = conn.execute("SELECT id FROM elemen_proyek WHERE nama = 'Slab-033'").fetchone()["id"]
    hitung_ulang_elemen(el, {"panjang": 10.0, "lebar": 8.0, "tebal": 0.15})
    tambah_biaya(pid, "Perencanaan", "persen", 3)
    ubah = potret_proyek(pid)
    assert ubah != awal

    pulihkan_proyek(pid, awal)
    assert potret_proyek(pid) == awal  # termasuk id baris
    pulihkan_proyek(pid, ubah)
    assert potret_proyek(pid) == ubah


def test_undo_redo_di_halaman_estimasi(proyek, qapp):
    from gui import tema
    from gui.estimasi_page import EstimasiPage

    tema.terapkan(qapp, "gelap")
    pid, conn = proyek
    hal = EstimasiPage(pid, "AC20")
    b = _baris(conn, "DND.BATA")[0]
    vol_awal = b["volume_pekerjaan"]

    hal._volume_diubah(b["id"], b["pekerjaan_id"], 99.0)
    hal._harga_diubah([b["id"]], 500_000)
    hal._catatan_diubah(b["id"], "cek lapangan")
    assert hal.riwayat.count() == 3
    assert hal.riwayat.undoText() == "Ubah catatan"

    def baris():
        return conn.execute("SELECT * FROM hasil_estimasi WHERE id = ?", (b["id"],)).fetchone()

    hal.riwayat.undo()  # catatan
    assert baris()["catatan"] is None
    hal.riwayat.undo()  # harga
    assert baris()["harga_manual"] is None
    hal.riwayat.undo()  # volume
    assert baris()["volume_pekerjaan"] == pytest.approx(vol_awal)
    assert baris()["diedit_manual"] == 0
    assert not hal.riwayat.canUndo()

    hal.riwayat.redo()
    hal.riwayat.redo()
    assert baris()["volume_pekerjaan"] == pytest.approx(99.0)
    assert baris()["subtotal_biaya"] == pytest.approx(99.0 * 500_000)
    # nilai di tabel ikut diperbarui
    assert any(x["hasil_id"] == b["id"] and x["harga_manual"] == 500_000 for x in hal._data)


def test_volume_di_tabel_baru_dapat_diubah_setelah_diklik(proyek, qapp):
    """Sel volume tampil sebagai teks: kursor yang lewat tidak memilih / mengubahnya. Setelah diklik baru menjadi
    kotak isian; Enter menyimpan (satu langkah urungkan), Esc membatalkan."""
    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtTest import QTest

    from gui import tema
    from gui.estimasi_page import EstimasiPage, SpinVolume

    tema.terapkan(qapp, "gelap")
    assert "QTableWidget QDoubleSpinBox:hover { border: 1px solid transparent; }" in qapp.styleSheet()
    pid, conn = proyek
    hal = EstimasiPage(pid, "AC20")
    hal.resize(1400, 900)
    hal.show()
    QTest.qWaitForWindowExposed(hal)
    try:
        hal.grup_mode.button(hal.MODE_DETAIL).click()
        b = _baris(conn, "DND.BATA")[0]
        i = hal._baris_dari_id(b["id"])
        spin = hal.tabel.cellWidget(i, 3)
        assert isinstance(spin, SpinVolume)

        # kursor di sel isian tidak memberi sorotan sel (sel teks biasa tetap disorot)
        from PySide6.QtCore import QEvent, QPointF
        from PySide6.QtGui import QHoverEvent
        from PySide6.QtWidgets import QApplication

        vp = hal.tabel.viewport()
        atas = next(j for j in range(hal.tabel.rowCount()) if hal.tabel.cellWidget(j, 3) is not None)  # baris terlihat

        def warna_saat_kursor(kolom):
            rect = hal.tabel.visualRect(hal.tabel.model().index(atas, kolom))
            titik = QPointF(rect.topLeft() + QPoint(2, 2))  # tepi sel, di luar kotak isian
            QApplication.sendEvent(vp, QHoverEvent(QEvent.HoverLeave, QPointF(-1, -1), QPointF(-1, -1), QPointF(-1, -1)))
            diam = vp.grab(rect).toImage().pixelColor(1, 1)
            QApplication.sendEvent(vp, QHoverEvent(QEvent.HoverMove, titik, QPointF(vp.mapToGlobal(titik)), titik))
            return diam, vp.grab(rect).toImage().pixelColor(1, 1)

        diam, lewat = warna_saat_kursor(5)  # subtotal (teks biasa)
        assert diam != lewat
        diam, lewat = warna_saat_kursor(3)  # volume (isian)
        assert diam == lewat

        QTest.mouseMove(spin.lineEdit(), QPoint(10, 5))  # hanya lewat
        assert not spin.hasFocus() and spin.lineEdit().cursor().shape() == Qt.PointingHandCursor
        QTest.keyClicks(hal.tabel, "7")  # mengetik tanpa klik tidak mengubah volume
        assert spin.value() == pytest.approx(b["volume_pekerjaan"])

        spin.setFocus(Qt.MouseFocusReason)  # = diklik (fokus offscreen tidak selalu ikut klik mouse)
        assert spin.hasFocus() and spin.lineEdit().cursor().shape() == Qt.IBeamCursor
        QTest.qWait(10)  # seluruh angka terpilih, ketikan menggantikannya
        QTest.keyClicks(spin, "12")
        QTest.keyClick(spin, Qt.Key_Return)
        assert not spin.hasFocus() and spin.lineEdit().cursor().shape() == Qt.PointingHandCursor
        row = conn.execute("SELECT volume_pekerjaan, diedit_manual FROM hasil_estimasi WHERE id = ?", (b["id"],)).fetchone()
        assert row["volume_pekerjaan"] == pytest.approx(12.0) and row["diedit_manual"] == 1
        assert hal.riwayat.count() == 1

        spin.setFocus(Qt.MouseFocusReason)
        QTest.qWait(10)
        QTest.keyClicks(spin, "55")
        QTest.keyClick(spin, Qt.Key_Escape)  # batal: kembali ke 12, tidak ada perubahan baru
        assert not spin.hasFocus() and spin.value() == pytest.approx(12.0)
        row = conn.execute("SELECT volume_pekerjaan FROM hasil_estimasi WHERE id = ?", (b["id"],)).fetchone()
        assert row["volume_pekerjaan"] == pytest.approx(12.0) and hal.riwayat.count() == 1
    finally:
        hal.close()
        hal.deleteLater()


def test_pratinjau_export(proyek, qapp, tmp_path):
    from PySide6.QtPdf import QPdfDocument

    from gui.export_dialog import ExportDialog
    from gui.pratinjau_dialog import PratinjauDialog

    pid, _ = proyek
    d = ExportDialog(pid, "AC20")
    path = d.buat_pratinjau(tmp_path)
    assert path.exists()
    p = PratinjauDialog(str(path), "AC20")
    assert p.dok.status() == QPdfDocument.Status.Ready
    assert p.dok.pageCount() >= 3
