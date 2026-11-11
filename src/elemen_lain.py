"""
Elemen lain dari model IFC yang tetap harus masuk RAB: cladding (batu alam, bata tempel, panel WPC / kayu),
kisi-kisi dan roster fasad, lisplang, nok genteng, talang, talang tegak / rantai hujan, waterproofing, beton
lansekap (planter, kolam, bak), media tanam, dan sanitair.

Semua IfcElement yang punya bentuk dan bukan bagian elemen yang sudah dihitung dikenali di sini (kelas LAINNYA).
Jenisnya ditentukan dari kelas IFC, PredefinedType, lalu teks elemen: nama, ObjectType, tipe elemen, material,
dan Pset bertema material / deskripsi. Contoh: IfcCovering CLADDING "Cladding Travertine" -> cladding batu alam.

Dua kelompok sengaja TIDAK dihitung per elemen, karena sudah termasuk pekerjaan lain dan akan menjadi hitung ganda:
- batang rangka atap (kuda-kuda, kasau, gording, reng, jurai): termasuk "Rangka atap baja ringan" per m² luas atap
  (ATP.RANGKA, HSPK 2.1.1.1 yang menganalisa seluruh batang + alat sambung per m²);
- penutup atap berupa IfcCovering ROOFING selain nok: termasuk "Penutup atap" per m² (ATP.PENUTUP).

Elemen yang belum punya padanan analisa HSPK tidak dibuang. Ia tetap masuk RAB sebagai pekerjaan "dari model"
dengan harga 0, sehingga muncul di peringatan "belum punya harga satuan" dan harganya dapat diisi pengguna.
"""

import re

RANGKA_ATAP = "rangka_atap"
PENUTUP_ATAP = "penutup_atap"
BAGIAN_TANGGA = "bagian_tangga"
TERMASUK = {
    BAGIAN_TANGGA: ("BTN.TANGGA", "Bagian tangga ini (mis. stringer / ibu tangga) sudah termasuk pekerjaan tangga."),
    RANGKA_ATAP: ("ATP.RANGKA", "Batang rangka atap ini sudah termasuk pekerjaan Rangka Atap Baja Ringan yang "
                                "dihitung per m² luas atap (HSPK 2.1.1.1: seluruh batang kuda-kuda, kasau, reng, dan "
                                "alat sambung). Menghitung batangnya lagi akan menjadi hitung ganda."),
    PENUTUP_ATAP: ("ATP.PENUTUP", "Penutup atap ini sudah termasuk pekerjaan Penutup Atap yang dihitung per m² luas "
                                  "atap."),
}

LABEL_TERMASUK = {
    RANGKA_ATAP: "Batang rangka atap",
    PENUTUP_ATAP: "Penutup atap",
    BAGIAN_TANGGA: "Bagian tangga",
}
LABEL_JENIS = {
    "cladding_batu": "Cladding batu alam",
    "cladding_bata": "Cladding bata tempel",
    "cladding_panel": "Cladding panel (WPC / kayu / komposit)",
    "kisi": "Kisi-kisi / louver fasad",
    "roster": "Roster / kerawang",
    "lisplang": "Lisplang",
    "nok": "Nok / bubungan genteng",
    "talang": "Talang",
    "talang_tegak": "Talang tegak / rantai hujan",
    "waterproofing": "Waterproofing",
    "beton_lansekap": "Beton lansekap (planter / kolam / bak)",
    "media_tanam": "Media tanam",
    "sanitair": "Sanitair",
    "rangka_baja": "Rangka / batang baja",
    "rangka_kayu": "Rangka / batang kayu",
    "lain": "Elemen lain (belum ada analisa HSPK)",
}
CLADDING = ("cladding_batu", "cladding_bata", "cladding_panel")
TEBAL_BETON_ASUMSI = 0.12  # m, bila tebal dinding beton lansekap tidak tertulis di model


