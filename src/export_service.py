"""
Export hasil estimasi RAB ke Excel (.xlsx) dan PDF (KF-8).
Format mengikuti BQ/RAB: bagian per kategori pekerjaan (I, II, ...), uraian, volume, satuan,
harga satuan, jumlah harga, total per bagian, lalu jumlah total + PPN.
"""

import logging
import re
from datetime import datetime
from pathlib import Path

from database.estimasi_repository import _connect, BUK_RATE, PPN_RATE

log = logging.getLogger("coststruct.export")

# Urutan bagian dalam dokumen (kategori lain menyusul sesuai abjad)
URUTAN_KATEGORI = ["Tanah", "Fondasi", "Beton", "Dinding", "Atap", "Cat", "Air Limbah"]

_SQL_HASIL = """
    SELECT he.id AS hasil_id, he.pekerjaan_id, he.volume_pekerjaan, he.subtotal_biaya, he.diedit_manual,
           p.kode_ahsp, p.nama_pekerjaan, p.kategori, p.satuan,
           ep.nama AS nama_elemen, ep.lantai
    FROM hasil_estimasi he
    JOIN pekerjaan p ON p.id = he.pekerjaan_id
    LEFT JOIN elemen_proyek ep ON ep.id = he.elemen_id
    WHERE he.proyek_id = ?
    ORDER BY p.kategori, p.nama_pekerjaan, ep.lantai, ep.nama
"""


# ---------------------------------------------------------------- data


def ambil_data_export(proyek_id: int) -> dict:
    conn = _connect()
    try:
        pr = conn.execute(
            "SELECT nama_proyek, path_file_ifc FROM proyek WHERE id = ?", (proyek_id,)
        ).fetchone()
        if pr is None:
            raise ValueError("Proyek tidak ditemukan.")
        baris = [dict(r) for r in conn.execute(_SQL_HASIL, (proyek_id,)).fetchall()]
    finally:
        conn.close()
    if not baris:
        raise ValueError("Belum ada hasil estimasi untuk di-export.")
    return {
        "nama_proyek": pr["nama_proyek"],
        "path_ifc": pr["path_file_ifc"],
        "baris": baris,
    }


def kelompokkan(baris: list) -> list:
    """Gabungkan semua elemen per pekerjaan, lalu kelompokkan per kategori.
    Return: [{'kategori', 'items': [{'kode','nama','satuan','volume','harga','jumlah'}], 'total'}]"""
    per_pekerjaan = {}
    for r in baris:
        d = per_pekerjaan.setdefault(
            r["pekerjaan_id"],
            {
                "kategori": r["kategori"],
                "kode": r["kode_ahsp"] or "",
                "nama": r["nama_pekerjaan"],
                "satuan": r["satuan"],
                "volume": 0.0,
                "jumlah": 0.0,
            },
        )
        d["volume"] += r["volume_pekerjaan"]
        d["jumlah"] += r["subtotal_biaya"]

    per_kategori = {}
    for d in per_pekerjaan.values():
        d["harga"] = d["jumlah"] / d["volume"] if d["volume"] else 0.0
        per_kategori.setdefault(d["kategori"], []).append(d)

    def urutan(k):
        return (
            URUTAN_KATEGORI.index(k) if k in URUTAN_KATEGORI else len(URUTAN_KATEGORI),
            k,
        )

    hasil = []
    for k in sorted(per_kategori, key=urutan):
        items = sorted(per_kategori[k], key=lambda x: x["nama"])
        hasil.append(
            {"kategori": k, "items": items, "total": sum(i["jumlah"] for i in items)}
        )
    return hasil


def baris_detail(baris: list) -> list:
    """Baris per elemen (KF-12/KF-18), diurutkan per lantai -> elemen -> kategori."""
    hasil = []
    for r in baris:
        v = r["volume_pekerjaan"]
        hasil.append(
            {
                "lantai": r["lantai"] or "-",
                "elemen": r["nama_elemen"] or "-",
                "kategori": r["kategori"],
                "pekerjaan": r["nama_pekerjaan"],
                "satuan": r["satuan"],
                "volume": v,
                "harga": r["subtotal_biaya"] / v if v else 0.0,
                "jumlah": r["subtotal_biaya"],
                "status": "Manual" if r["diedit_manual"] else "Otomatis",
            }
        )
    return sorted(
        hasil, key=lambda x: (x["lantai"], x["elemen"], x["kategori"], x["pekerjaan"])
    )


