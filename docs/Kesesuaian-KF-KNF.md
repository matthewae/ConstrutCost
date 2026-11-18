# Kesesuaian dengan Kebutuhan Fungsional (KF) dan Non-Fungsional (KNF)

Acuan: Tabel 3.1 (KF-1 s.d. KF-19) dan Tabel 3.2 (KNF-1 s.d. KNF-9) naskah skripsi, ditambah usulan KF-20 s.d. KF-23
dan KNF-10 s.d. KNF-11 untuk fitur Model 3D dan pilihan jenis fondasi kolom (lihat paket revisi laporan).
Bukti diambil dari kode dan tes otomatis (`python -m pytest`, 628 tes lulus). Panduan pemakaian singkat: `docs/Panduan-Singkat.md`.
Koreksi basis aturan setelah audit (pelat lantai dasar, elemen bukan beton, sloof turunan, dll.)
dijelaskan di `docs/Koreksi-Rule-Engine.md`. Katalog HSPK lengkap, pilihan material per pekerjaan dan per elemen,
serta rincian kebutuhan bahan (keseluruhan, per lantai, per elemen) dijelaskan di `docs/Katalog-Material-Kebutuhan.md`.
Penampil Model 3D dengan kebutuhan biaya per elemen dijelaskan di `docs/Model-3D.md`; elemen lain yang ikut masuk
RAB (cladding, kisi, lisplang, nok, talang, ...) di `docs/Elemen-Lain.md`.

## Kebutuhan fungsional

