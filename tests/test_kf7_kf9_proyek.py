"""KF-7 simpan & buka proyek (file .coststruct, parameter aturan per proyek) dan KF-9 multi-proyek."""

import json
import sqlite3
import zipfile

import pytest

from conftest import AC20


@pytest.fixture
def proyek(db_sementara):
    from database.proyek_repository import create_proyek
    from estimasi_service import jalankan_estimasi

    pid = create_proyek("AC20", str(AC20))
    jalankan_estimasi(pid)
    conn = sqlite3.connect(db_sementara)
    conn.row_factory = sqlite3.Row
    yield pid, conn
    conn.close()


def _total(conn, pid):
    return conn.execute("SELECT SUM(subtotal_biaya) FROM hasil_estimasi WHERE proyek_id = ?", (pid,)).fetchone()[0]


def _volume(conn, pid, kode):
    return conn.execute(
        "SELECT SUM(h.volume_pekerjaan) FROM hasil_estimasi h JOIN pekerjaan p ON p.id = h.pekerjaan_id "
        "WHERE h.proyek_id = ? AND p.kode_ahsp = ?", (pid, kode),
    ).fetchone()[0]


# ---------------------------------------------------------------- parameter aturan


def test_parameter_per_proyek_dan_validasi(proyek):
    from database.parameter_repository import (
        ParameterTidakValid,
        muat_parameter,
        perubahan_parameter,
        simpan_parameter,
    )
    from rules import PARAMETER_DEFAULT

    pid, _ = proyek
    assert muat_parameter(pid) == PARAMETER_DEFAULT
    simpan_parameter(pid, {"batu_kali_tinggi": 1.0, "sumuran_jumlah_tiang": 2, "rasio_besi_kolom": 150})
    assert perubahan_parameter(pid) == {"batu_kali_tinggi": 1.0, "sumuran_jumlah_tiang": 2}  # 150 = bawaan
    assert isinstance(muat_parameter(pid).sumuran_jumlah_tiang, int)
    with pytest.raises(ParameterTidakValid, match="Tinggi"):
        simpan_parameter(pid, {"batu_kali_tinggi": 5})
    with pytest.raises(ParameterTidakValid, match="tidak dikenal"):
        simpan_parameter(pid, {"apa_saja": 1})
    with pytest.raises(ParameterTidakValid, match="Lebar atas"):
        simpan_parameter(pid, {"batu_kali_lebar_atas": 0.8, "batu_kali_lebar_bawah": 0.6})


def test_hitung_ulang_dari_elemen_memakai_parameter_proyek(proyek):
    from database.estimasi_repository import ubah_catatan, ubah_harga_baris, update_volume_estimasi
    from database.parameter_repository import simpan_parameter
    from estimasi_service import hitung_ulang_dari_elemen, hitung_ulang_elemen, jalankan_estimasi

    pid, conn = proyek
    fdn = _volume(conn, pid, "FDN.BATUKALI")
    bata = conn.execute(
        "SELECT h.* FROM hasil_estimasi h JOIN pekerjaan p ON p.id = h.pekerjaan_id WHERE p.kode_ahsp = 'DND.BATA' "
        "ORDER BY h.id"
    ).fetchall()
    ubah_harga_baris([bata[0]["id"]], 400_000)
    ubah_catatan(bata[0]["id"], "harga nego")
    update_volume_estimasi(bata[1]["id"], bata[1]["pekerjaan_id"], 99.0)
    slab = conn.execute("SELECT id FROM elemen_proyek WHERE nama = 'Slab-033'").fetchone()["id"]
    hitung_ulang_elemen(slab, {"panjang": 10.0, "lebar": 8.0, "tebal": 0.15})

    simpan_parameter(pid, {"batu_kali_tinggi": 1.0})  # 0,8 -> 1,0 m
    r = hitung_ulang_dari_elemen(pid)
    assert r["manual_diganti"] == 1
    assert _volume(conn, pid, "FDN.BATUKALI") == pytest.approx(fdn * 1.0 / 0.8)
    b0 = conn.execute(
        "SELECT * FROM hasil_estimasi WHERE elemen_id = ? AND pekerjaan_id = ?", (bata[0]["elemen_id"], bata[0]["pekerjaan_id"])
    ).fetchone()
    assert b0["harga_manual"] == 400_000 and b0["catatan"] == "harga nego"
    assert b0["subtotal_biaya"] == pytest.approx(b0["volume_pekerjaan"] * 400_000)
    b1 = conn.execute(
        "SELECT * FROM hasil_estimasi WHERE elemen_id = ? AND pekerjaan_id = ?", (bata[1]["elemen_id"], bata[1]["pekerjaan_id"])
    ).fetchone()
    assert b1["volume_pekerjaan"] != 99.0 and b1["diedit_manual"] == 0
    # dimensi yang diubah pengguna (KF-19) tetap dipakai
    assert conn.execute("SELECT luas FROM elemen_proyek WHERE id = ?", (slab,)).fetchone()[0] == pytest.approx(80.0)
    # estimasi ulang dari IFC juga memakai parameter proyek
    jalankan_estimasi(pid)
    assert _volume(conn, pid, "FDN.BATUKALI") == pytest.approx(fdn * 1.0 / 0.8)


def test_undo_parameter(proyek):
    from database.parameter_repository import muat_parameter, simpan_parameter
    from database.riwayat_repository import potret_proyek, pulihkan_proyek

    pid, _ = proyek
    awal = potret_proyek(pid)
    simpan_parameter(pid, {"tebal_pasir_lantai": 0.1})
    pulihkan_proyek(pid, awal)
    assert muat_parameter(pid).tebal_pasir_lantai == 0.05


# ---------------------------------------------------------------- file proyek


