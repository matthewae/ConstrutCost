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
    termasuk: str | None = None  # elemen_lain.TERMASUK: batang rangka atap / penutup atap / bagian tangga

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


def _termasuk(entity) -> str | None:
    """Jenis 'sudah termasuk pekerjaan lain' (elemen_lain.TERMASUK) untuk batang, penutup atap, bagian tangga."""
    import ifcopenshell.util.element as ue

    from elemen_lain import TERMASUK, kenali

    induk = ue.get_aggregate(entity)
    if not (entity.is_a("IfcMember") or entity.is_a("IfcCovering")
            or (induk is not None and (induk.is_a("IfcStair") or induk.is_a("IfcRamp")))):
        return None
    try:
        jenis = kenali(entity)
    except Exception:
        return None
    return jenis if jenis in TERMASUK else None


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
            ke_y_atas(pos, geser), ke_y_atas(nrm), (*map(float, vmn), *map(float, vmx)), _termasuk(ent),
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


# ---------------------------------------------------------------- besi beton (IfcReinforcingBar)

@dataclass
class Besi3D:
    """Besi beton satu elemen induk (kolom, balok, pelat, fondasi, ...), digabung menjadi satu bentuk 3D."""
    gid: str  # "besi:<GlobalId induk>"
    host: str | None  # GlobalId elemen induk
    nama: str  # nama elemen induk
    posisi: np.ndarray
    normal: np.ndarray
    n_batang: int
    kotak: tuple

    @property
    def jumlah_segitiga(self) -> int:
        return len(self.posisi) // 3

    def batas(self) -> tuple:
        return self.posisi.min(axis=0), self.posisi.max(axis=0)


SISI_TABUNG = 6  # penampang besi digambar segi-6: cukup untuk dilihat, jauh lebih ringan dari bentuk asli


def tabung(a: np.ndarray, b: np.ndarray, r: np.ndarray, sisi: int = SISI_TABUNG) -> tuple:
    """(posisi, normal) segitiga tabung segi-`sisi` untuk N segmen garis a[i] -> b[i] berjari-jari r[i]."""
    d = b - a
    panjang = np.linalg.norm(d, axis=1)
    sah = panjang > 1e-6
    a, b, r, d, panjang = a[sah], b[sah], r[sah], d[sah], panjang[sah]
    if not len(a):
        return np.zeros((0, 3), np.float32), np.zeros((0, 3), np.float32)
    d = d / panjang[:, None]
    bantu = np.where(np.abs(d[:, 2:3]) < 0.9, [[0.0, 0.0, 1.0]], [[1.0, 0.0, 0.0]])
    u = np.cross(d, bantu)
    u /= np.linalg.norm(u, axis=1, keepdims=True)
    v = np.cross(d, u)
    t = np.arange(sisi) * 2 * np.pi / sisi
    ring = np.cos(t)[None, :, None] * u[:, None, :] + np.sin(t)[None, :, None] * v[:, None, :]  # (N, sisi, 3)
    p0 = a[:, None, :] + r[:, None, None] * ring
    p1 = b[:, None, :] + r[:, None, None] * ring
    k1 = np.roll(np.arange(sisi), -1)
    # dua segitiga per sisi: (p0_k, p0_k+1, p1_k) dan (p0_k+1, p1_k+1, p1_k)
    pos = np.stack([p0, p0[:, k1], p1, p0[:, k1], p1[:, k1], p1], axis=2)  # (N, sisi, 6, 3)
    nrm = np.stack([ring, ring[:, k1], ring, ring[:, k1], ring[:, k1], ring], axis=2)
    return pos.reshape(-1, 3), nrm.reshape(-1, 3)


def _normal(v) -> np.ndarray:
    a = np.array(v, dtype=float)
    n = np.linalg.norm(a)
    return a / n if n > 0 else a


def _a2p(pos, skala: float) -> np.ndarray:
    """Matriks 4x4 IfcAxis2Placement3D/2D (translasi dalam meter)."""
    m = np.eye(4)
    if pos is None:
        return m
    m[:3, 3] = np.array((list(pos.Location.Coordinates) + [0.0])[:3], dtype=float) * skala
    if pos.is_a("IfcAxis2Placement3D"):
        z = _normal(pos.Axis.DirectionRatios) if pos.Axis else np.array([0.0, 0.0, 1.0])
        x = _normal(pos.RefDirection.DirectionRatios) if pos.RefDirection else np.array([1.0, 0.0, 0.0])
        x = _normal(x - np.dot(x, z) * z)
        m[:3, 0], m[:3, 1], m[:3, 2] = x, np.cross(z, x), z
    return m


def _matriks_lokal(plc, skala: float, memo: dict) -> np.ndarray:
    """Matriks dunia IfcLocalPlacement (rantai PlacementRelTo, disimpan di memo)."""
    if plc is None or not plc.is_a("IfcLocalPlacement"):
        return np.eye(4)
    if plc.id() not in memo:
        induk = _matriks_lokal(plc.PlacementRelTo, skala, memo) if plc.PlacementRelTo else np.eye(4)
        memo[plc.id()] = induk @ _a2p(plc.RelativePlacement, skala)
    return memo[plc.id()]


