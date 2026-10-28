# Koreksi Basis Aturan (Rule Engine) setelah Audit

> Pilihan material, katalog HSPK lengkap, dan kebutuhan bahan per elemen: lihat `docs/Katalog-Material-Kebutuhan.md`.
> Mulai versi itu pasangan dinding bawaan adalah bata ringan 60×20×10 (HSPK 3.6.4.2); angka dampak di bawah dihitung dengan bata merah.

Mesin aturannya sudah benar sejak awal:
- pencocokan kelas, syarat, dan dimensi wajib;
- *forward chaining* satu siklus;
- satuan yang sama dengan analisa HSPK.

Audit pada tiga model uji menemukan beberapa **asumsi konstruksi** yang membuat RAB menyimpang. Dokumen ini
mencatat setiap koreksi, alasannya, dan dampaknya. Jumlah aturan bertambah dari 52 menjadi 69.

## Ringkasan koreksi

| No | Masalah | Koreksi | Kode |
|---|---|---|---|
| 1 | Pelat lantai dasar (slab on grade) dihitung D13-150 dua lapis penuh (±29 kg/m²) | Kelompok tipe baru **Pelat Lantai Dasar (L1, L2, …)**, bawaan Ø8-150 satu lapis (setara wiremesh M8-150, ±5,5 kg/m²) | `rules/penulangan.py` |
| 1 | Pelat lantai atas dan dak dihitung dua lapis penuh | Susunan bawaan **bawah penuh + atas tumpuan**: tulangan atas ¼ bentang dari tiap tepi = ½ lapis, faktor 1,5. Pilihan "1 lapis" dan "2 lapis penuh" tetap tersedia di Tipe Penulangan | `rules/penulangan.py`, `gui/penulangan_dialog.py` |
| 2 | Lapisan finishing (keramik/parket 1–2 cm) dan lantai kayu yang dimodelkan sebagai IfcSlab dihitung sebagai beton + besi + bekisting | Elemen **bukan beton** dikenali dari tiga ciri: tebal < 7 cm, nama kayu/finishing, atau profil baja. Beton, besi, bekisting, serta keramik/plafon/tanah dari pelat tidak dihitung, dan pengguna mendapat peringatan | `rules/sifat.py` |
| 3 | Kolom praktis (13/13) mendapat fondasi sumuran Ø100 cm sendiri | Sumuran turunan hanya untuk **kolom struktur** (sisi terkecil > 15 cm). Kolom tanpa ukuran tetap dianggap kolom struktur | `rules/sifat.py`, `rules/definitions.py` |
| 4 | Model tanpa fondasi: batu kali diturunkan tetapi **sloof** tidak | **Sloof turunan** di bawah dinding pasangan lantai dasar (beton, besi tipe S, bekisting 2 sisi). Ukuran otomatis 15/20 (1 lantai) atau 20/30 (≥ 2 lantai); bisa diubah di Parameter Aturan | `rules/konteks.py`, `rules/definitions.py` |
| 5 | Balok/kolom baja (WF, UB, HSS) dan gording kayu dihitung sebagai beton bertulang | Dikenali dari nama profil, dari volume < 50% b × h × L (penampang berongga), atau dari penampang < 10 cm | `rules/sifat.py` |
| 6 | (diperiksa) Plafon dari sumber "pelat" ikut menghitung pelat lantai dasar | **Bukan kesalahan**: plafon tiap lantai ≈ luas lantai tersebut (pelat dasar = plafon lantai 1, pelat lantai 2 = plafon lantai 2). Totalnya sudah benar, jadi tidak diubah | — |
| 7 | Tangga, railing, member, proxy, dan curtain wall diabaikan tanpa pemberitahuan | Dilaporkan di dialog Konfirmasi Import dan di peringatan estimasi, supaya pekerjaannya bisa ditambah manual | `klasifikasi.py`, `ifc_reader.py`, `gui/import_dialog.py` |
| 8 | Fondasi menerus dari model selalu dihargai sebagai batu kali | Parameter **Fondasi menerus dihitung sebagai**: otomatis dari nama (bawaan), batu kali, atau beton bertulang. Fondasi beton dihitung beton + besi + bekisting + lantai kerja dan tidak memerlukan sloof turunan | `rules/konteks.py`, `rules/parameter.py` |
| 9 | Bekisting balok selalu (b + 2h)L | Balok yang dicor bersama pelat: **(b + 2(h − t_pelat))L**, dengan t = median tebal pelat/dak beton. Ring balok/latei (≤ 15/20) dan sloof tidak dikurangi. Bisa dimatikan di Parameter Aturan | `rules/konteks.py`, `rules/definitions.py` |
| 10 | Sisi luar dinding luar memakai item cat interior | Dinding luar dikenali dari `Pset_WallCommon.IsExternal`, dan sisi luarnya menjadi item **Pengecatan Tembok Eksterior**. Harganya sementara mengikuti analisa interior (lihat catatan HSPK di bawah) | `ifc_reader.py`, `rules/definitions.py`, `database/seed_data.py` |
| 11 | Pekerjaan persiapan belum ada | **Pembersihan lahan** (luas pelat/ruang lantai dasar) dan **pengukuran + bowplank** (keliling dinding luar lantai dasar + 8a, dengan a = jarak bowplank, bawaan 1,5 m) | `rules/definitions.py`, `database/seed_data.py` |

