# Semua Elemen Model Masuk RAB

Untuk RAB, setiap elemen di model IFC harus tercatat. Ada dua kemungkinan:
- **dihitung sendiri**, sebagai item pekerjaan dengan analisa HSPK;
- **tercakup pekerjaan lain**, dengan alasan yang jelas, supaya tidak dihitung ganda.

Sebelumnya, elemen di luar 16 kelas utama hanya dilaporkan sebagai "tidak dihitung otomatis". Contohnya cladding,
kisi-kisi, lisplang, nok, talang, dan planter. Sekarang elemen seperti ini dikenali sebagai kelas **LAINNYA**
(`src/elemen_lain.py`) dan masuk RAB.

## Mengapa cladding model 3 lantai tropis sebelumnya tidak dihitung

Cladding di model itu berupa `IfcCovering` dengan PredefinedType `CLADDING`. Klasifikasi lama hanya mengenali
`IfcCovering` lantai (`FLOORING`), plafon (`CEILING`), dan keramik dinding yang namanya mengandung "keramik
dinding" / "backsplash". Akibatnya cladding travertine, batu putih, dan WPC terbaca sebagai "penutup lain" dan
tidak menghasilkan item RAB.

## Cara jenis elemen dikenali

Jenis ditentukan dari kelas IFC dan PredefinedType, lalu dari teks elemen. Teks dibaca dalam dua tahap:
1. **Nama elemen dulu:** nama, ObjectType, dan nama tipe.
2. **Teks lengkap bila nama tidak cukup:** material dan Pset bertema material / deskripsi.

Urutan ini penting. Contoh: keterangan talang box menyebut "rantai hujan", tetapi namanya "Talang Box …", jadi
tetap terbaca sebagai talang. Volume diambil dengan urutan:
1. quantity set standar (Qto `NetArea`, `Length`, `NetVolume`, …);
2. Pset perencana (`Panjang_m`, `Tinggi_m`, `LuasWaterproofing_m2`, `VolumeGalian_m3`, …);
3. geometri, bila keduanya tidak ada.

