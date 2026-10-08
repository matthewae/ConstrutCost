"""
KF-1 (import & validasi file IFC) dan KF-2 (parser, klasifikasi, ekstraksi dimensi).

Alur:
    info = buka_dan_validasi(path)              # KF-1: cek file + ringkasan untuk ditampilkan
    elemen, peringatan = ekstrak_elemen(info.model, progress)   # KF-2

Setiap elemen menghasilkan himpunan dimensi G = {L, B, H, t, A, V} (Rumus BAB 2.4.9) dalam meter, m2, m3:
    panjang (L), lebar (B), tinggi (H), tebal (t), luas (A), volume (V)
ditambah keliling, kemiringan (atap) dan luas_bukaan (dinding).

Sumber nilai, berurutan:
    1. Quantity set IFC (Qto_*BaseQuantities / BaseQuantities ArchiCAD / PSet_Revit_Dimensions)
       -> nilai resmi dari perangkat lunak BIM, dikonversi dengan satuan proyek
          (panjang, luas, dan volume punya faktor satuan masing-masing).
    2. Geometri 3D (IfcOpenShell, koordinat lokal elemen, sudah dalam meter) bila quantity set kosong.
Asal setiap nilai dicatat di 'sumber_dimensi' supaya bisa ditelusuri (KF-18).
"""

import math
import multiprocessing
from concurrent.futures import ProcessPoolExecutor
from concurrent.futures.process import BrokenProcessPool
from dataclasses import dataclass, field
from pathlib import Path

import ifcopenshell
import ifcopenshell.geom as geom
import numpy as np
import ifcopenshell.util.element as element_util
import ifcopenshell.util.shape as shape_util
import ifcopenshell.util.unit as unit_util

from klasifikasi import LABEL, ElementType, kumpulkan_elemen, predefined_type

SKEMA_DIDUKUNG = {"IFC2X3": "IFC2x3", "IFC4": "IFC4"}
PESAN_TIDAK_VALID = "File tidak valid. Pastikan file berformat IFC2x3 atau IFC4."

DIMENSI = ("panjang", "lebar", "tinggi", "tebal", "luas", "volume", "keliling")

_NAMA_SATUAN = {
    1.0: "meter",
    0.1: "desimeter",
    0.01: "sentimeter",
    0.001: "milimeter",
    0.3048: "kaki (feet)",
    0.0254: "inci",
}


class FileIFCTidakValid(Exception):
    """File gagal divalidasi (KF-1). Pesannya siap ditampilkan ke pengguna."""


@dataclass
class InfoFileIFC:
    """Ringkasan file IFC yang ditampilkan sebelum pengguna menekan "Import" (UC-01 langkah 7)."""

    path: str
    nama_file: str
    ukuran_byte: int
    skema: str
    aplikasi: str | None
    satuan_panjang: str
    lantai: list  # [(nama, elevasi_meter)] urut dari bawah
    jumlah_per_kelas: dict  # ElementType -> jumlah
    model: object = field(default=None, repr=False)

    @property
    def total_elemen(self) -> int:
        return sum(self.jumlah_per_kelas.values())

    @property
    def ukuran_teks(self) -> str:
        ukuran = float(self.ukuran_byte)
        for satuan in ("B", "KB", "MB"):
            if ukuran < 1024 or satuan == "MB":
                return f"{ukuran:,.0f} {satuan}" if satuan == "B" else f"{ukuran:,.1f} {satuan}"
            ukuran /= 1024
        return f"{ukuran:,.1f} GB"


# ======================================================================
# KF-1: validasi file
# ======================================================================


def _tidak_valid(alasan: str) -> FileIFCTidakValid:
    return FileIFCTidakValid(f"{PESAN_TIDAK_VALID}\n\n{alasan}")


