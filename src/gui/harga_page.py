"""
Halaman Kelola Harga Satuan (KF-5 / UC-04).

Tab "Harga Dasar"      : daftar harga bahan, upah, dan alat beserta merk. Harga yang diubah di sini
                         berlaku untuk semua pekerjaan yang memakainya. Tambah material baru
                         (UC-04 skenario alternatif), kembalikan ke harga bawaan, riwayat perubahan.
Tab "Analisa Pekerjaan": analisa harga satuan (AHSP) setiap pekerjaan: koefisien x harga dasar,
                         jumlah bahan/upah/alat, BUK, dan harga satuan. Komponen tambahan (mis. alat)
                         bisa ditambahkan.
"Terapkan ke Estimasi" menghitung ulang subtotal semua proyek dengan harga terbaru.
"""

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QAbstractSpinBox,
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QCompleter,
    QDialog,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSplitter,
    QStackedWidget,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)

from database.estimasi_repository import BUK_RATE
from database.harga_repository import (
    LABEL_TIPE,
    TIPE,
    HargaTidakValid,
    analisa_pekerjaan,
    daftar_pekerjaan,
    daftar_sumber_daya,
    hapus_komponen,
    hapus_sumber_daya,
    jumlah_estimasi_kedaluwarsa,
    kembalikan_harga_bawaan,
    pekerjaan_pemakai,
    riwayat_harga,
    tambah_komponen,
    tambah_sumber_daya,
    terapkan_ke_estimasi,
    ubah_sumber_daya,
)
from gui import tema

SATUAN_UMUM = ["kg", "m3", "m2", "m'", "buah", "lembar", "batang", "liter", "sak", "unit", "set", "OH", "jam", "hari"]
SEMUA_JENIS = "Semua jenis"
SEMUA_KATEGORI = "Semua kategori"


def _nama_tampil(nama: str) -> str:
    return nama.replace(" [PLACEHOLDER]", "")


def _status(sd: dict):
    """(teks, jenis chip) status harga dasar."""
    if sd.get("harga_bawaan") is None:
        return "Tambahan", "netral"
    if sd.get("diubah_manual"):
        return "Diubah", "info"
    if sd.get("sumber") == "Placeholder":
        return "Placeholder", "peringatan"
    if sd.get("sumber") == "Proxy HSPK":
        return "Proxy HSPK", "peringatan"
    return "HSPK", "sukses"


def _spin_harga() -> QDoubleSpinBox:
    s = QDoubleSpinBox()
    s.setRange(0, 1_000_000_000_000)
    s.setDecimals(2)
    s.setPrefix("Rp ")
    s.setGroupSeparatorShown(True)
    s.setButtonSymbols(QAbstractSpinBox.NoButtons)
    s.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
    return s


class HargaPage(QWidget):
    harga_diterapkan = Signal()

    TAB_DASAR, TAB_ANALISA = 0, 1

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("halaman")

        root = QVBoxLayout(self)
        root.setContentsMargins(32, 26, 32, 22)
        root.setSpacing(14)

        kepala = QHBoxLayout()
        kol, _, _ = tema.header_halaman(
            "Harga Satuan",
            "Harga dasar bahan, upah, dan alat, serta analisa harga satuan pekerjaan (AHSP). "
            f"Harga satuan pekerjaan = jumlah komponen + biaya umum & keuntungan {BUK_RATE:.0%}.",
        )
        kepala.addLayout(kol, stretch=1)
        root.addLayout(kepala)

        self.banner = tema.Banner("info")
        root.addWidget(self.banner)

        # --- Tab segmen ---
        baris_tab = QHBoxLayout()
        baris_tab.setSpacing(0)
        self.grup_tab = QButtonGroup(self)
        for i, (teks, posisi) in enumerate((("Harga Dasar", "kiri"), ("Analisa Pekerjaan (AHSP)", "kanan"))):
            b = QPushButton(teks)
            b.setObjectName("segmen")
            b.setProperty("posisi", posisi)
            b.setCheckable(True)
            b.setCursor(Qt.PointingHandCursor)
            self.grup_tab.addButton(b, i)
            baris_tab.addWidget(b)
        baris_tab.addStretch()
        root.addLayout(baris_tab)

        self.stack = QStackedWidget()
        self.tab_dasar = TabHargaDasar(self)
        self.tab_analisa = TabAnalisa(self)
        self.stack.addWidget(self.tab_dasar)
        self.stack.addWidget(self.tab_analisa)
        root.addWidget(self.stack, stretch=1)

        self.grup_tab.idClicked.connect(self.ganti_tab)
        self.grup_tab.button(self.TAB_DASAR).setChecked(True)
        self.tab_dasar.harga_berubah.connect(self._setelah_harga_berubah)
        self.tab_analisa.harga_berubah.connect(self._setelah_harga_berubah)
        self.tab_analisa.minta_ubah_harga.connect(self.fokus_sumber_daya)

        self._perbarui_banner()

    def ganti_tab(self, idx: int):
        self.grup_tab.button(idx).setChecked(True)
        self.stack.setCurrentIndex(idx)
        if idx == self.TAB_ANALISA:
            self.tab_analisa.muat()
        else:
            self.tab_dasar.muat()

    def muat(self):
        self.tab_dasar.muat()
        self.tab_analisa.muat()
        self._perbarui_banner()

    def fokus_pekerjaan(self, pekerjaan_id):
        self.ganti_tab(self.TAB_ANALISA)
        if pekerjaan_id is not None:
            self.tab_analisa.pilih(pekerjaan_id)

    def fokus_sumber_daya(self, sumber_daya_id):
        self.ganti_tab(self.TAB_DASAR)
        self.tab_dasar.pilih(sumber_daya_id)

    def _setelah_harga_berubah(self):
        self._perbarui_banner()

    def _perbarui_banner(self):
        n = jumlah_estimasi_kedaluwarsa()
        if n:
            self.banner.tampilkan(
                f"Ada perubahan harga yang belum diterapkan: {n} baris estimasi proyek masih memakai harga lama.",
                "Terapkan ke Estimasi",
                self.terapkan,
            )
        else:
            self.banner.hide()

    def terapkan(self):
        """UC-04 langkah 9-10: hitung ulang total estimasi dengan harga terbaru."""
        n = terapkan_ke_estimasi()
        self._perbarui_banner()
        tema.toast(self, f"Harga terbaru diterapkan pada {n} baris estimasi")
        self.harga_diterapkan.emit()


