"""plat – o que muda entre macOS/Linux e Windows (IPC local, pastas temporárias, processos, diálogos).

Regra de IPC: o IDEmu nomeia cada canal local por um caminho `<run>/<nome>.sock`.
  * macOS/Linux: o caminho é um socket unix (AF_UNIX), como sempre foi.
  * Windows: o caminho é um arquivo de texto com a porta TCP (canais stream) ou UDP (canais de datagrama) em 127.0.0.1.
    Quem escuta grava o arquivo depois de abrir a porta (o arquivo existir = canal pronto, como o socket unix).
    Para os canais que o QEMU serve (seriais, QMP), o IDEmu reserva a porta antes e grava o arquivo ao montar a linha de comando.
O glhost e o QEMU do IDEmu seguem a mesma regra (src/glhost/host.c, src/qemu/omap5-uevm.c).
"""
import os, sys, socket, subprocess, tempfile, time

WINDOWS = os.name == 'nt'
MACOS = sys.platform == 'darwin'
EXE = '.exe' if WINDOWS else ''


def exe(path):
    """Caminho de um executável do IDEmu (bin/glhost -> bin/glhost.exe no Windows)."""
    return path + EXE if WINDOWS and not path.lower().endswith('.exe') else path


def user_tag():
    if hasattr(os, 'getuid'): return str(os.getuid())
    return ''.join(c for c in (os.environ.get('USERNAME') or 'user') if c.isalnum()) or 'user'


def run_root():
    """Pasta dos temporários de execução (/tmp/idemu-<uid> no macOS/Linux, %TEMP%\\idemu-<usuário> no Windows)."""
    if os.environ.get('IDEMU_RUN_ROOT'): return os.environ['IDEMU_RUN_ROOT']      # Windows com acentos no nome do usuário: glhost/QEMU usam caminhos ANSI
    base = '/tmp' if not WINDOWS else tempfile.gettempdir()
    return os.path.join(base, 'idemu-%s' % user_tag())


# ---------------------------------------------------------------- portas (Windows)
def _write_port(path, port):
    tmp = path + '.tmp'
    with open(tmp, 'w') as f: f.write('%d\n' % port)
    os.replace(tmp, path)


def read_port(path):
    with open(path) as f: return int(f.read().strip())


def free_port(kind=socket.SOCK_STREAM):
    s = socket.socket(socket.AF_INET, kind)
    try:
        s.bind(('127.0.0.1', 0)); return s.getsockname()[1]
    finally:
        s.close()


def _remove(path):
    try: os.unlink(path)
    except OSError: pass


# ---------------------------------------------------------------- stream
def listen(path, backlog=8):
    """Socket de escuta para o canal `path`."""
    _remove(path)
    if not WINDOWS:
        s = socket.socket(socket.AF_UNIX); s.bind(path); s.listen(backlog); return s
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(('127.0.0.1', 0)); s.listen(backlog)
    _write_port(path, s.getsockname()[1])
    return s


def try_connect(path):
    """Uma tentativa de conexão; levanta OSError se o canal ainda não existe."""
    if not WINDOWS:
        s = socket.socket(socket.AF_UNIX)
        try: s.connect(path)
        except OSError: s.close(); raise
        return s
    try: port = read_port(path)
    except (OSError, ValueError) as e: raise OSError('canal %s ainda não publicado: %s' % (path, e))
    s = socket.create_connection(('127.0.0.1', port), timeout=5)
    s.settimeout(None)
    try: s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    except OSError: pass
    return s


def connect(path, timeout=30, alive=None):
    """Conecta ao canal, tentando de novo até `timeout` (o outro lado pode ainda estar subindo)."""
    end = time.time() + timeout
    while time.time() < end and (alive is None or alive()):
        try: return try_connect(path)
        except OSError: time.sleep(0.2)
    raise RuntimeError('não conectou em ' + path)


def exists(path):
    return os.path.exists(path)


# ---------------------------------------------------------------- datagramas
def dgram_server(path):
    _remove(path)
    if not WINDOWS:
        s = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM); s.bind(path); return s
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.bind(('127.0.0.1', 0))
    _write_port(path, s.getsockname()[1])
    return s


def dgram_client():
    return socket.socket(socket.AF_INET if WINDOWS else socket.AF_UNIX, socket.SOCK_DGRAM)


def dgram_send(sock, data, path):
    if not WINDOWS: return sock.sendto(data, path)
    try: port = read_port(path)
    except (OSError, ValueError) as e: raise OSError('canal %s indisponível: %s' % (path, e))
    return sock.sendto(data, ('127.0.0.1', port))


