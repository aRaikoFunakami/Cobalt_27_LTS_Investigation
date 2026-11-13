# For each modified file: fraction of Cobalt-added lines (vs upstream m138) that already exist
# in the same path at newer upstream refs. High fraction + no Cobalt markers => likely backport.
import sys,re,subprocess,collections,json
S=sys.argv[1]; refs=sys.argv[2:]
MARK=re.compile(r'COBALT|[Cc]obalt|STARBOARD|[Ss]tarboard|HERMETIC|PRIVACY_SANDBOX|privacy_sandbox|IN_MEMORY_UPDATES|WEBRTC_PEER|webrtc_peer|BUILD_BASE_WITH_CPP17|DEVTOOLS_BACKEND|devtools_backend|devtools_frontend|ANDROIDTV|NATIVE_TOOLCHAIN|MULTI_PACKETS')
added=collections.defaultdict(list); cur=None
for l in open(f'{S}/core_m.diff',errors='replace'):
    if l.startswith('diff --git'): cur=l.split(' b/',1)[1].strip(); continue
    if l.startswith('+') and not l.startswith('+++'):
        t=l[1:].strip()
        if len(t)>=12 and not re.fullmatch(r'[#/{}()\[\];,*\s-]*|#(endif|else).*|//.*',t): added[cur].append(t)
def show(ref,path):
    r=subprocess.run(['git','show',f'{ref}:{path}'],capture_output=True)
    return set(x.strip() for x in r.stdout.decode('utf-8','replace').splitlines()) if r.returncode==0 else None
res={}
for f,lines in added.items():
    if not lines: continue
    marked=any(MARK.search(x) for x in lines)
    row={'n':len(lines),'marked':marked}
    for ref in refs:
        s=show(ref,f); row[ref]=None if s is None else round(sum(x in s for x in lines)/len(lines),2)
    res[f]=row
json.dump(res,open(f'{S}/backport.json','w'))
last=refs[-1]
def bucket(r):
    v=r.get(last)
    if v is None: return 'file gone upstream'
    if v>=0.8: return 'mostly upstream(>=80%)'
    if v>=0.3: return 'partly upstream(30-80%)'
    return 'not upstream(<30%)'
c=collections.Counter((bucket(r),r['marked']) for r in res.values())
print('files analysed',len(res),'ref',last)
for (b,m),n in sorted(c.items()): print(f'{n:5d}  {b:26s} cobalt_marked={m}')
cand=sorted([(r['n'],f,r) for f,r in res.items() if not r['marked'] and (r.get(last) or 0)>=0.8],reverse=True)
print('likely backports (unmarked, >=80% in',last,'):',len(cand))
for n,f,r in cand[:15]: print(f'  {n:4d} {f}  '+' '.join(f'{k.split("/")[-1]}={r[k]}' for k in refs))
