"""
KF-14 Notifikasi & error handling (juga KNF-4 dan KNF-6).

1. `pesan_galat()` mengubah exception menjadi pesan berbahasa Indonesia beserta saran solusi
   (UC-05 skenario alternatif: "menampilkan pesan error deskriptif dan menyarankan solusi").
2. `tampilkan_galat()` menampilkan pesan itu, mencatatnya ke log aktivitas (KF-15), dan
   menyimpan rincian teknis (traceback) di tombol "Tampilkan Rincian".
3. `pasang_penangkap_galat()` memasang sys.excepthook: kesalahan tak terduga tidak menutup aplikasi,
   tetapi ditampilkan dan dicatat (KNF-4).
4. `TerjemahanQt` menerjemahkan teks bawaan Qt (OK/Cancel/Yes/No, Show Details, menu klik kanan
   kotak isian) ke Bahasa Indonesia. Qt tidak menyertakan berkas terjemahan qtbase_id (KNF-6).
"""

import errno
import sqlite3
import sys
import traceback

from PySide6.QtCore import QCoreApplication, QThread, QTranslator
from PySide6.QtWidgets import QApplication, QMessageBox

from aktivitas import catat

SARAN_UMUM = "Coba ulangi. Bila berulang, kirim file log (menu Riwayat Aktivitas → Buka Folder Log) ke pengembang."


def pesan_galat(e: BaseException) -> tuple:
    """(pesan, saran) berbahasa Indonesia untuk sebuah exception."""
    from database.berkas_proyek import BerkasTidakValid
    from ifc_reader import FileIFCTidakValid

    if isinstance(e, (FileIFCTidakValid, BerkasTidakValid)):
        return str(e), ""
    if isinstance(e, PermissionError):
        return (
            f"Akses ke file atau folder ditolak{_nama(e)}.",
            "Tutup file bila sedang dibuka di program lain (mis. Excel atau pembaca PDF), "
            "atau pilih folder lain yang bisa ditulis, mis. folder Dokumen.",
        )
    if isinstance(e, FileNotFoundError):
        return f"File atau folder tidak ditemukan{_nama(e)}.", "Periksa apakah file sudah dipindahkan atau dihapus, lalu pilih ulang."
    if isinstance(e, OSError) and e.errno == errno.ENOSPC:
        return "Ruang penyimpanan penuh.", "Kosongkan ruang disk atau simpan ke drive lain, lalu ulangi."
    if isinstance(e, sqlite3.OperationalError) and "locked" in str(e).lower():
        return "Database sedang dipakai proses lain.", "Tutup jendela CostStruct lain yang sedang terbuka, lalu ulangi."
    if isinstance(e, sqlite3.DatabaseError) and any(k in str(e).lower() for k in ("malformed", "not a database")):
        return (
            "Database aplikasi rusak.",
            "Tutup aplikasi lalu pulihkan database dari folder 'cadangan' di folder data aplikasi.",
        )
    if isinstance(e, MemoryError):
        return "Memori komputer tidak cukup untuk memproses data ini.", "Tutup aplikasi lain atau gunakan model IFC yang lebih kecil."
    if isinstance(e, OSError):
        return f"Gagal membaca atau menulis file{_nama(e)}: {e.strerror or e}.", "Periksa folder tujuan dan coba lagi."
    if isinstance(e, ValueError) and type(e) is not ValueError:
        return str(e), ""  # galat validasi aplikasi (…TidakValid) sudah berbahasa Indonesia
    if isinstance(e, ValueError):
        return str(e), SARAN_UMUM
    return f"Terjadi kesalahan tak terduga ({type(e).__name__}): {e}", SARAN_UMUM


def _nama(e: OSError) -> str:
    return f":\n{e.filename}" if getattr(e, "filename", None) else ""


def tampilkan_galat(parent, judul: str, e: BaseException, konteks: str = "", proyek_id: int | None = None) -> None:
    """Tampilkan pesan galat yang jelas + saran, dan catat ke log aktivitas beserta traceback."""
    pesan, saran = pesan_galat(e)
    rincian = "".join(traceback.format_exception(type(e), e, e.__traceback__))
    catat("galat", f"{konteks or judul}: {pesan}", proyek_id, detail=rincian, tingkat="GALAT")
    _kotak_galat(parent, judul, pesan, saran, rincian).exec()


