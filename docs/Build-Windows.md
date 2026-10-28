# Build CostStruct.exe di Windows (terminal Trae / VS Code / PowerShell)

Terminal bawaan Trae di Windows adalah PowerShell, jadi semua perintah di bawah bisa langsung diketik di sana
(**Terminal → New Terminal**, atau `` Ctrl+` ``). Folder proyek yang dibuka di Trae otomatis menjadi folder kerja
terminal.

## Sekali saja: siapkan Python dan virtual environment

1. Pasang **Python 3.13 64-bit** dari python.org dan centang *Add python.exe to PATH*. Periksa dengan:
   ```powershell
   python --version        # Python 3.13.x
   ```
2. Buat dan aktifkan virtual environment di folder proyek:
   ```powershell
   python -m venv venv
   .\venv\Scripts\Activate.ps1
   ```
   Bila muncul *"running scripts is disabled on this system"*, izinkan skrip untuk akun Anda (cukup sekali), lalu
   aktifkan lagi:
   ```powershell
   Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
   .\venv\Scripts\Activate.ps1
   ```
   Venv yang aktif ditandai `(venv)` di awal baris terminal.
3. Pasang paket:
   ```powershell
   python -m pip install -r requirements-dev.txt
   ```

Supaya Trae mengaktifkan venv otomatis di setiap terminal baru, pilih interpreter
**Ctrl+Shift+P → Python: Select Interpreter → .\venv\Scripts\python.exe**.

## Setiap kali build

```powershell
.\venv\Scripts\Activate.ps1          # bila (venv) belum tampil
git pull                              # ambil kode terbaru
python tools\build_exe.py             # build + uji mandiri hasil build
.\dist\CostStruct\CostStruct.exe      # jalankan aplikasi
```

Untuk satu file `.exe` (lebih lambat dibuka, mudah dibagikan), jalankan `python tools\build_exe.py --onefile`.
Hasilnya ada di `dist\CostStruct.exe`.

`tools\build_exe.py` menjalankan tiga langkah:
1. memeriksa lingkungan;
2. menjalankan PyInstaller (±2 menit);
3. menjalankan uji mandiri pada `.exe` yang baru dibuat.

Uji mandiri terdiri atas 6 tahap: database, validasi IFC, estimasi, export, file proyek, dan jendela aplikasi.
Laporannya ada di `build\uji_mandiri\uji_mandiri.txt`.

Folder `dist\CostStruct` berisi aplikasi lengkap. Seluruh folder bisa disalin atau di-zip ke komputer lain
tanpa memasang Python.

## Pesan yang mungkin muncul

| Pesan | Penyebab dan solusi |
|---|---|
| `Paket belum terpasang ... Virtual environment belum aktif` | Jalankan `.\venv\Scripts\Activate.ps1`, lalu `python -m pip install -r requirements.txt` |
| `Folder dist\CostStruct sedang dipakai` | Tutup `CostStruct.exe` yang masih terbuka, juga jendela File Explorer di folder itu, lalu ulangi |
| `Python ... 32-bit` | Pasang Python 3.13 **64-bit** |
| Windows SmartScreen: *Windows protected your PC* saat membuka `.exe` | `.exe` belum ditandatangani digital. Klik **More info → Run anyway** |
| Build sangat lambat atau `.exe` hilang setelah build | Antivirus memindai atau mengarantina hasil PyInstaller. Tambahkan folder proyek ke pengecualian Windows Security |

## Alternatif tanpa terminal

- **Klik dua kali** `tools\build_exe.bat`. Skrip ini memasang paket lalu mem-build dengan Python yang ada di PATH.
- **Unduh hasil build CI.** Setiap push ke PR otomatis di-build di Windows. Unduh dari GitHub
  **Actions → run terbaru → Artifacts → CostStruct-windows**.
