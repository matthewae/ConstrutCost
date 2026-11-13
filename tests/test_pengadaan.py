"""Detail kebutuhan material: kemasan beli (angka), kebutuhan per tahap pekerjaan & lantai, jadwal pengadaan dengan sisa
stok berpindah, kebutuhan per item pekerjaan RAB, tab Pengadaan, dan sheet export."""

import os

import pytest
from conftest import AC20

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


# ---------------------------------------------------------------- kemasan beli


def test_kemasan_beli_dalam_satuan_analisa():
    from setara import jumlah_beli, setara, setara_rinci, teks_kemasan

    teks, k = setara_rinci("Semen Portland (PC)", "kg", 1001)
    assert teks == setara("Semen Portland (PC)", "kg", 1001) == "≈ 21 zak @ 50 kg"
    assert teks_kemasan(k) == "21 zak @ 50 kg" and jumlah_beli(k) == 1050
    _, k = setara_rinci("Cat tembok interior", "kg", 30)
    assert teks_kemasan(k) == "1 pail @ 25 kg + 1 galon @ 5 kg" and jumlah_beli(k) == 30
    _, k = setara_rinci("Baja Tulangan Polos (BjTP) diameter < 12 mm", "kg", 43.38, {8: 10.0, 10: 30.0, 13: 50.0})
    assert teks_kemasan(k) == "5 btg Ø10 @ 12 m + 3 btg Ø8 @ 12 m"
    assert jumlah_beli(k) == pytest.approx(5 * 0.617 * 12 + 3 * 0.395 * 12, rel=0.01)  # berat batang per diameter
    _, k = setara_rinci("Keramik 40x40 cm", "m2", 12)  # dus dalam m²: 13 × 0,96
    assert jumlah_beli(k) == pytest.approx(12.48)
    _, k = setara_rinci("Kaso 5/7 kayu kelas II", "m3", 0.027)
    assert jumlah_beli(k) == pytest.approx(2 * 0.05 * 0.07 * 4)
    _, k = setara_rinci("Paku 2 inch", "kg", 2.28)  # eceran dibulatkan 0,5 kg
    assert teks_kemasan(k) == "2,5 kg (eceran)"
    # sisa kemasan besar dibeli dengan kemasan kecil
    assert setara("Paku 4 inch", "kg", 211.36).startswith("≈ 7 dus @ 30 kg + 1,5 kg eceran")
    assert setara("Pasir beton", "kg", 49738) == "≈ 35,53 m³ ≈ 5 truk @ 7 m³ + 1 pick-up @ 1,5 m³"
    _, k = setara_rinci("Adukan beton K-250 ready mix", "m3", 18.2)  # dipesan per 0,5 m³
    assert jumlah_beli(k) == 18.5
    _, k = setara_rinci("Batu paras", "m2", 15.4)  # tanpa kemasan: dibeli sesuai kebutuhan
    assert jumlah_beli(k) == 15.4 and teks_kemasan(k) == "15,4 m2"
    _, k = setara_rinci("Genteng beton", "buah", 978.74)
    assert jumlah_beli(k) == 979
    _, k = setara_rinci("Kayu papan kelas III", "buah", 0.888)  # satuan HSPK janggal (⚠): tanpa pembulatan
    assert jumlah_beli(k) == pytest.approx(0.888)


def test_jumlah_beli_tidak_pernah_kurang_dari_kebutuhan():
    from database.hspk_bandung_2027 import AHSP, HSD
    from setara import jumlah_beli, setara_rinci

    pas = {(n.strip(), s.strip()) for t, n, s, _h in HSD if t == "bahan"}
    pas |= {(n.strip(), s.strip()) for v in AHSP.values() for t, n, s, _k, _h in v[3] if t == "bahan"}
    for jumlah in (0.37, 3.2, 47.0, 1234.5):
        for n, s in pas:
            assert jumlah_beli(setara_rinci(n, s, jumlah)[1]) >= jumlah * 0.999, (n, s, jumlah)


# ---------------------------------------------------------------- jadwal pengadaan


def _kelompok(nama, satuan, jumlah, harga, besi=None, tahap="Beton", lantai="01"):
    from kebutuhan_lantai import _isi_setara

    d = {"nama": nama, "satuan": satuan, "jumlah": jumlah, "biaya": jumlah * harga, "harga": harga, "merk": ""}
    _isi_setara(d, besi)
    return {"tahap": tahap, "nomor": 1, "lantai": lantai, "sumber_daya": {"bahan": [d], "besi": besi or {}}}


