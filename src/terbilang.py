"""Angka -> kata dalam bahasa Indonesia, untuk baris "Terbilang" pada rekapitulasi RAB."""

_SATUAN = ["", "satu", "dua", "tiga", "empat", "lima", "enam", "tujuh", "delapan", "sembilan",
           "sepuluh", "sebelas"]
_SKALA = [(10**12, "triliun"), (10**9, "miliar"), (10**6, "juta"), (1000, "ribu")]


def _ratusan(n: int) -> str:
    """0 <= n < 1000"""
    if n < 12:
        return _SATUAN[n]
    if n < 20:
        return f"{_SATUAN[n - 10]} belas"
    if n < 100:
        puluh, sisa = divmod(n, 10)
        return f"{_SATUAN[puluh]} puluh {_SATUAN[sisa]}".strip()
    ratus, sisa = divmod(n, 100)
    depan = "seratus" if ratus == 1 else f"{_SATUAN[ratus]} ratus"
    return f"{depan} {_ratusan(sisa)}".strip()


def terbilang(nilai: float) -> str:
    """mis. 4.383.998.000 -> 'Empat miliar tiga ratus delapan puluh tiga juta ...'."""
    n = int(round(nilai))
    if n == 0:
        return "Nol"
    if n < 0:
        return "Minus " + terbilang(-n).lower()
    bagian = []
    for besar, nama in _SKALA:
        if n >= besar:
            depan, n = divmod(n, besar)
            if besar == 1000 and depan == 1:
                bagian.append("seribu")
            else:
                bagian.append(f"{terbilang(depan).lower()} {nama}")
    if n:
        bagian.append(_ratusan(n))
    teks = " ".join(bagian)
    return teks[0].upper() + teks[1:]
