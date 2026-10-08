"""
Dialog Ubah Dimensi Elemen (KF-19 Recalculate QTO, UC-03 langkah 7-12).

Pengguna mengubah dimensi utama (mis. panjang & lebar pelat); dimensi turunan (luas, volume,
keliling) ikut dihitung dengan asumsi bentuk reguler. Untuk elemen yang bentuknya tidak reguler,
dimensi turunan bisa diisi langsung. Setelah konfirmasi, rule engine dijalankan ulang untuk elemen
ini saja lalu subtotal dan total RAB diperbarui.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractSpinBox,
    QDialog,
    QDoubleSpinBox,
    QGridLayout,
    QHBoxLayout,
    QMessageBox,
    QVBoxLayout,
)

from estimasi_service import hitung_ulang_elemen
from gui import tema
from klasifikasi import LABEL, ElementType
from rules.dimensi import BOLEH_NOL, SATUAN, DimensiTidakValid, kolom_dimensi, label, turunkan_dari

TEKS_KONFIRMASI = "Perubahan dimensi akan memicu kalkulasi ulang QTO. Lanjutkan?"


def _desimal(kunci: str) -> int:
    return 2 if kunci == "kemiringan" else 3


class SpinDimensi(QDoubleSpinBox):
    """Spin box dimensi: tanpa tombol panah, roda mouse tidak mengubah nilai."""

    def __init__(self, kunci: str, nilai):
        super().__init__()
        self.kunci = kunci
        self.setDecimals(_desimal(kunci))
        self.setRange(0, 89.99 if kunci == "kemiringan" else 1_000_000)
        self.setButtonSymbols(QAbstractSpinBox.NoButtons)
        self.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.setKeyboardTracking(False)
        self.setFixedWidth(150)
        if kunci not in BOLEH_NOL:
            self.setSpecialValueText("–")  # 0 = belum ada nilai
        self.setValue(nilai or 0.0)

    def wheelEvent(self, event):
        event.ignore()

    def focusInEvent(self, event):
        super().focusInEvent(event)
        if self.specialValueText() and self.value() == self.minimum():
            self.lineEdit().clear()  # isian kosong siap diketik, bukan tanda "–"


class DimensiDialog(QDialog):
    def __init__(self, elemen: dict, jumlah_volume_manual: int = 0, parent=None):
        super().__init__(parent)
        self.elemen = elemen
        self.kelas = ElementType(elemen["kelas"])
        self.primer, self.turunan = kolom_dimensi(self.kelas)
        self.hasil = None
        self._turunan_otomatis = {}  # kunci -> nilai presisi penuh hasil turunkan()

        self.setWindowTitle("Ubah Dimensi Elemen")
        self.setModal(True)
        self.setMinimumWidth(560)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(26, 22, 26, 20)
        lay.setSpacing(12)
        info = [LABEL.get(self.kelas, self.kelas.value), elemen.get("nama") or "-"]
        if elemen.get("lantai"):
            info.append(elemen["lantai"])
        lay.addWidget(tema.kepala_dialog("Ubah Dimensi Elemen", "  ·  ".join(info), "dimensi")[0])

        self.spin = {}
        lay.addWidget(tema.label("DIMENSI UTAMA", "bagian"))
        lay.addLayout(self._grid(self.primer))
        lay.addWidget(tema.garis())
        lay.addWidget(tema.label("DIMENSI TURUNAN", "bagian"))
        lay.addLayout(self._grid(self.turunan))
        lay.addWidget(
            tema.label(
                "Dimensi turunan dihitung otomatis dari dimensi utama dengan asumsi bentuk reguler. "
                "Bila bentuk elemen tidak reguler (mis. pelat berbentuk L), isi langsung nilainya.",
                "infoKecil", wrap=True,
            )
        )
        if jumlah_volume_manual:
            lay.addWidget(
                tema.label(
                    f"{jumlah_volume_manual} volume pekerjaan yang diedit manual pada elemen ini akan "
                    "diganti hasil perhitungan ulang.",
                    "peringatan", wrap=True,
                )
            )
        self.label_galat = tema.label("", "galat", wrap=True)
        self.label_galat.hide()
        lay.addWidget(self.label_galat)

        tombol = QHBoxLayout()
        self.btn_semula = tema.tombol("Kembalikan Nilai Semula", "ghost", "ulang")
        self.btn_semula.clicked.connect(self._semula)
        batal = tema.tombol("Batal", "secondary")
        batal.clicked.connect(self.reject)
        self.btn_ok = tema.tombol("Hitung Ulang QTO", "primary", "ulang")
        self.btn_ok.setDefault(True)
        self.btn_ok.clicked.connect(self._ok)
        tombol.addWidget(self.btn_semula)
        tombol.addStretch()
        tombol.addWidget(batal)
        tombol.addWidget(self.btn_ok)
        lay.addLayout(tombol)

        for k in self.primer:
            self.spin[k].valueChanged.connect(self._primer_berubah)
        for k in self.turunan:
            self.spin[k].valueChanged.connect(lambda _, k=k: self._turunan_berubah(k))
        self._perbarui_tombol()
        if self.primer:
            self.spin[self.primer[0]].setFocus()
            self.spin[self.primer[0]].selectAll()

    # ---------------------------------------------------------------- tata letak

    def _grid(self, kunci_list) -> QGridLayout:
        g = QGridLayout()
        g.setHorizontalSpacing(12)
        g.setVerticalSpacing(8)
        g.setColumnStretch(0, 1)
        for i, k in enumerate(kunci_list):
            asli = self.elemen.get(k)
            sp = SpinDimensi(k, asli)
            self.spin[k] = sp
            g.addWidget(tema.label(label(self.kelas, k), "formLabel"), i, 0)
            g.addWidget(sp, i, 1)
            satuan = tema.label(SATUAN[k], "formLabel")
            satuan.setFixedWidth(22)
            g.addWidget(satuan, i, 2)
            semula = "semula –" if asli is None else f"semula {tema.format_angka(asli, _desimal(k))}"
            info = tema.label(semula, "infoKecil")
            info.setFixedWidth(110)
            g.addWidget(info, i, 3)
        return g

    # ---------------------------------------------------------------- perilaku

    def _nilai_form(self) -> dict:
        """Nilai di form; 0 pada dimensi yang tidak boleh nol berarti belum diisi."""
        return {
            k: (sp.value() if sp.value() > 0 or k in BOLEH_NOL else None) for k, sp in self.spin.items()
        }

    def _primer_berubah(self, *_):
        self._hitung_turunan([k for k in self.primer if k in self._berubah()])

    def _hitung_turunan(self, diubah, pulihkan: bool = True):
        self.label_galat.hide()
        try:
            hasil = turunkan_dari(self.kelas, self._nilai_form(), diubah)
        except DimensiTidakValid as e:
            self._galat(str(e))
            return
        # turunan yang tidak lagi terpengaruh (dimensi utama dikembalikan) kembali ke nilai semula
        for k in [k for k in self._turunan_otomatis if pulihkan and k not in hasil]:
            self._isi(k, self.elemen.get(k) or 0.0)
            del self._turunan_otomatis[k]
        for k, v in hasil.items():
            if k in self.spin:
                self._isi(k, v)
                self._turunan_otomatis[k] = v
        self._perbarui_tombol()

    def _isi(self, kunci: str, nilai: float):
        sp = self.spin[kunci]
        sp.blockSignals(True)
        sp.setValue(nilai)
        sp.blockSignals(False)

    def _turunan_berubah(self, kunci: str):
        self._turunan_otomatis.pop(kunci, None)  # diisi langsung oleh pengguna
        if kunci == "luas":  # pelat / atap / dinding: volume = luas x tebal
            self._hitung_turunan(["luas"], pulihkan=False)
            return
        self.label_galat.hide()
        self._perbarui_tombol()

    def _berubah(self) -> dict:
        """Dimensi yang nilainya berbeda dari semula (presisi tampilan)."""
        out = {}
        for k, v in self._nilai_form().items():
            asli = self.elemen.get(k)
            if v is None:
                continue
            if asli is not None and round(v, _desimal(k)) == round(asli, _desimal(k)):
                continue
            if asli is None and v == 0:
                continue
            otomatis = self._turunan_otomatis.get(k)
            out[k] = otomatis if otomatis is not None and round(otomatis, _desimal(k)) == round(v, _desimal(k)) else v
        return out

    def _perbarui_tombol(self):
        ada = bool(self._berubah())
        self.btn_ok.setEnabled(ada and self.label_galat.isHidden())
        self.btn_semula.setEnabled(ada)

    def _semula(self):
        for k, sp in self.spin.items():
            sp.blockSignals(True)
            sp.setValue(self.elemen.get(k) or 0.0)
            sp.blockSignals(False)
        self._turunan_otomatis.clear()
        self.label_galat.hide()
        self._perbarui_tombol()

    def _galat(self, teks: str):
        self.label_galat.setText(teks)
        self.label_galat.show()
        self.btn_ok.setEnabled(False)

    def _ok(self):
        """UC-03 langkah 9-12: konfirmasi, validasi, simpan, hitung ulang."""
        dimensi = self._berubah()
        if not dimensi:
            return
        kotak = QMessageBox(self)
        kotak.setIcon(QMessageBox.Question)
        kotak.setWindowTitle("Hitung Ulang QTO")
        kotak.setText(TEKS_KONFIRMASI)
        kotak.setInformativeText(
            "Kuantitas dan biaya pekerjaan elemen ini dihitung ulang dari dimensi baru. "
            "Elemen lain tidak berubah."
        )
        btn_ya = kotak.addButton("Ya, Lanjutkan", QMessageBox.AcceptRole)
        kotak.addButton("Batal", QMessageBox.RejectRole)
        kotak.setDefaultButton(btn_ya)
        kotak.exec()
        if kotak.clickedButton() is not btn_ya:
            return
        try:
            self.hasil = hitung_ulang_elemen(self.elemen["id"], dimensi)
        except DimensiTidakValid as e:  # UC-03 skenario alternatif A
            self._galat(str(e))
            return
        self.accept()
