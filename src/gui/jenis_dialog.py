"""
Dialog Koreksi Jenis Elemen Lain: daftar semua elemen kelas LAINNYA (cladding, kisi, roster, lisplang, nok,
talang, waterproofing, lansekap, sanitair, rangka baja/kayu, elemen tanpa analisa) beserta jenis yang dikenali
otomatis dari nama/teks model. Pengguna dapat mengoreksi jenisnya bila penamaan model tidak lazim, atau
mengecualikan elemen dari RAB ("Tidak dihitung"). Disimpan sekaligus sebagai satu langkah urungkan.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLineEdit,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

import elemen_lain
from estimasi_service import daftar_elemen_lain
from gui import tema

KOLOM = ("Elemen", "Kelas IFC", "Lantai", "Dimensi", "Dikenali otomatis", "Jenis yang dipakai", "Biaya")


def teks_dimensi(d: dict) -> str:
    bagian = []
    if d.get("luas"):
        bagian.append(f"{tema.format_angka(d['luas'], 2)} m²")
    if d.get("panjang"):
        bagian.append(f"{tema.format_angka(d['panjang'], 2)} m")
    if d.get("volume"):
        bagian.append(f"{tema.format_angka(d['volume'], 3)} m³")
    return " · ".join(bagian) or "-"


class JenisElemenDialog(QDialog):
    """`pilih` = elemen_id yang langsung disorot (dibuka dari panel Rincian / Model 3D)."""

    def __init__(self, proyek_id: int, parent=None, pilih: int | None = None):
        super().__init__(parent)
        self.proyek_id = proyek_id
        self.perubahan = {}  # elemen_id -> kunci jenis, atau None = kembali ke otomatis
        self._data = daftar_elemen_lain(proyek_id)
        self._combo = {}
        self.setWindowTitle("Koreksi Jenis Elemen Lain")
        self.setModal(True)
        self.resize(1400, 720)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(26, 22, 26, 20)
        lay.setSpacing(12)
        lay.addWidget(tema.kepala_dialog(
            "Koreksi Jenis Elemen Lain",
            "Jenis elemen di luar kolom, balok, pelat, dinding, dan sejenisnya dikenali dari nama dan keterangan "
            "model. Bila penamaan model tidak lazim, pilih jenis yang benar. Pilih \"Tidak dihitung\" untuk elemen "
            "yang sudah termasuk pekerjaan lain atau di luar lingkup RAB. Kuantitas dihitung ulang tanpa membaca "
            "file IFC, dan pilihan tetap berlaku saat IFC dibaca ulang.",
            "kubus",
        )[0])

        alat = QHBoxLayout()
        self.cari = QLineEdit()
        tema.pasang_ikon_cari(self.cari)
        self.cari.setPlaceholderText("Cari nama elemen, kelas IFC, lantai, atau jenis...")
        self.cari.setClearButtonEnabled(True)
        self.cari.textChanged.connect(self._saring)
        alat.addWidget(self.cari, stretch=1)
        self.label_jumlah = tema.label("", "subjudul")
        alat.addWidget(self.label_jumlah)
        lay.addLayout(alat)

        self.tabel = QTableWidget(len(self._data), len(KOLOM))
        self.tabel.setHorizontalHeaderLabels(KOLOM)
        tema.pasang_teks_kosong(self.tabel, "Tidak ada elemen lain",
                                "Semua elemen model termasuk kelas utama (kolom, balok, pelat, dinding, ...).")
        self.tabel.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tabel.setSelectionMode(QAbstractItemView.SingleSelection)
        self.tabel.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tabel.verticalHeader().setVisible(False)
        self.tabel.verticalHeader().setDefaultSectionSize(max(44, QComboBox().sizeHint().height() + 12))
        self.tabel.setWordWrap(False)
        h = self.tabel.horizontalHeader()
        h.setSectionResizeMode(0, QHeaderView.Stretch)
        h.setMinimumSectionSize(70)
        for i in (1, 2, 3, 4, 6):
            h.setSectionResizeMode(i, QHeaderView.ResizeToContents)
        h.setSectionResizeMode(5, QHeaderView.Fixed)
        self.tabel.setColumnWidth(5, 330)
        self._isi(pilih)
        lay.addWidget(self.tabel, stretch=1)

        bawah = QHBoxLayout()
        self.btn_otomatis = tema.tombol("Kembalikan Semua ke Otomatis", "ghost", "ulang",
                                        "Hapus semua koreksi jenis pada proyek ini")
        self.btn_otomatis.clicked.connect(self._semua_otomatis)
        bawah.addWidget(self.btn_otomatis)
        self.label_pesan = tema.label("", "petunjuk")
        bawah.addWidget(self.label_pesan, stretch=1)
        batal = tema.tombol("Batal", "secondary")
        batal.clicked.connect(self.reject)
        self.btn_simpan = tema.tombol("Simpan && Hitung Ulang", "primary")
        self.btn_simpan.clicked.connect(self.accept)
        bawah.addWidget(batal)
        bawah.addWidget(self.btn_simpan)
        lay.addLayout(bawah)
        self._perbarui()

    # ------------------------------------------------------------------ isi tabel

    def _isi(self, pilih):
        opsi = elemen_lain.pilihan_jenis()
        baris_pilih = None
        for i, d in enumerate(self._data):
            sel = [d["nama"] or d["global_id"], (d["ifc_type"] or "").replace("Ifc", ""), d["lantai"] or "-",
                   teks_dimensi(d), elemen_lain.label_pilihan(d["jenis_otomatis"]), None,
                   tema.format_rupiah(d["biaya"]) if d["baris"] else "tidak dihitung"]
            for j, teks in enumerate(sel):
                if teks is None:
                    continue
                item = QTableWidgetItem(teks)
                item.setToolTip(teks)
                if j == len(KOLOM) - 1:
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self.tabel.setItem(i, j, item)
            cb = QComboBox()
            cb.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            cb.setMinimumContentsLength(24)
            cb.wheelEvent = lambda e: e.ignore()  # roda mouse menggulir tabel, bukan mengganti jenis
            for kunci, label in opsi:
                cb.addItem(label + ("  (otomatis)" if kunci == d["jenis_otomatis"] else ""), kunci)
            cb.setCurrentIndex(max(0, cb.findData(d["jenis"])))
            cb.currentIndexChanged.connect(lambda _i, eid=d["id"]: self._ganti(eid))
            self.tabel.setCellWidget(i, 5, cb)
            self._combo[d["id"]] = cb
            if d["id"] == pilih:
                baris_pilih = i
        if baris_pilih is not None:
            self.tabel.selectRow(baris_pilih)
            self.tabel.scrollToItem(self.tabel.item(baris_pilih, 0), QAbstractItemView.PositionAtCenter)
            self._combo[pilih].setFocus()

    def _ganti(self, elemen_id: int):
        d = next(x for x in self._data if x["id"] == elemen_id)
        kunci = self._combo[elemen_id].currentData()
        if kunci == d["jenis"]:
            self.perubahan.pop(elemen_id, None)
        else:
            self.perubahan[elemen_id] = None if kunci == d["jenis_otomatis"] else kunci
        self._perbarui()

    def _semua_otomatis(self):
        for d in self._data:
            cb = self._combo[d["id"]]
            cb.setCurrentIndex(max(0, cb.findData(d["jenis_otomatis"])))

    def _saring(self, teks: str):
        kata = teks.strip().lower()
        for i, d in enumerate(self._data):
            isi = " ".join(str(x or "") for x in (d["nama"], d["ifc_type"], d["lantai"],
                                                    elemen_lain.label_pilihan(d["jenis"]),
                                                    elemen_lain.label_pilihan(d["jenis_otomatis"]))).lower()
            self.tabel.setRowHidden(i, bool(kata) and kata not in isi)

    def _perbarui(self):
        dikoreksi = sum(1 for d in self._data if d["manual"])
        self.label_jumlah.setText(f"{len(self._data)} elemen lain · {dikoreksi} dikoreksi pengguna")
        self.btn_otomatis.setEnabled(any(d["manual"] for d in self._data))
        n = len(self.perubahan)
        self.label_pesan.setText(f"{n} perubahan belum disimpan" if n else "")
        self.btn_simpan.setEnabled(bool(n))
