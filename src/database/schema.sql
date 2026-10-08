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
    dimensi_manual INTEGER DEFAULT 0, -- KF-19: dimensi diubah pengguna lalu QTO dihitung ulang
    tipe_id INTEGER                -- tipe_penulangan.id (kolom/balok/sloof/pelat/dak/fondasi)
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
    rumus TEXT,                       -- uraian perhitungan rule (dasar KF-18)
    uraian TEXT,                      -- rincian item, mis. 'Tulangan utama 6 D13'
    diameter REAL,                    -- mm, khusus pembesian
    harga_manual REAL,                -- KF-6: harga satuan khusus baris ini (NULL = harga master)
    catatan TEXT                      -- KF-6: catatan pengguna
);

-- tipe_penulangan: konfigurasi tulangan per tipe elemen dalam satu proyek (K1 20/25, P1 t=12, ...)
CREATE TABLE IF NOT EXISTS tipe_penulangan (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    proyek_id INTEGER NOT NULL,
    kelompok TEXT NOT NULL,        -- KOLOM, BALOK, SLOOF, PELAT, DAK, FONDASI
    kode TEXT NOT NULL,            -- K1, B1, S1, P1, D1, F1
    b_cm INTEGER NOT NULL,         -- lebar penampang (0 untuk pelat/dak/fondasi)
    h_cm INTEGER NOT NULL,         -- tinggi penampang / tebal
    n_utama INTEGER,
    d_utama REAL,                  -- mm
    jarak_utama REAL,              -- m (pelat/dak/fondasi)
    lapis INTEGER,
    d_sengkang REAL,               -- mm
    jarak_sengkang REAL,           -- m
    selimut REAL,                  -- m
    diubah INTEGER DEFAULT 0,      -- 1 = konfigurasi diubah pengguna (dipertahankan saat estimasi ulang)
    UNIQUE (proyek_id, kelompok, b_cm, h_cm)
);

-- biaya_tidak_langsung: KF-13, diisi pengguna (perencanaan, pengawasan, SMKK, perizinan, ...)
CREATE TABLE IF NOT EXISTS biaya_tidak_langsung (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    proyek_id INTEGER NOT NULL,
    uraian TEXT NOT NULL,
    jenis TEXT NOT NULL,           -- 'persen' (dari biaya langsung) atau 'nilai' (Rp)
    nilai REAL NOT NULL,
    urutan INTEGER DEFAULT 0
);

-- preferensi_pengguna: KF-10 (tema, direktori default, format laporan)
CREATE TABLE IF NOT EXISTS preferensi_pengguna (
    kunci TEXT PRIMARY KEY,
    nilai TEXT
);