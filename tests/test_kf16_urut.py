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
    kolom_subtotal = 5

    def subtotal():
        """Subtotal per kelompok (lantai -> jenis elemen); baris judul kelompok memisahkan kelompok."""
        grup, sekarang = [], []
        for i in range(hal.tabel.rowCount()):
            data = hal.tabel.item(i, 0).data(Qt.UserRole)
            if data[0] == "detail":
                sekarang.append(hal._index[data[1]]["subtotal_biaya"])
            elif sekarang:
                grup.append(sekarang)
                sekarang = []
        return grup + ([sekarang] if sekarang else [])

    asal = subtotal()
    assert len(asal) > 1  # dikelompokkan per lantai & jenis
    hal._klik_judul(kolom_subtotal)
    assert subtotal() == [sorted(g) for g in asal]
    assert hal.tabel.horizontalHeader().sortIndicatorOrder() == Qt.AscendingOrder
    hal._klik_judul(kolom_subtotal)
    assert subtotal() == [sorted(g, reverse=True) for g in asal]
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


def test_saring_elemen_checkbox_jenis_dan_radio_nama(db_sementara, qapp):
    """Kotak cari diganti penyaring tanpa mengetik: checkbox jenis elemen (Kolom, Dinding, ...), lalu radio button
    nama elemen yang hanya berisi jenis tercentang. Berlaku juga di tab RAB; Hapus Saringan mengembalikan semua."""
    from PySide6.QtCore import Qt

    from database.proyek_repository import create_proyek
    from estimasi_service import jalankan_estimasi
    from gui.estimasi_page import EstimasiPage
    from gui.saring_elemen import _teks_tombol, label_jenis, urut_alami
    from kebutuhan_lantai import JENIS_TAMBAHAN, jenis_elemen, urutan_jenis

    pid = create_proyek("AC20", str(AC20))
    jalankan_estimasi(pid)
    hal = EstimasiPage(pid, "AC20")
    hal.resize(1400, 900)
    hal.show()
    try:
        s = hal.saring
        assert not hasattr(hal, "kolom_cari")  # tidak ada kotak teks pencarian lagi
        jenis = list(s._cek)
        assert "Dinding" in jenis and jenis == sorted(jenis, key=urutan_jenis)
        n_dinding = len({r["elemen_id"] for r in hal._data if jenis_elemen(r) == "Dinding"})
        assert s._cek["Dinding"].text() == f"Dinding ({n_dinding})"
        assert s.baris_nama.isHidden() and s.btn_hapus.isHidden()

        hal.grup_mode.button(hal.MODE_DETAIL).click()

        def baris_tabel():
            hasil = []
            for i in range(hal.tabel.rowCount()):
                data = hal.tabel.item(i, 0).data(Qt.UserRole)
                if data and data[0] == "detail":
                    hasil.append(hal._index[data[1]])
            return hasil

        n_semua = len(baris_tabel())
        s._cek["Dinding"].setChecked(True)  # seperti diklik pengguna
        assert not s.baris_nama.isHidden() and not s.btn_hapus.isHidden()
        assert {jenis_elemen(r) for r in baris_tabel()} == {"Dinding"}
        assert set(s._radio) == {r["elemen_id"] for r in hal._data if jenis_elemen(r) == "Dinding"}
        semua = s.grup_nama.checkedButton()
        assert semua.text() == f"Semua ({n_dinding} elemen)"
        teks = [s._radio[e].text() for e in s._radio]
        lantai_pertama = [t for t, e in zip(teks, s._radio)
                          if hal._data and next(r for r in hal._data if r["elemen_id"] == e)["lantai"]
                          == next(r for r in hal._data if r["elemen_id"] == next(iter(s._radio)))["lantai"]]
        assert lantai_pertama == sorted(lantai_pertama, key=urut_alami)  # urut alami dalam satu lantai

        eid, rb = next(iter(s._radio.items()))
        rb.click()  # radio nama elemen
        assert s.elemen_terpilih() == eid and {r["elemen_id"] for r in baris_tabel()} == {eid}
        assert f"disaring: {s._nama[eid]}" in hal.label_jumlah.text()

        lain = next(j for j in jenis if j not in ("Dinding", JENIS_TAMBAHAN))
        s._cek[lain].setChecked(True)  # jenis kedua: daftar nama bertambah, elemen terpilih tetap
        assert s.elemen_terpilih() == eid
        assert {jenis_elemen(next(r for r in hal._data if r["elemen_id"] == e)) for e in s._radio} == {"Dinding", lain}
        s._cek["Dinding"].setChecked(False)  # jenis elemen terpilih dilepas: kembali ke semua elemen jenis lain
        assert s.elemen_terpilih() is None and {jenis_elemen(r) for r in baris_tabel()} == {lain}

        hal.grup_mode.button(hal.MODE_REKAP).click()  # tab RAB ikut tersaring
        assert "disaring: " + lain in hal.label_jumlah.text()

        s.btn_hapus.click()
        assert not s.aktif() and s.baris_nama.isHidden()
        hal.grup_mode.button(hal.MODE_DETAIL).click()
        assert len(baris_tabel()) == n_semua

        nama = next(r for r in hal._data if jenis_elemen(r) == "Dinding")
        hal.lihat_elemen(nama["nama_elemen"], nama["elemen_id"])  # dari Model 3D: Lihat di Tabel RAB
        assert s.jenis_terpilih() == {"Dinding"} and s.elemen_terpilih() == nama["elemen_id"]
        assert s._radio[nama["elemen_id"]].isChecked()
        assert _teks_tombol("Urugan & lantai kerja (40)") == "Urugan && lantai kerja (40)"  # "&" tidak hilang
        assert label_jenis("Elemen lain (fasad, atap, lansekap, sanitair)") == "Elemen lain"
        assert {r["elemen_id"] for r in baris_tabel()} == {nama["elemen_id"]}
    finally:
        hal.close()
        hal.deleteLater()
