"""
Titik masuk CostStruct.

    python src/main.py

Juga dipakai sebagai skrip utama PyInstaller:
    pyinstaller --windowed --name CostStruct src/main.py
"""

import multiprocessing
import sys
from pathlib import Path

if __name__ == "__main__":
    # Wajib paling awal: proses anak validasi IFC (spawn) masuk lewat sini saat dibundel PyInstaller.
    multiprocessing.freeze_support()
    sys.path.insert(0, str(Path(__file__).resolve().parent))

    from gui.splash_screen import main

    main()
