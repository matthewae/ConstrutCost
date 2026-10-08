"""
Halaman Pengaturan / User Preference (KF-10, UC-07).

- Tema antarmuka: Hitam Kuning (bawaan), Terang Emas, Biru Malam, Terang Biru (langsung diterapkan setelah disimpan).
- Direktori default: folder awal saat memilih file IFC dan folder tujuan export.
- Format laporan default: Excel / PDF, serta isi rekapitulasi / detail per elemen.
- Reset ke Default dengan konfirmasi.
"""

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLineEdit,
    QMessageBox,
    QScrollArea,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from database.estimasi_repository import BUK_RATE, PPN_RATE
from database.preferensi_repository import (
    KOLOM_LAPORAN,
    TEMA,
    Preferensi,
    PreferensiTidakValid,
    folder_default,
    muat_preferensi,
    reset_preferensi,
    simpan_preferensi,
)
from gui import tema


LABEL_KOLOM = {"no": "No", "kode": "Kode analisa", "harga": "Harga satuan", "bobot": "Bobot (%)", "rumus": "Uraian rumus"}


class PengaturanPage(QWidget):
    tersimpan = Signal(bool, str)  # tema_berubah, pesan

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("halaman")
        self.preferensi = Preferensi()
        self._tersimpan = Preferensi()

        luar = QVBoxLayout(self)
        luar.setContentsMargins(0, 0, 0, 0)
        gulir = QScrollArea()
        gulir.setWidgetResizable(True)
        gulir.setFrameShape(QFrame.NoFrame)
        luar.addWidget(gulir)
        isi = QWidget()
        isi.setObjectName("halaman")
        gulir.setWidget(isi)

        root = QVBoxLayout(isi)
        root.setContentsMargins(32, 26, 32, 22)
        root.setSpacing(16)
        kol, _, _ = tema.header_halaman(
            "Pengaturan", "Preferensi tampilan, folder, dan format laporan. Tersimpan di database lokal."
        )
        root.addLayout(kol)

        # --- Tampilan ---
        kartu, f = self._kartu("TAMPILAN")
        baris_tema = QGridLayout()  # kartu tema: 4 sejajar, menyesuaikan lebar layar (lihat resizeEvent)
        baris_tema.setHorizontalSpacing(12)
        baris_tema.setVerticalSpacing(12)
        self._grid_tema = baris_tema
        self.grup_tema = QButtonGroup(self)
        for i, nama in enumerate(TEMA):
            judul, ket = tema.NAMA_TEMA[nama]
            b = QToolButton()
            b.setObjectName("kartuTema")
            b.setText(judul)
            b.setToolTip(ket)
            b.setIcon(QIcon(tema.pratinjau_tema(nama)))
            b.setIconSize(QSize(150, 85))
            b.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
            b.setCheckable(True)
            b.setCursor(Qt.PointingHandCursor)
            self.grup_tema.addButton(b, i)
            baris_tema.addWidget(b, 0, i)
        baris_tema.setColumnStretch(len(TEMA), 1)
        self.grup_tema.idClicked.connect(self._berubah)
        self.grup_tema.idClicked.connect(self._tampilkan_ket_tema)
        f.addRow(tema.label("Tema antarmuka", "formLabel"), baris_tema)
        self.label_ket_tema = tema.label("", "infoKecil", wrap=True)
        f.addRow(QWidget(), self.label_ket_tema)
        root.addWidget(kartu)

        # --- Direktori default ---
        kartu, f = self._kartu("DIREKTORI DEFAULT")
        self.edit_ifc = self._baris_folder(f, "Folder file IFC", "Folder awal saat memilih file IFC untuk proyek baru.")
        self.edit_export = self._baris_folder(f, "Folder hasil export", "Folder tujuan bawaan saat export RAB ke Excel / PDF.")
        root.addWidget(kartu)

        # --- Format laporan default ---
        kartu, f = self._kartu("FORMAT LAPORAN DEFAULT")
        self.cek_excel = QCheckBox("Excel (.xlsx)")
        self.cek_pdf = QCheckBox("PDF (.pdf)")
        self.cek_rekap = QCheckBox("Rekapitulasi biaya")
        self.cek_rinci = QCheckBox("RAB rinci per tipe elemen")
        self.cek_besi = QCheckBox("Kebutuhan besi")
        self.cek_lantai = QCheckBox("Rekap per lantai")
        self.cek_per_lantai = QCheckBox("Rincian per lantai")
        self.cek_detail = QCheckBox("Detail per elemen && lantai")
        self.cek_kolom = {k: QCheckBox(LABEL_KOLOM[k]) for k in KOLOM_LAPORAN}
        semua_cek = (self.cek_excel, self.cek_pdf, self.cek_rekap, self.cek_rinci, self.cek_besi, self.cek_lantai, self.cek_per_lantai,
                     self.cek_detail, *self.cek_kolom.values())
        for cek in semua_cek:
            cek.setCursor(Qt.PointingHandCursor)
            cek.toggled.connect(self._berubah)
        self.combo_orientasi = QComboBox()
        self.combo_orientasi.addItem("PDF tegak (portrait)", "portrait")
        self.combo_orientasi.addItem("PDF mendatar (landscape)", "landscape")
        self.combo_orientasi.currentIndexChanged.connect(self._berubah)

        def baris(*widget):
            b = QHBoxLayout()
            b.setSpacing(24)
            for w in widget:
                b.addWidget(w)
            b.addStretch()
            return b

        f.addRow(tema.label("Format file", "formLabel"), baris(self.cek_excel, self.cek_pdf, self.combo_orientasi))
        isi_grid = QGridLayout()  # 3 kolom agar tidak melebar di layar laptop
        isi_grid.setHorizontalSpacing(24)
        isi_grid.setVerticalSpacing(10)
        for i, cek in enumerate((self.cek_rekap, self.cek_rinci, self.cek_besi, self.cek_lantai, self.cek_per_lantai,
                                 self.cek_detail)):
            isi_grid.addWidget(cek, i // 3, i % 3)
        isi_grid.setColumnStretch(3, 1)
        f.addRow(tema.label("Isi dokumen", "formLabel"), isi_grid)
        f.addRow(tema.label("Kolom laporan", "formLabel"), baris(*self.cek_kolom.values()))
        f.addRow(QWidget(), tema.label(
            "Dipakai sebagai pilihan awal di dialog Export RAB (KF-17). Uraian, volume, satuan, dan jumlah harga "
            "selalu ditampilkan.", "infoKecil", wrap=True,
        ))
        root.addWidget(kartu)

        root.addWidget(
            tema.label(
                f"PPN {PPN_RATE:.0%} dan biaya umum & keuntungan {BUK_RATE:.0%} mengikuti ketentuan (KF-11) "
                "dan tidak dapat diubah dari halaman ini.",
                "infoKecil", wrap=True,
            )
        )
        self.label_galat = tema.label("", "galat", wrap=True)
        self.label_galat.hide()
        root.addWidget(self.label_galat)

        tombol = QHBoxLayout()
        self.btn_reset = tema.tombol("Reset ke Default", "danger", "ulang", "Kembalikan semua pengaturan ke nilai bawaan")
        self.btn_reset.clicked.connect(self._reset)
        self.btn_batal = tema.tombol("Batalkan Perubahan", "secondary")
        self.btn_batal.clicked.connect(self.muat)
        self.btn_simpan = tema.tombol("Simpan Pengaturan", "primary")
        self.btn_simpan.clicked.connect(self._simpan)
        tombol.addWidget(self.btn_reset)
        tombol.addStretch()
        tombol.addWidget(self.btn_batal)
        tombol.addWidget(self.btn_simpan)
        root.addLayout(tombol)
        root.addStretch()

        self.muat()

    # ---------------------------------------------------------------- tata letak

    def _kartu(self, judul: str):
        kartu = QFrame()
        kartu.setObjectName("kartu")
        lay = QVBoxLayout(kartu)
        lay.setContentsMargins(20, 16, 20, 18)
        lay.setSpacing(12)
        lay.addWidget(tema.label(judul, "bagian"))
        f = QFormLayout()
        f.setHorizontalSpacing(24)
        f.setVerticalSpacing(10)
        f.setLabelAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        lay.addLayout(f)
        return kartu, f

    def _baris_folder(self, f: QFormLayout, label: str, info: str) -> QLineEdit:
        edit = QLineEdit()
        edit.setPlaceholderText(f"Bawaan: {folder_default()}")
        edit.setClearButtonEnabled(True)
        edit.textChanged.connect(self._berubah)
        btn = tema.tombol("Pilih Folder...", "secondary")
        btn.clicked.connect(lambda: self._pilih_folder(edit, label))
        baris = QHBoxLayout()
        baris.addWidget(edit, stretch=1)
        baris.addWidget(btn)
        f.addRow(tema.label(label, "formLabel"), baris)
        f.addRow(QWidget(), tema.label(info, "infoKecil"))
        return edit

    def _pilih_folder(self, edit: QLineEdit, judul: str):
        folder = QFileDialog.getExistingDirectory(self, judul, edit.text() or folder_default())
        if folder:
            edit.setText(folder)

    # ---------------------------------------------------------------- data

    def _dari_form(self) -> Preferensi:
        return Preferensi(
            tema=TEMA[max(self.grup_tema.checkedId(), 0)],
            direktori_ifc=self.edit_ifc.text().strip(),
            direktori_export=self.edit_export.text().strip(),
            format_excel=self.cek_excel.isChecked(),
            format_pdf=self.cek_pdf.isChecked(),
            isi_rekap=self.cek_rekap.isChecked(),
            isi_detail=self.cek_detail.isChecked(),
            isi_rinci=self.cek_rinci.isChecked(),
            isi_besi=self.cek_besi.isChecked(),
            isi_lantai=self.cek_lantai.isChecked(),
            isi_per_lantai=self.cek_per_lantai.isChecked(),
            kolom_laporan=",".join(k for k, c in self.cek_kolom.items() if c.isChecked()),
            orientasi_pdf=self.combo_orientasi.currentData(),
        )

    def _ke_form(self, p: Preferensi):
        widget = (self.grup_tema, self.edit_ifc, self.edit_export, self.cek_excel, self.cek_pdf, self.cek_rekap,
                  self.cek_detail, self.cek_rinci, self.cek_besi, self.cek_lantai, self.cek_per_lantai, self.combo_orientasi,
                  *self.cek_kolom.values())
        for w in widget:
            w.blockSignals(True)
        self.grup_tema.button(TEMA.index(p.tema)).setChecked(True)
        self._tampilkan_ket_tema(TEMA.index(p.tema))
        self.edit_ifc.setText(p.direktori_ifc)
        self.edit_export.setText(p.direktori_export)
        self.cek_excel.setChecked(p.format_excel)
        self.cek_pdf.setChecked(p.format_pdf)
        self.cek_rekap.setChecked(p.isi_rekap)
        self.cek_detail.setChecked(p.isi_detail)
        self.cek_rinci.setChecked(p.isi_rinci)
        self.cek_besi.setChecked(p.isi_besi)
        self.cek_lantai.setChecked(p.isi_lantai)
        self.cek_per_lantai.setChecked(p.isi_per_lantai)
        for k, c in self.cek_kolom.items():
            c.setChecked(k in p.kolom)
        self.combo_orientasi.setCurrentIndex(1 if p.orientasi_pdf == "landscape" else 0)
        for w in widget:
            w.blockSignals(False)
        self._berubah()

    def muat(self):
        self._tersimpan = muat_preferensi()
        self.preferensi = self._tersimpan
        self.label_galat.hide()
        self._ke_form(self._tersimpan)

    def _berubah(self, *_):
        ada = self._dari_form() != self._tersimpan
        self.btn_simpan.setEnabled(ada)
        self.btn_batal.setEnabled(ada)
        self.btn_reset.setEnabled(self._dari_form() != Preferensi())

    # ---------------------------------------------------------------- aksi

    def resizeEvent(self, event):
        """Kartu tema 4 sejajar di layar lebar, 2 x 2 di laptop / skala Windows besar."""
        super().resizeEvent(event)
        kolom = 4 if self.width() >= 1180 else 2
        if getattr(self, "_kolom_tema", None) == kolom:
            return
        self._kolom_tema = kolom
        for i, b in enumerate(self.grup_tema.buttons()):
            self._grid_tema.removeWidget(b)
            self._grid_tema.addWidget(b, i // kolom, i % kolom)
        for c in range(5):
            self._grid_tema.setColumnStretch(c, 1 if c == kolom else 0)

    def _tampilkan_ket_tema(self, idx: int):
        judul, ket = tema.NAMA_TEMA[TEMA[idx]]
        aktif = " (sedang dipakai)" if TEMA[idx] == tema.TEMA_AKTIF else " — klik Simpan Pengaturan untuk menerapkan"
        self.label_ket_tema.setText(f"{judul}: {ket}{aktif}.")

    def _simpan(self):
        """UC-07 langkah 4-6."""
        baru = self._dari_form()
        try:
            simpan_preferensi(baru)
        except PreferensiTidakValid as e:  # KF-14
            self.label_galat.setText(str(e))
            self.label_galat.show()
            return
        tema_berubah = baru.tema != self._tersimpan.tema
        self.preferensi = baru
        self._tersimpan = baru
        self.label_galat.hide()
        self._berubah()
        self.tersimpan.emit(tema_berubah, "Pengaturan berhasil disimpan")

    def _reset(self):
        """UC-07 skenario alternatif: Reset ke Default."""
        kotak = QMessageBox(self)
        kotak.setIcon(QMessageBox.Question)
        kotak.setWindowTitle("Reset ke Default")
        kotak.setText("Semua pengaturan akan dikembalikan ke nilai bawaan. Lanjutkan?")
        btn_ya = kotak.addButton("Ya", QMessageBox.AcceptRole)
        btn_tidak = kotak.addButton("Batal", QMessageBox.RejectRole)
        kotak.setDefaultButton(btn_tidak)
        kotak.exec()
        if kotak.clickedButton() is not btn_ya:
            return
        tema_lama = self._tersimpan.tema
        bawaan = reset_preferensi()
        self._tersimpan = bawaan
        self.preferensi = bawaan
        self.label_galat.hide()
        self._ke_form(bawaan)
        self.tersimpan.emit(bawaan.tema != tema_lama, "Pengaturan dikembalikan ke nilai bawaan")
