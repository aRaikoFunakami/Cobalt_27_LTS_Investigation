// LD_PRELOAD shim for experiments on how Cobalt adapts to machine resources.
//   FAKE_PHYS_MB : sysconf(_SC_PHYS_PAGES / _SC_AVPHYS_PAGES) report this much RAM
//   FAKE_NPROC   : sysconf(_SC_NPROCESSORS_ONLN / _CONF) report this many CPUs
//   FAKE_MEMINFO : path of a file served instead of /proc/meminfo (open/openat/fopen)
// ponytail: only the entry points Cobalt/glibc callers use here; add more if a reader bypasses them.
#define _GNU_SOURCE
#include <dlfcn.h>
#include <fcntl.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

#define REAL(name) static __typeof__(name) *real_##name; \
  if (!real_##name) real_##name = (__typeof__(name) *)dlsym(RTLD_NEXT, #name)

long sysconf(int name) {
  REAL(sysconf);
  const char *mb = getenv("FAKE_PHYS_MB"), *np = getenv("FAKE_NPROC");
  if (mb && (name == _SC_PHYS_PAGES || name == _SC_AVPHYS_PAGES)) {
    long pages = atol(mb) * 1024L * 1024L / real_sysconf(_SC_PAGESIZE);
    return name == _SC_AVPHYS_PAGES ? pages / 2 : pages;
  }
  if (np && (name == _SC_NPROCESSORS_ONLN || name == _SC_NPROCESSORS_CONF)) return atol(np);
  return real_sysconf(name);
}

static const char *redir(const char *p) {
  const char *f = getenv("FAKE_MEMINFO");
  return (f && p && strcmp(p, "/proc/meminfo") == 0) ? f : p;
}

int open(const char *p, int flags, ...) {
  REAL(open);
  mode_t m = 0;
  if (flags & (O_CREAT | O_TMPFILE)) { va_list a; va_start(a, flags); m = va_arg(a, int); va_end(a); }
  return real_open(redir(p), flags, m);
}
int open64(const char *p, int flags, ...) {
  REAL(open64);
  mode_t m = 0;
  if (flags & (O_CREAT | O_TMPFILE)) { va_list a; va_start(a, flags); m = va_arg(a, int); va_end(a); }
  return real_open64(redir(p), flags, m);
}
int openat(int d, const char *p, int flags, ...) {
  REAL(openat);
  mode_t m = 0;
  if (flags & (O_CREAT | O_TMPFILE)) { va_list a; va_start(a, flags); m = va_arg(a, int); va_end(a); }
  return real_openat(d, redir(p), flags, m);
}
FILE *fopen(const char *p, const char *mode) { REAL(fopen); return real_fopen(redir(p), mode); }
FILE *fopen64(const char *p, const char *mode) { REAL(fopen64); return real_fopen64(redir(p), mode); }
int openat64(int d, const char *p, int flags, ...) {
  REAL(openat64);
  mode_t m = 0;
  if (flags & (O_CREAT | O_TMPFILE)) { va_list a; va_start(a, flags); m = va_arg(a, int); va_end(a); }
  return real_openat64(d, redir(p), flags, m);
}
