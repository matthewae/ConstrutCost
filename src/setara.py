"""
Kolom SETARA di Kebutuhan Bahan: kebutuhan bahan (satuan analisa HSPK) diterjemahkan ke satuan beli di lapangan.

    Baja tulangan 43,38 kg        → ≈ 5 btg Ø10 @ 12 m   (per diameter dari penulangan; tanpa data diameter: asumsi)
    Semen 1.001 kg                → ≈ 21 zak @ 50 kg      (semen putih zak 40 kg; semen warna / nat kantong 1 kg)
    Pasir beton 338 kg            → ≈ 0,24 m³
    Kayu kaso 5/7 0,027 m³        → ≈ 2 btg 5/7 @ 4 m     (balok tanpa ukuran di nama: asumsi 6/12)
    Kawat beton 1,59 kg           → beli 1 rol @ 25 kg (terpakai 6%)
    Paku 2 inch 2,28 kg           → ≈ 750 btg (± 330 btg/kg) · eceran per kg   (≥ 15 kg: dus @ 30 kg)
    Paku 12 cm 450 buah           → ≈ 10 kg (± 45 btg/kg) · dijual per kg
    Paku sekrup 14,8 kg           → ≈ 12 dus @ 500 buah (± 400 buah/kg)
    Lem kayu 46,98 kg             → ≈ 19 kaleng @ 2,5 kg
    Wiremesh M6 35,94 kg          → ≈ 2 lembar M6 @ 2,1 × 5,4 m (± 33,6 kg)
    Granit 40x40 1.090 buah       → ≈ 182 dus @ 6 buah (0,96 m²)   (keramik, homogenous tile, porselen: sama)
    Keramik 40x40 12 m²           → ≈ 13 dus @ 6 buah (0,96 m²)
    Ubin teraso 40x40 66 buah     → ≈ 10,56 m² (6,25 buah/m²)       (ubin PC / tegel: sama)
    Plint 10x40 30 buah           → ≈ 12 m' (40 cm/buah)
    Cat tembok 30 kg              → ≈ 1 pail @ 25 kg + 1 galon @ 5 kg   (cat kayu / besi / meni: kaleng @ 1 kg)
    Self drilling screw 6.512 bh  → ≈ 7 dus @ 1.000 buah
    Besi siku 40x40x4 100 kg      → ≈ 7 btg @ 6 m (± 14,5 kg/btg)   (hollow: sama; pelat baja → lembar 4' × 8')
    Kabel NYM 3 x 2,5 mm² 120 m   → ≈ 3 rol @ 50 m        (penampang > 6 mm²: dipotong per meter; UTP: box 305 m)
    Beton ready mix 18 m³         → ≈ 3 truk mixer @ 7 m³
    Pasir pasang 74,5 m³          → ≈ 11 truk @ 7 m³
    Minyak bekisting 1,14 liter   → beli 1 jeriken @ 20 liter
    Plywood / papan semen 30 m²   → ≈ 11 lembar @ 122 × 244 cm     (gypsum / GRC board: 120 × 240 cm)
    Bata ringan 10 cm 1.889 bh    → ≈ 22,67 m³
    Pipa besi 3 inch 161 m'       → ≈ 27 btg @ 6 m          (pipa PVC 4 m, conduit 3 m, lisplang GRC 3 m)
    Genteng beton 978,7 buah      → beli 979 buah           (bahan yang memang dijual per satuannya)
    Batu paras 15,4 m²            → dijual per m²           (tanpa kemasan khusus; komponen berupa pekerjaan: kosong)

Angka konversi adalah ukuran kemasan / berat isi yang lazim di pasaran (dapat berbeda per merek dan pemasok).
"""

import math
import re

from rules.penulangan import PANJANG_BATANG, berat_per_m, label_d, ulir

BERAT_ZAK_SEMEN = 50  # kg per zak
BERAT_ZAK_SEMEN_PUTIH = 40  # kg per zak semen putih
BERAT_ZAK_MORTAR = 40  # kg per zak mortar instan (perekat bata ringan, plester, acian)
BERAT_KANTONG_NAT = 1.0  # kg semen warna / semen nat per kantong
BERAT_ISI = {  # kg/m³, berat isi lepas agregat (pembagi kg -> m³)
    "pasir": 1400.0,
    "batu split": 1350.0, "split": 1350.0, "kerikil": 1350.0, "koral": 1350.0, "batu pecah": 1350.0,
    "agregat": 1350.0, "agg ": 1350.0,
    "sirtu": 1600.0, "tanah": 1500.0,
}
AGREGAT_M3 = ("pasir", "kerikil", "koral", "batu belah", "batu kali", "batu pecah", "split", "sirtu", "tanah",
              "agregat", "agg ")
