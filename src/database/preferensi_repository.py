"""
Preferensi pengguna (KF-10 / UC-07) di tabel preferensi_pengguna (kunci, nilai).

`get_pref` / `set_pref` menyimpan nilai bebas. `Preferensi` mengumpulkan pengaturan yang
diatur dari halaman Pengaturan: tema, direktori default, dan format laporan default.
"""

from dataclasses import asdict, dataclass, fields
from pathlib import Path

from database.estimasi_repository import _connect

# Urutan = urutan kartu di Pengaturan. "hitam_kuning" (identitas Mandajaya) adalah bawaan sejak tema v2.
TEMA = ("hitam_kuning", "terang_emas", "gelap", "terang")
TEMA_BAWAAN = "hitam_kuning"
ORIENTASI = ("portrait", "landscape")
# KF-17: kolom laporan yang bisa dipilih (sama dengan export_service.KOLOM_OPSIONAL)
KOLOM_LAPORAN = ("no", "kode", "harga", "bobot", "rumus")
_AWALAN = "pref."  # kunci tersimpan: pref.tema, pref.direktori_ifc, ...


def _pastikan_tabel(conn):
    conn.execute("CREATE TABLE IF NOT EXISTS preferensi_pengguna (kunci TEXT PRIMARY KEY, nilai TEXT)")


def get_pref(kunci: str, default=None):
    conn = _connect()
    try:
        _pastikan_tabel(conn)
        row = conn.execute("SELECT nilai FROM preferensi_pengguna WHERE kunci = ?", (kunci,)).fetchone()
        return row["nilai"] if row else default
    finally:
        conn.close()


def set_pref(kunci: str, nilai: str) -> None:
    conn = _connect()
    try:
        _pastikan_tabel(conn)
        conn.execute("INSERT OR REPLACE INTO preferensi_pengguna (kunci, nilai) VALUES (?, ?)", (kunci, nilai))
        conn.commit()
    finally:
        conn.close()


class PreferensiTidakValid(ValueError):
    """Pengaturan ditolak. Pesannya siap ditampilkan ke pengguna."""


@dataclass
class Preferensi:
    tema: str = TEMA_BAWAAN
    versi_tema: str = "2"  # pengguna versi lama (tema "gelap" bawaan) dipindah sekali ke Hitam Kuning
    direktori_ifc: str = ""  # kosong = folder Dokumen
    direktori_export: str = ""  # kosong = folder Dokumen
    format_excel: bool = True
    format_pdf: bool = True
    isi_rekap: bool = True
    isi_detail: bool = True
    isi_rinci: bool = True  # RAB rinci per tipe elemen
    isi_besi: bool = True  # kebutuhan besi per diameter
    isi_lantai: bool = True  # KF-12 rekap per lantai
    isi_per_lantai: bool = True  # rincian kebutuhan tiap lantai (satu sheet / bagian per lantai)
    kolom_laporan: str = "no,kode,harga"  # KF-17, dipisah koma
    orientasi_pdf: str = "portrait"

    @property
    def kolom(self) -> tuple:
        return tuple(k for k in self.kolom_laporan.split(",") if k in KOLOM_LAPORAN)


def folder_default() -> str:
    """Folder Dokumen pengguna. Memakai lokasi dari sistem (QStandardPaths), sehingga tetap benar bila
    OneDrive memindahkan Dokumen ke C:\\Users\\<nama>\\OneDrive\\Documents."""
    try:
        from PySide6.QtCore import QStandardPaths

        lokasi = QStandardPaths.writableLocation(QStandardPaths.DocumentsLocation)
        if lokasi and Path(lokasi).is_dir():
            return lokasi
    except Exception:
        pass
    dokumen = Path.home() / "Documents"
    return str(dokumen if dokumen.is_dir() else Path.home())


def folder_ifc(p: "Preferensi") -> str:
    return p.direktori_ifc if p.direktori_ifc and Path(p.direktori_ifc).is_dir() else folder_default()


def folder_export(p: "Preferensi") -> str:
    return p.direktori_export if p.direktori_export and Path(p.direktori_export).is_dir() else folder_default()


def _ke_teks(v) -> str:
    return ("1" if v else "0") if isinstance(v, bool) else str(v)


