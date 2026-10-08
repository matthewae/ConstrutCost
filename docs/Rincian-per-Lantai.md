# Rincian Kebutuhan per Lantai (KF-12 lanjutan)

Mode **Per Lantai** di halaman Hasil Estimasi dan export Excel/PDF sekarang merinci kebutuhan setiap lantai:
- beton per mutu;
- bekisting;
- besi tulangan per diameter;
- bahan, tenaga kerja, dan alat.

Lantai dikenali dari `IfcBuildingStorey` di model IFC, berapa pun jumlahnya (fondasi, lantai 1..n, dak/atap).
Urutannya mengikuti elevasi. Modul perhitungan ada di `src/kebutuhan_lantai.py`.

## Tampilan aplikasi

**Semua lantai** (ringkasan) menampilkan:
- satu baris per lantai, berisi elemen, **beton (m³)**, **bekisting (m²)**, **besi (kg)**, jumlah harga, dan bobot;
- di bawahnya, rincian per kategori pekerjaan;
- baris terakhir **JUMLAH n LANTAI**.

**Satu lantai** dibuka dengan klik dua kali nama lantai, atau dengan memilih lantai di filter. Isinya:

| Bagian | Isi |
|---|---|
| I. Rekap biaya per kategori | Jumlah harga dan persentase terhadap lantai itu |
| II. Struktur beton per tipe elemen | Contoh baris: Kolom K1 (20/25) · beton f'c 20 MPa: jumlah buah, volume beton, bekisting, berat besi, **rasio besi kg/m³**. Rasio di luar 40–350 kg/m³ ditandai ⚠ *periksa* (biasanya dimensi elemen di model tidak wajar). Ditutup dengan total beton per mutu dan total bekisting |
| III. Kebutuhan besi per diameter | Ø8, Ø10, D13, ...: berat (kg), panjang (m'), **jumlah batang 12 m**, berat per meter. Besi dari asumsi rasio (elemen tanpa tipe penulangan) ditulis terpisah |
| IV. Bahan / material | Semen (beserta jumlah zak @ 50 kg), pasir, split, baja, kawat beton, kayu & plywood bekisting, bata, keramik, cat, dll |
| V. Tenaga kerja | Pekerja, tukang, kepala tukang, mandor (orang-hari) |
| VI. Peralatan | Bar bender, bar cutter, dll |
| VII. Rincian pekerjaan | RAB rinci lantai: beton, bekisting, dan tulangan per tipe elemen, ditambah pekerjaan lain |

**Cara menghitung bagian IV–VI:**
- Kuantitas = volume pekerjaan × koefisien analisa (AHSP/HSPK) setiap komponen.
- Harganya adalah harga dasar sumber daya, belum termasuk biaya umum & keuntungan.
- Jumlah seluruh bagian IV–VI × (1 + 10%) sama dengan biaya langsung lantai itu, selama tidak ada harga satuan khusus yang diubah manual.
- Sumber daya varian harga (mis. "Pekerja (Galian Tanah)") digabung dengan sumber daya dasarnya.

**Catatan berat besi:**
- Di bagian III, berat per diameter adalah hasil Rumus 2.33 dan sudah termasuk sisa potongan 5%.
- Di bagian IV, baja tulangan mengikuti koefisien AHSP: 1,05 kg per kg pembesian untuk kolom/balok/sloof, dan 1,02 kg per kg pembesian untuk pelat/fondasi.

## Export

| Isi (dialog Export) | Excel | PDF |
|---|---|---|
| **Rekap per lantai** | Sheet *Rekap per Lantai*: biaya per kategori ditambah kolom beton, bekisting, dan besi. Sheet *Kebutuhan per Lantai*: tabel silang **kebutuhan × lantai** (satu kolom per lantai, ditambah kolom Total) untuk besi per diameter, beton per mutu & bekisting, bahan, tenaga kerja, dan alat | Rekap per lantai dengan kolom beton/bekisting/besi, ditambah tabel besi per diameter × lantai (dipecah per 6 lantai bila lebih banyak) |
| **Rincian per lantai** (baru) | **Satu sheet untuk setiap lantai**: `Lt01 00 FONDASI`, `Lt02 01 LANTAI 1`, ... berisi bagian I–VII seperti di aplikasi | Satu bagian (halaman baru) untuk setiap lantai, berisi bagian I–VII |

**Ketentuan nama sheet:**
- Nama sheet dibuat aman: maksimal 31 karakter, dan karakter `[ ] : * ? / \` diganti spasi.
- Nama dibuat unik walaupun ada nama lantai yang sama atau sangat panjang.

**Rumus di Excel:**
- Besi: berat/m = π·d²/4·7850, panjang = berat / (berat/m), batang = ROUNDUP(panjang/12).
- Rasio besi = besi/beton.
- Jumlah harga = volume × harga.
- Setiap sheet lantai punya baris *Selisih terhadap rekap kategori (harus 0)*.

Pilihan isi tersimpan sebagai bawaan (Pengaturan → Isi dokumen → *Rincian per lantai*).

## Pengujian

`tests/test_kebutuhan_lantai.py` menguji:
- model sintetis **5 lantai**, termasuk nama lantai dengan karakter `/` dan `[ ]`;
- model Duplex Revit (4 lantai).

Yang diperiksa:
- semua lantai terbaca dan urut elevasinya benar;
- jumlah biaya per lantai = biaya langsung;
- besi per diameter konsisten dengan rekap kebutuhan besi;
- biaya sumber daya × 1,1 = biaya langsung;
- penggabungan varian sumber daya;
- nama sheet aman dan unik;
- satu sheet Excel dan satu bagian PDF per lantai;
- rumus Excel setelah dihitung ulang LibreOffice: tanpa `#ERROR`, dan semua selisih = 0;
- tampilan ringkas dan rinci di halaman Hasil Estimasi.
