"""
Pilihan jenis fondasi kolom (Parameter Aturan › "Fondasi kolom dihitung sebagai"), tanpa mengubah model IFC.

0. Sesuai model IFC (bawaan): fondasi yang dimodelkan dihitung apa adanya; bila model tanpa fondasi, sumuran
   diturunkan per kolom struktur (Batasan no. 8).
1. Footplate: setiap kolom struktur di lantai dasar berfondasi telapak.
   - Footplate yang dimodelkan tetap dipakai (ukuran rencana perencana).
   - Sumuran, poer, dan tiang yang dimodelkan di bawah kolom tidak dihitung; diganti footplate turunan.
   - Kolom tanpa fondasi di model mendapat footplate turunan B × B × t (otomatis menurut jumlah lantai:
     1 lantai 0,80 × 0,80 × 0,25; 2 lantai 1,00 × 1,00 × 0,25; >= 3 lantai 1,20 × 1,20 × 0,30 m) beserta
     galian, lantai kerja, urugan kembali, tulangan (tipe fondasi bawaan), dan pedestal bila kolom model
     tidak turun sampai fondasi.
2. Cakar ayam (sistem Sedijatmo): pelat beton bertulang tipis di bawah seluruh denah lantai dasar yang dikakukan
   pipa beton ("cakar") di bawahnya.
   - Tidak dihitung: semua fondasi model (footplate, sumuran, poer, tiang, batu kali menerus), pedestal,
     aanstamping, urugan pasir & lantai kerja bawah fondasi, pelat beton lantai dasar (digantikan pelat cakar
     ayam), dan sloof (kecuali parameter "sloof tetap dihitung" = Ya).
   - Dihitung: pelat cakar ayam = luas lantai dasar di dalam selubung bangunan (pelat / rabat / penutup lantai /
     ruang; perkerasan luar seperti carport dan jalan masuk tidak termasuk) + tapak dinding lantai dasar, tebal t; pipa cakar Ø D, tebal dinding tp, panjang L: satu di bawah setiap kolom struktur dan
     tambahan sampai jarak antarpipa <= s (n = maks(n kolom, ⌈A / s²⌉)); bekisting tepi pelat di dinding luar;
     bekisting pipa dalam & luar; tulangan pelat Ø10-200 dua arah dua lapis dan pipa Ø8-200 (vertikal & cincin);
     galian pelat dan lubang pipa; tanah di dalam pipa dipadatkan kembali.
   - Urugan pasir dan rabat/lantai kerja bawah lantai tetap dihitung (menjadi alas pelat cakar ayam).
"""

import math

from . import penulangan, tanah
from .item import ItemHasil
from .parameter import (
    CAKAR_TULANGAN_PELAT,
    CAKAR_TULANGAN_PIPA,
    FONDASI_FOOTPLATE,
    FONDASI_MODEL,
    JENIS_FONDASI_KOLOM,
    ukuran_footplate,
)
from .sifat import beton, bordes, dinding_pasangan, kolom_struktur, pekerjaan_tanah, rabat, sumuran_model

SEMUA = "*"
# pekerjaan tanah model yang menjadi bagian fondasi yang diganti cakar ayam
_TANAH_FONDASI = ("FDN.AANSTAMPING", "TNH.PASIR.FONDASI", "LTK.FONDASI")


def _n(x: float, d: int = 3) -> str:
    return f"{x:,.{d}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _ganti(e: dict, kode, alasan: str) -> None:
    e.setdefault("kode_diganti", set()).update(kode if isinstance(kode, (set, tuple, list)) else {kode})
    e["alasan_diganti"] = alasan


def _info(e: dict) -> dict:
    return e.get("info_kolom") or {}




