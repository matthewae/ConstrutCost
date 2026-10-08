"""KF-10: preferensi pengguna (UC-07)."""

import pytest


def test_nilai_bawaan(db_sementara):
    from database.preferensi_repository import Preferensi, muat_preferensi

    assert muat_preferensi() == Preferensi()
    assert muat_preferensi().tema == "hitam_kuning"  # identitas Mandajaya


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
        for nama in tema.PALET:  # token semua tema lengkap
            assert set(tema.PALET[nama]) == set(tema.PALET["hitam_kuning"]), nama
    finally:
        tema.pilih_tema(tema.TEMA_BAWAAN)


def test_migrasi_tema_lama_ke_hitam_kuning(db_sementara):
    """Pengguna versi lama menyimpan "gelap" sebagai bawaan: dipindah sekali ke Hitam Kuning.
    Setelah tema v2, pilihan "gelap" (Biru Malam) yang disimpan pengguna dihormati."""
    from database.estimasi_repository import _connect
    from database.preferensi_repository import Preferensi, muat_preferensi, simpan_preferensi

    conn = _connect()
    conn.execute("CREATE TABLE IF NOT EXISTS preferensi_pengguna (kunci TEXT PRIMARY KEY, nilai TEXT)")
    conn.execute("INSERT OR REPLACE INTO preferensi_pengguna VALUES ('pref.tema', 'gelap')")
    conn.commit()
    conn.close()
    assert muat_preferensi().tema == "hitam_kuning"
    simpan_preferensi(Preferensi(tema="gelap"))
    assert muat_preferensi().tema == "gelap"
    for t in ("terang_emas", "terang", "hitam_kuning"):
        simpan_preferensi(Preferensi(tema=t))
        assert muat_preferensi().tema == t


def _kontras(a: str, b: str) -> float:
    def lum(h):
        r, g, b_ = (int(h[i:i + 2], 16) / 255 for i in (1, 3, 5))
        f = lambda c: c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4  # noqa: E731
        return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b_)
    l1, l2 = sorted((lum(a), lum(b)), reverse=True)
    return (l1 + 0.05) / (l2 + 0.05)


def test_kontras_warna_semua_tema():
    """WCAG: teks utama >= 7:1, teks redup & tombol utama >= 4.5:1, aksen (judul lantai, garis) >= 3:1."""
    from gui import tema

    assert tema.PALET["hitam_kuning"]["aksen"].lower() == "#f9d759"  # kuning logo Mandajaya
    for nama, c in tema.PALET.items():
        assert _kontras(c["teks"], c["latar"]) >= 7, nama
        assert _kontras(c["teks_redup"], c["permukaan"]) >= 4.5, nama
        assert _kontras(c["tombol_utama_teks"], c["tombol_utama"]) >= 4.5, nama
        assert _kontras(c["aksen"], c["permukaan"]) >= 3, nama
        assert _kontras(c["utama_nilai"], c["utama_awal"]) >= 4.5, nama
        assert _kontras(c["sidebar_teks"], c["sidebar"]) >= 4.5, nama


def test_pratinjau_tema_dan_logo(monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    test_pratinjau_tema_dan_logo.app = QApplication.instance() or QApplication([])
    from gui import tema

    for nama in tema.PALET:
        pm = tema.pratinjau_tema(nama)
        assert not pm.isNull() and pm.width() > 0
        assert nama in tema.NAMA_TEMA
    try:
        tema.pilih_tema("hitam_kuning")
        warna = tema.gambar_ikon_aplikasi(64).toImage().pixelColor(4, 32)  # tepi kiri logo
        assert warna.red() > 200 and warna.green() > 170 and warna.blue() < 140  # kuning
    finally:
        tema.pilih_tema(tema.TEMA_BAWAAN)
