#!/usr/bin/env bash
# Compila o QEMU ARM do IDEmu para Windows (iDrive 5/6): QEMU 11.1.2 oficial + placa omap5-uevm (src/qemu).
# Resultado: bin/qemu-system-arm.exe e as DLLs de que ele depende.
#
# Rode no terminal "MSYS2 MINGW64". Pacotes (uma vez):
#   pacman -S --needed base-devel git python ninja patch \
#       mingw-w64-x86_64-toolchain mingw-w64-x86_64-glib2 mingw-w64-x86_64-pixman \
#       mingw-w64-x86_64-meson mingw-w64-x86_64-pkgconf mingw-w64-x86_64-python mingw-w64-x86_64-python-setuptools
# Uso: tools/qemu/build_windows_arm.sh <qemu-11.1.2.tar.xz>   (o tarball oficial vem de https://download.qemu.org; o script não baixa nada)
set -e
TAR=${1:?uso: build_windows_arm.sh <qemu-11.1.2.tar.xz>}
TAR=$(cd "$(dirname "$TAR")" && pwd)/$(basename "$TAR")
HERE=$(cd "$(dirname "$0")" && pwd); ROOT=$(cd "$HERE/../.." && pwd)
W=${QEMU_BUILD_DIR:-$HOME/idemu-qemu-arm}
mkdir -p "$W" && cd "$W"
# l'archive contient des liens symboliques (roms/, tests/) que Windows ne crée pas sans droits : ils ne servent pas à la compilation
if [ ! -f qemu-11.1.2/configure ]; then
  tar xf "$TAR" --exclude='qemu-11.1.2/roms/*' --exclude='qemu-11.1.2/tests/lcitool/*' || true
fi
[ -f qemu-11.1.2/configure ] && [ -f qemu-11.1.2/hw/arm/Kconfig ] || { echo "extraction de QEMU incomplète"; exit 1; }
SRC=$W/qemu-11.1.2
cp "$ROOT/src/qemu/omap5-uevm.c" "$SRC/hw/arm/omap5-uevm.c"
grep -q OMAP5_UEVM "$SRC/hw/arm/Kconfig" || (cd "$SRC" && patch -p1 < "$ROOT/src/qemu/qemu-v11.1.2-idemu.patch")
mkdir -p "$W/build-arm" && cd "$W/build-arm"
[ -f build.ninja ] || "$SRC/configure" --target-list=arm-softmmu --disable-docs --disable-guest-agent --disable-tools \
    --disable-gtk --disable-sdl --disable-vnc --disable-curses --disable-rust --disable-user \
    --without-default-features --enable-tcg
ninja qemu-system-arm.exe
mkdir -p "$ROOT/bin"
cp qemu-system-arm.exe "$ROOT/bin/"
for d in $(ldd qemu-system-arm.exe | awk '$3 ~ /^\/(mingw64|ucrt64|clang64)\// {print $3}'); do cp -u "$d" "$ROOT/bin/"; done
"$ROOT/bin/qemu-system-arm.exe" -machine help | grep -q omap5-uevm && echo "ok: bin/qemu-system-arm.exe com a placa omap5-uevm"
