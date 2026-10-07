"""KF-2: parser, klasifikasi, dan ekstraksi dimensi G = {L, B, H, t, A, V}."""

import math

import pytest

from conftest import AC20, DUPLEX, STRUKTURAL


def _per_kelas(elemen, kelas):
    return [e for e in elemen if e["kelas"] == kelas]


def test_klasifikasi_tanpa_duplikat(ekstrak_cache):
    for path in (AC20, DUPLEX, STRUKTURAL):
        info, elemen, _ = ekstrak_cache(path)
        ids = [e["global_id"] for e in elemen]
        assert len(ids) == len(set(ids))
        assert len(elemen) == info.total_elemen


def test_dimensi_dinding_dari_qto_archicad(ekstrak_cache):
    _, elemen, peringatan = ekstrak_cache(AC20)
    assert peringatan == []
    dinding = next(e for e in elemen if e["kelas"] == "WALL" and e["panjang"] == pytest.approx(4.17))
    assert dinding["tinggi"] == pytest.approx(2.5)
    assert dinding["tebal"] == pytest.approx(0.24)
    assert dinding["luas"] == pytest.approx(10.425, abs=1e-3)
    assert dinding["sumber_dimensi"]["luas"] == "qto"


def test_luas_bukaan_dinding_sama_dengan_luas_pintu_jendela(ekstrak_cache):
    _, elemen, _ = ekstrak_cache(AC20)
    bukaan = sum(e["luas_bukaan"] or 0 for e in _per_kelas(elemen, "WALL"))
    pintu_jendela = sum(e["luas"] for e in elemen if e["kelas"] in ("DOOR", "WINDOW"))
    assert bukaan == pytest.approx(pintu_jendela, rel=1e-3)


def test_atap_miring_luas_sebenarnya_dan_kemiringan(ekstrak_cache):
    _, elemen, _ = ekstrak_cache(AC20)
    for atap in _per_kelas(elemen, "ROOF"):
        assert atap["kemiringan"] == pytest.approx(30.0, abs=0.1)
        assert atap["luas"] == pytest.approx(82.56, abs=0.01)  # bukan proyeksi 71,50 m2
        assert atap["luas"] * math.cos(math.radians(atap["kemiringan"])) == pytest.approx(71.5, abs=0.05)


def test_lantai_dan_elevasi(ekstrak_cache):
    _, elemen, _ = ekstrak_cache(DUPLEX)
    pondasi = _per_kelas(elemen, "FOOTING")
    assert {e["lantai"] for e in pondasi} == {"T/FDN"}
    assert pondasi[0]["elevasi_lantai"] == pytest.approx(-1.25)
    # pintu/jendela ikut terbaca lantainya
    assert all(e["lantai"] for e in elemen if e["kelas"] in ("DOOR", "WINDOW"))


def test_konversi_satuan_milimeter(ekstrak_cache):
    info, elemen, _ = ekstrak_cache(STRUKTURAL)
    assert info.satuan_panjang == "milimeter"
    dinding = _per_kelas(elemen, "WALL")[0]
    assert dinding["panjang"] == pytest.approx(9.628, abs=1e-3)  # Qto 9628 mm
    assert dinding["luas"] == pytest.approx(45.25, abs=0.01)  # satuan luas file = m2


def test_keliling_qto_tidak_wajar_diganti_geometri(ekstrak_cache):
    # Revit 2025 menulis Perimeter dalam feet pada file milimeter -> 0,081 m untuk pelat 38 m2
    _, elemen, _ = ekstrak_cache(STRUKTURAL)
    for pelat in _per_kelas(elemen, "SLAB"):
        # batas bawah keliling = lingkaran; 0,9 memberi ruang untuk tesselasi pelat bundar
        assert pelat["keliling"] >= 0.9 * math.sqrt(4 * math.pi * pelat["luas"])


def test_dinding_sumbu_y_tanpa_qto(ifc_sintetis):
    """Regresi: luas sisi dinding harus dihitung di koordinat lokal, bukan global."""
    from ifc_reader import buka_dan_validasi, ekstrak_elemen

    elemen, peringatan = ekstrak_elemen(buka_dan_validasi(ifc_sintetis).model)
    assert peringatan == []
    dinding = next(e for e in elemen if e["kelas"] == "WALL")
    assert dinding["sumber_dimensi"]["luas"] == "geometri"
    assert dinding["panjang"] == pytest.approx(5.0)
    assert dinding["tinggi"] == pytest.approx(3.0)
    assert dinding["tebal"] == pytest.approx(0.2)
    assert dinding["luas"] == pytest.approx(15.0)
    assert dinding["volume"] == pytest.approx(3.0)
    assert dinding["lantai"] == "Lantai 1"


def test_atap_miring_tanpa_qto(ifc_sintetis):
    from ifc_reader import buka_dan_validasi, ekstrak_elemen

    elemen, _ = ekstrak_elemen(buka_dan_validasi(ifc_sintetis).model)
    atap = next(e for e in elemen if e["kelas"] == "ROOF")
    assert atap["kemiringan"] == pytest.approx(30.0, abs=0.1)
    assert atap["luas"] == pytest.approx(24.0, rel=1e-3)  # 6 x 4 m bidang miring
    assert atap["volume"] == pytest.approx(2.4, rel=1e-3)