# ---------------------------------------------------------------- QEMU
def qemu_server(path):
    """Endereço de chardev/QMP em que o QEMU escuta: unix:<caminho> ou, no Windows, tcp:127.0.0.1:<porta reservada>."""
    if not WINDOWS: return 'unix:%s,server=on,wait=off' % path
    port = free_port(); _write_port(path, port)
    return 'tcp:127.0.0.1:%d,server=on,wait=off,nodelay=on' % port


def qemu_uri(path):
    """Mesmo endereço sem as opções de servidor (útil para file:/migração não; só para documentação e logs)."""
    return ('tcp:127.0.0.1:%d' % read_port(path)) if WINDOWS else 'unix:' + path


def file_uri(path):
    """Caminho para `-incoming file:` / `migrate file:` (o QEMU no Windows aceita barras normais)."""
    return 'file:' + (path.replace('\\', '/') if WINDOWS else path)


# ---------------------------------------------------------------- processos
def popen_group_kwargs():
    """Popen numa sessão/grupo próprio (Ctrl+C no terminal não derruba o filho antes da hora)."""
    if WINDOWS: return {'creationflags': getattr(subprocess, 'CREATE_NEW_PROCESS_GROUP', 0x200) | 0x08000000}   # CREATE_NO_WINDOW
    return {'start_new_session': True}


def no_window_kwargs():
    return {'creationflags': 0x08000000} if WINDOWS else {}


if WINDOWS:
    import ctypes
    from ctypes import wintypes

    class _FT(ctypes.Structure):
        _fields_ = [('lo', wintypes.DWORD), ('hi', wintypes.DWORD)]

    class _PMC(ctypes.Structure):
        _fields_ = [('cb', wintypes.DWORD), ('PageFaultCount', wintypes.DWORD), ('PeakWorkingSetSize', ctypes.c_size_t),
                    ('WorkingSetSize', ctypes.c_size_t), ('QuotaPeakPagedPoolUsage', ctypes.c_size_t), ('QuotaPagedPoolUsage', ctypes.c_size_t),
                    ('QuotaPeakNonPagedPoolUsage', ctypes.c_size_t), ('QuotaNonPagedPoolUsage', ctypes.c_size_t),
                    ('PagefileUsage', ctypes.c_size_t), ('PeakPagefileUsage', ctypes.c_size_t), ('PrivateUsage', ctypes.c_size_t)]

    class _MSX(ctypes.Structure):
        _fields_ = [('dwLength', wintypes.DWORD), ('dwMemoryLoad', wintypes.DWORD), ('ullTotalPhys', ctypes.c_uint64),
                    ('ullAvailPhys', ctypes.c_uint64), ('ullTotalPageFile', ctypes.c_uint64), ('ullAvailPageFile', ctypes.c_uint64),
                    ('ullTotalVirtual', ctypes.c_uint64), ('ullAvailVirtual', ctypes.c_uint64), ('ullAvailExtendedVirtual', ctypes.c_uint64)]

    _k32 = ctypes.WinDLL('kernel32', use_last_error=True)
    try: _psapi = ctypes.WinDLL('psapi')
    except OSError: _psapi = None


def proc_info(pid):
    """(segundos de CPU, RSS em KB, memória virtual/privada em KB) do processo, ou None."""
    if not pid: return None
    if not WINDOWS:
        try:
            o = subprocess.run(['ps', '-o', 'time=,rss=,vsz=', '-p', str(pid)], capture_output=True, text=True, timeout=3).stdout.split()
            t = 0.0
            for p in o[0].split(':'): t = t * 60 + float(p)
            return t, int(o[1]), int(o[2])
        except Exception: return None
    h = _k32.OpenProcess(0x1000 | 0x0010, False, int(pid))     # PROCESS_QUERY_LIMITED_INFORMATION | PROCESS_VM_READ
    if not h: return None
    try:
        c, e, k, u = _FT(), _FT(), _FT(), _FT()
        if not _k32.GetProcessTimes(h, ctypes.byref(c), ctypes.byref(e), ctypes.byref(k), ctypes.byref(u)): return None
        cpu = (((k.hi << 32) | k.lo) + ((u.hi << 32) | u.lo)) / 1e7
        rss = vsz = 0
        if _psapi is not None:
            m = _PMC(); m.cb = ctypes.sizeof(m)
            if _psapi.GetProcessMemoryInfo(h, ctypes.byref(m), m.cb): rss, vsz = m.WorkingSetSize // 1024, m.PrivateUsage // 1024
        return cpu, rss, vsz
    finally:
        _k32.CloseHandle(h)


def cpu_seconds(pid):
    i = proc_info(pid)
    return i[0] if i else None


def total_ram_bytes():
    if WINDOWS:
        m = _MSX(); m.dwLength = ctypes.sizeof(m)
        return m.ullTotalPhys if _k32.GlobalMemoryStatusEx(ctypes.byref(m)) else 0
    if MACOS:
        try: return int(subprocess.run(['sysctl', '-n', 'hw.memsize'], capture_output=True, text=True, timeout=3).stdout.strip() or 0)
        except Exception: return 0
    try: return os.sysconf('SC_PAGE_SIZE') * os.sysconf('SC_PHYS_PAGES')
    except (ValueError, OSError, AttributeError): return 0