def siapkan(elemen: list, p, jumlah_lantai: int) -> dict:
    """Tandai elemen yang diganti dan item turunan sesuai pilihan jenis fondasi (diubah di tempat).
    Return ringkasan {'jenis', 'teks', ...} untuk Konteks dan peringatan."""
    jenis = p.fondasi_kolom_jenis
    for e in elemen:
        for k in ("kode_diganti", "alasan_diganti", "fondasi_pilihan", "luas_cakar", "pipa_cakar", "tepi_cakar",
                  "footplate_ukuran", "pedestal_turunan"):
            e.pop(k, None)
    if jenis == FONDASI_MODEL:
        return {"jenis": jenis, "teks": None}

    # kolom struktur di lantai dasar yang memikul fondasi (satu segmen per kolom fisik, lihat konteks)
    kolom = [e for e in elemen if e["kelas"] == "COLUMN" and e.get("di_lantai_dasar") and e.get("fondasi_kolom", True)
             and kolom_struktur(e) and not _info(e).get("duplikat")]
    per_gid = {e.get("global_id"): e for e in elemen if e.get("global_id")}
    ganti = {"fondasi": 0, "pedestal": 0, "sloof": 0, "tanah": 0, "pelat": 0}
    # relasi geometri (fondasi di bawah kolom) tersedia untuk proyek yang dibaca versi ini; proyek lama: semua fondasi
    # setempat dianggap fondasi kolom (hitung ulang dari IFC untuk pemetaan per kolom)
    ada_relasi = any(e.get("info_kolom") for e in elemen if e["kelas"] == "COLUMN")

    if jenis == FONDASI_FOOTPLATE:
        B, t, ket = ukuran_footplate(p, jumlah_lantai)
        for e in elemen:
            if e["kelas"] == "PILE" or (e["kelas"] == "FOOTING" and (sumuran_model(e) or (
                    e.get("predefined_type") or "") == "PILE_CAP") and (e.get("info_fondasi") or not ada_relasi)):
                _ganti(e, SEMUA, "diganti footplate (pilihan jenis fondasi)")
                ganti["fondasi"] += 1
        baru = 0
        ada_pad_model = any(e["kelas"] == "FOOTING" and not e.get("kode_diganti") and (
            e.get("predefined_type") or "") not in ("STRIP_FOOTING", "FOOTING_BEAM") for e in elemen)
        for e in kolom:
            pad = [g for g in _info(e).get("fondasi", []) if g in per_gid and not per_gid[g].get("kode_diganti")]
            if pad or (not ada_relasi and ada_pad_model):
                continue  # footplate rencana di model tetap dipakai
            e["fondasi_pilihan"] = "footplate"
            e["footplate_ukuran"] = (B, t, ket)
            # pedestal turunan bila kolom tidak dimodelkan turun sampai fondasi (tidak ada segmen pedestal)
            e["pedestal_turunan"] = not any(
                (x.get("info_kolom") or {}).get("peran") == "pedestal" for x in elemen
                if x.get("kolom_grup") and x.get("kolom_grup") == e.get("kolom_grup")
            )
            baru += 1
        catatan_lama = "" if ada_relasi else (" Relasi kolom–fondasi belum tersedia untuk proyek ini: lakukan "
                                               "Hitung Ulang dari IFC agar fondasi dipetakan per kolom.")
        teks = (f"Jenis fondasi kolom: footplate. {baru} kolom mendapat footplate turunan "
                f"{_n(B, 2)} × {_n(B, 2)} × {_n(t, 2)} m ({ket})"
                + (f"; {ganti['fondasi']} sumuran/poer/tiang model tidak dihitung" if ganti["fondasi"] else "")
                + "; footplate yang dimodelkan tetap dipakai." + catatan_lama)
        return {"jenis": jenis, "teks": teks, "footplate_baru": baru, **ganti}

    # ---- cakar ayam (Sedijatmo)
    for e in elemen:
        kelas, pre = e["kelas"], e.get("predefined_type") or ""
        if kelas == "PILE" or (kelas == "FOOTING" and pre != "FOOTING_BEAM"):
            _ganti(e, SEMUA, "fondasi diganti cakar ayam (pilihan jenis fondasi)")
            ganti["fondasi"] += 1
        elif not p.cakar_pakai_sloof and (
                (kelas == "FOOTING" and pre == "FOOTING_BEAM") or (kelas == "BEAM" and e.get("balok_sloof"))):
            _ganti(e, SEMUA, "sloof digantikan pelat cakar ayam")
            ganti["sloof"] += 1
        elif kelas == "COLUMN" and _info(e).get("peran") == "pedestal":
            _ganti(e, SEMUA, "pedestal tidak diperlukan: kolom berdiri di atas pelat cakar ayam")
            ganti["pedestal"] += 1
        elif kelas == "EARTHWORK" and (pekerjaan_tanah(e) in _TANAH_FONDASI or (
                not p.cakar_pakai_sloof and pekerjaan_tanah(e) == "TNH.PASIR.SLOOF")):
            _ganti(e, SEMUA, "pekerjaan tanah fondasi diganti cakar ayam")
            ganti["tanah"] += 1
    if not p.cakar_pakai_sloof:
        for e in elemen:
            if e["kelas"] == "WALL":
                e["sloof_turunan"] = None

    # luas pelat cakar ayam: lantai dasar (pelat/rabat > penutup lantai > ruang) + tapak dinding lantai dasar
    # perkerasan di luar selubung bangunan (carport, jalan masuk, area servis) tetap dihitung apa adanya
    def bidang(kelas, *syarat):
        return [e for e in elemen if e["kelas"] == kelas and e.get("di_lantai_dasar") and e.get("luas")
                and not e.get("di_luar_bangunan") and all(f(e) for f in syarat)]

    sumber = bidang("SLAB", lambda e: not bordes(e) and (beton(e) or rabat(e)))
    if not sumber:
        sumber = bidang("FLOOR")
    if not sumber:
        sumber = bidang("SPACE")
    for e in sumber:
        e["luas_cakar"] = e["luas"]
        if e["kelas"] == "SLAB" and beton(e) and not rabat(e):
            _ganti(e, {"BTN.PELAT", "BSI.PELAT", "BSK.PELAT"}, "pelat lantai dasar digantikan pelat cakar ayam")
            ganti["pelat"] += 1
    ada_luar = any(e.get("eksternal") is not None for e in elemen if e["kelas"] == "WALL")
    dinding = [e for e in elemen if e["kelas"] == "WALL" and e.get("di_lantai_dasar") and dinding_pasangan(e)
               and e.get("panjang") and e.get("tebal")]
    for e in dinding:
        e["luas_cakar"] = e["panjang"] * e["tebal"]
        e["tepi_cakar"] = bool(e.get("eksternal")) and ada_luar
    luas = sum(e["luas_cakar"] for e in sumber + dinding)

    # pipa: satu di bawah setiap kolom struktur, tambahan dibagi ke bidang lantai menurut luasnya
    for e in kolom:
        e["fondasi_pilihan"] = "cakar"
    s = p.cakar_jarak_pipa
    n_pipa = max(len(kolom), math.ceil(luas / (s * s) - 1e-9)) if luas else len(kolom)
    tambah = n_pipa - len(kolom)
    luas_sumber = sum(e["luas_cakar"] for e in sumber)
    if tambah > 0 and luas_sumber > 0:
        jatah = [(e, tambah * e["luas_cakar"] / luas_sumber) for e in sumber]
        for e, x in jatah:
            e["pipa_cakar"] = int(x)
        sisa = tambah - sum(int(x) for _e, x in jatah)
        for e, x in sorted(jatah, key=lambda z: -(z[1] - int(z[1])))[:sisa]:
            e["pipa_cakar"] += 1
    teks = (f"Jenis fondasi kolom: cakar ayam (sistem Sedijatmo). Pelat t = {_n(p.cakar_tebal_pelat, 2)} m seluas "
            f"{_n(luas, 2)} m², {n_pipa} pipa Ø{_n(p.cakar_diameter_pipa, 2)} m × {_n(p.cakar_panjang_pipa, 2)} m "
            f"({len(kolom)} di bawah kolom, jarak maks. {_n(s, 2)} m). Tidak dihitung: {ganti['fondasi']} fondasi model, "
            f"{ganti['pedestal']} pedestal, {ganti['sloof']} sloof, {ganti['tanah']} pekerjaan tanah fondasi, "
            f"{ganti['pelat']} pelat beton lantai dasar.")
    if not luas:
        teks += " Luas lantai dasar tidak terbaca: hanya pipa di bawah kolom yang dihitung."
    if not ada_relasi and any(e["kelas"] == "COLUMN" for e in elemen):
        teks += (" Relasi pedestal & selubung bangunan belum tersedia untuk proyek ini: lakukan Hitung Ulang dari IFC "
                 "agar pedestal dan perkerasan luar dikenali.")
    return {"jenis": jenis, "teks": teks, "luas": luas, "n_pipa": n_pipa, **ganti}