# ====================================================================
# Tab Harga Dasar
# ====================================================================


class TabHargaDasar(QWidget):
    harga_berubah = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._semua = []
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(12)

        alat = QHBoxLayout()
        alat.setSpacing(10)
        self.kolom_cari = QLineEdit()
        self.kolom_cari.setPlaceholderText("Cari nama bahan, upah, alat, atau merk...   (Ctrl+F)")
        self.kolom_cari.setClearButtonEnabled(True)
        self.kolom_cari.textChanged.connect(lambda _: self._tunda_cari.start())
        self.combo_jenis = QComboBox()
        self.combo_jenis.addItems([SEMUA_JENIS] + [LABEL_TIPE[t] for t in TIPE])
        self.combo_jenis.currentIndexChanged.connect(self._isi_tabel)
        self.cek_dipakai = QCheckBox("Hanya yang dipakai pekerjaan")
        self.cek_dipakai.setToolTip(
            "Daftar HSPK berisi ribuan harga dasar. Centang untuk hanya menampilkan yang dipakai di\n"
            "analisa pekerjaan, yang sudah Anda ubah, dan material tambahan Anda."
        )
        self.cek_dipakai.setChecked(True)
        self.cek_dipakai.toggled.connect(self._isi_tabel)
        # pencarian di ribuan baris: tunggu sebentar setelah berhenti mengetik
        self._tunda_cari = QTimer(self, singleShot=True, interval=220, timeout=self._isi_tabel)
        self.label_jumlah = tema.label("", "subjudul")
        btn_tambah = tema.tombol("Tambah Material", "secondary", "tambah", "Tambah bahan, upah, atau alat baru")
        btn_tambah.clicked.connect(self._tambah)
        alat.addWidget(self.kolom_cari, stretch=1)
        alat.addWidget(self.combo_jenis)
        alat.addWidget(self.cek_dipakai)
        alat.addWidget(self.label_jumlah)
        alat.addWidget(btn_tambah)
        lay.addLayout(alat)

        split = QSplitter(Qt.Horizontal)
        split.setChildrenCollapsible(False)
        split.setHandleWidth(14)
        self.tabel = QTableWidget()
        tema.siapkan_tabel(
            self.tabel, ["JENIS", "NAMA", "MERK", "SATUAN", "HARGA", "STATUS", "DIPAKAI"],
            rata_kanan=(4, 6), tinggi_baris=40,
        )
        tema.atur_lebar(self.tabel, 1, isi_konten=(0, 2, 3, 4, 5, 6))
        tema.siapkan_urut(self.tabel)  # KF-16: klik judul kolom untuk mengurutkan
        self.tabel.itemSelectionChanged.connect(self._pilih_berubah)
        split.addWidget(self.tabel)
        self.editor = PanelEditorHarga(self)
        self.editor.tersimpan.connect(self._setelah_simpan)
        split.addWidget(self.editor)
        split.setStretchFactor(0, 1)
        split.setSizes([900, 300])
        lay.addWidget(split, stretch=1)

        QShortcut(QKeySequence("Ctrl+F"), self, activated=lambda: (self.kolom_cari.setFocus(), self.kolom_cari.selectAll()))
        self.muat()

    def muat(self, pilih_id=None):
        pilih_id = pilih_id if pilih_id is not None else self._id_terpilih()
        self._semua = daftar_sumber_daya()
        self._isi_tabel()
        if pilih_id is not None:
            self.pilih(pilih_id)

    def _id_terpilih(self):
        r = self.tabel.currentRow()
        it = self.tabel.item(r, 0) if r >= 0 else None
        return it.data(Qt.UserRole) if it and self.tabel.selectedItems() else None

    def _isi_tabel(self, *_):
        kata = self.kolom_cari.text().strip().lower()
        jenis = self.combo_jenis.currentText()
        hanya_dipakai = self.cek_dipakai.isChecked()
        baris = []
        for sd in self._semua:
            if jenis != SEMUA_JENIS and LABEL_TIPE[sd["tipe"]] != jenis:
                continue
            if hanya_dipakai and not (sd["jumlah_pekerjaan"] or sd["diubah_manual"] or sd["harga_bawaan"] is None):
                continue
            if kata and kata not in f"{sd['nama']} {sd['merk'] or ''}".lower():
                continue
            baris.append(sd)
        pilih = self._id_terpilih()
        self.tabel.blockSignals(True)
        self.tabel.setUpdatesEnabled(False)
        self.tabel.setSortingEnabled(False)  # KF-16: isi dulu, lalu urutkan sesuai kolom pilihan
        self.tabel.setRowCount(len(baris))
        for i, sd in enumerate(baris):
            status, jenis_chip = _status(sd)
            warna_status = {
                "sukses": tema.W["sukses"], "peringatan": tema.W["peringatan"], "info": tema.W["aksen_hover"],
            }.get(jenis_chip, tema.W["teks_redup"])
            self.tabel.setItem(i, 0, tema.sel(LABEL_TIPE[sd["tipe"]], warna=tema.WARNA_TIPE[sd["tipe"]], tebal=True, data=sd["id"]))
            self.tabel.setItem(i, 1, tema.sel(_nama_tampil(sd["nama"]), tooltip=sd["nama"]))
            self.tabel.setItem(i, 2, tema.sel(sd["merk"] or "-", warna=tema.W["teks_redup"] if not sd["merk"] else None))
            self.tabel.setItem(i, 3, tema.sel(sd["satuan"], "tengah", tema.W["teks_redup"]))
            self.tabel.setItem(i, 4, tema.sel(tema.format_rupiah(sd["harga"], 2 if sd["harga"] < 100 else 0), "kanan", tebal=True, urut=sd["harga"]))
            self.tabel.setItem(i, 5, tema.sel(f"●  {status}", warna=warna_status))
            n = sd["jumlah_pekerjaan"]
            self.tabel.setItem(i, 6, tema.sel(f"{n} pekerjaan" if n else "-", "kanan", tema.W["teks_redup"], urut=n))
        self.tabel.setSortingEnabled(True)
        self.tabel.setUpdatesEnabled(True)
        self.tabel.blockSignals(False)
        self.label_jumlah.setText(f"{len(baris):,} dari {len(self._semua):,}".replace(",", "."))
        if pilih is not None:
            self.pilih(pilih)
        else:
            self.editor.kosongkan()

    def pilih(self, sumber_daya_id):
        for i in range(self.tabel.rowCount()):
            if self.tabel.item(i, 0).data(Qt.UserRole) == sumber_daya_id:
                self.tabel.selectRow(i)
                self.tabel.scrollToItem(self.tabel.item(i, 0))
                self._pilih_berubah()
                return
        # tersembunyi oleh filter -> bersihkan filter lalu coba lagi sekali
        if self.kolom_cari.text() or self.combo_jenis.currentIndex() or self.cek_dipakai.isChecked():
            self.kolom_cari.blockSignals(True)
            self.kolom_cari.clear()
            self.kolom_cari.blockSignals(False)
            self.combo_jenis.setCurrentIndex(0)
            self.cek_dipakai.setChecked(False)
            self.pilih(sumber_daya_id)

    def _pilih_berubah(self):
        sid = self._id_terpilih()
        sd = next((s for s in self._semua if s["id"] == sid), None)
        if sd:
            self.editor.tampilkan(sd)
        else:
            self.editor.kosongkan()

    def _setelah_simpan(self, sid, pesan):
        self.muat(pilih_id=sid)
        tema.toast(self, pesan)
        self.harga_berubah.emit()

    def _tambah(self):
        dlg = TambahSumberDayaDialog(self)
        if dlg.exec():
            self.muat(pilih_id=dlg.sumber_daya_id)
            tema.toast(self, "Material baru ditambahkan")
            self.harga_berubah.emit()


