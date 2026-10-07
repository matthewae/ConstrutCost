"""KF-19 Recalculate QTO: dimensi elemen diubah pengguna -> kuantitas & biaya dihitung ulang."""

import json
import math
import sqlite3

import pytest

from conftest import AC20
from klasifikasi import ElementType as T
from rules.dimensi import DimensiTidakValid, kolom_dimensi, turunkan, turunkan_dari, validasi

# ---------------------------------------------------------------- rumus turunan


def test_turunan_pelat():
    h = turunkan(T.SLAB, {"panjang": 5.0, "lebar": 4.0, "tebal": 0.12})
    assert h["luas"] == pytest.approx(20.0)
    assert h["volume"] == pytest.approx(2.4)
    assert h["keliling"] == pytest.approx(18.0)


def test_turunan_atap_miring():
    h = turunkan(T.ROOF, {"panjang": 13.0, "lebar": 5.5, "tebal": 0.2, "kemiringan": 30.0})
    assert h["luas"] == pytest.approx(13.0 * 5.5 / math.cos(math.radians(30)))  # 82,56 m²
    assert h["volume"] == pytest.approx(h["luas"] * 0.2)


def test_turunan_dinding_dikurangi_bukaan():
    h = turunkan(T.WALL, {"panjang": 4.0, "tinggi": 3.0, "tebal": 0.15, "luas_bukaan": 2.0})
    assert h["luas"] == pytest.approx(10.0)
    assert h["volume"] == pytest.approx(1.5)


def test_turunan_kolom_balok_tiang_pintu():
    assert turunkan(T.COLUMN, {"lebar": 0.3, "tebal": 0.3, "tinggi": 3.5})["volume"] == pytest.approx(0.315)
    assert turunkan(T.BEAM, {"panjang": 4.0, "lebar": 0.2, "tinggi": 0.3})["volume"] == pytest.approx(0.24)
    assert turunkan(T.PILE, {"panjang": 2.0, "lebar": 1.0})["volume"] == pytest.approx(math.pi / 2)
    assert turunkan(T.DOOR, {"lebar": 0.9, "tinggi": 2.1})["luas"] == pytest.approx(1.89)


def test_turunan_hanya_bila_masukan_lengkap():
    """Pelat tidak reguler dari IFC (tanpa panjang/lebar) tidak dipaksa jadi persegi."""
    assert turunkan(T.SLAB, {"panjang": None, "lebar": None, "tebal": 0.2}) == {}


def test_turunan_tolak_nilai_tidak_masuk_akal():
    with pytest.raises(DimensiTidakValid, match="bukaan"):
        turunkan(T.WALL, {"panjang": 1.0, "tinggi": 1.0, "luas_bukaan": 2.0})
    with pytest.raises(DimensiTidakValid, match="Kemiringan"):
        turunkan(T.ROOF, {"panjang": 5.0, "lebar": 5.0, "kemiringan": 90.0})


def test_turunan_hanya_yang_terpengaruh():
    """Luas Qto dinding (bisa tidak sama dengan L x H - bukaan) dipertahankan bila hanya tebal diubah."""
    d = {"panjang": 9.7, "tinggi": 2.7, "tebal": 0.2, "luas_bukaan": 6.83, "luas": 18.76}
    assert turunkan_dari(T.WALL, d, {"tebal"}) == {"volume": pytest.approx(18.76 * 0.2)}
    h = turunkan_dari(T.WALL, d, {"panjang"})
    assert h["luas"] == pytest.approx(9.7 * 2.7 - 6.83)
    assert h["volume"] == pytest.approx(h["luas"] * 0.2)
    # luas pelat tidak reguler diisi langsung -> volume ikut, keliling tetap
    assert turunkan_dari(T.SLAB, {"tebal": 0.2, "luas": 50.0}, {"luas"}) == {"volume": pytest.approx(10.0)}
    assert turunkan_dari(T.SLAB, {"panjang": 5.0, "lebar": 4.0, "tebal": 0.2}, {"volume"}) == {}
    assert turunkan_dari(T.COLUMN, {"lebar": 0.3, "tebal": 0.4, "tinggi": 3.0}, {"tinggi"}) == {
        "volume": pytest.approx(0.36)
    }


def test_validasi_masukan():
    assert validasi(T.SLAB, {"panjang": "5"}) == {"panjang": 5.0}
    assert validasi(T.WALL, {"luas_bukaan": 0}) == {"luas_bukaan": 0.0}
    with pytest.raises(DimensiTidakValid, match="lebih besar dari nol"):
        validasi(T.SLAB, {"tebal": 0})
    with pytest.raises(DimensiTidakValid, match="lebih besar dari nol"):
        validasi(T.BEAM, {"panjang": -2})
    with pytest.raises(DimensiTidakValid, match="angka"):
        validasi(T.SLAB, {"panjang": "abc"})
    with pytest.raises(DimensiTidakValid, match="tidak berlaku"):
        validasi(T.DOOR, {"tebal": 0.04})
    with pytest.raises(DimensiTidakValid, match="tidak dapat diubah"):
        validasi(T.UNKNOWN, {"panjang": 1})


