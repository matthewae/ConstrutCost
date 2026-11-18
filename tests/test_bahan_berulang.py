"""Bahan habis pakai dan bahan yang dipakai berulang (kayu, triplek, dolken bekisting: analisa HSPK "3 kali pakai"):
klasifikasi komponen, pemisahan Kebutuhan Bahan, tampilan di tab Kebutuhan Bahan, dan export Excel / PDF."""

import os

import pytest
from conftest import AC20

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


# ---------------------------------------------------------------- klasifikasi


def test_jumlah_pakai_dari_judul_analisa_hspk():
    from bahan_berulang import jumlah_pakai

    assert jumlah_pakai("Pemasangan 1 m2 bekisting untuk kolom (3 kali pakai)") == 3
    assert jumlah_pakai("Pembuatan 1 m2 Bekisting untuk balok Beton Pracetak ( 10 - 12 kali pakai )") == 10
    assert jumlah_pakai("Bekisting pelat Beton Pracetak ( 5kali pakai )") == 5
    assert jumlah_pakai("Pemasangan 1 m2 dinding bata merah") == 0 and jumlah_pakai(None) == 0


def test_bahan_bekisting_berulang_paku_minyak_habis_pakai():
    from bahan_berulang import pakai_komponen

    for nama in ("Kaso 5/7 kayu kelas II", "Tripleks t=9mm", "Plywood 12 mm", "Multiplek tebal 18 mm",
                 "Dolken kayu φ 8-10 panjang 400 cm", "Kayu papan kelas III", "Kayu balok 6/12 kelas II"):
        assert pakai_komponen(nama, 3) == 3, nama
    for nama in ("Paku 4 inch", "Paku 2 inch", "Minyak bekisting", "Formtie/penjaga jarak bekesting/spacer",
                 "Kawat beton", "Lem Kayu"):
        assert pakai_komponen(nama, 3) == 0, nama
    # kayu kusen / rangka atap / plafon: pekerjaannya bukan "n kali pakai" -> terpasang permanen, habis pakai
    assert pakai_komponen("Kaso 5/7 kayu kelas II", 0) == 0
    # komponen "Bekisting" di analisa lain (sumur resapan HSPK 6.2.4.1) mengikuti analisa bekisting HSPK
    assert pakai_komponen("Bekisting", 0) == 3


def test_pisah_berulang_membagi_bahan_yang_dipakai_di_dua_jenis_pekerjaan():
    """Kaso dipakai di bekisting (3×) dan rangka plafon (permanen): menjadi dua baris; total tetap sama."""
    from kebutuhan_lantai import kebutuhan_sumber_daya, pisah_berulang

    baris = [
        {"pekerjaan_id": 1, "nama_pekerjaan": "Bekisting Kolom", "volume_pekerjaan": 100.0, "satuan": "m2",
         "lantai": "01 LANTAI 1"},
        {"pekerjaan_id": 2, "nama_pekerjaan": "Rangka Plafon Kayu", "volume_pekerjaan": 50.0, "satuan": "m2",
         "lantai": "02 LANTAI 2"},
    ]
    komponen = {
        1: [{"tipe": "bahan", "nama": "Kaso 5/7 kayu kelas II", "satuan": "m3", "koefisien": 0.005, "harga": 2_500_000.0,
             "pakai": 3},
            {"tipe": "bahan", "nama": "Paku 4 inch", "satuan": "kg", "koefisien": 0.4, "harga": 22_000.0, "pakai": 0},
            {"tipe": "upah", "nama": "Tukang kayu", "satuan": "OH", "koefisien": 0.33, "harga": 200_000.0}],
        2: [{"tipe": "bahan", "nama": "Kaso 5/7 kayu kelas II", "satuan": "m3", "koefisien": 0.015, "harga": 2_500_000.0,
             "pakai": 0}],
    }
    kb = kebutuhan_sumber_daya(baris, komponen)
    kaso = next(d for d in kb["bahan"] if d["nama"].startswith("Kaso"))
    assert kaso["jumlah"] == pytest.approx(1.25) and kaso["jumlah_berulang"] == pytest.approx(0.5)
    assert kaso["pakai"] == 3 and kaso["lantai_berulang"] == {"01 LANTAI 1": pytest.approx(0.5)}

    habis, ulang = pisah_berulang(kb["bahan"], kb["besi"])
    assert [d["nama"] for d in ulang] == ["Kaso 5/7 kayu kelas II"]
    u = ulang[0]
    assert u["jumlah"] == pytest.approx(0.5) and u["sekali_pakai"] == pytest.approx(1.5) and u["pakai"] == 3
    assert list(u["pekerjaan"]) == ["Bekisting Kolom"] and u["keterangan"] == "≈ 36 btg 5/7 @ 4 m"
    h = next(d for d in habis if d["nama"].startswith("Kaso"))
    assert h["jumlah"] == pytest.approx(0.75) and h["pakai"] == 0 and list(h["pekerjaan"]) == ["Rangka Plafon Kayu"]
    assert h["lantai"] == {"02 LANTAI 2": pytest.approx(0.75)} and h["keterangan"] == "≈ 54 btg 5/7 @ 4 m"
    assert any(d["nama"] == "Paku 4 inch" for d in habis)  # paku bekisting habis pakai
    assert sum(d["biaya"] for d in habis + ulang) == pytest.approx(sum(d["biaya"] for d in kb["bahan"]))


