"""
Format RAB lengkap untuk export Excel (KF-8 / KF-13 / KF-17), mengikuti susunan RAB konsultan:

    REKAP ──> RAB ──SUMIFS──> ANALISA ──VLOOKUP──> HARGA
                └── biaya umum & keuntungan, PPN dari ASUMSI

- REKAP           : jumlah per bagian pekerjaan dipecah upah / bahan / alat, bobot, biaya tidak langsung,
                    PPN, total, pembulatan, terbilang.
- RAB             : volume × harga satuan; harga satuan = (HS upah + HS bahan + HS alat) × (1 + biaya umum &
                    keuntungan). HS diambil dari ANALISA (koefisien × harga dasar).
- ANALISA         : komponen tiap analisa pekerjaan yang dipakai proyek (koefisien = input biru).
- HARGA           : harga dasar upah / bahan / alat yang dipakai (input biru, boleh disesuaikan hasil survei).
- VOLUME_TAMBAHAN : pekerjaan yang diisi pengguna dari katalog HSPK (tidak dari model).
- ASUMSI          : biaya umum & keuntungan, PPN, parameter aturan proyek, pilihan material.
- Rekap_Volume, Rekap_Besi, BBS, Detail_Elemen: kuantitas per item, pembesian per kelompok & diameter,
                    daftar tulangan per elemen, dan rincian per elemen (dengan pemeriksaan selisih ke RAB).

Warna huruf: biru = input, hijau = rujukan ke sheet lain, hitam = rumus. Semua angka dapat diaudit di Excel:
ubah satu harga di HARGA atau satu koefisien di ANALISA, maka RAB dan REKAP ikut menghitung ulang.
"""

import re
from collections import defaultdict

from database.estimasi_repository import BUK_RATE, PPN_RATE
from kebutuhan_lantai import AWALAN_STRUKTUR, label_grup_struktur
from rab_rinci import urutan_kategori
from rules.penulangan import FAKTOR_SISA, berat_per_m, label_d

BIRU, HIJAU, PUTIH, ABU = "0000FF", "008000", "FFFFFF", "595959"
HEADER, SEKSI, HSP = "1F3B57", "DCE6F0", "FFF2CC"
RP = r"#,##0;\(#,##0\);\-"
VOL = r"#,##0.000;\(#,##0.000\);\-"
KG = r"#,##0.0;\(#,##0.0\);\-"
JENIS = {"upah": "Upah", "bahan": "Bahan", "alat": "Alat"}
AWAL_KODE = {"upah": "U", "bahan": "B", "alat": "P"}  # P = peralatan (A dipakai kode analisa)
URUT_JENIS = ("upah", "bahan", "alat")
BARIS_HEADER = 4  # sheet RAB, ANALISA, HARGA: judul baris 1-3, kepala tabel baris 4 (freeze C5)
ASUMSI_OVH, ASUMSI_PPN = "ASUMSI!$C$5", "ASUMSI!$C$6"
MODEL_IFC = "dari model IFC"


