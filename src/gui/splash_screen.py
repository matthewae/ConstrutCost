"""
Splash screen CostStruct — tampil sebentar saat aplikasi dibuka,
sambil melakukan pengecekan awal (koneksi database) sebelum
masuk ke Dashboard.
"""

import sys

from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QLabel, QProgressBar, QMessageBox
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont

from database.proyek_repository import get_all_proyek
from gui.dashboard_window import DashboardWindow


# Tahapan loading yang ditampilkan ke user.
# Format: (persen_selesai, teks_status)
TAHAPAN_LOADING = [
    (20, "Memeriksa koneksi database..."),
    (55, "Memuat data proyek tersimpan..."),
    (85, "Menyiapkan antarmuka..."),
    (100, "Siap."),
]


class SplashScreen(QWidget):
    """Layar pembuka CostStruct. Frameless, di tengah layar, auto-lanjut ke Dashboard."""

    def __init__(self):
        super().__init__()
        self.dashboard = None  # ditahan sebagai atribut supaya tidak ke-garbage-collect

        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setFixedSize(440, 280)
        self.setStyleSheet("""
            QWidget {
                background-color: #1c2733;
                border-radius: 8px;
            }
            QLabel#judul {
                color: #ffffff;
                font-size: 28px;
                font-weight: 700;
            }
            QLabel#subjudul {
                color: #9fb3c8;
                font-size: 12px;
            }
            QLabel#status {
                color: #cfd8e3;
                font-size: 11px;
            }
            QProgressBar {
                background-color: #2a3947;
                border: none;
                border-radius: 4px;
                height: 6px;
                text-align: center;
            }
            QProgressBar::chunk {
                background-color: #4f9df7;
                border-radius: 4px;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 60, 40, 30)
        layout.setSpacing(6)
        layout.addStretch()

        judul = QLabel("CostStruct")
        judul.setObjectName("judul")
        judul.setAlignment(Qt.AlignCenter)
        layout.addWidget(judul)

        subjudul = QLabel("BIM-Based Quantity Take-Off & Estimasi RAB")
        subjudul.setObjectName("subjudul")
        subjudul.setAlignment(Qt.AlignCenter)
        layout.addWidget(subjudul)

        layout.addStretch()

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setTextVisible(False)
        layout.addWidget(self.progress)

        self.status = QLabel("Memulai...")
        self.status.setObjectName("status")
        self.status.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.status)

        self._pusatkan_di_layar()

        self._tahap_index = 0
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._lanjut_tahap)
        self.timer.start(450)  # jeda antar tahap, ms

    def _pusatkan_di_layar(self):
        layar = QApplication.primaryScreen().geometry()
        x = (layar.width() - self.width()) // 2
        y = (layar.height() - self.height()) // 2
        self.move(x, y)

    def _lanjut_tahap(self):
        if self._tahap_index >= len(TAHAPAN_LOADING):
            self.timer.stop()
            self._buka_dashboard()
            return

        persen, teks = TAHAPAN_LOADING[self._tahap_index]
        self.status.setText(teks)
        self.progress.setValue(persen)

        # Tahap pertama sekalian jadi pengecekan nyata: pastikan DB bisa diakses.
        if self._tahap_index == 0:
            try:
                get_all_proyek()
            except Exception as e:
                self.timer.stop()
                QMessageBox.critical(
                    self, "Database Bermasalah",
                    f"CostStruct tidak bisa mengakses database.\n\n"
                    f"Pastikan sudah menjalankan init_db.py.\n\nDetail: {e}"
                )
                QApplication.quit()
                return

        self._tahap_index += 1

    def _buka_dashboard(self):
        self.dashboard = DashboardWindow()
        self.dashboard.show()
        self.close()


def main():
    app = QApplication(sys.argv)
    splash = SplashScreen()
    splash.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()