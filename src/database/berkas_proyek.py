"""
KF-7 / UC-06: simpan & buka proyek sebagai file .coststruct.

File .coststruct adalah arsip ZIP berisi:
- proyek.json : info proyek, parameter aturan, elemen (termasuk dimensi yang diubah pengguna),
                tipe penulangan, biaya tidak langsung, hasil estimasi (volume, harga khusus,
                catatan, rumus), dan potret harga satuan + komponen analisa setiap pekerjaan yang
                dipakai (harga saat file disimpan).
- model.ifc   : salinan file IFC (opsional), supaya proyek bisa dibuka & dihitung ulang di
                komputer lain.

Pekerjaan dirujuk dengan kode (mis. BTN.KOLOM), bukan id database, sehingga file bisa dibuka di
database lain. Harga master di komputer tujuan tidak ditimpa; bila berbeda, halaman Hasil Estimasi
menampilkan banner "harga satuan sudah berubah" seperti biasa (KF-5).
Fungsi ekspor/impor yang sama dipakai untuk menduplikasi proyek (KF-9).
"""

import json
import re
import shutil
import zipfile
from datetime import datetime
from pathlib import Path

from aktivitas import catat
from database.estimasi_repository import BUK_RATE, _connect

FORMAT = "coststruct-proyek"
VERSI = 1
EKSTENSI = ".coststruct"
_INFO = ("nama_proyek", "path_file_ifc", "lokasi", "pemilik", "tahun_anggaran", "parameter")


class BerkasTidakValid(ValueError):
    """File proyek tidak bisa dibuka. Pesannya siap ditampilkan ke pengguna (KF-14)."""


def _baris(conn, tabel: str, proyek_id: int) -> list:
    rows = [dict(r) for r in conn.execute(f"SELECT * FROM {tabel} WHERE proyek_id = ? ORDER BY id", (proyek_id,))]
    for r in rows:
        r.pop("proyek_id", None)
    return rows


def ekspor_data(proyek_id: int) -> dict:
    conn = _connect()
    try:
        pr = conn.execute(f"SELECT {', '.join(_INFO)} FROM proyek WHERE id = ?", (proyek_id,)).fetchone()
        if pr is None:
            raise BerkasTidakValid("Proyek tidak ditemukan.")
        kode = {r["id"]: r["kode_ahsp"] for r in conn.execute("SELECT id, kode_ahsp FROM pekerjaan")}
        hasil = _baris(conn, "hasil_estimasi", proyek_id)
        for h in hasil:
            h["kode_pekerjaan"] = kode.get(h.pop("pekerjaan_id"))
        dipakai = sorted({h["kode_pekerjaan"] for h in hasil if h["kode_pekerjaan"]})
        harga = {}
        for k in dipakai:
            p = conn.execute(
                "SELECT id, nama_pekerjaan, kategori, satuan FROM pekerjaan WHERE kode_ahsp = ?", (k,)
            ).fetchone()
            komp = [dict(r) for r in conn.execute(
                "SELECT tipe, nama_komponen, satuan, koefisien, harga_satuan FROM komponen_harga "
                "WHERE pekerjaan_id = ? ORDER BY id", (p["id"],)
            )]
            harga[k] = {
                "nama_pekerjaan": p["nama_pekerjaan"], "kategori": p["kategori"], "satuan": p["satuan"],
                "harga_satuan": sum(c["koefisien"] * c["harga_satuan"] for c in komp) * (1 + BUK_RATE),
                "komponen": komp,
            }
        return {
            "format": FORMAT,
            "versi": VERSI,
            "disimpan": datetime.now().isoformat(timespec="seconds"),
            "proyek": dict(pr),
            "elemen": _baris(conn, "elemen_proyek", proyek_id),
            "tipe_penulangan": _baris(conn, "tipe_penulangan", proyek_id),
            "biaya_tidak_langsung": _baris(conn, "biaya_tidak_langsung", proyek_id),
            "hasil": hasil,
            "harga": harga,
        }
    finally:
        conn.close()


