@echo off
rem Abre o IDEmu (Windows): janela do Electron se instalada; senao, servidor Python + navegador (Edge em modo app).
rem Versao instalada (IDEmu-Setup.exe): usa o Python embutido em python\.
cd /d "%~dp0"
if exist "python\python.exe" set "IDEMU_PYTHON=%~dp0python\python.exe"
if exist "electron\node_modules\.bin\electron.cmd" (
  start "" "electron\node_modules\.bin\electron.cmd" electron
  exit /b 0
)
if defined IDEMU_PYTHON (
  "%IDEMU_PYTHON%" -m idemu gui
  exit /b %errorlevel%
)
echo Electron nao instalado (rode: cd electron ^&^& npm install). Abrindo no navegador.
where py >nul 2>nul && (py -3 -m idemu gui & exit /b %errorlevel%)
python -m idemu gui
