"""
Dialog Tipe Penulangan: konfigurasi tulangan per tipe elemen (K1, B1, S1, P1, ...) dan rekap
kebutuhan besi per diameter (jumlah batang 12 m). Menyimpan konfigurasi menghitung ulang
pembesian seluruh proyek (Rumus 2.30 - 2.33).
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QAbstractSpinBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QSpinBox,
    QTableWidget,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from database.penulangan_repository import (
    PenulanganTidakValid,
    daftar_tipe,
    kebutuhan_besi,
    kembalikan_tipe_bawaan,
    ubah_tipe,
)
from estimasi_service import hitung_ulang_penulangan
from gui import tema
from gui.proses_latar import jalankan_di_latar
from rules.penulangan import DIAMETER_STANDAR, LINIER, Penulangan, jenis_baja, label_d


def _combo_diameter() -> QComboBox:
    c = QComboBox()
    c.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
    c.setMinimumContentsLength(10)
    for d in DIAMETER_STANDAR:
        c.addItem(f"{label_d(d)}  ({jenis_baja(d).split()[0].lower()})", d)
    return c


def _spin_mm(minimum: int, maksimum: int, langkah: int = 5) -> QSpinBox:
    s = QSpinBox()
    s.setRange(minimum, maksimum)
    s.setSingleStep(langkah)
    s.setSuffix(" mm")
    s.setButtonSymbols(QAbstractSpinBox.NoButtons)
    s.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
    return s


class PenulanganDialog(QDialog):
    def __init__(self, proyek_id: int, parent=None):
        super().__init__(parent)
        self.proyek_id = proyek_id
        self.diubah = False
        self._tipe = []
        self.setWindowTitle("Tipe Penulangan")
        self.setModal(True)
        self.resize(1180, 700)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(26, 22, 26, 20)
        lay.setSpacing(12)
        lay.addWidget(tema.kepala_dialog(
            "Tipe Penulangan",
            "Elemen struktur dikelompokkan per penampang. Ubah konfigurasi tulangan sesuai gambar kerja; "
            "pembesian seluruh proyek dihitung ulang: W = Σ(π d²/4 × 7850 × L_eff × n) × 1,05.",
            "besi",
        )[0])

        self.tab = QTabWidget()
        lay.addWidget(self.tab, stretch=1)

        # ---- tab tipe ----
        hal = QWidget()
        h = QHBoxLayout(hal)
        h.setContentsMargins(0, 12, 0, 0)
        h.setSpacing(14)
        self.tabel = QTableWidget()
        self.tabel.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tabel.setSelectionMode(QAbstractItemView.SingleSelection)
        self.tabel.itemSelectionChanged.connect(self._pilih)
        h.addWidget(self.tabel, stretch=1)
        h.addWidget(self._editor())
        self.tab.addTab(hal, "Tipe Elemen")

        # ---- tab kebutuhan besi ----
        hal = QWidget()
        v = QVBoxLayout(hal)
        v.setContentsMargins(0, 12, 0, 0)
        self.tabel_besi = QTableWidget()
        v.addWidget(self.tabel_besi, stretch=1)
        v.addWidget(tema.label(
            "Berat sudah termasuk sisa potongan 5% (Rumus 2.33). Jumlah batang = panjang total / 12 m, "
            "dibulatkan ke atas.", "infoKecil", wrap=True,
        ))
        self.tab.addTab(hal, "Kebutuhan Besi per Diameter")

        tombol = QHBoxLayout()
        self.label_pesan = tema.label("", "sukses")
        tombol.addWidget(self.label_pesan)
        tombol.addStretch()
        tutup = tema.tombol("Tutup", "secondary")
        tutup.clicked.connect(self.accept)
        tombol.addWidget(tutup)
        lay.addLayout(tombol)

        self.muat()

    # ---------------------------------------------------------------- editor

    def _editor(self) -> QFrame:
        kartu = QFrame()
        kartu.setObjectName("kartu")
        kartu.setFixedWidth(380)
        v = QVBoxLayout(kartu)
        v.setContentsMargins(18, 16, 18, 16)
        v.setSpacing(10)
        self.label_tipe = tema.label("Pilih satu tipe", "judulPanel", wrap=True)
        v.addWidget(self.label_tipe)
        self.label_status = tema.label("", "infoKecil", wrap=True)
        v.addWidget(self.label_status)
        v.addWidget(tema.garis())

        self.form_linier = QWidget()
        f = QFormLayout(self.form_linier)
        f.setLabelAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        f.setContentsMargins(0, 0, 0, 0)
        f.setVerticalSpacing(10)
        self.spin_n = QSpinBox()
        self.spin_n.setRange(2, 40)
        self.spin_n.setSuffix(" batang")
        self.spin_n.setButtonSymbols(QAbstractSpinBox.NoButtons)
        self.spin_n.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.combo_d = _combo_diameter()
        self.combo_ds = _combo_diameter()
        self.spin_s = _spin_mm(50, 300)
        f.addRow(tema.label("Tulangan utama", "formLabel"), self.spin_n)
        f.addRow(tema.label("Diameter utama", "formLabel"), self.combo_d)
        f.addRow(tema.label("Diameter sengkang", "formLabel"), self.combo_ds)
        f.addRow(tema.label("Jarak sengkang", "formLabel"), self.spin_s)
        v.addWidget(self.form_linier)

        self.form_bidang = QWidget()
        f = QFormLayout(self.form_bidang)
        f.setLabelAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        f.setContentsMargins(0, 0, 0, 0)
        f.setVerticalSpacing(10)
        self.combo_dp = _combo_diameter()
        self.spin_jp = _spin_mm(50, 400)
        self.combo_lapis = QComboBox()
        self.combo_lapis.addItem("1 lapis (bawah)", 1)
        self.combo_lapis.addItem("2 lapis (atas & bawah)", 2)
        f.addRow(tema.label("Diameter", "formLabel"), self.combo_dp)
        f.addRow(tema.label("Jarak (dua arah)", "formLabel"), self.spin_jp)
        f.addRow(tema.label("Lapis", "formLabel"), self.combo_lapis)
        v.addWidget(self.form_bidang)

        f = QFormLayout()
        f.setLabelAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        f.setVerticalSpacing(10)
        self.spin_c = _spin_mm(15, 100)
        f.addRow(tema.label("Selimut beton", "formLabel"), self.spin_c)
        v.addLayout(f)
        # Tiga form terpisah: samakan lebar kolom label agar isian sejajar.
        for w in kartu.findChildren(QLabel, "formLabel"):
            w.setFixedWidth(150)
            w.setMinimumHeight(36)
            w.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        for w in (self.spin_n, self.combo_d, self.combo_ds, self.spin_s,
                  self.combo_dp, self.spin_jp, self.combo_lapis, self.spin_c):
            w.setFixedWidth(170)
        for f in kartu.findChildren(QFormLayout):
            f.setHorizontalSpacing(12)
        v.addWidget(tema.label(
            "Ø = baja polos BjTP (< 12 mm), D = baja ulir BjTS (≥ 12 mm). Kait 12d, sengkang 135°, "
            "lewatan 40d tiap 12 m (SNI 2847:2019).", "infoKecil", wrap=True,
        ))
        self.label_galat = tema.label("", "galat", wrap=True)
        self.label_galat.hide()
        v.addWidget(self.label_galat)
        v.addStretch()
        self.btn_bawaan = tema.tombol("Kembalikan Bawaan", "ghost", "ulang")
        self.btn_bawaan.clicked.connect(self._bawaan)
        self.btn_simpan = tema.tombol("Simpan && Hitung Ulang", "primary", "ulang")
        self.btn_simpan.clicked.connect(self._simpan)
        v.addWidget(self.btn_simpan)
        v.addWidget(self.btn_bawaan)
        self._aktifkan(False)
        return kartu

    def _aktifkan(self, aktif: bool):
        for w in (self.form_linier, self.form_bidang, self.spin_c, self.btn_simpan, self.btn_bawaan):
            w.setEnabled(aktif)

    # ---------------------------------------------------------------- data

    def muat(self, pilih_id=None):
        self._tipe = daftar_tipe(self.proyek_id)
        t = self.tabel
        t.clear()
        tema.siapkan_tabel(t, ["TIPE", "JUMLAH", "KONFIGURASI TULANGAN", "BERAT BESI", "STATUS"], rata_kanan=(1, 3), tinggi_baris=40)
        t.setRowCount(len(self._tipe))
        baris_pilih = 0
        for i, d in enumerate(self._tipe):
            t.setItem(i, 0, tema.sel(d["label"], tebal=True, data=d["id"]))
            t.setItem(i, 1, tema.sel(f"{d['jumlah_elemen']} buah", "kanan", tema.W["teks_redup"]))
            t.setItem(i, 2, tema.sel(d["ringkas"]))
            t.setItem(i, 3, tema.sel(f"{tema.format_angka(d['berat_besi'], 1)} kg", "kanan"))
            if d["diubah"]:
                t.setItem(i, 4, tema.sel("●  Diubah", warna=tema.W["peringatan"], tebal=True))
            else:
                t.setItem(i, 4, tema.sel("●  Bawaan", warna=tema.W["sukses"]))
            if d["id"] == pilih_id:
                baris_pilih = i
        tema.atur_lebar(t, 2, isi_konten=(0, 1, 3, 4))
        if self._tipe:
            t.selectRow(baris_pilih)
        else:
            self.label_tipe.setText("Belum ada elemen struktur bertulang")
            self.label_status.setText("Model tidak memuat kolom, balok, sloof, pelat, atau fondasi telapak beton.")
            self._aktifkan(False)
        self._muat_besi()

    def _muat_besi(self):
        data = kebutuhan_besi(self.proyek_id)
        t = self.tabel_besi
        t.clear()
        tema.siapkan_tabel(
            t, ["DIAMETER", "JENIS BAJA", "BERAT / M'", "PANJANG TOTAL", "BERAT TOTAL", "BATANG 12 M"],
            rata_kanan=(2, 3, 4, 5), tinggi_baris=38,
        )
        t.setRowCount(len(data) + (1 if data else 0))
        for i, k in enumerate(data):
            t.setItem(i, 0, tema.sel(k["label"], tebal=True))
            t.setItem(i, 1, tema.sel(k["jenis"], warna=tema.W["teks_redup"]))
            t.setItem(i, 2, tema.sel(f"{tema.format_angka(k['berat_per_m'], 3)} kg", "kanan", tema.W["teks_redup"]))
            t.setItem(i, 3, tema.sel(f"{tema.format_angka(k['panjang'], 1)} m", "kanan"))
            t.setItem(i, 4, tema.sel(f"{tema.format_angka(k['berat'], 1)} kg", "kanan", tebal=True))
            t.setItem(i, 5, tema.sel(f"{k['batang']} batang", "kanan"))
        if data:
            n = len(data)
            t.setItem(n, 0, tema.sel("JUMLAH", tebal=True))
            t.setItem(n, 4, tema.sel(f"{tema.format_angka(sum(k['berat'] for k in data), 1)} kg", "kanan", tema.W["aksen"], tebal=True))
            t.setItem(n, 5, tema.sel(f"{sum(k['batang'] for k in data)} batang", "kanan", tebal=True))
        tema.atur_lebar(t, 1, isi_konten=(0, 2, 3, 4, 5))

    def _terpilih(self):
        baris = self.tabel.currentRow()
        it = self.tabel.item(baris, 0) if baris >= 0 else None
        if it is None:
            return None
        tid = it.data(Qt.UserRole)
        return next((d for d in self._tipe if d["id"] == tid), None)

    def _pilih(self):
        d = self._terpilih()
        self.label_galat.hide()
        if d is None:
            self._aktifkan(False)
            return
        self._aktifkan(True)
        p = d["penulangan"]
        self.label_tipe.setText(d["label"])
        self.label_status.setText(
            f"{d['jumlah_elemen']} elemen · {'diubah pengguna' if d['diubah'] else 'konfigurasi bawaan'}"
        )
        linier = d["kelompok"] in LINIER
        self.form_linier.setVisible(linier)
        self.form_bidang.setVisible(not linier)
        if linier:
            self.spin_n.setValue(p.n_utama)
            self._set_d(self.combo_d, p.d_utama)
            self._set_d(self.combo_ds, p.d_sengkang)
            self.spin_s.setValue(round(p.jarak_sengkang * 1000))
        else:
            self._set_d(self.combo_dp, p.d_utama)
            self.spin_jp.setValue(round(p.jarak_utama * 1000))
            self.combo_lapis.setCurrentIndex(0 if p.lapis == 1 else 1)
        self.spin_c.setValue(round(p.selimut * 1000))
        self.btn_bawaan.setEnabled(bool(d["diubah"]))

    @staticmethod
    def _set_d(combo: QComboBox, d: float):
        i = combo.findData(int(d)) if float(d).is_integer() else -1
        if i < 0:
            combo.addItem(label_d(d), d)
            i = combo.count() - 1
        combo.setCurrentIndex(i)

    def _dari_form(self, d) -> Penulangan:
        c = self.spin_c.value() / 1000
        if d["kelompok"] in LINIER:
            return Penulangan(
                d["kelompok"], self.spin_n.value(), float(self.combo_d.currentData()),
                d_sengkang=float(self.combo_ds.currentData()), jarak_sengkang=self.spin_s.value() / 1000, selimut=c,
            )
        return Penulangan(
            d["kelompok"], d_utama=float(self.combo_dp.currentData()), jarak_utama=self.spin_jp.value() / 1000,
            lapis=self.combo_lapis.currentData(), selimut=c,
        )

    # ---------------------------------------------------------------- aksi

    def _hitung_ulang(self, tid, pesan):
        try:
            jalankan_di_latar(self, "Menghitung ulang pembesian...", hitung_ulang_penulangan, self.proyek_id)
        except Exception as e:
            self.label_galat.setText(str(e))
            self.label_galat.show()
            return
        self.diubah = True
        self.muat(tid)
        self.label_pesan.setText("✓  " + pesan)

    def _simpan(self):
        d = self._terpilih()
        if d is None:
            return
        try:
            ubah_tipe(d["id"], self._dari_form(d))
        except PenulanganTidakValid as e:  # KF-14
            self.label_galat.setText(str(e))
            self.label_galat.show()
            return
        self._hitung_ulang(d["id"], f"Penulangan {d['label']} disimpan, pembesian dihitung ulang")

    def _bawaan(self):
        d = self._terpilih()
        if d is None:
            return
        kembalikan_tipe_bawaan(d["id"])
        self._hitung_ulang(d["id"], f"{d['label']} kembali ke konfigurasi bawaan")
