"""
Layar Dashboard / Daftar Proyek (KF-7, KF-9) untuk CostStruct.

Peningkatan tampilan:
- Header dengan logo mini dan tombol aksi utama
- Kartu ringkasan (total proyek, proyek ber-IFC, terakhir diubah)
- Tabel lebih bersih: nama file IFC singkat (path lengkap di tooltip),
  baris lebih lega, hover, scrollbar tipis, dan bisa diurutkan per kolom
- Tiga kondisi tampilan: tabel, belum ada proyek, dan hasil pencarian kosong
- Konfirmasi hapus menyebut nama proyek, dengan "Batal" sebagai pilihan bawaan
- Tombol Pengaturan (Ctrl+,) untuk menyimpan material, merk, dan harga
- Pintasan keyboard: Ctrl+N (proyek baru), Ctrl+F (cari)

Import proyek baru mengikuti UC-01: validasi file -> ringkasan & konfirmasi -> parsing
(proses latar dengan indikator) -> halaman hasil estimasi. File .ifc juga bisa diseret ke jendela.
"""

import multiprocessing
import sys
from pathlib import Path

from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QTableWidget,
    QTableWidgetItem,
    QPushButton,
    QLabel,
    QHeaderView,
    QFileDialog,
    QMessageBox,
    QAbstractItemView,
    QLineEdit,
    QStackedWidget,
    QFrame,
)
from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import (
    QColor,
    QPainter,
    QLinearGradient,
    QBrush,
    QPen,
    QFont,
    QShortcut,
    QKeySequence,
)

from database.proyek_repository import get_all_proyek, create_proyek, delete_proyek
from estimasi_service import jalankan_estimasi
from gui.estimasi_window import EstimasiWindow
from gui.import_dialog import RingkasanImportDialog, tampilkan_hasil_proses
from gui.pengaturan_dialog import PengaturanDialog
from gui.proses_latar import jalankan_di_latar
from ifc_reader import FileIFCTidakValid, buka_dan_validasi


STYLE_SHEET = """
QWidget {
    color: #e4ebf2;
    font-family: "Segoe UI", "Inter", sans-serif;
    font-size: 13px;
}
QMainWindow, QWidget#root { background-color: #131d28; }
QLabel { background: transparent; }

QLabel#judulApp { font-size: 24px; font-weight: 700; color: #ffffff; }
QLabel#subjudulApp { color: #7d92a8; font-size: 12px; }
QLabel#jumlahProyek { color: #7d92a8; font-size: 12px; }
QLabel#petunjuk { color: #566b80; font-size: 11px; }

/* ---- Kartu ringkasan ---- */
QFrame#kartuStat {
    background-color: #1b2937;
    border: 1px solid #27394b;
    border-radius: 12px;
}
QLabel#statJudul { color: #7d92a8; font-size: 11px; font-weight: 600; letter-spacing: 1px; }
QLabel#statNilai { color: #ffffff; font-size: 24px; font-weight: 700; }
QLabel#statKet { color: #6f869c; font-size: 11px; }

/* ---- Pencarian ---- */
QLineEdit#kolomCari {
    background-color: #1b2937;
    border: 1px solid #2b3f53;
    border-radius: 8px;
    padding: 9px 14px;
    color: #e4ebf2;
    selection-background-color: #2a4a6e;
}
QLineEdit#kolomCari:focus { border: 1px solid #4f9df7; background-color: #1e2d3d; }

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
QHeaderView::section:hover { color: #cfdbe7; }

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
QPushButton#btnPrimary { background-color: #4f9df7; color: #0c1a26; }
QPushButton#btnPrimary:hover { background-color: #6bacf9; }
QPushButton#btnPrimary:pressed { background-color: #3f8ce6; }
QPushButton#btnSecondary {
    background-color: #223244;
    color: #e4ebf2;
    border: 1px solid #2f4458;
}
QPushButton#btnSecondary:hover { background-color: #2b3f54; }
QPushButton#btnSecondary:disabled { color: #4c5c6d; background-color: #1b2937; border: 1px solid #263646; }
QPushButton#btnDanger {
    background-color: transparent;
    color: #f48b8b;
    border: 1px solid #54343d;
}
QPushButton#btnDanger:hover { background-color: #3a2229; }
QPushButton#btnDanger:disabled { color: #4c5c6d; border: 1px solid #263646; }
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


# ====================================================================
# Widget kecil yang digambar dengan QPainter (tanpa file gambar)
# ====================================================================


class LogoMini(QWidget):
    """Logo CostStruct versi kecil untuk header (sama dengan logo di splash)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(46, 46)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        area = QRectF(0, 0, self.width(), self.height())
        grad = QLinearGradient(area.topLeft(), area.bottomRight())
        grad.setColorAt(0.0, QColor("#6bb2ff"))
        grad.setColorAt(1.0, QColor("#2b6cd4"))
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(grad))
        p.drawRoundedRect(area, 13, 13)

        lebar, jarak = 7, 4
        total = 3 * lebar + 2 * jarak
        x0 = (self.width() - total) / 2
        dasar = self.height() - 12
        for i, (t, a) in enumerate(zip([10, 18, 26], [170, 215, 255])):
            p.setBrush(QColor(255, 255, 255, a))
            p.drawRoundedRect(
                QRectF(x0 + i * (lebar + jarak), dasar - t, lebar, t), 2, 2
            )
        p.end()


