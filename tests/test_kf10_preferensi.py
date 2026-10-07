"""KF-10: preferensi pengguna (UC-07)."""

import pytest


def test_nilai_bawaan(db_sementara):
    from database.preferensi_repository import Preferensi, muat_preferensi

    assert muat_preferensi() == Preferensi()
    assert muat_preferensi().tema == "gelap"


def test_simpan_lalu_muat(db_sementara, tmp_path):
    from database.preferensi_repository import Preferensi, muat_preferensi, simpan_preferensi

    p = Preferensi(tema="terang", direktori_ifc=str(tmp_path), direktori_export=str(tmp_path),
                   format_excel=False, format_pdf=True, isi_rekap=True, isi_detail=False)
    simpan_preferensi(p)
    assert muat_preferensi() == p


@pytest.mark.parametrize(
    "ubah, pesan",
    [
        ({"tema": "biru"}, "Tema"),
        ({"format_excel": False, "format_pdf": False}, "minimal satu format"),
        ({"direktori_ifc": "/folder/yang/tidak/ada"}, "tidak ditemukan"),
        ({"direktori_export": "/folder/yang/tidak/ada"}, "tidak ditemukan"),
    ],
)
def test_validasi(db_sementara, ubah, pesan):
    from database.preferensi_repository import Preferensi, PreferensiTidakValid, simpan_preferensi

    with pytest.raises(PreferensiTidakValid, match=pesan):
        simpan_preferensi(Preferensi(**ubah))


def test_reset_ke_default(db_sementara, tmp_path):
    from database.preferensi_repository import (
        Preferensi, muat_preferensi, reset_preferensi, set_pref, simpan_preferensi,
    )

    simpan_preferensi(Preferensi(tema="terang", direktori_export=str(tmp_path)))
    set_pref("seed_versi", "x")  # data lain tidak ikut terhapus
    assert reset_preferensi() == Preferensi()
    assert muat_preferensi() == Preferensi()
    from database.preferensi_repository import get_pref

    assert get_pref("seed_versi") == "x"


def test_folder_export_versi_lama_ikut_terbaca(db_sementara, tmp_path):
    from database.preferensi_repository import folder_default, folder_export, muat_preferensi, set_pref

    set_pref("export_dir", str(tmp_path))  # kunci dari versi sebelum KF-10
    assert muat_preferensi().direktori_export == str(tmp_path)
    assert folder_export(muat_preferensi()) == str(tmp_path)
    set_pref("export_dir", "/sudah/dihapus")
    assert folder_export(muat_preferensi()) == folder_default()


def test_tema_terang_mengganti_token_warna(monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    if QApplication.instance() is None:  # stylesheet() menggambar ikon (QPixmap)
        test_tema_terang_mengganti_token_warna.app = QApplication([])
    from gui import tema

    try:
        tema.pilih_tema("terang")
        assert tema.TEMA_AKTIF == "terang" and tema.W["latar"] == tema.PALET["terang"]["latar"]
        assert tema.WARNA_TIPE["bahan"] == "#1f6fd1"
        css = tema.stylesheet()
        assert tema.PALET["terang"]["permukaan"] in css and tema.PALET["gelap"]["permukaan"] not in css
        assert set(tema.PALET["gelap"]) == set(tema.PALET["terang"])  # token kedua tema lengkap
    finally:
        tema.pilih_tema("gelap")