ISI_TRUK = 7.0  # m³ dump truck
ISI_TRUK_MIXER = 7.0  # m³ beton ready mix per truk mixer
PANJANG_KAYU = 4.0  # m, panjang kayu di pasaran
BALOK_ASUMSI = ("6", "12")  # cm, balok kayu tanpa ukuran di nama dianggap 6/12
PAPAN_ASUMSI = ("2", "20")  # cm, papan kayu tanpa ukuran di nama dianggap 2/20
BERAT_ROL_KAWAT = 25.0  # kg per rol kawat bendrat
ISI_JERIKEN = 20.0  # liter minyak bekisting / additive per jeriken
ISI_GALON_CAIRAN = 5.0  # liter additive / curing compound per galon
ISI_KALENG_CAIRAN = 1.0  # liter thinner / vernis / pelitur / cat minyak per kaleng
BERAT_PAIL_CAT, BERAT_GALON_CAT = 25.0, 5.0  # kg cat tembok
BERAT_KALENG_CAT = 1.0  # kg cat kayu / besi / meni per kaleng
BERAT_PAIL_WP, BERAT_GALON_WP = 20.0, 4.0  # kg waterproofing (pelapis akrilik / semen)
CAT_MINYAK = ("besi", "kayu", "meni", "zinc", "zync", "minyak", "karat", "epoxy", "enamel")
PAKU_PER_KG = {  # perkiraan jumlah batang per kg paku kawat biasa
    1.0: 1500, 2.5: 1500, 3.0: 900, 5.0: 330, 7.0: 160, 10.0: 75, 12.0: 45, 12.7: 40,
}
PAKU_TANPA_UKURAN = {"tripleks": 2.5, "triplek": 2.5, "beton": 5.0}  # cm, asumsi panjang
PAKU_SEKRUP_PER_KG = 400  # buah sekrup kayu ± 3 cm per kg
ISI_DUS_PAKU_SEKRUP = 500  # buah sekrup kayu / paku sekrup per dus
ISI_DUS_UBIN = {  # buah per dus menurut ukuran (cm): keramik, granit / homogenous tile, porselen
    (10, 20): 50, (20, 20): 25, (20, 25): 20, (25, 25): 16, (20, 40): 12, (25, 40): 10, (30, 30): 11,
    (40, 40): 6, (50, 50): 4, (30, 60): 8, (60, 60): 4, (80, 80): 3, (60, 120): 2,
}
KERAMIK_PER_DUS = {k: v * k[0] * k[1] / 10_000 for k, v in ISI_DUS_UBIN.items()}  # m² per dus
UBIN_DUS = ("keramik", "granit", "homogen", "porselen", "porcelain", "tile")
BUKAN_UBIN_DUS = ("plint", "bakar", "serbuk", "mozaik", "batu")  # batu alam / mozaik dijual per m² / lembar
UBIN_SATUAN = ("ubin", "tegel", "teraso")  # ubin PC / teraso: dijual per buah atau per m²
DIAMETER_ASUMSI = {False: 10.0, True: 13.0}  # tanpa data penulangan: polos Ø10, ulir D13
PANJANG_PIPA_PVC, PANJANG_BATANG_PROFIL = 4.0, 6.0  # m per batang (pipa PVC; pipa besi / profil aluminium & baja)
PANJANG_CONDUIT = 3.0  # m, pipa conduit PVC per batang
PANJANG_LISPLANG_GRC = 3.0  # m, lisplang GRC per batang
PANJANG_BAMBU = 6.0  # m per batang
ISI_PICKUP = 1.5  # m³ mobil bak terbuka (agregat < 3 m³)
BERAT_KALENG_LEM = 2.5  # kg lem kayu (PVAc) per kaleng
BERAT_KALENG_LEM_LAIN = 1.0  # kg lem kuning / epoxy / vinyl per kaleng
LEMBAR_WIREMESH = (2.1, 5.4)  # m, lembar wiremesh standar; jarak kawat 150 mm dua arah
BERAT_DUS_PAKU = 30.0  # kg paku per dus (kebutuhan kecil dibeli eceran per kg)
ISI_DUS_SEKRUP = 1000  # buah self drilling screw / paku rivet per dus
PANJANG_ROL_MEMBRAN = 10.0  # m, membran bakar 1 × 10 m per rol
PANJANG_ROL_KABEL = 50.0  # m kabel NYA / NYM / NYY (penampang ≤ 6 mm²) per rol
PENAMPANG_ROL_MAKS = 6.0  # mm², kabel lebih besar dipotong per meter
ISI_BOX_UTP = 305.0  # m kabel UTP / LAN per box
PANJANG_ROL_WALLPAPER = 10.0  # m per rol (lebar ± 53 cm)
LEMBAR_PAPAN = (122, 244)  # cm, plywood / blockboard / papan semen / ACP / HPL
LEMBAR_GYPSUM = (120, 240)  # cm, gypsum / GRC board
PAPAN_LEMBAR = ("plywood", "triplek", "tripleks", "multiplek", "multiplex", "blockboard", "veneer", "veeneer",
                "papan semen", "hpl", "phenol", "aluminium composite", "acp")