| Kode | Fitur | Implementasi di CostStruct | Bukti uji | Status |
|---|---|---|---|---|
| KF-1 | Import File IFC | Pemeriksaan ekstensi, header ISO-10303-21, penutup file, skema IFC2x3/IFC4, dan `IfcProject`. Pembacaan file dilakukan di proses terpisah; ringkasan ditampilkan sebelum import | `test_kf1_validasi.py` | Sesuai |
| KF-2 | Parser & Klasifikasi Geometri | Elemen diklasifikasikan menjadi kolom, balok, pelat, atap, dinding, fondasi, tiang, pintu, jendela, lantai, plafon, dan ruang. Dimensi diambil dari Qto/BaseQuantities/PSet; bila tidak ada, dari geometri | `test_kf2_ekstraksi.py` | Sesuai |
| KF-3 | Rule-Based Processing | 91 aturan IF–THEN untuk 17 kelas elemen menentukan item pekerjaan (persiapan, tanah, beton, tangga, railing, bekisting, pembesian, pasangan, plesteran, dst.). Preprocessor konteks menetapkan lantai dasar, sumber luas, elemen turunan (batu kali, sloof, sumuran), elemen bukan beton, rabat dan bordes; pekerjaan yang dimodelkan (tulangan IfcReinforcingBar, urugan/lantai kerja/aanstamping, keramik dinding) menggantikan versi turunannya; jenis fondasi kolom dapat dipilih (sesuai model / footplate / cakar ayam Sedijatmo) tanpa mengubah model; semua elemen model masuk RAB (cladding, kisi, roster, lisplang, nok, talang, waterproofing, lansekap, sanitair, struktur baja/kayu; elemen tanpa analisa HSPK dengan harga 0), batang rangka atap tercakup rangka atap per m² (`docs/Elemen-Lain.md`) | `test_kf3_kf4_rules.py`, `test_penulangan.py`, `test_rule_koreksi.py`, `test_elemen_dimodelkan.py`, `test_kolom_fisik.py`, `test_fondasi_pilihan.py`, `test_elemen_lain.py` | Sesuai |
| KF-4 | Perhitungan QTO | Volume, luas, panjang, berat besi (Rumus 2.30–2.33), dan pekerjaan tanah dihitung per elemen | `test_kf3_kf4_rules.py`, `test_kf4_tanah.py` | Sesuai |
| KF-5 | Manajemen Harga Satuan | Ubah harga dan merk bahan, upah, serta alat; tambah material; harga bawaan HSPK (katalog lengkap 2.802 analisa bab 1–10); pilihan material per pekerjaan dan per elemen; mutu beton ditulis dalam K (K-250 campuran manual); kayu rangka & triplek bekisting dapat dipilih (bawaan termurah) dan ukuran paku menurut kegunaannya tanpa tembus (sambungan rangka ≤ 2 × tebal kayu; triplek ke rangka ≤ tebal triplek + kayu) | `test_kf5_harga.py`, `test_hspk.py`, `test_material_katalog.py`, `test_bekisting_bahan.py` | Sesuai |
| KF-6 | Edit Hasil Estimasi | Edit volume, harga khusus, dan catatan; tambah/hapus item dari katalog HSPK; undo/redo; pratinjau PDF | `test_kf6_edit.py`, `test_material_katalog.py` | Sesuai |
| KF-7 | Penyimpanan Proyek | File `.coststruct` berisi elemen, aturan (parameter), harga, dan hasil estimasi; bisa disimpan dan dibuka | `test_kf7_kf9_proyek.py`, `test_ketahanan.py` | Sesuai |
| KF-8 | Export Excel & PDF | Laporan RAB `.xlsx` format konsultan (REKAP, RAB, ANALISA, HARGA, ASUMSI, rekap volume & besi, BBS, detail elemen, kebutuhan bahan keseluruhan / habis pakai & berulang / per tahap / per item pekerjaan, pengadaan bahan & jadwal pengadaan; rumus saling terhubung) dan `.pdf` | `test_kf17_export.py`, `test_kf12_lantai.py`, `test_kebutuhan_lantai.py`, `test_pengadaan.py` | Sesuai |
| KF-9 | Multi-Project | Daftar proyek, info proyek, ganti nama, duplikat, ganti file IFC, hapus | `test_kf7_kf9_proyek.py` | Sesuai |
| KF-10 | User Preference | Tema (4 pilihan), direktori default, format laporan, dan isi dokumen bawaan (termasuk kebutuhan bahan proyek & per elemen), tersimpan di database | `test_kf10_preferensi.py`, `test_ui_modern.py` | Sesuai |
| KF-11 | Pajak & Markup | PPN 11% dan biaya umum & keuntungan 10% otomatis; konstanta, tidak bisa diubah pengguna | `test_kf13_biaya.py`, `test_pipeline.py` | Sesuai |
| KF-12 | Multi Lantai | Lantai dikenali dari `IfcBuildingStorey`; filter, rekap, dan rincian per lantai; satu sheet per lantai | `test_kf12_lantai.py`, `test_kebutuhan_lantai.py` | Sesuai |
| KF-13 | Ringkasan Biaya | Rekap per pekerjaan, biaya tidak langsung, PPN, total, dan terbilang | `test_kf13_biaya.py` | Sesuai |
| KF-14 | Notifikasi & Error Handling | Pesan galat berbahasa Indonesia beserta saran solusi, rincian teknis, dan toast | `test_knf8_kf14_kf15.py` | Sesuai |
| KF-15 | Logging Aktivitas | Import, estimasi, edit, ganti bahan, harga, export, file proyek, dan galat dicatat di database serta log harian; ada halaman Riwayat Aktivitas dengan filter per jenis (setiap jenis log punya label, diuji) | `test_knf8_kf14_kf15.py` | Sesuai |
| KF-16 | Navigasi Data | Hasil estimasi: saring elemen dengan checkbox jenis elemen dan radio button nama elemen (tanpa mengetik; penyaring dapat dilipat menjadi satu baris), filter kategori pekerjaan & lantai; pencarian teks di harga, proyek, dan aktivitas; pengurutan kolom | `test_kf16_urut.py` | Sesuai |
| KF-17 | Custom Output Formatting | Pilihan kolom (No, Kode, Harga, Bobot, Rumus), isi dokumen (termasuk kebutuhan bahan proyek & per elemen), dan orientasi PDF | `test_kf17_export.py`, `test_material_katalog.py` | Sesuai |
| KF-18 | Detail Volume Breakdown | Panel Rincian Perhitungan menampilkan dimensi, sumber data, rumus, dan backup volume; tersedia kolom "Uraian rumus" di export. Penampil **Model 3D**: klik elemen pada bangunan untuk melihat kebutuhan biayanya per tahap pekerjaan, termasuk pedestal, fondasi, sloof, dan pekerjaan tanah di bawahnya, dengan pilihan bahan per elemen (`docs/Model-3D.md`). Kebutuhan Bahan memiliki kolom **Setara** (mis. baja 43,38 kg ≈ 5 btg Ø10 @ 12 m, semen dalam zak, pasir dalam m³/truk, granit/keramik 40×40 dalam dus @ 6 buah, ubin teraso dalam m², paku sekrup dalam dus, cat kayu/besi dalam kaleng, kabel dalam rol 50 m, besi siku/hollow dalam batang, ready mix dalam truk mixer, lem kayu dalam kaleng, wiremesh dalam lembar, paku dalam dus) dan bahan dapat **diganti langsung** di tabel itu (proyek, atau hanya elemen yang tersaring). Bahan **habis pakai** dan bahan **dipakai berulang** (kayu, triplek, dolken bekisting; analisa HSPK "3 kali pakai") dapat ditampilkan gabungan atau terpisah, dan export memuat keduanya (sheet Kebutuhan Bahan + sheet Bahan Habis Pakai & Berulang). Tab **Pengadaan**: jumlah beli dalam kemasan utuh dan biaya beli per tahap pekerjaan & lantai (urutan pelaksanaan, sisa stok berpindah) atau seluruh proyek; panel RAB menampilkan bahan, tenaga, dan alat lengkap per item; export: sheet Kebutuhan per Tahap, Kebutuhan per Pekerjaan, Pengadaan Bahan, Jadwal Pengadaan | `test_kf3_kf4_rules.py`, `test_kebutuhan_lantai.py`, `test_penampil3d.py`, `test_bekisting_bahan.py`, `test_bahan_berulang.py`, `test_pengadaan.py` | Sesuai |
| KF-19 | Recalculate QTO | Ubah dimensi elemen (mis. pelat 30×30 → 50×50) lalu QTO dan RAB dihitung ulang | `test_kf19_dimensi.py` | Sesuai |
| KF-20 | Visualisasi Model 3D (usulan) | Mode Model 3D di halaman estimasi (Ctrl+3): putar/geser/zoom, pandangan cepat, saringan lantai, tampilan lengkap / tembus pandang / struktur saja, warna jenis / biaya, cari elemen lewat combo Jenis → Nama elemen, Kembali ke RAB (Esc) | `test_penampil3d.py` | Sesuai |
| KF-21 | Biaya per elemen & ganti bahan dari 3D (usulan) | Klik elemen → biaya elemen + pedestal, fondasi, sloof, pekerjaan tanah (per tahap / per bagian); combo bahan per elemen; koreksi jenis elemen lain (juga lewat menu Proyek › Koreksi Jenis Elemen Lain, `docs/Elemen-Lain.md`); tersimpan otomatis, urungkan/ulangi bersama tabel, sinkron dua arah dengan tabel RAB dan Export; elemen "termasuk pekerjaan lain" menampilkan pekerjaan pencakupnya | `test_penampil3d.py`, `test_elemen_lain.py` | Sesuai |
| KF-22 | Besi beton 3D (usulan) | Mode "Besi beton (pembesian)": IfcReinforcingBar per elemen induk di dalam beton tembus pandang; klik besi → pembesian elemen induk; model tanpa besi → pesan | `test_penampil3d.py` | Sesuai |
| KF-23 | Pilihan jenis fondasi kolom & perbandingan (usulan) | Parameter Aturan: sesuai model / footplate / cakar ayam Sedijatmo tanpa mengubah model; sheet PERBANDINGAN_FONDASI di Export Excel (`docs/Fondasi-Pilihan.md`) | `test_fondasi_pilihan.py` | Sesuai |

