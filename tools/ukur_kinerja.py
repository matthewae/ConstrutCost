"""
Ukur KNF-1 (parsing IFC <= 30 detik) dan KNF-2 (rule engine + RAB < 15 detik) di komputer sendiri.

    python tools/ukur_kinerja.py data/Duplex_A_20110907.ifc data/SampleStructuralModel.ifc
    python tools/buat_ifc_uji.py rumah_50mb.ifc 50      (membuat file uji rumah tinggal +- 50 MB)
    python tools/ukur_kinerja.py rumah_50mb.ifc

Database dibuat di folder sementara, sehingga data aplikasi tidak tersentuh. Hasil ditampilkan sebagai
tabel dan disimpan juga ke hasil_kinerja.csv untuk lampiran BAB IV.
"""

import csv
import os
import platform
import sys
import tempfile
import time
from pathlib import Path

AKAR = Path(__file__).resolve().parents[1]
BATAS_PARSING, BATAS_RULE = 30.0, 15.0


def ukur(path: str) -> dict:
    import estimasi_service as es
    from database.estimasi_repository import get_total_rab
    from database.proyek_repository import create_proyek
    from ifc_reader import buka_dan_validasi, ekstrak_elemen

    t0 = time.perf_counter()
    info = buka_dan_validasi(path, terisolasi=True)
    t1 = time.perf_counter()
    elemen, peringatan = ekstrak_elemen(info.model)
    t2 = time.perf_counter()
    pid = create_proyek(Path(path).stem, str(Path(path).resolve()))
    asli = es.ekstrak_elemen
    es.ekstrak_elemen = lambda m, p=None: (list(elemen), list(peringatan))  # parsing sudah diukur di atas
    try:
        t3 = time.perf_counter()
        hasil = es.jalankan_estimasi(pid, model=info.model)
        t4 = time.perf_counter()
    finally:
        es.ekstrak_elemen = asli
    return {
        "file": Path(path).name,
        "ukuran_mb": round(os.path.getsize(path) / 1e6, 1),
        "elemen": len(elemen),
        "item_rab": hasil["baris_hasil"],
        "validasi_s": round(t1 - t0, 2),
        "ekstraksi_s": round(t2 - t1, 2),
        "parsing_s (KNF-1)": round(t2 - t0, 2),
        "rule_rab_s (KNF-2)": round(t4 - t3, 2),
        "biaya_langsung": round(get_total_rab(pid)),
        "KNF-1": "LULUS" if t2 - t0 <= BATAS_PARSING else "TIDAK",
        "KNF-2": "LULUS" if t4 - t3 < BATAS_RULE else "TIDAK",
    }


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    os.environ["COSTSTRUCT_DATA"] = tempfile.mkdtemp(prefix="coststruct_kinerja_")
    sys.path.insert(0, str(AKAR / "src"))
    from database.init_db import siapkan_database

    siapkan_database()
    print(f"Komputer: {platform.system()} {platform.release()}, {platform.machine()}, {os.cpu_count()} inti CPU, "
          f"Python {platform.python_version()}\n")
    baris = [ukur(p) for p in sys.argv[1:]]
    kolom = list(baris[0])
    lebar = {k: max(len(k), *(len(str(b[k])) for b in baris)) for k in kolom}
    print("  ".join(k.ljust(lebar[k]) for k in kolom))
    for b in baris:
        print("  ".join(str(b[k]).ljust(lebar[k]) for k in kolom))
    with open("hasil_kinerja.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=kolom)
        w.writeheader()
        w.writerows(baris)
    print("\nDisimpan ke hasil_kinerja.csv")


if __name__ == "__main__":
    import multiprocessing

    multiprocessing.freeze_support()
    main()
