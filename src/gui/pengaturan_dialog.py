"""
Dialog Pengaturan CostStruct — Material & Harga.

Pengguna dapat menyimpan material yang biasa dipakai beserta merk dan harganya,
misalnya Semen — Tiga Roda — Rp 68.000 per sak.

Cara pakai (ringkas):
- Isi formulir di atas lalu klik "Simpan Material".
- Klik satu baris pada daftar untuk mengubah atau menghapusnya.
- Bila satu jenis material punya beberapa merk, tandai satu sebagai "merk utama".
"""

import tempfile
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QAbstractSpinBox,
    QCheckBox,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from database.material_repository import (
    buat_id,
    muat_daftar_material,
    simpan_daftar_material,
)

# Jenis material umum beserta satuan yang biasa dipakai (hanya saran, bisa diganti).
JENIS_MATERIAL = {
    "Semen": "sak",
    "Besi Beton": "batang",
    "Beton Ready Mix": "m³",
    "Pasir": "m³",
    "Batu Pecah": "m³",
    "Kayu Bekisting": "lembar",
    "Bata / Batako": "buah",
    "Cat": "kg",
}
SATUAN_UMUM = ["sak", "kg", "ton", "m³", "m²", "m", "batang", "lembar", "buah", "liter"]

WARNA_REDUP = "#8fa3b8"
WARNA_UTAMA = "#f5b84f"

KOL_JENIS, KOL_MERK, KOL_SATUAN, KOL_HARGA, KOL_UTAMA = range(5)

STYLE_SHEET = """
QWidget {
    color: #e4ebf2;
    font-family: "Segoe UI", "Inter", sans-serif;
    font-size: 13px;
}
QDialog { background-color: #152030; }
QLabel { background: transparent; }

QLabel#judulApp { font-size: 22px; font-weight: 700; color: #ffffff; }
QLabel#subjudulApp { color: #7d92a8; font-size: 12px; }
QLabel#bagian { color: #7d92a8; font-size: 11px; font-weight: 700; letter-spacing: 1px; }
QLabel#labelField { color: #9fb3c8; font-size: 12px; }
QLabel#infoKecil { color: #6f869c; font-size: 11px; }
QLabel#status { color: #6fcf97; font-size: 12px; font-weight: 600; }

QFrame#kartu {
    background-color: #1b2937;
    border: 1px solid #27394b;
    border-radius: 12px;
}

/* ---- Input ---- */
QLineEdit, QComboBox, QDoubleSpinBox {
    background-color: #223244;
    border: 1px solid #2f4458;
    border-radius: 8px;
    padding: 8px 12px;
    color: #e4ebf2;
    selection-background-color: #2a4a6e;
}
QLineEdit:hover, QComboBox:hover, QDoubleSpinBox:hover { border: 1px solid #4a6a8c; }
QLineEdit:focus, QComboBox:focus, QDoubleSpinBox:focus {
    border: 1px solid #4f9df7;
    background-color: #1e3a5a;
}
QComboBox QLineEdit { border: none; background: transparent; padding: 0; }
QComboBox::drop-down { border: none; width: 28px; }
QComboBox::down-arrow { image: __PANAH__; width: 12px; height: 12px; }
QComboBox QAbstractItemView {
    background-color: #1b2937;
    border: 1px solid #2b3f53;
    selection-background-color: #25456a;
    color: #e4ebf2;
    outline: none;
}

/* ---- Kotak centang ---- */
QCheckBox { spacing: 10px; }
QCheckBox::indicator {
    width: 18px;
    height: 18px;
    border-radius: 5px;
    border: 1px solid #3a5068;
    background-color: #1b2937;
}
QCheckBox::indicator:hover { border: 1px solid #4f9df7; }
QCheckBox::indicator:checked {
    background-color: #4f9df7;
    border: 1px solid #4f9df7;
    image: __CENTANG__;
}

/* ---- Tabel ---- */
QTableWidget {
    background-color: #1a2633;
    border: 1px solid #27394b;
    border-radius: 12px;
    gridline-color: transparent;
    outline: none;
    selection-background-color: #25456a;
    selection-color: #ffffff;
    alternate-background-color: #1d2b39;
}
QTableWidget::item { padding: 8px 14px; border: none; }
QTableWidget::item:hover { background-color: #233447; }
QTableWidget::item:selected { background-color: #25456a; }
QHeaderView { background-color: transparent; }
QHeaderView::section {
    background-color: #1a2633;
    color: #7d92a8;
    padding: 12px 14px;
    border: none;
    border-bottom: 1px solid #27394b;
    font-weight: 700;
    font-size: 11px;
    letter-spacing: 1px;
}
QScrollBar:vertical { background: transparent; width: 10px; margin: 4px 2px; }
QScrollBar::handle:vertical { background: #34495e; border-radius: 4px; min-height: 36px; }
QScrollBar::handle:vertical:hover { background: #4a6580; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }

/* ---- Kondisi kosong ---- */
QFrame#kartuKosong {
    background-color: #1a2633;
    border: 1px dashed #2f4458;
    border-radius: 14px;
}
QLabel#kosongJudul { font-size: 16px; font-weight: 700; color: #ffffff; }
QLabel#kosongDeskripsi { color: #7d92a8; font-size: 12px; }

/* ---- Tombol ---- */
QPushButton { border-radius: 8px; padding: 10px 22px; font-weight: 600; }
QPushButton#btnPrimary { background-color: #4f9df7; color: #0c1a26; }
QPushButton#btnPrimary:hover { background-color: #6bacf9; }
QPushButton#btnPrimary:pressed { background-color: #3f8ce6; }
QPushButton#btnSecondary {
    background-color: #223244;
    color: #e4ebf2;
    border: 1px solid #2f4458;
}
QPushButton#btnSecondary:hover { background-color: #2b3f54; }
QPushButton#btnDanger {
    background-color: transparent;
    color: #f48b8b;
    border: 1px solid #54343d;
}
QPushButton#btnDanger:hover { background-color: #3a2229; }

/* ---- Dialog pesan & tooltip ---- */
QMessageBox { background-color: #182430; }
QMessageBox QLabel { color: #e4ebf2; }
QMessageBox QPushButton {
    background-color: #223244;
    border: 1px solid #2f4458;
    min-width: 84px;
    padding: 8px 16px;
}
QMessageBox QPushButton:hover { background-color: #2b3f54; }
QToolTip {
    background-color: #223244;
    color: #e4ebf2;
    border: 1px solid #2f4458;
    padding: 5px 8px;
}
"""


