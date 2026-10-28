# Katalog HSPK, Pilihan Material, dan Rincian Kebutuhan Bahan

Dokumen ini mencatat empat tambahan yang menindaklanjuti masukan dosen pembimbing:
1. bahan setiap pekerjaan bisa dipilih (mis. bata merah atau bata ringan);
2. bahan bisa dipilih per elemen;
3. kebutuhan bahan dirinci sampai ke jumlah bata, semen, pasir, dan seterusnya;
4. seluruh katalog HSPK tersedia untuk pekerjaan yang tidak bisa dihitung dari model IFC.

## 1. Katalog HSPK lengkap

`tools/impor_hspk.py` kini membaca **semua sheet analisa** workbook HSPK Kota Bandung 2027, tidak hanya 16 sheet
bab arsitektur/struktur. Sheet ringkasan, harga dasar, dan daftar khusus rumah sakit (RSKGM, MOT, Radiologi,
kode bab 11 ke atas) tidak diimpor.

| | Sebelum | Sesudah |
|---|---|---|
| Analisa pekerjaan | 590 | **2.802** (bab 1–10) |
| Satuan per analisa | dari uraian | dari daftar induk sheet "HSPK" |
| Judul bab | – | bab 1–10 (Persiapan, Struktur, Arsitektur, Lansekap, M&E, Plambing, Jalan, Drainase, Pipa Luar Gedung, RISHA) |

- Analisa yang sudah dipakai aplikasi tidak berubah sama sekali (diuji).
- Harga dasar (HSD) juga tidak berubah.

Cakupan per sub-bab dibandingkan daftar induk "HSPK": semua sub-bab bab 1–10 lengkap.

Ada 31 analisa yang jumlah koefisien × harga di sheet analisanya **tidak sama** dengan harga F di dokumen
(mis. 3.18.3.1 kloset duduk, beberapa pipa tembaga dan pipa DCI). Ini ketidakkonsistenan di dalam workbook
HSPK itu sendiri. Aplikasi memakai hitungan komponen, dan daftar lengkapnya dicetak oleh `tools/impor_hspk.py`.

### Tambah item dari katalog (Hasil Estimasi → "+ Item Katalog")

Pekerjaan yang tidak bisa diturunkan dari model IFC (instalasi listrik, plambing, sanitair, lisplang, pagar,
dan seterusnya) ditambahkan dengan langkah berikut:
1. Cari kode atau kata kunci, lalu saring per bab.
2. Lihat bahan dan tenaga kerja per satuan item itu.
3. Isi volume, lantai, dan catatan, lalu klik **Tambahkan ke RAB**.

Sifat item tambahan:
- Disimpan sebagai baris RAB tanpa elemen (`item_tambahan = 1`) di kategori sesuai sheet-nya, mis. "Sanitair".
- **Tidak terhapus** saat estimasi dihitung ulang, baik dari elemen tersimpan maupun dari file IFC.
- Ikut file proyek, duplikat, undo/redo, dan export.
- Bisa dihapus dari panel Rincian.

Pekerjaan katalog dibuat di database saat pertama dipakai (kode `HSPK-<kode>`), lengkap dengan komponennya,
sehingga perubahan harga dasar di Harga Satuan juga berlaku untuk item tambahan.

## 2. Pilihan material per pekerjaan (Hasil Estimasi → "Ganti Bahan")

Dialog menampilkan pekerjaan yang ada di proyek: dinding, lantai, atap, plafon, cat, pintu & jendela. Mutu beton,
fondasi, dan pekerjaan yang belum ada di proyek disimpan di **Pengaturan lanjutan** agar daftar awal tidak
membingungkan. Panduan pemakaian 5 langkah ada di `docs/Panduan-Singkat.md`.

Rule engine menghitung **volume** pekerjaan dari model: dinding dalam m², kolom dalam m³. **Bahan** yang dipilih
menentukan analisa HSPK yang dipakai, sehingga harga satuan dan kebutuhan bahannya ikut berubah. Setiap pilihan
adalah varian pekerjaan dengan kode `slot~kunci`; pilihan bawaan memakai kode slot itu sendiri.