Perbaikan pendukung:
- **Dinding pasangan:** batu kali dan sloof turunan hanya diberikan pada dinding setebal ≥ 10 cm, sehingga partisi gypsum/GRC tidak mendapat fondasi.
- **Balok bernama sloof** ("Sloof", "Tie beam", "Ground beam") dihitung sebagai sloof: bekisting dua sisi, tipe tulangan S.
- **Tipe penulangan bawaan** yang belum diubah pengguna otomatis mengikuti konfigurasi bawaan terbaru saat estimasi atau hitung ulang. Tipe yang sudah diubah pengguna tidak disentuh.

## Koreksi lanjutan dari uji model rumah tinggal (Rumah Tipe 90, 2 lantai + carport)

| Masalah | Koreksi | Kode |
|---|---|---|
| "BSK.BALOK: lebar, tinggi kosong" pada *Ring Balok Miring Gevel 13/15*. Balok miring tanpa quantity set: bounding box elemen miring tidak mewakili penampang | Penampang dibaca dari **profil persegi yang diekstrusi** (IfcRectangleProfileDef XDim × YDim, panjang = Depth). Cadangan terakhir: ukuran di **nama elemen** ("13/15" = 13 × 15 cm). Asal nilai tercatat `profil` / `nama` | `ifc_reader.py` |
| Tangga dan railing hanya dilaporkan "tidak dihitung" | **Tangga beton** (IfcStairFlight, atau IfcStair yang tidak dipecah) dihitung: beton f'c 20 MPa, bekisting tangga B × √(L² + H²) + B × H (HSPK 2.2.1.3.7), dan besi dengan rasio 100 kg/m³ (parameter). Tangga kayu/baja dikenali dari nama, atau dari volume < 6% L × B × H. **Railing**: railing tangga/hand rail (HSPK 3.13.5) bila HANDRAIL, namanya menyebut tangga, atau miring; selain itu railing pengaman 1,2 m (HSPK 3.13.4) | `klasifikasi.py`, `rules/definitions.py`, `rules/sifat.py` |
| Enam baris "tidak dihitung" terpisah | Diringkas menjadi **satu catatan** berisi jumlah dan **contoh nama** tiap jenis (IfcMember, IfcPlate, proxy, penutup lain), plus keterangan bahwa rangka atap baja ringan sudah dihitung per m² luas atap | `klasifikasi.py` |
| Dialog Konfirmasi Import lebih tinggi dari layar, sehingga tombol Import tidak terjangkau | Ringkasan dapat digulir; kolom nama proyek dan tombol Batal/Import selalu terlihat di bawah; tinggi dialog maksimal 88% tinggi layar | `gui/import_dialog.py` |
| **Regresi:** hampir semua sloof, balok, ring balok, balok latei, dan balok praktis beton ditolak sebagai "penampang berongga (kemungkinan profil baja)" | Model menggambar balok sebagai **denah** L × b yang diekstrusi setinggi h (Depth = tinggi), bukan penampang b × h yang diekstrusi sepanjang L. Pembaca profil dulu selalu menganggap XDim = lebar, sehingga lebar = panjang bentang (Sloof 25/40 bentang 2,67 m → isi 0,40 / 2,67 = 15%). Sekarang sisi yang mewakili panjang dipilih dulu (panjang dari quantity set, atau sisi terpanjang), dan dua sisi lainnya menjadi penampang. **Pengaman:** bila b × h × L tidak cocok dengan volume tetapi ukuran di nama ("25/40") cocok, ukuran nama yang dipakai | `ifc_reader.py` |
| Tangga beton "Anak Tangga 1A (1-10)" ditolak (isi 15%) | Batas isi tangga diturunkan dari 25% menjadi **6%**. Tangga beton (pelat miring 10–15 cm + anak tangga) mengisi ± 11–20% kotak L × B × H. Tangga kayu/baja hanya ± 0,5–3% | `rules/sifat.py` |
| Catatan "tidak dihitung" untuk proxy *Lantai Kerja FP…* dan penutup *Keramik Dinding* | Catatan menurut nama: lantai kerja sudah dihitung dari ukuran fondasi telapak, sehingga tidak perlu ditambah lagi. Keramik dinding ruang basah dihitung dari ruang (IfcSpace) bila ada | `klasifikasi.py` |

