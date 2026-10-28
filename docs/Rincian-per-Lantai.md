# Rincian Kebutuhan per Lantai (KF-12 lanjutan)

Mode **Per Lantai** di halaman Hasil Estimasi dan export Excel/PDF sekarang merinci kebutuhan setiap lantai:
- beton per mutu;
- bekisting;
- besi tulangan per diameter;
- bahan, tenaga kerja, dan alat.

Lantai dikenali dari `IfcBuildingStorey` di model IFC, berapa pun jumlahnya (fondasi, lantai 1..n, dak/atap).
Urutannya mengikuti elevasi. Modul perhitungan ada di `src/kebutuhan_lantai.py`.

## Tampilan aplikasi

**Tabel Per Lantai hanya berisi judul**, seperti RAP/RAB konsultan:
- satu baris per lantai, berisi elemen, **beton (m³)**, **bekisting (m²)**, **besi (kg)**, jumlah harga, dan bobot;
- di bawahnya, judul bagian pekerjaan: `I. PEKERJAAN TANAH`, `II. PEKERJAAN BETON`, `III. PEKERJAAN DINDING`,
  … `PEKERJAAN KUDA-KUDA DAN ATAP`, `PEKERJAAN PLAFON`, `PEKERJAAN PENGECATAN`;
- baris terakhir **JUMLAH n LANTAI**.

Kolom judul minimal 320 px. Di layar sempit atau dengan skala tampilan Windows besar, tabel bergulir ke
samping sehingga judul tetap terbaca.

**Rincian lebih dalam ada di panel kanan Rincian Perhitungan**, yang diperlebar di mode ini. Susunannya
mengikuti RAP SMK N 6 Bandung, dengan rincian yang lebih detail:

```
LEVEL 1                                          Rp 552.597.761
I.   PEKERJAAN TANAH                             Rp   6.918.179
1    Urugan Pasir Bawah Lantai                         15,35 m3
     15,353 m3 × Rp 450.613 = Rp 6.918.179 · TNH.PASIR.LANTAI
       • Floor:150mm Slab on Grade: T 0,15 · 2 bh × 1,271 = 2,542 m3     <- backup volume
II.  PEKERJAAN BETON                             Rp 157.583.424
1    Balok B1 (18/41) — 2 buah                   Rp  11.911.302
       –  Beton Balok f'c 20 MPa                        0,09 m3
          • W410X60: P 6,18 × L 0,18 × T 0,41 · 2 bh × 0,046 = 0,093 m3
       –  Bekisting Balok                              12,26 m2
       –  Tulangan utama 6 D16                        130,58 kg
          Contoh rumus: W_m D16 = π × 16² / 4 × 7850 × 10⁻⁶ = 1,578 kg/m'; L_eff = …; W = n × L_eff × W_m × 1,05
       –  Sengkang Ø10-150                             54,38 kg
...
REKAP STRUKTUR & KEBUTUHAN BESI PER DIAMETER  (berat ÷ kg/m' = m' → batang 12 m)
BAHAN / TENAGA KERJA / ALAT (volume × koefisien AHSP)
PENUTUP BANGUNAN (lantai teratas: atap + plafon / dak beton / plafon)
```

Cara memakai panel:
- **Tanpa pilihan**: semua lantai berurutan dari lantai terbawah sampai penutup bangunan, berisi bagian dan
  item RAP.
- **Pilih lantai**: rincian lengkap lantai itu. Setiap item disertai harga × volume = jumlah dan **backup volume**:
  elemen dengan nama tipe dan dimensi sama digabung, P × L × T · jumlah unit × volume/unit = volume. Item besi
  disertai contoh rumus, lalu besi per diameter, bahan, tenaga kerja, alat, dan penutup.
- **Pilih bagian** (mis. `II. PEKERJAAN BETON` di Lantai 1): hanya bagian itu beserta backup volumenya.

Bagian **Penutup bangunan** ditulis di lantai teratas yang memuat atap (penutup + rangka) atau dak beton,
ditambah plafon di lantai itu. Bila model langsung beratap atau hanya memakai plafon, plafon tersebut yang
ditulis.

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
| (bagian dari *Rekap per lantai*) | Sheet *Rincian Perhitungan Lantai*: susunan RAP per lantai (I. PEKERJAAN TANAH, II. PEKERJAAN BETON: 1 Kolom K1 — n buah: – Beton / – Bekisting / – Tulangan …) dengan **BackUp Volume** di bawah setiap item. Kolom: No, Uraian, Panjang, Lebar, Tinggi, Luas, Jlh Unit, Volume/Unit, Total Volume (= Jlh Unit × Volume/Unit), Sat, Harga Satuan, Jumlah (= Total Volume × Harga), Kode. Volume item = SUM backup. Setelah itu kebutuhan besi per diameter, bahan, tenaga kerja, dan alat; jumlah tiap lantai dengan baris selisih (harus 0); ditutup **PENUTUP BANGUNAN** | Bagian *Rincian Perhitungan per Lantai (RAB & Backup Volume)* dengan isi yang sama |
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
