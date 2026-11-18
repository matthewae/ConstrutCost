"""
Pisahkan logo CostStruct dari latar kotak-kotak abu-abu yang ikut tercetak di gambar JPG (bukan transparan asli).

    python tools/pisah_logo.py [assets/logo/coststruct-logo-asli.jpg]

Hasil:
    src/gui/aset/logo_emblem.png     emblem huruf S, 512 x 512 px, transparan (dipakai aplikasi)
    assets/logo/coststruct-logo.png  emblem + tulisan CostStruct, lebar 640 px, transparan (dokumen)

Cara kerja: latar kotak-kotak berwarna abu-abu (kejenuhan rendah, kecerahan <= ±115), sedangkan logo berwarna kuning
(jenuh) atau putih (terang). Transparansi tiap piksel = max((kejenuhan - 14) / 30, (kecerahan - 120) / 50), dibatasi
0..1 lalu dihaluskan median 3 x 3. Bagian gelap di dalam logo ikut transparan; logo dirancang untuk latar gelap,
jadi aplikasi selalu menampilkannya di atas latar gelap (lihat gui/tema.py, gambar_logo).
"""

import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

AKAR = Path(__file__).resolve().parents[1]


def alpha_logo(rgb: np.ndarray) -> np.ndarray:
    jenuh = rgb.max(axis=2) - rgb.min(axis=2)
    terang = rgb.mean(axis=2)
    a = np.clip(np.maximum((jenuh - 14) / 30, (terang - 120) / 50), 0, 1)
    halus = Image.fromarray((a * 255).astype(np.uint8)).filter(ImageFilter.MedianFilter(3))
    return np.asarray(halus).astype(float) / 255


def _kotak(a: np.ndarray, y0: int, y1: int) -> tuple:
    ys, xs = np.where(a[y0:y1] > 0.25)
    return int(xs.min()), y0 + int(ys.min()), int(xs.max()) + 1, y0 + int(ys.max()) + 1


def pisah(sumber: Path) -> None:
    rgb = np.asarray(Image.open(sumber).convert("RGB")).astype(float)
    a = alpha_logo(rgb)
    logo = Image.fromarray(np.dstack([rgb, a * 255]).astype(np.uint8), "RGBA")
    # emblem dan tulisan dipisahkan oleh baris kosong (tanpa piksel logo) di antara keduanya
    baris = (a > 0.3).sum(axis=1)
    isi = [y for y in range(len(baris)) if baris[y] > 0]
    celah = next(y for y in range(isi[0], isi[-1]) if baris[y] == 0 and baris[y + 1:y + 20].sum() == 0)
    emblem = _kotak(a, isi[0], celah)
    teks = _kotak(a, celah, isi[-1] + 1)

    x0, y0, x1, y1 = emblem
    sisi = int(max(x1 - x0, y1 - y0) * 1.04)
    kanvas = Image.new("RGBA", (sisi, sisi), (0, 0, 0, 0))
    kanvas.paste(logo.crop(emblem), ((sisi - (x1 - x0)) // 2, (sisi - (y1 - y0)) // 2))
    tujuan = AKAR / "src" / "gui" / "aset"
    tujuan.mkdir(parents=True, exist_ok=True)
    kanvas.resize((512, 512), Image.LANCZOS).save(tujuan / "logo_emblem.png", optimize=True)

    lengkap = logo.crop((min(x0, teks[0]) - 8, y0 - 8, max(x1, teks[2]) + 8, teks[3] + 8))
    lengkap = lengkap.resize((640, round(lengkap.height * 640 / lengkap.width)), Image.LANCZOS)
    lengkap.save(AKAR / "assets" / "logo" / "coststruct-logo.png", optimize=True)
    print(f"emblem {emblem}, tulisan {teks} -> {tujuan / 'logo_emblem.png'}")


if __name__ == "__main__":
    pisah(Path(sys.argv[1]) if len(sys.argv) > 1 else AKAR / "assets" / "logo" / "coststruct-logo-asli.jpg")
