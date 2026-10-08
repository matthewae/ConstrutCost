# Tema & Pembaruan Antarmuka

Skema warna bawaan diganti dari biru ke **hitam–kuning**, mengikuti identitas PT Mandajaya Rekayasa Konstruksi.
Kuning `#F9D759` diambil dari logo perusahaan.

## Pilihan tema

Tema dipilih di **Pengaturan → Tampilan**: klik kartu tema, lalu **Simpan Pengaturan**.

| Tema | Kegunaan | Ciri |
|---|---|---|
| **Hitam Kuning** (bawaan) | Pemakaian sehari-hari | Latar hitam, aksen dan tombol utama kuning logo, teks tombol gelap |
| **Terang Emas** | Presentasi ke klien atau ruangan terang | Latar krem terang, sidebar hitam, tombol utama kuning, aksen emas tua agar teks tetap terbaca |
| **Biru Malam** | Tema gelap versi lama | Latar biru gelap |
| **Terang Biru** | Tema terang versi lama | Latar putih, aksen biru |

Pengguna lama yang menyimpan tema "gelap" sebelum versi ini otomatis dipindah ke Hitam Kuning, satu kali saja.
Penandanya `versi_tema` di preferensi.

## Ketentuan teknis

- Semua warna adalah token di `PALET` (`src/gui/tema.py`); stylesheet dibangun dari token tersebut.
- Token yang tidak diisi sebuah tema dilengkapi `_lengkapi`.
- Tombol utama memakai token `tombol_utama` / `tombol_utama_teks`, terpisah dari warna aksen.
  Dengan begitu tombol kuning tetap bertulisan gelap, dan aksen emas di tema terang tetap kontras dengan latar putih.
- Tes `tests/test_kf10_preferensi.py` memeriksa kontras **WCAG ≥ 4,5:1** untuk teks utama, teks redup, teks tombol utama,
  dan aksen pada setiap tema.

## Perbaikan UI/UX

**Navigasi**
- Sidebar hitam; menu aktif ditandai garis kuning di kiri.
- Logo aplikasi mengikuti warna tema, termasuk splash screen dan ikon jendela.

**Hasil Estimasi**
- Toolbar dibuat dua baris.
- Banner keterangan mode menjelaskan beda Rekap RAB, RAB Rinci, Detail per Elemen, dan Per Lantai.
- Di layar sempit, tombol header disembunyikan dan tetap tersedia di menu **Proyek ▾**.

**Pengaturan**
- Pemilih tema berupa kartu pratinjau.
- Pilihan isi dokumen disusun dalam tiga kolom.

**Dialog**
- Isi dialog Export dan Parameter bisa digulir, dan latarnya mengikuti tema (tidak ada lagi jalur putih).
- Tombol Export selalu terlihat.
- Label form tidak terpotong dan isian sejajar (Tipe Penulangan, Biaya Tidak Langsung, Info Proyek).
- Judul tabel Import rata kiri, sama dengan isinya.

**Harga Satuan**
- Panel ubah harga lebih ramping, sehingga kolom STATUS terlihat di layar 1280 px.

## Modernisasi tampilan (tahap 2)

**Splash screen**
- Kartu lebih lebar dengan garis aksen di atas dan cahaya lembut di belakang logo.
- Ditambah deskripsi singkat aplikasi dan chip fitur: IFC2x3 · IFC4, QTO otomatis, RAB · AHSP, Excel & PDF.
- Kaki splash berisi nama aplikasi, versi, dan keterangan bahwa data disimpan lokal (offline).

**Sidebar**
- Menu utama dengan item lebih lega.
- Zona **Import file IFC** yang bisa diklik atau dijadikan tempat menyeret file.
- Status *Offline · data lokal* dan nomor versi.

**Komponen bersama** (`src/gui/tema.py`)
- `LencanaIkon` / `kepala_dialog()`: lencana ikon, judul, dan keterangan. Dipakai seragam di dialog Export, Import,
  Info Proyek, Ubah Dimensi, Tipe Penulangan, Biaya Tidak Langsung, Parameter, dan Pratinjau.
- Ikon vektor baru: cari, panel, info, tanya, peringatan, galat, sukses, folder, parameter, dimensi, kubus, besi,
  kalender, import, tutup, Rp, %.
- **Kotak pesan** (konfirmasi dan galat):
  - ikon bawaan Windows diganti lencana berwarna sesuai jenis pesan;
  - judul pesan tebal;
  - tepi lebih lega.
- **Kotak pencarian** diberi ikon kaca pembesar.
- **Tabel kosong** menampilkan petunjuk di tengah, mis. "Belum ada biaya tidak langsung".
- **Toast**: lencana sukses / peringatan / galat.
- **Kartu angka** di halaman Proyek diberi ikon.

**Gaya**
- Sudut membulat 10–14 px.
- Tombol mode (Rekap RAB / RAB Rinci / Per Lantai / Detail) berupa *segmented control*; mode aktif terisi warna tombol utama.
- Judul tabel diberi latar.
- Garis pemisah panel menyala saat disorot.
- Keterangan mode diberi garis aksen di kiri.
- Warna kategori pekerjaan di tema Hitam Kuning / Terang Emas memakai palet hangat yang serasi dengan kuning logo.
  Kontrasnya ≥ 4,5:1.

**UX**
- Hasil Estimasi: tombol **Rincian** (Ctrl+B) menyembunyikan atau menampilkan panel Rincian Perhitungan, sehingga
  tabel memakai seluruh lebar layar laptop.
- Pengaturan:
  - tiap kartu punya ikon, judul, dan keterangan;
  - bilah **Simpan / Batalkan / Reset** menempel di bawah layar;
  - status *Tersimpan* atau *Ada perubahan belum disimpan* selalu terlihat.
- Dialog Export **responsif**:
  - di layar < 980 px, kartu angka disusun 2 × 2;
  - isian kop dokumen menjadi satu kolom;
  - opsi disusun dua kolom, sehingga tidak perlu menggulir ke samping.
- Ubah Dimensi: isian kosong (–) langsung kosong saat diklik, siap diketik.

Logo perusahaan belum dimasukkan ke aplikasi (aplikasi masih untuk penelitian). Hanya warna kuning logo yang dipakai di tema.
Tes: `tests/test_ui_modern.py`.
