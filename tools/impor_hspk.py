"""
Impor HSPK (Harga Satuan Pokok Kegiatan) dari workbook Excel menjadi modul data CostStruct.

    python tools/impor_hspk.py "HSPK_Kota_Bandung_2027.xlsx"

Menghasilkan src/database/hspk_bandung_2027.py berisi:
- HSD   : seluruh harga satuan dasar upah, material, dan peralatan (sheet "HSD (...)").
- AHSP  : seluruh analisa harga satuan pekerjaan pada sheet bab yang relevan, lengkap dengan
          koefisien, harga komponen, dan harga satuan F dari dokumen (untuk verifikasi).

Kolom setiap analisa dibaca dari baris header "No | Uraian | ... | Koefisien | Harga Satuan |
Jumlah Harga" milik item itu sendiri, karena susunan kolom antar sheet tidak sama.
Pemetaan kode pekerjaan aplikasi ke kode HSPK ada di src/database/seed_data.py.
"""

import argparse
import re
import sys
from pathlib import Path

import openpyxl

SHEET_HSD = {"HSD (Upah)": "upah", "HSD (Material)": "bahan", "HSD (Peralatan)": "alat"}
SHEET_AHSP = [
    "Galian Tanah",
    "Beton",
    "Pondasi",
    "Rangka Atap",
    "Penutup Atap",
    "Plafon",
    "Pasangan Dinding",
    "Plesteran Dan Acian",
    "Pengecatan dan Pelituran",
    "Penutup Lantai dan Dinding",
    "Pintu dan Jendela",
    "Kaca",
    "Kayu",
    "Struktur Kayu",
    "Besi dan Aluminium",
    "Sistem Air Limbah",
]
KODE = re.compile(r"^\d+(\.\d+)+[a-zA-Z]?$")
TIPE_BLOK = {"TENAGA KERJA": "upah", "BAHAN": "bahan", "PERALATAN": "alat"}
TUJUAN = Path(__file__).resolve().parents[1] / "src" / "database" / "hspk_bandung_2027.py"


def _teks(v) -> str:
    return " ".join(str(v).split()) if v is not None else ""


def _angka(v):
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    try:
        return float(str(v).replace(",", "."))
    except (TypeError, ValueError):
        return None


def baca_hsd(wb) -> list:
    hasil = []
    for nama_sheet, tipe in SHEET_HSD.items():
        ws = wb[nama_sheet]
        kol = None
        for row in ws.iter_rows(values_only=True):
            row = list(row) + [None] * 10
            t = [_teks(v) for v in row]
            if kol is None:
                if "URAIAN" in t:
                    i_uraian = t.index("URAIAN")
                    satuan = [i for i, v in enumerate(t) if v == "SATUAN"]
                    kol = (i_uraian, satuan[0], satuan[1])
                continue
            nama, sat, harga = t[kol[0]], t[kol[1]], _angka(row[kol[2]])
            if nama and sat and harga and harga > 0:
                hasil.append((tipe, nama, sat, round(harga, 4)))
    return hasil


