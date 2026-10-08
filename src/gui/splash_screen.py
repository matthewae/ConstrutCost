"""
Splash screen CostStruct — tampil sebentar saat aplikasi dibuka,
sambil melakukan pengecekan awal (koneksi database) sebelum
masuk ke jendela utama.

Tampilan dibuat bersih (minimalis):
- Kartu polos satu warna dengan sudut membulat dan bayangan halus
- Logo, nama aplikasi, dan satu baris keterangan di tengah
- Progress bar tipis yang bergerak halus, teks status, dan nomor versi
- Animasi fade-in saat muncul dan fade-out saat berpindah ke jendela utama
- Pengecekan database tetap nyata, dengan pesan error yang jelas
"""

import multiprocessing
import sys

from PySide6.QtWidgets import (
    QApplication,
    QWidget,
    QVBoxLayout,
    QLabel,
    QProgressBar,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
)
from PySide6.QtCore import QEasingCurve, QPointF, QPropertyAnimation, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen, QRadialGradient

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
    """Logo CostStruct dengan dua cincin tipis berwarna aksen di sekelilingnya."""

    UKURAN = 104
    LOGO = 56

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(self.UKURAN, self.UKURAN)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        tengah = self.UKURAN / 2
        warna = QColor(tema.W["tombol_utama"])
        p.setBrush(Qt.NoBrush)
        for jari, alpha in ((tengah - 1, 26), (tengah - 12, 52)):
            warna.setAlpha(alpha)
            p.setPen(QPen(warna, 1))
            p.drawEllipse(QRectF(tengah - jari, tengah - jari, jari * 2, jari * 2))
        p.translate(tengah - self.LOGO / 2, tengah - self.LOGO / 2)
        tema.gambar_logo(p, self.LOGO)  # warna mengikuti tema
        p.end()


class KartuSplash(QFrame):
    """Kartu splash: satu warna latar dengan pola grid gambar kerja yang samar di tepi
    (memudar ke tengah, sehingga isi tetap bersih), sudut membulat, garis tepi tipis."""

    RADIUS = 18
    GRID = 22

    def paintEvent(self, event):
        w = tema.W
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        area = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        bentuk = QPainterPath()
        bentuk.addRoundedRect(area, self.RADIUS, self.RADIUS)
        dasar = QColor(w["sidebar"])
        p.fillPath(bentuk, dasar)

        p.save()
        p.setClipPath(bentuk)
        garis = QColor(w["sidebar_judul"])
        garis.setAlpha(18 if dasar.lightness() < 128 else 12)  # latar gelap butuh garis sedikit lebih terang
        p.setPen(QPen(garis, 1))
        x = area.left() + self.GRID
        while x < area.right():
            p.drawLine(QPointF(x, area.top()), QPointF(x, area.bottom()))
            x += self.GRID
        y = area.top() + self.GRID
        while y < area.bottom():
            p.drawLine(QPointF(area.left(), y), QPointF(area.right(), y))
            y += self.GRID
        pudar = QRadialGradient(area.center(), max(area.width(), area.height()) * 0.62)
        pudar.setColorAt(0.0, dasar)
        pudar.setColorAt(0.55, dasar)
        transparan = QColor(dasar)
        transparan.setAlpha(0)
        pudar.setColorAt(1.0, transparan)
        p.fillRect(area, pudar)
        p.restore()

        p.setPen(QPen(QColor(w["sidebar_garis"]), 1))
        p.setBrush(Qt.NoBrush)
        p.drawPath(bentuk)
        p.end()


