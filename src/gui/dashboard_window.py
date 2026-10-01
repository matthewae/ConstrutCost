from rules.estimasi_service import jalankan_estimasi
import sys
from pathlib import Path

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTableWidget, QTableWidgetItem, QPushButton, QLabel, QHeaderView,
    QFileDialog, QMessageBox, QAbstractItemView, QLineEdit, QStackedWidget,
    QFrame
)
from PySide6.QtCore import Qt

from database.proyek_repository import get_all_proyek, create_proyek, delete_proyek
from rules.estimasi_service import jalankan_estimasi
from gui.estimasi_window import EstimasiWindow


STYLE_SHEET = """
QWidget {
    background-color: #182430;
    color: #e4ebf2;
    font-family: "Segoe UI", sans-serif;
    font-size: 13px;
}

QLabel#judulApp {
    font-size: 22px;
    font-weight: 700;
    color: #ffffff;
}

QLabel#subjudulApp {
    color: #7d92a8;
    font-size: 12px;
}

QLabel#jumlahProyek {
    color: #7d92a8;
    font-size: 12px;
}

QLineEdit#kolomCari {
    background-color: #223142;
    border: 1px solid #2f4356;
    border-radius: 6px;
    padding: 7px 12px;
    color: #e4ebf2;
}

QLineEdit#kolomCari:focus {
    border: 1px solid #4f9df7;
}

QTableWidget {
    background-color: #1c2733;
    border: 1px solid #2a3947;
    border-radius: 8px;
    gridline-color: transparent;
    selection-background-color: #2a4a6e;
    selection-color: #ffffff;
    alternate-background-color: #202e3b;
}

QTableWidget::item {
    padding: 8px 10px;
    border: none;
}

QHeaderView::section {
    background-color: #1c2733;
    color: #7d92a8;
    padding: 10px;
    border: none;
    border-bottom: 1px solid #2a3947;
    font-weight: 600;
    font-size: 11px;
}

QPushButton {
    border-radius: 6px;
    padding: 9px 18px;
    font-weight: 600;
}

QPushButton#btnPrimary {
    background-color: #4f9df7;
    color: #0c1a26;
}

QPushButton#btnPrimary:hover {
    background-color: #6bacf9;
}

QPushButton#btnSecondary {
    background-color: #223142;
    color: #e4ebf2;
    border: 1px solid #2f4356;
}

QPushButton#btnSecondary:hover {
    background-color: #2a3947;
}

QPushButton#btnSecondary:disabled {
    color: #4c5c6d;
}

QPushButton#btnDanger {
    background-color: transparent;
    color: #f16f6f;
    border: 1px solid #46313a;
}

QPushButton#btnDanger:hover {
    background-color: #3a2229;
}

QPushButton#btnDanger:disabled {
    color: #4c5c6d;
    border: 1px solid #2f4356;
}

QPushButton#btnCTA {
    background-color: #4f9df7;
    color: #0c1a26;
    padding: 12px 24px;
}

QPushButton#btnCTA:hover {
    background-color: #6bacf9;
}

QFrame#kartuKosong {
    background-color: #1c2733;
    border: 1px dashed #2f4356;
    border-radius: 10px;
}
"""


