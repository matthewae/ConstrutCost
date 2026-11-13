"""KNF-1 kinerja parsing, KNF-2 kinerja rule engine, KNF-3 konsistensi hasil, KNF-9 integritas database."""

import os
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

import pytest

from conftest import AC20, DUPLEX, STRUKTURAL

AKAR = Path(__file__).resolve().parents[1]

BATAS_PARSING = 30.0  # KNF-1: file IFC rumah tinggal (hingga 50 MB) selesai diparsing <= 30 detik
BATAS_RULE = 15.0  # KNF-2: QTO + RAB < 15 detik setelah parsing selesai


def _baris_hasil(pid):
    from database.estimasi_repository import get_hasil_estimasi_by_proyek

    kunci = ("global_id", "kode_ahsp", "uraian_pekerjaan", "volume", "satuan", "harga_satuan", "jumlah_harga")
    return sorted(tuple(r.get(k) for k in kunci) for r in map(dict, get_hasil_estimasi_by_proyek(pid)))


@pytest.mark.parametrize("path", [AC20, DUPLEX, STRUKTURAL], ids=lambda p: p.name)
def test_knf1_knf2_waktu_parsing_dan_rule_engine(db_sementara, monkeypatch, path):
    import estimasi_service as es
    from database.proyek_repository import create_proyek
    from ifc_reader import buka_dan_validasi, ekstrak_elemen

    t0 = time.perf_counter()
    info = buka_dan_validasi(path, terisolasi=True)
    elemen, peringatan = ekstrak_elemen(info.model)
    parsing = time.perf_counter() - t0
    assert parsing <= BATAS_PARSING, f"KNF-1: parsing {parsing:.1f} s"

    pid = create_proyek(path.stem, str(path))
    monkeypatch.setattr(es, "ekstrak_elemen", lambda m, p=None: (list(elemen), list(peringatan)))
    t1 = time.perf_counter()
    hasil = es.jalankan_estimasi(pid, model=info.model)
    rule = time.perf_counter() - t1
    assert hasil["baris_hasil"] > 0
    assert rule < BATAS_RULE, f"KNF-2: rule engine + RAB {rule:.1f} s"


def test_geometri_paralel_sama_dengan_satu_per_satu(monkeypatch, ekstrak_cache):
    """Percepatan KNF-1 (geometri dihitung paralel) tidak boleh mengubah hasil sedikit pun (KNF-3)."""
    import ifc_reader

    info, paralel, _ = ekstrak_cache(STRUKTURAL)
    monkeypatch.setattr(ifc_reader._Pengukur, "siapkan_geometri", lambda self, kandidat, progress=None: 0)
    satu_per_satu, _ = ifc_reader.ekstrak_elemen(info.model)
    assert satu_per_satu == paralel


def test_knf3_hasil_konsisten_untuk_input_sama(db_sementara):
    from database.estimasi_repository import get_total_rab
    from database.proyek_repository import create_proyek
    from estimasi_service import jalankan_estimasi

    hasil = []
    for i in range(3):  # tiga kali percobaan: dua proyek berbeda + hitung ulang proyek yang sama
        pid = create_proyek(f"Uji {i}", str(DUPLEX)) if i < 2 else hasil[0][0]
        jalankan_estimasi(pid)
        hasil.append((pid, _baris_hasil(pid), get_total_rab(pid)))
    assert hasil[0][1] == hasil[1][1] == hasil[2][1]
    assert hasil[0][2] == hasil[1][2] == hasil[2][2]


