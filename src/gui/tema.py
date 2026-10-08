"""
Tema tampilan CostStruct: satu sumber warna, satu stylesheet global, dan widget kecil yang
dipakai bersama oleh semua halaman (kartu angka, kondisi kosong, banner, toast, ikon).

Stylesheet dipasang sekali di QApplication lewat `terapkan(app)`, sehingga setiap halaman dan
dialog cukup memberi `objectName` / properti pada widget-nya.
"""

import tempfile
from pathlib import Path

from PySide6.QtCore import QEasingCurve, QEvent, QLocale, QObject, QPointF, QPropertyAnimation, QRectF, Qt, QTimer
from PySide6.QtGui import QBrush, QColor, QIcon, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap, QPolygonF
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

# ---------------------------------------------------------------- token warna

# Kuning Mandajaya Rekayasa Konstruksi, diambil dari logo perusahaan (#F9D759).
KUNING_LOGO = "#F9D759"

PALET = {
    # Bawaan: hitam-kuning seperti identitas PT Mandajaya Rekayasa Konstruksi.
    "hitam_kuning": {
        "latar": "#111111",
        "sidebar": "#0a0a0a",
        "permukaan": "#191919",
        "permukaan_2": "#1e1e1e",
        "permukaan_3": "#272727",
        "garis": "#2b2b2b",
        "garis_kuat": "#3b3b3b",
        "garis_hover": "#76652c",
        "teks": "#ece8df",
        "teks_kuat": "#ffffff",
        "teks_redup": "#a8a397",
        "teks_samar": "#716d63",
        "aksen": KUNING_LOGO,
        "aksen_hover": "#fbe384",
        "aksen_tekan": "#e9c440",
        "aksen_teks": "#141414",
        "aksen_lembut": "#2c2611",
        "aksen_garis": "#5f501d",
        "pilih": "#3b3216",
        "seleksi_teks": "#4d421c",
        "fokus_latar": "#1d1a11",
        "sekunder_hover": "#323232",
        "gulir": "#3d3d3d",
        "gulir_hover": "#5c5c5c",
        "sukses": "#7ed492",
        "sukses_lembut": "#15301f",
        "peringatan": "#ffa94d",
        "peringatan_lembut": "#352312",
        "peringatan_garis": "#5c3b18",
        "bahaya": "#ff7d76",
        "bahaya_lembut": "#3a1d1d",
        "bahaya_garis": "#5a2c2c",
        "info_teks": "#f5df8f",
        "info_tombol": "#c9ab45",
        "utama_awal": KUNING_LOGO,
        "utama_akhir": "#e2b62f",
        "utama_garis": "#f3cf4d",
        "utama_judul": "#4a3c0f",
        "utama_ket": "#5a4a17",
        "utama_nilai": "#141414",
        "logo_awal": KUNING_LOGO,
        "logo_akhir": "#e2b62f",
        "logo_batang": "#141414",
        "sidebar_aktif": "#2c2611",
    },
    # Terang dengan sidebar hitam dan tombol kuning; teks aksen memakai emas tua agar terbaca di latar putih.
    "terang_emas": {
        "latar": "#f6f5f0",
        "sidebar": "#141414",
        "permukaan": "#ffffff",
        "permukaan_2": "#faf9f5",
        "permukaan_3": "#f0eee6",
        "garis": "#e6e2d6",
        "garis_kuat": "#d6d0bf",
        "garis_hover": "#b59a3c",
        "teks": "#1f1d18",
        "teks_kuat": "#0c0b08",
        "teks_redup": "#615c50",
        "teks_samar": "#8f897b",
        "aksen": "#9a7200",
        "aksen_hover": "#b58600",
        "aksen_tekan": "#7f5e00",
        "aksen_teks": "#ffffff",
        "aksen_lembut": "#fbf1cf",
        "aksen_garis": "#ecd27a",
        "pilih": "#fbeaa9",
        "seleksi_teks": "#f6dc7c",
        "fokus_latar": "#ffffff",
        "sekunder_hover": "#e9e5da",
        "gulir": "#cfc9b8",
        "gulir_hover": "#b3ac98",
        "sukses": "#157a43",
        "sukses_lembut": "#e2f3e8",
        "peringatan": "#b45309",
        "peringatan_lembut": "#fdf0e1",
        "peringatan_garis": "#f0cfa6",
        "bahaya": "#c0392b",
        "bahaya_lembut": "#fde8e6",
        "bahaya_garis": "#f0c2bd",
        "info_teks": "#6f5300",
        "info_tombol": "#9a7200",
        "utama_awal": KUNING_LOGO,
        "utama_akhir": "#edc23d",
        "utama_garis": "#e3bd3b",
        "utama_judul": "#4a3c0f",
        "utama_ket": "#5a4a17",
        "utama_nilai": "#141414",
        "tombol_utama": KUNING_LOGO,
        "tombol_utama_hover": "#fbe384",
        "tombol_utama_tekan": "#e9c440",
        "tombol_utama_teks": "#141414",
        "logo_awal": KUNING_LOGO,
        "logo_akhir": "#e2b62f",
        "logo_batang": "#141414",
        "sidebar_teks": "#b9b4a8",
        "sidebar_teks_aktif": "#ffffff",
        "sidebar_hover": "#232323",
        "sidebar_aktif": "#2c2611",
        "sidebar_garis": "#232323",
        "sidebar_judul": "#ffffff",
        "sidebar_samar": "#7d786c",
    },
    "gelap": {
        "latar": "#111a24",
        "sidebar": "#0d151d",
        "permukaan": "#18232f",
        "permukaan_2": "#1d2a38",
        "permukaan_3": "#233344",
        "garis": "#26384a",
        "garis_kuat": "#33495f",
        "garis_hover": "#4a6a8c",
        "teks": "#e4ebf2",
        "teks_kuat": "#ffffff",
        "teks_redup": "#8094a9",
        "teks_samar": "#5d7287",
        "aksen": "#4f9df7",
        "aksen_hover": "#6bacf9",
        "aksen_tekan": "#3f8ce6",
        "aksen_teks": "#0b1824",
        "aksen_lembut": "#1e3a5c",
        "aksen_garis": "#2c5585",
        "pilih": "#25456a",
        "seleksi_teks": "#2a4a6e",
        "fokus_latar": "#1b2d40",
        "sekunder_hover": "#2b3f54",
        "gulir": "#34495e",
        "gulir_hover": "#4a6580",
        "sukses": "#6fcf97",
        "sukses_lembut": "#173a2a",
        "peringatan": "#f5b84f",
        "peringatan_lembut": "#3a2e17",
        "peringatan_garis": "#5a4620",
        "bahaya": "#f48b8b",
        "bahaya_lembut": "#3a2229",
        "bahaya_garis": "#54343d",
        "info_teks": "#b8d4f5",
        "info_tombol": "#6c9ad0",
        "utama_awal": "#24518a",
        "utama_akhir": "#1b3a63",
        "utama_garis": "#3a6ba8",
        "utama_judul": "#b8d4f5",
        "utama_ket": "#9fc0e8",
    },
    "terang": {
        "latar": "#f3f5f8",
        "sidebar": "#ffffff",
        "permukaan": "#ffffff",
        "permukaan_2": "#f7f9fb",
        "permukaan_3": "#edf1f5",
        "garis": "#e1e6ec",
        "garis_kuat": "#cfd7e0",
        "garis_hover": "#9fb1c4",
        "teks": "#1f2a37",
        "teks_kuat": "#0e1621",
        "teks_redup": "#5b6b7c",
        "teks_samar": "#8a97a6",
        "aksen": "#2f7de1",
        "aksen_hover": "#4a92ec",
        "aksen_tekan": "#2468c0",
        "aksen_teks": "#ffffff",
        "aksen_lembut": "#e4eefc",
        "aksen_garis": "#9cc2f2",
        "pilih": "#d6e6fb",
        "seleksi_teks": "#bcd5f5",
        "fokus_latar": "#ffffff",
        "sekunder_hover": "#e4e9f0",
        "gulir": "#c3ccd6",
        "gulir_hover": "#a5b2c0",
        "sukses": "#16884d",
        "sukses_lembut": "#e1f4e9",
        "peringatan": "#a86a00",
        "peringatan_lembut": "#fdf2dc",
        "peringatan_garis": "#f0d9a8",
        "bahaya": "#cc3b3b",
        "bahaya_lembut": "#fde7e7",
        "bahaya_garis": "#efc2c2",
        "info_teks": "#1f5fae",
        "info_tombol": "#6c9ad0",
        "utama_awal": "#2468c0",
        "utama_akhir": "#1f5fae",
        "utama_garis": "#2a6fc9",
        "utama_judul": "#dbe9fb",
        "utama_ket": "#cfe1f8",
        # tombol utama sedikit lebih gelap dari aksen agar teks putih memenuhi kontras WCAG 4.5:1
        "tombol_utama": "#2468c0",
        "tombol_utama_hover": "#2a72d4",
        "tombol_utama_tekan": "#1f5aa8",
    },
}

