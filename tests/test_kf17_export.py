"""KF-13 / KF-17: export RAB dengan kolom pilihan, rekap biaya, RAB rinci, dan kebutuhan besi."""

import shutil
import subprocess

import pytest

from conftest import DUPLEX


@pytest.fixture
def data_export(db_sementara):
    from database.biaya_repository import tambah_biaya
    from database.proyek_repository import create_proyek
    from estimasi_service import jalankan_estimasi
    from export_service import ambil_data_export

    pid = create_proyek("Duplex", str(DUPLEX))
    jalankan_estimasi(pid)
    tambah_biaya(pid, "Biaya perencanaan teknis", "persen", 3)
    tambah_biaya(pid, "Biaya perizinan (PBG / SLF)", "nilai", 7_500_000)
    return ambil_data_export(pid)


META = {"nama_proyek": "Rumah Uji", "lokasi": "Kota Bandung", "pemilik": "Bpk. Uji", "tahun": 2027}


def _header(ws, teks="Uraian Pekerjaan"):
    for row in ws.iter_rows():
        nilai = [c.value for c in row]
        if teks in nilai:
            return [v for v in nilai if v is not None]
    raise AssertionError("header tidak ditemukan")


def _terlihat(ws, teks="Uraian Pekerjaan"):
    """Judul kolom yang tidak disembunyikan (KF-17: kolom tidak dipilih disembunyikan, rumus tetap utuh)."""
    from openpyxl.utils import get_column_letter

    for row in ws.iter_rows():
        if teks in [c.value for c in row]:
            return [c.value for c in row
                    if c.value is not None and not ws.column_dimensions[get_column_letter(c.column)].hidden]
    raise AssertionError("header tidak ditemukan")


def test_kolom_dan_sheet_sesuai_pilihan(data_export, tmp_path):
    from openpyxl import load_workbook

    from export_service import OpsiExport, export_excel

    lengkap = tmp_path / "lengkap.xlsx"
    export_excel(lengkap, data_export, META, OpsiExport(kolom=("no", "kode", "harga", "bobot", "rumus")))
    wb = load_workbook(lengkap)
    lantai = [n for n in wb.sheetnames if n.startswith("Lt")]
    # format RAB konsultan di depan, lampiran aplikasi di tengah, rincian per elemen paling akhir
    assert lantai and wb.sheetnames == ["REKAP", "RAB", "ANALISA", "HARGA", "ASUMSI", "Rekap_Volume", "Rekap_Besi",
                                        "BBS", "RAB Rinci", "Rekap per Lantai", "Kebutuhan per Lantai",
                                        "Rincian Perhitungan Lantai", *lantai, "Kebutuhan Bahan",
                                        "Kebutuhan per Elemen", "Detail_Elemen"]
    assert _terlihat(wb["RAB"]) == [
        "No", "Uraian Pekerjaan", "Kode Analisa", "Volume", "Sat.", "HS Upah (Rp)", "HS Bahan (Rp)", "HS Alat (Rp)",
        "Harga Satuan (Rp)", "Jumlah Harga (Rp)", "Bobot", "Sumber Volume",
    ]
    assert "Uraian Rumus" in _header(wb["Detail_Elemen"])

    minimal = tmp_path / "minimal.xlsx"
    export_excel(minimal, data_export, META, OpsiExport(kolom=(), rekap=False, rinci=False, besi=False, detail=False, lantai=False,
                                                         per_lantai=False, bahan=False))
    wb = load_workbook(minimal)
    # RAB selalu bersama analisa, harga dasar, dan asumsi yang menjadi sumber rumusnya
    assert wb.sheetnames == ["RAB", "ANALISA", "HARGA", "ASUMSI"]
    # kolom wajib selalu terlihat; No, Kode, dan harga satuan disembunyikan
    assert _terlihat(wb["RAB"]) == ["Uraian Pekerjaan", "Volume", "Sat.", "Jumlah Harga (Rp)", "Sumber Volume"]
    teks = [c.value for row in wb["RAB"].iter_rows() for c in row if isinstance(c.value, str)]
    assert "TOTAL DIBULATKAN" in teks and any(t.startswith("Terbilang: ") for t in teks)