def romawi(n: int) -> str:
    out = ""
    for v, s in ((1000, "M"), (900, "CM"), (500, "D"), (400, "CD"), (100, "C"), (90, "XC"), (50, "L"), (40, "XL"),
                 (10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I")):
        while n >= v:
            out += s
            n -= v
    return out


def kode_hspk(catatan: str | None) -> str:
    """'HSPK Kota Bandung 2027 (...) · 2.2.1.4.5 · ...' -> '2.2.1.4.5'."""
    bagian = [b.strip() for b in (catatan or "").split(" · ")]
    return bagian[1] if len(bagian) > 1 and re.match(r"^\d+(\.\d+)*[a-z]?$", bagian[1]) else ""


def sumber_volume(r: dict) -> str:
    """Asal volume satu baris hasil (kolom 'Sumber Volume'; telusuri per elemen di Detail_Elemen)."""
    kode, kelas = r.get("kode_ahsp") or "", r.get("kelas") or ""
    dasar = kode.split("~")[0]
    if r.get("item_tambahan"):
        return "Input pengguna (katalog HSPK)"
    if r.get("diedit_manual"):
        return "Edit manual"
    if dasar.startswith("BSI."):
        return "Tulangan model IFC" if MODEL_IFC in (r.get("rumus") or "") else "Tipe penulangan"
    if kelas in ("EARTHWORK", "WALL_TILE") or (dasar.startswith("LTK.") and kelas == "SLAB"):
        return "Model IFC (elemen)"
    turunan = (
        dasar.startswith(("TNH.", "PSP.", "LTK.", "BTN.SUMURAN"))
        or (kelas == "WALL" and dasar.startswith(("FDN.", "BTN.SLOOF", "BSK.SLOOF")))
    )
    return "Turunan model (parameter aturan)" if turunan else "Model IFC (QTO)"


def _kelompok_pekerjaan(baris: list) -> list:
    """[(kategori, [pekerjaan])], pekerjaan = gabungan semua baris hasil satu pekerjaan."""
    per = {}
    for r in baris:
        d = per.setdefault(r["pekerjaan_id"], {
            "pid": r["pekerjaan_id"], "kategori": r["kategori"], "kode": r["kode_ahsp"] or "",
            "nama": r["nama_pekerjaan"], "satuan": r["satuan"], "volume": 0.0, "jumlah": 0.0,
            "manual": False, "sumber": set(), "elemen": set(),
        })
        d["volume"] += r["volume_pekerjaan"] or 0.0
        d["jumlah"] += r["subtotal_biaya"] or 0.0
        d["manual"] |= r.get("harga_manual") is not None
        d["sumber"].add(sumber_volume(r))
        if r.get("elemen_id"):
            d["elemen"].add(r["elemen_id"])
    kat = defaultdict(list)
    for d in per.values():
        kat[d["kategori"]].append(d)
    return [(k, sorted(kat[k], key=lambda x: x["nama"])) for k in sorted(kat, key=urutan_kategori)]


def _analisa_proyek(pekerjaan_ids) -> tuple:
    """({pid: [komponen]}, {pid: kode HSPK}). Nama sumber daya apa adanya (mis. 'Pekerja (Galian Tanah)')
    supaya harga varian tidak tertukar di sheet HARGA."""
    from database.estimasi_repository import _connect

    ids = sorted({int(i) for i in pekerjaan_ids})
    if not ids:
        return {}, {}
    tanda = ",".join("?" * len(ids))
    conn = _connect()
    try:
        komp = conn.execute(
            f"""SELECT k.pekerjaan_id, k.tipe, COALESCE(s.nama, k.nama_komponen) AS nama, k.satuan, k.koefisien,
                       k.harga_satuan AS harga
                FROM komponen_harga k LEFT JOIN sumber_daya s ON s.id = k.sumber_daya_id
                WHERE k.pekerjaan_id IN ({tanda}) ORDER BY k.id""", ids).fetchall()
        cat = conn.execute(f"SELECT id, catatan FROM pekerjaan WHERE id IN ({tanda})", ids).fetchall()
    finally:
        conn.close()
    hasil = defaultdict(list)
    for r in komp:
        hasil[r["pekerjaan_id"]].append({"tipe": r["tipe"], "nama": " ".join((r["nama"] or "").split()),
                                         "satuan": r["satuan"], "koefisien": r["koefisien"] or 0.0,
                                         "harga": r["harga"] or 0.0})
    for v in hasil.values():
        v.sort(key=lambda c: URUT_JENIS.index(c["tipe"]) if c["tipe"] in URUT_JENIS else 9)
    return dict(hasil), {r["id"]: kode_hspk(r["catatan"]) for r in cat}


def tulis_rab_lengkap(wb, data: dict, opsi, info_dokumen: list) -> str:
    """Tulis sheet format RAB lengkap ke `wb` (sheet aktif menjadi sheet pertama).
    Return rujukan sel jumlah biaya langsung (mis. "RAB!$J$120") untuk pemeriksaan selisih di sheet lain."""
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    from openpyxl.utils import get_column_letter as L

    F = "Arial"
    f9, f9b = Font(name=F, size=9), Font(name=F, size=9, bold=True)
    f9h = Font(name=F, size=9, bold=True, color=PUTIH)
    f9in = Font(name=F, size=9, color=BIRU)
    f9ref = Font(name=F, size=9, color=HIJAU)
    f9ket = Font(name=F, size=9, italic=True, color=ABU)
    fjudul = Font(name=F, size=13, bold=True)
    fill_h, fill_s, fill_hsp = (PatternFill("solid", fgColor=c) for c in (HEADER, SEKSI, HSP))
    sisi = Side(style="thin", color="A6A6A6")
    kotak = Border(left=sisi, right=sisi, top=sisi, bottom=sisi)
    tengah = Alignment(horizontal="center", vertical="top")
    kanan = Alignment(horizontal="right", vertical="top")
    bungkus = Alignment(wrap_text=True, vertical="top")
    ring, baris = data["ringkasan"], data["baris"]
    pilih = set(opsi.kolom)
    info_ringkas = " · ".join(f"{a}: {b}" for a, b in info_dokumen)

    def judul(ws, teks, ket):
        ws["A1"] = teks
        ws["A1"].font = fjudul
        ws["A2"] = info_ringkas
        ws["A2"].font = f9
        ws["A3"] = ket
        ws["A3"].font = f9ket

    def head(ws, r, teks, lebar):
        for c, (t, w) in enumerate(zip(teks, lebar), 1):
            s = ws.cell(r, c, t)
            s.font, s.fill, s.border = f9h, fill_h, kotak
            s.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
            if w:
                ws.column_dimensions[L(c)].width = w
        ws.row_dimensions[r].height = 26

    def sel(ws, r, c, v=None, fmt=None, font=f9, al=None, fill=None):
        s = ws.cell(r, c, v)
        s.font, s.border = font, kotak
        if fmt:
            s.number_format = fmt
        if al:
            s.alignment = al
        if fill:
            s.fill = fill
        return s

    def baris_seksi(ws, r, n, fill=fill_s, font=f9b):
        for c in range(1, n + 1):
            sel(ws, r, c, font=font, fill=fill)

    def cetak(ws, hdr, freeze, orient="portrait"):
        ws.page_setup.orientation = orient
        ws.page_setup.paperSize = ws.PAPERSIZE_A4
        ws.page_setup.fitToWidth = 1
        ws.page_setup.fitToHeight = 0
        ws.sheet_properties.pageSetUpPr.fitToPage = True
        ws.print_title_rows = f"{hdr}:{hdr}"
        ws.freeze_panes = freeze
        ws.page_margins.left = ws.page_margins.right = 0.4

    # ------------------------------------------------------------ data analisa & harga dasar
    kelompok = _kelompok_pekerjaan(baris)
    komponen, hspk = _analisa_proyek(r["pekerjaan_id"] for r in baris)
    urut_pid = [it["pid"] for _k, items in kelompok for it in items]
    kode_analisa = {pid: f"A{i:03d}" for i, pid in enumerate(urut_pid, 1)}
    harga_kode, harga_baris, nomor = {}, [], defaultdict(int)
    for pid in urut_pid:
        for c in komponen.get(pid, []):
            kunci = (c["tipe"], c["nama"], c["satuan"], round(c["harga"], 4))
            if kunci not in harga_kode:
                nomor[c["tipe"]] += 1
                harga_kode[kunci] = f"{AWAL_KODE.get(c['tipe'], 'X')}{nomor[c['tipe']]:03d}"
                harga_baris.append((harga_kode[kunci], *kunci))
    harga_baris.sort(key=lambda x: (URUT_JENIS.index(x[1]) if x[1] in URUT_JENIS else 9, x[0]))
    an_awal = BARIS_HEADER + 1
    an_akhir = an_awal - 1 + sum(1 + max(len(komponen.get(pid, [])), 1) + 6 + 1 for pid in urut_pid)
    harga_akhir = BARIS_HEADER + max(len(harga_baris), 1)

    def rng(kol):
        return f"ANALISA!${kol}${an_awal}:${kol}${an_akhir}"

    # ------------------------------------------------------------ sheet pertama: REKAP (atau RAB)
    wr = wb.active
    if opsi.rekap:
        wr.title = "REKAP"
        ws = wb.create_sheet("RAB")
    else:
        wr.title = "RAB"
        ws = wr

    # ------------------------------------------------------------ RAB
    kol = ["no", "uraian", "kode", "volume", "sat", "upah", "bahan", "alat", "hs", "jumlah"]
    if "bobot" in pilih:
        kol.append("bobot")
    kol.append("sumber")
    C = {k: i for i, k in enumerate(kol, 1)}
    judul_kol = {"no": "No", "uraian": "Uraian Pekerjaan", "kode": "Kode Analisa", "volume": "Volume", "sat": "Sat.",
                 "upah": "HS Upah (Rp)", "bahan": "HS Bahan (Rp)", "alat": "HS Alat (Rp)", "hs": "Harga Satuan (Rp)",
                 "jumlah": "Jumlah Harga (Rp)", "bobot": "Bobot", "sumber": "Sumber Volume"}
    lebar = {"no": 6, "uraian": 58, "kode": 9, "volume": 11, "sat": 6, "upah": 13, "bahan": 13, "alat": 12, "hs": 14,
             "jumlah": 16, "bobot": 8, "sumber": 28}
    n = len(kol)
    CV, CH, CJ = L(C["volume"]), L(C["hs"]), L(C["jumlah"])
    judul(ws, "RENCANA ANGGARAN BIAYA (RAB)",
          "Volume dari model IFC (quantity take-off). Harga satuan = (upah + bahan + alat) × (1 + biaya umum & "
          "keuntungan di ASUMSI); upah / bahan / alat dari ANALISA × HARGA.")
    head(ws, BARIS_HEADER, [judul_kol[k] for k in kol], [lebar[k] for k in kol])
    r = BARIS_HEADER + 1
    seksi = []  # (romawi, kategori, baris_awal, baris_akhir, baris_jumlah)
    harga_nilai = 0
    berumus = set()  # pekerjaan yang harga satuannya rumus analisa (Detail_Elemen merujuk ke RAB)
    for i, (kat, items) in enumerate(kelompok, 1):
        baris_seksi(ws, r, n)
        ws.cell(r, C["no"], romawi(i)).alignment = tengah
        ws.cell(r, C["uraian"], kat.upper())
        r += 1
        awal = r
        for no, it in enumerate(items, 1):
            komp = komponen.get(it["pid"], [])
            hs_app = it["jumlah"] / it["volume"] if it["volume"] else 0.0
            hs_analisa = sum(c["koefisien"] * c["harga"] for c in komp) * (1 + BUK_RATE)
            pakai_rumus = bool(komp) and not it["manual"] and abs(hs_app - hs_analisa) <= 0.01 + 1e-9 * hs_analisa
            input_vol = bool(it["sumber"] & {"Edit manual", "Input pengguna (katalog HSPK)"})
            sel(ws, r, C["no"], no, al=tengah)
            sel(ws, r, C["uraian"], it["nama"], al=bungkus)
            sel(ws, r, C["kode"], kode_analisa[it["pid"]], al=tengah)
            sel(ws, r, C["volume"], it["volume"], VOL, f9in if input_vol else f9)
            sel(ws, r, C["sat"], it["satuan"], al=tengah)
            for k in URUT_JENIS:
                rumus = (f'=SUMIFS({rng("G")},{rng("A")},${L(C["kode"])}{r},{rng("H")},"{JENIS[k]}")'
                         if pakai_rumus else None)
                sel(ws, r, C[k], rumus, RP, f9ref)
            if pakai_rumus:
                sel(ws, r, C["hs"], f"=({L(C['upah'])}{r}+{L(C['bahan'])}{r}+{L(C['alat'])}{r})*(1+{ASUMSI_OVH})", RP)
                berumus.add(it["pid"])
            else:
                sel(ws, r, C["hs"], hs_app, RP, f9in)  # harga khusus / belum diterapkan ulang: nilai aplikasi
                harga_nilai += 1
            sel(ws, r, C["jumlah"], f"={CV}{r}*{CH}{r}", RP)
            if "bobot" in C:
                sel(ws, r, C["bobot"], None, "0.00%")
            sel(ws, r, C["sumber"], " + ".join(sorted(it["sumber"])), al=bungkus)
            r += 1
        baris_seksi(ws, r, n, fill=None)
        ws.cell(r, C["uraian"], f"Jumlah {romawi(i)}. {kat}").alignment = kanan
        ws.cell(r, C["jumlah"], f"=SUM({CJ}{awal}:{CJ}{r - 1})").number_format = RP
        seksi.append((romawi(i), kat, awal, r - 1, r))
        r += 1
    r += 1
    baris_seksi(ws, r, n, fill=fill_hsp)
    ws.cell(r, C["uraian"], "JUMLAH BIAYA LANGSUNG (A)").alignment = kanan
    ws.cell(r, C["jumlah"], "=" + ("+".join(f"{CJ}{s[4]}" for s in seksi) or "0")).number_format = RP
    rA = r
    ref_A = f"RAB!${CJ}${rA}"
    if "bobot" in C:
        for s in seksi:
            for x in [*range(s[2], s[3] + 1), s[4]]:
                ws.cell(x, C["bobot"], f"=IF(${CJ}${rA}=0,0,{CJ}{x}/${CJ}${rA})").number_format = "0.00%"
    r += 1
    if not opsi.rekap:  # tanpa sheet REKAP: total lengkap ditulis di bawah RAB
        pct = sum(b["nilai"] for b in ring["item_tidak_langsung"] if b["jenis"] == "persen") / 100
        tetap = sum(b["nilai"] for b in ring["item_tidak_langsung"] if b["jenis"] == "nilai")
        for teks, rumus in (
            ("BIAYA TIDAK LANGSUNG (B)", f"={CJ}{rA}*{pct!r}+{tetap!r}"),
            ("JUMLAH (A + B)", f"={CJ}{rA}+{CJ}{r}"),
            (f"PPN {PPN_RATE:.0%}", f"={CJ}{r + 1}*{ASUMSI_PPN}"),
            ("TOTAL", f"={CJ}{r + 1}+{CJ}{r + 2}"),
            ("TOTAL DIBULATKAN", f"=ROUNDDOWN({CJ}{r + 3},-3)"),
        ):
            baris_seksi(ws, r, n, fill=fill_hsp if teks == "TOTAL DIBULATKAN" else None)
            ws.cell(r, C["uraian"], teks).alignment = kanan
            ws.cell(r, C["jumlah"], rumus).number_format = RP
            r += 1
        ws.cell(r + 1, 1, f"Terbilang: {ring['terbilang']}").font = Font(name=F, size=9, bold=True, italic=True)
        r += 2
    if harga_nilai:
        ws.cell(r + 1, 2, f"{harga_nilai} harga satuan biru = harga khusus pengguna atau harga yang belum diterapkan "
                          "ulang dari menu Harga Satuan; ditulis sebagai nilai, bukan rumus analisa.").font = f9ket
    # KF-17: kolom yang tidak dipilih disembunyikan (bukan dihapus) supaya rumus tetap utuh
    sembunyi = [] if "no" in pilih else ["no"]
    sembunyi += [] if "kode" in pilih else ["kode"]
    sembunyi += [] if "harga" in pilih else ["upah", "bahan", "alat", "hs"]
    for k in sembunyi:
        ws.column_dimensions[L(C[k])].hidden = True
    cetak(ws, BARIS_HEADER, f"C{BARIS_HEADER + 1}")

    # ------------------------------------------------------------ REKAP
    if opsi.rekap:
        wr["A1"] = "REKAPITULASI RENCANA ANGGARAN BIAYA"
        wr["A1"].font = Font(name=F, size=14, bold=True)
        r = 2
        for a, b in info_dokumen:
            wr.cell(r, 1, f"{a}: {b}").font = f9
            r += 1
        wr.cell(r, 1, "Jumlah tiap bagian dari sheet RAB; upah / bahan / alat dari ANALISA (sudah termasuk biaya "
                      "umum & keuntungan).").font = f9ket
        r += 2
        hdr = r
        head(wr, r, ["No", "Uraian Pekerjaan", "Jumlah Harga (Rp)", "Upah (Rp)", "Bahan (Rp)", "Alat (Rp)", "Bobot"],
             [6, 62, 18, 16, 16, 14, 9])
        r += 1
        baris_seksi(wr, r, 7)
        wr.cell(r, 1, "A").alignment = tengah
        wr.cell(r, 2, "BIAYA LANGSUNG")
        r += 1
        awal = r
        for rom, kat, a, b, rj in seksi:
            sel(wr, r, 1, rom, al=tengah)
            sel(wr, r, 2, kat.upper(), al=bungkus)
            sel(wr, r, 3, f"=RAB!{CJ}{rj}", RP, f9ref)
            for c, k in ((4, "upah"), (5, "bahan"), (6, "alat")):
                kk = L(C[k])
                sel(wr, r, c, f"=SUMPRODUCT(RAB!{CV}{a}:{CV}{b},RAB!{kk}{a}:{kk}{b})*(1+{ASUMSI_OVH})", RP)
            r += 1
        rA_rekap = r
        baris_seksi(wr, r, 7, fill=None)
        wr.cell(r, 2, "Jumlah A").alignment = kanan
        for c in "CDEF":
            wr[f"{c}{r}"] = f"=SUM({c}{awal}:{c}{r - 1})"
            wr[f"{c}{r}"].number_format = RP
        for x in range(awal, r + 1):
            sel(wr, x, 7, f"=IF($C${rA_rekap}=0,0,C{x}/$C${rA_rekap})", "0.0%", f9b if x == rA_rekap else f9)
        r += 1
        baris_seksi(wr, r, 7)
        wr.cell(r, 1, "B").alignment = tengah
        wr.cell(r, 2, "BIAYA TIDAK LANGSUNG")
        r += 1
        awal_b = r
        for i, b in enumerate(ring["item_tidak_langsung"], 1):
            sel(wr, r, 1, i, al=tengah)
            for c in range(4, 7):
                sel(wr, r, c)
            if b["jenis"] == "persen":
                sel(wr, r, 2, f"{b['uraian']} ({b['nilai']:g}% × A)".replace(".", ","))
                sel(wr, r, 7, b["nilai"] / 100, "0.00%", f9in)
                sel(wr, r, 3, f"=$C${rA_rekap}*G{r}", RP)
            else:
                sel(wr, r, 2, b["uraian"])
                sel(wr, r, 3, b["nilai"], RP, f9in)
                sel(wr, r, 7)
            r += 1
        if not ring["item_tidak_langsung"]:
            for c in range(1, 8):
                sel(wr, r, c)
            wr.cell(r, 2, "Tidak ada (dapat diisi di aplikasi: Biaya Tidak Langsung)").font = f9ket
            wr.cell(r, 3, 0).number_format = RP
            r += 1
        rB = r
        baris_seksi(wr, r, 7, fill=None)
        wr.cell(r, 2, "Jumlah B").alignment = kanan
        wr.cell(r, 3, f"=SUM(C{awal_b}:C{r - 1})").number_format = RP
        r += 2
        for teks, rumus, isi in (
            ("JUMLAH (A + B)", f"=C{rA_rekap}+C{rB}", None),
            (f"PPN {PPN_RATE:.0%}", f"=C{r}*{ASUMSI_PPN}", None),
            ("TOTAL", f"=C{r}+C{r + 1}", None),
            ("TOTAL DIBULATKAN", f"=ROUNDDOWN(C{r + 2},-3)", fill_hsp),
        ):
            sel(wr, r, 2, teks, font=f9b, al=kanan)
            sel(wr, r, 3, rumus, RP, f9b, fill=isi)
            r += 1
        r += 1
        wr.cell(r, 1, f"Terbilang: {ring['terbilang']}").font = Font(name=F, size=9, bold=True, italic=True)
        r += 2
        for teks in (
            f"Biaya umum & keuntungan {BUK_RATE:.0%} sudah termasuk dalam harga satuan (sheet ASUMSI).",
            "Pecahan upah / bahan / alat tidak mencakup pekerjaan berharga khusus pengguna (harga satuan biru di RAB).",
            "Pekerjaan yang tidak ada di model (mis. MEP, perizinan) dapat ditambahkan dari katalog HSPK di aplikasi.",
        ):
            wr.cell(r, 1, f"• {teks}").font = f9ket
            r += 1
        cetak(wr, hdr, f"A{hdr + 1}")

    # ------------------------------------------------------------ ANALISA
    wn = wb.create_sheet("ANALISA")
    judul(wn, "ANALISA HARGA SATUAN PEKERJAAN (upah, bahan & alat dipisah)",
          "Koefisien analisa (biru) × harga dasar dari sheet HARGA. Acuan: HSPK Kota Bandung 2027.")
    head(wn, BARIS_HEADER, ["Kode", "Uraian Analisa / Komponen", "Sat.", "Kode Harga", "Koefisien",
                            "Harga Satuan (Rp)", "Jumlah (Rp)", "Jenis", "Acuan"], [7, 60, 7, 9, 10, 14, 14, 8, 34])
    r = an_awal
    for _kat, items in kelompok:
        for it in items:
            ka, komp = kode_analisa[it["pid"]], komponen.get(it["pid"], [])
            baris_seksi(wn, r, 9)
            wn.cell(r, 1, ka)
            wn.cell(r, 2, f"{it['nama']} (per 1 {it['satuan']})")
            wn.cell(r, 3, it["satuan"]).alignment = tengah
            acuan = hspk.get(it["pid"])
            wn.cell(r, 9, f"HSPK Kota Bandung 2027 {acuan}" if acuan else "Analisa aplikasi")
            r += 1
            awal = r
            for c in komp:
                sel(wn, r, 1, ka)
                sel(wn, r, 2, f"  {c['nama']}")
                sel(wn, r, 3, c["satuan"], al=tengah)
                sel(wn, r, 4, harga_kode[(c["tipe"], c["nama"], c["satuan"], round(c["harga"], 4))], al=tengah)
                sel(wn, r, 5, c["koefisien"], "0.0000", f9in)
                sel(wn, r, 6, f"=VLOOKUP(D{r},HARGA!$A${BARIS_HEADER + 1}:$D${harga_akhir},4,FALSE())", RP, f9ref)
                sel(wn, r, 7, f"=E{r}*F{r}", RP)
                sel(wn, r, 8, JENIS.get(c["tipe"], c["tipe"]), al=tengah)
                sel(wn, r, 9)
                r += 1
            if not komp:
                for c in range(1, 10):
                    sel(wn, r, c)
                wn.cell(r, 2, "  (tanpa komponen analisa: harga satuan ditulis langsung di RAB)").font = f9ket
                r += 1
            akhir = r - 1
            for teks, rumus, tebal in (
                ("Jumlah upah", f'=SUMIFS(G{awal}:G{akhir},H{awal}:H{akhir},"Upah")', False),
                ("Jumlah bahan", f'=SUMIFS(G{awal}:G{akhir},H{awal}:H{akhir},"Bahan")', False),
                ("Jumlah alat", f'=SUMIFS(G{awal}:G{akhir},H{awal}:H{akhir},"Alat")', False),
                ("Biaya langsung (upah + bahan + alat)", f"=G{r}+G{r + 1}+G{r + 2}", False),
                ("Biaya umum & keuntungan", f"=G{r + 3}*{ASUMSI_OVH}", False),
                ("HARGA SATUAN PEKERJAAN", f"=G{r + 3}+G{r + 4}", True),
            ):
                sel(wn, r, 2, teks, font=f9b if tebal else f9, al=kanan)
                sel(wn, r, 7, rumus, RP, f9b if tebal else f9, fill=fill_hsp if tebal else None)
                r += 1
            r += 1
    if r - 1 != an_akhir:
        raise RuntimeError("Rentang SUMIFS sheet ANALISA tidak sesuai jumlah baris analisa.")
    cetak(wn, BARIS_HEADER, f"C{BARIS_HEADER + 1}")

    # ------------------------------------------------------------ HARGA
    wh = wb.create_sheet("HARGA")
    judul(wh, "DAFTAR HARGA DASAR UPAH, BAHAN & ALAT",
          "Harga dasar yang dipakai analisa (HSPK Kota Bandung 2027 / ubahan di aplikasi). Angka biru boleh disesuaikan "
          "hasil survei; perubahan mengalir ke ANALISA, RAB, dan REKAP.")
    head(wh, BARIS_HEADER, ["Kode", "Uraian", "Satuan", "Harga (Rp)", "Jenis"], [8, 62, 9, 15, 9])
    r = BARIS_HEADER + 1
    for kode, tipe, nama, satuan, harga in harga_baris:
        sel(wh, r, 1, kode, al=tengah)
        sel(wh, r, 2, nama)
        sel(wh, r, 3, satuan, al=tengah)
        sel(wh, r, 4, harga, RP, f9in)
        sel(wh, r, 5, JENIS.get(tipe, tipe), al=tengah)
        r += 1
    cetak(wh, BARIS_HEADER, f"C{BARIS_HEADER + 1}")

    # ------------------------------------------------------------ VOLUME_TAMBAHAN
    tambahan = [x for x in baris if x.get("item_tambahan")]
    if tambahan:
        wt = wb.create_sheet("VOLUME_TAMBAHAN")
        judul(wt, "VOLUME TAMBAHAN (diisi pengguna dari katalog HSPK)",
              "Pekerjaan yang tidak dapat dihitung dari model; volume (biru) diisi pengguna di aplikasi.")
        head(wt, BARIS_HEADER, ["No", "Uraian Pekerjaan", "Kode Analisa", "Volume", "Sat.", "Lantai", "Catatan"],
             [5, 56, 9, 12, 7, 16, 40])
        r = BARIS_HEADER + 1
        for i, x in enumerate(tambahan, 1):
            sel(wt, r, 1, i, al=tengah)
            sel(wt, r, 2, x["nama_pekerjaan"], al=bungkus)
            sel(wt, r, 3, kode_analisa.get(x["pekerjaan_id"]), al=tengah)
            sel(wt, r, 4, x["volume_pekerjaan"], VOL, f9in)
            sel(wt, r, 5, x["satuan"], al=tengah)
            sel(wt, r, 6, x.get("lantai") or "-")
            sel(wt, r, 7, x.get("catatan") or "", al=bungkus)
            r += 1
        cetak(wt, BARIS_HEADER, f"C{BARIS_HEADER + 1}")

    # ------------------------------------------------------------ ASUMSI
    wa = wb.create_sheet("ASUMSI")
    judul(wa, "ASUMSI & PARAMETER RAB", "Sel biru dapat diubah; RAB, ANALISA, dan REKAP ikut menghitung ulang.")
    head(wa, BARIS_HEADER, ["No", "Parameter", "Nilai", "Keterangan / Sumber"], [5, 60, 18, 72])
    for i, (nama, nilai, ket) in enumerate((
        ("Biaya umum & keuntungan (atas upah + bahan + alat)", BUK_RATE,
         "Struktur HSPK / AHSP (Permen PUPR No. 8 Tahun 2023: maksimal 15%); seragam untuk semua pekerjaan"),
        ("PPN", PPN_RATE, "Pajak pertambahan nilai atas jumlah biaya langsung + tidak langsung"),
    ), 1):
        r = BARIS_HEADER + i
        sel(wa, r, 1, i, al=tengah)
        sel(wa, r, 2, nama)
        sel(wa, r, 3, nilai, "0%", f9in)
        sel(wa, r, 4, ket, al=bungkus)
    r = BARIS_HEADER + 4
    param = data.get("parameter") or []
    if param:
        baris_seksi(wa, r, 4)
        wa.cell(r, 2, "Parameter aturan proyek (ubah di aplikasi: Parameter Aturan, lalu hitung ulang)")
        r += 1
        for grup, nama, nilai, satuan, bawaan in param:
            sel(wa, r, 1)
            sel(wa, r, 2, f"{grup} — {nama}")
            sel(wa, r, 3, nilai, al=kanan)
            sel(wa, r, 4, (satuan or "") + ("" if bawaan else "   ● diubah dari nilai bawaan"))
            r += 1
        r += 1
    mat = (data.get("material") or {}).get("proyek") or []
    if mat:
        baris_seksi(wa, r, 4)
        wa.cell(r, 2, "Pilihan material proyek (ubah di aplikasi: Ganti Bahan)")
        r += 1
        for slot, label, kode, bawaan in mat:
            sel(wa, r, 1)
            sel(wa, r, 2, slot)
            sel(wa, r, 3, "bawaan" if bawaan else "diubah", al=kanan)
            sel(wa, r, 4, f"{label} (HSPK {kode})" if kode else label)
            r += 1
        r += 1
    for teks in (
        "Volume dari model IFC (quantity set / geometri) dan aturan IF-THEN CostStruct; edit manual ditandai biru.",
        "Elemen yang dimodelkan langsung (tulangan, urugan pasir, lantai kerja, aanstamping, keramik dinding) "
        "menggantikan hasil turunan aturan agar tidak terhitung ganda.",
        "Pembesian: tulangan model (IfcReinforcingBar) bila ada, selain itu dari tipe penulangan; berat termasuk "
        f"sisa potongan {FAKTOR_SISA - 1:.0%}.",
        "Total = (biaya langsung + biaya tidak langsung) + PPN, dibulatkan ke bawah per Rp 1.000.",
        "Ubahan harga / koefisien di Excel mengalir ke ANALISA, RAB, REKAP, dan Detail_Elemen. Sheet lampiran "
        "(RAB Rinci, per lantai, kebutuhan bahan) memakai harga saat export; hitung ulang di aplikasi untuk memperbaruinya.",
    ):
        wa.cell(r, 2, f"• {teks}").font = f9
        r += 1

    # ------------------------------------------------------------ PERBANDINGAN_FONDASI
    pf = data.get("perbandingan_fondasi")
    if pf and opsi.rekap:  # bagian dari rekapitulasi biaya
        wf = wb.create_sheet("PERBANDINGAN_FONDASI")
        judul(wf, "PERBANDINGAN JENIS FONDASI KOLOM",
              "Pekerjaan yang volumenya berbeda antar jenis fondasi, dihitung ulang dari model yang sama tanpa mengubah "
              "gambar (Parameter Aturan › Fondasi kolom dihitung sebagai). Pekerjaan lain sama di semua jenis. "
              "● = jenis yang dipakai di sheet RAB.")
        nj = len(pf["jenis"])
        kepala = ["No", "Uraian Pekerjaan", "Sat."]
        for i, nama in enumerate(pf["jenis"]):
            tanda = " ●" if i == pf["aktif"] else ""
            kepala += [f"Volume\n{nama}{tanda}", f"Jumlah (Rp)\n{nama}{tanda}"]
        head(wf, BARIS_HEADER, kepala, [5, 52, 6] + [11, 15] * nj)
        wf.row_dimensions[BARIS_HEADER].height = 40
        kol_vol = [4 + 2 * i for i in range(nj)]
        kol_jml = [5 + 2 * i for i in range(nj)]
        r = BARIS_HEADER + 1
        awal = r
        kat_lalu, no = None, 0
        for b in pf["baris"]:
            if b["kategori"] != kat_lalu:
                baris_seksi(wf, r, 3 + 2 * nj)
                wf.cell(r, 2, b["kategori"].upper())
                kat_lalu = b["kategori"]
                r += 1
            no += 1
            sel(wf, r, 1, no, al=tengah)
            sel(wf, r, 2, b["nama"], al=bungkus)
            sel(wf, r, 3, b["satuan"], al=tengah)
            for i in range(nj):
                sel(wf, r, kol_vol[i], b["volume"][i] or None, VOL, fill=fill_hsp if i == pf["aktif"] else None)
                sel(wf, r, kol_jml[i], b["jumlah"][i] or None, RP, fill=fill_hsp if i == pf["aktif"] else None)
            r += 1
        akhir = r - 1
        r += 1
        ra = kol_jml[pf["aktif"]]
        baris_beda = r
        ring = data["ringkasan"]
        pct = sum(b_["nilai"] for b_ in ring["item_tidak_langsung"] if b_["jenis"] == "persen") / 100
        tetap = sum(b_["nilai"] for b_ in ring["item_tidak_langsung"] if b_["jenis"] == "nilai")
        for teks, fungsi, tebal in (
            ("Jumlah pekerjaan yang berbeda", lambda c, r_: f"=SUM({L(c)}{awal}:{L(c)}{akhir})", False),
            ("Biaya langsung (A) = A di RAB − pekerjaan berbeda jenis ● + pekerjaan berbeda jenis ini",
             lambda c, r_: f"={ref_A}-${L(ra)}${baris_beda}+{L(c)}{baris_beda}", True),
            ("Beda biaya langsung terhadap jenis ●",
             lambda c, r_: f"={L(c)}{baris_beda + 1}-${L(ra)}${baris_beda + 1}", False),
            ("Total (A + biaya tidak langsung) + PPN, dibulatkan",
             lambda c, r_: f"=ROUNDDOWN(({L(c)}{baris_beda + 1}*(1+{pct!r})+{tetap!r})*(1+{ASUMSI_PPN}),-3)", True),
        ):
            sel(wf, r, 2, teks, font=f9b if tebal else f9, al=Alignment(horizontal="right", vertical="top",
                                                                        wrap_text=True))
            for c in kol_jml:
                sel(wf, r, c, fungsi(c, r), RP, f9b if tebal else f9, fill=fill_hsp if c == ra else None)
            r += 1
        r += 1
        for nama, catatan in zip(pf["jenis"], pf["catatan"]):
            if catatan:
                wf.cell(r, 2, f"• {nama}: {catatan.split('. ', 1)[-1]}").font = f9ket
                wf.cell(r, 2).alignment = Alignment(wrap_text=True, vertical="top")
                wf.merge_cells(start_row=r, start_column=2, end_row=r, end_column=3 + 2 * nj)
                wf.row_dimensions[r].height = 36
                r += 1
        cetak(wf, BARIS_HEADER, f"C{BARIS_HEADER + 1}", "landscape")

    # ------------------------------------------------------------ Rekap_Volume
    if opsi.detail:
        wv = wb.create_sheet("Rekap_Volume")
        judul(wv, "REKAP VOLUME (QUANTITY TAKE-OFF)",
              "Volume tiap item pekerjaan dari seluruh elemen; rincian per elemen di sheet Detail_Elemen.")
        head(wv, BARIS_HEADER, ["No", "Uraian Pekerjaan", "Kode Analisa", "Volume", "Sat.", "Jml Elemen", "Sumber Volume"],
             [6, 58, 9, 13, 7, 10, 34])
        r = BARIS_HEADER + 1
        for i, (kat, items) in enumerate(kelompok, 1):
            baris_seksi(wv, r, 7)
            wv.cell(r, 1, romawi(i)).alignment = tengah
            wv.cell(r, 2, kat.upper())
            r += 1
            for no, it in enumerate(items, 1):
                sel(wv, r, 1, no, al=tengah)
                sel(wv, r, 2, it["nama"], al=bungkus)
                sel(wv, r, 3, kode_analisa[it["pid"]], al=tengah)
                sel(wv, r, 4, it["volume"], VOL)
                sel(wv, r, 5, it["satuan"], al=tengah)
                sel(wv, r, 6, len(it["elemen"]) or None, al=tengah)
                sel(wv, r, 7, " + ".join(sorted(it["sumber"])), al=bungkus)
                r += 1
        cetak(wv, BARIS_HEADER, f"C{BARIS_HEADER + 1}")

    # ------------------------------------------------------------ Rekap_Besi & BBS
    besi = [x for x in baris if (x.get("kode_ahsp") or "").startswith("BSI.")]
    if opsi.besi and besi:
        diam = sorted({x["diameter"] for x in besi if x.get("diameter")})
        ada_rasio = any(not x.get("diameter") for x in besi)
        grup = {}
        for x in baris:
            kode = x.get("kode_ahsp") or ""
            if not kode.startswith(AWALAN_STRUKTUR):
                continue
            kunci, label, urut = label_grup_struktur(x)
            g = grup.setdefault(kunci, {"label": label, "urut": urut, "d": defaultdict(float), "rasio": 0.0,
                                        "beton": 0.0, "model": False, "tipe": False})
            v = x["volume_pekerjaan"] or 0.0
            if kode.startswith("BSI."):
                if x.get("diameter"):
                    g["d"][x["diameter"]] += v
                else:
                    g["rasio"] += v
                if MODEL_IFC in (x.get("rumus") or ""):
                    g["model"] = True
                else:
                    g["tipe"] = True
            elif kode.startswith("BTN."):
                g["beton"] += v
        wbs = wb.create_sheet("Rekap_Besi")
        judul(wbs, "REKAP PEMBESIAN PER KELOMPOK ELEMEN & DIAMETER",
              f"Berat (kg) termasuk sisa potongan {FAKTOR_SISA - 1:.0%}. Sumber: tulangan model IFC bila ada, selain itu "
              "tipe penulangan (atau asumsi rasio kg/m³ bila penampang tidak diketahui).")
        kolom_d = [label_d(d) for d in diam] + (["Rasio (tanpa Ø)"] if ada_rasio else [])
        nd = len(kolom_d)
        ct = 2 + nd  # kolom total
        head(wbs, BARIS_HEADER, ["Kelompok Elemen", *kolom_d, "Total (kg)", "Beton (m³)", "kg/m³", "Sumber"],
             [34, *([10] * nd), 12, 11, 9, 22])
        r = BARIS_HEADER + 1
        awal = r
        for g in sorted(grup.values(), key=lambda g: (g["urut"], g["label"])):
            if not g["d"] and not g["rasio"]:
                continue
            sel(wbs, r, 1, g["label"])
            for j, d in enumerate(diam, 2):
                sel(wbs, r, j, g["d"].get(d) or None, KG)
            if ada_rasio:
                sel(wbs, r, 1 + nd, g["rasio"] or None, KG)
            sel(wbs, r, ct, f"=SUM(B{r}:{L(ct - 1)}{r})", KG, f9b)
            sel(wbs, r, ct + 1, g["beton"] or None, VOL)
            sel(wbs, r, ct + 2, f'=IF(N({L(ct + 1)}{r})>0,{L(ct)}{r}/{L(ct + 1)}{r},"-")', "#,##0")
            sel(wbs, r, ct + 3, " + ".join(s for s, ada in (("Model IFC", g["model"]), ("Tipe penulangan", g["tipe"]))
                                           if ada))
            r += 1
        baris_seksi(wbs, r, ct + 3)
        wbs.cell(r, 1, "JUMLAH")
        for c in range(2, ct + 2):
            wbs.cell(r, c, f"=SUM({L(c)}{awal}:{L(c)}{r - 1})").number_format = KG if c <= ct else VOL
        wbs.cell(r, ct + 2, f'=IF(N({L(ct + 1)}{r})>0,{L(ct)}{r}/{L(ct + 1)}{r},"-")').number_format = "#,##0"
        r += 2
        wbs.cell(r, 1, "KEBUTUHAN BESI PER DIAMETER (untuk pemesanan)").font = f9b
        r += 1
        head(wbs, r, ["Diameter", "Jenis Baja", "Berat/m (kg)", "Berat Total (kg)", "Panjang Total (m)", "Batang 12 m"],
             [None] * 6)
        r += 1
        awal = r
        for k in data.get("besi") or []:
            sel(wbs, r, 1, k["label"])
            sel(wbs, r, 2, k["jenis"])
            sel(wbs, r, 3, f"=PI()*{k['diameter']!r}^2/4*7850/1000000", "0.000")
            sel(wbs, r, 4, k["berat"], KG)
            sel(wbs, r, 5, f"=D{r}/C{r}", "#,##0.0")
            sel(wbs, r, 6, f"=ROUNDUP(E{r}/12,0)", "#,##0")
            r += 1
        sel(wbs, r, 1, "JUMLAH", font=f9b)
        sel(wbs, r, 4, f"=SUM(D{awal}:D{r - 1})", KG, f9b)
        sel(wbs, r, 6, f"=SUM(F{awal}:F{r - 1})", "#,##0", f9b)
        cetak(wbs, BARIS_HEADER, f"B{BARIS_HEADER + 1}", "landscape")

        wbb = wb.create_sheet("BBS")
        judul(wbb, "DAFTAR TULANGAN PER ELEMEN (BAR BENDING SCHEDULE RINGKAS)",
              f"Panjang bersih = berat ÷ {FAKTOR_SISA:g} ÷ berat per meter; berat total termasuk sisa potongan.")
        head(wbb, BARIS_HEADER, ["No", "Lantai", "Kelompok / Tipe", "Elemen (Induk)", "Diameter", "Uraian Tulangan",
                                 "Panjang Bersih (m)", "Berat/m (kg)", "Berat Total (kg)", "Sumber"],
             [5, 14, 26, 38, 9, 40, 12, 10, 12, 16])
        r = BARIS_HEADER + 1
        urut_besi = sorted(besi, key=lambda x: (x.get("elevasi_lantai") if x.get("elevasi_lantai") is not None else 1e9,
                                                x.get("nama_elemen") or "", x.get("diameter") or 0))
        for i, x in enumerate(urut_besi, 1):
            d = x.get("diameter")
            sel(wbb, r, 1, i, al=tengah)
            sel(wbb, r, 2, x.get("lantai") or "-")
            sel(wbb, r, 3, label_grup_struktur(x)[1])
            sel(wbb, r, 4, x.get("nama_elemen") or "-", al=bungkus)
            sel(wbb, r, 5, label_d(d) if d else "-", al=tengah)
            sel(wbb, r, 6, x.get("uraian") or x["nama_pekerjaan"], al=bungkus)
            sel(wbb, r, 7, f"=I{r}/{FAKTOR_SISA!r}/H{r}" if d else None, "#,##0.00")
            sel(wbb, r, 8, berat_per_m(d) if d else None, "0.000")
            sel(wbb, r, 9, x["volume_pekerjaan"], KG)
            sel(wbb, r, 10, "Model IFC" if MODEL_IFC in (x.get("rumus") or "") else
                "Tipe penulangan" if d else "Asumsi rasio kg/m³")
            r += 1
        sel(wbb, r, 8, "JUMLAH", font=f9b)
        sel(wbb, r, 9, f"=SUM(I{BARIS_HEADER + 1}:I{r - 1})", KG, f9b)
        cetak(wbb, BARIS_HEADER, f"E{BARIS_HEADER + 1}", "landscape")

    # ------------------------------------------------------------ Detail_Elemen (dipindah ke akhir oleh pemanggil)
    if opsi.detail:
        wd = wb.create_sheet("Detail_Elemen")
        judul(wd, "DETAIL VOLUME PER ELEMEN & LANTAI", "Setiap baris = satu item pekerjaan dari satu elemen model. "
                                                       "Jumlah seluruh baris sama dengan biaya langsung di RAB.")
        kolom = [("no", "No", 5), ("lantai", "Lantai", 14), ("elemen", "Elemen", 32), ("kelas", "Kelas IFC", 16),
                 ("kode", "Kode Analisa", 9), ("uraian", "Uraian Pekerjaan", 44), ("volume", "Volume", 11),
                 ("sat", "Sat.", 6), ("harga", "Harga Satuan (Rp)", 14), ("jumlah", "Jumlah (Rp)", 15),
                 ("status", "Status", 12), ("sumber", "Sumber Volume", 24)]
        if "rumus" in pilih:
            kolom.append(("rumus", "Uraian Rumus", 64))
        if any(x.get("catatan") for x in baris):
            kolom.append(("catatan", "Catatan", 30))
        kolom.append(("gid", "GlobalId", 24))
        D = {k: i for i, (k, _t, _w) in enumerate(kolom, 1)}
        head(wd, BARIS_HEADER, [t for _k, t, _w in kolom], [w for _k, _t, w in kolom])
        r = BARIS_HEADER + 1
        urut = sorted(baris, key=lambda x: (x.get("elevasi_lantai") if x.get("elevasi_lantai") is not None else 1e9,
                                            x.get("lantai") or "", x.get("nama_elemen") or "",
                                            urutan_kategori(x["kategori"]), x["nama_pekerjaan"]))
        rata = {"elemen", "uraian", "rumus", "catatan"}
        for i, x in enumerate(urut, 1):
            v = x["volume_pekerjaan"] or 0.0
            uraian = x["nama_pekerjaan"] + (f" — {x['uraian']}" if x.get("uraian") and x.get("diameter") else "")
            isi = {
                "no": i, "lantai": x.get("lantai") or "-", "elemen": x.get("nama_elemen") or "-",
                "kelas": x.get("ifc_type") or ("(item tambahan)" if x.get("item_tambahan") else "-"),
                "kode": kode_analisa.get(x["pekerjaan_id"]), "uraian": uraian, "volume": v, "sat": x["satuan"],
                "harga": (x["subtotal_biaya"] or 0.0) / v if v else 0.0, "jumlah": None,
                "status": "Manual" if x.get("diedit_manual") else ("Dimensi diubah" if x.get("dimensi_manual")
                                                                     else "Otomatis"),
                "sumber": sumber_volume(x), "rumus": x.get("rumus") or "", "catatan": x.get("catatan") or "",
                "gid": x.get("global_id") or "",
            }
            for k, c in D.items():
                fmt = VOL if k == "volume" else RP if k in ("harga", "jumlah") else None
                font = f9in if k == "volume" and x.get("diedit_manual") else f9
                sel(wd, r, c, isi[k], fmt, font, al=bungkus if k in rata else tengah if k in ("no", "kode", "sat") else None)
            if v and x["pekerjaan_id"] in berumus:  # ikut berubah bila HARGA / ANALISA diubah di Excel
                wd.cell(r, D["harga"], f"=INDEX(RAB!${CH}:${CH},MATCH({L(D['kode'])}{r},RAB!${L(C['kode'])}:${L(C['kode'])},0))")
            wd.cell(r, D["jumlah"], f"={L(D['volume'])}{r}*{L(D['harga'])}{r}" if v else (x["subtotal_biaya"] or 0.0))
            r += 1
        cj = L(D["jumlah"])
        sel(wd, r, D["uraian"], "JUMLAH", font=f9b, al=kanan)
        sel(wd, r, D["jumlah"], f"=SUM({cj}{BARIS_HEADER + 1}:{cj}{r - 1})", RP, f9b)
        sel(wd, r + 1, D["uraian"], "Selisih terhadap sheet RAB (harus 0)", font=f9ket, al=kanan)
        sel(wd, r + 1, D["jumlah"], f"={cj}{r}-{ref_A}", RP, f9ket)
        for k in ("no", "kode", "harga"):
            if k not in pilih:
                wd.column_dimensions[L(D[k])].hidden = True
        cetak(wd, BARIS_HEADER, f"F{BARIS_HEADER + 1}", "landscape")

    return ref_A
