# Attribute address ranges of DWARF compile units to source directories.
# Input: llvm-dwarfdump --debug-info --recurse-depth=0 output on stdin.
import sys,re,collections
pair=re.compile(r'\[0x([0-9a-f]+), 0x([0-9a-f]+)\)')
cu=None; ivs=[]
def flush():
    pass
name=None; rngs=[]; out=[]
low=None
for l in sys.stdin:
    if 'DW_TAG_compile_unit' in l:
        if name is not None: out.append((name,rngs))
        name='?'; rngs=[]; low=None
    m=re.search(r'DW_AT_name\s+\("([^"]*)"\)',l)
    if m and name=='?': name=m.group(1)
    m=re.search(r'DW_AT_low_pc\s+\(0x([0-9a-f]+)\)',l)
    if m: low=int(m.group(1),16)
    m=re.search(r'DW_AT_high_pc\s+\(0x([0-9a-f]+)\)',l)
    if m and low is not None: rngs.append((low,int(m.group(1),16)))
    for a,b in pair.findall(l):
        a,b=int(a,16),int(b,16)
        if b>a: rngs.append((a,b))
if name is not None: out.append((name,rngs))
def bucket(p):
    p=re.sub(r'^(\.\./)+','',p)
    parts=p.split('/')
    if parts[0] in ('third_party','components','services','starboard','cobalt') and len(parts)>2:
        if parts[0]=='third_party' and parts[1]=='blink' and len(parts)>3: return '/'.join(parts[:4])
        return '/'.join(parts[:2])
    if parts[0]=='gen': return 'gen/'+'/'.join(parts[1:3])
    return parts[0]
ev=[]
for n,rs in out:
    b=bucket(n)
    for a,e in rs: ev.append((a,e,b))
ev.sort(); c=collections.Counter(); end=0; tot=0
for a,e,b in ev:
    if e<=end: continue
    s=e-max(a,end); end=e; c[b]+=s; tot+=s
print(f'CUs={len(out)} covered={tot/2**20:.1f}MB')
for k,v in c.most_common(): print(f'{v/2**20:7.2f} MB {100*v/tot:5.1f}%  {k}')
