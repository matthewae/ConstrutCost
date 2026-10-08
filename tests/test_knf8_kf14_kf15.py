"""KNF-8 lokasi data & uji mandiri .exe, KF-15 logging aktivitas, KF-14 pesan galat & terjemahan Qt."""

import errno
import logging
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from conftest import AC20

AKAR = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def qapp():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


@pytest.fixture
def log_file(tmp_path):
    """File log harian di folder sementara; handler dilepas setelah tes."""
    from logging.handlers import TimedRotatingFileHandler

    from aktivitas import log, siapkan_log

    path = Path(siapkan_log(tmp_path / "log"))
    yield path
    for h in list(log.handlers):
        if isinstance(h, TimedRotatingFileHandler):
            log.removeHandler(h)
            h.close()


# ---------------------------------------------------------------- KNF-8 lokasi data


def test_lokasi_dari_kode_sumber_di_folder_data_repo(monkeypatch):
    import lokasi

    monkeypatch.delenv("COSTSTRUCT_DATA", raising=False)
    monkeypatch.delattr(sys, "frozen", raising=False)
    assert lokasi.folder_data() == AKAR / "data"
    assert lokasi.path_database() == AKAR / "data" / "coststruct.db"


def test_lokasi_exe_windows_di_appdata(monkeypatch, tmp_path):
    import lokasi

    monkeypatch.delenv("COSTSTRUCT_DATA", raising=False)
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setenv("APPDATA", str(tmp_path / "Roaming"))
    assert lokasi.dibundel()
    assert lokasi.folder_data() == tmp_path / "Roaming" / "CostStruct"
    assert lokasi.folder_log() == tmp_path / "Roaming" / "CostStruct" / "log"
    assert lokasi.folder_cadangan() == tmp_path / "Roaming" / "CostStruct" / "cadangan"


def test_lokasi_exe_linux_dan_override(monkeypatch, tmp_path):
    import lokasi

    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "share"))
    monkeypatch.delenv("COSTSTRUCT_DATA", raising=False)
    assert lokasi.folder_data() == tmp_path / "share" / "CostStruct"
    monkeypatch.setenv("COSTSTRUCT_DATA", str(tmp_path / "flashdisk"))
    assert lokasi.folder_data() == tmp_path / "flashdisk"


def test_cadangan_database_harian(db_sementara, tmp_path):
    from database.init_db import cadangkan_database

    folder = tmp_path / "cadangan"
    for i in range(9):  # cadangan lama: hanya 7 terbaru yang disimpan
        (folder / f"coststruct-2020010{i}.db").parent.mkdir(exist_ok=True)
        (folder / f"coststruct-2020010{i}.db").write_bytes(b"")
    hasil = cadangkan_database(folder=folder)
    assert hasil is not None and hasil.is_file()
    assert cadangkan_database(folder=folder) is None  # cukup sekali per hari
    assert len(list(folder.glob("coststruct-*.db"))) == 7
    with sqlite3.connect(hasil) as c:  # salinan konsisten & bisa dibuka
        assert c.execute("SELECT COUNT(*) FROM pekerjaan").fetchone() is not None


def test_spec_pyinstaller_membawa_berkas_wajib():
    spec = (AKAR / "CostStruct.spec").read_text(encoding="utf-8")
    assert "schema.sql" in spec and "src" in spec
    assert "ifcopenshell.express.rules" in spec  # atribut turunan IFC (gagal tanpa ini saat dibundel)
    assert "express/express_parser.py" in spec
    assert "console=False" in spec
    assert (AKAR / "assets" / "coststruct.ico").is_file()


