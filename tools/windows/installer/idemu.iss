; Instalador do IDEmu para Windows (iDrive 5/6). Compilado pelo GitHub Actions (.github/workflows/windows-release.yml):
;   iscc /DAppVersion=1.2.3 /DSrc=<pasta preparada> tools\windows\installer\idemu.iss
; A pasta preparada contém o projeto, bin\ (glhost.exe, qemu-system-arm.exe e DLLs) e python\ (Python embutido).
; Nada da BMW vai no instalador: PSdZData, firmware e shaders decompilados são do usuário.
#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif
#ifndef Src
  #define Src "..\..\..\dist\IDEmu"
#endif

[Setup]
AppId={{6E2B4D2A-6C1F-4F0E-9B7A-1D3C5E8F2A41}
AppName=IDEmu
AppVersion={#AppVersion}
AppPublisher=IDEmu (fork Windows)
AppPublisherURL=https://github.com/herrbimmer/IDEmu
DefaultDirName=C:\IDEmu
DisableDirPage=no
DefaultGroupName=IDEmu
OutputBaseFilename=IDEmu-Setup-{#AppVersion}
Compression=lzma2/max
SolidCompression=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=admin
WizardStyle=modern
LicenseFile={#Src}\LICENSE
InfoBeforeFile={#Src}\tools\windows\installer\LEIA-ME.txt
UninstallDisplayName=IDEmu (emulador BMW iDrive)
SetupLogging=yes

[Languages]
Name: "fr"; MessagesFile: "compiler:Languages\French.isl"
Name: "pt"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"
Name: "en"; MessagesFile: "compiler:Default.isl"

[Dirs]
; os ambientes, o settings.json e os logs ficam na pasta do programa: o usuário comum precisa poder gravar nela
Name: "{app}"; Permissions: users-modify
Name: "{app}\environments"; Permissions: users-modify

[Files]
Source: "{#Src}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs; Excludes: "\.git\*,\.github\*,\environments\*,\cache\*,\settings.json,\install-windows.log,\electron\node_modules\*,__pycache__\*,*.pyc"

[Registry]
; caminhos do QNX extraídos dos pacotes passam de 260 caracteres
Root: HKLM; Subkey: "SYSTEM\CurrentControlSet\Control\FileSystem"; ValueType: dword; ValueName: "LongPathsEnabled"; ValueData: "1"

[Icons]
Name: "{group}\IDEmu"; Filename: "{app}\IDEmu.bat"; WorkingDir: "{app}"; Flags: runminimized
Name: "{group}\Pasta do IDEmu"; Filename: "{app}"
Name: "{group}\Desinstalar o IDEmu"; Filename: "{uninstallexe}"
Name: "{autodesktop}\IDEmu"; Filename: "{app}\IDEmu.bat"; WorkingDir: "{app}"; Flags: runminimized; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Run]
Filename: "{app}\IDEmu.bat"; WorkingDir: "{app}"; Description: "{cm:LaunchProgram,IDEmu}"; Flags: postinstall nowait skipifsilent runasoriginaluser runminimized

[UninstallDelete]
Type: filesandordirs; Name: "{app}\idemu\__pycache__"
