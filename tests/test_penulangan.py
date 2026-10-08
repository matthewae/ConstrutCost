"""Penulangan rinci per tipe elemen (Rumus 2.30 - 2.33) dan rekap kebutuhan besi per diameter."""

import math
import sqlite3

import pytest

from conftest import AC20
from rules import terapkan_rules
from rules.penulangan import (
    Penulangan,
    PenulanganTidakValid,
    bawaan,
    berat_per_m,
    hitung,
    kunci_tipe,
    label_tipe,
    validasi,
)


def _el(kelas, **kw):
    dasar = dict(kelas=kelas, nama=f"{kelas}-1", predefined_type=None, lantai=None, elevasi_lantai=None)
    dasar.update(kw)
    return dasar


def test_berat_per_meter_sesuai_tabel_besi():
    # tabel berat besi beton (mis. sheet Perhitungan Besi RAP SMK N 6 Bandung)
    for d, kg in ((6, 0.222), (8, 0.395), (10, 0.617), (13, 1.042), (16, 1.578), (19, 2.226)):
        assert berat_per_m(d) == pytest.approx(kg, abs=0.001)


def test_kolom_tulangan_utama_dan_sengkang():
    kolom = _el("COLUMN", lebar=0.20, tebal=0.25, tinggi=3.5, volume=0.175)
    p = Penulangan("KOLOM", 6, 13, d_sengkang=10, jarak_sengkang=0.15, selimut=0.04)
    utama, sengkang = hitung(kolom, p)

    leff = 3.5 + 2 * 12 * 0.013  # kait 12d tiap ujung
    assert utama.kode == "BSI.KOLOM.U" and utama.diameter == 13
    assert utama.berat == pytest.approx(6 * leff * berat_per_m(13) * 1.05)
    assert utama.uraian == "Tulangan utama 6 D13"

    n = math.floor(3.5 / 0.15) + 1  # 24 sengkang
    panjang = 2 * (0.20 - 0.08) + 2 * (0.25 - 0.08) + 2 * 0.075
    assert sengkang.kode == "BSI.KOLOM.P" and sengkang.diameter == 10
    assert sengkang.berat == pytest.approx(n * panjang * berat_per_m(10) * 1.05)
    assert sengkang.uraian == "Sengkang Ø10-150"
    assert "W_m D13" in utama.rumus and "1,05" in utama.rumus


def test_batang_lebih_dari_12m_diberi_lewatan():
    sloof = _el("FOOTING", predefined_type="FOOTING_BEAM", lebar=0.15, tebal=0.20, panjang=15.0, volume=0.45)
    utama = hitung(sloof)[0]
    leff = 15.0 + 2 * 12 * 0.013 + 1 * 40 * 0.013
    assert utama.berat == pytest.approx(4 * leff * berat_per_m(13) * 1.05)
    assert "40d" in utama.rumus


def test_pelat_persegi_dan_tidak_reguler():
    p = Penulangan("PELAT", d_utama=10, jarak_utama=0.15, lapis=2, selimut=0.02)
    persegi = hitung(_el("SLAB", panjang=4.0, lebar=3.0, tebal=0.12, luas=12.0, volume=1.44), p)[0]
    nx, ny = math.floor(2.96 / 0.15) + 1, math.floor(3.96 / 0.15) + 1
    panjang = (nx * (3.96 + 0.24) + ny * (2.96 + 0.24)) * 2
    assert persegi.berat == pytest.approx(panjang * berat_per_m(10) * 1.05)

    bebas = hitung(_el("SLAB", tebal=0.12, luas=12.0, volume=1.44), p)[0]
    assert bebas.berat == pytest.approx(2 * 12.0 / 0.15 * 2 * berat_per_m(10) * 1.05)
    assert bebas.uraian == "Tulangan Ø10-150 dua arah, atas & bawah"


