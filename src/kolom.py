"""
Kolom fisik dan fungsi kolom (KF-2): satu kolom di lapangan sering dimodelkan sebagai beberapa IfcColumn.

1. Penggabungan segmen (kolom fisik)
   Dua IfcColumn yang bertumpuk vertikal (posisi denah sama, penampang saling menutup >= 50%, celah
   vertikal <= 10 cm) adalah satu kolom bila:
   - segmen bawah adalah pedestal / stek kolom (seluruhnya di bawah peil lantai dasar + 15 cm), atau
   - keduanya berada di lantai (IfcBuildingStorey) yang sama (kolom dipotong saat pemodelan).
   Kolom lantai 1 dan lantai 2 tetap dua kolom: volume kolom diukur per lantai (praktik RAB).
   Volume, bekisting, dan besi tetap dihitung per segmen (tidak ada yang hilang); yang digabung adalah
   penghitungan jumlah kolom, tipe "— n buah", dan fondasi turunan (satu per kolom fisik).

2. Objek ganda
   Dua IfcColumn yang menempati ruang yang sama (tumpang tindih >= 50% denah dan tinggi), mis. kolom
   arsitektur (pembungkus) di luar kolom struktur, atau kolom tersalin dua kali. Volumenya dihitung sekali:
   segmen yang LoadBearing / lebih kecil dipertahankan, yang lain ditandai `duplikat`.

3. Fungsi kolom (per kolom fisik)
   - arsitektur : Pset_ColumnCommon.LoadBearing = FALSE, atau nama/tipe menyebut dekoratif/ornamen/
                  arsitektur/pilaster (tidak memikul struktur utama, hanya memperindah desain);
   - kanopi     : nama/tipe menyebut kanopi/carport/teras/pergola/gazebo/selasar, atau kolom berdiri
                  di luar denah bangunan (di luar selubung dinding lantainya);
   - praktis    : beton dengan sisi terkecil <= 15 cm (kolom praktis di dalam pasangan dinding);
   - utama      : kolom struktur utama (portal bangunan).
"""

import re
from dataclasses import dataclass, field

from rules.sifat import _KAYU, _PROFIL_BAJA

FUNGSI_UTAMA, FUNGSI_KANOPI, FUNGSI_ARSITEKTUR, FUNGSI_PRAKTIS = "utama", "kanopi", "arsitektur", "praktis"
URUT_FUNGSI = (FUNGSI_UTAMA, FUNGSI_KANOPI, FUNGSI_PRAKTIS, FUNGSI_ARSITEKTUR)
LABEL_FUNGSI = {
    FUNGSI_UTAMA: "Kolom struktur utama",
    FUNGSI_KANOPI: "Kolom kanopi / carport / teras",
    FUNGSI_PRAKTIS: "Kolom praktis",
    FUNGSI_ARSITEKTUR: "Kolom arsitektur (non-struktural)",
}

TOL_CELAH = 0.10  # m, celah / tumpang vertikal antar-segmen yang masih dianggap menyambung
TOL_PEDESTAL = 0.15  # m, puncak pedestal <= peil lantai dasar + toleransi ini
TOL_SELUBUNG = 0.30  # m, kolom di luar selubung dinding lebih dari ini = berdiri di luar bangunan
TUTUP_MIN = 0.5  # porsi penampang yang saling menutup
SISI_PRAKTIS = 0.15  # m
BATAS_ELEVASI_FONDASI = -0.5  # m, sama dengan rules/konteks.py

_ARSITEKTUR = re.compile(
    r"dekor|ornamen|hias|arsitektur|architect|estetika|pilaster|non[\s_-]*struktur|non[\s_-]*structural|"
    r"kolom\s*palsu|fake\s*column|cladding|pembungkus|selubung\s*kolom", re.IGNORECASE)
_KANOPI = re.compile(
    r"kanopi|canopy|car\s*-?\s*port|teras|terrace|porch|pergola|gazebo|selasar|awning|luifel|"
    r"covered\s*walk", re.IGNORECASE)
_PEDESTAL = re.compile(r"pedestal|stek\s*kolom|stub\s*column|kolom\s*pendek|column\s*stub|neck\s*column",
                       re.IGNORECASE)


@dataclass
class Segmen:
    """Satu IfcColumn. kotak = (xmin, ymin, zmin, xmax, ymax, zmax) koordinat dunia, meter."""
    gid: str
    nama: str
    kotak: tuple
    teks: str = ""  # nama + nama tipe + ObjectType + Description (untuk kata kunci)
    load_bearing: bool | None = None
    lantai: str | None = None

    @property
    def tinggi(self) -> float:
        return self.kotak[5] - self.kotak[2]

    @property
    def luas_denah(self) -> float:
        return max(self.kotak[3] - self.kotak[0], 0.0) * max(self.kotak[4] - self.kotak[1], 0.0)

    @property
    def pusat(self) -> tuple:
        return (self.kotak[0] + self.kotak[3]) / 2, (self.kotak[1] + self.kotak[4]) / 2

    @property
    def sisi_kecil(self) -> float:
        return min(self.kotak[3] - self.kotak[0], self.kotak[4] - self.kotak[1])


