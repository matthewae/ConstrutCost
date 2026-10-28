@echo off
rem Build CostStruct.exe di Windows (KNF-8). Jalankan dari folder mana saja.
cd /d "%~dp0\.."
python -m pip install -r requirements.txt || goto :gagal
python tools\build_exe.py %* || goto :gagal
echo.
echo Selesai. Aplikasi: dist\CostStruct\CostStruct.exe
pause
exit /b 0
:gagal
echo.
echo Build atau uji mandiri GAGAL. Periksa pesan di atas.
pause
exit /b 1
