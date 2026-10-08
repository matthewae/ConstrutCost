"""
Aksi proyek yang dipakai halaman Daftar Proyek dan Hasil Estimasi:
- KF-7 / UC-06: simpan proyek ke file .coststruct dan buka file proyek.
- KF-9: ubah info proyek (nama, lokasi, pemilik, tahun, file IFC) dan duplikasi proyek.
"""

from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractSpinBox,
    QApplication,
    QCheckBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QInputDialog,
    QLineEdit,
    QMessageBox,
    QSpinBox,
    QVBoxLayout,
)

from database.berkas_proyek import EKSTENSI, BerkasTidakValid, baca_berkas, buka_berkas, duplikat_proyek, simpan_berkas
from database.preferensi_repository import folder_export, folder_ifc, muat_preferensi
from database.proyek_repository import ProyekTidakValid, get_proyek, ubah_info_proyek
from gui import tema
from gui.galat import tampilkan_galat

FILTER = f"File Proyek CostStruct (*{EKSTENSI})"


def _nama_file(nama: str) -> str:
    aman = "".join(c if c.isalnum() or c in " -_" else "_" for c in nama).strip() or "Proyek"
    return f"{aman}{EKSTENSI}"


# ---------------------------------------------------------------- KF-7 simpan / buka


def simpan_file_proyek(parent, proyek_id: int) -> Path | None:
    """UC-06 langkah 1-3: simpan proyek ke file .coststruct (beserta salinan file IFC)."""
    p = get_proyek(proyek_id)
    if p is None:
        return None
    awal = str(Path(folder_export(muat_preferensi())) / _nama_file(p["nama_proyek"]))
    path, _ = QFileDialog.getSaveFileName(parent, "Simpan File Proyek", awal, FILTER)
    if not path:
        return None
    ifc = p.get("path_file_ifc")
    sertakan = bool(ifc and Path(ifc).is_file())
    if sertakan and Path(ifc).stat().st_size > 5 * 1024 * 1024:
        sertakan = tema.tanya(
            parent, "Sertakan File IFC?",
            f"Sertakan salinan model IFC ({Path(ifc).stat().st_size / 1e6:.1f} MB) di dalam file proyek?",
            ya="Sertakan", tidak="Tanpa IFC",
            info="Dengan IFC, proyek bisa dibuka dan dihitung ulang dari IFC di komputer lain.",
        )
    QApplication.setOverrideCursor(Qt.WaitCursor)
    try:
        hasil = simpan_berkas(proyek_id, path, sertakan_ifc=sertakan)
    except (OSError, BerkasTidakValid) as e:  # KF-14
        QApplication.restoreOverrideCursor()
        tampilkan_galat(parent, "Gagal Menyimpan", e, "Simpan file proyek", proyek_id)
        return None
    QApplication.restoreOverrideCursor()
    tema.toast(parent, f"Proyek berhasil disimpan: {hasil.name}")
    return hasil


def buka_file_proyek(parent) -> tuple | None:
    """UC-06 langkah 4-7: buka file .coststruct menjadi proyek di database. Return (id, nama)."""
    path, _ = QFileDialog.getOpenFileName(parent, "Buka File Proyek", folder_ifc(muat_preferensi()), FILTER)
    if not path:
        return None
    try:
        data = baca_berkas(path)
    except BerkasTidakValid as e:
        tampilkan_galat(parent, "File Proyek Tidak Valid", e, f"Buka file proyek {path}")
        return None
    nama = (data.get("proyek") or {}).get("nama_proyek") or Path(path).stem
    info = f"Disimpan {data.get('disimpan', '-')}, {len(data.get('elemen', []))} elemen."
    if data.get("_ada_ifc"):
        info += f" Model IFC akan disalin ke folder {Path(path).parent}."
    if not tema.tanya(parent, "Buka File Proyek", f'Buka proyek "{nama}"?', ya="Buka", info=info):
        return None
    QApplication.setOverrideCursor(Qt.WaitCursor)
    try:
        pid = buka_berkas(path)
    except (OSError, BerkasTidakValid) as e:
        QApplication.restoreOverrideCursor()
        tampilkan_galat(parent, "Gagal Membuka", e, f"Buka file proyek {path}")
        return None
    QApplication.restoreOverrideCursor()
    return pid, nama


# ---------------------------------------------------------------- KF-9 info & duplikat


def duplikat(parent, proyek_id: int) -> tuple | None:
    p = get_proyek(proyek_id)
    if p is None:
        return None
    nama, ok = QInputDialog.getText(parent, "Duplikat Proyek", "Nama proyek baru:", text=f"{p['nama_proyek']} (salinan)")
    if not ok:
        return None
    try:
        pid = duplikat_proyek(proyek_id, nama)
    except BerkasTidakValid as e:
        QMessageBox.warning(parent, "Duplikat Proyek", str(e))
        return None
    return pid, nama.strip()


