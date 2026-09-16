"""
Layar Tabel Hasil Estimasi QTO & RAB (UC-03) untuk CostStruct.
Edit volume di sini otomatis memicu hitung ulang subtotal_biaya.
"""

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QTableWidget,
    QTableWidgetItem, QPushButton, QLabel, QHeaderView, QAbstractItemView,
    QDoubleSpinBox, QStackedWidget, QFrame
)
from PySide6.QtCore import Qt

from database.estimasi_repository import (
    get_hasil_estimasi_by_proyek, update_volume_estimasi, get_total_rab,
)

# Placeholder: belum ada layar Pengaturan Pajak/PPN (KF-11 masih perlu
# dirapikan penomorannya). Tarif efektif PPN non-barang-mewah di Indonesia
# per 2026 masih 11% -- ganti ini kalau KF-11 sudah punya tempatnya sendiri.
PPN_RATE = 0.11

STYLE_SHEET = """
QWidget {
    background-color: #182430;
    color: #e4ebf2;
    font-family: "Segoe UI", sans-serif;
    font-size: 13px;
}
QLabel#judulApp { font-size: 20px; font-weight: 700; color: #ffffff; }
QLabel#subjudulApp { color: #7d92a8; font-size: 12px; }
QLabel#labelStatusManual { color: #f7b955; font-size: 11px; font-weight: 600; }
QLabel#labelStatusOtomatis { color: #7d92a8; font-size: 11px; }
QLabel#labelRingkasan { color: #7d92a8; font-size: 13px; }
QLabel#labelTotal { color: #ffffff; font-size: 18px; font-weight: 700; }
QTableWidget {
    background-color: #1c2733;
    border: 1px solid #2a3947;
    border-radius: 8px;
    gridline-color: transparent;
    selection-background-color: #2a4a6e;
    alternate-background-color: #202e3b;
}
QTableWidget::item { padding: 8px 10px; border: none; }
QHeaderView::section {
    background-color: #1c2733;
    color: #7d92a8;
    padding: 10px;
    border: none;
    border-bottom: 1px solid #2a3947;
    font-weight: 600;
    font-size: 11px;
}
QDoubleSpinBox {
    background-color: #223142;
    border: 1px solid #2f4356;
    border-radius: 4px;
    padding: 4px 6px;
    color: #e4ebf2;
}
QDoubleSpinBox:focus { border: 1px solid #4f9df7; }
QPushButton { border-radius: 6px; padding: 9px 18px; font-weight: 600; }
QPushButton#btnKembali {
    background-color: #223142;
    color: #e4ebf2;
    border: 1px solid #2f4356;
}
QPushButton#btnKembali:hover { background-color: #2a3947; }
QFrame#panelRingkasan {
    background-color: #1c2733;
    border: 1px solid #2a3947;
    border-radius: 10px;
}
QFrame#kartuKosong {
    background-color: #1c2733;
    border: 1px dashed #2f4356;
    border-radius: 10px;
}
"""

KOL_KATEGORI, KOL_PEKERJAAN, KOL_ELEMEN, KOL_SATUAN, KOL_VOLUME, KOL_HARGA, KOL_SUBTOTAL, KOL_STATUS = range(8)


def format_rupiah(nilai: float) -> str:
    return "Rp " + f"{nilai:,.0f}".replace(",", ".")


