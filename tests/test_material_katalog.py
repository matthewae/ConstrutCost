"""Pilihan material per pekerjaan (combo box + bawaan) dan katalog HSPK lengkap."""

import pytest

from database.hspk_bandung_2027 import AHSP, BAB, SATUAN
from database.material import SLOT, kode_dasar, kode_varian, pilihan_lengkap, varian_terpilih
from database.seed_data import PEMETAAN


def _sama_satuan(a: str, b: str) -> bool:
    return a.replace("’", "'").lower() == b.replace("’", "'").lower()


@pytest.mark.parametrize("slot", list(SLOT))
def test_semua_pilihan_ada_di_hspk_dengan_satuan_sama(slot):
    s = SLOT[slot]
    satuan = PEMETAAN[slot][2]
    assert len({o.kunci for o in s.opsi}) == len(s.opsi)
    assert s.bawaan in {o.kunci for o in s.opsi}
    for o in s.opsi:
        assert o.kode_hspk in AHSP, o
        assert _sama_satuan(SATUAN[o.kode_hspk], satuan), (o, SATUAN[o.kode_hspk], satuan)
        assert PEMETAAN[kode_varian(slot, o.kunci)][3] == o.kode_hspk


def test_bawaan_dinding_bata_ringan_60x20x10():
    assert PEMETAAN["DND.BATA"][3] == "3.6.4.2"
    assert "60x20x10" in PEMETAAN["DND.BATA"][0]
    assert PEMETAAN["DND.BATA~merah"][3] == "3.6.1.8"
    assert kode_dasar("DND.BATA~merah") == "DND.BATA" and kode_dasar("BTN.KOLOM") == "BTN.KOLOM"
    assert pilihan_lengkap({"DND.BATA": "tidak-ada"})["DND.BATA"] == "ringan10"
    assert varian_terpilih({"DND.BATA": "merah", "BTN.KOLOM": "m20"}) == {"DND.BATA": "DND.BATA~merah"}


def test_katalog_hspk_lengkap_bab_1_sampai_10():
    assert len(AHSP) > 2700
    assert set(BAB) == {str(i) for i in range(1, 11)}
    assert {k.split(".")[0] for k in AHSP} == set(BAB)
    # contoh item di luar lingkup rule engine yang kini tersedia di katalog
    assert SATUAN["3.18.3.1"] == "buah"  # kloset duduk
    assert "3.8.23.1" in AHSP  # cat berbasis air (sheet PENGECATAN (BARU))
    assert any(k.startswith("5.1.") for k in AHSP)  # instalasi listrik
    assert not any(k.split(".")[0].split("@")[0].isdigit() and int(k.split(".")[0]) > 10 for k in AHSP)


def _proyek_ac20():
    from conftest import AC20
    from database.proyek_repository import create_proyek
    from estimasi_service import jalankan_estimasi

    pid = create_proyek("AC20", str(AC20))
    jalankan_estimasi(pid)
    return pid


def _baris(pid, awalan):
    from database.estimasi_repository import get_hasil_estimasi_by_proyek

    return [r for r in get_hasil_estimasi_by_proyek(pid) if kode_dasar(r["kode_ahsp"]) == awalan]


def test_ganti_pilihan_mengganti_pekerjaan_tanpa_mengubah_volume(db_sementara):
    from database.estimasi_repository import _connect, get_harga_satuan_pekerjaan
    from database.material_repository import muat_pilihan, simpan_pilihan
    from estimasi_service import hitung_ulang_dari_elemen

    pid = _proyek_ac20()
    dinding = _baris(pid, "DND.BATA")
    assert dinding and all(r["kode_ahsp"] == "DND.BATA" for r in dinding)  # bawaan: bata ringan
    luas = sum(r["volume_pekerjaan"] for r in dinding)
    # volume satu baris diedit manual (KF-6): harus tetap setelah material diganti
    conn = _connect()
    conn.execute("UPDATE hasil_estimasi SET volume_pekerjaan = 7.5, diedit_manual = 1 WHERE id = ?",
                 (dinding[0]["hasil_id"],))
    conn.commit()
    conn.close()

    hasil = simpan_pilihan(pid, {"DND.BATA": "merah", "BTN.PELAT": "rm25"})
    assert set(hasil["berubah"]) == {"DND.BATA", "BTN.PELAT"}
    assert muat_pilihan(pid)["DND.BATA"] == "merah"
    baru = _baris(pid, "DND.BATA")
    assert {r["kode_ahsp"] for r in baru} == {"DND.BATA~merah"}
    assert baru[0]["nama_pekerjaan"].startswith("Pasangan Dinding Bata Merah")
    harga = get_harga_satuan_pekerjaan(baru[0]["pekerjaan_id"])
    assert harga == pytest.approx(426435, abs=1)  # HSPK 3.6.1.8
    ubah = next(r for r in baru if r["hasil_id"] == dinding[0]["hasil_id"])
    assert ubah["volume_pekerjaan"] == 7.5 and ubah["subtotal_biaya"] == pytest.approx(7.5 * harga)
    kolom = _baris(pid, "BTN.PELAT")
    assert kolom and {r["kode_ahsp"] for r in kolom} == {"BTN.PELAT~rm25"}
    assert "Ready Mix" in kolom[0]["nama_pekerjaan"]

    # hitung ulang dari elemen tetap memakai pilihan proyek
    hitung_ulang_dari_elemen(pid)
    assert {r["kode_ahsp"] for r in _baris(pid, "DND.BATA")} == {"DND.BATA~merah"}
    assert sum(r["volume_pekerjaan"] for r in _baris(pid, "DND.BATA")) == pytest.approx(luas)

    # kembali ke bawaan: kode polos dan pilihan tidak disimpan
    simpan_pilihan(pid, {})
    assert {r["kode_ahsp"] for r in _baris(pid, "DND.BATA")} == {"DND.BATA"}
    conn = _connect()
    assert conn.execute("SELECT material FROM proyek WHERE id = ?", (pid,)).fetchone()[0] is None
    conn.close()


def test_pilihan_ikut_file_proyek_dan_duplikat(db_sementara, tmp_path):
    from database.berkas_proyek import buka_berkas, duplikat_proyek, simpan_berkas
    from database.material_repository import muat_pilihan, simpan_pilihan

    pid = _proyek_ac20()
    simpan_pilihan(pid, {"KRM.LANTAI": "gr60", "ATP.PENUTUP": "metal"})
    salinan = duplikat_proyek(pid, "AC20 salinan")
    assert muat_pilihan(salinan)["KRM.LANTAI"] == "gr60"
    assert {r["kode_ahsp"] for r in _baris(salinan, "KRM.LANTAI")} == {"KRM.LANTAI~gr60"}
    path = simpan_berkas(pid, tmp_path / "ac20.coststruct", sertakan_ifc=False)
    dibuka = buka_berkas(path)
    assert muat_pilihan(dibuka)["ATP.PENUTUP"] == "metal"


def test_pilihan_tidak_dikenal_ditolak(db_sementara):
    from database.material_repository import simpan_pilihan
    from database.proyek_repository import create_proyek

    pid = create_proyek("Kosong", None)
    with pytest.raises(ValueError):
        simpan_pilihan(pid, {"BUKAN.SLOT": "x"})