LEMBAR_PLAT = (1.22, 2.44)  # m, pelat baja 4' × 8'
BAJA_KG_PER_MM2_M = 0.00785  # kg per m' per mm² penampang baja
PROFIL = ("pipa", "rangka aluminium", "profil aluminium", "frame aluminium", "kusen aluminium", "hollow",
          "besi siku", "unp", "cnp", "kanal c", "c channel", "baja ringan", "reng baja", "besi lis", "plat strip",
          "besi strip")
KABEL_ROL = ("nya ", "nym", "nyy", "nyfgby", "frc", "kabel listrik")
SATUAN = {  # ejaan satuan HSPK -> bentuk baku
    "m2": "m²", "m3": "m³", "m": "m'", "m’": "m'", "ltr": "liter", "l": "liter", "bh": "buah", "btg": "batang",
    "lbr": "lembar", "sak": "zak", "roll": "rol",
}
SATUAN_BELI = ("buah", "unit", "set", "tube", "ikat", "lembar", "batang", "zak", "rol", "pasang", "biji", "keping",
               "pcs", "kaleng", "pail", "dus", "botol")  # satuan analisa yang sekaligus satuan beli
SATUAN_ECERAN = ("kg", "m²", "m'", "liter")  # bahan tanpa kemasan khusus: 'dijual per kg'
BUKAN_BAHAN = ("bekisting", "pasangan", "urukan", "pemasangan", "penulangan", "galian", "lantai kerja", "rabat",
               "instalasi", "pek.", "1 ")  # komponen berupa pekerjaan (analisa bertingkat): tanpa setara


def _angka(x: float, desimal: int = 2) -> str:
    teks = f"{x:,.{desimal}f}".replace(",", "_").replace(".", ",").replace("_", ".")
    return teks.rstrip("0").rstrip(",") if "," in teks else teks


def _naik(x: float) -> int:
    return max(1, math.ceil(x - 1e-9))


def _bil(teks: str) -> float:
    return float(teks.replace(",", "."))


def _ribuan(x: int) -> str:
    return f"{x:,}".replace(",", ".")


def _ukuran(n: str) -> tuple | None:
    """'granit 40x40 cm' / 'keramik lantai uk. 30 x 60 cm' -> (30, 60) urut tulisan; ukuran inch / kaki -> None."""
    m = re.search(r"(?<![\d.,x×])(\d+(?:[.,]\d+)?)\s*(?:cm)?\s*[x×]\s*(\d+(?:[.,]\d+)?)(?![\d.,])(?!\s*[x×]\s*\d)"
                  r"\s*(inch|\"|kaki|feet)?", n)
    if not m or m.group(3):
        return None
    a, b = _bil(m.group(1)), _bil(m.group(2))
    return (int(a) if a.is_integer() else a, int(b) if b.is_integer() else b)


def _kemasan(jumlah: float, besar: float, nama_besar: str, kecil: float, nama_kecil: str, satuan: str) -> str:
    """Kemasan besar sebanyak mungkin, sisanya kemasan kecil: '≈ 1 pail @ 25 kg + 1 galon @ 5 kg'."""
    if jumlah < besar:
        return f"≈ {_naik(jumlah / kecil)} {nama_kecil} @ {_angka(kecil, 1)} {satuan}"
    n, sisa = divmod(jumlah, besar)
    teks = f"≈ {int(n)} {nama_besar} @ {_angka(besar, 1)} {satuan}"
    return teks + (f" + {_naik(sisa / kecil)} {nama_kecil} @ {_angka(kecil, 1)} {satuan}" if sisa > 1e-6 else "")


