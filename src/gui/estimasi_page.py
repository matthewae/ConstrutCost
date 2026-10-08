"""
Halaman Hasil Estimasi QTO & RAB satu proyek (UC-02 / UC-03).

- Mode "Rekap RAB": item pekerjaan digabung per kategori, seperti dokumen RAB.
- Mode "RAB Rinci": beton, bekisting, dan tulangan per tipe elemen (Kolom K1 20/25: 6 D13,
  sengkang Ø10-150, ...), seperti RAB konsultan.
- Mode "Detail per elemen": satu baris per elemen x pekerjaan; volume bisa diedit (KF-6)
  dan subtotal / total dihitung ulang otomatis.
- Ubah Dimensi (KF-19): dimensi elemen diubah lalu QTO elemen itu dihitung ulang oleh rule engine.
- Panel kanan menampilkan rincian baris terpilih: dimensi elemen beserta asalnya dan
  uraian rumus (rekap: analisa harga satuan pekerjaan).
- Banner bila ada harga satuan yang berubah (KF-5) atau harga nol (UC-02 alternatif).
- KF-6: volume, harga satuan, dan catatan per baris bisa diedit; setiap perubahan tersimpan langsung
  ke SQLite dan bisa diurungkan / diulangi (Ctrl+Z / Ctrl+Y).
"""

