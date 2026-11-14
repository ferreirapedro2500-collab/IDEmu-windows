/* compat.h: o que muda entre macOS e Windows no glhost (GL/GLUT, IPC local, quadro compartilhado, relógio).

   IPC (mesma regra de idemu/plat.py):
     * macOS: cada canal é um socket unix no caminho dado (GLHOST_SOCK, <ctl>/input.sock, <ctl>/map.sock).
     * Windows: o caminho é um arquivo de texto com a porta em 127.0.0.1 (TCP para o canal do guest, UDP para input/map).
       Quem escuta grava o arquivo depois de abrir a porta; quem envia lê a porta do arquivo.
   Compilação no Windows: MSYS2 MinGW-w64 + freeglut + GLEW (src/glhost/build_windows.sh). */
#ifndef GLHOST_COMPAT_H
#define GLHOST_COMPAT_H

#ifdef _WIN32
/* ------------------------------------------------------------------ Windows */
#  ifndef WIN32_LEAN_AND_MEAN
#    define WIN32_LEAN_AND_MEAN
#  endif
#  include <winsock2.h>
#  include <ws2tcpip.h>
#  include <windows.h>
#  include <GL/glew.h>
#  include <GL/wglew.h>
#  include <GL/freeglut.h>
#  include <io.h>
#  include <fcntl.h>
#  include <sys/stat.h>
#  include <unistd.h>
#  include <strings.h>
/* glClearDepthf é GL 4.1/ES: nem todo driver o expõe no contexto de compatibilidade; glClearDepth (GL 1.0) faz o mesmo */
#  define glClearDepthf(x) glClearDepth((GLclampd)(x))
typedef SOCKET ipc_fd;
#  define IPC_BAD INVALID_SOCKET
#  define ipc_close(f) closesocket(f)
typedef WSAPOLLFD ipc_pollfd;
#  define ipc_poll(p,n,t) WSAPoll((p),(ULONG)(n),(t))
#  ifndef POLLIN
#    define POLLIN POLLRDNORM
#  endif
static void compat_init(void){ WSADATA w; WSAStartup(MAKEWORD(2,2),&w); }

static double mono_now(void){ static LARGE_INTEGER f; LARGE_INTEGER c; if(!f.QuadPart) QueryPerformanceFrequency(&f); QueryPerformanceCounter(&c); return (double)c.QuadPart/(double)f.QuadPart; }

static void ipc_write_port(const char *path,int port){
  char tmp[600]; snprintf(tmp,sizeof tmp,"%s.tmp",path); FILE *f=fopen(tmp,"w"); if(!f) return; fprintf(f,"%d\n",port); fclose(f);
  MoveFileExA(tmp,path,MOVEFILE_REPLACE_EXISTING); }
static int ipc_read_port(const char *path){ FILE *f=fopen(path,"r"); int p=0; if(!f) return 0; if(fscanf(f,"%d",&p)!=1) p=0; fclose(f); return p; }
static ipc_fd ipc_bind_loopback(const char *path,int type){
  ipc_fd s=socket(AF_INET,type,0); if(s==IPC_BAD) return IPC_BAD;
  struct sockaddr_in a; memset(&a,0,sizeof a); a.sin_family=AF_INET; a.sin_addr.s_addr=htonl(INADDR_LOOPBACK); a.sin_port=0;
  if(bind(s,(struct sockaddr*)&a,sizeof a)){ closesocket(s); return IPC_BAD; }
  int len=sizeof a; getsockname(s,(struct sockaddr*)&a,&len);
  if(type==SOCK_STREAM&&listen(s,1)){ closesocket(s); return IPC_BAD; }
  ipc_write_port(path,ntohs(a.sin_port)); return s; }
/* canal stream em que o glhost escuta (o QEMU conecta) */
static ipc_fd ipc_listen_stream(const char *path){ unlink(path); return ipc_bind_loopback(path,SOCK_STREAM); }
static ipc_fd ipc_accept(ipc_fd l){ ipc_fd f=accept(l,0,0); if(f!=IPC_BAD){ int one=1; setsockopt(f,IPPROTO_TCP,TCP_NODELAY,(const char*)&one,sizeof one); } return f; }
/* canal de datagramas em que o glhost recebe (input.sock) */
static ipc_fd ipc_dgram_bind(const char *path){ unlink(path); ipc_fd s=ipc_bind_loopback(path,SOCK_DGRAM); if(s!=IPC_BAD){ u_long nb=1; ioctlsocket(s,FIONBIO,&nb); int rb=256*1024; setsockopt(s,SOL_SOCKET,SO_RCVBUF,(const char*)&rb,sizeof rb); } return s; }
static int ipc_dgram_recv(ipc_fd s,char *b,int n){ return recv(s,b,n,0); }   /* socket já não bloqueante */
/* envia um datagrama ao canal `path` (map.sock): a porta é relida a cada envio, o serviço pode ter sido recriado */
static void ipc_dgram_send(ipc_fd *s,const char *path,const char *b,int n){
  if(*s==IPC_BAD){ *s=socket(AF_INET,SOCK_DGRAM,0); if(*s==IPC_BAD) return; u_long nb=1; ioctlsocket(*s,FIONBIO,&nb); }
  int port=ipc_read_port(path); if(!port) return;
  struct sockaddr_in a; memset(&a,0,sizeof a); a.sin_family=AF_INET; a.sin_addr.s_addr=htonl(INADDR_LOOPBACK); a.sin_port=htons((u_short)port);
  sendto(*s,b,n,0,(struct sockaddr*)&a,sizeof a); }