def test_format_rab_rumus_saling_terhubung(data_export, tmp_path):
    """REKAP -> RAB -> ANALISA -> HARGA, dengan biaya umum & keuntungan serta PPN dari ASUMSI."""
    from openpyxl import load_workbook

    from export_service import OpsiExport, export_excel

    path = tmp_path / "rab.xlsx"
    export_excel(path, data_export, META, OpsiExport())
    wb = load_workbook(path)
    ws = wb["RAB"]
    kepala = [c.value for c in ws[4]]
    k = {t: i for i, t in enumerate(kepala)}
    item = next(r for r in ws.iter_rows(min_row=5) if isinstance(r[k["Kode Analisa"]].value, str))
    assert item[k["Kode Analisa"]].value == "A001"
    assert item[k["HS Upah (Rp)"]].value.startswith("=SUMIFS(ANALISA!$G$5:")
    assert '"Bahan")' in item[k["HS Bahan (Rp)"]].value
    assert "ASUMSI!$C$5" in item[k["Harga Satuan (Rp)"]].value
    assert ws.freeze_panes == "C5" and wb["ANALISA"].freeze_panes == "C5" and wb["HARGA"].freeze_panes == "C5"
    an = wb["ANALISA"]
    komp = next(r for r in an.iter_rows(min_row=5) if r[3].value)
    assert komp[0].value == "A001" and komp[5].value.startswith("=VLOOKUP(D") and komp[7].value in ("Upah", "Bahan", "Alat")
    assert komp[4].font.color.rgb.endswith("0000FF")  # koefisien = input biru
    kode_harga = {r[0].value for r in wb["HARGA"].iter_rows(min_row=5) if r[0].value}
    assert {r[3].value for r in an.iter_rows(min_row=5) if r[3].value} <= kode_harga
    assert {k[0] for k in kode_harga} <= {"U", "B", "P"}
    rekap = wb["REKAP"]
    rumus = [c.value for row in rekap.iter_rows() for c in row if isinstance(c.value, str) and c.value.startswith("=")]
    assert any(f.startswith("=SUMPRODUCT(RAB!") for f in rumus) and any("ASUMSI!$C$6" in f for f in rumus)
    assert wb["ASUMSI"]["C5"].value == 0.10 and wb["ASUMSI"]["C6"].value == 0.11
    teks = [c.value for row in wb["ASUMSI"].iter_rows() for c in row if isinstance(c.value, str)]
    assert any("Sloof turunan" in t for t in teks) and "Pilihan material proyek (ubah di aplikasi: Ganti Bahan)" in teks


def test_harga_khusus_dan_item_tambahan(data_export, tmp_path):
    """Harga khusus pengguna ditulis sebagai nilai (biru); item dari katalog masuk sheet VOLUME_TAMBAHAN."""
    from openpyxl import load_workbook

    from database.estimasi_repository import ubah_harga_baris
    from database.katalog import tambah_item
    from export_service import OpsiExport, ambil_data_export, export_excel

    pid = data_export["proyek_id"]
    baris = next(r for r in data_export["baris"] if r["kode_ahsp"] == "DND.BATA")
    ubah_harga_baris([baris["hasil_id"]], 123_456.0)
    tambah_item(pid, "1.1.1.1", 2.0)
    data = ambil_data_export(pid)
    path = tmp_path / "rab.xlsx"
    export_excel(path, data, META, OpsiExport())
    wb = load_workbook(path)
    ws = wb["RAB"]
    kepala = [c.value for c in ws[4]]
    k = {t: i for i, t in enumerate(kepala)}
    bata = next(r for r in ws.iter_rows(min_row=5) if r[k["Uraian Pekerjaan"]].value == baris["nama_pekerjaan"])
    hs = bata[k["Harga Satuan (Rp)"]]
    assert isinstance(hs.value, float) and hs.font.color.rgb.endswith("0000FF")
    assert bata[k["HS Upah (Rp)"]].value is None
    assert "VOLUME_TAMBAHAN" in wb.sheetnames
    tambahan = [r for r in wb["VOLUME_TAMBAHAN"].iter_rows(min_row=5, values_only=True) if r[0]]
    assert len(tambahan) == 1 and tambahan[0][3] == 2.0


def test_rab_rinci_per_tipe_elemen(data_export, tmp_path):
    from openpyxl import load_workbook

    from export_service import OpsiExport, export_excel

    path = tmp_path / "rab.xlsx"
    export_excel(path, data_export, META, OpsiExport())
    teks = [c.value for row in load_workbook(path)["RAB Rinci"].iter_rows() for c in row if isinstance(c.value, str)]
    # Duplex: fondasi menerus "Bearing Footing" = beton bertulang, pelat lantai dasar 1 lapis;
    # balok W310/W410 adalah profil baja sehingga tidak muncul sebagai tipe beton
    assert "Fondasi Beton F1 (t = 30 cm) — 7 buah" in teks
    assert "Pelat Lantai Dasar L1 (t = 15 cm) — 2 buah" in teks
    assert any("Tulangan D13-150 dua arah, 1 lapis (bawah)" in t for t in teks)
    assert any("Tulangan Ø8-150 dua arah, 1 lapis (bawah)" in t for t in teks)
    assert not any(t.startswith("Balok B") for t in teks)
    wb = load_workbook(path)
    besi = [c.value for row in wb["Rekap_Besi"].iter_rows() for c in row]
    assert {"Ø8", "D13", "Batang 12 m"} <= set(besi)
    bbs = [r for r in wb["BBS"].iter_rows(min_row=5, values_only=True) if isinstance(r[0], int)]
    assert bbs and {r[4] for r in bbs} >= {"Ø8", "D13"}


