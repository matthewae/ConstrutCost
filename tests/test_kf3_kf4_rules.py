"""KF-3 (rule-based processing) dan KF-4 (perhitungan QTO) dengan elemen buatan."""

import math

import pytest

from rules import PARAMETER_DEFAULT as P
from rules import Konteks, proses_semua, siapkan_konteks, terapkan_rules
from rules.definitions import cari_ruang_basah


def _el(kelas, **kw):
    dasar = dict(kelas=kelas, nama=f"{kelas}-1", predefined_type=None, lantai=None, elevasi_lantai=None)
    dasar.update(kw)
    return dasar


def _hasil(elemen, konteks=None):
    hasil, dilewati = terapkan_rules(elemen, konteks)
    return {h.kode: h for h in hasil}, dilewati


KONTEKS_TANPA_FONDASI = Konteks(False, 0.0, "ruang", "ruang")


def test_kolom_beton_besi_bekisting():
    h, _ = _hasil(_el("COLUMN", lebar=0.3, tebal=0.3, tinggi=3.0, volume=0.27))
    assert h["BTN.KOLOM"].volume == pytest.approx(0.27)
    assert h["BSI.KOLOM"].volume == pytest.approx(0.27 * P.rasio_besi_kolom)
    assert h["BSK.KOLOM"].volume == pytest.approx(2 * (0.3 + 0.3) * 3.0)
    assert "2 × (b + h) × H" in h["BSK.KOLOM"].rumus


def test_balok_bekisting_alas_dan_dua_sisi():
    h, _ = _hasil(_el("BEAM", lebar=0.15, tinggi=0.3, panjang=4.0, volume=0.18))
    assert h["BSK.BALOK"].volume == pytest.approx((0.15 + 2 * 0.3) * 4.0)


def test_dimensi_kosong_dicatat_sebagai_dilewati():
    h, dilewati = _hasil(_el("BEAM", panjang=4.0, volume=0.18))
    assert "BTN.BALOK" in h and "BSK.BALOK" not in h
    assert any("BSK.BALOK" in d and "lebar" in d for d in dilewati)


def test_sumuran_hanya_untuk_kolom_lantai_dasar_tanpa_fondasi_model():
    kolom = _el("COLUMN", lebar=0.3, tebal=0.3, tinggi=3.0, volume=0.27, di_lantai_dasar=True)
    h, _ = _hasil(kolom, KONTEKS_TANPA_FONDASI)
    v_harap = P.sumuran_jumlah_tiang * math.pi * P.sumuran_diameter**2 / 4 * P.sumuran_kedalaman + (
        P.poer_panjang * P.poer_lebar * P.poer_tebal
    )
    assert h["BTN.SUMURAN"].volume == pytest.approx(v_harap)

    h, _ = _hasil(kolom, Konteks(True, 0.0, None, None))  # model sudah punya fondasi
    assert "BTN.SUMURAN" not in h
    h, _ = _hasil({**kolom, "di_lantai_dasar": False}, KONTEKS_TANPA_FONDASI)  # kolom lantai 2
    assert "BTN.SUMURAN" not in h


def test_batu_kali_dinding_rumus_trapesium():
    dinding = _el("WALL", panjang=10.0, luas=28.0, di_lantai_dasar=True)
    h, _ = _hasil(dinding, KONTEKS_TANPA_FONDASI)
    harap = (P.batu_kali_lebar_atas + P.batu_kali_lebar_bawah) / 2 * P.batu_kali_tinggi * 10.0
    assert h["FDN.BATUKALI"].volume == pytest.approx(harap)
    assert h["DND.BATA"].volume == pytest.approx(28.0)
    assert h["PLS.DINDING"].volume == pytest.approx(56.0)
    assert h["ACI.DINDING"].volume == pytest.approx(56.0)
    assert h["CAT.DINDING"].volume == pytest.approx(56.0)


def test_fondasi_menerus_model_jadi_batu_kali_dan_footplate_jadi_beton():
    h, _ = _hasil(_el("FOOTING", predefined_type="STRIP_FOOTING", volume=4.9, panjang=17, lebar=0.9, tebal=0.3))
    assert set(h) == {"FDN.BATUKALI"}
    h, _ = _hasil(_el("FOOTING", predefined_type="PAD_FOOTING", volume=0.36, panjang=1.2, lebar=1.2, tebal=0.25, keliling=4.8))
    assert set(h) == {"BTN.FONDASI", "BSI.FONDASI", "BSK.FONDASI"}
    assert h["BSK.FONDASI"].volume == pytest.approx(4.8 * 0.25)


