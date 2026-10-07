"""
Tema tampilan CostStruct: satu sumber warna, satu stylesheet global, dan widget kecil yang
dipakai bersama oleh semua halaman (kartu angka, kondisi kosong, banner, toast, ikon).

Stylesheet dipasang sekali di QApplication lewat `terapkan(app)`, sehingga setiap halaman dan
dialog cukup memberi `objectName` / properti pada widget-nya.
"""

import tempfile
from pathlib import Path

from PySide6.QtCore import QEasingCurve, QLocale, QPointF, QPropertyAnimation, QRectF, Qt, QTimer
from PySide6.QtGui import QBrush, QColor, QIcon, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap, QPolygonF
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

# ---------------------------------------------------------------- token warna

W = {
    "latar": "#111a24",
    "sidebar": "#0d151d",
    "permukaan": "#18232f",
    "permukaan_2": "#1d2a38",
    "permukaan_3": "#233344",
    "garis": "#26384a",
    "garis_kuat": "#33495f",
    "teks": "#e4ebf2",
    "teks_kuat": "#ffffff",
    "teks_redup": "#8094a9",
    "teks_samar": "#5d7287",
    "aksen": "#4f9df7",
    "aksen_hover": "#6bacf9",
    "aksen_teks": "#0b1824",
    "aksen_lembut": "#1e3a5c",
    "sukses": "#6fcf97",
    "sukses_lembut": "#173a2a",
    "peringatan": "#f5b84f",
    "peringatan_lembut": "#3a2e17",
    "bahaya": "#f48b8b",
    "bahaya_lembut": "#3a2229",
}

# warna per kategori pekerjaan / jenis sumber daya (dipakai konsisten di semua tabel)
WARNA_KATEGORI = ["#6bb2ff", "#7fd1b9", "#f5b84f", "#c39bf5", "#f48b8b", "#9bd16b", "#f0a6ca", "#8fd3f4"]
WARNA_TIPE = {"bahan": "#6bb2ff", "upah": "#7fd1b9", "alat": "#f5b84f"}

FONT = '"Segoe UI", "Inter", "Noto Sans", sans-serif'


def format_rupiah(nilai: float, desimal: int = 0) -> str:
    return "Rp " + format_angka(nilai, desimal)


def format_angka(nilai: float, desimal: int = 2) -> str:
    """Format Indonesia: 1.234.567,89"""
    return f"{nilai:,.{desimal}f}".replace(",", "X").replace(".", ",").replace("X", ".")


# ---------------------------------------------------------------- gambar kecil untuk QSS


def _simpan_pixmap(nama: str, gambar) -> str:
    try:
        path = Path(tempfile.gettempdir()) / f"coststruct_{nama}.png"
        pix = QPixmap(24, 24)
        pix.fill(Qt.transparent)
        p = QPainter(pix)
        p.setRenderHint(QPainter.Antialiasing)
        gambar(p)
        p.end()
        return f"url({path.as_posix()})" if pix.save(str(path), "PNG") else "none"
    except Exception:
        return "none"


