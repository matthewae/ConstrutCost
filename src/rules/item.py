"""Item hasil aturan yang mengembalikan beberapa pekerjaan sekaligus (mis. galian + urugan)."""

from dataclasses import dataclass


@dataclass
class ItemHasil:
    kode: str  # kode pekerjaan
    nilai: float
    rumus: str
    uraian: str = ""
    diameter: float | None = None