def _baja(nama: str, jumlah: float, besi: dict | None) -> str:
    """Baja tulangan kg -> batang 12 m per diameter, sebanding berat tiap diameter di penulangan."""
    n = nama.lower()
    m = re.search(r"(?:dia\.?|diameter|ø)\s*(\d+(?:[.,]\d+)?)", n)
    if m:  # diameter tertulis di nama (dowel, tie bar, besi angkur)
        d = _bil(m.group(1))
        return f"≈ {_naik(jumlah / (berat_per_m(d) * PANJANG_BATANG))} btg {label_d(d)} @ {PANJANG_BATANG:g} m"
    kata_ulir = any(k in n for k in ("bjts", "ulir", "sirip", "u-39", "u39", "u-48", "u48"))
    kata_polos = "bjtp" in n or "polos" in n
    jenis = {True} if kata_ulir and not kata_polos else {False} if kata_polos and not kata_ulir else {False, True}
    sebaran = {d: b for d, b in (besi or {}).items() if ulir(d) in jenis and b > 0}
    asumsi = not sebaran
    if asumsi:
        sebaran = {DIAMETER_ASUMSI[max(jenis)]: 1.0}
    total = sum(sebaran.values())
    bagian = []
    for d in sorted(sebaran, reverse=True):
        batang = _naik(jumlah * sebaran[d] / total / (berat_per_m(d) * PANJANG_BATANG))
        bagian.append(f"{batang} btg {label_d(d)}")
    teks = f"≈ {' + '.join(bagian)} @ {PANJANG_BATANG:g} m"
    return teks + " (asumsi diameter)" if asumsi else teks


def _tulangan(n: str) -> bool:
    awalan = ("besi beton", "pembesian", "tulangan", "dowel", "tie bar", "baja (ulir)", "baja ulir", "baja polos",
              "besi angkur dia")
    return "baja tulangan" in n or "bjts" in n or "bjtp" in n or n.startswith(awalan)


def _profil_baja(n: str, jumlah: float) -> str:
    """Besi siku / hollow 'a x b x t' (atau a.b.t, 'a x b tebal t mm') kg -> batang 6 m."""
    m = re.search(r"(\d+)\s*[x×.]\s*(\d+)\s*(?:[x×.]|tebal)\s*(\d+(?:,\d+)?)", n)
    if not m:
        return ""
    a, b, t = int(m.group(1)), int(m.group(2)), _bil(m.group(3))
    luas = 2 * t * (a + b - 2 * t) if "hollow" in n else t * (a + b - t)  # mm²
    per_btg = luas * BAJA_KG_PER_MM2_M * PANJANG_BATANG_PROFIL
    if per_btg <= 0:
        return ""
    return f"≈ {_naik(jumlah / per_btg)} btg @ {PANJANG_BATANG_PROFIL:g} m (± {_angka(per_btg, 1)} kg/btg)"


def _kayu(nama: str, jumlah: float) -> str:
    m = re.search(r"(\d+(?:[.,]\d+)?)\s*(?:cm)?\s*[/x×]\s*(\d+(?:[.,]\d+)?)", nama)
    if not m:
        return ""
    a, b = (_bil(x) / 100 for x in m.groups())
    per_batang = a * b * PANJANG_KAYU
    if per_batang <= 0:
        return ""
    return f"≈ {_naik(jumlah / per_batang)} btg {m.group(1)}/{m.group(2)} @ {PANJANG_KAYU:g} m"


def _agregat_m3(m3: float) -> str:
    if m3 >= 3:
        return f"≈ {_naik(m3 / ISI_TRUK)} truk @ {ISI_TRUK:g} m³"
    return f"≈ {_naik(m3 / ISI_PICKUP)} pick-up @ {_angka(ISI_PICKUP, 1)} m³"


def _wiremesh(nama: str, jumlah: float) -> str:
    m = re.search(r"\bM\s*(\d+)", nama, re.IGNORECASE)
    d = float(m.group(1)) if m else 6.0
    a, b = LEMBAR_WIREMESH
    per_lembar = 2 * berat_per_m(d) / 0.15 * a * b
    return f"≈ {_naik(jumlah / per_lembar)} lembar M{d:g} @ {_angka(a, 1)} × {_angka(b, 1)} m (± {_angka(per_lembar, 1)} kg)"


def _panjang_paku(n: str) -> tuple:
    """(panjang cm, asumsi?) dari nama paku; (None, False) bila tidak diketahui."""
    m = re.search(r"(\d+(?:[.,]\d+)?)\s*(inch|inchi|\")", n)
    if m:
        return round(_bil(m.group(1)) * 2.54, 1), False
    m = re.search(r"(\d+(?:[.,]\d+)?)\s*cm", n)
    if m:
        return _bil(m.group(1)), False
    asumsi = next((v for k, v in PAKU_TANPA_UKURAN.items() if k in n), None)
    return asumsi, asumsi is not None