def _p(pola: str):
    return re.compile(pola, re.IGNORECASE)


POLA_MAT_BAJA = _p(r"steel|baja|stahl|metal|\bbesi\b|\biron\b")
POLA_MAT_KAYU = _p(r"wood|kayu|holz|timber|lumber|plywood|multiplek")
POLA_RANGKA_ATAP = _p(r"kuda|kasau|kaso|\breng\b|gording|rafter|purlin|chord|jurai|\bnok\b|ridge|truss|bracing"
                      r"|ikatan angin|baja ringan|batang (tegak|diagonal)|\bjack\b|atap|roof|batten|\blath"
                      r"|sparren|pfette|kehlbalken|dachlatte|\bdach")
POLA_LANTAI_ATAP = _p(r"atap|roof|dach|attic|loteng")
POLA_BATANG_BAJA = _p(r"rangka|frame|hollow|\bsiku\b|\bunp\b|\bcnp\b|\bwf\b|\bhss\b|\brhs\b|\bshs\b|\bchs\b"
                      r"|pipa (besi|galvanis)|kanopi|canopy")
POLA_NOK = _p(r"\bnok\b|bubung|ridge|jurai|\bhip\b")
POLA_WATERPROOF = _p(r"waterproof|water ?proof|membran|membrane|kedap air|bitumen|aspal cair")
POLA_CLADDING = _p(r"cladding|pelapis|fasad|facade|\bwpc\b|\bacp\b|aluminium composite|panel (dinding|fasad|wpc)"
                   r"|secondary skin|penutup rangka")
POLA_BATU = _p(r"batu|travertin|paras|andesit|marmer|marble|granit|palimanan|templek|stone|onyx|limestone")
POLA_BATA = _p(r"\bbata\b|brick")
POLA_ROSTER = _p(r"roster|rooster|kerawang|krawang|loster|breeze ?block")
POLA_KISI = _p(r"kisi|louv(er|re)|sirip|\bfin\b|jalusi|shading|sun ?screen|\bscreen\b")
POLA_LISPLANG = _p(r"lis ?plank|list ?plank|lis ?plang|list ?plang|fascia")
POLA_TALANG_TEGAK = _p(r"rantai hujan|rain ?chain|talang tegak|down ?spout|down ?pipe|pipa (talang|air hujan)")
POLA_TALANG = _p(r"talang|gutter")
POLA_MEDIA_TANAM = _p(r"media tanam|tanah (taman|humus|subur)|top ?soil|\bsoil\b|kompos")
POLA_BETON_LANSEKAP = _p(r"planter|pot beton|kolam|\bbak\b|pond|\bpool\b|tandon|bangku beton|parit|saluran beton")
POLA_BETON = _p(r"beton|concrete|\bk-?\d{3}\b|f'?c")
POLA_RANGKA = _p(r"rangka(?!\s*atap)|hollow|\bframe\b|bracket|besi siku")  # "penutup rangka atap" bukan rangka
POLA_CAT = _p(r"\bcat\b|dicat|\bpaint")
POLA_PLESTER = _p(r"plester|plaster")
POLA_WIREMESH = _p(r"wire ?mesh|jaring kawat|\bm(\d{1,2})\b")
POLA_TANPA_DASAR = _p(r"tanpa dasar|tanpa alas|no base|bottomless")
POLA_TEBAL = _p(r"\bt\s*=\s*(\d+(?:[.,]\d+)?)\s*(mm|cm|m)?")
POLA_TULANGAN = _p(r"[Øø∅]\s*(\d{1,2})\s*-\s*(\d{2,3})")
POLA_TERMASUK_KATA_PSET = _p(r"material|bahan|description|deskripsi|spesifikasi|keterangan")

