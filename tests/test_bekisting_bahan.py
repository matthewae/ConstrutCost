"""Bahan bekisting (kayu & triplek termurah, dapat dipilih per proyek), panjang paku dari tebal bekisting, mutu beton
dalam K, dan kolom SETARA kebutuhan bahan (baja tulangan -> batang 12 m, pasir -> m³, kawat -> rol, ...)."""

import os
import sqlite3

import pytest
from conftest import AC20

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


# ---------------------------------------------------------------- paku & bahan


def test_paku_dari_tebal_bekisting_bukan_12_cm():
    from bahan_bekisting import paku, paku_rangka

    # plywood 12 mm + balok 6/12: tebal 7,2 cm -> paku 3,6 s.d. 7,2 cm -> 5 cm (2 inch), bukan 12 cm
    assert paku(1.2, 6.0) == (5.0, "Paku 2 inch", 3.6, 7.2)
    assert paku(0.9, 5.0)[:2] == (5.0, "Paku 2 inch")  # tripleks 9 mm + kaso 5/7 (bawaan)
    assert paku(1.8, 6.0)[:2] == (7.0, "Paku 5 dan 7 cm")  # multiplek 18 mm: paku >= 5,4 cm
    assert paku(1.8, 5.0)[:2] == (5.0, "Paku 2 inch")  # 18 mm + kaso 5/7 (6,8 cm): 7 cm tembus -> 5 cm
    for t in (0.9, 1.2):
        for k in (5.0, 6.0):
            assert paku(t, k)[0] <= t + k  # paku tidak pernah lebih panjang dari tebal bekisting
    # sambungan rangka kayu ke kayu: <= 2 x tebal kayu (tidak tembus), >= 1,5 x tebal kayu
    assert paku_rangka(5.0) == (10.0, "Paku 4 inch", 7.5, 10.0)  # kaso 5/7: paku 12 cm akan tembus 2 cm
    assert paku_rangka(6.0)[:2] == (10.0, "Paku 4 inch") and paku_rangka(6.0)[3] == 12.0  # balok 6/12: <= 12 cm


def test_komponen_bekisting_hspk_diganti_bahan_termurah():
    from bahan_bekisting import KAYU_BAWAAN, TRIPLEK_BAWAAN, ganti_komponen
    from database.seed_data import ANALISA

    kolom, catatan = ganti_komponen(ANALISA["2.2.1.3.3"][3], KAYU_BAWAAN, TRIPLEK_BAWAAN)
    bahan = {k[1]: k for k in kolom if k[0] == "bahan"}
    assert {"Kaso 5/7 kayu kelas II", "Tripleks t=9mm", "Paku 4 inch", "Paku 2 inch"} <= set(bahan)
    assert not {"Kayu balok 6/12 kelas II", "Plywood 12 mm", "Paku 12 cm"} & set(bahan)
    assert bahan["Kaso 5/7 kayu kelas II"][3] == pytest.approx(0.00465)  # koefisien HSPK tetap
    assert bahan["Paku 4 inch"][3] == pytest.approx(0.4)  # koefisien paku HSPK = paku sambungan rangka
    assert bahan["Paku 2 inch"][3] == pytest.approx(0.03)  # paku triplek ke rangka (seperti HSPK 3.5.2.3.x)
    assert any("Paku 12 cm → Paku 4 inch" in c for c in catatan)
    assert any("Paku 2 inch 5 cm" in c and "triplek ke rangka" in c for c in catatan)
    # bekisting fondasi HSPK memakai papan kayu tanpa triplek: papan & paku tidak diganti
    fondasi, catatan = ganti_komponen(ANALISA["2.2.1.3.1"][3], KAYU_BAWAAN, TRIPLEK_BAWAAN)
    assert fondasi == list(ANALISA["2.2.1.3.1"][3]) and catatan == []


def test_kode_varian_bekisting():
    from bahan_bekisting import kode_varian_bekisting, urai_varian

    assert kode_varian_bekisting("BSK.KOLOM", "kaso57", "t9") == "BSK.KOLOM"
    assert kode_varian_bekisting("BSK.KOLOM", "balok612k2", "p12") == "BSK.KOLOM~balok612k2+p12"
    assert urai_varian("BSK.KOLOM~balok612k2+p12") == ("BSK.KOLOM", "balok612k2", "p12")
    assert urai_varian("BSK.KOLOM~kayu-aneh+p12") is None and urai_varian("BTN.KOLOM~m21") is None


