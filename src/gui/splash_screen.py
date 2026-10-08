"""
Splash screen CostStruct — tampil sebentar saat aplikasi dibuka,
sambil melakukan pengecekan awal (koneksi database) sebelum
masuk ke jendela utama.

Peningkatan dari versi sebelumnya:
- Kartu bergradasi dengan sudut membulat dan bayangan (drop shadow)
- Logo vektor digambar dengan QPainter (tanpa file gambar eksternal)
- Animasi fade-in saat muncul dan fade-out saat berpindah ke Dashboard
- Progress bar bergerak halus (animasi), bukan melompat
- Indikator persen, label versi, dan footer
- Pengecekan database tetap nyata, dengan pesan error yang jelas
"""

import multiprocessing
import sys

from PySide6.QtWidgets import (
    QApplication,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QFrame,
    QGraphicsDropShadowEffect,
)
from PySide6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, QRectF
from PySide6.QtGui import QColor, QPainter, QLinearGradient, QBrush, QPen

from database.init_db import siapkan_database
from database.proyek_repository import get_all_proyek
from gui import tema
from gui.main_window import VERSI_APLIKASI, MainWindow



# Tahapan loading yang ditampilkan ke user.
# Format: (persen_selesai, teks_status)
TAHAPAN_LOADING = [
    (20, "Memeriksa koneksi database..."),
    (55, "Memuat data proyek tersimpan..."),
    (85, "Menyiapkan antarmuka..."),
    (100, "Siap."),
]

JEDA_ANTAR_TAHAP_MS = 600
DURASI_ANIMASI_BAR_MS = 500
DURASI_FADE_MS = 350


class LogoCostStruct(QWidget):
    """Logo sederhana: kotak bergradasi dengan tiga batang naik (simbol biaya/struktur)."""

    UKURAN = 76

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(self.UKURAN, self.UKURAN)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        # Latar kotak membulat dengan gradasi biru
        area = QRectF(0, 0, self.width(), self.height())
        grad = QLinearGradient(area.topLeft(), area.bottomRight())
        grad.setColorAt(0.0, QColor("#6bb2ff"))
        grad.setColorAt(1.0, QColor("#2b6cd4"))
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(grad))
        p.drawRoundedRect(area, 20, 20)

        # Tiga batang naik berwarna putih
        lebar, jarak = 12, 8
        total = 3 * lebar + 2 * jarak
        x0 = (self.width() - total) / 2
        dasar = self.height() - 18
        tinggi = [18, 30, 44]
        alpha = [170, 215, 255]
        for i, t in enumerate(tinggi):
            warna = QColor(255, 255, 255, alpha[i])
            p.setBrush(warna)
            p.drawRoundedRect(
                QRectF(x0 + i * (lebar + jarak), dasar - t, lebar, t), 3, 3
            )

        # Garis dasar tipis
        p.setPen(QPen(QColor(255, 255, 255, 120), 2, Qt.SolidLine, Qt.RoundCap))
        p.drawLine(int(x0 - 4), int(dasar + 5), int(x0 + total + 4), int(dasar + 5))
        p.end()


