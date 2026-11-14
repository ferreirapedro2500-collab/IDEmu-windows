# Installe tout ce qu'il faut pour lancer IDEmu (iDrive 5/6) sous Windows et compile les binaires.
#   Python 3.12, Node.js LTS (fenêtre Electron), MSYS2 (compilateur), chemins longs,
#   paquets MSYS2, bin\glhost.exe, bin\qemu-system-arm.exe, electron\node_modules.
# Lancé par tools\windows\install.bat (en administrateur). Peut être relancé sans risque : ce qui est déjà fait est sauté.
$ErrorActionPreference = 'Stop'
$Root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$Log = Join-Path $Root 'install-windows.log'
Start-Transcript -Path $Log -Append | Out-Null
function Step($t) { Write-Host ''; Write-Host "=== $t ===" -ForegroundColor Cyan }
function Have($c) { [bool](Get-Command $c -ErrorAction SilentlyContinue) }
function RefreshPath { $env:Path = [Environment]::GetEnvironmentVariable('Path','Machine') + ';' + [Environment]::GetEnvironmentVariable('Path','User') }
function WingetInstall($id) {
  Write-Host "winget install $id"
  winget install -e --id $id --silent --accept-package-agreements --accept-source-agreements --disable-interactivity
  if ($LASTEXITCODE -ne 0 -and $LASTEXITCODE -ne -1978335189) { throw "winget a échoué pour $id (code $LASTEXITCODE)" }   # -1978335189 = déjà installé
  RefreshPath
}
try {
  if (-not (Have 'winget')) { throw "winget est introuvable : installe 'App Installer' depuis le Microsoft Store puis relance." }

  Step 'Python 3'
  $py = $false
  if (Have 'py') { & py -3 --version 2>$null; if ($LASTEXITCODE -eq 0) { $py = $true } }
  if (-not $py) { WingetInstall 'Python.Python.3.12' } else { Write-Host 'déjà installé' }

  Step 'Node.js (fenêtre Electron)'
  if (-not (Have 'npm')) { WingetInstall 'OpenJS.NodeJS.LTS' } else { Write-Host 'déjà installé' }

  Step 'MSYS2 (compilateur)'
  $Msys = 'C:\msys64'
  if (-not (Test-Path "$Msys\usr\bin\bash.exe")) { WingetInstall 'MSYS2.MSYS2' } else { Write-Host 'déjà installé' }
  if (-not (Test-Path "$Msys\usr\bin\bash.exe")) { throw "MSYS2 n'est pas dans C:\msys64" }

  Step 'Chemins longs (> 260 caractères)'
  New-ItemProperty -Path 'HKLM:\SYSTEM\CurrentControlSet\Control\FileSystem' -Name 'LongPathsEnabled' -Value 1 -PropertyType DWORD -Force | Out-Null
  Write-Host 'LongPathsEnabled = 1'

  $env:MSYSTEM = 'MINGW64'; $env:CHERE_INVOKING = '1'
  $Bash = "$Msys\usr\bin\bash.exe"
  function MBash($cmd) { & $Bash -lc $cmd; if ($LASTEXITCODE -ne 0) { throw "échec : $cmd" } }
  $RootU = (& $Bash -lc "cygpath -u '$Root'").Trim()

  Step 'Paquets MSYS2 (peut prendre 10 minutes)'
  & $Bash -lc 'pacman -Syu --noconfirm' ; & $Bash -lc 'pacman -Syu --noconfirm'     # la 1re mise à jour redémarre le noyau MSYS2
  MBash 'pacman -S --needed --noconfirm base-devel git python ninja patch mingw-w64-x86_64-toolchain mingw-w64-x86_64-glib2 mingw-w64-x86_64-pixman mingw-w64-x86_64-meson mingw-w64-x86_64-pkgconf mingw-w64-x86_64-python mingw-w64-x86_64-python-setuptools mingw-w64-x86_64-freeglut mingw-w64-x86_64-glew'

  Remove-Item -Force -ErrorAction SilentlyContinue (Join-Path $Root 'bin\ucrtbase.dll')   # copiée par erreur par une version précédente du script
  Step 'Moteur d''affichage (bin\glhost.exe)'
  MBash "cd '$RootU' && bash src/glhost/build_windows.sh"

  Step 'QEMU ARM avec la carte OMAP5 (bin\qemu-system-arm.exe, 20 à 40 minutes)'
  if (Test-Path (Join-Path $Root 'bin\qemu-system-arm.exe')) { Write-Host 'déjà compilé' } else {
    $Cache = Join-Path $Root 'cache'; New-Item -ItemType Directory -Force $Cache | Out-Null
    $Tar = Join-Path $Cache 'qemu-11.1.2.tar.xz'
    if (-not (Test-Path $Tar)) { & curl.exe -L --fail -o $Tar 'https://download.qemu.org/qemu-11.1.2.tar.xz'; if ($LASTEXITCODE -ne 0) { throw 'téléchargement de QEMU impossible' } }
    $TarU = (& $Bash -lc "cygpath -u '$Tar'").Trim()
    MBash "cd '$RootU' && bash tools/qemu/build_windows_arm.sh '$TarU'"
  }

  Step 'Fenêtre Electron (npm install)'
  RefreshPath
  Push-Location (Join-Path $Root 'electron')
  & npm.cmd install --no-fund --no-audit; $rc = $LASTEXITCODE
  Pop-Location
  if ($rc -ne 0) { throw 'npm install a échoué' }

  Step 'Terminé'
  Write-Host "Tout est installé. Lance IDEmu avec IDEmu.bat (double-clic), sans les droits administrateur." -ForegroundColor Green
} catch {
  Write-Host ''; Write-Host "ERREUR : $($_.Exception.Message)" -ForegroundColor Red
  Write-Host "Journal : $Log"
} finally {
  Stop-Transcript | Out-Null
  Read-Host 'Appuie sur Entrée pour fermer'
}