import json
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QKeySequence, QShortcut, QUndoCommand, QUndoStack
from PySide6.QtWidgets import (
    QAbstractSpinBox,
    QButtonGroup,
    QComboBox,
    QDoubleSpinBox,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QMenu,
    QSizePolicy,
    QToolButton,
    QSplitter,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from database.biaya_repository import ringkasan_biaya
from database.estimasi_repository import (
    PPN_RATE,
    NilaiTidakValid,
    get_harga_satuan_pekerjaan,
    get_hasil_estimasi_by_proyek,
    ubah_catatan,
    ubah_harga_baris,
    update_volume_estimasi,
)
from database.riwayat_repository import potret_proyek, pulihkan_proyek
from database.harga_repository import LABEL_TIPE, analisa_pekerjaan, terapkan_ke_estimasi
from database.proyek_repository import get_proyek
from estimasi_service import ambil_elemen, jalankan_estimasi
from export_service import kelompokkan
from aktivitas import catat
from gui import tema
from gui.galat import tampilkan_galat
from gui.aksi_proyek import InfoProyekDialog, duplikat, simpan_file_proyek
from gui.biaya_dialog import BiayaDialog
from gui.dimensi_dialog import DimensiDialog
from gui.export_dialog import ExportDialog
from gui.import_dialog import tampilkan_hasil_proses
from gui.parameter_dialog import ParameterDialog
from gui.penulangan_dialog import PenulanganDialog
from gui.proses_latar import jalankan_di_latar
from klasifikasi import LABEL, ElementType
from kebutuhan_lantai import (
    BERAT_ZAK_SEMEN,
    RASIO_WAJAR,
    TIPE_SUMBER_DAYA,
    komponen_pekerjaan,
    pekerjaan_lantai,
    penutup_bangunan,
    penutup_lantai,
    rasio_wajar,
    rincian_per_lantai,
    ringkas_lantai,
)
from rab_rinci import TANPA_LANTAI, daftar_lantai, susun_rinci
from rules.dimensi import kolom_dimensi
from rules.penulangan import label_tipe

SEMUA_KATEGORI = "Semua kategori"
SEMUA_LANTAI = "Semua lantai"
LABEL_DIMENSI = [
    ("panjang", "Panjang (L)", "m"),
    ("lebar", "Lebar (B)", "m"),
    ("tinggi", "Tinggi (H)", "m"),
    ("tebal", "Tebal (t)", "m"),
    ("luas", "Luas (A)", "m²"),
    ("volume_elemen", "Volume (V)", "m³"),
    ("keliling", "Keliling", "m"),
    ("kemiringan", "Kemiringan", "°"),
    ("luas_bukaan", "Luas bukaan", "m²"),
]
LABEL_SUMBER = {
    "qto": "Qto IFC", "geometri": "Geometri", "atribut": "Atribut IFC", "turunan": "Turunan", "manual": "Manual",
}
JENIS_CHIP_SUMBER = {"Qto IFC": "info", "Manual": "peringatan"}


class SpinVolume(QDoubleSpinBox):
    """Kolom volume: rata kanan, tanpa panah, dan tidak berubah karena scroll kecuali sedang difokuskan."""

    def __init__(self, nilai: float, satuan: str):
        super().__init__()
        self.setRange(0, 10_000_000)
        self.setDecimals(3)
        if satuan:
            self.setSuffix(f" {satuan}")
        self.setGroupSeparatorShown(True)
        self.setValue(nilai)
        self.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.setButtonSymbols(QAbstractSpinBox.NoButtons)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setKeyboardTracking(False)
        self.setToolTip("Klik lalu ketik volume baru, tekan Enter untuk menyimpan")

    def wheelEvent(self, event):
        if self.hasFocus():
            super().wheelEvent(event)
        else:
            event.ignore()

    def focusInEvent(self, event):
        super().focusInEvent(event)
        QTimer.singleShot(0, self.selectAll)


class SpinHarga(SpinVolume):
    """Kolom harga satuan (Rp) yang bisa diedit (KF-6)."""

    def __init__(self, nilai: float):
        super().__init__(nilai, "")
        self.setRange(0, 1e12)
        self.setDecimals(0)
        self.setPrefix("Rp ")
        self.setValue(nilai)
        self.setToolTip("Klik lalu ketik harga satuan khusus baris ini, tekan Enter untuk menyimpan")


class _PerintahPotret(QUndoCommand):
    """Satu langkah riwayat: potret data proyek sebelum & sesudah perubahan (KF-6)."""

    def __init__(self, halaman, teks: str, sebelum: dict, sesudah: dict):
        super().__init__(teks)
        self.halaman, self.sebelum, self.sesudah = halaman, sebelum, sesudah
        self._baru = True

    def redo(self):
        if self._baru:  # perubahan sudah diterapkan saat dicatat
            self._baru = False
            return
        pulihkan_proyek(self.halaman.proyek_id, self.sesudah)
        catat("riwayat", f"Diulangi: {self.text()}", self.halaman.proyek_id)
        self.halaman._setelah_riwayat(f"Diulangi: {self.text()}")

    def undo(self):
        pulihkan_proyek(self.halaman.proyek_id, self.sebelum)
        catat("riwayat", f"Dibatalkan: {self.text()}", self.halaman.proyek_id)
        self.halaman._setelah_riwayat(f"Dibatalkan: {self.text()}")


class EstimasiPage(QWidget):
    minta_kembali = Signal()
    minta_harga = Signal(object)  # pekerjaan_id atau None
    minta_buka_proyek = Signal(int, str)  # proyek lain (mis. hasil duplikat)

    MODE_REKAP, MODE_RINCI, MODE_LANTAI, MODE_DETAIL = 0, 1, 2, 3
    HAL_TABEL, HAL_KOSONG, HAL_TIDAK_ADA = range(3)

    def __init__(self, proyek_id: int, nama_proyek: str, parent=None):
        super().__init__(parent)
        self.setObjectName("halaman")
        self.proyek_id = proyek_id
        self.nama_proyek = nama_proyek
        self._data = []
        self._komponen = None
        self._rincian_tampil = []
        self._index = {}
        self._warna_kategori = {}
        self._volume_terakhir = {}
        self._harga_terakhir = {}
        self.riwayat = QUndoStack(self)
        self.riwayat.setUndoLimit(50)

        root = QVBoxLayout(self)
        root.setContentsMargins(32, 22, 32, 20)
        root.setSpacing(14)

        # --- Header ---
        kepala = QHBoxLayout()
        kepala.setSpacing(10)
        btn_kembali = tema.tombol("Proyek", "ghost", "kembali", "Kembali ke daftar proyek (Esc)")
        btn_kembali.clicked.connect(self.minta_kembali.emit)
        kol, self.label_judul, self.label_sub = tema.header_halaman(nama_proyek, "")
        kepala.addWidget(btn_kembali, alignment=Qt.AlignTop)
        kepala.addSpacing(6)
        kepala.addLayout(kol)
        kepala.addStretch()
        self.btn_ulang = tema.tombol(
            "Hitung Ulang", "secondary", "ulang",
            "Baca ulang file IFC lalu jalankan rule engine. Volume yang diedit manual akan diganti.",
        )
        self.btn_ulang.clicked.connect(self._hitung_ulang)
        self.btn_tulangan = tema.tombol(
            "Penulangan", "secondary", None,
            "Konfigurasi tulangan per tipe elemen dan kebutuhan besi per diameter",
        )
        self.btn_tulangan.clicked.connect(self._buka_penulangan)
        self.btn_biaya = tema.tombol(
            "Biaya Tidak Langsung", "secondary", None,
            "Perencanaan, pengawasan, perizinan, SMKK, dan biaya lain di luar pekerjaan fisik (KF-13)",
        )
        self.btn_biaya.clicked.connect(self._buka_biaya)
        self.btn_export = tema.tombol("Export RAB", "primary", "unduh", "Export ke Excel / PDF (Ctrl+E)")
        self.btn_export.clicked.connect(self._buka_export)
        # KF-7 / KF-9: menu proyek
        self.btn_proyek = QToolButton()
        self.btn_proyek.setText("Proyek  ▾")
        self.btn_proyek.setObjectName("btnSecondary")
        self.btn_proyek.setCursor(Qt.PointingHandCursor)
        self.btn_proyek.setPopupMode(QToolButton.InstantPopup)
        self.btn_proyek.setToolButtonStyle(Qt.ToolButtonTextOnly)
        menu = QMenu(self.btn_proyek)
        menu.addAction("Info Proyek...", self._ubah_info)
        menu.addAction("Parameter Aturan...", self._buka_parameter)
        menu.addSeparator()
        menu.addAction("Simpan File Proyek...\tCtrl+S", self._simpan_file)
        menu.addAction("Duplikat Proyek...", self._duplikat)
        self.btn_proyek.setMenu(menu)
        kepala.addWidget(self.btn_proyek, alignment=Qt.AlignTop)
        kepala.addWidget(self.btn_ulang, alignment=Qt.AlignTop)
        kepala.addWidget(self.btn_tulangan, alignment=Qt.AlignTop)
        kepala.addWidget(self.btn_biaya, alignment=Qt.AlignTop)
        kepala.addWidget(self.btn_export, alignment=Qt.AlignTop)
        root.addLayout(kepala)

        self.banner_harga = tema.Banner("info")
        self.banner_nol = tema.Banner("peringatan")
        root.addWidget(self.banner_harga)
        root.addWidget(self.banner_nol)

        # --- Kartu ringkasan ---
        self.baris_kartu = QWidget()
        kartu = QHBoxLayout(self.baris_kartu)
        kartu.setContentsMargins(0, 0, 0, 0)
        kartu.setSpacing(14)
        self.k_subtotal = tema.KartuStat("A. Biaya Langsung")
        self.k_btl = tema.KartuStat("B. Biaya Tidak Langsung")
        self.k_ppn = tema.KartuStat(f"PPN {PPN_RATE:.0%}")
        self.k_total = tema.KartuStat("Total RAB", utama=True)
        for k in (self.k_subtotal, self.k_btl, self.k_ppn, self.k_total):
            kartu.addWidget(k, stretch=1)
        root.addWidget(self.baris_kartu)

        # --- Toolbar: mode + cari + kategori ---
        self.baris_alat = QWidget()
        alat = QHBoxLayout(self.baris_alat)
        alat.setContentsMargins(0, 0, 0, 0)
        alat.setSpacing(10)
        self.grup_mode = QButtonGroup(self)
        for i, (teks, posisi, tip) in enumerate((
            ("Rekap RAB", "kiri", "Item pekerjaan digabung per kategori, seperti dokumen RAB"),
            ("RAB Rinci", "tengah", "Beton, bekisting, dan tulangan per tipe elemen (mis. Kolom K1 20/25: 6 D13)"),
            ("Per Lantai", "tengah", "Biaya tiap lantai dirinci per kategori pekerjaan (KF-12)"),
            ("Detail per Elemen", "kanan", "Satu baris per elemen; volume, harga satuan, dan catatan bisa diedit"),
        )):
            b = QPushButton(teks)
            b.setObjectName("segmen")
            b.setProperty("posisi", posisi)
            b.setCheckable(True)
            b.setCursor(Qt.PointingHandCursor)
            b.setToolTip(tip)
            self.grup_mode.addButton(b, i)
            alat.addWidget(b)
        alat.setSpacing(0)
        self.grup_mode.button(self.MODE_REKAP).setChecked(True)
        self.grup_mode.idClicked.connect(lambda _: self._isi_ulang())
        alat.addSpacing(14)
        self.kolom_cari = QLineEdit()
        self.kolom_cari.setMinimumWidth(150)
        self.kolom_cari.setPlaceholderText("Cari pekerjaan, elemen, atau lantai...   (Ctrl+F)")
        self.kolom_cari.setClearButtonEnabled(True)
        self.kolom_cari.textChanged.connect(self._isi_ulang)
        alat.addWidget(self.kolom_cari, stretch=1)
        alat.addSpacing(10)
        self.combo_kategori = QComboBox()
        self.combo_kategori.setSizeAdjustPolicy(QComboBox.AdjustToContents)
        self.combo_kategori.currentIndexChanged.connect(self._isi_ulang)
        alat.addWidget(self.combo_kategori)
        alat.addSpacing(8)
        self.combo_lantai = QComboBox()  # KF-12
        self.combo_lantai.setSizeAdjustPolicy(QComboBox.AdjustToContents)
        self.combo_lantai.setToolTip("Tampilkan dan hitung pekerjaan satu lantai saja (KF-12)")
        self.combo_lantai.currentIndexChanged.connect(self._isi_ulang)
        alat.addWidget(self.combo_lantai)
        alat.addSpacing(10)
        self.label_jumlah = tema.label("", "subjudul")  # ditempatkan di baris bawah tabel
        alat.addSpacing(12)
        self.btn_urungkan = tema.tombol("↶ Urungkan", "ghost", None, "Batalkan perubahan terakhir (Ctrl+Z)")
        self.btn_ulangi = tema.tombol("↷ Ulangi", "ghost", None, "Ulangi perubahan yang dibatalkan (Ctrl+Y)")
        self.btn_urungkan.clicked.connect(self.riwayat.undo)
        self.btn_ulangi.clicked.connect(self.riwayat.redo)
        self.btn_urungkan.setEnabled(False)
        self.btn_ulangi.setEnabled(False)
        self.riwayat.canUndoChanged.connect(self.btn_urungkan.setEnabled)
        self.riwayat.canRedoChanged.connect(self.btn_ulangi.setEnabled)
        self.riwayat.undoTextChanged.connect(
            lambda t: self.btn_urungkan.setToolTip(f"Urungkan: {t} (Ctrl+Z)" if t else "Batalkan perubahan terakhir (Ctrl+Z)")
        )
        self.riwayat.redoTextChanged.connect(
            lambda t: self.btn_ulangi.setToolTip(f"Ulangi: {t} (Ctrl+Y)" if t else "Ulangi perubahan yang dibatalkan (Ctrl+Y)")
        )
        alat.addWidget(self.btn_urungkan)
        alat.addWidget(self.btn_ulangi)
        root.addWidget(self.baris_alat)

        # --- Konten: tabel + panel rincian ---
        self.stack = QStackedWidget()
        root.addWidget(self.stack, stretch=1)

        self.splitter = QSplitter(Qt.Horizontal)
        self.splitter.setChildrenCollapsible(False)
        self.splitter.setHandleWidth(14)
        self.tabel = QTableWidget()
        self._urut = {}  # KF-16: mode -> (kolom, Qt.SortOrder)
        self.tabel.horizontalHeader().setSectionsClickable(True)
        self.tabel.horizontalHeader().sectionClicked.connect(self._klik_judul)
        self.tabel.itemSelectionChanged.connect(self._tampilkan_rincian)
        self.tabel.cellDoubleClicked.connect(self._klik_ganda)
        self.splitter.addWidget(self.tabel)
        self.panel = PanelRincian(self)
        self.panel.minta_harga.connect(self.minta_harga.emit)
        self.panel.minta_ubah_dimensi.connect(self.ubah_dimensi)
        self.panel.minta_harga_baris.connect(self._harga_diubah)
        self.panel.minta_catatan.connect(self._catatan_diubah)
        self.splitter.addWidget(self.panel)
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 0)
        self.splitter.setSizes([840, 320])
        self.stack.addWidget(self.splitter)

        self.stack.addWidget(
            tema.KondisiKosong(
                "Belum ada hasil estimasi",
                "Parsing IFC dan rule engine untuk proyek ini belum dijalankan, atau model tidak "
                "berisi elemen struktural.",
                "Jalankan Estimasi dari File IFC",
                self._jalankan_estimasi,
                simbol="ulang",
            )
        )
        self.kosong_cari = tema.KondisiKosong(
            "Item tidak ditemukan", 'Ubah kata kunci atau pilih "Semua kategori".', simbol="file"
        )
        self.stack.addWidget(self.kosong_cari)

        self.label_petunjuk = tema.label("", "petunjuk")
        self.baris_bawah = QWidget()
        bawah = QHBoxLayout(self.baris_bawah)
        bawah.setContentsMargins(0, 0, 0, 0)
        bawah.addWidget(self.label_petunjuk, stretch=1)
        bawah.addWidget(self.label_jumlah)
        root.addWidget(self.baris_bawah)

        QShortcut(QKeySequence("Ctrl+F"), self, activated=self._fokus_cari)
        QShortcut(QKeySequence("Ctrl+E"), self, activated=self._pintasan_export)
        QShortcut(QKeySequence.Undo, self, activated=self.riwayat.undo)
        QShortcut(QKeySequence.Save, self, activated=self._simpan_file)
        QShortcut(QKeySequence("Ctrl+Y"), self, activated=self.riwayat.redo)
        QShortcut(QKeySequence("Ctrl+Shift+Z"), self, activated=self.riwayat.redo)
        QShortcut(QKeySequence(Qt.Key_Escape), self, activated=self.minta_kembali.emit)

        self.muat()

    # ---------------------------------------------------------------- data

    @property
    def mode(self) -> int:
        return self.grup_mode.checkedId()

    def muat(self):
        self._data = [dict(r) for r in get_hasil_estimasi_by_proyek(self.proyek_id)]
        self._komponen = None  # analisa AHSP untuk kebutuhan bahan per lantai, dimuat saat dibutuhkan
        for r in self._data:
            v = r["volume_pekerjaan"]
            r["harga_satuan"] = r["subtotal_biaya"] / v if v else 0.0
        self._index = {r["hasil_id"]: r for r in self._data}

        proyek = get_proyek(self.proyek_id) or {}
        path = proyek.get("path_file_ifc")
        bagian = [Path(path).name if path else "Tanpa file IFC"]
        if proyek.get("jumlah_elemen"):
            bagian.append(f"{proyek['jumlah_elemen']} elemen")
        self.label_sub.setText("  ·  ".join(bagian) + "  ·  Hasil Quantity Take-Off & RAB")

        ada = bool(self._data)
        for w in (self.baris_kartu, self.baris_alat, self.baris_bawah):
            w.setVisible(ada)
        self.btn_export.setEnabled(ada)
        for b in (self.btn_ulang, self.btn_tulangan, self.btn_biaya):
            b.setVisible(ada)
        if not ada:
            self.banner_harga.hide()
            self.banner_nol.hide()
            self.stack.setCurrentIndex(self.HAL_KOSONG)
            return

        kategori = sorted({r["kategori"] for r in self._data if r["kategori"]})
        self._warna_kategori = {
            k: tema.WARNA_KATEGORI[i % len(tema.WARNA_KATEGORI)] for i, k in enumerate(kategori)
        }
        lama = self.combo_kategori.currentText()
        self.combo_kategori.blockSignals(True)
        self.combo_kategori.clear()
        self.combo_kategori.addItem(SEMUA_KATEGORI)
        self.combo_kategori.addItems(kategori)
        idx = self.combo_kategori.findText(lama)
        self.combo_kategori.setCurrentIndex(max(idx, 0))
        self.combo_kategori.blockSignals(False)

        lama = self.combo_lantai.currentText()
        self.combo_lantai.blockSignals(True)
        self.combo_lantai.clear()
        self.combo_lantai.addItem(SEMUA_LANTAI)
        self.combo_lantai.addItems(daftar_lantai(self._data))
        idx = self.combo_lantai.findText(lama)
        self.combo_lantai.setCurrentIndex(max(idx, 0))
        self.combo_lantai.blockSignals(False)

        self._perbarui_banner()
        self._perbarui_ringkasan()
        self._isi_ulang()

    def _perbarui_banner(self):
        from database.harga_repository import daftar_pekerjaan

        harga_kini = {p["id"]: p["harga_satuan"] for p in daftar_pekerjaan()}
        beda = {
            r["pekerjaan_id"] for r in self._data
            if r["volume_pekerjaan"] and not r.get("harga_manual")
            and abs(r["harga_satuan"] - harga_kini.get(r["pekerjaan_id"], 0)) > 0.5
        }
        if beda:
            self.banner_harga.tampilkan(
                f"Harga satuan {len(beda)} item pekerjaan sudah berubah sejak estimasi ini dihitung.",
                "Terapkan Harga Terbaru",
                self._terapkan_harga,
            )
        else:
            self.banner_harga.hide()

        nol = sorted({r["nama_pekerjaan"] for r in self._data if harga_kini.get(r["pekerjaan_id"], 0) <= 0})
        if nol:
            self.banner_nol.tampilkan(
                f"{len(nol)} item pekerjaan belum punya harga satuan: {', '.join(nol[:3])}"
                + ("..." if len(nol) > 3 else ""),
                "Perbaiki Harga",
                lambda: self.minta_harga.emit(None),
            )
        else:
            self.banner_nol.hide()

    def _terapkan_harga(self):
        sebelum = potret_proyek(self.proyek_id)
        terapkan_ke_estimasi(self.proyek_id)
        self._catat("Terapkan harga terbaru", sebelum)
        self.muat()
        tema.toast(self, "Harga satuan terbaru diterapkan")

    def _perbarui_ringkasan(self):
        """KF-13: biaya langsung, biaya tidak langsung, PPN, dan total."""
        r = ringkasan_biaya(self.proyek_id)
        n_pekerjaan = len({x["pekerjaan_id"] for x in self._data})
        manual = sum(1 for x in self._data if x["diedit_manual"])
        dimensi = len({x["elemen_id"] for x in self._data if x.get("dimensi_manual")})
        ket = f"{n_pekerjaan} item pekerjaan"
        ket += f", {manual} volume diedit" if manual else ""
        ket += f", {dimensi} dimensi diubah" if dimensi else ""
        self.k_subtotal.set_data(tema.format_rupiah(r["langsung"]), ket)
        n_btl = len(r["item_tidak_langsung"])
        self.k_btl.set_data(
            tema.format_rupiah(r["tidak_langsung"]),
            f"{n_btl} item, klik Biaya Tidak Langsung" if n_btl else "belum ada, klik Biaya Tidak Langsung",
        )
        self.k_ppn.set_data(tema.format_rupiah(r["ppn"]), "dari biaya langsung + tidak langsung")
        self.k_total.set_data(tema.format_rupiah(r["dibulatkan"]), "termasuk PPN, dibulatkan")
        self.k_total.setToolTip(r["terbilang"])

    def _cocok(self, r, kata: str, kategori: str, lantai: str = SEMUA_LANTAI) -> bool:
        if kategori and kategori != SEMUA_KATEGORI and r["kategori"] != kategori:
            return False
        if lantai and lantai != SEMUA_LANTAI and (r.get("lantai") or TANPA_LANTAI) != lantai:
            return False
        if not kata:
            return True
        teks = " ".join(str(r.get(k) or "") for k in ("nama_pekerjaan", "nama_elemen", "lantai", "kode_ahsp", "uraian", "kode_tipe"))
        return kata in teks.lower()

    def _isi_ulang(self, *_):
        if not self._data:
            return
        kata = self.kolom_cari.text().strip().lower()
        kategori = self.combo_kategori.currentText()
        lantai = self.combo_lantai.currentText()
        baris = [r for r in self._data if self._cocok(r, kata, kategori, lantai)]
        if self.mode == self.MODE_REKAP:
            n = self._isi_rekap(baris)
            satuan = "item pekerjaan"
            self.label_petunjuk.setText(
                "Volume tiap pekerjaan adalah jumlah dari semua elemen. "
                "Pilih baris untuk melihat analisa harga satuannya."
            )
        elif self.mode == self.MODE_RINCI:
            n = self._isi_rinci(baris)
            satuan = "item"
            self.label_petunjuk.setText(
                "Beton, bekisting, dan tulangan dikelompokkan per tipe elemen. Konfigurasi tulangan bisa "
                "diubah lewat tombol Tipe Penulangan."
            )
        elif self.mode == self.MODE_LANTAI:
            if lantai and lantai != SEMUA_LANTAI:
                n = self._isi_lantai_rinci(baris)
                satuan = "baris rincian"
                self.label_petunjuk.setText(
                    "Rincian satu lantai: struktur beton per tipe, besi per diameter, bahan, tenaga kerja, alat, "
                    "dan RAB rinci. Pilih \"Semua lantai\" untuk kembali ke ringkasan."
                )
            else:
                n = self._isi_lantai(baris)
                satuan = "lantai"
                self.label_petunjuk.setText(
                    "Beton, bekisting, dan besi tiap lantai dihitung dari elemen di lantai tersebut. Klik dua kali "
                    "nama lantai untuk melihat rincian kebutuhan bahan dan besinya."
                )
        else:
            n = self._isi_detail(baris)
            satuan = "baris"
            self.label_petunjuk.setText(
                "Klik angka di kolom Volume untuk mengubahnya, lalu tekan Enter. Klik dua kali kolom "
                "Elemen untuk mengubah dimensinya. Subtotal dan total dihitung ulang otomatis."
            )
        teks = f"{n} {satuan}"
        if lantai and lantai != SEMUA_LANTAI:
            teks += f"  ·  {lantai}: {tema.format_rupiah(sum(r['subtotal_biaya'] for r in baris))}"
        self.label_jumlah.setText(teks)
        self._tampilkan_indikator()
        self.stack.setCurrentIndex(self.HAL_TABEL if baris else self.HAL_TIDAK_ADA)
        if self.mode != self.MODE_LANTAI:
            self._rincian_tampil = []
        self._panel_bawaan()

    def _panel_bawaan(self):
        """Panel kanan saat tidak ada baris dipilih. Mode Per Lantai: rincian perhitungan tiap lantai,
        dari lantai terbawah sampai penutup bangunan (atap / dak / plafon)."""
        if self.mode == self.MODE_LANTAI and self._rincian_tampil:
            self.panel.tampilkan_lantai(
                self._rincian_tampil, satu=self.combo_lantai.currentText() != SEMUA_LANTAI, warna=self._warna_kategori,
            )
        else:
            self.panel.kosongkan()

    # ---------------------------------------------------------------- KF-16 pengurutan

    def _klik_judul(self, kolom: int):
        """Klik judul kolom: urutkan naik, klik lagi turun, klik ketiga kembali ke urutan asal."""
        if self.mode == self.MODE_RINCI or (  # RAB rinci & rincian satu lantai mengikuti susunan bagian
            self.mode == self.MODE_LANTAI and self.combo_lantai.currentText() != SEMUA_LANTAI
        ):
            self._tampilkan_indikator()
            return
        lama = self._urut.get(self.mode)
        if lama is None or lama[0] != kolom:
            self._urut[self.mode] = (kolom, Qt.AscendingOrder)
        elif lama[1] == Qt.AscendingOrder:
            self._urut[self.mode] = (kolom, Qt.DescendingOrder)
        else:
            self._urut.pop(self.mode)
        self._isi_ulang()

    def _terurut(self, data: list, kunci: dict) -> list:
        urut = self._urut.get(self.mode)
        if not urut or urut[0] not in kunci:
            return list(data)
        return sorted(data, key=kunci[urut[0]], reverse=urut[1] == Qt.DescendingOrder)

    def _tampilkan_indikator(self):
        h = self.tabel.horizontalHeader()
        urut = self._urut.get(self.mode)
        h.setSortIndicatorShown(urut is not None)
        if urut:
            h.setSortIndicator(*urut)

    # ---------------------------------------------------------------- mode rekap

    def _isi_rekap(self, baris) -> int:
        t = self.tabel
        t.clearSpans()
        t.clear()
        tema.siapkan_tabel(
            t, ["NO", "URAIAN PEKERJAAN", "VOLUME", "SAT", "HARGA SATUAN", "JUMLAH HARGA", "%"],
            rata_kanan=(2, 4, 5, 6), tinggi_baris=38,
        )
        kelompok = kelompokkan(baris) if baris else []
        kunci = {1: lambda it: it["nama"].lower(), 2: lambda it: it["volume"], 3: lambda it: it["satuan"],
                 4: lambda it: it["harga"], 5: lambda it: it["jumlah"], 6: lambda it: it["jumlah"]}
        for k in kelompok:  # KF-16: urutkan item di dalam tiap kategori
            k["items"] = self._terurut(k["items"], kunci)
        total = sum(k["total"] for k in kelompok) or 1.0
        id_pekerjaan = {r["kode_ahsp"]: r["pekerjaan_id"] for r in baris}
        jumlah_baris = sum(len(k["items"]) + 2 for k in kelompok)
        t.setRowCount(jumlah_baris)
        r = 0
        n_item = 0
        for i, k in enumerate(kelompok, 1):
            warna = self._warna_kategori.get(k["kategori"], tema.W["teks"])
            t.setItem(r, 0, tema.sel(_romawi(i), warna=warna, tebal=True))
            t.setItem(r, 1, tema.sel(k["kategori"].upper(), warna=warna, tebal=True))
            t.setSpan(r, 1, 1, 6)
            r += 1
            for n, it in enumerate(k["items"], 1):
                n_item += 1
                pid = id_pekerjaan.get(it["kode"])
                t.setItem(r, 0, tema.sel(str(n), warna=tema.W["teks_samar"], data=("rekap", pid)))
                t.setItem(r, 1, tema.sel(it["nama"], tooltip=f"{it['kode']} — {it['nama']}"))
                t.setItem(r, 2, tema.sel(tema.format_angka(it["volume"], 2), "kanan"))
                t.setItem(r, 3, tema.sel(it["satuan"], "tengah", tema.W["teks_redup"]))
                t.setItem(r, 4, tema.sel(tema.format_rupiah(it["harga"]), "kanan", tema.W["teks_redup"]))
                t.setItem(r, 5, tema.sel(tema.format_rupiah(it["jumlah"]), "kanan", tebal=True))
                t.setItem(r, 6, tema.sel(f"{it['jumlah'] / total:.1%}".replace(".", ","), "kanan", tema.W["teks_samar"]))
                r += 1
            t.setItem(r, 1, tema.sel(f"Jumlah {k['kategori']}", "kanan", tema.W["teks_redup"]))
            t.setItem(r, 5, tema.sel(tema.format_rupiah(k["total"]), "kanan", warna, tebal=True))
            t.setItem(r, 6, tema.sel(f"{k['total'] / total:.1%}".replace(".", ","), "kanan", tema.W["teks_redup"]))
            r += 1
        tema.atur_lebar(t, 1, isi_konten=(0, 2, 3, 4, 5, 6))
        return n_item

    # ---------------------------------------------------------------- mode rinci

    def _isi_rinci(self, baris) -> int:
        t = self.tabel
        t.clearSpans()
        t.clear()
        tema.siapkan_tabel(
            t, ["NO", "URAIAN PEKERJAAN", "VOLUME", "SAT", "HARGA SATUAN", "JUMLAH HARGA"],
            rata_kanan=(2, 4, 5), tinggi_baris=36,
        )
        susunan = susun_rinci(baris) if baris else []
        t.setRowCount(sum(2 + sum(len(g["items"]) + (1 if g["judul"] else 0) for g in k["grup"]) for k in susunan))
        r = n_item = 0
        for i, k in enumerate(susunan, 1):
            warna = self._warna_kategori.get(k["kategori"], tema.W["teks"])
            t.setItem(r, 0, tema.sel(_romawi(i), warna=warna, tebal=True))
            t.setItem(r, 1, tema.sel(k["kategori"].upper(), warna=warna, tebal=True))
            t.setSpan(r, 1, 1, 5)
            r += 1
            nomor = 0
            for g in k["grup"]:
                if g["judul"]:
                    nomor += 1
                    t.setItem(r, 0, tema.sel(str(nomor), warna=tema.W["teks_redup"], tebal=True))
                    t.setItem(r, 1, tema.sel(g["judul"], tebal=True))
                    t.setItem(r, 5, tema.sel(tema.format_rupiah(g["total"]), "kanan", tema.W["teks_redup"]))
                    t.setSpan(r, 1, 1, 4)
                    r += 1
                for it in g["items"]:
                    n_item += 1
                    if g["judul"]:
                        no, label = "", f"      –  {it['label']}"
                    else:
                        nomor += 1
                        no, label = str(nomor), it["label"]
                    t.setItem(r, 0, tema.sel(no, warna=tema.W["teks_samar"], data=("rekap", it["pekerjaan_id"])))
                    t.setItem(r, 1, tema.sel(label, tooltip=f"{it['kode']} — {it['label']}"))
                    t.setItem(r, 2, tema.sel(tema.format_angka(it["volume"], 2), "kanan"))
                    t.setItem(r, 3, tema.sel(it["satuan"], "tengah", tema.W["teks_redup"]))
                    t.setItem(r, 4, tema.sel(tema.format_rupiah(it["harga"]), "kanan", tema.W["teks_redup"]))
                    t.setItem(r, 5, tema.sel(tema.format_rupiah(it["jumlah"]), "kanan", tebal=True))
                    r += 1
            t.setItem(r, 1, tema.sel(f"Jumlah {k['kategori']}", "kanan", tema.W["teks_redup"]))
            t.setItem(r, 5, tema.sel(tema.format_rupiah(k["total"]), "kanan", warna, tebal=True))
            r += 1
        tema.atur_lebar(t, 1, isi_konten=(0, 2, 3, 4, 5))
        return n_item

    # ---------------------------------------------------------------- mode per lantai (KF-12)

    def _rincian_lantai(self, baris) -> list:
        if self._komponen is None:
            self._komponen = komponen_pekerjaan(r["pekerjaan_id"] for r in self._data)
        self._rincian_tampil = rincian_per_lantai(baris, self._komponen)  # urut elevasi, untuk panel kanan
        return list(self._rincian_tampil)

    def _isi_lantai(self, baris) -> int:
        """Ringkasan semua lantai: biaya per kategori beserta beton, bekisting, dan besi (KF-12)."""
        t = self.tabel
        t.clearSpans()
        t.clear()
        tema.siapkan_tabel(
            t, ["NO", "LANTAI / KATEGORI PEKERJAAN", "ELEMEN", "BETON (m³)", "BEKISTING (m²)", "BESI (kg)",
                "JUMLAH HARGA", "%"],
            rata_kanan=(2, 3, 4, 5, 6, 7), tinggi_baris=36,
        )
        rekap = self._rincian_lantai(baris) if baris else []
        for x in rekap:
            x["ringkas"] = ringkas_lantai(x)
            per_kat = {}
            for r in x["baris"]:
                k = per_kat.setdefault(r["kategori"], {"beton": 0.0, "bekisting": 0.0, "besi": 0.0})
                kode = r.get("kode_ahsp") or ""
                kunci = ("beton" if kode.startswith(("BTN.", "LTK.")) else "bekisting" if kode.startswith("BSK.")
                         else "besi" if kode.startswith("BSI.") else None)
                if kunci:
                    k[kunci] += r["volume_pekerjaan"] or 0.0
            for k in x["kategori"]:
                k.update(per_kat.get(k["kategori"], {}))
        kunci_urut = {1: lambda x: x["lantai"].lower(), 2: lambda x: x.get("jumlah_elemen", 0),
                      3: lambda x: x["ringkas"]["beton"], 4: lambda x: x["ringkas"]["bekisting"],
                      5: lambda x: x["ringkas"]["besi"],
                      6: lambda x: x["total"], 7: lambda x: x["total"]}
        rekap = self._terurut(rekap, kunci_urut)
        for x in rekap:
            x["kategori"] = self._terurut(x["kategori"], {
                1: lambda k: k["kategori"].lower(), 3: lambda k: k.get("beton", 0), 4: lambda k: k.get("bekisting", 0),
                5: lambda k: k.get("besi", 0), 6: lambda k: k["total"], 7: lambda k: k["total"]})
        total = sum(x["total"] for x in rekap) or 1.0
        t.setRowCount(sum(1 + len(x["kategori"]) for x in rekap) + (1 if rekap else 0))

        def angka(v, d=2):
            return tema.format_angka(v, d) if v else "-"

        r = 0
        for i, x in enumerate(rekap, 1):
            elev = "" if x["elevasi"] is None else f"  ·  elevasi {tema.format_angka(x['elevasi'], 2)} m"
            tip = "Klik dua kali untuk melihat rincian kebutuhan lantai ini"
            t.setItem(r, 0, tema.sel(str(i), warna=tema.W["aksen"], tebal=True, data=("lantai", x["lantai"])))
            t.setItem(r, 1, tema.sel(f"{x['lantai']}{elev}", warna=tema.W["aksen"], tebal=True, tooltip=tip))
            t.setItem(r, 2, tema.sel(f"{x['jumlah_elemen']} elemen", "kanan", tema.W["teks_redup"]))
            for c, kunci in ((3, "beton"), (4, "bekisting"), (5, "besi")):
                t.setItem(r, c, tema.sel(angka(x["ringkas"][kunci]), "kanan", tema.W["aksen"], tebal=True))
            t.setItem(r, 6, tema.sel(tema.format_rupiah(x["total"]), "kanan", tema.W["aksen"], tebal=True))
            t.setItem(r, 7, tema.sel(f"{x['total'] / total:.1%}".replace(".", ","), "kanan", tebal=True))
            r += 1
            for k in x["kategori"]:
                warna = self._warna_kategori.get(k["kategori"], tema.W["teks"])
                t.setItem(r, 0, tema.sel("", data=("lantai", x["lantai"])))
                t.setItem(r, 1, tema.sel(f"      {k['kategori']}", warna=warna))
                for c, kunci in ((3, "beton"), (4, "bekisting"), (5, "besi")):
                    t.setItem(r, c, tema.sel(angka(k.get(kunci)), "kanan", tema.W["teks_redup"]))
                t.setItem(r, 6, tema.sel(tema.format_rupiah(k["total"]), "kanan"))
                t.setItem(r, 7, tema.sel(f"{k['total'] / total:.1%}".replace(".", ","), "kanan", tema.W["teks_samar"]))
                r += 1
        if rekap:
            t.setItem(r, 1, tema.sel(f"JUMLAH {len(rekap)} LANTAI", "kanan", tebal=True))
            for c, kunci in ((3, "beton"), (4, "bekisting"), (5, "besi")):
                t.setItem(r, c, tema.sel(angka(sum(x["ringkas"][kunci] for x in rekap)), "kanan", tebal=True))
            t.setItem(r, 6, tema.sel(tema.format_rupiah(sum(x["total"] for x in rekap)), "kanan", tebal=True))
            t.setItem(r, 7, tema.sel("100,0%", "kanan", tebal=True))
        tema.atur_lebar(t, 1, isi_konten=(0, 2, 3, 4, 5, 6, 7))
        return len(rekap)

    def _isi_lantai_rinci(self, baris) -> int:
        """Rincian satu lantai: biaya per kategori, struktur beton per tipe, besi per diameter, bahan,
        tenaga kerja, alat (koefisien AHSP), dan RAB rinci lantai."""
        t = self.tabel
        t.clearSpans()
        t.clear()
        tema.siapkan_tabel(
            t, ["NO", "URAIAN", "VOLUME", "SAT", "KETERANGAN", "HARGA SATUAN", "JUMLAH HARGA"],
            rata_kanan=(2, 5, 6), tinggi_baris=34,
        )
        daftar = self._rincian_lantai(baris) if baris else []
        if not daftar:
            t.setRowCount(0)
            return 0
        x = daftar[0]
        isi = []  # (jenis, kolom...) disusun dulu, baru ditulis ke tabel

        def judul(no, teks, jumlah=None):
            isi.append(("judul", no, teks, jumlah))

        def item(no, uraian, volume=None, satuan="", ket="", harga=None, jumlah=None, data=None, warna=None,
                 tebal=False, tooltip=None):
            isi.append(("item", no, uraian, volume, satuan, ket, harga, jumlah, data, warna, tebal, tooltip))

        ring = ringkas_lantai(x)
        elev = "" if x["elevasi"] is None else f"  ·  elevasi {tema.format_angka(x['elevasi'], 2)} m"
        isi.append(("lantai", f"{x['lantai']}{elev}  ·  {x['jumlah_elemen']} elemen", x["total"]))

        judul("I", "REKAP BIAYA PER KATEGORI", x["total"])
        for k in x["kategori"]:
            persen = f"{k['total'] / (x['total'] or 1):.1%} lantai ini".replace(".", ",")
            item("", k["kategori"], ket=persen, jumlah=k["total"], warna=self._warna_kategori.get(k["kategori"]))

        if x["struktur"]:
            judul("II", "STRUKTUR BETON PER TIPE ELEMEN", sum(g["biaya"] for g in x["struktur"]))
            for n, g in enumerate(x["struktur"], 1):
                bagian = [f"{g['jumlah_elemen']} buah"] if g["jumlah_elemen"] else []
                if g["bekisting"]:
                    bagian.append(f"bekisting {tema.format_angka(g['bekisting'], 2)} m²")
                if g["besi"]:
                    bagian.append(f"besi {tema.format_angka(g['besi'], 1)} kg")
                if g["rasio"] is not None:
                    bagian.append(f"{tema.format_angka(g['rasio'], 0)} kg/m³" + ("" if rasio_wajar(g["rasio"]) else " ⚠ periksa"))
                item(str(n), f"{g['label']}  ·  beton {g['mutu']}", g["beton"], "m³", "  ·  ".join(bagian),
                     jumlah=g["biaya"], warna=None if rasio_wajar(g["rasio"]) else tema.W["peringatan"],
                     tooltip=None if rasio_wajar(g["rasio"]) else (
                         f"Rasio besi {tema.format_angka(g['rasio'], 0)} kg/m³ di luar rentang wajar "
                         f"{RASIO_WAJAR[0]:.0f}–{RASIO_WAJAR[1]:.0f} kg/m³. Periksa dimensi elemen di model IFC "
                         "atau konfigurasi tipe penulangannya."))
            for m in x["beton_mutu"]:
                item("", f"Total beton {m['mutu']}", m["volume"], "m³", tebal=True)
            if ring["bekisting"]:
                item("", "Total bekisting", ring["bekisting"], "m²", tebal=True)

        if x["besi"] or x["besi_rasio"]:
            judul("III", "KEBUTUHAN BESI TULANGAN PER DIAMETER")
            for n, k in enumerate(x["besi"], 1):
                item(str(n), f"{k['label']}  ·  {k['jenis']}", k["berat"], "kg",
                     f"{tema.format_angka(k['panjang'], 1)} m'  ·  {k['batang']} batang @ 12 m  ·  "
                     f"{tema.format_angka(k['berat_per_m'], 3)} kg/m'")
            if x["besi_rasio"] > 1e-9:
                item("", "Besi tanpa rincian diameter (asumsi rasio kg/m³)", x["besi_rasio"], "kg",
                     "elemen tanpa tipe penulangan", warna=tema.W["teks_redup"])
            item("", "Total besi", ring["besi"], "kg",
                 f"{sum(k['batang'] for k in x['besi'])} batang @ 12 m (yang berdiameter)", tebal=True)

        sd = x["sumber_daya"]
        romawi = iter(("IV", "V", "VI"))
        for tipe, nama in TIPE_SUMBER_DAYA:
            if not sd[tipe]:
                continue
            judul(next(romawi), f"KEBUTUHAN {nama.upper()} (KOEFISIEN AHSP)", sum(d["biaya"] for d in sd[tipe]))
            for n, d in enumerate(sd[tipe], 1):
                item(str(n), d["nama"], d["jumlah"], d["satuan"], d["keterangan"], d["harga"], d["biaya"])
        if sd["tanpa_analisa"]:
            item("", "Pekerjaan tanpa analisa (tidak masuk kebutuhan): " + ", ".join(sd["tanpa_analisa"]),
                 warna=tema.W["peringatan"])

        judul("VII", "RINCIAN PEKERJAAN (RAB RINCI LANTAI)", x["total"])
        for k in x["rinci"]:
            item("", k["kategori"].upper(), jumlah=k["total"], warna=self._warna_kategori.get(k["kategori"]), tebal=True)
            nomor = 0
            for g in k["grup"]:
                if g["judul"]:
                    nomor += 1
                    item(str(nomor), g["judul"], jumlah=g["total"], tebal=True)
                for it in g["items"]:
                    if not g["judul"]:
                        nomor += 1
                    item("" if g["judul"] else str(nomor), ("      –  " if g["judul"] else "") + it["label"],
                         it["volume"], it["satuan"], it["kode"], it["harga"], it["jumlah"],
                         data=("rekap", it["pekerjaan_id"]))

        t.setRowCount(len(isi))
        n_item = 0
        for r, e in enumerate(isi):
            if e[0] == "lantai":
                t.setItem(r, 0, tema.sel("", data=("lantai", x["lantai"])))
                t.setItem(r, 1, tema.sel(e[1], warna=tema.W["aksen"], tebal=True))
                t.setSpan(r, 1, 1, 5)
                t.setItem(r, 6, tema.sel(tema.format_rupiah(e[2]), "kanan", tema.W["aksen"], tebal=True))
            elif e[0] == "judul":
                _, no, teks, jumlah = e
                t.setItem(r, 0, tema.sel(no, warna=tema.W["aksen"], tebal=True))
                t.setItem(r, 1, tema.sel(teks, warna=tema.W["aksen"], tebal=True))
                t.setSpan(r, 1, 1, 5)
                if jumlah is not None:
                    t.setItem(r, 6, tema.sel(tema.format_rupiah(jumlah), "kanan", tema.W["teks_redup"], tebal=True))
            else:
                _, no, uraian, volume, satuan, ket, harga, jumlah, data, warna, tebal, tooltip = e
                n_item += 1
                t.setItem(r, 0, tema.sel(no, warna=tema.W["teks_samar"], data=data))
                t.setItem(r, 1, tema.sel(uraian, warna=warna, tebal=tebal, tooltip=tooltip or uraian))
                if volume is not None:
                    t.setItem(r, 2, tema.sel(tema.format_angka(volume, 2), "kanan", tebal=tebal))
                t.setItem(r, 3, tema.sel(satuan, "tengah", tema.W["teks_redup"]))
                t.setItem(r, 4, tema.sel(ket, warna=tema.W["teks_redup"], tooltip=tooltip or ket or None))
                if harga is not None:
                    t.setItem(r, 5, tema.sel(tema.format_rupiah(harga), "kanan", tema.W["teks_redup"]))
                if jumlah is not None:
                    t.setItem(r, 6, tema.sel(tema.format_rupiah(jumlah), "kanan", tebal=True))
        tema.atur_lebar(t, 4, isi_konten=(0, 2, 3, 5, 6))  # keterangan (bekisting, besi, batang) melebar
        t.horizontalHeader().setSectionResizeMode(1, QHeaderView.Interactive)
        t.setColumnWidth(1, 400)
        return n_item

    def _buka_lantai(self, nama: str):
        """Tampilkan rincian kebutuhan satu lantai (tetap di mode Per Lantai)."""
        i = self.combo_lantai.findText(nama)
        if i >= 0 and i != self.combo_lantai.currentIndex():
            self.combo_lantai.setCurrentIndex(i)  # memicu _isi_ulang

    # ---------------------------------------------------------------- mode detail

    def _isi_detail(self, baris) -> int:
        t = self.tabel
        t.clearSpans()
        t.clear()
        tema.siapkan_tabel(
            t, ["PEKERJAAN", "ELEMEN / LANTAI", "VOLUME (EDIT)", "HARGA SATUAN (EDIT)", "SUBTOTAL", "STATUS"],
            rata_kanan=(2, 3, 4), tinggi_baris=46,
        )
        baris = self._terurut(baris, {
            0: lambda r: _nama_baris(r).lower(), 1: lambda r: ((r["lantai"] or ""), (r["nama_elemen"] or "").lower()),
            2: lambda r: r["volume_pekerjaan"], 3: lambda r: r["harga_satuan"], 4: lambda r: r["subtotal_biaya"],
            5: lambda r: (bool(r["diedit_manual"] or r.get("harga_manual")), bool(r.get("dimensi_manual"))),
        })
        t.setRowCount(len(baris))
        self._volume_terakhir = {}
        self._harga_terakhir = {}
        for i, r in enumerate(baris):
            hid = r["hasil_id"]
            nama = _nama_baris(r)
            t.setItem(i, 0, tema.sel(
                nama, warna=self._warna_kategori.get(r["kategori"]),
                tooltip=f"{r['kategori']} — {nama}", data=("detail", hid),
            ))
            t.setItem(i, 1, tema.sel(_label_elemen(r), warna=tema.W["teks_redup"], tooltip=_label_elemen(r)))
            spin = SpinVolume(r["volume_pekerjaan"], r["satuan"])
            self._volume_terakhir[hid] = spin.value()
            spin.editingFinished.connect(
                lambda hid=hid, pid=r["pekerjaan_id"], sp=spin: self._volume_diubah(hid, pid, sp.value())
            )
            t.setCellWidget(i, 2, spin)
            harga = SpinHarga(r["harga_satuan"])
            self._harga_terakhir[hid] = harga.value()
            harga.editingFinished.connect(lambda hid=hid, sp=harga: self._harga_sel_diubah(hid, sp))
            t.setCellWidget(i, 3, harga)
            t.setItem(i, 4, tema.sel(tema.format_rupiah(r["subtotal_biaya"]), "kanan", tebal=True))
            t.setItem(i, 5, _sel_status(r["diedit_manual"], r.get("dimensi_manual"), r.get("harga_manual")))
        tema.atur_lebar(t, 0, isi_konten=(4, 5))
        h = t.horizontalHeader()
        h.setSectionResizeMode(1, QHeaderView.Interactive)
        t.setColumnWidth(1, 180)
        h.setSectionResizeMode(2, QHeaderView.Fixed)
        t.setColumnWidth(2, 140)
        h.setSectionResizeMode(3, QHeaderView.Fixed)
        t.setColumnWidth(3, 150)
        return len(baris)

    def _baris_dari_id(self, hasil_id: int) -> int:
        for i in range(self.tabel.rowCount()):
            it = self.tabel.item(i, 0)
            if it is not None and it.data(Qt.UserRole) == ("detail", hasil_id):
                return i
        return -1

    def _volume_diubah(self, hasil_id: int, pekerjaan_id: int, volume_baru: float):
        r0 = self._index.get(hasil_id)
        lama = self._volume_terakhir.get(hasil_id, r0["volume_pekerjaan"] if r0 else volume_baru)
        if abs(volume_baru - lama) < 1e-9:
            return
        sebelum = potret_proyek(self.proyek_id)
        subtotal = update_volume_estimasi(hasil_id, pekerjaan_id, volume_baru)
        self._volume_terakhir[hasil_id] = volume_baru
        r = self._index.get(hasil_id)
        self._catat(f"Ubah volume {r['nama_pekerjaan'] if r else ''}".strip(), sebelum)
        if r is not None:
            r["volume_pekerjaan"] = volume_baru
            r["subtotal_biaya"] = subtotal
            r["diedit_manual"] = 1
            if volume_baru > 0:
                r["harga_satuan"] = subtotal / volume_baru
        i = self._baris_dari_id(hasil_id)
        if i >= 0 and r is not None:
            self.tabel.setItem(i, 4, tema.sel(tema.format_rupiah(subtotal), "kanan", tebal=True))
            self.tabel.setItem(i, 5, _sel_status(True, r.get("dimensi_manual"), r.get("harga_manual")))
        self._perbarui_ringkasan()
        self._tampilkan_rincian()

    # ---------------------------------------------------------------- KF-6 harga, catatan, riwayat

    def _catat(self, teks: str, sebelum: dict):
        """Masukkan perubahan yang sudah tersimpan ke riwayat undo/redo."""
        sesudah = potret_proyek(self.proyek_id)
        if sesudah != sebelum:
            self.riwayat.push(_PerintahPotret(self, teks, sebelum, sesudah))

    def _setelah_riwayat(self, pesan: str):
        self.muat()
        tema.toast(self, pesan)

    def _harga_sel_diubah(self, hasil_id: int, spin):
        nilai = spin.value()
        lama = self._harga_terakhir.get(hasil_id, nilai)
        if abs(nilai - lama) < 0.5:
            return
        if nilai <= 0:  # UC-03 alternatif A: tolak & kembalikan nilai semula
            spin.blockSignals(True)
            spin.setValue(lama)
            spin.blockSignals(False)
            tema.toast(self, "Harga satuan harus lebih besar dari nol", "peringatan")
            return
        self._harga_terakhir[hasil_id] = nilai
        self._harga_diubah([hasil_id], nilai)

    def _harga_diubah(self, hasil_ids, harga):
        """harga None = kembali ke harga master."""
        sebelum = potret_proyek(self.proyek_id)
        try:
            ubah_harga_baris(hasil_ids, harga)
        except NilaiTidakValid as e:
            tema.toast(self, str(e), "peringatan")
            return
        r = self._index.get(hasil_ids[0]) if hasil_ids else None
        nama = r["nama_pekerjaan"] if r else ""
        teks = f"Harga satuan {nama}" if harga is not None else f"Harga master {nama}"
        self._catat(teks, sebelum)
        terpilih = self._kunci_terpilih()
        self.muat()
        self._pilih_kunci(terpilih)
        tema.toast(self, "Perubahan berhasil disimpan")

    def _catatan_diubah(self, hasil_id: int, teks: str):
        sebelum = potret_proyek(self.proyek_id)
        try:
            ubah_catatan(hasil_id, teks)
        except NilaiTidakValid as e:
            tema.toast(self, str(e), "peringatan")
            return
        self._catat("Ubah catatan", sebelum)
        terpilih = self._kunci_terpilih()
        self.muat()
        self._pilih_kunci(terpilih)
        tema.toast(self, "Catatan disimpan")

    def _kunci_terpilih(self):
        baris = self.tabel.currentRow()
        it = self.tabel.item(baris, 0) if baris >= 0 else None
        return it.data(Qt.UserRole) if it else None

    def _pilih_kunci(self, kunci):
        if not kunci:
            return
        for i in range(self.tabel.rowCount()):
            it = self.tabel.item(i, 0)
            if it is not None and it.data(Qt.UserRole) == kunci:
                self.tabel.selectRow(i)
                self.tabel.scrollToItem(it, QTableWidget.PositionAtCenter)
                return

    # ---------------------------------------------------------------- rincian

    def _tampilkan_rincian(self):
        baris = self.tabel.currentRow()
        it = self.tabel.item(baris, 0) if baris >= 0 else None
        data = it.data(Qt.UserRole) if it else None
        if not data or not self.tabel.selectedItems():
            self._panel_bawaan()
            return
        jenis, kunci = data
        if jenis == "lantai":
            terpilih = [x for x in self._rincian_tampil if x["lantai"] == kunci]
            if terpilih:
                self.panel.tampilkan_lantai(terpilih, satu=True, warna=self._warna_kategori,
                                            semua=self._rincian_tampil)
            else:
                self._panel_bawaan()
        elif jenis == "detail" and kunci in self._index:
            self.panel.tampilkan_elemen(self._index[kunci])
        elif jenis == "rekap" and kunci is not None:
            lantai = self.combo_lantai.currentText()  # KF-12: ikut filter lantai
            baris_pekerjaan = [r for r in self._data if r["pekerjaan_id"] == kunci and self._cocok(r, "", "", lantai)]
            self.panel.tampilkan_pekerjaan(kunci, baris_pekerjaan)
        else:
            self._panel_bawaan()

    # ---------------------------------------------------------------- KF-19 ubah dimensi

    def _klik_ganda(self, baris: int, kolom: int):
        if self.mode == self.MODE_LANTAI:
            it = self.tabel.item(baris, 0)
            data = it.data(Qt.UserRole) if it else None
            if data and data[0] == "lantai":
                self._buka_lantai(data[1])
            return
        if self.mode != self.MODE_DETAIL or kolom != 1:
            return
        it = self.tabel.item(baris, 0)
        data = it.data(Qt.UserRole) if it else None
        r = self._index.get(data[1]) if data else None
        if r and r.get("elemen_id") and kolom_dimensi_elemen(r)[0]:
            self.ubah_dimensi(r["elemen_id"])

    def ubah_dimensi(self, elemen_id: int):
        """UC-03 langkah 7-12: dialog dimensi -> konfirmasi -> hitung ulang QTO elemen."""
        elemen = ambil_elemen(elemen_id)
        if elemen is None:
            QMessageBox.warning(self, "Ubah Dimensi", "Elemen tidak ditemukan. Hasil estimasi dimuat ulang.")
            self.muat()
            return
        manual = sum(1 for r in self._data if r["elemen_id"] == elemen_id and (r["diedit_manual"] or r.get("harga_manual")))
        sebelum = potret_proyek(self.proyek_id)
        dialog = DimensiDialog(elemen, manual, self)
        if dialog.exec() != DimensiDialog.Accepted:
            return
        self._catat(f"Ubah dimensi {elemen.get('nama') or ''}".strip(), sebelum)
        self.muat()
        self._pilih_elemen(elemen_id)
        tema.toast(self, "Perubahan berhasil disimpan, QTO elemen dihitung ulang")

    def _pilih_elemen(self, elemen_id: int):
        if self.mode != self.MODE_DETAIL:
            return
        for i in range(self.tabel.rowCount()):
            it = self.tabel.item(i, 0)
            data = it.data(Qt.UserRole) if it else None
            r = self._index.get(data[1]) if data else None
            if r and r["elemen_id"] == elemen_id:
                self.tabel.selectRow(i)
                self.tabel.scrollToItem(it, QTableWidget.PositionAtCenter)
                return

    # ---------------------------------------------------------------- aksi

    def _jalankan_estimasi(self) -> bool:
        sebelum = potret_proyek(self.proyek_id)
        try:
            r = jalankan_di_latar(
                self, "Membaca elemen & menghitung kuantitas...", jalankan_estimasi,
                self.proyek_id, pakai_progress=True,
            )
        except Exception as e:
            tampilkan_galat(self, "Parsing Gagal", e, "Hitung ulang dari IFC", self.proyek_id)
            return False
        self._catat("Hitung ulang dari IFC", sebelum)
        self.muat()
        tampilkan_hasil_proses(self, "Hasil Estimasi", r)
        return True

    def _hitung_ulang(self):
        manual = sum(1 for r in self._data if r["diedit_manual"])
        dimensi = len({r["elemen_id"] for r in self._data if r.get("dimensi_manual")})
        kotak = QMessageBox(self)
        kotak.setIcon(QMessageBox.Question)
        kotak.setWindowTitle("Hitung Ulang dari IFC")
        kotak.setText("Baca ulang file IFC dan hitung ulang seluruh kuantitas?")
        info = "Harga satuan terbaru juga ikut dipakai."
        if dimensi:
            info = f"Dimensi {dimensi} elemen yang diubah manual akan kembali ke dimensi model. " + info
        if manual:
            info = f"{manual} volume yang diedit manual akan diganti hasil perhitungan ulang. " + info
        kotak.setInformativeText(info)
        btn_ya = kotak.addButton("Hitung Ulang", QMessageBox.AcceptRole)
        kotak.addButton("Batal", QMessageBox.RejectRole)
        kotak.exec()
        if kotak.clickedButton() is btn_ya:
            self._jalankan_estimasi()

    def _fokus_cari(self):
        if self.baris_alat.isVisible():
            self.kolom_cari.setFocus()
            self.kolom_cari.selectAll()

    def _pintasan_export(self):
        if self.btn_export.isEnabled():
            self._buka_export()

    def _buka_penulangan(self):
        sebelum = potret_proyek(self.proyek_id)
        dialog = PenulanganDialog(self.proyek_id, self)
        dialog.exec()
        if dialog.diubah:
            self._catat("Ubah tipe penulangan", sebelum)
            self.muat()
            tema.toast(self, "Pembesian dihitung ulang sesuai tipe penulangan")

    def _buka_biaya(self):
        sebelum = potret_proyek(self.proyek_id)
        dialog = BiayaDialog(self.proyek_id, self)
        dialog.exec()
        if dialog.diubah:
            self._catat("Ubah biaya tidak langsung", sebelum)
            self._perbarui_ringkasan()
            tema.toast(self, "Biaya tidak langsung diperbarui")

    # ---------------------------------------------------------------- KF-7 / KF-9 proyek

    def _simpan_file(self):
        simpan_file_proyek(self, self.proyek_id)

    def _duplikat(self):
        hasil = duplikat(self, self.proyek_id)
        if hasil:
            tema.toast(self, f'Proyek "{hasil[1]}" dibuat')
            self.minta_buka_proyek.emit(*hasil)

    def _ubah_info(self):
        sebelum = potret_proyek(self.proyek_id)
        dialog = InfoProyekDialog(self.proyek_id, self)
        if dialog.exec() != InfoProyekDialog.Accepted:
            return
        self._catat("Ubah info proyek", sebelum)
        p = get_proyek(self.proyek_id) or {}
        self.nama_proyek = p.get("nama_proyek") or self.nama_proyek
        self.label_judul.setText(self.nama_proyek)
        if dialog.ifc_berubah:
            self._jalankan_estimasi()
        else:
            self.muat()
            tema.toast(self, "Info proyek disimpan")

    def _buka_parameter(self):
        manual = sum(1 for r in self._data if r["diedit_manual"])
        sebelum = potret_proyek(self.proyek_id)
        dialog = ParameterDialog(self.proyek_id, manual, self)
        if dialog.exec() != ParameterDialog.Accepted or not dialog.diubah:
            return
        self._catat("Ubah parameter aturan", sebelum)
        self.muat()
        tema.toast(self, "Parameter disimpan, kuantitas dihitung ulang")

    def _buka_export(self):
        ExportDialog(self.proyek_id, self.nama_proyek, self).exec()


