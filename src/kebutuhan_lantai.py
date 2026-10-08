"""
Rincian kebutuhan per lantai (KF-12 lanjutan): untuk setiap lantai, berapa beton, bekisting, besi,
bahan, tenaga kerja, dan alat yang dibutuhkan, seperti lampiran RAB/RAP konsultan.

Untuk satu lantai disusun:
1. Biaya per kategori pekerjaan (rekap_per_lantai).
2. Struktur beton per tipe elemen: jumlah elemen, volume beton (m³) per mutu, bekisting (m²),
   besi (kg), dan rasio besi (kg/m³) sebagai pemeriksaan kewajaran.
3. Kebutuhan besi per diameter: berat (kg, Rumus 2.33 termasuk sisa potongan 5%), panjang (m'),
   dan jumlah batang 12 m. Besi dari asumsi rasio (elemen tanpa rincian tulangan) dicatat terpisah.
4. Kebutuhan bahan, tenaga kerja, dan alat: volume pekerjaan x koefisien analisa (AHSP) setiap
   komponen, beserta harga dasarnya (belum termasuk biaya umum & keuntungan).
5. RAB rinci lantai (susun_rinci).

Lantai dikenali dari IfcBuildingStorey, berapa pun jumlahnya, urut elevasi (rab_rinci.daftar_lantai).
"""

import math
import re

from rab_rinci import TANPA_LANTAI, daftar_lantai, rekap_per_lantai, susun_rinci
from rules.penulangan import NAMA_KELOMPOK, PANJANG_BATANG, URUTAN, berat_per_m, jenis_baja, label_d, label_tipe

BERAT_ZAK_SEMEN = 50  # kg per zak
# Rentang wajar rasio besi beton bertulang rumah tinggal (kg/m³). Di luar rentang ini angka ditandai
# "periksa": biasanya dimensi elemen di model IFC tidak wajar atau konfigurasi tulangan perlu dicek.
RASIO_WAJAR = (40.0, 350.0)
AWALAN_BETON = ("BTN.", "LTK.")
AWALAN_STRUKTUR = ("BTN.", "BSK.", "BSI.", "LTK.")
TIPE_SUMBER_DAYA = (("bahan", "Bahan / Material"), ("upah", "Tenaga Kerja"), ("alat", "Peralatan"))
_MUTU = re.compile(r"f'c\s*([\d.,]+)\s*MPa", re.IGNORECASE)


def _kelompok_kode(kode: str) -> str:
    """'BTN.KOLOM' -> 'KOLOM', 'BSI.PELAT.U' -> 'PELAT', 'LTK.FONDASI' -> 'LANTAI_KERJA'."""
    if kode.startswith("LTK."):
        return "LANTAI_KERJA"
    bagian = kode.split(".")
    return bagian[1] if len(bagian) > 1 else kode


def rasio_wajar(rasio) -> bool:
    return rasio is None or RASIO_WAJAR[0] <= rasio <= RASIO_WAJAR[1]


def mutu_beton(nama_pekerjaan: str) -> str:
    m = _MUTU.search(nama_pekerjaan or "")
    return f"f'c {m.group(1)} MPa" if m else "beton masif"


# ---------------------------------------------------------------- struktur per tipe


