"""
Halaman Export Hasil Estimasi RAB (KF-8) untuk CostStruct.
Dibuka dari layar estimasi: pilih format (Excel/PDF), isi dokumen, dan folder tujuan.
"""

import logging
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QDialog, QFileDialog, QFormLayout, QFrame, QHBoxLayout, QLabel,
    QLineEdit, QMessageBox, QPushButton, QSpinBox, QVBoxLayout
)

from database.estimasi_repository import PPN_RATE
from database.preferensi_repository import get_pref, set_pref
from export_service import ambil_data_export, export_excel, export_pdf, kelompokkan, nama_file_default

log = logging.getLogger("coststruct.export")

STYLE_SHEET = """
QWidget { background-color: #182430; color: #e4ebf2; font-family: "Segoe UI", sans-serif; font-size: 13px; }
QLabel#judulApp { font-size: 18px; font-weight: 700; color: #ffffff; }
QLabel#subjudulApp { color: #7d92a8; font-size: 12px; }
QLabel#bagian { color: #7d92a8; font-size: 11px; font-weight: 600; }
QLabel#infoKecil { color: #7d92a8; font-size: 11px; }
QFrame#kartu { background-color: #1c2733; border: 1px solid #2a3947; border-radius: 10px; }
QLineEdit, QSpinBox {
    background-color: #223142; border: 1px solid #2f4356; border-radius: 4px; padding: 6px 8px; color: #e4ebf2;
}
QLineEdit:focus, QSpinBox:focus { border: 1px solid #4f9df7; }
QCheckBox { spacing: 8px; }
QPushButton { border-radius: 6px; padding: 9px 18px; font-weight: 600; }
QPushButton#btnPrimary { background-color: #4f9df7; color: #0c1a26; }
QPushButton#btnPrimary:hover { background-color: #6bacf9; }
QPushButton#btnPrimary:disabled { background-color: #2f4356; color: #7d92a8; }
QPushButton#btnSecondary { background-color: #223142; color: #e4ebf2; border: 1px solid #2f4356; }
QPushButton#btnSecondary:hover { background-color: #2a3947; }
"""


def format_rupiah(nilai: float) -> str:
    return "Rp " + f"{nilai:,.0f}".replace(",", ".")


