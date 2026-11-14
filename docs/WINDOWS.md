# IDEmu on Windows (iDrive 5/6)

Status: **port in progress**. The Python server, the web interface, the Electron window, the iDrive 5/6 image builder, the
renderer (`glhost`) and the OMAP5 QEMU board have Windows code paths. iDrive 4 (CIC), iDrive 7 and iDrive 8 still need their own
host renderers and QEMU devices ported (`glhost7`, `mguhost`, `idemu-shm`, the SH7785 board); on Windows they stop with a clear message.

## What changes on Windows

| macOS | Windows | Where |
|---|---|---|
| Unix sockets `<run>/*.sock` between the server, QEMU and `glhost` | Loopback TCP (streams) and UDP (input/map) ports. The `.sock` path becomes a text file holding the port; whoever listens writes it | `idemu/plat.py`, `src/glhost/compat.h`, `src/qemu/omap5-uevm.c` |
| QEMU `-serial unix:` / `-qmp unix:` | `tcp:127.0.0.1:<port>,server=on,wait=off,nodelay=on` (port reserved by the server) | `plat.qemu_server()` |
| GLUT + OpenGL frameworks, CGL | freeglut + GLEW, WGL (shared context for the map via `wglShareLists`) | `src/glhost/compat.h` |
| `mmap` of `frame.rgb` | `CreateFileMapping`/`MapViewOfFile` (same file, same header) | `compat.h: frame_map()` |
| ImageIO (map tiles) | WIC | `src/glhost/pngload.c` |
| `sshd` without root + `sshshell.py` | **Telnet/raw console** on the SSH port (127.0.0.1 only, no encryption): PuTTY *Raw*/*Telnet*, `ncat` or `telnet` | `sshbridge.ConsoleBridge` |
| `ps`, `sysctl`, `ioreg` (statistics) | `GetProcessTimes`, `GetProcessMemoryInfo`, `GlobalMemoryStatusEx` (no GPU load) | `plat.proc_info()`, `stats.py` |
| `osascript` file picker, `open` | tkinter picker (the Electron window keeps its own native dialog), Explorer | `plat.pick_dialog()`, `plat.open_path()` |
| Symlinks to SWFL packages and environment folders | symlink → hard link → copy; NTFS junction for folders | `plat.link_file()`, `plat.link_dir()` |
| SIGTERM/SIGHUP cleanup | Job Object (`KILL_ON_JOB_CLOSE`): QEMU and `glhost` die with the server; Electron closes the server's stdin to stop it cleanly | `plat.kill_children_on_exit()`, `electron/main.js` |
| Execute bit on extracted files | Decided by content (ELF or `#!`), NTFS has no execute bit | `qnxfs/mkq6.py` |

## Requirements

* Windows 10 1809+ or Windows 11, x64. A GPU driver with OpenGL 2.1 or later (any current NVIDIA/AMD/Intel driver).
* Python 3.10+ from python.org (tick "Add python.exe to PATH"; the `py` launcher is used if present). tkinter is included.
* Long paths: run `tools\windows\enable-long-paths.ps1` once as administrator (QNX paths extracted from the SWFL packages
  can exceed 260 characters), or keep the project in a short folder such as `C:\idemu`.
* If your Windows user name has accents or other non-ASCII characters, set `IDEMU_RUN_ROOT=C:\idemu-run` (renderer and QEMU use ANSI paths).
* To build the binaries: [MSYS2](https://www.msys2.org) (MINGW64 terminal).
* Optional: Node.js for the Electron window (`cd electron && npm install`).
* As on macOS: your own PSdZData/SWFL files. The HMI ships its shaders as source, so no shader dump is needed (verified on an Intel UHD 620 laptop: first boot ~2 min, then fast boot).

## Build the binaries (MSYS2 MINGW64 terminal)

```bash
pacman -S --needed base-devel git python ninja patch mingw-w64-x86_64-toolchain mingw-w64-x86_64-glib2 \
    mingw-w64-x86_64-pixman mingw-w64-x86_64-meson mingw-w64-x86_64-pkgconf mingw-w64-x86_64-python \
    mingw-w64-x86_64-python-setuptools mingw-w64-x86_64-freeglut mingw-w64-x86_64-glew
src/glhost/build_windows.sh                              # -> bin/glhost.exe (+ DLLs)
tools/qemu/build_windows_arm.sh /path/qemu-11.1.2.tar.xz # -> bin/qemu-system-arm.exe (+ DLLs), board omap5-uevm
```

The guest-side libraries (`idemu/shim/lib`) are already built and are the same on every host.

## Installer for GitHub (IDEmu-Setup.exe)

`.github/workflows/windows-release.yml` builds `glhost.exe` and `qemu-system-arm.exe` on a GitHub Windows runner, adds an embedded
Python and packages everything with Inno Setup (`tools/windows/installer/idemu.iss`):

* push a tag (`git tag v0.2.0 && git push --tags`): the installer is attached to the GitHub release;
* or run the workflow by hand (Actions → "Windows installer" → Run workflow): the `.exe` is a downloadable artifact.

The installer goes to `C:\IDEmu` (writable by normal users), enables long paths and adds Start menu / desktop shortcuts. It contains
**no BMW files**; each user brings their own PSdZData. QEMU is GPL-2.0-or-later: its source is the official
tarball plus `src/qemu` of the same tag (see `tools/windows/installer/TERCEIROS.txt`). The embedded Python has no tkinter, so the
"choose folder" dialog uses the in-app folder browser.

## Run

```bat
IDEmu.bat                 :: Electron window (falls back to the browser)
py -3 -m idemu gui        :: web interface at http://127.0.0.1:8765
```

## Known limits

* Tested on one Windows laptop (Intel UHD 620): boot to the HMI works; other machines may still need fixes (logs: `<environment>\logs\renderer.log`, `qemu.log`).
* The GL bridge goes over loopback TCP instead of a Unix socket: each GL request is a round trip, so drawing may be slower than on macOS.
* No real SSH: the console port speaks raw/telnet. `ssh host command`, `idemu push/pull` over SSH are not available.
* Names that NTFS rejects (`aux.c`, `a:b`, names that only differ in case) are skipped when extracting packages, with a warning in the build log.
* iDrive 4, 7 and 8: not ported (see above).
