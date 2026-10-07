"""KF-5: manajemen harga satuan (UC-04)."""

import sqlite3

import pytest

from conftest import AC20


@pytest.fixture
def db_seed(db_sementara):
    from database.seed_data import seed_pekerjaan

    seed_pekerjaan()
    return db_sementara


def _sd(nama_mengandung, tipe="bahan"):
    from database.harga_repository import daftar_sumber_daya

    return next(s for s in daftar_sumber_daya(tipe) if nama_mengandung in s["nama"])


def _harga_pekerjaan(kode):
    from database.harga_repository import daftar_pekerjaan

    return next(p for p in daftar_pekerjaan() if p["kode_ahsp"] == kode)


def test_harga_dasar_dipakai_bersama(db_seed):
    semen = _sd("Semen PC")
    assert semen["jumlah_pekerjaan"] >= 4  # bata, plester, keramik, batu kali
    assert semen["sumber"] == "Placeholder"
    upah = _sd("Pekerja", "upah")
    assert upah["sumber"] == "HSPK Kota Bandung 2027"


def test_ubah_harga_berlaku_di_semua_pekerjaan(db_seed):
    from database.harga_repository import riwayat_harga, ubah_sumber_daya

    semen = _sd("Semen PC")
    bata_lama = _harga_pekerjaan("DND.BATA")["harga_satuan"]
    ubah_sumber_daya(semen["id"], semen["harga"] * 2, merk="Tiga Roda")

    bata_baru = _harga_pekerjaan("DND.BATA")["harga_satuan"]
    koef_semen_bata = 11.5
    assert bata_baru - bata_lama == pytest.approx(koef_semen_bata * semen["harga"] * 1.10)
    baru = _sd("Semen PC")
    assert baru["merk"] == "Tiga Roda" and baru["diubah_manual"] == 1
    r = riwayat_harga(semen["id"])
    assert r[0]["harga_lama"] == semen["harga"] and r[0]["harga_baru"] == semen["harga"] * 2


@pytest.mark.parametrize("harga", [0, -5000, "abc", None])
def test_validasi_harga_positif(db_seed, harga):
    from database.harga_repository import HargaTidakValid, ubah_sumber_daya

    with pytest.raises(HargaTidakValid):
        ubah_sumber_daya(_sd("Semen PC")["id"], harga)


def test_kembalikan_harga_bawaan(db_seed):
    from database.harga_repository import kembalikan_harga_bawaan, ubah_sumber_daya

    semen = _sd("Semen PC")
    ubah_sumber_daya(semen["id"], 2500)
    kembalikan_harga_bawaan(semen["id"])
    assert _sd("Semen PC")["harga"] == semen["harga_bawaan"]
    assert _sd("Semen PC")["diubah_manual"] == 0


def test_tambah_alat_ke_analisa_lalu_hapus(db_seed):
    from database.harga_repository import (
        HargaTidakValid, analisa_pekerjaan, hapus_komponen, hapus_sumber_daya,
        tambah_komponen, tambah_sumber_daya,
    )

    sid = tambah_sumber_daya("alat", "Concrete vibrator", "jam", 50000)
    with pytest.raises(HargaTidakValid, match="sudah ada"):
        tambah_sumber_daya("alat", "concrete vibrator", "JAM", 1)

    beton = _harga_pekerjaan("BTN.KOLOM")
    kid = tambah_komponen(beton["id"], sid, 0.25)
    sesudah = _harga_pekerjaan("BTN.KOLOM")
    assert sesudah["alat"] == pytest.approx(0.25 * 50000)
    assert sesudah["harga_satuan"] - beton["harga_satuan"] == pytest.approx(0.25 * 50000 * 1.10)

    with pytest.raises(HargaTidakValid, match="Masih dipakai"):
        hapus_sumber_daya(sid)
    bawaan = next(k for k in analisa_pekerjaan(beton["id"]) if not k["diubah_manual"])
    with pytest.raises(HargaTidakValid, match="bawaan"):
        hapus_komponen(bawaan["id"])
    hapus_komponen(kid)
    hapus_sumber_daya(sid)
    assert _harga_pekerjaan("BTN.KOLOM")["harga_satuan"] == pytest.approx(beton["harga_satuan"])


def test_seed_ulang_mempertahankan_edit_pengguna(db_seed):
    from database import seed_data
    from database.harga_repository import tambah_komponen, tambah_sumber_daya, ubah_sumber_daya

    semen = _sd("Semen PC")
    ubah_sumber_daya(semen["id"], 1777)
    sid = tambah_sumber_daya("alat", "Molen 0,35 m3", "jam", 40000)
    tambah_komponen(_harga_pekerjaan("BTN.BALOK")["id"], sid, 0.2)

    conn = sqlite3.connect(db_seed)
    conn.execute("UPDATE preferensi_pengguna SET nilai = 'lama' WHERE kunci = 'seed_versi'")
    conn.commit()
    conn.close()
    seed_data.seed_pekerjaan()

    assert _sd("Semen PC")["harga"] == 1777
    assert _harga_pekerjaan("BTN.BALOK")["alat"] == pytest.approx(0.2 * 40000)


def test_terapkan_ke_estimasi_tanpa_mengubah_volume(db_seed):
    from database.estimasi_repository import get_total_rab, update_volume_estimasi
    from database.harga_repository import (
        jumlah_estimasi_kedaluwarsa, terapkan_ke_estimasi, ubah_sumber_daya,
    )
    from database.proyek_repository import create_proyek
    from estimasi_service import jalankan_estimasi

    pid = create_proyek("AC20", str(AC20))
    jalankan_estimasi(pid)
    conn = sqlite3.connect(db_seed)
    hid, pkj = conn.execute(
        "SELECT he.id, he.pekerjaan_id FROM hasil_estimasi he JOIN pekerjaan p ON p.id = he.pekerjaan_id "
        "WHERE p.kode_ahsp = 'DND.BATA' LIMIT 1"
    ).fetchone()
    update_volume_estimasi(hid, pkj, 12.5)  # edit manual
    total_lama = get_total_rab(pid)
    assert jumlah_estimasi_kedaluwarsa() == 0

    ubah_sumber_daya(_sd("Semen PC")["id"], 3000)
    assert jumlah_estimasi_kedaluwarsa() > 0
    assert get_total_rab(pid) == pytest.approx(total_lama)  # belum diterapkan

    assert terapkan_ke_estimasi() > 0
    assert jumlah_estimasi_kedaluwarsa() == 0
    assert get_total_rab(pid) > total_lama
    vol, manual = conn.execute(
        "SELECT volume_pekerjaan, diedit_manual FROM hasil_estimasi WHERE id = ?", (hid,)
    ).fetchone()
    assert vol == 12.5 and manual == 1
