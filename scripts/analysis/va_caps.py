#!/usr/bin/env python3
"""Minimal vainfo: list VA-API profiles that have a decode (VLD) entrypoint. usage: va_caps.py [/dev/dri/renderD128]"""
import ctypes, os, sys
dev = sys.argv[1] if len(sys.argv) > 1 else '/dev/dri/renderD128'
va = ctypes.CDLL('libva.so.2'); vadrm = ctypes.CDLL('libva-drm.so.2')
vadrm.vaGetDisplayDRM.restype = ctypes.c_void_p
va.vaQueryVendorString.restype = ctypes.c_char_p
for f in ('vaInitialize', 'vaMaxNumProfiles', 'vaMaxNumEntrypoints', 'vaQueryConfigProfiles', 'vaQueryConfigEntrypoints', 'vaQueryVendorString', 'vaTerminate'):
    getattr(va, f).argtypes = [ctypes.c_void_p] + ([ctypes.c_void_p, ctypes.c_void_p] if f == 'vaInitialize' else [ctypes.c_void_p, ctypes.c_void_p] if f == 'vaQueryConfigProfiles' else [ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p] if f == 'vaQueryConfigEntrypoints' else [])
fd = os.open(dev, os.O_RDWR)
dpy = vadrm.vaGetDisplayDRM(fd)
maj, mnr = ctypes.c_int(), ctypes.c_int()
assert va.vaInitialize(dpy, ctypes.byref(maj), ctypes.byref(mnr)) == 0, 'vaInitialize failed'
print(f'VA-API {maj.value}.{mnr.value}  driver: {va.vaQueryVendorString(dpy).decode()}')
# VAProfile enum values from va/va.h (libva 2.x)
NAMES = dict(enumerate(['MPEG2Simple','MPEG2Main','MPEG4Simple','MPEG4AdvancedSimple','MPEG4Main','H264Baseline','H264Main','H264High','VC1Simple','VC1Main','VC1Advanced','H263Baseline','JPEGBaseline','H264ConstrainedBaseline','VP8Version0_3','H264MultiviewHigh','H264StereoHigh','HEVCMain','HEVCMain10','VP9Profile0','VP9Profile1','VP9Profile2','VP9Profile3','HEVCMain12','HEVCMain422_10','HEVCMain422_12','HEVCMain444','HEVCMain444_10','HEVCMain444_12','HEVCSccMain','HEVCSccMain10','HEVCSccMain444','AV1Profile0','AV1Profile1','HEVCSccMain444_10','Protected','H264High10','VVCMain10','VVCMultilayerMain10']))  # VAProfile order in va/va.h (libva 2.20)
n = va.vaMaxNumProfiles(dpy); profs = (ctypes.c_int * n)(); cnt = ctypes.c_int()
va.vaQueryConfigProfiles(dpy, profs, ctypes.byref(cnt))
ne = va.vaMaxNumEntrypoints(dpy)
dec = []
for p in profs[:cnt.value]:
    eps = (ctypes.c_int * ne)(); ecnt = ctypes.c_int()
    if va.vaQueryConfigEntrypoints(dpy, p, eps, ctypes.byref(ecnt)) == 0 and 1 in eps[:ecnt.value]:  # VAEntrypointVLD = 1
        dec.append(NAMES.get(p, f'profile{p}'))
print('decode (VLD):', ', '.join(dec))
va.vaTerminate(dpy)
