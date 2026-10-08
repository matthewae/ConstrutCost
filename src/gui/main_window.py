"""
Jendela utama CostStruct: sidebar navigasi + halaman (Proyek, Hasil Estimasi, Harga Satuan, Pengaturan).
Semua halaman tinggal di satu jendela, sehingga berpindah halaman tidak membuka jendela baru.
Saat tema diganti (KF-10), isi jendela dibangun ulang dan pengguna kembali ke halaman yang sama.
"""

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QMainWindow,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from aktivitas import catat
from gui import tema
from gui.aktivitas_page import AktivitasPage
from gui.estimasi_page import EstimasiPage
from gui.harga_page import HargaPage
from gui.pengaturan_page import PengaturanPage
from gui.proyek_page import ProyekPage

VERSI_APLIKASI = "v1.4.0"
NAV_PROYEK, NAV_HARGA, NAV_PENGATURAN, NAV_AKTIVITAS = 0, 1, 2, 3


class MainWindow(QMainWindow):
    LEBAR_SIDEBAR = 224

    def __init__(self):
        super().__init__()
        self.setWindowTitle("CostStruct — Estimasi RAB dari Model IFC")
        self.resize(1320, 820)
        self.setMinimumSize(1080, 640)
        self.setAcceptDrops(True)
        self._estimasi = None  # EstimasiPage yang sedang terbuka
        self.toast = None

        self._bangun_isi()

        QShortcut(QKeySequence("Ctrl+N"), self, activated=lambda: self._ke_proyek_lalu_import())
        QShortcut(QKeySequence("Ctrl+1"), self, activated=self.tampilkan_proyek)
        QShortcut(QKeySequence("Ctrl+2"), self, activated=lambda: self.tampilkan_harga())
        QShortcut(QKeySequence("Ctrl+3"), self, activated=self.tampilkan_pengaturan)
        QShortcut(QKeySequence("Ctrl+,"), self, activated=self.tampilkan_pengaturan)
        QShortcut(QKeySequence("Ctrl+4"), self, activated=self.tampilkan_aktivitas)
        self.tampilkan_proyek()

    def _bangun_isi(self):
        """Buat sidebar dan semua halaman. Dipanggil ulang saat tema berganti."""
        self._estimasi = None
        pusat = QWidget()
        lay = QHBoxLayout(pusat)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        lay.addWidget(self._buat_sidebar())

        self.stack = QStackedWidget()
        lay.addWidget(self.stack, stretch=1)
        self.hal_proyek = ProyekPage()
        self.hal_harga = HargaPage()
        self.hal_pengaturan = PengaturanPage()
        self.hal_aktivitas = AktivitasPage()
        for hal in (self.hal_proyek, self.hal_harga, self.hal_pengaturan, self.hal_aktivitas):
            self.stack.addWidget(hal)
        self.setCentralWidget(pusat)  # pusat lama (bila ada) dihapus Qt

        self.hal_proyek.minta_buka.connect(self.buka_estimasi)
        self.hal_harga.harga_diterapkan.connect(self._setelah_harga_diterapkan)
        self.hal_pengaturan.tersimpan.connect(self._setelah_pengaturan_disimpan)

        if self.toast is not None:
            self.toast.deleteLater()
        self.toast = tema.Toast(self)

    # ---------------------------------------------------------------- sidebar

    def _buat_sidebar(self) -> QFrame:
        bar = QFrame()
        bar.setObjectName("sidebar")
        bar.setFixedWidth(self.LEBAR_SIDEBAR)
        lay = QVBoxLayout(bar)
        lay.setContentsMargins(16, 22, 16, 18)
        lay.setSpacing(6)

        merek = QHBoxLayout()
        merek.setSpacing(10)
        merek.addWidget(tema.Logo(38))
        teks = QVBoxLayout()
        teks.setSpacing(0)
        teks.addWidget(tema.label("CostStruct", "namaAplikasi"))
        teks.addWidget(tema.label("QTO & RAB dari model IFC", "taglineAplikasi"))
        merek.addLayout(teks)
        lay.addLayout(merek)
        lay.addSpacing(22)
        lay.addWidget(tema.label("MENU", "bagian"))
        lay.addSpacing(2)

        self.grup_nav = QButtonGroup(self)
        self.grup_nav.setExclusive(True)
        for idx, (teks_nav, nama_ikon, pintas) in (
            (NAV_PROYEK, ("Proyek", "proyek", "Ctrl+1")),
            (NAV_HARGA, ("Harga Satuan", "harga", "Ctrl+2")),
            (NAV_AKTIVITAS, ("Riwayat Aktivitas", "file", "Ctrl+4")),
            (NAV_PENGATURAN, ("Pengaturan", "pengaturan", "Ctrl+3")),
        ):
            b = QPushButton(f"  {teks_nav}")
            b.setObjectName("navItem")
            b.setCheckable(True)
            b.setCursor(Qt.PointingHandCursor)
            b.setIcon(tema.ikon(nama_ikon, tema.W["teks"]))
            b.setToolTip(f"{teks_nav} ({pintas})")
            self.grup_nav.addButton(b, idx)
            lay.addWidget(b)
        self.grup_nav.idClicked.connect(self._nav_diklik)

        lay.addStretch()
        lay.addWidget(tema.label("Seret file .ifc ke jendela ini untuk membuat proyek baru.", "infoSidebar", wrap=True))
        lay.addSpacing(8)
        lay.addWidget(tema.label(f"Offline · database lokal\n{VERSI_APLIKASI}", "infoSidebar"))
        return bar

    def _nav_diklik(self, idx: int):
        if idx == NAV_PROYEK:
            self.tampilkan_proyek()
        elif idx == NAV_HARGA:
            self.tampilkan_harga()
        elif idx == NAV_AKTIVITAS:
            self.tampilkan_aktivitas()
        else:
            self.tampilkan_pengaturan()

    # ---------------------------------------------------------------- navigasi

    def tampilkan_proyek(self):
        self.grup_nav.button(NAV_PROYEK).setChecked(True)
        self.hal_proyek.muat()
        self.stack.setCurrentWidget(self.hal_proyek)

    def buka_estimasi(self, proyek_id: int, nama: str):
        if self._estimasi is not None:
            self.stack.removeWidget(self._estimasi)
            self._estimasi.deleteLater()
        self._estimasi = EstimasiPage(proyek_id, nama)
        self._estimasi.minta_kembali.connect(self._tutup_estimasi)
        self._estimasi.minta_harga.connect(self.tampilkan_harga)
        self._estimasi.minta_buka_proyek.connect(self.buka_estimasi)
        self.stack.addWidget(self._estimasi)
        self.grup_nav.button(NAV_PROYEK).setChecked(True)
        self.stack.setCurrentWidget(self._estimasi)

    def _tutup_estimasi(self):
        if self._estimasi is not None:
            self.stack.removeWidget(self._estimasi)
            self._estimasi.deleteLater()
            self._estimasi = None
        self.tampilkan_proyek()

    def tampilkan_harga(self, pekerjaan_id=None):
        self.grup_nav.button(NAV_HARGA).setChecked(True)
        self.hal_harga.muat()
        if pekerjaan_id is not None:
            self.hal_harga.fokus_pekerjaan(pekerjaan_id)
        self.stack.setCurrentWidget(self.hal_harga)

    def tampilkan_aktivitas(self):
        self.grup_nav.button(NAV_AKTIVITAS).setChecked(True)
        self.hal_aktivitas.muat()
        self.stack.setCurrentWidget(self.hal_aktivitas)

    def closeEvent(self, event):
        catat("aplikasi", "Aplikasi ditutup")
        super().closeEvent(event)

    def tampilkan_pengaturan(self):
        self.grup_nav.button(NAV_PENGATURAN).setChecked(True)
        self.hal_pengaturan.muat()
        self.stack.setCurrentWidget(self.hal_pengaturan)

    def _setelah_pengaturan_disimpan(self, tema_berubah: bool, pesan: str):
        """UC-07 langkah 5: perubahan langsung diterapkan ke antarmuka."""
        if tema_berubah:
            from PySide6.QtWidgets import QApplication

            tema.terapkan(QApplication.instance(), self.hal_pengaturan.preferensi.tema)
            self._bangun_isi()
            self.tampilkan_pengaturan()
        self.toast.tampilkan(pesan)

    def _setelah_harga_diterapkan(self):
        # UC-04 langkah 10: kembali ke hasil estimasi yang sedang dikerjakan dengan total terbaru
        if self._estimasi is not None:
            self._estimasi.muat()
            self.grup_nav.button(NAV_PROYEK).setChecked(True)
            self.stack.setCurrentWidget(self._estimasi)
        else:
            self.hal_proyek.muat()

    def _ke_proyek_lalu_import(self, path=None):
        self.tampilkan_proyek()
        self.hal_proyek.import_ifc(path)

    # ---------------------------------------------------------------- drag & drop

    @staticmethod
    def _path_dari(event):
        urls = event.mimeData().urls() if event.mimeData().hasUrls() else []
        if len(urls) == 1 and urls[0].isLocalFile():
            return urls[0].toLocalFile()
        return None

    def dragEnterEvent(self, event):
        if self._path_dari(event):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):
        path = self._path_dari(event)
        if path:
            event.acceptProposedAction()
            self._ke_proyek_lalu_import(path)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.toast is not None and self.toast.isVisible():
            self.toast.posisikan()


def main():
    import multiprocessing
    import sys

    from PySide6.QtWidgets import QApplication

    from database.init_db import siapkan_database

    from database.preferensi_repository import muat_preferensi

    multiprocessing.freeze_support()
    app = QApplication(sys.argv)
    siapkan_database()
    tema.terapkan(app, muat_preferensi().tema)
    w = MainWindow()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