def struktur_per_tipe(baris: list) -> list:
    """Beton, bekisting, dan besi per tipe elemen (atau per kelompok bila elemen tanpa tipe).
    Return [{'label', 'jumlah_elemen', 'beton', 'mutu', 'bekisting', 'besi', 'rasio', 'biaya'}]."""
    grup = {}
    for r in baris:
        kode = r.get("kode_ahsp") or ""
        if not kode.startswith(AWALAN_STRUKTUR):
            continue
        kel = _kelompok_kode(kode)
        if r.get("tipe_id") and r.get("kelompok_tipe") and kode != "BTN.SUMURAN" and not kode.startswith("LTK."):
            kunci = ("tipe", r["tipe_id"])
            label = label_tipe(r["kelompok_tipe"], r["kode_tipe"], (r["tipe_b_cm"] or 0) / 100 or None,
                               (r["tipe_h_cm"] or 0) / 100)
            urut = (URUTAN.index(r["kelompok_tipe"]) if r["kelompok_tipe"] in URUTAN else 9,
                    0, int((r.get("kode_tipe") or "X0")[1:] or 0))
        else:
            kunci = ("kelompok", kel)
            if kel == "LANTAI_KERJA":
                label = "Lantai Kerja (bawah fondasi)"
            elif kel == "SUMURAN":
                label = "Fondasi Sumuran"
            else:
                label = f"{NAMA_KELOMPOK.get(kel, kel.title())} (tanpa tipe penulangan)"
            urut = (URUTAN.index(kel) if kel in URUTAN else -1 if kel == "LANTAI_KERJA" else 9, 1, 0)
        g = grup.setdefault(kunci, {"label": label, "urut": urut, "elemen": set(), "beton": 0.0, "bekisting": 0.0,
                                   "besi": 0.0, "biaya": 0.0, "mutu": {}})
        if r.get("elemen_id"):
            g["elemen"].add(r["elemen_id"])
        v = r["volume_pekerjaan"] or 0.0
        if kode.startswith(AWALAN_BETON):
            g["beton"] += v
            m = mutu_beton(r["nama_pekerjaan"])
            g["mutu"][m] = g["mutu"].get(m, 0.0) + v
        elif kode.startswith("BSK."):
            g["bekisting"] += v
        else:
            g["besi"] += v
        g["biaya"] += r["subtotal_biaya"] or 0.0
    hasil = []
    for g in sorted(grup.values(), key=lambda g: (g["urut"], g["label"])):
        hasil.append({
            "label": g["label"],
            "jumlah_elemen": len(g["elemen"]),
            "beton": g["beton"],
            "mutu": ", ".join(sorted(g["mutu"])) or "-",
            "bekisting": g["bekisting"],
            "besi": g["besi"],
            "rasio": g["besi"] / g["beton"] if g["beton"] > 1e-9 else None,
            "biaya": g["biaya"],
        })
    return hasil


def beton_per_mutu(baris: list) -> list:
    """[{'mutu', 'volume'}]: total volume beton per mutu (f'c 20 MPa, f'c 7,5 MPa, beton masif)."""
    d = {}
    for r in baris:
        if (r.get("kode_ahsp") or "").startswith(AWALAN_BETON):
            m = mutu_beton(r["nama_pekerjaan"])
            d[m] = d.get(m, 0.0) + (r["volume_pekerjaan"] or 0.0)
    return [{"mutu": m, "volume": v} for m, v in sorted(d.items(), key=lambda x: -x[1])]


# ---------------------------------------------------------------- besi per diameter


def besi_per_diameter(baris: list) -> tuple:
    """(rincian, rasio_kg). Rincian per diameter seperti penulangan_repository.kebutuhan_besi, dihitung
    dari baris yang diberikan (mis. satu lantai). rasio_kg = besi tanpa rincian diameter (asumsi rasio)."""
    per_d, rasio = {}, 0.0
    for r in baris:
        if not (r.get("kode_ahsp") or "").startswith("BSI."):
            continue
        if r.get("diameter"):
            per_d[r["diameter"]] = per_d.get(r["diameter"], 0.0) + (r["volume_pekerjaan"] or 0.0)
        else:
            rasio += r["volume_pekerjaan"] or 0.0
    hasil = []
    for d in sorted(per_d):
        berat, wm = per_d[d], berat_per_m(d)
        panjang = berat / wm
        hasil.append({
            "diameter": d,
            "label": label_d(d),
            "jenis": jenis_baja(d),
            "berat_per_m": wm,
            "panjang": panjang,
            "berat": berat,
            "batang": math.ceil(panjang / PANJANG_BATANG - 1e-9),
        })
    return hasil, rasio


# ---------------------------------------------------------------- bahan, upah, alat (AHSP)


def _nama_sheet() -> set:
    from database.seed_data import ANALISA

    return {v[0] for v in ANALISA.values()}


def nama_dasar(nama: str, sheet: set) -> str:
    """'Pekerja (Galian Tanah)' -> 'Pekerja': sumber daya varian harga (seed_data._nama_varian)
    adalah bahan/tenaga yang sama, jadi kuantitasnya dijumlahkan."""
    m = re.match(r"^(.*) \(([^()]*)\)$", nama)
    return m.group(1) if m and m.group(2) in sheet else nama