SANITAIR = (  # (pola, kode pekerjaan, nama)  urutan penting: jongkok sebelum kloset umum
    (_p(r"jongkok|squat"), "SNT.KLOSET_JONGKOK", "Kloset jongkok"),
    (_p(r"urinoir|urinal"), "SNT.URINOIR", "Urinoir"),
    (_p(r"kloset|closet|toilet|\bwc\b|monoblock"), "SNT.KLOSET_DUDUK", "Kloset duduk"),
    (_p(r"floor ?drain|avur|afur"), "SNT.FLOOR_DRAIN", "Floor drain"),
    (_p(r"shower"), "SNT.SHOWER", "Shower set"),
    (_p(r"wastafel|wash ?basin|lavatory|\bbasin\b|vanity"), "SNT.WASTAFEL", "Wastafel"),
    (_p(r"bak cuci|kitchen sink|\bsink\b"), "SNT.BAK_CUCI", "Bak cuci piring"),
    (_p(r"\bkran\b|keran|faucet|\btap\b"), "SNT.KRAN", "Kran air"),
)


# ---------------------------------------------------------------- teks elemen


def teks_elemen(entity) -> str:
    """Nama, ObjectType, deskripsi, nama tipe, material, dan Pset bertema material/deskripsi, digabung."""
    import ifcopenshell.util.element as ue

    bagian = [getattr(entity, a, None) for a in ("Name", "ObjectType", "Description", "Tag")]
    try:
        tipe = ue.get_type(entity)
        if tipe is not None:
            bagian += [tipe.Name, getattr(tipe, "Description", None)]
    except Exception:
        pass
    try:
        bagian += [getattr(m, "Name", None) for m in ue.get_materials(entity) or []]
    except Exception:
        pass
    try:
        for nama_set, isi in ue.get_psets(entity).items():
            for k, v in isi.items():
                if isinstance(v, str) and POLA_TERMASUK_KATA_PSET.search(k):
                    bagian.append(v)
    except Exception:
        pass
    return " | ".join(str(x) for x in bagian if x)


def _predefined(entity):
    v = getattr(entity, "PredefinedType", None)
    return str(v).upper() if v else None


def nama_elemen(entity) -> str:
    """Nama, ObjectType, dan nama tipe elemen (tanpa material / keterangan)."""
    import ifcopenshell.util.element as ue

    bagian = [getattr(entity, "Name", None), getattr(entity, "ObjectType", None)]
    try:
        tipe = ue.get_type(entity)
        if tipe is not None:
            bagian.append(tipe.Name)
    except Exception:
        pass
    return " | ".join(str(x) for x in bagian if x)


def kenali(entity, teks: str | None = None) -> str:
    """Jenis elemen lain (kunci LABEL_JENIS), RANGKA_ATAP, atau PENUTUP_ATAP. Nama elemen diperiksa lebih dulu;
    teks lengkap (material, keterangan Pset) hanya bila nama tidak cukup, karena keterangan sering menyebut elemen
    lain (mis. talang box yang "mengalirkan air ke rantai hujan")."""
    t = teks if teks is not None else teks_elemen(entity)
    pre = _predefined(entity)
    jenis = _kenali(entity, pre, nama_elemen(entity), t)
    return jenis if jenis != "lain" else _kenali(entity, pre, t, t)


def _induk(entity):
    import ifcopenshell.util.element as ue

    try:
        return ue.get_aggregate(entity), ue.get_container(entity)
    except Exception:
        return None, None