def test_tipe_bawaan_mengikuti_penampang():
    assert bawaan("KOLOM", 0.12, 0.15).ringkas() == "4 Ø10, sengkang Ø6-150"  # kolom praktis
    assert bawaan("KOLOM", 0.20, 0.25).ringkas() == "6 D13, sengkang Ø10-150"
    assert bawaan("BALOK", 0.15, 0.20).ringkas() == "4 Ø10, sengkang Ø8-150"  # ring balok
    assert bawaan("PELAT", None, 0.12).ringkas() == "Ø10-150 dua arah, 2 lapis (atas & bawah)"
    assert kunci_tipe(_el("COLUMN", lebar=0.2, tebal=0.25, tinggi=3)) == ("KOLOM", 20, 25)
    assert kunci_tipe(_el("ROOF", tebal=0.12, kemiringan=30)) is None  # atap miring: tanpa tulangan
    assert kunci_tipe(_el("BEAM", tinggi=0.3)) is None
    # bukan beton bertulang: lapisan finishing 2 cm, gording 8/16
    assert kunci_tipe(_el("SLAB", tebal=0.02)) is None
    assert kunci_tipe(_el("BEAM", lebar=0.08, tinggi=0.16, panjang=13)) is None
    assert label_tipe("KOLOM", "K1", 0.2, 0.25) == "Kolom K1 (20/25)"
    assert label_tipe("PELAT", "P1", None, 0.12) == "Pelat Lantai P1 (t = 12 cm)"


def test_tanpa_penampang_kembali_ke_rasio():
    hasil, _ = terapkan_rules(_el("COLUMN", tinggi=3.0, volume=0.27))
    besi = next(h for h in hasil if h.kode.startswith("BSI."))
    assert besi.kode == "BSI.KOLOM" and besi.diameter is None
    assert besi.volume == pytest.approx(0.27 * 150)
    assert "asumsi rasio" in besi.rumus


def test_validasi_konfigurasi():
    validasi(Penulangan("KOLOM", 4, 10, d_sengkang=8, jarak_sengkang=0.15, selimut=0.04))
    with pytest.raises(PenulanganTidakValid, match="Jumlah tulangan"):
        validasi(Penulangan("KOLOM", 1, 10, d_sengkang=8, jarak_sengkang=0.15, selimut=0.04))
    with pytest.raises(PenulanganTidakValid, match="Diameter sengkang"):
        validasi(Penulangan("BALOK", 4, 10, d_sengkang=4, jarak_sengkang=0.15, selimut=0.04))
    with pytest.raises(PenulanganTidakValid, match="Jarak tulangan"):
        validasi(Penulangan("PELAT", d_utama=10, jarak_utama=0.6, lapis=2, selimut=0.02))
    with pytest.raises(PenulanganTidakValid, match="lapis"):
        validasi(Penulangan("PELAT", d_utama=10, jarak_utama=0.15, lapis=3, selimut=0.02))


# ---------------------------------------------------------------- database


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


def test_tipe_dibuat_per_penampang(proyek_ac20):
    from database.penulangan_repository import daftar_tipe

    pid, conn = proyek_ac20
    tipe = daftar_tipe(pid)
    label = {t["label"]: t for t in tipe}
    # AC20: balok 20/24 dan pelat t = 20 cm (2 buah); gording kayu 8/16 bukan beton bertulang
    assert set(label) == {"Balok B1 (20/24)", "Pelat Lantai P1 (t = 20 cm)"}
    assert label["Pelat Lantai P1 (t = 20 cm)"]["jumlah_elemen"] == 2
    assert label["Pelat Lantai P1 (t = 20 cm)"]["ringkas"].startswith("D13-150")
    assert all(t["berat_besi"] > 0 for t in tipe)
    # pembesian rinci per diameter kecuali 3 gording (asumsi rasio)
    assert conn.execute(
        "SELECT COUNT(*) FROM hasil_estimasi h JOIN pekerjaan p ON p.id = h.pekerjaan_id "
        "WHERE p.kode_ahsp LIKE 'BSI.%' AND h.diameter IS NULL"
    ).fetchone()[0] == 3


