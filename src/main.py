"""
Titik masuk CostStruct.

    python src/main.py                       aplikasi
    python src/main.py --uji-mandiri [ifc]   uji mandiri tanpa antarmuka (lihat uji_mandiri.py)

Juga dipakai sebagai skrip utama PyInstaller (CostStruct.spec, KNF-8).
"""

import multiprocessing
import sys
from pathlib import Path


def _uji_mandiri(argumen: list) -> int:
    keluar = None
    if "--keluar" in argumen:
        i = argumen.index("--keluar")
        keluar = argumen[i + 1] if i + 1 < len(argumen) else None
        argumen = argumen[:i] + argumen[i + 2:]
    ifc = next((a for a in argumen if a.lower().endswith(".ifc")), None)
    from uji_mandiri import jalankan

    hasil = jalankan(ifc, keluar)
    return 0 if hasil["berhasil"] else 1


if __name__ == "__main__":
    # Wajib paling awal: proses anak validasi IFC (spawn) masuk lewat sini saat dibundel PyInstaller.
    multiprocessing.freeze_support()
    sys.path.insert(0, str(Path(__file__).resolve().parent))

    if "--uji-mandiri" in sys.argv:
        sys.exit(_uji_mandiri([a for a in sys.argv[1:] if a != "--uji-mandiri"]))

    from gui.splash_screen import main

    main()