def _insert(conn, tabel: str, row: dict) -> int:
    kolom = list(row)
    return conn.execute(
        f"INSERT INTO {tabel} ({', '.join(kolom)}) VALUES ({', '.join('?' * len(kolom))})",
        [row[k] for k in kolom],
    ).lastrowid


def _kolom_tabel(conn, tabel: str) -> set:
    return {r[1] for r in conn.execute(f"PRAGMA table_info({tabel})")}


def impor_data(data: dict, nama: str | None = None, path_ifc: str | None = None) -> int:
    """Buat proyek baru dari data hasil ekspor_data(). Return id proyek baru."""
    if not isinstance(data, dict) or data.get("format") != FORMAT:
        raise BerkasTidakValid("File ini bukan file proyek CostStruct.")
    if int(data.get("versi", 0)) > VERSI:
        raise BerkasTidakValid("File proyek dibuat oleh versi CostStruct yang lebih baru. Perbarui aplikasi.")
    from database.init_db import pastikan_skema
    from database.seed_data import seed_pekerjaan

    conn = _connect()
    try:
        pastikan_skema(conn)
    finally:
        conn.close()
    seed_pekerjaan()

    conn = _connect()
    try:
        conn.execute("BEGIN")
        info = {k: v for k, v in (data.get("proyek") or {}).items() if k in _INFO}
        info["nama_proyek"] = (nama or info.get("nama_proyek") or "Proyek").strip()
        if path_ifc is not None:
            info["path_file_ifc"] = path_ifc
        pid = _insert(conn, "proyek", info)

        def bersih(tabel, row, buang=("id",)):
            ada = _kolom_tabel(conn, tabel)
            return {k: v for k, v in row.items() if k in ada and k not in buang}

        peta_tipe = {}
        for t in data.get("tipe_penulangan", []):
            peta_tipe[t["id"]] = _insert(conn, "tipe_penulangan", {**bersih("tipe_penulangan", t), "proyek_id": pid})
        peta_elemen = {}
        for e in data.get("elemen", []):
            row = {**bersih("elemen_proyek", e), "proyek_id": pid}
            row["tipe_id"] = peta_tipe.get(e.get("tipe_id"))
            peta_elemen[e["id"]] = _insert(conn, "elemen_proyek", row)
        for b in data.get("biaya_tidak_langsung", []):
            _insert(conn, "biaya_tidak_langsung", {**bersih("biaya_tidak_langsung", b), "proyek_id": pid})

        kode_ke_id = {r["kode_ahsp"]: r["id"] for r in conn.execute("SELECT id, kode_ahsp FROM pekerjaan")}
        for h in data.get("hasil", []):
            k = h.get("kode_pekerjaan")
            if k not in kode_ke_id:  # pekerjaan tidak dikenal di database ini: buat dari potret harga
                snap = (data.get("harga") or {}).get(k)
                if not snap:
                    raise BerkasTidakValid(f"Pekerjaan '{k}' tidak dikenal dan tidak ada data harganya di file.")
                kode_ke_id[k] = _insert(conn, "pekerjaan", {
                    "kode_ahsp": k, "nama_pekerjaan": snap["nama_pekerjaan"], "kategori": snap["kategori"],
                    "satuan": snap["satuan"], "catatan": "Dari file proyek",
                })
                for c in snap.get("komponen", []):
                    _insert(conn, "komponen_harga", {**c, "pekerjaan_id": kode_ke_id[k]})
            row = {**bersih("hasil_estimasi", h, ("id", "kode_pekerjaan")), "proyek_id": pid, "pekerjaan_id": kode_ke_id[k]}
            row["elemen_id"] = peta_elemen.get(h.get("elemen_id"))
            _insert(conn, "hasil_estimasi", row)
        conn.commit()
        return pid
    except BerkasTidakValid:
        conn.rollback()
        raise
    except (KeyError, TypeError, ValueError) as e:
        conn.rollback()
        raise BerkasTidakValid(f"Isi file proyek rusak atau tidak lengkap ({e}).") from None
    finally:
        conn.close()


