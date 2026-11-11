# Penampil Model 3D dan Kebutuhan Biaya per Elemen

Tombol **Model 3D** (kanan atas halaman estimasi, atau Ctrl+3) mengganti tampilan halaman estimasi ke mode 3D,
di jendela yang sama. Klik sebuah elemen, misalnya Kolom K1 A1, dan panel kanan menampilkan berapa biaya untuk
membangunnya. Isinya dimulai dari pekerjaan tanah dan fondasi di bawahnya, lalu kolom itu sendiri, beserta pilihan
bahannya.

## Kembali, urungkan, dan tersimpan otomatis

Bagian atas mode 3D berisi:

| Kontrol | Fungsi |
|---|---|
| **← Kembali ke RAB** (atau Esc) | Kembali ke tabel RAB. Esc pertama membatalkan pilihan elemen, Esc kedua kembali |
| **✓ Tersimpan otomatis** | Setiap perubahan (bahan, volume, harga) langsung tersimpan ke database proyek. Tidak ada tombol simpan terpisah, dan tidak ada perubahan yang hilang saat kembali. Ctrl+S tetap menyimpan salinan file .coststruct |
| **↶ Urungkan / ↷ Ulangi** (Ctrl+Z / Ctrl+Y) | Riwayatnya sama dengan tabel RAB. Perubahan yang dibuat di mode 3D bisa diurungkan dari tabel, dan sebaliknya. Tooltip menyebut langkah yang akan dibatalkan |
| **Export RAB** (Ctrl+E) | Export Excel / PDF langsung dari mode 3D |

**Sinkron dua arah.** Mode 3D dan tabel RAB membaca data yang sama (`hasil_estimasi`), jadi:
- bahan yang diganti di mode 3D langsung tampil di tabel RAB, rekap, kebutuhan bahan, dan **Export RAB**;
- perubahan di luar mode 3D tampil saat masuk mode 3D lagi, misalnya edit volume, harga khusus, ganti bahan proyek,
  parameter aturan / jenis fondasi, atau hitung ulang.

Mode 3D dibangun sekali per halaman proyek. Masuk lagi berikutnya langsung tampil dengan data terbaru. Bila file
IFC proyek diganti, bentuk 3D dibaca ulang.

Kode program:
- `src/model3d.py`: geometri dari IFC;
- `src/biaya_elemen.py`: biaya elemen dan elemen di bawahnya;
- `src/gui/penampil3d.py` + `penampil3d.qml`: jendela 3D (Qt Quick 3D) dan panel biaya.

## Alur pemakaian

1. **Buka.** Klik **Model 3D**. File IFC proyek dibaca sekali di latar, dengan jendela progres (±3–7 detik untuk
   rumah tipe 120). Membuka lagi berikutnya langsung tampil karena bentuk 3D disimpan selama aplikasi terbuka.
   **Kembali ke RAB** untuk kembali ke tabel.
2. **Lihat.**

   | Aksi | Kontrol |
   |---|---|
   | Putar | seret kiri |
   | Geser | seret kanan / tengah |
   | Zoom | roda mouse |
   | Pandangan cepat | Iso, Atas, Depan, Samping, Pas (pojok kanan atas tampilan) |

   Label kecil di dekat kursor menyebut nama elemen, jenis, lantai, dan biayanya.
3. **Klik elemen.** Elemen terpilih berwarna **kuning**. Bagian yang ikut dihitung (pedestal, fondasi, lantai
   kerja, sloof) berwarna **hijau**. Panel kanan menampilkan:
   - jenis (mis. *Kolom struktur utama*), lantai, nama, dan dimensi;
   - **kebutuhan biaya** total beserta pembagiannya, mis. *Elemen ini Rp 4,28 jt · Pedestal Rp 1,82 jt ·
     Fondasi Rp 1,70 jt · Pekerjaan tanah Rp 117.347*;
   - **pilihan bahan elemen ini** (combo box). Setiap pilihan menampilkan biayanya untuk elemen itu dan selisihnya
     terhadap pilihan sekarang;
   - daftar pekerjaan dalam dua tampilan: **Urutan pekerjaan** (per tahap: tanah → fondasi → beton → dinding →
     plesteran → cat) dan **Per bagian** (elemen ini, pedestal, fondasi, pekerjaan tanah). Setiap baris berisi
     volume × harga satuan = jumlah; rumus volume muncul di tooltip.
4. **Tindak lanjut.**
   - Ganti bahan di combo box: RAB langsung dihitung ulang, pesan menunjukkan total RAB lama → baru.
   - **Ctrl+Z** mengurungkan perubahan itu; riwayatnya sama dengan riwayat tabel RAB.
   - **Lihat di Tabel RAB** membuka tab Per Elemen dengan pencarian nama elemen itu.
   - **Ganti Bahan…** membuka dialog bahan lengkap, dengan kebutuhan bata, semen, pasir, dan lain-lain.
   - **Fokus** (atau dobel klik) mendekatkan kamera ke elemen.
   - **Esc** membatalkan pilihan.

