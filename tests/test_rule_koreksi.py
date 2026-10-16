"""Koreksi basis aturan setelah audit: elemen bukan beton, sumuran hanya untuk kolom struktur, sloof
turunan, jenis fondasi menerus, bekisting balok monolit, cat eksterior, pekerjaan persiapan, dan
laporan elemen IFC yang tidak dihitung."""

from dataclasses import replace

import pytest

from rules import PARAMETER_DEFAULT as P
from rules import proses_semua, siapkan_konteks, terapkan_rules
from rules.sifat import bukan_beton, kolom_struktur, menerus_beton_dari_nama


def _el(kelas, **kw):
    dasar = dict(kelas=kelas, nama=f"{kelas}-1", predefined_type=None, lantai=None, elevasi_lantai=None)
    dasar.update(kw)
    return dasar


def _total(elemen, parameter=P):
    """Jumlah volume per kode pekerjaan untuk satu model + daftar peringatan."""
    _, keluaran, dilewati = proses_semua(elemen, parameter)
    total = {}
    for _e, hasil in keluaran:
        for h in hasil:
            total[h.kode] = total.get(h.kode, 0) + h.volume
    return total, dilewati


def _rumah(*tambahan, eksternal=True):
    """Rumah 1 lantai sederhana tanpa fondasi di model: 4 dinding luar 10 m + 1 partisi tipis + pelat dasar."""
    dinding = [
        _el("WALL", nama=f"Dinding luar {i}", elevasi_lantai=0.0, panjang=10.0, tinggi=3.0, tebal=0.15,
            luas=30.0, volume=4.5, eksternal=eksternal)
        for i in range(4)
    ]
    partisi = _el("WALL", nama="Partisi gypsum", elevasi_lantai=0.0, panjang=4.0, tinggi=3.0, tebal=0.075,
                  luas=12.0, volume=0.9, eksternal=False if eksternal is not None else None)
    pelat = _el("SLAB", nama="Lantai dasar", predefined_type="BASESLAB", elevasi_lantai=0.0, luas=100.0,
                tebal=0.10, volume=10.0)
    return [*dinding, partisi, pelat, *tambahan]


# ---------------------------------------------------------------- elemen bukan beton


@pytest.mark.parametrize("e, alasan", [
    (_el("SLAB", tebal=0.019, luas=22, volume=0.42), "lapisan finishing"),
    (_el("SLAB", nama="Floor:Residential - Wood Joist with Subflooring", tebal=0.305, luas=59, volume=18),
     "kayu"),
    (_el("BEAM", nama="M_W-Wide Flange:W310X60:207325", lebar=0.17, tinggi=0.30, panjang=5, volume=0.04),
     "profil baja"),
    (_el("BEAM", nama="Balok B2", lebar=0.17, tinggi=0.30, panjang=5.0, volume=0.04), "berongga"),
    (_el("BEAM", nama="Gording 8/16", lebar=0.08, tinggi=0.16, panjang=10, volume=0.13), "terlalu kecil"),
    (_el("COLUMN", nama="Kolom IWF 200", lebar=0.2, tebal=0.2, tinggi=3, volume=0.02), "profil baja"),
])
def test_elemen_bukan_beton_dikenali(e, alasan):
    assert alasan in bukan_beton(e)
    hasil, dilewati = terapkan_rules(e)
    assert not any(h.kode.startswith(("BTN.", "BSI.", "BSK.")) for h in hasil)
    assert any("tidak dihitung sebagai beton bertulang" in d for d in dilewati)


@pytest.mark.parametrize("e", [
    _el("SLAB", nama="Pelat lantai 12", tebal=0.12, luas=20, volume=2.4),
    _el("BEAM", nama="Balok B1 20/30", lebar=0.2, tinggi=0.3, panjang=4, volume=0.24),
    _el("COLUMN", nama="Kolom bulat D30", lebar=0.3, tebal=0.3, tinggi=3, volume=0.212),  # isi 78,5 %
    _el("BEAM", nama="Ring balok", lebar=0.12, tinggi=0.15, panjang=4, volume=0.072),
])
def test_beton_biasa_tetap_beton(e):
    assert bukan_beton(e) is None
    hasil, _ = terapkan_rules(e)
    assert any(h.kode.startswith("BTN.") for h in hasil)


