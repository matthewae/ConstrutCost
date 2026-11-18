"""
Halaman Riwayat Aktivitas (KF-15): daftar aktivitas penting yang tercatat (import, edit, ubah harga,
export, simpan/buka proyek, kesalahan) dengan pencarian, filter jenis & tingkat, pengurutan, dan
rincian teknis kesalahan. Tombol "Buka Folder Log" membuka folder file log harian.
"""

from PySide6.QtCore import Qt, QTimer, QUrl
from PySide6.QtGui import QDesktopServices, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QHBoxLayout,
    QLineEdit,
    QPlainTextEdit,
    QSplitter,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)

from aktivitas import JENIS, daftar_aktivitas
from gui import tema
from lokasi import folder_log

WARNA_TINGKAT = {"INFO": "teks_redup", "PERINGATAN": "peringatan", "GALAT": "bahaya"}


class AktivitasPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("halaman")
        self._data = []
        root = QVBoxLayout(self)
        root.setContentsMargins(32, 26, 32, 22)
        root.setSpacing(14)

        kepala = QHBoxLayout()
        kol, _, _ = tema.header_halaman(
            "Riwayat Aktivitas",
            "Catatan aktivitas penting: import, edit hasil, harga satuan, export, file proyek, dan kesalahan.",
        )
        kepala.addLayout(kol)
        kepala.addStretch()
        btn_folder = tema.tombol("Buka Folder Log", "secondary", "file", f"Folder file log harian:\n{folder_log()}")
        btn_folder.clicked.connect(self._buka_folder)
        btn_muat = tema.tombol("Muat Ulang", "secondary", "ulang")
        btn_muat.clicked.connect(self.muat)
        kepala.addWidget(btn_folder, alignment=Qt.AlignTop)
        kepala.addWidget(btn_muat, alignment=Qt.AlignTop)
        root.addLayout(kepala)

        alat = QHBoxLayout()
        alat.setSpacing(10)
        self.kolom_cari = QLineEdit()
        tema.pasang_ikon_cari(self.kolom_cari)
        self.kolom_cari.setPlaceholderText("Cari aktivitas atau nama proyek...   (Ctrl+F)")
        self.kolom_cari.setClearButtonEnabled(True)
        self._tunda = QTimer(self)
        self._tunda.setSingleShot(True)
        self._tunda.setInterval(250)
        self._tunda.timeout.connect(self.muat)
        self.kolom_cari.textChanged.connect(lambda _: self._tunda.start())
        self.combo_jenis = QComboBox()
        self.combo_jenis.addItem("Semua jenis", None)
        for k, v in JENIS.items():
            self.combo_jenis.addItem(v, k)
        self.combo_jenis.setSizeAdjustPolicy(QComboBox.AdjustToContents)
        self.combo_jenis.currentIndexChanged.connect(self.muat)
        self.combo_tingkat = QComboBox()
        for teks, nilai in (("Semua tingkat", None), ("Peringatan & kesalahan", "PERINGATAN"), ("Kesalahan saja", "GALAT")):
            self.combo_tingkat.addItem(teks, nilai)
        self.combo_tingkat.currentIndexChanged.connect(self._isi)
        self.label_jumlah = tema.label("", "subjudul")
        alat.addWidget(self.kolom_cari, stretch=1)
        alat.addWidget(self.combo_jenis)
        alat.addWidget(self.combo_tingkat)
        alat.addWidget(self.label_jumlah)
        root.addLayout(alat)

        split = QSplitter(Qt.Vertical)
        split.setChildrenCollapsible(False)
        split.setHandleWidth(12)
        self.tabel = QTableWidget()
        tema.pasang_teks_kosong(self.tabel, "Tidak ada aktivitas", "Ubah kata kunci atau filter jenis / tingkat.")
        tema.siapkan_tabel(self.tabel, ["WAKTU", "TINGKAT", "JENIS", "PROYEK", "AKTIVITAS"], tinggi_baris=36)
        tema.atur_lebar(self.tabel, 4, isi_konten=(0, 1, 2, 3))
        tema.siapkan_urut(self.tabel)
        self.tabel.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tabel.itemSelectionChanged.connect(self._tampilkan_rincian)
        split.addWidget(self.tabel)
        self.rincian = QPlainTextEdit()
        self.rincian.setReadOnly(True)
        self.rincian.setPlaceholderText("Pilih satu baris untuk melihat rincian aktivitas.")
        self.rincian.setObjectName("rincianLog")
        split.addWidget(self.rincian)
        split.setSizes([520, 140])
        root.addWidget(split, stretch=1)
        root.addWidget(tema.label(
            f"File log harian (disimpan 30 hari): {folder_log() / 'coststruct.log'}", "petunjuk",
        ))
        QShortcut(QKeySequence("Ctrl+F"), self, activated=lambda: (self.kolom_cari.setFocus(), self.kolom_cari.selectAll()))

    def muat(self, *_):
        self._data = daftar_aktivitas(jenis=self.combo_jenis.currentData(), kata=self.kolom_cari.text().strip() or None)
        self._isi()

    def _isi(self, *_):
        tingkat = self.combo_tingkat.currentData()
        boleh = {"PERINGATAN": ("PERINGATAN", "GALAT"), "GALAT": ("GALAT",)}.get(tingkat)
        baris = [r for r in self._data if boleh is None or r["tingkat"] in boleh]
        t = self.tabel
        t.setSortingEnabled(False)
        t.setRowCount(len(baris))
        for i, r in enumerate(baris):
            warna = tema.W[WARNA_TINGKAT.get(r["tingkat"], "teks_redup")]
            t.setItem(i, 0, tema.sel(r["waktu"], warna=tema.W["teks_redup"], data=r["id"], urut=r["id"]))
            t.setItem(i, 1, tema.sel(f"●  {r['tingkat'].capitalize()}", warna=warna, tebal=r["tingkat"] != "INFO"))
            t.setItem(i, 2, tema.sel(JENIS.get(r["jenis"], r["jenis"])))
            proyek = r["nama_proyek"] or (f"(proyek #{r['proyek_id']} dihapus)" if r["proyek_id"] else "-")
            t.setItem(i, 3, tema.sel(proyek, warna=tema.W["teks_redup"]))
            t.setItem(i, 4, tema.sel(r["pesan"], tooltip=r["pesan"]))
        t.setSortingEnabled(True)
        self.label_jumlah.setText(f"{len(baris)} aktivitas")
        self.rincian.clear()

    def _tampilkan_rincian(self):
        baris = self.tabel.currentRow()
        it = self.tabel.item(baris, 0) if baris >= 0 else None
        r = next((x for x in self._data if it and x["id"] == it.data(Qt.UserRole)), None)
        if r is None:
            self.rincian.clear()
            return
        teks = f"{r['waktu']}  ·  {r['tingkat']}  ·  {JENIS.get(r['jenis'], r['jenis'])}\n{r['pesan']}"
        if r.get("detail"):
            teks += f"\n\nRincian teknis:\n{r['detail']}"
        self.rincian.setPlainText(teks)

    def _buka_folder(self):
        folder = folder_log()
        folder.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))