@pytest.fixture
def proyek(db_sementara):
    from database.proyek_repository import create_proyek
    from estimasi_service import jalankan_estimasi

    pid = create_proyek("AC20", str(AC20))
    jalankan_estimasi(pid)
    conn = sqlite3.connect(db_sementara)
    conn.row_factory = sqlite3.Row
    yield pid, conn
    conn.close()


def _bekisting(conn, pid):
    return conn.execute(
        """SELECT h.id, h.subtotal_biaya, p.kode_ahsp, p.id AS pid FROM hasil_estimasi h JOIN pekerjaan p
           ON p.id = h.pekerjaan_id WHERE h.proyek_id = ? AND p.kode_ahsp LIKE 'BSK.%'""", (pid,)).fetchall()


def _bahan(conn, pekerjaan_id):
    return {r["nama_komponen"] for r in conn.execute(
        "SELECT nama_komponen FROM komponen_harga WHERE pekerjaan_id = ? AND tipe = 'bahan'", (pekerjaan_id,))}


def test_pilihan_kayu_dan_triplek_per_proyek(proyek):
    from database.material_repository import muat_pilihan, ringkasan_opsi, simpan_pilihan
    from estimasi_service import jalankan_estimasi

    pid, conn = proyek
    awal = _bekisting(conn, pid)
    assert awal and all("~" not in r["kode_ahsp"] for r in awal)
    pelat = next(r for r in awal if r["kode_ahsp"] in ("BSK.PELAT", "BSK.DAK", "BSK.KOLOM", "BSK.BALOK"))
    assert {"Kaso 5/7 kayu kelas II", "Tripleks t=9mm", "Paku 4 inch", "Paku 2 inch"} <= _bahan(conn, pelat["pid"])
    total_awal = sum(r["subtotal_biaya"] for r in awal)

    opsi = ringkasan_opsi()
    assert opsi["BSK.KAYU"]["dasar"] == pytest.approx(2_497_500) and opsi["BSK.TRIPLEK"]["dasar"] == 150_000
    assert opsi["BSK.KAYU~balok612k2"]["dasar"] > opsi["BSK.KAYU"]["dasar"]

    hasil = simpan_pilihan(pid, {"BSK.KAYU": "balok612k2", "BSK.TRIPLEK": "p12"})
    assert set(hasil["berubah"]) == {"BSK.KAYU", "BSK.TRIPLEK"} and hasil["baris"] == len(awal)
    ganti = _bekisting(conn, pid)
    assert all(r["kode_ahsp"].endswith("~balok612k2+p12") for r in ganti)
    bahan = _bahan(conn, next(r for r in ganti if r["id"] == pelat["id"])["pid"])
    assert {"Kayu balok 6/12 kelas II", "Plywood 12 mm", "Paku 2 inch", "Paku 4 inch"} <= bahan  # 5 & 10 cm
    assert sum(r["subtotal_biaya"] for r in ganti) > total_awal  # kayu & plywood HSPK lebih mahal
    nama = conn.execute("SELECT nama_pekerjaan FROM pekerjaan WHERE id = ?", (ganti[0]["pid"],)).fetchone()[0]
    assert "Balok 6/12 kayu kelas II" in nama and "Plywood 12 mm" in nama

    jalankan_estimasi(pid)  # hitung ulang dari IFC: pilihan bahan bekisting proyek tetap dipakai
    assert all(r["kode_ahsp"].endswith("~balok612k2+p12") for r in _bekisting(conn, pid))
    assert muat_pilihan(pid)["BSK.TRIPLEK"] == "p12"

    simpan_pilihan(pid, {"BSK.KAYU": "kaso57", "BSK.TRIPLEK": "t9"})  # kembali ke bawaan
    kembali = _bekisting(conn, pid)
    assert all("~" not in r["kode_ahsp"] for r in kembali)
    assert sum(r["subtotal_biaya"] for r in kembali) == pytest.approx(total_awal)