def format_rupiah(nilai: float) -> str:
    return "Rp " + f"{nilai:,.0f}".replace(",", ".")


def _siapkan_ikon_centang() -> str:
    """Membuat gambar tanda centang untuk indikator QCheckBox di folder sementara.
    Return path berformat url Qt, atau 'none' bila gagal dibuat."""
    try:
        path = Path(tempfile.gettempdir()) / "coststruct_centang.png"
        pix = QPixmap(18, 18)
        pix.fill(Qt.transparent)
        p = QPainter(pix)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(QPen(QColor("#0c1a26"), 2.4, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.drawLine(5, 9, 8, 12)
        p.drawLine(8, 12, 13, 6)
        p.end()
        if not pix.save(str(path), "PNG"):
            return "none"
        return f"url({path.as_posix()})"
    except Exception:
        return "none"


def _siapkan_ikon_panah() -> str:
    """Membuat gambar panah kecil untuk dropdown (QComboBox) di folder sementara.
    Return path berformat url Qt, atau 'none' bila gagal dibuat."""
    try:
        path = Path(tempfile.gettempdir()) / "coststruct_panah.png"
        pix = QPixmap(12, 12)
        pix.fill(Qt.transparent)
        p = QPainter(pix)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(QPen(QColor("#9fb3c8"), 1.8, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.drawLine(2, 4, 6, 8)
        p.drawLine(6, 8, 10, 4)
        p.end()
        if not pix.save(str(path), "PNG"):
            return "none"
        return f"url({path.as_posix()})"
    except Exception:
        return "none"


class PengaturanDialog(QDialog):
    """Pengaturan aplikasi. Saat ini berisi: Material & Harga."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Pengaturan — CostStruct")
        self.setModal(True)
        self.resize(900, 700)
        self.setMinimumSize(760, 600)
        self.setStyleSheet(
            STYLE_SHEET.replace("__CENTANG__", _siapkan_ikon_centang()).replace(
                "__PANAH__", _siapkan_ikon_panah()
            )
        )

        self._daftar = []  # semua material tersimpan
        self._id_diedit = None  # id material yang sedang diubah (None = mode tambah)
        self._sedang_mengisi = False

        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 22)
        root.setSpacing(14)

        # --- Header ---
        judul = QLabel("Pengaturan")
        judul.setObjectName("judulApp")
        subjudul = QLabel(
            "Simpan material yang biasa Anda pakai beserta merk dan harganya."
        )
        subjudul.setObjectName("subjudulApp")
        root.addWidget(judul)
        root.addWidget(subjudul)
        root.addSpacing(4)

        # --- Formulir ---
        self.label_mode = self._bagian("TAMBAH MATERIAL BARU")
        root.addWidget(self.label_mode)
        root.addWidget(self._buat_formulir())

        # --- Daftar tersimpan ---
        baris_daftar = QHBoxLayout()
        baris_daftar.addWidget(self._bagian("MATERIAL TERSIMPAN"))
        baris_daftar.addStretch()
        self.label_jumlah = QLabel("")
        self.label_jumlah.setObjectName("infoKecil")
        baris_daftar.addWidget(self.label_jumlah)
        root.addLayout(baris_daftar)

        self.stack = QStackedWidget()
        self.stack.addWidget(self._buat_tabel())
        self.stack.addWidget(self._buat_kosong())
        root.addWidget(self.stack, stretch=1)

        # --- Baris bawah ---
        baris_bawah = QHBoxLayout()
        self.label_status = QLabel("")
        self.label_status.setObjectName("status")
        baris_bawah.addWidget(self.label_status)
        baris_bawah.addStretch()
        info = QLabel("Data disimpan di komputer ini dan bisa diubah kapan saja.")
        info.setObjectName("infoKecil")
        baris_bawah.addWidget(info)
        baris_bawah.addSpacing(14)
        btn_tutup = QPushButton("Tutup")
        btn_tutup.setObjectName("btnSecondary")
        btn_tutup.setCursor(Qt.PointingHandCursor)
        btn_tutup.clicked.connect(self.accept)
        baris_bawah.addWidget(btn_tutup)
        root.addLayout(baris_bawah)

        self._timer_status = QTimer(self)
        self._timer_status.setSingleShot(True)
        self._timer_status.timeout.connect(lambda: self.label_status.setText(""))

        self._muat()

    # ---------- Konstruksi UI ----------

    @staticmethod
    def _bagian(teks: str) -> QLabel:
        label = QLabel(teks)
        label.setObjectName("bagian")
        return label

    @staticmethod
    def _field(teks: str, widget: QWidget) -> QVBoxLayout:
        kolom = QVBoxLayout()
        kolom.setSpacing(5)
        label = QLabel(teks)
        label.setObjectName("labelField")
        kolom.addWidget(label)
        kolom.addWidget(widget)
        return kolom

    def _buat_formulir(self) -> QFrame:
        kartu = QFrame()
        kartu.setObjectName("kartu")
        layout = QVBoxLayout(kartu)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(14)

        grid = QGridLayout()
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(12)

        self.combo_jenis = QComboBox()
        self.combo_jenis.setEditable(True)
        self.combo_jenis.setInsertPolicy(QComboBox.NoInsert)
        self.combo_jenis.addItems(list(JENIS_MATERIAL.keys()))
        self.combo_jenis.lineEdit().setPlaceholderText(
            "Pilih atau ketik jenis material"
        )
        self.combo_jenis.activated.connect(
            lambda i: self._saran_satuan(self.combo_jenis.itemText(i))
        )

        self.edit_merk = QLineEdit()
        self.edit_merk.setPlaceholderText("mis. Tiga Roda, Gresik, Holcim")
        self.edit_merk.returnPressed.connect(self._simpan)

        self.combo_satuan = QComboBox()
        self.combo_satuan.setEditable(True)
        self.combo_satuan.setInsertPolicy(QComboBox.NoInsert)
        self.combo_satuan.addItems(SATUAN_UMUM)
        self.combo_satuan.lineEdit().setPlaceholderText("mis. sak, kg, m³")

        self.spin_harga = QDoubleSpinBox()
        self.spin_harga.setRange(0, 1_000_000_000_000)
        self.spin_harga.setDecimals(0)
        self.spin_harga.setSingleStep(1000)
        self.spin_harga.setPrefix("Rp ")
        self.spin_harga.setGroupSeparatorShown(True)
        self.spin_harga.setButtonSymbols(QAbstractSpinBox.NoButtons)
        self.spin_harga.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.spin_harga.setKeyboardTracking(False)
        self.spin_harga.setToolTip("Harga per satuan, dalam Rupiah")

        grid.addLayout(self._field("Jenis material", self.combo_jenis), 0, 0)
        grid.addLayout(self._field("Merk", self.edit_merk), 0, 1)
        grid.addLayout(self._field("Satuan", self.combo_satuan), 1, 0)
        grid.addLayout(self._field("Harga per satuan", self.spin_harga), 1, 1)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        layout.addLayout(grid)

        self.cek_utama = QCheckBox("Jadikan merk utama untuk jenis material ini")
        self.cek_utama.setCursor(Qt.PointingHandCursor)
        self.cek_utama.setToolTip(
            "Bila satu jenis material punya beberapa merk, merk utama dipakai sebagai acuan."
        )
        layout.addWidget(self.cek_utama)

        baris_tombol = QHBoxLayout()
        baris_tombol.setSpacing(10)
        self.btn_hapus = QPushButton("Hapus")
        self.btn_hapus.setObjectName("btnDanger")
        self.btn_hapus.setCursor(Qt.PointingHandCursor)
        self.btn_hapus.clicked.connect(self._hapus)
        self.btn_batal = QPushButton("Batal Ubah")
        self.btn_batal.setObjectName("btnSecondary")
        self.btn_batal.setCursor(Qt.PointingHandCursor)
        self.btn_batal.clicked.connect(self._batal_ubah)
        self.btn_simpan = QPushButton("Simpan Material")
        self.btn_simpan.setObjectName("btnPrimary")
        self.btn_simpan.setCursor(Qt.PointingHandCursor)
        self.btn_simpan.clicked.connect(self._simpan)
        baris_tombol.addWidget(self.btn_hapus)
        baris_tombol.addStretch()
        baris_tombol.addWidget(self.btn_batal)
        baris_tombol.addWidget(self.btn_simpan)
        layout.addLayout(baris_tombol)

        self._atur_mode(ubah=False)
        return kartu

    def _buat_tabel(self) -> QWidget:
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(
            ["JENIS MATERIAL", "MERK", "SATUAN", "HARGA SATUAN", "MERK UTAMA"]
        )
        self.table.horizontalHeaderItem(KOL_HARGA).setTextAlignment(
            Qt.AlignRight | Qt.AlignVCenter
        )
        self.table.horizontalHeaderItem(KOL_SATUAN).setTextAlignment(Qt.AlignCenter)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        self.table.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(46)

        header = self.table.horizontalHeader()
        header.setHighlightSections(False)
        header.setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        header.setSectionResizeMode(KOL_JENIS, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(KOL_MERK, QHeaderView.Stretch)
        header.setSectionResizeMode(KOL_SATUAN, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(KOL_HARGA, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(KOL_UTAMA, QHeaderView.ResizeToContents)

        self.table.itemSelectionChanged.connect(self._pilihan_berubah)
        return self.table

    def _buat_kosong(self) -> QWidget:
        wrap = QFrame()
        wrap.setObjectName("kartuKosong")
        layout = QVBoxLayout(wrap)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(6)
        judul = QLabel("Belum ada material tersimpan")
        judul.setObjectName("kosongJudul")
        judul.setAlignment(Qt.AlignCenter)
        deskripsi = QLabel(
            "Isi formulir di atas, misalnya Semen — Tiga Roda — Rp 68.000 per sak."
        )
        deskripsi.setObjectName("kosongDeskripsi")
        deskripsi.setAlignment(Qt.AlignCenter)
        layout.addWidget(judul)
        layout.addWidget(deskripsi)
        return wrap

    # ---------- Data ----------

    def _muat(self):
        self._daftar = muat_daftar_material()
        self._normalisasi_utama()
        self._isi_tabel()

    def _simpan_ke_penyimpanan(self) -> bool:
        try:
            simpan_daftar_material(self._daftar)
            return True
        except Exception as e:
            QMessageBox.critical(
                self,
                "Gagal Menyimpan",
                f"Data material tidak bisa disimpan.\n\nDetail: {e}",
            )
            return False

    def _normalisasi_utama(self):
        """Pastikan tiap jenis material punya tepat satu merk utama."""
        per_jenis = {}
        for m in self._daftar:
            per_jenis.setdefault(m["material"].lower(), []).append(m)
        for kelompok in per_jenis.values():
            kelompok.sort(key=lambda m: m["merk"].lower())
            utama = [m for m in kelompok if m["utama"]]
            if not utama:
                kelompok[0]["utama"] = True
            elif len(utama) > 1:
                for m in utama[1:]:
                    m["utama"] = False

    def _isi_tabel(self):
        self._sedang_mengisi = True
        urut = sorted(
            self._daftar,
            key=lambda m: (m["material"].lower(), not m["utama"], m["merk"].lower()),
        )
        self.table.setRowCount(0)
        for row_idx, m in enumerate(urut):
            self.table.insertRow(row_idx)

            item_jenis = QTableWidgetItem(m["material"])
            f = item_jenis.font()
            f.setWeight(f.Weight.DemiBold)
            item_jenis.setFont(f)
            item_jenis.setData(Qt.UserRole, m["id"])

            item_merk = QTableWidgetItem(m["merk"])
            item_satuan = QTableWidgetItem(m["satuan"] or "-")
            item_satuan.setTextAlignment(Qt.AlignCenter)
            item_satuan.setForeground(QColor(WARNA_REDUP))

            item_harga = QTableWidgetItem(format_rupiah(m["harga"]))
            item_harga.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            f2 = item_harga.font()
            f2.setWeight(f2.Weight.DemiBold)
            item_harga.setFont(f2)

            item_utama = QTableWidgetItem("●  Utama" if m["utama"] else "-")
            item_utama.setForeground(QColor(WARNA_UTAMA if m["utama"] else WARNA_REDUP))

            self.table.setItem(row_idx, KOL_JENIS, item_jenis)
            self.table.setItem(row_idx, KOL_MERK, item_merk)
            self.table.setItem(row_idx, KOL_SATUAN, item_satuan)
            self.table.setItem(row_idx, KOL_HARGA, item_harga)
            self.table.setItem(row_idx, KOL_UTAMA, item_utama)

        # Pilih ulang baris yang sedang diubah (bila masih ada)
        if self._id_diedit is not None:
            for r in range(self.table.rowCount()):
                if self.table.item(r, KOL_JENIS).data(Qt.UserRole) == self._id_diedit:
                    self.table.selectRow(r)
                    break
        self._sedang_mengisi = False

        jumlah = len(self._daftar)
        self.label_jumlah.setText(f"{jumlah} material" if jumlah else "")
        self.stack.setCurrentIndex(0 if jumlah else 1)

    # ---------- Formulir ----------

    def _atur_mode(self, ubah: bool):
        self.btn_hapus.setVisible(ubah)
        self.btn_batal.setVisible(ubah)
        self.btn_simpan.setText("Perbarui Material" if ubah else "Simpan Material")
        self.label_mode.setText("UBAH MATERIAL" if ubah else "TAMBAH MATERIAL BARU")

    def _saran_satuan(self, jenis: str):
        """Saat jenis dipilih dari daftar, isi satuan yang lazim (hanya saat tambah baru)."""
        if self._id_diedit is not None:
            return
        satuan = JENIS_MATERIAL.get(jenis)
        if satuan:
            self.combo_satuan.setCurrentText(satuan)

    def _reset_form(self):
        self._id_diedit = None
        self.combo_jenis.setCurrentIndex(-1)
        self.combo_jenis.setEditText("")
        self.edit_merk.clear()
        self.combo_satuan.setCurrentIndex(-1)
        self.combo_satuan.setEditText("")
        self.spin_harga.setValue(0)
        self.cek_utama.setChecked(False)
        self._sedang_mengisi = True
        self.table.clearSelection()
        self._sedang_mengisi = False
        self._atur_mode(ubah=False)

    def _pilihan_berubah(self):
        if self._sedang_mengisi:
            return
        baris = self.table.selectionModel().selectedRows()
        if not baris:
            return
        id_dipilih = self.table.item(baris[0].row(), KOL_JENIS).data(Qt.UserRole)
        m = next((x for x in self._daftar if x["id"] == id_dipilih), None)
        if m is None:
            return
        self._id_diedit = m["id"]
        self.combo_jenis.setEditText(m["material"])
        self.edit_merk.setText(m["merk"])
        self.combo_satuan.setEditText(m["satuan"])
        self.spin_harga.setValue(m["harga"])
        self.cek_utama.setChecked(m["utama"])
        self._atur_mode(ubah=True)

    def _batal_ubah(self):
        self._reset_form()

    def _tampilkan_status(self, teks: str):
        self.label_status.setText(teks)
        self._timer_status.start(3500)

    # ---------- Aksi ----------

    def _simpan(self):
        jenis = self.combo_jenis.currentText().strip()
        merk = self.edit_merk.text().strip()
        satuan = self.combo_satuan.currentText().strip()
        harga = self.spin_harga.value()

        if not jenis:
            QMessageBox.warning(
                self,
                "Data Belum Lengkap",
                "Jenis material belum diisi, misalnya Semen.",
            )
            self.combo_jenis.setFocus()
            return
        if not merk:
            QMessageBox.warning(
                self, "Data Belum Lengkap", "Merk belum diisi, misalnya Tiga Roda."
            )
            self.edit_merk.setFocus()
            return
        if not satuan:
            QMessageBox.warning(
                self, "Data Belum Lengkap", "Satuan belum diisi, misalnya sak atau m³."
            )
            self.combo_satuan.setFocus()
            return
        if harga <= 0:
            QMessageBox.warning(
                self, "Data Belum Lengkap", "Harga per satuan harus lebih dari 0."
            )
            self.spin_harga.setFocus()
            return

        for m in self._daftar:
            if (
                m["id"] != self._id_diedit
                and m["material"].lower() == jenis.lower()
                and m["merk"].lower() == merk.lower()
            ):
                QMessageBox.warning(
                    self,
                    "Sudah Ada",
                    f'{jenis} merk "{merk}" sudah tersimpan.\n'
                    "Klik barisnya di daftar bila ingin mengubah harganya.",
                )
                return

        if self._id_diedit is not None:
            rec = next((m for m in self._daftar if m["id"] == self._id_diedit), None)
        else:
            rec = None
        if rec is None:
            rec = {"id": buat_id()}
            self._daftar.append(rec)
        rec.update(
            {
                "material": jenis,
                "merk": merk,
                "satuan": satuan,
                "harga": float(harga),
                "utama": self.cek_utama.isChecked(),
            }
        )

        # Bila ditandai utama, merk lain dengan jenis yang sama otomatis tidak utama.
        if rec["utama"]:
            for m in self._daftar:
                if m is not rec and m["material"].lower() == jenis.lower():
                    m["utama"] = False
        self._normalisasi_utama()

        if not self._simpan_ke_penyimpanan():
            return
        diubah = self._id_diedit is not None
        self._reset_form()
        self._isi_tabel()
        self._tampilkan_status(
            f"{'Diperbarui' if diubah else 'Tersimpan'}: {jenis} — {merk}"
        )
        self.combo_jenis.setFocus()

    def _hapus(self):
        if self._id_diedit is None:
            return
        m = next((x for x in self._daftar if x["id"] == self._id_diedit), None)
        if m is None:
            return

        kotak = QMessageBox(self)
        kotak.setIcon(QMessageBox.Warning)
        kotak.setWindowTitle("Hapus Material")
        kotak.setText(f'Hapus {m["material"]} merk "{m["merk"]}"?')
        kotak.setInformativeText(
            "Data harga yang tersimpan untuk merk ini akan hilang."
        )
        btn_hapus = kotak.addButton("Hapus", QMessageBox.DestructiveRole)
        btn_batal = kotak.addButton("Batal", QMessageBox.RejectRole)
        kotak.setDefaultButton(btn_batal)
        kotak.exec()
        if kotak.clickedButton() is not btn_hapus:
            return

        nama = f"{m['material']} — {m['merk']}"
        self._daftar = [x for x in self._daftar if x["id"] != m["id"]]
        self._normalisasi_utama()  # bila yang dihapus merk utama, merk lain naik menjadi utama
        if not self._simpan_ke_penyimpanan():
            return
        self._reset_form()
        self._isi_tabel()
        self._tampilkan_status(f"Dihapus: {nama}")
