-- pekerjaan: master daftar item pekerjaan (mis. "Pasangan Dinding Bata Merah")
CREATE TABLE IF NOT EXISTS pekerjaan (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    kode_ahsp TEXT UNIQUE,
    nama_pekerjaan TEXT NOT NULL,
    kategori TEXT NOT NULL,        -- 'Beton','Dinding','Atap','Fondasi','Plafon','Cat', dst.
    satuan TEXT NOT NULL,          -- 'm3','m2','kg','unit'
    catatan TEXT
);

-- sumber_daya: daftar harga satuan dasar bahan / upah / alat (KF-5).
-- Satu baris dipakai bersama oleh semua analisa pekerjaan, jadi harga semen cukup diubah sekali.
CREATE TABLE IF NOT EXISTS sumber_daya (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tipe TEXT NOT NULL CHECK (tipe IN ('bahan', 'upah', 'alat')),
    nama TEXT NOT NULL,
    satuan TEXT NOT NULL,
    harga REAL NOT NULL CHECK (harga >= 0),
    harga_bawaan REAL,             -- harga dari seed; NULL untuk sumber daya tambahan pengguna
    merk TEXT,
    sumber TEXT,                   -- 'HSPK Kota Bandung 2027', 'Placeholder', 'Pengguna'
    diubah_manual INTEGER DEFAULT 0,
    tanggal_diubah TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (tipe, nama, satuan)
);

-- riwayat_harga: jejak setiap perubahan harga / merk dasar
CREATE TABLE IF NOT EXISTS riwayat_harga (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sumber_daya_id INTEGER NOT NULL REFERENCES sumber_daya(id),
    harga_lama REAL,
    harga_baru REAL,
    merk_lama TEXT,
    merk_baru TEXT,
    waktu TEXT DEFAULT CURRENT_TIMESTAMP
);

-- komponen_harga: rincian bahan/upah/alat per pekerjaan, sesuai struktur AHSP/SNI
CREATE TABLE IF NOT EXISTS komponen_harga (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pekerjaan_id INTEGER NOT NULL REFERENCES pekerjaan(id),
    tipe TEXT NOT NULL CHECK (tipe IN ('bahan', 'upah', 'alat')),
    nama_komponen TEXT NOT NULL,   -- 'Semen PC 50kg', 'Tukang Batu', 'Molen'
    satuan TEXT NOT NULL,
    koefisien REAL NOT NULL,       -- indeks dari AHSP/SNI
    harga_satuan REAL NOT NULL,    -- salinan sumber_daya.harga, disinkronkan saat harga diubah
    diubah_manual INTEGER DEFAULT 0,  -- 1 = komponen tambahan pengguna (tidak ditimpa seed)
    sumber_daya_id INTEGER REFERENCES sumber_daya(id)
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
    sumber_dimensi TEXT,           -- JSON: asal tiap dimensi ('qto' / 'geometri' / 'atribut' / 'manual')
    dimensi_manual INTEGER DEFAULT 0  -- KF-19: dimensi diubah pengguna lalu QTO dihitung ulang
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