def duplikat_proyek(proyek_id: int, nama_baru: str) -> int:
    """KF-9: salin proyek lengkap (elemen, tipe penulangan, biaya, hasil, parameter)."""
    if not nama_baru.strip():
        raise BerkasTidakValid("Nama proyek tidak boleh kosong.")
    data = ekspor_data(proyek_id)
    pid = impor_data(data, nama=nama_baru)
    catat("proyek", f"Proyek diduplikasi dari '{data['proyek']['nama_proyek']}' menjadi '{nama_baru.strip()}'", pid)
    return pid


def simpan_berkas(proyek_id: int, path, sertakan_ifc: bool = True) -> Path:
    """Tulis file .coststruct. Ditulis ke file sementara dulu agar file lama tidak rusak bila gagal."""
    path = Path(path)
    if path.suffix.lower() != EKSTENSI:
        path = path.with_suffix(EKSTENSI)
    data = ekspor_data(proyek_id)
    ifc = data["proyek"].get("path_file_ifc")
    sementara = path.with_name(path.name + ".tmp")
    try:
        with zipfile.ZipFile(sementara, "w", compression=zipfile.ZIP_DEFLATED) as z:
            if sertakan_ifc and ifc and Path(ifc).is_file():
                z.write(ifc, "model.ifc")
                data["ifc_disertakan"] = Path(ifc).name
            z.writestr("proyek.json", json.dumps(data, ensure_ascii=False, indent=1))
        sementara.replace(path)
    finally:  # gagal di tengah jalan (IFC / file tujuan terkunci): jangan tinggalkan file .tmp
        sementara.unlink(missing_ok=True)
    catat("berkas", f"Proyek disimpan ke file {path}" + (" (beserta model IFC)" if "ifc_disertakan" in data else ""), proyek_id)
    return path


def baca_berkas(path) -> dict:
    """Baca isi file .coststruct (tanpa mengubah database)."""
    path = Path(path)
    if not path.is_file():
        raise BerkasTidakValid(f"File tidak ditemukan:\n{path}")
    try:
        with zipfile.ZipFile(path) as z:
            data = json.loads(z.read("proyek.json").decode("utf-8"))
            data["_ada_ifc"] = "model.ifc" in z.namelist()
    except (zipfile.BadZipFile, KeyError, UnicodeDecodeError, json.JSONDecodeError):
        raise BerkasTidakValid("File ini bukan file proyek CostStruct atau isinya rusak.") from None
    if not isinstance(data, dict) or data.get("format") != FORMAT:
        raise BerkasTidakValid("File ini bukan file proyek CostStruct.")
    return data


def buka_berkas(path, folder_ifc=None, nama: str | None = None) -> int:
    """Buka file .coststruct menjadi proyek baru. Bila file memuat model IFC, model diekstrak ke
    `folder_ifc` (bawaan: folder file proyek) dan proyek merujuk ke salinan itu."""
    path = Path(path)
    data = baca_berkas(path)
    path_ifc = None
    if data.get("_ada_ifc"):
        folder = Path(folder_ifc) if folder_ifc else path.parent
        folder.mkdir(parents=True, exist_ok=True)
        # hanya nama file: nama di dalam file proyek tidak boleh menulis ke luar folder tujuan (..\, C:\)
        nama_ifc = re.split(r"[\\/:]", str(data.get("ifc_disertakan") or ""))[-1].strip(" .")
        if not nama_ifc.lower().endswith(".ifc"):
            nama_ifc = f"{path.stem}.ifc"
        tujuan = folder / nama_ifc
        n = 1
        while tujuan.exists():
            tujuan = folder / f"{Path(nama_ifc).stem} ({n}).ifc"
            n += 1
        with zipfile.ZipFile(path) as z, z.open("model.ifc") as src, open(tujuan, "wb") as dst:
            shutil.copyfileobj(src, dst)
        path_ifc = str(tujuan)
    pid = impor_data(data, nama=nama, path_ifc=path_ifc)
    catat("berkas", f"Proyek dibuka dari file {path}" + (f", model IFC disalin ke {path_ifc}" if path_ifc else ""), pid)
    return pid
