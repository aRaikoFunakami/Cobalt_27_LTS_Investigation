#!/usr/bin/env python3
"""Sample memory of a process tree once per interval.
usage: mem_sample.py <root_pid> <out.csv> [interval_s=1]
Columns: t, nproc, rss_kb, pss_kb, uss_kb (Private_Clean+Private_Dirty), swap_pss_kb, per-process "name:pid:pss" list.
"""
import os, sys, time
root, out = int(sys.argv[1]), sys.argv[2]
iv = float(sys.argv[3]) if len(sys.argv) > 3 else 1.0

def children_map():
    m = {}
    for p in os.listdir('/proc'):
        if not p.isdigit(): continue
        try:
            st = open(f'/proc/{p}/stat').read()
            ppid = int(st[st.rindex(')') + 2:].split()[1])
            m.setdefault(ppid, []).append(int(p))
        except OSError: pass
    return m

def tree(pid, m):
    out, st = [], [pid]
    while st:
        x = st.pop(); out.append(x); st += m.get(x, [])
    return out

def drm(pids):
    """GPU buffer memory from DRM fdinfo (not part of RSS), once per drm-client-id."""
    seen = {}
    for pid in pids:
        try: fds = os.listdir(f'/proc/{pid}/fd')
        except OSError: continue
        for fd in fds:
            try:
                if not os.readlink(f'/proc/{pid}/fd/{fd}').startswith('/dev/dri/'): continue
                info = dict(l.split(':', 1) for l in open(f'/proc/{pid}/fdinfo/{fd}') if ':' in l)
            except OSError: continue
            cid = info.get('drm-client-id', '').strip()
            if not cid or cid in seen: continue
            kib = lambda k: int(info.get(k, '0 KiB').split()[0])
            seen[cid] = (kib('drm-total-system0'), kib('drm-resident-system0'), int(info.get('drm-engine-video', '0 ns').split()[0]))
    return [sum(v[i] for v in seen.values()) for i in range(3)]

def rollup(pid):
    d = {}
    try:
        for l in open(f'/proc/{pid}/smaps_rollup'):
            k, *v = l.split()
            if v and v[0].isdigit(): d[k.rstrip(':')] = int(v[0])
        d['name'] = open(f'/proc/{pid}/comm').read().strip()
    except OSError: return None
    return d

t0 = time.time()
with open(out, 'w') as f:
    f.write('t,nproc,rss_kb,pss_kb,uss_kb,swap_pss_kb,threads,drm_total_kb,drm_resident_kb,drm_video_ns,procs\n')
    while os.path.exists(f'/proc/{root}'):
        pids = tree(root, children_map())
        rs = [r for r in (rollup(p) for p in pids) if r]
        dt, dr, dv = drm(pids)
        s = lambda k: sum(r.get(k, 0) for r in rs)
        procs = ' '.join(f"{r['name']}:{r.get('Pss',0)}" for r in rs if r.get('Pss', 0) > 1024)
        f.write(f"{time.time()-t0:.1f},{len(rs)},{s('Rss')},{s('Pss')},{s('Private_Clean')+s('Private_Dirty')},{s('SwapPss')},{sum(len(os.listdir(f'/proc/{p}/task')) for p in tree(root, children_map()) if os.path.exists(f'/proc/{p}/task'))},{dt},{dr},{dv},{procs}\n")
        f.flush(); time.sleep(0.1 if time.time()-t0 < float(os.environ.get('FAST_FIRST', '0')) else iv)