def test_knf3_export_konsisten(db_sementara, tmp_path):
    import openpyxl

    from database.proyek_repository import create_proyek
    from estimasi_service import jalankan_estimasi
    from export_service import OpsiExport, ambil_data_export, export_excel

    pid = create_proyek("Konsisten", str(AC20))
    jalankan_estimasi(pid)
    meta = {"nama_proyek": "Konsisten", "lokasi": "Kota Bandung", "pemilik": "Uji", "tahun": 2027}
    isi = []
    for i in range(2):
        path = export_excel(tmp_path / f"rab{i}.xlsx", ambil_data_export(pid), meta, OpsiExport())
        wb = openpyxl.load_workbook(path)
        isi.append({ws.title: [[c.value for c in r] for r in ws.iter_rows()] for ws in wb.worksheets})
    assert isi[0] == isi[1]


_PENULIS = """
import os, sys
sys.path.insert(0, {src!r})
from database.init_db import siapkan_database
from estimasi_service import hitung_ulang_dari_elemen
siapkan_database()
pid = int(sys.argv[1])
print("siap", flush=True)
n = 0
while True:  # hapus & tulis ulang seluruh hasil estimasi terus-menerus sampai dimatikan paksa
    hitung_ulang_dari_elemen(pid)
    n += 1
    print(n, flush=True)
"""


def test_knf9_database_utuh_setelah_aplikasi_dimatikan_paksa(tmp_path):
    """Proses yang sedang menulis hasil estimasi dimatikan paksa (kill -9) berulang kali. Database harus tetap
    utuh (integrity_check = ok) dan hasil estimasi proyek lengkap: tidak pernah setengah terhapus.
    Berlaku juga di Windows (Task Manager → End task / listrik padam)."""
    env = dict(os.environ, COSTSTRUCT_DATA=str(tmp_path), PYTHONPATH=str(AKAR / "src"))
    siapkan = (
        f"import sys; sys.path.insert(0, {str(AKAR / 'src')!r})\n"
        "from database.init_db import siapkan_database\n"
        "from database.proyek_repository import create_proyek\n"
        "from estimasi_service import jalankan_estimasi\n"
        "siapkan_database()\n"
        f"pid = create_proyek('Uji KNF-9', {str(DUPLEX)!r}); print(pid, jalankan_estimasi(pid)['baris_hasil'])\n"
    )
    keluaran = subprocess.run([sys.executable, "-c", siapkan], env=env, capture_output=True, text=True, check=True)
    pid, jumlah = map(int, keluaran.stdout.split()[-2:])
    skrip = tmp_path / "penulis.py"
    skrip.write_text(_PENULIS.format(src=str(AKAR / "src")))
    db = tmp_path / "coststruct.db"

    for jeda in (0.35, 0.8, 1.3, 1.9, 2.6):
        p = subprocess.Popen([sys.executable, str(skrip), str(pid)], env=env, stdout=subprocess.PIPE, text=True)
        assert p.stdout.readline().strip() == "siap"
        time.sleep(jeda)
        p.kill()  # SIGKILL di Linux/macOS, TerminateProcess di Windows: proses berhenti seketika
        p.wait()
        conn = sqlite3.connect(db)
        try:
            assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
            n = conn.execute("SELECT COUNT(*) FROM hasil_estimasi WHERE proyek_id = ?", (pid,)).fetchone()[0]
            assert n == jumlah, f"hasil estimasi tidak lengkap setelah kill pada {jeda} s: {n} dari {jumlah}"
            assert conn.execute("SELECT COUNT(*) FROM sumber_daya").fetchone()[0] > 0
        finally:
            conn.close()


def test_knf9_database_rusak_dikenali(db_sementara):
    from database.init_db import periksa_integritas
    from gui.galat import pesan_galat

    periksa_integritas()  # database baru: utuh
    data = bytearray(db_sementara.read_bytes())
    halaman = 4096
    for i in range(halaman * 2, min(len(data), halaman * 6)):
        data[i] = 0xAB  # timpa beberapa halaman tabel dengan sampah
    db_sementara.write_bytes(bytes(data))
    with pytest.raises(sqlite3.DatabaseError) as e:
        periksa_integritas()
    pesan, saran = pesan_galat(e.value)
    assert "rusak" in pesan and "cadangan" in saran
