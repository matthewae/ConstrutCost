"""
Layar Tabel Hasil Estimasi QTO & RAB (UC-03) untuk CostStruct.
Edit volume di sini otomatis memicu hitung ulang subtotal_biaya.

Peningkatan tampilan dan kemudahan penggunaan:
- Ringkasan RAB dipindah ke kartu di atas tabel, jadi total selalu terlihat
  walaupun tabel di-scroll (Subtotal, PPN, Total RAB, jumlah item)
- Pencarian dan filter kategori pekerjaan
- Kategori diberi warna, angka rata kanan, status "Otomatis" / "Manual" berwarna
- Kolom Volume menampilkan satuan dan terlindung dari scroll mouse yang tidak
  sengaja (angka hanya berubah bila kolomnya sedang diklik)
- Petunjuk singkat cara mengedit volume
- Tiga kondisi tampilan: tabel, belum ada estimasi, dan hasil filter kosong
- Pintasan: Ctrl+F (cari), Ctrl+E (export)

Logika data (baca, edit volume, hitung ulang, export) tidak diubah.
"""

from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QTableWidget,
    QTableWidgetItem,
    QPushButton,
    QLabel,
    QHeaderView,
    QAbstractItemView,
    QDoubleSpinBox,
    QAbstractSpinBox,
    QStackedWidget,
    QFrame,
    QMessageBox,
    QLineEdit,
    QComboBox,
)
import tempfile
from pathlib import Path

from PySide6.QtCore import Qt, QRectF, QTimer
from PySide6.QtGui import (
    QColor,
    QPainter,
    QPen,
    QPixmap,
    QFont,
    QShortcut,
    QKeySequence,
)

from database.estimasi_repository import (
    get_hasil_estimasi_by_proyek,
    update_volume_estimasi,
    get_total_rab,
    PPN_RATE,
)
from estimasi_service import jalankan_estimasi
from gui.export_dialog import ExportDialog
from gui.import_dialog import tampilkan_hasil_proses
from gui.proses_latar import jalankan_di_latar

