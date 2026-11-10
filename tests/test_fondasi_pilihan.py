"""Pilihan jenis fondasi kolom (sesuai model / footplate / cakar ayam Sedijatmo) tanpa mengubah model, sumuran yang
dimodelkan, bekisting balok berbasis relasi geometri, dan sheet PERBANDINGAN_FONDASI."""

import math
from dataclasses import replace

import pytest

from relasi import analisis_balok, fondasi_di_bawah_kolom
from rules import PARAMETER_DEFAULT as P
from rules import proses_semua
from rules.parameter import FONDASI_CAKAR, FONDASI_FOOTPLATE, FONDASI_MODEL


def _total(elemen, p=P):
    konteks, keluaran, dilewati = proses_semua(elemen, p)
    total, per_el = {}, {}
    for e, hasil in keluaran:
        per_el[e["global_id"]] = {h.kode for h in hasil}
        for h in hasil:
            total[h.kode] = total.get(h.kode, 0.0) + h.volume
    return total, per_el, dilewati, konteks


# ---------------------------------------------------------------- relasi geometri balok


def test_relasi_balok_di_atas_dinding_dan_pelat_per_sisi():
    dinding = [(0, -0.075, 0, 4, 0.075, 3.2)]  # dinding sepanjang sumbu X, puncak +3,20
    pelat = [(0, 0.10, 3.38, 4, 3.0, 3.50)]  # pelat t = 12 cm hanya di sisi +Y balok tepi, puncak rata balok
    balok = {
        "RING": (0, -0.10, 3.2, 4, 0.10, 3.5),  # duduk di atas dinding, tanpa pelat
        "TEPI": (0, -0.10, 3.2, 4, 0.10, 3.5),
        "LATEI": (1, -0.075, 2.1, 2.5, 0.075, 2.25),  # di dalam dinding (puncak dinding di atas balok)
    }
    r = analisis_balok({"RING": balok["RING"], "LATEI": balok["LATEI"]}, dinding, [])
    assert r["RING"] == {"ditopang": 4.0, "pelat_sisi": [None, None]}
    assert r["LATEI"]["ditopang"] == 0.0  # balok latei tetap berbekisting alas di atas bukaan
    t = analisis_balok({"TEPI": balok["TEPI"]}, dinding, pelat)["TEPI"]
    assert t["pelat_sisi"] == [None, pytest.approx(0.12)]


def _balok(gid, info, **kw):
    e = dict(kelas="BEAM", global_id=gid, nama=gid, predefined_type="BEAM", lantai="Lantai 2", elevasi_lantai=3.5,
             lebar=0.2, tinggi=0.3, panjang=4.0, volume=0.24, info_balok=info)
    e.update(kw)
    return e


def test_bekisting_balok_ring_di_atas_dinding_dan_balok_tepi():
    elemen = [_balok("RING", {"ditopang": 4.0, "pelat_sisi": [None, None]}),
              _balok("TEPI", {"ditopang": 4.0, "pelat_sisi": [None, 0.12]}, tinggi=0.4, lebar=0.25, volume=0.4),
              _balok("TENGAH", {"ditopang": 0.0, "pelat_sisi": [0.12, 0.12]}, tinggi=0.4, lebar=0.25, volume=0.4)]
    _, keluaran, _ = proses_semua(elemen, P)
    bsk = {e["global_id"]: next(h for h in hasil if h.kode == "BSK.BALOK") for e, hasil in keluaran}
    assert bsk["RING"].volume == pytest.approx(2 * 0.3 * 4.0)  # alas = dinding: hanya dua sisi
    assert "duduk di atas pasangan dinding" in bsk["RING"].rumus
    # balok yang dicor bersama pelat tetap berbekisting alas walau ada dinding di bawahnya; sisi luar penuh
    assert bsk["TEPI"].volume == pytest.approx(0.25 * 4 + (0.4 + 0.28) * 4)
    assert bsk["TENGAH"].volume == pytest.approx(0.25 * 4 + 2 * 0.28 * 4)


# ---------------------------------------------------------------- elemen sintetis untuk pilihan fondasi