# ---------------------------------------------------------------- travas de arquivo
class FileLock(object):
    """Trava não bloqueante de um arquivo (flock no POSIX, msvcrt.locking no Windows; no Windows a trava é sempre exclusiva)."""
    def __init__(self, path, shared=False):
        self.path, self.shared, self.fd = path, shared, None

    def try_acquire(self):
        fd = os.open(self.path, os.O_RDWR | os.O_CREAT, 0o600)
        try:
            if WINDOWS:
                import msvcrt
                if os.fstat(fd).st_size < 1: os.write(fd, b'\0')
                os.lseek(fd, 0, 0); msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(fd, (fcntl.LOCK_SH if self.shared else fcntl.LOCK_EX) | fcntl.LOCK_NB)
        except OSError:
            os.close(fd); return False
        self.fd = fd; return True

    def release(self):
        fd, self.fd = self.fd, None
        if fd is None: return
        try:
            if WINDOWS:
                import msvcrt
                os.lseek(fd, 0, 0); msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(fd, fcntl.LOCK_UN)
        except OSError: pass
        finally:
            os.close(fd)


# ---------------------------------------------------------------- área de trabalho
def open_path(path, reveal=False):
    """Abre uma pasta/arquivo no gerenciador de arquivos do sistema. Devolve (ok, erro)."""
    try:
        if WINDOWS:
            if reveal and os.path.isfile(path): subprocess.Popen(['explorer', '/select,', os.path.normpath(path)])
            else: os.startfile(os.path.normpath(path))
            return True, ''
        if MACOS: cmd = ['open', '-R', path] if reveal and os.path.isfile(path) else ['open', path]
        else: cmd = ['xdg-open', os.path.dirname(path) if reveal and os.path.isfile(path) else path]
        r = subprocess.run(cmd, capture_output=True, text=True)
        return r.returncode == 0, r.stderr.strip()
    except Exception as e:
        return False, str(e)


def open_url(url):
    if MACOS:
        for app in ('Google Chrome', 'Chromium', 'Microsoft Edge', 'Brave Browser'):
            if os.path.isdir('/Applications/%s.app' % app):
                subprocess.Popen(['open', '-na', app, '--args', '--app=' + url, '--window-size=1400,900']); return
        subprocess.Popen(['open', url]); return
    if WINDOWS:
        for p in (r'%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe', r'%ProgramFiles%\Microsoft\Edge\Application\msedge.exe',
                  r'%ProgramFiles%\Google\Chrome\Application\chrome.exe', r'%LocalAppData%\Google\Chrome\Application\chrome.exe'):
            p = os.path.expandvars(p)
            if os.path.isfile(p):
                subprocess.Popen([p, '--app=' + url, '--window-size=1400,900']); return
    import webbrowser
    webbrowser.open(url)


def pick_dialog(kind, prompt='', start=None):
    """Seletor nativo no Windows/Linux (tkinter, num processo separado para não prender a thread do servidor).
    Devolve o caminho (ou lista com kind='files'), None se cancelado. Levanta RuntimeError se não houver tkinter."""
    code = ('import sys, json, tkinter as tk\nfrom tkinter import filedialog as fd\n'
            'k, p, s = sys.argv[1], sys.argv[2], sys.argv[3] or None\n'
            'r = tk.Tk(); r.withdraw(); r.attributes("-topmost", True)\n'
            'if k == "folder": v = fd.askdirectory(title=p, initialdir=s, mustexist=True)\n'
            'elif k == "files": v = list(fd.askopenfilenames(title=p, initialdir=s))\n'
            'else: v = fd.askopenfilename(title=p, initialdir=s)\n'
            'print(json.dumps(v or None))\n')
    st = os.path.expanduser(start) if start and os.path.isdir(os.path.expanduser(start)) else ''
    try:
        r = subprocess.run([sys.executable, '-c', code, kind, prompt or '', st], capture_output=True, text=True, timeout=900, **no_window_kwargs())
    except subprocess.TimeoutExpired:
        return None
    if r.returncode != 0: raise RuntimeError((r.stderr or 'tkinter indisponível').strip()[-160:])
    import json
    v = json.loads(r.stdout.strip() or 'null')
    if kind == 'files' and isinstance(v, list): return [os.path.normpath(x) for x in v] or None
    return os.path.normpath(v) if v else None