def _per_kg(panjang: float) -> int:
    return PAKU_PER_KG[min(PAKU_PER_KG, key=lambda p: abs(p - panjang))]


def _paku(nama: str, jumlah: float) -> str:
    n = nama.lower()
    if "sekrup" in n or "skrup" in n:
        buah = jumlah * PAKU_SEKRUP_PER_KG
        if buah >= ISI_DUS_PAKU_SEKRUP / 2:
            return f"≈ {_naik(buah / ISI_DUS_PAKU_SEKRUP)} dus @ {ISI_DUS_PAKU_SEKRUP} buah (± {PAKU_SEKRUP_PER_KG} buah/kg)"
        return f"≈ {_ribuan(_naik(buah))} buah (± {PAKU_SEKRUP_PER_KG} buah/kg) · eceran"
    panjang, asumsi = _panjang_paku(n)
    if panjang is None:  # ukuran tidak diketahui: kemasan saja
        if jumlah >= BERAT_DUS_PAKU / 2:
            return f"≈ {_naik(jumlah / BERAT_DUS_PAKU)} dus @ {BERAT_DUS_PAKU:g} kg"
        return "eceran per kg"
    per_kg = _per_kg(panjang)
    catatan = f", asumsi {_angka(panjang, 1)} cm" if asumsi else ""
    teks = f"≈ {_angka(round(jumlah * per_kg, -1), 0)} btg (± {per_kg} btg/kg{catatan})"
    if jumlah >= BERAT_DUS_PAKU / 2:
        return f"≈ {_naik(jumlah / BERAT_DUS_PAKU)} dus @ {BERAT_DUS_PAKU:g} kg · {teks}"
    return f"{teks} · eceran per kg"


def _cat(n: str, jumlah: float) -> str:
    if any(k in n for k in CAT_MINYAK):  # cat kayu / besi / meni: kaleng 1 kg
        return f"≈ {_naik(jumlah / BERAT_KALENG_CAT)} kaleng @ {BERAT_KALENG_CAT:g} kg"
    return _kemasan(jumlah, BERAT_PAIL_CAT, "pail", BERAT_GALON_CAT, "galon", "kg")


def _ubin(n: str, s: str, jumlah: float) -> str:
    ukuran = _ukuran(n)
    if not ukuran:
        return ""
    ukuran = tuple(sorted(ukuran))
    a, b = ukuran
    if "plint" in n:  # plint: panjang = sisi terpanjang
        return f"≈ {_angka(jumlah * b / 100, 2)} m' ({_angka(b, 1)} cm/buah)" if s == "buah" else ""
    if any(k in n for k in UBIN_DUS) and not any(k in n for k in BUKAN_UBIN_DUS):
        isi = ISI_DUS_UBIN.get(ukuran)
        if not isi:
            return ""
        m2 = isi * a * b / 10_000
        dus = jumlah / isi if s == "buah" else jumlah / m2
        return f"≈ {_naik(dus)} dus @ {isi} buah ({_angka(m2, 2)} m²)"
    if any(k in n for k in UBIN_SATUAN) and s == "buah":
        per_m2 = 10_000 / (a * b)
        return f"≈ {_angka(jumlah / per_m2, 2)} m² ({_angka(per_m2, 2)} buah/m²)"
    return ""


def _kabel(n: str, jumlah: float) -> str:
    if "+" in n:  # kabel + conduit + aksesoris: satuan pekerjaan
        return ""
    if "utp" in n or "lan" in n.split():
        return f"≈ {_naik(jumlah / ISI_BOX_UTP)} box @ {ISI_BOX_UTP:g} m"
    if not any(k in n for k in KABEL_ROL):
        return ""
    m = re.search(r"\d+\s*x\s*(\d+(?:[.,]\d+)?)\s*mm", n)
    if m and _bil(m.group(1)) > PENAMPANG_ROL_MAKS:
        return "dipotong per meter (eceran)"
    return f"≈ {_naik(jumlah / PANJANG_ROL_KABEL)} rol @ {PANJANG_ROL_KABEL:g} m"