def _kolom(gid, grup, urut=1, n=1, peran="kolom", fondasi=(), **kw):
    e = dict(kelas="COLUMN", global_id=gid, nama=gid, predefined_type="COLUMN", lantai="01 Lantai 1",
             elevasi_lantai=0.0, lebar=0.3, tebal=0.3, tinggi=3.5, volume=0.315, kolom_grup=grup,
             info_kolom={"grup": grup, "fungsi": "utama", "urut": urut, "n": n, "peran": peran, "duplikat": None,
                         "fondasi": list(fondasi)})
    e.update(kw)
    return e


def _fondasi(gid, pre, kolom, **kw):
    e = dict(kelas="FOOTING", global_id=gid, nama=gid, predefined_type=pre, lantai="00 Fondasi", elevasi_lantai=-1.5,
             panjang=0.9, lebar=0.9, tebal=0.25, volume=0.2025, keliling=3.6, luas=0.81,
             info_fondasi={"kolom": kolom} if kolom else None)
    e.update(kw)
    return e


def _model():
    """Tiga titik kolom: A1 footplate model + pedestal, A2 sumuran + poer model + pedestal, A3 tanpa fondasi.
    Batu kali di bawah dinding, sloof, lantai kerja model, pelat lantai dasar beton, carport di luar bangunan."""
    return [
        _kolom("PD-A1", "K-A1", 1, 2, "pedestal", ["FP-A1"], lantai="00 Fondasi", elevasi_lantai=-1.5, tinggi=1.1,
               volume=0.099),
        _kolom("K-A1", "K-A1", 2, 2, "kolom", ["FP-A1"]),
        _kolom("PD-A2", "K-A2", 1, 2, "pedestal", ["SM-A2", "PC-A2"], lantai="00 Fondasi", elevasi_lantai=-1.5,
               tinggi=1.1, volume=0.099),
        _kolom("K-A2", "K-A2", 2, 2, "kolom", ["SM-A2", "PC-A2"]),
        _kolom("K-A3", "K-A3"),
        _fondasi("FP-A1", "PAD_FOOTING", "K-A1"),
        _fondasi("SM-A2", "CAISSON_FOUNDATION", "K-A2", nama="Sumuran SM-1 D0.80 H2.00", panjang=0.8, lebar=0.8,
                 tebal=2.0, volume=1.0053),
        _fondasi("PC-A2", "PILE_CAP", "K-A2", nama="Poer PC-1", tebal=0.35, volume=0.2835),
        _fondasi("BK-1", "STRIP_FOOTING", None, nama="Batu Kali BK-1", panjang=10.0, lebar=0.7, tebal=0.8,
                 volume=4.0),
        dict(kelas="BEAM", global_id="S1", nama="Sloof S1 20/30", predefined_type="BEAM", lantai="01 Lantai 1",
             elevasi_lantai=0.0, lebar=0.2, tinggi=0.3, panjang=10.0, volume=0.6),
        dict(kelas="EARTHWORK", global_id="LK-A1", nama="Lantai Kerja FP1 A1", predefined_type="LANTAI_KERJA",
             lantai="00 Fondasi", elevasi_lantai=-1.5, volume=0.04, luas=0.81),
        dict(kelas="SLAB", global_id="PL", nama="Pelat Lantai Dasar t=12cm", predefined_type="FLOOR",
             lantai="01 Lantai 1", elevasi_lantai=0.0, tebal=0.12, luas=50.0, volume=6.0, di_luar_bangunan=0),
        dict(kelas="SLAB", global_id="CP", nama="Rabat Beton Bertulang Wiremesh Carport t=7cm", predefined_type="FLOOR",
             lantai="01 Lantai 1", elevasi_lantai=0.0, tebal=0.07, luas=30.0, volume=2.1, di_luar_bangunan=1),
        dict(kelas="WALL", global_id="W1", nama="Dinding Bata 1/2 Batu", predefined_type="STANDARD",
             lantai="01 Lantai 1", elevasi_lantai=0.0, panjang=10.0, tebal=0.15, tinggi=3.0, luas=30.0,
             volume=4.5, eksternal=True),
    ]


