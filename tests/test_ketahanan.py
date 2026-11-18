"""Perbaikan dari tinjauan menyeluruh: harga khusus & catatan tidak hilang saat hitung ulang, panel RAB
Rinci hanya baris yang dipilih, file proyek aman, dan file sementara dibersihkan."""

import json
import sqlite3
import zipfile
from dataclasses import replace

import pytest

from conftest import AC20


@pytest.fixture
def proyek(db_sementara):
    from database.proyek_repository import create_proyek
    from estimasi_service import jalankan_estimasi

    pid = create_proyek("AC20", str(AC20))
    jalankan_estimasi(pid)
    return pid


def _khusus(db, pid):
    conn = sqlite3.connect(db)
    try:
        return conn.execute(
            "SELECT COUNT(*), SUM(h.harga_manual IS NOT NULL), SUM(h.catatan IS NOT NULL) FROM hasil_estimasi h "
            "JOIN pekerjaan p ON p.id = h.pekerjaan_id WHERE h.proyek_id = ? AND p.kode_ahsp LIKE 'BSI.%'",
            (pid,),
        ).fetchone()
    finally:
        conn.close()


def test_harga_khusus_dan_catatan_tetap_setelah_hitung_ulang_penulangan(db_sementara, proyek):
    from database.estimasi_repository import get_hasil_estimasi_by_proyek, ubah_catatan, ubah_harga_baris
    from database.penulangan_repository import daftar_tipe, ubah_tipe
    from estimasi_service import hitung_ulang_penulangan
    from rules.penulangan import Penulangan

    bsi = [r for r in get_hasil_estimasi_by_proyek(proyek) if (r["kode_ahsp"] or "").startswith("BSI.")]
    ubah_harga_baris([r["hasil_id"] for r in bsi], 15000)
    ubah_catatan(bsi[0]["hasil_id"], "harga negosiasi supplier")
    n, harga, catatan = _khusus(db_sementara, proyek)
    assert harga == n and catatan == 1

    hitung_ulang_penulangan(proyek)
    assert _khusus(db_sementara, proyek)[1:] == (n, 1)

    # konfigurasi tulangan diubah -> uraian berubah (6 D13 -> 4 D16), harga khusus tetap ikut elemen & pekerjaan
    tipe = next(t for t in daftar_tipe(proyek) if t["kelompok"] == "BALOK")
    p = Penulangan(kelompok="BALOK", n_utama=4, d_utama=16, d_sengkang=8, jarak_sengkang=0.15, selimut=0.04)
    ubah_tipe(tipe["id"], p)
    hitung_ulang_penulangan(proyek)
    baru = [r for r in get_hasil_estimasi_by_proyek(proyek) if (r["kode_ahsp"] or "").startswith("BSI.")]
    assert all(r["harga_manual"] == 15000 for r in baru)
    assert all(r["subtotal_biaya"] == pytest.approx(r["volume_pekerjaan"] * 15000) for r in baru)


def test_harga_khusus_tetap_setelah_ubah_dimensi(db_sementara, proyek):
    from database.estimasi_repository import get_hasil_estimasi_by_proyek, ubah_catatan, ubah_harga_baris
    from estimasi_service import hitung_ulang_elemen

    r = next(r for r in get_hasil_estimasi_by_proyek(proyek) if r["kode_ahsp"] == "BTN.PELAT")
    ubah_harga_baris([r["hasil_id"]], 2_000_000)
    ubah_catatan(r["hasil_id"], "beton ready mix")
    hitung_ulang_elemen(r["elemen_id"], {"tebal": 0.25})
    baru = next(x for x in get_hasil_estimasi_by_proyek(proyek)
                if x["elemen_id"] == r["elemen_id"] and x["kode_ahsp"] == "BTN.PELAT")
    assert baru["harga_manual"] == 2_000_000 and baru["catatan"] == "beton ready mix"
    assert baru["volume_pekerjaan"] != pytest.approx(r["volume_pekerjaan"])  # volume memang dihitung ulang


def test_saring_rab_rinci_hanya_baris_item(proyek):
    """Panel rincian & 'Pakai Harga Ini' di RAB Rinci memakai baris item yang dipilih saja."""
    from database.estimasi_repository import get_hasil_estimasi_by_proyek
    from rab_rinci import cocok_saring, susun_rinci

    baris = [dict(r) for r in get_hasil_estimasi_by_proyek(proyek)]
    for per_tipe in (False, True):
        for k in susun_rinci(baris, per_tipe_elemen=per_tipe):
            for g in k["grup"]:
                for it in g["items"]:
                    cocok = [r for r in baris if r["pekerjaan_id"] == it["pekerjaan_id"] and cocok_saring(r, it["saring"])]
                    assert sum(r["volume_pekerjaan"] for r in cocok) == pytest.approx(it["volume"]), it["label"]


def test_buka_file_proyek_nama_ifc_tidak_keluar_folder(db_sementara, proyek, tmp_path):
    from database.berkas_proyek import buka_berkas, simpan_berkas

    path = simpan_berkas(proyek, tmp_path / "asli.coststruct")
    jahat = tmp_path / "jahat.coststruct"
    with zipfile.ZipFile(path) as z, zipfile.ZipFile(jahat, "w") as out:
        data = json.loads(z.read("proyek.json"))
        data["ifc_disertakan"] = "../../luar/evil.ifc"
        out.writestr("proyek.json", json.dumps(data))
        out.writestr("model.ifc", z.read("model.ifc"))
    folder = tmp_path / "buka"
    buka_berkas(jahat, folder_ifc=folder)
    assert (folder / "evil.ifc").is_file() and not (tmp_path.parent / "luar").exists()


def test_simpan_file_proyek_gagal_tidak_meninggalkan_tmp(db_sementara, proyek, tmp_path, monkeypatch):
    from pathlib import Path

    from database.berkas_proyek import simpan_berkas

    def replace(self, target):
        raise PermissionError(13, "file tujuan sedang dikunci", str(target))

    monkeypatch.setattr(Path, "replace", replace)
    with pytest.raises(PermissionError):
        simpan_berkas(proyek, tmp_path / "x.coststruct")
    assert not list(tmp_path.glob("*.tmp"))


def test_folder_dokumen_dari_sistem():
    from database.preferensi_repository import folder_default
    from pathlib import Path

    assert Path(folder_default()).is_dir()


def test_preferensi_tetap_bisa_dibandingkan():
    from database.preferensi_repository import Preferensi

    assert replace(Preferensi(), tema="gelap") != Preferensi()