# ---------------------------------------------------------------- proyek nyata


@pytest.fixture
def proyek_ac20(db_sementara):
    from database.proyek_repository import create_proyek
    from estimasi_service import jalankan_estimasi

    pid = create_proyek("AC20", str(AC20))
    jalankan_estimasi(pid)
    return pid


def _kebutuhan(pid):
    from database.estimasi_repository import get_hasil_estimasi_by_proyek
    from kebutuhan_lantai import kebutuhan_sumber_daya, komponen_pekerjaan

    baris = [dict(r) for r in get_hasil_estimasi_by_proyek(pid)]
    return kebutuhan_sumber_daya(baris, komponen_pekerjaan(r["pekerjaan_id"] for r in baris))


def test_bekisting_proyek_ditandai_3_kali_pakai(proyek_ac20):
    from kebutuhan_lantai import pisah_berulang

    kb = _kebutuhan(proyek_ac20)
    habis, ulang = pisah_berulang(kb["bahan"], kb["besi"])
    nama_ulang = {d["nama"] for d in ulang}
    assert {"Kaso 5/7 kayu kelas II", "Tripleks t=9mm"} <= nama_ulang
    assert all(d["pakai"] == 3 and all(p.get("pakai") == 3 for p in d["pekerjaan"].values()) for d in ulang)
    assert all(n.startswith("Bekisting") for d in ulang for n in d["pekerjaan"])
    assert not any(d["nama"].lower().startswith(("paku", "minyak")) for d in ulang)
    assert {"Semen Portland (PC)"} <= {d["nama"] for d in habis}


