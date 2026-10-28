"""
Integrasi khusus Windows 10/11 (KNF-7). Semua fungsi aman dipanggil di sistem lain (tidak melakukan apa-apa).

- `atur_id_aplikasi()`: AppUserModelID sendiri, sehingga taskbar menampilkan ikon CostStruct (bukan ikon
  Python) dan jendela aplikasi dikelompokkan dengan benar.
- `atur_title_bar(widget, gelap)`: title bar jendela ikut gelap pada tema gelap (Hitam Kuning, Biru Malam),
  memakai atribut DWM Immersive Dark Mode (Windows 10 20H1+ dan Windows 11).
"""

import sys

ID_APLIKASI = "STMIKLIKMI.CostStruct.EstimasiRAB"
_DWMWA_DARK = (20, 19)  # 20: Windows 10 20H1+ / 11, 19: Windows 10 1809-1909


def di_windows() -> bool:
    return sys.platform == "win32"


def atur_id_aplikasi() -> bool:
    if not di_windows():
        return False
    try:
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(ID_APLIKASI)
        return True
    except Exception:
        return False


def atur_title_bar(widget, gelap: bool) -> bool:
    """Return True bila atribut berhasil dipasang."""
    if not di_windows():
        return False
    try:
        import ctypes
        from ctypes import wintypes

        hwnd = wintypes.HWND(int(widget.winId()))
        nilai = ctypes.c_int(1 if gelap else 0)
        for atribut in _DWMWA_DARK:
            hasil = ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd, wintypes.DWORD(atribut), ctypes.byref(nilai), ctypes.sizeof(nilai)
            )
            if hasil == 0:  # S_OK
                return True
    except Exception:
        pass
    return False
