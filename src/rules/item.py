"""Item hasil aturan yang mengembalikan beberapa pekerjaan sekaligus (mis. galian + urugan)."""

from dataclasses import dataclass


@dataclass
class ItemHasil:
    kode: str  # kode pekerjaan
    nilai: float
    rumus: str
    uraian: str = ""
    diameter: float | None = None
    pengganti: bool = False  # menggantikan pekerjaan model (pilihan jenis fondasi): tidak digugurkan "model > turunan"