def test_sumuran_model_tanpa_bekisting_dan_dengan_analisa_sumuran():
    total, per_el, _, _ = _total(_model())
    assert per_el["SM-A2"] == {"BTN.SUMURAN", "TNH.GALIAN.3"}  # tanpa BSK.FONDASI, tanpa tipe tulangan
    assert total["BTN.SUMURAN"] == pytest.approx(1.0053)
    assert {"BTN.FONDASI", "BSK.FONDASI"} <= per_el["PC-A2"]  # poer = beton fondasi biasa


def test_pilihan_footplate_mengganti_sumuran_dan_poer_saja():
    p = replace(P, fondasi_kolom_jenis=FONDASI_FOOTPLATE)
    model, _, _, _ = _total(_model())
    total, per_el, dilewati, k = _total(_model(), p)
    assert not per_el["SM-A2"] and not per_el["PC-A2"]  # sumuran & poer model tidak dihitung
    assert per_el["FP-A1"] >= {"BTN.FONDASI", "BSK.FONDASI"}  # footplate rencana tetap dipakai
    assert "BTN.FONDASI" not in per_el["K-A1"]  # kolom A1 sudah punya footplate model
    # A2 (pedestal ada) dan A3 (tanpa pedestal) mendapat footplate turunan 0,8 x 0,8 x 0,25 (1 lantai)
    assert {"BTN.FONDASI", "BSK.FONDASI", "LTK.FONDASI", "TNH.URUG.KEMBALI"} <= per_el["K-A2"]
    assert "BTN.KOLOM" in per_el["K-A3"] and total["BTN.FONDASI"] == pytest.approx(
        model["BTN.FONDASI"] - 0.2835 + 2 * 0.8 * 0.8 * 0.25)
    # lantai kerja footplate turunan tidak digugurkan oleh lantai kerja yang dimodelkan
    assert total["LTK.FONDASI"] == pytest.approx(0.04 + 2 * 0.64 * P.tebal_lantai_kerja)
    assert "BTN.SUMURAN" not in total
    assert k.pilihan_fondasi["footplate_baru"] == 2 and any(d.startswith("Jenis fondasi kolom: footplate") for d in dilewati)


def test_pilihan_cakar_ayam_sedijatmo():
    p = replace(P, fondasi_kolom_jenis=FONDASI_CAKAR)
    total, per_el, dilewati, k = _total(_model(), p)
    for gid in ("FP-A1", "SM-A2", "PC-A2", "BK-1", "S1", "LK-A1", "PD-A1", "PD-A2"):
        assert not per_el[gid], gid  # fondasi, sloof, lantai kerja fondasi, pedestal: digantikan
    for kode in ("BTN.FONDASI", "BTN.SUMURAN", "FDN.BATUKALI", "BTN.SLOOF", "LTK.FONDASI"):
        assert kode not in total
    # pelat beton lantai dasar digantikan pelat cakar ayam; carport di luar bangunan tetap
    assert "BTN.PELAT" not in per_el["PL"] and "BTN.CAKAR.PELAT" in per_el["PL"]
    assert "BTN.CAKAR.PELAT" not in per_el["CP"] and "BTN.PELAT" in per_el["CP"]
    luas = 50.0 + 10.0 * 0.15
    assert total["BTN.CAKAR.PELAT"] == pytest.approx(luas * 0.15)
    n = max(3, math.ceil(luas / 2.5**2))  # 3 kolom, luas 51,5 m², jarak 2,5 m -> 9 pipa
    assert k.pilihan_fondasi["n_pipa"] == n
    D, tp, L = P.cakar_diameter_pipa, P.cakar_tebal_pipa, P.cakar_panjang_pipa
    assert total["BTN.CAKAR.PIPA"] == pytest.approx(n * math.pi / 4 * (D**2 - (D - 2 * tp) ** 2) * L)
    assert total["BSK.CAKAR.PELAT"] == pytest.approx(10.0 * 0.15)  # tepi pelat di dinding luar
    assert total["BSI.CAKAR.P"] > 0 and total["TNH.GALIAN.3"] > 0
    assert any("cakar ayam (sistem Sedijatmo)" in d for d in dilewati)
    # sloof tetap dihitung bila dipilih
    total2, per_el2, _, _ = _total(_model(), replace(p, cakar_pakai_sloof=1))
    assert "BTN.SLOOF" in per_el2["S1"]


