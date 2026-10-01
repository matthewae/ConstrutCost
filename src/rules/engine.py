"""Rule engine: satu elemen (dict dari ifc_reader) -> daftar (kode_pekerjaan, volume)."""

from dataclasses import dataclass
from .definitions import RULES


@dataclass
class HasilRule:
    kode: str
    volume: float
    keterangan: str = ""


def _cocok(rule, elemen) -> bool:
    if rule.ifc_type != elemen["ifc_type"]:
        return False
    pre = (elemen.get("predefined_type") or "").upper()
    if rule.hanya_predefined and pre not in rule.hanya_predefined:
        return False
    if rule.kecuali_predefined and pre in rule.kecuali_predefined:
        return False
    return True


def terapkan_rules(elemen: dict, rules=RULES):
    """Return (hasil, dilewati). dilewati = alasan rule cocok tapi datanya kosong."""
    hasil, dilewati = [], []
    for rule in rules:
        if not _cocok(rule, elemen):
            continue
        nilai = elemen.get(rule.basis)
        if nilai is None or nilai <= 0:
            dilewati.append(f"{rule.kode}: '{rule.basis}' kosong pada {elemen.get('nama')}")
            continue
        hasil.append(HasilRule(rule.kode, nilai * rule.faktor, rule.keterangan))
    return hasil, dilewati