def _kenali(entity, pre, t: str, lengkap: str) -> str:
    """`t` = teks yang diperiksa pola jenisnya; `lengkap` = teks lengkap untuk bahan cladding."""
    induk, wadah = _induk(entity)
    if induk is not None and (induk.is_a("IfcStair") or induk.is_a("IfcRamp")):
        return BAGIAN_TANGGA
    if entity.is_a("IfcMember"):
        lantai = getattr(wadah, "Name", None) or ""
        if pre in ("RAFTER", "PURLIN", "CHORD") or POLA_RANGKA_ATAP.search(t) or POLA_LANTAI_ATAP.search(lantai) \
                or (induk is not None and induk.is_a("IfcRoof")):
            return RANGKA_ATAP
        if POLA_MAT_KAYU.search(t):
            return "rangka_kayu"
        if POLA_MAT_BAJA.search(t) or POLA_BATANG_BAJA.search(t):
            return "rangka_baja"  # mis. rangka carport / kanopi besi hollow
        return "lain"
    if entity.is_a("IfcCovering"):
        if pre == "ROOFING":
            return "nok" if POLA_NOK.search(t) else PENUTUP_ATAP
        if pre == "MEMBRANE" or POLA_WATERPROOF.search(t):
            return "waterproofing"
        if pre == "CLADDING" or POLA_CLADDING.search(t):
            return _cladding(lengkap)
        if POLA_KISI.search(t):
            return "kisi"
        return "lain"
    if entity.is_a("IfcShadingDevice"):
        return "roster" if POLA_ROSTER.search(lengkap) else "kisi"
    if entity.is_a("IfcPlate"):
        if POLA_LISPLANG.search(t):
            return "lisplang"
        if POLA_CLADDING.search(t) or POLA_BATU.search(t):
            return _cladding(lengkap)
        return "lain"
    if entity.is_a("IfcFlowSegment") or entity.is_a("IfcFlowFitting") or entity.is_a("IfcPipeSegment"):
        if POLA_TALANG_TEGAK.search(t):
            return "talang_tegak"
        if pre == "GUTTER" or POLA_TALANG.search(t):
            return "talang"
        return "lain"
    if entity.is_a("IfcSanitaryTerminal") or entity.is_a("IfcFlowTerminal"):
        return "sanitair" if sanitair(t) else "lain"
    # elemen generik (IfcBuildingElementProxy, IfcCivilElement, ...): dari teks saja. Urutan penting: media tanam
    # di dalam planter, roster beton, lalu beton lansekap (planter/kolam/bak yang juga dilapis waterproofing)
    if POLA_MEDIA_TANAM.search(t):
        return "media_tanam"
    if POLA_ROSTER.search(t):
        return "roster"
    if POLA_BETON_LANSEKAP.search(t) or (POLA_BETON.search(t) and entity.is_a("IfcBuildingElementProxy")):
        return "beton_lansekap"
    for pola, jenis in ((POLA_WATERPROOF, "waterproofing"), (POLA_TALANG_TEGAK, "talang_tegak"),
                        (POLA_TALANG, "talang"), (POLA_LISPLANG, "lisplang"), (POLA_KISI, "kisi")):
        if pola.search(t):
            return jenis
    if POLA_CLADDING.search(t):
        return _cladding(lengkap)
    if sanitair(t):
        return "sanitair"
    return "lain"


def _cladding(t: str) -> str:
    if POLA_BATU.search(t):
        return "cladding_batu"
    if POLA_BATA.search(t):
        return "cladding_bata"
    return "cladding_panel"


def sanitair(t: str):
    """(kode, nama) sanitair dari teks elemen, atau None."""
    for pola, kode, nama in SANITAIR:
        if pola.search(t):
            return kode, nama
    return None


def _angka(teks: str) -> float:
    return float(teks.replace(",", "."))


def tebal_dari_teks(t: str) -> float | None:
    """'Beton K-175 t=12 cm' -> 0,12 m; satuan tanpa keterangan dianggap cm (bila > 1) atau m."""
    m = POLA_TEBAL.search(t or "")
    if not m:
        return None
    v, satuan = _angka(m.group(1)), (m.group(2) or "").lower()
    if satuan == "mm":
        v /= 1000
    elif satuan == "cm" or (not satuan and v > 1):
        v /= 100
    return v if 0.02 <= v <= 1.0 else None


