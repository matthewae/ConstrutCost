"""
Dialog Katalog HSPK: cari seluruh analisa HSPK Kota Bandung 2027 (bab 1-10, ±2.800 item) lalu tambahkan
item yang tidak bisa dihitung dari model IFC ke RAB proyek, mis. instalasi listrik, plambing, sanitair,
lisplang, atau pagar. Volume, lantai, dan catatan diisi pengguna. Dialog tetap terbuka sehingga beberapa
item bisa ditambahkan sekaligus.
"""

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QAbstractSpinBox,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLineEdit,
    QSplitter,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)

from database.estimasi_repository import BUK_RATE, NilaiTidakValid
from database.hspk_bandung_2027 import AHSP, BAB
from database.katalog import cari_katalog, daftar_katalog, kode_dasar, tambah_item
from gui import tema
from gui.material_dialog import angka_bahan, satuan_tampil

MAKS_BARIS = 600  # baris tabel yang ditampilkan sekaligus; persempit dengan kata kunci / bab
TANPA_LANTAI = "(tanpa lantai)"


class KatalogDialog(QDialog):
    def __init__(self, proyek_id: int, daftar_lantai: list | None = None, parent=None):
        super().__init__(parent)
        self.proyek_id = proyek_id
        self.ditambah = []  # id baris hasil yang ditambahkan
        self._data = daftar_katalog()
        self._terpilih = None
        self.setWindowTitle("Katalog HSPK")
        self.setModal(True)
        self.resize(1180, 760)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(26, 22, 26, 20)
        lay.setSpacing(10)
        lay.addWidget(tema.kepala_dialog(
            "Tambah Item dari Katalog HSPK",
            f"{tema.format_angka(len(self._data), 0)} analisa HSPK Kota Bandung 2027 (bab 1–10). Tambahkan pekerjaan "
            "yang tidak bisa dihitung dari model IFC, mis. instalasi listrik, plambing, sanitair, lisplang, atau pagar.",
            "file",
        )[0])

        cari = QHBoxLayout()
        self.kolom_cari = QLineEdit()
        tema.pasang_ikon_cari(self.kolom_cari)
        self.kolom_cari.setPlaceholderText("Cari kode atau uraian, mis. \"kloset\", \"stop kontak\", \"pipa pvc 3/4\"")
        self.kolom_cari.setClearButtonEnabled(True)
        self._tunda = QTimer(self)
        self._tunda.setSingleShot(True)
        self._tunda.setInterval(200)
        self._tunda.timeout.connect(self._isi)
        self.kolom_cari.textChanged.connect(lambda _: self._tunda.start())
        self.combo_bab = QComboBox()
        self.combo_bab.addItem("Semua bab", None)
        for k, judul in BAB.items():
            self.combo_bab.addItem(f"{k}. {judul}", k)
        self.combo_bab.currentIndexChanged.connect(self._isi)
        cari.addWidget(self.kolom_cari, stretch=1)
        cari.addWidget(self.combo_bab)
        lay.addLayout(cari)

        split = QSplitter(Qt.Horizontal)
        split.setChildrenCollapsible(False)
        self.tabel = QTableWidget()
        tema.siapkan_tabel(self.tabel, ["KODE", "URAIAN PEKERJAAN", "SAT", "HARGA HSPK"], rata_kanan=(3,), tinggi_baris=34)
        self.tabel.itemSelectionChanged.connect(self._pilih)
        self.tabel.cellDoubleClicked.connect(lambda *_: self.spin_volume.setFocus())
        split.addWidget(self.tabel)

        kanan = QFrame()
        kanan.setObjectName("kartu")
        kanan.setMinimumWidth(360)
        k = QVBoxLayout(kanan)
        k.setContentsMargins(18, 14, 18, 14)
        k.setSpacing(8)
        k.addWidget(tema.label("ITEM TERPILIH", "bagian"))
        self.label_item = tema.label("Pilih satu item di tabel.", "subjudul", wrap=True)
        k.addWidget(self.label_item)
        self.label_analisa = tema.label("", "infoKecil", wrap=True)
        self.label_analisa.setTextFormat(Qt.RichText)
        k.addWidget(self.label_analisa)
        k.addStretch()
        form = QGridLayout()
        form.setHorizontalSpacing(10)
        form.setVerticalSpacing(8)
        self.spin_volume = QDoubleSpinBox()
        self.spin_volume.setRange(0.0, 1e9)
        self.spin_volume.setDecimals(3)
        self.spin_volume.setValue(1.0)
        self.spin_volume.setButtonSymbols(QAbstractSpinBox.NoButtons)
        self.spin_volume.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.label_satuan = tema.label("", "formLabel")
        baris_vol = QHBoxLayout()
        baris_vol.addWidget(self.spin_volume, stretch=1)
        baris_vol.addWidget(self.label_satuan)
        self.combo_lantai = QComboBox()
        self.combo_lantai.addItem(TANPA_LANTAI, None)
        for nama in daftar_lantai or []:
            self.combo_lantai.addItem(nama, nama)
        self.edit_catatan = QLineEdit()
        self.edit_catatan.setPlaceholderText("mis. 2 KM, sesuai gambar ME lembar 3")
        self.edit_catatan.setMaxLength(500)
        form.addWidget(tema.label("Volume", "formLabel"), 0, 0)
        form.addLayout(baris_vol, 0, 1)
        form.addWidget(tema.label("Lantai", "formLabel"), 1, 0)
        form.addWidget(self.combo_lantai, 1, 1)
        form.addWidget(tema.label("Catatan", "formLabel"), 2, 0)
        form.addWidget(self.edit_catatan, 2, 1)
        k.addLayout(form)
        self.label_jumlah = tema.label("", "infoKecil", wrap=True)
        k.addWidget(self.label_jumlah)
        self.spin_volume.valueChanged.connect(self._perbarui_jumlah)
        self.btn_tambah = tema.tombol("Tambahkan ke RAB", "primary")
        self.btn_tambah.clicked.connect(self._tambah)
        self.btn_tambah.setEnabled(False)
        k.addWidget(self.btn_tambah)
        split.addWidget(kanan)
        split.setStretchFactor(0, 1)
        split.setSizes([780, 380])
        lay.addWidget(split, stretch=1)

        self.label_status = tema.label("", "infoKecil", wrap=True)
        self.label_galat = tema.label("", "galat", wrap=True)
        self.label_galat.hide()
        lay.addWidget(self.label_status)
        lay.addWidget(self.label_galat)
        tombol = QHBoxLayout()
        tombol.addStretch()
        selesai = tema.tombol("Selesai", "secondary")
        selesai.clicked.connect(self.accept)
        tombol.addWidget(selesai)
        lay.addLayout(tombol)
        self._isi()

    # ---------------------------------------------------------------- tabel

    def _isi(self):
        hasil = cari_katalog(self._data, self.kolom_cari.text(), self.combo_bab.currentData())
        tampil = hasil[:MAKS_BARIS]
        t = self.tabel
        sebelum = self._terpilih
        t.setUpdatesEnabled(False)
        t.clearSelection()
        t.setRowCount(len(tampil))
        for i, d in enumerate(tampil):
            t.setItem(i, 0, tema.sel(kode_dasar(d["kode"]), warna=tema.W["teks_redup"], data=d["kode"]))
            t.setItem(i, 1, tema.sel(d["uraian"], tooltip=f"{d['kategori']} — {d['uraian']}"))
            t.setItem(i, 2, tema.sel(satuan_tampil(d["satuan"]), "tengah", tema.W["teks_redup"]))
            t.setItem(i, 3, tema.sel(tema.format_rupiah(d["harga"]), "kanan"))
        tema.atur_lebar(t, 1, isi_konten=(0, 2, 3), minimum=320)
        t.setUpdatesEnabled(True)
        for i, d in enumerate(tampil):  # item terpilih tetap terpilih bila masih ada di hasil pencarian
            if d["kode"] == sebelum:
                t.selectRow(i)
                break
        lebih = f" (ditampilkan {MAKS_BARIS}; persempit dengan kata kunci atau bab)" if len(hasil) > MAKS_BARIS else ""
        self.label_status.setText(f"{tema.format_angka(len(hasil), 0)} item cocok{lebih}." + self._teks_ditambah())
        self._pilih()

    def _teks_ditambah(self) -> str:
        return f"  ·  {len(self.ditambah)} item sudah ditambahkan ke RAB." if self.ditambah else ""

    def _pilih(self):
        baris = self.tabel.currentRow()
        it = self.tabel.item(baris, 0) if baris >= 0 and self.tabel.selectedItems() else None
        self._terpilih = it.data(Qt.UserRole) if it else None
        self.btn_tambah.setEnabled(self._terpilih is not None)
        self.label_galat.hide()
        if self._terpilih is None:
            self.label_item.setText("Pilih satu item di tabel.")
            self.label_analisa.setText("")
            self.label_satuan.setText("")
            self.label_jumlah.setText("")
            return
        sheet, uraian, f, komponen = AHSP[self._terpilih]
        d = next(x for x in self._data if x["kode"] == self._terpilih)
        self.label_item.setText(f"<b>{kode_dasar(self._terpilih)}</b> · {d['kategori']}<br>{uraian}")
        self.label_satuan.setText(satuan_tampil(d["satuan"]) or "unit")
        baris_k = []
        for judul, tipe in (("Bahan", "bahan"), ("Tenaga kerja", "upah"), ("Alat", "alat")):
            isi = [f"{angka_bahan(kf)} {sat} {nm}" for tp, nm, sat, kf, _h in komponen if tp == tipe]
            if isi:
                baris_k.append(f"<b>{judul}</b> per 1 {satuan_tampil(d['satuan']) or 'unit'}: " + " · ".join(isi))
        self.label_analisa.setText("<br>".join(baris_k))
        self._perbarui_jumlah()

    def _perbarui_jumlah(self):
        if self._terpilih is None:
            return
        harga = sum(kf * h for *_x, kf, h in AHSP[self._terpilih][3]) * (1 + BUK_RATE)
        self.label_jumlah.setText(
            f"Perkiraan jumlah harga: {tema.format_rupiah(harga * self.spin_volume.value())} "
            "(komponen analisa HSPK + biaya umum & keuntungan; harga dasar yang Anda ubah di Harga Satuan ikut berlaku)."
        )

    def _tambah(self):
        if self._terpilih is None:
            return
        try:
            hid = tambah_item(self.proyek_id, self._terpilih, self.spin_volume.value(),
                              self.combo_lantai.currentData(), self.edit_catatan.text())
        except NilaiTidakValid as e:  # KF-14
            self.label_galat.setText(str(e))
            self.label_galat.show()
            return
        self.ditambah.append(hid)
        self.edit_catatan.clear()
        uraian = AHSP[self._terpilih][1]
        self.label_status.setText(f"Ditambahkan: {kode_dasar(self._terpilih)} {uraian[:70]}." + self._teks_ditambah())
        tema.toast(self, "Item ditambahkan ke RAB")