def buka_dan_validasi(path, terisolasi: bool = False) -> InfoFileIFC:
    """Validasi ekstensi, header, integritas, dan versi IFC. Raise FileIFCTidakValid bila gagal.

    terisolasi=True: file dibuka lebih dulu di proses terpisah. Pustaka IfcOpenShell bisa
    crash (segmentation fault) pada file yang terpotong; dengan cara ini yang berhenti hanya
    proses anak, aplikasi tetap berjalan dan menampilkan pesan (KNF-4). Setelah lolos, file
    dibuka lagi di proses ini untuk dipakai parsing.
    """
    p = Path(path)
    _cek_berkas(p)
    if terisolasi:
        _validasi_di_proses_anak(p)
    return _validasi(p)


def _cek_berkas(p: Path) -> None:
    """Pemeriksaan cepat sebelum file dibaca IfcOpenShell."""
    if not p.is_file():
        raise FileIFCTidakValid(f"File tidak ditemukan:\n{p}")
    if p.suffix.lower() != ".ifc":
        raise _tidak_valid(f"Ekstensi file '{p.suffix or '(tanpa ekstensi)'}' bukan .ifc.")
    if p.stat().st_size == 0:
        raise _tidak_valid("File kosong (0 byte).")

    with open(p, "rb") as f:
        awal = f.read(256).lstrip(b"\xef\xbb\xbf \t\r\n")
        f.seek(max(0, p.stat().st_size - 512))
        akhir = f.read().rstrip()
    if not awal.startswith(b"ISO-10303-21"):
        raise _tidak_valid(
            "Header file bukan format IFC-SPF (ISO-10303-21). "
            "File kemungkinan rusak, atau berupa ifcXML / ifcZIP yang belum didukung."
        )
    if not akhir.endswith(b"END-ISO-10303-21;"):
        raise _tidak_valid(
            "Penutup file (END-ISO-10303-21;) tidak ditemukan. File kemungkinan terpotong, "
            "misalnya karena proses unduh atau salin yang tidak selesai. Ekspor ulang file dari aplikasi BIM."
        )


def _validasi(p: Path) -> InfoFileIFC:
    try:
        model = ifcopenshell.open(str(p))
    except Exception as e:  # sintaks STEP rusak
        raise _tidak_valid(f"File tidak dapat dibaca, kemungkinan rusak.\nDetail: {e}") from e

    skema = (model.schema or "").upper()
    if skema not in SKEMA_DIDUKUNG:
        raise _tidak_valid(f"Versi skema '{model.schema}' belum didukung.")
    if not model.by_type("IfcProject"):
        raise _tidak_valid("File tidak memiliki IfcProject (struktur IFC tidak lengkap).")

    jumlah = {}
    for _entity, _tipe, kelas in kumpulkan_elemen(model):
        jumlah[kelas] = jumlah.get(kelas, 0) + 1

    skala = unit_util.calculate_unit_scale(model)
    lantai = sorted(
        (
            (s.Name or "(tanpa nama)", (s.Elevation or 0.0) * skala)
            for s in model.by_type("IfcBuildingStorey")
        ),
        key=lambda x: x[1],
    )
    return InfoFileIFC(
        path=str(p),
        nama_file=p.name,
        ukuran_byte=p.stat().st_size,
        skema=SKEMA_DIDUKUNG[skema],
        aplikasi=_nama_aplikasi(model),
        satuan_panjang=_nama_satuan(skala),
        lantai=lantai,
        jumlah_per_kelas=jumlah,
        model=model,
    )


def _validasi_anak(path: str) -> bool:
    """Dijalankan di proses anak; hanya hasil lolos/gagal yang dikirim balik."""
    _validasi(Path(path))
    return True


def _validasi_di_proses_anak(p: Path) -> None:
    konteks = multiprocessing.get_context("spawn")
    with ProcessPoolExecutor(max_workers=1, mp_context=konteks) as ex:
        try:
            ex.submit(_validasi_anak, str(p)).result()
        except BrokenProcessPool as e:
            raise _tidak_valid(
                "Pembaca IFC berhenti tidak normal saat membuka file ini. "
                "File kemungkinan terpotong atau korup; ekspor ulang file dari aplikasi BIM."
            ) from e