## Kebutuhan non-fungsional

| Kode | Kebutuhan | Implementasi / hasil ukur | Bukti uji | Status |
|---|---|---|---|---|
| KNF-1 | Parsing ≤ 30 detik (file rumah tinggal hingga 50 MB) | Geometri elemen tanpa Qto dihitung paralel di semua inti CPU; hasilnya identik dengan perhitungan satu per satu. Hasil ukur ada di tabel di bawah | `test_knf_kinerja_integritas.py`, `tools/ukur_kinerja.py` | Sesuai |
| KNF-2 | Rule engine + RAB < 15 detik setelah parsing | 0,02–0,07 detik untuk 193–2.132 item RAB | `test_knf_kinerja_integritas.py` | Sesuai |
| KNF-3 | Konsistensi hasil | Input dan database yang sama menghasilkan baris RAB, total, dan isi Excel yang identik pada setiap percobaan | `test_knf_kinerja_integritas.py` | Sesuai |
| KNF-4 | Tidak crash saat ada galat | File rusak atau bukan .ifc dibaca di proses terpisah; `sys.excepthook` menampilkan peringatan tanpa menutup aplikasi | `test_kf1_validasi.py`, `test_knf8_kf14_kf15.py` | Sesuai |
| KNF-5 | Indikator proses | Dialog progres "Memproses file IFC" dengan i/n elemen (termasuk tahap geometri paralel); splash dengan progress bar dan tahap pemuatan | `test_ui_modern.py` (splash) | Sesuai |
| KNF-6 | Bahasa Indonesia baku | Seluruh teks UI, pesan galat, dan tombol bawaan Qt (OK/Batal/Ya/Tidak, menu klik kanan) berbahasa Indonesia | `test_knf8_kf14_kf15.py` | Sesuai (lihat catatan 1) |
| KNF-7 | Windows 11 64-bit, luring | Tidak ada akses jaringan di kode; data disimpan di `%APPDATA%\CostStruct`; gaya Qt Fusion, ikon taskbar, dan title bar gelap Windows. Seluruh tes lulus di Windows (CI `windows-latest`) | `.github/workflows/windows.yml`, `test_knf8_kf14_kf15.py` | Sesuai di Windows Server 2025 (CI); uji akhir di Windows 11 penelitian (catatan 2) |
| KNF-8 | Paket .exe mandiri | `CostStruct.spec` + `tools/build_exe.py`. Uji mandiri `CostStruct.exe` 7 tahap: database, validasi IFC di proses anak, parsing & rule engine, export Excel/PDF, file proyek, jendela utama Qt (gaya Fusion), dan Model 3D (model benar-benar tergambar). Installer `CostStruct-Setup-<versi>.exe` (Inno Setup 6, `installer/`, `tools/build_installer.py`): tanpa hak administrator, shortcut, asosiasi `.coststruct`; di CI dipasang diam-diam, uji mandiri dari folder instalasi, lalu dicopot (`docs/Build-Windows.md`) | `.github/workflows/windows.yml`, `test_knf8_kf14_kf15.py` | Sesuai: `CostStruct.exe` dibuild & lulus uji mandiri di Windows (CI) |
| KNF-9 | Integritas database SQLite | Setiap proses tulis dalam satu transaksi; `PRAGMA synchronous=FULL`; `quick_check` saat aplikasi dibuka; cadangan harian. Diuji dengan `kill -9` saat menulis, 5 kali: database tetap `ok` dan hasil estimasi lengkap | `test_knf_kinerja_integritas.py`, `test_knf8_kf14_kf15.py` | Sesuai |
| KNF-10 | Model 3D ≤ 15 detik, besi beton ≤ 15 detik (usulan) | Geometri dibaca paralel; dibuka ulang tanpa membaca IFC lagi; jendela progres. Hasil ukur di tabel di bawah | `uji_mandiri.py` tahap 7, pengukuran manual | Sesuai untuk rumah tinggal tipikal; file sintetis 50 MB dengan perabot bermesh padat **belum** (± 110 s, catatan 4) |
| KNF-11 | Grafis terintegrasi & ketahanan penampil 3D (usulan) | Direct3D 11 di Windows; bila API grafis 3D tidak tersedia, pesan tampil dan panel biaya tetap dapat dipakai lewat combo pencarian elemen; file IFC hilang → pesan tanpa crash | `test_penampil3d.py` (`test_grafis_3d_tidak_tersedia_...`, `test_file_ifc_hilang_...`), uji mandiri tahap 7 di CI Windows | Sesuai |