STYLE_SHEET = """
QWidget {
    color: #e4ebf2;
    font-family: "Segoe UI", "Inter", sans-serif;
    font-size: 13px;
}
QMainWindow, QWidget#root { background-color: #131d28; }
QLabel { background: transparent; }

QLabel#judulApp { font-size: 22px; font-weight: 700; color: #ffffff; }
QLabel#subjudulApp { color: #7d92a8; font-size: 12px; }
QLabel#jumlahItem { color: #7d92a8; font-size: 12px; }
QLabel#petunjuk { color: #6f869c; font-size: 12px; }

/* ---- Kartu ringkasan ---- */
QFrame#kartuStat {
    background-color: #1b2937;
    border: 1px solid #27394b;
    border-radius: 12px;
}
QFrame#kartuUtama {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 #24518a, stop:1 #1b3a63);
    border: 1px solid #3a6ba8;
    border-radius: 12px;
}
QLabel#statJudul { color: #7d92a8; font-size: 11px; font-weight: 600; letter-spacing: 1px; }
QLabel#statNilai { color: #ffffff; font-size: 22px; font-weight: 700; }
QLabel#statKet { color: #6f869c; font-size: 11px; }
QFrame#kartuUtama QLabel#statJudul { color: #b8d4f5; }
QFrame#kartuUtama QLabel#statNilai { color: #ffffff; font-size: 22px; }
QFrame#kartuUtama QLabel#statKet { color: #9fc0e8; }

/* ---- Pencarian & filter ---- */
QLineEdit#kolomCari, QComboBox#filterKategori {
    background-color: #1b2937;
    border: 1px solid #2b3f53;
    border-radius: 8px;
    padding: 8px 14px;
    color: #e4ebf2;
    selection-background-color: #2a4a6e;
}
QLineEdit#kolomCari:focus, QComboBox#filterKategori:focus {
    border: 1px solid #4f9df7;
    background-color: #1e2d3d;
}
QComboBox#filterKategori { min-width: 170px; }
QComboBox#filterKategori::drop-down { border: none; width: 28px; }
QComboBox#filterKategori::down-arrow { image: __PANAH__; width: 12px; height: 12px; }
QComboBox QAbstractItemView {
    background-color: #1b2937;
    border: 1px solid #2b3f53;
    selection-background-color: #25456a;
    color: #e4ebf2;
    outline: none;
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
QTableWidget::item { padding: 8px 10px; border: none; }
QTableWidget::item:hover { background-color: #233447; }
QTableWidget::item:selected { background-color: #25456a; }
QHeaderView { background-color: transparent; }
QHeaderView::section {
    background-color: #1a2633;
    color: #7d92a8;
    padding: 12px 10px;
    border: none;
    border-bottom: 1px solid #27394b;
    font-weight: 700;
    font-size: 11px;
    letter-spacing: 1px;
}

/* ---- Kolom volume yang bisa diedit ---- */
QTableWidget QDoubleSpinBox {
    background-color: #223244;
    border: 1px solid #2f4458;
    border-radius: 6px;
    padding: 4px 8px;
    margin: 6px 8px;
    color: #ffffff;
    selection-background-color: #2a5d99;
}
QTableWidget QDoubleSpinBox:hover { border: 1px solid #4a6a8c; }
QTableWidget QDoubleSpinBox:focus {
    border: 1px solid #4f9df7;
    background-color: #1e3a5a;
}

/* ---- Scrollbar tipis ---- */
QScrollBar:vertical { background: transparent; width: 10px; margin: 4px 2px; }
QScrollBar::handle:vertical { background: #34495e; border-radius: 4px; min-height: 36px; }
QScrollBar::handle:vertical:hover { background: #4a6580; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
QScrollBar:horizontal { background: transparent; height: 10px; margin: 2px 4px; }
QScrollBar::handle:horizontal { background: #34495e; border-radius: 4px; min-width: 36px; }
QScrollBar::handle:horizontal:hover { background: #4a6580; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal { background: transparent; }

/* ---- Tombol ---- */
QPushButton { border-radius: 8px; padding: 10px 20px; font-weight: 600; }
QPushButton#btnExport { background-color: #4f9df7; color: #0c1a26; }
QPushButton#btnExport:hover { background-color: #6bacf9; }
QPushButton#btnExport:pressed { background-color: #3f8ce6; }
QPushButton#btnKembali {
    background-color: #223244;
    color: #e4ebf2;
    border: 1px solid #2f4458;
}
QPushButton#btnKembali:hover { background-color: #2b3f54; }
QPushButton#btnCTA { background-color: #4f9df7; color: #0c1a26; padding: 12px 26px; }
QPushButton#btnCTA:hover { background-color: #6bacf9; }

/* ---- Kondisi kosong ---- */
QFrame#kartuKosong {
    background-color: #1a2633;
    border: 1px dashed #2f4458;
    border-radius: 14px;
}
QLabel#kosongJudul { font-size: 18px; font-weight: 700; color: #ffffff; }
QLabel#kosongDeskripsi { color: #7d92a8; font-size: 13px; }

/* ---- Dialog & tooltip ---- */
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

(
    KOL_KATEGORI,
    KOL_PEKERJAAN,
    KOL_ELEMEN,
    KOL_SATUAN,
    KOL_VOLUME,
    KOL_HARGA,
    KOL_SUBTOTAL,
    KOL_STATUS,
) = range(8)

SEMUA_KATEGORI = "Semua kategori"
WARNA_KATEGORI = ["#6bb2ff", "#7fd1b9", "#f5b84f", "#c39bf5", "#f48b8b", "#9bd16b"]
WARNA_REDUP = "#8fa3b8"
WARNA_MANUAL = "#f5b84f"
WARNA_OTOMATIS = "#6fcf97"


def _siapkan_ikon_panah() -> str:
    """Membuat gambar panah kecil untuk dropdown di folder sementara.
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


def format_rupiah(nilai: float) -> str:
    return "Rp " + f"{nilai:,.0f}".replace(",", ".")


# ====================================================================
# Widget pendukung
# ====================================================================