class DashboardWindow(QMainWindow):
    """Window utama saat aplikasi dibuka: daftar proyek yang tersimpan."""

    def __init__(self):
        super().__init__()

        self.setWindowTitle("CostStruct — Dashboard Proyek")
        self.resize(980, 600)
        self.setStyleSheet(STYLE_SHEET)

        self._semua_proyek = []

        central = QWidget()
        self.setCentralWidget(central)

        root = QVBoxLayout(central)
        root.setContentsMargins(28, 24, 28, 24)
        root.setSpacing(16)

        # --- Header: judul + tombol proyek baru ---
        header_row = QHBoxLayout()

        judul_col = QVBoxLayout()
        judul_col.setSpacing(2)

        judul = QLabel("Daftar Proyek")
        judul.setObjectName("judulApp")

        subjudul = QLabel(
            "CostStruct — BIM-Based Quantity Take-Off & Estimasi RAB"
        )
        subjudul.setObjectName("subjudulApp")

        judul_col.addWidget(judul)
        judul_col.addWidget(subjudul)

        header_row.addLayout(judul_col)
        header_row.addStretch()

        self.btn_baru = QPushButton("+  Proyek Baru")
        self.btn_baru.setObjectName("btnPrimary")
        self.btn_baru.setCursor(Qt.PointingHandCursor)
        self.btn_baru.clicked.connect(self.proyek_baru)

        header_row.addWidget(self.btn_baru)
        root.addLayout(header_row)

        # --- Baris pencarian + jumlah proyek ---
        cari_row = QHBoxLayout()

        self.kolom_cari = QLineEdit()
        self.kolom_cari.setObjectName("kolomCari")
        self.kolom_cari.setPlaceholderText("Cari nama proyek...")
        self.kolom_cari.textChanged.connect(self._terapkan_filter)

        cari_row.addWidget(self.kolom_cari, stretch=1)

        self.label_jumlah = QLabel("")
        self.label_jumlah.setObjectName("jumlahProyek")

        cari_row.addWidget(self.label_jumlah)
        root.addLayout(cari_row)

        # --- Stacked: tabel proyek ATAU empty state ---
        self.stack = QStackedWidget()
        root.addWidget(self.stack, stretch=1)

        self.stack.addWidget(self._buat_halaman_tabel())
        self.stack.addWidget(self._buat_halaman_kosong())

        # --- Baris tombol aksi ---
        aksi_row = QHBoxLayout()
        aksi_row.addStretch()

        self.btn_buka = QPushButton("Buka Proyek")
        self.btn_buka.setObjectName("btnSecondary")
        self.btn_buka.setCursor(Qt.PointingHandCursor)
        self.btn_buka.clicked.connect(self.buka_proyek)

        self.btn_hapus = QPushButton("Hapus Proyek")
        self.btn_hapus.setObjectName("btnDanger")
        self.btn_hapus.setCursor(Qt.PointingHandCursor)
        self.btn_hapus.clicked.connect(self.hapus_proyek)

        aksi_row.addWidget(self.btn_buka)
        aksi_row.addWidget(self.btn_hapus)

        root.addLayout(aksi_row)

        self._perbarui_tombol_aksi()
        self.muat_daftar_proyek()

    # ---------- Konstruksi UI ----------

    def _buat_halaman_tabel(self) -> QWidget:
        wrap = QWidget()

        layout = QVBoxLayout(wrap)
        layout.setContentsMargins(0, 0, 0, 0)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels([
            "NAMA PROYEK",
            "FILE IFC",
            "DIBUAT",
            "DIUBAH"
        ])

        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(42)

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)

        self.table.doubleClicked.connect(self.buka_proyek)
        self.table.itemSelectionChanged.connect(
            self._perbarui_tombol_aksi
        )

        layout.addWidget(self.table)

        return wrap

    def _buat_halaman_kosong(self) -> QWidget:
        wrap = QFrame()
        wrap.setObjectName("kartuKosong")

        layout = QVBoxLayout(wrap)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(10)

        judul = QLabel("Belum ada proyek")
        judul.setStyleSheet(
            "font-size: 16px; font-weight: 600; color: #e4ebf2;"
        )
        judul.setAlignment(Qt.AlignCenter)

        deskripsi = QLabel(
            "Import file IFC untuk mulai membuat estimasi RAB pertama kamu."
        )
        deskripsi.setStyleSheet("color: #7d92a8;")
        deskripsi.setAlignment(Qt.AlignCenter)

        btn_cta = QPushButton("+  Buat Proyek Pertama")
        btn_cta.setObjectName("btnCTA")
        btn_cta.setCursor(Qt.PointingHandCursor)
        btn_cta.clicked.connect(self.proyek_baru)
        btn_cta.setFixedWidth(220)

        layout.addWidget(judul)
        layout.addWidget(deskripsi)
        layout.addWidget(btn_cta, alignment=Qt.AlignCenter)

        return wrap

    # ---------- Data & filter ----------

    def muat_daftar_proyek(self):
        self._semua_proyek = get_all_proyek()

        ada_proyek = len(self._semua_proyek) > 0
        self.stack.setCurrentIndex(0 if ada_proyek else 1)

        self.kolom_cari.setVisible(ada_proyek)
        self._terapkan_filter()

    def _terapkan_filter(self):
        if not self._semua_proyek:
            return

        kata_kunci = self.kolom_cari.text().strip().lower()

        hasil = [
            p for p in self._semua_proyek
            if kata_kunci in p["nama_proyek"].lower()
        ] if kata_kunci else self._semua_proyek

        self.table.setRowCount(0)

        for row_idx, p in enumerate(hasil):
            self.table.insertRow(row_idx)

            self.table.setItem(
                row_idx,
                0,
                QTableWidgetItem(p["nama_proyek"])
            )

            self.table.setItem(
                row_idx,
                1,
                QTableWidgetItem(p["path_file_ifc"] or "-")
            )

            self.table.setItem(
                row_idx,
                2,
                QTableWidgetItem(p["tanggal_dibuat"] or "-")
            )

            self.table.setItem(
                row_idx,
                3,
                QTableWidgetItem(p["tanggal_diubah"] or "-")
            )

            self.table.item(row_idx, 0).setData(
                Qt.UserRole,
                p["id"]
            )

        total = len(self._semua_proyek)

        if kata_kunci:
            self.label_jumlah.setText(
                f"{len(hasil)} dari {total} proyek"
            )
        else:
            self.label_jumlah.setText(
                f"{total} proyek tersimpan"
            )

        self._perbarui_tombol_aksi()

    def _selected_proyek_id(self):
        row = self.table.currentRow()

        if row < 0:
            return None

        item = self.table.item(row, 0)

        return item.data(Qt.UserRole) if item else None

    def _perbarui_tombol_aksi(self):
        ada_pilihan = self._selected_proyek_id() is not None

        self.btn_buka.setEnabled(ada_pilihan)
        self.btn_hapus.setEnabled(ada_pilihan)

    # ---------- Aksi ----------

    def proyek_baru(self):
        """KF-7: Buat proyek baru dengan import file IFC."""

        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Pilih File IFC",
            "",
            "IFC Files (*.ifc)"
        )

        if not file_path:
            return

        nama_default = Path(file_path).stem

        proyek_id = create_proyek(
            nama_proyek=nama_default,
            path_file_ifc=file_path
        )

        QApplication.setOverrideCursor(Qt.WaitCursor)

        try:
            r = jalankan_estimasi(proyek_id)

            pesan = (
                f"{r['elemen']} elemen, "
                f"{r['baris_hasil']} baris estimasi."
            )

            if r["peringatan"]:
                pesan += (
                    f"\n{len(r['peringatan'])} peringatan "
                    f"(mis. data luas/volume kosong)."
                )

        except Exception as e:
            pesan = f"Parsing gagal: {e}"

        finally:
            QApplication.restoreOverrideCursor()

        self.muat_daftar_proyek()

        QMessageBox.information(
            self,
            f"Proyek '{nama_default}'",
            pesan
        )

    def buka_proyek(self):
        """KF-9: Buka proyek yang dipilih."""

        proyek_id = self._selected_proyek_id()

        if proyek_id is None:
            QMessageBox.warning(
                self,
                "Belum Ada Pilihan",
                "Pilih dulu satu proyek dari tabel."
            )
            return

        proyek = next(
            (p for p in self._semua_proyek if p["id"] == proyek_id),
            None
        )

        nama_proyek = proyek["nama_proyek"] if proyek else "Proyek"

        self._window_estimasi = EstimasiWindow(
            proyek_id,
            nama_proyek,
            on_kembali=self._kembali_dari_estimasi
        )

        self._window_estimasi.show()
        self.hide()

    def _kembali_dari_estimasi(self):
        self._window_estimasi.close()
        self.muat_daftar_proyek()
        self.show()

    def hapus_proyek(self):
        proyek_id = self._selected_proyek_id()

        if proyek_id is None:
            QMessageBox.warning(
                self,
                "Belum Ada Pilihan",
                "Pilih dulu satu proyek dari tabel."
            )
            return

        jawaban = QMessageBox.question(
            self,
            "Hapus Proyek",
            "Yakin mau hapus proyek ini beserta semua data estimasinya?",
            QMessageBox.Yes | QMessageBox.No
        )

        if jawaban == QMessageBox.Yes:
            delete_proyek(proyek_id)
            self.muat_daftar_proyek()


def main():
    app = QApplication(sys.argv)

    window = DashboardWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()