| Jenis | Dikenali dari | Pekerjaan (HSPK Bandung 2027) | Volume |
|---|---|---|---|
| Cladding batu alam | IfcCovering CLADDING / "cladding", bahan batu, travertine, paras, andesit, marmer | CLD.BATU, dinding batu paras 3.10.4.2 (pilihan: batu tempel, marmer basah/kering, homogeneous tile) | m² |
| Cladding bata tempel | bahan bata tempel / ekspos / brick | CLD.BATA, bata pelapis 3x7x24 3.10.4.1 | m² |
| Cladding panel (WPC, kayu, ACP) | cladding selain batu / bata | CLD.PANEL, **pendekatan** lambrisering papan kayu kelas I 3.10.5.3 (pilihan: plywood, profil aluminium) | m² |
| Kisi-kisi / louver | IfcShadingDevice, "kisi", "louver", "sirip" | CLD.KISI, **pendekatan** profil jalusi aluminium 3.13.2 | m² bidang |
| Rangka cladding / kisi | bahan menyebut "rangka", "hollow" ("penutup rangka atap" tidak dihitung) | CLD.RANGKA, rangka hollow galvanis 20x40 3.10.6.3 (pilihan: 40x40, baja ringan, kayu) | m² |
| Roster / kerawang | "roster", "kerawang" (proxy atau secondary skin) | DND.ROSTER, roster 20x20 3.6.3.5; dicat dua muka bila tertulis "cat" | m² |
| Lisplang | IfcPlate "listplank" / "lisplang" / "fascia" | ATP.LISPLANG, GRC lebar 20 cm 3.3.6 (pilihan: GRC 30, kayu 3x20 / 3x30) | m' |
| Nok / bubungan | IfcCovering ROOFING "nok", "bubung", "jurai" | ATP.NOK, nok genteng beton 3.1.1.8 (pilihan: palentong, kodok, metal, aspal) | m' (luas / lebar bila panjang tidak tertulis) |
| Talang | IfcPipeSegment GUTTER / "talang" | ATP.TALANG, talang ½ lingkaran seng 3.3.2 (pilihan: talang datar / box 3.3.1) | m' |
| Talang tegak / rantai hujan | "rantai hujan", "talang tegak", "downspout" | ATP.TALANG_TEGAK, **pendekatan** pipa PVC D 3" 6.4.1.21 | m' |
| Waterproofing | IfcCovering MEMBRANE / "waterproofing" | WTP.LAPISAN, membran bakar 3.4.1 (pilihan: kristalin, semen base, akrilik) | m² |
| Beton lansekap (planter, kolam, bak) | proxy "planter", "kolam", "bak", atau proxy beton | LSK.BETON K-175 (f'c 15 MPa) 2.2.1.4.3; LSK.BEKISTING 2 muka dinding 2.2.1.3.6; LSK.BESI / LSK.WIREMESH (Ø8-150 bawaan) | m³, m², kg |
| Media tanam | "media tanam", "tanah taman" | LSK.MEDIA_TANAM, urukan tanah subur 1.3.1.7 | m³ |
| Sanitair | IfcSanitaryTerminal / nama kloset, wastafel, floor drain, kran, shower | SNT.*, bab 3.18 (kloset duduk 3.18.3.1, wastafel 3.18.1.1, …) | buah |
| Rangka / batang baja | IfcMember non-atap: "rangka", "hollow", WF, bahan steel / besi | BJA.PROFIL, pabrikasi & ereksi baja profil 2.3.1.1 | kg = V × 7.850 |
| Rangka / batang kayu | IfcMember non-atap berbahan kayu | KYU.KONSTRUKSI, **pendekatan** konstruksi gording kayu kelas II 2.1.2.3 | m³ |
| Elemen tanpa padanan HSPK | perabot, MEP, dll. | `LAIN\|kelas IFC\|nama tipe`, harga 0 (kategori Lain-lain) | buah |

**Pendekatan** berarti HSPK Bandung 2027 tidak memuat analisa bahan itu, jadi dipakai analisa terdekat. Contohnya
panel WPC, kisi WPC, dan rantai hujan. Pengguna dapat:
- mengganti pilihan (combo box bahan, untuk seluruh proyek atau per elemen di Model 3D);
- mengubah komponen di Harga Satuan;
- mengisi harga khusus baris sesuai penawaran.

Beton lansekap memakai tebal yang tertulis di model (mis. "t=8cm"); bila tidak tertulis, diasumsikan 12 cm.
- **Bidang beton** = V / t.
- **Bekisting** = 2 × bidang dinding, yaitu bidang beton dikurangi alas (alas tidak dibekisting kecuali tertulis
  "tanpa dasar").
- **Pembesian** = bidang × berat jaring tulangan dua arah: Ø8-150 = 5,26 kg/m², atau sesuai "Ø…-…" / "wiremesh M…"
  di model.
- **Waterproofing, plester, cat, dan galian** dihitung bila tertulis di model.

## Mengoreksi jenis elemen

Pengenalan jenis bergantung pada nama dan keterangan model. Bila penamaan model tidak lazim, pengguna dapat
mengoreksi jenis elemen kelas LAINNYA:

| Tempat | Cara |
|---|---|
| Model 3D | Klik elemen → seksi **Jenis elemen** di panel kanan (chip *otomatis* / *dikoreksi pengguna*) |
| Menu **Proyek ▾ → Koreksi Jenis Elemen Lain...** | Daftar semua elemen lain: nama, kelas IFC, lantai, dimensi, jenis otomatis, jenis dipakai, dan biaya; dapat dicari dan dikembalikan semua ke otomatis |
| Panel Rincian (tabel) | Tombol **Ubah Jenis Elemen...** membuka daftar di atas dengan elemen itu disorot |

Pilihan berisi semua jenis pada tabel di atas, sanitair per alat (kloset duduk, wastafel, floor drain, ...), dan
**Tidak dihitung** untuk elemen yang sudah termasuk pekerjaan lain atau di luar lingkup RAB.

Cara kerja (`estimasi_service.ubah_jenis_elemen`, `elemen_lain.ganti_jenis`):
- **Tanpa membaca file IFC.** Teks elemen, nama tipe, angka Pset, dan tapak disimpan di `info_lain` saat import,
  sehingga info jenis baru dapat disusun ulang. Volume memakai dimensi yang sudah terbaca (luas, panjang, volume).
- **Cat di balik cladding ikut diperbarui.** Saat import, kontribusi setiap elemen pelat tipis yang menempel pada
  dinding disimpan di dinding (`tutup`: {GlobalId: [luas, sisi, nama]}). Hanya yang berjenis cladding yang
  mengurangi cat. Bila sebuah elemen diubah menjadi atau dari cladding, luas tertutup dinding dihitung ulang.
- **Yang dihitung ulang** hanya elemen yang berubah dan dinding di baliknya. Harga khusus dan catatan
  dipertahankan, volume yang diedit manual pada dinding juga dipertahankan.
- **Dapat diurungkan** (satu langkah per penyimpanan) dan dicatat di Riwayat Aktivitas dengan jenis *Ubah jenis
  elemen*.
- **Tetap berlaku saat IFC dibaca ulang.** Pilihan disimpan di `info_lain.manual`, lalu dipakai lagi lewat
  GlobalId (`ekstrak_elemen(..., jenis_manual)`). Jenis otomatis disimpan di `info_lain.jenis_otomatis`.

Batasan: elemen kelas utama (kolom, balok, pelat, dinding, ...) dan elemen yang **termasuk pekerjaan lain**
(batang rangka atap, penutup atap, bagian tangga) tidak diubah dari sini, karena aturan perhitungannya bukan
dari nama.

## Elemen yang tidak dihitung tersendiri (bukan hitung ganda)

| Elemen | Mengapa | Di penampil 3D |
|---|---|---|
| Batang rangka atap: kuda-kuda, kasau, gording, reng, jurai, termasuk "Sparren" / "Pfette" pada model berbahasa Jerman; IfcMember di lantai bernama atap / roof / Dach | Sudah termasuk Rangka Atap Baja Ringan per m² luas atap. HSPK 2.1.1.1 menganalisa seluruh batang dan alat sambung per m² | Abu-abu "termasuk pekerjaan lain"; diklik → baris Rangka Atap pada bidang atap di atasnya (hijau) |
| Penutup atap IfcCovering ROOFING selain nok | Sudah termasuk Penutup Atap per m² | idem, baris Penutup Atap |
| Bagian IfcStair / IfcRamp (stringer, ibu tangga) | Sudah termasuk pekerjaan tangga | idem, baris tangga |
| Pelat lapisan finishing (tebal < 7 cm atau nama "Finish …") | Penutup lantai sudah dihitung dari penutup lantai, ruang, atau luas pelat struktur. Bila tidak ada sumber lain, pelat ini dihitung sebagai keramik / parket | penjelasan di panel |

## Struktur bukan beton

Kolom, balok, tangga, pelat, dan dak yang **bukan beton bertulang** dulu hanya diberi peringatan. Sekarang tetap
masuk RAB (`elemen_lain.item_nonbeton`):
- **profil baja** (nama WF/HSS/UB… atau material steel/baja): BJA.PROFIL per kg = V × 7.850;
- **kayu** (nama atau material kayu/wood/holz): KYU.KONSTRUKSI per m³;
- **pelat finishing**: keramik (KRM.LANTAI) atau parket (LNT.PARKET), hanya bila penutup lantai belum dihitung dari
  sumber lain;
- **bahan tidak diketahui**: pekerjaan dari model dengan harga 0.

Material IFC disimpan bersama elemen untuk keputusan ini.

## Cat dinding di balik cladding

Bidang dinding yang dilapis cladding tidak dicat. Cladding tegak yang tipis (sisi horizontal terpendek ≤ 10 cm),
sejajar, dan berjarak ≤ 12 cm dari muka dinding dianggap menutup dinding itu. Toleransi 12 cm diperlukan karena
cladding sering dipasang rata dengan muka kolom yang menonjol dari dinding.

Luas yang tertutup = luas cladding × (bidang yang menutup dinding / bidang cladding). Dengan begitu, bagian yang
menutup kolom tidak mengurangi cat dinding. Cladding luar (`Pset_CoveringCommon.IsExternal` atau dinding luar)
mengurangi cat eksterior, cladding dalam mengurangi cat interior. Plester tetap dihitung karena menjadi dasar
pemasangan cladding. Contoh: dinding gevel model 1 lantai, cat eksterior berkurang 11,7 m² + 13,0 m².

## Dampak pada model uji (biaya langsung, HSPK Bandung 2027)

| Model | Sebelum | Sesudah | Tambahan utama |
|---|---|---|---|
| Tipe 120 1 lantai | Rp 828,6 jt | Rp 867,3 jt | bata tempel gevel 28,7 m², lisplang 56,2 m', talang box 18 m, bak air hujan beton |
| Tipe 120 2 lantai courtyard | Rp 1.016,4 jt | Rp 1.140,2 jt | roster 41,6 m² (+ rangka + cat), panel WPC 33,8 m², kolam refleksi beton, lisplang, talang |
| Tipe 120 3 lantai modern tropis | Rp 1.276,8 jt | Rp 1.345,3 jt | cladding batu 14,0 m², WPC kolom 12,0 m², kisi 4,0 m², nok 24,7 m', waterproofing 52,3 m², planter |

Elemen yang masih tidak dihitung tersendiri di ketiga model hanyalah batang rangka atap baja ringan (39 / 170 /
171 batang). Semuanya tercakup Rangka Atap per m².

## Pengujian

`tests/test_elemen_lain.py` memakai model buatan yang berisi cladding batu di muka dinding luar, WPC + rangka,
kisi, lisplang, talang, rantai hujan, nok, waterproofing, planter + media tanam, kloset, kasau, lemari, dan balok
baja WF. Yang diuji:

- jenis dan volume tiap elemen;
- kasau tidak dihitung tersendiri;
- cat eksterior berkurang 6 m² di balik cladding;
- lemari masuk RAB dengan harga 0;
- hasil hitung ulang dari elemen tersimpan sama;
- batang "Sparren" AC20 diklik di penampil 3D → baris Rangka Atap.

Tes lama di `test_rule_koreksi.py` / `test_kf2_ekstraksi.py` disesuaikan:
- stringer Duplex = bagian tangga;
- rangka carport = baja per kg;
- tangga kayu = konstruksi kayu.
