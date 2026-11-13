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

from bahan_berulang import jumlah_pakai, pakai_komponen
from database.material import kode_dasar
from rab_rinci import TANPA_LANTAI, daftar_lantai, rekap_per_lantai, susun_rinci, urutan_kategori
from rules.penulangan import NAMA_KELOMPOK, PANJANG_BATANG, URUTAN, berat_per_m, jenis_baja, label_d, label_tipe
from setara import (  # noqa: F401 (BERAT_ZAK_*, rumus_zak, teks_kemasan dipakai halaman & export)
    BERAT_ZAK_MORTAR,
    BERAT_ZAK_SEMEN,
    beli_baja,
    jumlah_beli,
    sebaran_baja,
    rumus_zak,
    setara,
    setara_rinci,
    teks_kemasan,
    tulangan,
)

# Rentang wajar rasio besi beton bertulang rumah tinggal (kg/m³). Di luar rentang ini angka ditandai
# "periksa": biasanya dimensi elemen di model IFC tidak wajar atau konfigurasi tulangan perlu dicek.
RASIO_WAJAR = (40.0, 350.0)
AWALAN_BETON = ("BTN.", "LTK.")
AWALAN_STRUKTUR = ("BTN.", "BSK.", "BSI.", "LTK.")
TIPE_SUMBER_DAYA = (("bahan", "Bahan / Material"), ("upah", "Tenaga Kerja"), ("alat", "Peralatan"))
_MUTU = re.compile(r"f'c\s*([\d.,]+)\s*MPa", re.IGNORECASE)
_MUTU_K = re.compile(r"\bK\s*-?\s*(\d{3})\b")


def _kelompok_kode(kode: str) -> str:
    """'BTN.KOLOM' -> 'KOLOM', 'BSI.PELAT.U' -> 'PELAT', 'LTK.FONDASI' -> 'LANTAI_KERJA',
    'BTN.KOLOM~rm25' (pilihan material) -> 'KOLOM'."""
    if kode.startswith("LTK."):
        return "LANTAI_KERJA"
    bagian = kode_dasar(kode).split(".")
    return bagian[1] if len(bagian) > 1 else kode


def rasio_wajar(rasio) -> bool:
    return rasio is None or RASIO_WAJAR[0] <= rasio <= RASIO_WAJAR[1]


def mutu_beton(nama_pekerjaan: str) -> str:
    """Mutu beton dari nama pekerjaan dalam K: 'Beton Kolom K-250' -> 'K-250'; nama lama 'f'c 20 MPa' -> 'K-250'."""
    from database.material import mutu_k

    m = _MUTU_K.search(nama_pekerjaan or "")
    if m:
        return f"K-{m.group(1)}"
    m = _MUTU.search(nama_pekerjaan or "")
    return f"K-{mutu_k(float(m.group(1).replace(',', '.')))}" if m else "beton masif"


# ---------------------------------------------------------------- struktur per tipe


def label_grup_struktur(r: dict) -> tuple:
    """(kunci, label, urutan) kelompok struktur satu baris hasil: per tipe penulangan (Kolom K1 (20/25))
    atau per kelompok elemen bila tanpa tipe (Lantai Kerja, Fondasi Sumuran, Tangga Beton, ...)."""
    kode = r.get("kode_ahsp") or ""
    kel = _kelompok_kode(kode)
    if r.get("tipe_id") and r.get("kelompok_tipe") and kode != "BTN.SUMURAN" and not kode.startswith("LTK."):
        label = label_tipe(r["kelompok_tipe"], r["kode_tipe"], (r.get("tipe_b_cm") or 0) / 100 or None,
                           (r.get("tipe_h_cm") or 0) / 100)
        urut = (URUTAN.index(r["kelompok_tipe"]) if r["kelompok_tipe"] in URUTAN else 9,
                0, int((r.get("kode_tipe") or "X0")[1:] or 0))
        return ("tipe", r["tipe_id"]), label, urut
    if kel == "CAKAR":
        return ("kelompok", kel), "Fondasi Cakar Ayam (pelat + pipa)", (-1, 1, 0)
    if kel == "LANTAI_KERJA":
        label = "Lantai Kerja / Rabat (K-100)"
    elif kel == "SUMURAN":
        label = "Fondasi Sumuran"
    elif kel == "TANGGA":
        label = "Tangga Beton"
    else:
        label = f"{NAMA_KELOMPOK.get(kel, kel.title())} (tanpa tipe penulangan)"
    urut = (URUTAN.index(kel) if kel in URUTAN else -1 if kel == "LANTAI_KERJA" else 9, 1, 0)
    return ("kelompok", kel), label, urut


