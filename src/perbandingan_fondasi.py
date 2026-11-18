"""
Perbandingan jenis fondasi kolom untuk export (sheet PERBANDINGAN_FONDASI), tanpa mengubah model maupun RAB.

Rule engine dijalankan ulang di memori untuk setiap jenis fondasi (sesuai model IFC, footplate, cakar ayam
Sedijatmo) memakai elemen proyek yang tersimpan. Yang dilaporkan hanya pekerjaan yang volumenya berbeda antar
jenis; pekerjaan lain sama di semua jenis. Biaya langsung tiap jenis = biaya langsung RAB sekarang − pekerjaan
berbeda (jenis yang sedang dipakai) + pekerjaan berbeda (jenis itu), sehingga edit manual, harga khusus, dan item
katalog di RAB tetap terbawa. Tipe penulangan baru yang sempat dibuat dibatalkan (rollback).
"""

import copy
from dataclasses import replace

from database.estimasi_repository import _connect
from database.material_repository import kode_elemen
from database.parameter_repository import muat_parameter
from database.penulangan_repository import pasang_tipe
from rules import proses_semua
from rules.parameter import JENIS_FONDASI_KOLOM

URUT_JENIS = tuple(JENIS_FONDASI_KOLOM)


def _hitung(conn, proyek_id: int, elemen: list, parameter, harga, kode) -> dict:
    """({pekerjaan_id: [volume, jumlah]}, catatan pilihan fondasi) hasil rule engine untuk satu set parameter."""
    pasang_tipe(conn, proyek_id, elemen, parameter.batas_kemiringan_dak)
    _konteks, keluaran, dilewati = proses_semua(elemen, parameter)
    per = {}
    for el, hasil in keluaran:
        peta = kode_elemen(*kode, el.get("material"), conn)
        for h in hasil:
            pid = peta.get(h.kode)
            if pid is None:
                continue
            d = per.setdefault(pid, [0.0, 0.0])
            d[0] += h.volume
            d[1] += h.volume * harga.get(pid, 0.0)
    teks = next((x for x in dilewati if x.startswith("Jenis fondasi kolom")), None)
    return per, teks


def bandingkan(proyek_id: int) -> dict | None:
    """{'jenis': [label], 'aktif': indeks jenis dipakai RAB, 'baris': [{kode, nama, satuan, kategori, volume[],
    jumlah[]}], 'beda': [total pekerjaan berbeda per jenis], 'catatan': [teks per jenis]}; None bila proyek tidak
    punya kolom struktur / fondasi (semua jenis sama)."""
    from estimasi_service import _baris_ke_elemen, _harga_dan_kode

    parameter = muat_parameter(proyek_id)
    conn = _connect()
    try:
        elemen = [_baris_ke_elemen(r) for r in conn.execute(
            "SELECT * FROM elemen_proyek WHERE proyek_id = ? ORDER BY id", (proyek_id,))]
        if not any(e["kelas"] in ("COLUMN", "FOOTING", "PILE") for e in elemen):
            return None
        harga, kode = _harga_dan_kode(conn, proyek_id)
        hasil, catatan = [], []
        for jenis in URUT_JENIS:
            per, teks = _hitung(conn, proyek_id, copy.deepcopy(elemen), replace(parameter, fondasi_kolom_jenis=jenis),
                                harga, kode)
            hasil.append(per)
            catatan.append(teks)
        conn.rollback()  # tipe penulangan sementara tidak disimpan
        pids = sorted({pid for per in hasil for pid in per})
        beda = [pid for pid in pids
                if max(per.get(pid, [0.0])[0] for per in hasil) - min(per.get(pid, [0.0])[0] for per in hasil) > 1e-6]
        info = {}
        if beda:
            tanda = ",".join("?" * len(beda))
            info = {r["id"]: r for r in conn.execute(
                f"SELECT id, kode_ahsp, nama_pekerjaan, satuan, kategori FROM pekerjaan WHERE id IN ({tanda})", beda)}
    finally:
        conn.close()
    if not beda:
        return None
    baris = []
    for pid in beda:
        r = info[pid]
        baris.append({
            "kode": r["kode_ahsp"], "nama": r["nama_pekerjaan"], "satuan": r["satuan"], "kategori": r["kategori"],
            "volume": [per.get(pid, [0.0, 0.0])[0] for per in hasil],
            "jumlah": [per.get(pid, [0.0, 0.0])[1] for per in hasil],
        })
    from rab_rinci import urutan_kategori

    baris.sort(key=lambda b: (urutan_kategori(b["kategori"]), b["kode"]))
    return {
        "jenis": [JENIS_FONDASI_KOLOM[j] for j in URUT_JENIS],
        "aktif": URUT_JENIS.index(parameter.fondasi_kolom_jenis),
        "baris": baris,
        "beda": [sum(b["jumlah"][i] for b in baris) for i in range(len(URUT_JENIS))],
        "catatan": catatan,
    }
