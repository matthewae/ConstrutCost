"""
Penampil 3D bangunan dengan panel kebutuhan biaya per elemen.

Alur pengguna (tombol "Model 3D" di halaman estimasi):
1. Model IFC proyek dibaca sekali di latar (model3d.py) dan disimpan di cache selama aplikasi terbuka.
2. Klik elemen pada model untuk memilihnya. Panel kanan menampilkan kebutuhan biaya elemen itu, diurutkan
   menurut tahap pekerjaan (tanah, fondasi, beton, dinding, ... cat). Untuk kolom ikut ditampilkan pedestal,
   fondasi, dan pekerjaan tanah di bawahnya; untuk dinding ikut sloof, fondasi menerus, dan pekerjaan tanahnya
   (biaya_elemen.py). Bagian yang ikut dihitung diberi warna hijau di model.
3. Bahan elemen dapat diganti langsung dari panel (combo box, harga per pilihan untuk elemen ini). Perubahan
   tersimpan ke RAB, masuk riwayat Urungkan (Ctrl+Z), dan tabel RAB ikut diperbarui.

Kontrol: seret kiri = putar, seret kanan/tengah = geser, roda = zoom, klik = pilih, dobel klik = fokus,
Esc = batal pilih. Semua angka dibaca dari hasil estimasi tersimpan, sama dengan tabel RAB dan export.
"""

import math
from pathlib import Path

import numpy as np
from PySide6.QtCore import (
    Property, QAbstractListModel, QByteArray, QModelIndex, QObject, QStringListModel, Qt, QTimer, QUrl, Signal, Slot,
)
from PySide6.QtGui import QColor, QKeySequence, QLinearGradient, QPainter, QPen, QShortcut, QVector3D
from PySide6.QtQuick import QSGRendererInterface
from PySide6.QtQuick3D import QQuick3DGeometry
from PySide6.QtQuickWidgets import QQuickWidget
from PySide6.QtWidgets import (
    QButtonGroup, QCheckBox, QComboBox, QCompleter, QDialog, QFrame, QHBoxLayout, QLabel, QLineEdit, QMessageBox,
    QPushButton, QScrollArea, QSizePolicy, QSplitter, QStackedWidget, QVBoxLayout, QWidget,
)

from biaya_elemen import peta_biaya, rincian
from database.material import SLOT, kode_varian
from gui import tema
from gui.galat import tanpa_terjemahan_python
from klasifikasi import LABEL, ElementType
from kolom import LABEL_FUNGSI
from rab_rinci import urutan_kategori

QML = Path(__file__).with_name("penampil3d.qml")

# ---------------------------------------------------------------- warna & pengelompokan

WARNA_JENIS = {
    "COLUMN": "#c9784a", "BEAM": "#6f8fb3", "SLAB": "#a7adb4", "FLOOR": "#bfc3c8", "ROOF": "#a0503f",
    "WALL": "#ddd3c2", "FOOTING": "#8c7355", "PILE": "#7a6249", "EARTHWORK": "#c2aa80", "DOOR": "#8a6040",
    "WINDOW": "#8fc9e6", "STAIR": "#9d8fc4", "RAILING": "#7b828a", "CEILING": "#ebe7e0", "WALL_TILE": "#cfe3e8",
}
WARNA_LAIN = "#8d8d8d"  # elemen yang tidak menghasilkan item RAB
WARNA_PILIH = "#ffd43b"
WARNA_TERKAIT = "#69db7c"
SKALA_BIAYA = ("#3b4cc0", "#88abfd", "#dddddd", "#f4987a", "#b40426")  # rendah -> tinggi

STRUKTUR = {"COLUMN", "BEAM", "SLAB", "FOOTING", "PILE", "STAIR", "EARTHWORK"}
URUT_LEGENDA = ("FOOTING", "PILE", "EARTHWORK", "COLUMN", "BEAM", "SLAB", "STAIR", "WALL", "FLOOR", "WALL_TILE",
                "DOOR", "WINDOW", "RAILING", "CEILING", "ROOF")
KELAS_IFC = {
    "IfcWall": "WALL", "IfcWallStandardCase": "WALL", "IfcCurtainWall": "WALL", "IfcPlate": "WALL",
    "IfcColumn": "COLUMN", "IfcBeam": "BEAM", "IfcMember": "BEAM", "IfcSlab": "SLAB", "IfcRoof": "ROOF",
    "IfcFooting": "FOOTING", "IfcPile": "PILE", "IfcDoor": "DOOR", "IfcWindow": "WINDOW", "IfcStair": "STAIR",
    "IfcStairFlight": "STAIR", "IfcRamp": "STAIR", "IfcRampFlight": "STAIR", "IfcRailing": "RAILING",
    "IfcCovering": "CEILING",
}
TAMPIL_LENGKAP, TAMPIL_TEMBUS, TAMPIL_STRUKTUR = range(3)
WARNA_JENIS_MODE, WARNA_BIAYA_MODE = range(2)

PERAN_RINGKAS = {
    "Elemen terpilih": "Elemen ini", "Pedestal (bagian kolom ini)": "Pedestal", "Segmen kolom yang sama": "Segmen kolom",
    "Sloof di bawah dinding": "Sloof", "Fondasi di bawah kolom": "Fondasi",
    "Fondasi lain di titik kolom yang sama": "Fondasi", "Fondasi menerus di bawah dinding": "Fondasi menerus",
    "Pekerjaan tanah di bawah fondasi": "Pekerjaan tanah",
}
NAMA_TAHAP = {
    "Persiapan": "Pekerjaan Persiapan", "Tanah": "Pekerjaan Tanah", "Fondasi": "Pekerjaan Fondasi",
    "Beton": "Pekerjaan Beton Bertulang", "Dinding": "Pekerjaan Dinding", "Lantai": "Pekerjaan Lantai",
    "Cat": "Pekerjaan Pengecatan", "Atap": "Pekerjaan Atap", "Plafon": "Pekerjaan Plafon",
}


def tersedia() -> tuple:
    """(True, "") bila penampil dapat dibuka. Modul Qt Quick 3D sudah diimpor di atas (ImportError ditangkap
    pemanggil); yang tersisa adalah file tampilan QML yang harus ikut terpasang (CostStruct.spec)."""
    if QML.exists():
        return True, ""
    return False, f"File tampilan {QML.name} tidak ditemukan di {QML.parent}"


def kelas_tampil(info: dict | None, ifc: str) -> str:
    """Kelas elemen untuk warna & penyaring: kelas hasil klasifikasi bila dihitung, selain itu dari tipe IFC."""
    if info and info.get("kelas"):
        return info["kelas"]
    return KELAS_IFC.get(ifc, "UNKNOWN")


def label_kelas(info: dict | None, ifc: str) -> str:
    kelas = kelas_tampil(info, ifc)
    if kelas == "COLUMN" and info and (info.get("info_kolom") or {}).get("fungsi"):
        return LABEL_FUNGSI.get(info["info_kolom"]["fungsi"], "Kolom")
    if kelas in ElementType._value2member_map_ and kelas != "UNKNOWN":
        return LABEL[ElementType(kelas)]
    return ifc.replace("Ifc", "") if ifc else "Elemen"


def warna_skala(t: float) -> QColor:
    """Warna skala biaya, t = 0 (rendah) .. 1 (tinggi)."""
    t = min(max(t, 0.0), 1.0) * (len(SKALA_BIAYA) - 1)
    i = min(int(t), len(SKALA_BIAYA) - 2)
    a, b = QColor(SKALA_BIAYA[i]), QColor(SKALA_BIAYA[i + 1])
    f = t - i
    return QColor.fromRgbF(a.redF() + (b.redF() - a.redF()) * f, a.greenF() + (b.greenF() - a.greenF()) * f,
                           a.blueF() + (b.blueF() - a.blueF()) * f)


def peringkat_biaya(peta: dict) -> dict:
    """{gid: t} posisi persentil biaya elemen (0 termurah, 1 termahal) di antara elemen yang punya biaya."""
    nilai = sorted((x["total"], g) for g, x in peta.items() if x["total"] > 0)
    n = len(nilai)
    return {g: (i / (n - 1) if n > 1 else 1.0) for i, (_t, g) in enumerate(nilai)}


