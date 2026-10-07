"""
Menjalankan proses berat (validasi & parsing IFC) di thread terpisah sambil menampilkan
indikator proses, supaya jendela tidak "Not Responding" (UC-01 langkah 6 dan 9).

Pemakaian (blok sampai selesai, tetapi event loop Qt tetap berjalan):

    hasil = jalankan_di_latar(parent, "Memproses file IFC", fungsi, arg1, pakai_progress=True)

Bila `pakai_progress=True`, fungsi dipanggil dengan argumen kata kunci `progress(i, n, teks)`.
Exception dari fungsi diteruskan ke pemanggil apa adanya.
"""

from PySide6.QtCore import QEventLoop, QObject, Qt, QThread, Signal, Slot
from PySide6.QtWidgets import QProgressDialog



class _Pekerja(QObject):
    progres = Signal(int, int, str)
    selesai = Signal()

    def __init__(self, fungsi, args, kwargs, pakai_progress):
        super().__init__()
        self._fungsi, self._args, self._kwargs = fungsi, args, kwargs
        self._pakai_progress = pakai_progress
        self.hasil = None
        self.galat = None

    def jalankan(self):
        try:
            kwargs = dict(self._kwargs)
            if self._pakai_progress:
                kwargs["progress"] = lambda i, n, teks: self.progres.emit(i, n, teks)
            self.hasil = self._fungsi(*self._args, **kwargs)
        except BaseException as e:  # diteruskan ke thread utama
            self.galat = e
        finally:
            self.selesai.emit()


class _Penerima(QObject):
    """Dibuat di thread utama, sehingga slot-nya (yang menyentuh widget) selalu berjalan di thread utama."""

    def __init__(self, fungsi):
        super().__init__()
        self._fungsi = fungsi

    @Slot(int, int, str)
    def terima(self, i, n, teks):
        self._fungsi(i, n, teks)


def jalankan_di_latar(parent, judul: str, fungsi, *args, pakai_progress=False, **kwargs):
    dialog = QProgressDialog(judul, None, 0, 0, parent)
    dialog.setWindowTitle("CostStruct")
    dialog.setWindowModality(Qt.WindowModal)
    dialog.setCancelButton(None)  # proses tidak dapat dibatalkan di tengah jalan
    dialog.setMinimumDuration(0)
    dialog.setMinimumWidth(460)
    dialog.setAutoClose(False)
    dialog.setAutoReset(False)

    thread = QThread()
    pekerja = _Pekerja(fungsi, args, kwargs, pakai_progress)
    pekerja.moveToThread(thread)
    loop = QEventLoop()

    def perbarui(i, n, teks):
        if n > 0:
            dialog.setMaximum(n)
            dialog.setValue(min(i, n))
            dialog.setLabelText(f"{judul}\n{i} / {n}  —  {teks}")
        else:
            dialog.setLabelText(f"{judul}\n{teks}")

    penerima = _Penerima(perbarui)
    pekerja.progres.connect(penerima.terima, Qt.QueuedConnection)
    pekerja.selesai.connect(loop.quit, Qt.QueuedConnection)
    thread.started.connect(pekerja.jalankan)

    dialog.show()
    thread.start()
    loop.exec()
    thread.quit()
    thread.wait()
    dialog.close()
    dialog.deleteLater()

    if pekerja.galat is not None:
        raise pekerja.galat
    return pekerja.hasil