def struktur_per_tipe(baris: list) -> list:
    """Beton, bekisting, dan besi per tipe elemen (atau per kelompok bila elemen tanpa tipe).
    Return [{'label', 'jumlah_elemen', 'beton', 'mutu', 'bekisting', 'besi', 'rasio', 'biaya'}]."""
    grup = {}
    for r in baris:
        kode = r.get("kode_ahsp") or ""
        if not kode.startswith(AWALAN_STRUKTUR):
            continue
        kunci, label, urut = label_grup_struktur(r)
        g = grup.setdefault(kunci, {"label": label, "urut": urut, "elemen": set(), "beton": 0.0, "bekisting": 0.0,
                                   "besi": 0.0, "biaya": 0.0, "mutu": {}})
        if r.get("elemen_id"):
            g["elemen"].add(r.get("kolom_grup") or r["elemen_id"])  # pedestal + kolom = satu kolom
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
    """[{'mutu', 'volume'}]: total volume beton per mutu (K-250, K-100, beton masif)."""
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
    """{pekerjaan_id: [{'tipe', 'nama', 'satuan', 'koefisien', 'harga', 'pakai'}]} dari analisa harga satuan.
    'pakai' = berapa kali bahan itu dipakai (bahan bekisting pada analisa "3 kali pakai": 3), 0 = habis pakai."""
    from database.estimasi_repository import _connect

    ids = sorted({int(i) for i in pekerjaan_ids})
    if not ids:
        return {}
    sheet = _nama_sheet()
    conn = _connect()
    try:
        rows = conn.execute(
            f"""SELECT k.pekerjaan_id, k.tipe, COALESCE(s.nama, k.nama_komponen) AS nama, k.satuan, k.koefisien,
                       k.harga_satuan AS harga, s.merk AS merk
                FROM komponen_harga k LEFT JOIN sumber_daya s ON s.id = k.sumber_daya_id
                WHERE k.pekerjaan_id IN ({','.join('?' * len(ids))}) ORDER BY k.id""",
            ids,
        ).fetchall()
        pakai = {r["id"]: jumlah_pakai(f"{r['nama_pekerjaan']} {r['catatan'] or ''}") for r in conn.execute(
            f"SELECT id, nama_pekerjaan, catatan FROM pekerjaan WHERE id IN ({','.join('?' * len(ids))})", ids)}
    finally:
        conn.close()
    hasil = {}
    for r in rows:
        nama = nama_dasar(" ".join(r["nama"].split()), sheet)
        hasil.setdefault(r["pekerjaan_id"], []).append({
            "tipe": r["tipe"], "nama": nama, "satuan": r["satuan"], "koefisien": r["koefisien"], "harga": r["harga"],
            "pakai": pakai_komponen(nama, pakai.get(r["pekerjaan_id"], 0)) if r["tipe"] == "bahan" else 0,
            "merk": (r["merk"] or "").strip(),
        })
    return hasil


def keterangan_sumber_daya(nama: str, satuan: str, jumlah: float, besi: dict | None = None,
                           tipe: str = "bahan") -> str:
    """Kolom SETARA: satuan beli di lapangan (zak, batang 12 m, m³, rol, jeriken, pail, dus, ...); lihat setara.py.
    `besi` = {diameter: berat kg} penulangan baris yang sama, untuk mengubah baja tulangan kg -> batang."""
    return setara(nama, satuan, jumlah, besi, tipe)