def info(entity, teks: str, jenis: str, pset_angka: dict) -> dict:
    """Keterangan elemen lain yang disimpan bersama elemen (kolom info_lain, JSON)."""
    d = {"jenis": jenis, "label": LABEL_JENIS.get(jenis, jenis), "ifc": entity.is_a(), "teks": teks[:300]}
    if jenis in CLADDING + ("kisi", "roster"):
        d["rangka"] = bool(POLA_RANGKA.search(teks))
    if jenis in ("roster", "beton_lansekap"):
        d["cat"] = bool(POLA_CAT.search(teks))
    if jenis == "beton_lansekap":
        d["plester"] = bool(POLA_PLESTER.search(teks))
        d["waterproofing"] = bool(POLA_WATERPROOF.search(teks))
        d["tanpa_dasar"] = bool(POLA_TANPA_DASAR.search(teks))
        d["tebal"] = pset_angka.get("tebal") or tebal_dari_teks(teks)
        mesh = POLA_WIREMESH.search(teks)
        d["wiremesh"] = bool(mesh)
        tul = POLA_TULANGAN.search(teks)
        if tul:
            d["tulangan"] = [int(tul.group(1)), int(tul.group(2))]
        elif mesh and mesh.group(1):
            d["tulangan"] = [int(mesh.group(1)), 150]
        for k in ("luas_waterproofing", "volume_galian"):
            if pset_angka.get(k):
                d[k] = pset_angka[k]
    if jenis == "sanitair":
        s = sanitair(teks)
        d["kode"], d["nama_sanitair"] = s if s else (None, None)
    if jenis in ("lain", "rangka_baja", "rangka_kayu"):
        nama = re.sub(r":\d+$", "", (getattr(entity, "Name", None) or "").strip())
        try:
            import ifcopenshell.util.element as ue

            tipe = ue.get_type(entity)
            nama = (tipe.Name if tipe is not None and tipe.Name else None) or nama
        except Exception:
            pass
        d["nama_tipe"] = (nama or entity.is_a())[:80]
    if jenis in CLADDING:
        d["eksternal"] = pset_angka.get("eksternal")
    return d


# ---------------------------------------------------------------- pekerjaan


def _n(x: float, d: int = 3) -> str:
    return f"{x:,.{d}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def kode_lain(e: dict) -> str:
    """Kode pekerjaan elemen tanpa padanan HSPK: satu pekerjaan per kelas IFC + nama tipe."""
    i = e.get("info_lain") or {}
    nama = (i.get("nama_tipe") or e.get("nama") or "").replace("~", "-").replace("|", "/")
    return f"LAIN|{i.get('ifc') or e.get('ifc_type') or 'IfcElement'}|{nama}"[:140]


def pekerjaan_lain(kode: str) -> tuple:
    """(nama, kategori, satuan) pekerjaan untuk kode LAIN|kelas|nama[|satuan]."""
    bagian = kode.split("|")
    ifc, nama = (bagian + ["", ""])[1:3]
    satuan = bagian[3] if len(bagian) > 3 and bagian[3] else "buah"
    return f"{nama or ifc} ({ifc}, dari model, belum ada analisa HSPK)", "Lain-lain", satuan


def berat_jaring(d_mm: float, s_mm: float) -> float:
    """kg/m² tulangan dua arah satu lapis: 2 x 0,00617 d² / s."""
    return 2 * 0.006165 * d_mm ** 2 / (s_mm / 1000)


