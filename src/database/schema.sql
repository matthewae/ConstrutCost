-- pekerjaan: master daftar item pekerjaan (mis. "Pasangan Dinding Bata Merah")
CREATE TABLE IF NOT EXISTS pekerjaan (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    kode_ahsp TEXT UNIQUE,
    nama_pekerjaan TEXT NOT NULL,
    kategori TEXT NOT NULL,        -- 'Beton','Dinding','Atap','Fondasi','Plafon','Cat', dst.
    satuan TEXT NOT NULL,          -- 'm3','m2','kg','unit'
    catatan TEXT
);

-- komponen_harga: rincian bahan/upah/alat per pekerjaan, sesuai struktur AHSP/SNI
CREATE TABLE IF NOT EXISTS komponen_harga (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pekerjaan_id INTEGER NOT NULL REFERENCES pekerjaan(id),
    tipe TEXT NOT NULL CHECK (tipe IN ('bahan', 'upah', 'alat')),
    nama_komponen TEXT NOT NULL,   -- 'Semen PC 50kg', 'Tukang Batu', 'Molen'
    satuan TEXT NOT NULL,
    koefisien REAL NOT NULL,       -- indeks dari AHSP/SNI
    harga_satuan REAL NOT NULL,    -- bisa diedit user (KF-5)
    diubah_manual INTEGER DEFAULT 0
);

-- proyek: setiap proyek yang dibuat/dibuka user (KF-7, KF-9)
CREATE TABLE IF NOT EXISTS proyek (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nama_proyek TEXT NOT NULL,
    path_file_ifc TEXT,
    tanggal_dibuat TEXT DEFAULT CURRENT_TIMESTAMP,
    tanggal_diubah TEXT DEFAULT CURRENT_TIMESTAMP
);

-- elemen_proyek: hasil ekstraksi IFC per proyek (output dari ifc_reader.py)
CREATE TABLE IF NOT EXISTS elemen_proyek (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    proyek_id INTEGER NOT NULL REFERENCES proyek(id),
    global_id TEXT NOT NULL,
    ifc_type TEXT NOT NULL,
    predefined_type TEXT,          -- FLOOR/ROOF dst. -- kunci routing rule
    nama TEXT,
    lantai TEXT,                   -- untuk KF-12 multi-lantai
    panjang REAL,
    luas REAL,
    volume REAL,
    sumber_volume TEXT,            -- 'qto', 'geometri', atau 'gagal'
    kelas TEXT,                    -- hasil klasifikasi KF-2 (COLUMN, BEAM, SLAB, ROOF, WALL, ...)
    lebar REAL,
    tinggi REAL,
    tebal REAL,
    keliling REAL,
    kemiringan REAL,               -- derajat, khusus atap
    luas_bukaan REAL,              -- luas pintu/jendela pada dinding (info Rumus 2.17)
    elevasi_lantai REAL,
    sumber_dimensi TEXT            -- JSON: asal tiap dimensi ('qto' / 'geometri' / 'atribut')
);

-- hasil_estimasi: output rule-engine, per elemen per pekerjaan
CREATE TABLE IF NOT EXISTS hasil_estimasi (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    proyek_id INTEGER NOT NULL REFERENCES proyek(id),
    elemen_id INTEGER REFERENCES elemen_proyek(id),
    pekerjaan_id INTEGER NOT NULL REFERENCES pekerjaan(id),
    volume_pekerjaan REAL NOT NULL,
    subtotal_biaya REAL NOT NULL,
    diedit_manual INTEGER DEFAULT 0,  -- untuk KF-6
    rumus TEXT                        -- uraian perhitungan rule (dasar KF-18)
);

-- preferensi_pengguna: KF-10 (tema, direktori default, format laporan)
CREATE TABLE IF NOT EXISTS preferensi_pengguna (
    kunci TEXT PRIMARY KEY,
    nilai TEXT
);