def _panah(p):
    p.setPen(QPen(QColor(W["teks_redup"]), 2.4, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    p.drawLine(6, 9, 12, 15)
    p.drawLine(12, 15, 18, 9)


def _centang(p):
    p.setPen(QPen(QColor(W["aksen_teks"]), 3.0, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    p.drawLine(6, 12, 10, 16)
    p.drawLine(10, 16, 18, 7)


# ---------------------------------------------------------------- stylesheet


def stylesheet() -> str:
    panah = _simpan_pixmap("panah", _panah)
    centang = _simpan_pixmap("centang", _centang)
    c = W
    return f"""
* {{ font-family: {FONT}; font-size: 13px; color: {c['teks']}; }}
QMainWindow, QDialog, QWidget#halaman {{ background-color: {c['latar']}; }}
QLabel {{ background: transparent; }}
QToolTip {{ background-color: {c['permukaan_3']}; color: {c['teks']}; border: 1px solid {c['garis_kuat']}; padding: 6px 8px; }}

/* ---------- sidebar ---------- */
QFrame#sidebar {{ background-color: {c['sidebar']}; border-right: 1px solid {c['garis']}; }}
QLabel#namaAplikasi {{ font-size: 16px; font-weight: 700; color: {c['teks_kuat']}; }}
QLabel#taglineAplikasi {{ font-size: 11px; color: {c['teks_samar']}; }}
QLabel#infoSidebar {{ font-size: 11px; color: {c['teks_samar']}; }}
QPushButton#navItem {{
    text-align: left; padding: 10px 14px; border: none; border-radius: 8px;
    background: transparent; color: {c['teks_redup']}; font-weight: 600;
}}
QPushButton#navItem:hover {{ background-color: {c['permukaan']}; color: {c['teks']}; }}
QPushButton#navItem:checked {{ background-color: {c['aksen_lembut']}; color: {c['teks_kuat']}; }}

/* ---------- tipografi halaman ---------- */
QLabel#judulHalaman {{ font-size: 22px; font-weight: 700; color: {c['teks_kuat']}; }}
QLabel#subjudul {{ font-size: 12px; color: {c['teks_redup']}; }}
QLabel#remah {{ font-size: 12px; color: {c['teks_redup']}; }}
QLabel#bagian {{ font-size: 11px; font-weight: 700; color: {c['teks_redup']}; letter-spacing: 1px; }}
QLabel#infoKecil, QLabel#petunjuk {{ font-size: 11px; color: {c['teks_samar']}; }}
QLabel#formLabel {{ color: {c['teks_redup']}; }}
QLabel#namaFile {{ color: {c['teks_redup']}; font-size: 12px; }}
QLabel#galat {{ color: {c['bahaya']}; font-size: 12px; }}
QLabel#peringatan {{ color: {c['peringatan']}; font-size: 12px; }}
QLabel#judulPanel {{ font-size: 15px; font-weight: 700; color: {c['teks_kuat']}; }}
QLabel#nilaiBesar {{ font-size: 20px; font-weight: 700; color: {c['teks_kuat']}; }}
QLabel#rumus {{
    font-family: "Cascadia Mono", "Consolas", "DejaVu Sans Mono", monospace; font-size: 12px;
    background-color: {c['latar']}; border: 1px solid {c['garis']}; border-radius: 6px; padding: 8px 10px;
}}
QLabel#chip {{ border-radius: 9px; padding: 2px 9px; font-size: 11px; font-weight: 600; }}
QLabel#chip[jenis="netral"] {{ background-color: {c['permukaan_3']}; color: {c['teks_redup']}; }}
QLabel#chip[jenis="info"] {{ background-color: {c['aksen_lembut']}; color: {c['aksen_hover']}; }}
QLabel#chip[jenis="sukses"] {{ background-color: {c['sukses_lembut']}; color: {c['sukses']}; }}
QLabel#chip[jenis="peringatan"] {{ background-color: {c['peringatan_lembut']}; color: {c['peringatan']}; }}
QLabel#chip[jenis="bahaya"] {{ background-color: {c['bahaya_lembut']}; color: {c['bahaya']}; }}

/* ---------- kartu & panel ---------- */
QFrame#kartu, QFrame#panel {{ background-color: {c['permukaan']}; border: 1px solid {c['garis']}; border-radius: 12px; }}
QFrame#kartuStat {{ background-color: {c['permukaan']}; border: 1px solid {c['garis']}; border-radius: 12px; }}
QFrame#kartuStatUtama {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #24518a, stop:1 #1b3a63);
    border: 1px solid #3a6ba8; border-radius: 12px;
}}
QLabel#statJudul {{ color: {c['teks_redup']}; font-size: 11px; font-weight: 700; letter-spacing: 1px; }}
QLabel#statNilai {{ color: {c['teks_kuat']}; font-size: 21px; font-weight: 700; }}
QLabel#statKet {{ color: {c['teks_samar']}; font-size: 11px; }}
QFrame#kartuStatUtama QLabel#statJudul {{ color: #b8d4f5; }}
QFrame#kartuStatUtama QLabel#statKet {{ color: #9fc0e8; }}
QFrame#kartuKosong {{ background-color: {c['permukaan']}; border: 1px dashed {c['garis_kuat']}; border-radius: 14px; }}
QLabel#kosongJudul {{ font-size: 17px; font-weight: 700; color: {c['teks_kuat']}; }}
QLabel#kosongDeskripsi {{ color: {c['teks_redup']}; }}
QFrame#garis {{ background-color: {c['garis']}; max-height: 1px; min-height: 1px; border: none; }}

/* ---------- banner ---------- */
QFrame#banner {{ border-radius: 10px; }}
QFrame#banner[jenis="peringatan"] {{ background-color: {c['peringatan_lembut']}; border: 1px solid #5a4620; }}
QFrame#banner[jenis="info"] {{ background-color: {c['aksen_lembut']}; border: 1px solid #2c5585; }}
QFrame#banner[jenis="peringatan"] QLabel {{ color: {c['peringatan']}; }}
QFrame#banner[jenis="info"] QLabel {{ color: #b8d4f5; }}

/* ---------- toast ---------- */
QFrame#toast {{ background-color: {c['permukaan_3']}; border: 1px solid {c['garis_kuat']}; border-radius: 10px; }}
QFrame#toast QLabel {{ color: {c['teks_kuat']}; font-weight: 600; }}

/* ---------- tombol ---------- */
QPushButton {{ border-radius: 8px; padding: 9px 18px; font-weight: 600; border: none; }}
QPushButton#btnPrimary {{ background-color: {c['aksen']}; color: {c['aksen_teks']}; }}
QPushButton#btnPrimary:hover {{ background-color: {c['aksen_hover']}; }}
QPushButton#btnPrimary:pressed {{ background-color: #3f8ce6; }}
QPushButton#btnPrimary:disabled {{ background-color: {c['permukaan_3']}; color: {c['teks_samar']}; }}
QPushButton#btnSecondary {{ background-color: {c['permukaan_3']}; color: {c['teks']}; border: 1px solid {c['garis_kuat']}; }}
QPushButton#btnSecondary:hover {{ background-color: #2b3f54; }}
QPushButton#btnSecondary:disabled {{ color: {c['teks_samar']}; background-color: {c['permukaan']}; border: 1px solid {c['garis']}; }}
QPushButton#btnGhost {{ background: transparent; color: {c['teks_redup']}; padding: 8px 12px; }}
QPushButton#btnGhost:hover {{ background-color: {c['permukaan']}; color: {c['teks']}; }}
QPushButton#btnGhost:disabled {{ color: {c['teks_samar']}; }}
QPushButton#btnDanger {{ background: transparent; color: {c['bahaya']}; border: 1px solid #54343d; }}
QPushButton#btnDanger:hover {{ background-color: {c['bahaya_lembut']}; }}
QPushButton#btnDanger:disabled {{ color: {c['teks_samar']}; border: 1px solid {c['garis']}; }}
QPushButton#btnBanner {{ background: transparent; border: 1px solid currentColor; padding: 6px 14px; }}
QFrame#banner[jenis="peringatan"] QPushButton#btnBanner {{ color: {c['peringatan']}; border: 1px solid {c['peringatan']}; }}
QFrame#banner[jenis="info"] QPushButton#btnBanner {{ color: #b8d4f5; border: 1px solid #6c9ad0; }}
QPushButton#segmen {{
    background: transparent; color: {c['teks_redup']}; border: 1px solid {c['garis_kuat']};
    border-radius: 0; padding: 8px 16px;
}}
QPushButton#segmen[posisi="kiri"] {{ border-top-left-radius: 8px; border-bottom-left-radius: 8px; }}
QPushButton#segmen[posisi="kanan"] {{ border-top-right-radius: 8px; border-bottom-right-radius: 8px; border-left: none; }}
QPushButton#segmen:hover {{ color: {c['teks']}; }}
QPushButton#segmen:checked {{ background-color: {c['aksen_lembut']}; color: {c['teks_kuat']}; border-color: #2c5585; }}
QPushButton:focus {{ outline: none; }}

/* ---------- input ---------- */
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox, QPlainTextEdit {{
    background-color: {c['permukaan']}; border: 1px solid {c['garis_kuat']}; border-radius: 8px;
    padding: 7px 12px; color: {c['teks']}; selection-background-color: #2a4a6e;
}}
QLineEdit:hover, QSpinBox:hover, QDoubleSpinBox:hover, QComboBox:hover {{ border: 1px solid #4a6a8c; }}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {{ border: 1px solid {c['aksen']}; background-color: #1b2d40; }}
QLineEdit:disabled, QDoubleSpinBox:disabled {{ color: {c['teks_samar']}; }}
QComboBox {{ padding-right: 30px; }}
QComboBox::drop-down {{ border: none; width: 28px; }}
QComboBox::down-arrow {{ image: {panah}; width: 14px; height: 14px; }}
QComboBox QAbstractItemView {{
    background-color: {c['permukaan_2']}; border: 1px solid {c['garis_kuat']}; color: {c['teks']};
    selection-background-color: #25456a; outline: none; padding: 4px;
}}
QCheckBox {{ spacing: 9px; }}
QCheckBox::indicator {{ width: 18px; height: 18px; border-radius: 5px; border: 1px solid {c['garis_kuat']}; background-color: {c['permukaan']}; }}
QCheckBox::indicator:hover {{ border: 1px solid {c['aksen']}; }}
QCheckBox::indicator:checked {{ background-color: {c['aksen']}; border: 1px solid {c['aksen']}; image: {centang}; }}

/* ---------- tabel ---------- */
QTableWidget, QListWidget {{
    background-color: {c['permukaan']}; border: 1px solid {c['garis']}; border-radius: 12px;
    gridline-color: transparent; outline: none; alternate-background-color: {c['permukaan_2']};
    selection-background-color: #25456a; selection-color: {c['teks_kuat']};
}}
QTableWidget::item {{ padding: 6px 10px; border: none; }}
QTableWidget::item:hover {{ background-color: {c['permukaan_3']}; }}
QTableWidget::item:selected {{ background-color: #25456a; }}
QHeaderView {{ background-color: transparent; }}
QHeaderView::section {{
    background-color: {c['permukaan']}; color: {c['teks_redup']}; padding: 10px; border: none;
    border-bottom: 1px solid {c['garis']}; font-weight: 700; font-size: 11px;
}}
QTableWidget QDoubleSpinBox {{ background-color: {c['permukaan_3']}; border-radius: 6px; padding: 3px 8px; margin: 5px 6px; }}
QTableWidget QDoubleSpinBox:focus {{ background-color: #1e3a5a; }}

/* ---------- scrollbar ---------- */
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 4px 2px; }}
QScrollBar::handle:vertical {{ background: #34495e; border-radius: 4px; min-height: 36px; }}
QScrollBar::handle:vertical:hover {{ background: #4a6580; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 2px 4px; }}
QScrollBar::handle:horizontal {{ background: #34495e; border-radius: 4px; min-width: 36px; }}
QScrollBar::handle:horizontal:hover {{ background: #4a6580; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}
QScrollArea {{ background: transparent; border: none; }}
QSplitter::handle {{ background: transparent; }}
QWidget#isiPanel {{ background: transparent; }}

/* ---------- dialog ---------- */
QMessageBox {{ background-color: {c['permukaan']}; }}
QMessageBox QPushButton {{ background-color: {c['permukaan_3']}; border: 1px solid {c['garis_kuat']}; min-width: 90px; padding: 8px 16px; }}
QMessageBox QPushButton:hover {{ background-color: #2b3f54; }}
QProgressDialog {{ background-color: {c['permukaan']}; }}
QProgressBar {{ background-color: {c['latar']}; border: 1px solid {c['garis_kuat']}; border-radius: 6px; height: 14px; text-align: center; }}
QProgressBar::chunk {{ background-color: {c['aksen']}; border-radius: 5px; }}
"""


def terapkan(app) -> None:
    # angka di kotak input mengikuti format Indonesia: 1.234,56
    QLocale.setDefault(QLocale(QLocale.Indonesian, QLocale.Indonesia))
    app.setStyleSheet(stylesheet())


# ---------------------------------------------------------------- ikon vektor


def _gambar_ikon(nama: str, p: QPainter, warna: QColor):
    pena = QPen(warna, 1.8, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
    p.setPen(pena)
    p.setBrush(Qt.NoBrush)
    if nama == "proyek":  # tumpukan lantai bangunan
        p.drawPolygon(QPolygonF([QPointF(10, 3), QPointF(17, 6.5), QPointF(10, 10), QPointF(3, 6.5)]))
        for y in (10, 13.5):
            p.drawPolyline(QPolygonF([QPointF(3, y), QPointF(10, y + 3.5), QPointF(17, y)]))
    elif nama == "harga":  # label harga
        path = QPainterPath()
        path.moveTo(3, 4)
        path.lineTo(10, 4)
        path.lineTo(17, 11)
        path.lineTo(11, 17)
        path.lineTo(4, 10)
        path.closeSubpath()
        p.drawPath(path)
        p.setBrush(warna)
        p.drawEllipse(QRectF(6, 6.5, 2.5, 2.5))
    elif nama == "kembali":
        p.drawLine(15, 10, 5, 10)
        p.drawLine(5, 10, 9, 6)
        p.drawLine(5, 10, 9, 14)
    elif nama == "tambah":
        p.drawLine(10, 4, 10, 16)
        p.drawLine(4, 10, 16, 10)
    elif nama == "unduh":
        p.drawLine(10, 3, 10, 12)
        p.drawLine(6, 8, 10, 12)
        p.drawLine(14, 8, 10, 12)
        p.drawLine(4, 16, 16, 16)
    elif nama == "ulang":
        p.drawArc(QRectF(4, 4, 12, 12), 30 * 16, 290 * 16)
        p.drawLine(16, 4, 16, 8)
        p.drawLine(16, 8, 12, 8)
    elif nama == "file":
        path = QPainterPath()
        path.moveTo(5, 3)
        path.lineTo(12, 3)
        path.lineTo(15, 6)
        path.lineTo(15, 17)
        path.lineTo(5, 17)
        path.closeSubpath()
        p.drawPath(path)
        p.drawLine(7, 10, 13, 10)
        p.drawLine(7, 13, 13, 13)


def ikon(nama: str, warna: str | None = None) -> QIcon:
    pix = QPixmap(40, 40)
    pix.fill(Qt.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.Antialiasing)
    p.scale(2, 2)
    _gambar_ikon(nama, p, QColor(warna or W["teks_redup"]))
    p.end()
    ik = QIcon()
    ik.addPixmap(pix)
    return ik


# ---------------------------------------------------------------- widget bersama


def tombol(teks: str, peran: str = "secondary", ikon_nama: str | None = None, tooltip: str | None = None) -> QPushButton:
    b = QPushButton(teks)
    b.setObjectName({"primary": "btnPrimary", "secondary": "btnSecondary", "ghost": "btnGhost", "danger": "btnDanger"}[peran])
    b.setCursor(Qt.PointingHandCursor)
    if ikon_nama:
        warna = W["aksen_teks"] if peran == "primary" else (W["bahaya"] if peran == "danger" else W["teks"])
        b.setIcon(ikon(ikon_nama, warna))
    if tooltip:
        b.setToolTip(tooltip)
    return b


def label(teks: str = "", nama: str | None = None, wrap: bool = False) -> QLabel:
    l = QLabel(teks)
    if nama:
        l.setObjectName(nama)
    l.setWordWrap(wrap)
    return l


def chip(teks: str, jenis: str = "netral") -> QLabel:
    l = QLabel(teks)
    l.setObjectName("chip")
    l.setProperty("jenis", jenis)
    return l


def set_chip(l: QLabel, teks: str, jenis: str) -> None:
    l.setText(teks)
    l.setProperty("jenis", jenis)
    l.style().unpolish(l)
    l.style().polish(l)


def garis() -> QFrame:
    g = QFrame()
    g.setObjectName("garis")
    return g


def header_halaman(judul: str, sub: str = "", remah: str | None = None):
    """Kolom judul halaman. Return (layout, label_judul, label_sub)."""
    kol = QVBoxLayout()
    kol.setSpacing(2)
    if remah:
        kol.addWidget(label(remah, "remah"))
    lj = label(judul, "judulHalaman")
    ls = label(sub, "subjudul")
    kol.addWidget(lj)
    kol.addWidget(ls)
    return kol, lj, ls


def kosongkan_layout(lay) -> None:
    """Lepas dan hapus semua isi layout segera (tidak menunggu deleteLater untuk berhenti tampil)."""
    while lay.count():
        it = lay.takeAt(0)
        w = it.widget()
        if w is not None:
            w.hide()
            w.setParent(None)
            w.deleteLater()
        elif it.layout() is not None:
            kosongkan_layout(it.layout())


class KartuStat(QFrame):
    """Kartu angka ringkas: judul kecil, nilai besar, keterangan. `utama=True` untuk angka kunci."""

    def __init__(self, judul: str, utama: bool = False):
        super().__init__()
        self.setObjectName("kartuStatUtama" if utama else "kartuStat")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 14, 18, 14)
        lay.setSpacing(2)
        self._judul = label(judul.upper(), "statJudul")
        self._nilai = label("-", "statNilai")
        self._ket = label("", "statKet")
        for w in (self._judul, self._nilai, self._ket):
            lay.addWidget(w)

    def set_data(self, nilai: str, keterangan: str = ""):
        self._nilai.setText(nilai)
        self._ket.setText(keterangan)

    def set_judul(self, judul: str):
        self._judul.setText(judul.upper())


class IkonKosong(QWidget):
    def __init__(self, simbol: str = "tambah", parent=None):
        super().__init__(parent)
        self._simbol = simbol
        self.setFixedSize(76, 76)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(QPen(QColor(W["garis_kuat"]), 2, Qt.DashLine))
        p.setBrush(QColor(W["permukaan_2"]))
        p.drawRoundedRect(QRectF(3, 3, self.width() - 6, self.height() - 6), 18, 18)
        p.translate(self.width() / 2 - 20, self.height() / 2 - 20)
        p.scale(2, 2)
        _gambar_ikon(self._simbol, p, QColor(W["aksen"]))
        p.end()


class KondisiKosong(QFrame):
    """Kartu kondisi kosong: ikon, judul, deskripsi, dan tombol aksi opsional."""

    def __init__(self, judul: str, deskripsi: str, teks_tombol: str | None = None, aksi=None, simbol="tambah"):
        super().__init__()
        self.setObjectName("kartuKosong")
        lay = QVBoxLayout(self)
        lay.setAlignment(Qt.AlignCenter)
        lay.setSpacing(10)
        lay.addWidget(IkonKosong(simbol), alignment=Qt.AlignCenter)
        lay.addSpacing(4)
        self.judul = label(judul, "kosongJudul")
        self.judul.setAlignment(Qt.AlignCenter)
        self.deskripsi = label(deskripsi, "kosongDeskripsi", wrap=True)
        self.deskripsi.setAlignment(Qt.AlignCenter)
        self.deskripsi.setMaximumWidth(520)
        lay.addWidget(self.judul)
        lay.addWidget(self.deskripsi, alignment=Qt.AlignCenter)
        if teks_tombol:
            b = tombol(teks_tombol, "primary", "tambah")
            if aksi:
                b.clicked.connect(aksi)
            lay.addSpacing(6)
            lay.addWidget(b, alignment=Qt.AlignCenter)
            self.tombol = b


class Banner(QFrame):
    """Pita pemberitahuan di atas konten, dengan satu tombol aksi opsional."""

    def __init__(self, jenis: str = "peringatan"):
        super().__init__()
        self.setObjectName("banner")
        self.setProperty("jenis", jenis)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(14, 8, 8, 8)
        lay.setSpacing(12)
        self.teks = label("", wrap=True)
        lay.addWidget(self.teks, stretch=1)
        self.tombol = QPushButton("")
        self.tombol.setObjectName("btnBanner")
        self.tombol.setCursor(Qt.PointingHandCursor)
        lay.addWidget(self.tombol)
        self._aksi = None
        self.tombol.clicked.connect(lambda: self._aksi and self._aksi())
        self.hide()

    def tampilkan(self, teks: str, teks_tombol: str | None = None, aksi=None):
        self.teks.setText(teks)
        self._aksi = aksi
        self.tombol.setVisible(bool(teks_tombol))
        self.tombol.setText(teks_tombol or "")
        self.show()


class Toast(QFrame):
    """Notifikasi singkat di pojok kanan bawah jendela (mis. 'Harga satuan berhasil diperbarui')."""

    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setObjectName("toast")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(16, 10, 16, 10)
        self._titik = label("●")
        self._teks = label("")
        lay.addWidget(self._titik)
        lay.addWidget(self._teks)
        self._efek = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self._efek)
        self._anim = QPropertyAnimation(self._efek, b"opacity", self)
        self._anim.setDuration(250)
        self._anim.setEasingCurve(QEasingCurve.InOutQuad)
        self._timer = QTimer(self, singleShot=True, timeout=self._sembunyi)
        self.hide()

    def tampilkan(self, teks: str, jenis: str = "sukses"):
        warna = {"sukses": W["sukses"], "peringatan": W["peringatan"], "bahaya": W["bahaya"]}.get(jenis, W["aksen"])
        self._titik.setStyleSheet(f"color: {warna};")
        self._teks.setText(teks)
        self.adjustSize()
        self.posisikan()
        self.raise_()
        self.show()
        self._anim.stop()
        self._anim.setStartValue(0.0)
        self._anim.setEndValue(1.0)
        self._anim.start()
        self._timer.start(2600)

    def posisikan(self):
        """Tengah-bawah area konten (di sebelah kanan sidebar), di atas baris tombol aksi."""
        induk = self.parentWidget()
        kiri = getattr(induk, "LEBAR_SIDEBAR", 0)
        x = kiri + (induk.width() - kiri - self.width()) // 2
        self.move(x, induk.height() - self.height() - 72)

    def _sembunyi(self):
        self._anim.stop()
        self._anim.setStartValue(1.0)
        self._anim.setEndValue(0.0)
        self._anim.finished.connect(self._selesai)
        self._anim.start()

    def _selesai(self):
        self._anim.finished.disconnect(self._selesai)
        self.hide()


def toast(widget: QWidget, teks: str, jenis: str = "sukses") -> None:
    """Tampilkan toast di jendela tempat `widget` berada (bila jendelanya punya toast)."""
    jendela = widget.window()
    t = getattr(jendela, "toast", None)
    if isinstance(t, Toast):
        t.tampilkan(teks, jenis)


class Logo(QWidget):
    """Logo CostStruct: kotak bergradasi dengan tiga batang naik."""

    def __init__(self, ukuran: int = 38, parent=None):
        super().__init__(parent)
        self.setFixedSize(ukuran, ukuran)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        s = self.width()
        area = QRectF(0, 0, s, s)
        grad = QLinearGradient(area.topLeft(), area.bottomRight())
        grad.setColorAt(0.0, QColor("#6bb2ff"))
        grad.setColorAt(1.0, QColor("#2b6cd4"))
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(grad))
        p.drawRoundedRect(area, s * 0.28, s * 0.28)
        lebar, jarak = s * 0.15, s * 0.09
        x0 = (s - (3 * lebar + 2 * jarak)) / 2
        dasar = s * 0.74
        for i, (t, a) in enumerate(zip([0.22, 0.38, 0.54], [170, 215, 255])):
            p.setBrush(QColor(255, 255, 255, a))
            p.drawRoundedRect(QRectF(x0 + i * (lebar + jarak), dasar - s * t, lebar, s * t), 2, 2)
        p.end()


# ---------------------------------------------------------------- tabel


def siapkan_tabel(tabel: QTableWidget, judul_kolom: list, rata_kanan=(), tinggi_baris: int = 42) -> None:
    tabel.setColumnCount(len(judul_kolom))
    tabel.setHorizontalHeaderLabels(judul_kolom)
    for kol in rata_kanan:
        tabel.horizontalHeaderItem(kol).setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
    tabel.horizontalHeader().setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
    tabel.horizontalHeader().setHighlightSections(False)
    tabel.verticalHeader().setVisible(False)
    tabel.verticalHeader().setDefaultSectionSize(tinggi_baris)
    tabel.setSelectionBehavior(QAbstractItemView.SelectRows)
    tabel.setSelectionMode(QAbstractItemView.SingleSelection)
    tabel.setEditTriggers(QAbstractItemView.NoEditTriggers)
    tabel.setAlternatingRowColors(True)
    tabel.setShowGrid(False)
    tabel.setWordWrap(False)
    tabel.setTextElideMode(Qt.ElideRight)
    tabel.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
    tabel.setHorizontalScrollMode(QAbstractItemView.ScrollPerPixel)


def atur_lebar(tabel: QTableWidget, stretch: int, isi_konten=()) -> None:
    h = tabel.horizontalHeader()
    for kol in range(tabel.columnCount()):
        if kol == stretch:
            h.setSectionResizeMode(kol, QHeaderView.Stretch)
        elif kol in isi_konten:
            h.setSectionResizeMode(kol, QHeaderView.ResizeToContents)
        else:
            h.setSectionResizeMode(kol, QHeaderView.Interactive)


def sel(teks, rata=None, warna=None, tebal=False, tooltip=None, data=None) -> QTableWidgetItem:
    it = QTableWidgetItem("" if teks is None else str(teks))
    if rata == "kanan":
        it.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
    elif rata == "tengah":
        it.setTextAlignment(Qt.AlignCenter)
    if warna:
        it.setForeground(QColor(warna))
    if tebal:
        f = it.font()
        f.setBold(True)
        it.setFont(f)
    if tooltip:
        it.setToolTip(tooltip)
    if data is not None:
        it.setData(Qt.UserRole, data)
    return it
