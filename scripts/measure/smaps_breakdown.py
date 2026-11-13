#!/usr/bin/env python3
"""Group /proc/<pid>/smaps by mapping into categories. usage: smaps_breakdown.py <smaps file>"""
import sys, re, collections
pss = collections.Counter(); rss = collections.Counter(); name = None
def cat(n):
    if not n: return 'anon (unnamed)'
    if n.startswith('[anon:'): return n
    if n.startswith('['): return n
    b = n.rsplit('/', 1)[-1]
    if b == 'cobalt': return 'file: cobalt (code/rodata)'
    if b.startswith('libstarboard'): return 'file: libstarboard'
    if re.search(r'gallium|swrast|dri|LLVM|libGL|libEGL|mesa|glapi', b): return 'file: Mesa/GL/LLVM'
    if '/dev/' in n or 'memfd' in n or 'SYSV' in n: return 'shared: ' + b.split(' ')[0]
    if n.endswith(('.pak', '.dat')) or '/fonts/' in n: return 'file: pak/fonts/data'
    return 'file: other libs'
for l in open(sys.argv[1]):
    m = re.match(r'^[0-9a-f]+-[0-9a-f]+ \S+ \S+ \S+ \S+\s*(.*)$', l)
    if m: name = cat(m.group(1).strip()); continue
    m = re.match(r'^(Pss|Rss):\s+(\d+)', l)
    if m: (pss if m.group(1) == 'Pss' else rss)[name] += int(m.group(2))
tot = sum(pss.values())
for k, v in pss.most_common(14): print(f'{v/1024:8.1f} MB {100*v/tot:5.1f}%  {k}')
print(f'{tot/1024:8.1f} MB total PSS')