def test_semua_kelas_berdimensi_punya_volume_atau_luas():
    for kelas in T:
        primer, turunan = kolom_dimensi(kelas)
        if primer:
            assert {"luas", "volume"} & set(turunan), kelas


# ---------------------------------------------------------------- service + database


@pytest.fixture
def proyek_ac20(db_sementara):
    from database.proyek_repository import create_proyek
    from estimasi_service import jalankan_estimasi

    pid = create_proyek("AC20", str(AC20))
    jalankan_estimasi(pid)
    conn = sqlite3.connect(db_sementara)
    conn.row_factory = sqlite3.Row
    yield pid, conn
    conn.close()


def _elemen(conn, nama):
    return conn.execute("SELECT * FROM elemen_proyek WHERE nama = ?", (nama,)).fetchone()


def _hasil(conn, elemen_id):
    return {
        r["kode_ahsp"]: r
        for r in conn.execute(
            "SELECT p.kode_ahsp, h.* FROM hasil_estimasi h JOIN pekerjaan p ON p.id = h.pekerjaan_id "
            "WHERE h.elemen_id = ?",
            (elemen_id,),
        )
    }


def test_ubah_dimensi_pelat_menghitung_ulang_qto(proyek_ac20):
    from estimasi_service import hitung_ulang_elemen

    pid, conn = proyek_ac20
    el = _elemen(conn, "Slab-033")
    lain_sebelum = conn.execute(
        "SELECT id, volume_pekerjaan, subtotal_biaya FROM hasil_estimasi WHERE elemen_id != ? ORDER BY id",
        (el["id"],),
    ).fetchall()
    total_sebelum = conn.execute("SELECT SUM(subtotal_biaya) FROM hasil_estimasi").fetchone()[0]

    r = hitung_ulang_elemen(el["id"], {"panjang": 10.0, "lebar": 8.0, "tebal": 0.15})
    assert r["baris"] == 3
    assert set(r["berubah"]) >= {"panjang", "lebar", "tebal", "luas", "volume"}

    baru = _elemen(conn, "Slab-033")
    assert baru["luas"] == pytest.approx(80.0)
    assert baru["volume"] == pytest.approx(12.0)
    assert baru["keliling"] == pytest.approx(36.0)
    assert baru["dimensi_manual"] == 1
    assert baru["sumber_volume"] == "manual"
    assert json.loads(baru["sumber_dimensi"])["luas"] == "manual"

    h = _hasil(conn, el["id"])
    assert h["BTN.PELAT"]["volume_pekerjaan"] == pytest.approx(12.0)
    # pelat 10 x 8 m t = 15 cm -> tipe bawaan Ø10-150 dua arah 2 lapis, selimut 2 cm
    nx, ny = math.floor(7.96 / 0.15) + 1, math.floor(9.96 / 0.15) + 1
    panjang = (nx * (9.96 + 0.24) + ny * (7.96 + 0.24)) * 2
    besi = h["BSI.PELAT.P"]
    assert besi["volume_pekerjaan"] == pytest.approx(panjang * math.pi * 10**2 / 4 * 7850e-6 * 1.05)
    assert besi["uraian"] == "Tulangan Ø10-150 dua arah, atas & bawah"
    assert besi["diameter"] == 10
    assert h["BSK.PELAT"]["volume_pekerjaan"] == pytest.approx(80.0)
    assert "12" in h["BTN.PELAT"]["rumus"]
    assert all(x["subtotal_biaya"] > 0 for x in h.values())

    # elemen lain tidak tersentuh, total RAB ikut berubah
    lain_sesudah = conn.execute(
        "SELECT id, volume_pekerjaan, subtotal_biaya FROM hasil_estimasi WHERE elemen_id != ? ORDER BY id",
        (el["id"],),
    ).fetchall()
    assert [tuple(x) for x in lain_sesudah] == [tuple(x) for x in lain_sebelum]
    assert conn.execute("SELECT SUM(subtotal_biaya) FROM hasil_estimasi").fetchone()[0] < total_sebelum


def test_elemen_tidak_reguler_volume_diisi_langsung(proyek_ac20):
    """Pelat dasar tanpa panjang/lebar di IFC: pengguna mengoreksi volume saja, luas tetap."""
    from estimasi_service import hitung_ulang_elemen

    _, conn = proyek_ac20
    el = _elemen(conn, "Bodenplatte")
    hitung_ulang_elemen(el["id"], {"volume": 18.0})
    baru = _elemen(conn, "Bodenplatte")
    assert baru["volume"] == pytest.approx(18.0)
    assert baru["luas"] == pytest.approx(el["luas"])
    assert baru["panjang"] is None
    assert _hasil(conn, el["id"])["BTN.PELAT"]["volume_pekerjaan"] == pytest.approx(18.0)


