"""
KF-15 Logging aktivitas.

Setiap aktivitas penting dicatat di dua tempat:
1. Tabel `log_aktivitas` di database: ditampilkan di halaman Riwayat Aktivitas (cari, filter, urut).
2. File log harian `log/coststruct.log` di folder data (lokasi.py), diputar tiap tengah malam dan
   disimpan 30 hari: jejak teknis termasuk detail kesalahan (traceback) untuk penelusuran.

Jenis aktivitas (JENIS) mengikuti use case skripsi: import IFC (UC-01), edit hasil & recalculate
(UC-03), harga satuan (UC-04), export (UC-05), simpan/buka proyek (UC-06), pengaturan (UC-07).
Pencatatan tidak pernah menggagalkan aktivitas utamanya: bila database log bermasalah, cukup
ditulis ke file log.
"""

import logging
from datetime import datetime, timedelta
from logging.handlers import TimedRotatingFileHandler

log = logging.getLogger("coststruct")

JENIS = {
    "aplikasi": "Aplikasi",
    "proyek": "Proyek",
    "import": "Import IFC",
    "estimasi": "Hitung QTO",
    "edit": "Edit hasil",
    "dimensi": "Ubah dimensi",
    "penulangan": "Penulangan",
    "parameter": "Parameter aturan",
    "biaya": "Biaya tidak langsung",
    "harga": "Harga satuan",
    "export": "Export laporan",
    "berkas": "File proyek",
    "riwayat": "Urungkan / ulangi",
    "pengaturan": "Pengaturan",
    "galat": "Kesalahan",
}
TINGKAT = ("INFO", "PERINGATAN", "GALAT")
_LEVEL = {"INFO": logging.INFO, "PERINGATAN": logging.WARNING, "GALAT": logging.ERROR}
FORMAT = "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s"


def siapkan_log(folder=None) -> str | None:
    """Pasang handler file log harian. Return path file log (None bila folder tidak bisa ditulis)."""
    from lokasi import folder_log

    folder = folder or folder_log()
    try:
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / "coststruct.log"
        for h in list(log.handlers):
            if isinstance(h, TimedRotatingFileHandler):
                log.removeHandler(h)
                h.close()
        handler = TimedRotatingFileHandler(path, when="midnight", backupCount=30, encoding="utf-8")
        handler.setFormatter(logging.Formatter(FORMAT, "%Y-%m-%d %H:%M:%S"))
        log.addHandler(handler)
        log.setLevel(logging.INFO)
        logging.captureWarnings(True)
        return str(path)
    except OSError:
        return None


def catat(jenis: str, pesan: str, proyek_id: int | None = None, detail: str | None = None,
          tingkat: str = "INFO") -> None:
    """Catat satu aktivitas. Tidak pernah melempar exception."""
    tingkat = tingkat if tingkat in TINGKAT else "INFO"
    log.getChild(jenis).log(_LEVEL[tingkat], "%s%s%s", f"[proyek {proyek_id}] " if proyek_id else "", pesan,
                            f"\n{detail}" if detail else "")
    try:
        from database.estimasi_repository import _connect

        conn = _connect()
        try:
            conn.execute(
                "INSERT INTO log_aktivitas (waktu, tingkat, jenis, proyek_id, pesan, detail) VALUES (?,?,?,?,?,?)",
                (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), tingkat, jenis, proyek_id, pesan, detail),
            )
            conn.commit()
        finally:
            conn.close()
    except Exception as e:  # tabel belum ada / database terkunci: cukup di file log
        log.warning("Aktivitas tidak tersimpan di database (%s): %s", e, pesan)


def daftar_aktivitas(batas: int = 5000, jenis: str | None = None, kata: str | None = None,
                     proyek_id: int | None = None) -> list:
    """Aktivitas terbaru dulu, beserta nama proyek (bila proyeknya masih ada)."""
    from database.estimasi_repository import _connect

    sql = """SELECT l.*, p.nama_proyek FROM log_aktivitas l LEFT JOIN proyek p ON p.id = l.proyek_id WHERE 1 = 1"""
    args = []
    if jenis:
        sql += " AND l.jenis = ?"
        args.append(jenis)
    if proyek_id is not None:
        sql += " AND l.proyek_id = ?"
        args.append(proyek_id)
    if kata:
        sql += " AND (l.pesan LIKE ? OR p.nama_proyek LIKE ?)"
        args += [f"%{kata}%"] * 2
    sql += " ORDER BY l.id DESC LIMIT ?"
    args.append(batas)
    conn = _connect()
    try:
        return [dict(r) for r in conn.execute(sql, args)]
    finally:
        conn.close()


def pangkas(maks_hari: int = 365) -> int:
    """Hapus catatan yang lebih tua dari `maks_hari` (dijalankan saat aplikasi dibuka)."""
    from database.estimasi_repository import _connect

    batas = (datetime.now() - timedelta(days=maks_hari)).strftime("%Y-%m-%d %H:%M:%S")
    conn = _connect()
    try:
        n = conn.execute("DELETE FROM log_aktivitas WHERE waktu < ?", (batas,)).rowcount
        conn.commit()
        return n
    finally:
        conn.close()


def rp(nilai: float) -> str:
    return "Rp " + f"{nilai:,.0f}".replace(",", ".")