def test_dialog_ganti_bahan_kelompok_bekisting(proyek, qapp_bekisting):
    from gui.estimasi_page import EstimasiPage
    from gui.material_dialog import MaterialDialog

    pid, _conn = proyek
    hal = EstimasiPage(pid, "AC20")
    d = MaterialDialog(pid, hal._data, hal)
    try:
        assert {"BSK.KAYU", "BSK.TRIPLEK"} <= set(d.combo)
        cb = d.combo["BSK.KAYU"]
        assert cb.currentData() == "kaso57" and "(bawaan)" in cb.currentText() and "Rp" in cb.currentText()
        info = d._info["BSK.TRIPLEK"].text()
        assert "Paku triplek ke rangka: Paku 2 inch" in info and "sambungan rangka: Paku 4 inch" in info
        assert d._volume["BSK.KAYU"] > 0 and d._volume["BSK.TRIPLEK"] > 0
        d.combo["BSK.TRIPLEK"].setCurrentIndex(d.combo["BSK.TRIPLEK"].findData("m18"))
        # paku triplek ikut tebal triplek: 3 x 1,8 = 5,4 cm s.d. 1,8 + 5 = 6,8 cm; tanpa ukuran di antaranya dipilih
        # yang terpanjang tanpa tembus (5 cm), bukan 7 cm yang tembus
        assert "5,4–6,8 cm" in d._info["BSK.KAYU"].toolTip()
        assert "Paku triplek ke rangka: Paku 2 inch (5,0 cm)" in d._info["BSK.KAYU"].text()
        assert d._selisih() > 0 and d.btn_simpan.isEnabled()
    finally:
        d.deleteLater()
        hal.deleteLater()


@pytest.fixture(scope="module")
def qapp_bekisting():
    from PySide6.QtWidgets import QApplication

    from gui import tema

    app = QApplication.instance() or QApplication([])
    tema.terapkan(app, "gelap")
    return app


# ---------------------------------------------------------------- mutu beton K


def test_mutu_beton_ditulis_dalam_k():
    from database.material import SLOT, mutu_k
    from database.seed_data import PEMETAAN
    from kebutuhan_lantai import mutu_beton

    assert [mutu_k(x) for x in (7.5, 10, 15, 17, 20, 21, 25, 30)] == [100, 125, 175, 200, 250, 250, 300, 350]
    assert SLOT["BTN.KOLOM"].cari("m20").label == "K-250, campuran manual"
    assert SLOT["BTN.KOLOM"].cari("rm25").label == "K-300, ready mix"
    assert "f'c 21 MPa" in SLOT["BTN.KOLOM"].cari("m21").label  # K-250 kedua dibedakan dengan f'c-nya
    assert PEMETAAN["BTN.KOLOM"][0] == "Beton Kolom K-250" and PEMETAAN["LTK.FONDASI"][0].count("K-100") == 1
    assert not [k for k, v in PEMETAAN.items() if k.startswith(("BTN.", "LTK.")) and "f'c" in v[0]
                and "f'c 21" not in v[0]]
    assert mutu_beton("Beton Kolom K-250 (Ready Mix)") == "K-250"
    assert mutu_beton("Beton Kolom f'c 20 MPa") == "K-250"  # nama lama (proyek lama) tetap dikelompokkan


# ---------------------------------------------------------------- setara


