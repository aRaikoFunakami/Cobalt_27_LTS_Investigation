#!/usr/bin/env python3
"""Summarize runs: steady PSS (median of last 60%), peak PSS/RSS, playback progress via screenshot diffs.
usage: mem_summary.py <run_dir>..."""
import sys, csv, glob, os, statistics
from PIL import Image, ImageChops
for d in sys.argv[1:]:
    rows = list(csv.DictReader(open(f'{d}/mem.csv')))
    rows = [r for r in rows if int(r['pss_kb']) > 0]
    tail = rows[int(len(rows) * 0.4):-3] or rows
    med = statistics.median(int(r['pss_kb']) for r in tail) / 1024
    pk = max(int(r['pss_kb']) for r in rows) / 1024; rk = max(int(r['rss_kb']) for r in rows) / 1024
    shots = sorted(glob.glob(f'{d}/shot_*s.png'), key=lambda p: int(p.rsplit('_', 1)[1][:-5]))
    moving = []
    for a, b in zip(shots, shots[1:]):
        diff = ImageChops.difference(Image.open(a).convert('L'), Image.open(b).convert('L')).getbbox()
        moving.append('Y' if diff else 'n')
    log = open(f'{d}/cobalt.log', errors='replace').read()
    import re
    res = re.findall(r'Updated VideoDecoderConfig.*?natural size: \[(\d+),(\d+)\]', log)
    press = re.findall(r'memory pressure level=(\d)', log)
    gpu = ''
    if 'drm_resident_kb' in rows[0]:
        drm_med = statistics.median(int(r['drm_resident_kb']) for r in tail) / 1024
        drm_pk = max(int(r['drm_total_kb']) for r in rows) / 1024
        vid_s = max(int(r['drm_video_ns']) for r in rows) / 1e9
        gpu = f" gpuResident={drm_med:6.1f}MB gpuTotalPeak={drm_pk:6.1f}MB videoEngine={vid_s:5.1f}s"
    print(f"{os.path.basename(d):24s} samples={len(rows):3d} steadyPSS={med:6.1f}MB peakPSS={pk:6.1f}MB peakRSS={rk:6.1f}MB "
          f"res={'/'.join(sorted(set(w+'x'+h for w,h in res))) or '-'} pressure={''.join(press[-12:]) or '-'} player={'Y' if 'SbPlayerCreate' in log else 'n'} frames_changing={''.join(moving)} last_t={rows[-1]['t']}{gpu}")
