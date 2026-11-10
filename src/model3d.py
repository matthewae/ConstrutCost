"""
Geometri 3D bangunan dari file IFC untuk penampil 3D (gui/penampil3d.py).

Setiap elemen bangunan (IfcElement) diubah menjadi segitiga dengan normal per bidang (flat shading) dalam
koordinat dunia, lalu disusun Y-ke-atas untuk Qt Quick 3D: (x, y, z)_IFC -> (x, z, -y). Model digeser sehingga
titik tengah denah berada di (0, 0) dan muka terbawah di y = 0. Tulangan, lubang, ruang, dan elemen virtual tidak
ditampilkan (ribuan batang tulangan tidak perlu untuk memilih elemen dan memperlambat tampilan).
"""

import os
from dataclasses import dataclass, field

import numpy as np

TIDAK_DITAMPILKAN = ("IfcOpeningElement", "IfcReinforcingBar", "IfcReinforcingMesh", "IfcVirtualElement",
                     "IfcSpace", "IfcAnnotation", "IfcFeatureElement", "IfcTendon", "IfcFastener",
                     "IfcMechanicalFastener", "IfcElementAssembly")


@dataclass
class Elemen3D:
    gid: str
    ifc: str
    nama: str
    lantai: str | None
    elevasi: float | None
    posisi: np.ndarray  # (n, 3) float32, segitiga tanpa indeks, Y ke atas, sudah digeser
    normal: np.ndarray  # (n, 3) float32
    kotak: tuple  # (xmin, ymin, zmin, xmax, ymax, zmax) koordinat IFC dunia (meter), sebelum digeser

    @property
    def jumlah_segitiga(self) -> int:
        return len(self.posisi) // 3

    def batas(self) -> tuple:
        """(min, max) koordinat tampilan (Y ke atas)."""
        return self.posisi.min(axis=0), self.posisi.max(axis=0)


@dataclass
class Model3D:
    elemen: list = field(default_factory=list)
    lantai: list = field(default_factory=list)  # [(nama, elevasi)] urut dari bawah
    geser: tuple = (0.0, 0.0, 0.0)  # x, y, z IFC yang dikurangkan

    def batas(self) -> tuple:
        if not self.elemen:
            return np.zeros(3, np.float32), np.ones(3, np.float32)
        mn = np.min([e.batas()[0] for e in self.elemen], axis=0)
        mx = np.max([e.batas()[1] for e in self.elemen], axis=0)
        return mn, mx

    def per_gid(self) -> dict:
        return {e.gid: e for e in self.elemen}


def _lantai(entity):
    """IfcBuildingStorey tempat elemen berada (containment / agregasi / dinding induk untuk pintu & jendela)."""
    import ifcopenshell.util.element as ue

    node = entity
    for _ in range(12):
        induk = ue.get_container(node) or ue.get_aggregate(node)
        if induk is None:
            for rel in getattr(node, "FillsVoids", None) or []:
                for v in getattr(rel.RelatingOpeningElement, "VoidsElements", None) or []:
                    induk = v.RelatingBuildingElement
        if induk is None:
            return None
        if induk.is_a("IfcBuildingStorey"):
            return induk
        node = induk
    return None


def segitiga_rata(verts: np.ndarray, faces: np.ndarray) -> tuple:
    """(posisi, normal) segitiga tanpa indeks dengan normal per bidang. verts (m, 3), faces (k, 3)."""
    tri = verts[faces.reshape(-1, 3)]  # (k, 3, 3)
    n = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
    panjang = np.linalg.norm(n, axis=1, keepdims=True)
    sah = panjang[:, 0] > 1e-12
    tri, n = tri[sah], n[sah] / panjang[sah]
    return tri.reshape(-1, 3).astype(np.float32), np.repeat(n, 3, axis=0).astype(np.float32)


