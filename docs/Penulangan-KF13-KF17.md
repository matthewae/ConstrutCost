# Penulangan Rinci, KF-13 Ringkasan Biaya, dan KF-17 Custom Output

Fitur ini menyusun RAB serinci RAB konsultan. Contohnya *RAP Kontrak SMK N 6 Bandung*: sheet
*Perhitungan Besi* menghitung kebutuhan besi per tipe elemen, lalu RAB per bangunan memecah tiap elemen
menjadi bekisting, tulangan utama, beugel, dan beton.

## Penulangan per tipe elemen (KF-4, Rumus 2.30 – 2.33)

Elemen struktur dikelompokkan menjadi **tipe** berdasarkan penampangnya, seperti daftar tipe pada gambar kerja:

| Kelompok | Kode | Kunci tipe | Contoh |
|---|---|---|---|
| Kolom | K1, K2, ... | b × h | Kolom K1 (20/25) |
| Balok | B1, ... | b × h | Balok B1 (15/20) |
| Sloof | S1, ... | b × h | Sloof S1 (20/30) |
| Pelat lantai | P1, ... | tebal | Pelat Lantai P1 (t = 12 cm) |
| Pelat atap (dak) | D1, ... | tebal | Pelat Atap (Dak) D1 (t = 12 cm) |
| Fondasi telapak | F1, ... | tebal | Fondasi Telapak F1 (t = 25 cm) |

Kode diberikan berurutan dari penampang terbesar. Model IFC arsitektur umumnya tidak memuat `IfcReinforcingBar`,
sehingga konfigurasi tulangan diambil dari tipe. Setiap tipe baru mendapat **konfigurasi bawaan**, yang bisa
diubah di menu **Tipe Penulangan**. Konfigurasi yang sudah diubah tetap dipakai saat *Hitung Ulang dari IFC*.

| Kelompok | Konfigurasi bawaan (asumsi rumah tinggal ≤ 2 lantai) |
|---|---|
| Kolom praktis (sisi ≤ 15 cm) | 4 Ø10, sengkang Ø6-150 |
| Kolom b·h ≤ 20/20 | 4 D13, sengkang Ø8-150 |
| Kolom b·h ≤ 25/25 (mis. 20/25) | 6 D13, sengkang Ø10-150 |
| Kolom lebih besar | 8 D16, sengkang Ø10-150 |
| Ring balok / latei (b ≤ 15, h ≤ 20) | 4 Ø10, sengkang Ø8-150 |
| Balok h ≤ 30 / ≤ 40 / lebih | 4 D13 Ø8-150 / 6 D13 Ø10-150 / 6 D16 Ø10-150 |
| Sloof b·h ≤ 15/20 / ≤ 20/25 / lebih | 4 D13 Ø8-150 / 6 D13 Ø10-150 / 6 D16 Ø10-150 |
| Pelat & dak t ≤ 15 cm / lebih | Ø10-150 / D13-150 dua arah, 2 lapis |
| Fondasi telapak t ≤ 30 cm / lebih | D13-150 dua arah 1 lapis / D16-150 2 lapis |

Selimut beton mengikuti SNI 2847:2019 Tabel 20.6.1.3.1: kolom, balok, dan sloof 40 mm; pelat 20 mm; fondasi
75 mm. Diameter < 12 mm dianggap baja polos BjTP (Ø), ≥ 12 mm baja ulir BjTS (D).

**Rumus** (`src/rules/penulangan.py`):

```
W_m      = π d² / 4 × 7850 × 10⁻⁶                              kg/m'   (2.30 – 2.31)
Utama    : L_eff = L + 2 × 12d (+ 40d tiap sambungan 12 m)                (2.32)
           W = n × L_eff × W_m × 1,05                                      (2.33)
Sengkang : n = L / s + 1;  p = 2(b − 2c) + 2(h − 2c) + 2 × max(6d, 75 mm)
           W = n × p × W_m × 1,05
Pelat    : persegi  → jumlah batang tiap arah × (bentang − 2c + 2 × 12d) × lapis
           tidak reguler → panjang = 2 × A / s × lapis
           W = panjang × W_m × 1,05
```

Contoh kolom 20/25, tinggi 3,5 m, 6 D13 + Ø10-150:
- Tulangan utama: 6 × (3,5 + 0,312) × 1,042 × 1,05 = 25,0 kg.
- Sengkang: 24 × 0,73 × 0,617 × 1,05 = 11,3 kg.

Elemen dengan tebal < 7 cm (lapisan finishing yang dimodelkan sebagai pelat) atau sisi < 10 cm (gording
kayu/baja) tidak dianggap beton bertulang. Untuk elemen ini, dan elemen tanpa data penampang, sistem
memakai asumsi rasio kg/m³ seperti sebelumnya.

