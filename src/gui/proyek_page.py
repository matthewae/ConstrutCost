"""
Halaman Daftar Proyek (KF-7, KF-9) dan pintu masuk import file IFC (KF-1 / UC-01).

Alur import: pilih / seret file .ifc -> validasi (proses terpisah) -> ringkasan & konfirmasi ->
parsing + rule engine di latar dengan progress bar -> halaman hasil estimasi.
"""

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLineEdit,
    QMenu,
    QMessageBox,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from database.harga_repository import jumlah_estimasi_kedaluwarsa, terapkan_ke_estimasi
from database.preferensi_repository import folder_ifc, muat_preferensi
from database.proyek_repository import create_proyek, delete_proyek, get_all_proyek, get_proyek
from estimasi_service import jalankan_estimasi
from aktivitas import catat
from gui import tema
from gui.galat import tampilkan_galat
from gui.aksi_proyek import InfoProyekDialog, buka_file_proyek, duplikat, simpan_file_proyek
from gui.import_dialog import RingkasanImportDialog, tampilkan_hasil_proses
from gui.proses_latar import jalankan_di_latar
from ifc_reader import FileIFCTidakValid, buka_dan_validasi

KOL_NAMA, KOL_FILE, KOL_ELEMEN, KOL_TOTAL, KOL_DIUBAH = range(5)