def _panjang_batang(n: str) -> float | None:
    """Panjang batang (m) bahan yang dijual per batang; None bila bukan."""
    m = re.search(r"panjang\s*(\d+)\s*cm", n)
    if m:
        return float(m.group(1)) / 100
    if ("conduit" in n or "konduit" in n) and "flexible" not in n:
        return PANJANG_CONDUIT
    if ("listplank" in n or "lisplang" in n or "lisplank" in n) and "grc" in n:
        return PANJANG_LISPLANG_GRC
    if "bambu" in n:
        return PANJANG_BAMBU
    if any(k in n for k in PROFIL) and "isolasi" not in n:
        return PANJANG_PIPA_PVC if ("pvc" in n or "plastik" in n) else PANJANG_BATANG_PROFIL
    return None


def _lembar(n: str, jumlah_m2: float) -> str:
    """Papan lembaran (m²) -> lembar 122 × 244 cm (gypsum / GRC board 120 × 240 cm, atau ukuran di nama)."""
    ukuran = _ukuran(n)
    if not ukuran:
        ukuran = LEMBAR_GYPSUM if ("gypsum" in n or "grc" in n) else LEMBAR_PAPAN
    a, b = ukuran
    return f"≈ {_naik(jumlah_m2 / (a * b / 10_000))} lembar @ {_angka(a, 1)} × {_angka(b, 1)} cm"


def rumus_zak(jumlah: float, keterangan: str, fmt=None) -> str:
    """'1.001 kg ÷ 50 kg = 21 zak @ 50 kg' bila setara berupa zak; selain itu setara apa adanya."""
    m = re.search(r"zak @ (\d+(?:,\d+)?) kg", keterangan or "")
    if not m:
        return keterangan or ""
    teks = fmt(jumlah) if fmt else _angka(jumlah, 2)
    return f"{teks} kg ÷ {m.group(1)} kg = {keterangan.replace('≈ ', '')}"


def setara(nama: str, satuan: str, jumlah: float, besi: dict | None = None, tipe: str = "bahan") -> str:
    """Teks kolom SETARA. `besi` = {diameter mm: berat kg} penulangan baris yang sama (untuk baja tulangan).
    Bahan yang satuan analisanya sudah satuan beli (buah, unit, lembar, zak, ...) -> 'beli n buah'."""
    n = nama.lower().strip()
    s = satuan.lower().strip()
    s = SATUAN.get(s, s)
    if jumlah <= 0:
        return ""
    if s == "oh":
        return "orang-hari"
    if tipe != "bahan" or n.startswith(BUKAN_BAHAN) or n == "beton":
        return ""
    teks = _aturan(nama, n, s, jumlah, besi)
    if teks:
        return teks
    if s in SATUAN_BELI:
        return f"beli {_ribuan(_naik(jumlah))} {s}"
    if s in SATUAN_ECERAN and "dynabolt" not in n:  # dynabolt dijual per buah, HSPK dalam kg
        return f"dijual per {s}"
    return ""


def _aturan(nama: str, n: str, s: str, jumlah: float, besi: dict | None) -> str:
    if n.startswith("paku") and s in ("liter", "m³"):  # satuan HSPK tidak lazim
        return f"⚠ satuan HSPK {s}, kemungkinan kg: " + _paku(nama, jumlah)
    if s == "kg":
        return _aturan_kg(nama, n, jumlah, besi)
    if s == "m³":
        return _aturan_m3(nama, n, jumlah)
    if s == "m²":
        return _aturan_m2(n, jumlah)
    if s == "m'":
        return _aturan_m(n, jumlah)
    if s == "liter":
        return _aturan_liter(n, jumlah)
    if s == "buah":
        return _aturan_buah(n, jumlah)
    if s == "batang":
        panjang = _panjang_batang(n) or (PANJANG_BATANG_PROFIL if "reng" in n else None)
        return f"≈ {_naik(jumlah)} btg" + (f" @ {panjang:g} m" if panjang else "")
    if s == "lembar":
        if any(k in n for k in ("plywood", "triplek", "tripleks", "multiplek", "multiplex")):
            return "lembar 122 × 244 cm"
        ukuran = _ukuran(n)
        if ukuran:
            return f"≈ {_naik(jumlah)} lembar @ {_angka(ukuran[0], 1)} × {_angka(ukuran[1], 1)} cm"
    return ""