class PanelEditorHarga(QFrame):
    """Form ubah harga & merk satu sumber daya (UC-04 langkah 3-8)."""

    tersimpan = Signal(object, str)  # sumber_daya_id (None bila dihapus), pesan

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("panel")
        self.setMinimumWidth(290)
        self.setMaximumWidth(440)
        self._sd = None
        luar = QVBoxLayout(self)
        luar.setContentsMargins(0, 0, 0, 0)
        gulir = QScrollArea()
        gulir.setWidgetResizable(True)
        gulir.setFrameShape(QFrame.NoFrame)
        luar.addWidget(gulir)
        isi = QWidget()
        isi.setObjectName("isiPanel")
        gulir.setWidget(isi)
        lay = QVBoxLayout(isi)
        lay.setContentsMargins(18, 16, 18, 16)
        lay.setSpacing(10)

        self.kosong = tema.label(
            "Pilih satu baris untuk mengubah harga atau merk. Perubahan berlaku untuk semua "
            "pekerjaan yang memakai bahan / upah / alat tersebut.",
            "subjudul", wrap=True,
        )
        lay.addWidget(tema.label("UBAH HARGA DASAR", "bagian"))
        lay.addWidget(self.kosong)

        self.form = QWidget()
        f = QVBoxLayout(self.form)
        f.setContentsMargins(0, 0, 0, 0)
        f.setSpacing(10)
        self.judul = tema.label("", "judulPanel", wrap=True)
        f.addWidget(self.judul)
        chip_baris = QHBoxLayout()
        self.chip_jenis = tema.chip("", "info")
        self.chip_status = tema.chip("", "netral")
        chip_baris.addWidget(self.chip_jenis)
        chip_baris.addWidget(self.chip_status)
        chip_baris.addStretch()
        f.addLayout(chip_baris)

        form = QFormLayout()
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(10)
        form.setLabelAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.edit_merk = QLineEdit()
        self.edit_merk.setPlaceholderText("mis. Tiga Roda, Holcim, ...")
        self.spin_harga = _spin_harga()
        self.label_satuan = tema.label("", "formLabel")
        harga_baris = QHBoxLayout()
        harga_baris.addWidget(self.spin_harga, stretch=1)
        harga_baris.addWidget(self.label_satuan)
        form.addRow(tema.label("Merk", "formLabel"), self.edit_merk)
        form.addRow(tema.label("Harga", "formLabel"), harga_baris)
        f.addLayout(form)
        self.label_bawaan = tema.label("", "infoKecil", wrap=True)
        f.addWidget(self.label_bawaan)
        self.label_galat = tema.label("", "galat", wrap=True)
        self.label_galat.hide()
        f.addWidget(self.label_galat)

        tombol = QHBoxLayout()
        self.btn_simpan = tema.tombol("Simpan", "primary")
        self.btn_simpan.clicked.connect(self._simpan)
        self.btn_bawaan = tema.tombol("Kembalikan ke Bawaan", "ghost", "ulang")
        self.btn_bawaan.clicked.connect(self._kembalikan)
        tombol.addWidget(self.btn_simpan)
        tombol.addWidget(self.btn_bawaan)
        tombol.addStretch()
        f.addLayout(tombol)
        self.btn_hapus = tema.tombol("Hapus Material", "danger")
        self.btn_hapus.clicked.connect(self._hapus)
        f.addWidget(self.btn_hapus, alignment=Qt.AlignLeft)
        for w in (self.edit_merk, self.spin_harga):
            w.installEventFilter(self)
        self.edit_merk.returnPressed.connect(self._simpan)

        f.addWidget(tema.garis())
        self.label_pemakai = tema.label("", "bagian")
        f.addWidget(self.label_pemakai)
        self.daftar_pemakai = tema.label("", "subjudul", wrap=True)
        f.addWidget(self.daftar_pemakai)
        f.addWidget(tema.garis())
        f.addWidget(tema.label("RIWAYAT PERUBAHAN", "bagian"))
        self.daftar_riwayat = tema.label("", "subjudul", wrap=True)
        f.addWidget(self.daftar_riwayat)
        lay.addWidget(self.form)
        lay.addStretch()
        self.kosongkan()

    def eventFilter(self, obj, event):
        # Enter di kotak harga = simpan
        if obj is self.spin_harga and event.type() == event.Type.KeyPress and event.key() in (Qt.Key_Return, Qt.Key_Enter):
            self._simpan()
            return True
        return super().eventFilter(obj, event)

    def kosongkan(self):
        self._sd = None
        self.form.hide()
        self.kosong.show()

    def tampilkan(self, sd: dict):
        self._sd = sd
        self.kosong.hide()
        self.form.show()
        self.label_galat.hide()
        self.judul.setText(_nama_tampil(sd["nama"]))
        tema.set_chip(self.chip_jenis, LABEL_TIPE[sd["tipe"]], "info")
        teks, jenis = _status(sd)
        tema.set_chip(self.chip_status, teks, jenis)
        self.edit_merk.setText(sd["merk"] or "")
        self.spin_harga.setValue(sd["harga"])
        self.label_satuan.setText(f"/ {sd['satuan']}")
        if sd["harga_bawaan"] is not None:
            asal = sd["sumber"] or "seed"
            self.label_bawaan.setText(f"Harga bawaan: {tema.format_rupiah(sd['harga_bawaan'], 2)} ({asal})")
        else:
            self.label_bawaan.setText("Material tambahan pengguna.")
        self.btn_bawaan.setVisible(sd["harga_bawaan"] is not None)
        self.btn_bawaan.setEnabled(bool(sd["diubah_manual"]))
        self.btn_hapus.setVisible(sd["harga_bawaan"] is None)
        self.btn_hapus.setEnabled(not sd["jumlah_pekerjaan"])
        self.btn_hapus.setToolTip("" if not sd["jumlah_pekerjaan"] else "Masih dipakai di analisa pekerjaan")

        pemakai = pekerjaan_pemakai(sd["id"])
        self.label_pemakai.setText(f"DIPAKAI DI {len(pemakai)} PEKERJAAN")
        self.daftar_pemakai.setText(
            "\n".join(
                f"• {p['nama_pekerjaan']}  ({tema.format_angka(p['koefisien'], 4)} {sd['satuan']})" for p in pemakai[:12]
            ) + (f"\n• dan {len(pemakai) - 12} lainnya" if len(pemakai) > 12 else "")
            or "Belum dipakai. Tambahkan ke analisa pekerjaan di tab Analisa Pekerjaan."
        )
        riwayat = riwayat_harga(sd["id"], 6)
        self.daftar_riwayat.setText(
            "\n".join(
                f"{r['waktu'][:16]}  ·  {tema.format_rupiah(r['harga_lama'] or 0)} → {tema.format_rupiah(r['harga_baru'] or 0)}"
                + (f"  ·  merk {r['merk_baru']}" if r["merk_baru"] and r["merk_baru"] != r["merk_lama"] else "")
                for r in riwayat
            )
            or "Belum pernah diubah."
        )

    def _galat(self, teks: str):
        self.label_galat.setText(teks)
        self.label_galat.show()

    def _simpan(self):
        if not self._sd:
            return
        try:
            ubah_sumber_daya(self._sd["id"], self.spin_harga.value(), self.edit_merk.text())
        except HargaTidakValid as e:  # KF-14
            self._galat(str(e))
            self.spin_harga.setFocus()
            return
        self.tersimpan.emit(self._sd["id"], "Harga satuan berhasil diperbarui")

    def _kembalikan(self):
        if not self._sd:
            return
        try:
            kembalikan_harga_bawaan(self._sd["id"])
        except HargaTidakValid as e:
            self._galat(str(e))
            return
        self.tersimpan.emit(self._sd["id"], "Harga dikembalikan ke harga bawaan")

    def _hapus(self):
        if not self._sd:
            return
        try:
            hapus_sumber_daya(self._sd["id"])
        except HargaTidakValid as e:
            self._galat(str(e))
            return
        self.tersimpan.emit(None, f"'{self._sd['nama']}' dihapus")