class ExportDialog(QDialog):
    def __init__(self, proyek_id: int, nama_proyek: str, parent=None):
        super().__init__(parent)
        self.proyek_id = proyek_id
        self.setWindowTitle("Export RAB")
        self.setModal(True)
        self.setMinimumWidth(560)
        self.setStyleSheet(STYLE_SHEET)

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(14)

        judul = QLabel("Export Hasil Estimasi RAB")
        judul.setObjectName("judulApp")
        self.label_ringkasan = QLabel("")
        self.label_ringkasan.setObjectName("subjudulApp")
        root.addWidget(judul)
        root.addWidget(self.label_ringkasan)

        # --- Informasi dokumen ---
        kartu_info = QFrame()
        kartu_info.setObjectName("kartu")
        form = QFormLayout(kartu_info)
        form.setContentsMargins(16, 14, 16, 14)
        form.setSpacing(10)
        self.edit_nama = QLineEdit(nama_proyek)
        self.edit_lokasi = QLineEdit()
        self.edit_lokasi.setPlaceholderText("Opsional, mis. Kota Bandung, Jawa Barat")
        self.spin_tahun = QSpinBox()
        self.spin_tahun.setRange(2000, 2100)
        self.spin_tahun.setValue(datetime.now().year)
        form.addRow("Nama pekerjaan", self.edit_nama)
        form.addRow("Lokasi", self.edit_lokasi)
        form.addRow("Tahun anggaran", self.spin_tahun)
        root.addWidget(self._bagian("INFORMASI DOKUMEN"))
        root.addWidget(kartu_info)

        # --- Format & isi ---
        kartu_opsi = QFrame()
        kartu_opsi.setObjectName("kartu")
        lay_opsi = QVBoxLayout(kartu_opsi)
        lay_opsi.setContentsMargins(16, 14, 16, 14)
        lay_opsi.setSpacing(8)
        self.cek_excel = QCheckBox("Excel (.xlsx) - rumus aktif, bisa diedit")
        self.cek_pdf = QCheckBox("PDF (.pdf) - siap cetak")
        self.cek_excel.setChecked(True)
        self.cek_pdf.setChecked(True)
        self.cek_rekap = QCheckBox("Sertakan rekapitulasi per kategori")
        self.cek_detail = QCheckBox("Sertakan detail volume per elemen & lantai")
        self.cek_rekap.setChecked(True)
        self.cek_detail.setChecked(True)
        for cek in (self.cek_excel, self.cek_pdf):
            cek.toggled.connect(self._perbarui_tombol)
            lay_opsi.addWidget(cek)
        lay_opsi.addSpacing(6)
        lay_opsi.addWidget(self.cek_rekap)
        lay_opsi.addWidget(self.cek_detail)
        root.addWidget(self._bagian("FORMAT & ISI"))
        root.addWidget(kartu_opsi)

        # --- Folder tujuan ---
        folder_default = get_pref("export_dir", str(Path.home() / "Documents"))
        if not Path(folder_default).exists():
            folder_default = str(Path.home())
        baris_folder = QHBoxLayout()
        self.edit_folder = QLineEdit(folder_default)
        self.edit_folder.textChanged.connect(self._perbarui_tombol)
        btn_cari = QPushButton("Pilih...")
        btn_cari.setObjectName("btnSecondary")
        btn_cari.clicked.connect(self._pilih_folder)
        baris_folder.addWidget(self.edit_folder, stretch=1)
        baris_folder.addWidget(btn_cari)
        root.addWidget(self._bagian("FOLDER TUJUAN"))
        root.addLayout(baris_folder)
        info = QLabel(f"Nama file: {nama_file_default(nama_proyek, 'xlsx')} / .pdf")
        info.setObjectName("infoKecil")
        root.addWidget(info)

        # --- Tombol ---
        baris_tombol = QHBoxLayout()
        baris_tombol.addStretch()
        btn_batal = QPushButton("Batal")
        btn_batal.setObjectName("btnSecondary")
        btn_batal.clicked.connect(self.reject)
        self.btn_export = QPushButton("Export")
        self.btn_export.setObjectName("btnPrimary")
        self.btn_export.setDefault(True)
        self.btn_export.clicked.connect(self._export)
        baris_tombol.addWidget(btn_batal)
        baris_tombol.addWidget(self.btn_export)
        root.addLayout(baris_tombol)

        self._muat_ringkasan()
        self._perbarui_tombol()

    # ---------- UI helper ----------

    @staticmethod
    def _bagian(teks: str) -> QLabel:
        label = QLabel(teks)
        label.setObjectName("bagian")
        return label

    def _muat_ringkasan(self):
        try:
            data = ambil_data_export(self.proyek_id)
            kelompok = kelompokkan(data["baris"])
            subtotal = sum(k["total"] for k in kelompok)
            n_pekerjaan = sum(len(k["items"]) for k in kelompok)
            self.label_ringkasan.setText(
                f"{n_pekerjaan} item pekerjaan dalam {len(kelompok)} kategori  |  "
                f"Subtotal {format_rupiah(subtotal)}  |  Total + PPN {PPN_RATE:.0%}: "
                f"{format_rupiah(subtotal * (1 + PPN_RATE))}"
            )
        except Exception as e:
            self.label_ringkasan.setText(str(e))
            self.btn_export.setEnabled(False)

    def _perbarui_tombol(self):
        ada_format = self.cek_excel.isChecked() or self.cek_pdf.isChecked()
        self.btn_export.setEnabled(ada_format and bool(self.edit_folder.text().strip()))

    def _pilih_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Pilih Folder Tujuan", self.edit_folder.text())
        if folder:
            self.edit_folder.setText(folder)

    # ---------- Logika export (terpisah dari pesan dialog agar bisa diuji) ----------

    def proses_export(self):
        """Return (daftar_file_berhasil, daftar_pesan_gagal)."""
        data = ambil_data_export(self.proyek_id)
        meta = {
            "nama_proyek": self.edit_nama.text().strip() or data["nama_proyek"],
            "lokasi": self.edit_lokasi.text().strip(),
            "tahun": self.spin_tahun.value(),
        }
        folder = Path(self.edit_folder.text().strip())
        folder.mkdir(parents=True, exist_ok=True)
        opsi = {"rekap": self.cek_rekap.isChecked(), "detail": self.cek_detail.isChecked()}

        tugas = []
        if self.cek_excel.isChecked():
            tugas.append(("Excel", "xlsx", export_excel))
        if self.cek_pdf.isChecked():
            tugas.append(("PDF", "pdf", export_pdf))

        berhasil, gagal = [], []
        for label, ekstensi, fungsi in tugas:
            tujuan = folder / nama_file_default(meta["nama_proyek"], ekstensi)
            try:
                fungsi(tujuan, data, meta, **opsi)
                berhasil.append(tujuan)
            except PermissionError:
                gagal.append(f"{label}: file '{tujuan.name}' sedang dibuka di program lain. Tutup dulu, lalu coba lagi.")
            except Exception as e:  # KF-14: pesan jelas bila ada kesalahan
                log.exception("Export %s gagal", label)
                gagal.append(f"{label}: {e}")
        if berhasil:
            set_pref("export_dir", str(folder))
        return berhasil, gagal

    def _export(self):
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            berhasil, gagal = self.proses_export()
        except Exception as e:
            QApplication.restoreOverrideCursor()
            QMessageBox.critical(self, "Export Gagal", str(e))
            return
        QApplication.restoreOverrideCursor()

        if gagal:
            QMessageBox.warning(self, "Sebagian Gagal", "\n\n".join(gagal))
        if berhasil:
            kotak = QMessageBox(self)
            kotak.setWindowTitle("Export Berhasil")
            kotak.setText("File berhasil dibuat:\n" + "\n".join(f"- {p.name}" for p in berhasil))
            kotak.setInformativeText(str(berhasil[0].parent))
            btn_folder = kotak.addButton("Buka Folder", QMessageBox.ActionRole)
            kotak.addButton("Tutup", QMessageBox.RejectRole)
            kotak.exec()
            if kotak.clickedButton() is btn_folder:
                QDesktopServices.openUrl(QUrl.fromLocalFile(str(berhasil[0].parent)))
            self.accept()