def komponen_pekerjaan(pekerjaan_ids) -> dict:
    """{pekerjaan_id: [{'tipe', 'nama', 'satuan', 'koefisien', 'harga'}]} dari analisa harga satuan."""
    from database.estimasi_repository import _connect

    ids = sorted({int(i) for i in pekerjaan_ids})
    if not ids:
        return {}
    sheet = _nama_sheet()
    conn = _connect()
    try:
        rows = conn.execute(
            f"""SELECT k.pekerjaan_id, k.tipe, COALESCE(s.nama, k.nama_komponen) AS nama, k.satuan, k.koefisien,
                       k.harga_satuan AS harga
                FROM komponen_harga k LEFT JOIN sumber_daya s ON s.id = k.sumber_daya_id
                WHERE k.pekerjaan_id IN ({','.join('?' * len(ids))}) ORDER BY k.id""",
            ids,
        ).fetchall()
    finally:
        conn.close()
    hasil = {}
    for r in rows:
        hasil.setdefault(r["pekerjaan_id"], []).append({
            "tipe": r["tipe"], "nama": nama_dasar(" ".join(r["nama"].split()), sheet), "satuan": r["satuan"],
            "koefisien": r["koefisien"], "harga": r["harga"],
        })
    return hasil


def keterangan_sumber_daya(nama: str, satuan: str, jumlah: float) -> str:
    n = nama.lower()
    if "semen" in n and satuan.lower() == "kg":
        return f"≈ {math.ceil(jumlah / BERAT_ZAK_SEMEN - 1e-9):,} zak @ {BERAT_ZAK_SEMEN} kg".replace(",", ".")
    if satuan.lower() == "oh":
        return "orang-hari"
    return ""


def kebutuhan_sumber_daya(baris: list, komponen: dict) -> dict:
    """{'bahan': [...], 'upah': [...], 'alat': [...], 'tanpa_analisa': [nama pekerjaan]}.
    Item: {'nama', 'satuan', 'jumlah', 'harga', 'biaya', 'keterangan'}; urut biaya terbesar dulu."""
    acc = {t: {} for t, _ in TIPE_SUMBER_DAYA}
    tanpa = set()
    for r in baris:
        kom = komponen.get(r["pekerjaan_id"])
        v = r["volume_pekerjaan"] or 0.0
        if not kom:
            if v:
                tanpa.add(r["nama_pekerjaan"])
            continue
        for k in kom:
            if k["tipe"] not in acc:
                continue
            kunci = (k["nama"].lower(), k["satuan"].lower())
            d = acc[k["tipe"]].setdefault(kunci, {"nama": k["nama"], "satuan": k["satuan"], "jumlah": 0.0, "biaya": 0.0})
            d["jumlah"] += v * k["koefisien"]
            d["biaya"] += v * k["koefisien"] * k["harga"]
    hasil = {"tanpa_analisa": sorted(tanpa)}
    for tipe, _ in TIPE_SUMBER_DAYA:
        items = [d for d in acc[tipe].values() if d["jumlah"] > 1e-9]
        for d in items:
            d["harga"] = d["biaya"] / d["jumlah"] if d["jumlah"] else 0.0
            d["keterangan"] = keterangan_sumber_daya(d["nama"], d["satuan"], d["jumlah"])
        hasil[tipe] = sorted(items, key=lambda d: (-d["biaya"], d["nama"]))
    return hasil


# ---------------------------------------------------------------- per lantai


def rincian_per_lantai(baris: list, komponen: dict | None = None) -> list:
    """Rincian lengkap setiap lantai (urut elevasi). `komponen` dari komponen_pekerjaan(); bila None
    diambil dari database. Return [{'lantai', 'elevasi', 'jumlah_elemen', 'total', 'kategori',
    'struktur', 'beton_mutu', 'besi', 'besi_rasio', 'sumber_daya', 'rinci', 'baris'}]."""
    if komponen is None:
        komponen = komponen_pekerjaan(r["pekerjaan_id"] for r in baris)
    per_lantai = {}
    for r in baris:
        per_lantai.setdefault(r.get("lantai") or TANPA_LANTAI, []).append(r)
    rekap = {x["lantai"]: x for x in rekap_per_lantai(baris)}
    hasil = []
    for nama in daftar_lantai(baris):
        sub = per_lantai[nama]
        besi, rasio = besi_per_diameter(sub)
        hasil.append({
            **rekap[nama],
            "struktur": struktur_per_tipe(sub),
            "beton_mutu": beton_per_mutu(sub),
            "besi": besi,
            "besi_rasio": rasio,
            "sumber_daya": kebutuhan_sumber_daya(sub, komponen),
            "rinci": susun_rinci(sub),
            "baris": sub,
        })
    return hasil