def item(e: dict, p=None) -> list:
    """Item pekerjaan elemen kelas LAINNYA, menurut jenisnya."""
    from rules.item import ItemHasil  # di sini: rules.definitions mengimpor modul ini
    i = e.get("info_lain") or {}
    jenis = i.get("jenis")
    L, A, V = e.get("panjang") or 0.0, e.get("luas") or 0.0, e.get("volume") or 0.0
    h = []

    def luas(kode, keterangan="luas bidang dari model", faktor=1.0):
        if A > 0:
            h.append(ItemHasil(kode, A * faktor, f"A = {('%s × ' % _n(faktor, 0)) if faktor != 1 else ''}"
                                                 f"{_n(A)} m² ({keterangan})"))

    def panjang(kode, keterangan="panjang dari model"):
        if L > 0:
            h.append(ItemHasil(kode, L, f"L = {_n(L)} m ({keterangan})"))

    if jenis == "cladding_batu":
        luas("CLD.BATU")
    elif jenis == "cladding_bata":
        luas("CLD.BATA")
    elif jenis == "cladding_panel":
        luas("CLD.PANEL")
    elif jenis == "kisi":
        luas("CLD.KISI", "luas bidang fasad yang ditutup kisi")
    elif jenis == "roster":
        luas("DND.ROSTER")
        if i.get("cat"):
            luas("CAT.EKSTERIOR", "dua muka roster dicat", 2.0)
    elif jenis == "lisplang":
        panjang("ATP.LISPLANG")
    elif jenis == "nok":
        panjang("ATP.NOK")
    elif jenis == "talang":
        panjang("ATP.TALANG")
    elif jenis == "talang_tegak":
        panjang("ATP.TALANG_TEGAK")
    elif jenis == "waterproofing":
        luas("WTP.LAPISAN")
    elif jenis == "media_tanam":
        if V > 0:
            h.append(ItemHasil("LSK.MEDIA_TANAM", V, f"V = {_n(V)} m³ (volume media tanam dari model)"))
    elif jenis == "beton_lansekap":
        h += _beton_lansekap(e, i, V)
    elif jenis == "rangka_baja" and V > 0:
        w = V * BERAT_BAJA
        h.append(ItemHasil("BJA.PROFIL", w, f"W = V × 7.850 kg/m³ = {_n(V, 4)} × 7.850 = {_n(w, 1)} kg (profil baja)"))
    elif jenis == "rangka_kayu" and V > 0:
        h.append(ItemHasil("KYU.KONSTRUKSI", V, f"V = {_n(V, 4)} m³ (batang kayu dari model)"))
    elif jenis == "sanitair":
        if i.get("kode"):
            h.append(ItemHasil(i["kode"], 1.0, f"1 buah {i.get('nama_sanitair') or 'sanitair'} (dari model)"))
    elif jenis in ("lain", "rangka_baja", "rangka_kayu"):  # rangka tanpa volume: harga diisi pengguna
        h.append(ItemHasil(kode_lain(e), 1.0, "1 buah (elemen model tanpa padanan analisa HSPK: isi harga satuannya)"))
    if jenis in CLADDING + ("kisi", "roster") and i.get("rangka") and A > 0:
        h.append(ItemHasil("CLD.RANGKA", A, f"A rangka = {_n(A)} m² (rangka penggantung sesuai luas bidang)"))
    return h


def _beton_lansekap(e: dict, i: dict, V: float) -> list:
    from rules.item import ItemHasil

    if V <= 0:
        return []
    t = i.get("tebal") or TEBAL_BETON_ASUMSI
    asal_t = "dari model" if i.get("tebal") else "asumsi"
    bidang = V / t
    dasar = 0.0 if i.get("tanpa_dasar") else min(i.get("tapak") or 0.0, bidang)
    dinding = max(bidang - dasar, 0.0)
    h = [ItemHasil("LSK.BETON", V, f"V = {_n(V)} m³ (volume beton dari model)")]
    if dinding > 0:
        catatan = f"dinding = V / t − alas = {_n(V)} / {_n(t, 2)} − {_n(dasar, 2)}" if dasar else \
            f"dinding = V / t = {_n(V)} / {_n(t, 2)}"
        h.append(ItemHasil("LSK.BEKISTING", 2 * dinding,
                           f"A = 2 muka × {_n(dinding, 2)} m² ({catatan}; t {asal_t})"))
    d, s = i.get("tulangan") or (8, 150)
    berat = berat_jaring(d, s) * bidang
    kode = "LSK.WIREMESH" if i.get("wiremesh") else "LSK.BESI"
    nama = f"wiremesh M{d}" if i.get("wiremesh") else f"Ø{d}-{s}"
    h.append(ItemHasil(kode, berat, f"W = {_n(bidang, 2)} m² bidang × {_n(berat_jaring(d, s), 2)} kg/m² "
                                    f"({nama} dua arah) = {_n(berat, 2)} kg", uraian=nama, diameter=float(d)))
    if i.get("waterproofing"):
        a = i.get("luas_waterproofing") or bidang
        h.append(ItemHasil("WTP.LAPISAN", a, f"A = {_n(a)} m² (permukaan dalam yang dilapis)"))
    if i.get("plester") and dinding > 0:
        h.append(ItemHasil("PLS.DINDING", dinding, f"A = {_n(dinding, 2)} m² (muka luar dinding)"))
    if i.get("cat") and dinding > 0:
        h.append(ItemHasil("CAT.EKSTERIOR", dinding, f"A = {_n(dinding, 2)} m² (muka luar dinding)"))
    if i.get("volume_galian"):
        vg = i["volume_galian"]
        h.append(ItemHasil("TNH.GALIAN.1", vg, f"V = {_n(vg)} m³ (volume galian dari model)"))
    return h