def test_lapisan_finishing_bukan_sumber_lantai_plafon():
    """Pelat finishing tidak dipakai sebagai sumber luas pelat dan tidak menambah keramik/plafon."""
    elemen = [
        _el("WALL", nama="Dinding lt 1", elevasi_lantai=0.0, panjang=4, tinggi=3, tebal=0.15, luas=12, volume=1.8),
        _el("SLAB", nama="Pelat", elevasi_lantai=3.0, tebal=0.12, luas=50, volume=6),
        _el("SLAB", nama="Finish Floor - Ceramic Tile", elevasi_lantai=3.0, tebal=0.013, luas=20, volume=0.26),
    ]
    total, _ = _total(elemen)
    assert total["BTN.PELAT"] == pytest.approx(6)
    assert total["KRM.LANTAI"] == pytest.approx(50) and total["PLF.GYPSUM"] == pytest.approx(50)
    assert total["BSK.PELAT"] == pytest.approx(50)  # bekisting hanya pelat beton


# ---------------------------------------------------------------- sumuran & kolom praktis


def test_sumuran_tidak_untuk_kolom_praktis():
    struktur = _el("COLUMN", nama="K1", elevasi_lantai=0.0, lebar=0.2, tebal=0.25, tinggi=3, volume=0.15)
    praktis = _el("COLUMN", nama="KP", elevasi_lantai=0.0, lebar=0.13, tebal=0.13, tinggi=3, volume=0.05)
    tanpa_ukuran = _el("COLUMN", nama="K?", elevasi_lantai=0.0, tinggi=3, volume=0.15)
    assert kolom_struktur(struktur) and not kolom_struktur(praktis) and kolom_struktur(tanpa_ukuran)
    _, keluaran, _ = proses_semua([struktur, praktis, tanpa_ukuran])
    kode = {e["nama"]: {h.kode for h in hasil} for e, hasil in keluaran}
    assert "BTN.SUMURAN" in kode["K1"] and "TNH.GALIAN.3" in kode["K1"]  # sumuran 2 m + poer 0,25 m
    assert "BTN.SUMURAN" not in kode["KP"] and not any(k.startswith("TNH.") for k in kode["KP"])
    assert "BTN.SUMURAN" in kode["K?"]  # penampang tidak diketahui: fondasi tetap dihitung (aman)
    assert "BTN.KOLOM" in kode["KP"]  # kolom praktis tetap dihitung betonnya


# ---------------------------------------------------------------- sloof turunan


def test_sloof_turunan_di_atas_batu_kali():
    total, _ = _total(_rumah())
    # sloof hanya di bawah dinding pasangan (4 × 10 m); partisi 7,5 cm tidak berfondasi
    assert total["FDN.BATUKALI"] == pytest.approx((0.30 + 0.70) / 2 * 0.80 * 40)
    assert total["BTN.SLOOF"] == pytest.approx(0.15 * 0.20 * 40)  # 1 lantai -> otomatis 15/20
    assert total["BSK.SLOOF"] == pytest.approx(2 * 0.20 * 40)
    assert total["BSI.SLOOF.U"] > 0 and total["BSI.SLOOF.P"] > 0  # 4 D13 + sengkang Ø8-150
    assert "TNH.PASIR.SLOOF" not in total  # sloof duduk di atas batu kali


def test_sloof_turunan_ukuran_otomatis_dan_parameter():
    atas = [_el("WALL", nama="Dinding lt 2", elevasi_lantai=3.2, panjang=10.0, tinggi=3.0, tebal=0.15,
                luas=30.0, volume=4.5)]
    total, _ = _total(_rumah(*atas))
    assert total["BTN.SLOOF"] == pytest.approx(0.20 * 0.30 * 40)  # 2 lantai -> otomatis 20/30
    total, _ = _total(_rumah(), replace(P, sloof_lebar=0.25, sloof_tinggi=0.40))
    assert total["BTN.SLOOF"] == pytest.approx(0.25 * 0.40 * 40)


def test_tidak_ada_sloof_turunan_bila_sloof_dimodelkan():
    sloof = _el("BEAM", nama="Sloof S1 20/30", elevasi_lantai=0.0, lebar=0.2, tinggi=0.3, panjang=40,
                volume=2.4)
    total, _ = _total(_rumah(sloof))
    assert total["BTN.SLOOF"] == pytest.approx(2.4)  # hanya sloof model, dihitung sebagai sloof
    assert "BTN.BALOK" not in total
    assert total["BSK.SLOOF"] == pytest.approx(2 * 0.3 * 40)  # dua sisi, tanpa alas


def test_sloof_turunan_di_antara_footplate_diberi_pasir():
    footplate = _el("FOOTING", nama="F1", predefined_type="PAD_FOOTING", elevasi_lantai=-1.0, panjang=1.0,
                    lebar=1.0, tebal=0.25, keliling=4.0, volume=0.25)
    total, _ = _total(_rumah(footplate))
    assert "FDN.BATUKALI" not in total  # fondasi sudah dimodelkan
    assert total["BTN.SLOOF"] == pytest.approx(0.15 * 0.20 * 40)
    assert total["TNH.PASIR.SLOOF"] == pytest.approx(0.15 * P.tebal_pasir_sloof * 40)