def test_uji_mandiri_semua_tahap_berhasil(tmp_path):
    """Sama dengan `CostStruct.exe --uji-mandiri` yang dijalankan tools/build_exe.py setelah build."""
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen")
    env.pop("COSTSTRUCT_DATA", None)
    r = subprocess.run(
        [sys.executable, str(AKAR / "src" / "main.py"), "--uji-mandiri", "--keluar", str(tmp_path)],
        env=env, capture_output=True, text=True, timeout=300,
    )
    laporan = (tmp_path / "uji_mandiri.txt").read_text(encoding="utf-8")
    assert r.returncode == 0, laporan
    assert laporan.count("[OK]") == 5 and "SEMUA TAHAP BERHASIL" in laporan
    assert (tmp_path / "uji_mandiri.xlsx").stat().st_size > 0
    assert (tmp_path / "uji_mandiri.pdf").read_bytes().startswith(b"%PDF")
    assert "coststruct_uji_" in laporan  # database pengguna tidak tersentuh: folder data sementara


# ---------------------------------------------------------------- KF-15 logging aktivitas


def test_catat_ke_database_dan_file(db_sementara, log_file):
    from aktivitas import catat, daftar_aktivitas

    catat("harga", "Semen Portland: harga diubah", detail="rincian")
    catat("galat", "Gagal export", tingkat="GALAT")
    for h in logging.getLogger("coststruct").handlers:
        h.flush()
    teks = log_file.read_text(encoding="utf-8")
    assert "coststruct.harga | Semen Portland: harga diubah" in teks and "rincian" in teks
    assert "ERROR" in teks and "Gagal export" in teks
    rows = daftar_aktivitas()
    assert [r["jenis"] for r in rows] == ["galat", "harga"]  # terbaru dulu
    assert rows[0]["tingkat"] == "GALAT" and rows[1]["detail"] == "rincian"


def test_catat_tidak_pernah_menggagalkan_aktivitas(monkeypatch, log_file):
    import database.estimasi_repository as er
    from aktivitas import catat

    def rusak():
        raise sqlite3.OperationalError("database is locked")

    monkeypatch.setattr(er, "_connect", rusak)
    catat("export", "tetap jalan")  # tidak melempar
    catat("export", "tingkat aneh", tingkat="???")
    for h in logging.getLogger("coststruct").handlers:
        h.flush()
    teks = log_file.read_text(encoding="utf-8")
    assert "tetap jalan" in teks and "Aktivitas tidak tersimpan di database" in teks


def test_aktivitas_penting_tercatat_sepanjang_alur(db_sementara, tmp_path):
    from aktivitas import daftar_aktivitas
    from database.berkas_proyek import simpan_berkas
    from database.estimasi_repository import get_hasil_estimasi_by_proyek, ubah_catatan, ubah_harga_baris
    from database.harga_repository import daftar_sumber_daya, ubah_sumber_daya
    from database.proyek_repository import create_proyek, delete_proyek
    from database.seed_data import seed_pekerjaan
    from estimasi_service import jalankan_estimasi
    from export_service import OpsiExport, ambil_data_export, export_excel

    seed_pekerjaan()
    pid = create_proyek("Rumah Uji Log", str(AC20))
    jalankan_estimasi(pid)
    baris = get_hasil_estimasi_by_proyek(pid)[0]
    ubah_harga_baris([baris["hasil_id"]], 123456)
    ubah_catatan(baris["hasil_id"], "cek gambar kerja")
    sd = daftar_sumber_daya()[0]
    ubah_sumber_daya(sd["id"], sd["harga"] + 1000)
    export_excel(tmp_path / "rab.xlsx", ambil_data_export(pid), {}, OpsiExport())
    simpan_berkas(pid, tmp_path / "rumah.coststruct")

    jenis = {r["jenis"] for r in daftar_aktivitas()}
    assert {"proyek", "estimasi", "edit", "harga", "export", "berkas"} <= jenis
    milik = daftar_aktivitas(proyek_id=pid)
    assert all(r["nama_proyek"] == "Rumah Uji Log" for r in milik)
    assert any("123.456" in r["pesan"] for r in milik if r["jenis"] == "edit")
    assert [r["jenis"] for r in daftar_aktivitas(kata="rab.xlsx")] == ["export"]
    assert all(r["jenis"] == "harga" for r in daftar_aktivitas(jenis="harga"))

    delete_proyek(pid)  # riwayat tetap ada walau proyeknya dihapus
    assert daftar_aktivitas(proyek_id=pid)[0]["nama_proyek"] is None