def luas_tertutup_cladding(cladding: dict, dinding: dict, celah: float = 0.12) -> dict:
    """Bagian luas cladding yang menempel pada tiap dinding, untuk mengurangi luas cat dinding di baliknya.

    cladding: {gid: (kotak, luas)}; dinding: {gid: kotak}; kotak = (xmin, ymin, zmin, xmax, ymax, zmax) dunia.
    Hanya cladding tegak yang tipis (sisi horizontal terpendek <= 10 cm), sejajar dan berjarak <= `celah` dari
    muka dinding (cladding sering dipasang rata dengan muka kolom yang menonjol dari dinding). Return
    {gid_cladding: [(gid_dinding, luas)]}: luas cladding x (bidang yang menutup dinding / bidang cladding), dibagi
    ke dinding menurut panjang x tinggi tumpang tindihnya; bagian yang menutup kolom tidak mengurangi cat dinding."""
    hasil = {}
    for gc, (c, luas) in cladding.items():
        ex, ey, ez = c[3] - c[0], c[4] - c[1], c[5] - c[2]
        if min(ex, ey) > 0.10 or ez < 0.2 or luas <= 0:
            continue
        tipis = 0 if ex <= ey else 1  # sumbu tebal cladding
        lain = 1 - tipis
        bobot = []
        for gw, w in dinding.items():
            if c[tipis] - celah > w[3 + tipis] or c[3 + tipis] + celah < w[tipis]:
                continue  # tidak bersentuhan di sumbu tebal
            ob = min(c[3 + lain], w[3 + lain]) - max(c[lain], w[lain])
            oz = min(c[5], w[5]) - max(c[2], w[2])
            if ob > 0.05 and oz > 0.05:
                bobot.append((gw, ob * oz))
        total = sum(b for _g, b in bobot)
        if total > 0:
            luas_kotak = max((c[3 + lain] - c[lain]) * ez, 1e-9)
            tertutup = luas * min(total / luas_kotak, 1.0)
            hasil[gc] = [(gw, tertutup * b / total) for gw, b in bobot]
    return hasil


def jumlah_tertutup(e: dict, sisi: str) -> float:
    """Luas dinding yang tertutup cladding pada sisi 'luar' / 'dalam' (dari info_lain dinding)."""
    i = e.get("info_lain") or {}
    return float(i.get(f"tertutup_{sisi}") or 0.0)



# ---------------------------------------------------------------- elemen struktur bukan beton

POLA_KERAMIK = _p(r"ceramic|keramik|\btile\b|granit|homogen")
BERAT_BAJA = 7850.0  # kg/m³