def test_tab_kebutuhan_bahan_gabungan_dan_dipisah(proyek_ac20, qapp_berulang):
    from gui.estimasi_page import EstimasiPage

    hal = EstimasiPage(proyek_ac20, "AC20")
    try:
        assert hal.combo_pakai.isHidden()  # hanya di tab Kebutuhan Bahan
        hal.grup_mode.button(hal.MODE_BAHAN).click()
        assert not hal.combo_pakai.isHidden() and hal.combo_pakai.currentData() == "gabung"
        t = hal.tabel

        def kelompok():
            return {t.item(i, 0).text(): t.item(i, 1).text() for i in range(t.rowCount())
                    if t.item(i, 0) and t.item(i, 1) and not t.item(i, 0).text().isdigit()}

        def jumlah(label):
            i = next(i for i in range(t.rowCount()) if t.item(i, 1) and t.item(i, 1).text() == label)
            return t.item(i, 6).text()

        assert list(kelompok()) == ["A", "B", "C"] and kelompok()["A"] == "BAHAN / MATERIAL"
        total_bahan = jumlah("Jumlah bahan / material")

        hal.combo_pakai.setCurrentIndex(hal.combo_pakai.findData("pisah"))
        g = kelompok()
        assert list(g) == ["A.1", "A.2", "B", "C"]
        assert g["A.1"] == "BAHAN HABIS PAKAI" and g["A.2"].startswith("BAHAN DIPAKAI BERULANG") and "3×" in g["A.2"]
        assert jumlah("Jumlah bahan / material (A.1 + A.2)") == total_bahan
        kunci = next(k for k in hal._bahan if k[0] == "bahan_berulang")
        assert hal._bahan[kunci]["pakai"] == 3
        hal.panel.tampilkan_bahan(hal._bahan[kunci])  # panel Rincian: pemakaian & kebutuhan bila sekali pakai
        teks = [w.text() for w in hal.panel.findChildren(type(hal.label_jumlah))]
        assert "DIPAKAI BERULANG" in teks and "Bila sekali pakai" in teks

        hal.combo_pakai.setCurrentIndex(hal.combo_pakai.findData("berulang"))
        assert list(kelompok()) == ["A"] and kelompok()["A"].startswith("BAHAN DIPAKAI BERULANG")
        hal.combo_pakai.setCurrentIndex(hal.combo_pakai.findData("habis"))
        assert kelompok() == {"A": "BAHAN HABIS PAKAI"}

        from database.preferensi_repository import get_pref
        assert get_pref("kebutuhan_bahan_tampilan_pakai") == "habis"  # pilihan diingat
        hal.grup_mode.button(hal.MODE_REKAP).click()
        assert hal.combo_pakai.isHidden()
    finally:
        hal.deleteLater()


def test_export_bahan_habis_pakai_dan_berulang(proyek_ac20, tmp_path):
    from openpyxl import load_workbook

    from export_service import OpsiExport, ambil_data_export, export_excel, export_pdf

    data = ambil_data_export(proyek_ac20)
    opsi = OpsiExport(rekap=False, rinci=False, besi=False, detail=False, lantai=False, per_lantai=False)
    wb = load_workbook(export_excel(tmp_path / "pakai.xlsx", data, {"nama_proyek": "AC20"}, opsi))
    assert wb.sheetnames.index("Bahan Habis Pakai & Berulang") == wb.sheetnames.index("Kebutuhan Bahan") + 1
    ws = wb["Bahan Habis Pakai & Berulang"]
    baris = [[c.value for c in row] for row in ws.iter_rows()]
    kode = [r[0] for r in baris if r[0] in ("A.1", "A.2")]
    assert kode == ["A.1", "A.2"]
    awal = next(i for i, r in enumerate(baris) if r[0] == "A.2")
    ulang = [r for r in baris[awal + 1:] if isinstance(r[0], int)]
    assert ulang and all(r[4] == "3×" and str(r[5]).endswith("*3") for r in ulang)
    assert {"Kaso 5/7 kayu kelas II", "Tripleks t=9mm"} <= {r[1] for r in ulang}
    total = next(r for r in baris if r[1] == "JUMLAH BAHAN / MATERIAL (A.1 + A.2)")
    assert str(total[8]).startswith("=I") and "+I" in str(total[8])
    # keseluruhan tetap di sheet Kebutuhan Bahan
    assert any(c.value == "BAHAN / MATERIAL" for row in wb["Kebutuhan Bahan"].iter_rows() for c in row)
    pdf = export_pdf(tmp_path / "pakai.pdf", data, {"nama_proyek": "AC20"}, opsi)
    from pypdf import PdfReader

    teks = " ".join(" ".join(p.extract_text().split()) for p in PdfReader(pdf).pages)
    assert "BAHAN DIPAKAI BERULANG" in teks and "Bahan habis pakai & bahan dipakai berulang" in teks
    assert "⚠" not in teks


@pytest.fixture(scope="module")
def qapp_berulang():
    from PySide6.QtWidgets import QApplication

    from gui import tema

    app = QApplication.instance() or QApplication([])
    tema.terapkan(app, "gelap")
    return app