# warna per kategori pekerjaan / jenis sumber daya (dipakai konsisten di semua tabel)
_KATEGORI = {
    "gelap": ["#6bb2ff", "#7fd1b9", "#f5b84f", "#c39bf5", "#f48b8b", "#9bd16b", "#f0a6ca", "#8fd3f4"],
    "terang": ["#1f6fd1", "#138a6b", "#b26b00", "#7a4cc2", "#c63d3d", "#4e8a1e", "#b8467f", "#1b84a8"],
}
_TIPE = {
    "gelap": {"bahan": "#6bb2ff", "upah": "#7fd1b9", "alat": "#f5b84f"},
    "terang": {"bahan": "#1f6fd1", "upah": "#138a6b", "alat": "#b26b00"},
}

_KATEGORI["hitam_kuning"] = [KUNING_LOGO, "#7fd1b9", "#ffa94d", "#c39bf5", "#ff8b8b", "#9bd16b", "#f0a6ca", "#8fd3f4"]
_KATEGORI["terang_emas"] = ["#9a7200", "#138a6b", "#c2410c", "#7a4cc2", "#c63d3d", "#4e8a1e", "#b8467f", "#1b84a8"]
_TIPE["hitam_kuning"] = {"bahan": KUNING_LOGO, "upah": "#7fd1b9", "alat": "#ffa94d"}
_TIPE["terang_emas"] = {"bahan": "#9a7200", "upah": "#138a6b", "alat": "#c2410c"}