### Hasil ukur KNF-1 / KNF-2

Diukur dengan `python tools/ukur_kinerja.py <file.ifc>` (4 inti CPU, Linux):

| File | Ukuran | Elemen | Item RAB | Parsing (KNF-1) | Rule + RAB (KNF-2) |
|---|---|---|---|---|---|
| AC20-FZK-Haus.ifc | 2,5 MB | 47 | 193 | 2,2 s | 0,02 s |
| Duplex_A_20110907.ifc | 2,4 MB | 171 | 453 | 2,1 s | 0,02 s |
| SampleStructuralModel.ifc | 6,0 MB | 349 | 324 | 4,4 s | 0,04 s |
| rumah_50mb.ifc (sintetis, `tools/buat_ifc_uji.py`) | 53,4 MB | 447 | 2.132 | 15,0 s | 0,07 s |

Hasil ukur yang sama di **Windows** (CI GitHub Actions, Windows Server 2025, 4 inti CPU, Python 3.13):

| File | Ukuran | Parsing (KNF-1) | Rule + RAB (KNF-2) |
|---|---|---|---|
| AC20-FZK-Haus.ifc | 2,6 MB | 1,0 s | 0,05 s |
| Duplex_A_20110907.ifc | 2,4 MB | 1,6 s | 0,06 s |
| SampleStructuralModel.ifc | 6,1 MB | 6,0 s | 0,08 s |