# ---------------------------------------------------------------- item turunan


def _pengganti(items: list) -> list:
    for it in items:
        if isinstance(it, ItemHasil):
            it.pengganti = True  # menggantikan fondasi model: tidak digugurkan oleh "model > turunan"
    return items


def _pipa(n: int, p, uraian: str) -> list:
    D, tp, L, t = p.cakar_diameter_pipa, p.cakar_tebal_pipa, p.cakar_panjang_pipa, p.cakar_tebal_pelat
    Di, Dm = D - 2 * tp, D - tp
    v = n * math.pi / 4 * (D**2 - Di**2) * L
    bsk = n * math.pi * (D + Di) * L
    d, jarak = CAKAR_TULANGAN_PIPA
    wm = penulangan.berat_per_m(d)
    n_v = math.ceil(math.pi * Dm / jarak - 1e-9)
    p_v = L + t  # tulangan vertikal masuk ke pelat
    n_c = math.floor(L / jarak + 1e-9) + 1
    p_c = math.pi * Dm + penulangan.LEWATAN * d / 1000
    berat = n * (n_v * p_v + n_c * p_c) * wm * penulangan.FAKTOR_SISA
    galian = n * math.pi / 4 * D**2 * L
    tanah_dalam = n * math.pi / 4 * Di**2 * L
    teks_n = f"{n} pipa {uraian}"
    return [
        ItemHasil("BTN.CAKAR.PIPA", v, f"V = n × π/4 × (D² − Di²) × L = {n} × π/4 × ({_n(D, 2)}² − {_n(Di, 2)}²) × "
                                       f"{_n(L, 2)} = {_n(v)} m³ ({teks_n})"),
        ItemHasil("BSK.CAKAR.PIPA", bsk, f"A = n × π × (D + Di) × L = {n} × π × ({_n(D, 2)} + {_n(Di, 2)}) × "
                                         f"{_n(L, 2)} = {_n(bsk)} m² (bekisting dalam & luar)"),
        penulangan.ItemBesi(
            penulangan.kode_pekerjaan("CAKAR", d), berat,
            f"W_m Ø{d:g} = {_n(wm)} kg/m'; vertikal {n_v} × (L + t) = {n_v} × {_n(p_v, 2)} m, cincin {n_c} × "
            f"(π Dm + 40d) = {n_c} × {_n(p_c)} m; W = {n} × ({_n(n_v * p_v)} + {_n(n_c * p_c)}) × {_n(wm)} × 1,05 "
            f"= {_n(berat, 2)} kg", f"Tulangan pipa cakar Ø{d:g}-{jarak * 1000:.0f}", d),
        ItemHasil(tanah.kode_galian(t + L), galian, f"V = n × π/4 × D² × L = {n} × π/4 × {_n(D, 2)}² × {_n(L, 2)} "
                                                     f"= {_n(galian)} m³ (lubang pipa cakar)"),
        ItemHasil("TNH.URUG.KEMBALI", tanah_dalam, f"V = n × π/4 × Di² × L = {n} × π/4 × {_n(Di, 2)}² × {_n(L, 2)} "
                                                   f"= {_n(tanah_dalam)} m³ (tanah di dalam pipa dipadatkan kembali)"),
    ]


