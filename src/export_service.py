"""
Export hasil estimasi RAB ke Excel (.xlsx) dan PDF (KF-8, KF-13, KF-17).

Isi dokumen:
- RAB              : bagian per kategori (I, II, ...), item per pekerjaan, jumlah tiap bagian, lalu
                     biaya langsung (A), biaya tidak langsung (B), PPN, total, dan pembulatan.
- Rekapitulasi     : ringkasan biaya (KF-13): A per kategori, rincian B, PPN, total, terbilang.
- RAB Rinci        : beton, bekisting, dan tulangan per tipe elemen (Kolom K1 20/25: 6 D13, ...).
- Kebutuhan Besi   : berat, panjang, dan jumlah batang 12 m per diameter.
- Detail Elemen    : volume tiap elemen dan lantai (KF-12), opsional dengan uraian rumus (KF-18).

KF-17: kolom No, Kode Analisa, Harga Satuan, Bobot (%), dan Rumus dapat dipilih; Uraian, Volume,
Satuan, dan Jumlah Harga selalu ada. Excel memakai rumus aktif (jumlah = volume x harga satuan).
"""

import logging
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from database.biaya_repository import ringkasan_biaya
from database.estimasi_repository import BUK_RATE, PPN_RATE, _connect, get_hasil_estimasi_by_proyek
from database.penulangan_repository import daftar_tipe, kebutuhan_besi
from rab_rinci import URUTAN_KATEGORI, susun_rinci, urutan_kategori

log = logging.getLogger("coststruct.export")

__all__ = ["URUTAN_KATEGORI", "OpsiExport", "ambil_data_export", "export_excel", "export_pdf", "kelompokkan"]

# KF-17: kolom yang bisa dipilih pengguna (kunci -> label)
KOLOM_OPSIONAL = {
    "no": "No",
    "kode": "Kode Analisa",
    "harga": "Harga Satuan",
    "bobot": "Bobot (%)",
    "rumus": "Uraian Rumus (detail elemen)",
}
KOLOM_BAWAAN = ("no", "kode", "harga")


@dataclass
class OpsiExport:
    kolom: tuple = KOLOM_BAWAAN
    rekap: bool = True
    rinci: bool = True
    besi: bool = True
    detail: bool = True
    orientasi_pdf: str = "portrait"  # portrait / landscape

    def ada(self, kunci: str) -> bool:
        return kunci in self.kolom


# ---------------------------------------------------------------- data


def ambil_data_export(proyek_id: int) -> dict:
    conn = _connect()
    try:
        pr = conn.execute("SELECT nama_proyek, path_file_ifc FROM proyek WHERE id = ?", (proyek_id,)).fetchone()
    finally:
        conn.close()
    if pr is None:
        raise ValueError("Proyek tidak ditemukan.")
    baris = [dict(r) for r in get_hasil_estimasi_by_proyek(proyek_id)]
    if not baris:
        raise ValueError("Belum ada hasil estimasi untuk di-export.")
    return {
        "nama_proyek": pr["nama_proyek"],
        "path_ifc": pr["path_file_ifc"],
        "baris": baris,
        "ringkasan": ringkasan_biaya(proyek_id),
        "besi": kebutuhan_besi(proyek_id),
        "tipe": daftar_tipe(proyek_id),
    }


def kelompokkan(baris: list) -> list:
    """Gabungkan semua elemen per pekerjaan, lalu kelompokkan per kategori.
    Return: [{'kategori', 'items': [{'kode','nama','satuan','volume','harga','jumlah'}], 'total'}]"""
    per_pekerjaan = {}
    for r in baris:
        d = per_pekerjaan.setdefault(r["pekerjaan_id"], {
            "kategori": r["kategori"], "kode": r["kode_ahsp"] or "", "nama": r["nama_pekerjaan"],
            "satuan": r["satuan"], "volume": 0.0, "jumlah": 0.0,
        })
        d["volume"] += r["volume_pekerjaan"]
        d["jumlah"] += r["subtotal_biaya"]
    per_kategori = {}
    for d in per_pekerjaan.values():
        d["harga"] = d["jumlah"] / d["volume"] if d["volume"] else 0.0
        per_kategori.setdefault(d["kategori"], []).append(d)
    hasil = []
    for k in sorted(per_kategori, key=urutan_kategori):
        items = sorted(per_kategori[k], key=lambda x: x["nama"])
        hasil.append({"kategori": k, "items": items, "total": sum(i["jumlah"] for i in items)})
    return hasil


def _entri_rab(baris: list) -> list:
    """Baris tabel RAB per pekerjaan: kategori, item, subtotal."""
    out = []
    for i, k in enumerate(kelompokkan(baris), 1):
        out.append({"jenis": "kategori", "no": f"{_romawi(i)}.", "uraian": k["kategori"].upper()})
        for n, it in enumerate(k["items"], 1):
            out.append({"jenis": "item", "no": str(n), "kode": it["kode"], "uraian": it["nama"],
                        "volume": it["volume"], "satuan": it["satuan"], "harga": it["harga"], "jumlah": it["jumlah"]})
        out.append({"jenis": "subtotal", "uraian": f"Jumlah {_romawi(i)}. {k['kategori']}", "jumlah": k["total"]})
    return out


