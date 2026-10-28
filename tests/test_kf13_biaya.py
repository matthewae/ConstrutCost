"""KF-13 Ringkasan biaya: biaya langsung, biaya tidak langsung, PPN, pembulatan, terbilang."""

import pytest

from terbilang import terbilang


def test_terbilang():
    assert terbilang(0) == "Nol"
    assert terbilang(11) == "Sebelas"
    assert terbilang(115) == "Seratus lima belas"
    assert terbilang(1_000) == "Seribu"
    assert terbilang(21_500) == "Dua puluh satu ribu lima ratus"
    assert terbilang(1_000_000) == "Satu juta"
    # rekap RAP SMK N 6 Bandung
    assert terbilang(4_383_998_000) == (
        "Empat miliar tiga ratus delapan puluh tiga juta sembilan ratus sembilan puluh delapan ribu"
    )


def test_hitung_ringkasan():
    from database.biaya_repository import hitung_ringkasan

    r = hitung_ringkasan(100_000_000, [
        {"uraian": "Perencanaan", "jenis": "persen", "nilai": 4.0},
        {"uraian": "PBG", "jenis": "nilai", "nilai": 2_500_000},
    ])
    assert [i["jumlah"] for i in r["item_tidak_langsung"]] == [4_000_000, 2_500_000]
    assert r["tidak_langsung"] == 6_500_000
    assert r["jumlah"] == 106_500_000
    assert r["ppn"] == pytest.approx(11_715_000)
    assert r["total"] == pytest.approx(118_215_000)
    assert r["dibulatkan"] == 118_215_000
    assert r["buk"] == pytest.approx(100_000_000 * 0.10 / 1.10)
    assert r["terbilang"].endswith("rupiah")
    assert hitung_ringkasan(1_234_567.89, [])["dibulatkan"] == 1_370_000  # 1.370.370,36 -> ke bawah


def test_crud_dan_validasi(db_sementara):
    from database.biaya_repository import (
        BiayaTidakValid,
        daftar_biaya,
        hapus_biaya,
        ringkasan_biaya,
        tambah_biaya,
        ubah_biaya,
    )
    from database.proyek_repository import create_proyek, delete_proyek, get_proyek

    pid = create_proyek("Uji")
    bid = tambah_biaya(pid, "  Biaya   pengawasan ", "persen", 2.5)
    tambah_biaya(pid, "PBG", "nilai", 1_500_000)
    assert [b["uraian"] for b in daftar_biaya(pid)] == ["Biaya pengawasan", "PBG"]
    ubah_biaya(bid, "Biaya pengawasan", "persen", 3)
    assert daftar_biaya(pid)[0]["nilai"] == 3

    for args, pesan in (
        (("", "persen", 1), "kosong"),
        (("X", "persen", 0), "lebih besar dari nol"),
        (("X", "persen", 150), "100%"),
        (("X", "rupiah", 5), "Jenis"),
        (("X", "nilai", "abc"), "angka"),
    ):
        with pytest.raises(BiayaTidakValid, match=pesan):
            tambah_biaya(pid, *args)

    # proyek tanpa hasil estimasi: biaya langsung 0, persen = 0
    r = ringkasan_biaya(pid)
    assert r["langsung"] == 0 and r["tidak_langsung"] == 1_500_000
    assert get_proyek(pid)["total_rab"] == 0  # belum dihitung

    hapus_biaya(bid)
    assert len(daftar_biaya(pid)) == 1
    delete_proyek(pid)
    assert daftar_biaya(pid) == []


def test_total_proyek_termasuk_biaya_tidak_langsung(db_sementara):
    from conftest import AC20
    from database.biaya_repository import ringkasan_biaya, tambah_biaya
    from database.estimasi_repository import get_total_rab
    from database.proyek_repository import create_proyek, get_proyek
    from estimasi_service import jalankan_estimasi

    pid = create_proyek("AC20", str(AC20))
    jalankan_estimasi(pid)
    langsung = get_total_rab(pid)
    tambah_biaya(pid, "Perencanaan", "persen", 5)
    r = ringkasan_biaya(pid)
    assert r["tidak_langsung"] == pytest.approx(langsung * 0.05)
    assert get_proyek(pid)["total_rab"] == pytest.approx(langsung * 1.05 * 1.11)
