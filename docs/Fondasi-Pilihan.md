# Pilihan Jenis Fondasi Kolom: Footplate atau Cakar Ayam (Sedijatmo)

Masukan dosen pembimbing: jenis fondasi dapat dipilih tanpa mengubah gambar (model IFC). Untuk tahap ini pilihannya
dibatasi **footplate** dan **cakar ayam**. Pilihan ada di **Parameter Aturan › Jenis fondasi kolom › Fondasi kolom
dihitung sebagai** (combo box, grup paling atas). Menyimpan pilihan langsung menghitung ulang RAB dari elemen
tersimpan. Kode: `src/rules/fondasi_kolom.py`, `src/relasi.py`, `src/perbandingan_fondasi.py`.

| Pilihan | Isi perhitungan |
|---|---|
| Sesuai model IFC (bawaan) | Fondasi yang dimodelkan dihitung apa adanya. Model tanpa fondasi: sumuran turunan per kolom struktur (Batasan no. 8) |
| Footplate (fondasi telapak) | Setiap kolom struktur di lantai dasar berfondasi telapak (lihat di bawah) |
| Cakar ayam (sistem Sedijatmo) | Pelat beton bertulang tipis di bawah denah lantai dasar + pipa beton ("cakar") di bawahnya |

"Cakar ayam" di sini adalah **sistem Prof. Sedijatmo**: pelat beton bertulang tipis yang dikakukan pipa-pipa beton
di bawahnya, dan pelat berfungsi sebagai lantai sekaligus fondasi. Istilah lapangan "cakar ayam" untuk footplate
tidak dipakai, karena dengan arti itu kedua pilihan akan sama.

## Fondasi di bawah kolom (relasi geometri)

Saat IFC dibaca, setiap fondasi setempat (footplate, sumuran, poer, tiang) dipetakan ke kolom fisik di atasnya.
Syaratnya: titik kolom berada di dalam denah fondasi (toleransi 5 cm) dan puncak fondasi di bawah kaki kolom.
Kolom fisik mengikuti `src/kolom.py` (pedestal + kolom = satu kolom).

## Footplate

- Footplate yang dimodelkan **tetap dipakai**, karena itu ukuran rencana perencana.
- Sumuran, poer, dan tiang yang dimodelkan di bawah kolom **tidak dihitung**, lalu diganti footplate turunan.
- Kolom struktur yang tidak punya fondasi di model mendapat **footplate turunan** B × B × t:

| Jumlah lantai | B × B × t (otomatis) |
|---|---|
| 1 | 0,80 × 0,80 × 0,25 m |
| 2 | 1,00 × 1,00 × 0,25 m |
| ≥ 3 | 1,20 × 1,20 × 0,30 m |

  Ukuran bisa diisi sendiri (Footplate: lebar / tebal). Item yang dihitung:
  - beton fondasi f'c 20 MPa;
  - bekisting 4·B·t;
  - tulangan dari tipe fondasi bawaan (D13-150, 1 lapis untuk t ≤ 30 cm);
  - galian, lantai kerja, dan urugan kembali (rumus footplate di `rules/tanah.py`);
  - **pedestal turunan** b × h × (kedalaman − t), bila kolom model tidak turun sampai fondasi.
- Batu kali turunan di bawah dinding dan sloof turunan tetap seperti bawaan.

## Cakar ayam (sistem Sedijatmo)

**Tidak dihitung:**
- semua fondasi model (footplate, sumuran, poer, tiang, batu kali menerus);
- pedestal;
- aanstamping, urugan pasir bawah fondasi, dan lantai kerja bawah fondasi;
- pelat beton lantai dasar di dalam bangunan (digantikan pelat cakar ayam);
- sloof, kecuali parameter *Cakar ayam: sloof tetap dihitung = Ya*.

**Dihitung** (parameter bawaan dapat diubah):

