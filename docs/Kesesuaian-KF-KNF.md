# Kesesuaian dengan Kebutuhan Fungsional (KF) dan Non-Fungsional (KNF)

Acuan: Tabel 3.1 (KF-1 s.d. KF-19) dan Tabel 3.2 (KNF-1 s.d. KNF-9) naskah skripsi.
Bukti diambil dari kode dan tes otomatis (`python -m pytest`, 286 tes lulus di Linux dan Windows).

## Kebutuhan fungsional

| Kode | Fitur | Implementasi di CostStruct | Bukti uji | Status |
|---|---|---|---|---|
| KF-1 | Import File IFC | Pemeriksaan ekstensi, header ISO-10303-21, penutup file, skema IFC2x3/IFC4, dan `IfcProject`. Pembacaan file dilakukan di proses terpisah; ringkasan ditampilkan sebelum import | `test_kf1_validasi.py` | Sesuai |
| KF-2 | Parser & Klasifikasi Geometri | Elemen diklasifikasikan menjadi kolom, balok, pelat, atap, dinding, fondasi, tiang, pintu, jendela, lantai, plafon, dan ruang. Dimensi diambil dari Qto/BaseQuantities/PSet; bila tidak ada, dari geometri | `test_kf2_ekstraksi.py` | Sesuai |
| KF-3 | Rule-Based Processing | Aturan IF–THEN per kelas elemen menentukan item pekerjaan (beton, bekisting, pembesian, pasangan, plesteran, dst.) | `test_kf3_kf4_rules.py`, `test_penulangan.py` | Sesuai |
| KF-4 | Perhitungan QTO | Volume, luas, panjang, berat besi (Rumus 2.30–2.33), dan pekerjaan tanah dihitung per elemen | `test_kf3_kf4_rules.py`, `test_kf4_tanah.py` | Sesuai |
| KF-5 | Manajemen Harga Satuan | Ubah harga dan merk bahan, upah, serta alat; tambah material; harga bawaan HSPK | `test_kf5_harga.py`, `test_hspk.py` | Sesuai |
| KF-6 | Edit Hasil Estimasi | Edit volume, harga khusus, dan catatan; undo/redo; pratinjau PDF | `test_kf6_edit.py` | Sesuai |
| KF-7 | Penyimpanan Proyek | File `.coststruct` berisi elemen, aturan (parameter), harga, dan hasil estimasi; bisa disimpan dan dibuka | `test_kf7_kf9_proyek.py`, `test_ketahanan.py` | Sesuai |
| KF-8 | Export Excel & PDF | Laporan RAB `.xlsx` (rumus aktif) dan `.pdf` | `test_kf17_export.py`, `test_kf12_lantai.py`, `test_kebutuhan_lantai.py` | Sesuai |
| KF-9 | Multi-Project | Daftar proyek, info proyek, ganti nama, duplikat, ganti file IFC, hapus | `test_kf7_kf9_proyek.py` | Sesuai |
| KF-10 | User Preference | Tema (4 pilihan), direktori default, dan format laporan, tersimpan di database | `test_kf10_preferensi.py`, `test_ui_modern.py` | Sesuai |
| KF-11 | Pajak & Markup | PPN 11% dan biaya umum & keuntungan 10% otomatis; konstanta, tidak bisa diubah pengguna | `test_kf13_biaya.py`, `test_pipeline.py` | Sesuai |
| KF-12 | Multi Lantai | Lantai dikenali dari `IfcBuildingStorey`; filter, rekap, dan rincian per lantai; satu sheet per lantai | `test_kf12_lantai.py`, `test_kebutuhan_lantai.py` | Sesuai |
| KF-13 | Ringkasan Biaya | Rekap per pekerjaan, biaya tidak langsung, PPN, total, dan terbilang | `test_kf13_biaya.py` | Sesuai |
| KF-14 | Notifikasi & Error Handling | Pesan galat berbahasa Indonesia beserta saran solusi, rincian teknis, dan toast | `test_knf8_kf14_kf15.py` | Sesuai |
| KF-15 | Logging Aktivitas | Import, estimasi, edit, harga, export, file proyek, dan galat dicatat di database serta log harian; ada halaman Riwayat Aktivitas | `test_knf8_kf14_kf15.py` | Sesuai |
| KF-16 | Navigasi Data | Pencarian, filter (kategori, lantai, jenis), dan pengurutan kolom di hasil estimasi, harga, proyek, dan aktivitas | `test_kf16_urut.py` | Sesuai |
| KF-17 | Custom Output Formatting | Pilihan kolom (No, Kode, Harga, Bobot, Rumus), isi dokumen, dan orientasi PDF | `test_kf17_export.py` | Sesuai |
| KF-18 | Detail Volume Breakdown | Panel Rincian Perhitungan menampilkan dimensi, sumber data, rumus, dan backup volume; tersedia kolom "Uraian rumus" di export | `test_kf3_kf4_rules.py`, `test_kebutuhan_lantai.py` | Sesuai |
| KF-19 | Recalculate QTO | Ubah dimensi elemen (mis. pelat 30×30 → 50×50) lalu QTO dan RAB dihitung ulang | `test_kf19_dimensi.py` | Sesuai |

## Kebutuhan non-fungsional

