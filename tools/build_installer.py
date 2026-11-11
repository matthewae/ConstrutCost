"""
Build installer Windows CostStruct (Inno Setup 6) dari hasil PyInstaller, lalu (opsional) mengujinya.

    python tools/build_exe.py                     1. build folder dist/CostStruct (wajib lebih dulu)
    python tools/build_installer.py               2. build dist/installer/CostStruct-Setup-<versi>.exe
    python tools/build_installer.py --uji         2 + uji: pasang diam-diam, uji mandiri dari folder instalasi,
                                                      periksa asosiasi .coststruct, copot, periksa bersih
    python tools/build_installer.py --pasang-iscc pasang Inno Setup lewat Chocolatey bila ISCC.exe belum ada (CI)

ISCC.exe dicari di variabel lingkungan ISCC, PATH, lalu folder instalasi bawaan Inno Setup 6.
Unduh Inno Setup: https://jrsoftware.org/isdl.php (gratis).
"""

import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

AKAR = Path(__file__).resolve().parents[1]
SKRIP = AKAR / "installer" / "CostStruct.iss"
FOLDER_APP = AKAR / "dist" / "CostStruct"
KELUAR = AKAR / "dist" / "installer"


def versi_aplikasi() -> str:
    """Versi dari VERSI_APLIKASI (src/gui/main_window.py), tanpa awalan 'v'."""
    teks = (AKAR / "src" / "gui" / "main_window.py").read_text(encoding="utf-8")
    m = re.search(r'VERSI_APLIKASI\s*=\s*"v?([0-9][^"]*)"', teks)
    if not m:
        raise SystemExit("VERSI_APLIKASI tidak ditemukan di src/gui/main_window.py")
    return m.group(1)


def cari_iscc() -> Path | None:
    calon = [os.environ.get("ISCC"), shutil.which("iscc"), shutil.which("ISCC")]
    for dasar in (os.environ.get("ProgramFiles(x86)"), os.environ.get("ProgramFiles"),
                  str(Path(os.environ.get("LOCALAPPDATA", "")) / "Programs")):
        if dasar:
            calon.append(str(Path(dasar) / "Inno Setup 6" / "ISCC.exe"))
    return next((Path(c) for c in calon if c and Path(c).is_file()), None)


def pasang_iscc() -> Path | None:
    print(">> ISCC.exe belum ada; memasang Inno Setup lewat Chocolatey...", flush=True)
    subprocess.run(["choco", "install", "innosetup", "-y", "--no-progress"], check=False)
    return cari_iscc()


def build(iscc: Path, versi: str) -> Path:
    print(f">> ISCC {SKRIP.relative_to(AKAR)} (versi {versi})", flush=True)
    t0 = time.perf_counter()
    r = subprocess.run([str(iscc), f"/DVersiApp={versi}", str(SKRIP)], cwd=SKRIP.parent)
    if r.returncode != 0:
        raise SystemExit(f"BUILD INSTALLER GAGAL (ISCC kode {r.returncode}). Periksa pesan ISCC di atas.")
    setup = KELUAR / f"CostStruct-Setup-{versi}.exe"
    if not setup.is_file():
        raise SystemExit(f"File installer tidak ditemukan: {setup}")
    print(f">> Installer selesai dalam {time.perf_counter() - t0:.0f} s: {setup} ({setup.stat().st_size / 1e6:.0f} MB)")
    return setup


def _baca_registri(subkey: str) -> str | None:
    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, subkey) as k:
            return winreg.QueryValueEx(k, "")[0]
    except OSError:
        return None


def uji(setup: Path) -> int:
    """Pasang untuk pengguna ini ke folder sementara, jalankan uji mandiri dari hasil instalasi, periksa asosiasi
    file, lalu copot dan periksa folder serta registri bersih. Return 0 bila semua lulus."""
    gagal = []
    folder = Path(tempfile.mkdtemp(prefix="coststruct_pasang_")) / "CostStruct"
    log = AKAR / "build" / "uji_installer"
    shutil.rmtree(log, ignore_errors=True)
    log.mkdir(parents=True, exist_ok=True)

    print(f">> Memasang (diam-diam, pengguna ini) ke {folder}", flush=True)
    r = subprocess.run([str(setup), "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/CURRENTUSER",
                        f"/DIR={folder}", "/TASKS=asosiasi,bukaifc", f"/LOG={log / 'pasang.log'}"], timeout=900)
    exe = folder / "CostStruct.exe"
    if r.returncode != 0 or not exe.is_file():
        print(f"GAGAL memasang (kode {r.returncode}); lihat {log / 'pasang.log'}")
        return 1
    print(">> Terpasang. Uji mandiri dari folder instalasi...", flush=True)
    r = subprocess.run([str(exe), "--uji-mandiri", "--keluar", str(log / "uji_mandiri")], timeout=900)
    laporan = log / "uji_mandiri" / "uji_mandiri.txt"
    print(laporan.read_text(encoding="utf-8") if laporan.is_file() else "Laporan uji mandiri tidak dibuat.")
    if r.returncode != 0:
        gagal.append("uji mandiri aplikasi terpasang gagal")

    perintah = _baca_registri(r"Software\Classes\CostStruct.Proyek\shell\open\command") or ""
    if _baca_registri(r"Software\Classes\.coststruct") != "CostStruct.Proyek" or str(exe).lower() not in perintah.lower():
        gagal.append(f"asosiasi .coststruct tidak terpasang dengan benar (perintah: {perintah!r})")
    else:
        print(f">> Asosiasi .coststruct: {perintah}")
    if _baca_registri(r"Software\Classes\CostStruct.IFC\shell\open\command") is None:
        gagal.append("entri 'Buka dengan' untuk .ifc tidak terpasang")

    pencopot = folder / "unins000.exe"
    print(">> Mencopot (diam-diam)...", flush=True)
    if not pencopot.is_file():
        gagal.append("unins000.exe tidak ada")
    else:
        subprocess.run([str(pencopot), "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART"], timeout=600)
        batas = time.time() + 120  # pencopot menyalin dirinya ke folder sementara lalu bekerja di latar
        while exe.exists() and time.time() < batas:
            time.sleep(1)
        if exe.exists():
            gagal.append("CostStruct.exe masih ada setelah dicopot")
        if _baca_registri(r"Software\Classes\CostStruct.Proyek") is not None:
            gagal.append("kunci registri CostStruct.Proyek masih ada setelah dicopot")
    if gagal:
        print("UJI INSTALLER GAGAL:\n - " + "\n - ".join(gagal))
        return 1
    print(">> UJI INSTALLER BERHASIL: pasang, uji mandiri, asosiasi file, dan copot bersih.")
    return 0


def main(argumen: list) -> int:
    if sys.platform != "win32":
        print("Installer hanya dapat dibangun di Windows (Inno Setup).")
        return 2
    if not (FOLDER_APP / "CostStruct.exe").is_file():
        print("dist\\CostStruct\\CostStruct.exe belum ada. Jalankan dulu: python tools\\build_exe.py")
        return 2
    iscc = cari_iscc() or (pasang_iscc() if "--pasang-iscc" in argumen else None)
    if iscc is None:
        print("ISCC.exe (Inno Setup 6) tidak ditemukan. Pasang dari https://jrsoftware.org/isdl.php, atau isi "
              "variabel lingkungan ISCC dengan lokasi ISCC.exe.")
        return 2
    setup = build(iscc, versi_aplikasi())
    return uji(setup) if "--uji" in argumen else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
