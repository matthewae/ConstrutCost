; Installer Windows CostStruct (Inno Setup 6).
;
; Dibangun dari folder hasil PyInstaller (dist\CostStruct) dengan:
;     python tools\build_installer.py            (mencari ISCC.exe, membaca versi, lalu menguji installer)
; atau langsung:
;     "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" /DVersiApp=1.4.0 installer\CostStruct.iss
; Hasil: dist\installer\CostStruct-Setup-<versi>.exe
;
; Data pengguna (database, log, cadangan) ada di %APPDATA%\CostStruct dan TIDAK dihapus saat aplikasi dicopot,
; sehingga proyek dan harga satuan tetap ada bila aplikasi dipasang ulang atau diperbarui.

#define NamaApp "CostStruct"
#ifndef VersiApp
  #define VersiApp "1.4.0"
#endif
#define ExeApp "CostStruct.exe"

[Setup]
; AppId tetap: versi baru memperbarui instalasi lama, bukan dipasang berdampingan
AppId={{7C756491-F728-4E18-A102-F4EA87F33597}
AppName={#NamaApp}
AppVersion={#VersiApp}
AppVerName={#NamaApp} {#VersiApp}
AppPublisher={#NamaApp}
AppComments=Estimasi QTO dan RAB dari model IFC (HSPK Kota Bandung 2027)
VersionInfoVersion={#VersiApp}
VersionInfoDescription=Installer {#NamaApp}
DefaultDirName={autopf}\{#NamaApp}
DefaultGroupName={#NamaApp}
DisableProgramGroupPage=yes
; tanpa hak administrator: dipasang untuk pengguna ini (%LOCALAPPDATA%\Programs); dialog menawarkan semua pengguna
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=commandline dialog
ArchitecturesAllowed=x64
ArchitecturesInstallIn64BitMode=x64
MinVersion=10.0
OutputDir=..\dist\installer
OutputBaseFilename=CostStruct-Setup-{#VersiApp}
SetupIconFile=..\assets\coststruct.ico
UninstallDisplayIcon={app}\{#ExeApp}
UninstallDisplayName={#NamaApp} {#VersiApp}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ShowLanguageDialog=no
ChangesAssociations=yes
CloseApplications=yes

[Languages]
; pesan bawaan Inno Setup (Inggris) ditimpa terjemahan bahasa Indonesia di Indonesian.isl
Name: "id"; MessagesFile: "compiler:Default.isl,Indonesian.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"
Name: "asosiasi"; Description: "{cm:AsosiasiProyek}"; GroupDescription: "{cm:AsosiasiFile}"
Name: "bukaifc"; Description: "{cm:AsosiasiIFC}"; GroupDescription: "{cm:AsosiasiFile}"

[Files]
Source: "..\dist\CostStruct\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#NamaApp}"; Filename: "{app}\{#ExeApp}"; Comment: "{cm:KomentarShortcut}"
Name: "{autodesktop}\{#NamaApp}"; Filename: "{app}\{#ExeApp}"; Comment: "{cm:KomentarShortcut}"; Tasks: desktopicon

[Registry]
; File proyek .coststruct dibuka dengan CostStruct (klik dua kali di Explorer)
Root: HKA; Subkey: "Software\Classes\.coststruct"; ValueType: string; ValueName: ""; ValueData: "CostStruct.Proyek"; Flags: uninsdeletevalue; Tasks: asosiasi
Root: HKA; Subkey: "Software\Classes\CostStruct.Proyek"; ValueType: string; ValueName: ""; ValueData: "{cm:JenisFileProyek}"; Flags: uninsdeletekey; Tasks: asosiasi
Root: HKA; Subkey: "Software\Classes\CostStruct.Proyek\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: "{app}\{#ExeApp},0"; Tasks: asosiasi
Root: HKA; Subkey: "Software\Classes\CostStruct.Proyek\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#ExeApp}"" ""%1"""; Tasks: asosiasi
; File .ifc: hanya ditambahkan ke daftar "Buka dengan" (aplikasi bawaan .ifc tidak diganti)
Root: HKA; Subkey: "Software\Classes\.ifc\OpenWithProgids"; ValueType: string; ValueName: "CostStruct.IFC"; ValueData: ""; Flags: uninsdeletevalue; Tasks: bukaifc
Root: HKA; Subkey: "Software\Classes\CostStruct.IFC"; ValueType: string; ValueName: ""; ValueData: "{cm:JenisFileIFC}"; Flags: uninsdeletekey; Tasks: bukaifc
Root: HKA; Subkey: "Software\Classes\CostStruct.IFC\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: "{app}\{#ExeApp},0"; Tasks: bukaifc
Root: HKA; Subkey: "Software\Classes\CostStruct.IFC\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#ExeApp}"" ""%1"""; Tasks: bukaifc

[Run]
Filename: "{app}\{#ExeApp}"; Description: "{cm:LaunchProgram,{#NamaApp}}"; Flags: nowait postinstall skipifsilent