def test_setara_satuan_beli_di_lapangan():
    from setara import setara

    besi = {8: 10.0, 10: 30.0, 13: 50.0}
    assert setara("Baja Tulangan Polos (BjTP) diameter < 12 mm", "kg", 43.38, besi) == "≈ 5 btg Ø10 + 3 btg Ø8 @ 12 m"
    assert setara("Baja Tulangan Sirip (BjTS) diameter >12 mm", "kg", 58.61, besi) == "≈ 5 btg D13 @ 12 m"
    assert "asumsi" in setara("Baja Tulangan Polos (BjTP) diameter < 12 mm", "kg", 43.38)
    assert setara("Semen Portland (PC)", "kg", 1001) == "≈ 21 zak @ 50 kg"
    assert setara("Pasir beton", "kg", 338) == "≈ 0,24 m³"
    assert setara("Batu split 2/3", "kg", 9000) == "≈ 6,67 m³ ≈ 1 truk @ 7 m³"
    assert setara("Kaso 5/7 kayu kelas II", "m3", 0.027) == "≈ 2 btg 5/7 @ 4 m"
    assert setara("Kawat beton", "kg", 1.59) == "beli 1 rol @ 25 kg (terpakai 6%)"
    assert setara("Paku 2 inch", "kg", 2.28) == "≈ 750 btg (± 330 btg/kg) · eceran per kg"
    assert setara("Minyak bekisting", "liter", 1.14) == "beli 1 jeriken @ 20 liter"
    assert setara("Cat tembok interior", "kg", 30) == "≈ 1 pail @ 25 kg + 1 galon @ 5 kg"
    assert setara("Keramik 40x40 cm", "m2", 12) == "≈ 13 dus @ 0,96 m²"
    assert setara("Air", "liter", 86.36) == "≈ 0,09 m³"
    assert setara("Pekerja", "OH", 3) == "orang-hari"
    assert setara("Keramik Lantai uk. 40 x 40 cm, Polished", "buah", 1216) == "≈ 203 dus @ 6 buah"
    assert setara("Bata ringan tebal 10 cm", "buah", 1889) == "≈ 22,67 m³ (60 × 20 × 10 cm)"
    assert setara("Pipa besi hitam 3 inch", "m'", 161) == "≈ 27 btg @ 6 m"
    assert setara("Pipa PVC 4 inch", "m'", 30) == "≈ 8 btg @ 4 m"
    assert setara("Kabel listrik NYM", "m'", 100) == ""  # bukan profil batang
    assert setara("Lem Kayu", "kg", 46.98) == "≈ 19 kaleng @ 2,5 kg"
    assert setara("Wiremesh M6", "kg", 35.94) == "≈ 2 lembar M6 @ 2,1 × 5,4 m (± 33,6 kg)"
    assert setara("Paku 4 inch", "kg", 48.0).startswith("≈ 2 dus @ 30 kg")
    assert setara("Paku 2 inch", "kg", 2.28).endswith("eceran per kg")
    assert setara("Self Drilling Screw dia-6 x 20 mm (Main Truss Screw)", "buah", 6511.89) == "≈ 7 dus @ 1.000 buah"
    assert setara("Baja Ringan C75, t=1 mm (Batang Utama)", "batang", 253.74) == "≈ 254 btg @ 6 m"
    assert setara("Dolken kayu φ 8-10 panjang 400 cm", "batang", 911.73) == "≈ 912 btg @ 4 m"
    assert setara("Pasir pasang (quarry - lokasi pekerjaan)", "m3", 74.52) == "≈ 11 truk @ 7 m³"
    assert setara("Kayu papan kelas II", "m3", 3.17).endswith("(asumsi papan 2/20)")
    assert setara("Besi strip (20x3) mm", "kg", 17.22) == "≈ 7 btg @ 6 m (± 2,83 kg/btg)"
    assert setara("Membran Bakar", "m'", 81.93) == "≈ 9 rol @ 1 × 10 m"
    assert setara("Minyak Bekisting", "m3", 17.01).startswith("⚠ satuan HSPK m³")


def test_setara_baja_memakai_diameter_penulangan_proyek(proyek):
    from database.estimasi_repository import get_hasil_estimasi_by_proyek
    from kebutuhan_lantai import kebutuhan_sumber_daya, komponen_pekerjaan

    pid, _conn = proyek
    baris = [dict(r) for r in get_hasil_estimasi_by_proyek(pid)]
    sd = kebutuhan_sumber_daya(baris, komponen_pekerjaan(r["pekerjaan_id"] for r in baris))
    baja = [d for d in sd["bahan"] if "baja tulangan" in d["nama"].lower()]
    assert baja and all("btg" in d["keterangan"] and "@ 12 m" in d["keterangan"] for d in baja)
    semen = next(d for d in sd["bahan"] if d["nama"].lower().startswith("semen"))
    assert "zak" in semen["keterangan"]