# Nama tampilan & keterangan tema untuk halaman Pengaturan (urutan = urutan kartu).
NAMA_TEMA = {
    "hitam_kuning": ("Hitam Kuning", "Identitas Mandajaya; nyaman untuk kerja lama"),
    "terang_emas": ("Terang Emas", "Latar terang, sidebar hitam, tombol kuning"),
    "gelap": ("Biru Malam", "Tema gelap biru versi sebelumnya"),
    "terang": ("Terang Biru", "Cocok untuk ruangan terang / presentasi"),
}
TEMA_BAWAAN = "hitam_kuning"


def _lengkapi(nama: str, p: dict) -> None:
    """Token yang tidak ditulis eksplisit mengikuti token dasar palet."""
    bawaan = {
        "tombol_utama": p["aksen"], "tombol_utama_hover": p["aksen_hover"], "tombol_utama_tekan": p["aksen_tekan"],
        "tombol_utama_teks": p["aksen_teks"], "utama_nilai": "#ffffff",
        "logo_awal": "#6bb2ff", "logo_akhir": "#2b6cd4", "logo_batang": "#ffffff",
        "sidebar_teks": p["teks_redup"], "sidebar_teks_aktif": p["teks_kuat"], "sidebar_hover": p["permukaan"],
        "sidebar_aktif": p["aksen_lembut"], "sidebar_garis": p["garis"], "sidebar_judul": p["teks_kuat"],
        "sidebar_samar": p["teks_samar"],
    }
    for k, v in bawaan.items():
        p.setdefault(k, v)


for _nama, _p in PALET.items():
    _lengkapi(_nama, _p)

# Token aktif. Diubah di tempat oleh pilih_tema(), sehingga semua modul yang memakai
# tema.W[...] / tema.WARNA_KATEGORI langsung mendapat warna tema terpilih.
W = dict(PALET[TEMA_BAWAAN])
WARNA_KATEGORI = list(_KATEGORI[TEMA_BAWAAN])
WARNA_TIPE = dict(_TIPE[TEMA_BAWAAN])
TEMA_AKTIF = TEMA_BAWAAN


def pilih_tema(nama: str) -> None:
    global TEMA_AKTIF
    nama = nama if nama in PALET else TEMA_BAWAAN
    W.clear()
    W.update(PALET[nama])
    WARNA_KATEGORI[:] = _KATEGORI[nama]
    WARNA_TIPE.clear()
    WARNA_TIPE.update(_TIPE[nama])
    TEMA_AKTIF = nama


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
QFrame#sidebar {{ background-color: {c['sidebar']}; border-right: 1px solid {c['sidebar_garis']}; }}
QFrame#sidebar QLabel#bagian {{ color: {c['sidebar_samar']}; }}
QLabel#namaAplikasi {{ font-size: 16px; font-weight: 700; color: {c['sidebar_judul']}; }}
QLabel#taglineAplikasi {{ font-size: 11px; color: {c['sidebar_samar']}; }}
QLabel#infoSidebar {{ font-size: 11px; color: {c['sidebar_samar']}; }}
QPushButton#navItem {{
    text-align: left; padding: 10px 14px; border: none; border-left: 3px solid transparent; border-radius: 8px;
    background: transparent; color: {c['sidebar_teks']}; font-weight: 600;
}}
QPushButton#navItem:hover {{ background-color: {c['sidebar_hover']}; color: {c['sidebar_teks_aktif']}; }}
QPushButton#navItem:checked {{
    background-color: {c['sidebar_aktif']}; color: {c['sidebar_teks_aktif']};
    border-left: 3px solid {c['tombol_utama']}; border-top-left-radius: 2px; border-bottom-left-radius: 2px;
}}