def kebutuhan_sumber_daya(baris: list, komponen: dict) -> dict:
    """{'bahan': [...], 'upah': [...], 'alat': [...], 'tanpa_analisa': [nama pekerjaan]}.
    Item: {'nama', 'satuan', 'jumlah', 'harga', 'biaya', 'keterangan', 'pekerjaan', 'lantai'}; urut biaya
    terbesar dulu. 'pekerjaan' = {nama pekerjaan: {'volume', 'satuan', 'koefisien', 'jumlah', 'pakai'}} dan 'lantai' =
    {lantai: jumlah}: asal kebutuhan itu (mis. semen dari pasangan bata, plesteran, dan acian).
    Bagian yang dipakai berulang (kayu / triplek / dolken bekisting): 'jumlah_berulang', 'biaya_berulang',
    'lantai_berulang', dan 'pakai' (berapa kali dipakai); lihat pisah_berulang()."""
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
            d = acc[k["tipe"]].setdefault(kunci, {"nama": k["nama"], "satuan": k["satuan"], "jumlah": 0.0, "biaya": 0.0,
                                                  "pekerjaan": {}, "lantai": {}, "jumlah_berulang": 0.0,
                                                  "biaya_berulang": 0.0, "lantai_berulang": {}, "pakai": 0,
                                                  "merk": ""})
            if k.get("merk") and not d["merk"]:
                d["merk"] = k["merk"]
            jumlah = v * k["koefisien"]
            d["jumlah"] += jumlah
            d["biaya"] += jumlah * k["harga"]
            pakai = k.get("pakai") or 0
            p = d["pekerjaan"].setdefault(r["nama_pekerjaan"], {"volume": 0.0, "satuan": r.get("satuan") or "",
                                                                "koefisien": k["koefisien"], "jumlah": 0.0,
                                                                "pakai": pakai})
            p["volume"] += v
            p["jumlah"] += jumlah
            lt = r.get("lantai") or TANPA_LANTAI
            d["lantai"][lt] = d["lantai"].get(lt, 0.0) + jumlah
            if pakai:
                d["jumlah_berulang"] += jumlah
                d["biaya_berulang"] += jumlah * k["harga"]
                d["lantai_berulang"][lt] = d["lantai_berulang"].get(lt, 0.0) + jumlah
                d["pakai"] = max(d["pakai"], pakai)
    hasil = {"tanpa_analisa": sorted(tanpa)}
    besi = {}  # sebaran diameter penulangan baris ini: baja tulangan kg -> batang per diameter
    for r in baris:
        if (r.get("kode_ahsp") or "").startswith("BSI.") and r.get("diameter"):
            besi[r["diameter"]] = besi.get(r["diameter"], 0.0) + (r["volume_pekerjaan"] or 0.0)
    for tipe, _ in TIPE_SUMBER_DAYA:
        items = [d for d in acc[tipe].values() if d["jumlah"] > 1e-9]
        for d in items:
            d["harga"] = d["biaya"] / d["jumlah"] if d["jumlah"] else 0.0
            _isi_setara(d, besi, tipe)
        hasil[tipe] = sorted(items, key=lambda d: (-d["biaya"], d["nama"]))
    hasil["besi"] = besi
    return hasil


def _isi_setara(d: dict, besi: dict | None, tipe: str = "bahan") -> None:
    """Setara dan, untuk bahan, kemasan beli: 'kemasan' [Kemasan], 'jumlah_beli' (satuan analisa), 'biaya_beli'."""
    d["keterangan"], kemasan = setara_rinci(d["nama"], d["satuan"], d["jumlah"], besi, tipe)
    if tipe == "bahan":
        d["kemasan"] = kemasan
        d["jumlah_beli"] = jumlah_beli(kemasan) if kemasan else d["jumlah"]
        d["biaya_beli"] = d["jumlah_beli"] * d["harga"]