def _entri_rinci(baris: list) -> list:
    """Baris tabel RAB rinci per tipe elemen."""
    out = []
    for i, k in enumerate(susun_rinci(baris), 1):
        out.append({"jenis": "kategori", "no": f"{_romawi(i)}.", "uraian": k["kategori"].upper()})
        nomor = 0
        for g in k["grup"]:
            if g["judul"]:
                nomor += 1
                out.append({"jenis": "grup", "no": str(nomor), "uraian": g["judul"]})
            for it in g["items"]:
                if g["judul"]:
                    no = "-"
                else:
                    nomor += 1
                    no = str(nomor)
                out.append({"jenis": "item", "no": no, "kode": it["kode"], "uraian": it["label"],
                            "volume": it["volume"], "satuan": it["satuan"], "harga": it["harga"],
                            "jumlah": it["jumlah"], "indent": bool(g["judul"])})
        out.append({"jenis": "subtotal", "uraian": f"Jumlah {_romawi(i)}. {k['kategori']}", "jumlah": k["total"]})
    return out


def baris_detail(baris: list) -> list:
    """Baris per elemen (KF-12/KF-18), diurutkan per lantai -> elemen -> kategori."""
    hasil = []
    for r in baris:
        v = r["volume_pekerjaan"]
        pekerjaan = r["nama_pekerjaan"]
        if r.get("uraian") and r.get("diameter"):
            pekerjaan += f" — {r['uraian']}"
        hasil.append({
            "lantai": r["lantai"] or "-",
            "elemen": r["nama_elemen"] or "-",
            "kategori": r["kategori"],
            "kode": r["kode_ahsp"] or "",
            "pekerjaan": pekerjaan,
            "satuan": r["satuan"],
            "volume": v,
            "harga": r["subtotal_biaya"] / v if v else 0.0,
            "jumlah": r["subtotal_biaya"],
            "status": "Manual" if r["diedit_manual"] else ("Dimensi diubah" if r.get("dimensi_manual") else "Otomatis"),
            "rumus": r.get("rumus") or "",
        })
    return sorted(hasil, key=lambda x: (x["lantai"], x["elemen"], x["kategori"], x["pekerjaan"]))


def nama_file_default(nama_proyek: str, ekstensi: str) -> str:
    slug = re.sub(r"[^\w\-]+", "_", nama_proyek, flags=re.UNICODE).strip("_") or "Proyek"
    return f"RAB_{slug}_{datetime.now():%Y%m%d}.{ekstensi}"