/* ---------- tab ---------- */
QTabWidget::pane {{ border: none; border-top: 1px solid {c['garis']}; top: -1px; }}
QTabBar::tab {{
    background: transparent; color: {c['teks_redup']}; font-weight: 600; padding: 8px 16px;
    border: none; border-bottom: 2px solid transparent; margin-right: 4px;
}}
QTabBar::tab:hover {{ color: {c['teks']}; }}
QTabBar::tab:selected {{ color: {c['teks_kuat']}; border-bottom: 2px solid {c['aksen']}; }}

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
QLabel#sukses {{ color: {c['sukses']}; font-size: 12px; font-weight: 600; }}
QLabel#judulPanel {{ font-size: 15px; font-weight: 700; color: {c['teks_kuat']}; }}
QLabel#nilaiBesar {{ font-size: 20px; font-weight: 700; color: {c['teks_kuat']}; }}
QLabel#rumus {{
    font-family: "Cascadia Mono", "Consolas", "DejaVu Sans Mono", monospace; font-size: 12px;
    background-color: {c['latar']}; border: 1px solid {c['garis']}; border-radius: 6px; padding: 8px 10px;
}}
QPlainTextEdit#rincianLog {{ font-family: "Cascadia Mono", "Consolas", "DejaVu Sans Mono", monospace; font-size: 12px; }}
QLabel#chip {{ border-radius: 9px; padding: 2px 9px; font-size: 11px; font-weight: 600; }}
QLabel#chip[jenis="netral"] {{ background-color: {c['permukaan_3']}; color: {c['teks_redup']}; }}
QLabel#chip[jenis="info"] {{ background-color: {c['aksen_lembut']}; color: {c['aksen_hover']}; }}
QLabel#chip[jenis="sukses"] {{ background-color: {c['sukses_lembut']}; color: {c['sukses']}; }}
QLabel#chip[jenis="peringatan"] {{ background-color: {c['peringatan_lembut']}; color: {c['peringatan']}; }}
QLabel#chip[jenis="bahaya"] {{ background-color: {c['bahaya_lembut']}; color: {c['bahaya']}; }}

/* ---------- kartu & panel ---------- */
QFrame#kartu, QFrame#panel {{ background-color: {c['permukaan']}; border: 1px solid {c['garis']}; border-radius: 12px; }}
QFrame#kartuStat {{ background-color: {c['permukaan']}; border: 1px solid {c['garis']}; border-radius: 12px; }}
QFrame#kartuStat[klik="true"]:hover {{ border: 1px solid {c['garis_hover']}; background-color: {c['permukaan_2']}; }}
QFrame#kartuStatUtama {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 {c['utama_awal']}, stop:1 {c['utama_akhir']});
    border: 1px solid {c['utama_garis']}; border-radius: 12px;
}}
QLabel#statJudul {{ color: {c['teks_redup']}; font-size: 11px; font-weight: 700; letter-spacing: 1px; }}
QLabel#statNilai {{ color: {c['teks_kuat']}; font-size: 21px; font-weight: 700; }}
QLabel#statKet {{ color: {c['teks_samar']}; font-size: 11px; }}
QFrame#kartuStatUtama QLabel#statJudul {{ color: {c['utama_judul']}; }}
QFrame#kartuStatUtama QLabel#statNilai {{ color: {c['utama_nilai']}; }}
QFrame#kartuStatUtama QLabel#statKet {{ color: {c['utama_ket']}; }}
QFrame#kartuKosong {{ background-color: {c['permukaan']}; border: 1px dashed {c['garis_kuat']}; border-radius: 14px; }}
QLabel#kosongJudul {{ font-size: 17px; font-weight: 700; color: {c['teks_kuat']}; }}
QLabel#kosongDeskripsi {{ color: {c['teks_redup']}; }}
QFrame#garis {{ background-color: {c['garis']}; max-height: 1px; min-height: 1px; border: none; }}

/* ---------- banner ---------- */
QFrame#banner {{ border-radius: 10px; }}
QFrame#banner[jenis="peringatan"] {{ background-color: {c['peringatan_lembut']}; border: 1px solid {c['peringatan_garis']}; }}
QFrame#banner[jenis="info"] {{ background-color: {c['aksen_lembut']}; border: 1px solid {c['aksen_garis']}; }}
QFrame#banner[jenis="peringatan"] QLabel {{ color: {c['peringatan']}; }}
QFrame#banner[jenis="info"] QLabel {{ color: {c['info_teks']}; }}
QLabel#keteranganMode {{ background-color: {c['aksen_lembut']}; border: 1px solid {c['aksen_garis']}; border-radius: 8px;
    padding: 7px 12px; color: {c['info_teks']}; font-size: 12px; }}

/* ---------- toast ---------- */
QFrame#toast {{ background-color: {c['permukaan_3']}; border: 1px solid {c['garis_kuat']}; border-radius: 10px; }}
QFrame#toast QLabel {{ color: {c['teks_kuat']}; font-weight: 600; }}

