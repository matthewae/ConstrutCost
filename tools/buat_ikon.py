"""
Buat ikon aplikasi `assets/coststruct.ico` (dan .png) dari logo vektor di gui/tema.py (KNF-8).
Ikon ini dipakai PyInstaller sebagai ikon CostStruct.exe.

    python tools/buat_ikon.py
"""

import io
import os
import sys
from pathlib import Path

AKAR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AKAR / "src"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

UKURAN = (16, 24, 32, 48, 64, 128, 256)


def buat(folder: Path = AKAR / "assets") -> Path:
    from PIL import Image
    from PySide6.QtCore import QBuffer, QIODevice
    from PySide6.QtGui import QGuiApplication

    from gui.tema import gambar_ikon_aplikasi

    if QGuiApplication.instance() is None:
        buat._app = QGuiApplication([])  # QPixmap butuh QGuiApplication; referensi ditahan
    folder.mkdir(parents=True, exist_ok=True)
    gambar = []
    for u in UKURAN:
        buf = QBuffer()
        buf.open(QIODevice.WriteOnly)
        gambar_ikon_aplikasi(u).save(buf, "PNG")
        gambar.append(Image.open(io.BytesIO(bytes(buf.data()))).convert("RGBA"))
    gambar[-1].save(folder / "coststruct.png")
    ico = folder / "coststruct.ico"
    gambar[-1].save(ico, sizes=[(u, u) for u in UKURAN], append_images=gambar[:-1])
    return ico


if __name__ == "__main__":
    print(f"Ikon dibuat: {buat()}")
