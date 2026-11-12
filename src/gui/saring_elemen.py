"""
Penyaring baris hasil estimasi per elemen tanpa mengetik (pengganti kotak cari di halaman Hasil Estimasi):

- checkbox **Jenis elemen**: Kolom, Balok, Pelat lantai, Dinding, Fondasi, ... beserta jumlah elemennya;
- radio button **Nama elemen**: hanya elemen dari jenis yang dicentang, mis. Kolom K1 30x30 Lt.1 A1, A2, ...;
  muncul setelah ada jenis yang dicentang.

Tanpa centang = semua elemen. Saringan berlaku di semua tab (RAB, RAB Rinci, Per Lantai, Per Elemen, Kebutuhan
Bahan), bersama combo kategori pekerjaan dan lantai.
"""

import re

from PySide6.QtCore import QPoint, QRect, QSize, Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QLayout,
    QRadioButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from gui import tema
from kebutuhan_lantai import JENIS_TAMBAHAN, jenis_elemen, urutan_jenis
from rab_rinci import TANPA_LANTAI, daftar_lantai

SEMUA_NAMA = 0  # id radio "Semua elemen" (id -1 berarti "otomatis" bagi QButtonGroup)


def _teks_tombol(teks: str) -> str:
    """Teks checkbox / radio: "&" ditampilkan apa adanya (bukan tanda pintasan Alt)."""
    return teks.replace("&", "&&")


def label_jenis(jenis: str) -> str:
    """Label checkbox ringkas: "Elemen lain (fasad, atap, lansekap, sanitair)" -> "Elemen lain"."""
    return jenis.split(" (", 1)[0] if jenis.startswith("Elemen lain") else jenis


def urut_alami(teks: str) -> list:
    """Kunci urut nama: angka dibandingkan sebagai angka (A2 sebelum A10, As 2 sebelum As 10)."""
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", teks or "")]


class TataAlir(QLayout):
    """Tata letak mengalir: widget berjajar ke kanan lalu pindah ke baris berikutnya bila lebar habis."""

    def __init__(self, parent=None, jarak_h: int = 16, jarak_v: int = 6):
        super().__init__(parent)
        self._item = []
        self._h, self._v = jarak_h, jarak_v
        self.setContentsMargins(0, 0, 0, 0)

    def addItem(self, item):  # nama metode mengikuti API Qt
        self._item.append(item)

    def count(self):
        return len(self._item)

    def itemAt(self, i):
        return self._item[i] if 0 <= i < len(self._item) else None

    def takeAt(self, i):
        return self._item.pop(i) if 0 <= i < len(self._item) else None

    def expandingDirections(self):
        return Qt.Orientation(0)

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, lebar):
        return self._atur(QRect(0, 0, lebar, 0), True)

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self._atur(rect, False)

    def sizeHint(self):
        return self.minimumSize()

    def minimumSize(self):
        s = QSize()
        for it in self._item:
            s = s.expandedTo(it.minimumSize())
        m = self.contentsMargins()
        return s + QSize(m.left() + m.right(), m.top() + m.bottom())

    def _atur(self, rect: QRect, uji: bool) -> int:
        m = self.contentsMargins()
        r = rect.adjusted(m.left(), m.top(), -m.right(), -m.bottom())
        x, y, tinggi = r.x(), r.y(), 0
        for it in self._item:
            w = it.widget()
            if w is not None and w.isHidden():
                continue
            ukuran = it.sizeHint()
            if x > r.x() and x + ukuran.width() > r.right() + 1:  # tidak muat: pindah baris
                x, y, tinggi = r.x(), y + tinggi + self._v, 0
            if not uji:
                it.setGeometry(QRect(QPoint(x, y), ukuran))
            x += ukuran.width() + self._h
            tinggi = max(tinggi, ukuran.height())
        return y + tinggi - rect.y() + m.bottom()


def _kosongkan(lay: QLayout):
    while lay.count():
        w = lay.takeAt(0).widget()
        if w is not None:
            w.hide()
            w.deleteLater()


