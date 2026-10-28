"""
Dialog Pilihan Material: combo box bahan per pekerjaan (dinding, plester, keramik, atap, plafon, cat,
pintu & jendela, mutu beton, batu kali), masing-masing dengan pilihan bawaan.

Setiap pilihan menampilkan harga satuan dan kebutuhan bahan per satuan pekerjaan dari analisa HSPK-nya
(mis. bata ringan 60x20x10: 8,75 buah + 3,43 kg mortar per m²), serta perkiraan perubahan biaya proyek.
Menyimpan pilihan mengganti analisa pada baris RAB yang sudah ada; volume tidak berubah, sehingga rule
engine tidak perlu dijalankan ulang.

MaterialElemenDialog: pilihan khusus satu elemen (mis. "Dinding A" bata merah, dinding lain tetap bata
ringan) dengan tabel perbandingan biaya dan kebutuhan bahan setiap pilihan untuk volume elemen itu.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QScrollArea,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)

from database.material import KELOMPOK, SLOT, kode_dasar, kode_varian
from database.material_repository import (
    material_elemen,
    muat_pilihan,
    ringkasan_opsi,
    simpan_material_elemen,
    simpan_pilihan,
)
from gui import tema

MAKS_BAHAN = 4  # komponen bahan yang ditampilkan di bawah combo box


_SATUAN = {"m2": "m²", "m3": "m³"}


def satuan_tampil(s: str) -> str:
    return _SATUAN.get(s, s)


def angka_bahan(x: float) -> str:
    return tema.format_angka(x, 3 if abs(x) < 1 else 2 if abs(x) < 100 else 0)


def teks_bahan(bahan: list, satuan: str, volume: float = 0.0) -> str:
    """'Bahan per 1 m²: 8,75 buah Bata ringan · 3,429 kg Mortar' + total untuk volume proyek bila ada."""
    if not bahan:
        return ""
    isi = [f"{angka_bahan(k)} {s} {n}" for n, s, k in bahan[:MAKS_BAHAN]]
    lebih = f" · +{len(bahan) - MAKS_BAHAN} bahan lain" if len(bahan) > MAKS_BAHAN else ""
    teks = f"Bahan per 1 {satuan_tampil(satuan)}: " + " · ".join(isi) + lebih
    if volume > 1e-9:
        total = [f"{angka_bahan(k * volume)} {s} {n}" for n, s, k in bahan[:MAKS_BAHAN]]
        teks += f"<br>Untuk {angka_bahan(volume)} {satuan_tampil(satuan)} di proyek ini: " + " · ".join(total)
    return teks


class MaterialDialog(QDialog):
    def __init__(self, proyek_id: int, baris: list | None = None, parent=None):
        super().__init__(parent)
        self.proyek_id = proyek_id
        self.diubah = False
        self.hasil = None
        self._awal = muat_pilihan(proyek_id)
        self._opsi = ringkasan_opsi()
        # volume per slot dari baris RAB (tanpa baris berharga khusus) untuk perkiraan selisih biaya
        self._volume = {}
        for r in baris or []:
            slot = kode_dasar(r.get("kode_ahsp"))
            if slot in SLOT and not r.get("harga_manual"):
                self._volume[slot] = self._volume.get(slot, 0.0) + (r.get("volume_pekerjaan") or 0.0)

        self.setWindowTitle("Pilihan Material")
        self.setModal(True)
        self.resize(860, 760)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(26, 22, 26, 20)
        lay.setSpacing(10)
        lay.addWidget(tema.kepala_dialog(
            "Pilihan Material Proyek",
            "Bahan yang dipakai setiap pekerjaan menentukan analisa HSPK, harga satuan, dan kebutuhan bahannya "
            "(jumlah bata, semen, pasir, ...). Volume pekerjaan dari model tidak berubah.",
            "kubus",
        )[0])

        gulir = QScrollArea()
        gulir.setWidgetResizable(True)
        gulir.setFrameShape(QFrame.NoFrame)
        isi = QWidget()
        gulir.setWidget(isi)
        v = QVBoxLayout(isi)
        v.setContentsMargins(0, 4, 8, 4)
        v.setSpacing(12)
        self.combo = {}
        self._info = {}
        for kelompok in KELOMPOK:
            kartu = QFrame()
            kartu.setObjectName("kartu")
            g = QGridLayout(kartu)
            g.setContentsMargins(18, 14, 18, 14)
            g.setHorizontalSpacing(12)
            g.setVerticalSpacing(4)
            g.setColumnStretch(1, 1)
            g.addWidget(tema.label(kelompok.upper(), "bagian"), 0, 0, 1, 2)
            baris_g = 1
            slots = [s for s in SLOT.values() if s.kelompok == kelompok]
            if kelompok == "Mutu beton":
                samakan = tema.tombol("Samakan semua dengan kolom", "ghost", None,
                                      "Pakai mutu beton kolom untuk balok, pelat, dak, sloof, fondasi, dan tangga")
                samakan.clicked.connect(lambda _=False, sl=slots: self._samakan(sl))
                g.addWidget(samakan, 0, 1, alignment=Qt.AlignRight)
            for s in slots:
                cb = QComboBox()
                cb.setMinimumWidth(420)
                for o in s.opsi:
                    data = self._opsi.get(kode_varian(s.kode, o.kunci))
                    harga = f"  ·  {tema.format_rupiah(data['harga'])}/{satuan_tampil(data['satuan'])}" if data else ""
                    bawaan = "  (bawaan)" if o.kunci == s.bawaan else ""
                    cb.addItem(f"{o.label}{bawaan}{harga}", o.kunci)
                cb.setCurrentIndex(max(0, cb.findData(self._awal[s.kode])))
                cb.currentIndexChanged.connect(lambda _i, k=s.kode: self._berubah(k))
                self.combo[s.kode] = cb
                info = tema.label("", "infoKecil", wrap=True)
                self._info[s.kode] = info
                g.addWidget(tema.label(s.judul, "formLabel"), baris_g, 0)
                g.addWidget(cb, baris_g, 1)
                g.addWidget(info, baris_g + 1, 1)
                baris_g += 2
            v.addWidget(kartu)
        v.addStretch()
        lay.addWidget(gulir, stretch=1)

        self.label_selisih = tema.label("", "infoKecil", wrap=True)
        lay.addWidget(self.label_selisih)
        self.label_galat = tema.label("", "galat", wrap=True)
        self.label_galat.hide()
        lay.addWidget(self.label_galat)

        tombol = QHBoxLayout()
        bawaan = tema.tombol("Kembalikan Semua ke Bawaan", "ghost", "ulang")
        bawaan.clicked.connect(self._bawaan)
        batal = tema.tombol("Batal", "secondary")
        batal.clicked.connect(self.reject)
        self.btn_simpan = tema.tombol("Simpan Pilihan", "primary")
        self.btn_simpan.clicked.connect(self._simpan)
        tombol.addWidget(bawaan)
        tombol.addStretch()
        tombol.addWidget(batal)
        tombol.addWidget(self.btn_simpan)
        lay.addLayout(tombol)
        for k in self.combo:
            self._berubah(k, perbarui=False)
        self._perbarui()

    def pilihan(self) -> dict:
        return {k: cb.currentData() for k, cb in self.combo.items()}

    def _harga(self, slot: str, kunci: str) -> float | None:
        d = self._opsi.get(kode_varian(slot, kunci))
        return d["harga"] if d else None

    def _berubah(self, slot: str, perbarui: bool = True):
        s = SLOT[slot]
        kunci = self.combo[slot].currentData()
        o = s.cari(kunci)
        data = self._opsi.get(kode_varian(slot, kunci)) or {}
        teks = teks_bahan(data.get("bahan", []), data.get("satuan", ""), self._volume.get(slot, 0.0))
        teks = f"HSPK {o.kode_hspk}" + (f"  ·  {teks}" if teks else "")
        warna = None
        if o.catatan:
            teks += f"<br>⚠ {o.catatan}"
            warna = tema.W["peringatan"]
        if kunci != s.bawaan:
            teks += f"<br>● bawaan: {s.opsi_bawaan.label}"
        self._info[slot].setText(teks)
        self._info[slot].setStyleSheet(f"color: {warna};" if warna else "")
        if perbarui:
            self._perbarui()

    def _selisih(self) -> float:
        total = 0.0
        for slot, vol in self._volume.items():
            lama, baru = self._harga(slot, self._awal[slot]), self._harga(slot, self.combo[slot].currentData())
            if lama is not None and baru is not None:
                total += vol * (baru - lama)
        return total

    def _perbarui(self):
        berubah = [k for k, cb in self.combo.items() if cb.currentData() != self._awal[k]]
        self.btn_simpan.setEnabled(bool(berubah))
        self.label_galat.hide()
        if not berubah:
            self.label_selisih.setText("Belum ada perubahan.")
            return
        d = self._selisih()
        arah = "naik" if d > 0 else "turun"
        self.label_selisih.setText(
            f"{len(berubah)} pekerjaan diganti bahannya. Perkiraan biaya langsung {arah} "
            f"{tema.format_rupiah(abs(d))} (volume tetap; baris berharga satuan khusus tidak berubah)."
        )

    def _samakan(self, slots):
        kunci = self.combo[slots[0].kode].currentData()
        for s in slots[1:]:
            i = self.combo[s.kode].findData(kunci)
            if i >= 0:
                self.combo[s.kode].setCurrentIndex(i)

    def _bawaan(self):
        for k, cb in self.combo.items():
            cb.setCurrentIndex(max(0, cb.findData(SLOT[k].bawaan)))

    def _simpan(self):
        try:
            self.hasil = simpan_pilihan(self.proyek_id, self.pilihan())
        except ValueError as e:  # KF-14
            self.label_galat.setText(str(e))
            self.label_galat.show()
            return
        self.diubah = True
        self.accept()


class MaterialElemenDialog(QDialog):
    """Pilihan material satu elemen + perbandingan semua pilihan untuk volume elemen itu."""

    def __init__(self, elemen_id: int, nama_elemen: str = "", parent=None):
        super().__init__(parent)
        self.elemen_id = elemen_id
        self.diubah = False
        self.hasil = None
        self._slot = material_elemen(elemen_id)
        self._opsi = ringkasan_opsi()
        self.setWindowTitle("Material Elemen")
        self.setModal(True)
        self.resize(900, 720)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(26, 22, 26, 20)
        lay.setSpacing(10)
        lay.addWidget(tema.kepala_dialog(
            "Material Elemen Ini",
            f"{nama_elemen or 'Elemen'}. Bandingkan biaya dan kebutuhan bahan setiap pilihan untuk volume elemen "
            "ini. Pilihan yang berbeda dari pilihan proyek hanya berlaku untuk elemen ini.",
            "kubus",
        )[0])

        gulir = QScrollArea()
        gulir.setWidgetResizable(True)
        gulir.setFrameShape(QFrame.NoFrame)
        isi = QWidget()
        gulir.setWidget(isi)
        v = QVBoxLayout(isi)
        v.setContentsMargins(0, 4, 8, 4)
        v.setSpacing(12)
        self.combo, self.tabel, self._proyek = {}, {}, {}
        if not self._slot:
            v.addWidget(tema.label("Pekerjaan elemen ini tidak punya pilihan material.", "subjudul", wrap=True))
        proyek = muat_pilihan_proyek_elemen(elemen_id)
        for slot, d in self._slot.items():
            s = SLOT[slot]
            self._proyek[slot] = proyek.get(slot, s.bawaan)
            kartu = QFrame()
            kartu.setObjectName("kartu")
            k = QVBoxLayout(kartu)
            k.setContentsMargins(18, 14, 18, 14)
            k.setSpacing(8)
            k.addWidget(tema.label(
                f"{s.judul.upper()}  ·  {angka_bahan(d['volume'])} {satuan_tampil(d['satuan'])}", "bagian"))
            cb = QComboBox()
            for o in s.opsi:
                tanda = "  (pilihan proyek)" if o.kunci == self._proyek[slot] else ""
                cb.addItem(f"{o.label}{tanda}", o.kunci)
            cb.setCurrentIndex(max(0, cb.findData(d["kunci"])))
            cb.currentIndexChanged.connect(lambda _i, sl=slot: self._tandai(sl))
            k.addWidget(cb)
            t = QTableWidget()
            tema.siapkan_tabel(t, ["PILIHAN", "BIAYA ELEMEN", "KEBUTUHAN BAHAN ELEMEN INI"], rata_kanan=(1,), tinggi_baris=34)
            t.setWordWrap(True)
            t.setRowCount(len(s.opsi))
            for i, o in enumerate(s.opsi):
                data = self._opsi.get(kode_varian(slot, o.kunci)) or {}
                biaya = (data.get("harga") or 0.0) * d["volume"]
                bahan = " · ".join(
                    f"{angka_bahan(kf * d['volume'])} {sat} {nm}" for nm, sat, kf in data.get("bahan", [])
                ) or "-"
                t.setItem(i, 0, tema.sel(o.label, data=o.kunci))
                t.setItem(i, 1, tema.sel(tema.format_rupiah(biaya), "kanan"))
                t.setItem(i, 2, tema.sel(bahan, tooltip=bahan))
            tema.atur_lebar(t, 2, isi_konten=(0, 1), minimum=260)
            t.resizeRowsToContents()
            t.setMinimumHeight(min(42 + sum(t.rowHeight(i) for i in range(t.rowCount())), 340))
            t.cellClicked.connect(lambda baris, _k, sl=slot, tb=t: self._pilih_baris(sl, tb, baris))
            k.addWidget(t)
            self.combo[slot], self.tabel[slot] = cb, t
            v.addWidget(kartu)
            self._tandai(slot, perbarui=False)
        v.addStretch()
        lay.addWidget(gulir, stretch=1)

        self.label_info = tema.label("", "infoKecil", wrap=True)
        lay.addWidget(self.label_info)
        self.label_galat = tema.label("", "galat", wrap=True)
        self.label_galat.hide()
        lay.addWidget(self.label_galat)
        tombol = QHBoxLayout()
        ikut = tema.tombol("Ikuti Pilihan Proyek", "ghost", "ulang")
        ikut.clicked.connect(self._ikut_proyek)
        batal = tema.tombol("Batal", "secondary")
        batal.clicked.connect(self.reject)
        self.btn_simpan = tema.tombol("Simpan Material Elemen", "primary")
        self.btn_simpan.clicked.connect(self._simpan)
        tombol.addWidget(ikut)
        tombol.addStretch()
        tombol.addWidget(batal)
        tombol.addWidget(self.btn_simpan)
        lay.addLayout(tombol)
        self._perbarui()

    def pilihan(self) -> dict:
        return {k: cb.currentData() for k, cb in self.combo.items()}

    def _pilih_baris(self, slot, tabel, baris):
        kunci = tabel.item(baris, 0).data(Qt.UserRole)
        self.combo[slot].setCurrentIndex(self.combo[slot].findData(kunci))

    def _tandai(self, slot, perbarui: bool = True):
        kunci = self.combo[slot].currentData()
        t = self.tabel[slot]
        for i in range(t.rowCount()):
            dipilih = t.item(i, 0).data(Qt.UserRole) == kunci
            for kol in range(t.columnCount()):
                it = t.item(i, kol)
                f = it.font()
                f.setBold(dipilih)
                it.setFont(f)
                if kol == 0:
                    it.setText(("▶ " if dipilih else "") + SLOT[slot].cari(it.data(Qt.UserRole)).label)
        if perbarui:
            self._perbarui()

    def _perbarui(self):
        berubah = [k for k, cb in self.combo.items() if cb.currentData() != self._slot[k]["kunci"]]
        khusus = [k for k, cb in self.combo.items() if cb.currentData() != self._proyek[k]]
        self.btn_simpan.setEnabled(bool(berubah))
        self.label_galat.hide()
        teks = (f"{len(khusus)} pekerjaan memakai material khusus elemen ini." if khusus
                else "Elemen ini mengikuti pilihan material proyek.")
        self.label_info.setText(teks + " Volume elemen tidak berubah.")

    def _ikut_proyek(self):
        for k, cb in self.combo.items():
            cb.setCurrentIndex(max(0, cb.findData(self._proyek[k])))

    def _simpan(self):
        try:
            self.hasil = simpan_material_elemen(self.elemen_id, self.pilihan())
        except ValueError as e:  # KF-14
            self.label_galat.setText(str(e))
            self.label_galat.show()
            return
        self.diubah = True
        self.accept()


def muat_pilihan_proyek_elemen(elemen_id: int) -> dict:
    """Pilihan material proyek tempat elemen ini berada."""
    from database.estimasi_repository import _connect

    conn = _connect()
    try:
        row = conn.execute("SELECT proyek_id FROM elemen_proyek WHERE id = ?", (elemen_id,)).fetchone()
        return muat_pilihan(row["proyek_id"], conn) if row else {}
    finally:
        conn.close()
