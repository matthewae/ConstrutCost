"""
Lokasi data aplikasi (KNF-8).

- Dijalankan sebagai .exe (PyInstaller, `sys.frozen`): data disimpan di folder pengguna yang tetap,
  bukan di folder sementara _MEIxxxx yang terhapus setiap aplikasi ditutup:
      Windows : %APPDATA%\\CostStruct
      lainnya : ~/.local/share/CostStruct
- Dijalankan dari kode sumber (python src/main.py): <folder proyek>/data, seperti sebelumnya.
- Variabel lingkungan COSTSTRUCT_DATA dapat menunjuk folder lain (mis. flashdisk / pengujian).

Isi folder data:
    coststruct.db      database SQLite (proyek, harga, preferensi, log aktivitas)
    log/               file log harian (KF-15)
    cadangan/          salinan cadangan database
"""

import os
import sys
from pathlib import Path

NAMA_APLIKASI = "CostStruct"


def dibundel() -> bool:
    """True bila berjalan dari executable PyInstaller."""
    return bool(getattr(sys, "frozen", False))


def folder_data() -> Path:
    khusus = os.environ.get("COSTSTRUCT_DATA")
    if khusus:
        return Path(khusus)
    if dibundel():
        if sys.platform == "win32":
            dasar = Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming")
        else:
            dasar = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share")
        return dasar / NAMA_APLIKASI
    return Path(__file__).resolve().parents[1] / "data"


def path_database() -> Path:
    return folder_data() / "coststruct.db"


def folder_log() -> Path:
    return folder_data() / "log"


def folder_cadangan() -> Path:
    return folder_data() / "cadangan"


def folder_sumber() -> Path:
    """Folder berkas pendukung (schema.sql, ikon). Di .exe = folder ekstraksi PyInstaller."""
    return Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