def test_ganti_bahan_langsung_dari_kebutuhan_bahan(proyek, qapp_bekisting):
    """Nama bahan yang dapat diganti menjadi combo di tab Kebutuhan Bahan: tanpa saringan berlaku untuk proyek,
    dengan saringan hanya untuk elemen yang tersaring (kayu bekisting pun dapat berbeda per elemen)."""
    from PySide6.QtWidgets import QComboBox

    from database.material_repository import material_elemen, muat_pilihan
    from estimasi_service import jalankan_estimasi
    from gui.estimasi_page import EstimasiPage
    from kebutuhan_lantai import jenis_elemen

    pid, conn = proyek
    hal = EstimasiPage(pid, "AC20")
    try:
        hal.grup_mode.button(hal.MODE_BAHAN).click()

        def combo(nama):
            t = hal.tabel
            for i in range(t.rowCount()):
                if t.item(i, 1) and t.item(i, 1).text() == nama:
                    w = t.cellWidget(i, 1)
                    return w if isinstance(w, QComboBox) else None
            raise AssertionError(f"baris {nama} tidak ada")

        assert combo("Semen Portland (PC)") is None  # berubah lewat mutu beton / campuran, bukan diganti langsung
        bata = combo("Bata ringan tebal 10 cm")
        assert bata is not None and bata.currentData() == "ringan10" and bata.findData("merah") >= 0
        kaso = combo("Kaso 5/7 kayu kelas II")
        assert kaso.currentData() == "kaso57" and "Rp" in kaso.currentText()

        kaso.setCurrentIndex(kaso.findData("balok612k2"))  # tanpa saringan: pilihan proyek
        assert muat_pilihan(pid)["BSK.KAYU"] == "balok612k2" and hal.riwayat.count() == 1
        assert all(r["kode_ahsp"].endswith("~balok612k2+t9") for r in _bekisting(conn, pid))
        hal.riwayat.undo()
        assert muat_pilihan(pid)["BSK.KAYU"] == "kaso57"
        assert all("~" not in r["kode_ahsp"] for r in _bekisting(conn, pid))

        r = next(x for x in hal._data if (x["kode_ahsp"] or "").startswith("BSK.") and x.get("elemen_id"))
        hal.saring.pilih_elemen(r["elemen_id"], jenis_elemen(r))  # satu elemen tersaring
        hal._isi_ulang()
        combo("Kaso 5/7 kayu kelas II").setCurrentIndex(combo("Kaso 5/7 kayu kelas II").findData("sengon"))
        assert muat_pilihan(pid)["BSK.KAYU"] == "kaso57"  # proyek tidak berubah
        elemen = {}
        for b in conn.execute("""SELECT h.elemen_id, p.kode_ahsp FROM hasil_estimasi h JOIN pekerjaan p
                                 ON p.id = h.pekerjaan_id WHERE h.proyek_id = ? AND p.kode_ahsp LIKE 'BSK.%'""",
                              (pid,)):
            elemen.setdefault(b["elemen_id"], set()).add(b["kode_ahsp"])
        assert all(k.endswith("~sengon+t9") for k in elemen.pop(r["elemen_id"]))
        assert all("~" not in k for ks in elemen.values() for k in ks)
        assert material_elemen(r["elemen_id"])["BSK.KAYU"] == {
            "kunci": "sengon", "khusus": True, "volume": pytest.approx(material_elemen(r["elemen_id"])["BSK.KAYU"]
                                                                         ["volume"]), "satuan": "m3"}
        gid = conn.execute("SELECT global_id FROM elemen_proyek WHERE id = ?", (r["elemen_id"],)).fetchone()[0]
        jalankan_estimasi(pid)  # hitung ulang dari IFC: kayu khusus elemen tetap berlaku (dicocokkan lewat GlobalId)
        kode = {b[0] for b in conn.execute(
            """SELECT p.kode_ahsp FROM hasil_estimasi h JOIN pekerjaan p ON p.id = h.pekerjaan_id
               JOIN elemen_proyek e ON e.id = h.elemen_id WHERE h.proyek_id = ? AND p.kode_ahsp LIKE 'BSK.%'
               AND e.global_id = ?""", (pid, gid))}
        assert kode and all(k.endswith("~sengon+t9") for k in kode)
    finally:
        hal.deleteLater()