def nama_file_default(nama_proyek: str, ekstensi: str) -> str:
    slug = (
        re.sub(r"[^\w\-]+", "_", nama_proyek, flags=re.UNICODE).strip("_") or "Proyek"
    )
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


def _info_dokumen(data: dict, meta: dict) -> list:
    info = [("Pekerjaan", meta.get("nama_proyek") or data["nama_proyek"])]
    if meta.get("lokasi"):
        info.append(("Lokasi", meta["lokasi"]))
    if meta.get("tahun"):
        info.append(("Tahun Anggaran", str(meta["tahun"])))
    if data.get("path_ifc"):
        info.append(("Sumber QTO", f"Model IFC: {Path(data['path_ifc']).name}"))
    return info


CATATAN = [
    "Volume dihitung otomatis dari model IFC (quantity take-off) dan dapat diedit manual pada aplikasi.",
    f"Harga satuan = analisa harga satuan (bahan + upah + alat) ditambah Biaya Umum & Keuntungan {BUK_RATE:.0%}.",
    f"PPN {PPN_RATE:.0%} dihitung otomatis dari jumlah total.",
]


# ---------------------------------------------------------------- Excel


def export_excel(
    path, data: dict, meta: dict, rekap: bool = True, detail: bool = True
) -> str:
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side

    f_norm = Font(name="Arial", size=10)
    f_bold = Font(name="Arial", size=10, bold=True)
    f_judul = Font(name="Arial", size=14, bold=True)
    f_input = Font(name="Arial", size=10, color="0000FF")
    f_catatan = Font(name="Arial", size=9, italic=True)
    fill_head = PatternFill("solid", fgColor="D9D9D9")
    fill_kat = PatternFill("solid", fgColor="EEF3F8")
    sisi = Side(style="thin", color="808080")
    kotak = Border(left=sisi, right=sisi, top=sisi, bottom=sisi)
    FMT_ANGKA = "#,##0.00"

    kelompok = kelompokkan(data["baris"])
    wb = Workbook()

    def judul_sheet(ws, teks, lebar_kolom):
        ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=lebar_kolom)
        ws["A1"] = teks
        ws["A1"].font = f_judul
        ws["A1"].alignment = Alignment(horizontal="center")
        r = 2
        for label, nilai in _info_dokumen(data, meta):
            ws.cell(r, 1, f"{label} : {nilai}").font = f_norm
            r += 1
        return r + 1  # satu baris kosong

    def header(ws, r, judul_kolom):
        for c, teks in enumerate(judul_kolom, 1):
            sel = ws.cell(r, c, teks)
            sel.font, sel.fill, sel.border = f_bold, fill_head, kotak
            sel.alignment = Alignment(
                horizontal="center", vertical="center", wrap_text=True
            )

    def atur_cetak(ws, baris_header, orientasi="portrait"):
        ws.page_setup.orientation = orientasi
        ws.page_setup.paperSize = ws.PAPERSIZE_A4
        ws.page_setup.fitToWidth = 1
        ws.page_setup.fitToHeight = 0
        ws.sheet_properties.pageSetUpPr.fitToPage = True
        ws.print_title_rows = f"{baris_header}:{baris_header}"
        ws.freeze_panes = ws.cell(baris_header + 1, 1)
        ws.page_margins.left = ws.page_margins.right = 0.5

    # ---------- Sheet RAB ----------
    ws = wb.active
    ws.title = "RAB"
    for kolom, lebar in zip("ABCDEFG", (6, 16, 54, 13, 8, 19, 21)):
        ws.column_dimensions[kolom].width = lebar
    r = judul_sheet(ws, "RENCANA ANGGARAN BIAYA (RAB)", 7)
    baris_header = r
    header(
        ws,
        r,
        [
            "No",
            "Kode Analisa",
            "Uraian Pekerjaan",
            "Volume",
            "Sat",
            "Harga Satuan (Rp)",
            "Jumlah Harga (Rp)",
        ],
    )
    r += 1

    baris_total_kategori = []
    for i, k in enumerate(kelompok, 1):
        for c in range(1, 8):
            ws.cell(r, c).fill, ws.cell(r, c).border = fill_kat, kotak
        ws.cell(r, 1, f"{_romawi(i)}.").font = f_bold
        ws.cell(r, 3, k["kategori"].upper()).font = f_bold
        r += 1
        awal = r
        for n, it in enumerate(k["items"], 1):
            ws.cell(r, 1, n)
            ws.cell(r, 2, it["kode"])
            ws.cell(r, 3, it["nama"])
            ws.cell(r, 4, it["volume"]).number_format = FMT_ANGKA
            ws.cell(r, 5, it["satuan"])
            ws.cell(r, 6, it["harga"]).number_format = FMT_ANGKA
            ws.cell(r, 7, f"=D{r}*F{r}").number_format = FMT_ANGKA
            for c in range(1, 8):
                ws.cell(r, c).font, ws.cell(r, c).border = f_norm, kotak
            ws.cell(r, 3).alignment = Alignment(wrap_text=True, vertical="top")
            ws.cell(r, 1).alignment = Alignment(horizontal="center", vertical="top")
            ws.cell(r, 5).alignment = Alignment(horizontal="center", vertical="top")
            r += 1
        akhir = r - 1
        ws.cell(r, 3, f"Total {_romawi(i)}")
        ws.cell(r, 7, f"=SUM(G{awal}:G{akhir})").number_format = FMT_ANGKA
        for c in range(1, 8):
            ws.cell(r, c).font, ws.cell(r, c).border = f_bold, kotak
        ws.cell(r, 3).alignment = Alignment(horizontal="right")
        baris_total_kategori.append(r)
        r += 1

    r += 1
    baris_jumlah = r
    ws.cell(r, 3, "JUMLAH TOTAL")
    ws.cell(
        r, 7, "=" + "+".join(f"G{x}" for x in baris_total_kategori)
    ).number_format = FMT_ANGKA
    r += 1
    baris_ppn = r
    ws.cell(r, 3, "PPN")
    ws.cell(r, 6, PPN_RATE).number_format = "0%"
    ws.cell(r, 6).font = f_input  # asumsi (KF-11), sel biru = nilai input
    ws.cell(r, 7, f"=G{baris_jumlah}*F{r}").number_format = FMT_ANGKA
    r += 1
    baris_grand = r
    ws.cell(r, 3, "TOTAL + PPN")
    ws.cell(r, 7, f"=G{baris_jumlah}+G{baris_ppn}").number_format = FMT_ANGKA
    for rr in (baris_jumlah, baris_ppn, baris_grand):
        for c in range(1, 8):
            ws.cell(rr, c).border = kotak
            if not (rr == baris_ppn and c == 6):
                ws.cell(rr, c).font = f_bold
        ws.cell(rr, 3).alignment = Alignment(horizontal="right")
    r += 2
    ws.cell(r, 1, "Catatan:").font = f_catatan
    for teks in CATATAN:
        r += 1
        ws.cell(r, 1, f"- {teks}").font = f_catatan
    atur_cetak(ws, baris_header)

    # ---------- Sheet Rekapitulasi ----------
    if rekap:
        wr = wb.create_sheet("Rekapitulasi")
        for kolom, lebar in zip("ABCD", (6, 44, 24, 14)):
            wr.column_dimensions[kolom].width = lebar
        r = judul_sheet(wr, "REKAPITULASI RAB", 4)
        hdr = r
        header(wr, r, ["No", "Kategori Pekerjaan", "Jumlah (Rp)", "Persentase"])
        r += 1
        awal = r
        akhir = r + len(kelompok) - 1
        baris_tot_rekap = akhir + 1
        for i, (k, baris_rab) in enumerate(zip(kelompok, baris_total_kategori), 1):
            wr.cell(r, 1, i).alignment = Alignment(horizontal="center")
            wr.cell(r, 2, k["kategori"])
            wr.cell(r, 3, f"=RAB!G{baris_rab}").number_format = FMT_ANGKA
            wr.cell(
                r, 4, f"=IF(C${baris_tot_rekap}=0,0,C{r}/C${baris_tot_rekap})"
            ).number_format = "0.0%"
            for c in range(1, 5):
                wr.cell(r, c).font, wr.cell(r, c).border = f_norm, kotak
            r += 1
        wr.cell(r, 2, "JUMLAH TOTAL")
        wr.cell(r, 3, f"=SUM(C{awal}:C{akhir})").number_format = FMT_ANGKA
        wr.cell(r, 4, f"=SUM(D{awal}:D{akhir})").number_format = "0.0%"
        r += 1
        wr.cell(r, 2, "PPN")
        wr.cell(r, 3, f"=C{baris_tot_rekap}*RAB!F{baris_ppn}").number_format = FMT_ANGKA
        r += 1
        wr.cell(r, 2, "TOTAL + PPN")
        wr.cell(r, 3, f"=C{baris_tot_rekap}+C{r - 1}").number_format = FMT_ANGKA
        for rr in range(baris_tot_rekap, r + 1):
            for c in range(1, 5):
                wr.cell(rr, c).font, wr.cell(rr, c).border = f_bold, kotak
        atur_cetak(wr, hdr)

    # ---------- Sheet Detail Elemen ----------
    if detail:
        wd = wb.create_sheet("Detail Elemen")
        lebar = (6, 14, 24, 12, 38, 12, 8, 19, 21, 11)
        for kolom, w in zip("ABCDEFGHIJ", lebar):
            wd.column_dimensions[kolom].width = w
        r = judul_sheet(wd, "DETAIL VOLUME PER ELEMEN & LANTAI", 10)
        hdr = r
        header(
            wd,
            r,
            [
                "No",
                "Lantai",
                "Elemen",
                "Kategori",
                "Pekerjaan",
                "Volume",
                "Sat",
                "Harga Satuan (Rp)",
                "Jumlah (Rp)",
                "Status",
            ],
        )
        r += 1
        awal = r
        det = baris_detail(data["baris"])
        for n, d in enumerate(det, 1):
            nilai = [
                n,
                d["lantai"],
                d["elemen"],
                d["kategori"],
                d["pekerjaan"],
                d["volume"],
                d["satuan"],
                d["harga"],
                f"=F{r}*H{r}",
                d["status"],
            ]
            for c, v in enumerate(nilai, 1):
                sel = wd.cell(r, c, v)
                sel.font, sel.border = f_norm, kotak
            for c in (6, 8, 9):
                wd.cell(r, c).number_format = FMT_ANGKA
            r += 1
        akhir = r - 1
        wd.cell(r, 5, "JUMLAH")
        wd.cell(r, 9, f"=SUM(I{awal}:I{akhir})").number_format = FMT_ANGKA
        for c in range(1, 11):
            wd.cell(r, c).font, wd.cell(r, c).border = f_bold, kotak
        wd.cell(r, 5).alignment = Alignment(horizontal="right")
        baris_det_total = r
        r += 2
        wd.cell(r, 5, "Selisih terhadap sheet RAB (harus 0)").font = f_catatan
        wd.cell(
            r, 9, f"=I{baris_det_total}-RAB!G{baris_jumlah}"
        ).number_format = FMT_ANGKA
        wd.cell(r, 9).font = f_catatan
        atur_cetak(wd, hdr, "landscape")

    wb.save(str(path))
    log.info("Export Excel: %s", path)
    return str(path)