def test_jadwal_pengadaan_sisa_stok_dipakai_tahap_berikutnya():
    from kebutuhan_lantai import jadwal_pengadaan

    kel = [_kelompok("Semen Portland (PC)", "kg", 1001, 2125, lantai="01"),
           _kelompok("Semen Portland (PC)", "kg", 40, 2125, lantai="02"),
           _kelompok("Semen Portland (PC)", "kg", 120, 2125, lantai="03")]
    j = jadwal_pengadaan(kel)
    assert [x[0]["dibeli"] for x in j] == [1050, 0.0, 150]  # lantai 2 cukup dari sisa 49 kg lantai 1
    assert [round(x[0]["stok_awal"], 2) for x in j] == [0.0, 49.0, 9.0]
    assert j[1][0]["kemasan"] == [] and j[1][0]["biaya_beli"] == 0
    assert j[2][0]["sisa"] == pytest.approx(39.0)


def test_jadwal_pengadaan_stok_baja_per_diameter():
    """Sisa D16 tidak dapat menggantikan D13: stok baja dihitung per diameter."""
    from kebutuhan_lantai import jadwal_pengadaan

    kel = [_kelompok("Baja Tulangan Sirip (BjTS)", "kg", 20.0, 15000, {16: 20.0}),
           _kelompok("Baja Tulangan Sirip (BjTS)", "kg", 10.0, 15000, {13: 10.0})]
    j = jadwal_pengadaan(kel)
    assert [k.nama for k in j[0][0]["kemasan"]] == ["btg D16"]
    assert [k.nama for k in j[1][0]["kemasan"]] == ["btg D13"]  # sisa D16 (± 17,9 kg) tidak dipakai untuk D13
    assert j[1][0]["stok_awal"] == 0.0


# ---------------------------------------------------------------- proyek nyata


@pytest.fixture
def proyek_ac20(db_sementara):
    from database.proyek_repository import create_proyek
    from estimasi_service import jalankan_estimasi

    pid = create_proyek("AC20", str(AC20))
    jalankan_estimasi(pid)
    return pid


def _data(pid):
    from database.estimasi_repository import get_hasil_estimasi_by_proyek
    from kebutuhan_lantai import komponen_pekerjaan

    baris = [dict(r) for r in get_hasil_estimasi_by_proyek(pid)]
    return baris, komponen_pekerjaan(r["pekerjaan_id"] for r in baris)


def test_kebutuhan_per_tahap_dan_per_pekerjaan_cocok_dengan_rab(proyek_ac20):
    from database.estimasi_repository import BUK_RATE
    from kebutuhan_lantai import (
        jadwal_pengadaan,
        kebutuhan_per_pekerjaan,
        kebutuhan_per_tahap,
        kebutuhan_sumber_daya,
    )
    from rab_rinci import URUTAN_KATEGORI

    baris, kom = _data(proyek_ac20)
    kb = kebutuhan_sumber_daya(baris, kom)
    total = sum(d["biaya"] for t in ("bahan", "upah", "alat") for d in kb[t])
    tahap = kebutuhan_per_tahap(baris, kom)
    assert sum(g["biaya"] for g in tahap) == pytest.approx(total)
    urutan = [URUTAN_KATEGORI.index(g["tahap"]) for g in tahap]
    assert urutan == sorted(urutan)  # urutan pelaksanaan
    assert all(g["lantai"] for g in tahap) and all(g["lantai"] is None for g in kebutuhan_per_tahap(baris, kom, False))
    # beli bertahap: setiap bahan dibeli >= kebutuhannya, sisa akhir < satu kemasan terbesar
    beli = {}
    for g in jadwal_pengadaan(tahap):
        for x in g:
            b = beli.setdefault((x["nama"], x["satuan"]), [0.0, 0.0])
            b[0] += x["kebutuhan"]
            b[1] += x["dibeli"]
    assert all(dibeli >= butuh - 1e-6 for butuh, dibeli in beli.values())
    # per item pekerjaan: harga dasar × (1 + biaya umum & keuntungan) = jumlah RAB item
    items = [it for k in kebutuhan_per_pekerjaan(baris, kom) for it in k["items"]]
    assert sum(it["biaya"] for it in items) == pytest.approx(total)
    for it in items:
        assert it["biaya"] * (1 + BUK_RATE) == pytest.approx(it["jumlah_rab"], rel=1e-6, abs=1.0), it["nama"]
    semen = [it for it in items if ("bahan", "semen portland (pc)", "kg") in it["koefisien"]]
    assert semen and all(it["koefisien"][("bahan", "semen portland (pc)", "kg")] > 0 for it in semen)


