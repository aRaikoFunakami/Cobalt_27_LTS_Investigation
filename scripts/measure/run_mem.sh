#!/usr/bin/env bash
# usage: run_mem.sh <label> <seconds> [cobalt args...]
# Starts a private Xvfb (:99, 1920x1080), runs the stripped gold Cobalt, samples memory every 1s,
# takes screenshots every 30s, then stops Cobalt. Outputs go to ~/chrobalt/mem/<label>/.
set -u
SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
label=$1 secs=$2; shift 2
OUT=${ROOT:-$HOME/chrobalt}/mem/$label; mkdir -p $OUT
Xvfb :99 -screen 0 1920x1080x24 -nolisten tcp >/dev/null 2>&1 & XV=$!
sleep 2
cd ${ROOT:-$HOME/chrobalt}/run-gold
# Optional: WRAP="systemd-run --user --scope -q -p MemoryMax=2G" and/or FAKE_PHYS_MB=2048 (LD_PRELOAD shim).
PRE=""; [ -n "${FAKE_PHYS_MB:-}${FAKE_NPROC:-}${FAKE_MEMINFO:-}" ] && PRE="env ${FAKE_PHYS_MB:+FAKE_PHYS_MB=$FAKE_PHYS_MB} ${FAKE_NPROC:+FAKE_NPROC=$FAKE_NPROC} ${FAKE_MEMINFO:+FAKE_MEMINFO=$FAKE_MEMINFO} LD_PRELOAD=${ROOT:-$HOME/chrobalt}/memshim/fake_physmem.so"
DISPLAY=:99 ${WRAP:-} $PRE ./cobalt --enable-logging=stderr --log-level=0 --v=0 "$@" > $OUT/cobalt.log 2>&1 & CB=$!
FAST_FIRST=${FAST_FIRST:-0} python3 -I $SCRIPT_DIR/mem_sample.py $CB $OUT/mem.csv 1 & MS=$!
for ((t=30; t<=secs; t+=30)); do
  sleep 30
  CG=$(awk -F: '$1=="0"{print $3}' /proc/$CB/cgroup 2>/dev/null)
  [ -n "$CG" ] && { echo "t=${t}s $(tr '\n' ' ' < /sys/fs/cgroup$CG/memory.events) peak=$(cat /sys/fs/cgroup$CG/memory.peak 2>/dev/null)" >> $OUT/cgroup_events.txt; } 2>/dev/null
  kill -0 $CB 2>/dev/null || { echo "cobalt exited early at ~${t}s"; break; }
  [ "${SMAPS_AT:-0}" = "$t" ] && cp /proc/$CB/smaps $OUT/smaps_${t}s.txt 2>/dev/null
  xwd -root -display :99 -silent | ffmpeg -loglevel error -y -f xwd_pipe -i - $OUT/shot_${t}s.png
done
kill $CB 2>/dev/null; sleep 3; kill -9 $CB 2>/dev/null; wait $MS 2>/dev/null
kill $XV 2>/dev/null
echo "DONE $label"
