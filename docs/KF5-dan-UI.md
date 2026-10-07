# KF-5 Manajemen Harga Satuan dan Pembaruan Antarmuka

## KF-5 (UC-04 Kelola Harga Satuan)

Struktur harga mengikuti susunan AHSP dengan dua tingkat:

| Tingkat | Tabel | Isi |
|---|---|---|
| Harga satuan dasar | `sumber_daya` | Bahan, upah, dan alat: nama, satuan, harga, merk, sumber harga |
| Analisa harga satuan pekerjaan | `komponen_harga` | Koefisien × harga dasar per pekerjaan |

Satu bahan dipakai bersama oleh semua pekerjaan. Contohnya Semen PC dipakai di 5 analisa:
bata, plester, keramik lantai, keramik dinding, dan batu kali. Karena itu harga cukup diubah sekali.

Harga satuan pekerjaan = (A bahan + B upah + C alat) + biaya umum & keuntungan 10%.

| Langkah UC-04 | Implementasi |
|---|---|
| 1–2 Buka halaman, tampilkan daftar harga | Menu **Harga Satuan** → tab *Harga Dasar* |
| 3–5 Pilih item, isi harga baru | Panel kanan: merk dan harga per satuan |
| 6 Validasi angka positif | `HargaTidakValid`: "Harga harus lebih besar dari nol." |
| 7 Simpan ke SQLite + catat | `sumber_daya` diperbarui, perubahan dicatat di `riwayat_harga` |
| 8 Notifikasi | Toast "Harga satuan berhasil diperbarui" |
| 9–10 Terapkan ke estimasi | Banner **Terapkan ke Estimasi** menghitung ulang subtotal semua proyek; volume (termasuk edit manual) tidak berubah, lalu kembali ke halaman hasil estimasi |
| Alternatif: Tambah material | Tombol **Tambah Material**: jenis, nama, satuan, merk, harga |

Fitur tambahan:
- **Kembalikan ke bawaan**: kembali ke harga dari data seed (HSPK / placeholder).
- **Status harga**: `HSPK`, `Placeholder`, `Proxy HSPK`, `Diubah`, `Tambahan`. Filter *Hanya yang belum
  diverifikasi* menampilkan harga yang masih harus diganti dengan harga sebenarnya.
- **Tab Analisa Pekerjaan (AHSP)**: rincian A/B/C/BUK setiap pekerjaan. Komponen tambahan (misalnya sewa
  alat) bisa ditambahkan dan dihapus. Komponen bawaan AHSP dijaga tetap utuh.
- **Pembaruan seed tidak menimpa edit pengguna**: harga yang diubah dan komponen tambahan tetap tersimpan.
- **UC-02 alternatif**: halaman hasil estimasi menampilkan banner bila harga satuan sudah berubah
  atau ada item berharga nol, lengkap dengan tombol *Perbaiki Harga*.

Kode: `src/database/harga_repository.py`, `src/gui/harga_page.py`. Tes: `tests/test_kf5_harga.py`.

## Antarmuka

- **Satu jendela dengan menu samping** (`gui/main_window.py`): Proyek dan Harga Satuan. Halaman hasil
  estimasi terbuka di jendela yang sama, dengan tombol kembali (Esc).
- **Tema terpusat** (`gui/tema.py`): satu palet warna dan satu stylesheet untuk semua halaman dan dialog,
  angka berformat Indonesia (1.234,56), ikon vektor, toast notifikasi, dan banner.
- **Daftar Proyek**: kolom jumlah elemen dan total RAB per proyek, kartu nilai RAB semua proyek,
  penanda file IFC yang hilang, dan menu klik kanan.
- **Hasil Estimasi**:
  - Mode *Rekap RAB*: dikelompokkan per kategori dengan angka romawi, jumlah per kategori, dan persentase.
  - Mode *Detail per Elemen*: volume bisa diedit.
  - Panel rincian: dimensi elemen beserta asalnya (Qto IFC / geometri) dan rumus rule engine. Pada mode
    rekap, panel menampilkan analisa harga satuan pekerjaan.
  - Tombol *Hitung Ulang dari IFC* dengan konfirmasi.
- **Titik masuk**: `python src/main.py`, yang juga dipakai untuk PyInstaller.