class PanelRincian(QFrame):
    """Panel kanan: jejak perhitungan baris terpilih."""

    minta_harga = Signal(object)
    minta_ubah_dimensi = Signal(int)  # elemen_id
    minta_harga_baris = Signal(object, object)  # [hasil_id], harga (None = harga master)
    minta_catatan = Signal(int, str)  # hasil_id, teks

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("panel")
        self.setMinimumWidth(300)
        self.setMaximumWidth(460)
        luar = QVBoxLayout(self)
        luar.setContentsMargins(0, 0, 0, 0)
        self._gulir = QScrollArea()
        self._gulir.setWidgetResizable(True)
        self._gulir.setFrameShape(QFrame.NoFrame)
        self._gulir.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        luar.addWidget(self._gulir)
        self._isi = QWidget()
        self._isi.setObjectName("isiPanel")
        self._gulir.setWidget(self._isi)
        self._lay = QVBoxLayout(self._isi)
        self._lay.setContentsMargins(18, 16, 18, 16)
        self._lay.setSpacing(10)
        self.kosongkan()

    def _bersihkan(self):
        tema.kosongkan_layout(self._lay)
        QTimer.singleShot(0, self._sesuaikan_tinggi)

    def _sesuaikan_tinggi(self):
        """QScrollArea memakai minimumSizeHint, yang tidak memperhitungkan teks terbungkus.
        Tinggi minimum isi disetel dari heightForWidth agar rumus panjang tidak terpotong
        melainkan panel bisa digulir."""
        lebar = self._gulir.viewport().width()
        if lebar > 0:
            self._isi.setMinimumHeight(max(self._isi.heightForWidth(lebar), 0))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._sesuaikan_tinggi()

    def kosongkan(self):
        self._bersihkan()
        self._lay.addWidget(tema.label("RINCIAN PERHITUNGAN", "bagian"))
        self._lay.addWidget(
            tema.label(
                "Pilih satu baris di tabel untuk melihat dimensi elemen, asal datanya, "
                "dan rumus yang dipakai rule engine.",
                "subjudul", wrap=True,
            )
        )
        self._lay.addStretch()

    def _baris_nilai(self, kiri: str, kanan: str, chip_teks: str | None = None):
        b = QHBoxLayout()
        b.setSpacing(8)
        kiri_l = tema.label(kiri, "formLabel")
        kiri_l.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Preferred)
        b.addWidget(kiri_l, alignment=Qt.AlignTop)
        # nilai panjang (mis. nama elemen Revit) dibungkus, tidak melebarkan panel
        kanan_l = tema.label(kanan, wrap=True)
        kanan_l.setAlignment(Qt.AlignRight | Qt.AlignTop)
        kanan_l.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        kanan_l.setToolTip(kanan)
        b.addWidget(kanan_l, stretch=1)
        if chip_teks:
            b.addWidget(tema.chip(chip_teks, JENIS_CHIP_SUMBER.get(chip_teks, "netral")))
        self._lay.addLayout(b)

    def tampilkan_elemen(self, r: dict):
        self._bersihkan()
        self._lay.addWidget(tema.label("RINCIAN ELEMEN", "bagian"))
        judul = tema.label(r["nama_pekerjaan"], "judulPanel", wrap=True)
        self._lay.addWidget(judul)
        kelas = r.get("kelas")
        label_kelas = LABEL.get(ElementType(kelas), kelas) if kelas in ElementType._value2member_map_ else (kelas or "-")
        info = QHBoxLayout()
        info.addWidget(tema.chip(r["kategori"] or "-", "netral"))
        info.addWidget(tema.chip(label_kelas, "info"))
        if r["diedit_manual"]:
            info.addWidget(tema.chip("Volume diedit manual", "peringatan"))
        if r.get("dimensi_manual"):
            info.addWidget(tema.chip("Dimensi diubah", "peringatan"))
        info.addStretch()
        self._lay.addLayout(info)
        self._baris_nilai("Elemen", r["nama_elemen"] or "-")
        self._baris_nilai("Lantai", r["lantai"] or "-")
        self._baris_nilai("Entitas IFC", r.get("ifc_type") or "-")
        if r.get("kode_tipe"):
            self._baris_nilai("Tipe", label_tipe(
                r["kelompok_tipe"], r["kode_tipe"], (r["tipe_b_cm"] or 0) / 100 or None, (r["tipe_h_cm"] or 0) / 100
            ))
        if r.get("uraian") and r.get("diameter"):
            self._baris_nilai("Item", r["uraian"])

        self._lay.addWidget(tema.garis())
        self._lay.addWidget(tema.label("DIMENSI ELEMEN" if r.get("dimensi_manual") else "DIMENSI DARI MODEL", "bagian"))
        try:
            sumber = json.loads(r.get("sumber_dimensi") or "{}")
        except ValueError:
            sumber = {}
        ada = False
        for kunci, nama, sat in LABEL_DIMENSI:
            nilai = r.get(kunci)
            if not nilai:
                continue
            ada = True
            asal = sumber.get("volume" if kunci == "volume_elemen" else kunci)
            d = 1 if kunci == "kemiringan" else 3
            self._baris_nilai(nama, f"{tema.format_angka(nilai, d)} {sat}", LABEL_SUMBER.get(asal))
        if not ada:
            self._lay.addWidget(tema.label("Tidak ada dimensi tersimpan untuk elemen ini.", "subjudul"))
        if r.get("elemen_id") and kolom_dimensi_elemen(r)[0]:
            btn = tema.tombol(
                "Ubah Dimensi", "secondary", "ulang",
                "Ubah dimensi elemen lalu hitung ulang kuantitas dan biayanya (KF-19)",
            )
            btn.clicked.connect(lambda _=False, eid=r["elemen_id"]: self.minta_ubah_dimensi.emit(eid))
            self._lay.addSpacing(2)
            self._lay.addWidget(btn)

        self._lay.addWidget(tema.garis())
        self._lay.addWidget(tema.label("RUMUS (RULE ENGINE)", "bagian"))
        rumus = tema.label(r.get("rumus") or "Tidak ada uraian rumus (hasil estimasi versi lama).", "rumus", wrap=True)
        rumus.setTextInteractionFlags(Qt.TextSelectableByMouse)
        rumus.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self._lay.addWidget(rumus)
        if r["diedit_manual"]:
            self._lay.addWidget(
                tema.label(
                    f"Volume saat ini {tema.format_angka(r['volume_pekerjaan'], 3)} {r['satuan']} "
                    "adalah hasil edit manual, bukan hasil rumus di atas.",
                    "peringatan", wrap=True,
                )
            )

        self._lay.addWidget(tema.garis())
        self._baris_nilai("Harga satuan", tema.format_rupiah(r["harga_satuan"]))
        if r.get("harga_manual"):
            master = get_harga_satuan_pekerjaan(r["pekerjaan_id"])
            self._lay.addWidget(tema.label(
                f"Harga khusus baris ini. Harga master (analisa): {tema.format_rupiah(master)}.", "peringatan", wrap=True,
            ))
            btn = tema.tombol("Kembalikan Harga Master", "ghost", "ulang")
            btn.clicked.connect(lambda _=False, hid=r["hasil_id"]: self.minta_harga_baris.emit([hid], None))
            self._lay.addWidget(btn)
        self._baris_nilai("Subtotal", tema.format_rupiah(r["subtotal_biaya"]))

        self._lay.addWidget(tema.garis())
        self._lay.addWidget(tema.label("CATATAN", "bagian"))
        edit = QLineEdit(r.get("catatan") or "")
        edit.setPlaceholderText("mis. sesuai gambar revisi 2, volume dari opname lapangan")
        edit.setMaxLength(500)
        btn = tema.tombol("Simpan Catatan", "secondary")
        btn.setEnabled(False)
        edit.textChanged.connect(lambda t, asli=(r.get("catatan") or ""), b=btn: b.setEnabled(t.strip() != asli))
        simpan = lambda _=False, hid=r["hasil_id"], e=edit: self.minta_catatan.emit(hid, e.text())  # noqa: E731
        btn.clicked.connect(simpan)
        edit.returnPressed.connect(simpan)
        self._lay.addWidget(edit)
        self._lay.addWidget(btn)
        self._lay.addStretch()

    def _baris_kecil(self, kiri: str, kanan: str, warna: str | None = None, tebal: bool = False, ket: str = ""):
        """Satu baris rincian: uraian (terbungkus) di kiri, nilai di kanan, keterangan kecil di bawahnya."""
        b = QHBoxLayout()
        b.setSpacing(8)
        kiri_l = tema.label(kiri, wrap=True)
        kiri_l.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        gaya = (f"color: {warna};" if warna else "") + ("font-weight: 600;" if tebal else "")
        if gaya:
            kiri_l.setStyleSheet(gaya)
        b.addWidget(kiri_l, stretch=1)
        kanan_l = tema.label(kanan)
        kanan_l.setAlignment(Qt.AlignRight | Qt.AlignTop)
        kanan_l.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Preferred)
        if tebal:
            kanan_l.setStyleSheet("font-weight: 600;")
        b.addWidget(kanan_l, alignment=Qt.AlignTop)
        self._lay.addLayout(b)
        if ket:
            k = tema.label(ket, "infoKecil", wrap=True)
            k.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
            self._lay.addWidget(k)

    def tampilkan_lantai(self, daftar: list, satu: bool = False, warna: dict | None = None, semua: list | None = None):
        """Rincian perhitungan per lantai, urut dari lantai terbawah (fondasi) sampai penutup bangunan.
        satu=True: satu lantai dengan bahan, tenaga kerja, dan alat lengkap."""
        self._bersihkan()
        if not daftar:
            self.kosongkan()
            return
        warna = warna or {}
        semua = semua or daftar

        def label(teks, gaya, warna_teks=None):
            """Label terbungkus yang tidak melebarkan panel (angka di kanan tetap terlihat)."""
            lb = tema.label(teks, gaya, wrap=True)
            lb.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
            if warna_teks:
                lb.setStyleSheet(f"color: {warna_teks};")
            self._lay.addWidget(lb)
        n = len(semua)
        angka = tema.format_angka
        if satu:
            label("RINCIAN PERHITUNGAN LANTAI", "bagian")
        else:
            label(f"RINCIAN PERHITUNGAN PER LANTAI ({n} LANTAI)", "bagian")
            label("Urut dari lantai terbawah sampai penutup bangunan. Pilih satu lantai di tabel untuk "
                  "melihat bahan, tenaga kerja, dan alatnya.", "infoKecil")
        lantai_penutup, unsur_penutup = penutup_bangunan(semua)

        for x in daftar:
            urutan = next((i for i, y in enumerate(semua, 1) if y["lantai"] == x["lantai"]), 1)
            self._lay.addWidget(tema.garis())
            label(x["lantai"].upper(), "judulPanel")
            elev = "" if x["elevasi"] is None else f"  ·  elevasi {angka(x['elevasi'], 2)} m"
            label(f"Lantai {urutan} dari {n}{elev}  ·  {x['jumlah_elemen']} elemen", "infoKecil")
            self._baris_kecil("Biaya langsung lantai", tema.format_rupiah(x["total"]), tebal=True)

            # volume pekerjaan per kategori
            for k in pekerjaan_lantai(x["baris"]):
                self._lay.addSpacing(4)
                label(k["kategori"].upper(), "formLabel", warna.get(k["kategori"], tema.W["teks_redup"]))
                for d in k["items"]:
                    self._baris_kecil(d["nama"], f"{angka(d['volume'], 2)} {d['satuan']}")

            # struktur: beton, bekisting, besi per diameter
            rs = ringkas_lantai(x)
            if rs["beton"] or rs["besi"]:
                self._lay.addSpacing(4)
                label("STRUKTUR", "formLabel")
                for m in x["beton_mutu"]:
                    self._baris_kecil(f"Beton {m['mutu']}", f"{angka(m['volume'], 3)} m³")
                if rs["bekisting"]:
                    self._baris_kecil("Bekisting", f"{angka(rs['bekisting'], 2)} m²")
                for k in x["besi"]:
                    self._baris_kecil(
                        f"Besi {k['label']} ({k['jenis']})", f"{angka(k['berat'], 2)} kg",
                        ket=f"{angka(k['berat'], 2)} kg ÷ {angka(k['berat_per_m'], 3)} kg/m' = "
                            f"{angka(k['panjang'], 1)} m' → {k['batang']} batang @ 12 m",
                    )
                if x["besi_rasio"] > 1e-9:
                    self._baris_kecil("Besi asumsi rasio (tanpa diameter)", f"{angka(x['besi_rasio'], 2)} kg")
                if rs["besi"]:
                    self._baris_kecil("Total besi", f"{angka(rs['besi'], 2)} kg", tebal=True,
                                      ket=(f"rasio {angka(rs['besi'] / rs['beton'], 0)} kg/m³ beton" if rs["beton"] else ""))
                for g in x["struktur"]:
                    if not rasio_wajar(g["rasio"]):
                        label(f"⚠ {g['label']}: rasio besi {angka(g['rasio'], 0)} kg/m³ di luar "
                              f"{RASIO_WAJAR[0]:.0f}–{RASIO_WAJAR[1]:.0f} kg/m³, periksa dimensi di model.", "peringatan")

            # bahan, tenaga kerja, alat (AHSP)
            for tipe, nama in TIPE_SUMBER_DAYA:
                items = x["sumber_daya"][tipe]
                if not items or (not satu and tipe != "bahan"):
                    continue
                tampil = items if satu else items[:6]
                self._lay.addSpacing(4)
                label(nama.upper() + ("" if satu else " UTAMA") + " (KOEFISIEN AHSP)", "formLabel")
                for d in tampil:
                    ket = ""
                    if "zak" in d["keterangan"]:
                        ket = f"{angka(d['jumlah'], 2)} kg ÷ {BERAT_ZAK_SEMEN} kg = {d['keterangan'].replace('≈ ', '')}"
                    self._baris_kecil(d["nama"], f"{angka(d['jumlah'], 2)} {d['satuan']}", ket=ket)
                if len(items) > len(tampil):
                    self._lay.addWidget(tema.label(f"+ {len(items) - len(tampil)} bahan lain", "infoKecil"))

            # penutup bangunan
            unsur = penutup_lantai(x)
            if x["lantai"] == lantai_penutup:
                unsur = unsur_penutup
            if unsur and (x["lantai"] == lantai_penutup or satu):
                self._lay.addSpacing(4)
                judul = "PENUTUP BANGUNAN" if x["lantai"] == lantai_penutup else "ATAP / PLAFON DI LANTAI INI"
                label(judul, "formLabel")
                for jenis, uraian in unsur:
                    self._baris_kecil(jenis, "", tebal=True, ket=uraian)

        if not satu and lantai_penutup is None:
            self._lay.addWidget(tema.garis())
            label("Model tidak memuat atap, dak beton, maupun plafon, sehingga penutup bangunan tidak tercatat.",
                  "peringatan")
        self._lay.addStretch()

    def tampilkan_pekerjaan(self, pekerjaan_id: int, baris: list):
        self._bersihkan()
        if not baris:
            self.kosongkan()
            return
        r0 = baris[0]
        volume = sum(r["volume_pekerjaan"] for r in baris)
        jumlah = sum(r["subtotal_biaya"] for r in baris)
        self._lay.addWidget(tema.label(f"{r0['kode_ahsp']}  ·  {r0['kategori']}", "bagian"))
        self._lay.addWidget(tema.label(r0["nama_pekerjaan"], "judulPanel", wrap=True))
        self._baris_nilai("Volume total", f"{tema.format_angka(volume, 3)} {r0['satuan']}")
        self._baris_nilai("Dari", f"{len(baris)} elemen")
        self._baris_nilai("Jumlah harga", tema.format_rupiah(jumlah))

        self._lay.addWidget(tema.garis())
        self._lay.addWidget(tema.label(f"ANALISA HARGA SATUAN PER {r0['satuan'].upper()}", "bagian"))
        komponen = analisa_pekerjaan(pekerjaan_id)
        subtotal = {"bahan": 0.0, "upah": 0.0, "alat": 0.0}
        for k in komponen:
            subtotal[k["tipe"]] += k["jumlah"]
            b = QVBoxLayout()
            b.setSpacing(0)
            atas = QHBoxLayout()
            nama = tema.label(k["nama_komponen"].replace(" [PLACEHOLDER]", ""), wrap=True)
            nama.setStyleSheet(f"color: {tema.WARNA_TIPE[k['tipe']]};")
            atas.addWidget(nama, stretch=1)
            atas.addWidget(tema.label(tema.format_rupiah(k["jumlah"])))
            b.addLayout(atas)
            b.addWidget(tema.label(
                f"{tema.format_angka(k['koefisien'], 4)} {k['satuan']} × {tema.format_rupiah(k['harga_satuan'])}",
                "infoKecil",
            ))
            self._lay.addLayout(b)
        self._lay.addWidget(tema.garis())
        for tipe in ("bahan", "upah", "alat"):
            if subtotal[tipe]:
                self._baris_nilai(f"Jumlah {LABEL_TIPE[tipe].lower()}", tema.format_rupiah(subtotal[tipe]))
        from database.estimasi_repository import BUK_RATE

        dasar = sum(subtotal.values())
        self._baris_nilai(f"Biaya umum & keuntungan {BUK_RATE:.0%}", tema.format_rupiah(dasar * BUK_RATE))
        self._baris_nilai("Harga satuan", tema.format_rupiah(dasar * (1 + BUK_RATE)))
        btn = tema.tombol("Ubah Harga Dasar", "secondary", "harga")
        btn.clicked.connect(lambda: self.minta_harga.emit(pekerjaan_id))
        self._lay.addSpacing(4)
        self._lay.addWidget(btn)

        # KF-6: harga satuan khusus proyek ini (mis. hasil negosiasi), tanpa mengubah harga master
        self._lay.addWidget(tema.garis())
        self._lay.addWidget(tema.label("HARGA KHUSUS PROYEK INI", "bagian"))
        ids = [r["hasil_id"] for r in baris]
        manual = [r for r in baris if r.get("harga_manual")]
        spin = SpinHarga(jumlah / volume if volume else dasar * (1 + BUK_RATE))
        spin.setMinimumHeight(34)
        self._lay.addWidget(spin)
        if manual:
            self._lay.addWidget(tema.label(
                f"{len(manual)} dari {len(baris)} baris memakai harga khusus.", "peringatan", wrap=True,
            ))
        aksi = QHBoxLayout()
        pakai = tema.tombol("Pakai Harga Ini", "primary")
        pakai.clicked.connect(lambda: self.minta_harga_baris.emit(ids, spin.value()))
        aksi.addWidget(pakai)
        if manual:
            master = tema.tombol("Harga Master", "ghost", "ulang")
            master.clicked.connect(lambda: self.minta_harga_baris.emit(ids, None))
            aksi.addWidget(master)
        self._lay.addLayout(aksi)
        self._lay.addStretch()