def test_rekap_biaya_tidak_langsung_dan_terbilang(data_export, tmp_path):
    from openpyxl import load_workbook

    from export_service import OpsiExport, export_excel

    path = tmp_path / "rab.xlsx"
    export_excel(path, data_export, META, OpsiExport())
    teks = [c.value for row in load_workbook(path)["REKAP"].iter_rows() for c in row if isinstance(c.value, str)]
    assert "BIAYA TIDAK LANGSUNG" in teks
    assert "Biaya perencanaan teknis (3% × A)" in teks
    assert "TOTAL DIBULATKAN" in teks
    assert any(t.startswith("Terbilang: ") and t.endswith("rupiah") for t in teks)


@pytest.mark.skipif(shutil.which("soffice") is None, reason="LibreOffice tidak tersedia")
def test_rumus_excel_dihitung_tanpa_galat(data_export, tmp_path):
    """Hitung ulang semua rumus dengan LibreOffice: tidak ada #REF!/#NAME?, total sama dengan aplikasi,
    dan selisih sheet rinci & detail terhadap sheet RAB = 0."""
    from openpyxl import load_workbook

    from export_service import OpsiExport, export_excel

    sumber = tmp_path / "rab.xlsx"
    export_excel(sumber, data_export, META, OpsiExport(kolom=("no", "kode", "harga", "bobot")))
    keluar = tmp_path / "hitung"
    subprocess.run(
        ["soffice", "--headless", "--calc", "--convert-to", "xlsx", "--outdir", str(keluar), str(sumber)],
        check=True, capture_output=True, timeout=180,
    )
    wb = load_workbook(keluar / "rab.xlsx", data_only=True)
    ring = data_export["ringkasan"]
    for ws in wb.worksheets:
        for row in ws.iter_rows():
            for c in row:
                assert not (isinstance(c.value, str) and c.value.startswith(("#", "Err:"))), (ws.title, c.coordinate)
            label = next((c.value for c in row if isinstance(c.value, str)), "")
            angka = [c.value for c in row if isinstance(c.value, (int, float))]
            if label == "TOTAL DIBULATKAN":
                assert angka[-1] == ring["dibulatkan"]
            if label.startswith("Selisih terhadap sheet RAB"):
                assert angka[-1] == pytest.approx(0, abs=0.01)
            if label == "Jumlah A":  # REKAP: upah + bahan + alat = biaya langsung (tanpa harga khusus)
                assert angka[0] == pytest.approx(ring["langsung"], abs=0.5)
                assert sum(angka[1:4]) == pytest.approx(angka[0], abs=0.5)


@pytest.mark.skipif(shutil.which("soffice") is None, reason="LibreOffice tidak tersedia")
def test_ubah_harga_dasar_mengalir_ke_rab(data_export, tmp_path):
    """Harga dasar di sheet HARGA dinaikkan -> ANALISA, RAB, REKAP, dan Detail_Elemen ikut berubah."""
    from openpyxl import load_workbook

    from export_service import OpsiExport, export_excel

    sumber = tmp_path / "rab.xlsx"
    export_excel(sumber, data_export, META, OpsiExport(rinci=False, lantai=False, per_lantai=False, bahan=False))
    wb = load_workbook(sumber)
    wh = wb["HARGA"]
    upah = [r for r in wh.iter_rows(min_row=5) if r[4].value == "Upah"]
    for r in upah:
        r[3].value = r[3].value * 2
    ubah = tmp_path / "ubah.xlsx"
    wb.save(ubah)
    keluar = tmp_path / "hitung"
    subprocess.run(["soffice", "--headless", "--calc", "--convert-to", "xlsx", "--outdir", str(keluar), str(ubah)],
                   check=True, capture_output=True, timeout=180)
    wb = load_workbook(keluar / "ubah.xlsx", data_only=True)
    nilai = {}
    for ws in (wb["REKAP"], wb["Detail_Elemen"]):
        for row in ws.iter_rows():
            label = next((c.value for c in row if isinstance(c.value, str)), "")
            angka = [c.value for c in row if isinstance(c.value, (int, float))]
            if label in ("Jumlah A",) or label.startswith("Selisih"):
                nilai[label] = angka
    a, upah_a = nilai["Jumlah A"][0], nilai["Jumlah A"][1]
    lama = data_export["ringkasan"]["langsung"]
    assert a > lama and a - lama == pytest.approx(upah_a / 2, rel=1e-6)
    assert nilai["Selisih terhadap sheet RAB (harus 0)"][-1] == pytest.approx(0, abs=0.01)


