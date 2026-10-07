"""Rule engine: elemen (dict dari ifc_reader) + konteks bangunan -> daftar kuantitas pekerjaan."""

from dataclasses import dataclass

from klasifikasi import LABEL, ElementType

from .definitions import RULES
from .konteks import Konteks, siapkan_konteks
from .parameter import PARAMETER_DEFAULT

KONTEKS_KOSONG = Konteks(
    ada_fondasi_model=False, elevasi_lantai_dasar=None, sumber_lantai=None, sumber_plafon=None
)


@dataclass
class HasilRule:
    kode: str
    volume: float
    rumus: str
    keterangan: str = ""


def _cocok(rule, elemen, konteks, parameter) -> bool:
    if rule.kelas.value != elemen["kelas"]:
        return False
    return rule.syarat is None or rule.syarat(elemen, konteks, parameter)


def terapkan_rules(elemen: dict, konteks: Konteks = None, parameter=PARAMETER_DEFAULT, rules=RULES):
    """Return (hasil, dilewati). dilewati = alasan aturan cocok tetapi dimensinya kosong."""
    konteks = konteks or KONTEKS_KOSONG
    hasil, dilewati = [], []
    for rule in rules:
        if not _cocok(rule, elemen, konteks, parameter):
            continue
        kosong = [b for b in rule.butuh if not elemen.get(b) or elemen[b] <= 0]
        if kosong:
            label = LABEL.get(ElementType(elemen["kelas"]), elemen["kelas"])
            dilewati.append(
                f"{rule.kode}: {', '.join(kosong)} kosong pada {label} '{elemen.get('nama')}'"
            )
            continue
        nilai, uraian = rule.hitung(elemen, parameter)
        if nilai is None or nilai <= 0:
            continue
        hasil.append(HasilRule(rule.kode, nilai, uraian, rule.keterangan))
    return hasil, dilewati


def proses_semua(elemen: list, parameter=PARAMETER_DEFAULT, rules=RULES):
    """Jalankan preprocessor + rule engine untuk seluruh elemen satu model.
    Return (konteks, [(elemen, [HasilRule])], dilewati)."""
    konteks = siapkan_konteks(elemen)
    keluaran, dilewati = [], []
    for el in elemen:
        hasil, lewat = terapkan_rules(el, konteks, parameter, rules)
        keluaran.append((el, hasil))
        dilewati.extend(lewat)
    return konteks, keluaran, dilewati
