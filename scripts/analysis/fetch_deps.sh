#!/usr/bin/env bash
# Fetch each vendored dep's pinned upstream commit (depth 1) into the cobalt repo as refs/upstream-deps/<name>.
cd ${ROOT:-$HOME/chrobalt}/src
C=https://chromium.googlesource.com
while read d url; do
  sha=$(git ls-tree origin/chromium/m138 "$d" | awk '{print $3}')
  name=$(echo "$d" | tr '/+' '__')
  echo "### $d $sha"
  for i in 1 2 3; do git fetch --depth 1 --no-tags "$url" "$sha:refs/upstream-deps/$name" && break; echo "retry $i"; sleep $((i*10)); done
done <<LIST
v8 $C/v8/v8.git
third_party/skia https://skia.googlesource.com/skia.git
third_party/webrtc https://webrtc.googlesource.com/src.git
third_party/angle $C/angle/angle.git
third_party/perfetto $C/external/github.com/google/perfetto.git
third_party/icu $C/chromium/deps/icu.git
third_party/boringssl/src https://boringssl.googlesource.com/boringssl.git
net/third_party/quiche/src https://quiche.googlesource.com/quiche.git
third_party/libc++/src $C/external/github.com/llvm/llvm-project/libcxx.git
third_party/googletest/src $C/external/github.com/google/googletest.git
third_party/cpuinfo/src $C/external/github.com/pytorch/cpuinfo.git
LIST
echo "ALLDONE"