Di runner yang sama, `CostStruct.exe` dibuild (folder ±272 MB) dan uji mandirinya lulus ketujuh tahap, termasuk Model 3D.

Sebelum geometri dihitung paralel, parsing SampleStructuralModel memakan 12,4 s. Sekarang 4,4 s, dengan hasil
dimensi yang identik.

Untuk BAB IV, jalankan ulang alat ukur di laptop Windows 11 yang dipakai penelitian. Alat ini menyimpan
hasilnya ke `hasil_kinerja.csv`.

### Hasil ukur KNF-10 (Model 3D)

Waktu `model3d.muat_model3d` dan `model3d.muat_besi` (4 inti CPU, Linux, Python 3.13):

| File | Ukuran | Elemen 3D | Segitiga | Model 3D | Besi beton | Memuat besi |
|---|---|---|---|---|---|---|
| Tipe 120 1 lantai | 10,9 MB | 360 | 11.456 | 2,05 s | 3.099 batang | 3,71 s |
| Tipe 120 2 lantai courtyard | 16,8 MB | 569 | 31.792 | 3,46 s | 4.803 batang | 5,35 s |
| Tipe 120 3 lantai modern tropis | 19,0 MB | 571 | 19.588 | 3,01 s | 5.740 batang | 6,46 s |
| rumah_50mb.ifc (sintetis) | 53,4 MB | 475 | 1.203.921 | 109,93 s | — | — |

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
4. **KNF-10 pada model bermesh padat.** File sintetis 50 MB berisi 100 perabot dengan 1,2 juta segitiga (±61 kali model 3 lantai). Parsing dan RAB-nya tetap memenuhi KNF-1/KNF-2, tetapi Model 3D-nya ±110 s. Penyederhanaan geometri elemen non-RAB (mis. perabot) dicatat sebagai pengembangan lanjutan.