def _kotak_galat(parent, judul: str, pesan: str, saran: str, rincian: str) -> QMessageBox:
    kotak = QMessageBox(parent)
    kotak.setIcon(QMessageBox.Critical)
    kotak.setWindowTitle(judul)
    kotak.setText(pesan)
    if saran:
        kotak.setInformativeText(saran)
    kotak.setDetailedText(rincian)
    kotak.addButton("Tutup", QMessageBox.AcceptRole)
    # Lebar teks & tombol "Tampilkan Rincian" dihitung Qt tanpa padding tema, jadi bisa terpotong.
    kotak.setStyleSheet("QLabel#qt_msgbox_label, QLabel#qt_msgbox_informativelabel { min-width: 400px; }")
    for b in kotak.buttons():
        if kotak.buttonRole(b) == QMessageBox.ActionRole:
            b.setMinimumWidth(b.fontMetrics().horizontalAdvance(TERJEMAHAN["Hide Details..."]) + 56)
    return kotak


_SEDANG = False


def _penangkap(jenis, nilai, tb):
    """sys.excepthook: kesalahan tak terduga di slot Qt tidak menutup aplikasi (KNF-4)."""
    global _SEDANG
    if issubclass(jenis, KeyboardInterrupt):
        sys.__excepthook__(jenis, nilai, tb)
        return
    rincian = "".join(traceback.format_exception(jenis, nilai, tb))
    catat("galat", f"Kesalahan tak terduga: {jenis.__name__}: {nilai}", detail=rincian, tingkat="GALAT")
    app = QApplication.instance()
    # Dialog hanya boleh dibuat di thread utama; dari thread lain cukup dicatat (sudah di atas).
    if _SEDANG or app is None or QThread.currentThread() is not app.thread():
        sys.__excepthook__(jenis, nilai, tb)
        return
    _SEDANG = True
    try:
        pesan, saran = pesan_galat(nilai)
        saran = (saran + "\n\n" if saran else "") + "Aplikasi tetap berjalan dan data yang sudah tersimpan aman."
        _kotak_galat(QApplication.activeWindow(), "Terjadi Kesalahan", pesan, saran, rincian).exec()
    finally:
        _SEDANG = False


def pasang_penangkap_galat() -> None:
    sys.excepthook = _penangkap


# ---------------------------------------------------------------- terjemahan teks bawaan Qt

TERJEMAHAN = {
    "OK": "OK",
    "&OK": "&OK",
    "Cancel": "Batal",
    "&Cancel": "&Batal",
    "Yes": "Ya",
    "&Yes": "&Ya",
    "No": "Tidak",
    "&No": "&Tidak",
    "Yes to &All": "Ya untuk &Semua",
    "N&o to All": "T&idak untuk Semua",
    "Close": "Tutup",
    "&Close": "&Tutup",
    "Save": "Simpan",
    "&Save": "&Simpan",
    "Save All": "Simpan Semua",
    "Open": "Buka",
    "&Open": "&Buka",
    "Discard": "Buang",
    "Don't Save": "Jangan Simpan",
    "Apply": "Terapkan",
    "Reset": "Atur Ulang",
    "Restore Defaults": "Kembalikan Bawaan",
    "Help": "Bantuan",
    "Abort": "Hentikan",
    "Retry": "Coba Lagi",
    "Ignore": "Abaikan",
    "Show Details...": "Tampilkan Rincian...",
    "Hide Details...": "Sembunyikan Rincian...",
    "&Undo": "&Urungkan",
    "&Redo": "&Ulangi",
    "Cu&t": "Po&tong",
    "&Copy": "&Salin",
    "&Paste": "&Tempel",
    "Delete": "Hapus",
    "Select All": "Pilih Semua",
    "&Step up": "&Naikkan",
    "Step &down": "&Turunkan",
    "Look in:": "Cari di:",
    "File &name:": "&Nama file:",
    "Files of type:": "Jenis file:",
    "&Choose": "&Pilih",
    "Directory:": "Folder:",
    "File name:": "Nama file:",
    "Back": "Kembali",
    "Forward": "Maju",
    "Parent Directory": "Folder Induk",
    "Create New Folder": "Buat Folder Baru",
    "New Folder": "Folder Baru",
    "Detail View": "Tampilan Rinci",
    "List View": "Tampilan Daftar",
}


class TerjemahanQt(QTranslator):
    """Penerjemah teks bawaan Qt (tombol standar dialog, menu klik kanan kotak isian, dialog file)."""

    def translate(self, context, sumber, disambiguation=None, n=-1):
        return TERJEMAHAN.get(sumber, "")

    def isEmpty(self):
        return False


def pasang_terjemahan(app) -> TerjemahanQt:
    t = TerjemahanQt(app)
    QCoreApplication.installTranslator(t)
    app._terjemahan_qt = t  # simpan referensi agar tidak dibersihkan garbage collector
    return t
