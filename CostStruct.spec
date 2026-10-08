# -*- mode: python ; coding: utf-8 -*-
"""
Spesifikasi PyInstaller CostStruct (KNF-8: aplikasi desktop Windows berbentuk .exe).

    python tools/build_exe.py             build + uji mandiri (disarankan)
    pyinstaller --noconfirm CostStruct.spec

Hasil (mode folder, bawaan): dist/CostStruct/CostStruct.exe beserta folder _internal.
Mode satu file: set COSTSTRUCT_ONEFILE=1 -> dist/CostStruct.exe (lebih lambat dibuka karena
diekstrak dulu ke folder sementara setiap kali dijalankan).

Data pengguna (database, log, cadangan) TIDAK ikut dibundel; dibuat otomatis di
%APPDATA%\\CostStruct saat aplikasi pertama kali dibuka (lihat src/lokasi.py).
"""

import os
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

AKAR = Path(SPECPATH)
SATU_FILE = os.environ.get("COSTSTRUCT_ONEFILE") == "1"
IKON = AKAR / "assets" / "coststruct.ico"

# ifcopenshell: modul `api` memuat usecase secara dinamis, jadi semua submodulnya ikut dikumpulkan.
# Atribut turunan entitas IFC dihitung oleh `ifcopenshell.express.rules.<SKEMA>`, jadi hanya aturan
# skema yang didukung (IFC2X3 & IFC4) yang dibawa; pengurai EXPRESS, MVD, dan gambar 2D tidak dipakai.
SKEMA = ("IFC2X3", "IFC4")
TANPA_IFC = ("ifcopenshell.mvd", "ifcopenshell.draw", "ifcopenshell.validate", "ifcopenshell.simple_spf")
EXPRESS_PERLU = ["ifcopenshell.express", "ifcopenshell.express.rules"] + [f"ifcopenshell.express.rules.{s}" for s in SKEMA]
TANPA_EXPRESS = [
    m for m in collect_submodules("ifcopenshell.express", filter=lambda m: True) if m not in EXPRESS_PERLU
]
modul_ifc = collect_submodules(
    "ifcopenshell",
    filter=lambda m: not m.startswith(TANPA_IFC + ("ifcopenshell.express",)) and "test" not in m,
) + EXPRESS_PERLU
data_ifc = collect_data_files("ifcopenshell", excludes=["express/**", "mvd/**", "**/__pycache__/**"])
# ifcopenshell/express/__init__.py memeriksa keberadaan berkas express_parser.py di disk saat diimpor.
data_ifc += collect_data_files("ifcopenshell", include_py_files=True, includes=["express/express_parser.py"])

a = Analysis(
    [str(AKAR / "src" / "main.py")],
    pathex=[str(AKAR / "src")],
    binaries=[],
    datas=[
        (str(AKAR / "src" / "database" / "schema.sql"), "database"),
        (str(AKAR / "assets" / "mandajaya.png"), "assets"),  # logo perusahaan (sidebar & splash)
    ] + data_ifc,
    hiddenimports=modul_ifc + collect_submodules("rules") + ["PySide6.QtPdf", "PySide6.QtPdfWidgets"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "tkinter", "matplotlib", "pandas", "IPython", "pytest", "experta", "notebook", "scipy", "lxml",
        "cryptography",
        "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets", "PySide6.Qt3DCore", "PySide6.QtQuick",
        "PySide6.QtQml", "PySide6.QtMultimedia", "PySide6.QtCharts", "PySide6.QtDataVisualization",
    ] + list(TANPA_IFC) + TANPA_EXPRESS,
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

opsi_exe = dict(
    name="CostStruct",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,  # aplikasi jendela, tanpa jendela konsol
    disable_windowed_traceback=False,
    icon=str(IKON) if IKON.is_file() else None,
    version=None,
)

if SATU_FILE:
    exe = EXE(pyz, a.scripts, a.binaries, a.datas, [], runtime_tmpdir=None, **opsi_exe)
else:
    exe = EXE(pyz, a.scripts, [], exclude_binaries=True, **opsi_exe)
    coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, upx_exclude=[], name="CostStruct")