def test_pilihan_footplate_pada_model_tanpa_fondasi_menggantikan_sumuran_turunan():
    elemen = [_kolom("K1", "K1", fondasi=()), _kolom("K2", "K2", fondasi=())]
    model, _, _, _ = _total(elemen)
    assert "BTN.SUMURAN" in model  # bawaan: sumuran turunan (Batasan no. 8)
    fp, _, _, _ = _total([_kolom("K1", "K1"), _kolom("K2", "K2")], replace(P, fondasi_kolom_jenis=FONDASI_FOOTPLATE))
    assert "BTN.SUMURAN" not in fp and fp["BTN.FONDASI"] == pytest.approx(2 * 0.8 * 0.8 * 0.25)


def test_relasi_fondasi_di_bawah_kolom():
    kolom = {"A1": (0.0, 0.0, -1.2), "B1": (3.0, 0.0, -1.2)}
    fondasi = {"FP": (-0.45, -0.45, -1.45, 0.45, 0.45, -1.2), "SM": (2.6, -0.4, -3.4, 3.4, 0.4, -1.4),
               "JAUH": (10, 10, -1.5, 11, 11, -1.2)}
    assert fondasi_di_bawah_kolom(kolom, fondasi) == {"FP": "A1", "SM": "B1"}


def test_validasi_parameter_fondasi():
    from database.parameter_repository import ParameterTidakValid, validasi_parameter

    assert validasi_parameter({"fondasi_kolom_jenis": 2})["fondasi_kolom_jenis"] == 2
    with pytest.raises(ParameterTidakValid):
        validasi_parameter({"fondasi_kolom_jenis": 5})
    with pytest.raises(ParameterTidakValid):
        validasi_parameter({"footplate_lebar": 0.3})
    with pytest.raises(ParameterTidakValid):
        validasi_parameter({"cakar_diameter_pipa": 0.4, "cakar_tebal_pipa": 0.15})
    assert FONDASI_MODEL == 0


# ---------------------------------------------------------------- integrasi IFC + export


def test_estimasi_dan_export_perbandingan_fondasi(db_sementara, tmp_path):
    from openpyxl import load_workbook

    from database.parameter_repository import simpan_parameter
    from database.proyek_repository import create_proyek
    from estimasi_service import jalankan_estimasi
    from export_service import OpsiExport, ambil_data_export, export_excel
    from test_kolom_fisik import _model as model_kolom

    pid = create_proyek("Uji Fondasi", str(model_kolom(tmp_path)))
    jalankan_estimasi(pid)
    data = ambil_data_export(pid)
    pf = data["perbandingan_fondasi"]
    assert pf["jenis"] == ["Sesuai model IFC", "Footplate (fondasi telapak)", "Cakar ayam (sistem Sedijatmo)"]
    assert pf["aktif"] == 0 and pf["baris"]
    # biaya langsung tiap jenis = estimasi penuh dengan jenis itu
    langsung = data["ringkasan"]["langsung"]
    for jenis in (1, 2):
        simpan_parameter(pid, {"fondasi_kolom_jenis": jenis})
        jalankan_estimasi(pid)
        lain = ambil_data_export(pid)["ringkasan"]["langsung"]
        assert langsung - pf["beda"][0] + pf["beda"][jenis] == pytest.approx(lain, rel=1e-9)
    path = export_excel(tmp_path / "rab.xlsx", data, {}, OpsiExport())
    wb = load_workbook(path)
    assert wb.sheetnames.index("PERBANDINGAN_FONDASI") == wb.sheetnames.index("ASUMSI") + 1
    teks = [c.value for row in wb["PERBANDINGAN_FONDASI"].iter_rows() for c in row if isinstance(c.value, str)]
    assert any("Sesuai model IFC ●" in t for t in teks)
    assert "Biaya langsung (A) = A di RAB − pekerjaan berbeda jenis ● + pekerjaan berbeda jenis ini" in teks