def _nama_aplikasi(model):
    for app in model.by_type("IfcApplication"):
        nama = " ".join(x for x in (app.ApplicationFullName, app.Version) if x)
        if nama:
            return nama
    return None


def _nama_satuan(skala: float) -> str:
    for nilai, nama in _NAMA_SATUAN.items():
        if math.isclose(skala, nilai, rel_tol=1e-6):
            return nama
    return f"{skala:g} meter"


# ======================================================================
# KF-2: ekstraksi dimensi
# ======================================================================

# Prioritas quantity set: standar IFC dulu, lalu ekspor vendor.
def _prioritas_set(nama: str):
    if nama.startswith("Qto_"):
        return 0
    if nama == "BaseQuantities":  # ArchiCAD
        return 1
    if nama == "PSet_Revit_Dimensions":
        return 2
    if nama == "PSet_Revit_Type_Dimensions":
        return 3
    return None


@dataclass
class _Geometri:
    volume: float
    ext: tuple  # rentang bounding box lokal (x, y, z), meter
    sisi_x: float  # luas satu sisi yang menghadap +X
    sisi_y: float  # luas satu sisi yang menghadap +Y
    atas: float  # luas permukaan atas sebenarnya (miring tetap dihitung miring)
    tapak: float  # luas proyeksi horizontal
    keliling_tapak: float
    kemiringan: float | None = None  # derajat, bidang atas dominan (khusus atap)
    luas_miring: float | None = None  # luas bidang atas dengan kemiringan dominan (khusus atap)


class _Pengukur:
    def __init__(self, model):
        self.model = model
        self.s_panjang = unit_util.calculate_unit_scale(model, "LENGTHUNIT")
        self.s_luas = unit_util.calculate_unit_scale(model, "AREAUNIT")
        self.s_volume = unit_util.calculate_unit_scale(model, "VOLUMEUNIT")
        self.set_lokal = self._settings()
        self._cache_lantai = {}

    @staticmethod
    def _settings():
        # Koordinat lokal elemen: sumbu X dinding = arah panjang, Y = tebal (konvensi IFC),
        # sehingga luas sisi dinding benar untuk dinding ke arah mana pun.
        settings = geom.settings()
        try:
            settings.set("use-world-coords", False)  # IfcOpenShell >= 0.8
        except Exception:
            settings.set(settings.USE_WORLD_COORDS, False)  # versi lama
        return settings

    # ---------- quantity set ----------

    def kuantitas(self, entity) -> list:
        psets = element_util.get_psets(entity)
        terpilih = [(p, n) for n in psets if (p := _prioritas_set(n)) is not None]
        return [psets[n] for _p, n in sorted(terpilih)]

    @staticmethod
    def ambil(sets: list, *nama):
        """Nilai positif pertama. Urutan nama lebih diutamakan daripada urutan set."""
        for n in nama:
            for s in sets:
                v = s.get(n)
                if isinstance(v, (int, float)) and not isinstance(v, bool) and v > 0:
                    return float(v)
        return None

    def panjang(self, sets, *nama):
        v = self.ambil(sets, *nama)
        return v * self.s_panjang if v is not None else None

    def luas(self, sets, *nama):
        v = self.ambil(sets, *nama)
        return v * self.s_luas if v is not None else None

    def volume(self, sets, *nama):
        v = self.ambil(sets, *nama)
        return v * self.s_volume if v is not None else None

    # ---------- geometri ----------

    def geometri(self, entity, atap=False) -> _Geometri:
        shape = geom.create_shape(self.set_lokal, entity)
        g = shape.geometry  # `shape` tetap dipegang selama g dipakai
        mn, mx = shape_util.get_bbox(shape_util.get_vertices(g))
        ext = tuple(float(v) for v in (mx - mn))
        hasil = _Geometri(
            volume=float(shape_util.get_volume(g)),
            ext=ext,
            sisi_x=float(shape_util.get_side_area(g, axis="X")),
            sisi_y=float(shape_util.get_side_area(g, axis="Y")),
            atas=float(shape_util.get_top_area(g)),
            tapak=float(shape_util.get_footprint_area(g)),
            keliling_tapak=float(shape_util.get_footprint_perimeter(g)),
        )
        if atap:
            hasil.kemiringan, hasil.luas_miring = _bidang_atap(shape, g)
        return hasil

    # ---------- lantai ----------

    def lantai(self, entity):
        """IfcBuildingStorey tempat elemen berada (lewat containment, agregasi, atau dinding induk)."""
        node = entity
        for _ in range(12):
            induk = element_util.get_container(node) or element_util.get_aggregate(node)
            if induk is None:
                induk = self._dinding_induk(node)
            if induk is None:
                return None
            if induk.is_a("IfcBuildingStorey"):
                return induk
            node = induk
        return None

    @staticmethod
    def _dinding_induk(entity):
        """Pintu/jendela tanpa containment: ikuti bukaan -> dinding yang dilubangi."""
        for rel in getattr(entity, "FillsVoids", None) or []:
            for v in getattr(rel.RelatingOpeningElement, "VoidsElements", None) or []:
                return v.RelatingBuildingElement
        return None

    def info_lantai(self, entity):
        storey = self.lantai(entity)
        if storey is None:
            return None, None
        if storey.id() not in self._cache_lantai:
            elev = storey.Elevation
            self._cache_lantai[storey.id()] = (
                storey.Name,
                elev * self.s_panjang if elev is not None else None,
            )
        return self._cache_lantai[storey.id()]

    # ---------- bukaan dinding ----------

    def luas_bukaan(self, dinding) -> float:
        """Total luas bukaan (pintu/jendela/lubang) pada dinding, untuk Rumus 2.17."""
        total = 0.0
        for rel in getattr(dinding, "HasOpenings", None) or []:
            bukaan = rel.RelatedOpeningElement
            luas = None
            for isi in getattr(bukaan, "HasFillings", None) or []:
                el = isi.RelatedBuildingElement
                w, h = getattr(el, "OverallWidth", None), getattr(el, "OverallHeight", None)
                if w and h:
                    luas = w * h * self.s_panjang**2
                    break
            if luas is None:
                sets = self.kuantitas(bukaan)
                w, h = self.panjang(sets, "Width"), self.panjang(sets, "Height")
                if w and h:
                    luas = w * h
            total += luas or 0.0
        return total


