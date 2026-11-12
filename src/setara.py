"""
Kolom SETARA di Kebutuhan Bahan: kebutuhan bahan (satuan analisa HSPK) diterjemahkan ke satuan beli di lapangan.

    Baja tulangan 43,38 kg      → ≈ 5 btg Ø10 @ 12 m   (per diameter dari penulangan; tanpa data diameter: asumsi)
    Semen 1.001 kg              → ≈ 21 zak @ 50 kg
    Pasir beton 338 kg          → ≈ 0,24 m³
    Batu split 431 kg           → ≈ 0,32 m³
    Kayu kaso 5/7 0,027 m³      → ≈ 2 btg 5/7 @ 4 m
    Kawat beton 1,59 kg         → beli 1 rol @ 25 kg (terpakai 6%)
    Paku 2 inch 2,28 kg         → ≈ 750 btg (± 330 btg/kg)
    Minyak bekisting 1,14 liter → beli 1 jeriken @ 20 liter
    Cat tembok 30 kg            → ≈ 2 pail @ 25 kg
    Keramik 40x40 12 m²         → ≈ 13 dus @ 0,96 m²     (per buah: ≈ 203 dus @ 6 buah)
    Bata ringan 10 cm 1.889 bh  → ≈ 22,67 m³
    Pipa besi 3 inch 161 m'     → ≈ 27 btg @ 6 m          (pipa PVC: batang 4 m)

Angka konversi adalah ukuran kemasan / berat isi yang lazim di pasaran (dapat berbeda per merek dan pemasok).
"""

import math
import re

from rules.penulangan import PANJANG_BATANG, berat_per_m, label_d, ulir

BERAT_ZAK_SEMEN = 50  # kg per zak
BERAT_ZAK_MORTAR = 40  # kg per zak mortar instan (perekat bata ringan, plester, acian)
BERAT_ISI = {  # kg/m³, berat isi lepas agregat (pembagi kg -> m³)
    "pasir": 1400.0,
    "batu split": 1350.0, "split": 1350.0, "kerikil": 1350.0, "koral": 1350.0, "batu pecah": 1350.0,
    "sirtu": 1600.0, "tanah": 1500.0,
}
ISI_TRUK = 7.0  # m³ dump truck
PANJANG_KAYU = 4.0  # m, panjang kayu di pasaran
BERAT_ROL_KAWAT = 25.0  # kg per rol kawat bendrat
ISI_JERIKEN = 20.0  # liter minyak bekisting per jeriken
BERAT_PAIL_CAT, BERAT_GALON_CAT = 25.0, 5.0  # kg
PAKU_PER_KG = {  # perkiraan jumlah batang per kg paku kawat biasa
    1.0: 1500, 2.5: 1500, 3.0: 900, 5.0: 330, 7.0: 160, 10.0: 75, 12.0: 45, 12.7: 40,
}
KERAMIK_PER_DUS = {  # m² per dus menurut ukuran (cm)
    (20, 20): 1.0, (20, 25): 1.0, (25, 25): 1.0, (25, 40): 1.0, (30, 30): 0.99, (40, 40): 0.96, (50, 50): 1.25,
    (60, 60): 1.44, (20, 40): 0.96, (30, 60): 1.44,
}
DIAMETER_ASUMSI = {False: 10.0, True: 13.0}  # tanpa data penulangan: polos Ø10, ulir D13
PANJANG_PIPA_PVC, PANJANG_BATANG_PROFIL = 4.0, 6.0  # m per batang (pipa PVC; pipa besi / profil aluminium & baja)
PROFIL = ("pipa", "rangka aluminium", "hollow", "besi siku", "unp", "cnp", "kanal c")  # batang 6 m (PVC 4 m)


def _angka(x: float, desimal: int = 2) -> str:
    teks = f"{x:,.{desimal}f}".replace(",", "_").replace(".", ",").replace("_", ".")
    return teks.rstrip("0").rstrip(",") if "," in teks else teks


def _naik(x: float) -> int:
    return max(1, math.ceil(x - 1e-9))


def _baja(nama: str, jumlah: float, besi: dict | None) -> str:
    """Baja tulangan kg -> batang 12 m per diameter, sebanding berat tiap diameter di penulangan."""
    n = nama.lower()
    jenis_ulir = "bjts" in n or "ulir" in n or "sirip" in n
    sebaran = {d: b for d, b in (besi or {}).items() if ulir(d) == jenis_ulir and b > 0}
    asumsi = not sebaran
    if asumsi:
        sebaran = {DIAMETER_ASUMSI[jenis_ulir]: 1.0}
    total = sum(sebaran.values())
    bagian = []
    for d in sorted(sebaran, reverse=True):
        batang = _naik(jumlah * sebaran[d] / total / (berat_per_m(d) * PANJANG_BATANG))
        bagian.append(f"{batang} btg {label_d(d)}")
    teks = f"≈ {' + '.join(bagian)} @ {PANJANG_BATANG:g} m"
    return teks + " (asumsi diameter)" if asumsi else teks


def _kayu(nama: str, jumlah: float) -> str:
    m = re.search(r"(\d+(?:[.,]\d+)?)\s*/\s*(\d+(?:[.,]\d+)?)", nama)
    if not m:
        return ""
    a, b = (float(x.replace(",", ".")) / 100 for x in m.groups())
    per_batang = a * b * PANJANG_KAYU
    if per_batang <= 0:
        return ""
    return f"≈ {_naik(jumlah / per_batang)} btg {m.group(1)}/{m.group(2)} @ {PANJANG_KAYU:g} m"