def item_kolom(e: dict, p) -> list:
    """Fondasi pilihan di bawah satu kolom fisik: footplate turunan atau satu pipa cakar ayam."""
    if e.get("fondasi_pilihan") == "cakar":
        return _pengganti(_pipa(1, p, "di bawah kolom"))
    B, t, ket = e["footplate_ukuran"]
    V = B * B * t
    out = [
        ItemHasil("BTN.FONDASI", V, f"V = B × B × t = {_n(B, 2)} × {_n(B, 2)} × {_n(t, 2)} = {_n(V)} m³ "
                                    f"(footplate turunan, {ket})"),
        ItemHasil("BSK.FONDASI", 4 * B * t, f"A = 4 × B × t = 4 × {_n(B, 2)} × {_n(t, 2)} = {_n(4 * B * t)} m²"),
    ]
    semu = {"kelas": "FOOTING", "predefined_type": "PAD_FOOTING", "panjang": B, "lebar": B, "tebal": t,
            "luas": B * B, "keliling": 4 * B, "volume": V, "nama": "footplate turunan"}
    out += penulangan.hitung(semu, None, p.batas_kemiringan_dak)
    v_ped, ket_ped = 0.0, ""
    hp = max(p.kedalaman_fondasi_telapak - t, 0.0)
    b, h = e.get("lebar"), e.get("tebal")
    if e.get("pedestal_turunan") and b and h and hp > 0:
        v_ped = b * h * hp
        out += [
            ItemHasil("BTN.KOLOM", v_ped, f"V = b × h × H = {_n(b, 2)} × {_n(h, 2)} × {_n(hp, 2)} = {_n(v_ped)} m³ "
                                          f"(pedestal turunan: atas footplate s.d. muka tanah)"),
            ItemHasil("BSK.KOLOM", 2 * (b + h) * hp, f"A = 2 × (b + h) × H = 2 × ({_n(b, 2)} + {_n(h, 2)}) × "
                                                     f"{_n(hp, 2)} = {_n(2 * (b + h) * hp)} m² (pedestal turunan)"),
        ]
        out += penulangan.hitung({"kelas": "COLUMN", "lebar": b, "tebal": h, "tinggi": hp}, None)
        ket_ped = f" + pedestal {_n(v_ped)}"
    out += tanah.footplate(B, B, t, V + v_ped, p)
    if ket_ped:
        for it in out:
            if it.kode == "TNH.URUG.KEMBALI":
                it.rumus = it.rumus.replace("footplate ", "footplate" + ket_ped.replace(" + ", " & ") + " ", 1)
    return _pengganti(out)