| Kode | Kebutuhan | Implementasi / hasil ukur | Bukti uji | Status |
|---|---|---|---|---|
| KNF-1 | Parsing ≤ 30 detik (file rumah tinggal hingga 50 MB) | Geometri elemen tanpa Qto dihitung paralel di semua inti CPU; hasilnya identik dengan perhitungan satu per satu. Hasil ukur ada di tabel di bawah | `test_knf_kinerja_integritas.py`, `tools/ukur_kinerja.py` | Sesuai |
| KNF-2 | Rule engine + RAB < 15 detik setelah parsing | 0,02–0,04 detik untuk 163–1.966 item RAB | `test_knf_kinerja_integritas.py` | Sesuai |
| KNF-3 | Konsistensi hasil | Input dan database yang sama menghasilkan baris RAB, total, dan isi Excel yang identik pada setiap percobaan | `test_knf_kinerja_integritas.py` | Sesuai |
| KNF-4 | Tidak crash saat ada galat | File rusak atau bukan .ifc dibaca di proses terpisah; `sys.excepthook` menampilkan peringatan tanpa menutup aplikasi | `test_kf1_validasi.py`, `test_knf8_kf14_kf15.py` | Sesuai |
| KNF-5 | Indikator proses | Dialog progres "Memproses file IFC" dengan i/n elemen (termasuk tahap geometri paralel); splash dengan progress bar dan tahap pemuatan | `test_ui_modern.py` (splash) | Sesuai |
| KNF-6 | Bahasa Indonesia baku | Seluruh teks UI, pesan galat, dan tombol bawaan Qt (OK/Batal/Ya/Tidak, menu klik kanan) berbahasa Indonesia | `test_knf8_kf14_kf15.py` | Sesuai (lihat catatan 1) |
| KNF-7 | Windows 11 64-bit, luring | Tidak ada akses jaringan di kode; data disimpan di `%APPDATA%\CostStruct`; gaya Qt Fusion, ikon taskbar, dan title bar gelap Windows. Seluruh tes lulus di Windows (CI `windows-latest`) | `.github/workflows/windows.yml`, `test_knf8_kf14_kf15.py` | Sesuai di Windows Server 2025 (CI); uji akhir di Windows 11 penelitian (catatan 2) |
| KNF-8 | Paket .exe mandiri | `CostStruct.spec` + `tools/build_exe.py`. Uji mandiri `CostStruct.exe` 6 tahap: database, validasi IFC di proses anak, parsing & rule engine, export Excel/PDF, file proyek, dan jendela utama Qt (gaya Fusion) | `.github/workflows/windows.yml`, `test_knf8_kf14_kf15.py` | Sesuai: `CostStruct.exe` dibuild & lulus uji mandiri di Windows (CI) |
| KNF-9 | Integritas database SQLite | Setiap proses tulis dalam satu transaksi; `PRAGMA synchronous=FULL`; `quick_check` saat aplikasi dibuka; cadangan harian. Diuji dengan `kill -9` saat menulis, 5 kali: database tetap `ok` dan hasil estimasi lengkap | `test_knf_kinerja_integritas.py`, `test_knf8_kf14_kf15.py` | Sesuai |

### Hasil ukur KNF-1 / KNF-2

Diukur dengan `python tools/ukur_kinerja.py <file.ifc>` (4 inti CPU, Linux):

| File | Ukuran | Elemen | Item RAB | Parsing (KNF-1) | Rule + RAB (KNF-2) |
|---|---|---|---|---|---|
| AC20-FZK-Haus.ifc | 2,5 MB | 44 | 163 | 1,3 s | 0,02 s |
| Duplex_A_20110907.ifc | 2,4 MB | 165 | 484 | 1,6 s | 0,02 s |
| SampleStructuralModel.ifc | 6,0 MB | 348 | 1.189 | 4,4 s | 0,03 s |
| rumah_50mb.ifc (sintetis, `tools/buat_ifc_uji.py`) | 53,4 MB | 447 | 1.966 | 13,4 s | 0,04 s |

Sebelum geometri dihitung paralel, parsing SampleStructuralModel memakan 12,4 s. Sekarang 4,4 s, dengan hasil
dimensi yang identik.

Untuk BAB IV, jalankan ulang alat ukur di laptop Windows 11 yang dipakai penelitian. Alat ini menyimpan
hasilnya ke `hasil_kinerja.csv`.

## Catatan

1. **Istilah Import/Export dan Quantity Take-Off** dipertahankan karena dipakai di naskah (nama KF-1, KF-8, dan
   judul penelitian) dan lazim di praktik estimasi. Bila penguji meminta bentuk baku KBBI, istilahnya cukup diganti
   menjadi "Impor/Ekspor" di teks antarmuka.
2. **KNF-7 dan KNF-8.** Setiap perubahan pada PR otomatis diuji di Windows lewat GitHub Actions (`windows-latest`,
   Windows Server 2025, 64-bit). Langkahnya:
   1. seluruh tes;
   2. ukur kinerja;
   3. build `CostStruct.exe`;
   4. uji mandiri `.exe`.

   Folder aplikasi siap pakai bisa diunduh dari tab **Actions → run terbaru → Artifacts → CostStruct-windows**.
   Ekstrak lalu jalankan `CostStruct.exe`; tidak perlu memasang Python. Untuk bukti BAB IV di Windows 11 64-bit
   penelitian:
   - jalankan `CostStruct.exe --uji-mandiri`;
   - buka aplikasi dengan Wi-Fi dimatikan;
   - lakukan import, estimasi, dan export.
3. **Pemetaan UC ke KF di naskah tampak bergeser satu nomor** dibandingkan Tabel 3.1, mis. UC-05 Export Laporan
   mencantumkan KF-9 (seharusnya KF-8), UC-06 Simpan dan Buka Proyek mencantumkan KF-8 dan KF-10 (seharusnya KF-7),
   dan UC-07 Kelola User Preference mencantumkan KF-11 (seharusnya KF-10). Kode dan dokumen ini mengikuti
   Tabel 3.1.