/* ---------- tombol ---------- */
QPushButton {{ border-radius: 8px; padding: 9px 18px; font-weight: 600; border: none; }}
QPushButton#btnPrimary {{ background-color: {c['tombol_utama']}; color: {c['tombol_utama_teks']}; }}
QPushButton#btnPrimary:hover {{ background-color: {c['tombol_utama_hover']}; }}
QPushButton#btnPrimary:pressed {{ background-color: {c['tombol_utama_tekan']}; }}
QPushButton#btnPrimary:disabled {{ background-color: {c['permukaan_3']}; color: {c['teks_samar']}; }}
QPushButton#btnSecondary {{ background-color: {c['permukaan_3']}; color: {c['teks']}; border: 1px solid {c['garis_kuat']}; }}
QPushButton#btnSecondary:hover {{ background-color: {c['sekunder_hover']}; }}
QPushButton#btnSecondary:disabled {{ color: {c['teks_samar']}; background-color: {c['permukaan']}; border: 1px solid {c['garis']}; }}
QToolButton#btnSecondary {{
    background-color: {c['permukaan_3']}; color: {c['teks']}; border: 1px solid {c['garis_kuat']};
    border-radius: 8px; padding: 9px 16px; font-weight: 600;
}}
QToolButton#btnSecondary:hover {{ background-color: {c['sekunder_hover']}; }}
QToolButton#btnSecondary::menu-indicator {{ image: none; width: 0; }}
QMenu {{ background-color: {c['permukaan_2']}; color: {c['teks']}; border: 1px solid {c['garis_kuat']}; padding: 6px; }}
QMenu::item {{ padding: 7px 26px 7px 14px; border-radius: 6px; }}
QMenu::item:selected {{ background-color: {c['aksen_lembut']}; color: {c['teks_kuat']}; }}
QMenu::separator {{ height: 1px; background: {c['garis']}; margin: 5px 8px; }}
QPushButton#btnGhost {{ background: transparent; color: {c['teks_redup']}; padding: 8px 12px; }}
QPushButton#btnGhost:hover {{ background-color: {c['permukaan']}; color: {c['teks']}; }}
QPushButton#btnGhost:disabled {{ color: {c['teks_samar']}; }}
QPushButton#btnDanger {{ background: transparent; color: {c['bahaya']}; border: 1px solid {c['bahaya_garis']}; }}
QPushButton#btnDanger:hover {{ background-color: {c['bahaya_lembut']}; }}
QPushButton#btnDanger:disabled {{ color: {c['teks_samar']}; border: 1px solid {c['garis']}; }}
QPushButton#btnBanner {{ background: transparent; border: 1px solid currentColor; padding: 6px 14px; }}
QFrame#banner[jenis="peringatan"] QPushButton#btnBanner {{ color: {c['peringatan']}; border: 1px solid {c['peringatan']}; }}
QFrame#banner[jenis="info"] QPushButton#btnBanner {{ color: {c['info_teks']}; border: 1px solid {c['info_tombol']}; }}
QPushButton#segmen {{
    background: transparent; color: {c['teks_redup']}; border: 1px solid {c['garis_kuat']};
    border-radius: 0; padding: 8px 16px;
}}
QPushButton#segmen[posisi="kiri"] {{ border-top-left-radius: 8px; border-bottom-left-radius: 8px; }}
QPushButton#segmen[posisi="kanan"] {{ border-top-right-radius: 8px; border-bottom-right-radius: 8px; border-left: none; }}
QPushButton#segmen[posisi="tengah"] {{ border-radius: 0; border-left: none; }}
QPushButton#segmen:hover {{ color: {c['teks']}; }}
QPushButton#segmen:checked {{ background-color: {c['aksen_lembut']}; color: {c['teks_kuat']}; border-color: {c['aksen_garis']}; }}
QPushButton:focus {{ outline: none; }}

QToolButton#kartuTema {{
    background-color: {c['permukaan']}; border: 2px solid {c['garis']}; border-radius: 12px;
    padding: 10px 10px 8px 10px; color: {c['teks']}; font-weight: 600;
}}
QToolButton#kartuTema:hover {{ border-color: {c['garis_hover']}; }}
QToolButton#kartuTema:checked {{ border-color: {c['tombol_utama']}; background-color: {c['aksen_lembut']}; }}

/* ---------- input ---------- */
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox, QPlainTextEdit {{
    background-color: {c['permukaan']}; border: 1px solid {c['garis_kuat']}; border-radius: 8px;
    padding: 7px 12px; color: {c['teks']}; selection-background-color: {c['seleksi_teks']};
}}
QLineEdit:hover, QSpinBox:hover, QDoubleSpinBox:hover, QComboBox:hover {{ border: 1px solid {c['garis_hover']}; }}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {{ border: 1px solid {c['aksen']}; background-color: {c['fokus_latar']}; }}
QLineEdit:disabled, QDoubleSpinBox:disabled {{ color: {c['teks_samar']}; }}
QComboBox {{ padding-right: 30px; }}
QComboBox::drop-down {{ border: none; width: 28px; }}
QComboBox::down-arrow {{ image: {panah}; width: 14px; height: 14px; }}
QComboBox QAbstractItemView {{
    background-color: {c['permukaan_2']}; border: 1px solid {c['garis_kuat']}; color: {c['teks']};
    selection-background-color: {c['pilih']}; selection-color: {c['teks_kuat']}; outline: none; padding: 4px;
}}
QCheckBox {{ spacing: 9px; }}
QCheckBox::indicator {{ width: 18px; height: 18px; border-radius: 5px; border: 1px solid {c['garis_kuat']}; background-color: {c['permukaan']}; }}
QCheckBox::indicator:hover {{ border: 1px solid {c['aksen']}; }}
QCheckBox::indicator:checked {{ background-color: {c['aksen']}; border: 1px solid {c['aksen']}; image: {centang}; }}