## Analisa pekerjaan persiapan

Pekerjaan persiapan memakai analisa HSPK Kota Bandung 2027 dari sheet *Persiapan* (bab 1.1):

| Kode HSPK | Analisa | Harga satuan |
|---|---|---|
| 1.1.3.1 | Pembersihan dan pengupasan permukaan tanah (striping) s.d. tanaman Ø 2 cm | Rp 24.413 /m² |
| 1.1.4.2 | Pasangan 1 m' bouwplank | Rp 76.453 /m' |

**Koreksi:** versi sebelumnya memakai analisa pengganti SNI 2835:2008 (Rp 39.686/m² dan Rp 106.880/m').
Alasannya keliru, yaitu anggapan bahwa HSPK tidak memuat pekerjaan persiapan; sebenarnya sheet *Persiapan*
saja yang belum ikut diimpor. Urugan tanah kembali dan urugan pasir juga sudah dipindahkan ke analisa
HSPK 1.3.1.1 dan 1.3.1.2.

## Catatan data HSPK: cat tembok eksterior

Analisa HSPK **3.8.10.2** (pengecatan tembok baru eksterior) memakai harga dasar *"Cat penutup (cat tembok
eksterior)"* **Rp 1.624.000/kg**. Akibatnya harga satuannya Rp 509.761/m², sekitar 6 kali cat interior
(Rp 82.542/m²). Angka ini kemungkinan harga per pail yang tercatat sebagai harga per kg.

Karena itu item **CAT.EKSTERIOR** sementara memakai analisa **3.8.10.1**. Volumenya tetap dipisah, sehingga
cukup mengganti komponen analisanya setelah harga cat eksterior diverifikasi.

## Dampak pada model uji

Total RAB (biaya langsung, HSPK Bandung 2027), dihitung ulang dengan `jalankan_estimasi`:

| Model | Sebelum | Sesudah | Selisih | Penyebab utama |
|---|---|---|---|---|
| AC20-FZK-Haus | Rp 895.387.245 | Rp 800.630.509 | −10,6% | Besi pelat dasar 3,5 t → 0,66 t; pelat atas ke tulangan tumpuan; gording kayu bukan beton; ditambah sloof turunan 20/30 dan pembersihan lahan; railing tangga 6,3 m' |
| Duplex_A_20110907 | Rp 1.837.987.806 | Rp 1.193.024.683 | −35,1% | Lantai "Wood Joist" dan atap "Wood Joist Flat Roof" bukan beton; balok baja W310/W410; lapisan finishing; fondasi menerus "Bearing Footing" = beton; ditambah cat eksterior, persiapan, dan railing 26,2 m' (tangga kayu tidak dihitung beton) |
| SampleStructuralModel | Rp 1.675.856.975 | Rp 1.320.404.167 | −21,2% | 268 balok UB baja dan kolom UB/HSS bukan beton; lantai plywood; fondasi menerus beton; pelat atas ke tulangan tumpuan |

Ketiga model uji ini bukan rumah tinggal Indonesia. Duplex dan SampleStructural memakai konstruksi kayu/baja,
sehingga selisih besar di sana adalah koreksi, bukan regresi. Uji akurasi terhadap RAB referensi tetap
memakai model rumah tinggal dari PT Mandajaya.

## Pengujian

`tests/test_rule_koreksi.py` (35 tes) menguji setiap koreksi di atas, termasuk dialog Parameter Aturan
(pilihan dan nilai "otomatis") dan dialog Tipe Penulangan. `tests/test_penulangan.py` menambah tes susunan
"atas tumpuan", tipe Pelat Lantai Dasar, dan pembaruan tipe bawaan.
