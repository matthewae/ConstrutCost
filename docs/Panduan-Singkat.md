# Panduan Singkat CostStruct

Lima langkah dari file IFC sampai RAB, ditambah penampil Model 3D.

**Pemasangan:** jalankan `CostStruct-Setup-<versi>.exe` (tanpa hak administrator). Bila SmartScreen muncul,
klik **More info → Run anyway**. Setelah terpasang, file proyek `.coststruct` dapat dibuka dengan klik dua kali.

## 1. Import model
Halaman **Proyek** → **Import IFC** → pilih file `.ifc` → periksa ringkasan → **Import**.
Volume semua pekerjaan dihitung otomatis dari model.

## 2. Pilih bahan proyek
Tombol **Ganti Bahan** (kanan atas). Bahan bawaan sudah terisi, misalnya dinding bata ringan 60×20×10 cm dan
keramik 40×40.
- Ganti bila perlu, lalu klik **Simpan & Hitung RAB**.
- Setiap pilihan menunjukkan harga per m² dan kebutuhan bahannya. Contoh: 8,75 buah bata ringan per m², total
  proyek 1.667 buah.
- Mutu beton dan fondasi ada di **Pengaturan lanjutan**.

## 3. Bahan berbeda untuk elemen tertentu (bila perlu)
Tab **Per Elemen** → kolom **BAHAN ▾** pada baris elemen itu, misalnya "Dinding A".
- Pilih bahan lain, misalnya bata merah. Perubahan langsung tersimpan.
- Harga baris, total RAB, rekap per lantai, dan kebutuhan bahan ikut berubah.
- Pesan di bawah menunjukkan total RAB lama → baru.
- Untuk membandingkan semua pilihan sebelum memutuskan, gunakan **Bandingkan & Ganti Bahan...** di panel kanan.
  Panel ini menampilkan biaya dan jumlah bata, semen, dan pasir setiap pilihan.

## 4. Tambah pekerjaan yang tidak ada di model
Tombol **+ Tambah Pekerjaan** → cari, mis. "kloset", "stop kontak", "pipa pvc" → isi volume dan lantai →
**Tambahkan ke RAB**.

## 5. Lihat dan export
| Tab | Isi |
|---|---|
| **RAB** | Daftar pekerjaan, volume, harga (bentuk penawaran) |
| **RAB Rinci** | Sama, dipecah per tipe elemen |
| **Per Lantai** | Biaya dan kebutuhan tiap lantai |
| **Per Elemen** | Elemen dikelompokkan **per lantai lalu per jenis** (fondasi, kolom, balok, pelat, dinding, ...). Klik judul kelompok, mis. "Dinding — 9 elemen" di Lantai 1, untuk melihat jumlah elemen, volume pekerjaan, dan kebutuhan bahannya. Di baris elemen: ganti bahan, volume, atau harga |
| **Kebutuhan Bahan** | Jumlah bata, semen (zak), pasir, cat, besi, dan lainnya yang perlu dibeli, untuk seluruh bangunan atau satu lantai |

Tombol **Export RAB** membuat file Excel/PDF. File itu memuat RAB, rincian per lantai, kebutuhan bahan
proyek & per elemen, dan daftar bahan yang dipilih.

## 6. Lihat model 3D dan biaya per elemen
Tombol **Model 3D** (Ctrl+3) → klik elemen pada bangunan, mis. Kolom K1 A1.
- Panel kanan menampilkan kebutuhan biayanya: kolom itu, pedestal, fondasi, dan pekerjaan tanah di bawahnya,
  diurutkan per tahap pekerjaan.
- Elemen terpilih berwarna kuning; bagian yang ikut dihitung berwarna hijau.
- Dinding dan elemen lain yang punya pilihan bahan menampilkan combo box bahan dengan harga tiap pilihan untuk
  elemen itu.
- Seret kiri untuk memutar, seret kanan untuk menggeser, roda mouse untuk zoom.
- **Lantai: s.d. …** dan **Arsitektur tembus pandang** membantu memilih kolom di dalam bangunan; **Besi beton** menampilkan
  besi yang dimodelkan di dalam beton tembus pandang.
- **← Kembali ke RAB** (Esc) kembali ke tabel. Semua perubahan tersimpan otomatis dan ikut ke tabel dan Export RAB.
  **Urungkan / Ulangi** tersedia di bagian atas.
- Rincian: `docs/Model-3D.md`.

## 7. Koreksi jenis elemen lain (bila perlu)
Elemen di luar kolom, balok, pelat, dinding, dan sejenisnya (cladding, kisi, roster, lisplang, nok, talang,
waterproofing, planter, sanitair, perabot, ...) dikenali dari nama dan keterangan model. Bila penamaan model tidak
lazim, misalnya panel fasad terbaca kisi-kisi:
- di **Model 3D**, klik elemen → **Jenis elemen** → pilih jenis yang benar; atau
- menu **Proyek ▾ → Koreksi Jenis Elemen Lain...** untuk memeriksa semua elemen lain sekaligus; atau
- tombol **Ubah Jenis Elemen...** di panel Rincian (tabel Per Elemen).

Pilih **Tidak dihitung** untuk elemen yang sudah termasuk pekerjaan lain atau di luar lingkup RAB. Kuantitas
dihitung ulang langsung (termasuk cat dinding di balik cladding), dan pilihan tetap berlaku saat IFC dibaca ulang.

Semua perubahan bisa dibatalkan dengan **Urungkan** (Ctrl+Z). Pengaturan lain ada di menu **Proyek ▾**: biaya
tidak langsung, tipe penulangan, parameter aturan, hitung ulang dari IFC, serta simpan/duplikat proyek.