**Harga**: pekerjaan pembesian dipisah per jenis baja agar memakai item HSPK yang tepat:

| Kode | Item HSPK | Harga satuan |
|---|---|---|
| BSI.KOLOM/BALOK/SLOOF.P | 2.2.1.1.3 Penulangan kolom/balok/sloof BjTP < 12 mm | Rp 27.868 /kg |
| BSI.KOLOM/BALOK/SLOOF.U | 2.2.1.1.4a Penulangan kolom/balok/sloof BjTS ≥ 12 mm | Rp 44.288 /kg |
| BSI.PELAT/DAK/FONDASI.P | 2.2.1.1.1 Penulangan slab BjTP < 12 mm | Rp 22.184 /kg |
| BSI.PELAT/DAK/FONDASI.U | 2.2.1.1.2a Penulangan slab BjTS ≥ 12 mm | Rp 42.171 /kg |

**Kebutuhan besi per diameter**: menu *Tipe Penulangan → Kebutuhan Besi per Diameter* menampilkan berat,
panjang total, dan jumlah batang 12 m per Ø/D. Data ini juga tersedia di sheet export *Kebutuhan Besi*.

**Tampilan RAB Rinci** (mode baru di Hasil Estimasi):

```
II. BETON
  1  Balok B1 (18/41) — 6 buah
       –  Beton Balok f'c 20 MPa          0,22 m3
       –  Bekisting Balok                28,58 m2
       –  Tulangan utama 6 D16          309,35 kg
       –  Sengkang Ø10-150              126,88 kg
```

## KF-13 Ringkasan biaya dan biaya tidak langsung

Sesuai subbab 2.4.2.5, biaya tidak langsung tidak dihitung otomatis, tetapi diisi pengguna per proyek lewat
tombol **Biaya Tidak Langsung**. Setiap item berupa **persentase biaya langsung** atau **nilai tetap (Rp)**.
Usulan uraian yang tersedia: perencanaan teknis, pengawasan, pengelolaan/operasional, perizinan (PBG/SLF),
penerapan SMKK, serta administrasi dan dokumentasi.

```
A. Biaya langsung        = Σ volume × harga satuan     (BUK 10% sudah di dalam harga satuan)
B. Biaya tidak langsung  = Σ (persen × A, atau nilai Rp)
   Jumlah (A + B)
   PPN 11%               = 11% × (A + B)               (KF-11)
   Total, dibulatkan ke bawah per Rp 1.000, beserta terbilang
```

Kartu di halaman Hasil Estimasi berisi A, B, PPN, dan Total RAB. Daftar proyek juga memakai total ini.

## KF-17 Custom Output Formatting

Di dialog **Export RAB**:

| Pilihan | Isi |
|---|---|
| Format | Excel (rumus aktif) / PDF tegak atau mendatar |
| Isi dokumen | Rekapitulasi biaya, RAB rinci per tipe elemen, kebutuhan besi, detail per elemen & lantai |
| Kolom laporan | No, Kode Analisa, Harga Satuan, Bobot (%), Uraian Rumus (detail). Uraian, Volume, Satuan, dan Jumlah Harga selalu ada |
| Informasi dokumen | Nama pekerjaan, lokasi, pemilik/instansi, tahun anggaran |

Pilihan terakhir diingat sebagai bawaan export berikutnya. Bawaan ini juga bisa diatur di halaman Pengaturan.
Pada file Excel, jumlah = volume × harga satuan dan semua total memakai rumus. Sheet *RAB Rinci* dan
*Detail Elemen* memuat baris "Selisih terhadap sheet RAB" yang harus bernilai 0.

## Pengujian

| Berkas | Isi |
|---|---|
| `tests/test_penulangan.py` | berat per meter sesuai tabel besi, kolom (utama + sengkang), lewatan > 12 m, pelat persegi/tidak reguler, tipe bawaan, fallback rasio, validasi, tipe per penampang (AC20), ubah tipe → hitung ulang, kebutuhan besi, harga polos/ulir sesuai HSPK |
| `tests/test_kf13_biaya.py` | terbilang, ringkasan A/B/PPN/pembulatan, CRUD + validasi, total proyek termasuk biaya tidak langsung |
| `tests/test_kf17_export.py` | kolom & sheet sesuai pilihan, RAB rinci & kebutuhan besi, rekap biaya tidak langsung, rumus Excel dihitung ulang LibreOffice tanpa galat dengan selisih 0, PDF tegak/mendatar, pilihan export diingat |
