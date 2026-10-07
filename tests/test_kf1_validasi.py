"""KF-1: import & validasi file IFC (UC-01 skenario normal dan alternatif)."""

import pytest

from ifc_reader import PESAN_TIDAK_VALID, FileIFCTidakValid, buka_dan_validasi
from klasifikasi import ElementType as T

from conftest import AC20, DUPLEX


def test_file_valid_menghasilkan_ringkasan():
    info = buka_dan_validasi(AC20)
    assert info.skema == "IFC4"
    assert info.nama_file == "AC20-FZK-Haus.ifc"
    assert info.satuan_panjang == "meter"
    assert [nama for nama, _ in info.lantai] == ["Erdgeschoss", "Dachgeschoss"]
    assert info.jumlah_per_kelas[T.WALL] == 13
    assert info.jumlah_per_kelas[T.ROOF] == 2
    assert info.total_elemen == 44
    assert info.model is not None


def test_ifc2x3_didukung():
    info = buka_dan_validasi(DUPLEX)
    assert info.skema == "IFC2x3"
    assert info.jumlah_per_kelas[T.FOOTING] == 7


def test_ekstensi_bukan_ifc(tmp_path):
    f = tmp_path / "gambar.dwg"
    f.write_bytes(b"ISO-10303-21;")
    with pytest.raises(FileIFCTidakValid, match="bukan .ifc"):
        buka_dan_validasi(f)


def test_file_tidak_ada(tmp_path):
    with pytest.raises(FileIFCTidakValid, match="tidak ditemukan"):
        buka_dan_validasi(tmp_path / "tidak_ada.ifc")


def test_file_kosong(tmp_path):
    f = tmp_path / "kosong.ifc"
    f.write_bytes(b"")
    with pytest.raises(FileIFCTidakValid, match="kosong"):
        buka_dan_validasi(f)


def test_header_bukan_step(tmp_path):
    f = tmp_path / "palsu.ifc"
    f.write_text("ini bukan file IFC")
    with pytest.raises(FileIFCTidakValid) as e:
        buka_dan_validasi(f)
    assert PESAN_TIDAK_VALID in str(e.value)


def test_skema_lain_ditolak(tmp_path):
    import ifcopenshell

    f = ifcopenshell.file(schema="IFC4X3_ADD2")
    f.createIfcProject(ifcopenshell.guid.new(), Name="Uji")
    path = tmp_path / "ifc4x3.ifc"
    f.write(str(path))
    with pytest.raises(FileIFCTidakValid, match="belum didukung"):
        buka_dan_validasi(path)


def test_tanpa_ifcproject_ditolak(tmp_path):
    import ifcopenshell

    f = ifcopenshell.file(schema="IFC4")
    f.createIfcWall(ifcopenshell.guid.new())
    path = tmp_path / "tanpa_proyek.ifc"
    f.write(str(path))
    with pytest.raises(FileIFCTidakValid, match="IfcProject"):
        buka_dan_validasi(path)


def test_file_terpotong_tanpa_penutup(tmp_path):
    isi = AC20.read_bytes()
    f = tmp_path / "terpotong.ifc"
    f.write_bytes(isi[: int(len(isi) * 0.99)])
    with pytest.raises(FileIFCTidakValid, match="terpotong"):
        buka_dan_validasi(f)


def test_crash_pembaca_ifc_tidak_menghentikan_aplikasi(tmp_path):
    """KNF-4: potongan file ini membuat IfcOpenShell segfault walau penutupnya ada.
    Dengan validasi terisolasi, yang berhenti hanya proses anak."""
    isi = AC20.read_bytes()
    f = tmp_path / "korup.ifc"
    f.write_bytes(isi[: len(isi) // 3] + b"\nENDSEC;\nEND-ISO-10303-21;\n")
    with pytest.raises(FileIFCTidakValid, match="berhenti tidak normal"):
        buka_dan_validasi(f, terisolasi=True)


def test_validasi_terisolasi_file_valid():
    info = buka_dan_validasi(AC20, terisolasi=True)
    assert info.total_elemen == 44 and info.model is not None
