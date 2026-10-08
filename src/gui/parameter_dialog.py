"""
Dialog Parameter Aturan (KF-7): asumsi teknis rule engine yang disimpan per proyek, mis. dimensi
fondasi batu kali turunan, sumuran, pekerjaan tanah, dan rasio besi cadangan. Menyimpan
parameter menjalankan ulang rule engine dari elemen tersimpan (file IFC tidak dibaca ulang).
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractSpinBox,
    QDialog,
    QDoubleSpinBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from database.parameter_repository import (
    PARAMETER_EDIT,
    ParameterTidakValid,
    muat_parameter,
    simpan_parameter,
    validasi_parameter,
)
from estimasi_service import hitung_ulang_dari_elemen
from gui import tema
from gui.proses_latar import jalankan_di_latar
from rules.parameter import PARAMETER_DEFAULT


class ParameterDialog(QDialog):
    def __init__(self, proyek_id: int, jumlah_volume_manual: int = 0, parent=None):
        super().__init__(parent)
        self.proyek_id = proyek_id
        self.diubah = False
        self.hasil = None
        self._awal = muat_parameter(proyek_id)
        self.label_galat = tema.label("", "galat", wrap=True)
        self.label_galat.hide()
        self.btn_simpan = tema.tombol("Simpan && Hitung Ulang", "primary", "ulang")
        self.btn_simpan.clicked.connect(self._simpan)
        self.setWindowTitle("Parameter Aturan")
        self.setModal(True)
        self.resize(760, 720)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(26, 22, 26, 20)
        lay.setSpacing(10)
        lay.addWidget(tema.label("Parameter Aturan Proyek", "judulHalaman"))
        lay.addWidget(tema.label(
            "Asumsi teknis yang dipakai rule engine untuk proyek ini. Nilai disimpan bersama proyek "
            "(juga di file .coststruct). Nilai yang berbeda dari bawaan ditandai.",
            "subjudul", wrap=True,
        ))

        gulir = QScrollArea()
        gulir.setWidgetResizable(True)
        gulir.setFrameShape(QFrame.NoFrame)
        isi = QWidget()
        gulir.setWidget(isi)
        v = QVBoxLayout(isi)
        v.setContentsMargins(0, 4, 8, 4)
        v.setSpacing(12)
        self.spin = {}
        self.tanda = {}
        for grup, daftar in PARAMETER_EDIT.items():
            kartu = QFrame()
            kartu.setObjectName("kartu")
            g = QGridLayout(kartu)
            g.setContentsMargins(18, 14, 18, 14)
            g.setHorizontalSpacing(12)
            g.setVerticalSpacing(8)
            g.setColumnStretch(0, 1)
            g.addWidget(tema.label(grup.upper(), "bagian"), 0, 0, 1, 4)
            for i, (k, label, sat, lo, hi, d) in enumerate(daftar, 1):
                sp = QDoubleSpinBox()
                sp.setRange(lo, hi)
                sp.setDecimals(d)
                sp.setSingleStep(10 ** -d if d else 1)
                sp.setButtonSymbols(QAbstractSpinBox.NoButtons)
                sp.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
                sp.setFixedWidth(110)
                sp.setValue(getattr(self._awal, k))
                sp.valueChanged.connect(lambda _=0, k=k: self._berubah(k))
                self.spin[k] = sp
                bawaan = getattr(PARAMETER_DEFAULT, k)
                tanda = tema.label("", "infoKecil")
                tanda.setFixedWidth(130)
                self.tanda[k] = (tanda, bawaan, d)
                g.addWidget(tema.label(label, "formLabel"), i, 0)
                g.addWidget(sp, i, 1)
                satuan = tema.label(sat, "formLabel")
                satuan.setFixedWidth(48)
                g.addWidget(satuan, i, 2)
                g.addWidget(tanda, i, 3)
                self._berubah(k)
            v.addWidget(kartu)
        v.addStretch()
        lay.addWidget(gulir, stretch=1)

        info = "Menyimpan akan menghitung ulang seluruh kuantitas dari elemen tersimpan (file IFC tidak dibaca ulang)."
        if jumlah_volume_manual:
            info += f" {jumlah_volume_manual} volume yang diedit manual akan diganti hasil perhitungan baru."
        lay.addWidget(tema.label(info, "peringatan" if jumlah_volume_manual else "infoKecil", wrap=True))
        lay.addWidget(self.label_galat)

        tombol = QHBoxLayout()
        bawaan = tema.tombol("Kembalikan Semua ke Bawaan", "ghost", "ulang")
        bawaan.clicked.connect(self._bawaan)
        batal = tema.tombol("Batal", "secondary")
        batal.clicked.connect(self.reject)
        tombol.addWidget(bawaan)
        tombol.addStretch()
        tombol.addWidget(batal)
        tombol.addWidget(self.btn_simpan)
        lay.addLayout(tombol)
        self._perbarui_tombol()

    def nilai(self) -> dict:
        return {k: sp.value() for k, sp in self.spin.items()}

    def _berubah(self, k):
        tanda, bawaan, d = self.tanda[k]
        nilai = self.spin[k].value()
        if abs(nilai - bawaan) > 10 ** -(d + 1):
            tanda.setText(f"● bawaan {tema.format_angka(bawaan, d)}")
            tanda.setStyleSheet(f"color: {tema.W['peringatan']};")
        else:
            tanda.setText("bawaan")
            tanda.setStyleSheet("")
        self.label_galat.hide()
        self._perbarui_tombol()

    def _perbarui_tombol(self):
        self.btn_simpan.setEnabled(
            any(abs(sp.value() - getattr(self._awal, k)) > 1e-9 for k, sp in self.spin.items())
        )

    def _bawaan(self):
        for k, sp in self.spin.items():
            sp.setValue(getattr(PARAMETER_DEFAULT, k))

    def _simpan(self):
        try:
            validasi_parameter(self.nilai())
        except ParameterTidakValid as e:  # KF-14
            self.label_galat.setText(str(e))
            self.label_galat.show()
            return
        if not tema.tanya(self, "Hitung Ulang", "Parameter baru akan dipakai untuk menghitung ulang seluruh kuantitas proyek. Lanjutkan?"):
            return
        simpan_parameter(self.proyek_id, self.nilai())
        try:
            self.hasil = jalankan_di_latar(self, "Menghitung ulang kuantitas...", hitung_ulang_dari_elemen, self.proyek_id)
        except Exception as e:
            self.label_galat.setText(f"Parameter tersimpan, tetapi hitung ulang gagal: {e}")
            self.label_galat.show()
            return
        self.diubah = True
        self.accept()
