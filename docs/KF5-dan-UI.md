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
- **Kembalikan ke bawaan**: kembali ke harga HSPK Kota Bandung 2027.
- **Status harga**: `HSPK`, `Diubah`, `Tambahan`. Filter *Hanya yang dipakai pekerjaan* (aktif secara
  default) menyaring 3.680 harga dasar HSPK menjadi yang dipakai analisa, yang diubah, dan tambahan pengguna.
- **Tab Analisa Pekerjaan (AHSP)**: rincian A/B/C/BUK setiap pekerjaan. Komponen tambahan (misalnya sewa
  alat) bisa ditambahkan dan dihapus. Komponen bawaan AHSP dijaga tetap utuh.
- **Pembaruan seed tidak menimpa edit pengguna**: harga yang diubah dan komponen tambahan tetap tersimpan.
- **UC-02 alternatif**: halaman hasil estimasi menampilkan banner bila harga satuan sudah berubah
  atau ada item berharga nol, lengkap dengan tombol *Perbaiki Harga*.

Kode: `src/database/harga_repository.py`, `src/gui/harga_page.py`. Tes: `tests/test_kf5_harga.py`.

## Harga default: HSPK Kota Bandung 2027

Harga awal aplikasi diambil dari workbook *HSPK Kota Bandung 2027 (update setelah rapat 27 Agustus)*:

- **3.680 harga dasar** (44 upah, 3.458 material, 178 peralatan) dari sheet `HSD (Upah)`,
  `HSD (Material)`, dan `HSD (Peralatan)`.
- **542 analisa pekerjaan** dari 16 sheet bab. Hasil rekonstruksi (koefisien × harga × 1,10)
  cocok dengan harga F dokumen untuk 541 analisa. Satu-satunya yang tidak cocok adalah kaca cermin
  3.12.7, yang tidak dipakai aplikasi.

Data dibuat oleh `tools/impor_hspk.py` menjadi `src/database/hspk_bandung_2027.py`. Bila ada HSPK versi
baru, jalankan ulang lalu naikkan `SEED_VERSI`:

```
python tools/impor_hspk.py "HSPK_Kota_Bandung_2027.xlsx"
```

Pemetaan kode pekerjaan aplikasi ke item HSPK (`PEMETAAN` di `src/database/seed_data.py`):

| Kode aplikasi | Item HSPK | Harga satuan |
|---|---|---|
| FDN.BATUKALI | 2.2.2.1.6 Pondasi batu belah mortar tipe N (1SP : 4PP), manual | Rp 1.601.728 /m³ |
| BTN.SUMURAN | 2.2.2.2.6 Pondasi sumuran diameter 100 cm masif | Rp 1.786.529 /m³ |
| BTN.* (kolom, balok, pelat, dak, sloof, telapak) | 2.2.1.4.5 Beton f'c 20 MPa, manual | Rp 2.349.627 /m³ |
| BSI.KOLOM / BALOK / SLOOF | 2.2.1.1.3a Penulangan kolom/balok/sloof BjTS < 12 mm, manual | Rp 36.469 /kg |
| BSI.PELAT / DAK / FONDASI | 2.2.1.1.1a Penulangan slab BjTS < 12 mm, manual | Rp 30.540 /kg |
| BSK.FONDASI / SLOOF / KOLOM / BALOK / PELAT | 2.2.1.3.1 – 2.2.1.3.5 Bekisting (3 kali pakai) | Rp 246.979 – 413.951 /m² |
| DND.BATA | 3.6.1.8 Dinding bata merah 1/2 batu, mortar tipe N (1SP : 4PP) | Rp 426.435 /m² |
| PLS.DINDING / ACI.DINDING | 3.7.4 Plesteran 1SP : 4PP 15 mm / 3.7.8 Acian | Rp 98.457 / 80.889 /m² |
| KRM.LANTAI / KRM.DINDING | 3.9.8.6 Keramik lantai 40x40 polished / 3.10.1.4 Keramik dinding 20x20 | Rp 242.542 / 473.102 /m² |
| PTU.DAUN / KUSEN / KUNCI / ENGSEL | 3.11.1.11 / 3.11.3.5 / 3.11.4.2 / 3.11.4.5 | per m² / m' / buah |
| JDL.JENDELA | 3.11.1.6 Jendela kaca 6 mm rangka aluminium | Rp 1.134.602 /m² |
| ATP.RANGKA / ATP.PENUTUP | 2.1.1.1 Rangka atap pelana baja ringan C75 / 3.1.1.4 Genteng beton | Rp 266.780 / 209.670 /m² |
| PLF.RANGKA / PLF.GYPSUM | 3.5.3.1 Rangka hollow 40.40 / 3.5.2.1 Gypsum 9 mm | Rp 241.875 / 78.560 /m² |
| CAT.DINDING | 3.8.10.1 Cat tembok baru interior (1 dasar + 2 penutup) | Rp 82.542 /m² |

Bahan dengan nama sama digabung tanpa membedakan huruf besar/kecil (misalnya "Semen Portland (PC)"
dipakai oleh 13 pekerjaan). `tests/test_hspk.py` memastikan harga satuan setiap pekerjaan di aplikasi
sama dengan harga F dokumen (selisih ≤ Rp 1).

**Temuan pada data HSPK** (dipakai apa adanya, bisa dikoreksi lewat menu Harga Satuan):

1. Air untuk beton Rp 1.854 per liter. Pada beton f'c 20 MPa (202 liter/m³) ini menjadi Rp 412 ribu/m³,
   atau 17,5% harga beton. Kemungkinan harga per m³ tertulis per liter.
2. "Paku 12 cm" tercatat Rp 1.200 per **buah** di daftar HSD, tetapi analisa bekisting kolom/balok dan
   kusen memakai satuan **kg**. Akibatnya paku dihargai Rp 1.200/kg.
3. Kusen kayu 6x15 (3.11.3.5) memakai lem kayu 1 kg per m' kusen (42,5% harga kusen).

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
