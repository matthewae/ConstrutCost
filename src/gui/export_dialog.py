"""
Halaman Export Hasil Estimasi RAB (KF-8) untuk CostStruct.
Dibuka dari layar estimasi: pilih format (Excel/PDF), isi dokumen, dan folder tujuan.

Tampilan memakai tema global (gui/tema.py): tiga kartu angka (Subtotal, PPN, Total RAB),
pilihan format & isi dokumen dua kolom, pratinjau nama file, dan tombol Export yang menyebut
jumlah file yang akan dibuat.
"""

import logging
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QAbstractSpinBox,
    QApplication,
    QCheckBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from database.estimasi_repository import PPN_RATE
from database.preferensi_repository import get_pref, set_pref
from gui import tema
from export_service import (
    ambil_data_export,
    export_excel,
    export_pdf,
    kelompokkan,
    nama_file_default,
)

log = logging.getLogger("coststruct.export")


class ExportDialog(QDialog):
    def __init__(self, proyek_id: int, nama_proyek: str, parent=None):
        super().__init__(parent)
        self.proyek_id = proyek_id
        self.nama_proyek = nama_proyek
        self._data_ok = (
            True  # False bila data export gagal dimuat -> tombol Export dimatikan
        )
        self.setWindowTitle("Export RAB")
        self.setModal(True)
        self.setMinimumWidth(780)

        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 22)
        root.setSpacing(14)

        # --- Header ---
        judul = QLabel("Export Hasil Estimasi RAB")
        judul.setObjectName("judulHalaman")
        self.label_ringkasan = QLabel("")
        self.label_ringkasan.setObjectName("subjudul")
        root.addWidget(judul)
        root.addWidget(self.label_ringkasan)

        # --- Kartu angka ringkasan ---
        self.baris_kartu = QWidget()
        kartu_layout = QHBoxLayout(self.baris_kartu)
        kartu_layout.setContentsMargins(0, 0, 0, 0)
        kartu_layout.setSpacing(12)
        self.kartu_subtotal = tema.KartuStat("Subtotal")
        self.kartu_ppn = tema.KartuStat(f"PPN {PPN_RATE:.0%}")
        self.kartu_total = tema.KartuStat("Total RAB", utama=True)
        for kartu in (self.kartu_subtotal, self.kartu_ppn, self.kartu_total):
            kartu_layout.addWidget(kartu, stretch=1)
        root.addWidget(self.baris_kartu)

        # --- Informasi dokumen ---
        kartu_info = QFrame()
        kartu_info.setObjectName("kartu")
        form = QFormLayout(kartu_info)
        form.setContentsMargins(18, 16, 18, 16)
        form.setHorizontalSpacing(18)
        form.setVerticalSpacing(10)
        form.setLabelAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.edit_nama = QLineEdit(nama_proyek)
        self.edit_nama.textChanged.connect(self._perbarui_nama_file)
        self.edit_lokasi = QLineEdit()
        self.edit_lokasi.setPlaceholderText("Opsional, mis. Kota Bandung, Jawa Barat")
        self.spin_tahun = QSpinBox()
        self.spin_tahun.setRange(2000, 2100)
        self.spin_tahun.setValue(datetime.now().year)
        self.spin_tahun.setButtonSymbols(QAbstractSpinBox.NoButtons)
        self.spin_tahun.setMaximumWidth(120)
        form.addRow(self._label_form("Nama pekerjaan"), self.edit_nama)
        form.addRow(self._label_form("Lokasi"), self.edit_lokasi)
        form.addRow(self._label_form("Tahun anggaran"), self.spin_tahun)
        root.addWidget(self._bagian("INFORMASI DOKUMEN"))
        root.addWidget(kartu_info)

        # --- Format file & isi dokumen (dua kolom) ---
        self.cek_excel = QCheckBox("Excel (.xlsx)")
        self.cek_pdf = QCheckBox("PDF (.pdf)")
        self.cek_excel.setChecked(True)
        self.cek_pdf.setChecked(True)
        self.cek_rekap = QCheckBox("Rekapitulasi per kategori")
        self.cek_detail = QCheckBox("Detail volume per elemen && lantai")
        self.cek_rekap.setChecked(True)
        self.cek_detail.setChecked(True)
        for cek in (self.cek_excel, self.cek_pdf):
            cek.setCursor(Qt.PointingHandCursor)
            cek.toggled.connect(self._perbarui_tombol)
            cek.toggled.connect(self._perbarui_nama_file)
        for cek in (self.cek_rekap, self.cek_detail):
            cek.setCursor(Qt.PointingHandCursor)

        kolom_format = self._kolom_opsi(
            "FORMAT FILE",
            [
                (self.cek_excel, "Rumus aktif, bisa diedit"),
                (self.cek_pdf, "Siap cetak"),
            ],
        )
        kolom_isi = self._kolom_opsi(
            "ISI DOKUMEN",
            [
                (self.cek_rekap, "Total tiap kategori pekerjaan"),
                (self.cek_detail, "Rincian volume tiap elemen dan lantai"),
            ],
        )
        baris_opsi = QHBoxLayout()
        baris_opsi.setSpacing(14)
        baris_opsi.addLayout(kolom_format, stretch=1)
        baris_opsi.addLayout(kolom_isi, stretch=1)
        root.addLayout(baris_opsi)

        # --- Folder tujuan ---
        folder_default = get_pref("export_dir", str(Path.home() / "Documents"))
        if not Path(folder_default).exists():
            folder_default = str(Path.home())
        baris_folder = QHBoxLayout()
        baris_folder.setSpacing(10)
        self.edit_folder = QLineEdit(folder_default)
        self.edit_folder.textChanged.connect(self._perbarui_tombol)
        btn_cari = QPushButton("Pilih Folder...")
        btn_cari.setObjectName("btnSecondary")
        btn_cari.setCursor(Qt.PointingHandCursor)
        btn_cari.clicked.connect(self._pilih_folder)
        baris_folder.addWidget(self.edit_folder, stretch=1)
        baris_folder.addWidget(btn_cari)
        root.addWidget(self._bagian("FOLDER TUJUAN"))
        root.addLayout(baris_folder)

        self.label_nama_file = QLabel("")
        self.label_nama_file.setObjectName("namaFile")
        self.label_nama_file.setWordWrap(True)
        root.addWidget(self.label_nama_file)

        # --- Tombol ---
        baris_tombol = QHBoxLayout()
        baris_tombol.setSpacing(10)
        baris_tombol.addStretch()
        btn_batal = QPushButton("Batal")
        btn_batal.setObjectName("btnSecondary")
        btn_batal.setCursor(Qt.PointingHandCursor)
        btn_batal.clicked.connect(self.reject)
        self.btn_export = QPushButton("Export")
        self.btn_export.setObjectName("btnPrimary")
        self.btn_export.setCursor(Qt.PointingHandCursor)
        self.btn_export.setDefault(True)
        self.btn_export.clicked.connect(self._export)
        baris_tombol.addWidget(btn_batal)
        baris_tombol.addWidget(self.btn_export)
        root.addLayout(baris_tombol)

        self._muat_ringkasan()
        self._perbarui_nama_file()
        self._perbarui_tombol()

    # ---------- UI helper ----------

    @staticmethod
    def _bagian(teks: str) -> QLabel:
        label = QLabel(teks)
        label.setObjectName("bagian")
        return label

    @staticmethod
    def _label_form(teks: str) -> QLabel:
        label = QLabel(teks)
        label.setObjectName("formLabel")
        return label

    def _kolom_opsi(self, judul_bagian: str, opsi) -> QVBoxLayout:
        """Satu kolom: judul bagian + kartu berisi kotak centang beserta penjelasan singkat."""
        kolom = QVBoxLayout()
        kolom.setSpacing(8)
        kolom.addWidget(self._bagian(judul_bagian))

        kartu = QFrame()
        kartu.setObjectName("kartu")
        lay = QVBoxLayout(kartu)
        lay.setContentsMargins(18, 14, 18, 14)
        lay.setSpacing(2)
        for i, (cek, deskripsi) in enumerate(opsi):
            if i > 0:
                lay.addSpacing(10)
            lay.addWidget(cek)
            baris_desk = QHBoxLayout()
            baris_desk.setContentsMargins(0, 0, 0, 0)
            baris_desk.addSpacing(28)  # sejajar dengan teks kotak centang
            info = QLabel(deskripsi)
            info.setObjectName("infoKecil")
            baris_desk.addWidget(info)
            baris_desk.addStretch()
            lay.addLayout(baris_desk)
        lay.addStretch()
        kolom.addWidget(kartu, stretch=1)
        return kolom

    def _muat_ringkasan(self):
        try:
            data = ambil_data_export(self.proyek_id)
            kelompok = kelompokkan(data["baris"])
            subtotal = sum(k["total"] for k in kelompok)
            n_pekerjaan = sum(len(k["items"]) for k in kelompok)
            self.label_ringkasan.setText(
                f"{n_pekerjaan} item pekerjaan dalam {len(kelompok)} kategori  •  "
                f"Periksa isi dokumen, pilih format, lalu tentukan folder tujuan."
            )
            self.kartu_subtotal.set_data(tema.format_rupiah(subtotal))
            self.kartu_ppn.set_data(tema.format_rupiah(subtotal * PPN_RATE))
            self.kartu_total.set_data(tema.format_rupiah(subtotal * (1 + PPN_RATE)))
        except Exception as e:
            self._data_ok = False
            self.baris_kartu.setVisible(False)
            self.label_ringkasan.setObjectName("galat")
            self.label_ringkasan.style().unpolish(self.label_ringkasan)
            self.label_ringkasan.style().polish(self.label_ringkasan)
            self.label_ringkasan.setText(str(e))

    def _perbarui_nama_file(self, *_):
        """Pratinjau nama file sesuai nama pekerjaan dan format yang dicentang."""
        nama = self.edit_nama.text().strip() or self.nama_proyek
        daftar = []
        try:
            if self.cek_excel.isChecked():
                daftar.append(nama_file_default(nama, "xlsx"))
            if self.cek_pdf.isChecked():
                daftar.append(nama_file_default(nama, "pdf"))
        except Exception:
            daftar = []
        if daftar:
            self.label_nama_file.setText("Nama file:  " + "   |   ".join(daftar))
        else:
            self.label_nama_file.setText("Pilih minimal satu format file.")

    def _perbarui_tombol(self, *_):
        jumlah_format = int(self.cek_excel.isChecked()) + int(self.cek_pdf.isChecked())
        punya_folder = bool(self.edit_folder.text().strip())
        self.btn_export.setEnabled(self._data_ok and jumlah_format > 0 and punya_folder)
        if jumlah_format > 0:
            self.btn_export.setText(
                "Export" if jumlah_format == 1 else f"Export {jumlah_format} File"
            )
        else:
            self.btn_export.setText("Export")

    def _pilih_folder(self):
        folder = QFileDialog.getExistingDirectory(
            self, "Pilih Folder Tujuan", self.edit_folder.text()
        )
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
        opsi = {
            "rekap": self.cek_rekap.isChecked(),
            "detail": self.cek_detail.isChecked(),
        }

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
                gagal.append(
                    f"{label}: file '{tujuan.name}' sedang dibuka di program lain. Tutup dulu, lalu coba lagi."
                )
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
            kotak.setIcon(QMessageBox.Information)
            kotak.setWindowTitle("Export Berhasil")
            kotak.setText(
                "File berhasil dibuat:\n" + "\n".join(f"- {p.name}" for p in berhasil)
            )
            kotak.setInformativeText(str(berhasil[0].parent))
            btn_folder = kotak.addButton("Buka Folder", QMessageBox.ActionRole)
            kotak.addButton("Tutup", QMessageBox.RejectRole)
            kotak.exec()
            if kotak.clickedButton() is btn_folder:
                QDesktopServices.openUrl(QUrl.fromLocalFile(str(berhasil[0].parent)))
            self.accept()