def openssl():
    """Executável do openssl (o do sistema no macOS; no Windows, o do Git for Windows se não estiver no PATH)."""
    import shutil
    if MACOS and os.path.exists('/usr/bin/openssl'): return '/usr/bin/openssl'
    p = shutil.which('openssl')
    if p: return p
    if WINDOWS:
        for c in (r'%ProgramFiles%\Git\usr\bin\openssl.exe', r'%ProgramFiles%\Git\mingw64\bin\openssl.exe', r'C:\msys64\usr\bin\openssl.exe'):
            c = os.path.expandvars(c)
            if os.path.isfile(c): return c
    return 'openssl'


# ---------------------------------------------------------------- links
def link_file(src, dst):
    """Link para um arquivo grande (pacotes SWFL). No Windows o symlink pede modo de desenvolvedor: tenta symlink, hardlink e, por fim, cópia."""
    if not WINDOWS: return os.symlink(src, dst)
    try: return os.symlink(src, dst)
    except OSError: pass
    try: return os.link(src, dst)
    except OSError: pass
    import shutil
    shutil.copyfile(src, dst)


def link_dir(src, dst):
    """Link de pasta (ambiente guardado em outro disco). No Windows: junção NTFS, que não pede privilégio."""
    if not WINDOWS: return os.symlink(src, dst)
    try: return os.symlink(src, dst, target_is_directory=True)
    except OSError: pass
    import _winapi
    _winapi.CreateJunction(os.path.abspath(src), os.path.abspath(dst))


def is_link(path):
    """Symlink ou, no Windows, junção NTFS."""
    if os.path.islink(path): return True
    isj = getattr(os.path, 'isjunction', None)
    return bool(isj and isj(path))


def remove_link(path):
    """Apaga o link (não o destino). Uma junção sai com rmdir."""
    try: os.unlink(path)
    except (IsADirectoryError, PermissionError):
        os.rmdir(path)


def long_paths_enabled():
    """Windows: o sistema aceita caminhos com mais de 260 caracteres (HKLM\\...\\FileSystem\\LongPathsEnabled = 1)."""
    if not WINDOWS: return True
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r'SYSTEM\CurrentControlSet\Control\FileSystem') as k:
            return winreg.QueryValueEx(k, 'LongPathsEnabled')[0] == 1
    except OSError:
        return False


_job = None

def kill_children_on_exit():
    """Windows: põe este processo num Job Object com KILL_ON_JOB_CLOSE. QEMU, glhost e o resto herdam o job e morrem junto com o
    servidor mesmo se ele for encerrado à força (TerminateProcess não roda os tratadores de sinal). No macOS/Linux não faz nada."""
    global _job
    if not WINDOWS or _job is not None: return
    try:
        class _BASIC(ctypes.Structure):
            _fields_ = [('PerProcessUserTimeLimit', ctypes.c_int64), ('PerJobUserTimeLimit', ctypes.c_int64), ('LimitFlags', wintypes.DWORD),
                        ('MinimumWorkingSetSize', ctypes.c_size_t), ('MaximumWorkingSetSize', ctypes.c_size_t), ('ActiveProcessLimit', wintypes.DWORD),
                        ('Affinity', ctypes.c_size_t), ('PriorityClass', wintypes.DWORD), ('SchedulingClass', wintypes.DWORD)]
        class _IO(ctypes.Structure):
            _fields_ = [(n, ctypes.c_uint64) for n in ('ReadOperationCount', 'WriteOperationCount', 'OtherOperationCount', 'ReadTransferCount', 'WriteTransferCount', 'OtherTransferCount')]
        class _EXT(ctypes.Structure):
            _fields_ = [('Basic', _BASIC), ('Io', _IO), ('ProcessMemoryLimit', ctypes.c_size_t), ('JobMemoryLimit', ctypes.c_size_t),
                        ('PeakProcessMemoryUsed', ctypes.c_size_t), ('PeakJobMemoryUsed', ctypes.c_size_t)]
        _k32.CreateJobObjectW.restype = wintypes.HANDLE
        _k32.GetCurrentProcess.restype = wintypes.HANDLE
        h = _k32.CreateJobObjectW(None, None)
        if not h: return
        info = _EXT(); info.Basic.LimitFlags = 0x2000                 # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        if not _k32.SetInformationJobObject(wintypes.HANDLE(h), 9, ctypes.byref(info), ctypes.sizeof(info)): return   # JobObjectExtendedLimitInformation
        if _k32.AssignProcessToJobObject(wintypes.HANDLE(h), wintypes.HANDLE(_k32.GetCurrentProcess())): _job = h
    except Exception:
        pass


def watch_stdin_eof(callback):
    """Chama `callback` quando a entrada padrão fecha (o Electron saiu ou pediu para encerrar): no Windows não há SIGTERM entre processos."""
    import threading
    def run():
        try:
            while sys.stdin.buffer.read(1): pass
        except Exception: pass
        callback()
    threading.Thread(target=run, daemon=True).start()