/* ---------- tabel ---------- */
QTableWidget, QListWidget {{
    background-color: {c['permukaan']}; border: 1px solid {c['garis']}; border-radius: 12px;
    gridline-color: transparent; outline: none; alternate-background-color: {c['permukaan_2']};
    selection-background-color: {c['pilih']}; selection-color: {c['teks_kuat']};
}}
QTableWidget::item {{ padding: 6px 10px; border: none; }}
QTableWidget::item:hover {{ background-color: {c['permukaan_3']}; }}
QTableWidget::item:selected {{ background-color: {c['pilih']}; color: {c['teks_kuat']}; }}
QHeaderView {{ background-color: transparent; }}
QHeaderView::section {{
    background-color: {c['permukaan']}; color: {c['teks_redup']}; padding: 10px; border: none;
    border-bottom: 1px solid {c['garis']}; font-weight: 700; font-size: 11px;
}}
QTableWidget QDoubleSpinBox {{ background-color: {c['permukaan_3']}; border-radius: 6px; padding: 3px 8px; margin: 5px 6px; }}
QTableWidget QDoubleSpinBox:focus {{ background-color: {c['fokus_latar']}; }}

/* ---------- scrollbar ---------- */
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 4px 2px; }}
QScrollBar::handle:vertical {{ background: {c['gulir']}; border-radius: 4px; min-height: 36px; }}
QScrollBar::handle:vertical:hover {{ background: {c['gulir_hover']}; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 2px 4px; }}
QScrollBar::handle:horizontal {{ background: {c['gulir']}; border-radius: 4px; min-width: 36px; }}
QScrollBar::handle:horizontal:hover {{ background: {c['gulir_hover']}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}
QScrollArea {{ background: transparent; border: none; }}
QScrollArea > QWidget#qt_scrollarea_viewport, QScrollArea > QWidget > QWidget {{ background: transparent; }}
QSplitter::handle {{ background: transparent; }}
QWidget#isiPanel {{ background: transparent; }}

/* ---------- dialog ---------- */
QMessageBox {{ background-color: {c['permukaan']}; }}
QMessageBox QPushButton {{ background-color: {c['permukaan_3']}; border: 1px solid {c['garis_kuat']}; min-width: 90px; padding: 8px 16px; }}
QMessageBox QPushButton:hover {{ background-color: {c['sekunder_hover']}; }}
QProgressDialog {{ background-color: {c['permukaan']}; }}
QProgressBar {{ background-color: {c['latar']}; border: 1px solid {c['garis_kuat']}; border-radius: 6px; height: 14px; text-align: center; }}
QProgressBar::chunk {{ background-color: {c['aksen']}; border-radius: 5px; }}
"""


def terapkan(app, nama_tema: str | None = None) -> None:
    """Pasang tema ke seluruh aplikasi. `nama_tema` = salah satu kunci PALET (None = tema aktif)."""
    if nama_tema:
        pilih_tema(nama_tema)
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
    elif nama == "pengaturan":  # roda gigi: lingkaran + 8 gigi
        import math as _m

        for i in range(8):
            a = _m.radians(i * 45)
            p.drawLine(QPointF(10 + 5.5 * _m.cos(a), 10 + 5.5 * _m.sin(a)), QPointF(10 + 7.8 * _m.cos(a), 10 + 7.8 * _m.sin(a)))
        p.drawEllipse(QRectF(4.5, 4.5, 11, 11))
        p.drawEllipse(QRectF(8, 8, 4, 4))
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
        warna = W["tombol_utama_teks"] if peran == "primary" else (W["bahaya"] if peran == "danger" else W["teks"])
        b.setIcon(ikon(ikon_nama, warna))
    if tooltip:
        b.setToolTip(tooltip)
    return b


class LabelPotong(QLabel):
    """Label satu baris yang memotong teks panjang dengan "…" (teks lengkap di tooltip),
    sehingga judul panjang tidak mendorong tombol di sebelahnya keluar layar."""

    def __init__(self, teks: str = "", parent=None):
        super().__init__(parent)
        self._penuh = ""
        self.setMinimumWidth(120)
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.setText(teks)

    def setText(self, teks: str) -> None:  # noqa: N802 (API Qt)
        self._penuh = teks or ""
        self.setToolTip(self._penuh)
        self._potong()

    def text(self) -> str:  # noqa: N802
        return self._penuh

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._potong()

    def _potong(self):
        super().setText(self.fontMetrics().elidedText(self._penuh, Qt.ElideRight, max(self.width(), 40)))

    def sizeHint(self):
        h = super().sizeHint()
        h.setWidth(self.fontMetrics().horizontalAdvance(self._penuh) + 8)
        return h


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


def header_halaman(judul: str, sub: str = "", remah: str | None = None, potong: bool = False):
    """Kolom judul halaman. Return (layout, label_judul, label_sub).
    potong=True: judul & subjudul dipotong dengan "…" bila ruang sempit (teks lengkap di tooltip)."""
    kol = QVBoxLayout()
    kol.setSpacing(2)
    if remah:
        kol.addWidget(label(remah, "remah"))
    if potong:
        lj, ls = LabelPotong(judul), LabelPotong(sub)
        lj.setObjectName("judulHalaman")
        ls.setObjectName("subjudul")
    else:
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

    def bisa_diklik(self, aksi, tooltip: str = "") -> None:
        """Jadikan kartu sebagai tombol (mis. kartu Biaya Tidak Langsung membuka dialognya)."""
        self._aksi = aksi
        self.setCursor(Qt.PointingHandCursor)
        self.setProperty("klik", True)
        if tooltip:
            self.setToolTip(tooltip)

    def mouseReleaseEvent(self, event):
        aksi = getattr(self, "_aksi", None)
        if aksi and event.button() == Qt.LeftButton and self.rect().contains(event.position().toPoint()):
            aksi()
        super().mouseReleaseEvent(event)


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
        gambar_logo(p, self.width())
        p.end()


def gambar_logo(p: QPainter, s: float) -> None:
    """Gambar logo CostStruct ukuran s x s (dipakai widget Logo, ikon jendela, dan ikon .exe)."""
    p.setRenderHint(QPainter.Antialiasing)
    area = QRectF(0, 0, s, s)
    grad = QLinearGradient(area.topLeft(), area.bottomRight())
    grad.setColorAt(0.0, QColor(W["logo_awal"]))
    grad.setColorAt(1.0, QColor(W["logo_akhir"]))
    p.setPen(Qt.NoPen)
    p.setBrush(QBrush(grad))
    p.drawRoundedRect(area, s * 0.28, s * 0.28)
    lebar, jarak = s * 0.15, s * 0.09
    x0 = (s - (3 * lebar + 2 * jarak)) / 2
    dasar = s * 0.74
    for i, (t, a) in enumerate(zip([0.22, 0.38, 0.54], [170, 215, 255])):
        batang = QColor(W["logo_batang"])
        batang.setAlpha(a)
        p.setBrush(batang)
        p.drawRoundedRect(QRectF(x0 + i * (lebar + jarak), dasar - s * t, lebar, s * t), s * 0.05, s * 0.05)


def pratinjau_tema(nama: str, lebar: int = 184, tinggi: int = 104) -> QPixmap:
    """Miniatur aplikasi dengan warna tema `nama` (kartu pilihan tema di halaman Pengaturan)."""
    c = PALET[nama]
    skala = 2  # gambar 2x agar tajam di layar HiDPI
    pm = QPixmap(lebar * skala, tinggi * skala)
    pm.setDevicePixelRatio(skala)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    p.setPen(Qt.NoPen)
    bingkai = QPainterPath()
    bingkai.addRoundedRect(QRectF(0, 0, lebar, tinggi), 8, 8)
    p.setClipPath(bingkai)
    p.fillRect(QRectF(0, 0, lebar, tinggi), QColor(c["latar"]))
    p.fillRect(QRectF(0, 0, 44, tinggi), QColor(c["sidebar"]))
    p.setBrush(QColor(c["logo_awal"]))
    p.drawRoundedRect(QRectF(8, 8, 12, 12), 3, 3)
    for i in range(4):  # menu sidebar, yang pertama aktif
        p.setBrush(QColor(c["sidebar_aktif"] if i == 0 else c["sidebar_hover"]))
        p.drawRoundedRect(QRectF(6, 30 + i * 13, 32, 8), 2, 2)
    p.setBrush(QColor(c["tombol_utama"]))
    p.drawRect(QRectF(6, 30, 2, 8))
    for i, warna in enumerate((c["permukaan"], c["permukaan"], c["utama_awal"])):  # kartu angka
        p.setBrush(QColor(warna))
        p.drawRoundedRect(QRectF(52 + i * 42, 10, 38, 20), 4, 4)
    p.setBrush(QColor(c["permukaan"]))
    p.drawRoundedRect(QRectF(52, 36, 124, 60), 5, 5)
    for i in range(4):  # baris tabel
        p.setBrush(QColor(c["teks_redup"] if i else c["aksen"]))
        p.drawRoundedRect(QRectF(58, 44 + i * 12, 60 if i else 46, 4), 2, 2)
        p.setBrush(QColor(c["teks_samar"]))
        p.drawRoundedRect(QRectF(140, 44 + i * 12, 28, 4), 2, 2)
    p.setBrush(QColor(c["tombol_utama"]))
    p.drawRoundedRect(QRectF(140, 10, 36, 10), 3, 3)
    p.end()
    return pm


def gambar_ikon_aplikasi(ukuran: int = 256) -> QPixmap:
    pm = QPixmap(ukuran, ukuran)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    gambar_logo(p, ukuran)
    p.end()
    return pm


def ikon_aplikasi() -> QIcon:
    """Ikon jendela/taskbar CostStruct (KNF-8), digambar tanpa file gambar."""
    ik = QIcon()
    for u in (16, 24, 32, 48, 64, 128, 256):
        ik.addPixmap(gambar_ikon_aplikasi(u))
    return ik


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


def atur_lebar(tabel: QTableWidget, stretch: int, isi_konten=(), minimum: int = 170) -> None:
    """Kolom `stretch` mengisi sisa lebar, tetapi tidak pernah lebih sempit dari `minimum` piksel:
    di layar sempit / skala Windows besar tabel bergulir ke samping, judul (mis. nama lantai) tetap terbaca."""
    h = tabel.horizontalHeader()
    for kol in range(tabel.columnCount()):
        if kol == stretch:
            h.setSectionResizeMode(kol, QHeaderView.Stretch)
        elif kol in isi_konten:
            h.setSectionResizeMode(kol, QHeaderView.ResizeToContents)
        else:
            h.setSectionResizeMode(kol, QHeaderView.Interactive)
    lama = getattr(tabel, "_lebar_minimum", None)
    if lama is not None:
        tabel.viewport().removeEventFilter(lama)
        lama.deleteLater()
    tabel._lebar_minimum = _LebarMinimum(tabel, stretch, minimum) if minimum else None


class _LebarMinimum(QObject):
    """Mengganti kolom Stretch menjadi Interactive (lebar = minimum) bila ruang tersisa terlalu sempit."""

    def __init__(self, tabel: QTableWidget, kolom: int, minimum: int):
        super().__init__(tabel)
        self.tabel, self.kolom, self.minimum = tabel, kolom, minimum
        tabel.viewport().installEventFilter(self)
        QTimer.singleShot(0, self.periksa)

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Resize:
            QTimer.singleShot(0, self.periksa)
        return False

    def periksa(self):
        try:
            h = self.tabel.horizontalHeader()
        except RuntimeError:  # tabel sudah dihapus
            return
        if self.kolom >= h.count():
            return
        lain = sum(h.sectionSize(i) for i in range(h.count()) if i != self.kolom and not h.isSectionHidden(i))
        sisa = self.tabel.viewport().width() - lain
        if sisa >= self.minimum:
            if h.sectionResizeMode(self.kolom) != QHeaderView.Stretch:
                h.setSectionResizeMode(self.kolom, QHeaderView.Stretch)
        elif h.sectionResizeMode(self.kolom) != QHeaderView.Interactive or h.sectionSize(self.kolom) < self.minimum:
            h.setSectionResizeMode(self.kolom, QHeaderView.Interactive)
            h.resizeSection(self.kolom, self.minimum)


KUNCI_URUT = Qt.UserRole + 7


class SelUrut(QTableWidgetItem):
    """Sel tabel yang diurutkan menurut kunci (angka) bila ada, selain itu teks tanpa membedakan
    huruf besar/kecil (KF-16). Rp 1.250.000 diurutkan sebagai angka, bukan sebagai teks."""

    def __lt__(self, lain):
        a, b = self.data(KUNCI_URUT), lain.data(KUNCI_URUT)
        if a is not None and b is not None and type(a) is type(b):
            return a < b
        if isinstance(a, (int, float)) and isinstance(b, (int, float)):
            return a < b
        return self.text().lower() < lain.text().lower()


def siapkan_urut(tabel: QTableWidget) -> None:
    """Klik judul kolom untuk mengurutkan (KF-16); urutan awal tetap urutan data."""
    h = tabel.horizontalHeader()
    h.setSortIndicatorShown(True)
    h.setSortIndicator(-1, Qt.AscendingOrder)
    h.setSectionsClickable(True)
    tabel.setSortingEnabled(True)


def sel(teks, rata=None, warna=None, tebal=False, tooltip=None, data=None, urut=None) -> QTableWidgetItem:
    it = SelUrut("" if teks is None else str(teks))
    if urut is not None:
        it.setData(KUNCI_URUT, urut)
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


def tanya(parent, judul: str, teks: str, ya: str = "Ya, Lanjutkan", tidak: str = "Batal", info: str = "") -> bool:
    """Konfirmasi dengan tombol berbahasa Indonesia (KNF-6). True bila pengguna memilih `ya`."""
    from PySide6.QtWidgets import QMessageBox

    kotak = QMessageBox(parent)
    kotak.setIcon(QMessageBox.Question)
    kotak.setWindowTitle(judul)
    kotak.setText(teks)
    if info:
        kotak.setInformativeText(info)
    btn_ya = kotak.addButton(ya, QMessageBox.AcceptRole)
    btn_tidak = kotak.addButton(tidak, QMessageBox.RejectRole)
    kotak.setDefaultButton(btn_tidak)
    kotak.exec()
    return kotak.clickedButton() is btn_ya
