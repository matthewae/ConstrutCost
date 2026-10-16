# KF-4 Pekerjaan Tanah, KF-6 Edit Hasil Estimasi, dan KF-12 Multi Lantai

## KF-4: Pekerjaan tanah

Seperti RAB konsultan (misalnya bab *PEK. TANAH* pada RAP SMK N 6 Bandung), volume pekerjaan tanah
diturunkan dari fondasi dan lantai dasar yang sudah dihitung rule engine (`src/rules/tanah.py`):

| Sumber | Pekerjaan | Rumus |
|---|---|---|
| Fondasi batu kali (dimodelkan atau turunan dinding lantai dasar) | Galian | (B_bawah + 2 rk) × (H + t_pasir) × L |
| | Urugan pasir bawah fondasi | B_bawah × t_pasir × L |
| | Urugan tanah kembali | V_galian − V_batu kali − V_pasir |
| Fondasi telapak (footplate) | Galian | (P + 2 rk)(B + 2 rk) × (kedalaman + t_lantai kerja) |
| | Lantai kerja f'c 7,5 MPa | P × B × t_lantai kerja |
| | Urugan tanah kembali | V_galian − V_footplate − V_lantai kerja |
| Sumuran + poer (turunan kolom lantai dasar) | Galian | n·π d²/4·H + (P + 2 rk)(L + 2 rk)·T |
| | Urugan tanah kembali | V_lubang poer − V_poer |
| Tiang (IfcPile) | Galian | V tiang |
| Sloof | Urugan pasir bawah sloof | b × t_pasir × L |
| Pelat lantai dasar | Urugan pasir bawah lantai | A × t_pasir |
| Lantai dasar tanpa pelat beton (luas ruang / penutup lantai) | Urugan pasir + rabat beton | A × t_pasir; A × t_rabat |

Asumsi (`src/rules/parameter.py`):
- Ruang kerja galian 10 cm tiap sisi.
- Pasir 5 cm.
- Lantai kerja/rabat 5 cm.
- Dasar footplate 1,0 m dari muka tanah.

Item galian dipilih menurut kedalaman:

| Kedalaman | Item HSPK | Harga satuan |
|---|---|---|
| 0 – 1 m | 1.2.1.1.1 | Rp 194.855 /m³ |
| > 1 – 2 m | 1.2.1.1.4 | Rp 233.605 /m³ |
| > 2 – 3 m | 1.2.1.1.6 | Rp 277.867 /m³ |

**Harga.** Workbook HSPK Kota Bandung 2027 tidak memuat analisa urugan, sehingga dibuat analisa tambahan
(`src/database/ahsp_tambahan.py`) dengan koefisien **SNI 2835:2008** dan harga dasar HSPK:

| Kode | Analisa | Koefisien | Harga satuan |
|---|---|---|---|
| SNI-2835-6.9 | 1 m³ urugan tanah kembali | Pekerja 0,192 OH; Mandor 0,019 OH | Rp 50.064 |
| SNI-2835-6.11 | 1 m³ urugan pasir | Pasir urug 1,2 m³; Pekerja 0,3 OH; Mandor 0,01 OH | Rp 450.613 |
| 2.2.1.4.1 (HSPK) | Lantai kerja / rabat beton f'c 7,5 MPa | sesuai HSPK | Rp 2.346.944 |

Sheet *Galian Tanah* di HSPK memakai upah Pekerja Rp 219.263,24 dan Mandor Rp 334.030,78, berbeda dari
daftar HSD (Rp 206.513,24 dan Rp 308.530,78). Agar harga satuan galian tetap sama dengan harga F dokumen,
seed membuat sumber daya varian "Pekerja (Galian Tanah)" dan "Mandor (Galian Tanah)". Aturan ini berlaku
umum: setiap analisa yang dipakai dan memakai harga berbeda untuk nama yang sama otomatis mendapat varian.

## KF-6: Edit hasil estimasi (UC-03)

| Kebutuhan | Implementasi |
|---|---|
| Edit volume | Kolom *Volume (Edit)* pada mode Detail per Elemen |
| Edit harga satuan | Kolom *Harga Satuan (Edit)* per baris; panel rekap memiliki tombol **Pakai Harga Ini** untuk semua baris satu pekerjaan di proyek ini (mis. harga negosiasi). Harga master tidak berubah, dan "Terapkan Harga Terbaru" tidak menimpa harga khusus. Tombol **Kembalikan Harga Master** tersedia |
| Catatan | Kolom catatan per baris di panel rincian (maks. 500 karakter), ikut di sheet *Detail Elemen* |
| Subtotal & total otomatis | Langsung dihitung ulang setelah setiap perubahan |
| Input tidak valid (Alternatif A) | Volume tidak bisa negatif, harga harus > 0. Nilai dikembalikan dan muncul pesan |
| **Undo / redo** (Alternatif B) | Tombol **↶ Urungkan / ↷ Ulangi**, Ctrl+Z / Ctrl+Y, hingga 50 langkah |
| Pratinjau | Tombol **Pratinjau** di dialog Export menampilkan laporan PDF dengan pilihan isi & kolom saat ini, lalu **Export Sekarang** |
| Simpan | Setiap perubahan langsung tersimpan ke SQLite (tidak ada data yang hilang bila aplikasi ditutup) |

Undo/redo bekerja dengan potret data proyek (`src/database/riwayat_repository.py`). Data yang dipotret adalah
hasil estimasi, elemen, tipe penulangan, dan biaya tidak langsung. Potret diambil sebelum dan sesudah setiap
perubahan, sehingga perubahan yang menyentuh banyak tabel tetap bisa dibatalkan utuh. Perubahan yang tercakup:
- edit volume, harga, dan catatan;
- ubah dimensi (KF-19);
- tipe penulangan;
- biaya tidak langsung;
- terapkan harga terbaru;
- hitung ulang dari IFC.

## KF-12: Multi lantai

- **Filter lantai** di toolbar Hasil Estimasi. Lantai diurutkan menurut elevasi. Filter ini berlaku untuk mode
  Rekap RAB, RAB Rinci, dan Detail. Label di toolbar menampilkan subtotal lantai yang dipilih.
- **Mode Per Lantai**: biaya tiap lantai dirinci per kategori, beserta jumlah elemen, elevasi, dan bobot.
  Klik dua kali nama lantai untuk membuka rekap RAB lantai itu saja.
- **Export**: sheet/halaman *Rekap per Lantai*, dengan baris "Selisih terhadap sheet RAB" yang bernilai 0.

## Pengujian

| Berkas | Isi |
|---|---|
| `tests/test_kf4_tanah.py` | kode galian per kedalaman, batu kali turunan, footplate, sumuran, sloof, lantai dasar (pelat vs rabat), harga galian = HSPK & urugan = SNI, AC20 punya bab Tanah |
| `tests/test_kf6_edit.py` | harga khusus baris + tidak ditimpa "terapkan harga", catatan, potret/pulihkan proyek, undo/redo di halaman, pratinjau PDF |
| `tests/test_kf12_lantai.py` | urutan lantai, total per lantai = total proyek, baris tanpa lantai, filter lantai di halaman, export rekap per lantai |