def pisah_berulang(items: list, besi: dict | None = None) -> tuple:
    """(bahan habis pakai, bahan dipakai berulang) dari item kebutuhan_sumber_daya()['bahan']. Bahan yang dipakai di
    kedua jenis pekerjaan (mis. kaso 5/7 untuk bekisting dan rangka plafon) dibagi dua baris; setara dihitung ulang.
    Item berulang memuat 'pakai' (n kali) dan 'sekali_pakai' (kebutuhan bila tanpa pemakaian ulang = jumlah × n)."""
    habis, ulang = [], []
    for d in items:
        jb = d.get("jumlah_berulang") or 0.0
        if jb <= 1e-9:
            habis.append(d)
            continue
        if jb >= d["jumlah"] - 1e-9:
            ulang.append({**d, "sekali_pakai": d["jumlah"] * d["pakai"]})
            continue
        for berulang, daftar in ((False, habis), (True, ulang)):
            jumlah = jb if berulang else d["jumlah"] - jb
            biaya = d["biaya_berulang"] if berulang else d["biaya"] - d["biaya_berulang"]
            lantai = dict(d["lantai_berulang"]) if berulang else {
                lt: j - d["lantai_berulang"].get(lt, 0.0) for lt, j in d["lantai"].items()
                if j - d["lantai_berulang"].get(lt, 0.0) > 1e-9}
            x = {**d, "jumlah": jumlah, "biaya": biaya, "harga": biaya / jumlah if jumlah else 0.0, "lantai": lantai,
                 "pekerjaan": {n: p for n, p in d["pekerjaan"].items() if bool(p.get("pakai")) == berulang},
                 "jumlah_berulang": jumlah if berulang else 0.0, "biaya_berulang": biaya if berulang else 0.0,
                 "lantai_berulang": lantai if berulang else {}, "pakai": d["pakai"] if berulang else 0}
            _isi_setara(x, besi)
            if berulang:
                x["sekali_pakai"] = jumlah * d["pakai"]
            daftar.append(x)
    return (sorted(habis, key=lambda d: (-d["biaya"], d["nama"])),
            sorted(ulang, key=lambda d: (-d["biaya"], d["nama"])))


# ---------------------------------------------------------------- per tahap & per item pekerjaan


def _total(kb: dict) -> dict:
    return {
        "biaya": sum(d["biaya"] for t, _ in TIPE_SUMBER_DAYA for d in kb.get(t, [])),
        "biaya_bahan": sum(d["biaya"] for d in kb.get("bahan", [])),
        "biaya_beli": sum(d.get("biaya_beli", d["biaya"]) for d in kb.get("bahan", [])),
        "oh": sum(d["jumlah"] for d in kb.get("upah", []) if d["satuan"].lower() == "oh"),
    }


def kebutuhan_per_tahap(baris: list, komponen: dict, per_lantai: bool = True) -> list:
    """Kebutuhan bahan, tenaga, dan alat per tahap pekerjaan (kategori RAB: Persiapan, Tanah, Fondasi, Beton, ...)
    dan, bila `per_lantai`, per lantai di dalamnya. Urutan = urutan pelaksanaan: tahap menurut urutan RAB, lantai dari
    terbawah. Kemasan beli dihitung per kelompok (satu kali pengiriman per tahap & lantai), sehingga jumlah beli
    seluruh kelompok dapat sedikit lebih besar daripada pembelian sekaligus untuk seluruh proyek.
    Return [{'tahap', 'nomor', 'lantai' (None bila tidak per lantai), 'baris', 'sumber_daya', 'biaya',
    'biaya_bahan', 'biaya_beli', 'oh'}]."""
    urut_lantai = {lt: i for i, lt in enumerate(daftar_lantai(baris))}
    grup = {}
    for r in baris:
        lt = (r.get("lantai") or TANPA_LANTAI) if per_lantai else None
        grup.setdefault((r.get("kategori") or "Lain-lain", lt), []).append(r)
    tahap = sorted({k[0] for k in grup}, key=urutan_kategori)
    hasil = []
    for k in sorted(grup, key=lambda k: (urutan_kategori(k[0]), urut_lantai.get(k[1], -1))):
        kb = kebutuhan_sumber_daya(grup[k], komponen)
        hasil.append({"tahap": k[0], "nomor": tahap.index(k[0]) + 1, "lantai": k[1], "baris": grup[k],
                      "sumber_daya": kb, **_total(kb)})
    return hasil