class SaringElemen(QFrame):
    """Checkbox jenis elemen + radio button nama elemen. `cocok(baris)` dipakai halaman untuk menyaring baris."""

    berubah = Signal()
    BARIS_NAMA = 3  # tinggi daftar nama elemen (baris radio button) sebelum digulir

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("saringElemen")
        self._cek = {}  # jenis -> QCheckBox
        self._radio = {}  # elemen_id -> QRadioButton
        self._kunci_jenis = None
        self._kunci_nama = None
        self._elemen = None  # elemen_id terpilih, None = semua elemen jenis tercentang
        self._nama = {}  # elemen_id -> label tampil
        self._id_elemen = {}  # id radio -> elemen_id

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)

        b1 = QHBoxLayout()
        b1.setSpacing(12)
        self.label_jenis = tema.label("JENIS ELEMEN", "bagian")
        self.label_jenis.setFixedWidth(118)
        self.label_jenis.setToolTip("Centang satu atau beberapa jenis elemen; tanpa centang = semua elemen")
        b1.addWidget(self.label_jenis, 0, Qt.AlignTop)
        self._wadah_jenis = QWidget()
        self._alir_jenis = TataAlir(self._wadah_jenis, 18, 6)
        b1.addWidget(self._wadah_jenis, 1)
        self.btn_hapus = tema.tombol("Hapus Saringan", "ghost", "ulang", "Tampilkan lagi semua elemen")
        self.btn_hapus.clicked.connect(self.hapus)
        self.btn_hapus.hide()
        b1.addWidget(self.btn_hapus, 0, Qt.AlignTop)
        lay.addLayout(b1)

        self.baris_nama = QWidget()
        b2 = QHBoxLayout(self.baris_nama)
        b2.setContentsMargins(0, 0, 0, 0)
        b2.setSpacing(12)
        self.label_nama = tema.label("NAMA ELEMEN", "bagian")
        self.label_nama.setFixedWidth(118)
        self.label_nama.setToolTip("Pilih satu elemen dari jenis yang dicentang")
        b2.addWidget(self.label_nama, 0, Qt.AlignTop)
        self.gulir = QScrollArea()
        self.gulir.setWidgetResizable(True)
        self.gulir.setFrameShape(QFrame.NoFrame)
        self.gulir.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._wadah_nama = QWidget()
        self._wadah_nama.setObjectName("wadahNamaElemen")
        self._alir_nama = TataAlir(self._wadah_nama, 22, 4)
        self.gulir.setWidget(self._wadah_nama)
        b2.addWidget(self.gulir, 1)
        self.grup_nama = QButtonGroup(self)
        self.grup_nama.setExclusive(True)
        self.grup_nama.idClicked.connect(self._pilih_radio)
        self.baris_nama.hide()
        lay.addWidget(self.baris_nama)

    # ------------------------------------------------------------------ status

    def jenis_terpilih(self) -> set:
        return {j for j, cb in self._cek.items() if cb.isChecked()}

    def elemen_terpilih(self):
        return self._elemen

    def aktif(self) -> bool:
        return bool(self.jenis_terpilih()) or self._elemen is not None

    def cocok(self, r: dict) -> bool:
        if self._elemen is not None:
            return r.get("elemen_id") == self._elemen
        jenis = self.jenis_terpilih()
        return not jenis or jenis_elemen(r) in jenis

    def ringkasan(self) -> str:
        """Teks saringan aktif untuk baris jumlah, mis. "Kolom K1 30x30 Lt.1 A1" atau "Kolom, Balok"."""
        if self._elemen is not None:
            return self._nama.get(self._elemen, "")
        jenis = sorted(self.jenis_terpilih(), key=urutan_jenis)
        return ", ".join(jenis)

    # ------------------------------------------------------------------ isi

    def isi_jenis(self, data: list):
        """Checkbox jenis elemen dari seluruh baris proyek (centang lama dipertahankan)."""
        elemen = {}
        for r in data:
            jn = jenis_elemen(r)
            elemen.setdefault(jn, set()).add(r.get("elemen_id") or ("baris", r.get("hasil_id")))
        daftar = [(jn, len(elemen[jn])) for jn in sorted(elemen, key=urutan_jenis)]
        if daftar == self._kunci_jenis:
            return
        self._kunci_jenis = daftar
        lama = self.jenis_terpilih()
        _kosongkan(self._alir_jenis)
        self._cek = {}
        for jn, n in daftar:
            satuan = "item" if jn == JENIS_TAMBAHAN else "elemen"
            cb = QCheckBox(_teks_tombol(f"{label_jenis(jn)} ({n})"))
            cb.setToolTip(f"Tampilkan hanya {jn.lower()} ({n} {satuan}); dapat dicentang lebih dari satu")
            cb.setCursor(Qt.PointingHandCursor)
            cb.setChecked(jn in lama)
            cb.toggled.connect(self._ganti_jenis)
            self._alir_jenis.addWidget(cb)
            self._cek[jn] = cb
        if self._elemen is not None and not self.jenis_terpilih():
            self._elemen = None

    def perbarui_nama(self, baris: list):
        """Radio button nama elemen dari jenis yang dicentang, di antara baris yang lolos saringan kategori & lantai.
        Urut jenis (fondasi → atap), lantai (bawah → atas), lalu nama (A1, A2, ..., A10)."""
        jenis = self.jenis_terpilih()
        self.baris_nama.setVisible(bool(jenis))
        self.btn_hapus.setVisible(self.aktif())
        if not jenis:
            self._elemen = None
            return
        urut_lt = {nama: i for i, nama in enumerate(daftar_lantai(baris))}
        elemen = {}
        for r in baris:
            eid = r.get("elemen_id")
            if eid and jenis_elemen(r) in jenis and eid not in elemen:
                elemen[eid] = (jenis_elemen(r), r.get("lantai") or TANPA_LANTAI, r.get("nama_elemen") or f"Elemen {eid}")
        kembar = {}
        for eid, (_jn, _lt, nama) in elemen.items():
            kembar.setdefault(nama, []).append(eid)
        label = {}
        for nama, ids in kembar.items():
            for eid in ids:
                label[eid] = nama if len(ids) == 1 else f"{nama} · {elemen[eid][1]}"
        sama = {}
        for eid, teks in label.items():
            sama.setdefault(teks, []).append(eid)
        for teks, ids in sama.items():
            if len(ids) > 1:
                for i, eid in enumerate(sorted(ids), 1):
                    label[eid] = f"{teks} #{i}"
        urut = sorted(elemen, key=lambda e: (urutan_jenis(elemen[e][0]), urut_lt.get(elemen[e][1], 1e9),
                                             urut_alami(label[e])))
        kunci = [(e, label[e]) for e in urut]
        if self._elemen not in elemen:
            self._elemen = None
        self.btn_hapus.setVisible(self.aktif())
        if kunci != self._kunci_nama:
            self._kunci_nama = kunci
            self._nama = label
            _kosongkan(self._alir_nama)
            for b in self.grup_nama.buttons():
                self.grup_nama.removeButton(b)
            self._radio = {}
            semua = QRadioButton(f"Semua ({len(urut)} elemen)")
            semua.setToolTip("Semua elemen dari jenis yang dicentang")
            self.grup_nama.addButton(semua, SEMUA_NAMA)
            self._alir_nama.addWidget(semua)
            for i, eid in enumerate(urut):
                jn, lt, _nama = elemen[eid]
                rb = QRadioButton(_teks_tombol(label[eid]))
                rb.setToolTip(f"{jn}  ·  {lt}")
                self.grup_nama.addButton(rb, i + 1)
                self._alir_nama.addWidget(rb)
                self._radio[eid] = rb
            self._id_elemen = {i + 1: eid for i, eid in enumerate(urut)}
        tombol = self._radio.get(self._elemen) if self._elemen is not None else self.grup_nama.button(SEMUA_NAMA)
        if tombol is not None:
            tombol.setChecked(True)
        self._atur_tinggi_nama()
        if self._elemen is not None and tombol is not None:  # radio terpilih (mis. dari Model 3D) tampak di daftar
            QTimer.singleShot(0, lambda: self._tampakkan(tombol))

    def _tampakkan(self, tombol):
        """Gulir daftar nama ke radio terpilih (setelah tata letak selesai menghitung posisinya)."""
        if tombol in self._radio.values() and tombol.isChecked():
            self.gulir.ensureWidgetVisible(tombol, 0, 6)

    def _atur_tinggi_nama(self):
        """Daftar nama setinggi isinya, paling tinggi BARIS_NAMA baris; selebihnya digulir."""
        if not self._radio and self.grup_nama.button(SEMUA_NAMA) is None:
            return
        contoh = self.grup_nama.button(SEMUA_NAMA)
        tinggi_baris = contoh.sizeHint().height() if contoh is not None else 24
        maks = tinggi_baris * self.BARIS_NAMA + 4 * (self.BARIS_NAMA - 1)
        lebar = max(self.gulir.viewport().width(), 200)
        isi = self._alir_nama.heightForWidth(lebar)
        self.gulir.setFixedHeight(min(isi, maks) + 2)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.baris_nama.isVisible():
            self._atur_tinggi_nama()

    # ------------------------------------------------------------------ aksi

    def _ganti_jenis(self, _centang: bool):
        self.berubah.emit()

    def _pilih_radio(self, i: int):
        self._elemen = None if i == SEMUA_NAMA else self._id_elemen.get(i)
        self.btn_hapus.setVisible(self.aktif())
        self.berubah.emit()

    def hapus(self):
        """Tanpa saringan: semua centang dilepas, semua elemen tampil."""
        for cb in self._cek.values():
            cb.blockSignals(True)
            cb.setChecked(False)
            cb.blockSignals(False)
        self._elemen = None
        self.berubah.emit()

    def pilih_elemen(self, elemen_id: int, jenis: str):
        """Saring ke satu elemen (mis. dari Model 3D > Lihat di Tabel RAB): hanya jenisnya yang dicentang, lalu
        radio elemen itu dipilih. Tidak memancarkan `berubah`; halaman mengisi ulang tabel sendiri."""
        for jn, cb in self._cek.items():
            cb.blockSignals(True)
            cb.setChecked(jn == jenis)
            cb.blockSignals(False)
        self._elemen = elemen_id if jenis in self._cek else None

    def fokus(self):
        """Ctrl+F: fokus ke checkbox jenis elemen pertama."""
        if self._cek:
            next(iter(self._cek.values())).setFocus(Qt.ShortcutFocusReason)