class InfoProyekDialog(QDialog):
    """KF-9: ubah nama, lokasi, pemilik/instansi, tahun anggaran, dan file IFC proyek."""

    def __init__(self, proyek_id: int, parent=None):
        super().__init__(parent)
        self.proyek_id = proyek_id
        self.ifc_berubah = False
        p = get_proyek(proyek_id) or {}
        self._ifc_lama = p.get("path_file_ifc") or ""
        self.setWindowTitle("Info Proyek")
        self.setModal(True)
        self.setMinimumWidth(620)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(26, 22, 26, 20)
        lay.setSpacing(12)
        lay.addWidget(tema.label("Info Proyek", "judulHalaman"))
        lay.addWidget(tema.label("Lokasi, pemilik, dan tahun anggaran dipakai sebagai kop laporan RAB.", "subjudul", wrap=True))
        f = QFormLayout()
        f.setLabelAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        f.setVerticalSpacing(10)
        f.setHorizontalSpacing(14)
        self.edit_nama = QLineEdit(p.get("nama_proyek") or "")
        self.edit_lokasi = QLineEdit(p.get("lokasi") or "")
        self.edit_lokasi.setPlaceholderText("mis. Kota Bandung, Jawa Barat")
        self.edit_pemilik = QLineEdit(p.get("pemilik") or "")
        self.edit_pemilik.setPlaceholderText("mis. nama pemilik rumah atau instansi")
        self.spin_tahun = QSpinBox()
        self.spin_tahun.setRange(2000, 2100)
        self.spin_tahun.setValue(p.get("tahun_anggaran") or datetime.now().year)
        self.spin_tahun.setButtonSymbols(QAbstractSpinBox.NoButtons)
        self.spin_tahun.setMaximumWidth(120)
        self.edit_ifc = QLineEdit(self._ifc_lama)
        self.edit_ifc.setReadOnly(True)
        pilih = tema.tombol("Ganti File IFC...", "secondary")
        pilih.clicked.connect(self._pilih_ifc)
        baris_ifc = QHBoxLayout()
        baris_ifc.addWidget(self.edit_ifc, stretch=1)
        baris_ifc.addWidget(pilih)
        f.addRow(tema.label("Nama proyek", "formLabel"), self.edit_nama)
        f.addRow(tema.label("Lokasi", "formLabel"), self.edit_lokasi)
        f.addRow(tema.label("Pemilik / instansi", "formLabel"), self.edit_pemilik)
        f.addRow(tema.label("Tahun anggaran", "formLabel"), self.spin_tahun)
        f.addRow(tema.label("File IFC", "formLabel"), baris_ifc)
        lay.addLayout(f)
        self.cek_hitung = QCheckBox("Hitung ulang dari file IFC baru setelah disimpan")
        self.cek_hitung.setChecked(True)
        self.cek_hitung.hide()
        lay.addWidget(self.cek_hitung)
        self.label_galat = tema.label("", "galat", wrap=True)
        self.label_galat.hide()
        lay.addWidget(self.label_galat)
        tombol = QHBoxLayout()
        tombol.addStretch()
        batal = tema.tombol("Batal", "secondary")
        batal.clicked.connect(self.reject)
        simpan = tema.tombol("Simpan", "primary")
        simpan.setDefault(True)
        simpan.clicked.connect(self._simpan)
        tombol.addWidget(batal)
        tombol.addWidget(simpan)
        lay.addLayout(tombol)

    def _pilih_ifc(self):
        awal = str(Path(self.edit_ifc.text()).parent) if self.edit_ifc.text() else folder_ifc(muat_preferensi())
        path, _ = QFileDialog.getOpenFileName(self, "Pilih File IFC", awal, "File IFC (*.ifc)")
        if path:
            self.edit_ifc.setText(path)
            self.cek_hitung.setVisible(path != self._ifc_lama)

    def _simpan(self):
        try:
            ubah_info_proyek(
                self.proyek_id, self.edit_nama.text(), self.edit_lokasi.text(), self.edit_pemilik.text(),
                self.spin_tahun.value(), self.edit_ifc.text().strip() or None,
            )
        except ProyekTidakValid as e:  # KF-14
            self.label_galat.setText(str(e))
            self.label_galat.show()
            return
        self.ifc_berubah = self.edit_ifc.text().strip() != self._ifc_lama and self.cek_hitung.isChecked()
        self.accept()