class IkonKosong(QWidget):
    """Ikon untuk kondisi 'belum ada proyek': kotak putus-putus dengan tanda plus."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(84, 84)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        pena = QPen(QColor("#3a5068"), 2, Qt.DashLine)
        p.setPen(pena)
        p.setBrush(QColor("#1f2f3f"))
        p.drawRoundedRect(QRectF(3, 3, self.width() - 6, self.height() - 6), 20, 20)

        pena_plus = QPen(QColor("#4f9df7"), 4, Qt.SolidLine, Qt.RoundCap)
        p.setPen(pena_plus)
        cx, cy, r = self.width() / 2, self.height() / 2, 13
        p.drawLine(int(cx - r), int(cy), int(cx + r), int(cy))
        p.drawLine(int(cx), int(cy - r), int(cx), int(cy + r))
        p.end()


class KartuStat(QFrame):
    """Kartu ringkasan kecil: judul, nilai besar, dan keterangan."""

    def __init__(self, judul: str):
        super().__init__()
        self.setObjectName("kartuStat")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
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

    def set_data(self, nilai: str, keterangan: str = ""):
        self._nilai.setText(nilai)
        self._ket.setText(keterangan)


# ====================================================================
# Window utama
# ====================================================================


class DashboardWindow(QMainWindow):
    """Window utama saat aplikasi dibuka: daftar proyek yang tersimpan."""

    HALAMAN_TABEL = 0
    HALAMAN_KOSONG = 1
    HALAMAN_TIDAK_ADA_HASIL = 2

    def __init__(self):
        super().__init__()
        self.setWindowTitle("CostStruct — Dashboard Proyek")
        self.resize(1040, 680)
        self.setMinimumSize(860, 560)
        self.setStyleSheet(STYLE_SHEET)

        self._semua_proyek = []
        self._window_estimasi = None

        central = QWidget()
        central.setObjectName("root")
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(32, 26, 32, 22)
        root.setSpacing(18)

        # --- Header: logo + judul + tombol proyek baru ---
        header_row = QHBoxLayout()
        header_row.setSpacing(14)
        header_row.addWidget(LogoMini(), alignment=Qt.AlignVCenter)

        judul_col = QVBoxLayout()
        judul_col.setSpacing(2)
        judul = QLabel("Daftar Proyek")
        judul.setObjectName("judulApp")
        subjudul = QLabel("CostStruct — BIM-Based Quantity Take-Off & Estimasi RAB")
        subjudul.setObjectName("subjudulApp")
        judul_col.addWidget(judul)
        judul_col.addWidget(subjudul)
        header_row.addLayout(judul_col)
        header_row.addStretch()

        self.btn_pengaturan = QPushButton("Pengaturan")
        self.btn_pengaturan.setObjectName("btnSecondary")
        self.btn_pengaturan.setCursor(Qt.PointingHandCursor)
        self.btn_pengaturan.setToolTip(
            "Atur material, merk, dan harga yang dipakai (Ctrl+,)"
        )
        self.btn_pengaturan.clicked.connect(self.buka_pengaturan)
        header_row.addWidget(self.btn_pengaturan)
        header_row.addSpacing(8)

        self.btn_baru = QPushButton("+  Proyek Baru")
        self.btn_baru.setObjectName("btnPrimary")
        self.btn_baru.setCursor(Qt.PointingHandCursor)
        self.btn_baru.setToolTip(
            "Import file IFC dan buat proyek baru (Ctrl+N). File .ifc juga bisa diseret ke jendela ini."
        )
        self.btn_baru.clicked.connect(self.proyek_baru)
        header_row.addWidget(self.btn_baru)
        root.addLayout(header_row)

        # --- Kartu ringkasan ---
        self.baris_stat = QWidget()
        stat_layout = QHBoxLayout(self.baris_stat)
        stat_layout.setContentsMargins(0, 0, 0, 0)
        stat_layout.setSpacing(14)
        self.stat_total = KartuStat("Total Proyek")
        self.stat_ifc = KartuStat("Proyek dengan File IFC")
        self.stat_terakhir = KartuStat("Terakhir Diubah")
        for kartu in (self.stat_total, self.stat_ifc, self.stat_terakhir):
            stat_layout.addWidget(kartu, stretch=1)
        root.addWidget(self.baris_stat)

        # --- Baris pencarian + jumlah proyek ---
        cari_row = QHBoxLayout()
        cari_row.setSpacing(12)
        self.kolom_cari = QLineEdit()
        self.kolom_cari.setObjectName("kolomCari")
        self.kolom_cari.setPlaceholderText("Cari nama proyek...   (Ctrl+F)")
        self.kolom_cari.setClearButtonEnabled(True)
        self.kolom_cari.textChanged.connect(self._terapkan_filter)
        cari_row.addWidget(self.kolom_cari, stretch=1)
        self.label_jumlah = QLabel("")
        self.label_jumlah.setObjectName("jumlahProyek")
        cari_row.addWidget(self.label_jumlah)
        root.addLayout(cari_row)

        # --- Stacked: tabel / belum ada proyek / hasil pencarian kosong ---
        self.stack = QStackedWidget()
        root.addWidget(self.stack, stretch=1)
        self.stack.addWidget(self._buat_halaman_tabel())
        self.stack.addWidget(self._buat_halaman_kosong())
        self.stack.addWidget(self._buat_halaman_tidak_ada_hasil())

        # --- Baris bawah: petunjuk + tombol aksi ---
        aksi_row = QHBoxLayout()
        aksi_row.setSpacing(10)
        self.label_petunjuk = QLabel("Klik dua kali pada proyek untuk membukanya")
        self.label_petunjuk.setObjectName("petunjuk")
        aksi_row.addWidget(self.label_petunjuk)
        aksi_row.addStretch()

        self.btn_buka = QPushButton("Buka Proyek")
        self.btn_buka.setObjectName("btnSecondary")
        self.btn_buka.setCursor(Qt.PointingHandCursor)
        self.btn_buka.clicked.connect(self.buka_proyek)
        self.btn_hapus = QPushButton("Hapus Proyek")
        self.btn_hapus.setObjectName("btnDanger")
        self.btn_hapus.setCursor(Qt.PointingHandCursor)
        self.btn_hapus.clicked.connect(self.hapus_proyek)
        aksi_row.addWidget(self.btn_hapus)
        aksi_row.addWidget(self.btn_buka)
        root.addLayout(aksi_row)

        # --- Pintasan keyboard ---
        QShortcut(QKeySequence("Ctrl+N"), self, activated=self.proyek_baru)
        QShortcut(QKeySequence("Ctrl+F"), self, activated=self._fokus_cari)
        QShortcut(QKeySequence("Ctrl+,"), self, activated=self.buka_pengaturan)

        self.setAcceptDrops(True)  # drag-and-drop file IFC (UC-01)
        self._perbarui_tombol_aksi()
        self.muat_daftar_proyek()

    # ---------- Drag & drop file IFC ----------

    @staticmethod
    def _path_ifc_dari(event):
        urls = event.mimeData().urls() if event.mimeData().hasUrls() else []
        if len(urls) == 1 and urls[0].isLocalFile():
            return urls[0].toLocalFile()
        return None

    def dragEnterEvent(self, event):
        if self._path_ifc_dari(event):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):
        path = self._path_ifc_dari(event)
        if path:
            event.acceptProposedAction()
            self.proyek_baru(path)

    # ---------- Konstruksi UI ----------

    def _buat_halaman_tabel(self) -> QWidget:
        wrap = QWidget()
        layout = QVBoxLayout(wrap)
        layout.setContentsMargins(0, 0, 0, 0)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(
            ["NAMA PROYEK", "FILE IFC", "DIBUAT", "DIUBAH"]
        )
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        self.table.setFocusPolicy(Qt.StrongFocus)
        self.table.setTextElideMode(Qt.ElideMiddle)
        self.table.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(50)

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        header.setHighlightSections(False)
        header.setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        header.setSortIndicator(
            3, Qt.DescendingOrder
        )  # terbaru diubah tampil paling atas

        self.table.doubleClicked.connect(lambda _idx: self.buka_proyek())
        self.table.itemSelectionChanged.connect(self._perbarui_tombol_aksi)

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

        judul = QLabel("Belum ada proyek")
        judul.setObjectName("kosongJudul")
        judul.setAlignment(Qt.AlignCenter)

        deskripsi = QLabel(
            "Import file IFC untuk mulai membuat estimasi RAB pertama kamu."
        )
        deskripsi.setObjectName("kosongDeskripsi")
        deskripsi.setAlignment(Qt.AlignCenter)

        btn_cta = QPushButton("+  Buat Proyek Pertama")
        btn_cta.setObjectName("btnCTA")
        btn_cta.setCursor(Qt.PointingHandCursor)
        btn_cta.clicked.connect(self.proyek_baru)
        btn_cta.setFixedWidth(230)

        layout.addWidget(judul)
        layout.addWidget(deskripsi)
        layout.addSpacing(8)
        layout.addWidget(btn_cta, alignment=Qt.AlignCenter)
        return wrap

    def _buat_halaman_tidak_ada_hasil(self) -> QWidget:
        wrap = QFrame()
        wrap.setObjectName("kartuKosong")
        layout = QVBoxLayout(wrap)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(8)

        judul = QLabel("Proyek tidak ditemukan")
        judul.setObjectName("kosongJudul")
        judul.setAlignment(Qt.AlignCenter)

        self.label_tidak_ada = QLabel("")
        self.label_tidak_ada.setObjectName("kosongDeskripsi")
        self.label_tidak_ada.setAlignment(Qt.AlignCenter)

        layout.addWidget(judul)
        layout.addWidget(self.label_tidak_ada)
        return wrap

    # ---------- Data & filter ----------

    def muat_daftar_proyek(self):
        self._semua_proyek = get_all_proyek()
        ada_proyek = len(self._semua_proyek) > 0
        self.kolom_cari.setVisible(ada_proyek)
        self.label_jumlah.setVisible(ada_proyek)
        self.baris_stat.setVisible(ada_proyek)
        self._perbarui_ringkasan()
        self._terapkan_filter()

    def _perbarui_ringkasan(self):
        total = len(self._semua_proyek)
        dengan_ifc = sum(1 for p in self._semua_proyek if p["path_file_ifc"])
        self.stat_total.set_data(str(total), "proyek tersimpan")
        self.stat_ifc.set_data(str(dengan_ifc), f"dari {total} proyek")

        # Proyek yang paling baru diubah (tanggal berupa teks, dibandingkan apa adanya)
        berdiubah = [p for p in self._semua_proyek if p["tanggal_diubah"]]
        if berdiubah:
            terbaru = max(berdiubah, key=lambda p: str(p["tanggal_diubah"]))
            self.stat_terakhir.set_data(
                str(terbaru["tanggal_diubah"]), terbaru["nama_proyek"]
            )
        else:
            self.stat_terakhir.set_data("-", "")

    def _terapkan_filter(self):
        if not self._semua_proyek:
            self.table.setRowCount(0)
            self.stack.setCurrentIndex(self.HALAMAN_KOSONG)
            self._perbarui_tombol_aksi()
            return

        kata_kunci = self.kolom_cari.text().strip().lower()
        hasil = (
            [p for p in self._semua_proyek if kata_kunci in p["nama_proyek"].lower()]
            if kata_kunci
            else self._semua_proyek
        )

        # Matikan sorting saat mengisi tabel supaya urutan baris tidak bergeser di tengah proses.
        self.table.setSortingEnabled(False)
        self.table.setRowCount(0)
        warna_redup = QColor("#8fa3b8")
        for row_idx, p in enumerate(hasil):
            self.table.insertRow(row_idx)

            item_nama = QTableWidgetItem(p["nama_proyek"])
            font_nama = item_nama.font()
            font_nama.setWeight(QFont.DemiBold)
            item_nama.setFont(font_nama)
            item_nama.setData(Qt.UserRole, p["id"])

            path_ifc = p["path_file_ifc"]
            item_ifc = QTableWidgetItem(Path(path_ifc).name if path_ifc else "-")
            item_ifc.setForeground(warna_redup)
            item_ifc.setToolTip(path_ifc or "Belum ada file IFC")

            item_dibuat = QTableWidgetItem(p["tanggal_dibuat"] or "-")
            item_dibuat.setForeground(warna_redup)
            item_diubah = QTableWidgetItem(p["tanggal_diubah"] or "-")
            item_diubah.setForeground(warna_redup)

            self.table.setItem(row_idx, 0, item_nama)
            self.table.setItem(row_idx, 1, item_ifc)
            self.table.setItem(row_idx, 2, item_dibuat)
            self.table.setItem(row_idx, 3, item_diubah)
        self.table.setSortingEnabled(True)

        total = len(self._semua_proyek)
        if kata_kunci:
            self.label_jumlah.setText(f"{len(hasil)} dari {total} proyek")
        else:
            self.label_jumlah.setText(f"{total} proyek tersimpan")

        if hasil:
            self.stack.setCurrentIndex(self.HALAMAN_TABEL)
        else:
            self.label_tidak_ada.setText(
                f'Tidak ada proyek dengan nama "{self.kolom_cari.text().strip()}".'
            )
            self.stack.setCurrentIndex(self.HALAMAN_TIDAK_ADA_HASIL)
        self._perbarui_tombol_aksi()

    def _fokus_cari(self):
        if self.kolom_cari.isVisible():
            self.kolom_cari.setFocus()
            self.kolom_cari.selectAll()

    def _selected_proyek_id(self):
        row = self.table.currentRow()
        if row < 0 or not self.table.item(row, 0) or not self.table.selectedItems():
            return None
        return self.table.item(row, 0).data(Qt.UserRole)

    def _perbarui_tombol_aksi(self):
        ada_pilihan = self._selected_proyek_id() is not None
        self.btn_buka.setEnabled(ada_pilihan)
        self.btn_hapus.setEnabled(ada_pilihan)

    # ---------- Aksi ----------

    def buka_pengaturan(self):
        """Buka dialog Pengaturan (material, merk, dan harga)."""
        PengaturanDialog(self).exec()

    def proyek_baru(self, file_path: str | None = None):
        """KF-1 (UC-01): pilih file IFC -> validasi -> ringkasan & konfirmasi -> parsing + rule engine
        (KF-2..KF-4) -> buka halaman hasil estimasi."""
        if not file_path:
            file_path, _ = QFileDialog.getOpenFileName(
                self, "Pilih File IFC", "", "IFC Files (*.ifc);;Semua file (*)"
            )
        if not file_path:
            return

        # 1. Validasi file (ekstensi, header, integritas, versi IFC2x3/IFC4)
        try:
            info = jalankan_di_latar(
                self, "Memvalidasi file IFC...", buka_dan_validasi, file_path, terisolasi=True
            )
        except FileIFCTidakValid as e:
            QMessageBox.critical(self, "File Tidak Valid", str(e))
            return
        except Exception as e:
            QMessageBox.critical(self, "File Tidak Valid", f"File IFC tidak dapat dibuka.\n\nDetail: {e}")
            return

        # 2. Ringkasan file + konfirmasi
        dialog = RingkasanImportDialog(info, self)
        if not dialog.exec():
            return
        nama = dialog.nama_proyek() or Path(file_path).stem

        # 3. Simpan proyek, lalu parsing + klasifikasi + rule engine + QTO di thread terpisah
        proyek_id = create_proyek(nama_proyek=nama, path_file_ifc=info.path)
        try:
            r = jalankan_di_latar(
                self,
                "Membaca elemen & menghitung kuantitas...",
                jalankan_estimasi,
                proyek_id,
                model=info.model,
                pakai_progress=True,
            )
        except Exception as e:
            self.muat_daftar_proyek()
            QMessageBox.critical(
                self,
                f"Proyek '{nama}'",
                f"Proyek dibuat, tetapi parsing gagal:\n{e}\n\n"
                "Proyek tetap tersimpan; estimasi dapat dijalankan ulang dari halaman proyek.",
            )
            return

        self.muat_daftar_proyek()
        tampilkan_hasil_proses(self, f"Proyek '{nama}'", r)
        self._buka_window_estimasi(proyek_id, nama)  # UC-01 langkah 12

    def buka_proyek(self):
        """KF-9: Buka proyek yang dipilih."""
        proyek_id = self._selected_proyek_id()
        if proyek_id is None:
            QMessageBox.warning(
                self, "Belum Ada Pilihan", "Pilih dulu satu proyek dari tabel."
            )
            return
        proyek = next((p for p in self._semua_proyek if p["id"] == proyek_id), None)
        nama_proyek = proyek["nama_proyek"] if proyek else "Proyek"
        self._buka_window_estimasi(proyek_id, nama_proyek)

    def _buka_window_estimasi(self, proyek_id: int, nama_proyek: str):
        self._window_estimasi = EstimasiWindow(
            proyek_id, nama_proyek, on_kembali=self._kembali_dari_estimasi
        )
        self._window_estimasi.show()
        self.hide()

    def _kembali_dari_estimasi(self):
        if self._window_estimasi is not None:
            self._window_estimasi.close()
        self.muat_daftar_proyek()
        self.show()

    def hapus_proyek(self):
        proyek_id = self._selected_proyek_id()
        if proyek_id is None:
            QMessageBox.warning(
                self, "Belum Ada Pilihan", "Pilih dulu satu proyek dari tabel."
            )
            return
        proyek = next((p for p in self._semua_proyek if p["id"] == proyek_id), None)
        nama_proyek = proyek["nama_proyek"] if proyek else "proyek ini"

        kotak = QMessageBox(self)
        kotak.setIcon(QMessageBox.Warning)
        kotak.setWindowTitle("Hapus Proyek")
        kotak.setText(f'Hapus proyek "{nama_proyek}"?')
        kotak.setInformativeText(
            "Semua data estimasinya ikut terhapus dan tidak bisa dikembalikan."
        )
        btn_hapus = kotak.addButton("Hapus", QMessageBox.DestructiveRole)
        btn_batal = kotak.addButton("Batal", QMessageBox.RejectRole)
        kotak.setDefaultButton(
            btn_batal
        )  # supaya tidak terhapus tanpa sengaja saat menekan Enter
        kotak.exec()

        if kotak.clickedButton() is btn_hapus:
            delete_proyek(proyek_id)
            self.muat_daftar_proyek()


def main():
    app = QApplication(sys.argv)
    window = DashboardWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    multiprocessing.freeze_support()  # validasi IFC memakai proses anak (juga saat dibundel PyInstaller)
    main()
