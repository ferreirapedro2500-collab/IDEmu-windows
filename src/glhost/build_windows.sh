#!/usr/bin/env bash
# Compila o renderizador do host para Windows (bin/glhost.exe).
# Rode no terminal "MSYS2 MINGW64" (ou UCRT64) depois de instalar:
#   pacman -S --needed mingw-w64-x86_64-gcc mingw-w64-x86_64-freeglut mingw-w64-x86_64-glew
#   (UCRT64: troque x86_64 por ucrt-x86_64)
# As DLLs (freeglut, glew32, libgcc) são copiadas para bin/ junto com o executável.
set -e
cd "$(dirname "$0")"
cp ../shim/glops.h ../shim/gen_host.inc ../shim/opnames.inc ../shim/gl_hand_names.inc . 2>/dev/null || true
mkdir -p ../../bin
CC=${CC:-gcc}
$CC -O2 -w -std=gnu11 host.c pngload.c -o ../../bin/glhost.exe \
    -lfreeglut -lglew32 -lopengl32 -lglu32 -lws2_32 -lole32 -lwindowscodecs -luuid -lgdi32 -lwinmm
# DLLs de que o glhost.exe depende (as do MSYS2, não as do Windows)
for d in $(ldd ../../bin/glhost.exe | awk '$3 ~ /^\/(mingw64|ucrt64|clang64)\// {print $3}'); do cp -u "$d" ../../bin/; done
ls -l ../../bin/glhost.exe