def test_pangkas_log_lama(db_sementara):
    from aktivitas import daftar_aktivitas, pangkas
    from database.estimasi_repository import _connect

    conn = _connect()
    conn.execute("INSERT INTO log_aktivitas (waktu, tingkat, jenis, pesan) VALUES ('2001-01-01 00:00:00','INFO','aplikasi','lama')")
    conn.execute("INSERT INTO log_aktivitas (waktu, tingkat, jenis, pesan) VALUES ('2999-01-01 00:00:00','INFO','aplikasi','baru')")
    conn.commit()
    conn.close()
    assert pangkas(365) == 1
    assert [r["pesan"] for r in daftar_aktivitas()] == ["baru"]


def test_halaman_riwayat_aktivitas(db_sementara, qapp):
    from aktivitas import catat
    from gui.aktivitas_page import AktivitasPage

    catat("import", "File diterima: rumah.ifc")
    catat("galat", "Export PDF: Akses ditolak", detail="Traceback ...\nPermissionError", tingkat="GALAT")
    catat("export", "Export Excel: rab.xlsx", tingkat="PERINGATAN")
    hal = AktivitasPage()
    hal.muat()
    assert hal.tabel.rowCount() == 3
    hal.combo_tingkat.setCurrentIndex(hal.combo_tingkat.findData("GALAT"))
    assert hal.tabel.rowCount() == 1
    hal.tabel.selectRow(0)
    assert "PermissionError" in hal.rincian.toPlainText()
    hal.combo_tingkat.setCurrentIndex(0)
    hal.combo_jenis.setCurrentIndex(hal.combo_jenis.findData("import"))
    assert hal.tabel.rowCount() == 1 and "rumah.ifc" in hal.tabel.item(0, 4).text()
    hal.combo_jenis.setCurrentIndex(0)
    hal.kolom_cari.setText("xlsx")
    hal.muat()
    assert hal.tabel.rowCount() == 1 and hal.label_jumlah.text() == "1 aktivitas"


# ---------------------------------------------------------------- KF-14 pesan galat & notifikasi


@pytest.mark.parametrize(
    "galat, kata_pesan, kata_saran",
    [
        (PermissionError(13, "Permission denied", "C:/RAB.xlsx"), "Akses ke file atau folder ditolak", "Excel"),
        (FileNotFoundError(2, "No such file", "rumah.ifc"), "tidak ditemukan", "dipindahkan"),
        (OSError(errno.ENOSPC, "No space left on device"), "Ruang penyimpanan penuh", "Kosongkan"),
        (sqlite3.OperationalError("database is locked"), "Database sedang dipakai", "CostStruct lain"),
        (sqlite3.DatabaseError("database disk image is malformed"), "Database aplikasi rusak", "cadangan"),
        (MemoryError(), "Memori komputer tidak cukup", "lebih kecil"),
        (KeyError("x"), "kesalahan tak terduga (KeyError)", "file log"),
    ],
)
def test_pesan_galat_bahasa_indonesia_dengan_saran(galat, kata_pesan, kata_saran):
    from gui.galat import pesan_galat

    pesan, saran = pesan_galat(galat)
    assert kata_pesan.lower() in pesan.lower()
    assert kata_saran.lower() in saran.lower()