def _paku(nama: str, jumlah: float) -> str:
    n = nama.lower()
    panjang = None
    m = re.search(r"(\d+(?:[.,]\d+)?)\s*(inch|inchi|\")", n)
    if m:
        panjang = round(float(m.group(1).replace(",", ".")) * 2.54, 1)
    else:
        m = re.search(r"(\d+(?:[.,]\d+)?)\s*cm", n)
        if m:
            panjang = float(m.group(1).replace(",", "."))
    if panjang is None:
        return ""
    per_kg = PAKU_PER_KG[min(PAKU_PER_KG, key=lambda p: abs(p - panjang))]
    return f"≈ {_angka(round(jumlah * per_kg, -1), 0)} btg (± {per_kg} btg/kg)"


def setara(nama: str, satuan: str, jumlah: float, besi: dict | None = None) -> str:
    """Teks kolom SETARA. `besi` = {diameter mm: berat kg} penulangan baris yang sama (untuk baja tulangan)."""
    n = nama.lower()
    s = satuan.lower().strip()
    if jumlah <= 0:
        return ""
    if s == "oh":
        return "orang-hari"
    if s == "kg" and ("baja tulangan" in n or n.startswith("besi beton")):
        return _baja(nama, jumlah, besi)
    if s == "kg" and "semen" in n and "warna" not in n:
        return f"≈ {_naik(jumlah / BERAT_ZAK_SEMEN):,} zak @ {BERAT_ZAK_SEMEN} kg".replace(",", ".")
    if s == "kg" and "mortar" in n:
        return f"≈ {_naik(jumlah / BERAT_ZAK_MORTAR):,} zak @ {BERAT_ZAK_MORTAR} kg".replace(",", ".")
    if s == "kg":
        isi = next((v for k, v in BERAT_ISI.items() if k in n), None)
        if isi:
            m3 = jumlah / isi
            teks = f"≈ {_angka(m3, 2)} m³"
            return teks + f" ≈ {_naik(m3 / ISI_TRUK)} truk @ {ISI_TRUK:g} m³" if m3 >= 3 else teks
    if s in ("m3", "m³") and ("kayu" in n or "kaso" in n or "balok" in n or "papan" in n):
        return _kayu(nama, jumlah)
    if s == "kg" and n.startswith("paku"):
        return _paku(nama, jumlah)
    if s == "kg" and ("kawat" in n or "bendrat" in n):
        rol = _naik(jumlah / BERAT_ROL_KAWAT)
        return f"beli {rol} rol @ {BERAT_ROL_KAWAT:g} kg (terpakai {jumlah / (rol * BERAT_ROL_KAWAT):.0%})"
    if s in ("liter", "ltr", "l") and "minyak" in n:
        jr = _naik(jumlah / ISI_JERIKEN)
        return f"beli {jr} jeriken @ {ISI_JERIKEN:g} liter"
    if s == "kg" and "cat" in n:
        if jumlah >= BERAT_PAIL_CAT:
            pail, sisa = divmod(jumlah, BERAT_PAIL_CAT)
            teks = f"≈ {int(pail)} pail @ {BERAT_PAIL_CAT:g} kg"
            return teks + (f" + {_naik(sisa / BERAT_GALON_CAT)} galon @ {BERAT_GALON_CAT:g} kg" if sisa > 1e-6 else "")
        return f"≈ {_naik(jumlah / BERAT_GALON_CAT)} galon @ {BERAT_GALON_CAT:g} kg"
    if s in ("m2", "m²") and "keramik" in n:
        m = re.search(r"(\d+)\s*[x×]\s*(\d+)", n)
        if m:
            a, b = sorted((int(m.group(1)), int(m.group(2))))
            per_dus = KERAMIK_PER_DUS.get((a, b))
            if per_dus:
                return f"≈ {_naik(jumlah / per_dus)} dus @ {_angka(per_dus, 2)} m²"
    if s in ("buah", "bh") and "keramik" in n:
        m = re.search(r"(\d+)\s*[x×]\s*(\d+)", n)
        if m:
            a, b = sorted((int(m.group(1)), int(m.group(2))))
            per_dus = KERAMIK_PER_DUS.get((a, b))
            if per_dus:
                isi = round(per_dus / (a * b / 10_000))
                return f"≈ {_naik(jumlah / isi)} dus @ {isi} buah"
    if s in ("buah", "bh") and "bata ringan" in n:
        m = re.search(r"(\d+(?:[.,]\d+)?)\s*cm", n)
        tebal = float(m.group(1).replace(",", ".")) / 100 if m else 0.10
        return f"≈ {_angka(jumlah * 0.60 * 0.20 * tebal, 2)} m³ (60 × 20 × {_angka(tebal * 100, 1)} cm)"
    if s in ("m'", "m", "m’") and any(k in n for k in PROFIL):
        panjang = PANJANG_PIPA_PVC if ("pvc" in n or "plastik" in n) else PANJANG_BATANG_PROFIL
        return f"≈ {_naik(jumlah / panjang)} btg @ {panjang:g} m"
    if s in ("liter", "ltr", "l") and n.startswith("air"):
        return f"≈ {_angka(jumlah / 1000, 2)} m³"
    if s == "lembar" and any(k in n for k in ("plywood", "triplek", "tripleks", "multiplek")):
        return "lembar 122 × 244 cm"
    return ""