def jadwal_pengadaan(kelompok: list) -> list:
    """Pembelian bahan per kelompok kebutuhan_per_tahap() berurutan, dengan sisa stok berpindah: kelompok berikutnya
    hanya membeli kekurangannya (kemasan utuh), sisa kemasan dipakai tahap berikutnya. Stok baja tulangan dihitung
    per diameter (sisa D16 tidak dapat menggantikan D13). Return per kelompok
    [{'nama', 'satuan', 'kebutuhan', 'stok_awal', 'kemasan', 'dibeli', 'sisa', 'harga', 'biaya_beli', 'merk',
    'keterangan'}] (urut biaya beli terbesar), dengan urutan kelompok sama."""
    stok = {}
    hasil = []
    for g in kelompok:
        besi = g["sumber_daya"].get("besi")
        baris_g = []
        for d in g["sumber_daya"]["bahan"]:
            kunci = (d["nama"].lower(), d["satuan"].lower())
            if tulangan(d["nama"]) and d["satuan"].lower() == "kg":  # stok per diameter
                awal, kemasan = 0.0, []
                for dia, bagian in sebaran_baja(d["nama"], besi)[0].items():
                    perlu = d["jumlah"] * bagian
                    ada = stok.get((*kunci, dia), 0.0)
                    awal += ada
                    k = beli_baja(dia, perlu - ada) if perlu - ada > 1e-9 else None
                    if k:
                        kemasan.append(k)
                    stok[(*kunci, dia)] = ada + (k.jumlah * k.isi if k else 0.0) - perlu
                dibeli = jumlah_beli(kemasan)
                stok[kunci] = awal + dibeli - d["jumlah"]
            else:
                awal = stok.get(kunci, 0.0)
                kurang = d["jumlah"] - awal
                kemasan = setara_rinci(d["nama"], d["satuan"], kurang, besi)[1] if kurang > 1e-9 else []
                dibeli = jumlah_beli(kemasan) if kemasan else 0.0
                stok[kunci] = awal + dibeli - d["jumlah"]
            baris_g.append({"nama": d["nama"], "satuan": d["satuan"], "kebutuhan": d["jumlah"], "stok_awal": awal,
                            "kemasan": kemasan, "dibeli": dibeli, "sisa": stok[kunci], "harga": d["harga"],
                            "biaya_beli": dibeli * d["harga"], "merk": d.get("merk") or "",
                            "keterangan": d.get("keterangan") or ""})
        hasil.append(sorted(baris_g, key=lambda x: (-x["biaya_beli"], x["nama"])))
    return hasil


def kebutuhan_per_pekerjaan(baris: list, komponen: dict) -> list:
    """Bahan, tenaga, dan alat untuk setiap item pekerjaan RAB (urutan sama dengan RAB: kategori lalu nama).
    Return [{'kategori', 'nomor', 'items': [{'pekerjaan_id', 'kode', 'nama', 'satuan', 'volume', 'jumlah_rab',
    'koefisien': {(tipe, nama, satuan): koef}, 'sumber_daya', 'biaya', ...}], 'total_rab'}]."""
    per_pekerjaan = {}
    for r in baris:
        d = per_pekerjaan.setdefault(r["pekerjaan_id"], {
            "pekerjaan_id": r["pekerjaan_id"], "kategori": r.get("kategori") or "Lain-lain",
            "kode": r.get("kode_ahsp") or "", "nama": r["nama_pekerjaan"], "satuan": r.get("satuan") or "",
            "volume": 0.0, "jumlah_rab": 0.0, "baris": []})
        d["volume"] += r["volume_pekerjaan"] or 0.0
        d["jumlah_rab"] += r.get("subtotal_biaya") or 0.0
        d["baris"].append(r)
    per_kategori = {}
    for d in per_pekerjaan.values():
        kom = komponen.get(d["pekerjaan_id"]) or []
        d["koefisien"] = {(k["tipe"], k["nama"].lower(), k["satuan"].lower()): k["koefisien"] for k in kom}
        d["sumber_daya"] = kebutuhan_sumber_daya(d["baris"], komponen)
        d.update(_total(d["sumber_daya"]))
        per_kategori.setdefault(d["kategori"], []).append(d)
    return [{"kategori": k, "nomor": i, "items": sorted(per_kategori[k], key=lambda x: x["nama"]),
             "total_rab": sum(x["jumlah_rab"] for x in per_kategori[k])}
            for i, k in enumerate(sorted(per_kategori, key=urutan_kategori), 1)]


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


# ---------------------------------------------------------------- RAB lantai gaya RAP + backup volume

