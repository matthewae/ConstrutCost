# KNF-8 Aplikasi .exe, KF-15 Logging Aktivitas, dan KF-14 Notifikasi & Error Handling

## KNF-8: Aplikasi desktop Windows (.exe)

### Membuat CostStruct.exe

Di komputer Windows yang sudah memasang Python 3.13:

```bat
tools\build_exe.bat
```

Atau dengan perintah biasa:

```bat
python -m pip install -r requirements.txt
python tools\build_exe.py              :: mode folder (disarankan)
python tools\build_exe.py --onefile    :: satu file dist\CostStruct.exe
```

Hasil mode folder adalah `dist\CostStruct\CostStruct.exe` beserta folder `_internal`. Untuk dibagikan,
kompres seluruh folder `dist\CostStruct` (zip). Mode satu file lebih praktis dibagikan, tetapi setiap kali
dibuka lebih lambat beberapa detik karena isinya diekstrak dulu ke folder sementara.

`tools/build_exe.py` menjalankan tiga langkah:
1. Membuat ikon `assets/coststruct.ico` dari logo aplikasi (`tools/buat_ikon.py`), bila belum ada.
2. Menjalankan PyInstaller dengan `CostStruct.spec`. Spec ini memuat:
   - `schema.sql`;
   - modul `ifcopenshell` yang dipakai, termasuk aturan atribut turunan untuk skema IFC2X3 dan IFC4;
   - aplikasi jendela tanpa konsol.
   Pustaka yang tidak dipakai dikecualikan, antara lain pandas, matplotlib, validator EXPRESS, dan Qt Quick/WebEngine.
3. Menjalankan **uji mandiri** pada hasil build: `CostStruct.exe --uji-mandiri`.

### Uji mandiri (`--uji-mandiri`)

Uji mandiri menjalankan seluruh alur utama tanpa antarmuka. Ia memakai folder data sementara, jadi database
pengguna tidak tersentuh:

| Tahap | Yang diuji |
|---|---|
| Database & harga HSPK | skema SQLite + data master HSPK Kota Bandung |
| Validasi IFC (proses anak) | pembacaan IFC di proses terpisah (KNF-4); di .exe ini menguji `freeze_support` |
| Parsing & rule engine | ekstraksi elemen, QTO, RAB |
| Export Excel & PDF | openpyxl dan reportlab ikut terbundel |
| Simpan & buka file proyek | file `.coststruct` |

Contoh pemanggilan:

```bat
CostStruct.exe --uji-mandiri                         :: model IFC kecil buatan
CostStruct.exe --uji-mandiri D:\model\rumah.ifc --keluar D:\hasil-uji
```

Laporan ditulis ke `uji_mandiri.txt` dan `.json`, beserta contoh `uji_mandiri.xlsx` dan `uji_mandiri.pdf`.
Kode keluar adalah 0 bila semua tahap berhasil.

Build sudah diverifikasi di Linux (PyInstaller 6.22.3): kelima tahap berhasil dan aplikasi terbuka dari
hasil build. Pengujian ini menemukan satu masalah yang hanya muncul saat dibundel: ifcopenshell
membutuhkan `ifcopenshell.express.rules` untuk atribut turunan. Masalah ini sudah ditangani di spec.

### Lokasi data (`src/lokasi.py`)

| Dijalankan dari | Folder data |
|---|---|
| `CostStruct.exe` (Windows) | `%APPDATA%\CostStruct` (mis. `C:\Users\<nama>\AppData\Roaming\CostStruct`) |
| kode sumber (`python src/main.py`) | `data/` di folder proyek, seperti sebelumnya |
| variabel `COSTSTRUCT_DATA` | folder yang ditunjuk (mis. flashdisk atau pengujian) |

Isi folder data:
- `coststruct.db`: database SQLite (proyek, harga, preferensi, log aktivitas).
- `log\coststruct.log`: file log harian, diputar setiap tengah malam dan disimpan 30 hari.
- `cadangan\coststruct-YYYYMMDD.db`: salinan cadangan harian database. Dibuat saat aplikasi dibuka; disimpan 7
  salinan terakhir.

Data tidak ikut dibundel ke dalam .exe. Dengan begitu, memperbarui aplikasi (mengganti .exe) tidak
menghapus proyek dan harga yang sudah disesuaikan pengguna.

## KF-15: Logging aktivitas

Setiap aktivitas penting dicatat oleh `aktivitas.catat()` ke dua tempat:
- tabel `log_aktivitas` di database;
- file log harian.