| Kelompok | Pekerjaan | Pilihan bawaan | Pilihan lain |
|---|---|---|---|
| Mutu beton | Kolom, balok, pelat, dak, sloof, fondasi, tangga (masing-masing) | f'c 20 MPa manual (2.2.1.4.5) | f'c 21 manual; f'c 20/25/30 molen; f'c 20/25/30 ready mix |
| Fondasi | Batu kali | 1SP:4PP (2.2.2.1.6) | 1:3, 1:5, 1:6 |
| Dinding | Pasangan dinding | **Bata ringan 60×20×10 cm** (3.6.4.2) | bata ringan 7,5 / 20 cm; bata merah ½ batu 1:4 / 1:6; bata merah 1 batu; batako; conblock HB10 |
| | Plesteran | 1SP:4PP 15 mm (3.7.4) | 1:2, 1:3, 1:5, 1:6, semen instan 10 mm |
| | Keramik dinding ruang basah | 20×20 (3.10.1.4) | 10×20, porselen 20×20, homogeneous tile 30×30 / 60×60 |
| Lantai | Penutup lantai | Keramik 40×40 polished (3.9.8.6) | keramik 30×30 / 30×60 / 20×20, unpolished, homogeneous tile, granit, teraso, vinyl, parket |
| Atap | Rangka | Baja ringan C75 pelana (2.1.1.1) | C75 jurai/limasan, kayu kelas II |
| | Penutup | Genteng beton (3.1.1.4) | palentong, kodok glazur, metal, seng, serat semen, bitumen, UPVC |
| Plafon | Rangka | Hollow 40.40 (3.5.3.1) | kayu 50×100, 60×100 |
| | Penutup | Gypsum 9 mm (3.5.2.1) | GRC, kayu lapis, lambrisering, spandrel, akustik |
| Cat | Interior | Tembok baru (3.8.10.1) | cat berbasis air, kapur |
| | Eksterior | Analisa interior (sementara) | analisa eksterior HSPK 3.8.10.2, cat berbasis air, breathable mineral paint |
| Pintu & jendela | Daun pintu, kusen, kunci, jendela | Panel kayu; kayu II/III 6×15; kunci tanam biasa; kaca aluminium | plywood, kaca aluminium, PVC, engineering wood, besi; kusen aluminium; kunci silinder/antik/KM; nako, kayu |

Setiap combo box menampilkan tiga hal:
- harga satuan dari harga yang berlaku di database;
- bahan per satuan, mis. bata ringan 8,75 buah + mortar 3,43 kg per m²;
- total bahan untuk volume proyek.

Di bawah daftar tampil perkiraan perubahan biaya langsung. Menyimpan pilihan **hanya mengganti analisa pada baris
RAB yang sudah ada**:
- volume tetap, termasuk volume yang diedit manual;
- harga satuan khusus dan catatan tetap;
- rule engine tidak perlu dijalankan ulang.

Pilihan disimpan per proyek (`proyek.material`) dan ikut file proyek, duplikat, serta undo/redo.

### Material khusus satu elemen

Ada dua cara:
- tab **Per Elemen** → kolom **BAHAN ▾** di baris elemen itu: langsung tersimpan;
- panel kanan → **Bandingkan & Ganti Bahan...**: dengan tabel perbandingan.

Setelah diganti, subtotal baris, total RAB (kartu di atas), rekap per lantai, dan kebutuhan bahan ikut dihitung
ulang. Pesan menampilkan "Total RAB Rp lama → Rp baru". Perubahan bisa dibatalkan dengan Urungkan. Alur ini diuji
oleh `test_ganti_bahan_di_tabel_per_elemen_mengubah_total_dan_kebutuhan`.

Contoh: semua dinding bata ringan, tetapi "Dinding A" bata merah. Dialog menampilkan **tabel perbandingan semua
pilihan** untuk volume elemen itu, mis. dinding 18,47 m²:

| Pilihan | Biaya elemen | Kebutuhan bahan elemen ini |
|---|---|---|
| Bata ringan 60×20×10 | Rp 6.852.554 | 162 buah bata ringan · 63,3 kg mortar siap pakai |
| Bata merah ½ batu 1:4 | Rp 7.877.396 | 1.328 buah bata merah · 212 kg semen · 0,794 m³ pasir |