class ProyekPage(QWidget):
    minta_buka = Signal(int, str)  # proyek_id, nama

    HAL_TABEL, HAL_KOSONG, HAL_TIDAK_ADA = range(3)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("halaman")
        self._semua = []

        root = QVBoxLayout(self)
        root.setContentsMargins(32, 26, 32, 22)
        root.setSpacing(16)

        # --- Header ---
        kepala = QHBoxLayout()
        kol, _, _ = tema.header_halaman(
            "Daftar Proyek", "Setiap proyek berisi satu model IFC beserta hasil QTO dan RAB-nya."
        )
        kepala.addLayout(kol)
        kepala.addStretch()
        self.btn_import = tema.tombol(
            "Import File IFC", "primary", "tambah",
            "Buat proyek baru dari file IFC (Ctrl+N). File .ifc juga bisa diseret ke jendela ini.",
        )
        self.btn_import.clicked.connect(lambda: self.import_ifc())
        self.btn_buka_file = tema.tombol(
            "Buka File Proyek", "secondary", "file", "Buka proyek dari file .coststruct (Ctrl+O)",
        )
        self.btn_buka_file.clicked.connect(self.buka_file)
        kepala.addWidget(self.btn_buka_file, alignment=Qt.AlignTop)
        kepala.addWidget(self.btn_import, alignment=Qt.AlignTop)
        root.addLayout(kepala)

        self.banner = tema.Banner("info")
        root.addWidget(self.banner)

        # --- Kartu ringkasan ---
        self.baris_stat = QWidget()
        stat = QHBoxLayout(self.baris_stat)
        stat.setContentsMargins(0, 0, 0, 0)
        stat.setSpacing(14)
        self.stat_total = tema.KartuStat("Total Proyek")
        self.stat_nilai = tema.KartuStat("Nilai RAB Semua Proyek", utama=True)
        self.stat_terakhir = tema.KartuStat("Terakhir Diubah")
        for k in (self.stat_total, self.stat_nilai, self.stat_terakhir):
            stat.addWidget(k, stretch=1)
        root.addWidget(self.baris_stat)

        # --- Pencarian ---
        self.baris_cari = QWidget()
        cari = QHBoxLayout(self.baris_cari)
        cari.setContentsMargins(0, 0, 0, 0)
        self.kolom_cari = QLineEdit()
        self.kolom_cari.setPlaceholderText("Cari nama proyek atau file IFC...   (Ctrl+F)")
        self.kolom_cari.setClearButtonEnabled(True)
        self.kolom_cari.textChanged.connect(self._terapkan_filter)
        self.label_jumlah = tema.label("", "subjudul")
        cari.addWidget(self.kolom_cari, stretch=1)
        cari.addSpacing(10)
        cari.addWidget(self.label_jumlah)
        root.addWidget(self.baris_cari)

        # --- Konten ---
        self.stack = QStackedWidget()
        root.addWidget(self.stack, stretch=1)

        self.tabel = QTableWidget()
        tema.siapkan_tabel(
            self.tabel,
            ["NAMA PROYEK", "FILE IFC", "ELEMEN", "TOTAL RAB (TERMASUK PPN)", "TERAKHIR DIUBAH"],
            rata_kanan=(KOL_ELEMEN, KOL_TOTAL),
            tinggi_baris=50,
        )
        tema.atur_lebar(self.tabel, KOL_NAMA, isi_konten=(KOL_FILE, KOL_ELEMEN, KOL_TOTAL, KOL_DIUBAH))
        self.tabel.setSortingEnabled(True)
        self.tabel.itemSelectionChanged.connect(self._perbarui_tombol)
        self.tabel.cellDoubleClicked.connect(lambda *_: self.buka_terpilih())
        self.tabel.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tabel.customContextMenuRequested.connect(self._menu_konteks)
        self.stack.addWidget(self.tabel)

        self.stack.addWidget(
            tema.KondisiKosong(
                "Belum ada proyek",
                "Mulai dengan mengimpor model BIM berformat IFC (IFC2x3 atau IFC4). "
                "Anda juga bisa menyeret file .ifc langsung ke jendela ini.",
                "Import File IFC",
                lambda: self.import_ifc(),
                simbol="file",
            )
        )
        self.kosong_cari = tema.KondisiKosong("Proyek tidak ditemukan", "", simbol="file")
        self.stack.addWidget(self.kosong_cari)

        # --- Aksi bawah ---
        bawah = QHBoxLayout()
        bawah.addWidget(tema.label("Klik dua kali pada proyek untuk membukanya.", "petunjuk"))
        bawah.addStretch()
        self.btn_hapus = tema.tombol("Hapus", "danger")
        self.btn_hapus.clicked.connect(self.hapus_terpilih)
        self.btn_buka = tema.tombol("Buka Proyek", "secondary")
        self.btn_buka.clicked.connect(self.buka_terpilih)
        bawah.addWidget(self.btn_hapus)
        bawah.addWidget(self.btn_buka)
        root.addLayout(bawah)

        QShortcut(QKeySequence("Ctrl+F"), self, activated=self._fokus_cari)
        QShortcut(QKeySequence.Open, self, activated=self.buka_file)
        QShortcut(QKeySequence(Qt.Key_Delete), self.tabel, activated=self.hapus_terpilih)
        QShortcut(QKeySequence(Qt.Key_Return), self.tabel, activated=self.buka_terpilih)

        self.muat()

    # ---------------------------------------------------------------- data

    def muat(self):
        self._semua = get_all_proyek()
        ada = bool(self._semua)
        self.baris_stat.setVisible(ada)
        self.baris_cari.setVisible(ada)

        total_nilai = sum(p["total_rab"] for p in self._semua)
        dengan_ifc = sum(1 for p in self._semua if p["path_file_ifc"])
        self.stat_total.set_data(str(len(self._semua)), f"{dengan_ifc} proyek dengan file IFC")
        self.stat_nilai.set_data(tema.format_rupiah(total_nilai), "termasuk PPN 11%")
        if self._semua:
            terbaru = max(self._semua, key=lambda p: str(p["tanggal_diubah"] or ""))
            self.stat_terakhir.set_data(_tanggal(terbaru["tanggal_diubah"]), terbaru["nama_proyek"])

        n = jumlah_estimasi_kedaluwarsa() if ada else 0
        if n:
            self.banner.tampilkan(
                f"Harga satuan telah berubah. {n} baris estimasi belum memakai harga terbaru.",
                "Terapkan Harga Terbaru",
                self._terapkan_harga,
            )
        else:
            self.banner.hide()
        self._terapkan_filter()

    def _terapkan_harga(self):
        n = terapkan_ke_estimasi()
        self.muat()
        tema.toast(self, f"Harga terbaru diterapkan pada {n} baris estimasi")

    def _terapkan_filter(self):
        if not self._semua:
            self.tabel.setRowCount(0)
            self.stack.setCurrentIndex(self.HAL_KOSONG)
            self._perbarui_tombol()
            return
        kata = self.kolom_cari.text().strip().lower()
        hasil = [
            p for p in self._semua
            if not kata or kata in p["nama_proyek"].lower() or kata in (p["path_file_ifc"] or "").lower()
        ]
        self.tabel.setSortingEnabled(False)
        self.tabel.setRowCount(len(hasil))
        for r, p in enumerate(hasil):
            nama = tema.sel(p["nama_proyek"], tebal=True, data=p["id"])
            path = p["path_file_ifc"]
            file = tema.sel(Path(path).name if path else "-", warna=tema.W["teks_redup"], tooltip=path or "Belum ada file IFC")
            if path and not Path(path).exists():
                file.setForeground(QColor(tema.W["peringatan"]))
                file.setToolTip(f"File tidak ditemukan:\n{path}")
            elemen = _SelAngka(str(p["jumlah_elemen"]) if p["jumlah_elemen"] else "-", p["jumlah_elemen"])
            nilai = p["total_rab"]
            total = _SelAngka(tema.format_rupiah(nilai) if nilai else "Belum dihitung", nilai)
            if not nilai:
                total.setForeground(QColor(tema.W["teks_samar"]))
            diubah = tema.sel(_tanggal(p["tanggal_diubah"]), warna=tema.W["teks_redup"])
            diubah.setData(Qt.UserRole + 1, str(p["tanggal_diubah"] or ""))
            for kol, it in ((KOL_NAMA, nama), (KOL_FILE, file), (KOL_ELEMEN, elemen), (KOL_TOTAL, total), (KOL_DIUBAH, diubah)):
                self.tabel.setItem(r, kol, it)
        self.tabel.setSortingEnabled(True)

        total = len(self._semua)
        self.label_jumlah.setText(f"{len(hasil)} dari {total} proyek" if kata else f"{total} proyek")
        if hasil:
            self.stack.setCurrentIndex(self.HAL_TABEL)
        else:
            self.kosong_cari.deskripsi.setText(f'Tidak ada proyek yang cocok dengan "{self.kolom_cari.text().strip()}".')
            self.stack.setCurrentIndex(self.HAL_TIDAK_ADA)
        self._perbarui_tombol()

    def _terpilih(self):
        baris = self.tabel.currentRow()
        if baris < 0 or not self.tabel.selectedItems():
            return None
        pid = self.tabel.item(baris, KOL_NAMA).data(Qt.UserRole)
        return next((p for p in self._semua if p["id"] == pid), None)

    def _perbarui_tombol(self):
        ada = self._terpilih() is not None
        self.btn_buka.setEnabled(ada)
        self.btn_hapus.setEnabled(ada)

    def _fokus_cari(self):
        if self.kolom_cari.isVisible():
            self.kolom_cari.setFocus()
            self.kolom_cari.selectAll()

    def _menu_konteks(self, pos):
        if self.tabel.itemAt(pos) is None:
            return
        menu = QMenu(self)
        menu.addAction("Buka proyek", self.buka_terpilih)
        menu.addAction("Info proyek...", self.ubah_info_terpilih)
        menu.addAction("Duplikat proyek...", self.duplikat_terpilih)
        menu.addAction("Simpan sebagai file...", self.simpan_file_terpilih)
        menu.addSeparator()
        menu.addAction("Hapus proyek", self.hapus_terpilih)
        menu.exec(self.tabel.viewport().mapToGlobal(pos))

    # ---------------------------------------------------------------- aksi

    def buka_terpilih(self):
        p = self._terpilih()
        if p:
            self.minta_buka.emit(p["id"], p["nama_proyek"])

    # ---------------------------------------------------------------- KF-7 / KF-9

    def buka_file(self):
        hasil = buka_file_proyek(self)
        if hasil:
            self.muat()
            tema.toast(self, f'Proyek "{hasil[1]}" dibuka')
            self.minta_buka.emit(*hasil)

    def simpan_file_terpilih(self):
        p = self._terpilih()
        if p:
            simpan_file_proyek(self, p["id"])

    def duplikat_terpilih(self):
        p = self._terpilih()
        if p is None:
            return
        hasil = duplikat(self, p["id"])
        if hasil:
            self.muat()
            tema.toast(self, f'Proyek "{hasil[1]}" dibuat')

    def ubah_info_terpilih(self):
        p = self._terpilih()
        if p is None:
            return
        dialog = InfoProyekDialog(p["id"], self)
        if dialog.exec() != InfoProyekDialog.Accepted:
            return
        self.muat()
        if dialog.ifc_berubah:  # file IFC diganti: hitung ulang dari model baru
            baru = get_proyek(p["id"])
            try:
                r = jalankan_di_latar(
                    self, "Membaca elemen & menghitung kuantitas...", jalankan_estimasi, p["id"], pakai_progress=True,
                )
            except Exception as e:
                tampilkan_galat(self, "Parsing Gagal", e, "Hitung ulang dari IFC baru", p["id"])
                return
            self.muat()
            tampilkan_hasil_proses(self, f"Proyek '{baru['nama_proyek']}'", r)
            self.minta_buka.emit(p["id"], baru["nama_proyek"])
        else:
            tema.toast(self, "Info proyek disimpan")

    def hapus_terpilih(self):
        p = self._terpilih()
        if p is None:
            return
        kotak = QMessageBox(self)
        kotak.setIcon(QMessageBox.Warning)
        kotak.setWindowTitle("Hapus Proyek")
        kotak.setText(f'Hapus proyek "{p["nama_proyek"]}"?')
        kotak.setInformativeText("Semua hasil QTO dan RAB proyek ini ikut terhapus. File IFC tidak dihapus.")
        btn_hapus = kotak.addButton("Hapus", QMessageBox.DestructiveRole)
        btn_batal = kotak.addButton("Batal", QMessageBox.RejectRole)
        kotak.setDefaultButton(btn_batal)  # Enter tidak langsung menghapus
        kotak.exec()
        if kotak.clickedButton() is btn_hapus:
            delete_proyek(p["id"])
            self.muat()
            tema.toast(self, f'Proyek "{p["nama_proyek"]}" dihapus')

    def import_ifc(self, file_path: str | None = None):
        """KF-1 (UC-01)."""
        if not file_path:
            file_path, _ = QFileDialog.getOpenFileName(
                self, "Pilih File IFC", folder_ifc(muat_preferensi()), "File IFC (*.ifc);;Semua file (*)"
            )
        if not file_path:
            return

        # 1. Validasi (ekstensi, header, integritas, versi) di proses terpisah
        try:
            info = jalankan_di_latar(
                self, "Memvalidasi file IFC...", buka_dan_validasi, file_path, terisolasi=True
            )
        except FileIFCTidakValid as e:  # UC-01 alternatif: file ditolak dengan alasan yang jelas
            catat("import", f"File IFC ditolak: {Path(file_path).name}: {e}", tingkat="PERINGATAN")
            QMessageBox.critical(self, "File Tidak Valid", str(e))
            return
        except Exception as e:
            tampilkan_galat(self, "File Tidak Valid", e, f"Validasi file IFC {Path(file_path).name}")
            return

        # 2. Ringkasan + konfirmasi
        dialog = RingkasanImportDialog(info, self)
        if not dialog.exec():
            return
        nama = dialog.nama_proyek() or Path(file_path).stem
        catat("import", f"File IFC diterima: {Path(file_path).name} ({info.skema}, {info.total_elemen} elemen)")

        # 3. Parsing + klasifikasi + rule engine + QTO di latar
        proyek_id = create_proyek(nama_proyek=nama, path_file_ifc=info.path)
        try:
            r = jalankan_di_latar(
                self, "Membaca elemen & menghitung kuantitas...", jalankan_estimasi,
                proyek_id, model=info.model, pakai_progress=True,
            )
        except Exception as e:
            self.muat()
            tampilkan_galat(
                self, f"Proyek '{nama}'", e,
                "Proyek dibuat, tetapi parsing gagal (proyek tetap tersimpan; estimasi dapat dijalankan ulang)",
                proyek_id,
            )
            return

        self.muat()
        tampilkan_hasil_proses(self, f"Proyek '{nama}'", r)
        self.minta_buka.emit(proyek_id, nama)  # UC-01 langkah 12


class _SelAngka(QTableWidgetItem):
    """Sel yang diurutkan berdasarkan nilai angka, bukan teks."""

    def __init__(self, teks: str, nilai):
        super().__init__(teks)
        self._nilai = nilai or 0
        self.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)

    def __lt__(self, lain):
        return self._nilai < getattr(lain, "_nilai", 0)


def _tanggal(teks) -> str:
    """'2026-10-07 04:03:11' -> '07 Okt 2026, 04:03'"""
    if not teks:
        return "-"
    bulan = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des"]
    try:
        tgl, jam = str(teks).split(" ")
        y, m, d = tgl.split("-")
        return f"{d} {bulan[int(m) - 1]} {y}, {jam[:5]}"
    except (ValueError, IndexError):
        return str(teks)