class EstimasiWindow(QMainWindow):
    """Layar hasil estimasi QTO & RAB untuk satu proyek."""

    def __init__(self, proyek_id: int, nama_proyek: str, on_kembali=None):
        super().__init__()
        self.proyek_id = proyek_id
        self.nama_proyek = nama_proyek
        self.on_kembali = on_kembali

        self.setWindowTitle(f"CostStruct — Estimasi: {nama_proyek}")
        self.resize(1040, 640)
        self.setStyleSheet(STYLE_SHEET)

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(28, 24, 28, 24)
        root.setSpacing(16)

        # --- Header ---
        header_row = QHBoxLayout()
        btn_kembali = QPushButton("←  Kembali")
        btn_kembali.setObjectName("btnKembali")
        btn_kembali.setCursor(Qt.PointingHandCursor)
        btn_kembali.clicked.connect(self._kembali)
        header_row.addWidget(btn_kembali)

        judul_col = QVBoxLayout()
        judul_col.setSpacing(2)
        judul = QLabel(nama_proyek)
        judul.setObjectName("judulApp")
        subjudul = QLabel("Hasil Estimasi — Quantity Take-Off & RAB")
        subjudul.setObjectName("subjudulApp")
        judul_col.addWidget(judul)
        judul_col.addWidget(subjudul)
        header_row.addSpacing(12)
        header_row.addLayout(judul_col)
        header_row.addStretch()
        root.addLayout(header_row)

        # --- Stacked: tabel ATAU empty state ---
        self.stack = QStackedWidget()
        root.addWidget(self.stack, stretch=1)
        self.stack.addWidget(self._buat_halaman_tabel())
        self.stack.addWidget(self._buat_halaman_kosong())

        # --- Panel ringkasan RAB ---
        self.panel_ringkasan = self._buat_panel_ringkasan()
        root.addWidget(self.panel_ringkasan)

        self.muat_data()

    # ---------- Konstruksi UI ----------

    def _buat_halaman_tabel(self) -> QWidget:
        wrap = QWidget()
        layout = QVBoxLayout(wrap)
        layout.setContentsMargins(0, 0, 0, 0)

        self.table = QTableWidget(0, 8)
        self.table.setHorizontalHeaderLabels(
            ["KATEGORI", "PEKERJAAN", "ELEMEN / LANTAI", "SATUAN", "VOLUME", "HARGA SATUAN", "SUBTOTAL", "STATUS"]
        )
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)  # edit lewat spinbox, bukan cell langsung
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(44)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(KOL_PEKERJAAN, QHeaderView.Stretch)
        header.setSectionResizeMode(KOL_ELEMEN, QHeaderView.Stretch)
        for kol in (KOL_KATEGORI, KOL_SATUAN, KOL_VOLUME, KOL_HARGA, KOL_SUBTOTAL, KOL_STATUS):
            header.setSectionResizeMode(kol, QHeaderView.ResizeToContents)

        layout.addWidget(self.table)
        return wrap

    def _buat_halaman_kosong(self) -> QWidget:
        wrap = QFrame()
        wrap.setObjectName("kartuKosong")
        layout = QVBoxLayout(wrap)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(10)

        judul = QLabel("Belum ada hasil estimasi")
        judul.setStyleSheet("font-size: 16px; font-weight: 600; color: #e4ebf2;")
        judul.setAlignment(Qt.AlignCenter)

        deskripsi = QLabel(
            "Proses parsing IFC & perhitungan rule-engine untuk proyek ini\nbelum dijalankan, jadi hasil_estimasi masih kosong."
        )
        deskripsi.setStyleSheet("color: #7d92a8;")
        deskripsi.setAlignment(Qt.AlignCenter)

        layout.addWidget(judul)
        layout.addWidget(deskripsi)
        return wrap

    def _buat_panel_ringkasan(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("panelRingkasan")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(20, 14, 20, 14)
        layout.setSpacing(4)

        baris_subtotal = QHBoxLayout()
        baris_subtotal.addWidget(QLabel("Subtotal RAB"))
        self.label_subtotal = QLabel("Rp 0")
        self.label_subtotal.setObjectName("labelRingkasan")
        baris_subtotal.addStretch()
        baris_subtotal.addWidget(self.label_subtotal)
        for w in baris_subtotal.parentWidget() and [] or []:
            pass

        baris_ppn = QHBoxLayout()
        label_ppn_judul = QLabel(f"PPN {int(PPN_RATE * 100)}%")
        label_ppn_judul.setObjectName("labelRingkasan")
        self.label_ppn = QLabel("Rp 0")
        self.label_ppn.setObjectName("labelRingkasan")
        baris_ppn.addWidget(label_ppn_judul)
        baris_ppn.addStretch()
        baris_ppn.addWidget(self.label_ppn)

        baris_total = QHBoxLayout()
        baris_total.addWidget(QLabel("Total RAB"))
        self.label_total = QLabel("Rp 0")
        self.label_total.setObjectName("labelTotal")
        baris_total.addStretch()
        baris_total.addWidget(self.label_total)

        layout.addLayout(baris_subtotal)
        layout.addLayout(baris_ppn)
        layout.addLayout(baris_total)
        return panel

    # ---------- Data ----------

    def muat_data(self):
        data = get_hasil_estimasi_by_proyek(self.proyek_id)
        ada_data = len(data) > 0
        self.stack.setCurrentIndex(0 if ada_data else 1)
        self.panel_ringkasan.setVisible(ada_data)
        if not ada_data:
            return

        self.table.setRowCount(0)
        for row_idx, row in enumerate(data):
            self.table.insertRow(row_idx)
            self.table.setItem(row_idx, KOL_KATEGORI, QTableWidgetItem(row["kategori"]))
            self.table.setItem(row_idx, KOL_PEKERJAAN, QTableWidgetItem(row["nama_pekerjaan"]))
            elemen_label = row["nama_elemen"] or "-"
            if row["lantai"]:
                elemen_label += f" ({row['lantai']})"
            self.table.setItem(row_idx, KOL_ELEMEN, QTableWidgetItem(elemen_label))
            self.table.setItem(row_idx, KOL_SATUAN, QTableWidgetItem(row["satuan"]))

            spin_volume = QDoubleSpinBox()
            spin_volume.setRange(0, 1_000_000)
            spin_volume.setDecimals(3)
            spin_volume.setValue(row["volume_pekerjaan"])
            spin_volume.editingFinished.connect(
                lambda r=row_idx, hid=row["hasil_id"], pid=row["pekerjaan_id"], sp=spin_volume:
                    self._volume_diubah(r, hid, pid, sp.value())
            )
            self.table.setCellWidget(row_idx, KOL_VOLUME, spin_volume)

            harga_satuan = row["subtotal_biaya"] / row["volume_pekerjaan"] if row["volume_pekerjaan"] else 0
            self.table.setItem(row_idx, KOL_HARGA, QTableWidgetItem(format_rupiah(harga_satuan)))
            self.table.setItem(row_idx, KOL_SUBTOTAL, QTableWidgetItem(format_rupiah(row["subtotal_biaya"])))

            status_item = QTableWidgetItem("Manual" if row["diedit_manual"] else "Otomatis")
            self.table.setItem(row_idx, KOL_STATUS, status_item)

        self._perbarui_ringkasan()

    def _volume_diubah(self, row_idx: int, hasil_id: int, pekerjaan_id: int, volume_baru: float):
        subtotal_baru = update_volume_estimasi(hasil_id, pekerjaan_id, volume_baru)
        self.table.setItem(row_idx, KOL_SUBTOTAL, QTableWidgetItem(format_rupiah(subtotal_baru)))
        self.table.setItem(row_idx, KOL_STATUS, QTableWidgetItem("Manual"))
        self._perbarui_ringkasan()

    def _perbarui_ringkasan(self):
        subtotal = get_total_rab(self.proyek_id)
        ppn = subtotal * PPN_RATE
        total = subtotal + ppn
        self.label_subtotal.setText(format_rupiah(subtotal))
        self.label_ppn.setText(format_rupiah(ppn))
        self.label_total.setText(format_rupiah(total))

    # ---------- Navigasi ----------

    def _kembali(self):
        if self.on_kembali:
            self.on_kembali()
        else:
            self.close()