def item_pelat(e: dict, p) -> list:
    """Pelat cakar ayam di bawah satu bidang lantai dasar / tapak dinding, beserta pipa tambahannya."""
    A, t = e["luas_cakar"], p.cakar_tebal_pelat
    asal = "tapak dinding" if e["kelas"] == "WALL" else "bidang lantai dasar"
    V = A * t
    d, s, lapis = CAKAR_TULANGAN_PELAT
    wm = penulangan.berat_per_m(d)
    berat = lapis * 2 * (A / s) * wm * penulangan.FAKTOR_SISA
    out = [
        ItemHasil("BTN.CAKAR.PELAT", V, f"V = A × t = {_n(A)} × {_n(t, 2)} = {_n(V)} m³ (pelat cakar ayam, {asal})"),
        penulangan.ItemBesi(
            penulangan.kode_pekerjaan("CAKAR", d), berat,
            f"W_m Ø{d:g} = {_n(wm)} kg/m'; W = lapis × 2 arah × A / s × W_m × 1,05 = {lapis} × 2 × {_n(A)} / "
            f"{_n(s, 2)} × {_n(wm)} × 1,05 = {_n(berat, 2)} kg",
            f"Tulangan pelat cakar Ø{d:g}-{s * 1000:.0f} dua arah, {lapis} lapis", d),
        ItemHasil(tanah.kode_galian(t), V, f"V = A × t = {_n(A)} × {_n(t, 2)} = {_n(V)} m³ (galian pelat cakar ayam)"),
    ]
    if e.get("tepi_cakar"):
        a = e["panjang"] * t
        out.append(ItemHasil("BSK.CAKAR.PELAT", a, f"A = L × t = {_n(e['panjang'])} × {_n(t, 2)} = {_n(a)} m² "
                                                   "(bekisting tepi pelat di sisi dinding luar)"))
    if e.get("pipa_cakar"):
        out += _pipa(e["pipa_cakar"], p, "tambahan (jarak antarpipa)")
    return _pengganti(out)


def label_jenis(jenis: int) -> str:
    return JENIS_FONDASI_KOLOM.get(jenis, str(jenis))