# ---------------------------------------------------------------- fondasi menerus model


def test_jenis_fondasi_menerus_dari_nama_dan_parameter():
    assert menerus_beton_dari_nama("Wall Foundation:Bearing Footing - 900 x 300")
    assert menerus_beton_dari_nama("Pondasi menerus beton bertulang")
    assert not menerus_beton_dari_nama("Pondasi Batu Kali 30/70")
    assert not menerus_beton_dari_nama("Fondasi menerus")  # tanpa petunjuk: batu kali
    beton = _el("FOOTING", nama="Bearing Footing", predefined_type="STRIP_FOOTING", elevasi_lantai=-0.8,
                panjang=10, lebar=0.9, tebal=0.3, keliling=21.8, volume=2.7)
    total, _ = _total([beton])
    assert total["BTN.FONDASI"] == pytest.approx(2.7) and "FDN.BATUKALI" not in total
    assert total["BSK.FONDASI"] == pytest.approx(21.8 * 0.3) and total["LTK.FONDASI"] > 0
    total, _ = _total([beton], replace(P, fondasi_menerus_jenis=1))  # paksa batu kali
    assert total["FDN.BATUKALI"] == pytest.approx(2.7) and "BTN.FONDASI" not in total


def test_fondasi_menerus_beton_tidak_perlu_sloof_turunan():
    beton = _el("FOOTING", nama="Bearing Footing", predefined_type="STRIP_FOOTING", elevasi_lantai=-0.8,
                panjang=40, lebar=0.9, tebal=0.3, keliling=81.8, volume=10.8)
    total, _ = _total(_rumah(beton))
    assert "BTN.SLOOF" not in total
    batu = {**beton, "nama": "Pondasi batu kali"}
    total, _ = _total(_rumah(batu))
    assert total["BTN.SLOOF"] == pytest.approx(0.15 * 0.20 * 40)
    assert "TNH.PASIR.SLOOF" not in total  # di atas batu kali model


# ---------------------------------------------------------------- bekisting balok monolit


def test_bekisting_balok_dikurangi_tebal_pelat():
    elemen = [
        _el("WALL", nama="Dinding lt 1", elevasi_lantai=0.0, panjang=4, tinggi=3, tebal=0.15, luas=12, volume=1.8),
        _el("SLAB", nama="Pelat", elevasi_lantai=3.0, tebal=0.12, luas=40, volume=4.8),
        _el("BEAM", nama="B1", elevasi_lantai=3.0, lebar=0.2, tinggi=0.4, panjang=5, volume=0.4),
        _el("BEAM", nama="Ring balok", elevasi_lantai=3.0, lebar=0.15, tinggi=0.2, panjang=5, volume=0.15),
    ]
    _, keluaran, _ = proses_semua(elemen)
    bsk = {e["nama"]: h for e, hasil in keluaran for h in hasil if h.kode == "BSK.BALOK"}
    assert bsk["B1"].volume == pytest.approx((0.2 + 2 * (0.4 - 0.12)) * 5)
    assert "h − t_pelat" in bsk["B1"].rumus
    assert bsk["Ring balok"].volume == pytest.approx((0.15 + 2 * 0.2) * 5)  # ring balok tidak dikurangi
    _, keluaran, _ = proses_semua(elemen, replace(P, bekisting_balok_monolit=0))
    bsk = {e["nama"]: h for e, hasil in keluaran for h in hasil if h.kode == "BSK.BALOK"}
    assert bsk["B1"].volume == pytest.approx((0.2 + 2 * 0.4) * 5)


def test_tanpa_pelat_beton_bekisting_balok_utuh():
    balok = _el("BEAM", nama="B1", elevasi_lantai=3.0, lebar=0.2, tinggi=0.4, panjang=5, volume=0.4)
    siapkan_konteks([balok])
    assert balok["tebal_pelat_monolit"] is None


# ---------------------------------------------------------------- cat eksterior & persiapan


def test_cat_eksterior_untuk_sisi_luar_dinding_luar():
    total, dilewati = _total(_rumah())
    # 4 dinding luar 30 m²: 1 sisi interior + 1 sisi eksterior; partisi 12 m² dua sisi interior
    assert total["CAT.EKSTERIOR"] == pytest.approx(4 * 30)
    assert total["CAT.DINDING"] == pytest.approx(4 * 30 + 2 * 12)
    assert not any("IsExternal" in d for d in dilewati)


