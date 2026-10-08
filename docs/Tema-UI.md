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
