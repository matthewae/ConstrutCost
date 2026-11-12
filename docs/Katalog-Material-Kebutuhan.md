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
| Mutu beton | Kolom, balok, pelat, dak, sloof, fondasi, tangga (masing-masing) | **K-250 campuran manual** (f'c 20 MPa, 2.2.1.4.5) | K-250 (f'c 21 MPa) manual; K-250 / K-300 / K-350 molen; K-250 / K-300 / K-350 ready mix |
| Bekisting | Kayu rangka & triplek untuk **semua** pekerjaan bekisting | **Kaso 5/7 kayu kelas II** + **tripleks 9 mm** (termurah di HSPK) | kaso 5/7 kelas III, balok sengon, balok borneo, balok 6/12 kelas II (analisa HSPK) / kelas I; plywood 9 mm, multiplek 9 / 12 / 18 mm, plywood 12 mm (analisa HSPK) |
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

### Mutu beton dalam K

Nama pekerjaan dan pilihan mutu ditulis dalam **K** (kuat tekan kubus, kg/cm²) yang lazim di lapangan, mis.
*Beton Kolom K-250* dan *K-250, campuran manual*. Analisa HSPK 2027 memakai f'c (silinder, MPa); konversinya
K ≈ f'c ÷ 0,083 dibulatkan ke kelipatan 25 (`database/material.mutu_k`): f'c 7,5 → K-100, f'c 15 → K-175,
f'c 20 → K-250, f'c 25 → K-300, f'c 30 → K-350. f'c 21 MPa juga K-250, jadi labelnya tetap menyebut f'c 21 MPa.
Uraian analisa di sheet ANALISA tetap memakai teks asli HSPK (f'c) agar dapat ditelusuri.

### Bahan bekisting: kayu, triplek, dan paku (`bahan_bekisting.py`)

Analisa bekisting HSPK (2.2.1.3.3 kolom s.d. 2.2.1.3.7 tangga) memakai kayu balok 6/12 kelas II
(Rp 5,56 jt/m³), plywood 12 mm (Rp 265.468/lembar), dan paku 12 cm (pelat: paku 4 inch). Untuk rumah tinggal
dipakai bahan yang lebih murah:

- **Kayu rangka** dan **triplek** dipilih per proyek di kelompok **Bekisting** dialog Ganti Bahan. Bawaannya adalah
  yang termurah di HSPK: kaso 5/7 kayu kelas II (Rp 2.497.500/m³) dan tripleks 9 mm (Rp 150.000/lembar).
  Pilihan berlaku untuk semua pekerjaan bekisting (kolom, balok, pelat, dak, sloof, tangga, cakar ayam, planter).
- **Koefisien HSPK tetap** (m³ kayu, lembar triplek, kg paku per m²). Hanya jenis dan harga bahannya yang diganti.
  Upah dan bahan lain sama.
- **Ukuran paku menurut kegunaannya**, dan paku tidak boleh lebih panjang dari tebal bahan yang disambung
  (tembus). Dari ukuran paku per kg di HSPK (3 cm, 5 cm/2 inch, 7 cm, 10 cm/4 inch, 5 inch) dipilih yang termurah di
  antara batasnya; bila tidak ada, yang terpanjang tanpa tembus.
  - **Sambungan rangka kayu ke kayu** (tiang, gelagar, klem): koefisien paku HSPK 0,4 kg/m² dipakai untuk ini.
    Panjang 1,5 × s.d. 2 × tebal kayu: kaso 5/7 → 7,5–10 cm → **paku 10 cm (4 inch)**; balok 6/12 → 9–12 cm →
    paku 10 cm (12 cm juga tidak tembus, tetapi paku 12 cm di HSPK berharga per buah).
  - **Triplek ke rangka**: 0,03 kg/m², sama dengan "Paku Tripleks" pada analisa HSPK pemasangan kayu lapis
    (3.5.2.3.x). Panjang 3 × tebal triplek s.d. tebal triplek + tebal kayu: plywood 12 mm + balok 6/12 (tebal
    7,2 cm) → 3,6–7,2 cm → **paku 5 cm** (paku 12 cm akan tembus ± 4,8 cm); tripleks 9 mm + kaso 5/7 (5,9 cm) →
    paku 5 cm.
- Bekisting fondasi dan sloof HSPK (2.2.1.3.1/2) memakai papan kayu kelas III sebagai muka bekisting tanpa triplek,
  sehingga papan dan pakunya tidak diganti.
- Varian kayu/triplek selain bawaan disimpan sebagai pekerjaan `BSK.KOLOM~kayu+triplek` (dibuat saat pertama
  dipilih, dari pekerjaan bawaannya) dan tetap dipakai saat estimasi dihitung ulang dari IFC.
- Catatan data HSPK: analisa bekisting kolom/balok/sloof memakai "Paku 12 cm" 0,4 kg/m² dengan harga Rp 1.200,
  padahal daftar harga dasar HSPK mencatat Paku 12 cm Rp 1.200 **per buah**, bukan per kg.

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
| **Keseluruhan** | Mode **Kebutuhan Bahan**: bahan, tenaga kerja, alat seluruh bangunan; kolom **SETARA** menerjemahkan kebutuhan ke satuan beli (lihat di bawah). Pilih satu bahan untuk melihat asalnya per pekerjaan dan per lantai | Sheet **Kebutuhan Bahan** (beserta daftar pilihan material proyek & elemen) |
| **Per lantai** | Mode Kebutuhan Bahan dengan filter lantai, atau mode Per Lantai | Sheet **Kebutuhan per Lantai** (tabel silang bahan × lantai) dan satu sheet per lantai |
| **Per elemen** | Tab **Per Elemen**, dikelompokkan per lantai lalu per jenis elemen. Judul kelompok (mis. Lantai 1 · Dinding) menampilkan jumlah elemen, volume, dan kebutuhan bahan kelompok. Baris elemen menampilkan kebutuhan bahan **seluruh elemen** (bata + plester + acian + cat) | Sheet **Kebutuhan per Elemen** dengan susunan sama: lantai → jenis → elemen → pekerjaan → bahan |

### Kolom SETARA (`setara.py`)

| Bahan (satuan analisa) | Setara | Dasar konversi |
|---|---|---|
| Baja tulangan (kg) | ≈ 4 btg D16 @ 12 m; ≈ 5 btg Ø10 + 3 btg Ø8 @ 12 m | dibagi per diameter sebanding berat penulangan baris yang sama (BBS); berat/m = π/4·d²·7.850; tanpa data diameter: asumsi Ø10 / D13 |
| Semen, mortar instan (kg) | ≈ n zak @ 50 kg / 40 kg | berat per zak |
| Pasir, batu split, kerikil, sirtu (kg) | ≈ m³ (dan truk @ 7 m³ bila ≥ 3 m³) | berat isi lepas: pasir 1.400, split 1.350, sirtu 1.600 kg/m³ |
| Kayu kaso / balok / papan (m³) | ≈ n btg 5/7 @ 4 m | penampang dari nama, panjang 4 m |
| Paku (kg) | ≈ n btg (± k btg/kg) | perkiraan jumlah per kg menurut panjang |
| Kawat beton (kg) | beli n rol @ 25 kg (terpakai x%) | berat per rol |
| Minyak bekisting (liter) | beli n jeriken @ 20 liter | isi jeriken |
| Cat (kg) | ≈ n pail @ 25 kg + n galon @ 5 kg | kemasan |
| Keramik (m² atau buah) | ≈ n dus @ 0,96 m² / @ 6 buah | isi per dus menurut ukuran |
| Bata ringan (buah) | ≈ m³ | 60 × 20 × tebal cm |
| Pipa, rangka aluminium, hollow, besi siku, UNP/CNP (m') | ≈ n btg @ 6 m (pipa PVC @ 4 m) | panjang batang di pasaran |
| Pasir, kerikil, batu belah, tanah (m³) | ≈ n truk @ 7 m³ (< 3 m³: pick-up @ 1,5 m³) | isi kendaraan |
| Lem kayu (kg) | ≈ n kaleng @ 2,5 kg | kemasan |
| Wiremesh M6 / M8 (kg) | ≈ n lembar @ 2,1 × 5,4 m (± 33,6 / 59,7 kg) | berat lembar dari diameter, jarak 150 mm dua arah |
| Paku (kg) ≥ 15 kg | ≈ n dus @ 30 kg + jumlah batang | kebutuhan kecil: eceran per kg |
| Self drilling screw, paku rivet (buah) | ≈ n dus @ 1.000 buah | isi dus |
| Baja ringan, reng (batang) | ≈ n btg @ 6 m; dolken @ 4 m (dari nama) | panjang batang |
| Papan kayu tanpa ukuran (m³) | ≈ n lbr papan 2/20 @ 4 m (asumsi 2/20) | |
| Besi strip a × b mm (kg) | ≈ n btg @ 6 m | berat = a·b·7.850 per m |
| Membran bakar (m') | ≈ n rol @ 1 × 10 m | ukuran rol |
| Minyak bekisting dalam m³ (satuan HSPK analisa sloof) | ⚠ kemungkinan liter: ≈ n jeriken | satuan HSPK tidak lazim, ditandai |
| Air (liter) | ≈ m³ | 1.000 liter = 1 m³ |
| Tenaga kerja (OH) | orang-hari | |

Ukuran kemasan dan berat isi adalah angka yang lazim di pasaran dan dapat berbeda per merek / pemasok. Bahan
yang ukuran kemasannya tidak seragam (listplank GRC, talang seng, dynabolt, sealant, cairan primer) dibiarkan
kosong.

### Ganti bahan langsung di Kebutuhan Bahan

Nama bahan yang dapat diganti tampil sebagai combo (▾), mis. *Kaso 5/7 kayu kelas II ▾*, *Tripleks 9 mm ▾*,
*Bata ringan ▾*, keramik, genteng, gypsum, cat. Pilihan di combo memuat harga per satuan.

- **Tanpa saringan**: berlaku untuk seluruh proyek (sama dengan dialog Ganti Bahan).
- **Dengan saringan** (mis. *Kolom › Kolom K1 30x30 Lt.1 A1*, atau semua kolom yang dicentang): hanya elemen yang
  tersaring yang berubah. Kayu & triplek bekisting juga dapat dipilih per elemen (varian `BSK.KOLOM~kayu+triplek`),
  dan tetap berlaku saat estimasi dihitung ulang dari IFC.
- Bahan yang berubah lewat pilihan pekerjaannya (semen, pasir, split, air: mutu beton / campuran) tidak diberi
  combo; ukuran paku bekisting mengikuti kayu & triplek.
- Setiap penggantian masuk riwayat Urungkan/Ulangi dan menampilkan total RAB sebelum → sesudah.

Laporan PDF memuat kebutuhan seluruh proyek dan daftar pilihan material. Opsi export baru: **Kebutuhan bahan
proyek & per elemen**.

## 4. Catatan data HSPK yang perlu diverifikasi estimator

| Data | Temuan | Dampak | Penanganan |
|---|---|---|---|
| Paku 12 cm (bekisting 2.2.1.3.3/4) | Dipakai 0,4 **kg**/m² dengan harga Rp 1.200, padahal daftar harga dasar mencatat Rp 1.200 **per buah** | Harga paku bekisting terlalu rendah | Paku diganti sesuai tebal bekisting (paku 5 cm/2 inch Rp 21.900/kg) |
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

Bahan bekisting bawaan (kaso 5/7 + tripleks 9 mm; paku 10 cm untuk sambungan rangka dan paku 5 cm untuk triplek)
dibanding analisa HSPK asli (balok 6/12 kelas II + plywood 12 mm + paku 12 cm @ Rp 1.200), biaya langsung tiga model
Tipe 120:

| Model | Bekisting | Sebelum | Sesudah | Selisih |
|---|---|---|---|---|
| Tipe 120 1 lantai kupu-kupu | 285,6 m² | Rp 867.290.896 | Rp 861.973.674 | −Rp 5,32 jt |
| Tipe 120 2 lantai courtyard | 414,0 m² | Rp 1.140.198.455 | Rp 1.130.816.059 | −Rp 9,38 jt |
| Tipe 120 3 lantai modern tropis | 528,3 m² | Rp 1.345.347.801 | Rp 1.333.162.336 | −Rp 12,19 jt |

Per m² bekisting kolom (sebelum BUK 10%): kayu −Rp 14.220, triplek −Rp 14.664, paku sambungan rangka +Rp 8.400 (harga
paku dikoreksi ke per kg), paku triplek +Rp 657.

## Pengujian

`tests/test_material_katalog.py` (35 tes) menguji:
- keberadaan dan satuan setiap pilihan;
- penggantian material proyek dan elemen tanpa mengubah volume;
- hitung ulang dan baca ulang IFC;
- file proyek dan duplikat;
- dialog Pilihan Material, Material Elemen, dan Katalog;
- mode Kebutuhan Bahan;
- tambah/hapus item katalog;
- isi sheet export.

`tests/test_bekisting_bahan.py` menguji ukuran paku menurut kegunaan (sambungan rangka kaso 5/7 → 10 cm; triplek
12 mm + balok 6/12 → 5 cm; tidak pernah tembus), penggantian kayu/triplek/paku pada analisa (koefisien tetap, fondasi papan tidak
diganti), pilihan kayu & triplek per proyek (varian, hitung ulang IFC, kembali ke bawaan), dialog Ganti Bahan
kelompok Bekisting, label mutu K, kolom SETARA (baja → batang per diameter penulangan proyek, lem, wiremesh,
paku per dus, dll.), dan ganti bahan langsung dari Kebutuhan Bahan (proyek / elemen tersaring, kayu per elemen,
urungkan, hitung ulang IFC).
