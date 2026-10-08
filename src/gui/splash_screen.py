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
from PySide6.QtCore import QEasingCurve, QPointF, QPropertyAnimation, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QLinearGradient, QPainter, QPainterPath, QPen, QRadialGradient

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

    UKURAN = 64

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(self.UKURAN, self.UKURAN)

    def paintEvent(self, event):
        p = QPainter(self)
        tema.gambar_logo(p, self.width())  # warna mengikuti tema (Hitam Kuning: kuning Mandajaya)
        p.end()


class KartuSplash(QFrame):
    """Kartu splash: gradasi warna sidebar, garis aksen kuning di atas, cahaya lembut di belakang logo,
    dan logo Mandajaya samar sebagai watermark di sisi kanan."""

    RADIUS = 20

    def __init__(self, parent=None):
        super().__init__(parent)
        self._watermark = tema.logo_perusahaan(330)

    def paintEvent(self, event):
        w = tema.W
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        area = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        bentuk = QPainterPath()
        bentuk.addRoundedRect(area, self.RADIUS, self.RADIUS)
        p.setClipPath(bentuk)

        dasar = QColor(w["sidebar"])
        grad = QLinearGradient(area.topLeft(), area.bottomRight())
        grad.setColorAt(0.0, dasar.lighter(135) if dasar.lightness() < 128 else dasar)
        grad.setColorAt(1.0, dasar)
        p.fillRect(area, grad)

        cahaya = QRadialGradient(QPointF(90, 70), 260)
        warna = QColor(w["tombol_utama"])
        warna.setAlpha(46)
        cahaya.setColorAt(0.0, warna)
        warna.setAlpha(0)
        cahaya.setColorAt(1.0, warna)
        p.fillRect(area, cahaya)

        if not self._watermark.isNull():
            ukuran = self._watermark.width() / self._watermark.devicePixelRatio()
            p.setOpacity(0.07)
            p.drawPixmap(QPointF(area.right() - ukuran * 0.72, area.bottom() - ukuran * 0.86), self._watermark)
            p.setOpacity(1.0)

        p.fillRect(QRectF(area.left(), area.top(), area.width(), 4), QColor(w["tombol_utama"]))
        p.setClipping(False)
        p.setPen(QPen(QColor(w["sidebar_garis"]), 1))
        p.setBrush(Qt.NoBrush)
        p.drawPath(bentuk)
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
            640 + 2 * self.MARGIN_BAYANGAN, 380 + 2 * self.MARGIN_BAYANGAN
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

        kartu = KartuSplash()
        kartu.setObjectName("kartuSplash")
        w = tema.W
        kartu.setStyleSheet(f"""
            QLabel {{ background: transparent; }}
            QLabel#judul {{ color: {w['sidebar_judul']}; font-size: 34px; font-weight: 800; }}
            QLabel#subjudul {{ color: {w['sidebar_teks']}; font-size: 13px; font-weight: 600; }}
            QLabel#deskripsi {{ color: {w['sidebar_samar']}; font-size: 12px; }}
            QLabel#fitur {{
                color: {w['sidebar_teks_aktif']}; background-color: {w['sidebar_hover']};
                border: 1px solid {w['sidebar_garis']}; border-radius: 11px; padding: 4px 11px;
                font-size: 11px; font-weight: 600;
            }}
            QLabel#status {{ color: {w['sidebar_teks']}; font-size: 11px; }}
            QLabel#persen {{ color: {w['tombol_utama']}; font-size: 11px; font-weight: 700; }}
            QLabel#footer {{ color: {w['sidebar_samar']}; font-size: 10px; }}
            QLabel#perusahaan {{ color: {w['sidebar_judul']}; font-size: 11px; font-weight: 700; }}
            QFrame#garisSplash {{ background-color: {w['sidebar_garis']}; max-height: 1px; min-height: 1px; border: none; }}
            QProgressBar {{
                background-color: {w['sidebar_hover']}; border: none; border-radius: 3px;
                max-height: 6px; min-height: 6px;
            }}
            QProgressBar::chunk {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {w['tombol_utama_tekan']}, stop:1 {w['tombol_utama_hover']});
                border-radius: 3px;
            }}
        """)

        bayangan = QGraphicsDropShadowEffect(self)
        bayangan.setBlurRadius(36)
        bayangan.setOffset(0, 10)
        bayangan.setColor(QColor(0, 0, 0, 170))
        kartu.setGraphicsEffect(bayangan)
        luar.addWidget(kartu)

        layout = QVBoxLayout(kartu)
        layout.setContentsMargins(44, 42, 44, 22)
        layout.setSpacing(0)

        merek = QHBoxLayout()
        merek.setSpacing(18)
        merek.addWidget(LogoCostStruct(), alignment=Qt.AlignVCenter)
        teks = QVBoxLayout()
        teks.setSpacing(2)
        judul = QLabel("CostStruct")
        judul.setObjectName("judul")
        subjudul = QLabel("BIM-Based Quantity Take-Off & Estimasi RAB")
        subjudul.setObjectName("subjudul")
        teks.addWidget(judul)
        teks.addWidget(subjudul)
        merek.addLayout(teks)
        merek.addStretch()
        layout.addLayout(merek)
        layout.addSpacing(18)

        deskripsi = QLabel(
            "Volume pekerjaan dihitung langsung dari model IFC, lalu disusun menjadi RAB\n"
            "dengan analisa harga satuan (AHSP) — per pekerjaan, per tipe elemen, dan per lantai."
        )
        deskripsi.setObjectName("deskripsi")
        layout.addWidget(deskripsi)
        layout.addSpacing(14)

        fitur = QHBoxLayout()
        fitur.setSpacing(8)
        for teks_fitur in ("IFC2x3 · IFC4", "QTO otomatis", "RAB · AHSP", "Excel & PDF"):
            chip = QLabel(teks_fitur)
            chip.setObjectName("fitur")
            fitur.addWidget(chip)
        fitur.addStretch()
        layout.addLayout(fitur)

        layout.addStretch(1)

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
        layout.addSpacing(8)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setTextVisible(False)
        layout.addWidget(self.progress)
        layout.addSpacing(18)

        garis = QFrame()
        garis.setObjectName("garisSplash")
        layout.addWidget(garis)
        layout.addSpacing(12)

        kaki = QHBoxLayout()
        kaki.setSpacing(10)
        kaki.addWidget(tema.LogoPerusahaan(28))
        perusahaan = QLabel(tema.NAMA_PERUSAHAAN)
        perusahaan.setObjectName("perusahaan")
        kaki.addWidget(perusahaan)
        kaki.addStretch()
        footer = QLabel(f"{VERSI_APLIKASI}  ·  Engineering Consultant")
        footer.setObjectName("footer")
        kaki.addWidget(footer)
        layout.addLayout(kaki)

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

                catat("aplikasi", f"Aplikasi dibuka ({VERSI_APLIKASI}), folder data: {folder_data()}")
                try:  # perawatan rutin: kegagalannya tidak boleh menghentikan aplikasi
                    pangkas()
                    cadangan = cadangkan_database()
                    if cadangan:
                        catat("aplikasi", f"Cadangan database harian dibuat: {cadangan.name}")
                except Exception as e:
                    catat("aplikasi", f"Cadangan / pemangkasan log dilewati: {e}", tingkat="PERINGATAN")
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
    try:  # tema pilihan pengguna sudah dipakai sejak splash screen
        from database.preferensi_repository import muat_preferensi

        tema.terapkan(app, muat_preferensi().tema)
    except Exception:  # database belum siap / rusak: tema bawaan, galat ditangani tahap pemeriksaan database
        tema.terapkan(app)
    app.setWindowIcon(tema.ikon_aplikasi())
    splash = SplashScreen()
    splash.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    multiprocessing.freeze_support()  # validasi IFC memakai proses anak (juga saat dibundel PyInstaller)
    main()