Sifat pilihan khusus elemen:
- Disimpan di `elemen_proyek.material` dan menimpa pilihan proyek untuk elemen itu saja.
- Pilihan proyek yang diganti kemudian tidak mengubah elemen yang punya pilihan sendiri.
- Tetap berlaku saat hitung ulang dari elemen, dan saat file IFC dibaca ulang (dicocokkan lewat GlobalId).

## 3. Rincian kebutuhan bahan: keseluruhan, per lantai, per elemen

Kebutuhan dihitung dengan rumus: **volume pekerjaan × koefisien analisa HSPK yang dipakai**. Karena itu
kebutuhan selalu mengikuti pilihan material proyek dan elemen.

| Tingkat | Di aplikasi | Di export Excel |
|---|---|---|
| **Keseluruhan** | Mode **Kebutuhan Bahan**: bahan, tenaga kerja, alat seluruh bangunan; semen dan mortar dikonversi ke zak (50 kg / 40 kg). Pilih satu bahan untuk melihat asalnya per pekerjaan dan per lantai | Sheet **Kebutuhan Bahan** (beserta daftar pilihan material proyek & elemen) |
| **Per lantai** | Mode Kebutuhan Bahan dengan filter lantai, atau mode Per Lantai | Sheet **Kebutuhan per Lantai** (tabel silang bahan × lantai) dan satu sheet per lantai |
| **Per elemen** | Mode Detail per Elemen → panel Rincian: kebutuhan bahan pekerjaan itu dan **seluruh elemen** (bata + plester + acian + cat) | Sheet **Kebutuhan per Elemen**: tiap elemen, pekerjaannya, lalu bahannya |

Laporan PDF memuat kebutuhan seluruh proyek dan daftar pilihan material. Opsi export baru: **Kebutuhan bahan
proyek & per elemen**.

## 4. Catatan data HSPK yang perlu diverifikasi estimator

| Data | Temuan | Dampak | Penanganan |
|---|---|---|---|
| Mortar siap pakai (bata ringan 3.6.4.x) | Rp 42.800/**kg**, padahal "Mortar Perekat Bata Ringan" Rp 198.210/zak 40 kg (± Rp 4.955/kg) | Bata ringan 10 cm Rp 370.956/m²; bila mortar ± Rp 4.955/kg menjadi ± Rp 228.000/m² | Catatan pada pilihan bata ringan. Ubah harga di Harga Satuan bila sudah diverifikasi |
| Cat eksterior 3.8.10.2 | Rp 1.624.000/kg (kemungkinan per pail) | ± 6× cat interior | Bawaan sementara memakai analisa interior; pilihan lain tersedia |
| Jendela nako + tralis 3.11.2.2 | Daftar induk "buah", uraian "1 m²" | Satuan tidak pasti | Tidak dijadikan pilihan jendela |
| 31 analisa | Hitungan koefisien ≠ harga F dokumen | Selisih kecil per item | Aplikasi memakai hitungan komponen |

## 5. Dampak pada model uji

Total biaya langsung dengan pilihan bawaan baru (bata ringan) dibanding bata merah:

| Model | Luas dinding | Bata ringan (bawaan) | Bata merah | Selisih dinding |
|---|---|---|---|---|
| AC20-FZK-Haus | 190,5 m² | Rp 789.833.854 | Rp 800.400.648 | −Rp 10,6 jt |
| Duplex_A | 593,8 m² | Rp 1.158.940.169 | Rp 1.191.885.375 | −Rp 32,9 jt |
| SampleStructuralModel | 325,8 m² | Rp 1.305.474.207 | Rp 1.323.550.152 | −Rp 18,1 jt |

Total bata ringan di atas juga sudah memakai analisa HSPK untuk pembersihan lahan, bouwplank, dan urugan
(lihat `docs/Koreksi-Rule-Engine.md`).

## Pengujian

`tests/test_material_katalog.py` (34 tes) menguji:
- keberadaan dan satuan setiap pilihan;
- penggantian material proyek dan elemen tanpa mengubah volume;
- hitung ulang dan baca ulang IFC;
- file proyek dan duplikat;
- dialog Pilihan Material, Material Elemen, dan Katalog;
- mode Kebutuhan Bahan;
- tambah/hapus item katalog;
- isi sheet export.