# ---------------------------------------------------------------- PDF


def export_pdf(
    path, data: dict, meta: dict, rekap: bool = True, detail: bool = True
) -> str:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.platypus import (
        PageBreak,
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
    )

    kelompok = kelompokkan(data["baris"])
    nama = meta.get("nama_proyek") or data["nama_proyek"]
    total = sum(k["total"] for k in kelompok)
    ppn = total * PPN_RATE

    s_judul = ParagraphStyle(
        "judul", fontName="Helvetica-Bold", fontSize=13, alignment=1, spaceAfter=6
    )
    s_info = ParagraphStyle("info", fontName="Helvetica", fontSize=9, leading=12)
    s_sel = ParagraphStyle("sel", fontName="Helvetica", fontSize=8, leading=10)
    s_selb = ParagraphStyle("selb", parent=s_sel, fontName="Helvetica-Bold")
    s_head = ParagraphStyle("head", parent=s_selb, alignment=1)
    s_bag = ParagraphStyle(
        "bag", fontName="Helvetica-Bold", fontSize=10, spaceBefore=14, spaceAfter=6
    )
    s_cat = ParagraphStyle(
        "cat",
        fontName="Helvetica-Oblique",
        fontSize=7.5,
        leading=9,
        textColor=colors.HexColor("#444444"),
    )

    abu, biru = colors.HexColor("#D9D9D9"), colors.HexColor("#EEF3F8")
    dasar = [
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#808080")),
        ("BACKGROUND", (0, 0), (-1, 0), abu),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 2.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
    ]

    def footer(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(colors.HexColor("#666666"))
        canvas.drawString(
            1.4 * cm,
            0.9 * cm,
            f"{nama}  |  Dibuat dengan CostStruct, {datetime.now():%d-%m-%Y %H:%M}",
        )
        canvas.drawRightString(A4[0] - 1.4 * cm, 0.9 * cm, f"Halaman {doc.page}")
        canvas.restoreState()

    story = [Paragraph("RENCANA ANGGARAN BIAYA (RAB)", s_judul)]
    for label, nilai in _info_dokumen(data, meta):
        story.append(Paragraph(f"<b>{label}</b> : {_esc(nilai)}", s_info))
    story.append(Spacer(1, 10))

    # --- tabel RAB ---
    baris = [
        [
            Paragraph(t, s_head)
            for t in (
                "No",
                "Uraian Pekerjaan",
                "Volume",
                "Sat",
                "Harga Satuan (Rp)",
                "Jumlah Harga (Rp)",
            )
        ]
    ]
    gaya = list(dasar)
    for i, k in enumerate(kelompok, 1):
        baris.append(
            [
                Paragraph(f"{_romawi(i)}.", s_selb),
                Paragraph(_esc(k["kategori"].upper()), s_selb),
                "",
                "",
                "",
                "",
            ]
        )
        gaya += [
            ("BACKGROUND", (0, len(baris) - 1), (-1, len(baris) - 1), biru),
            ("SPAN", (1, len(baris) - 1), (-1, len(baris) - 1)),
        ]
        for n, it in enumerate(k["items"], 1):
            baris.append(
                [
                    Paragraph(str(n), s_sel),
                    Paragraph(_esc(it["nama"]), s_sel),
                    _rp(it["volume"]),
                    it["satuan"],
                    _rp(it["harga"]),
                    _rp(it["jumlah"]),
                ]
            )
        baris.append(
            ["", Paragraph(f"Total {_romawi(i)}", s_selb), "", "", "", _rp(k["total"])]
        )
        gaya += [
            ("FONTNAME", (5, len(baris) - 1), (5, len(baris) - 1), "Helvetica-Bold"),
            ("LINEABOVE", (0, len(baris) - 1), (-1, len(baris) - 1), 0.8, colors.black),
        ]
        gaya.append(("ALIGN", (1, len(baris) - 1), (1, len(baris) - 1), "RIGHT"))
    t = Table(
        baris,
        colWidths=[1.0 * cm, 7.2 * cm, 2.2 * cm, 1.4 * cm, 3.0 * cm, 3.4 * cm],
        repeatRows=1,
    )
    gaya += [
        ("ALIGN", (2, 1), (2, -1), "RIGHT"),
        ("ALIGN", (4, 1), (5, -1), "RIGHT"),
        ("ALIGN", (3, 1), (3, -1), "CENTER"),
        ("ALIGN", (0, 1), (0, -1), "CENTER"),
        ("FONTSIZE", (2, 1), (-1, -1), 8),
    ]
    t.setStyle(TableStyle(gaya))
    story.append(t)
    story.append(Spacer(1, 8))

    ringkas = Table(
        [
            ["JUMLAH TOTAL", _rp(total)],
            [f"PPN {PPN_RATE:.0%}", _rp(ppn)],
            ["TOTAL + PPN", _rp(total + ppn)],
        ],
        colWidths=[11.8 * cm, 3.4 * cm],
        hAlign="RIGHT",
    )
    ringkas.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, -1), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("ALIGN", (0, 0), (-1, -1), "RIGHT"),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#808080")),
                ("BACKGROUND", (0, 2), (-1, 2), abu),
            ]
        )
    )
    story.append(ringkas)
    story.append(Spacer(1, 10))
    story.append(Paragraph("Catatan:", s_cat))
    for teks in CATATAN:
        story.append(Paragraph(f"- {_esc(teks)}", s_cat))

    # --- rekapitulasi ---
    if rekap:
        story.append(Paragraph("REKAPITULASI", s_bag))
        rb = [
            [
                Paragraph(t, s_head)
                for t in ("No", "Kategori Pekerjaan", "Jumlah (Rp)", "%")
            ]
        ]
        for i, k in enumerate(kelompok, 1):
            persen = k["total"] / total * 100 if total else 0
            rb.append(
                [
                    str(i),
                    k["kategori"],
                    _rp(k["total"]),
                    f"{persen:.1f}".replace(".", ",") + "%",
                ]
            )
        rb.append(["", "JUMLAH TOTAL", _rp(total), "100,0%"])
        rt = Table(rb, colWidths=[1.0 * cm, 8.0 * cm, 4.5 * cm, 2.2 * cm])
        rt.setStyle(
            TableStyle(
                dasar
                + [
                    ("ALIGN", (2, 1), (3, -1), "RIGHT"),
                    ("ALIGN", (0, 1), (0, -1), "CENTER"),
                    ("FONTSIZE", (0, 1), (-1, -1), 8),
                    ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
                ]
            )
        )
        story.append(rt)

    # --- detail per elemen ---
    if detail:
        story.append(PageBreak())
        story.append(Paragraph("DETAIL VOLUME PER ELEMEN & LANTAI", s_bag))
        db = [
            [
                Paragraph(t, s_head)
                for t in (
                    "Lantai",
                    "Elemen",
                    "Pekerjaan",
                    "Volume",
                    "Sat",
                    "Jumlah (Rp)",
                )
            ]
        ]
        for d in baris_detail(data["baris"]):
            db.append(
                [
                    Paragraph(_esc(d["lantai"]), s_sel),
                    Paragraph(_esc(d["elemen"]), s_sel),
                    Paragraph(_esc(d["pekerjaan"]), s_sel),
                    _rp(d["volume"], 3),
                    d["satuan"],
                    _rp(d["jumlah"]),
                ]
            )
        dt = Table(
            db,
            colWidths=[2.2 * cm, 3.8 * cm, 5.8 * cm, 2.2 * cm, 1.2 * cm, 3.0 * cm],
            repeatRows=1,
        )
        dt.setStyle(
            TableStyle(
                dasar
                + [
                    ("ALIGN", (3, 1), (3, -1), "RIGHT"),
                    ("ALIGN", (5, 1), (5, -1), "RIGHT"),
                    ("ALIGN", (4, 1), (4, -1), "CENTER"),
                    ("FONTSIZE", (3, 1), (-1, -1), 8),
                ]
            )
        )
        story.append(dt)

    doc = SimpleDocTemplate(
        str(path),
        pagesize=A4,
        leftMargin=1.4 * cm,
        rightMargin=1.4 * cm,
        topMargin=1.4 * cm,
        bottomMargin=1.6 * cm,
        title=f"RAB {nama}",
        author="CostStruct",
    )
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    log.info("Export PDF: %s", path)
    return str(path)


def _esc(teks) -> str:
    return str(teks).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
