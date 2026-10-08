"""Data harga default: HSPK Kota Bandung 2027 (update setelah rapat 27 Agustus)."""

import pytest

from database.hspk_bandung_2027 import HSD
from database.seed_data import ANALISA, PEMETAAN


def test_data_hspk_lengkap():
    tipe = {t for t, *_ in HSD}
    assert tipe == {"bahan", "upah", "alat"}
    assert len(HSD) > 3000
    assert ("upah", "Pekerja", "OH", 206513.24) in HSD


@pytest.mark.parametrize("kode", sorted(PEMETAAN))
def test_analisa_hspk_sama_dengan_harga_dokumen(kode):
    """sum(koefisien x harga dasar) x 1,10 harus sama dengan harga F di dokumen HSPK."""
    _nama, _kategori, _satuan, kode_hspk = PEMETAAN[kode]
    _sheet, _uraian, harga_f, komponen = ANALISA[kode_hspk]
    assert sum(k[3] * k[4] for k in komponen) * 1.10 == pytest.approx(harga_f, abs=1.0)


def test_harga_satuan_aplikasi_sama_dengan_hspk(db_sementara):
    """Setelah seed (harga dasar digabung per nama), harga satuan setiap pekerjaan = harga F HSPK."""
    from database.harga_repository import daftar_pekerjaan
    from database.seed_data import seed_pekerjaan

    seed_pekerjaan()
    beda = []
    for p in daftar_pekerjaan():
        f = ANALISA[PEMETAAN[p["kode_ahsp"]][3]][2]
        if abs(p["harga_satuan"] - f) > 1.0:
            beda.append((p["kode_ahsp"], round(p["harga_satuan"]), round(f)))
    assert beda == []


def test_seed_membersihkan_data_placeholder_lama(db_sementara):
    import sqlite3

    from database.seed_data import seed_pekerjaan

    conn = sqlite3.connect(db_sementara)
    conn.execute("INSERT INTO sumber_daya (tipe, nama, satuan, harga, harga_bawaan, sumber) "
                 "VALUES ('bahan', 'Semen PC [PLACEHOLDER]', 'kg', 1500, 1500, 'Placeholder')")
    conn.execute("INSERT INTO sumber_daya (tipe, nama, satuan, harga, harga_bawaan, sumber, diubah_manual) "
                 "VALUES ('bahan', 'Cat lama diubah pengguna', 'kg', 9000, 8000, 'Placeholder', 1)")
    conn.commit()
    seed_pekerjaan()
    nama = {r[0] for r in conn.execute("SELECT nama FROM sumber_daya")}
    assert "Semen PC [PLACEHOLDER]" not in nama
    assert "Cat lama diubah pengguna" in nama  # edit pengguna dipertahankan