def ke_y_atas(p: np.ndarray, geser=(0.0, 0.0, 0.0)) -> np.ndarray:
    """IFC (x, y, z) -> tampilan (x, z, -y), setelah dikurangi titik geser."""
    q = p - np.asarray(geser, dtype=p.dtype)
    return np.stack([q[:, 0], q[:, 2], -q[:, 1]], axis=1).astype(np.float32)


def muat_model3d(path: str, progress=None) -> Model3D:
    """Baca geometri semua elemen bangunan file IFC. `progress(i, n, teks)` opsional."""
    import ifcopenshell
    import ifcopenshell.geom as geom
    import ifcopenshell.util.unit as unit_util

    model = ifcopenshell.open(str(path))
    entitas = [e for e in model.by_type("IfcElement")
               if getattr(e, "Representation", None) and not any(e.is_a(t) for t in TIDAK_DITAMPILKAN)]
    skala = unit_util.calculate_unit_scale(model)
    lantai = sorted(((s.Name or "(tanpa nama)", (s.Elevation or 0.0) * skala) for s in model.by_type("IfcBuildingStorey")),
                    key=lambda x: x[1])
    per_id = {e.id(): e for e in entitas}
    st = geom.settings()
    st.set("use-world-coords", True)
    st.set("weld-vertices", False)
    mentah = []
    n = len(entitas)
    if entitas:
        it = geom.iterator(st, model, max(1, min(os.cpu_count() or 1, 8)), include=entitas)
        if it.initialize():
            i = 0
            while True:
                sh = it.get()
                g = sh.geometry
                verts = np.asarray(g.verts, dtype=np.float64).reshape(-1, 3)
                faces = np.asarray(g.faces, dtype=np.int64)
                if len(verts) and len(faces):
                    mentah.append((per_id.get(sh.id), verts, faces))
                i += 1
                if progress and (i % 25 == 0 or i == n):
                    progress(i, n, "Membaca bentuk elemen 3D")
                if not it.next():
                    break
    if not mentah:
        return Model3D(lantai=lantai)
    semua = np.vstack([v for _e, v, _f in mentah])
    mn, mx = semua.min(axis=0), semua.max(axis=0)
    geser = (float((mn[0] + mx[0]) / 2), float((mn[1] + mx[1]) / 2), float(mn[2]))
    hasil = Model3D(lantai=lantai, geser=geser)
    cache_lantai = {}
    for ent, verts, faces in mentah:
        if ent is None:
            continue
        pos, nrm = segitiga_rata(verts, faces)
        if not len(pos):
            continue
        st_ = _lantai(ent)
        if st_ is not None and st_.id() not in cache_lantai:
            cache_lantai[st_.id()] = (st_.Name, (st_.Elevation or 0.0) * skala)
        nama_lt, elev = cache_lantai.get(st_.id(), (None, None)) if st_ is not None else (None, None)
        vmn, vmx = verts.min(axis=0), verts.max(axis=0)
        hasil.elemen.append(Elemen3D(
            ent.GlobalId, ent.is_a(), ent.Name or ent.is_a(), nama_lt, elev,
            ke_y_atas(pos, geser), ke_y_atas(nrm), (*map(float, vmn), *map(float, vmx)),
        ))
    return hasil


def di_bawah(atas: tuple, bawah: tuple, toleransi: float = 0.15) -> bool:
    """Kotak `bawah` (IFC) berada tepat di bawah kotak `atas`: denah saling menutup >= 50% denah yang lebih kecil
    dan puncak `bawah` dekat dengan dasar `atas` (dipakai untuk lantai kerja / pasir di bawah fondasi)."""
    dx = min(atas[3], bawah[3]) - max(atas[0], bawah[0])
    dy = min(atas[4], bawah[4]) - max(atas[1], bawah[1])
    if dx <= 0 or dy <= 0:
        return False
    kecil = min((atas[3] - atas[0]) * (atas[4] - atas[1]), (bawah[3] - bawah[0]) * (bawah[4] - bawah[1]))
    return kecil > 0 and dx * dy >= 0.5 * kecil and abs(bawah[5] - atas[2]) <= toleransi
