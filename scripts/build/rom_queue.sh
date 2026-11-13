#!/usr/bin/env bash
# Sequential build queue for ROM attribution. Writes progress to rom_queue.log and sizes to rom_sizes.tsv.
# Each build: autoninja (AI-agent env vars removed for the pinned siso), watchdog for stall/error, then
# strip + section sizes of the produced binary.
set -u
ROOT=${ROOT:-$HOME/chrobalt}; SRC=$ROOT/src; LOG=$ROOT/rom_queue.log; OUT=$ROOT/rom_sizes.tsv
export PATH="$HOME/depot_tools:$PATH"
cd $SRC
log() { echo "[$(date '+%F %T')] $*" >> $LOG; }

measure() {  # label binary
  local label=$1 bin=$2 tmp=$ROOT/rom_strip_$1
  strip -o $tmp $bin || { log "MEASURE_FAIL $label"; return; }
  local sz=$(stat -c %s $tmp)
  local secs=$(readelf -SW $tmp | python3 -I -c "
import sys,re
d={}
for l in sys.stdin:
  m=re.match(r'\s*\[\s*\d+\]\s+(\S+)\s+\S+\s+[0-9a-f]+\s+[0-9a-f]+\s+([0-9a-f]+)',l)
  if m: d[m.group(1)]=int(m.group(2),16)
print(' '.join(f'{k}={d.get(k,0)}' for k in ('.text','.rodata','.rela.dyn','.data.rel.ro','.eh_frame')))")
  echo -e "$label\t$sz\t$secs" >> $OUT
  rm -f $tmp
  log "MEASURED $label stripped=$sz"
}

build() {  # label outdir targets...
  local label=$1 dir=$2; shift 2
  log "START $label ($dir: $*)"
  local blog=$ROOT/rom_build_$label.log
  ( env -u CLAUDECODE -u AI_AGENT autoninja -C $dir "$@" > $blog 2>&1; echo "EXIT $?" >> $blog ) &
  local bp=$!
  sleep 5
  local np=$(pgrep -P $bp | head -1)
  QUIET= $ROOT/watchdog.sh ${np:-$bp} $blog 10 0 >> $LOG 2>&1 &
  local wp=$!
  wait $bp
  kill $wp 2>/dev/null
  log "END $label $(tail -1 $blog) $(tr '\r' '\n' < $blog | grep -E 'Build Succeeded|FAILED' | tail -1 | cut -c1-120)"
}

[ -f $OUT ] || echo -e "label\tstripped_bytes\tsections" > $OUT
grep -q '^gold_baseline' $OUT || measure gold_baseline out/linux-x64x11_gold/cobalt

build rom_O2 out/rom_O2 cobalt && measure rom_O2 out/rom_O2/cobalt
build rom_nocfi out/rom_nocfi cobalt && measure rom_nocfi out/rom_nocfi/cobalt
build rom_nolto out/rom_nolto cobalt && measure rom_nolto out/rom_nolto/cobalt
build chromium out/chromium_linux-x64x11_gold chrome content_shell && {
  measure chromium_chrome out/chromium_linux-x64x11_gold/chrome
  measure chromium_content_shell out/chromium_linux-x64x11_gold/content_shell
}

# ICF: relink only, done in the gold dir and reverted afterwards.
G=out/linux-x64x11_gold/args.gn
cp $G $G.bak
echo "use_icf = false" >> $G
build rom_noicf out/linux-x64x11_gold cobalt && measure rom_noicf out/linux-x64x11_gold/cobalt
cp $G.bak $G
build gold_restore out/linux-x64x11_gold cobalt && measure gold_restored out/linux-x64x11_gold/cobalt
log "ALL_DONE"