def _bidang_atap(shape, g):
    """Kemiringan (derajat) dan luas bidang atas atap.

    Normal tiap segitiga diputar ke koordinat dunia, lalu segitiga yang menghadap ke atas
    dikelompokkan menurut komponen vertikal normalnya (n_z = cos theta). Kelompok dengan luas
    terbesar = bidang atap; sisi tebal pelat (n_z berbeda) tidak ikut terhitung.
    Atap pelana/perisai dengan kemiringan sama tetap satu kelompok (Rumus 2.22 / 2.23).
    """
    v = shape_util.get_vertices(g)
    f = shape_util.get_faces(g)
    silang = np.cross(v[f[:, 1]] - v[f[:, 0]], v[f[:, 2]] - v[f[:, 0]])
    luas = 0.5 * np.linalg.norm(silang, axis=1)
    sah = luas > 1e-12
    normal = silang[sah] / (2 * luas[sah])[:, None]
    putar = np.array(shape_util.get_shape_matrix(shape))[:3, :3]
    nz = (normal @ putar.T)[:, 2]
    luas = luas[sah]
    atas = nz > 0.01
    if not atas.any():
        return None, None
    kelompok = {}
    for z, a in zip(np.round(nz[atas], 2), luas[atas]):
        kelompok[z] = kelompok.get(z, 0.0) + a
    nz_dominan = max(kelompok, key=kelompok.get)
    pilih = atas & (np.abs(nz - nz_dominan) <= 0.015)
    cos_t = float(np.average(nz[pilih], weights=luas[pilih]))
    return math.degrees(math.acos(min(1.0, cos_t))), float(luas[pilih].sum())


