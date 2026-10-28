# Panduan Singkat CostStruct

Lima langkah dari file IFC sampai RAB.

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

Semua perubahan bisa dibatalkan dengan **Urungkan** (Ctrl+Z). Pengaturan lain ada di menu **Proyek ▾**: biaya
tidak langsung, tipe penulangan, parameter aturan, hitung ulang dari IFC, serta simpan/duplikat proyek.