## Elemen yang ikut dihitung

Biaya diambil dari hasil estimasi yang tersimpan, termasuk volume yang diedit, harga khusus, dan pilihan bahan.
Karena itu angkanya sama dengan tabel RAB dan export Excel.

| Elemen diklik | Yang ikut dihitung (warna hijau) | Dasar |
|---|---|---|
| Kolom | segmen lain kolom fisik yang sama (pedestal / potongan kolom), fondasi di bawah kolom (footplate, sumuran, poer), lalu lantai kerja / urugan pasir yang dimodelkan di bawah fondasi | kolom fisik (`kolom.py`) dan relasi fondasi–kolom (`relasi.py`), dibaca saat import |
| Fondasi | fondasi lain di titik kolom yang sama (mis. sumuran + poer), lalu pekerjaan tanah di bawahnya | relasi fondasi–kolom |
| Dinding | sloof di bawah dinding, fondasi menerus (batu kali) di bawah dinding atau di bawah sloof, lalu pekerjaan tanahnya | kotak pembatas 3D: denah bertumpuk ≥ 50 %, puncak elemen bawah antara kaki dinding dan 60 cm di bawahnya |
| Lainnya (balok, pelat, atap, pintu, ...) | elemen itu saja | — |

Fondasi dan pekerjaan tanah yang **diturunkan** aplikasi, misalnya footplate turunan dari pilihan jenis fondasi,
sumuran turunan, atau galian, sudah menjadi baris RAB elemen itu sendiri. Baris itu ikut tampil tanpa elemen
tambahan. Kotak centang *Termasuk pedestal, fondasi & pekerjaan tanah di bawahnya* dapat dimatikan untuk melihat
biaya elemen itu saja.

Semua elemen model masuk RAB, termasuk cladding, kisi, lisplang, nok, talang, waterproofing, lansekap, dan
sanitair (`docs/Elemen-Lain.md`). Elemen yang **sudah termasuk pekerjaan lain** tampil abu-abu muda: batang rangka
atap, penutup atap, dan bagian tangga. Saat diklik, panel menampilkan pekerjaan yang mencakupnya. Contoh: kasau /
kuda-kuda → baris Rangka Atap per m² pada bidang atap di atasnya, dan atap itu diberi warna hijau. Objek kolom ganda
menyebut kolom tempat biayanya sudah dihitung, jadi tidak dihitung dua kali.

## Pilihan tampilan

| Pilihan | Fungsi |
|---|---|
| **Cari elemen** (Ctrl+F) | ketik mis. "K1", "dinding", "fondasi"; pilih dari daftar untuk memilih dan memfokuskan elemen |
| **Lantai: s.d. …** | sembunyikan lantai di atasnya, mis. *s.d. 00 Fondasi* menampilkan denah fondasi dan sloof saja |
| **Tampilan lengkap / Arsitektur tembus pandang / Struktur saja / Besi beton** | Tembus pandang: dinding, atap, pintu, dan jendela dibuat transparan, dan klik menembus ke kolom/balok di baliknya. Struktur saja: hanya kolom, balok, pelat, fondasi, tangga, dan pekerjaan tanah. Besi beton: beton dibuat tembus pandang sehingga besi beton yang dimodelkan (IfcReinforcingBar) di dalamnya terlihat; lihat bagian di bawah |
| **Warna jenis / Warna biaya** | Warna biaya: biru = elemen murah, merah = elemen mahal (peringkat persentil); legenda menampilkan biaya terendah, median, dan tertinggi |
| **Elemen tak dihitung** | tampilkan atau sembunyikan elemen yang tidak masuk RAB |

## Mode besi beton (pembesian)

Pilih **Besi beton (pembesian)** di combo tampilan:
- kolom, balok, pelat, fondasi, dan tangga menjadi tembus pandang, elemen lain disembunyikan, dan besi beton yang
  dimodelkan terlihat di dalamnya (oranye);
- besi dikelompokkan per elemen induk (relasi agregasi IFC atau properti `HostGlobalId`). Klik besi sebuah kolom →
  besi kolom itu kuning, panel menampilkan rincian biaya kolom (baris pembesian per diameter), dan besi pedestal /
  footplate di bawahnya hijau;
- sorot kursor pada besi menampilkan jumlah batang dan biaya pembesian elemen itu;
- saringan **s.d. lantai** juga berlaku, mis. *s.d. 01 Lantai 1* untuk melihat besi kolom, sloof, dan fondasi
  lantai 1.