# Judul bagian mengikuti penulisan RAP/RAB konsultan (mis. RAP SMK N 6 Bandung: "I. PEK. TANAH",
# "II. PEKERJAAN BETON", ... "VI. PEKERJAAN KUDA-KUDA DAN ATAP", "VII. PEKERJAAN PENGECATAN").
JUDUL_KATEGORI = {
    "Persiapan": "PEKERJAAN PERSIAPAN",
    "Tanah": "PEKERJAAN TANAH",
    "Fondasi": "PEKERJAAN FONDASI",
    "Beton": "PEKERJAAN BETON",
    "Dinding": "PEKERJAAN DINDING",
    "Lantai": "PEKERJAAN LANTAI / KERAMIK",
    "Tangga & Railing": "PEKERJAAN TANGGA DAN RAILING",
    "Pintu & Jendela": "PEKERJAAN PINTU DAN JENDELA",
    "Atap": "PEKERJAAN KUDA-KUDA DAN ATAP",
    "Plafon": "PEKERJAAN PLAFON",
    "Cat": "PEKERJAAN PENGECATAN",
    "Air Limbah": "PEKERJAAN SANITASI / AIR LIMBAH",
}


def judul_kategori(kategori: str) -> str:
    return JUDUL_KATEGORI.get(kategori, f"PEKERJAAN {kategori.upper()}")


def _nama_elemen_bersih(nama) -> str:
    """'Basic Wall:Generic - 200mm:347125' -> 'Basic Wall:Generic - 200mm' (id unik Revit dibuang)."""
    nama = re.sub(r":\d+$", "", (nama or "-").strip())
    return nama if len(nama) <= 48 else nama[:47] + "…"


def backup_volume(rows: list) -> list:
    """BackUp Volume seperti lampiran RAB: elemen dengan nama & dimensi sama digabung.
    Return [{'uraian', 'panjang', 'lebar', 'tinggi', 'luas', 'unit', 'per_unit', 'volume', 'rumus'}],
    volume terbesar dulu. per_unit = volume pekerjaan satu elemen; volume = per_unit x unit."""
    grup = {}
    for r in rows:
        t = r.get("tinggi") or r.get("tebal")
        kunci = (_nama_elemen_bersih(r.get("nama_elemen")), *(round(v, 3) if v else None for v in
                 (r.get("panjang"), r.get("lebar"), t, r.get("luas"))), round(r["volume_pekerjaan"] or 0.0, 4))
        g = grup.setdefault(kunci, {
            "uraian": kunci[0], "panjang": r.get("panjang"), "lebar": r.get("lebar"), "tinggi": t,
            "luas": r.get("luas"), "unit": 0, "per_unit": r["volume_pekerjaan"] or 0.0, "volume": 0.0,
            "rumus": r.get("rumus") or "",
        })
        g["unit"] += 1
        g["volume"] += r["volume_pekerjaan"] or 0.0
    for g in grup.values():  # rata-rata kelompok: unit x per_unit = volume tepat (tanpa selisih pembulatan)
        g["per_unit"] = g["volume"] / g["unit"]
    return sorted(grup.values(), key=lambda g: (-g["volume"], g["uraian"]))


def rab_lantai(x: dict) -> list:
    """RAB satu lantai dengan susunan RAP: bagian (I. PEKERJAAN TANAH ...) -> grup tipe elemen
    (1 Kolom K1 (20/25) — 12 buah) -> item (– Beton, – Bekisting, – Tulangan utama 6 D13 ...),
    setiap item dilengkapi backup volume elemen-elemennya.
    Return [{'no', 'kategori', 'judul', 'total', 'grup': [{'no', 'judul', 'total', 'items': [{'no', 'uraian',
    'kode', 'volume', 'satuan', 'harga', 'jumlah', 'backup'}]}]}]."""
    from rab_rinci import _per_tipe, susun_rinci

    romawi = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI", "XII", "XIII", "XIV", "XV"]
    hasil = []
    for i, k in enumerate(susun_rinci(x["baris"])):
        rows_k = [r for r in x["baris"] if r["kategori"] == k["kategori"]]
        bagian = {"no": f"{romawi[i] if i < len(romawi) else i + 1}.", "kategori": k["kategori"],
                  "judul": judul_kategori(k["kategori"]), "total": k["total"], "grup": []}
        nomor = 0
        for g in k["grup"]:
            if g["judul"]:
                nomor += 1
            grup = {"no": str(nomor) if g["judul"] else "", "judul": g["judul"], "total": g["total"], "items": []}
            for it in g["items"]:
                if not g["judul"]:
                    nomor += 1
                if g["tipe_id"] is not None:
                    rows = [r for r in rows_k if _per_tipe(r) and r["tipe_id"] == g["tipe_id"]
                            and r["pekerjaan_id"] == it["pekerjaan_id"]
                            and (not it["diameter"] or r.get("uraian") == it["label"])]
                else:
                    rows = [r for r in rows_k if r["pekerjaan_id"] == it["pekerjaan_id"] and not _per_tipe(r)]
                grup["items"].append({
                    "no": "-" if g["judul"] else str(nomor), "uraian": it["label"], "kode": it["kode"],
                    "volume": it["volume"], "satuan": it["satuan"], "harga": it["harga"], "jumlah": it["jumlah"],
                    "backup": backup_volume(rows),
                })
            bagian["grup"].append(grup)
        hasil.append(bagian)
    return hasil