def _segmen_besi(bar, skala: float, memo: dict | None = None):
    """[(a, b, r)] segmen garis besi dalam koordinat dunia IFC (meter) dari IfcExtrudedAreaSolid, atau None bila
    bentuknya lain (mis. IfcSweptDiskSolid lengkung) sehingga perlu dibaca dengan pembaca geometri."""
    memo = {} if memo is None else memo
    rep = next((r for r in bar.Representation.Representations if (r.RepresentationIdentifier or "Body") == "Body"),
               None)
    if rep is None or not bar.ObjectPlacement:
        return None
    m = _matriks_lokal(bar.ObjectPlacement, skala, memo)
    r = (bar.NominalDiameter or 0.0) * skala / 2 or 0.006
    hasil = []
    for item in rep.Items or []:
        if not item.is_a("IfcExtrudedAreaSolid"):
            return None
        p = m @ _a2p(item.Position, skala)
        arah = _normal(item.ExtrudedDirection.DirectionRatios)
        a = p[:3, 3]
        b = a + p[:3, :3] @ arah * (item.Depth * skala)
        hasil.append((a, b, r))
    return hasil or None


def _peta_induk_pset(model) -> dict:
    """{id besi: GlobalId induk} dari properti HostGlobalId, dalam satu kali telusur relasi properti."""
    hasil = {}
    for rel in model.by_type("IfcRelDefinesByProperties"):
        ps = rel.RelatingPropertyDefinition
        if not ps.is_a("IfcPropertySet"):
            continue
        for prop in ps.HasProperties or []:
            if (prop.Name or "").lower() == "hostglobalid" and prop.is_a("IfcPropertySingleValue") and prop.NominalValue:
                for o in rel.RelatedObjects:
                    hasil[o.id()] = prop.NominalValue.wrappedValue
    return hasil


def _induk_besi(bar, model, peta_pset: dict):
    host = None
    for atribut in ("Decomposes", "Nests"):
        for rel in getattr(bar, atribut, None) or ():
            host = rel.RelatingObject
    if host is None and bar.id() in peta_pset:
        try:
            host = model.by_guid(peta_pset[bar.id()])
        except RuntimeError:
            host = None
    while host is not None and host.is_a("IfcElementAssembly") and getattr(host, "Decomposes", None):
        host = host.Decomposes[0].RelatingObject
    return host


def muat_besi(path: str, geser: tuple, progress=None) -> list:
    """Besi beton yang dimodelkan (IfcReinforcingBar), digabung per elemen induk, dalam koordinat tampilan
    (Y ke atas, digeser sama seperti Model3D). [] bila model tidak memuat besi."""
    import ifcopenshell
    import ifcopenshell.geom as geom
    import ifcopenshell.util.unit as unit_util

    model = ifcopenshell.open(str(path))
    bars = [b for b in model.by_type("IfcReinforcingBar") if getattr(b, "Representation", None)]
    if not bars:
        return []
    skala = unit_util.calculate_unit_scale(model)
    per_host = {}  # gid induk -> {"nama", "seg": [(a,b,r)], "mesh": [(pos, nrm)], "n"}
    lengkung = []
    peta_pset, memo = _peta_induk_pset(model), {}
    for i, bar in enumerate(bars):
        host = _induk_besi(bar, model, peta_pset)
        kunci = host.GlobalId if host is not None else None
        d = per_host.setdefault(kunci, {"nama": (host.Name if host is not None else None) or "Besi tanpa induk",
                                        "seg": [], "mesh": [], "n": 0})
        d["n"] += 1
        seg = None
        try:
            seg = _segmen_besi(bar, skala, memo)
        except Exception:
            seg = None
        if seg:
            d["seg"].extend(seg)
        else:
            lengkung.append((bar, kunci))
        if progress and (i % 200 == 0 or i == len(bars) - 1):
            progress(i + 1, len(bars), "Membaca besi beton")
    if lengkung:  # bentuk lain: pembaca geometri IfcOpenShell (lebih lambat, hanya untuk besi ini)
        st = geom.settings()
        st.set("use-world-coords", True)
        st.set("weld-vertices", False)
        induk = {b.id(): k for b, k in lengkung}
        it = geom.iterator(st, model, max(1, min(os.cpu_count() or 1, 8)), include=[b for b, _k in lengkung])
        if it.initialize():
            while True:
                sh = it.get()
                g = sh.geometry
                verts = np.asarray(g.verts, dtype=np.float64).reshape(-1, 3)
                faces = np.asarray(g.faces, dtype=np.int64)
                if len(verts) and len(faces):
                    per_host[induk.get(sh.id)]["mesh"].append(segitiga_rata(verts, faces))
                if not it.next():
                    break
    hasil = []
    for kunci, d in per_host.items():
        bagian_pos, bagian_nrm = [], []
        if d["seg"]:
            a = np.array([s[0] for s in d["seg"]])
            b = np.array([s[1] for s in d["seg"]])
            r = np.array([s[2] for s in d["seg"]])
            pos, nrm = tabung(a, b, r)
            bagian_pos.append(pos)
            bagian_nrm.append(nrm)
        for pos, nrm in d["mesh"]:
            bagian_pos.append(pos.astype(np.float64))
            bagian_nrm.append(nrm.astype(np.float64))
        if not bagian_pos:
            continue
        pos = np.vstack(bagian_pos)
        nrm = np.vstack(bagian_nrm)
        mn, mx = pos.min(axis=0), pos.max(axis=0)
        hasil.append(Besi3D(f"besi:{kunci or 'lepas'}", kunci, d["nama"], ke_y_atas(pos, geser), ke_y_atas(nrm),
                            d["n"], (*map(float, mn), *map(float, mx))))
    return hasil