def test_simpan_dan_buka_file_proyek(proyek, tmp_path):
    from database.berkas_proyek import buka_berkas, simpan_berkas
    from database.biaya_repository import ringkasan_biaya, tambah_biaya
    from database.parameter_repository import muat_parameter, simpan_parameter
    from database.penulangan_repository import daftar_tipe
    from database.proyek_repository import get_proyek, ubah_info_proyek
    from estimasi_service import hitung_ulang_dari_elemen

    pid, conn = proyek
    ubah_info_proyek(pid, "Rumah AC20", "Kota Bandung", "Bpk. Uji", 2027, str(AC20))
    simpan_parameter(pid, {"ruang_kerja_galian": 0.2})
    hitung_ulang_dari_elemen(pid)
    tambah_biaya(pid, "Perencanaan", "persen", 3)

    path = simpan_berkas(pid, tmp_path / "rumah")
    assert path.suffix == ".coststruct"
    with zipfile.ZipFile(path) as z:
        assert set(z.namelist()) == {"proyek.json", "model.ifc"}
        data = json.loads(z.read("proyek.json"))
    assert "DND.BATA" in data["harga"] and data["harga"]["DND.BATA"]["komponen"]

    folder = tmp_path / "komputer_lain"
    baru = buka_berkas(path, folder_ifc=folder)
    assert baru != pid
    p = get_proyek(baru)
    assert (p["nama_proyek"], p["lokasi"], p["pemilik"], p["tahun_anggaran"]) == ("Rumah AC20", "Kota Bandung", "Bpk. Uji", 2027)
    assert p["path_file_ifc"] == str(folder / "AC20-FZK-Haus.ifc")
    assert (folder / "AC20-FZK-Haus.ifc").stat().st_size == AC20.stat().st_size
    assert muat_parameter(baru).ruang_kerja_galian == 0.2
    assert _total(conn, baru) == pytest.approx(_total(conn, pid))
    assert ringkasan_biaya(baru)["dibulatkan"] == ringkasan_biaya(pid)["dibulatkan"]
    assert [t["ringkas"] for t in daftar_tipe(baru)] == [t["ringkas"] for t in daftar_tipe(pid)]
    # id elemen di proyek baru terhubung benar
    yatim = conn.execute(
        "SELECT COUNT(*) FROM hasil_estimasi h LEFT JOIN elemen_proyek e ON e.id = h.elemen_id "
        "WHERE h.proyek_id = ? AND (e.proyek_id IS NULL OR e.proyek_id != ?)", (baru, baru),
    ).fetchone()[0]
    assert yatim == 0
    # dibuka lagi: nama file IFC tidak menimpa salinan yang sudah ada
    buka_berkas(path, folder_ifc=folder)
    assert (folder / "AC20-FZK-Haus (1).ifc").exists()


def test_file_proyek_tidak_valid(db_sementara, tmp_path):
    from database.berkas_proyek import BerkasTidakValid, buka_berkas, impor_data

    bukan_zip = tmp_path / "x.coststruct"
    bukan_zip.write_text("halo")
    with pytest.raises(BerkasTidakValid, match="bukan file proyek"):
        buka_berkas(bukan_zip)
    with pytest.raises(BerkasTidakValid, match="tidak ditemukan"):
        buka_berkas(tmp_path / "tidak_ada.coststruct")
    with pytest.raises(BerkasTidakValid, match="lebih baru"):
        impor_data({"format": "coststruct-proyek", "versi": 99})
    with pytest.raises(BerkasTidakValid, match="tidak dikenal"):
        impor_data({"format": "coststruct-proyek", "versi": 1, "proyek": {"nama_proyek": "X"},
                    "hasil": [{"kode_pekerjaan": "ZZZ.TIDAK.ADA", "volume_pekerjaan": 1, "subtotal_biaya": 1}]})
    conn = sqlite3.connect(db_sementara)
    assert conn.execute("SELECT COUNT(*) FROM proyek").fetchone()[0] == 0  # transaksi dibatalkan


# ---------------------------------------------------------------- KF-9


def test_duplikat_proyek_terpisah(proyek):
    from database.berkas_proyek import duplikat_proyek
    from database.estimasi_repository import update_volume_estimasi

    pid, conn = proyek
    salinan = duplikat_proyek(pid, "AC20 (alternatif genteng metal)")
    assert _total(conn, salinan) == pytest.approx(_total(conn, pid))
    b = conn.execute("SELECT * FROM hasil_estimasi WHERE proyek_id = ? LIMIT 1", (salinan,)).fetchone()
    update_volume_estimasi(b["id"], b["pekerjaan_id"], b["volume_pekerjaan"] + 100)
    assert _total(conn, salinan) != pytest.approx(_total(conn, pid))  # proyek asli tidak berubah


def test_ubah_info_proyek_validasi(proyek, tmp_path):
    from database.proyek_repository import ProyekTidakValid, get_all_proyek, ubah_info_proyek

    pid, _ = proyek
    for args, pesan in (
        (("",), "kosong"),
        (("A" * 121,), "120"),
        (("X", "", "", 1990), "Tahun"),
        (("X", "", "", 2027, str(tmp_path / "a.txt")), "ekstensi"),
        (("X", "", "", 2027, str(tmp_path / "hilang.ifc")), "tidak ditemukan"),
    ):
        with pytest.raises(ProyekTidakValid, match=pesan):
            ubah_info_proyek(pid, *args)
    ubah_info_proyek(pid, "  Rumah   Tinggal  ", " Bandung ", "", None, str(AC20))
    p = get_all_proyek()[0]
    assert p["nama_proyek"] == "Rumah Tinggal" and p["lokasi"] == "Bandung" and p["pemilik"] is None
