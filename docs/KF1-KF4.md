# Implementasi KF-1 s.d. KF-4

Ringkasan implementasi untuk BAB IV (Implementasi dan Pengujian). Nomor rumus mengacu BAB II subbab 2.4.9.

## Alur

```
UC-01  Pilih / seret file .ifc
  └─ KF-1  buka_dan_validasi()            src/ifc_reader.py
           ekstensi .ifc → header ISO-10303-21 → penutup END-ISO-10303-21;
           → dibuka di proses terpisah (file korup tidak membuat aplikasi crash)
           → versi IFC2x3 / IFC4 → ada IfcProject
           → ringkasan: ukuran, versi, pembuat, satuan, lantai, jumlah elemen per kelas
  └─ Dialog "Konfirmasi Import File IFC"   src/gui/import_dialog.py
  └─ KF-2  ekstrak_elemen()                src/ifc_reader.py, src/klasifikasi.py
           klasifikasi → ElementType, dimensi G = {L, B, H, t, A, V}, lantai, elevasi
  └─ KF-3  preprocessor + rule engine      src/rules/konteks.py, src/rules/engine.py
  └─ KF-4  rumus kuantitas per aturan      src/rules/definitions.py
  └─ simpan elemen_proyek + hasil_estimasi (beserta uraian rumus) → halaman hasil
```

Parsing berjalan di thread terpisah dengan progress bar (`src/gui/proses_latar.py`).

## KF-2: klasifikasi

| Entitas IFC | Kelas | Catatan |
|---|---|---|
| IfcColumn | COLUMN | |
| IfcBeam | BEAM | |
| IfcSlab | SLAB / ROOF | ROOF bila PredefinedType ROOF atau bagian dari IfcRoof |
| IfcRoof | ROOF | hanya bila tidak dipecah menjadi IfcSlab (hindari hitung ganda) |
| IfcWall (+ subtipe) | WALL | |
| IfcFooting | FOOTING | STRIP_FOOTING, FOOTING_BEAM (sloof), PAD_FOOTING, dst. |
| IfcPile | PILE | |
| IfcDoor / IfcWindow | DOOR / WINDOW | |
| IfcCovering | CEILING / FLOOR | hanya CEILING dan FLOORING |
| IfcSpace | SPACE | kecuali EXTERNAL dan GFA |

Sumber dimensi, berurutan: (1) quantity set `Qto_*BaseQuantities`, `BaseQuantities` (ArchiCAD),
`PSet_Revit_Dimensions`; (2) geometri 3D di koordinat lokal elemen. Asal setiap nilai disimpan di
kolom `sumber_dimensi`. Faktor satuan panjang, luas, dan volume dibaca terpisah dari file
(contoh: `SampleStructuralModel.ifc` memakai mm untuk panjang tetapi m² untuk luas).

Uji kewajaran:
- Keliling < 0,9·√(4πA) dianggap salah satuan dan dihitung ulang dari geometri.
- Penampang balok/kolom miring tidak diambil dari bounding box.

## KF-3 / KF-4: basis aturan

| Kelas | Syarat | Kode | Kuantitas | Rumus |
|---|---|---|---|---|
| COLUMN | – | BTN.KOLOM | V | 2.10 |
| COLUMN | – | BSI.KOLOM | V × rasio besi | |
| COLUMN | – | BSK.KOLOM | 2(b + h) × H | |
| COLUMN | lantai dasar & model tanpa fondasi | BTN.SUMURAN | n·πd²/4·H + P·L·T | 2.36–2.39 |
| BEAM | – | BTN / BSI / BSK.BALOK | V; V × rasio; (b + 2h) × L | 2.9 |
| SLAB | – | BTN / BSI.PELAT | V; V × rasio | 2.11 |
| SLAB | bukan BASESLAB & bukan lantai dasar | BSK.PELAT | A | |
| ROOF | θ ≥ 5° | ATP.RANGKA, ATP.PENUTUP | A = A_proyeksi / cos θ | 2.22–2.23, 2.42 |
| ROOF | θ < 5° (dak) | BTN / BSI / BSK.DAK | V; V × rasio; A | |
| WALL | – | DND.BATA | A bersih (bukaan sudah dikurangkan) | 2.17 |
| WALL | – | PLS.DINDING, ACI.DINDING, CAT.DINDING | A × 2 sisi | 2.17–2.19 |
| WALL | lantai dasar & model tanpa fondasi | FDN.BATUKALI | (B_atas + B_bawah)/2 × H × L | 2.34 |
| FOOTING | STRIP_FOOTING | FDN.BATUKALI | V | |
| FOOTING | FOOTING_BEAM | BTN / BSI / BSK.SLOOF | V; V × rasio; 2h × L | |
| FOOTING | lainnya (footplate) | BTN / BSI / BSK.FONDASI | V; V × rasio; keliling × t | |
| PILE | – | BTN.SUMURAN | V | |
| DOOR | – | PTU.DAUN, PTU.KUSEN, PTU.KUNCI, PTU.ENGSEL | B × H; 2H + B; 1 buah; 3 buah | |
| WINDOW | – | JDL.JENDELA | lebar × tinggi | |
| FLOOR / SPACE / SLAB | sumber lantai* | KRM.LANTAI | A | 2.12–2.13 |
| SPACE | nama ruang basah (KM, WC, dapur, ...) | KRM.DINDING | keliling × tinggi keramik | 2.14–2.15 |
| CEILING / SPACE / SLAB | sumber plafon* | PLF.RANGKA, PLF.GYPSUM | A | 2.16 |

\*Preprocessor memilih **satu** sumber agar tidak terhitung ganda, dengan prioritas: penutup lantai/plafon
yang dimodelkan → luas ruang (IfcSpace) → luas pelat.

Lantai dasar adalah lantai terendah yang berisi dinding/kolom/pelat dan elevasinya ≥ −0,5 m (level
fondasi seperti `T/FDN −1,25` tidak dihitung sebagai lantai dasar).

Semua angka asumsi (rasio besi, dimensi batu kali/sumuran, ukuran keramik/genteng, kata kunci ruang
basah) ada di `src/rules/parameter.py`. Kebutuhan keramik/genteng per m² diturunkan dengan rumus BAB II,
misalnya keramik 40×40: 1/(0,40 × 0,40) × 1,05 = 6,5625 buah/m².

## Pengujian

```
pip install -r requirements-dev.txt
python -m pytest
```

| Berkas | Isi |
|---|---|
| `tests/test_kf1_validasi.py` | file valid IFC2x3/IFC4, ekstensi salah, file tidak ada, file kosong, header bukan STEP, file terpotong, file korup yang membuat IfcOpenShell crash, skema IFC4X3, tanpa IfcProject |
| `tests/test_kf2_ekstraksi.py` | tanpa duplikat, dimensi dari Qto, luas bukaan = luas pintu + jendela, atap 30° (82,56 m², bukan proyeksi 71,50 m²), lantai & elevasi, konversi mm, keliling tidak wajar, dinding sumbu Y tanpa Qto (geometri), atap miring tanpa Qto |
| `tests/test_kf3_kf4_rules.py` | rumus setiap aturan, syarat fondasi turunan, dak vs atap miring, ruang basah, prioritas sumber lantai/plafon, tidak ada hitung ganda |
| `tests/test_pipeline.py` | IFC → database, estimasi ulang tidak menggandakan data, migrasi database lama, file proyek hilang |
