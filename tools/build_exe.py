"""
Build CostStruct.exe (KNF-8) lalu jalankan uji mandiri pada hasil build.

    python tools/build_exe.py              mode folder: dist/CostStruct/CostStruct.exe (disarankan)
    python tools/build_exe.py --onefile    satu file: dist/CostStruct.exe
    python tools/build_exe.py --tanpa-uji  lewati uji mandiri

Langkah:
1. Buat ikon assets/coststruct.ico dari logo aplikasi (bila belum ada).
2. Jalankan PyInstaller dengan CostStruct.spec.
3. Jalankan `CostStruct.exe --uji-mandiri` di folder data sementara: database & harga HSPK,
   validasi IFC di proses anak, parsing & rule engine, export Excel/PDF, simpan & buka file proyek,
   dan membuka jendela utama (antarmuka Qt).
   Laporan: build/uji_mandiri/uji_mandiri.txt.
"""

import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

AKAR = Path(__file__).resolve().parents[1]
PAKET_WAJIB = (("PyInstaller", "pyinstaller"), ("PySide6", "PySide6"), ("ifcopenshell", "ifcopenshell"),
               ("openpyxl", "openpyxl"), ("reportlab", "reportlab"), ("shapely", "shapely"), ("numpy", "numpy"))


def periksa_lingkungan() -> list:
    """Masalah yang membuat build gagal, dalam bahasa yang jelas (list kosong = siap build)."""
    import importlib.util
    import struct

    masalah = []
    if sys.version_info < (3, 11):
        masalah.append(f"Python {sys.version.split()[0]} terlalu lama; gunakan Python 3.13 64-bit.")
    if struct.calcsize("P") != 8:
        masalah.append("Python yang dipakai 32-bit; pasang Python 3.13 64-bit (Windows installer (64-bit)).")
    kurang = [paket for modul, paket in PAKET_WAJIB if importlib.util.find_spec(modul) is None]
    if kurang:
        di_venv = sys.prefix != sys.base_prefix
        masalah.append(
            f"Paket belum terpasang di Python ini ({sys.executable}): {', '.join(kurang)}.\n"
            + ("   Jalankan: python -m pip install -r requirements.txt" if di_venv else
               "   Virtual environment belum aktif. Di terminal (PowerShell): .\\venv\\Scripts\\Activate.ps1\n"
               "   lalu: python -m pip install -r requirements.txt")
        )
    folder = AKAR / "dist" / "CostStruct"
    if folder.is_dir():  # Windows: folder tidak bisa dihapus/diganti selama CostStruct.exe masih berjalan
        uji = folder.with_name("CostStruct_cek_kunci")
        try:
            folder.rename(uji)
            uji.rename(folder)
        except OSError:
            masalah.append("Folder dist\\CostStruct sedang dipakai. Tutup CostStruct.exe (dan File Explorer di folder "
                           "itu), lalu ulangi build.")
    return masalah


def main(argumen: list) -> int:
    satu_file = "--onefile" in argumen
    masalah = periksa_lingkungan()
    if masalah:
        print("BUILD DIBATALKAN, perbaiki dulu:")
        for m in masalah:
            print(" - " + m)
        return 2
    if not (AKAR / "assets" / "coststruct.ico").is_file():
        subprocess.run([sys.executable, str(AKAR / "tools" / "buat_ikon.py")], check=True)

    env = dict(os.environ, COSTSTRUCT_ONEFILE="1" if satu_file else "0")
    print(">> PyInstaller CostStruct.spec" + (" (satu file)" if satu_file else ""), flush=True)
    t0 = time.perf_counter()
    r = subprocess.run([sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "CostStruct.spec"], cwd=AKAR, env=env)
    if r.returncode != 0:
        print("BUILD GAGAL. Periksa pesan PyInstaller di atas.")
        return r.returncode
    nama = "CostStruct.exe" if sys.platform == "win32" else "CostStruct"
    exe = AKAR / "dist" / nama if satu_file else AKAR / "dist" / "CostStruct" / nama
    ukuran = exe.stat().st_size if satu_file else sum(f.stat().st_size for f in exe.parent.rglob("*") if f.is_file() and not f.is_symlink())
    print(f">> Build selesai dalam {time.perf_counter() - t0:.0f} s: {exe} ({ukuran / 1e6:.0f} MB)")
    print(f">> Jalankan aplikasi: {exe.relative_to(AKAR) if exe.is_relative_to(AKAR) else exe}")

    if "--tanpa-uji" in argumen:
        return 0
    keluar = AKAR / "build" / "uji_mandiri"
    shutil.rmtree(keluar, ignore_errors=True)
    print(">> Uji mandiri hasil build...", flush=True)
    r = subprocess.run([str(exe), "--uji-mandiri", "--keluar", str(keluar)], timeout=600)
    laporan = keluar / "uji_mandiri.txt"
    print(laporan.read_text(encoding="utf-8") if laporan.is_file() else "Laporan uji mandiri tidak dibuat.")
    return r.returncode


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