# ====================================================================
# Tab Analisa Pekerjaan
# ====================================================================


class TabAnalisa(QWidget):
    harga_berubah = Signal()
    minta_ubah_harga = Signal(object)  # sumber_daya_id

    def __init__(self, parent=None):
        super().__init__(parent)
        self._semua = []
        self._komponen = []
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(12)

        alat = QHBoxLayout()
        alat.setSpacing(10)
        self.kolom_cari = QLineEdit()
        self.kolom_cari.setPlaceholderText("Cari kode atau uraian pekerjaan...")
        self.kolom_cari.setClearButtonEnabled(True)
        self.kolom_cari.textChanged.connect(self._isi_tabel)
        self.combo_kategori = QComboBox()
        self.combo_kategori.currentIndexChanged.connect(self._isi_tabel)
        self.label_jumlah = tema.label("", "subjudul")
        alat.addWidget(self.kolom_cari, stretch=1)
        alat.addWidget(self.combo_kategori)
        alat.addWidget(self.label_jumlah)
        lay.addLayout(alat)

        split = QSplitter(Qt.Horizontal)
        split.setChildrenCollapsible(False)
        split.setHandleWidth(14)
        self.tabel = QTableWidget()
        tema.siapkan_tabel(
            self.tabel, ["KODE", "URAIAN PEKERJAAN", "SAT", "HARGA SATUAN"],
            rata_kanan=(3,), tinggi_baris=40,
        )
        tema.atur_lebar(self.tabel, 1, isi_konten=(0, 2, 3))
        tema.siapkan_urut(self.tabel)  # KF-16: klik judul kolom untuk mengurutkan
        self.tabel.itemSelectionChanged.connect(self._tampilkan_analisa)
        split.addWidget(self.tabel)

        # --- panel analisa ---
        panel = QFrame()
        panel.setObjectName("panel")
        panel.setMinimumWidth(460)
        p = QVBoxLayout(panel)
        p.setContentsMargins(18, 16, 18, 16)
        p.setSpacing(10)
        self.label_kode = tema.label("ANALISA HARGA SATUAN", "bagian")
        self.legenda = tema.label(
            "  ".join(f'<span style="color:{tema.WARNA_TIPE[t]}">■ {LABEL_TIPE[t]}</span>' for t in TIPE),
            "infoKecil",
        )
        self.label_judul = tema.label("Pilih satu pekerjaan di tabel.", "judulPanel", wrap=True)
        self.label_catatan = tema.label("", "infoKecil", wrap=True)
        p.addWidget(self.label_kode)
        p.addWidget(self.label_judul)
        p.addWidget(self.label_catatan)
        p.addWidget(self.legenda)
        self.tabel_komponen = QTableWidget()
        tema.siapkan_tabel(
            self.tabel_komponen, ["URAIAN", "KOEFISIEN", "HARGA DASAR", "JUMLAH"],
            rata_kanan=(1, 2, 3), tinggi_baris=34,
        )
        tema.atur_lebar(self.tabel_komponen, 0, isi_konten=(1, 2, 3))
        self.tabel_komponen.itemSelectionChanged.connect(self._perbarui_tombol)
        self.tabel_komponen.cellDoubleClicked.connect(lambda *_: self._ubah_harga())
        self.tabel_komponen.setToolTip("Klik dua kali untuk mengubah harga dasarnya")
        p.addWidget(self.tabel_komponen, stretch=1)

        self.ringkasan = QFormLayout()
        self.ringkasan.setHorizontalSpacing(18)
        self.ringkasan.setVerticalSpacing(4)
        p.addLayout(self.ringkasan)

        tombol = QHBoxLayout()
        self.btn_tambah = tema.tombol("Tambah Komponen", "secondary", "tambah", "Tambah bahan, upah, atau alat ke analisa ini")
        self.btn_tambah.clicked.connect(self._tambah)
        self.btn_ubah = tema.tombol("Ubah Harga", "ghost", "harga")
        self.btn_ubah.clicked.connect(self._ubah_harga)
        self.btn_hapus = tema.tombol("Hapus", "danger")
        self.btn_hapus.setToolTip("Hanya komponen tambahan yang bisa dihapus")
        self.btn_hapus.clicked.connect(self._hapus)
        tombol.addWidget(self.btn_tambah)
        tombol.addWidget(self.btn_ubah)
        tombol.addStretch()
        tombol.addWidget(self.btn_hapus)
        p.addLayout(tombol)
        split.addWidget(panel)
        split.setStretchFactor(0, 1)
        split.setSizes([560, 600])
        lay.addWidget(split, stretch=1)
        self._pekerjaan = None
        self.muat()

    def muat(self):
        pilih = self._pekerjaan["id"] if self._pekerjaan else None
        self._semua = daftar_pekerjaan()
        kategori = sorted({p["kategori"] for p in self._semua})
        lama = self.combo_kategori.currentText()
        self.combo_kategori.blockSignals(True)
        self.combo_kategori.clear()
        self.combo_kategori.addItems([SEMUA_KATEGORI] + kategori)
        self.combo_kategori.setCurrentIndex(max(self.combo_kategori.findText(lama), 0))
        self.combo_kategori.blockSignals(False)
        self._isi_tabel()
        if pilih is not None:
            self.pilih(pilih)

    def _isi_tabel(self, *_):
        kata = self.kolom_cari.text().strip().lower()
        kat = self.combo_kategori.currentText()
        baris = [
            p for p in self._semua
            if (kat in ("", SEMUA_KATEGORI) or p["kategori"] == kat)
            and (not kata or kata in f"{p['kode_ahsp']} {p['nama_pekerjaan']}".lower())
        ]
        self.tabel.blockSignals(True)
        self.tabel.setSortingEnabled(False)  # KF-16
        self.tabel.setRowCount(len(baris))
        for i, p in enumerate(baris):
            self.tabel.setItem(i, 0, tema.sel(p["kode_ahsp"], warna=tema.W["teks_redup"], data=p["id"]))
            self.tabel.setItem(i, 1, tema.sel(p["nama_pekerjaan"], tooltip=f"{p['kategori']} — {p['nama_pekerjaan']}"))
            self.tabel.setItem(i, 2, tema.sel(p["satuan"], "tengah", tema.W["teks_redup"]))
            self.tabel.setItem(i, 3, tema.sel(tema.format_rupiah(p["harga_satuan"]), "kanan", tebal=True, urut=p["harga_satuan"]))
        self.tabel.setSortingEnabled(True)
        self.tabel.blockSignals(False)
        self.label_jumlah.setText(f"{len(baris)} pekerjaan")
        if self._pekerjaan:
            self.pilih(self._pekerjaan["id"], gulir=False)

    def pilih(self, pekerjaan_id, gulir=True):
        for i in range(self.tabel.rowCount()):
            if self.tabel.item(i, 0).data(Qt.UserRole) == pekerjaan_id:
                self.tabel.selectRow(i)
                if gulir:
                    self.tabel.scrollToItem(self.tabel.item(i, 0))
                return

    def _tampilkan_analisa(self):
        r = self.tabel.currentRow()
        it = self.tabel.item(r, 0) if r >= 0 else None
        pid = it.data(Qt.UserRole) if it and self.tabel.selectedItems() else None
        self._pekerjaan = next((p for p in self._semua if p["id"] == pid), None)
        p = self._pekerjaan
        while self.ringkasan.rowCount():
            self.ringkasan.removeRow(0)
        if p is None:
            self.label_kode.setText("ANALISA HARGA SATUAN")
            self.label_judul.setText("Pilih satu pekerjaan di tabel.")
            self.label_catatan.setText("")
            self.tabel_komponen.setRowCount(0)
            self._komponen = []
            self._perbarui_tombol()
            return
        self.label_kode.setText(f"{p['kode_ahsp']}  ·  {p['kategori'].upper()}  ·  PER 1 {p['satuan'].upper()}")
        self.label_judul.setText(p["nama_pekerjaan"])
        self.label_catatan.setText(p["catatan"] or "")
        self._komponen = analisa_pekerjaan(p["id"])
        t = self.tabel_komponen
        t.setRowCount(len(self._komponen))
        for i, k in enumerate(self._komponen):
            nama = _nama_tampil(k["nama_komponen"]) + (f" ({k['merk']})" if k["merk"] else "")
            if k["diubah_manual"]:
                nama += "  · tambahan"
            it_nama = tema.sel(
                nama, warna=tema.WARNA_TIPE[k["tipe"]], data=k["id"],
                tooltip=f"{LABEL_TIPE[k['tipe']]}: {nama}\nKlik dua kali untuk mengubah harga dasarnya",
            )
            t.setItem(i, 0, it_nama)
            t.setItem(i, 1, tema.sel(f"{tema.format_angka(k['koefisien'], 4)} {k['satuan']}", "kanan"))
            t.setItem(i, 2, tema.sel(tema.format_rupiah(k["harga_satuan"]), "kanan", tema.W["teks_redup"]))
            t.setItem(i, 3, tema.sel(tema.format_rupiah(k["jumlah"]), "kanan", tebal=True))

        def baris(kiri, kanan, kuat=False):
            a = tema.label(kiri, "formLabel")
            b = tema.label(kanan, "judulPanel" if kuat else None)
            b.setAlignment(Qt.AlignRight)
            self.ringkasan.addRow(a, b)

        baris("A. Jumlah bahan", tema.format_rupiah(p["bahan"]))
        baris("B. Jumlah upah", tema.format_rupiah(p["upah"]))
        baris("C. Jumlah alat", tema.format_rupiah(p["alat"]))
        baris("D. Jumlah A + B + C", tema.format_rupiah(p["jumlah_abc"]))
        baris(f"E. Biaya umum & keuntungan {BUK_RATE:.0%} × D", tema.format_rupiah(p["buk"]))
        baris(f"F. Harga satuan pekerjaan (D + E) per {p['satuan']}", tema.format_rupiah(p["harga_satuan"]), kuat=True)
        self._perbarui_tombol()

    def _komponen_terpilih(self):
        r = self.tabel_komponen.currentRow()
        if r < 0 or not self.tabel_komponen.selectedItems():
            return None
        kid = self.tabel_komponen.item(r, 0).data(Qt.UserRole)
        return next((k for k in self._komponen if k["id"] == kid), None)

    def _perbarui_tombol(self):
        k = self._komponen_terpilih()
        self.btn_tambah.setEnabled(self._pekerjaan is not None)
        self.btn_ubah.setEnabled(k is not None and k["sumber_daya_id"] is not None)
        self.btn_hapus.setEnabled(bool(k and k["diubah_manual"]))

    def _ubah_harga(self):
        k = self._komponen_terpilih()
        if k and k["sumber_daya_id"] is not None:
            self.minta_ubah_harga.emit(k["sumber_daya_id"])

    def _tambah(self):
        if not self._pekerjaan:
            return
        dlg = TambahKomponenDialog(self._pekerjaan, self)
        if dlg.exec():
            self.muat()
            tema.toast(self, "Komponen ditambahkan ke analisa")
            self.harga_berubah.emit()

    def _hapus(self):
        k = self._komponen_terpilih()
        if not k:
            return
        try:
            hapus_komponen(k["id"])
        except HargaTidakValid as e:
            QMessageBox.warning(self, "Tidak Bisa Dihapus", str(e))
            return
        self.muat()
        tema.toast(self, "Komponen dihapus dari analisa")
        self.harga_berubah.emit()


