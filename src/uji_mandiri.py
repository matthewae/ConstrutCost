"""
Uji mandiri hasil build .exe (KNF-8):

    CostStruct.exe --uji-mandiri [file.ifc] [--keluar FOLDER]

Menjalankan seluruh alur utama tanpa antarmuka di folder data SEMENTARA (database pengguna tidak
tersentuh): siapkan database + harga HSPK -> validasi IFC di proses anak (KNF-4) -> parsing & rule
engine -> export Excel & PDF -> simpan & buka file .coststruct. Laporan ditulis ke
`uji_mandiri.txt` di folder keluaran; kode keluar 0 bila semua tahap berhasil.
Tanpa file IFC, dipakai model kecil buatan (dinding, pelat, kolom, pintu) yang dibuat di tempat.
"""

import json
import os
import tempfile
import time
import traceback
from pathlib import Path


def _model_buatan(folder: Path) -> Path:
    """Model IFC4 kecil: 1 lantai, dinding 6 m, pelat 6 x 4 m, kolom 20/25."""
    import ifcopenshell.api as api

    f = api.run("project.create_file", version="IFC4")
    proj = api.run("root.create_entity", f, ifc_class="IfcProject", name="Uji Mandiri")
    api.run("unit.assign_unit", f, length={"is_metric": True, "raw": "METERS"})  # profil kolom dalam meter
    model = api.run("context.add_context", f, context_type="Model")
    body = api.run("context.add_context", f, context_type="Model", context_identifier="Body",
                   target_view="MODEL_VIEW", parent=model)
    site = api.run("root.create_entity", f, ifc_class="IfcSite")
    gedung = api.run("root.create_entity", f, ifc_class="IfcBuilding")
    lantai = api.run("root.create_entity", f, ifc_class="IfcBuildingStorey", name="Lantai 1")
    lantai.Elevation = 0.0
    api.run("aggregate.assign_object", f, products=[site], relating_object=proj)
    api.run("aggregate.assign_object", f, products=[gedung], relating_object=site)
    api.run("aggregate.assign_object", f, products=[lantai], relating_object=gedung)
    dinding = api.run("root.create_entity", f, ifc_class="IfcWall", name="Dinding 1")
    api.run("geometry.assign_representation", f, product=dinding, representation=api.run(
        "geometry.add_wall_representation", f, context=body, length=6, height=3, thickness=0.15))
    pelat = api.run("root.create_entity", f, ifc_class="IfcSlab", name="Pelat 1", predefined_type="FLOOR")
    api.run("geometry.assign_representation", f, product=pelat, representation=api.run(
        "geometry.add_slab_representation", f, context=body, depth=0.12,
        polyline=[(0.0, 0.0), (6.0, 0.0), (6.0, 4.0), (0.0, 4.0)]))
    kolom = api.run("root.create_entity", f, ifc_class="IfcColumn", name="Kolom K1")
    api.run("geometry.assign_representation", f, product=kolom, representation=api.run(
        "geometry.add_profile_representation", f, context=body,
        profile=f.createIfcRectangleProfileDef("AREA", None, None, 0.2, 0.25), depth=3.0))
    api.run("spatial.assign_container", f, products=[dinding, pelat, kolom], relating_structure=lantai)
    path = folder / "model_uji.ifc"
    f.write(str(path))
    return path


def jalankan(path_ifc: str | None = None, folder_keluar: str | None = None) -> dict:
    """Jalankan semua tahap. Return {"berhasil": bool, "tahap": [(nama, ok, keterangan, detik)]}."""
    data = Path(tempfile.mkdtemp(prefix="coststruct_uji_"))
    os.environ["COSTSTRUCT_DATA"] = str(data)  # sebelum modul database diimpor
    keluar = Path(folder_keluar or Path.cwd())
    keluar.mkdir(parents=True, exist_ok=True)
    tahap, konteks = [], {}

    def langkah(nama, fungsi):
        t0 = time.perf_counter()
        try:
            ket = fungsi()
            tahap.append((nama, True, ket or "", round(time.perf_counter() - t0, 2)))
            return True
        except Exception as e:
            tahap.append((nama, False, f"{type(e).__name__}: {e}\n{traceback.format_exc()}", round(time.perf_counter() - t0, 2)))
            return False

    def db():
        from database.init_db import siapkan_database
        from lokasi import path_database

        siapkan_database()
        return f"database {path_database()}"

    def ifc():
        konteks["ifc"] = Path(path_ifc) if path_ifc else _model_buatan(data)
        from ifc_reader import buka_dan_validasi

        info = buka_dan_validasi(str(konteks["ifc"]), terisolasi=True)  # proses anak (spawn)
        return f"{info.nama_file}: {info.skema}, {info.total_elemen} elemen"

    def estimasi():
        from aktivitas import rp
        from database.biaya_repository import ringkasan_biaya
        from database.proyek_repository import create_proyek
        from estimasi_service import jalankan_estimasi

        pid = create_proyek("Uji Mandiri", str(konteks["ifc"]))
        r = jalankan_estimasi(pid)
        konteks["pid"] = pid
        total = ringkasan_biaya(pid)["dibulatkan"]
        if r["baris_hasil"] == 0:
            raise RuntimeError("tidak ada kuantitas yang terhitung")
        return f"{r['elemen']} elemen, {r['baris_hasil']} item, total RAB {rp(total)}"

    def export():
        from export_service import OpsiExport, ambil_data_export, export_excel, export_pdf

        d = ambil_data_export(konteks["pid"])
        xlsx = export_excel(keluar / "uji_mandiri.xlsx", d, {}, OpsiExport())
        pdf = export_pdf(keluar / "uji_mandiri.pdf", d, {}, OpsiExport())
        return f"{Path(xlsx).name} ({Path(xlsx).stat().st_size // 1024} KB), {Path(pdf).name} ({Path(pdf).stat().st_size // 1024} KB)"

    def berkas():
        from database.berkas_proyek import buka_berkas, simpan_berkas

        path = simpan_berkas(konteks["pid"], data / "uji.coststruct")
        baru = buka_berkas(path, folder_ifc=data / "buka")
        return f"{path.name} disimpan & dibuka kembali sebagai proyek #{baru}"

    for nama, fungsi in (("Database & harga HSPK", db), ("Validasi IFC (proses anak)", ifc),
                         ("Parsing & rule engine", estimasi), ("Export Excel & PDF", export),
                         ("Simpan & buka file proyek", berkas)):
        if not langkah(nama, fungsi):
            break

    hasil = {"berhasil": all(ok for _, ok, _, _ in tahap) and len(tahap) == 5, "tahap": tahap, "folder_data": str(data)}
    baris = ["UJI MANDIRI COSTSTRUCT", ""]
    for nama, ok, ket, detik in tahap:
        baris.append(f"[{'OK' if ok else 'GAGAL'}] {nama} ({detik} s) - {ket}")
    baris += ["", "HASIL: " + ("SEMUA TAHAP BERHASIL" if hasil["berhasil"] else "ADA TAHAP YANG GAGAL")]
    (keluar / "uji_mandiri.txt").write_text("\n".join(baris), encoding="utf-8")
    (keluar / "uji_mandiri.json").write_text(json.dumps(hasil, ensure_ascii=False, indent=1), encoding="utf-8")
    return hasil