class _Dimensi:
    """Mengumpulkan dimensi + asal nilainya. Nilai pertama yang valid yang dipakai."""

    def __init__(self):
        self.nilai = {}
        self.sumber = {}

    def isi(self, kunci, nilai, asal):
        if kunci in self.nilai or nilai is None:
            return
        if isinstance(nilai, float) and (math.isnan(nilai) or nilai <= 0):
            return
        self.nilai[kunci] = float(nilai)
        self.sumber[kunci] = asal

    def kurang(self, *kunci) -> bool:
        return any(k not in self.nilai for k in kunci)

    def buang(self, kunci):
        self.nilai.pop(kunci, None)
        self.sumber.pop(kunci, None)

    def buang_keliling_tidak_wajar(self):
        """Keliling bidang tidak mungkin < sqrt(4*pi*A) (lingkaran). Nilai di bawah itu
        berarti quantity set salah satuan (mis. Revit menulis feet pada file milimeter)."""
        k, a = self.nilai.get("keliling"), self.nilai.get("luas")
        if k and a and k < 0.9 * math.sqrt(4 * math.pi * a):
            self.buang("keliling")


def _cocok(a, b, toleransi=0.10) -> bool:
    return abs(a - b) <= toleransi * max(a, b)


def _ukur(p: _Pengukur, entity, kelas: ElementType) -> _Dimensi:
    d = _Dimensi()
    q = p.kuantitas(entity)
    vol = ("NetVolume", "GrossVolume", "Volume")

    if kelas == ElementType.WALL:
        d.isi("panjang", p.panjang(q, "Length"), "qto")
        d.isi("tinggi", p.panjang(q, "Height"), "qto")
        d.isi("tebal", p.panjang(q, "Width", "Thickness"), "qto")
        d.isi("luas", p.luas(q, "NetSideArea", "Area", "GrossSideArea"), "qto")
        d.isi("volume", p.volume(q, *vol), "qto")
        if d.kurang("panjang", "tinggi", "tebal", "luas", "volume"):
            g = p.geometri(entity)
            ex, ey, ez = g.ext
            # sumbu tebal dinding = sisi horizontal terpendek (standar IFC: sumbu Y lokal)
            tebal_di_y = ey <= ex
            d.isi("panjang", ex if tebal_di_y else ey, "geometri")
            d.isi("tinggi", ez, "geometri")
            d.isi("tebal", ey if tebal_di_y else ex, "geometri")
            d.isi("luas", g.sisi_y if tebal_di_y else g.sisi_x, "geometri")
            d.isi("volume", g.volume, "geometri")

    elif kelas == ElementType.COLUMN:
        d.isi("tinggi", p.panjang(q, "Length", "Height"), "qto")
        d.isi("lebar", p.panjang(q, "Width", "b"), "qto")
        d.isi("tebal", p.panjang(q, "Depth", "h"), "qto")
        d.isi("volume", p.volume(q, *vol), "qto")
        if d.kurang("tinggi", "lebar", "tebal", "volume"):
            g = p.geometri(entity)
            kecil, sedang, besar = sorted(g.ext)
            d.isi("tinggi", besar, "geometri")
            if _cocok(besar, d.nilai["tinggi"]):  # kolom miring: bbox tidak mewakili penampang
                d.isi("lebar", kecil, "geometri")
                d.isi("tebal", sedang, "geometri")
            d.isi("volume", g.volume, "geometri")

    elif kelas == ElementType.BEAM:
        d.isi("panjang", p.panjang(q, "Length"), "qto")
        d.isi("lebar", p.panjang(q, "Width", "b"), "qto")
        d.isi("tinggi", p.panjang(q, "Depth", "Height", "h"), "qto")
        d.isi("volume", p.volume(q, *vol), "qto")
        if d.kurang("panjang", "lebar", "tinggi", "volume"):
            g = p.geometri(entity)
            kecil, sedang, besar = sorted(g.ext)
            d.isi("panjang", besar, "geometri")
            if _cocok(besar, d.nilai["panjang"]):  # balok miring/diagonal: bbox tidak mewakili penampang
                d.isi("lebar", kecil, "geometri")
                d.isi("tinggi", sedang, "geometri")
            d.isi("volume", g.volume, "geometri")

    elif kelas == ElementType.SLAB:
        d.isi("luas", p.luas(q, "NetArea", "GrossArea", "Area"), "qto")
        d.isi("tebal", p.panjang(q, "Depth", "Thickness", "Width"), "qto")
        d.isi("keliling", p.panjang(q, "Perimeter"), "qto")
        d.isi("volume", p.volume(q, *vol), "qto")
        d.buang_keliling_tidak_wajar()
        if d.kurang("luas", "tebal", "keliling", "volume"):
            g = p.geometri(entity)
            d.isi("luas", g.atas, "geometri")
            d.isi("keliling", g.keliling_tapak, "geometri")
            d.isi("volume", g.volume, "geometri")
            d.isi("panjang", max(g.ext[0], g.ext[1]), "geometri")
            d.isi("lebar", min(g.ext[0], g.ext[1]), "geometri")
        if "tebal" not in d.nilai and d.nilai.get("luas") and d.nilai.get("volume"):
            d.isi("tebal", d.nilai["volume"] / d.nilai["luas"], "turunan")

    elif kelas == ElementType.ROOF:
        d.isi("luas", p.luas(q, "NetArea", "GrossArea", "Area"), "qto")
        d.isi("volume", p.volume(q, *vol), "qto")
        g = p.geometri(entity, atap=True)  # kemiringan selalu diukur dari geometri
        d.isi("luas", g.luas_miring, "geometri")
        d.isi("volume", g.volume, "geometri")
        d.isi("keliling", g.keliling_tapak, "geometri")
        d.isi("panjang", max(g.ext[0], g.ext[1]), "geometri")
        d.isi("lebar", min(g.ext[0], g.ext[1]), "geometri")
        if g.kemiringan is not None:
            d.nilai["kemiringan"] = g.kemiringan
            d.sumber["kemiringan"] = "geometri"
        if d.nilai.get("luas") and d.nilai.get("volume"):
            d.isi("tebal", d.nilai["volume"] / d.nilai["luas"], "turunan")

    elif kelas == ElementType.FOOTING:
        d.isi("panjang", p.panjang(q, "Length"), "qto")
        d.isi("lebar", p.panjang(q, "Width"), "qto")
        d.isi("tebal", p.panjang(q, "Height", "Depth", "Foundation Thickness"), "qto")
        d.isi("volume", p.volume(q, *vol), "qto")
        if d.kurang("panjang", "lebar", "tebal", "volume"):
            g = p.geometri(entity)
            d.isi("panjang", max(g.ext[0], g.ext[1]), "geometri")
            d.isi("lebar", min(g.ext[0], g.ext[1]), "geometri")
            d.isi("tebal", g.ext[2], "geometri")
            d.isi("volume", g.volume, "geometri")
        if "panjang" in d.nilai and "lebar" in d.nilai:
            d.isi("keliling", 2 * (d.nilai["panjang"] + d.nilai["lebar"]), "turunan")

    elif kelas == ElementType.PILE:
        d.isi("panjang", p.panjang(q, "Length"), "qto")
        d.isi("lebar", p.panjang(q, "Diameter", "Width"), "qto")
        d.isi("volume", p.volume(q, *vol), "qto")
        if d.kurang("panjang", "lebar", "volume"):
            g = p.geometri(entity)
            d.isi("panjang", max(g.ext), "geometri")
            d.isi("lebar", min(g.ext), "geometri")
            d.isi("volume", g.volume, "geometri")

    elif kelas in (ElementType.DOOR, ElementType.WINDOW):
        w, h = getattr(entity, "OverallWidth", None), getattr(entity, "OverallHeight", None)
        d.isi("lebar", w * p.s_panjang if w else None, "atribut")
        d.isi("tinggi", h * p.s_panjang if h else None, "atribut")
        d.isi("lebar", p.panjang(q, "Width"), "qto")
        d.isi("tinggi", p.panjang(q, "Height"), "qto")
        if "lebar" in d.nilai and "tinggi" in d.nilai:
            d.isi("luas", d.nilai["lebar"] * d.nilai["tinggi"], "turunan")
        d.isi("luas", p.luas(q, "Area"), "qto")

    elif kelas in (ElementType.FLOOR, ElementType.CEILING):
        d.isi("luas", p.luas(q, "NetArea", "GrossArea", "Area"), "qto")
        d.isi("keliling", p.panjang(q, "Perimeter"), "qto")
        d.buang_keliling_tidak_wajar()
        if d.kurang("luas"):
            g = p.geometri(entity)
            d.isi("luas", g.tapak, "geometri")
            d.isi("keliling", g.keliling_tapak, "geometri")

    elif kelas == ElementType.SPACE:
        d.isi("luas", p.luas(q, "NetFloorArea", "GrossFloorArea", "Area"), "qto")
        d.isi("keliling", p.panjang(q, "NetPerimeter", "GrossPerimeter", "Perimeter"), "qto")
        d.isi("tinggi", p.panjang(q, "Height", "ClearHeight", "Unbounded Height"), "qto")
        d.buang_keliling_tidak_wajar()
        if d.kurang("luas", "keliling"):
            g = p.geometri(entity)
            d.isi("luas", g.tapak, "geometri")
            d.isi("keliling", g.keliling_tapak, "geometri")
            d.isi("tinggi", g.ext[2], "geometri")

    return d