def jenis_nonbeton(e: dict, alasan: str) -> str:
    """'baja' / 'kayu' / 'keramik' / 'tidak_diketahui' untuk elemen struktur yang bukan beton bertulang."""
    from rules.sifat import _KAYU, _PROFIL_BAJA

    nama, mat = e.get("nama") or "", (e.get("info_lain") or {}).get("material") or ""
    if e.get("kelas") in ("SLAB", "ROOF") and POLA_KERAMIK.search(f"{nama} {mat}"):
        return "keramik"
    if _PROFIL_BAJA.search(nama) or POLA_MAT_BAJA.search(mat):
        return "baja"
    if _KAYU.search(nama) or POLA_MAT_KAYU.search(mat):
        return "kayu"
    return "tidak_diketahui"


def rangka_atap_nonbeton(e: dict, alasan: str) -> bool:
    """Balok / kolom bukan beton di lantai atap yang bukan profil baja (mis. gording / kuda-kuda kayu "Pfette"):
    bagian rangka atap, sudah termasuk Rangka Atap per m² luas atap."""
    return (e.get("kelas") in ("BEAM", "COLUMN") and bool(alasan)
            and not (e.get("info_kolom") or {}).get("duplikat")
            and bool(POLA_LANTAI_ATAP.search(e.get("lantai") or ""))
            and jenis_nonbeton(e, alasan) != "baja")


def lapisan_finishing(e: dict, alasan: str) -> bool:
    """Pelat yang sebenarnya lapisan penutup lantai (tipis, atau nama/material finishing)."""
    return e.get("kelas") == "SLAB" and ("lapisan finishing" in alasan
                                         or bool(re.search(r"finish|penutup lantai", e.get("nama") or "", re.I)))


def item_nonbeton(e: dict, p=None) -> list:
    """Item kolom / balok / tangga / pelat / dak yang bukan beton bertulang: baja per kg (V x 7.850 kg/m³), kayu
    per m³, pelat finishing sebagai penutup lantai; selain itu pekerjaan dari model dengan harga 0."""
    from rules.item import ItemHasil
    from rules.sifat import bukan_beton

    alasan = bukan_beton(e) or ""
    jenis = jenis_nonbeton(e, alasan)
    V, A = e.get("volume") or 0.0, e.get("luas") or 0.0
    kelas = e.get("kelas")
    if lapisan_finishing(e, alasan) and A > 0:
        if jenis == "keramik":
            return [ItemHasil("KRM.LANTAI", A, f"A = {_n(A)} m² (pelat lapisan finishing keramik = penutup lantai)")]
        if jenis == "kayu":
            return [ItemHasil("LNT.PARKET", A, f"A = {_n(A)} m² (pelat lapisan finishing kayu = lantai parket)")]
    if jenis == "baja" and V > 0 and kelas in ("COLUMN", "BEAM", "STAIR"):
        w = V * BERAT_BAJA
        return [ItemHasil("BJA.PROFIL", w, f"W = V × 7.850 kg/m³ = {_n(V, 4)} × 7.850 = {_n(w, 1)} kg (profil baja)")]
    if jenis == "kayu" and V > 0 and kelas in ("COLUMN", "BEAM", "STAIR"):
        return [ItemHasil("KYU.KONSTRUKSI", V, f"V = {_n(V, 4)} m³ (konstruksi kayu dari model)")]
    i = {"ifc": e.get("ifc_type"), "nama_tipe": re.sub(r":\d+$", "", (e.get("nama") or "").strip())[:80]}
    if kelas in ("SLAB", "ROOF") and A > 0:
        kode = kode_lain({"info_lain": i, "nama": e.get("nama")}) + "|m2"
        return [ItemHasil(kode, A, f"A = {_n(A)} m² ({alasan}; isi harga satuannya)")]
    return [ItemHasil(kode_lain({"info_lain": i, "nama": e.get("nama")}), 1.0,
                      f"1 buah ({alasan or 'bukan beton bertulang'}; isi harga satuannya)")]