def test_dinding_lantai_dasar_ikut_menghitung_fondasi_turunan(proyek_ac20):
    """Konteks bangunan (lantai dasar, model tanpa fondasi) tetap dipakai saat hitung ulang."""
    from estimasi_service import hitung_ulang_elemen

    _, conn = proyek_ac20
    el = _elemen(conn, "Wand-Int-ERDG-4")
    fdn_lama = _hasil(conn, el["id"])["FDN.BATUKALI"]["volume_pekerjaan"]
    hitung_ulang_elemen(el["id"], {"panjang": el["panjang"] * 2, "tinggi": 2.5, "luas_bukaan": 1.0})
    h = _hasil(conn, el["id"])
    assert h["FDN.BATUKALI"]["volume_pekerjaan"] == pytest.approx(fdn_lama * 2)
    assert h["DND.BATA"]["volume_pekerjaan"] == pytest.approx(4.17 * 2 * 2.5 - 1.0)
    assert h["PLS.DINDING"]["volume_pekerjaan"] == pytest.approx((4.17 * 2 * 2.5 - 1.0) * 2)


def test_ubah_tebal_dinding_mempertahankan_luas_qto(proyek_ac20):
    from estimasi_service import hitung_ulang_elemen

    _, conn = proyek_ac20
    el = _elemen(conn, "Wand-Ext-ERDG-1")  # luas Qto 18,76 m², L x H - bukaan = 19,36 m²
    r = hitung_ulang_elemen(el["id"], {"tebal": 0.2})
    assert set(r["berubah"]) == {"tebal", "volume"}
    baru = _elemen(conn, "Wand-Ext-ERDG-1")
    assert baru["luas"] == pytest.approx(el["luas"])
    assert baru["volume"] == pytest.approx(el["luas"] * 0.2)
    assert _hasil(conn, el["id"])["DND.BATA"]["volume_pekerjaan"] == pytest.approx(el["luas"])


def test_edit_volume_manual_diganti_hasil_hitung_ulang(proyek_ac20):
    from database.estimasi_repository import update_volume_estimasi
    from estimasi_service import hitung_ulang_elemen

    _, conn = proyek_ac20
    el = _elemen(conn, "First")
    h = _hasil(conn, el["id"])["BTN.BALOK"]
    update_volume_estimasi(h["id"], h["pekerjaan_id"], 99.0)
    hitung_ulang_elemen(el["id"], {"panjang": 10.0, "lebar": 0.1, "tinggi": 0.2})
    baru = _hasil(conn, el["id"])["BTN.BALOK"]
    assert baru["volume_pekerjaan"] == pytest.approx(0.2)
    assert baru["diedit_manual"] == 0


def test_dimensi_tidak_valid_tidak_mengubah_apa_pun(proyek_ac20):
    from estimasi_service import hitung_ulang_elemen

    _, conn = proyek_ac20
    el = _elemen(conn, "Wand-Int-ERDG-1")
    sebelum = {k: dict(v) for k, v in _hasil(conn, el["id"]).items()}
    with pytest.raises(DimensiTidakValid):
        hitung_ulang_elemen(el["id"], {"panjang": 1.0, "tinggi": 1.0, "luas_bukaan": 5.0})
    with pytest.raises(DimensiTidakValid):
        hitung_ulang_elemen(el["id"], {"tebal": 0})
    with pytest.raises(DimensiTidakValid, match="tidak ditemukan"):
        hitung_ulang_elemen(99999, {"panjang": 1.0})
    assert {k: dict(v) for k, v in _hasil(conn, el["id"]).items()} == sebelum
    assert _elemen(conn, "Wand-Int-ERDG-1")["dimensi_manual"] == 0


def test_tanda_manual_tampil_di_hasil_dan_hilang_saat_estimasi_ulang(proyek_ac20):
    from database.estimasi_repository import get_hasil_estimasi_by_proyek
    from estimasi_service import hitung_ulang_elemen, jalankan_estimasi

    pid, conn = proyek_ac20
    el = _elemen(conn, "Haustuer")
    hitung_ulang_elemen(el["id"], {"lebar": 1.2, "tinggi": 2.1})
    rows = [r for r in get_hasil_estimasi_by_proyek(pid) if r["elemen_id"] == el["id"]]
    assert rows and all(r["dimensi_manual"] == 1 for r in rows)
    daun = next(r for r in rows if r["kode_ahsp"] == "PTU.DAUN")
    assert daun["volume_pekerjaan"] == pytest.approx(2.52)

    jalankan_estimasi(pid)  # Hitung Ulang dari IFC: kembali ke dimensi model
    assert all(r["dimensi_manual"] == 0 for r in get_hasil_estimasi_by_proyek(pid))