def test_tanpa_info_dinding_luar_semua_cat_interior_dan_diperingatkan():
    total, dilewati = _total(_rumah(eksternal=None))
    assert "CAT.EKSTERIOR" not in total and "PSP.BOWPLANK" not in total
    assert total["CAT.DINDING"] == pytest.approx(2 * (4 * 30 + 12))
    assert any("IsExternal" in d for d in dilewati)


def test_pekerjaan_persiapan():
    total, _ = _total(_rumah())
    assert total["PSP.BERSIH"] == pytest.approx(100)  # luas pelat lantai dasar
    # bowplank = keliling dinding luar + 8a (denah siku), a = 1,5 m
    assert total["PSP.BOWPLANK"] == pytest.approx(40 + 8 * P.jarak_bowplank)
    total, _ = _total(_rumah(), replace(P, jarak_bowplank=1.0))
    assert total["PSP.BOWPLANK"] == pytest.approx(48)


def test_pembersihan_dari_ruang_bila_tanpa_pelat_dasar():
    elemen = [
        _el("SPACE", nama="R. Tamu", elevasi_lantai=0.0, luas=30, keliling=22),
        _el("SPACE", nama="R. Tidur", elevasi_lantai=0.0, luas=12, keliling=14),
        _el("SPACE", nama="R. Atas", elevasi_lantai=3.0, luas=20, keliling=18),
        _el("WALL", nama="D", elevasi_lantai=0.0, panjang=4, tinggi=3, tebal=0.15, luas=12, volume=1.8),
    ]
    total, _ = _total(elemen)
    assert total["PSP.BERSIH"] == pytest.approx(42)


# ---------------------------------------------------------------- data dari model IFC


def test_dinding_luar_dibaca_dan_elemen_tidak_dihitung_dilaporkan(ekstrak_cache):
    from conftest import DUPLEX

    info, elemen, peringatan = ekstrak_cache(DUPLEX)
    luar = [e for e in elemen if e["kelas"] == "WALL" and e["eksternal"]]
    dalam = [e for e in elemen if e["kelas"] == "WALL" and e["eksternal"] is False]
    assert luar and dalam
    assert info.tidak_dihitung  # Duplex memuat tangga, railing, dll.
    assert any("Tangga (IfcStair)" in k for k in info.tidak_dihitung)
    assert any("tidak dihitung rule engine" in p for p in peringatan)


# ---------------------------------------------------------------- antarmuka


@pytest.fixture
def app():
    import os

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def test_dialog_parameter_pilihan_dan_otomatis(app, db_sementara):
    from database.parameter_repository import validasi_parameter
    from database.proyek_repository import create_proyek
    from gui.parameter_dialog import ParameterDialog, _Pilihan

    d = ParameterDialog(create_proyek("Uji", None))
    jenis = d.spin["fondasi_menerus_jenis"]
    assert isinstance(jenis, _Pilihan) and jenis.currentText() == "Otomatis dari nama"
    assert d.spin["sloof_lebar"].text() == "otomatis"
    jenis.setValue(2)
    assert d.nilai()["fondasi_menerus_jenis"] == 2.0 and d.btn_simpan.isEnabled()
    assert "bawaan Otomatis dari nama" in d.tanda["fondasi_menerus_jenis"][0].text()
    assert validasi_parameter(d.nilai())["fondasi_menerus_jenis"] == 2
    from database.parameter_repository import ParameterTidakValid
    with pytest.raises(ParameterTidakValid, match="otomatis"):
        validasi_parameter({**d.nilai(), "sloof_lebar": 0.05})
    d.deleteLater()


def test_dialog_tipe_penulangan_susunan_tumpuan(app, db_sementara):
    from conftest import AC20
    from database.proyek_repository import create_proyek
    from estimasi_service import jalankan_estimasi
    from gui.penulangan_dialog import PenulanganDialog

    pid = create_proyek("AC20", str(AC20))
    jalankan_estimasi(pid)
    d = PenulanganDialog(pid)
    d.muat()
    label = [d.tabel.item(i, 0).text() for i in range(d.tabel.rowCount())]
    assert "Pelat Lantai Dasar L1 (t = 20 cm)" in label and "Sloof S1 (20/30)" in label
    d.tabel.selectRow(label.index("Pelat Lantai P1 (t = 20 cm)"))
    assert d.combo_lapis.currentText() == "bawah penuh + atas tumpuan"
    assert [d.combo_lapis.itemData(i) for i in range(d.combo_lapis.count())] == [1, 3, 2]
    d.deleteLater()