def _nama_baris(r: dict) -> str:
    """Nama pekerjaan; pembesian rinci ditambah uraian tulangannya (mis. '... — Sengkang Ø8-150')."""
    if r.get("uraian") and r.get("diameter"):
        return f"{r['nama_pekerjaan']} — {r['uraian']}"
    return r["nama_pekerjaan"]


def _label_elemen(r: dict) -> str:
    label = r["nama_elemen"] or "-"
    if r["lantai"]:
        label += f"  ·  {r['lantai']}"
    return label


def kolom_dimensi_elemen(r: dict):
    kelas = r.get("kelas")
    if kelas not in ElementType._value2member_map_:
        return (), ()
    return kolom_dimensi(ElementType(kelas))


def _sel_status(manual, dimensi_manual=False, harga_manual=None) -> QTableWidgetItem:
    if manual or harga_manual:
        ket = [t for t, ada in (("volume diubah manual", manual), ("harga satuan khusus", harga_manual)) if ada]
        return tema.sel("●  Manual", warna=tema.W["peringatan"], tebal=True, tooltip=", ".join(ket).capitalize())
    if dimensi_manual:
        return tema.sel(
            "●  Dimensi diubah", warna=tema.W["aksen"], tebal=True,
            tooltip="Dimensi elemen diubah pengguna; volume dihitung ulang oleh rule engine",
        )
    return tema.sel("●  Otomatis", warna=tema.W["sukses"], tooltip="Volume dihitung dari model IFC")


def _romawi(n: int) -> str:
    out = ""
    for nilai, sim in ((10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I")):
        while n >= nilai:
            out += sim
            n -= nilai
    return out