def baca_ahsp(wb) -> list:
    items = []
    for sh in SHEET_AHSP:
        if sh not in wb.sheetnames:
            print(f"  (lewati, sheet tidak ada: {sh})")
            continue
        ws = wb[sh]
        cur, tipe, kol = None, None, None
        for row in ws.iter_rows(values_only=True):
            row = list(row) + [None] * 20
            t = [_teks(v) for v in row]
            idx = next((i for i, v in enumerate(t) if v), None)
            if idx is None:
                continue
            cs, ds = t[idx], t[idx + 1]
            if KODE.match(cs) and cs.count(".") >= 2 and ds and not ds.lower().startswith("jumlah"):
                cur = {"sheet": sh, "kode": cs, "uraian": ds, "komponen": [], "F": None, "BUK": None}
                items.append(cur)
                tipe, kol = None, None
                continue
            if cur is None:
                continue
            if kol is not None:
                cs, ds = t[kol["no"]], t[kol["no"] + 1]
            if cs == "No" and ds.lower().startswith("uraian"):
                low = [v.lower() for v in t]

                def cari(pred):
                    return next((i for i, v in enumerate(low) if i > idx and pred(v)), None)

                kol = {
                    "no": idx,
                    "sat": cari(lambda v: v.startswith("sat")),
                    "koef": cari(lambda v: v.startswith("koef")),
                    "harga": cari(lambda v: "harga" in v and "satuan" in v and "jumlah" not in v),
                    "jumlah": cari(lambda v: v.startswith("jumlah harga") or v == "jumlah"),
                }
                continue
            if kol is None:
                continue
            if cs in ("A", "B", "C") and ds.upper() in TIPE_BLOK:
                tipe = TIPE_BLOK[ds.upper()]
                continue
            if cs == "E" and "keuntungan" in ds.lower():
                cur["BUK"] = _angka(row[kol["harga"]])
                tipe = None
                continue
            if cs == "F" and "harga satuan" in ds.lower():
                cur["F"] = _angka(row[kol["jumlah"]])
                cur, tipe = None, None
                continue
            if tipe and ds and not ds.upper().startswith("JUMLAH"):
                koef = _angka(row[kol["koef"]])
                if koef and koef > 0:
                    cur["komponen"].append(
                        (tipe, ds, t[kol["sat"]], round(koef, 6), round(_angka(row[kol["harga"]]) or 0.0, 4))
                    )
    return [i for i in items if i["komponen"] and i["F"]]


def tulis_modul(hsd: list, ahsp: list, sumber: str) -> None:
    baris = [
        '"""',
        f"Data HSPK hasil impor otomatis dari: {sumber}",
        "JANGAN diedit manual. Buat ulang dengan:  python tools/impor_hspk.py <file.xlsx>",
        "",
        "HSD  : (tipe, nama, satuan, harga) harga satuan dasar upah / bahan / alat.",
        "AHSP : kode HSPK -> (sheet, uraian, F, [(tipe, nama, satuan, koefisien, harga)])",
        "       F = harga satuan pekerjaan menurut dokumen (sudah termasuk BUK), untuk verifikasi.",
        '"""',
        "",
        f"SUMBER = {sumber!r}",
        "",
        "HSD = [",
    ]
    baris += [f"    {h!r}," for h in hsd]
    baris += ["]", "", "AHSP = {"]
    sudah = set()
    for i in ahsp:
        kode = i["kode"] if i["kode"] not in sudah else f"{i['kode']}@{i['sheet']}"
        sudah.add(kode)
        baris.append(f"    {kode!r}: ({i['sheet']!r}, {i['uraian']!r}, {round(i['F'], 4)!r}, [")
        baris += [f"        {k!r}," for k in i["komponen"]]
        baris.append("    ]),")
    baris += ["}", ""]
    TUJUAN.write_text("\n".join(baris), encoding="utf-8")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("xlsx", help="workbook HSPK (.xlsx)")
    ap.add_argument("--sumber", default="HSPK Kota Bandung 2027 (update setelah rapat 27 Agustus)")
    a = ap.parse_args()

    print("Membaca workbook ...")
    wb = openpyxl.load_workbook(a.xlsx, read_only=True, data_only=True)
    hsd = baca_hsd(wb)
    ahsp = baca_ahsp(wb)

    # verifikasi: koefisien x harga x (1 + BUK) harus sama dengan F di dokumen
    beda = []
    for i in ahsp:
        dasar = sum(k[3] * k[4] for k in i["komponen"])
        buk = i["BUK"] if i["BUK"] is not None else 0.1
        if abs(dasar * (1 + buk) - i["F"]) > max(1.0, 0.002 * i["F"]):
            beda.append(f"{i['sheet']} {i['kode']} {i['uraian'][:60]}")
    tulis_modul(hsd, ahsp, a.sumber)
    print(f"{len(hsd)} harga dasar, {len(ahsp)} analisa pekerjaan -> {TUJUAN}")
    if beda:
        print(f"{len(beda)} analisa tidak cocok dengan harga F dokumen (periksa sumbernya):")
        for b in beda:
            print("  -", b)
    return 0


if __name__ == "__main__":
    sys.exit(main())