def rupiah_ringkas(x: float) -> str:
    if abs(x) >= 1e9:
        return f"Rp {tema.format_angka(x / 1e9, 2)} M"
    if abs(x) >= 1e6:
        return f"Rp {tema.format_angka(x / 1e6, 2)} jt"
    return tema.format_rupiah(x)


# ---------------------------------------------------------------- objek Qt Quick 3D

class Geometri3D(QQuick3DGeometry):
    """Segitiga satu elemen (posisi + normal, tanpa indeks)."""

    def __init__(self, posisi: np.ndarray, normal: np.ndarray, parent=None):
        super().__init__(parent)
        data = np.ascontiguousarray(np.hstack([posisi, normal]), dtype=np.float32)
        self.setVertexData(QByteArray(data.tobytes()))
        self.setStride(24)
        self.setPrimitiveType(QQuick3DGeometry.PrimitiveType.Triangles)
        self.addAttribute(QQuick3DGeometry.Attribute.PositionSemantic, 0, QQuick3DGeometry.Attribute.F32Type)
        self.addAttribute(QQuick3DGeometry.Attribute.NormalSemantic, 12, QQuick3DGeometry.Attribute.F32Type)
        mn, mx = posisi.min(axis=0), posisi.max(axis=0)
        self.setBounds(QVector3D(*map(float, mn)), QVector3D(*map(float, mx)))


class AdeganModel(QAbstractListModel):
    """Satu baris per elemen 3D; QML membuat satu Model per baris (Repeater3D)."""

    GID, GEOM, WARNA, BURAM, TAMPIL, KLIK, SINAR = range(Qt.UserRole + 1, Qt.UserRole + 8)
    _NAMA = {GID: b"gid", GEOM: b"geom", WARNA: b"warna", BURAM: b"buram", TAMPIL: b"tampil", KLIK: b"klik",
             SINAR: b"sinar"}
    _KUNCI = {WARNA: "warna", BURAM: "buram", TAMPIL: "tampil", KLIK: "klik", SINAR: "sinar"}

    def __init__(self, parent=None):
        super().__init__(parent)
        self._baris = []
        self._indeks = {}

    def roleNames(self):  # noqa: N802 (API Qt)
        return self._NAMA

    def rowCount(self, parent=QModelIndex()):  # noqa: N802
        return 0 if parent.isValid() else len(self._baris)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid() or not 0 <= index.row() < len(self._baris):
            return None
        b = self._baris[index.row()]
        if role == self.GID:
            return b["gid"]
        if role == self.GEOM:
            return b["geom"]
        kunci = self._KUNCI.get(role)
        return b[kunci] if kunci else None

    def atur(self, elemen: list) -> None:
        """elemen: [(gid, Geometri3D)]."""
        self.beginResetModel()
        self._baris = [{"gid": g, "geom": geo, "warna": QColor(WARNA_LAIN), "buram": 1.0, "tampil": True,
                        "klik": True, "sinar": 0.0} for g, geo in elemen]
        self._indeks = {b["gid"]: i for i, b in enumerate(self._baris)}
        self.endResetModel()

    def gids(self) -> list:
        return [b["gid"] for b in self._baris]

    def keadaan(self, gid: str) -> dict | None:
        i = self._indeks.get(gid)
        return dict(self._baris[i]) if i is not None else None

    def perbarui(self, keadaan: dict) -> int:
        """keadaan: {gid: {"warna", "buram", "tampil", "klik", "sinar"}}; hanya baris yang berubah dikirim ke QML."""
        berubah = []
        for gid, k in keadaan.items():
            i = self._indeks.get(gid)
            if i is None:
                continue
            b = self._baris[i]
            peran = [r for r, nama in self._KUNCI.items() if b[nama] != k[nama]]
            if peran:
                b.update({nama: k[nama] for nama in self._KUNCI.values()})
                berubah.append((i, peran))
        if len(berubah) > 64:
            self.dataChanged.emit(self.index(0), self.index(len(self._baris) - 1), list(self._KUNCI))
        else:
            for i, peran in berubah:
                self.dataChanged.emit(self.index(i), self.index(i), peran)
        return len(berubah)


class Backend(QObject):
    """Kamera orbit, warna adegan, dan penghubung klik/sorot dari QML ke Python."""

    pusatChanged = Signal()
    rotasiChanged = Signal()
    jarakChanged = Signal()
    animasiChanged = Signal()
    teksSorotChanged = Signal()
    warnaChanged = Signal()

    dipilih = Signal(str)
    disorot = Signal(str)
    fokus_diminta = Signal(str)

    FOV = 38.0

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pusat = QVector3D(0, 3, 0)
        self._rotasi = QVector3D(-28, -35, 0)
        self._jarak = 30.0
        self._animasi = False
        self._teks_sorot = ""
        self._sorot = ""
        gelap = QColor(tema.W["latar"]).lightnessF() < 0.5
        self._warna = {
            "latar": QColor("#1c1d20" if gelap else "#e9ebee"),
            "label": QColor(tema.W["permukaan"]),
            "garis": QColor(tema.W["garis_kuat"]),
            "teks": QColor(tema.W["teks"]),
        }
        self._henti = QTimer(self, singleShot=True, interval=520, timeout=lambda: self._set_animasi(False))

    # --- properti untuk QML
    def _get_pusat(self):
        return self._pusat

    def _set_pusat(self, v):
        self._henti_animasi_bila_manual()
        if v != self._pusat:
            self._pusat = QVector3D(v)
            self.pusatChanged.emit()

    def _get_rotasi(self):
        return self._rotasi

    def _set_rotasi(self, v):
        self._henti_animasi_bila_manual()
        if v != self._rotasi:
            self._rotasi = QVector3D(v)
            self.rotasiChanged.emit()

    def _get_jarak(self):
        return self._jarak

    def _set_jarak(self, v):
        v = float(min(max(v, 0.4), 5000.0))
        if abs(v - self._jarak) > 1e-6:
            self._jarak = v
            self.jarakChanged.emit()

    def _get_animasi(self):
        return self._animasi

    def _set_animasi(self, v):
        if v != self._animasi:
            self._animasi = v
            self.animasiChanged.emit()

    def _henti_animasi_bila_manual(self):
        if self._animasi and not self._henti.isActive():
            self._set_animasi(False)

    def _get_teks(self):
        return self._teks_sorot

    def set_teks_sorot(self, teks: str):
        if teks != self._teks_sorot:
            self._teks_sorot = teks
            self.teksSorotChanged.emit()

    pusat = Property(QVector3D, _get_pusat, _set_pusat, notify=pusatChanged)
    rotasi = Property(QVector3D, _get_rotasi, _set_rotasi, notify=rotasiChanged)
    jarak = Property(float, _get_jarak, _set_jarak, notify=jarakChanged)
    animasi = Property(bool, _get_animasi, _set_animasi, notify=animasiChanged)
    teksSorot = Property(str, _get_teks, notify=teksSorotChanged)
    warnaLatar = Property(QColor, lambda s: s._warna["latar"], notify=warnaChanged)
    warnaLabel = Property(QColor, lambda s: s._warna["label"], notify=warnaChanged)
    warnaGaris = Property(QColor, lambda s: s._warna["garis"], notify=warnaChanged)
    warnaTeks = Property(QColor, lambda s: s._warna["teks"], notify=warnaChanged)
    fov = Property(float, lambda s: s.FOV, constant=True)

    # --- dipanggil QML
    @Slot(str)
    def pilih(self, gid: str):
        self.dipilih.emit(gid)

    @Slot(str)
    def sorot(self, gid: str):
        if gid != self._sorot:
            self._sorot = gid
            self.disorot.emit(gid)

    @Slot(str)
    def fokus(self, gid: str):
        self.fokus_diminta.emit(gid)

    @Slot(float)
    def zoom(self, delta: float):
        self._set_animasi(False)
        self._set_jarak(self._jarak * 0.86 ** (delta / 120.0))

    # --- dipakai Python
    def kamera(self, pusat=None, rotasi=None, jarak=None, animasi: bool = True):
        """Pindahkan kamera; dengan animasi, yaw dipilih yang terdekat agar tidak berputar lebih dari setengah putaran."""
        if rotasi is not None:
            yaw = rotasi.y()
            yaw += 360.0 * round((self._rotasi.y() - yaw) / 360.0)
            rotasi = QVector3D(rotasi.x(), yaw, 0)
        self._set_animasi(animasi)
        if animasi:
            self._henti.start()
        if pusat is not None and pusat != self._pusat:
            self._pusat = QVector3D(pusat)
            self.pusatChanged.emit()
        if rotasi is not None and rotasi != self._rotasi:
            self._rotasi = rotasi
            self.rotasiChanged.emit()
        if jarak is not None:
            self._set_jarak(jarak)

    def jarak_muat(self, radius: float) -> float:
        """Jarak kamera agar bola berjari-jari `radius` mengisi tinggi tampilan."""
        return max(radius, 0.3) / math.sin(math.radians(self.FOV) / 2) * 0.92


