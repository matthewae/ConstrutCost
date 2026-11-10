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
import re
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

# Penampil Model 3D (src/gui/penampil3d.py + penampil3d.qml) memakai Qt Quick 3D lewat QQuickWidget.
QT_3D = ["PySide6.QtQml", "PySide6.QtQuick", "PySide6.QtQuickWidgets", "PySide6.QtQuick3D"]

a = Analysis(
    [str(AKAR / "src" / "main.py")],
    pathex=[str(AKAR / "src")],
    binaries=[],
    datas=[(str(AKAR / "src" / "database" / "schema.sql"), "database"),
           (str(AKAR / "src" / "gui" / "penampil3d.qml"), "gui")] + data_ifc,
    hiddenimports=modul_ifc + collect_submodules("rules") + ["PySide6.QtPdf", "PySide6.QtPdfWidgets"] + QT_3D,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "tkinter", "matplotlib", "pandas", "IPython", "pytest", "experta", "notebook", "scipy", "lxml",
        "cryptography",
        "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets", "PySide6.Qt3DCore", "PySide6.QtMultimedia",
        "PySide6.QtCharts", "PySide6.QtDataVisualization", "PySide6.QtQuickControls2", "PySide6.QtQuick3DXr",
    ] + list(TANPA_IFC) + TANPA_EXPRESS,
    noarchive=False,
    optimize=0,
)

# Hook PyInstaller untuk QtQml membawa SEMUA modul QML PySide6 (Controls, WebEngine, Multimedia, Charts, ...)
# beserta pustaka Qt yang mereka perlukan (Qt6WebEngineCore saja ~200 MB). penampil3d.qml hanya mengimpor QtQuick
# dan QtQuick3D, jadi yang dibawa: berkas langsung di folder QtQml, QtQuick, dan QtQuick3D (qmldir + plugin, tanpa
# sub-modul seperti QtQuick/Controls atau QtQuick3D/Helpers) ditambah QtQml.Models & QtQml.WorkerScript yang diimpor
# otomatis oleh QtQml. Pustaka Qt milik modul yang tidak dipakai, importir aset 3D, dan alat debug QML dibuang.
# Yang dipakai penampil 3D: Qt6Qml, Qt6QmlMeta, Qt6QmlModels, Qt6QmlWorkerScript, Qt6Quick, Qt6QuickWidgets,
# Qt6Quick3D, Qt6Quick3DRuntimeRender, Qt6Quick3DUtils, Qt6ShaderTools, Qt6OpenGL (uji mandiri tahap "Model 3D").
QML_DASAR = ("QtQml/", "QtQuick/", "QtQuick3D/")
QML_SUB = ("QtQml/Models/", "QtQml/WorkerScript/")
QT_TIDAK_DIPAKAI = (
    "3D", "Charts", "DataVisualization", "Graphs", "Labs", "Location", "Multimedia", "PdfQuick", "Positioning",
    "QmlLocalStorage", "QmlNetwork", "QmlXmlListModel", "Quick3DAssetImport", "Quick3DAssetUtils", "Quick3DEffects",
    "Quick3DHelpers", "Quick3DParticle", "Quick3DSpatialAudio", "Quick3DXr", "QuickControls2", "QuickDialogs2",
    "QuickEffects", "QuickLayouts", "QuickParticles", "QuickShapes", "QuickTemplates2", "QuickTest", "QuickTimeline",
    "QuickVectorImage", "RemoteObjects", "Scxml", "Sensors", "SpatialAudio", "StateMachine", "Test", "TextToSpeech",
    "VirtualKeyboard", "WaylandCompositor", "WebChannel", "WebEngine", "WebSockets", "WebView",
)


def qml_dipakai(tujuan: str) -> bool:
    t = tujuan.replace("\\", "/")
    if not t.startswith("PySide6/"):
        return True
    if "/plugins/assetimporters/" in t or "/plugins/qmltooling/" in t:
        return False
    m = re.match(r"(?:lib)?Qt6(\w+)\.(?:dll|so|dylib)", t.rsplit("/", 1)[-1])
    if m and m.group(1).startswith(QT_TIDAK_DIPAKAI):
        return False
    i = t.find("/qml/")
    if i < 0:
        return True
    rel = t[i + len("/qml/"):]
    if "/" not in rel:  # builtins.qmltypes, jsroot.qmltypes
        return True
    if rel.startswith(QML_SUB):
        return True
    return any(rel.startswith(d) and "/" not in rel[len(d):] for d in QML_DASAR)


a.datas = [x for x in a.datas if qml_dipakai(x[0])]
a.binaries = [x for x in a.binaries if qml_dipakai(x[0])]
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
