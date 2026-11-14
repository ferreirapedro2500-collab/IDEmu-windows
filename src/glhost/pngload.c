/* pngload.c: decodifica um PNG/JPEG do cache de mapas para RGBA com alfa pré-multiplicado.
   macOS: ImageIO. Windows: WIC (Windows Imaging Component). Separado de host.c por causa dos cabeçalhos do sistema. */
#ifdef _WIN32
#define COBJMACROS
#include <windows.h>
#include <wincodec.h>
#include <stdlib.h>
#include <string.h>
unsigned char *pngload(const char *path,int *w,int *h){
  static IWICImagingFactory *fac; static int inited;
  if(!inited){ inited=1; CoInitializeEx(0,COINIT_APARTMENTTHREADED);
    if(FAILED(CoCreateInstance(&CLSID_WICImagingFactory,0,CLSCTX_INPROC_SERVER,&IID_IWICImagingFactory,(void**)&fac))) fac=0; }
  if(!fac) return 0;
  wchar_t wp[MAX_PATH*2]; if(!MultiByteToWideChar(CP_UTF8,0,path,-1,wp,MAX_PATH*2)) return 0;
  IWICBitmapDecoder *dec=0; IWICBitmapFrameDecode *fr=0; IWICFormatConverter *cv=0; unsigned char *px=0; UINT W=0,H=0;
  if(FAILED(IWICImagingFactory_CreateDecoderFromFilename(fac,wp,0,GENERIC_READ,WICDecodeMetadataCacheOnDemand,&dec))) goto out;
  if(FAILED(IWICBitmapDecoder_GetFrame(dec,0,&fr))) goto out;
  if(FAILED(IWICImagingFactory_CreateFormatConverter(fac,&cv))) goto out;
  if(FAILED(IWICFormatConverter_Initialize(cv,(IWICBitmapSource*)fr,&GUID_WICPixelFormat32bppPRGBA,WICBitmapDitherTypeNone,0,0.0,WICBitmapPaletteTypeCustom))) goto out;
  if(FAILED(IWICFormatConverter_GetSize(cv,&W,&H))||!W||!H) goto out;
  px=calloc(1,(size_t)W*H*4); if(!px) goto out;
  if(FAILED(IWICFormatConverter_CopyPixels(cv,0,W*4,W*H*4,px))){ free(px); px=0; goto out; }
  *w=(int)W; *h=(int)H;
out:
  if(cv) IWICFormatConverter_Release(cv); if(fr) IWICBitmapFrameDecode_Release(fr); if(dec) IWICBitmapDecoder_Release(dec);
  return px; }
#else
#include <ApplicationServices/ApplicationServices.h>
#include <stdlib.h>
#include <string.h>
unsigned char *pngload(const char *path,int *w,int *h){
  CFStringRef s=CFStringCreateWithCString(0,path,kCFStringEncodingUTF8); if(!s) return 0;
  CFURLRef u=CFURLCreateWithFileSystemPath(0,s,kCFURLPOSIXPathStyle,0); CFRelease(s); if(!u) return 0;
  CGImageSourceRef src=CGImageSourceCreateWithURL(u,0); CFRelease(u); if(!src) return 0;
  CGImageRef img=CGImageSourceCreateImageAtIndex(src,0,0); CFRelease(src); if(!img) return 0;
  int W=(int)CGImageGetWidth(img),H=(int)CGImageGetHeight(img);
  unsigned char *px=calloc(1,(size_t)W*H*4);
  CGColorSpaceRef cs=CGColorSpaceCreateDeviceRGB();
  CGContextRef c=px?CGBitmapContextCreate(px,W,H,8,(size_t)W*4,cs,kCGImageAlphaPremultipliedLast):0;
  if(c){ CGContextDrawImage(c,CGRectMake(0,0,W,H),img); CGContextRelease(c); } else { free(px); px=0; }
  CGColorSpaceRelease(cs); CGImageRelease(img); *w=W; *h=H; return px; }
#endif