# ---------------------------------------------------------------- per elemen

# Urutan jenis elemen di dalam satu lantai: dari bawah (fondasi) ke atas (atap), lalu pekerjaan tambahan katalog.
JENIS_TAMBAHAN = "Pekerjaan tambahan (katalog)"


def _urutan_kelas():
    from klasifikasi import ElementType as T

    return [T.EARTHWORK, T.FOOTING, T.PILE, T.COLUMN, T.BEAM, T.SLAB, T.WALL, T.WALL_TILE, T.DOOR, T.WINDOW, T.STAIR,
            T.RAILING, T.FLOOR, T.SPACE, T.CEILING, T.ROOF]


def jenis_elemen(r: dict) -> str:
    """Label jenis elemen baris hasil ('Dinding', 'Kolom', ...); baris tanpa elemen = pekerjaan tambahan."""
    from klasifikasi import LABEL, ElementType

    if not r.get("elemen_id"):
        return JENIS_TAMBAHAN
    kelas = r.get("kelas")
    return LABEL.get(ElementType(kelas), kelas) if kelas in ElementType._value2member_map_ else (kelas or "Lainnya")


def urutan_jenis(jenis: str):
    from klasifikasi import LABEL

    urut = [LABEL.get(e, e.value) for e in _urutan_kelas()]
    return (jenis == JENIS_TAMBAHAN, urut.index(jenis) if jenis in urut else len(urut), jenis)


def kebutuhan_per_elemen(baris: list, komponen: dict) -> list:
    """Kebutuhan bahan setiap elemen IFC (mis. "Dinding A": bata, semen, pasir, acian, cat dasar, ...),
    urut lantai, jenis elemen (fondasi → atap), lalu nama elemen. Item tambahan tanpa elemen dikumpulkan dalam satu kelompok.
    Return [{'lantai', 'elemen', 'kelas', 'jenis', 'pekerjaan': [{'nama', 'volume', 'satuan', 'jumlah'}],
             'bahan': [...kebutuhan_sumber_daya bahan...], 'oh', 'total'}]."""
    urut_lantai = {nama: i for i, nama in enumerate(daftar_lantai(baris))}
    grup = {}
    for r in baris:
        kunci = r.get("elemen_id") or 0
        g = grup.setdefault(kunci, {
            "lantai": r.get("lantai") or TANPA_LANTAI,
            "elemen": r.get("nama_elemen") or ("Item tambahan (tanpa elemen model)" if not kunci else f"Elemen {kunci}"),
            "kelas": r.get("kelas") or "", "jenis": jenis_elemen(r), "baris": [],
        })
        g["baris"].append(r)
    hasil = []
    for g in grup.values():
        pek = {}
        for r in g["baris"]:
            p = pek.setdefault(r["nama_pekerjaan"], {"nama": r["nama_pekerjaan"], "volume": 0.0,
                                                     "satuan": r.get("satuan") or "", "jumlah": 0.0})
            p["volume"] += r["volume_pekerjaan"] or 0.0
            p["jumlah"] += r["subtotal_biaya"] or 0.0
        kb = kebutuhan_sumber_daya(g["baris"], komponen)
        hasil.append({
            "lantai": g["lantai"], "elemen": g["elemen"], "kelas": g["kelas"], "jenis": g["jenis"],
            "pekerjaan": list(pek.values()), "bahan": kb["bahan"],
            "oh": sum(d["jumlah"] for d in kb["upah"] if d["satuan"].lower() == "oh"),
            "total": sum(p["jumlah"] for p in pek.values()),
        })
    hasil.sort(key=lambda x: (urut_lantai.get(x["lantai"], len(urut_lantai)), urutan_jenis(x["jenis"]), x["elemen"].lower()))
    return hasil
