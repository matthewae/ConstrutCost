"""
Build CostStruct.exe (KNF-8) lalu jalankan uji mandiri pada hasil build.

    python tools/build_exe.py              mode folder: dist/CostStruct/CostStruct.exe (disarankan)
    python tools/build_exe.py --onefile    satu file: dist/CostStruct.exe
    python tools/build_exe.py --tanpa-uji  lewati uji mandiri

Langkah:
1. Buat ikon assets/coststruct.ico dari logo aplikasi (bila belum ada).
2. Jalankan PyInstaller dengan CostStruct.spec.
3. Jalankan `CostStruct.exe --uji-mandiri` di folder data sementara: database & harga HSPK,
   validasi IFC di proses anak, parsing & rule engine, export Excel/PDF, simpan & buka file proyek.
   Laporan: build/uji_mandiri/uji_mandiri.txt.
"""

import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

AKAR = Path(__file__).resolve().parents[1]


def main(argumen: list) -> int:
    satu_file = "--onefile" in argumen
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