def muat_preferensi() -> Preferensi:
    conn = _connect()
    try:
        _pastikan_tabel(conn)
        tersimpan = {
            r["kunci"][len(_AWALAN):]: r["nilai"]
            for r in conn.execute("SELECT kunci, nilai FROM preferensi_pengguna WHERE kunci LIKE ?", (_AWALAN + "%",))
        }
        lama = conn.execute("SELECT nilai FROM preferensi_pengguna WHERE kunci = 'export_dir'").fetchone()
    finally:
        conn.close()
    p = Preferensi()
    for f in fields(Preferensi):
        if f.name not in tersimpan:
            continue
        nilai = tersimpan[f.name]
        setattr(p, f.name, nilai == "1" if f.type in (bool, "bool") else nilai)
    if "versi_tema" not in tersimpan and p.tema == "gelap":
        p.tema = TEMA_BAWAAN  # dulu "gelap" adalah bawaan, bukan pilihan pengguna
    p.versi_tema = "2"
    if p.tema not in TEMA:
        p.tema = TEMA_BAWAAN
    if p.orientasi_pdf not in ORIENTASI:
        p.orientasi_pdf = "portrait"
    if not p.direktori_export and lama:  # folder export terakhir dari versi sebelumnya
        p.direktori_export = lama["nilai"]
    return p


def validasi_preferensi(p: Preferensi) -> None:
    if p.tema not in TEMA:
        raise PreferensiTidakValid("Tema tidak dikenal. Pilih salah satu tema di halaman Pengaturan.")
    for label, folder in (("Folder file IFC", p.direktori_ifc), ("Folder hasil export", p.direktori_export)):
        if folder and not Path(folder).is_dir():
            raise PreferensiTidakValid(f"{label} tidak ditemukan:\n{folder}")
    if not (p.format_excel or p.format_pdf):
        raise PreferensiTidakValid("Pilih minimal satu format laporan (Excel atau PDF).")
    tidak_dikenal = [k for k in p.kolom_laporan.split(",") if k and k not in KOLOM_LAPORAN]
    if tidak_dikenal:
        raise PreferensiTidakValid(f"Kolom laporan tidak dikenal: {', '.join(tidak_dikenal)}")
    if p.orientasi_pdf not in ORIENTASI:
        raise PreferensiTidakValid("Orientasi PDF harus portrait atau landscape.")


def simpan_preferensi(p: Preferensi) -> None:
    validasi_preferensi(p)
    conn = _connect()
    try:
        _pastikan_tabel(conn)
        conn.executemany(
            "INSERT OR REPLACE INTO preferensi_pengguna (kunci, nilai) VALUES (?, ?)",
            [(_AWALAN + k, _ke_teks(v)) for k, v in asdict(p).items()],
        )
        conn.commit()
    finally:
        conn.close()
    from aktivitas import catat

    format_ = "/".join(n for n, a in (("Excel", p.format_excel), ("PDF", p.format_pdf)) if a)
    catat("pengaturan", f"Pengaturan disimpan: tema {p.tema}, format {format_}, kolom {p.kolom_laporan or '-'}")


def simpan_pilihan_export(p: Preferensi) -> None:
    """Ingat pilihan dialog Export (format, isi, kolom, orientasi) sebagai bawaan berikutnya.
    Folder tidak divalidasi di sini; pengaturan lain tidak berubah."""
    kunci = ("format_excel", "format_pdf", "isi_rekap", "isi_detail", "isi_rinci", "isi_besi", "isi_lantai",
             "isi_per_lantai", "kolom_laporan", "orientasi_pdf", "direktori_export")
    conn = _connect()
    try:
        _pastikan_tabel(conn)
        conn.executemany(
            "INSERT OR REPLACE INTO preferensi_pengguna (kunci, nilai) VALUES (?, ?)",
            [(_AWALAN + k, _ke_teks(getattr(p, k))) for k in kunci],
        )
        conn.commit()
    finally:
        conn.close()


def reset_preferensi() -> Preferensi:
    """UC-07 skenario alternatif: kembalikan semua pengaturan ke nilai bawaan."""
    conn = _connect()
    try:
        _pastikan_tabel(conn)
        conn.execute("DELETE FROM preferensi_pengguna WHERE kunci LIKE ? OR kunci = 'export_dir'", (_AWALAN + "%",))
        conn.commit()
    finally:
        conn.close()
    from aktivitas import catat

    catat("pengaturan", "Pengaturan dikembalikan ke nilai bawaan")
    return Preferensi()