def ringkas_lantai(x: dict) -> dict:
    """Angka kunci satu lantai untuk tabel ringkasan: beton (m³), bekisting (m²), besi (kg)."""
    s = x["struktur"]
    return {
        "beton": sum(g["beton"] for g in s),
        "bekisting": sum(g["bekisting"] for g in s),
        "besi": sum(g["besi"] for g in s),
    }


def matriks_lantai(rincian: list, kunci: str) -> list:
    """Tabel silang kebutuhan x lantai untuk export: kunci 'besi' (per diameter) atau 'bahan'.
    Return [{'label', 'satuan', 'per_lantai': [nilai per lantai sesuai urutan rincian], 'total'}]."""
    baris = {}
    for i, x in enumerate(rincian):
        if kunci == "besi":
            sumber = [(f"{k['label']} {k['jenis']}", "kg", k["berat"], k["diameter"]) for k in x["besi"]]
            if x["besi_rasio"] > 1e-9:
                sumber.append(("Tanpa rincian diameter (asumsi rasio)", "kg", x["besi_rasio"], 999.0))
        else:
            sumber = [(d["nama"], d["satuan"], d["jumlah"], d["biaya"]) for d in x["sumber_daya"][kunci]]
        for label, satuan, nilai, bobot in sumber:
            b = baris.setdefault((label, satuan), {"label": label, "satuan": satuan,
                                                  "per_lantai": [0.0] * len(rincian), "_urut": 0.0})
            b["per_lantai"][i] += nilai
            b["_urut"] = bobot if kunci == "besi" else b["_urut"] - bobot  # diameter naik / biaya terbesar dulu
    hasil = sorted(baris.values(), key=lambda b: (b.pop("_urut"), b["label"]))
    for b in hasil:
        b["total"] = sum(b["per_lantai"])
    return hasil


# ---------------------------------------------------------------- penutup bangunan


def pekerjaan_lantai(baris: list) -> list:
    """Volume tiap pekerjaan di satu lantai, urut kategori: [{'kategori', 'items': [{'nama', 'volume',
    'satuan', 'jumlah'}]}]. Pembesian rinci digabung per pekerjaan (rinciannya ada di besi per diameter)."""
    from rab_rinci import urutan_kategori

    kat = {}
    for r in baris:
        d = kat.setdefault(r["kategori"], {}).setdefault(r["pekerjaan_id"], {
            "nama": r["nama_pekerjaan"], "satuan": r["satuan"], "volume": 0.0, "jumlah": 0.0})
        d["volume"] += r["volume_pekerjaan"] or 0.0
        d["jumlah"] += r["subtotal_biaya"] or 0.0
    return [{"kategori": k, "items": sorted(kat[k].values(), key=lambda d: d["nama"])}
            for k in sorted(kat, key=urutan_kategori)]


def penutup_lantai(x: dict) -> list:
    """Unsur penutup bangunan di lantai ini: [(jenis, uraian)] untuk dak beton, atap, dan plafon."""
    hasil = []
    dak = [g for g in x["struktur"] if g["label"].startswith(NAMA_KELOMPOK["DAK"])]
    if dak:
        hasil.append(("Dak beton", ", ".join(g["label"] for g in dak)
                      + f" ({sum(g['beton'] for g in dak):,.2f} m³)".replace(",", "X").replace(".", ",").replace("X", ".")))
    for kategori, jenis in (("Atap", "Atap"), ("Plafon", "Plafon")):
        items = next((k["items"] for k in pekerjaan_lantai(x["baris"]) if k["kategori"] == kategori), [])
        if items:
            hasil.append((jenis, "; ".join(
                f"{d['nama']} {d['volume']:,.2f} {d['satuan']}".replace(",", "X").replace(".", ",").replace("X", ".")
                for d in items)))
    return hasil


def penutup_bangunan(rincian: list) -> tuple:
    """(lantai, [(jenis, uraian)]) untuk lantai teratas yang memuat atap atau dak beton, ditambah plafon
    bila ada di lantai itu. Bila model tidak punya atap/dak, dipakai lantai teratas yang punya plafon.
    (None, []) bila tidak ditemukan sama sekali."""
    for syarat in (("Atap", "Dak beton"), ("Plafon",)):
        for x in reversed(rincian):
            unsur = penutup_lantai(x)
            if any(j in syarat for j, _ in unsur):
                return x["lantai"], unsur
    return None, []