# ---------------------------------------------------------------- legenda di atas tampilan 3D

class Legenda(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("legenda3d")
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        latar = QColor(tema.W["permukaan"])
        self.setStyleSheet(
            f"QFrame#legenda3d {{ background-color: rgba({latar.red()},{latar.green()},{latar.blue()},225);"
            f" border: 1px solid {tema.W['garis']}; border-radius: 10px; }}"
            f" QLabel {{ background: transparent; font-size: 11px; color: {tema.W['teks_redup']}; }}"
        )
        self._mode = WARNA_JENIS_MODE
        self._entri = []
        self._skala = ("", "", "")
        self._kolom, self._lebar_kolom = 1, 160

    def atur_jenis(self, kelas_ada: list, ada_lain: bool):
        self._mode = WARNA_JENIS_MODE
        self._entri = [(WARNA_JENIS[k], LABEL[ElementType(k)]) for k in URUT_LEGENDA if k in kelas_ada]
        if ada_lain:
            self._entri.append((WARNA_LAIN, "Tidak dihitung di RAB"))
        self._entri += [(WARNA_PILIH, "Elemen dipilih"), (WARNA_TERKAIT, "Ikut dihitung")]
        self._ukur()

    def atur_biaya(self, rendah: str, tengah: str, tinggi: str):
        self._mode = WARNA_BIAYA_MODE
        self._skala = (rendah, tengah, tinggi)
        self._entri = [(WARNA_LAIN, "Tidak dihitung di RAB"), (WARNA_PILIH, "Elemen dipilih"),
                       (WARNA_TERKAIT, "Ikut dihitung")]
        self._ukur()

    def _ukur(self):
        fm = self.fontMetrics()
        self._kolom = 2 if len(self._entri) > 8 else 1
        self._lebar_kolom = max([fm.horizontalAdvance(t) for _w, t in self._entri] + [80]) + 34
        baris = math.ceil(len(self._entri) / self._kolom)
        lebar = 12 + self._lebar_kolom * self._kolom
        tinggi = 32 + 19 * baris + (52 if self._mode == WARNA_BIAYA_MODE else 0)
        self.setFixedSize(max(lebar, 200 if self._mode == WARNA_BIAYA_MODE else 170), tinggi)
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        f = p.font()
        f.setPixelSize(11)
        f.setBold(True)
        p.setFont(f)
        p.setPen(QColor(tema.W["teks"]))
        p.drawText(12, 20, "Warna menurut jenis" if self._mode == WARNA_JENIS_MODE else "Warna menurut biaya elemen")
        f.setBold(False)
        p.setFont(f)
        y = 30
        if self._mode == WARNA_BIAYA_MODE:
            g = QLinearGradient(12, 0, self.width() - 12, 0)
            for i, w in enumerate(SKALA_BIAYA):
                g.setColorAt(i / (len(SKALA_BIAYA) - 1), QColor(w))
            p.setPen(Qt.NoPen)
            p.setBrush(g)
            p.drawRoundedRect(12, y + 2, self.width() - 24, 10, 4, 4)
            p.setPen(QColor(tema.W["teks_redup"]))
            rendah, tengah, tinggi = self._skala
            p.drawText(12, y + 28, rendah)
            p.drawText(self.width() - 12 - p.fontMetrics().horizontalAdvance(tinggi), y + 28, tinggi)
            p.setPen(QColor(tema.W["teks_samar"]))
            p.drawText(12, y + 43, f"median {tengah}")
            y += 52
        baris = math.ceil(len(self._entri) / self._kolom)
        for i, (warna, teks) in enumerate(self._entri):
            x = 12 + (i // baris) * self._lebar_kolom
            yy = y + (i % baris) * 19
            p.setPen(QPen(QColor(0, 0, 0, 60), 1))
            p.setBrush(QColor(warna))
            p.drawRoundedRect(x, yy + 3, 12, 12, 3, 3)
            p.setPen(QColor(tema.W["teks_redup"]))
            p.drawText(x + 20, yy + 13, teks)
        p.end()


# ---------------------------------------------------------------- panel kebutuhan biaya

class _Baris(QFrame):
    """Satu item pekerjaan: nama, volume × harga satuan, jumlah."""

    def __init__(self, b: dict, asal: str = "", parent=None):
        super().__init__(parent)
        self.setObjectName("baris3d")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(10, 7, 10, 7)
        lay.setSpacing(10)
        kiri = QVBoxLayout()
        kiri.setSpacing(1)
        nama = b["nama"] + (f" — {b['uraian']}" if b.get("uraian") and b.get("diameter") else "")
        l_nama = tema.label(nama, wrap=True)
        l_nama.setStyleSheet(f"color: {tema.W['teks']}; font-size: 12px;")
        kiri.addWidget(l_nama)
        rinci = f"{tema.format_angka(b['volume'], 3)} {b['satuan']} × {tema.format_rupiah(b['harga'])}"
        tanda = []
        if b.get("diedit_manual"):
            tanda.append("volume diedit")
        if b.get("harga_manual") is not None:
            tanda.append("harga khusus")
        if asal:
            rinci += f"  ·  {asal}"
        l_rinci = tema.label(rinci + (f"  ·  {', '.join(tanda)}" if tanda else ""), "petunjuk", wrap=True)
        kiri.addWidget(l_rinci)
        lay.addLayout(kiri, stretch=1)
        l_jumlah = tema.label(tema.format_rupiah(b["jumlah"]))
        l_jumlah.setStyleSheet(f"color: {tema.W['teks_kuat']}; font-weight: 700; font-size: 12px;")
        l_jumlah.setAlignment(Qt.AlignRight | Qt.AlignTop)
        lay.addWidget(l_jumlah, alignment=Qt.AlignTop)
        tip = [f"<b>{nama}</b>", f"Kode: {b['kode']}"]
        if b.get("rumus"):
            tip.append(f"Rumus: {b['rumus']}")
        tip.append(f"{tema.format_angka(b['volume'], 3)} {b['satuan']} × {tema.format_rupiah(b['harga'])} "
                   f"= {tema.format_rupiah(b['jumlah'])}")
        self.setToolTip("<br>".join(tip))


class PanelBiaya3D(QFrame):
    """Panel kanan penampil 3D: kondisi kosong, atau rincian kebutuhan biaya elemen terpilih."""

    minta_bahan = Signal(int, str, str, str)  # elemen_id, slot, kunci, nama elemen
    minta_bahan_lengkap = Signal(int, str)  # elemen_id, nama elemen
    minta_tabel = Signal(str)  # nama elemen
    minta_fokus = Signal()
    terkait_diubah = Signal(bool)

    PER_TAHAP, PER_BAGIAN = 0, 1

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("panel")
        self.setMinimumWidth(380)
        self._data = None
        self._opsi = {}
        self._mode = self.PER_TAHAP
        self.setStyleSheet(
            f"QFrame#baris3d {{ background: transparent; border-radius: 8px; }}"
            f" QFrame#baris3d:hover {{ background-color: {tema.W['permukaan_2']}; }}"
            f" QFrame#seksi3d {{ background-color: {tema.W['permukaan_2']}; border: 1px solid {tema.W['garis']};"
            f" border-radius: 10px; }}"
        )
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        self.stack = QStackedWidget()
        lay.addWidget(self.stack, stretch=1)

        # halaman 0: belum ada yang dipilih
        kosong = QWidget()
        lk = QVBoxLayout(kosong)
        lk.setContentsMargins(28, 28, 28, 28)
        lk.addStretch(2)
        lk.addWidget(tema.IkonKosong("kubus"), alignment=Qt.AlignHCenter)
        lk.addSpacing(10)
        j = tema.label("Klik elemen pada model", "judulDialog")
        j.setAlignment(Qt.AlignHCenter)
        lk.addWidget(j)
        d = tema.label("Kebutuhan biaya elemen yang diklik akan muncul di sini, lengkap dengan urutan pekerjaannya "
                       "dan pilihan bahannya.", "subjudul", wrap=True)
        d.setAlignment(Qt.AlignHCenter)
        lk.addWidget(d)
        lk.addSpacing(18)
        for kunci, isi in (("Klik", "pilih elemen (kolom, balok, dinding, fondasi, ...)"),
                           ("Dobel klik", "dekatkan kamera ke elemen"),
                           ("Seret kiri", "putar model"),
                           ("Seret kanan", "geser model"),
                           ("Roda mouse", "perbesar / perkecil"),
                           ("Esc", "batal pilih")):
            baris = QHBoxLayout()
            k = tema.chip(kunci, "netral")
            k.setFixedWidth(96)
            k.setAlignment(Qt.AlignCenter)
            baris.addWidget(k)
            baris.addWidget(tema.label(isi, "subjudul", wrap=True), stretch=1)
            lk.addLayout(baris)
        lk.addStretch(3)
        self.stack.addWidget(kosong)

        # halaman 1: rincian
        isi = QWidget()
        li = QVBoxLayout(isi)
        li.setContentsMargins(0, 0, 0, 0)
        li.setSpacing(0)
        self.gulir = QScrollArea()
        self.gulir.setWidgetResizable(True)
        self.gulir.setFrameShape(QFrame.NoFrame)
        self.gulir.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.konten = QWidget()
        self.lay_konten = QVBoxLayout(self.konten)
        self.lay_konten.setContentsMargins(20, 18, 16, 14)
        self.lay_konten.setSpacing(10)
        self.gulir.setWidget(self.konten)
        li.addWidget(self.gulir, stretch=1)
        bawah = QFrame()
        bawah.setStyleSheet(f"QFrame {{ border-top: 1px solid {tema.W['garis']}; background: transparent; }}")
        lb = QHBoxLayout(bawah)
        lb.setContentsMargins(14, 10, 14, 12)
        lb.setSpacing(8)
        self.btn_fokus = tema.tombol("Fokus", "ghost", "cari", "Dekatkan kamera ke elemen ini (dobel klik)")
        self.btn_fokus.clicked.connect(self.minta_fokus.emit)
        self.btn_tabel = tema.tombol("Lihat di Tabel RAB", "secondary", None,
                                     "Buka tabel RAB mode Per Elemen dengan pencarian nama elemen ini")
        self.btn_tabel.clicked.connect(lambda: self._data and self.minta_tabel.emit(self._data["utama"]["judul"]))
        self.btn_bahan = tema.tombol("Ganti Bahan…", "secondary", None,
                                     "Semua pilihan bahan elemen ini beserta kebutuhan bahannya")
        self.btn_bahan.clicked.connect(
            lambda: self._data and self.minta_bahan_lengkap.emit(self._data["utama"]["elemen_id"],
                                                                 self._data["utama"]["judul"]))
        lb.addWidget(self.btn_fokus)
        lb.addStretch()
        lb.addWidget(self.btn_tabel)
        lb.addWidget(self.btn_bahan)
        li.addWidget(bawah)
        self.stack.addWidget(isi)
        self.bawah = bawah

    # ------------------------------------------------------------ isi

    def kosong(self):
        self._data = None
        self.stack.setCurrentIndex(0)

    def _mulai(self):
        tema.kosongkan_layout(self.lay_konten)
        self.stack.setCurrentIndex(1)

    def tidak_dihitung(self, judul: str, label: str, lantai: str | None, alasan: str):
        """Elemen yang ada di model tetapi tidak menghasilkan item RAB."""
        self._data = None
        self._mulai()
        self._kepala(label, lantai, judul, "")
        kartu = tema.KartuStat("Kebutuhan biaya")
        kartu.set_data("Tidak dihitung", "")
        self.lay_konten.addWidget(kartu)
        self.lay_konten.addWidget(tema.label(alasan, "subjudul", wrap=True))
        self.lay_konten.addStretch()
        for b in (self.btn_tabel, self.btn_bahan):
            b.hide()

    def tampilkan(self, data: dict, opsi_harga: dict, terkait_aktif: bool, pesan: str = ""):
        self._data = data
        self._opsi = opsi_harga
        self._terkait_aktif = terkait_aktif
        self._pesan = pesan
        self._gambar()

    def _gambar(self):
        data = self._data
        posisi = self.gulir.verticalScrollBar().value()
        self._mulai()
        u = data["utama"]
        self._kepala(u["label_kelas"], u["lantai"], u["judul"], u["dimensi"])

        kartu = tema.KartuStat("Kebutuhan biaya", utama=True)
        per_peran = {}
        for b in data["bagian"]:
            k = PERAN_RINGKAS.get(b["peran"], b["peran"])
            per_peran[k] = per_peran.get(k, 0.0) + b["total"]
        ket = "  ·  ".join(f"{k} {rupiah_ringkas(v)}" for k, v in per_peran.items()) if len(per_peran) > 1 else (
            f"{sum(len(b['baris']) for b in data['bagian'])} item pekerjaan")
        kartu.set_data(tema.format_rupiah(data["total"]), ket)
        kartu._ket.setWordWrap(True)
        self.lay_konten.addWidget(kartu)

        if data["ada_terkait"]:
            # kotak centang + label yang dapat membungkus baris (teks QCheckBox tidak bisa dibungkus)
            baris = QHBoxLayout()
            baris.setSpacing(8)
            cb = QCheckBox()
            cb.setChecked(self._terkait_aktif)
            tip = "Bagian yang ikut dihitung diberi warna hijau di model 3D. Matikan untuk melihat biaya elemen ini saja."
            cb.setToolTip(tip)
            # panel dibangun ulang setelah sinyal widget ini selesai (widget pengirim ikut dihapus)
            cb.toggled.connect(lambda aktif: self._tunda(self.terkait_diubah.emit, aktif))
            teks = tema.label(self._teks_terkait(u["kelas"]), wrap=True)
            teks.setToolTip(tip)
            teks.setCursor(Qt.PointingHandCursor)
            teks.mousePressEvent = lambda _e, c=cb: c.toggle()
            baris.addWidget(cb, alignment=Qt.AlignTop)
            baris.addWidget(teks, stretch=1)
            self.lay_konten.addLayout(baris)
        if self._pesan:
            self.lay_konten.addWidget(tema.label(self._pesan, "petunjuk", wrap=True))

        if data["slot"]:
            self._seksi_bahan(u, data["slot"])

        if not any(b["baris"] for b in data["bagian"]):
            self.lay_konten.addWidget(tema.label("Elemen ini tidak menghasilkan item pekerjaan.", "subjudul", wrap=True))
        else:
            self._pilihan_mode()
            if self._mode == self.PER_TAHAP:
                self._isi_per_tahap(data)
            else:
                self._isi_per_bagian(data)
        self.lay_konten.addStretch()
        self.btn_tabel.show()
        self.btn_bahan.setVisible(bool(data["slot"]))
        QTimer.singleShot(0, lambda: self.gulir.verticalScrollBar().setValue(posisi))

    def _kepala(self, label_kelas: str, lantai: str | None, judul: str, dimensi: str):
        chips = QHBoxLayout()
        chips.setSpacing(6)
        chips.addWidget(tema.chip(label_kelas, "info"))
        if lantai:
            chips.addWidget(tema.chip(lantai, "netral"))
        chips.addStretch()
        self.lay_konten.addLayout(chips)
        j = tema.label(judul, "judulDialog", wrap=True)
        j.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.lay_konten.addWidget(j)
        if dimensi:
            self.lay_konten.addWidget(tema.label(dimensi, "subjudul", wrap=True))

    @staticmethod
    def _teks_terkait(kelas: str) -> str:
        if kelas == "COLUMN":
            return "Termasuk pedestal, fondasi & pekerjaan tanah di bawahnya"
        if kelas == "WALL":
            return "Termasuk sloof, fondasi menerus & pekerjaan tanah di bawahnya"
        if kelas in ("FOOTING", "PILE"):
            return "Termasuk fondasi lain & pekerjaan tanah di titik ini"
        return "Termasuk elemen di bawahnya"

    def _judul_seksi(self, teks: str, kanan: str = ""):
        baris = QHBoxLayout()
        baris.setContentsMargins(0, 8, 0, 0)
        l = tema.label(teks.upper())
        l.setStyleSheet(f"color: {tema.W['teks_samar']}; font-size: 11px; font-weight: 800; letter-spacing: 0.6px;")
        baris.addWidget(l, stretch=1)
        if kanan:
            r = tema.label(kanan)
            r.setStyleSheet(f"color: {tema.W['teks_redup']}; font-size: 11px; font-weight: 700;")
            baris.addWidget(r)
        self.lay_konten.addLayout(baris)

    def _seksi_bahan(self, u: dict, slot: dict):
        self._judul_seksi("Pilihan bahan elemen ini")
        for kode, s in slot.items():
            info = SLOT[kode]
            kartu = QFrame()
            kartu.setObjectName("seksi3d")
            lk = QVBoxLayout(kartu)
            lk.setContentsMargins(12, 10, 12, 10)
            lk.setSpacing(6)
            atas = QHBoxLayout()
            atas.addWidget(tema.label(f"<b>{info.judul}</b>"), stretch=1)
            atas.addWidget(tema.chip("khusus elemen ini" if s["khusus"] else "ikut pilihan proyek",
                                     "info" if s["khusus"] else "netral"))
            lk.addLayout(atas)
            cb = QComboBox()
            cb.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
            cb.setMinimumContentsLength(12)  # teks pilihan panjang tidak melebarkan panel
            cb.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
            cb.view().setMinimumWidth(460)
            cb.setFocusPolicy(Qt.StrongFocus)
            cb.wheelEvent = lambda e: e.ignore()  # roda mouse menggulir panel, bukan mengganti bahan
            kini = self._biaya_opsi(kode, s["kunci"], s["volume"])
            for o in info.opsi:
                biaya = self._biaya_opsi(kode, o.kunci, s["volume"])
                teks = o.label
                if biaya is not None:
                    teks += f"  —  {tema.format_rupiah(biaya)}"
                    if o.kunci != s["kunci"] and kini is not None and abs(biaya - kini) >= 1:
                        teks += f"  ({'+' if biaya > kini else '−'}{rupiah_ringkas(abs(biaya - kini))})"
                cb.addItem(teks, o.kunci)
                cb.setItemData(cb.count() - 1, teks, Qt.ToolTipRole)
            cb.setCurrentIndex(max(0, cb.findData(s["kunci"])))
            cb.currentIndexChanged.connect(
                lambda _i, c=cb, k=kode: self._tunda(self.minta_bahan.emit, u["elemen_id"], k, c.currentData(),
                                                     u["judul"]))
            cb.setToolTip("Harga di setiap pilihan = volume elemen ini × harga satuan pilihan itu. Mengganti bahan "
                          "langsung menghitung ulang RAB dan dapat diurungkan (Ctrl+Z).")
            lk.addWidget(cb)
            harga = f"<b>{tema.format_rupiah(kini)}</b> untuk " if kini is not None else ""
            lk.addWidget(tema.label(f"{harga}{tema.format_angka(s['volume'], 2)} {s['satuan']} · hanya elemen ini, "
                                    "total RAB langsung diperbarui", "petunjuk", wrap=True))
            self.lay_konten.addWidget(kartu)

    @staticmethod
    def _tunda(fungsi, *args):
        """Jalankan setelah sinyal widget pengirim selesai: panel dibangun ulang dan widget itu ikut dihapus."""
        QTimer.singleShot(0, lambda: fungsi(*args))

    def _biaya_opsi(self, slot: str, kunci: str, volume: float):
        info = self._opsi.get(kode_varian(slot, kunci))
        return volume * info["harga"] if info else None

    def _pilihan_mode(self):
        baris = QHBoxLayout()
        baris.setContentsMargins(0, 8, 0, 0)
        baris.setSpacing(0)
        grup = QButtonGroup(self.konten)
        for i, (teks, posisi, tip) in enumerate((
            ("Urutan pekerjaan", "kiri", "Item dikelompokkan per tahap pekerjaan: tanah → fondasi → beton → dinding → "
             "finishing"),
            ("Per bagian", "kanan", "Item dikelompokkan per elemen: elemen ini, pedestal, fondasi, pekerjaan tanah"),
        )):
            b = QPushButton(teks)
            b.setObjectName("segmen")
            b.setProperty("posisi", posisi)
            b.setCheckable(True)
            b.setCursor(Qt.PointingHandCursor)
            b.setToolTip(tip)
            b.setChecked(i == self._mode)
            grup.addButton(b, i)
            baris.addWidget(b)
        baris.addStretch()
        grup.idClicked.connect(lambda i: self._tunda(self._ganti_mode, i))
        self.lay_konten.addLayout(baris)

    def _ganti_mode(self, i: int):
        if i != self._mode:
            self._mode = i
            self._gambar()

    def _isi_per_tahap(self, data: dict):
        banyak = len([b for b in data["bagian"] if b["baris"]]) > 1
        per_kat = {}
        for b in data["bagian"]:
            asal = b["judul"] if banyak else ""
            for r in b["baris"]:
                per_kat.setdefault(r["kategori"] or "Lainnya", []).append((r, asal))
        for no, kat in enumerate(sorted(per_kat, key=urutan_kategori), start=1):
            isi = per_kat[kat]
            self._judul_seksi(f"{no}. {NAMA_TAHAP.get(kat, 'Pekerjaan ' + kat)}",
                              tema.format_rupiah(sum(r["jumlah"] for r, _a in isi)))
            for r, asal in isi:
                self.lay_konten.addWidget(_Baris(r, asal))

    def _isi_per_bagian(self, data: dict):
        for b in data["bagian"]:
            if not b["baris"]:
                continue
            self._judul_seksi(PERAN_RINGKAS.get(b["peran"], b["peran"]), tema.format_rupiah(b["total"]))
            judul = tema.label(f"<b>{b['judul']}</b>" + (f"  ·  {b['dimensi']}" if b["dimensi"] else ""),
                               "subjudul", wrap=True)
            self.lay_konten.addWidget(judul)
            for r in b["baris"]:
                self.lay_konten.addWidget(_Baris(r))


# ---------------------------------------------------------------- jendela penampil

_CACHE = {}


def muat_model(path: str, progress=None):
    """Model3D dari cache (kunci: path + waktu ubah file); dibaca ulang bila file IFC berubah."""
    from model3d import muat_model3d

    p = Path(path)
    kunci = (str(p.resolve()), p.stat().st_mtime)
    if kunci not in _CACHE:
        model = muat_model3d(str(p), progress)
        _CACHE.clear()  # simpan satu model saja: model besar memakan memori
        _CACHE[kunci] = model
    return _CACHE[kunci]


def ada_di_cache(path: str) -> bool:
    try:
        p = Path(path)
        return (str(p.resolve()), p.stat().st_mtime) in _CACHE
    except OSError:
        return False


class Penampil3D(QDialog):
    """Jendela Model 3D: tampilan 3D (kiri) + panel kebutuhan biaya (kanan).

    `halaman` (opsional) = halaman estimasi pemilik jendela, untuk menyimpan perubahan bahan dengan riwayat urungkan
    (`terapkan_perubahan`), membuka tabel RAB (`lihat_elemen`), dan Ctrl+Z (`riwayat`)."""

    def __init__(self, proyek_id: int, nama_proyek: str, model, halaman=None, parent=None):
        super().__init__(parent)
        self.proyek_id = proyek_id
        self.model3d = model
        self.halaman = halaman
        self.setWindowTitle(f"Model 3D — {nama_proyek}")
        self.setWindowFlags(Qt.Window | Qt.WindowMinMaxButtonsHint | Qt.WindowCloseButtonHint)
        self.setWindowIcon(tema.ikon_aplikasi())
        self.setAttribute(Qt.WA_QuitOnClose, False)  # menutup jendela utama tetap menutup aplikasi
        self.resize(1380, 860)
        self.setMinimumSize(980, 600)

        self._e3d = model.per_gid()
        self._kotak = {g: e.kotak for g, e in self._e3d.items()}
        self._peta = {}
        self._peringkat = {}
        self._pilih = ""
        self._sorot = ""
        self._terkait = set()
        self._termasuk_terkait = True
        self._opsi = None

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 16, 20, 16)
        root.setSpacing(12)
        kepala, _j, self.label_sub = tema.kepala_dialog(
            "Model 3D Bangunan", "Klik elemen untuk melihat kebutuhan biayanya.", "kubus")
        root.addWidget(kepala)

        # --- baris alat
        alat = QHBoxLayout()
        alat.setSpacing(10)
        self.cari = QLineEdit()
        tema.pasang_ikon_cari(self.cari)
        self.cari.setPlaceholderText("Cari elemen, mis. K1, dinding, fondasi...")
        self.cari.setClearButtonEnabled(True)
        self.cari.setMinimumWidth(260)
        self.cari.returnPressed.connect(self._cari_enter)
        alat.addWidget(self.cari, stretch=2)
        self.combo_lantai = QComboBox()
        self.combo_lantai.setToolTip("Sembunyikan lantai di atasnya untuk melihat isi bangunan")
        self.combo_lantai.addItem("Semua lantai", None)
        for nama, elev in model.lantai:
            self.combo_lantai.addItem(f"s.d. {nama}", elev)
        self.combo_lantai.currentIndexChanged.connect(lambda _i: self._warnai())
        alat.addWidget(self.combo_lantai)
        self.combo_tampil = QComboBox()
        self.combo_tampil.addItem("Tampilan lengkap", TAMPIL_LENGKAP)
        self.combo_tampil.addItem("Arsitektur tembus pandang", TAMPIL_TEMBUS)
        self.combo_tampil.addItem("Struktur saja", TAMPIL_STRUKTUR)
        self.combo_tampil.setToolTip("Tembus pandang: dinding, atap, pintu, jendela dibuat transparan dan klik "
                                     "menembus ke kolom/balok di baliknya.")
        self.combo_tampil.currentIndexChanged.connect(lambda _i: self._warnai())
        alat.addWidget(self.combo_tampil)
        warna = QHBoxLayout()
        warna.setSpacing(0)
        self.grup_warna = QButtonGroup(self)
        for i, (teks, posisi, tip) in enumerate((
            ("Warna jenis", "kiri", "Warna menurut jenis elemen"),
            ("Warna biaya", "kanan", "Biru = elemen murah, merah = elemen mahal"),
        )):
            b = QPushButton(teks)
            b.setObjectName("segmen")
            b.setProperty("posisi", posisi)
            b.setCheckable(True)
            b.setCursor(Qt.PointingHandCursor)
            b.setToolTip(tip)
            self.grup_warna.addButton(b, i)
            warna.addWidget(b)
        self.grup_warna.button(WARNA_JENIS_MODE).setChecked(True)
        self.grup_warna.idClicked.connect(lambda _i: self._warnai())
        alat.addLayout(warna)
        self.cb_lain = QCheckBox("Elemen tak dihitung")
        self.cb_lain.setChecked(True)
        self.cb_lain.setToolTip("Tampilkan elemen model yang tidak menghasilkan item RAB (abu-abu)")
        self.cb_lain.toggled.connect(lambda _b: self._warnai())
        alat.addWidget(self.cb_lain)
        alat.addStretch(1)
        root.addLayout(alat)

        # --- tampilan 3D + panel
        self.splitter = QSplitter(Qt.Horizontal)
        self.splitter.setChildrenCollapsible(False)
        self.backend = Backend(self)
        self.adegan = AdeganModel(self)
        self.adegan.atur([(e.gid, Geometri3D(e.posisi, e.normal)) for e in model.elemen])
        self.quick = QQuickWidget()
        self.quick.setResizeMode(QQuickWidget.SizeRootObjectToView)
        self.quick.setMinimumWidth(520)
        # backend & adegan anak QQuickWidget: dihapus setelah mesin QML, bukan sebelumnya
        self.backend.setParent(self.quick)
        self.adegan.setParent(self.quick)
        self.quick.rootContext().setContextProperty("backend", self.backend)
        self.quick.rootContext().setContextProperty("adegan", self.adegan)
        with tanpa_terjemahan_python():  # cegah macet: lihat gui/galat.py
            self.quick.setSource(QUrl.fromLocalFile(str(QML)))
        self.galat_qml = [e.toString() for e in self.quick.errors()]
        self.legenda = Legenda(self.quick)
        self.petunjuk = QLabel("Seret kiri: putar  ·  Seret kanan: geser  ·  Roda: zoom  ·  Dobel klik: fokus",
                               self.quick)
        latar = QColor(tema.W["permukaan"])
        self.petunjuk.setStyleSheet(
            f"background-color: rgba({latar.red()},{latar.green()},{latar.blue()},210); color: {tema.W['teks_redup']};"
            f" border: 1px solid {tema.W['garis']}; border-radius: 9px; padding: 5px 10px; font-size: 11px;")
        self.petunjuk.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.petunjuk.adjustSize()
        self.pandang = QWidget(self.quick)
        lp = QHBoxLayout(self.pandang)
        lp.setContentsMargins(0, 0, 0, 0)
        lp.setSpacing(0)
        daftar = (("Iso", "Pandangan isometrik"), ("Atas", "Pandangan dari atas (denah)"),
                  ("Depan", "Pandangan depan"), ("Samping", "Pandangan samping kanan"),
                  ("Pas", "Tampilkan seluruh bangunan tanpa mengubah arah pandang"))
        for i, (teks, tip) in enumerate(daftar):
            b = QPushButton(teks)
            b.setObjectName("segmen")
            b.setProperty("posisi", "kiri" if i == 0 else "kanan" if i == len(daftar) - 1 else "tengah")
            b.setCursor(Qt.PointingHandCursor)
            b.setToolTip(tip)
            b.setMinimumWidth(64 if teks != "Samping" else 84)
            b.clicked.connect(lambda _c=False, t=teks: self.pandangan(t))
            lp.addWidget(b)
        self.pandang.adjustSize()
        self.quick.installEventFilter(self)
        self.splitter.addWidget(self.quick)
        self.panel = PanelBiaya3D()
        self.panel.minta_bahan.connect(self._ganti_bahan)
        self.panel.minta_bahan_lengkap.connect(self._bahan_lengkap)
        self.panel.minta_tabel.connect(self._lihat_tabel)
        self.panel.minta_fokus.connect(lambda: self._pilih and self.fokus(self._pilih))
        self.panel.terkait_diubah.connect(self._atur_terkait)
        self.splitter.addWidget(self.panel)
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 0)
        self.splitter.setSizes([920, 460])
        root.addWidget(self.splitter, stretch=1)

        self.toast = tema.Toast(self)
        self.backend.dipilih.connect(self.pilih)
        self.backend.disorot.connect(self._sorot_elemen)
        self.backend.fokus_diminta.connect(self.fokus)
        if halaman is not None and hasattr(halaman, "riwayat"):
            QShortcut(QKeySequence.Undo, self, activated=self.urungkan)
            QShortcut(QKeySequence("Ctrl+Y"), self, activated=self.ulangi)
            QShortcut(QKeySequence("Ctrl+Shift+Z"), self, activated=self.ulangi)
        QShortcut(QKeySequence("Ctrl+F"), self, activated=lambda: (self.cari.setFocus(), self.cari.selectAll()))

        self.segarkan()
        self._siapkan_cari()
        self.pandangan("Iso", animasi=False)

    # ------------------------------------------------------------ data

    def segarkan(self):
        """Baca ulang biaya dari database (dipanggil setelah RAB berubah) lalu perbarui warna dan panel."""
        self._peta = peta_biaya(self.proyek_id)
        self._peringkat = peringkat_biaya(self._peta)
        self._opsi = None
        n_hitung = sum(1 for g in self._e3d if g in self._peta and self._peta[g]["baris"])
        self.label_sub.setText(
            f"{len(self._e3d)} elemen di model, {n_hitung} menghasilkan item RAB. Klik elemen untuk melihat "
            "kebutuhan biayanya.")
        if self._pilih:
            self._isi_panel()
        self._warnai()

    def _opsi_harga(self) -> dict:
        if self._opsi is None:
            from database.material_repository import ringkasan_opsi

            self._opsi = ringkasan_opsi()
        return self._opsi

    def _siapkan_cari(self):
        entri = []
        self._teks_ke_gid = {}
        for e in sorted(self.model3d.elemen,
                        key=lambda e: (e.gid not in self._peta, e.elevasi if e.elevasi is not None else 1e9, e.nama)):
            info = self._peta.get(e.gid)
            teks = f"{(info or {}).get('nama') or e.nama}  ·  {label_kelas(info, e.ifc)}"
            if e.lantai:
                teks += f"  ·  {e.lantai}"
            if teks in self._teks_ke_gid:
                continue
            self._teks_ke_gid[teks] = e.gid
            entri.append(teks)
        komp = QCompleter(QStringListModel(entri, self), self)
        komp.setCaseSensitivity(Qt.CaseInsensitive)
        komp.setFilterMode(Qt.MatchContains)
        komp.setMaxVisibleItems(14)
        komp.activated[str].connect(self._cari_pilih)
        self.cari.setCompleter(komp)
        self._entri_cari = entri

    def _cari_pilih(self, teks: str):
        gid = self._teks_ke_gid.get(teks)
        if gid:
            self.pilih(gid)
            self.fokus(gid)

    def _cari_enter(self):
        kata = self.cari.text().strip().lower()
        if not kata:
            return
        if self.cari.text() in self._teks_ke_gid:
            self._cari_pilih(self.cari.text())
            return
        cocok = next((t for t in self._entri_cari if kata in t.lower()), None)
        if cocok:
            self._cari_pilih(cocok)
        else:
            self.toast.tampilkan(f'Elemen "{self.cari.text()}" tidak ditemukan', "peringatan")

    # ------------------------------------------------------------ pilih, sorot, warna

    @Slot(str)
    def pilih(self, gid: str):
        gid = gid if gid in self._e3d else ""
        self._pilih = gid
        if not gid:
            self._terkait = set()
            self.panel.kosong()
        else:
            self._isi_panel()
        self._warnai()

    def _isi_panel(self):
        gid = self._pilih
        e = self._e3d[gid]
        info = self._peta.get(gid)
        if info is None or not info["baris"]:
            self._terkait = set()
            self.panel.tidak_dihitung(
                (info or {}).get("nama") or e.nama, label_kelas(info, e.ifc), e.lantai, self._alasan(info, e))
            return
        data = rincian(self.proyek_id, gid, self._kotak, self._termasuk_terkait, self._peta)
        self._terkait = set(data["terkait"]) if self._termasuk_terkait else set()
        pesan = ""
        if info.get("kolom_grup") and (info.get("info_kolom") or {}).get("n", 1) > 1:
            pesan = ("Kolom ini tersusun dari beberapa objek IFC (mis. pedestal + kolom) dan dihitung sebagai satu "
                     "kolom fisik.")
        self.panel.tampilkan(data, self._opsi_harga(), self._termasuk_terkait, pesan)

    @staticmethod
    def _alasan(info, e) -> str:
        if info is None:
            return (f"{e.ifc.replace('Ifc', '')} ini ada di model tetapi tidak termasuk elemen yang dihitung aplikasi "
                    "(mis. perabot, aksesori, atau elemen bantu), sehingga tidak masuk RAB.")
        ik = info.get("info_kolom") or {}
        if ik.get("peran") == "duplikat":
            return (f"Objek ganda: menempati tempat yang sama dengan {ik.get('nama_duplikat') or 'kolom lain'}. "
                    "Biayanya sudah dihitung pada kolom itu, jadi tidak dihitung dua kali.")
        return ("Elemen ini dikenali tetapi tidak menghasilkan item pekerjaan, misalnya karena pekerjaannya sudah "
                "diwakili elemen lain atau digantikan pilihan jenis fondasi.")

    def _atur_terkait(self, aktif: bool):
        self._termasuk_terkait = aktif
        if self._pilih:
            self._isi_panel()
            self._warnai()

    def _sorot_elemen(self, gid: str):
        lama = self._sorot
        self._sorot = gid if gid in self._e3d else ""
        if self._sorot:
            e = self._e3d[self._sorot]
            info = self._peta.get(self._sorot)
            nama = (info or {}).get("nama") or e.nama
            bagian = [label_kelas(info, e.ifc)] + ([e.lantai] if e.lantai else [])
            biaya = tema.format_rupiah(info["total"]) if info and info["baris"] else "tidak dihitung di RAB"
            self.backend.set_teks_sorot(f"<b>{_html(nama)}</b><br>{_html(' · '.join(bagian))}<br>{biaya}")
        else:
            self.backend.set_teks_sorot("")
        self._warnai({lama, self._sorot} - {""})

    def _keadaan(self, gid: str) -> dict:
        e = self._e3d[gid]
        info = self._peta.get(gid)
        kelas = kelas_tampil(info, e.ifc)
        dihitung = bool(info and info["baris"])
        tampil_mode = self.combo_tampil.currentData()
        batas = self.combo_lantai.currentData()
        tampil = True
        if batas is not None and e.elevasi is not None and e.elevasi > batas + 0.01:
            tampil = False
        if tampil_mode == TAMPIL_STRUKTUR and kelas not in STRUKTUR:
            tampil = False
        if not dihitung and not self.cb_lain.isChecked():
            tampil = False
        buram, klik, sinar = 1.0, True, 0.0
        if gid == self._pilih:
            warna, sinar = QColor(WARNA_PILIH), 0.30
        elif gid in self._terkait:
            warna, sinar = QColor(WARNA_TERKAIT), 0.18
        else:
            if not dihitung:
                warna = QColor(WARNA_LAIN)
            elif self.grup_warna.checkedId() == WARNA_BIAYA_MODE:
                warna = warna_skala(self._peringkat.get(gid, 0.0))
            else:
                warna = QColor(WARNA_JENIS.get(kelas, WARNA_LAIN))
            if kelas == "WINDOW":
                buram = 0.55
            if tampil_mode == TAMPIL_TEMBUS and kelas not in STRUKTUR:
                buram, klik = 0.12, False
            if gid == self._sorot and klik:
                warna = warna.lighter(128)
        return {"warna": warna, "buram": buram, "tampil": tampil, "klik": tampil and klik, "sinar": sinar}

    def _warnai(self, gids=None):
        """Hitung ulang warna/visibilitas semua elemen (gids=None) atau sebagian (mis. dua elemen saat sorot)."""
        semua = gids is None
        self.adegan.perbarui({g: self._keadaan(g) for g in (self._e3d if semua else gids) if g in self._e3d})
        if semua:
            self._perbarui_legenda()

    def _perbarui_legenda(self):
        if self.grup_warna.checkedId() == WARNA_BIAYA_MODE:
            nilai = sorted(x["total"] for g, x in self._peta.items() if x["total"] > 0 and g in self._e3d)
            if nilai:
                self.legenda.atur_biaya(rupiah_ringkas(nilai[0]), rupiah_ringkas(nilai[len(nilai) // 2]),
                                        rupiah_ringkas(nilai[-1]))
            else:
                self.legenda.atur_biaya("-", "-", "-")
        else:
            kelas = {kelas_tampil(self._peta.get(g), e.ifc) for g, e in self._e3d.items()
                     if g in self._peta and self._peta[g]["baris"]}
            lain = any(not (g in self._peta and self._peta[g]["baris"]) for g in self._e3d)
            self.legenda.atur_jenis(sorted(kelas), lain)
        self._posisikan_overlay()

    # ------------------------------------------------------------ kamera

    def pandangan(self, nama: str, animasi: bool = True):
        mn, mx = self.model3d.batas()
        pusat = QVector3D(*map(float, (mn + mx) / 2))
        radius = float(np.linalg.norm(mx - mn) / 2)
        rot = {"Iso": (-28, -35), "Atas": (-89.5, 0), "Depan": (-6, 0), "Samping": (-6, 90)}.get(nama)
        if rot is None:  # "Pas": arah pandang tetap, seluruh bangunan masuk layar
            self.backend.kamera(pusat, None, self.backend.jarak_muat(radius), animasi)
        else:
            self.backend.kamera(pusat, QVector3D(rot[0], rot[1], 0), self.backend.jarak_muat(radius), animasi)

    @Slot(str)
    def fokus(self, gid: str):
        e = self._e3d.get(gid)
        if e is None:
            return
        if gid != self._pilih:
            self.pilih(gid)
        mn, mx = e.batas()
        radius = float(np.linalg.norm(mx - mn) / 2)
        self.backend.kamera(QVector3D(*map(float, (mn + mx) / 2)), None,
                            max(self.backend.jarak_muat(radius) * 1.8, 3.0), True)

    # ------------------------------------------------------------ perubahan bahan

    def _terapkan(self, aksi, keterangan: str, ringkas: str):
        """Jalankan perubahan lewat halaman estimasi (riwayat urungkan + muat ulang tabel); tanpa halaman, langsung."""
        lewat_halaman = self.halaman is not None and hasattr(self.halaman, "terapkan_perubahan")
        try:
            # halaman.muat() memanggil segarkan() jendela ini; tanpa halaman, segarkan sendiri
            pesan = self.halaman.terapkan_perubahan(aksi, keterangan, ringkas) if lewat_halaman else (
                ringkas if aksi() else None)
        except ValueError as e:
            self.toast.tampilkan(str(e), "peringatan")
            self.segarkan()
            return
        if pesan:
            if not lewat_halaman:
                self.segarkan()
            self.toast.tampilkan(pesan)

    def _ganti_bahan(self, elemen_id: int, slot: str, kunci: str, nama: str):
        from database.material_repository import simpan_material_elemen

        label = SLOT[slot].cari(kunci).label

        def aksi():
            simpan_material_elemen(elemen_id, {slot: kunci})
            return True

        self._terapkan(aksi, f"Ganti bahan {nama}: {label}".strip(), f"{SLOT[slot].judul} {nama} → {label}")

    def _bahan_lengkap(self, elemen_id: int, nama: str):
        from gui.material_dialog import MaterialElemenDialog

        def aksi():
            dialog = MaterialElemenDialog(elemen_id, nama, self)
            ok = dialog.exec() == QDialog.Accepted and dialog.diubah
            dialog.deleteLater()
            return ok

        self._terapkan(aksi, f"Ganti bahan elemen {nama}".strip(), f"Bahan {nama} diganti")

    def urungkan(self):
        r = self.halaman.riwayat
        if r.canUndo():
            teks = r.undoText()
            r.undo()  # halaman memuat ulang RAB lalu memanggil segarkan()
            self.toast.tampilkan(f"Diurungkan: {teks}")

    def ulangi(self):
        r = self.halaman.riwayat
        if r.canRedo():
            teks = r.redoText()
            r.redo()
            self.toast.tampilkan(f"Diulangi: {teks}")

    def _lihat_tabel(self, nama: str):
        if self.halaman is not None and hasattr(self.halaman, "lihat_elemen"):
            self.halaman.lihat_elemen(nama)

    # ------------------------------------------------------------ Qt

    def eventFilter(self, obj, event):  # noqa: N802
        if obj is self.quick and event.type() == event.Type.Resize:
            self._posisikan_overlay()
        return super().eventFilter(obj, event)

    def _posisikan_overlay(self):
        h = self.quick.height()
        self.legenda.move(14, max(h - self.legenda.height() - 14, 8))
        self.petunjuk.move(max(self.quick.width() - self.petunjuk.width() - 14, 8), max(h - self.petunjuk.height() - 14, 8))
        self.pandang.move(max(self.quick.width() - self.pandang.width() - 14, 8), 14)
        self.legenda.raise_()
        self.petunjuk.raise_()
        self.pandang.raise_()

    def render_3d_aktif(self) -> bool | None:
        """True bila Qt Quick memakai API grafis 3D (Direct3D / OpenGL / Vulkan / Metal); False bila memakai
        perender perangkat lunak 2D (View3D tidak menggambar apa pun); None bila jendela belum siap."""
        jendela = self.quick.quickWindow()
        ri = jendela.rendererInterface() if jendela is not None else None
        if ri is None:
            return None
        return QSGRendererInterface.isApiRhiBased(ri.graphicsApi())

    def showEvent(self, event):
        super().showEvent(event)
        QTimer.singleShot(400, self._cek_render)

    def _cek_render(self):
        if self.render_3d_aktif() is not False or getattr(self, "_label_galat", None) is not None:
            return
        self._label_galat = tema.label(
            "<b>Tampilan 3D tidak dapat digambar di komputer ini.</b><br>Driver kartu grafis tidak menyediakan "
            "Direct3D 11 / OpenGL 3.3. Perbarui driver grafis, atau cari elemen lewat kotak pencarian: "
            "kebutuhan biayanya tetap tampil di panel kanan.", wrap=True)
        self._label_galat.setParent(self.quick)
        self._label_galat.setStyleSheet(
            f"background-color: {tema.W['peringatan_lembut']}; color: {tema.W['teks']}; border: 1px solid "
            f"{tema.W['peringatan_garis']}; border-radius: 10px; padding: 14px;")
        self._label_galat.setFixedWidth(min(520, self.quick.width() - 40))
        self._label_galat.adjustSize()
        self._label_galat.move((self.quick.width() - self._label_galat.width()) // 2, 70)
        self._label_galat.show()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape and self._pilih:
            self.pilih("")
            return
        super().keyPressEvent(event)


def _html(teks: str) -> str:
    return (teks or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def buka_penampil(halaman, proyek_id: int, nama_proyek: str, path_ifc: str | None):
    """Siapkan model 3D (di latar, dengan progres) lalu kembalikan jendela Penampil3D, atau None bila gagal."""
    from gui.proses_latar import jalankan_di_latar

    ok, galat = tersedia()
    if not ok:
        QMessageBox.warning(halaman, "Model 3D", f"Penampil 3D tidak dapat dibuka di komputer ini.\n\n{galat}")
        return None
    if not path_ifc or not Path(path_ifc).is_file():
        QMessageBox.warning(
            halaman, "Model 3D",
            "File IFC proyek ini tidak ditemukan"
            + (f":\n{path_ifc}" if path_ifc else ".")
            + "\n\nPenampil 3D membaca bentuk bangunan dari file IFC asli. Pindahkan file ke lokasi semula atau "
              "jalankan Hitung Ulang dari File IFC.")
        return None
    try:
        if ada_di_cache(path_ifc):
            model = muat_model(path_ifc)
        else:
            model = jalankan_di_latar(halaman, "Menyiapkan model 3D bangunan...", muat_model, path_ifc,
                                      pakai_progress=True)
    except Exception as e:  # file rusak / geometri tidak terbaca
        QMessageBox.warning(halaman, "Model 3D", f"Bentuk 3D bangunan tidak dapat dibaca dari file IFC.\n\n{e}")
        return None
    if not model.elemen:
        QMessageBox.information(halaman, "Model 3D", "File IFC ini tidak berisi geometri elemen bangunan.")
        return None
    jendela = Penampil3D(proyek_id, nama_proyek, model, halaman)
    if jendela.galat_qml:
        QMessageBox.warning(halaman, "Model 3D", "Tampilan 3D gagal disiapkan:\n\n" + "\n".join(jendela.galat_qml[:5]))
        jendela.deleteLater()
        return None
    return jendela