/* quadro compartilhado com o servidor Python (mmap do lado de lá) */
static unsigned char *frame_map(const char *path,size_t len){
  HANDLE f=CreateFileA(path,GENERIC_READ|GENERIC_WRITE,FILE_SHARE_READ|FILE_SHARE_WRITE|FILE_SHARE_DELETE,0,OPEN_ALWAYS,FILE_ATTRIBUTE_NORMAL,0);
  if(f==INVALID_HANDLE_VALUE) return 0;
  HANDLE m=CreateFileMappingA(f,0,PAGE_READWRITE,(DWORD)((unsigned long long)len>>32),(DWORD)(len&0xffffffffu),0);   /* aumenta o arquivo até len */
  CloseHandle(f); if(!m) return 0;
  void *p=MapViewOfFile(m,FILE_MAP_ALL_ACCESS,0,0,len); CloseHandle(m); return (unsigned char*)p; }

/* GL: sem intervalo de troca (o vCPU espera cada quadro) */
static void gl_no_vsync(void){ if(WGLEW_EXT_swap_control) wglSwapIntervalEXT(0); }
static void gl_load(void){ glewExperimental=GL_TRUE; GLenum e=glewInit(); if(e!=GLEW_OK) fprintf(stderr,"[host] glewInit: %s\n",glewGetErrorString(e)); }

/* contexto GL secundário compartilhado (mapa) */
typedef HGLRC glctx_t;
static HDC glctx_dc;
static glctx_t glctx_current(void){ glctx_dc=wglGetCurrentDC(); return wglGetCurrentContext(); }
static glctx_t glctx_create_shared(glctx_t main){ HDC dc=wglGetCurrentDC(); HGLRC c=wglCreateContext(dc); if(!c) return 0; if(!wglShareLists(main,c)){ fprintf(stderr,"[map] wglShareLists falhou (%lu)\n",GetLastError()); wglDeleteContext(c); return 0; } return c; }
static void glctx_make_current(glctx_t c){ wglMakeCurrent(glctx_dc?glctx_dc:wglGetCurrentDC(),c); }

#else
/* ------------------------------------------------------------------ macOS (comportamento original) */
#  define GL_SILENCE_DEPRECATION 1
#  include <GLUT/glut.h>
#  include <OpenGL/gl.h>
#  include <OpenGL/glext.h>
#  include <OpenGL/OpenGL.h>
#  include <unistd.h>
#  include <poll.h>
#  include <sys/socket.h>
#  include <sys/un.h>
#  include <sys/stat.h>
#  include <sys/mman.h>
#  include <fcntl.h>
#  include <strings.h>
#  include <time.h>
typedef int ipc_fd;
#  define IPC_BAD (-1)
#  define ipc_close(f) close(f)
typedef struct pollfd ipc_pollfd;
#  define ipc_poll(p,n,t) poll((p),(n),(t))
static void compat_init(void){}
static double mono_now(void){ struct timespec ts; clock_gettime(CLOCK_MONOTONIC,&ts); return ts.tv_sec+ts.tv_nsec*1e-9; }
static ipc_fd ipc_listen_stream(const char *path){
  unlink(path); int l=socket(AF_UNIX,SOCK_STREAM,0); struct sockaddr_un sa={.sun_family=AF_UNIX}; strncpy(sa.sun_path,path,sizeof sa.sun_path-1);
  if(l<0||bind(l,(struct sockaddr*)&sa,sizeof sa)||listen(l,1)){ if(l>=0) close(l); return -1; } return l; }
static ipc_fd ipc_accept(ipc_fd l){ return accept(l,0,0); }
static ipc_fd ipc_dgram_bind(const char *path){
  struct sockaddr_un ia={.sun_family=AF_UNIX}; snprintf(ia.sun_path,sizeof ia.sun_path,"%s",path); unlink(ia.sun_path); int s=socket(AF_UNIX,SOCK_DGRAM,0);
  if(s>=0&&bind(s,(struct sockaddr*)&ia,sizeof ia)){ close(s); s=-1; } if(s>=0){ int rb=256*1024; setsockopt(s,SOL_SOCKET,SO_RCVBUF,&rb,sizeof rb); } return s; }
static int ipc_dgram_recv(ipc_fd s,char *b,int n){ return (int)recv(s,b,n,MSG_DONTWAIT); }
static void ipc_dgram_send(ipc_fd *s,const char *path,const char *b,int n){
  static struct sockaddr_un sa; if(*s<0){ *s=socket(AF_UNIX,SOCK_DGRAM,0); sa.sun_family=AF_UNIX; snprintf(sa.sun_path,sizeof sa.sun_path,"%s",path); }
  sendto(*s,b,n,MSG_DONTWAIT,(struct sockaddr*)&sa,sizeof sa); }
static unsigned char *frame_map(const char *path,size_t len){
  int ff=open(path,O_RDWR|O_CREAT,0644); if(ff<0) return 0; unsigned char *p=0;
  if(ftruncate(ff,len)==0){ p=mmap(0,len,PROT_READ|PROT_WRITE,MAP_SHARED,ff,0); if(p==MAP_FAILED) p=0; } return p; }
static void gl_no_vsync(void){ GLint si=0; CGLSetParameter(CGLGetCurrentContext(),kCGLCPSwapInterval,&si); }
static void gl_load(void){}
typedef CGLContextObj glctx_t;
static glctx_t glctx_current(void){ return CGLGetCurrentContext(); }
static glctx_t glctx_create_shared(glctx_t main){ glctx_t c=0; CGLError e=CGLCreateContext(CGLGetPixelFormat(main),main,&c); if(e){ fprintf(stderr,"[map] CGLCreateContext: %d\n",e); return 0; } return c; }
static void glctx_make_current(glctx_t c){ CGLSetCurrentContext(c); }
#endif

#endif
