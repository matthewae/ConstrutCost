"""Integrasi KF-1..KF-4: file IFC -> database (elemen_proyek + hasil_estimasi)."""

import json
import sqlite3

import pytest

from conftest import AC20, DUPLEX


def test_pipeline_ac20(db_sementara):
    from database.proyek_repository import create_proyek
    from estimasi_service import jalankan_estimasi

    pid = create_proyek("AC20", str(AC20))
    progres = []
    r = jalankan_estimasi(pid, progress=lambda i, n, t: progres.append((i, n)))
    assert r["elemen"] == 44
    assert r["baris_hasil"] > 0
    assert r["peringatan"] == []
    assert progres[-1] == (44, 44)

    conn = sqlite3.connect(db_sementara)
    kelas = dict(conn.execute("SELECT kelas, COUNT(*) FROM elemen_proyek GROUP BY kelas"))
    assert kelas["WALL"] == 13 and kelas["ROOF"] == 2
    sumber = json.loads(conn.execute("SELECT sumber_dimensi FROM elemen_proyek WHERE kelas='WALL'").fetchone()[0])
    assert sumber["luas"] == "qto"
    kode = {r[0] for r in conn.execute(
        "SELECT p.kode_ahsp FROM hasil_estimasi h JOIN pekerjaan p ON p.id = h.pekerjaan_id")}
    assert {"FDN.BATUKALI", "ATP.PENUTUP", "ATP.RANGKA", "KRM.LANTAI", "PLF.GYPSUM", "PLF.RANGKA",
            "PTU.DAUN", "PTU.KUSEN", "ACI.DINDING"} <= kode
    assert conn.execute("SELECT COUNT(*) FROM hasil_estimasi WHERE rumus IS NULL OR rumus = ''").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM hasil_estimasi WHERE subtotal_biaya <= 0").fetchone()[0] == 0


def test_estimasi_ulang_menimpa_bukan_menggandakan(db_sementara):
    from database.proyek_repository import create_proyek
    from estimasi_service import jalankan_estimasi

    pid = create_proyek("Duplex", str(DUPLEX))
    r1 = jalankan_estimasi(pid)
    r2 = jalankan_estimasi(pid)
    conn = sqlite3.connect(db_sementara)
    assert conn.execute("SELECT COUNT(*) FROM hasil_estimasi").fetchone()[0] == r2["baris_hasil"] == r1["baris_hasil"]


def test_migrasi_database_lama(tmp_path, monkeypatch):
    """Database dengan skema versi awal dilengkapi kolom baru tanpa kehilangan data."""
    import database.estimasi_repository as er
    import database.init_db as idb

    path = tmp_path / "lama.db"
    conn = sqlite3.connect(path)
    conn.executescript("""
        CREATE TABLE proyek (id INTEGER PRIMARY KEY AUTOINCREMENT, nama_proyek TEXT NOT NULL,
            path_file_ifc TEXT, tanggal_dibuat TEXT DEFAULT CURRENT_TIMESTAMP,
            tanggal_diubah TEXT DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE elemen_proyek (id INTEGER PRIMARY KEY AUTOINCREMENT, proyek_id INTEGER NOT NULL,
            global_id TEXT NOT NULL, ifc_type TEXT NOT NULL, predefined_type TEXT, nama TEXT, lantai TEXT,
            panjang REAL, luas REAL, volume REAL, sumber_volume TEXT);
        INSERT INTO proyek (nama_proyek) VALUES ('Proyek lama');
    """)
    conn.close()
    monkeypatch.setattr(er, "DB_PATH", path)
    monkeypatch.setattr(idb, "DB_PATH", path)
    idb.init_db()
    idb.init_db()  # idempotent

    conn = sqlite3.connect(path)
    kolom = {r[1] for r in conn.execute("PRAGMA table_info(elemen_proyek)")}
    assert {"kelas", "lebar", "tinggi", "tebal", "kemiringan", "sumber_dimensi"} <= kolom
    assert {r[1] for r in conn.execute("PRAGMA table_info(hasil_estimasi)")} >= {"rumus"}
    assert conn.execute("SELECT nama_proyek FROM proyek").fetchone()[0] == "Proyek lama"


def test_proyek_dengan_file_hilang(db_sementara, tmp_path):
    from database.proyek_repository import create_proyek
    from estimasi_service import jalankan_estimasi
    from ifc_reader import FileIFCTidakValid

    pid = create_proyek("Hilang", str(tmp_path / "sudah_dihapus.ifc"))
    with pytest.raises(FileIFCTidakValid):
        jalankan_estimasi(pid)