@dataclass
class HasilKolom:
    info: dict = field(default_factory=dict)  # gid -> {grup, fungsi, urut, n, peran, duplikat, nama_grup}
    ringkasan: dict = field(default_factory=dict)


def _tutup_denah(a: Segmen, b: Segmen) -> float:
    """Porsi penampang yang saling menutup terhadap penampang yang lebih kecil (0..1)."""
    dx = min(a.kotak[3], b.kotak[3]) - max(a.kotak[0], b.kotak[0])
    dy = min(a.kotak[4], b.kotak[4]) - max(a.kotak[1], b.kotak[1])
    kecil = min(a.luas_denah, b.luas_denah)
    if dx <= 0 or dy <= 0 or kecil <= 0:
        return 0.0
    return dx * dy / kecil


def _tumpang_tinggi(a: Segmen, b: Segmen) -> float:
    return min(a.kotak[5], b.kotak[5]) - max(a.kotak[2], b.kotak[2])


def _bawah_tanah(s: Segmen, elev_dasar: float | None) -> bool:
    if _PEDESTAL.search(s.teks or s.nama or ""):
        return True
    return elev_dasar is not None and s.kotak[5] <= elev_dasar + TOL_PEDESTAL


def _selubung(titik: list) -> list:
    """Convex hull 2D (monotone chain), berlawanan arah jarum jam."""
    p = sorted(set(titik))
    if len(p) < 3:
        return p

    def silang(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    bawah, atas = [], []
    for q in p:
        while len(bawah) >= 2 and silang(bawah[-2], bawah[-1], q) <= 0:
            bawah.pop()
        bawah.append(q)
    for q in reversed(p):
        while len(atas) >= 2 and silang(atas[-2], atas[-1], q) <= 0:
            atas.pop()
        atas.append(q)
    return bawah[:-1] + atas[:-1]


def _jarak_luar(poli: list, t: tuple) -> float:
    """0 bila titik di dalam poligon cembung (CCW), selain itu jarak ke tepi terdekat."""
    if len(poli) < 3:
        return 0.0
    di_dalam = True
    terdekat = float("inf")
    for i, a in enumerate(poli):
        b = poli[(i + 1) % len(poli)]
        ex, ey = b[0] - a[0], b[1] - a[1]
        if ex * (t[1] - a[1]) - ey * (t[0] - a[0]) < 0:
            di_dalam = False
        panjang2 = ex * ex + ey * ey
        u = 0.0 if panjang2 == 0 else max(0.0, min(1.0, ((t[0] - a[0]) * ex + (t[1] - a[1]) * ey) / panjang2))
        px, py = a[0] + u * ex, a[1] + u * ey
        terdekat = min(terdekat, ((t[0] - px) ** 2 + (t[1] - py) ** 2) ** 0.5)
    return 0.0 if di_dalam else terdekat


def elevasi_dasar(lantai_elev: dict, lantai_berisi: set) -> float | None:
    """Peil lantai dasar: elevasi terendah >= -0,5 m di antara lantai yang memuat dinding/kolom."""
    elev = [lantai_elev[n] for n in lantai_berisi if lantai_elev.get(n) is not None]
    atas = [x for x in elev if x >= BATAS_ELEVASI_FONDASI]
    calon = atas or elev
    return min(calon) if calon else None


def analisis(segmen: list, dinding: dict | None = None, elev_dasar: float | None = None) -> HasilKolom:
    """Kelompokkan segmen menjadi kolom fisik dan tentukan fungsinya.
    dinding: {nama lantai: [kotak dinding (xmin, ymin, zmin, xmax, ymax, zmax)]} untuk selubung bangunan."""
    dinding = dinding or {}
    n = len(segmen)
    induk = list(range(n))

    def akar(i):
        while induk[i] != i:
            induk[i] = induk[induk[i]]
            i = induk[i]
        return i

    # objek ganda: dua kolom menempati ruang yang sama
    duplikat = {}
    urut = sorted(range(n), key=lambda i: (segmen[i].load_bearing is not True, segmen[i].luas_denah, segmen[i].gid))
    for posisi, i in enumerate(urut):
        if i in duplikat:
            continue
        for j in urut[posisi + 1:]:
            if j in duplikat:
                continue
            a, b = segmen[i], segmen[j]
            t = _tumpang_tinggi(a, b)
            if _tutup_denah(a, b) >= TUTUP_MIN and t > 0 and t >= 0.5 * min(a.tinggi, b.tinggi):
                duplikat[j] = i
    # segmen bertumpuk -> satu kolom fisik. Segmen atas boleh tertanam sebagian di segmen bawah (tumpang tindih
    # di bawah batas objek ganda): digabung, dan volume tumpang tindihnya dilaporkan karena terhitung dua kali.
    aktif = [i for i in range(n) if i not in duplikat]
    aktif.sort(key=lambda i: segmen[i].kotak[2])
    tumpang = []
    for x, i in enumerate(aktif):
        a = segmen[i]
        for j in aktif[x + 1:]:
            b = segmen[j]
            celah = b.kotak[2] - a.kotak[5]
            if celah > TOL_CELAH or b.kotak[5] <= a.kotak[5] or _tutup_denah(a, b) < TUTUP_MIN:
                continue
            if _bawah_tanah(a, elev_dasar) or a.lantai == b.lantai:  # lantai None = model tanpa IfcBuildingStorey
                induk[akar(j)] = akar(i)
                if celah < -0.02:
                    dx = min(a.kotak[3], b.kotak[3]) - max(a.kotak[0], b.kotak[0])
                    dy = min(a.kotak[4], b.kotak[4]) - max(a.kotak[1], b.kotak[1])
                    tumpang.append((f"{a.nama} / {b.nama}", dx * dy * -celah))

    grup = {}
    for i in aktif:
        grup.setdefault(akar(i), []).append(i)

    selubung = {}
    for lantai, kotak in dinding.items():
        if len(kotak) >= 3:
            titik = [(k[0], k[1]) for k in kotak] + [(k[3], k[4]) for k in kotak] + \
                    [(k[0], k[4]) for k in kotak] + [(k[3], k[1]) for k in kotak]
            selubung[lantai] = _selubung(titik)

    hasil = HasilKolom()
    per_fungsi = {f: 0 for f in URUT_FUNGSI}
    contoh_gabung, contoh_fungsi = [], {f: [] for f in URUT_FUNGSI}
    for anggota in grup.values():
        anggota.sort(key=lambda i: segmen[i].kotak[2])
        seg = [segmen[i] for i in anggota]
        atas = [s for s in seg if not _bawah_tanah(s, elev_dasar)] or seg
        utama = max(atas, key=lambda s: s.tinggi)  # segmen terpanjang di atas tanah = wakil kolom
        teks = " ".join(s.teks or s.nama or "" for s in seg)
        lb = [s.load_bearing for s in atas if s.load_bearing is not None]
        if _ARSITEKTUR.search(teks) or (lb and not any(lb)):
            fungsi = FUNGSI_ARSITEKTUR
        elif _KANOPI.search(teks):
            fungsi = FUNGSI_KANOPI
        elif utama.lantai in selubung and _jarak_luar(selubung[utama.lantai], utama.pusat) > TOL_SELUBUNG:
            fungsi = FUNGSI_KANOPI
        elif 0 < utama.sisi_kecil <= SISI_PRAKTIS + 1e-9 and not (_PROFIL_BAJA.search(teks) or _KAYU.search(teks)):
            # kolom praktis = beton kecil di dalam pasangan; profil baja/kayu kecil tetap kolom struktur
            fungsi = FUNGSI_PRAKTIS
        else:
            fungsi = FUNGSI_UTAMA
        per_fungsi[fungsi] += 1
        if len(contoh_fungsi[fungsi]) < 3:
            contoh_fungsi[fungsi].append(utama.nama)
        if len(seg) > 1 and len(contoh_gabung) < 3:
            contoh_gabung.append(" + ".join(s.nama for s in seg))
        for k, s in enumerate(seg, 1):
            hasil.info[s.gid] = {
                "grup": utama.gid, "nama_grup": utama.nama, "fungsi": fungsi, "urut": k, "n": len(seg),
                "peran": "pedestal" if len(seg) > 1 and _bawah_tanah(s, elev_dasar) else "kolom", "duplikat": None,
            }
    for j, i in duplikat.items():
        asli = hasil.info.get(segmen[i].gid, {})
        hasil.info[segmen[j].gid] = {
            "grup": asli.get("grup", segmen[i].gid), "nama_grup": asli.get("nama_grup", segmen[i].nama),
            "fungsi": asli.get("fungsi", FUNGSI_UTAMA), "urut": 0, "n": asli.get("n", 1), "peran": "duplikat",
            "duplikat": segmen[i].gid, "nama_duplikat": segmen[i].nama,
        }
    hasil.ringkasan = {
        "objek": n,
        "fisik": len(grup),
        "per_fungsi": per_fungsi,
        "digabung": len(aktif) - len(grup),
        "duplikat": len(duplikat),
        "contoh_gabung": contoh_gabung,
        "contoh_fungsi": contoh_fungsi,
        "contoh_duplikat": [f"{segmen[j].nama} (menumpuk dengan {segmen[i].nama})" for j, i in list(duplikat.items())[:3]],
        "tumpang": len(tumpang),
        "volume_tumpang": sum(v for _n, v in tumpang),
        "contoh_tumpang": [nama for nama, _v in tumpang[:3]],
    }
    return hasil


def teks_ringkasan(r: dict) -> str:
    """'16 kolom struktur utama, 2 kolom kanopi / carport / teras; 36 objek IfcColumn: 18 segmen ...'."""
    if not r or not r.get("objek"):
        return ""
    bagian = [f"{n} {LABEL_FUNGSI[f].lower()}" for f, n in r["per_fungsi"].items() if n]
    teks = ", ".join(bagian) or "0 kolom"
    rinci = []
    if r["digabung"]:
        rinci.append(f"{r['digabung']} segmen (pedestal / potongan kolom) digabung dengan kolom di atasnya, "
                     f"mis. {r['contoh_gabung'][0]}")
    if r["duplikat"]:
        rinci.append(f"{r['duplikat']} objek ganda tidak dihitung ulang, mis. {r['contoh_duplikat'][0]}")
    if r.get("tumpang"):
        rinci.append(f"{r['tumpang']} sambungan segmen saling menumpuk ({r['volume_tumpang']:.3f} m³ terhitung dua kali, "
                     f"mis. {r['contoh_tumpang'][0]}; rapikan di model bila perlu)".replace(".", ",", 1))
    if rinci:
        teks += f" ({r['objek']} objek IfcColumn: " + "; ".join(rinci) + ")"
    return teks


# ---------------------------------------------------------------- pembacaan dari model IFC


def _lantai(entity):
    import ifcopenshell.util.element as ue

    node = entity
    for _ in range(12):
        induk = ue.get_container(node) or ue.get_aggregate(node)
        if induk is None:
            return None
        if induk.is_a("IfcBuildingStorey"):
            return induk
        node = induk
    return None


def _teks(entity) -> str:
    import ifcopenshell.util.element as ue

    tipe = ue.get_type(entity)
    return " ".join(x for x in (entity.Name, getattr(tipe, "Name", None), getattr(entity, "ObjectType", None),
                                entity.Description) if x)


def _load_bearing(entity):
    import ifcopenshell.util.element as ue

    for nama, isi in ue.get_psets(entity).items():
        if nama.endswith("ColumnCommon") and isi.get("LoadBearing") is not None:
            return bool(isi["LoadBearing"])
    return None


def baca_model(model) -> tuple:
    """(segmen kolom, dinding per lantai, elevasi lantai dasar) dari model IFC (geometri koordinat dunia)."""
    import os

    import ifcopenshell.geom as geom
    import ifcopenshell.util.shape as shape_util
    import ifcopenshell.util.unit as unit_util

    kolom = model.by_type("IfcColumn")
    if not kolom:
        return [], {}, None
    walls = model.by_type("IfcWall")
    kotak = {}
    st = geom.settings()
    st.set("use-world-coords", True)
    it = geom.iterator(st, model, max(1, min(os.cpu_count() or 1, 8)), include=kolom + walls)
    if it.initialize():
        while True:
            sh = it.get()
            mn, mx = shape_util.get_bbox(shape_util.get_vertices(sh.geometry))
            kotak[sh.guid] = tuple(float(v) for v in (*mn, *mx))
            if not it.next():
                break
    skala = unit_util.calculate_unit_scale(model)
    lantai_elev, berisi = {}, set()
    segmen = []
    for e in kolom:
        st_ = _lantai(e)
        nama_lantai = st_.Name if st_ is not None else None
        if st_ is not None:
            lantai_elev[nama_lantai] = (st_.Elevation or 0.0) * skala
            berisi.add(nama_lantai)
        if e.GlobalId not in kotak:
            continue
        segmen.append(Segmen(e.GlobalId, e.Name or e.GlobalId, kotak[e.GlobalId], _teks(e), _load_bearing(e),
                             nama_lantai))
    dinding = {}
    for w in walls:
        st_ = _lantai(w)
        if st_ is None or w.GlobalId not in kotak:
            continue
        lantai_elev[st_.Name] = (st_.Elevation or 0.0) * skala
        berisi.add(st_.Name)
        dinding.setdefault(st_.Name, []).append(kotak[w.GlobalId])
    return segmen, dinding, elevasi_dasar(lantai_elev, berisi)


def analisis_model(model) -> HasilKolom:
    segmen, dinding, elev = baca_model(model)
    return analisis(segmen, dinding, elev)
