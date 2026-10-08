"""
Pratinjau laporan RAB sebelum export (KF-6: memverifikasi keluaran melalui tampilan pratinjau).
Laporan dibuat sebagai PDF sementara dengan pilihan isi & kolom yang sama, lalu ditampilkan
dengan QPdfView (tanpa aplikasi luar, tetap luring).
"""

from PySide6.QtCore import Qt
from PySide6.QtPdf import QPdfDocument
from PySide6.QtPdfWidgets import QPdfView
from PySide6.QtWidgets import QComboBox, QDialog, QHBoxLayout, QVBoxLayout

from gui import tema

ZOOM = (("Sesuai lebar", None), ("75%", 0.75), ("100%", 1.0), ("125%", 1.25), ("150%", 1.5))


class PratinjauDialog(QDialog):
    def __init__(self, path_pdf: str, judul: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Pratinjau Laporan")
        self.setModal(True)
        self.resize(1000, 820)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 16, 20, 16)
        lay.setSpacing(10)

        self.dok = QPdfDocument(self)
        self.dok.load(path_pdf)
        kepala = QHBoxLayout()
        kepala.addWidget(tema.kepala_dialog(
            "Pratinjau Laporan",
            f"{judul}  ·  {self.dok.pageCount()} halaman. Periksa isi sebelum export; tutup untuk mengubah pilihan.",
            "file",
        )[0], stretch=1)
        self.combo_zoom = QComboBox()
        for teks, nilai in ZOOM:
            self.combo_zoom.addItem(teks, nilai)
        self.combo_zoom.currentIndexChanged.connect(self._zoom)
        kepala.addWidget(self.combo_zoom, alignment=Qt.AlignBottom)
        lay.addLayout(kepala)

        self.view = QPdfView(self)
        self.view.setDocument(self.dok)
        self.view.setPageMode(QPdfView.PageMode.MultiPage)
        self.view.setPageSpacing(12)
        lay.addWidget(self.view, stretch=1)
        self._zoom()

        tombol = QHBoxLayout()
        tombol.addStretch()
        tutup = tema.tombol("Tutup", "secondary")
        tutup.clicked.connect(self.reject)
        self.btn_export = tema.tombol("Export Sekarang", "primary", "unduh")
        self.btn_export.clicked.connect(self.accept)
        tombol.addWidget(tutup)
        tombol.addWidget(self.btn_export)
        lay.addLayout(tombol)

    def _zoom(self, *_):
        nilai = self.combo_zoom.currentData()
        if nilai is None:
            self.view.setZoomMode(QPdfView.ZoomMode.FitToWidth)
        else:
            self.view.setZoomMode(QPdfView.ZoomMode.Custom)
            self.view.setZoomFactor(nilai)
