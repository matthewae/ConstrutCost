"""
Halaman Export Hasil Estimasi RAB (KF-8, KF-17) untuk CostStruct.
Dibuka dari layar estimasi: pilih format (Excel/PDF), isi dokumen, kolom laporan, dan folder tujuan.
Pilihan terakhir diingat sebagai bawaan export berikutnya (KF-10).

Tampilan memakai tema global (gui/tema.py): tiga kartu angka (Subtotal, PPN, Total RAB),
pilihan format & isi dokumen dua kolom, pratinjau nama file, dan tombol Export yang menyebut
jumlah file yang akan dibuat.
"""

import logging
import traceback
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QAbstractSpinBox,
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QGridLayout,
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

from dataclasses import replace

from database.estimasi_repository import PPN_RATE
from database.proyek_repository import get_proyek
from database.preferensi_repository import folder_export, muat_preferensi, simpan_pilihan_export
from aktivitas import catat
from gui import tema
from gui.galat import pesan_galat, tampilkan_galat
from export_service import (
    KOLOM_OPSIONAL,
    OpsiExport,
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
        self.setMinimumWidth(1000)

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
        self.kartu_subtotal = tema.KartuStat("A. Biaya Langsung")
        self.kartu_btl = tema.KartuStat("B. Biaya Tidak Langsung")
        self.kartu_ppn = tema.KartuStat(f"PPN {PPN_RATE:.0%}")
        self.kartu_total = tema.KartuStat("Total RAB", utama=True)
        for kartu in (self.kartu_subtotal, self.kartu_btl, self.kartu_ppn, self.kartu_total):
            kartu_layout.addWidget(kartu, stretch=1)
        root.addWidget(self.baris_kartu)

        # --- Informasi dokumen ---
        kartu_info = QFrame()
        kartu_info.setObjectName("kartu")
        form = QGridLayout(kartu_info)
        form.setContentsMargins(18, 14, 18, 14)
        form.setHorizontalSpacing(14)
        form.setVerticalSpacing(10)
        form.setColumnStretch(1, 1)
        form.setColumnStretch(3, 1)
        self.edit_nama = QLineEdit(nama_proyek)
        self.edit_nama.textChanged.connect(self._perbarui_nama_file)
        self.edit_lokasi = QLineEdit()
        self.edit_lokasi.setPlaceholderText("Opsional, mis. Kota Bandung, Jawa Barat")
        self.edit_pemilik = QLineEdit()
        self.edit_pemilik.setPlaceholderText("Opsional, mis. nama pemilik rumah atau instansi")
        self.spin_tahun = QSpinBox()
        self.spin_tahun.setRange(2000, 2100)
        self.spin_tahun.setValue(datetime.now().year)
        # KF-9: kop laporan dari info proyek
        info = get_proyek(proyek_id) or {}
        self.edit_lokasi.setText(info.get("lokasi") or "")
        self.edit_pemilik.setText(info.get("pemilik") or "")
        if info.get("tahun_anggaran"):
            self.spin_tahun.setValue(info["tahun_anggaran"])
        self.spin_tahun.setButtonSymbols(QAbstractSpinBox.NoButtons)
        self.spin_tahun.setMaximumWidth(120)
        for i, (teks, w) in enumerate((
            ("Nama pekerjaan", self.edit_nama), ("Lokasi", self.edit_lokasi),
            ("Pemilik / instansi", self.edit_pemilik), ("Tahun anggaran", self.spin_tahun),
        )):
            baris, kol = divmod(i, 2)
            form.addWidget(self._label_form(teks), baris, kol * 2)
            form.addWidget(w, baris, kol * 2 + 1, alignment=Qt.AlignLeft if w is self.spin_tahun else Qt.Alignment())
        root.addWidget(self._bagian("INFORMASI DOKUMEN"))
        root.addWidget(kartu_info)

        # --- Format file & isi dokumen (dua kolom) ---
        self.cek_excel = QCheckBox("Excel (.xlsx)")
        self.cek_pdf = QCheckBox("PDF (.pdf)")
        pref = muat_preferensi()  # KF-10: format laporan & folder default
        self.cek_excel.setChecked(pref.format_excel)
        self.cek_pdf.setChecked(pref.format_pdf)
        self.cek_rekap = QCheckBox("Rekapitulasi biaya")
        self.cek_rinci = QCheckBox("RAB rinci per tipe elemen")
        self.cek_besi = QCheckBox("Kebutuhan besi per diameter")
        self.cek_lantai = QCheckBox("Rekap biaya per lantai")
        self.cek_lantai.setChecked(pref.isi_lantai)
        self.cek_per_lantai = QCheckBox("Rincian per lantai")
        self.cek_per_lantai.setChecked(pref.isi_per_lantai)
        self.cek_detail = QCheckBox("Detail volume per elemen && lantai")
        self.cek_rekap.setChecked(pref.isi_rekap)
        self.cek_rinci.setChecked(pref.isi_rinci)
        self.cek_besi.setChecked(pref.isi_besi)
        self.cek_detail.setChecked(pref.isi_detail)
        for cek in (self.cek_excel, self.cek_pdf):
            cek.setCursor(Qt.PointingHandCursor)
            cek.toggled.connect(self._perbarui_tombol)
            cek.toggled.connect(self._perbarui_nama_file)
        for cek in (self.cek_rekap, self.cek_rinci, self.cek_besi, self.cek_lantai, self.cek_per_lantai, self.cek_detail):
            cek.setCursor(Qt.PointingHandCursor)
        self.combo_orientasi = QComboBox()
        self.combo_orientasi.addItem("PDF tegak (portrait)", "portrait")
        self.combo_orientasi.addItem("PDF mendatar (landscape)", "landscape")
        self.combo_orientasi.setCurrentIndex(1 if pref.orientasi_pdf == "landscape" else 0)
        self.cek_pdf.toggled.connect(self.combo_orientasi.setEnabled)
        self.combo_orientasi.setEnabled(pref.format_pdf)

        # KF-17: kolom laporan. Uraian, volume, satuan, dan jumlah harga selalu ada.
        self.cek_kolom = {}
        for kunci, teks in KOLOM_OPSIONAL.items():
            cek = QCheckBox(teks)
            cek.setCursor(Qt.PointingHandCursor)
            cek.setChecked(kunci in pref.kolom)
            self.cek_kolom[kunci] = cek

        kolom_format = self._kolom_opsi(
            "FORMAT FILE",
            [
                (self.cek_excel, "Rumus aktif, bisa diedit"),
                (self.cek_pdf, "Siap cetak"),
                (self.combo_orientasi, "Orientasi halaman PDF"),
            ],
        )
        kolom_isi = self._kolom_opsi(
            "ISI DOKUMEN",
            [
                (self.cek_rekap, "A, B, PPN, total, terbilang"),
                (self.cek_rinci, "Beton, bekisting, tulangan per tipe"),
                (self.cek_besi, "Berat & batang 12 m per Ø/D"),
                (self.cek_lantai, "Biaya, beton, besi & bahan tiap lantai"),
                (self.cek_per_lantai, "Satu sheet per lantai: struktur, besi Ø, bahan"),
                (self.cek_detail, "Volume tiap elemen dan lantai"),
            ],
        )
        kolom_kolom = self._kolom_opsi(
            "KOLOM LAPORAN",
            [
                (self.cek_kolom["no"], ""),
                (self.cek_kolom["kode"], "Kode analisa HSPK"),
                (self.cek_kolom["harga"], "Jumlah = volume × harga"),
                (self.cek_kolom["bobot"], "Persentase terhadap biaya A"),
                (self.cek_kolom["rumus"], "Jejak rumus (KF-18)"),
            ],
            rapat=True,
        )
        baris_opsi = QHBoxLayout()
        baris_opsi.setSpacing(14)
        baris_opsi.addLayout(kolom_format, stretch=1)
        baris_opsi.addLayout(kolom_isi, stretch=1)
        baris_opsi.addLayout(kolom_kolom, stretch=1)
        root.addLayout(baris_opsi)
        root.addWidget(QLabel(
            "Uraian, volume, satuan, dan jumlah harga selalu ditampilkan. Pilihan ini diingat untuk export berikutnya."
        , objectName="infoKecil"))

        # --- Folder tujuan ---
        folder_default = folder_export(pref)
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
        self.btn_pratinjau = tema.tombol("Pratinjau", "secondary", "file", "Lihat laporan sebelum export (KF-6)")
        self.btn_pratinjau.clicked.connect(self._pratinjau)
        baris_tombol.insertWidget(0, self.btn_pratinjau)
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

    def _kolom_opsi(self, judul_bagian: str, opsi, rapat: bool = False) -> QVBoxLayout:
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
                lay.addSpacing(4 if rapat else 8)
            lay.addWidget(cek)
            if not deskripsi:
                continue
            baris_desk = QHBoxLayout()
            baris_desk.setContentsMargins(0, 0, 0, 0)
            baris_desk.addSpacing(28 if isinstance(cek, QCheckBox) else 2)  # sejajar dengan teks kotak centang
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
            n_pekerjaan = sum(len(k["items"]) for k in kelompok)
            self.label_ringkasan.setText(
                f"{n_pekerjaan} item pekerjaan dalam {len(kelompok)} kategori  •  "
                f"Periksa isi dokumen, pilih format dan kolom, lalu tentukan folder tujuan."
            )
            r = data["ringkasan"]
            self.kartu_subtotal.set_data(tema.format_rupiah(r["langsung"]))
            self.kartu_btl.set_data(tema.format_rupiah(r["tidak_langsung"]))
            self.kartu_ppn.set_data(tema.format_rupiah(r["ppn"]))
            self.kartu_total.set_data(tema.format_rupiah(r["dibulatkan"]), "dibulatkan")
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
        meta = self._meta(data)
        folder = Path(self.edit_folder.text().strip())
        folder.mkdir(parents=True, exist_ok=True)
        opsi = self.opsi()

        tugas = []
        if self.cek_excel.isChecked():
            tugas.append(("Excel", "xlsx", export_excel))
        if self.cek_pdf.isChecked():
            tugas.append(("PDF", "pdf", export_pdf))

        berhasil, gagal = [], []
        for label, ekstensi, fungsi in tugas:
            tujuan = folder / nama_file_default(meta["nama_proyek"], ekstensi)
            try:
                fungsi(tujuan, data, meta, opsi)
                berhasil.append(tujuan)
            except PermissionError as e:
                catat("galat", f"Export {label} gagal: {tujuan} sedang dibuka / akses ditolak", self.proyek_id,
                      detail=repr(e), tingkat="GALAT")
                gagal.append(
                    f"{label}: file '{tujuan.name}' sedang dibuka di program lain atau folder tidak bisa ditulis. "
                    "Tutup file tersebut atau pilih folder lain, lalu coba lagi."
                )
            except Exception as e:  # KF-14: pesan jelas + saran solusi, rincian di log
                pesan, saran = pesan_galat(e)
                catat("galat", f"Export {label} gagal: {pesan}", self.proyek_id,
                      detail="".join(traceback.format_exception(e)), tingkat="GALAT")
                gagal.append(f"{label}: {pesan}" + (f"\n{saran}" if saran else ""))
        if berhasil:
            self._ingat_pilihan()
        return berhasil, gagal

    def _meta(self, data) -> dict:
        return {
            "nama_proyek": self.edit_nama.text().strip() or data["nama_proyek"],
            "lokasi": self.edit_lokasi.text().strip(),
            "pemilik": self.edit_pemilik.text().strip(),
            "tahun": self.spin_tahun.value(),
        }

    def buat_pratinjau(self, folder) -> Path:
        """PDF sementara dengan isi & kolom pilihan saat ini (untuk dialog pratinjau)."""
        data = ambil_data_export(self.proyek_id)
        tujuan = Path(folder) / "pratinjau.pdf"
        export_pdf(tujuan, data, self._meta(data), self.opsi(), catat_log=False)
        return tujuan

    def _pratinjau(self):
        import tempfile

        from gui.pratinjau_dialog import PratinjauDialog

        self._folder_pratinjau = tempfile.TemporaryDirectory(prefix="coststruct_")
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            path = self.buat_pratinjau(self._folder_pratinjau.name)
        except Exception as e:  # KF-14
            QApplication.restoreOverrideCursor()
            tampilkan_galat(self, "Pratinjau Gagal", e, "Pratinjau laporan", self.proyek_id)
            return
        QApplication.restoreOverrideCursor()
        dialog = PratinjauDialog(str(path), self.edit_nama.text().strip() or self.nama_proyek, self)
        dialog.btn_export.setEnabled(self.btn_export.isEnabled())
        if dialog.exec() == QDialog.Accepted:
            self._export()

    def opsi(self) -> OpsiExport:
        return OpsiExport(
            kolom=tuple(k for k, c in self.cek_kolom.items() if c.isChecked()),
            rekap=self.cek_rekap.isChecked(),
            rinci=self.cek_rinci.isChecked(),
            besi=self.cek_besi.isChecked(),
            detail=self.cek_detail.isChecked(),
            lantai=self.cek_lantai.isChecked(),
            per_lantai=self.cek_per_lantai.isChecked(),
            orientasi_pdf=self.combo_orientasi.currentData(),
        )

    def _ingat_pilihan(self):
        """KF-10: pilihan export ini menjadi bawaan berikutnya."""
        o = self.opsi()
        try:
            simpan_pilihan_export(replace(
                muat_preferensi(),
                format_excel=self.cek_excel.isChecked(), format_pdf=self.cek_pdf.isChecked(),
                isi_rekap=o.rekap, isi_rinci=o.rinci, isi_besi=o.besi, isi_detail=o.detail, isi_lantai=o.lantai,
                isi_per_lantai=o.per_lantai,
                kolom_laporan=",".join(o.kolom), orientasi_pdf=o.orientasi_pdf,
                direktori_export=self.edit_folder.text().strip(),
            ))
        except Exception:  # preferensi gagal disimpan tidak membatalkan export
            log.exception("Pilihan export gagal disimpan")

    def _export(self):
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            berhasil, gagal = self.proses_export()
        except Exception as e:
            QApplication.restoreOverrideCursor()
            tampilkan_galat(self, "Export Gagal", e, "Export laporan", self.proyek_id)
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
