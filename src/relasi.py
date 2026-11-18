"""
Relasi geometri antar-elemen (koordinat dunia) untuk aturan yang bergantung pada letak elemen lain:

- balok: panjang alas yang ditopang pasangan dinding di bawahnya (balok dicor di atas dinding, mis. ring
  balok / balok praktis: alasnya dinding, tidak perlu bekisting alas) dan tebal pelat beton yang dicor
  bersama balok di tiap sisinya (bekisting sisi itu = h − t). Sisi tanpa pelat (sisi luar balok tepi, ring
  balok di level atap) dibekisting setinggi penuh.
- fondasi: fondasi setempat (footplate, sumuran, poer, tiang) yang berada di bawah setiap kolom fisik, untuk
  pilihan jenis fondasi (rules/fondasi_kolom.py).

Semua batas memakai kotak pembatas (bounding box) sumbu-sejajar; elemen miring tidak dianalisis.
"""

import os

TOL_Z = 0.05  # m, puncak dinding / pelat dianggap rata dengan alas / puncak balok
TOL_DENAH = 0.05  # m
TUTUP_LEBAR = 0.5  # dinding menopang bila menutup >= 50% lebar balok
TEBAL_PELAT_MAKS = 0.40  # m, kotak pelat lebih tebal = pelat miring / atap, tidak dianalisis
KELAS_GEOMETRI = ("IfcColumn", "IfcWall", "IfcBeam", "IfcSlab", "IfcFooting", "IfcPile")


def kotak_dunia(model, entitas: list) -> dict:
    """{GlobalId: (xmin, ymin, zmin, xmax, ymax, zmax)} koordinat dunia, meter (iterator multi-thread)."""
    import ifcopenshell.geom as geom
    import ifcopenshell.util.shape as shape_util

    kotak = {}
    if not entitas:
        return kotak
    st = geom.settings()
    st.set("use-world-coords", True)
    it = geom.iterator(st, model, max(1, min(os.cpu_count() or 1, 8)), include=list(entitas))
    if it.initialize():
        while True:
            sh = it.get()
            mn, mx = shape_util.get_bbox(shape_util.get_vertices(sh.geometry))
            kotak[sh.guid] = tuple(float(v) for v in (*mn, *mx))
            if not it.next():
                break
    return kotak


def _gabung_interval(iv: list) -> float:
    total, akhir = 0.0, None
    for a, b in sorted(iv):
        if akhir is None or a > akhir:
            total += b - a
            akhir = b
        elif b > akhir:
            total += b - akhir
            akhir = b
    return total


def analisis_balok(balok: dict, dinding: list, pelat: list) -> dict:
    """{gid balok: {'ditopang': panjang alas di atas dinding (m), 'pelat_sisi': [t sisi 1, t sisi 2]}}.
    Pelat beton yang puncaknya rata dengan puncak balok dan menempel / menutupi sisi balok sepanjang >= 50%
    bentang dianggap dicor bersama balok pada sisi itu (t = tebal pelat; None = sisi tanpa pelat).
    balok: {gid: kotak}; dinding, pelat: [kotak]."""
    hasil = {}
    for gid, b in balok.items():
        dx, dy, tinggi = b[3] - b[0], b[4] - b[1], b[5] - b[2]
        if min(dx, dy) <= 0 or tinggi <= 0:
            continue
        a, c = (0, 1) if dx >= dy else (1, 0)  # sumbu panjang, sumbu lebar
        lebar, panjang = b[c + 3] - b[c], b[a + 3] - b[a]
        interval = []
        for w in dinding:
            if abs(w[5] - b[2]) > TOL_Z:  # puncak dinding harus rata dengan alas balok (balok di atas dinding)
                continue
            tutup = min(b[c + 3], w[c + 3]) - max(b[c], w[c])
            if tutup < TUTUP_LEBAR * lebar:
                continue
            lo, hi = max(b[a], w[a]), min(b[a + 3], w[a + 3])
            if hi > lo:
                interval.append((lo, hi))
        sisi = [[], []]  # (interval sepanjang balok, tebal) untuk sisi bawah / atas sumbu lebar
        for s in pelat:
            t = s[5] - s[2]
            if t <= 0 or t > TEBAL_PELAT_MAKS or t >= tinggi or abs(s[5] - b[5]) > TOL_Z:
                continue
            lo, hi = max(b[a], s[a]), min(b[a + 3], s[a + 3])
            if hi <= lo:
                continue
            if s[c] < b[c] + TOL_DENAH and s[c + 3] >= b[c] - TOL_DENAH:  # pelat menempel/menutupi sisi bawah
                sisi[0].append(((lo, hi), t))
            if s[c + 3] > b[c + 3] - TOL_DENAH and s[c] <= b[c + 3] + TOL_DENAH:  # sisi atas
                sisi[1].append(((lo, hi), t))
        pelat_sisi = []
        for daftar in sisi:
            if daftar and _gabung_interval([iv for iv, _t in daftar]) >= 0.5 * panjang:
                pelat_sisi.append(round(max(t for _iv, t in daftar), 4))
            else:
                pelat_sisi.append(None)
        hasil[gid] = {"ditopang": round(min(_gabung_interval(interval), panjang), 4), "pelat_sisi": pelat_sisi}
    return hasil


def fondasi_di_bawah_kolom(kolom: dict, fondasi: dict) -> dict:
    """{gid fondasi: gid grup kolom} untuk fondasi setempat yang berada tepat di bawah kolom fisik.
    kolom: {gid grup: (x, y, z_bawah)}; fondasi: {gid: kotak}."""
    hasil = {}
    for gid, f in fondasi.items():
        terbaik = None
        for grup, (x, y, z) in kolom.items():
            if not (f[0] - TOL_DENAH <= x <= f[3] + TOL_DENAH and f[1] - TOL_DENAH <= y <= f[4] + TOL_DENAH):
                continue
            if f[5] > z + 0.30:  # fondasi harus di bawah kaki kolom
                continue
            jarak = z - f[5]
            if terbaik is None or jarak < terbaik[0]:
                terbaik = (jarak, grup)
        if terbaik:
            hasil[gid] = terbaik[1]
    return hasil
