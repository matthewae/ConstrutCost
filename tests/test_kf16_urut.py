"""KF-16 Navigasi data: pengurutan kolom di Hasil Estimasi dan Harga Satuan (angka diurutkan sebagai angka)."""

import os

import pytest

from conftest import AC20


@pytest.fixture(scope="module")
def qapp():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    from gui import tema

    tema.terapkan(app, "gelap")
    return app


def test_sel_urut_angka_bukan_teks(qapp):
    from PySide6.QtWidgets import QTableWidget

    from gui import tema

    t = QTableWidget(3, 1)
    for i, v in enumerate((1_250_000, 950_000, 12_000_000)):
        t.setItem(i, 0, tema.sel(tema.format_rupiah(v), urut=v))
    t.sortItems(0)
    assert [t.item(i, 0).data(tema.KUNCI_URUT) for i in range(3)] == [950_000, 1_250_000, 12_000_000]
    # sebagai teks "Rp 1.250.000" < "Rp 12.000.000" < "Rp 950.000" -> salah; SelUrut memakai angka


def test_urut_detail_dan_rekap(db_sementara, qapp):
    from PySide6.QtCore import Qt

    from database.proyek_repository import create_proyek
    from estimasi_service import jalankan_estimasi
    from gui.estimasi_page import EstimasiPage

    pid = create_proyek("AC20", str(AC20))
    jalankan_estimasi(pid)
    hal = EstimasiPage(pid, "AC20")

    hal.grup_mode.button(hal.MODE_DETAIL).click()
    kolom_subtotal = 4

    def subtotal():
        return [hal._index[hal.tabel.item(i, 0).data(Qt.UserRole)[1]]["subtotal_biaya"] for i in range(hal.tabel.rowCount())]

    asal = subtotal()
    hal._klik_judul(kolom_subtotal)
    assert subtotal() == sorted(asal)
    assert hal.tabel.horizontalHeader().sortIndicatorOrder() == Qt.AscendingOrder
    hal._klik_judul(kolom_subtotal)
    assert subtotal() == sorted(asal, reverse=True)
    hal._klik_judul(kolom_subtotal)  # klik ketiga: urutan asal
    assert subtotal() == asal

    # rekap: item di dalam tiap kategori diurutkan menurut jumlah harga
    hal.grup_mode.button(hal.MODE_REKAP).click()
    hal._klik_judul(5)
    jumlah_per_kategori, sekarang = [], []
    for i in range(hal.tabel.rowCount()):
        it = hal.tabel.item(i, 0)
        data = it.data(Qt.UserRole) if it else None
        if data and data[0] == "rekap":
            teks = hal.tabel.item(i, 5).text()
            sekarang.append(int(teks.replace("Rp", "").replace(".", "").strip()))
        elif sekarang:
            jumlah_per_kategori.append(sekarang)
            sekarang = []
    assert jumlah_per_kategori and all(x == sorted(x) for x in jumlah_per_kategori)


def test_urut_harga_dasar(db_sementara, qapp):
    from database.seed_data import seed_pekerjaan
    from gui import tema
    from gui.harga_page import HargaPage

    seed_pekerjaan()
    from gui.harga_page import TabHargaDasar

    hal = HargaPage()
    tab = hal.findChild(TabHargaDasar)
    t = tab.tabel
    t.sortItems(4)  # sama dengan klik judul kolom HARGA
    harga = [t.item(i, 4).data(tema.KUNCI_URUT) for i in range(t.rowCount())]
    assert harga == sorted(harga) and len(harga) > 10