class SpinVolume(QDoubleSpinBox):
    """Kolom volume: rata kanan, tanpa tombol panah, dan tidak berubah karena scroll mouse
    kecuali sedang difokuskan (supaya angka tidak berubah tidak sengaja saat menggulir tabel)."""

    def __init__(self, nilai: float, satuan: str):
        super().__init__()
        self.setRange(0, 1_000_000)
        self.setDecimals(3)
        if satuan:
            self.setSuffix(f" {satuan}")
        self.setGroupSeparatorShown(True)
        self.setValue(nilai)
        self.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.setButtonSymbols(QAbstractSpinBox.NoButtons)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setKeyboardTracking(False)
        self.setToolTip("Klik lalu ketik volume baru, tekan Enter untuk menyimpan")

    def wheelEvent(self, event):
        if self.hasFocus():
            super().wheelEvent(event)
        else:
            event.ignore()  # teruskan ke tabel supaya tetap bisa di-scroll

    def focusInEvent(self, event):
        super().focusInEvent(event)
        QTimer.singleShot(0, self.selectAll)  # langsung siap diketik ulang


class IkonKosong(QWidget):
    """Ikon kondisi 'belum ada estimasi': kotak putus-putus dengan tiga batang naik."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(84, 84)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(QPen(QColor("#3a5068"), 2, Qt.DashLine))
        p.setBrush(QColor("#1f2f3f"))
        p.drawRoundedRect(QRectF(3, 3, self.width() - 6, self.height() - 6), 20, 20)

        p.setPen(Qt.NoPen)
        lebar, jarak = 9, 6
        total = 3 * lebar + 2 * jarak
        x0 = (self.width() - total) / 2
        dasar = self.height() - 26
        for i, (t, a) in enumerate(zip([14, 26, 38], [150, 200, 255])):
            p.setBrush(QColor(79, 157, 247, a))
            p.drawRoundedRect(
                QRectF(x0 + i * (lebar + jarak), dasar - t, lebar, t), 3, 3
            )
        p.end()


class KartuRingkasan(QFrame):
    """Kartu ringkasan: judul kecil, nilai besar, keterangan. `utama=True` untuk Total RAB."""

    def __init__(self, judul: str, utama: bool = False):
        super().__init__()
        self.setObjectName("kartuUtama" if utama else "kartuStat")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 14, 20, 14)
        layout.setSpacing(2)

        self._judul = QLabel(judul.upper())
        self._judul.setObjectName("statJudul")
        self._nilai = QLabel("-")
        self._nilai.setObjectName("statNilai")
        self._ket = QLabel("")
        self._ket.setObjectName("statKet")
        layout.addWidget(self._judul)
        layout.addWidget(self._nilai)
        layout.addWidget(self._ket)

    def set_judul(self, judul: str):
        self._judul.setText(judul.upper())

    def set_data(self, nilai: str, keterangan: str = ""):
        self._nilai.setText(nilai)
        self._ket.setText(keterangan)


def _item(teks, rata=None, warna=None, tebal=False, tooltip=None):
    """Pembuat sel tabel dengan perataan, warna, dan ketebalan huruf opsional."""
    it = QTableWidgetItem(teks)
    if rata is not None:
        it.setTextAlignment(rata | Qt.AlignVCenter)
    if warna:
        it.setForeground(QColor(warna))
    if tebal:
        f = it.font()
        f.setWeight(QFont.DemiBold)
        it.setFont(f)
    if tooltip:
        it.setToolTip(tooltip)
    return it


def _item_status(manual: bool):
    if manual:
        return _item(
            "●  Manual",
            warna=WARNA_MANUAL,
            tebal=True,
            tooltip="Volume ini sudah diubah secara manual",
        )
    return _item(
        "●  Otomatis",
        warna=WARNA_OTOMATIS,
        tooltip="Volume dihitung otomatis dari model IFC",
    )


# ====================================================================
# Window estimasi
# ====================================================================


class EstimasiWindow(QMainWindow):
    """Layar hasil estimasi QTO & RAB untuk satu proyek."""

    HALAMAN_TABEL = 0
    HALAMAN_KOSONG = 1
    HALAMAN_TIDAK_ADA_HASIL = 2

    def __init__(self, proyek_id: int, nama_proyek: str, on_kembali=None):
        super().__init__()
        self.proyek_id = proyek_id
        self.nama_proyek = nama_proyek
        self.on_kembali = on_kembali
        self._volume_terakhir = {}  # hasil_id -> volume terakhir, untuk deteksi perubahan nyata
        self._data = []  # semua baris hasil estimasi (cache untuk filter)
        self._index = {}  # hasil_id -> baris pada _data
        self._warna_kategori = {}

        self.setWindowTitle(f"CostStruct — Estimasi: {nama_proyek}")
        self.resize(1120, 720)
        self.setMinimumSize(900, 580)
        self.setStyleSheet(STYLE_SHEET.replace("__PANAH__", _siapkan_ikon_panah()))

        central = QWidget()
        central.setObjectName("root")
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(32, 26, 32, 22)
        root.setSpacing(16)

        # --- Header ---
        header_row = QHBoxLayout()
        btn_kembali = QPushButton("←  Kembali")
        btn_kembali.setObjectName("btnKembali")
        btn_kembali.setCursor(Qt.PointingHandCursor)
        btn_kembali.setToolTip("Kembali ke daftar proyek")
        btn_kembali.clicked.connect(self._kembali)
        header_row.addWidget(btn_kembali)

        judul_col = QVBoxLayout()
        judul_col.setSpacing(2)
        judul = QLabel(nama_proyek)
        judul.setObjectName("judulApp")
        subjudul = QLabel("Hasil Estimasi — Quantity Take-Off & RAB")
        subjudul.setObjectName("subjudulApp")
        judul_col.addWidget(judul)
        judul_col.addWidget(subjudul)
        header_row.addSpacing(14)
        header_row.addLayout(judul_col)
        header_row.addStretch()

        self.btn_export = QPushButton("Export RAB")
        self.btn_export.setObjectName("btnExport")
        self.btn_export.setCursor(Qt.PointingHandCursor)
        self.btn_export.setToolTip("Export RAB proyek ini (Ctrl+E)")
        self.btn_export.clicked.connect(self._buka_export)
        header_row.addWidget(self.btn_export)
        root.addLayout(header_row)

        # --- Kartu ringkasan RAB ---
        self.baris_ringkasan = QWidget()
        ringkasan_layout = QHBoxLayout(self.baris_ringkasan)
        ringkasan_layout.setContentsMargins(0, 0, 0, 0)
        ringkasan_layout.setSpacing(14)
        self.kartu_subtotal = KartuRingkasan("Subtotal RAB")
        self.kartu_ppn = KartuRingkasan(f"PPN {int(PPN_RATE * 100)}%")
        self.kartu_total = KartuRingkasan("Total RAB", utama=True)
        self.kartu_item = KartuRingkasan("Item Pekerjaan")
        for kartu, tarik in (
            (self.kartu_subtotal, 1),
            (self.kartu_ppn, 1),
            (self.kartu_total, 1),
            (self.kartu_item, 1),
        ):
            ringkasan_layout.addWidget(kartu, stretch=tarik)
        root.addWidget(self.baris_ringkasan)

        # --- Pencarian + filter kategori ---
        self.baris_filter = QWidget()
        filter_layout = QHBoxLayout(self.baris_filter)
        filter_layout.setContentsMargins(0, 0, 0, 0)
        filter_layout.setSpacing(12)

        self.kolom_cari = QLineEdit()
        self.kolom_cari.setObjectName("kolomCari")
        self.kolom_cari.setPlaceholderText("Cari pekerjaan atau elemen...   (Ctrl+F)")
        self.kolom_cari.setClearButtonEnabled(True)
        self.kolom_cari.textChanged.connect(self._terapkan_filter)
        filter_layout.addWidget(self.kolom_cari, stretch=1)

        self.combo_kategori = QComboBox()
        self.combo_kategori.setObjectName("filterKategori")
        self.combo_kategori.setToolTip("Tampilkan satu kategori pekerjaan saja")
        self.combo_kategori.currentIndexChanged.connect(self._terapkan_filter)
        filter_layout.addWidget(self.combo_kategori)

        self.label_jumlah = QLabel("")
        self.label_jumlah.setObjectName("jumlahItem")
        filter_layout.addWidget(self.label_jumlah)
        root.addWidget(self.baris_filter)

        # --- Stacked: tabel / belum ada estimasi / hasil filter kosong ---
        self.stack = QStackedWidget()
        root.addWidget(self.stack, stretch=1)
        self.stack.addWidget(self._buat_halaman_tabel())
        self.stack.addWidget(self._buat_halaman_kosong())
        self.stack.addWidget(self._buat_halaman_tidak_ada_hasil())

        # --- Petunjuk penggunaan ---
        self.label_petunjuk = QLabel(
            "Klik angka pada kolom Volume untuk mengubahnya, lalu tekan Enter. "
            "Subtotal dan Total RAB dihitung ulang otomatis."
        )
        self.label_petunjuk.setObjectName("petunjuk")
        self.label_petunjuk.setWordWrap(True)
        root.addWidget(self.label_petunjuk)

        # --- Pintasan keyboard ---
        QShortcut(QKeySequence("Ctrl+F"), self, activated=self._fokus_cari)
        QShortcut(QKeySequence("Ctrl+E"), self, activated=self._pintasan_export)

        self.muat_data()

    # ---------- Konstruksi UI ----------

    def _buat_halaman_tabel(self) -> QWidget:
        wrap = QWidget()
        layout = QVBoxLayout(wrap)
        layout.setContentsMargins(0, 0, 0, 0)

        self.table = QTableWidget(0, 8)
        self.table.setHorizontalHeaderLabels(
            [
                "KATEGORI",
                "PEKERJAAN",
                "ELEMEN / LANTAI",
                "SATUAN",
                "VOLUME (EDIT)",
                "HARGA SATUAN",
                "SUBTOTAL",
                "STATUS",
            ]
        )
        # Kolom angka rata kanan, satuan di tengah
        for kol in (KOL_VOLUME, KOL_HARGA, KOL_SUBTOTAL):
            self.table.horizontalHeaderItem(kol).setTextAlignment(
                Qt.AlignRight | Qt.AlignVCenter
            )
        self.table.horizontalHeaderItem(KOL_SATUAN).setTextAlignment(Qt.AlignCenter)

        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(
            QAbstractItemView.NoEditTriggers
        )  # edit lewat spinbox
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        self.table.setTextElideMode(Qt.ElideRight)
        self.table.setWordWrap(
            False
        )  # nama panjang dipotong dengan "…", lengkapnya di tooltip
        self.table.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(52)

        header = self.table.horizontalHeader()
        header.setHighlightSections(False)
        header.setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        header.setSectionResizeMode(KOL_PEKERJAAN, QHeaderView.Stretch)
        for kol in (
            KOL_KATEGORI,
            KOL_ELEMEN,
            KOL_SATUAN,
            KOL_HARGA,
            KOL_SUBTOTAL,
            KOL_STATUS,
        ):
            header.setSectionResizeMode(kol, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(KOL_VOLUME, QHeaderView.Fixed)
        self.table.setColumnWidth(KOL_VOLUME, 155)

        layout.addWidget(self.table)
        return wrap

    def _buat_halaman_kosong(self) -> QWidget:
        wrap = QFrame()
        wrap.setObjectName("kartuKosong")
        layout = QVBoxLayout(wrap)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(10)

        layout.addWidget(IkonKosong(), alignment=Qt.AlignCenter)
        layout.addSpacing(8)

        judul = QLabel("Belum ada hasil estimasi")
        judul.setObjectName("kosongJudul")
        judul.setAlignment(Qt.AlignCenter)

        self.label_info_kosong = QLabel(
            "Parsing IFC & perhitungan rule-engine untuk proyek ini belum dijalankan\n"
            "atau tidak menghasilkan elemen struktural."
        )
        self.label_info_kosong.setObjectName("kosongDeskripsi")
        self.label_info_kosong.setAlignment(Qt.AlignCenter)

        btn_jalankan = QPushButton("Jalankan Estimasi dari File IFC")
        btn_jalankan.setObjectName("btnCTA")
        btn_jalankan.setCursor(Qt.PointingHandCursor)
        btn_jalankan.setFixedWidth(290)
        btn_jalankan.clicked.connect(self._jalankan_estimasi)

        layout.addWidget(judul)
        layout.addWidget(self.label_info_kosong)
        layout.addSpacing(8)
        layout.addWidget(btn_jalankan, alignment=Qt.AlignCenter)
        return wrap

    def _buat_halaman_tidak_ada_hasil(self) -> QWidget:
        wrap = QFrame()
        wrap.setObjectName("kartuKosong")
        layout = QVBoxLayout(wrap)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(8)

        judul = QLabel("Item tidak ditemukan")
        judul.setObjectName("kosongJudul")
        judul.setAlignment(Qt.AlignCenter)

        deskripsi = QLabel(
            'Coba ubah kata kunci pencarian atau pilih kategori "Semua kategori".'
        )
        deskripsi.setObjectName("kosongDeskripsi")
        deskripsi.setAlignment(Qt.AlignCenter)

        layout.addWidget(judul)
        layout.addWidget(deskripsi)
        return wrap

    # ---------- Data ----------

    def muat_data(self):
        self._data = [dict(r) for r in get_hasil_estimasi_by_proyek(self.proyek_id)]
        self._index = {r["hasil_id"]: r for r in self._data}
        self._volume_terakhir = {}
        ada_data = len(self._data) > 0

        # Harga satuan diturunkan dari subtotal / volume; disimpan agar tetap
        # terbaca walau volume nanti diubah menjadi 0.
        for r in self._data:
            v = r["volume_pekerjaan"]
            r["harga_satuan"] = r["subtotal_biaya"] / v if v else 0

        self.baris_ringkasan.setVisible(ada_data)
        self.baris_filter.setVisible(ada_data)
        self.label_petunjuk.setVisible(ada_data)
        self.btn_export.setVisible(ada_data)

        if not ada_data:
            self.table.setRowCount(0)
            self.stack.setCurrentIndex(self.HALAMAN_KOSONG)
            return

        self._isi_pilihan_kategori()
        self._terapkan_filter()
        self._perbarui_ringkasan()

    def _isi_pilihan_kategori(self):
        kategori = sorted({r["kategori"] for r in self._data if r["kategori"]})
        self._warna_kategori = {
            k: WARNA_KATEGORI[i % len(WARNA_KATEGORI)] for i, k in enumerate(kategori)
        }
        pilihan_lama = self.combo_kategori.currentText()
        self.combo_kategori.blockSignals(True)
        self.combo_kategori.clear()
        self.combo_kategori.addItem(SEMUA_KATEGORI)
        self.combo_kategori.addItems(kategori)
        idx = self.combo_kategori.findText(pilihan_lama)
        self.combo_kategori.setCurrentIndex(idx if idx >= 0 else 0)
        self.combo_kategori.blockSignals(False)

    @staticmethod
    def _label_elemen(row: dict) -> str:
        label = row["nama_elemen"] or "-"
        if row["lantai"]:
            label += f" ({row['lantai']})"
        return label

    def _terapkan_filter(self, *_):
        if not self._data:
            return
        kata = self.kolom_cari.text().strip().lower()
        kategori = self.combo_kategori.currentText()
        semua_kategori = (kategori == SEMUA_KATEGORI) or not kategori

        hasil = [
            r
            for r in self._data
            if (semua_kategori or r["kategori"] == kategori)
            and (
                not kata
                or kata in (r["nama_pekerjaan"] or "").lower()
                or kata in self._label_elemen(r).lower()
            )
        ]
        self._isi_tabel(hasil)

        total = len(self._data)
        if len(hasil) == total:
            self.label_jumlah.setText(f"{total} item")
        else:
            self.label_jumlah.setText(f"{len(hasil)} dari {total} item")
        self.stack.setCurrentIndex(
            self.HALAMAN_TABEL if hasil else self.HALAMAN_TIDAK_ADA_HASIL
        )

    def _isi_tabel(self, rows):
        self.table.setRowCount(0)
        for row_idx, row in enumerate(rows):
            self.table.insertRow(row_idx)
            hasil_id = row["hasil_id"]

            kategori = row["kategori"] or "-"
            item_kategori = _item(
                kategori, warna=self._warna_kategori.get(row["kategori"]), tebal=True
            )
            item_kategori.setData(
                Qt.UserRole, hasil_id
            )  # untuk mencari baris saat ada perubahan
            self.table.setItem(row_idx, KOL_KATEGORI, item_kategori)

            self.table.setItem(
                row_idx,
                KOL_PEKERJAAN,
                _item(row["nama_pekerjaan"], tooltip=row["nama_pekerjaan"]),
            )
            self.table.setItem(
                row_idx, KOL_ELEMEN, _item(self._label_elemen(row), warna=WARNA_REDUP)
            )
            self.table.setItem(
                row_idx,
                KOL_SATUAN,
                _item(row["satuan"], rata=Qt.AlignHCenter, warna=WARNA_REDUP),
            )

            spin_volume = SpinVolume(row["volume_pekerjaan"], row["satuan"])
            self._volume_terakhir[hasil_id] = spin_volume.value()
            spin_volume.editingFinished.connect(
                lambda hid=hasil_id, pid=row["pekerjaan_id"], sp=spin_volume: (
                    self._volume_diubah(hid, pid, sp.value())
                )
            )
            self.table.setCellWidget(row_idx, KOL_VOLUME, spin_volume)

            self.table.setItem(
                row_idx,
                KOL_HARGA,
                _item(
                    format_rupiah(row["harga_satuan"]),
                    rata=Qt.AlignRight,
                    warna=WARNA_REDUP,
                ),
            )
            self.table.setItem(
                row_idx,
                KOL_SUBTOTAL,
                _item(
                    format_rupiah(row["subtotal_biaya"]), rata=Qt.AlignRight, tebal=True
                ),
            )
            self.table.setItem(row_idx, KOL_STATUS, _item_status(row["diedit_manual"]))

    def _cari_baris(self, hasil_id: int) -> int:
        for r in range(self.table.rowCount()):
            item = self.table.item(r, KOL_KATEGORI)
            if item is not None and item.data(Qt.UserRole) == hasil_id:
                return r
        return -1

    def _volume_diubah(self, hasil_id: int, pekerjaan_id: int, volume_baru: float):
        # editingFinished juga terpicu saat fokus hilang tanpa perubahan -> abaikan
        if abs(volume_baru - self._volume_terakhir.get(hasil_id, volume_baru)) < 1e-9:
            return
        subtotal_baru = update_volume_estimasi(hasil_id, pekerjaan_id, volume_baru)
        self._volume_terakhir[hasil_id] = volume_baru

        # Perbarui cache supaya tidak hilang saat tabel dibangun ulang oleh filter
        row = self._index.get(hasil_id)
        if row is not None:
            row["volume_pekerjaan"] = volume_baru
            row["subtotal_biaya"] = subtotal_baru
            row["diedit_manual"] = 1
            if volume_baru > 0:
                row["harga_satuan"] = subtotal_baru / volume_baru

        baris = self._cari_baris(hasil_id)
        if baris >= 0 and row is not None:
            self.table.setItem(
                baris,
                KOL_HARGA,
                _item(
                    format_rupiah(row["harga_satuan"]),
                    rata=Qt.AlignRight,
                    warna=WARNA_REDUP,
                ),
            )
            self.table.setItem(
                baris,
                KOL_SUBTOTAL,
                _item(format_rupiah(subtotal_baru), rata=Qt.AlignRight, tebal=True),
            )
            self.table.setItem(baris, KOL_STATUS, _item_status(True))
        self._perbarui_ringkasan()

    def _perbarui_ringkasan(self):
        subtotal = get_total_rab(self.proyek_id)
        ppn = subtotal * PPN_RATE
        self.kartu_subtotal.set_data(format_rupiah(subtotal), "sebelum PPN")
        self.kartu_ppn.set_data(format_rupiah(ppn), "pajak pertambahan nilai")
        self.kartu_total.set_data(format_rupiah(subtotal + ppn), "termasuk PPN")

        jumlah = len(self._data)
        manual = sum(1 for r in self._data if r["diedit_manual"])
        ket = f"{manual} diedit manual" if manual else "semua otomatis dari IFC"
        self.kartu_item.set_data(str(jumlah), ket)

    def _jalankan_estimasi(self):
        """Validasi + parse ulang file IFC proyek ini lalu isi hasil_estimasi (KF-1..KF-4)."""
        try:
            r = jalankan_di_latar(
                self,
                "Membaca elemen & menghitung kuantitas...",
                jalankan_estimasi,
                self.proyek_id,
                pakai_progress=True,
            )
        except Exception as e:
            QMessageBox.critical(self, "Parsing Gagal", str(e))
            return

        self.muat_data()
        tampilkan_hasil_proses(self, "Hasil Estimasi", r)

    def _fokus_cari(self):
        if self.baris_filter.isVisible():
            self.kolom_cari.setFocus()
            self.kolom_cari.selectAll()

    def _pintasan_export(self):
        if self.btn_export.isVisible():
            self._buka_export()

    def _buka_export(self):
        ExportDialog(self.proyek_id, self.nama_proyek, self).exec()

    # ---------- Navigasi ----------

    def _kembali(self):
        if self.on_kembali:
            self.on_kembali()
        else:
            self.close()