def _romawi(n: int) -> str:
    out = ""
    for nilai, sim in ((10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I")):
        while n >= nilai:
            out += sim
            n -= nilai
    return out


def _rp(x: float, desimal: int = 2) -> str:
    """Format Indonesia: 1.234.567,89"""
    return f"{x:,.{desimal}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _persen(x: float) -> str:
    return f"{x * 100:.2f}".replace(".", ",") + "%"


def _info_dokumen(data: dict, meta: dict) -> list:
    info = [("Pekerjaan", meta.get("nama_proyek") or data["nama_proyek"])]
    if meta.get("lokasi"):
        info.append(("Lokasi", meta["lokasi"]))
    if meta.get("pemilik"):
        info.append(("Pemilik / Instansi", meta["pemilik"]))
    if meta.get("tahun"):
        info.append(("Tahun Anggaran", str(meta["tahun"])))
    if data.get("path_ifc"):
        info.append(("Sumber QTO", f"Model IFC: {Path(data['path_ifc']).name}"))
    return info


def _label_btl(b: dict) -> str:
    if b["jenis"] == "persen":
        return f"{b['uraian']} ({_rp(b['nilai'], 2).rstrip('0').rstrip(',')}% × A)"
    return b["uraian"]


CATATAN = [
    "Volume dihitung otomatis dari model IFC (quantity take-off) dan dapat diedit manual pada aplikasi.",
    f"Harga satuan = analisa harga satuan (bahan + upah + alat) ditambah Biaya Umum & Keuntungan {BUK_RATE:.0%}.",
    "Pembesian dihitung per diameter dari tipe penulangan: W = Σ(π d²/4 × 7850 × L_eff × n) × 1,05.",
    f"PPN {PPN_RATE:.0%} dihitung dari jumlah biaya langsung dan biaya tidak langsung.",
]


def _kolom_tabel(opsi: OpsiExport, jenis: str = "rab") -> list:
    """Daftar (kunci, judul, lebar_excel, lebar_pdf_relatif) sesuai pilihan kolom (KF-17)."""
    k = []
    if opsi.ada("no"):
        k.append(("no", "No", 6, 0.6))
    if jenis == "detail":
        k += [("lantai", "Lantai", 14, 1.3), ("elemen", "Elemen", 26, 2.2)]
    if opsi.ada("kode"):
        k.append(("kode", "Kode Analisa", 16, 1.75))
    k.append(("uraian", "Uraian Pekerjaan", 52 if jenis != "detail" else 40, 4.6 if jenis != "detail" else 3.4))
    k += [("volume", "Volume", 13, 1.3), ("satuan", "Sat", 7, 0.75)]
    if opsi.ada("harga"):
        k.append(("harga", "Harga Satuan (Rp)", 18, 1.6))
    k.append(("jumlah", "Jumlah Harga (Rp)", 20, 1.8))
    if opsi.ada("bobot") and jenis != "detail":
        k.append(("bobot", "Bobot", 10, 1.0))
    if jenis == "detail":
        k.append(("status", "Status", 12, 1.1))
        if opsi.ada("rumus"):
            k.append(("rumus", "Uraian Rumus", 70, 5.0))
    return k


# ---------------------------------------------------------------- Excel


def export_excel(path, data: dict, meta: dict, opsi: OpsiExport | None = None) -> str:
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    from openpyxl.utils import get_column_letter as L

    opsi = opsi or OpsiExport()
    f_norm = Font(name="Arial", size=10)
    f_bold = Font(name="Arial", size=10, bold=True)
    f_judul = Font(name="Arial", size=14, bold=True)
    f_input = Font(name="Arial", size=10, color="0000FF")
    f_catatan = Font(name="Arial", size=9, italic=True)
    fill_head = PatternFill("solid", fgColor="D9D9D9")
    fill_kat = PatternFill("solid", fgColor="EEF3F8")
    fill_grup = PatternFill("solid", fgColor="F7F9FB")
    sisi = Side(style="thin", color="808080")
    kotak = Border(left=sisi, right=sisi, top=sisi, bottom=sisi)
    ANGKA, ANGKA3, PERSEN = "#,##0.00", "#,##0.000", "0.00%"
    ring = data["ringkasan"]
    wb = Workbook()

    def judul_sheet(ws, teks, n_kolom):
        ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=n_kolom)
        ws["A1"] = teks
        ws["A1"].font = f_judul
        ws["A1"].alignment = Alignment(horizontal="center")
        r = 2
        for label, nilai in _info_dokumen(data, meta):
            ws.cell(r, 1, f"{label} : {nilai}").font = f_norm
            r += 1
        return r + 1

    def header(ws, r, judul):
        for c, teks in enumerate(judul, 1):
            s = ws.cell(r, c, teks)
            s.font, s.fill, s.border = f_bold, fill_head, kotak
            s.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

    def gaya_baris(ws, r, n, font=f_norm, fill=None):
        for c in range(1, n + 1):
            s = ws.cell(r, c)
            s.font, s.border = font, kotak
            if fill:
                s.fill = fill

    def atur_cetak(ws, baris_header, orientasi="portrait"):
        ws.page_setup.orientation = orientasi
        ws.page_setup.paperSize = ws.PAPERSIZE_A4
        ws.page_setup.fitToWidth = 1
        ws.page_setup.fitToHeight = 0
        ws.sheet_properties.pageSetUpPr.fitToPage = True
        ws.print_title_rows = f"{baris_header}:{baris_header}"
        ws.freeze_panes = ws.cell(baris_header + 1, 1)
        ws.page_margins.left = ws.page_margins.right = 0.5

    def tulis_tabel(ws, r, kolom, entri):
        """Tulis tabel RAB (kategori / grup / item / subtotal). Return (r, baris_subtotal, baris_item)."""
        ci = {k[0]: i + 1 for i, k in enumerate(kolom)}
        n = len(kolom)
        c_uraian, c_jumlah = ci["uraian"], ci["jumlah"]
        sub, item_rows, awal = [], [], None
        for e in entri:
            if e["jenis"] == "kategori":
                gaya_baris(ws, r, n, f_bold, fill_kat)
                if "no" in ci:
                    ws.cell(r, ci["no"], e["no"])
                    ws.cell(r, c_uraian, e["uraian"])
                else:
                    ws.cell(r, c_uraian, f"{e['no']} {e['uraian']}")
                awal = r + 1
            elif e["jenis"] == "grup":
                gaya_baris(ws, r, n, f_bold, fill_grup)
                if "no" in ci:
                    ws.cell(r, ci["no"], e["no"]).alignment = Alignment(horizontal="center")
                ws.cell(r, c_uraian, e["uraian"])
            elif e["jenis"] == "item":
                gaya_baris(ws, r, n)
                for kunci in ("no", "kode", "satuan"):
                    if kunci in ci:
                        ws.cell(r, ci[kunci], e[kunci]).alignment = Alignment(
                            horizontal="center" if kunci != "kode" else "left", vertical="top"
                        )
                s = ws.cell(r, c_uraian, ("    " if e.get("indent") else "") + e["uraian"])
                s.alignment = Alignment(wrap_text=True, vertical="top")
                ws.cell(r, ci["volume"], e["volume"]).number_format = ANGKA
                if "harga" in ci:
                    ws.cell(r, ci["harga"], e["harga"]).number_format = ANGKA
                    ws.cell(r, c_jumlah, f"={L(ci['volume'])}{r}*{L(ci['harga'])}{r}")
                else:
                    ws.cell(r, c_jumlah, e["jumlah"])
                ws.cell(r, c_jumlah).number_format = ANGKA
                item_rows.append(r)
            elif e["jenis"] == "subtotal":
                gaya_baris(ws, r, n, f_bold)
                ws.cell(r, c_uraian, e["uraian"]).alignment = Alignment(horizontal="right")
                ws.cell(r, c_jumlah, f"=SUM({L(c_jumlah)}{awal}:{L(c_jumlah)}{r - 1})").number_format = ANGKA
                sub.append(r)
            r += 1
        return r, sub, item_rows

    def isi_bobot(ws, kolom, rows, ref_total):
        ci = {k[0]: i + 1 for i, k in enumerate(kolom)}
        if "bobot" not in ci:
            return
        for r in rows:
            s = ws.cell(r, ci["bobot"], f"=IF({ref_total}=0,0,{L(ci['jumlah'])}{r}/{ref_total})")
            s.number_format = PERSEN

    # ---------- Sheet RAB ----------
    ws = wb.active
    ws.title = "RAB"
    kolom = _kolom_tabel(opsi)
    for i, k in enumerate(kolom, 1):
        ws.column_dimensions[L(i)].width = k[2]
    r = judul_sheet(ws, "RENCANA ANGGARAN BIAYA (RAB)", len(kolom))
    hdr = r
    header(ws, r, [k[1] for k in kolom])
    r, sub_rab, item_rab = tulis_tabel(ws, r + 1, kolom, _entri_rab(data["baris"]))
    ci = {k[0]: i + 1 for i, k in enumerate(kolom)}
    cu, cj = ci["uraian"], L(ci["jumlah"])
    r += 1

    def baris_total(ws, r, teks, rumus, fmt=ANGKA, n=len(kolom)):
        gaya_baris(ws, r, n, f_bold)
        ws.cell(r, cu, teks).alignment = Alignment(horizontal="right")
        ws.cell(r, ci["jumlah"], rumus).number_format = fmt
        return r

    rA = baris_total(ws, r, "A. JUMLAH BIAYA LANGSUNG", "=" + "+".join(f"{cj}{x}" for x in sub_rab))
    baris_A = rA
    pct = sum(b["nilai"] for b in ring["item_tidak_langsung"] if b["jenis"] == "persen") / 100
    tetap = sum(b["nilai"] for b in ring["item_tidak_langsung"] if b["jenis"] == "nilai")
    rB = baris_total(ws, r + 1, "B. BIAYA TIDAK LANGSUNG (rincian di sheet Rekapitulasi)",
                     f"={cj}{rA}*{pct!r}+{tetap!r}")
    rJ = baris_total(ws, r + 2, "JUMLAH (A + B)", f"={cj}{rA}+{cj}{rB}")
    rP = baris_total(ws, r + 3, f"PPN {PPN_RATE:.0%}", f"={cj}{rJ}*{PPN_RATE!r}")
    rT = baris_total(ws, r + 4, "TOTAL", f"={cj}{rJ}+{cj}{rP}")
    baris_total(ws, r + 5, "TOTAL DIBULATKAN", f"=ROUNDDOWN({cj}{rT},-3)")
    isi_bobot(ws, kolom, item_rab + sub_rab, f"${cj}${rA}")
    r += 7
    ws.cell(r, 1, f"Terbilang: {ring['terbilang']}").font = Font(name="Arial", size=10, italic=True, bold=True)
    r += 2
    ws.cell(r, 1, "Catatan:").font = f_catatan
    for teks in CATATAN:
        r += 1
        ws.cell(r, 1, f"- {teks}").font = f_catatan
    atur_cetak(ws, hdr)
    ref_kat = {e["uraian"]: f"RAB!{cj}{x}" for e, x in zip([e for e in _entri_rab(data["baris"]) if e["jenis"] == "subtotal"], sub_rab)}

    # ---------- Sheet Rekapitulasi (KF-13) ----------
    if opsi.rekap:
        wr = wb.create_sheet("Rekapitulasi")
        for kol, lebar in zip("ABCD", (7, 60, 24, 12)):
            wr.column_dimensions[kol].width = lebar
        r = judul_sheet(wr, "REKAPITULASI RENCANA ANGGARAN BIAYA", 4)
        hdr = r
        header(wr, r, ["No", "Uraian", "Jumlah (Rp)", "Bobot"])
        r += 1
        gaya_baris(wr, r, 4, f_bold, fill_kat)
        wr.cell(r, 1, "A")
        wr.cell(r, 2, "BIAYA LANGSUNG")
        r += 1
        awalA = r
        for i, nama in enumerate(ref_kat, 1):
            gaya_baris(wr, r, 4)
            wr.cell(r, 1, _romawi(i)).alignment = Alignment(horizontal="center")
            wr.cell(r, 2, nama.split(". ", 1)[1])
            wr.cell(r, 3, f"={ref_kat[nama]}").number_format = ANGKA
            r += 1
        rA = r
        gaya_baris(wr, r, 4, f_bold)
        wr.cell(r, 2, "Jumlah A").alignment = Alignment(horizontal="right")
        wr.cell(r, 3, f"=SUM(C{awalA}:C{r - 1})").number_format = ANGKA
        for x in range(awalA, r + 1):
            wr.cell(x, 4, f"=IF($C${rA}=0,0,C{x}/$C${rA})").number_format = PERSEN
        r += 1
        gaya_baris(wr, r, 4, f_bold, fill_kat)
        wr.cell(r, 1, "B")
        wr.cell(r, 2, "BIAYA TIDAK LANGSUNG")
        r += 1
        awalB = r
        for i, b in enumerate(ring["item_tidak_langsung"], 1):
            gaya_baris(wr, r, 4)
            wr.cell(r, 1, i).alignment = Alignment(horizontal="center")
            wr.cell(r, 2, _label_btl(b))
            if b["jenis"] == "persen":
                wr.cell(r, 4, b["nilai"] / 100).number_format = PERSEN
                wr.cell(r, 4).font = f_input  # sel biru = nilai input
                wr.cell(r, 3, f"=C${rA}*D{r}")
            else:
                wr.cell(r, 3, b["nilai"]).font = f_input
            wr.cell(r, 3).number_format = ANGKA
            r += 1
        if not ring["item_tidak_langsung"]:
            gaya_baris(wr, r, 4)
            wr.cell(r, 2, "Tidak ada (diperhitungkan terpisah oleh pengguna)").font = f_catatan
            wr.cell(r, 3, 0).number_format = ANGKA
            r += 1
        rB = r
        gaya_baris(wr, r, 4, f_bold)
        wr.cell(r, 2, "Jumlah B").alignment = Alignment(horizontal="right")
        wr.cell(r, 3, f"=SUM(C{awalB}:C{r - 1})").number_format = ANGKA
        r += 2
        for teks, rumus in (
            ("JUMLAH (A + B)", f"=C{rA}+C{rB}"),
            (f"PPN {PPN_RATE:.0%}", f"=C{r}*{PPN_RATE!r}"),
            ("TOTAL", f"=C{r}+C{r + 1}"),
            ("TOTAL DIBULATKAN", f"=ROUNDDOWN(C{r + 2},-3)"),
        ):
            gaya_baris(wr, r, 4, f_bold)
            wr.cell(r, 2, teks).alignment = Alignment(horizontal="right")
            wr.cell(r, 3, rumus).number_format = ANGKA
            r += 1
        r += 1
        wr.cell(r, 1, f"Terbilang: {ring['terbilang']}").font = Font(name="Arial", size=10, italic=True, bold=True)
        r += 1
        wr.cell(r, 1, f"Biaya umum & keuntungan {BUK_RATE:.0%} sudah termasuk dalam harga satuan "
                      f"(± Rp {_rp(ring['buk'], 0)} dari biaya langsung).").font = f_catatan
        atur_cetak(wr, hdr)

    # ---------- Sheet RAB Rinci ----------
    if opsi.rinci:
        wi = wb.create_sheet("RAB Rinci")
        for i, k in enumerate(kolom, 1):
            wi.column_dimensions[L(i)].width = k[2]
        r = judul_sheet(wi, "RAB RINCI PER TIPE ELEMEN", len(kolom))
        hdr = r
        header(wi, r, [k[1] for k in kolom])
        r, sub, items = tulis_tabel(wi, r + 1, kolom, _entri_rinci(data["baris"]))
        r += 1
        gaya_baris(wi, r, len(kolom), f_bold)
        wi.cell(r, cu, "JUMLAH BIAYA LANGSUNG").alignment = Alignment(horizontal="right")
        wi.cell(r, ci["jumlah"], "=" + "+".join(f"{cj}{x}" for x in sub)).number_format = ANGKA
        isi_bobot(wi, kolom, items + sub, f"${cj}${r}")
        r += 2
        wi.cell(r, 1, "Selisih terhadap sheet RAB (harus 0):").font = f_catatan
        wi.cell(r, ci["jumlah"], f"={cj}{r - 2}-RAB!{cj}{baris_A}")
        wi.cell(r, ci["jumlah"]).number_format = ANGKA
        wi.cell(r, ci["jumlah"]).font = f_catatan
        atur_cetak(wi, hdr)

    # ---------- Sheet Kebutuhan Besi ----------
    if opsi.besi and data["besi"]:
        wb_ = wb.create_sheet("Kebutuhan Besi")
        for kol, lebar in zip("ABCDEFG", (6, 12, 16, 14, 16, 16, 14)):
            wb_.column_dimensions[kol].width = lebar
        r = judul_sheet(wb_, "KEBUTUHAN BESI TULANGAN PER DIAMETER", 7)
        hdr = r
        header(wb_, r, ["No", "Diameter", "Jenis Baja", "Berat (kg/m')", "Panjang Total (m)", "Berat Total (kg)", "Batang 12 m"])
        r += 1
        awal = r
        for i, k in enumerate(data["besi"], 1):
            gaya_baris(wb_, r, 7)
            wb_.cell(r, 1, i).alignment = Alignment(horizontal="center")
            wb_.cell(r, 2, k["label"])
            wb_.cell(r, 3, k["jenis"])
            wb_.cell(r, 4, f"=PI()*{k['diameter']!r}^2/4*7850/1000000").number_format = ANGKA3
            wb_.cell(r, 6, k["berat"]).number_format = ANGKA
            wb_.cell(r, 5, f"=F{r}/D{r}").number_format = ANGKA
            wb_.cell(r, 7, f"=ROUNDUP(E{r}/12,0)")
            r += 1
        gaya_baris(wb_, r, 7, f_bold)
        wb_.cell(r, 3, "JUMLAH")
        wb_.cell(r, 6, f"=SUM(F{awal}:F{r - 1})").number_format = ANGKA
        wb_.cell(r, 7, f"=SUM(G{awal}:G{r - 1})")
        r += 2
        wb_.cell(r, 1, "Berat termasuk sisa potongan 5% (Rumus 2.33). Rincian tipe penulangan:").font = f_catatan
        for t in data["tipe"]:
            r += 1
            wb_.cell(r, 2, f"{t['label']} — {t['jumlah_elemen']} buah: {t['ringkas']}").font = f_norm
        atur_cetak(wb_, hdr)

    # ---------- Sheet Detail Elemen ----------
    if opsi.detail:
        wd = wb.create_sheet("Detail Elemen")
        kd = _kolom_tabel(opsi, "detail")
        cd = {k[0]: i + 1 for i, k in enumerate(kd)}
        for i, k in enumerate(kd, 1):
            wd.column_dimensions[L(i)].width = k[2]
        r = judul_sheet(wd, "DETAIL VOLUME PER ELEMEN & LANTAI", len(kd))
        hdr = r
        header(wd, r, [k[1] for k in kd])
        r += 1
        awal = r
        for n, d in enumerate(baris_detail(data["baris"]), 1):
            gaya_baris(wd, r, len(kd))
            nilai = {**d, "no": n, "uraian": d["pekerjaan"]}
            for kunci, idx in cd.items():
                if kunci == "jumlah":
                    continue
                s = wd.cell(r, idx, nilai[kunci])
                if kunci in ("volume", "harga"):
                    s.number_format = ANGKA
                if kunci in ("uraian", "rumus"):
                    s.alignment = Alignment(wrap_text=True, vertical="top")
            if "harga" in cd:
                wd.cell(r, cd["jumlah"], f"={L(cd['volume'])}{r}*{L(cd['harga'])}{r}")
            else:
                wd.cell(r, cd["jumlah"], d["jumlah"])
            wd.cell(r, cd["jumlah"]).number_format = ANGKA
            r += 1
        gaya_baris(wd, r, len(kd), f_bold)
        wd.cell(r, cd["uraian"], "JUMLAH").alignment = Alignment(horizontal="right")
        cdj = L(cd["jumlah"])
        wd.cell(r, cd["jumlah"], f"=SUM({cdj}{awal}:{cdj}{r - 1})").number_format = ANGKA
        r += 2
        wd.cell(r, cd["uraian"], "Selisih terhadap sheet RAB (harus 0)").font = f_catatan
        wd.cell(r, cd["jumlah"], f"={cdj}{r - 2}-RAB!{cj}{baris_A}").number_format = ANGKA
        wd.cell(r, cd["jumlah"]).font = f_catatan
        atur_cetak(wd, hdr, "landscape")

    wb.save(str(path))
    log.info("Export Excel: %s", path)
    return str(path)


# ---------------------------------------------------------------- PDF


def export_pdf(path, data: dict, meta: dict, opsi: OpsiExport | None = None) -> str:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    opsi = opsi or OpsiExport()
    ukuran = landscape(A4) if opsi.orientasi_pdf == "landscape" else A4
    lebar_isi = ukuran[0] - 2.8 * cm
    nama = meta.get("nama_proyek") or data["nama_proyek"]
    ring = data["ringkasan"]
    total_A = ring["langsung"] or 1.0

    s_judul = ParagraphStyle("judul", fontName="Helvetica-Bold", fontSize=13, alignment=1, spaceAfter=6)
    s_info = ParagraphStyle("info", fontName="Helvetica", fontSize=9, leading=12)
    s_sel = ParagraphStyle("sel", fontName="Helvetica", fontSize=8, leading=10)
    s_selb = ParagraphStyle("selb", parent=s_sel, fontName="Helvetica-Bold")
    s_head = ParagraphStyle("head", parent=s_selb, alignment=1)
    s_kanan = ParagraphStyle("kanan", parent=s_selb, alignment=2)
    s_cat = ParagraphStyle("cat", fontName="Helvetica-Oblique", fontSize=7.5, leading=9, textColor=colors.HexColor("#444444"))
    s_mono = ParagraphStyle("mono", fontName="Courier", fontSize=6.5, leading=8)

    abu, biru, muda = colors.HexColor("#D9D9D9"), colors.HexColor("#EEF3F8"), colors.HexColor("#F7F9FB")
    dasar = [
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#808080")),
        ("BACKGROUND", (0, 0), (-1, 0), abu),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 2.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
        ("FONTSIZE", (0, 1), (-1, -1), 8),
    ]

    def footer(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(colors.HexColor("#666666"))
        canvas.drawString(1.4 * cm, 0.9 * cm, f"{nama}  |  Dibuat dengan CostStruct, {datetime.now():%d-%m-%Y %H:%M}")
        canvas.drawRightString(ukuran[0] - 1.4 * cm, 0.9 * cm, f"Halaman {doc.page}")
        canvas.restoreState()

    def kop(teks):
        out = [Paragraph(teks, s_judul)]
        for label, nilai in _info_dokumen(data, meta):
            out.append(Paragraph(f"<b>{label}</b> : {_esc(nilai)}", s_info))
        out.append(Spacer(1, 8))
        return out

    def lebar(kolom):
        total = sum(k[3] for k in kolom)
        return [lebar_isi * k[3] / total for k in kolom]

    def tabel_rab(entri, kolom):
        ci = {k[0]: i for i, k in enumerate(kolom)}
        isi = [[Paragraph(k[1], s_head) for k in kolom]]
        gaya = list(dasar)
        n = len(kolom)
        for e in entri:
            baris = [""] * n
            i = len(isi)
            if e["jenis"] in ("kategori", "grup"):
                st = s_selb
                if "no" in ci:
                    baris[ci["no"]] = Paragraph(e["no"], st)
                    baris[ci["uraian"]] = Paragraph(_esc(e["uraian"]), st)
                else:
                    baris[ci["uraian"]] = Paragraph(_esc(f"{e['no']} {e['uraian']}"), st)
                gaya.append(("BACKGROUND", (0, i), (-1, i), biru if e["jenis"] == "kategori" else muda))
            elif e["jenis"] == "item":
                if "no" in ci:
                    baris[ci["no"]] = e["no"]
                if "kode" in ci:
                    baris[ci["kode"]] = Paragraph(_esc(e["kode"]), s_sel)
                pref = "&nbsp;&nbsp;&nbsp;&nbsp;" if e.get("indent") else ""
                baris[ci["uraian"]] = Paragraph(pref + _esc(e["uraian"]), s_sel)
                baris[ci["volume"]] = _rp(e["volume"])
                baris[ci["satuan"]] = e["satuan"]
                if "harga" in ci:
                    baris[ci["harga"]] = _rp(e["harga"])
                baris[ci["jumlah"]] = _rp(e["jumlah"])
                if "bobot" in ci:
                    baris[ci["bobot"]] = _persen(e["jumlah"] / total_A)
            else:  # subtotal
                baris[ci["uraian"]] = Paragraph(_esc(e["uraian"]), s_kanan)
                baris[ci["jumlah"]] = _rp(e["jumlah"])
                if "bobot" in ci:
                    baris[ci["bobot"]] = _persen(e["jumlah"] / total_A)
                gaya += [("FONTNAME", (0, i), (-1, i), "Helvetica-Bold"),
                         ("LINEABOVE", (0, i), (-1, i), 0.8, colors.black)]
            isi.append(baris)
        for kunci in ("volume", "harga", "jumlah", "bobot"):
            if kunci in ci:
                gaya.append(("ALIGN", (ci[kunci], 1), (ci[kunci], -1), "RIGHT"))
        for kunci in ("no", "satuan"):
            if kunci in ci:
                gaya.append(("ALIGN", (ci[kunci], 1), (ci[kunci], -1), "CENTER"))
        t = Table(isi, colWidths=lebar(kolom), repeatRows=1)
        t.setStyle(TableStyle(gaya))
        return t

    def tabel_ringkas(baris, tebal_dari=0):
        t = Table(baris, colWidths=[lebar_isi - 4.2 * cm, 4.2 * cm], hAlign="RIGHT")
        t.setStyle(TableStyle([
            ("FONTNAME", (0, tebal_dari), (-1, -1), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("ALIGN", (0, 0), (-1, -1), "RIGHT"),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#808080")),
            ("BACKGROUND", (0, -1), (-1, -1), abu),
        ]))
        return t

    kolom = _kolom_tabel(opsi)
    story = kop("RENCANA ANGGARAN BIAYA (RAB)")
    story.append(tabel_rab(_entri_rab(data["baris"]), kolom))
    story.append(Spacer(1, 8))
    story.append(tabel_ringkas([
        ["A. JUMLAH BIAYA LANGSUNG", _rp(ring["langsung"])],
        ["B. BIAYA TIDAK LANGSUNG", _rp(ring["tidak_langsung"])],
        ["JUMLAH (A + B)", _rp(ring["jumlah"])],
        [f"PPN {PPN_RATE:.0%}", _rp(ring["ppn"])],
        ["TOTAL", _rp(ring["total"])],
        ["TOTAL DIBULATKAN", _rp(ring["dibulatkan"], 0)],
    ]))
    story.append(Spacer(1, 6))
    story.append(Paragraph(f"<b><i>Terbilang: {_esc(ring['terbilang'])}</i></b>", s_info))
    story.append(Spacer(1, 8))
    story.append(Paragraph("Catatan:", s_cat))
    for teks in CATATAN:
        story.append(Paragraph(f"- {_esc(teks)}", s_cat))

    if opsi.rekap:
        story += [PageBreak()] + kop("REKAPITULASI RENCANA ANGGARAN BIAYA")
        rb = [[Paragraph(t, s_head) for t in ("No", "Uraian", "Jumlah (Rp)", "Bobot")]]
        gaya = list(dasar) + [("ALIGN", (2, 1), (3, -1), "RIGHT"), ("ALIGN", (0, 1), (0, -1), "CENTER")]

        def tambah(baris, tebal=False, latar=None):
            rb.append(baris)
            i = len(rb) - 1
            if tebal:
                gaya.append(("FONTNAME", (0, i), (-1, i), "Helvetica-Bold"))
            if latar:
                gaya.append(("BACKGROUND", (0, i), (-1, i), latar))

        tambah(["A", "BIAYA LANGSUNG", "", ""], True, biru)
        for i, k in enumerate(kelompokkan(data["baris"]), 1):
            tambah([_romawi(i), k["kategori"], _rp(k["total"]), _persen(k["total"] / total_A)])
        tambah(["", "Jumlah A", _rp(ring["langsung"]), "100,00%"], True)
        tambah(["B", "BIAYA TIDAK LANGSUNG", "", ""], True, biru)
        for i, b in enumerate(ring["item_tidak_langsung"], 1):
            tambah([str(i), Paragraph(_esc(_label_btl(b)), s_sel), _rp(b["jumlah"]), ""])
        if not ring["item_tidak_langsung"]:
            tambah(["", "Tidak ada (diperhitungkan terpisah oleh pengguna)", _rp(0), ""])
        tambah(["", "Jumlah B", _rp(ring["tidak_langsung"]), ""], True)
        for teks, nilai in (("JUMLAH (A + B)", ring["jumlah"]), (f"PPN {PPN_RATE:.0%}", ring["ppn"]),
                            ("TOTAL", ring["total"])):
            tambah(["", teks, _rp(nilai), ""], True)
        tambah(["", "TOTAL DIBULATKAN", _rp(ring["dibulatkan"], 0), ""], True, abu)
        t = Table(rb, colWidths=[1.2 * cm, lebar_isi - 8.4 * cm, 4.6 * cm, 2.6 * cm], repeatRows=1)
        t.setStyle(TableStyle(gaya))
        story += [t, Spacer(1, 6), Paragraph(f"<b><i>Terbilang: {_esc(ring['terbilang'])}</i></b>", s_info),
                  Spacer(1, 4),
                  Paragraph(f"Biaya umum & keuntungan {BUK_RATE:.0%} sudah termasuk dalam harga satuan "
                            f"(± Rp {_rp(ring['buk'], 0)} dari biaya langsung).", s_cat)]

    if opsi.rinci:
        story += [PageBreak()] + kop("RAB RINCI PER TIPE ELEMEN")
        story.append(tabel_rab(_entri_rinci(data["baris"]), kolom))

    if opsi.besi and data["besi"]:
        story += [PageBreak()] + kop("KEBUTUHAN BESI TULANGAN PER DIAMETER")
        bb = [[Paragraph(t, s_head) for t in ("No", "Diameter", "Jenis Baja", "Berat (kg/m')", "Panjang (m)", "Berat (kg)", "Batang 12 m")]]
        for i, k in enumerate(data["besi"], 1):
            bb.append([str(i), k["label"], k["jenis"], _rp(k["berat_per_m"], 3), _rp(k["panjang"]), _rp(k["berat"]), str(k["batang"])])
        bb.append(["", "", "JUMLAH", "", "", _rp(sum(k["berat"] for k in data["besi"])), str(sum(k["batang"] for k in data["besi"]))])
        t = Table(bb, colWidths=[lebar_isi * x for x in (0.07, 0.12, 0.2, 0.14, 0.16, 0.16, 0.15)], repeatRows=1)
        t.setStyle(TableStyle(dasar + [("ALIGN", (3, 1), (-1, -1), "RIGHT"), ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold")]))
        story.append(t)
        story.append(Spacer(1, 6))
        story.append(Paragraph("Berat termasuk sisa potongan 5% (Rumus 2.33). Tipe penulangan:", s_cat))
        for tp in data["tipe"]:
            story.append(Paragraph(_esc(f"• {tp['label']} — {tp['jumlah_elemen']} buah: {tp['ringkas']}"), s_info))

    if opsi.detail:
        story += [PageBreak()] + kop("DETAIL VOLUME PER ELEMEN & LANTAI")
        kd = _kolom_tabel(opsi, "detail")
        cd = {k[0]: i for i, k in enumerate(kd)}
        db = [[Paragraph(k[1], s_head) for k in kd]]
        for n, d in enumerate(baris_detail(data["baris"]), 1):
            baris = [""] * len(kd)
            nilai = {**d, "no": str(n), "uraian": d["pekerjaan"]}
            for kunci, idx in cd.items():
                v = nilai[kunci]
                if kunci in ("volume",):
                    baris[idx] = _rp(v, 3)
                elif kunci in ("harga", "jumlah"):
                    baris[idx] = _rp(v)
                elif kunci == "rumus":
                    baris[idx] = Paragraph(_esc(v), s_mono)
                elif kunci in ("lantai", "elemen", "uraian", "kode"):
                    baris[idx] = Paragraph(_esc(v), s_sel)
                else:
                    baris[idx] = v
            db.append(baris)
        gaya = list(dasar)
        for kunci in ("volume", "harga", "jumlah"):
            if kunci in cd:
                gaya.append(("ALIGN", (cd[kunci], 1), (cd[kunci], -1), "RIGHT"))
        t = Table(db, colWidths=lebar(kd), repeatRows=1)
        t.setStyle(TableStyle(gaya))
        story.append(t)

    doc = SimpleDocTemplate(
        str(path), pagesize=ukuran, leftMargin=1.4 * cm, rightMargin=1.4 * cm, topMargin=1.4 * cm,
        bottomMargin=1.6 * cm, title=f"RAB {nama}", author="CostStruct",
    )
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    log.info("Export PDF: %s", path)
    return str(path)


def _esc(teks) -> str:
    return str(teks).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
