"""KF-4 pekerjaan tanah: galian, urugan pasir, lantai kerja, urugan kembali."""

import math

import pytest

from rules import PARAMETER_DEFAULT as P
from rules import Konteks, siapkan_konteks, terapkan_rules
from rules.tanah import kode_galian

KONTEKS_TANPA_FONDASI = Konteks(False, 0.0, "ruang", "ruang")


def _el(kelas, **kw):
    dasar = dict(kelas=kelas, nama=f"{kelas}-1", predefined_type=None, lantai=None, elevasi_lantai=None)
    dasar.update(kw)
    return dasar


def _hasil(elemen, konteks=None):
    hasil, _ = terapkan_rules(elemen, konteks)
    return {h.kode: h for h in hasil}


def test_kode_galian_menurut_kedalaman():
    assert kode_galian(0.85) == "TNH.GALIAN.1"
    assert kode_galian(1.0) == "TNH.GALIAN.1"
    assert kode_galian(1.3) == "TNH.GALIAN.2"
    assert kode_galian(2.25) == "TNH.GALIAN.3"


def test_fondasi_batu_kali_turunan_dinding():
    dinding = _el("WALL", panjang=10.0, luas=28.0, di_lantai_dasar=True)
    h = _hasil(dinding, KONTEKS_TANPA_FONDASI)
    B, H, rk, tp = P.batu_kali_lebar_bawah, P.batu_kali_tinggi, P.ruang_kerja_galian, P.tebal_pasir_fondasi
    galian = (B + 2 * rk) * (H + tp) * 10.0  # 0,9 × 0,85 × 10 = 7,65 m³
    pasir = B * tp * 10.0
    batu_kali = (P.batu_kali_lebar_atas + B) / 2 * H * 10.0
    assert h["TNH.GALIAN.1"].volume == pytest.approx(galian)
    assert h["TNH.PASIR.FONDASI"].volume == pytest.approx(pasir)
    assert h["TNH.URUG.KEMBALI"].volume == pytest.approx(galian - batu_kali - pasir)
    assert "V_galian − V_terisi" in h["TNH.URUG.KEMBALI"].rumus
    # dinding lantai 2 tidak memicu pekerjaan tanah
    assert "TNH.GALIAN.1" not in _hasil({**dinding, "di_lantai_dasar": False}, KONTEKS_TANPA_FONDASI)


def test_footplate_galian_lantai_kerja_urugan():
    fp = _el("FOOTING", predefined_type="PAD_FOOTING", panjang=1.2, lebar=1.2, tebal=0.25, volume=0.36, keliling=4.8)
    h = _hasil(fp)
    dalam = P.kedalaman_fondasi_telapak + P.tebal_lantai_kerja  # 1,05 m -> galian > 1 s.d. 2 m
    galian = (1.2 + 0.2) ** 2 * dalam
    lk = 1.2 * 1.2 * P.tebal_lantai_kerja
    assert h["TNH.GALIAN.2"].volume == pytest.approx(galian)
    assert h["LTK.FONDASI"].volume == pytest.approx(lk)
    assert h["TNH.URUG.KEMBALI"].volume == pytest.approx(galian - 0.36 - lk)


def test_sumuran_turunan_kolom():
    kolom = _el("COLUMN", lebar=0.3, tebal=0.3, tinggi=3.0, volume=0.27, di_lantai_dasar=True)
    h = _hasil(kolom, KONTEKS_TANPA_FONDASI)
    rk = P.ruang_kerja_galian
    tiang = P.sumuran_jumlah_tiang * math.pi * P.sumuran_diameter**2 / 4 * P.sumuran_kedalaman
    lubang = (P.poer_panjang + 2 * rk) * (P.poer_lebar + 2 * rk) * P.poer_tebal
    kode = kode_galian(P.sumuran_kedalaman + P.poer_tebal)
    assert h[kode].volume == pytest.approx(tiang + lubang)
    assert h["TNH.URUG.KEMBALI"].volume == pytest.approx(lubang - P.poer_panjang * P.poer_lebar * P.poer_tebal)