Besi dibaca sekali saat mode ini pertama dipilih (±6 detik untuk 5.740 batang model 3 lantai, dengan jendela
progres). Penampang besi digambar sebagai tabung segi-6 langsung dari sumbu segmen dan diameter nominalnya, sekitar
300 ribu segitiga untuk 5.740 batang (bentuk asli 711 ribu segitiga, ±20 detik). Besi berbentuk lain (mis.
IfcSweptDiskSolid lengkung dari Revit) dibaca dengan pembaca geometri IfcOpenShell.

Model yang tidak memuat besi beton menampilkan pesan bahwa pembesiannya dihitung dari Tipe Penulangan, lalu
tampilan kembali ke pilihan sebelumnya.

## Catatan teknis

- **Geometri.** Geometri dibaca dengan `ifcopenshell.geom.iterator` dalam koordinat dunia, paralel di semua inti
  CPU. Setiap elemen menjadi segitiga dengan normal per bidang, lalu diubah ke sumbu Y-atas Qt Quick 3D:
  (x, y, z)<sub>IFC</sub> → (x, z, −y). Tulangan, lubang, dan ruang tidak ditampilkan.
- **Kinerja.** Rumah 1 lantai: 360 elemen / 11.456 segitiga, 6,4 detik. Rumah 3 lantai: 571 elemen /
  19.588 segitiga, 2,8 detik.
- **Grafis.** Penampil memakai Direct3D 11 di Windows; OpenGL / Vulkan / Metal di sistem lain. Bila driver grafis
  tidak menyediakannya, jendela menampilkan pesan dan panel biaya tetap dapat dipakai lewat kotak pencarian.
- **File IFC.** Penampil membutuhkan file IFC asli proyek. Bila file dipindahkan, aplikasi memberi pesan.
- **Penerjemah tombol Qt.** Penerjemah teks bawaan Qt (`TerjemahanQt` di `gui/galat.py`) ditulis di Python.
  - Masalahnya: QML dimuat secara sinkron. Selama itu thread utama memegang GIL sambil menunggu thread pemuat QML,
    dan thread pemuat QML juga memanggil penerjemah, yang butuh GIL. Keduanya saling menunggu dan aplikasi macet.
  - Solusinya: penerjemah dilepas sementara selama `setSource`, lalu dipasang kembali (`tanpa_terjemahan_python`).
  - Tes 3D dan uji mandiri memasang penerjemah ini seperti aplikasi sungguhan, sehingga masalah ini akan
    tertangkap bila muncul lagi.
- **Build .exe.**
  - `CostStruct.spec` membawa modul QML QtQml, QtQuick, dan QtQuick3D saja, beserta pustaka Qt yang dibutuhkannya.
  - Modul QML lain yang ikut terbawa oleh hook PyInstaller dibuang, mis. WebEngine (±200 MB), Controls, Charts,
    dan Multimedia.
  - Uji mandiri `--uji-mandiri` punya tahap ke-7, **Model 3D (Qt Quick 3D)**. Tahap ini membuka penampil, memilih
    elemen, dan memeriksa bahwa model benar-benar tergambar.

## Pengujian

`tests/test_penampil3d.py` (17 tes) memakai model IFC buatan. Isinya: kolom = pedestal + kolom di atas footplate
dan lantai kerja, dinding di atas sloof, dan perabot. Yang diuji:

- **Geometri:** lantai, koordinat dunia vs koordinat tampilan, dan penghapusan segitiga tanpa luas.
- **Elemen yang ikut dihitung:**
  - kolom → pedestal, footplate, lantai kerja (urut);
  - fondasi → lantai kerja;
  - dinding → sloof.
- **Konsistensi biaya:** total = jumlah biaya elemen-elemennya = hasil estimasi.
- **Panel:** urutan pekerjaan vs per bagian, combo bahan, kondisi kosong, dan elemen tak dihitung.
- **Jendela 3D:**
  - warna pilih dan terkait;
  - saringan lantai, struktur saja, dan tembus pandang (klik menembus);
  - pencarian dan ganti bahan.
- **Mode 3D di halaman estimasi:**
  - Kembali ke RAB, Esc dua tahap, tombol Urungkan / Ulangi, dan Lihat di Tabel RAB;
  - **sinkron dua arah**: ganti bahan di 3D → tabel RAB dan file Excel hasil Export memuat bahan baru; edit volume di
    tabel → panel 3D memuat volume baru.
- **File hilang:** pesan file IFC tidak ditemukan.
- **Besi beton:** tabung segi-6, besi dikelompokkan per elemen induk, mode besi (beton tembus pandang, klik besi →
  pembesian elemen induk), dan model tanpa besi (pesan, tampilan kembali).
