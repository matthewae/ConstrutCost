"""
Dialog Biaya Tidak Langsung (KF-13): item biaya di luar pekerjaan fisik (perencanaan, pengawasan,
perizinan, SMKK, operasional) yang diisi pengguna sebagai persentase biaya langsung atau nilai
rupiah, beserta ringkasan biaya proyek: A biaya langsung, B biaya tidak langsung, PPN, total.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QAbstractSpinBox,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QTableWidget,
    QVBoxLayout,
)

from database.biaya_repository import (
    USULAN,
    BiayaTidakValid,
    daftar_biaya,
    hapus_biaya,
    ringkasan_biaya,
    tambah_biaya,
    ubah_biaya,
)
from database.estimasi_repository import BUK_RATE, PPN_RATE
from gui import tema

LABEL_JENIS = {"persen": "% dari biaya langsung", "nilai": "Nilai tetap (Rp)"}


class BiayaDialog(QDialog):
    def __init__(self, proyek_id: int, parent=None):
        super().__init__(parent)
        self.proyek_id = proyek_id
        self.diubah = False
        self._data = []
        self.setWindowTitle("Biaya Tidak Langsung")
        self.setModal(True)
        self.resize(980, 640)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(26, 22, 26, 20)
        lay.setSpacing(12)
        lay.addWidget(tema.label("Biaya Tidak Langsung", "judulHalaman"))
        lay.addWidget(tema.label(
            "Biaya di luar pekerjaan fisik, mis. perencanaan, pengawasan, perizinan, dan penerapan SMKK. "
            "Nilainya mengikuti kontrak atau ketentuan proyek, sehingga diisi sendiri (tidak dihitung otomatis).",
            "subjudul", wrap=True,
        ))

        isi = QHBoxLayout()
        isi.setSpacing(14)
        kiri = QVBoxLayout()
        kiri.setSpacing(10)
        self.tabel = QTableWidget()
        self.tabel.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tabel.setSelectionMode(QAbstractItemView.SingleSelection)
        self.tabel.itemSelectionChanged.connect(self._pilih)
        kiri.addWidget(self.tabel, stretch=1)
        kiri.addWidget(self._kartu_ringkasan())
        isi.addLayout(kiri, stretch=1)
        isi.addWidget(self._editor())
        lay.addLayout(isi, stretch=1)

        tombol = QHBoxLayout()
        self.label_pesan = tema.label("", "sukses")
        tombol.addWidget(self.label_pesan)
        tombol.addStretch()
        tutup = tema.tombol("Tutup", "secondary")
        tutup.clicked.connect(self.accept)
        tombol.addWidget(tutup)
        lay.addLayout(tombol)
        self.muat()

    # ---------------------------------------------------------------- tata letak

    def _kartu_ringkasan(self) -> QFrame:
        kartu = QFrame()
        kartu.setObjectName("kartu")
        self.form_ringkas = QFormLayout(kartu)
        self.form_ringkas.setContentsMargins(18, 12, 18, 12)
        self.form_ringkas.setVerticalSpacing(4)
        self.nilai = {}
        for kunci, teks in (
            ("langsung", "A. Biaya langsung"),
            ("tidak_langsung", "B. Biaya tidak langsung"),
            ("jumlah", "Jumlah (A + B)"),
            ("ppn", f"PPN {PPN_RATE:.0%}"),
            ("dibulatkan", "Total RAB (dibulatkan)"),
        ):
            n = tema.label("-", "judulPanel" if kunci == "dibulatkan" else None)
            n.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.nilai[kunci] = n
            self.form_ringkas.addRow(tema.label(teks, "formLabel"), n)
        self.label_terbilang = tema.label("", "infoKecil", wrap=True)
        self.form_ringkas.addRow(self.label_terbilang)
        return kartu

    def _editor(self) -> QFrame:
        kartu = QFrame()
        kartu.setObjectName("kartu")
        kartu.setFixedWidth(350)
        v = QVBoxLayout(kartu)
        v.setContentsMargins(18, 16, 18, 16)
        v.setSpacing(10)
        self.label_mode = tema.label("Tambah biaya", "judulPanel")
        v.addWidget(self.label_mode)
        f = QFormLayout()
        f.setVerticalSpacing(10)
        self.combo_uraian = QComboBox()
        self.combo_uraian.setEditable(True)
        for c in (self.combo_uraian,):
            c.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
            c.setMinimumContentsLength(12)
        self.combo_uraian.addItems(USULAN)
        self.combo_uraian.setCurrentText("")
        self.combo_uraian.lineEdit().setPlaceholderText("Pilih atau ketik uraian")
        self.combo_jenis = QComboBox()
        self.combo_jenis.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self.combo_jenis.setMinimumContentsLength(12)
        for k, t in LABEL_JENIS.items():
            self.combo_jenis.addItem(t, k)
        self.combo_jenis.currentIndexChanged.connect(self._jenis_berubah)
        self.spin_nilai = QDoubleSpinBox()
        self.spin_nilai.setButtonSymbols(QAbstractSpinBox.NoButtons)
        self.spin_nilai.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.spin_nilai.setGroupSeparatorShown(True)
        f.addRow(tema.label("Uraian", "formLabel"), self.combo_uraian)
        f.addRow(tema.label("Jenis", "formLabel"), self.combo_jenis)
        f.addRow(tema.label("Nilai", "formLabel"), self.spin_nilai)
        v.addLayout(f)
        self.label_galat = tema.label("", "galat", wrap=True)
        self.label_galat.hide()
        v.addWidget(self.label_galat)
        v.addWidget(tema.label(
            f"Persentase dihitung dari biaya langsung (sudah termasuk biaya umum & keuntungan {BUK_RATE:.0%} "
            f"di harga satuan). PPN {PPN_RATE:.0%} dikenakan pada biaya langsung + tidak langsung.",
            "infoKecil", wrap=True,
        ))
        v.addStretch()
        self.btn_simpan = tema.tombol("Tambahkan", "primary")
        self.btn_simpan.clicked.connect(self._simpan)
        self.btn_baru = tema.tombol("Item Baru", "ghost", "tambah")
        self.btn_baru.clicked.connect(self._kosongkan)
        self.btn_hapus = tema.tombol("Hapus Item", "danger")
        self.btn_hapus.clicked.connect(self._hapus)
        v.addWidget(self.btn_simpan)
        baris = QHBoxLayout()
        baris.addWidget(self.btn_baru)
        baris.addWidget(self.btn_hapus)
        v.addLayout(baris)
        self._jenis_berubah()
        return kartu

    # ---------------------------------------------------------------- data

    def muat(self, pilih_id=None):
        self._data = daftar_biaya(self.proyek_id)
        r = ringkasan_biaya(self.proyek_id)
        jumlah = {b["id"]: b["jumlah"] for b in r["item_tidak_langsung"]}
        t = self.tabel
        t.blockSignals(True)
        t.clear()
        tema.siapkan_tabel(t, ["NO", "URAIAN", "DASAR", "JUMLAH (Rp)"], rata_kanan=(2, 3), tinggi_baris=40)
        t.setRowCount(len(self._data))
        for i, b in enumerate(self._data):
            t.setItem(i, 0, tema.sel(str(i + 1), warna=tema.W["teks_samar"], data=b["id"]))
            t.setItem(i, 1, tema.sel(b["uraian"], tebal=True))
            dasar = (
                f"{tema.format_angka(b['nilai'], 2)}% × A" if b["jenis"] == "persen" else "nilai tetap"
            )
            t.setItem(i, 2, tema.sel(dasar, "kanan", tema.W["teks_redup"]))
            t.setItem(i, 3, tema.sel(tema.format_rupiah(jumlah[b["id"]]), "kanan"))
        tema.atur_lebar(t, 1, isi_konten=(0, 2, 3))
        t.blockSignals(False)
        for k, n in self.nilai.items():
            n.setText(tema.format_rupiah(r[k]))
        self.label_terbilang.setText(f"Terbilang: {r['terbilang']}")
        baris = next((i for i, b in enumerate(self._data) if b["id"] == pilih_id), -1)
        if baris >= 0:
            t.selectRow(baris)
        else:
            self._kosongkan()

    def _jenis_berubah(self, *_):
        if self.combo_jenis.currentData() == "persen":
            self.spin_nilai.setRange(0, 100)
            self.spin_nilai.setDecimals(2)
            self.spin_nilai.setPrefix("")
            self.spin_nilai.setSuffix(" %")
        else:
            self.spin_nilai.setRange(0, 1e13)
            self.spin_nilai.setDecimals(0)
            self.spin_nilai.setPrefix("Rp ")
            self.spin_nilai.setSuffix("")

    def _terpilih(self):
        baris = self.tabel.currentRow()
        it = self.tabel.item(baris, 0) if baris >= 0 and self.tabel.selectedItems() else None
        if it is None:
            return None
        return next((b for b in self._data if b["id"] == it.data(Qt.UserRole)), None)

    def _pilih(self):
        b = self._terpilih()
        self.label_galat.hide()
        if b is None:
            return
        self.label_mode.setText("Ubah biaya")
        self.combo_uraian.setCurrentText(b["uraian"])
        self.combo_jenis.setCurrentIndex(0 if b["jenis"] == "persen" else 1)
        self.spin_nilai.setValue(b["nilai"])
        self.btn_simpan.setText("Simpan Perubahan")
        self.btn_hapus.setEnabled(True)

    def _kosongkan(self):
        self.tabel.clearSelection()
        self.label_mode.setText("Tambah biaya")
        self.combo_uraian.setCurrentText("")
        self.spin_nilai.setValue(0)
        self.btn_simpan.setText("Tambahkan")
        self.btn_hapus.setEnabled(False)
        self.label_galat.hide()

    # ---------------------------------------------------------------- aksi

    def _simpan(self):
        b = self._terpilih()
        args = (self.combo_uraian.currentText(), self.combo_jenis.currentData(), self.spin_nilai.value())
        try:
            if b is None:
                bid = tambah_biaya(self.proyek_id, *args)
                pesan = "Biaya tidak langsung ditambahkan"
            else:
                ubah_biaya(b["id"], *args)
                bid = b["id"]
                pesan = "Perubahan berhasil disimpan"
        except BiayaTidakValid as e:  # KF-14
            self.label_galat.setText(str(e))
            self.label_galat.show()
            return
        self.diubah = True
        self.muat(bid)
        self.label_pesan.setText("✓  " + pesan)

    def _hapus(self):
        b = self._terpilih()
        if b is None:
            return
        if not tema.tanya(self, "Hapus Item", f"Hapus '{b['uraian']}' dari biaya tidak langsung?", ya="Hapus"):
            return
        hapus_biaya(b["id"])
        self.diubah = True
        self.muat()
        self.label_pesan.setText("✓  Item dihapus")
