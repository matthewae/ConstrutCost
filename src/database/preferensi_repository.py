"""
Preferensi pengguna (KF-10 / UC-07) di tabel preferensi_pengguna (kunci, nilai).

`get_pref` / `set_pref` menyimpan nilai bebas. `Preferensi` mengumpulkan pengaturan yang
diatur dari halaman Pengaturan: tema, direktori default, dan format laporan default.
"""

from dataclasses import asdict, dataclass, fields
from pathlib import Path

from database.estimasi_repository import _connect

TEMA = ("gelap", "terang")
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
    tema: str = "gelap"
    direktori_ifc: str = ""  # kosong = folder Dokumen
    direktori_export: str = ""  # kosong = folder Dokumen
    format_excel: bool = True
    format_pdf: bool = True
    isi_rekap: bool = True
    isi_detail: bool = True


def folder_default() -> str:
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
    if p.tema not in TEMA:
        p.tema = "gelap"
    if not p.direktori_export and lama:  # folder export terakhir dari versi sebelumnya
        p.direktori_export = lama["nilai"]
    return p


def validasi_preferensi(p: Preferensi) -> None:
    if p.tema not in TEMA:
        raise PreferensiTidakValid("Tema harus Gelap atau Terang.")
    for label, folder in (("Folder file IFC", p.direktori_ifc), ("Folder hasil export", p.direktori_export)):
        if folder and not Path(folder).is_dir():
            raise PreferensiTidakValid(f"{label} tidak ditemukan:\n{folder}")
    if not (p.format_excel or p.format_pdf):
        raise PreferensiTidakValid("Pilih minimal satu format laporan (Excel atau PDF).")


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


def reset_preferensi() -> Preferensi:
    """UC-07 skenario alternatif: kembalikan semua pengaturan ke nilai bawaan."""
    conn = _connect()
    try:
        _pastikan_tabel(conn)
        conn.execute("DELETE FROM preferensi_pengguna WHERE kunci LIKE ? OR kunci = 'export_dir'", (_AWALAN + "%",))
        conn.commit()
    finally:
        conn.close()
    return Preferensi()