def test_ubah_tipe_menghitung_ulang_pembesian(proyek_ac20):
    from database.penulangan_repository import daftar_tipe, kebutuhan_besi, ubah_tipe
    from estimasi_service import hitung_ulang_penulangan, jalankan_estimasi

    pid, conn = proyek_ac20
    balok = next(t for t in daftar_tipe(pid) if t["kode"] == "B1")
    lain = conn.execute(
        "SELECT SUM(subtotal_biaya) FROM hasil_estimasi h JOIN pekerjaan p ON p.id = h.pekerjaan_id "
        "WHERE p.kode_ahsp NOT LIKE 'BSI.%'"
    ).fetchone()[0]

    ubah_tipe(balok["id"], Penulangan("BALOK", 4, 16, d_sengkang=8, jarak_sengkang=0.10, selimut=0.03))
    r = hitung_ulang_penulangan(pid)
    assert r["baris"] > 0
    rinci = conn.execute(
        "SELECT h.uraian, h.diameter FROM hasil_estimasi h JOIN elemen_proyek e ON e.id = h.elemen_id "
        "WHERE e.tipe_id = ? AND h.diameter IS NOT NULL", (balok["id"],)
    ).fetchall()
    assert {x["uraian"] for x in rinci} == {"Tulangan utama 4 D16", "Sengkang Ø8-100"}
    assert 16 in {k["diameter"] for k in kebutuhan_besi(pid)}
    # pekerjaan selain pembesian tidak berubah
    assert conn.execute(
        "SELECT SUM(subtotal_biaya) FROM hasil_estimasi h JOIN pekerjaan p ON p.id = h.pekerjaan_id "
        "WHERE p.kode_ahsp NOT LIKE 'BSI.%'"
    ).fetchone()[0] == pytest.approx(lain)

    # konfigurasi yang diubah pengguna dipertahankan saat Hitung Ulang dari IFC
    jalankan_estimasi(pid)
    b1 = next(t for t in daftar_tipe(pid) if t["kode"] == "B1")
    assert b1["diubah"] == 1 and b1["ringkas"] == "4 D16, sengkang Ø8-100"


def test_kebutuhan_besi_per_diameter(proyek_ac20):
    from database.penulangan_repository import kebutuhan_besi

    pid, conn = proyek_ac20
    rekap = kebutuhan_besi(pid)
    total = conn.execute("SELECT SUM(volume_pekerjaan) FROM hasil_estimasi WHERE diameter IS NOT NULL").fetchone()[0]
    assert sum(r["berat"] for r in rekap) == pytest.approx(total)
    for r in rekap:
        assert r["panjang"] == pytest.approx(r["berat"] / berat_per_m(r["diameter"]))
        assert r["batang"] == math.ceil(r["panjang"] / 12 - 1e-9)
        assert r["jenis"] == ("Ulir (BjTS)" if r["diameter"] >= 12 else "Polos (BjTP)")


def test_harga_polos_dan_ulir_mengikuti_hspk(proyek_ac20):
    from database.estimasi_repository import get_harga_satuan_pekerjaan

    _, conn = proyek_ac20
    kode = {r["kode_ahsp"]: r["id"] for r in conn.execute("SELECT id, kode_ahsp FROM pekerjaan")}
    assert get_harga_satuan_pekerjaan(kode["BSI.KOLOM.P"]) == pytest.approx(27868, abs=1)  # 2.2.1.1.3
    assert get_harga_satuan_pekerjaan(kode["BSI.KOLOM.U"]) == pytest.approx(44288, abs=1)  # 2.2.1.1.4a
    assert get_harga_satuan_pekerjaan(kode["BSI.PELAT.U"]) == pytest.approx(42171, abs=1)  # 2.2.1.1.2a