def test_atap_miring_vs_dak():
    miring = _el("ROOF", luas=82.56, volume=16.5, kemiringan=30.0)
    h, _ = _hasil(miring)
    assert set(h) == {"ATP.RANGKA", "ATP.PENUTUP"}
    assert "cos" in h["ATP.PENUTUP"].rumus

    dak = _el("ROOF", luas=100.0, volume=12.0, kemiringan=0.0)
    h, _ = _hasil(dak)
    assert set(h) == {"BTN.DAK", "BSI.DAK", "BSK.DAK"}


def test_pelat_di_atas_tanah_tanpa_bekisting():
    h, _ = _hasil(_el("SLAB", predefined_type="BASESLAB", luas=100, volume=12))
    assert "BSK.PELAT" not in h
    h, _ = _hasil(_el("SLAB", predefined_type="FLOOR", luas=100, volume=12, di_lantai_dasar=False))
    assert h["BSK.PELAT"].volume == pytest.approx(100)


def test_pintu_dipecah_seperti_hspk_dan_jendela_per_m2():
    h, _ = _hasil(_el("DOOR", lebar=0.9, tinggi=2.1, luas=1.89))
    assert h["PTU.DAUN"].volume == pytest.approx(1.89)
    assert h["PTU.KUSEN"].volume == pytest.approx(2 * 2.1 + 0.9)
    assert h["PTU.KUNCI"].volume == 1.0
    assert h["PTU.ENGSEL"].volume == P.jumlah_engsel_pintu
    h, _ = _hasil(_el("WINDOW", lebar=1.2, tinggi=1.0, luas=1.2))
    assert h["JDL.JENDELA"].volume == pytest.approx(1.2)


@pytest.mark.parametrize(
    "nama, basah",
    [("Kamar Mandi 1", True), ("KM/WC", True), ("Bathroom", True), ("Dapur", True),
     ("Kamar Tidur", False), ("Ruang Keluarga", False), ("KMR Tamu", False)],
)
def test_deteksi_ruang_basah(nama, basah):
    assert (cari_ruang_basah(nama, P) is not None) is basah


def test_keramik_dinding_ruang_basah():
    h, _ = _hasil(_el("SPACE", nama="Kamar Mandi", luas=4.0, keliling=8.0), KONTEKS_TANPA_FONDASI)
    assert h["KRM.DINDING"].volume == pytest.approx(8.0 * 1.5)
    assert h["KRM.LANTAI"].volume == pytest.approx(4.0)
    assert h["PLF.GYPSUM"].volume == pytest.approx(4.0)
    assert h["PLF.RANGKA"].volume == pytest.approx(4.0)


def test_konteks_prioritas_sumber_dan_lantai_dasar():
    elemen = [
        _el("FOOTING", elevasi_lantai=-1.25, predefined_type="STRIP_FOOTING", volume=1.0),
        _el("WALL", elevasi_lantai=0.0, panjang=3, luas=9),
        _el("WALL", elevasi_lantai=3.1, panjang=3, luas=9),
        _el("SLAB", elevasi_lantai=3.1, luas=50, volume=6),
        _el("SPACE", elevasi_lantai=0.0, luas=20, keliling=18),
        _el("CEILING", elevasi_lantai=0.0, luas=20),
    ]
    k = siapkan_konteks(elemen)
    assert k.elevasi_lantai_dasar == 0.0  # level fondasi -1,25 bukan lantai dasar
    assert k.ada_fondasi_model
    assert k.sumber_plafon == "covering"  # plafon dimodelkan -> dipakai
    assert k.sumber_lantai == "ruang"  # penutup lantai tidak dimodelkan -> luas ruang
    assert [e["di_lantai_dasar"] for e in elemen[1:3]] == [True, False]


def test_tidak_ada_hitung_ganda_lantai_dan_plafon():
    elemen = [
        _el("SLAB", elevasi_lantai=0.0, luas=50, volume=6),
        _el("SPACE", elevasi_lantai=0.0, nama="R. Tidur", luas=20, keliling=18),
        _el("SPACE", elevasi_lantai=0.0, nama="R. Tamu", luas=25, keliling=20),
    ]
    _, keluaran, _ = proses_semua(elemen)
    total = {}
    for _e, hasil in keluaran:
        for h in hasil:
            total[h.kode] = total.get(h.kode, 0) + h.volume
    assert total["KRM.LANTAI"] == pytest.approx(45)  # dari ruang saja, pelat tidak ikut
    assert total["PLF.GYPSUM"] == pytest.approx(45)


def test_koefisien_keramik_dan_genteng_dari_rumus_bab2():
    assert P.kebutuhan_per_m2(P.keramik_lantai, P.sisa_keramik_lantai) == pytest.approx(1 / 0.16 * 1.05)
    assert P.kebutuhan_per_m2(P.keramik_dinding, P.sisa_keramik_dinding) == pytest.approx(1 / 0.04 * 1.10)
