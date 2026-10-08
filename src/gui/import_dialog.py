"""
Dialog konfirmasi import file IFC (KF-1, UC-01 langkah 7-8).
Menampilkan ringkasan hasil validasi: nama, ukuran, versi IFC, pembuat, lantai, dan jumlah elemen
per kelas, lalu pengguna menekan "Import" untuk mulai parsing.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from klasifikasi import LABEL, ElementType


# Kelas yang menghasilkan pekerjaan struktur/arsitektur utama.
KELAS_UTAMA = {
    ElementType.COLUMN,
    ElementType.BEAM,
    ElementType.SLAB,
    ElementType.ROOF,
    ElementType.WALL,
    ElementType.FOOTING,
    ElementType.PILE,
}


def _elevasi(m: float) -> str:
    tanda = "±" if abs(m) < 0.005 else ("+" if m > 0 else "−")
    return f"{tanda}{abs(m):.2f}".replace(".", ",")


class RingkasanImportDialog(QDialog):
    def __init__(self, info, parent=None):
        super().__init__(parent)
        self.info = info
        self.setWindowTitle("Import File IFC")
        self.setModal(True)
        self.setMinimumWidth(560)

        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 22)
        root.setSpacing(12)

        judul = QLabel("Konfirmasi Import File IFC")
        judul.setObjectName("judulHalaman")
        sub = QLabel("File valid. Periksa ringkasan di bawah, lalu tekan Import untuk memproses.")
        sub.setObjectName("subjudul")
        sub.setWordWrap(True)
        root.addWidget(judul)
        root.addWidget(sub)

        # --- Informasi file ---
        kartu = QFrame()
        kartu.setObjectName("kartu")
        form = QFormLayout(kartu)
        form.setLabelAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        form.setContentsMargins(18, 14, 18, 14)
        form.setHorizontalSpacing(18)
        form.setVerticalSpacing(8)

        def baris(label, nilai):
            kiri = QLabel(label)
            kiri.setObjectName("formLabel")
            kanan = QLabel(nilai)
            kanan.setWordWrap(True)
            kanan.setTextInteractionFlags(Qt.TextSelectableByMouse)
            form.addRow(kiri, kanan)

        baris("Nama file", info.nama_file)
        baris("Ukuran", info.ukuran_teks)
        baris("Versi IFC", info.skema)
        baris("Dibuat dengan", info.aplikasi or "-")
        baris("Satuan panjang", info.satuan_panjang)
        if info.lantai:
            daftar = ", ".join(f"{nama} ({_elevasi(elev)})" for nama, elev in info.lantai)
            baris("Lantai", f"{len(info.lantai)} lantai: {daftar}")
        else:
            baris("Lantai", "Tidak ada IfcBuildingStorey (pemisahan per lantai tidak tersedia)")
        root.addWidget(kartu)

        # --- Jumlah elemen per kelas ---
        bagian = QLabel(f"ELEMEN TERDETEKSI  ·  {info.total_elemen} elemen")
        bagian.setObjectName("bagian")
        root.addWidget(bagian)

        urut = [k for k in ElementType if k in info.jumlah_per_kelas]
        tabel = QTableWidget(len(urut), 3)
        tabel.setHorizontalHeaderLabels(["KELAS", "ENTITAS IFC", "JUMLAH"])
        tabel.verticalHeader().setVisible(False)
        tabel.setEditTriggers(QAbstractItemView.NoEditTriggers)
        tabel.setSelectionMode(QAbstractItemView.NoSelection)
        tabel.setFocusPolicy(Qt.NoFocus)
        tabel.setAlternatingRowColors(True)
        tabel.setShowGrid(False)
        header = tabel.horizontalHeader()
        header.setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        tabel.horizontalHeaderItem(2).setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        for r, kelas in enumerate(urut):
            tabel.setItem(r, 0, QTableWidgetItem(LABEL[kelas]))
            tabel.setItem(r, 1, QTableWidgetItem(kelas.value))
            jml = QTableWidgetItem(str(info.jumlah_per_kelas[kelas]))
            jml.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            tabel.setItem(r, 2, jml)
        tabel.verticalHeader().setDefaultSectionSize(30)
        tabel.setFixedHeight(min(48 + 30 * max(len(urut), 1), 360))
        root.addWidget(tabel)

        ada_utama = any(k in KELAS_UTAMA for k in info.jumlah_per_kelas)
        if not ada_utama:
            peringatan = QLabel(
                "Tidak ada elemen struktural (kolom, balok, pelat, atap, dinding, atau fondasi). "
                "Model MEP biasanya tidak berisi elemen ini, sehingga RAB struktural tidak dapat dihitung."
            )
            peringatan.setObjectName("peringatan")
            peringatan.setWordWrap(True)
            root.addWidget(peringatan)

        # --- Nama proyek ---
        root.addSpacing(6)
        label_nama = QLabel("Nama proyek")
        label_nama.setObjectName("formLabel")
        self.edit_nama = QLineEdit(info.nama_file.rsplit(".", 1)[0])
        self.edit_nama.setPlaceholderText("Nama proyek")
        root.addWidget(label_nama)
        root.addWidget(self.edit_nama)

        # --- Tombol ---
        tombol = QHBoxLayout()
        tombol.addStretch()
        btn_batal = QPushButton("Batal")
        btn_batal.setObjectName("btnSecondary")
        btn_batal.clicked.connect(self.reject)
        self.btn_import = QPushButton("Import")
        self.btn_import.setObjectName("btnPrimary")
        self.btn_import.setDefault(True)
        self.btn_import.setEnabled(ada_utama)
        self.btn_import.clicked.connect(self.accept)
        self.edit_nama.textChanged.connect(
            lambda t: self.btn_import.setEnabled(ada_utama and bool(t.strip()))
        )
        tombol.addWidget(btn_batal)
        tombol.addWidget(self.btn_import)
        root.addLayout(tombol)

    def nama_proyek(self) -> str:
        return self.edit_nama.text().strip()


def tampilkan_hasil_proses(parent, judul: str, r: dict) -> None:
    """Pesan ringkas hasil parsing + rule engine; seluruh peringatan bisa dibuka di 'Tampilkan Rincian'."""
    from PySide6.QtWidgets import QMessageBox

    kotak = QMessageBox(parent)
    kotak.setWindowTitle(judul)
    teks = f"{r['elemen']} elemen terbaca, {r['baris_hasil']} baris estimasi dibuat."
    if r["baris_hasil"] == 0:
        kotak.setIcon(QMessageBox.Warning)
        teks += (
            "\n\nTidak ada kuantitas pekerjaan yang dapat dihitung. Pastikan model berisi "
            "kolom, balok, pelat, atap, dinding, atau fondasi."
        )
    else:
        kotak.setIcon(QMessageBox.Information)
    if r["peringatan"]:
        teks += f"\n\n{len(r['peringatan'])} peringatan (elemen dengan data dimensi kosong). Klik 'Tampilkan Rincian' untuk melihat."
        kotak.setDetailedText("\n".join(r["peringatan"]))
    kotak.setText(teks)
    kotak.exec()