def test_pasir_bawah_sloof():
    sloof = _el("FOOTING", predefined_type="FOOTING_BEAM", lebar=0.15, tebal=0.2, panjang=8.0, volume=0.24)
    h = _hasil(sloof)
    assert h["TNH.PASIR.SLOOF"].volume == pytest.approx(0.15 * P.tebal_pasir_sloof * 8.0)


def test_lantai_dasar_pelat_atau_rabat():
    # pelat di atas tanah: hanya urugan pasir
    h = _hasil(_el("SLAB", predefined_type="BASESLAB", luas=100, volume=12))
    assert h["TNH.PASIR.LANTAI"].volume == pytest.approx(100 * P.tebal_pasir_lantai)
    assert "LTK.LANTAI" not in h

    # tanpa pelat dasar: luas ruang lantai dasar -> pasir + rabat beton
    ruang = _el("SPACE", nama="Ruang Tamu", luas=20.0, keliling=18.0, elevasi_lantai=0.0)
    dinding = _el("WALL", panjang=4, luas=10, elevasi_lantai=0.0)
    ruang_atas = _el("SPACE", nama="Kamar", luas=15.0, keliling=16.0, elevasi_lantai=3.0)
    k = siapkan_konteks([ruang, dinding, ruang_atas])
    assert k.ada_pelat_dasar is False
    h = _hasil(ruang, k)
    assert h["TNH.PASIR.LANTAI"].volume == pytest.approx(20.0 * P.tebal_pasir_lantai)
    assert h["LTK.LANTAI"].volume == pytest.approx(20.0 * P.tebal_lantai_kerja)
    assert "TNH.PASIR.LANTAI" not in _hasil(ruang_atas, k)  # lantai 2 tidak diurug


def test_harga_galian_dan_urugan(db_sementara):
    from database.estimasi_repository import get_harga_satuan_pekerjaan
    from database.estimasi_repository import _connect
    from database.seed_data import seed_pekerjaan

    seed_pekerjaan()
    conn = _connect()
    kode = {r["kode_ahsp"]: r["id"] for r in conn.execute("SELECT id, kode_ahsp FROM pekerjaan")}
    varian = conn.execute("SELECT harga FROM sumber_daya WHERE nama = 'Pekerja (Galian Tanah)'").fetchone()
    conn.close()
    assert get_harga_satuan_pekerjaan(kode["TNH.GALIAN.1"]) == pytest.approx(194855, abs=1)  # HSPK 1.2.1.1.1
    assert varian["harga"] == pytest.approx(219263.24)  # upah pekerja khusus sheet Galian Tanah
    # SNI 2835:2008 6.11: 1,2 m³ pasir urug + 0,3 pekerja + 0,01 mandor, + BUK 10%
    pasir = (1.2 * 287174.25 + 0.3 * 206513.24 + 0.01 * 308530.78) * 1.1
    assert get_harga_satuan_pekerjaan(kode["TNH.PASIR.LANTAI"]) == pytest.approx(pasir, abs=1)
    urug = (0.192 * 206513.24 + 0.019 * 308530.78) * 1.1
    assert get_harga_satuan_pekerjaan(kode["TNH.URUG.KEMBALI"]) == pytest.approx(urug, abs=1)


def test_ac20_punya_bab_pekerjaan_tanah(db_sementara):
    from conftest import AC20
    from database.estimasi_repository import get_hasil_estimasi_by_proyek
    from database.proyek_repository import create_proyek
    from estimasi_service import jalankan_estimasi

    pid = create_proyek("AC20", str(AC20))
    r = jalankan_estimasi(pid)
    assert r["peringatan"] == []
    rows = get_hasil_estimasi_by_proyek(pid)
    tanah = {x["kode_ahsp"] for x in rows if x["kategori"] == "Tanah"}
    assert {"TNH.GALIAN.1", "TNH.PASIR.FONDASI", "TNH.URUG.KEMBALI", "TNH.PASIR.LANTAI"} <= tanah
    pasir_lantai = sum(x["volume_pekerjaan"] for x in rows if x["kode_ahsp"] == "TNH.PASIR.LANTAI")
    assert pasir_lantai == pytest.approx(120.0 * P.tebal_pasir_lantai)  # Bodenplatte 120 m²