def test_pesan_galat_validasi_aplikasi_apa_adanya():
    from database.berkas_proyek import BerkasTidakValid
    from database.estimasi_repository import NilaiTidakValid
    from gui.galat import pesan_galat
    from ifc_reader import PESAN_TIDAK_VALID, FileIFCTidakValid

    assert pesan_galat(FileIFCTidakValid(PESAN_TIDAK_VALID)) == (PESAN_TIDAK_VALID, "")
    assert pesan_galat(BerkasTidakValid("Bukan file proyek CostStruct.")) == ("Bukan file proyek CostStruct.", "")
    assert pesan_galat(NilaiTidakValid("Volume harus angka.")) == ("Volume harus angka.", "")


def test_tampilkan_galat_mencatat_traceback(db_sementara, qapp, monkeypatch):
    from PySide6.QtWidgets import QMessageBox

    from aktivitas import daftar_aktivitas
    from gui.galat import tampilkan_galat

    tampil = []
    monkeypatch.setattr(QMessageBox, "exec", lambda self: tampil.append((self.text(), self.informativeText(), self.detailedText())))
    try:
        open("/folder/yang/tidak/ada/rab.xlsx", "rb")
    except OSError as e:
        tampilkan_galat(None, "Export Gagal", e, "Export Excel", proyek_id=None)
    pesan, saran, rincian = tampil[0]
    assert "tidak ditemukan" in pesan and "pilih ulang" in saran and "Traceback" in rincian
    r = daftar_aktivitas(jenis="galat")[0]
    assert r["tingkat"] == "GALAT" and r["pesan"].startswith("Export Excel:") and "FileNotFoundError" in r["detail"]


def test_penangkap_galat_tak_terduga_tidak_menutup_aplikasi(db_sementara, qapp, monkeypatch):
    from PySide6.QtWidgets import QMessageBox

    import gui.galat as galat
    from aktivitas import daftar_aktivitas

    tampil = []
    monkeypatch.setattr(QMessageBox, "exec", lambda self: tampil.append(self.informativeText()))
    monkeypatch.setattr(sys, "excepthook", sys.excepthook)
    galat.pasang_penangkap_galat()
    assert sys.excepthook is galat._penangkap
    try:
        {}["tidak_ada"]
    except KeyError:
        sys.excepthook(*sys.exc_info())
    assert "Aplikasi tetap berjalan" in tampil[0]
    r = daftar_aktivitas(jenis="galat")[0]
    assert "KeyError" in r["pesan"] and "Traceback" in r["detail"]


def test_terjemahan_tombol_bawaan_qt(qapp):
    from PySide6.QtWidgets import QDialogButtonBox, QMessageBox

    from gui.galat import pasang_terjemahan

    pasang_terjemahan(qapp)
    kotak = QMessageBox(QMessageBox.Question, "Hapus", "Hapus proyek?", QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel)
    teks = {kotak.button(b).text().replace("&", "") for b in (QMessageBox.Yes, QMessageBox.No, QMessageBox.Cancel)}
    assert teks == {"Ya", "Tidak", "Batal"}
    bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel | QDialogButtonBox.Close)
    assert bb.button(QDialogButtonBox.Close).text().replace("&", "") == "Tutup"
    assert bb.button(QDialogButtonBox.Cancel).text().replace("&", "") == "Batal"


def test_penangkap_galat_dari_thread_lain_hanya_dicatat(db_sementara, qapp, monkeypatch):
    """Dialog Qt tidak boleh dibuat di luar thread utama (bisa membuat aplikasi crash)."""
    import threading

    from PySide6.QtWidgets import QMessageBox

    import gui.galat as galat
    from aktivitas import daftar_aktivitas

    tampil = []
    monkeypatch.setattr(QMessageBox, "exec", lambda self: tampil.append(self.text()))
    monkeypatch.setattr(sys, "__excepthook__", lambda *a: None)

    def kerja():
        try:
            raise RuntimeError("galat di thread latar")
        except RuntimeError:
            galat._penangkap(*sys.exc_info())

    th = threading.Thread(target=kerja)
    th.start()
    th.join()
    assert tampil == []
    assert "galat di thread latar" in daftar_aktivitas(jenis="galat")[0]["pesan"]