Pencatatan tidak pernah menggagalkan aktivitas utamanya. Bila database log bermasalah, catatan cukup
ditulis ke file.

| Jenis | Contoh yang dicatat |
|---|---|
| Import IFC | file diterima (skema, jumlah elemen) / ditolak beserta alasannya |
| Proyek | proyek dibuat, dihapus, info diubah, diduplikasi |
| Hitung QTO | estimasi dari IFC, hitung ulang setelah dimensi/penulangan/parameter diubah |
| Edit hasil | volume, harga khusus, dan catatan per baris (nilai lama → baru) |
| Harga satuan | harga sumber daya diubah/dikembalikan, sumber daya & komponen analisa ditambah/dihapus, harga terbaru diterapkan |
| Biaya tidak langsung, Parameter aturan, Penulangan, Pengaturan | setiap perubahan |
| Export laporan | Excel/PDF: path file, isi, dan kolom |
| File proyek | simpan dan buka `.coststruct` |
| Urungkan / ulangi | setiap undo/redo |
| Kesalahan | pesan galat beserta traceback (rincian teknis) |

**Halaman Riwayat Aktivitas** ada di sidebar (Ctrl+4). Halaman ini menyediakan:
- pencarian berdasarkan teks atau nama proyek (Ctrl+F);
- filter jenis dan tingkat (Info / Peringatan / Galat);
- pengurutan kolom;
- panel rincian teknis untuk baris yang dipilih;
- tombol **Buka Folder Log**.

Catatan yang lebih tua dari 365 hari dipangkas saat aplikasi dibuka.

## KF-14: Notifikasi & error handling

1. **Pesan galat berbahasa Indonesia dengan saran solusi.** `gui/galat.py:pesan_galat` memetakan jenis
   kesalahan ke pesan beserta sarannya:

   | Kesalahan | Pesan | Saran |
   |---|---|---|
   | `PermissionError` | akses ditolak | tutup file di Excel/pembaca PDF atau pilih folder lain |
   | `FileNotFoundError` | file tidak ditemukan | pilih ulang |
   | disk penuh | ruang penyimpanan penuh | kosongkan ruang disk atau pakai drive lain |
   | database terkunci | database sedang dipakai | tutup jendela CostStruct lain |
   | database rusak | database aplikasi rusak | pulihkan dari folder `cadangan` |
   | memori habis | memori tidak cukup | tutup aplikasi lain atau pakai model yang lebih kecil |
   | galat validasi aplikasi (`...TidakValid`) | ditampilkan apa adanya | (sudah berbahasa Indonesia) |

   Pemetaan ini dipakai di import IFC, export Excel/PDF, pratinjau, hitung QTO, serta simpan/buka file
   proyek. Setiap kesalahan dicatat ke Riwayat Aktivitas. Tombol **Tampilkan Rincian** memuat traceback
   untuk pengembang.
2. **Kesalahan tak terduga tidak menutup aplikasi (KNF-4).** `sys.excepthook` diganti. Kesalahan
   ditampilkan dan dicatat, lalu aplikasi tetap berjalan.
3. **Teks bawaan Qt berbahasa Indonesia (KNF-6).** Qt tidak menyertakan terjemahan Indonesia, jadi
   `TerjemahanQt` menerjemahkan:
   - tombol OK/Cancel/Yes/No/Close menjadi OK/Batal/Ya/Tidak/Tutup;
   - "Show Details..." menjadi "Tampilkan Rincian...";
   - menu klik kanan kotak isian (Urungkan, Potong, Salin, Tempel, Pilih Semua);
   - dialog file.
4. **Notifikasi berhasil** (toast) untuk simpan proyek, edit hasil, dan perubahan harga, seperti sebelumnya.

## Pengujian

`tests/test_knf8_kf14_kf15.py` berisi 22 tes:
- lokasi data untuk .exe Windows/Linux, kode sumber, dan override;
- cadangan harian;
- isi spec PyInstaller;
- uji mandiri lima tahap;
- pencatatan ke database dan file, termasuk ketahanan saat database terkunci;
- aktivitas yang tercatat sepanjang alur import → edit → harga → export → simpan;
- pemangkasan log;
- halaman Riwayat Aktivitas;
- pemetaan pesan galat;
- dialog galat dengan traceback dan penangkap galat global;
- terjemahan tombol Qt.

Seluruh rangkaian: **223 tes lulus**.