| Pekerjaan | Rumus |
|---|---|
| Pelat cakar ayam | A × t, t = 0,15 m; A = luas lantai dasar di dalam selubung bangunan (pelat/rabat › penutup lantai › ruang) + tapak dinding lantai dasar (L × tebal) |
| Pipa cakar | n = maks(n kolom struktur, ⌈A / s²⌉), s = 2,50 m; satu pipa di bawah setiap kolom struktur (termasuk kolom carport), sisanya dibagi ke bidang lantai menurut luasnya |
| Beton pipa | n × π/4 × (D² − Di²) × L; D = 0,80 m, tebal 0,08 m (Di = 0,64 m), L = 2,00 m |
| Bekisting pipa | n × π × (D + Di) × L (dalam & luar, dicor di tempat) |
| Bekisting tepi pelat | panjang dinding luar lantai dasar × t |
| Tulangan pelat | Ø10-200 dua arah dua lapis: 2 × 2 × A / s × W_m × 1,05 |
| Tulangan pipa | Ø8-200: vertikal ⌈π Dm / s⌉ × (L + t) dan cincin (⌊L / s⌋ + 1) × (π Dm + 40d), Dm = D − tebal |
| Galian | pelat A × t (0–1 m); lubang pipa n × π/4 × D² × L (kedalaman t + L) |
| Urugan kembali | tanah di dalam pipa dipadatkan kembali: n × π/4 × Di² × L |

Urugan pasir dan rabat/lantai kerja di bawah lantai tetap dihitung, karena menjadi alas pelat cakar ayam.

Perkerasan di luar selubung bangunan (carport, jalan masuk, area servis, teras luar) tidak termasuk pelat cakar ayam
dan tetap dihitung apa adanya. Selubung bangunan adalah poligon cembung dinding semua lantai ditambah kolom yang
menerus antarlantai. Bidang yang titik tengahnya lebih dari 30 cm di luar selubung dianggap perkerasan luar.

Analisa HSPK yang dipakai:
- beton pelat & pipa: 2.2.1.4.5 (beton f'c 20 MPa);
- bekisting: 2.2.1.3.1 (bekisting fondasi);
- pembesian: 2.2.1.1.1 / 2.2.1.1.2a (penulangan slab).

## Export: sheet PERBANDINGAN_FONDASI

Saat export Excel (bersama Rekapitulasi), rule engine dijalankan ulang di memori untuk ketiga pilihan. Sheet
**PERBANDINGAN_FONDASI** memuat:

1. Hanya pekerjaan yang volumenya berbeda antar jenis, dengan volume dan jumlah per jenis.
2. Jumlah pekerjaan yang berbeda per jenis.
3. Biaya langsung (A) per jenis = A di sheet RAB − pekerjaan berbeda jenis ● + pekerjaan berbeda jenis itu (rumus
   aktif ke RAB). Edit manual, harga khusus, dan item katalog tetap terbawa.
4. Beda biaya langsung terhadap jenis yang dipakai (●), lalu total (A + biaya tidak langsung) + PPN, dibulatkan.
5. Catatan ringkas tiap jenis: jumlah footplate turunan, luas pelat, jumlah pipa, dan elemen yang tidak dihitung.

Biaya langsung tiap jenis di sheet ini sama dengan estimasi penuh bila jenis itu dipilih (diuji di
`tests/test_fondasi_pilihan.py`).

## Hasil pada model uji (biaya langsung, HSPK Bandung 2027)

| Model | Sesuai model | Footplate | Cakar ayam |
|---|---|---|---|
| Tipe 120 1 lantai | Rp 828.626.724 | Rp 828.626.724 (semua kolom sudah footplate) | Rp 829.754.908 (pelat 122,1 m², 20 pipa) |
| Tipe 120 2 lantai courtyard | Rp 1.016.409.882 | Rp 1.009.646.048 (3 sumuran+poer → footplate 1,0 × 1,0 × 0,25) | Rp 973.708.444 (pelat 117,4 m², 19 pipa) |
| Tipe 120 3 lantai modern tropis | Rp 1.276.780.174 | Rp 1.266.598.840 (4 sumuran+poer → footplate 1,2 × 1,2 × 0,30) | Rp 1.197.628.629 (pelat 44,4 m², 15 pipa) |

## Batasan

- Dimensi cakar ayam adalah asumsi rumah tinggal pada tanah lunak–sedang (pipa Ø 0,80 m panjang 2 m, jarak 2,5 m),
  bukan hasil desain struktur. Ubah di Parameter Aturan sesuai gambar kerja atau perhitungan perencana.
- Footplate turunan berukuran seragam per jumlah lantai, bukan dari beban kolom.
- Proyek yang dibaca dengan versi sebelumnya belum punya relasi geometri. Lakukan **Hitung Ulang dari IFC** sekali
  agar fondasi per kolom, pedestal, dan perkerasan luar dikenali.
