#!/usr/bin/env bash
# Watch a long-running job: emits one line per event (error / stall / exit / heartbeat).
# usage: watchdog.sh <pid> <logfile> [stall_minutes=10] [heartbeat_minutes=15 (0=off)]
# QUIET=1: no heartbeat, exit on first ERROR/STALL (one notification total when run via Bash run_in_background).
# Progress = any change in: log size, disk used on /, network rx bytes, CPU time of the process tree.
# ponytail: whole-process-tree CPU via /proc scan; fine for one job at a time.
pid=$1 log=$2 stall_min=${3:-10} hb_min=${4:-15}
ERR='fatal:|error:|ERROR|FAILED|Traceback|Killed|out of memory|HTTP 4[0-9][0-9]|HTTP 5[0-9][0-9]|RESOURCE_EXHAUSTED|rate limit|Connection reset|timed out|early EOF|RPC failed'

tree_cpu() {  # sum utime+stime (ticks) of pid and all descendants
  local p kids sum=0
  for p in $(pstree -p "$1" 2>/dev/null | grep -o '([0-9]*)' | tr -d '()'); do
    [ -r /proc/$p/stat ] && sum=$((sum + $(awk '{print $14+$15}' /proc/$p/stat 2>/dev/null || echo 0)))
  done
  echo $sum
}
snap() { echo "$(stat -c %s "$log" 2>/dev/null || echo 0) $(df --output=used / | tail -1) $(awk 'NR>2{s+=$2}END{print s}' /proc/net/dev) $(tree_cpu "$pid")"; }

last=$(snap) still=0 tick=0 seen=0
while kill -0 "$pid" 2>/dev/null; do
  sleep 60; tick=$((tick+1))
  # new error lines (log may use \r for progress)
  n=$(tr '\r' '\n' < "$log" 2>/dev/null | wc -l)
  if [ "$n" -gt "$seen" ]; then
    tr '\r' '\n' < "$log" | tail -n +$((seen+1)) | grep -E "$ERR" | head -5 | sed 's/^/[ERROR] /'
    seen=$n
    [ -n "$QUIET" ] && tr '\r' '\n' < "$log" | grep -qE "$ERR" && exit 1
  fi
  cur=$(snap)
  if [ "$cur" = "$last" ]; then still=$((still+1)); else still=0; fi
  [ $((still % stall_min)) -eq 0 ] && [ $still -gt 0 ] && { echo "[STALL] no progress for ${still} min (log/disk/net/cpu unchanged)"; [ -n "$QUIET" ] && exit 1; }
  # near-stall: only CPU ticking, nothing written/downloaded
  read -r ls du rx cpu <<<"$cur"; read -r ls0 du0 rx0 cpu0 <<<"$last"
  last=$cur
  if [ -z "$QUIET" ] && [ "$hb_min" -gt 0 ] && [ $((tick % hb_min)) -eq 0 ]; then
    prog=$(tr '\r' '\n' < "$log" | grep -v '^\s*$' | tail -1 | cut -c1-150)
    echo "[HEARTBEAT] ${tick}min disk_used=$((du/1048576))GB net_rx=$((rx/1073741824))GB last: $prog"
  fi
done
echo "[EXIT] pid $pid gone. log tail: $(tr '\r' '\n' < "$log" | grep -v '^\s*$' | tail -2 | tr '\n' ' ' | cut -c1-300)"
