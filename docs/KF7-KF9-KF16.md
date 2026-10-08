# KF-7 Penyimpanan Proyek, KF-9 Multi-Project, dan KF-16 Navigasi Data

## KF-7: Simpan dan buka proyek (UC-06)

Semua data proyek tersimpan otomatis di database SQLite lokal setiap kali ada perubahan, sehingga tidak ada
data yang hilang bila aplikasi ditutup. KF-7 menambahkan dua hal:

### 1. File proyek `.coststruct`

| Aksi | Tempat |
|---|---|
| **Simpan File Proyek** (Ctrl+S) | Menu **Proyek ▾** di Hasil Estimasi, atau klik kanan proyek → *Simpan sebagai file* |
| **Buka File Proyek** (Ctrl+O) | Tombol di Daftar Proyek |

File `.coststruct` adalah arsip ZIP (`src/database/berkas_proyek.py`) berisi:
- `proyek.json`, yang memuat:
  - info proyek dan **parameter aturan**;
  - elemen, termasuk dimensi yang diubah pengguna;
  - tipe penulangan dan biaya tidak langsung;
  - hasil estimasi: volume, harga khusus, catatan, dan rumus;
  - potret **harga satuan beserta komponen analisa** setiap pekerjaan yang dipakai.
- `model.ifc` (opsional, ditawarkan bila file > 5 MB), supaya proyek bisa dihitung ulang di komputer lain.

Saat dibuka, proyek ditambahkan sebagai proyek baru dan model IFC disalin ke folder file proyek. Nama yang sudah
ada tidak ditimpa. Pekerjaan dirujuk dengan kode (mis. `BTN.KOLOM`), sehingga file bisa dibuka di database lain.
Bila harga master di komputer tujuan berbeda, muncul banner "harga satuan sudah berubah" (KF-5). Bila kode
pekerjaan tidak dikenal, pekerjaan dibuat dari potret harga di file.

Penanganan kesalahan (KF-14):
- file bukan ZIP atau rusak;
- format salah;
- dibuat versi aplikasi yang lebih baru;
- pekerjaan tidak dikenal tanpa data harga.

Semua menampilkan pesan yang jelas, dan database tidak berubah (transaksi dibatalkan). File ditulis ke file
sementara dulu, sehingga file lama tidak rusak bila penyimpanan gagal.

### 2. Parameter aturan per proyek

Menu **Proyek ▾ → Parameter Aturan** mengatur asumsi rule engine untuk proyek tersebut:

| Kelompok | Parameter |
|---|---|
| Fondasi batu kali turunan | lebar atas, lebar bawah, tinggi |
| Sumuran turunan | diameter, kedalaman, jumlah per kolom, ukuran poer |
| Pekerjaan tanah | ruang kerja galian, tebal pasir fondasi/sloof/lantai, lantai kerja, kedalaman footplate |
| Pembesian cadangan | rasio kg/m³ kolom, balok, sloof, pelat, fondasi |
| Dinding, atap, pintu | sisi plester/cat, batas kemiringan dak, engsel per pintu |

- Nilai yang berbeda dari bawaan ditandai.
- Hanya nilai yang berubah yang disimpan (kolom `proyek.parameter`, JSON).
- Nilai divalidasi terhadap rentang wajar.
- Menyimpan parameter menjalankan `hitung_ulang_dari_elemen()`: rule engine dihitung ulang dari elemen
  tersimpan tanpa membaca IFC lagi.
  - **Tetap dipertahankan:** dimensi yang diubah pengguna (KF-19), harga khusus, dan catatan (KF-6).
  - **Diganti:** volume yang diedit manual (jumlahnya diberitahukan sebelum menyimpan).
- Estimasi ulang dari IFC dan hitung ulang penulangan juga memakai parameter proyek.
- Perubahan parameter bisa diurungkan (Ctrl+Z).

## KF-9: Kelola banyak proyek

| Fitur | Implementasi |
|---|---|
| **Info proyek** | Nama, lokasi, pemilik/instansi, tahun anggaran. Dipakai otomatis sebagai kop dialog Export |
| **Ganti file IFC** | Di dialog Info Proyek, dengan pilihan langsung hitung ulang dari model baru |
| **Duplikat proyek** | Salinan lengkap dan terpisah, mis. untuk membandingkan alternatif material atau versi desain |
| Akses | Menu **Proyek ▾** di Hasil Estimasi, atau klik kanan pada Daftar Proyek |

Validasi (KF-14):
- Nama wajib diisi, maksimal 120 karakter.
- Tahun anggaran harus 2000–2100.
- File harus berekstensi `.ifc` dan benar-benar ada.

## KF-16: Pencarian, filter, dan pengurutan

| Halaman | Cari | Filter | Urut (klik judul kolom) |
|---|---|---|---|
| Daftar Proyek | nama / file | – | semua kolom |
| Hasil Estimasi | pekerjaan, elemen, lantai, kode, tipe | kategori, lantai (KF-12) | Rekap: item di dalam tiap kategori. Per Lantai: lantai & kategori. Detail: semua kolom |
| Harga Satuan → Harga Dasar | nama | jenis, hanya yang dipakai | semua kolom |
| Harga Satuan → Analisa | kode / uraian | kategori | semua kolom |

Kolom angka (volume, harga, jumlah) diurutkan sebagai angka, bukan teks. Contoh: Rp 950.000 < Rp 1.250.000
< Rp 12.000.000 (`tema.SelUrut`). Di Hasil Estimasi:
- klik pertama mengurutkan naik;
- klik kedua mengurutkan turun;
- klik ketiga mengembalikan urutan semula.

Mode RAB Rinci tetap mengikuti susunan tipe elemen.

## Pengujian

| Berkas | Isi |
|---|---|
| `tests/test_kf7_kf9_proyek.py` | parameter per proyek + validasi, hitung ulang dari elemen (harga khusus, catatan & dimensi dipertahankan), undo parameter, simpan/buka `.coststruct` (data, IFC, parameter, tipe, biaya, total sama), file tidak valid, duplikat terpisah, validasi info proyek |
| `tests/test_kf16_urut.py` | urut angka vs teks, urut Detail naik/turun/asal, urut Rekap per kategori, urut harga dasar |