def test_pdf_portrait_dan_landscape(data_export, tmp_path):
    from pypdf import PdfReader

    from export_service import OpsiExport, export_pdf

    tegak = tmp_path / "tegak.pdf"
    datar = tmp_path / "datar.pdf"
    export_pdf(tegak, data_export, META, OpsiExport(kolom=("no", "harga")))
    export_pdf(datar, data_export, META, OpsiExport(kolom=(), orientasi_pdf="landscape", detail=False))
    a, b = PdfReader(tegak), PdfReader(datar)
    assert a.pages[0].mediabox.width < a.pages[0].mediabox.height
    assert b.pages[0].mediabox.width > b.pages[0].mediabox.height
    isi = " ".join(p.extract_text() for p in a.pages)
    for teks in ("REKAPITULASI", "RAB RINCI PER TIPE ELEMEN", "KEBUTUHAN BESI", "Terbilang", "Bpk. Uji"):
        assert teks in isi


def test_pilihan_export_diingat(db_sementara, tmp_path):
    from dataclasses import replace

    from database.preferensi_repository import muat_preferensi, simpan_pilihan_export

    simpan_pilihan_export(replace(muat_preferensi(), kolom_laporan="no,bobot", isi_besi=False,
                                  orientasi_pdf="landscape", direktori_export=str(tmp_path)))
    p = muat_preferensi()
    assert p.kolom == ("no", "bobot") and p.isi_besi is False and p.orientasi_pdf == "landscape"


def test_export_file_terkunci_disimpan_dengan_nama_baru(data_export, tmp_path, monkeypatch):
    """Windows: file hasil export lama masih dikunci (Excel latar belakang / Preview Explorer / antivirus)."""
    import os

    import export_service as es

    asli = os.replace
    terkunci = tmp_path / "RAB.xlsx"

    def replace(src, dst):
        if str(dst) == str(terkunci):
            raise PermissionError(13, "The process cannot access the file", str(dst))
        return asli(src, dst)

    monkeypatch.setattr(es.os, "replace", replace)
    hasil = es.export_excel(terkunci, data_export, META, es.OpsiExport(detail=False))
    assert hasil.endswith("RAB (2).xlsx") and os.path.getsize(hasil) > 0
    pdf = es.export_pdf(tmp_path / "RAB.pdf", data_export, META, es.OpsiExport(detail=False))
    assert pdf.endswith("RAB.pdf")
    assert not [f for f in os.listdir(tmp_path) if f.startswith("~coststruct_")]  # file sementara dibersihkan


def test_export_folder_diblokir_pesan_khusus(data_export, tmp_path, monkeypatch):
    import export_service as es
    from gui.galat import pesan_galat

    def mkstemp(**_):
        raise PermissionError(13, "Access is denied")

    monkeypatch.setattr(es.tempfile, "mkstemp", mkstemp)
    with pytest.raises(es.FolderTidakBisaDitulis) as info:
        es.export_excel(tmp_path / "RAB.xlsx", data_export, META, es.OpsiExport(detail=False))
    pesan, saran = pesan_galat(info.value)
    assert "Folder tujuan tidak mengizinkan" in pesan and "Akses folder terkontrol" in saran


def test_rab_rinci_beda_dengan_rekap(data_export):
    """RAB Rinci memecah SEMUA item: struktur per tipe penulangan, pekerjaan lain per tipe elemen IFC;
    Rekap RAB satu baris per item. Totalnya sama."""
    from export_service import _entri_rab, _entri_rinci
    from rab_rinci import susun_rinci

    baris = data_export["baris"]
    rinci = susun_rinci(baris, per_tipe_elemen=True)
    assert sum(k["total"] for k in rinci) == pytest.approx(sum(r["subtotal_biaya"] for r in baris))
    dinding = next(k for k in rinci if k["kategori"] == "Dinding")
    assert all(g["judul"] for g in dinding["grup"])  # tiap pekerjaan dinding jadi grup ...
    assert all(it["label"].endswith("buah") for g in dinding["grup"] for it in g["items"])  # ... berisi tipe elemen
    jml = lambda e: [x for x in e if x["jenis"] == "item"]  # noqa: E731
    assert len(jml(_entri_rinci(baris))) > len(jml(_entri_rab(baris)))
    assert sum(x["jumlah"] for x in jml(_entri_rinci(baris))) == pytest.approx(sum(x["jumlah"] for x in jml(_entri_rab(baris))))