class LangkahMuat(QLabel):
    """Satu tahap pemuatan: titik (abu-abu → kuning) dan nama tahap."""

    def atur(self, keadaan: str) -> None:  # "tunggu" | "jalan" | "selesai"
        w = tema.W
        titik = {"tunggu": w["sidebar_garis"], "jalan": w["tombol_utama"], "selesai": w["tombol_utama"]}[keadaan]
        teks = w["sidebar_samar"] if keadaan == "tunggu" else w["sidebar_teks_aktif"]
        simbol = "✓" if keadaan == "selesai" else "●"
        self.setText(f'<span style="color:{titik}">{simbol}</span>&nbsp;&nbsp;'
                     f'<span style="color:{teks}">{self.property("nama")}</span>')


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
            480 + 2 * self.MARGIN_BAYANGAN, 340 + 2 * self.MARGIN_BAYANGAN
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
        w = tema.W
        kartu.setStyleSheet(f"""
            QLabel {{ background: transparent; }}
            QLabel#judul {{ color: {w['sidebar_judul']}; font-size: 26px; font-weight: 700; }}
            QLabel#subjudul {{ color: {w['sidebar_samar']}; font-size: 12px; }}
            QLabel#langkah {{ font-size: 11px; font-weight: 600; }}
            QLabel#footer {{ color: {w['sidebar_samar']}; font-size: 10px; }}
            QProgressBar {{
                background-color: {w['sidebar_garis']}; border: none; border-radius: 1px;
                max-height: 3px; min-height: 3px;
            }}
            QProgressBar::chunk {{ background-color: {w['tombol_utama']}; border-radius: 1px; }}
        """)

        bayangan = QGraphicsDropShadowEffect(self)
        bayangan.setBlurRadius(30)
        bayangan.setOffset(0, 8)
        bayangan.setColor(QColor(0, 0, 0, 140))
        kartu.setGraphicsEffect(bayangan)
        luar.addWidget(kartu)

        layout = QVBoxLayout(kartu)
        layout.setContentsMargins(56, 0, 56, 22)
        layout.setSpacing(0)
        layout.addStretch(3)

        layout.addWidget(LogoCostStruct(), alignment=Qt.AlignHCenter)
        layout.addSpacing(8)
        judul = QLabel("CostStruct")
        judul.setObjectName("judul")
        judul.setAlignment(Qt.AlignCenter)
        layout.addWidget(judul)
        layout.addSpacing(4)
        subjudul = QLabel("Quantity Take-Off & Estimasi RAB dari model IFC")
        subjudul.setObjectName("subjudul")
        subjudul.setAlignment(Qt.AlignCenter)
        layout.addWidget(subjudul)

        layout.addStretch(2)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setTextVisible(False)
        layout.addWidget(self.progress)
        layout.addSpacing(10)

        # Tiga tahap pemuatan (TAHAPAN_LOADING); teks status lengkap ada di tooltip.
        baris_langkah = QHBoxLayout()
        baris_langkah.setSpacing(22)
        baris_langkah.addStretch()
        self.langkah = []
        for nama in ("Database", "Data proyek", "Antarmuka"):
            l = LangkahMuat()
            l.setObjectName("langkah")
            l.setTextFormat(Qt.RichText)
            l.setProperty("nama", nama)
            l.atur("tunggu")
            self.langkah.append(l)
            baris_langkah.addWidget(l)
        baris_langkah.addStretch()
        layout.addLayout(baris_langkah)
        self.status = QLabel("Memulai...")  # dipakai sebagai tooltip & log; tidak ditampilkan terpisah
        self.status.hide()
        layout.addStretch(1)

        footer = QLabel(VERSI_APLIKASI)
        footer.setObjectName("footer")
        footer.setAlignment(Qt.AlignCenter)
        layout.addWidget(footer)

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
    def _perbarui_langkah(self, aktif: int, teks: str = "") -> None:
        for i, l in enumerate(self.langkah):
            l.atur("selesai" if i < aktif else ("jalan" if i == aktif else "tunggu"))
            l.setToolTip(teks if i == aktif else "")

    def _lanjut_tahap(self):
        if self._tahap_index >= len(TAHAPAN_LOADING):
            self.timer.stop()
            self._fade(1.0, 0.0, selesai=self._buka_dashboard)
            return

        persen, teks = TAHAPAN_LOADING[self._tahap_index]
        self.status.setText(teks)
        self._perbarui_langkah(self._tahap_index, teks)
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