def test_tab_pengadaan_dan_rincian_item_rab(proyek_ac20, qapp_pengadaan):
    from gui.estimasi_page import EstimasiPage

    hal = EstimasiPage(proyek_ac20, "AC20")
    try:
        assert hal.combo_kelompok.isHidden()
        hal.grup_mode.button(hal.MODE_PENGADAAN).click()
        assert not hal.combo_kelompok.isHidden() and hal.combo_pakai.isHidden()
        t = hal.tabel
        judul = [t.horizontalHeaderItem(i).text() for i in range(t.columnCount())]
        assert judul == ["NO", "BAHAN", "KEBUTUHAN", "SAT", "DIBELI (KEMASAN)", "BIAYA BELI", "SISA"]
        grup = [t.item(i, 1).text() for i in range(t.rowCount()) if t.item(i, 0) and t.item(i, 0).data(0x0100)
                and t.item(i, 0).data(0x0100)[0] == "grup_beli"]
        assert grup and all(" · " in g for g in grup)  # tahap · lantai
        i = next(i for i in range(t.rowCount()) if t.item(i, 0) and t.item(i, 0).data(0x0100)
                 and t.item(i, 0).data(0x0100)[0] == "beli")
        t.selectRow(i)
        hal._tampilkan_rincian()
        teks = [w.text() for w in hal.panel.findChildren(type(hal.label_jumlah))]
        assert "PENGADAAN BAHAN" in teks and "Biaya beli" in teks and "Merk" in teks
        hal.combo_kelompok.setCurrentIndex(hal.combo_kelompok.findData("proyek"))
        assert t.item(0, 1).text() == "SELURUH PROYEK (BELI SEKALIGUS)"
        from database.preferensi_repository import get_pref
        assert get_pref("pengadaan_kelompok") == "proyek"
        # RAB: panel item pekerjaan memuat bahan, tenaga kerja, dan alat lengkap
        hal.grup_mode.button(hal.MODE_REKAP).click()
        pid = next(r["pekerjaan_id"] for r in hal._data if (r["kode_ahsp"] or "").startswith("BTN."))
        hal.panel.tampilkan_pekerjaan(pid, [r for r in hal._data if r["pekerjaan_id"] == pid], hal.komponen())
        teks = [w.text() for w in hal.panel.findChildren(type(hal.label_jumlah))]
        assert any(x.startswith("KEBUTUHAN ITEM INI") for x in teks)
        assert any(x.startswith("BAHAN / MATERIAL · Rp") for x in teks)
        assert any(x.startswith("TENAGA KERJA · Rp") for x in teks)
    finally:
        hal.deleteLater()


def test_export_sheet_tahap_pekerjaan_pengadaan(proyek_ac20, tmp_path):
    from openpyxl import load_workbook

    from export_service import OpsiExport, ambil_data_export, export_excel, export_pdf

    data = ambil_data_export(proyek_ac20)
    opsi = OpsiExport(rekap=False, rinci=False, besi=False, detail=False, lantai=False, per_lantai=False)
    wb = load_workbook(export_excel(tmp_path / "p.xlsx", data, {"nama_proyek": "AC20"}, opsi))
    for nama in ("Kebutuhan per Tahap", "Kebutuhan per Pekerjaan", "Pengadaan Bahan", "Jadwal Pengadaan"):
        assert nama in wb.sheetnames
    def nilai(ws):
        return [[c.value for c in row] for row in ws.iter_rows()]

    th = nilai(wb["Kebutuhan per Tahap"])
    assert any(r[1] == "Bahan / Material" for r in th) and any(r[1] == "Tenaga Kerja" for r in th)
    assert any(str(r[1]).startswith("JUMLAH SELURUH TAHAP") for r in th)
    pk = nilai(wb["Kebutuhan per Pekerjaan"])
    assert any(str(r[1]).startswith("Bahan: Semen Portland") and r[2] for r in pk)  # dengan koefisien
    assert any(r[1] == "Jumlah di RAB (termasuk biaya umum & keuntungan)" for r in pk)
    pb = nilai(wb["Pengadaan Bahan"])
    hdr = next(i for i, r in enumerate(pb) if r[0] == "No")
    assert pb[hdr] == ["No", "Bahan", "Kebutuhan", "Sat", "Dibeli (Kemasan)", "Jumlah Beli", "Harga Dasar (Rp)",
                       "Biaya Kebutuhan (Rp)", "Biaya Beli (Rp)", "Merk"]
    semen = next(r for r in pb if r[1] == "Semen Portland (PC)")
    assert semen[4].endswith("zak @ 50 kg") and semen[5] % 50 == 0 and str(semen[8]).startswith("=F")
    jp = nilai(wb["Jadwal Pengadaan"])
    assert any(r[1] == "JUMLAH BIAYA BELI BERTAHAP" for r in jp)
    assert any(" · " in str(r[1]) and str(r[0]).endswith(".") for r in jp)
    from pypdf import PdfReader

    teks = " ".join(" ".join(p.extract_text().split()) for p in PdfReader(
        export_pdf(tmp_path / "p.pdf", data, {"nama_proyek": "AC20"}, opsi)).pages)
    assert "Pengadaan bahan: jumlah beli dalam kemasan" in teks


@pytest.fixture(scope="module")
def qapp_pengadaan():
    from PySide6.QtWidgets import QApplication

    from gui import tema

    app = QApplication.instance() or QApplication([])
    tema.terapkan(app, "gelap")
    return app