class SplashScreen(QWidget):
    """Layar pembuka CostStruct. Frameless, di tengah layar, auto-lanjut ke Dashboard."""

    MARGIN_BAYANGAN = 24

    def __init__(self):
        super().__init__()
        self.dashboard = None  # ditahan sebagai atribut supaya tidak ke-garbage-collect

        # Jendela transparan supaya sudut membulat dan bayangan tampil mulus
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(
            520 + 2 * self.MARGIN_BAYANGAN, 340 + 2 * self.MARGIN_BAYANGAN
        )
        self.setWindowOpacity(0.0)

        self._susun_ui()
        self._pusatkan_di_layar()

        self._tahap_index = 0
        self._anim_bar = None
        self._anim_fade = None

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._lanjut_tahap)

    # ------------------------------------------------------------------ UI
    def _susun_ui(self):
        luar = QVBoxLayout(self)
        m = self.MARGIN_BAYANGAN
        luar.setContentsMargins(m, m, m, m)

        kartu = QFrame()
        kartu.setObjectName("kartu")
        kartu.setStyleSheet("""
            QFrame#kartu {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #223142, stop:1 #111a24);
                border: 1px solid #2f4258;
                border-radius: 18px;
            }
            QLabel { background: transparent; }
            QLabel#judul {
                color: #ffffff;
                font-size: 32px;
                font-weight: 700;
                letter-spacing: 1px;
            }
            QLabel#subjudul {
                color: #9fb3c8;
                font-size: 12px;
            }
            QLabel#status {
                color: #cfd8e3;
                font-size: 11px;
            }
            QLabel#persen {
                color: #6bb2ff;
                font-size: 11px;
                font-weight: 600;
            }
            QLabel#footer {
                color: #5f7388;
                font-size: 10px;
            }
            QProgressBar {
                background-color: #2a3947;
                border: none;
                border-radius: 3px;
                max-height: 6px;
                min-height: 6px;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #3d86ee, stop:1 #7cc4ff);
                border-radius: 3px;
            }
        """)

        bayangan = QGraphicsDropShadowEffect(self)
        bayangan.setBlurRadius(32)
        bayangan.setOffset(0, 8)
        bayangan.setColor(QColor(0, 0, 0, 170))
        kartu.setGraphicsEffect(bayangan)
        luar.addWidget(kartu)

        layout = QVBoxLayout(kartu)
        layout.setContentsMargins(44, 36, 44, 22)
        layout.setSpacing(0)
        layout.addStretch(2)

        logo = LogoCostStruct()
        layout.addWidget(logo, alignment=Qt.AlignHCenter)
        layout.addSpacing(16)

        judul = QLabel("CostStruct")
        judul.setObjectName("judul")
        judul.setAlignment(Qt.AlignCenter)
        layout.addWidget(judul)
        layout.addSpacing(4)

        subjudul = QLabel("BIM-Based Quantity Take-Off & Estimasi RAB")
        subjudul.setObjectName("subjudul")
        subjudul.setAlignment(Qt.AlignCenter)
        layout.addWidget(subjudul)

        layout.addStretch(3)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setTextVisible(False)
        layout.addWidget(self.progress)
        layout.addSpacing(8)

        baris_status = QHBoxLayout()
        self.status = QLabel("Memulai...")
        self.status.setObjectName("status")
        self.persen = QLabel("0%")
        self.persen.setObjectName("persen")
        self.persen.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        baris_status.addWidget(self.status)
        baris_status.addStretch()
        baris_status.addWidget(self.persen)
        layout.addLayout(baris_status)
        layout.addSpacing(14)

        footer = QLabel(f"{VERSI_APLIKASI}   •   CostStruct")
        footer.setObjectName("footer")
        footer.setAlignment(Qt.AlignCenter)
        layout.addWidget(footer)

        self.progress.valueChanged.connect(lambda v: self.persen.setText(f"{v}%"))

    def _pusatkan_di_layar(self):
        layar = (self.screen() or QApplication.primaryScreen()).availableGeometry()
        x = layar.x() + (layar.width() - self.width()) // 2
        y = layar.y() + (layar.height() - self.height()) // 2
        self.move(x, y)

    # ------------------------------------------------------------ Animasi
    def showEvent(self, event):
        super().showEvent(event)
        if self._tahap_index == 0 and not self.timer.isActive():
            self._fade(0.0, 1.0, selesai=None)
            # Mulai tahap pertama setelah fade-in hampir selesai
            QTimer.singleShot(DURASI_FADE_MS, self._mulai_loading)

    def _mulai_loading(self):
        self._lanjut_tahap()
        self.timer.start(JEDA_ANTAR_TAHAP_MS)

    def _fade(self, dari, ke, selesai):
        self._anim_fade = QPropertyAnimation(self, b"windowOpacity", self)
        self._anim_fade.setDuration(DURASI_FADE_MS)
        self._anim_fade.setStartValue(dari)
        self._anim_fade.setEndValue(ke)
        self._anim_fade.setEasingCurve(QEasingCurve.InOutQuad)
        if selesai:
            self._anim_fade.finished.connect(selesai)
        self._anim_fade.start()

    def _animasikan_bar(self, target):
        self._anim_bar = QPropertyAnimation(self.progress, b"value", self)
        self._anim_bar.setDuration(DURASI_ANIMASI_BAR_MS)
        self._anim_bar.setStartValue(self.progress.value())
        self._anim_bar.setEndValue(target)
        self._anim_bar.setEasingCurve(QEasingCurve.OutCubic)
        self._anim_bar.start()

    # -------------------------------------------------------------- Logika
    def _lanjut_tahap(self):
        if self._tahap_index >= len(TAHAPAN_LOADING):
            self.timer.stop()
            self._fade(1.0, 0.0, selesai=self._buka_dashboard)
            return

        persen, teks = TAHAPAN_LOADING[self._tahap_index]
        self.status.setText(teks)
        self._animasikan_bar(persen)

        # Tahap pertama sekalian jadi pengecekan nyata: siapkan & pastikan DB bisa diakses.
        if self._tahap_index == 0:
            try:
                siapkan_database()  # idempotent: skema + data master harga
                get_all_proyek()
                from aktivitas import catat, pangkas
                from database.init_db import cadangkan_database
                from lokasi import folder_data

                pangkas()
                catat("aplikasi", f"Aplikasi dibuka ({VERSI_APLIKASI}), folder data: {folder_data()}")
                cadangan = cadangkan_database()
                if cadangan:
                    catat("aplikasi", f"Cadangan database harian dibuat: {cadangan.name}")
            except Exception as e:
                self.timer.stop()
                self.setWindowFlag(Qt.WindowStaysOnTopHint, False)
                self.show()
                from gui.galat import tampilkan_galat
                from lokasi import folder_data

                tampilkan_galat(self, "Database Bermasalah", e, f"Membuka database di {folder_data()}")
                QApplication.quit()
                return

        self._tahap_index += 1

    def _buka_dashboard(self):
        from database.preferensi_repository import muat_preferensi

        try:
            tema.terapkan(QApplication.instance(), muat_preferensi().tema)  # KF-10
        except Exception:
            pass  # tetap pakai tema bawaan bila preferensi tidak terbaca
        self.dashboard = MainWindow()
        self.dashboard.show()
        self.close()


def main():
    from aktivitas import siapkan_log
    from gui.galat import pasang_penangkap_galat, pasang_terjemahan

    siapkan_log()  # KF-15: file log harian di folder data
    app = QApplication(sys.argv)
    app.setApplicationName("CostStruct")
    app.setWindowIcon(tema.ikon_aplikasi())
    pasang_terjemahan(app)  # KNF-6: tombol bawaan Qt berbahasa Indonesia
    pasang_penangkap_galat()  # KF-14 / KNF-4: kesalahan tak terduga tidak menutup aplikasi
    tema.terapkan(app)
    splash = SplashScreen()
    splash.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    multiprocessing.freeze_support()  # validasi IFC memakai proses anak (juga saat dibundel PyInstaller)
    main()