# ====================================================================
# Dialog
# ====================================================================


class _DialogDasar(QDialog):
    def __init__(self, judul: str, sub: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(judul)
        self.setModal(True)
        self.setMinimumWidth(480)
        self.lay = QVBoxLayout(self)
        self.lay.setContentsMargins(26, 22, 26, 20)
        self.lay.setSpacing(12)
        self.lay.addWidget(tema.label(judul, "judulHalaman"))
        self.lay.addWidget(tema.label(sub, "subjudul", wrap=True))
        self.form = QFormLayout()
        self.form.setHorizontalSpacing(14)
        self.form.setVerticalSpacing(10)
        self.lay.addLayout(self.form)
        self.label_galat = tema.label("", "galat", wrap=True)
        self.label_galat.hide()
        self.lay.addWidget(self.label_galat)
        tombol = QHBoxLayout()
        tombol.addStretch()
        batal = tema.tombol("Batal", "secondary")
        batal.clicked.connect(self.reject)
        self.btn_ok = tema.tombol("Simpan", "primary")
        self.btn_ok.setDefault(True)
        self.btn_ok.clicked.connect(self._ok)
        tombol.addWidget(batal)
        tombol.addWidget(self.btn_ok)
        self.lay.addLayout(tombol)

    def galat(self, teks: str):
        self.label_galat.setText(teks)
        self.label_galat.show()

    def _ok(self):
        raise NotImplementedError


class TambahSumberDayaDialog(_DialogDasar):
    """UC-04 skenario alternatif: form nama material, satuan, dan harga."""

    def __init__(self, parent=None, tipe_awal: str = "bahan"):
        super().__init__("Tambah Material", "Material baru masuk ke daftar harga dasar dan bisa ditambahkan ke analisa pekerjaan.", parent)
        self.sumber_daya_id = None
        self.combo_tipe = QComboBox()
        for t in TIPE:
            self.combo_tipe.addItem(LABEL_TIPE[t], t)
        self.combo_tipe.setCurrentIndex(TIPE.index(tipe_awal))
        self.edit_nama = QLineEdit()
        self.edit_nama.setPlaceholderText("mis. Semen PC 50 kg, Concrete vibrator")
        self.combo_satuan = QComboBox()
        self.combo_satuan.setEditable(True)
        self.combo_satuan.addItems(SATUAN_UMUM)
        self.combo_satuan.setCurrentText("")
        self.combo_satuan.lineEdit().setPlaceholderText("kg, m3, OH, jam, ...")
        self.edit_merk = QLineEdit()
        self.edit_merk.setPlaceholderText("opsional")
        self.spin_harga = _spin_harga()
        for teks, w in (("Jenis", self.combo_tipe), ("Nama", self.edit_nama), ("Satuan", self.combo_satuan),
                        ("Merk", self.edit_merk), ("Harga per satuan", self.spin_harga)):
            self.form.addRow(tema.label(teks, "formLabel"), w)
        self.edit_nama.setFocus()

    def _ok(self):
        try:
            self.sumber_daya_id = tambah_sumber_daya(
                self.combo_tipe.currentData(), self.edit_nama.text(), self.combo_satuan.currentText(),
                self.spin_harga.value(), self.edit_merk.text(),
            )
        except HargaTidakValid as e:
            self.galat(str(e))
            return
        self.accept()


class TambahKomponenDialog(_DialogDasar):
    """Tambah bahan / upah / alat dari daftar harga dasar ke analisa satu pekerjaan."""

    def __init__(self, pekerjaan: dict, parent=None):
        super().__init__(
            "Tambah Komponen",
            f"{pekerjaan['kode_ahsp']} — {pekerjaan['nama_pekerjaan']}. Koefisien = kebutuhan per 1 {pekerjaan['satuan']}.",
            parent,
        )
        self.pekerjaan = pekerjaan
        self.combo_tipe = QComboBox()
        for t in TIPE:
            self.combo_tipe.addItem(LABEL_TIPE[t], t)
        self.combo_tipe.setCurrentIndex(TIPE.index("alat"))
        self.combo_sd = QComboBox()
        self.combo_sd.setMinimumWidth(320)
        # ribuan harga dasar HSPK: ketik sebagian nama untuk mencari
        self.combo_sd.setEditable(True)
        self.combo_sd.setInsertPolicy(QComboBox.NoInsert)
        self.combo_sd.completer().setFilterMode(Qt.MatchContains)
        self.combo_sd.completer().setCompletionMode(QCompleter.PopupCompletion)
        self.combo_sd.lineEdit().setPlaceholderText("Ketik untuk mencari, mis. molen, vibrator, semen")
        self.setMinimumWidth(600)
        baris_sd = QHBoxLayout()
        baris_sd.addWidget(self.combo_sd, stretch=1)
        btn_baru = tema.tombol("Baru...", "ghost", "tambah", "Tambah material baru ke daftar harga dasar")
        btn_baru.clicked.connect(self._baru)
        baris_sd.addWidget(btn_baru)
        self.spin_koef = QDoubleSpinBox()
        self.spin_koef.setRange(0, 100000)
        self.spin_koef.setDecimals(4)
        self.spin_koef.setButtonSymbols(QAbstractSpinBox.NoButtons)
        self.spin_koef.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.label_satuan = tema.label("", "formLabel")
        baris_koef = QHBoxLayout()
        baris_koef.addWidget(self.spin_koef, stretch=1)
        baris_koef.addWidget(self.label_satuan)
        self.form.addRow(tema.label("Jenis", "formLabel"), self.combo_tipe)
        self.form.addRow(tema.label("Item", "formLabel"), baris_sd)
        self.form.addRow(tema.label("Koefisien", "formLabel"), baris_koef)
        self.combo_tipe.currentIndexChanged.connect(lambda _: self._isi_sd())
        self.combo_sd.currentIndexChanged.connect(self._perbarui_satuan)
        self.btn_ok.setText("Tambahkan")
        self._isi_sd()

    def _isi_sd(self, pilih_id=None):
        tipe = self.combo_tipe.currentData()
        self.combo_sd.clear()
        for sd in daftar_sumber_daya(tipe):
            self.combo_sd.addItem(
                f"{_nama_tampil(sd['nama'])}  ·  {tema.format_rupiah(sd['harga'])}/{sd['satuan']}", (sd["id"], sd["satuan"])
            )
            if sd["id"] == pilih_id:
                self.combo_sd.setCurrentIndex(self.combo_sd.count() - 1)
        if self.combo_sd.count() == 0:
            self.combo_sd.addItem(f"Belum ada {LABEL_TIPE[tipe].lower()} — klik Baru...", None)
        self._perbarui_satuan()

    def _perbarui_satuan(self, *_):
        data = self.combo_sd.currentData()
        self.label_satuan.setText(f"{data[1]} / {self.pekerjaan['satuan']}" if data else "")

    def _baru(self):
        dlg = TambahSumberDayaDialog(self, self.combo_tipe.currentData())
        if dlg.exec():
            self._isi_sd(pilih_id=dlg.sumber_daya_id)

    def _ok(self):
        data = self.combo_sd.currentData()
        if not data:
            self.galat("Pilih bahan / upah / alat terlebih dahulu.")
            return
        try:
            tambah_komponen(self.pekerjaan["id"], data[0], self.spin_koef.value())
        except HargaTidakValid as e:
            self.galat(str(e))
            return
        self.accept()