def _aturan_kg(nama: str, n: str, jumlah: float, besi: dict | None) -> str:
    if _tulangan(n):
        return _baja(nama, jumlah, besi)
    if "waterproofing" in n or "water proofing" in n:
        return _kemasan(jumlah, BERAT_PAIL_WP, "pail", BERAT_GALON_WP, "galon", "kg")
    if "semen merah" in n:  # bata merah tumbuk: dijual per karung / m³
        return ""
    if "semen" in n or n.startswith("nat"):
        if "warna" in n or re.search(r"\bnat\b", n) or "grout" in n:
            return f"≈ {_ribuan(_naik(jumlah / BERAT_KANTONG_NAT))} kantong @ {BERAT_KANTONG_NAT:g} kg"
        berat = BERAT_ZAK_SEMEN_PUTIH if "putih" in n else BERAT_ZAK_SEMEN
        return f"≈ {_ribuan(_naik(jumlah / berat))} zak @ {berat} kg"
    if "mortar" in n:
        return f"≈ {_ribuan(_naik(jumlah / BERAT_ZAK_MORTAR))} zak @ {BERAT_ZAK_MORTAR} kg"
    isi = next((v for k, v in BERAT_ISI.items() if k in n), None)
    if isi and "serbuk" not in n and "rayap" not in n:
        m3 = jumlah / isi
        teks = f"≈ {_angka(m3, 2)} m³"
        return teks + f" ≈ {_naik(m3 / ISI_TRUK)} truk @ {ISI_TRUK:g} m³" if m3 >= 3 else teks
    if "lem kayu" in n:
        return f"≈ {_naik(jumlah / BERAT_KALENG_LEM)} kaleng @ {_angka(BERAT_KALENG_LEM, 1)} kg"
    if n.startswith("lem"):
        return f"≈ {_naik(jumlah / BERAT_KALENG_LEM_LAIN)} kaleng @ {BERAT_KALENG_LEM_LAIN:g} kg"
    if "wiremesh" in n.replace(" ", "").replace("-", ""):
        return _wiremesh(nama, jumlah)
    if "besi strip" in n:
        m = re.search(r"(\d+(?:[.,]\d+)?)\s*[x×]\s*(\d+(?:[.,]\d+)?)", n)
        if m:
            a, b = (_bil(x) for x in m.groups())
            per_btg = a * b * BAJA_KG_PER_MM2_M * PANJANG_BATANG_PROFIL
            return f"≈ {_naik(jumlah / per_btg)} btg @ {PANJANG_BATANG_PROFIL:g} m (± {_angka(per_btg, 2)} kg/btg)"
        return ""
    if any(k in n for k in ("siku", "hollow", "baja l ", "besi l.", "frame besi l")):
        return _profil_baja(n, jumlah)
    if ("plat" in n or "pelat" in n) and ("besi" in n or "baja" in n):
        m = re.search(r"(\d+(?:[.,]\d+)?)\s*mm", n)
        if m:
            a, b = LEMBAR_PLAT
            per_lembar = a * b * _bil(m.group(1)) * 7.85
            return (f"≈ {_naik(jumlah / per_lembar)} lembar 4' × 8' @ {_angka(a, 2)} × {_angka(b, 2)} m"
                    f" (± {_angka(per_lembar, 1)} kg)")
        return ""
    if n.startswith("paku"):
        return _paku(nama, jumlah)
    if ("kawat" in n or "bendrat" in n) and not any(k in n for k in ("harmonika", "nyamuk", "kasa", "jaring",
                                                                      "strimin", "duri")):
        rol = _naik(jumlah / BERAT_ROL_KAWAT)
        return f"beli {rol} rol @ {BERAT_ROL_KAWAT:g} kg (terpakai {jumlah / (rol * BERAT_ROL_KAWAT):.0%})"
    if "plamir kayu" in n or "dempul" in n or "wood filler" in n:
        return f"≈ {_naik(jumlah / BERAT_KALENG_CAT)} kaleng @ {BERAT_KALENG_CAT:g} kg"
    if re.search(r"\bcat\b", n) or "meni" in n or "paint" in n or "primer" in n or "plamir" in n:
        return _cat(n, jumlah)
    return ""


