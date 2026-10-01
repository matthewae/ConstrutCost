"""
Penyimpanan daftar material & harga pilihan pengguna (merk semen, harga, dst.)
untuk CostStruct.

Disimpan sebagai JSON di tabel preferensi yang sudah ada (get_pref / set_pref),
jadi TIDAK perlu mengubah skema database atau menjalankan ulang init_db.py.

Bentuk satu material:
    {
        "id": "a1b2...",          # pengenal unik
        "material": "Semen",      # jenis material
        "merk": "Tiga Roda",
        "satuan": "sak",
        "harga": 68000.0,         # harga per satuan, dalam Rupiah
        "utama": True,            # merk utama untuk jenis material ini
    }

Fungsi get_material_utama() disiapkan supaya nanti mudah dipakai oleh
perhitungan RAB (rule engine) bila harga material ingin dihubungkan.
"""

import json
import uuid

from database.preferensi_repository import get_pref, set_pref

KUNCI_PREF = "daftar_material"


def buat_id() -> str:
    return uuid.uuid4().hex


def muat_daftar_material() -> list:
    """Baca daftar material. Data rusak/kosong menghasilkan list kosong, bukan error."""
    mentah = get_pref(KUNCI_PREF, "[]")
    try:
        data = json.loads(mentah) if mentah else []
    except (TypeError, ValueError):
        return []
    if not isinstance(data, list):
        return []

    hasil = []
    for d in data:
        if not isinstance(d, dict):
            continue
        try:
            hasil.append({
                "id": str(d.get("id") or buat_id()),
                "material": str(d["material"]).strip(),
                "merk": str(d["merk"]).strip(),
                "satuan": str(d.get("satuan", "")).strip(),
                "harga": float(d.get("harga", 0)),
                "utama": bool(d.get("utama", False)),
            })
        except (KeyError, TypeError, ValueError):
            continue
    return hasil


def simpan_daftar_material(daftar: list) -> None:
    set_pref(KUNCI_PREF, json.dumps(daftar, ensure_ascii=False))


def get_material_utama(jenis: str):
    """Merk utama untuk satu jenis material (mis. 'Semen'), atau None bila belum ada."""
    sejenis = [m for m in muat_daftar_material() if m["material"].lower() == jenis.strip().lower()]
    if not sejenis:
        return None
    for m in sejenis:
        if m["utama"]:
            return m
    return sejenis[0]