def _nama(entity, kelas):
    if kelas == ElementType.SPACE:
        bagian = [x for x in (entity.Name, getattr(entity, "LongName", None)) if x]
        return " - ".join(dict.fromkeys(bagian)) or None
    return entity.Name


def ekstrak_elemen(model, progress=None):
    """
    Return (elemen, peringatan). `progress(i, n, teks)` dipanggil per elemen bila diberikan.
    Nilai yang gagal dibaca dibiarkan None; rule engine yang memutuskan item mana dilewati.
    """
    p = _Pengukur(model)
    kandidat = list(kumpulkan_elemen(model))
    n = len(kandidat)
    elemen, peringatan = [], []

    for i, (entity, _tipe, kelas) in enumerate(kandidat):
        nama = _nama(entity, kelas)
        if progress:
            progress(i, n, f"{LABEL[kelas]}: {nama or entity.GlobalId}")
        try:
            d = _ukur(p, entity, kelas)
        except Exception as e:  # geometri rusak / representasi tidak didukung
            d = _Dimensi()
            peringatan.append(
                f"Dimensi gagal dihitung: {LABEL[kelas]} '{nama}' ({entity.GlobalId}): {e}"
            )

        luas_bukaan = None
        if kelas == ElementType.WALL:
            try:
                luas_bukaan = p.luas_bukaan(entity)
            except Exception:
                luas_bukaan = None

        lantai, elevasi = p.info_lantai(entity)
        if "volume" in d.sumber:
            sumber_volume = d.sumber["volume"]
        elif kelas in (ElementType.COLUMN, ElementType.BEAM, ElementType.SLAB, ElementType.WALL,
                       ElementType.FOOTING, ElementType.PILE):
            sumber_volume = "gagal"
            peringatan.append(
                f"Volume tidak ditemukan: {LABEL[kelas]} '{nama}' ({entity.GlobalId})"
            )
        else:
            sumber_volume = None

        elemen.append(
            {
                "global_id": entity.GlobalId,
                "ifc_type": entity.is_a(),
                "kelas": kelas.value,
                "predefined_type": predefined_type(entity),
                "nama": nama,
                "lantai": lantai,
                "elevasi_lantai": elevasi,
                **{k: d.nilai.get(k) for k in DIMENSI},
                "kemiringan": d.nilai.get("kemiringan"),
                "luas_bukaan": luas_bukaan,
                "sumber_volume": sumber_volume,
                "sumber_dimensi": dict(d.sumber),
            }
        )

    if progress:
        progress(n, n, "Ekstraksi selesai")
    return elemen, peringatan