def _aturan_m3(nama: str, n: str, jumlah: float) -> str:
    if "ready mix" in n:
        return f"≈ {_naik(jumlah / ISI_TRUK_MIXER)} truk mixer @ {ISI_TRUK_MIXER:g} m³"
    if "bata ringan" in n:
        ukuran = re.search(r"(\d+)\s*x\s*(\d+)\s*x\s*(\d+)\s*cm", n)
        p, l, t = (int(x) for x in ukuran.groups()) if ukuran else (60, 20, 10)
        m = re.search(r"t\s*=\s*(\d+)\s*cm", n)
        if m and not ukuran:
            t = int(m.group(1))
        return f"≈ {_ribuan(_naik(jumlah / (p * l * t / 1e6)))} buah ({p} × {l} × {t} cm)"
    if any(k in n for k in ("kayu", "kaso", "balok", "papan", "reng", "list kayu")) and "perancah" not in n:
        teks = _kayu(nama, jumlah)
        if not teks and "papan" in n:  # papan tanpa ukuran di nama: asumsi 2/20 panjang 4 m
            a, b = PAPAN_ASUMSI
            teks = _kayu(f"{a}/{b}", jumlah).replace("btg", "lbr papan") + f" (asumsi papan {a}/{b})"
        elif not teks and "balok" in n:
            a, b = BALOK_ASUMSI
            teks = _kayu(f"{a}/{b}", jumlah) + f" (asumsi balok {a}/{b})"
        return teks
    if any(k in n for k in AGREGAT_M3) or n == "batu":
        return _agregat_m3(jumlah)
    if "minyak" in n:  # satuan HSPK tidak lazim (analisa bekisting sloof)
        return f"⚠ satuan HSPK m³, kemungkinan liter: ≈ {_naik(jumlah / ISI_JERIKEN)} jeriken @ {ISI_JERIKEN:g} liter"
    return ""


def _aturan_m2(n: str, jumlah: float) -> str:
    teks = _ubin(n, "m²", jumlah)
    if teks:
        return teks
    if any(k in n for k in PAPAN_LEMBAR) or ("gypsum" in n and "list" not in n) or "grcboard" in n:
        return _lembar(n, jumlah)
    if "atap" in n and _ukuran(n):  # atap lembaran berukuran (mis. UPVC 86 × 119 cm)
        return _lembar(n, jumlah)
    if "atap metal" in n or "spandek" in n:
        return "dipesan per lembar sesuai panjang bentang"
    return ""


def _aturan_m(n: str, jumlah: float) -> str:
    if "membran" in n:
        return f"≈ {_naik(jumlah / PANJANG_ROL_MEMBRAN)} rol @ 1 × {PANJANG_ROL_MEMBRAN:g} m"
    if "kabel" in n or n.startswith(("nym", "nya ")):
        return _kabel(n, jumlah)
    if "wallpaper" in n:
        return f"≈ {_naik(jumlah / PANJANG_ROL_WALLPAPER)} rol @ {PANJANG_ROL_WALLPAPER:g} m"
    panjang = _panjang_batang(n)
    if panjang:
        return f"≈ {_naik(jumlah / panjang)} btg @ {panjang:g} m"
    return ""


def _aturan_liter(n: str, jumlah: float) -> str:
    if re.search(r"\bcat\b", n) or any(k in n for k in ("thinner", "pengencer", "vernis", "pelitur", "politur",
                                                          "teak oil")):
        return _kemasan(jumlah, ISI_JERIKEN, "jeriken", ISI_KALENG_CAIRAN, "kaleng", "liter")
    if "minyak bekisting" in n or n == "minyak":
        return f"beli {_naik(jumlah / ISI_JERIKEN)} jeriken @ {ISI_JERIKEN:g} liter"
    if "additive" in n or "aditif" in n or "curing" in n:
        return _kemasan(jumlah, ISI_JERIKEN, "jeriken", ISI_GALON_CAIRAN, "galon", "liter")
    if n.startswith("air"):
        return f"≈ {_angka(jumlah / 1000, 2)} m³"
    return ""


def _aturan_buah(n: str, jumlah: float) -> str:
    if "self drilling" in n or "rivet" in n or "roofing screw" in n:
        return f"≈ {_naik(jumlah / ISI_DUS_SEKRUP)} dus @ {_ribuan(ISI_DUS_SEKRUP)} buah"
    if n.startswith("paku") and ("sekrup" in n or "skrup" in n):
        if jumlah >= ISI_DUS_PAKU_SEKRUP / 2:
            return f"≈ {_naik(jumlah / ISI_DUS_PAKU_SEKRUP)} dus @ {ISI_DUS_PAKU_SEKRUP} buah"
        return ""
    if n.startswith("paku"):  # paku dijual per kg
        panjang, _asumsi = _panjang_paku(n)
        if panjang:
            per_kg = _per_kg(panjang)
            return f"≈ {_angka(jumlah / per_kg, 2)} kg (± {per_kg} btg/kg) · dijual per kg"
        return ""
    teks = _ubin(n, "buah", jumlah)
    if teks:
        return teks
    if "bata ringan" in n:
        m = re.search(r"(\d+(?:[.,]\d+)?)\s*cm", n)
        tebal = _bil(m.group(1)) / 100 if m else 0.10
        return f"≈ {_angka(jumlah * 0.60 * 0.20 * tebal, 2)} m³ (60 × 20 × {_angka(tebal * 100, 1)} cm)"
    return ""
