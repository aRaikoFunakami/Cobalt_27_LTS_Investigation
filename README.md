# Cobalt 27.lts (Chrobalt) investigation

Chromium 138 ベースの Cobalt（Chrobalt）27.lts.13 について、バイナリサイズ（ROM）と RAM 使用量を調査したときのパッチ・スクリプト・計測データです。
調査の全記録は [docs/investigation-log.md](docs/investigation-log.md) にあります。

## 調査対象

| 項目 | 値 |
|---|---|
| ソース | https://github.com/youtube/cobalt タグ `27.lts.13`（commit `03973ab22573f78be9b3765c595742d77c75a65e`） |
| Chromium バージョン | 138.0.7204.311（`chrome/VERSION`） |
| 上流との比較に使ったブランチ | 同リポジトリの `chromium/m138`（commit `c5c88badf4`、138.0.7204.311）、`chromium/m144`（144.0.7559.259）、`chromium/main`（152.0.7977.0） |
| サイズ比較用の Chrome | Chrome for Testing 138.0.7204.183 linux64 |
| ビルド構成 | `linux-x64x11`、build type `gold`（`is_official_build=true`、`cobalt_is_release_build=true`） |
| ホスト | Ubuntu 24.04.3、24 論理コア、RAM 125GB、Intel UHD Graphics 770（Raptor Lake-S）、カーネル 6.17.0-35、iHD 24.1.0、libva 2.20、FFmpeg 6.1.1 |

## ディレクトリ

```
patches/vaapi_experiment.patch   Starboard の FFmpeg デコーダに VA-API を追加する実験パッチ（環境変数で有効化）
scripts/measure/                 計測スクリプト（起動・メモリサンプリング・集計・smaps 分類・監視）
scripts/memshim/                 物理メモリ量・CPU 数・/proc/meminfo を偽装する LD_PRELOAD シム
scripts/build/rom_queue.sh       ROM の内訳用ビルドキュー（-Os / CFI / ThinLTO / ICF を 1 つずつ外した cobalt と上流 Chromium）
scripts/analysis/                DWARF によるサイズ内訳、上流との backport 判定、依存リポジトリ取得、VA-API 対応確認、グラフ作成
data/<run>/                      各計測の mem.csv（1 秒ごと）、cgroup_events.txt、key_log_lines.txt、smaps 内訳
data/SUMMARY.txt                 全計測の集計（mem_summary.py の出力）
data/rom_sizes.tsv               ROM の内訳用ビルドの strip 後サイズ
docs/investigation-log.md        調査ログ（Step 1〜14）
docs/images/                     記事用のグラフ・スクリーンショット
```

## 再現手順

### 1. ソース取得と gold ビルド

```bash
mkdir -p ~/chrobalt && cd ~/chrobalt
export PATH="$HOME/depot_tools:$PATH"
git clone --depth 1 --branch 27.lts.13 https://github.com/youtube/cobalt.git src
gclient config --name=src https://github.com/youtube/cobalt.git
cd src
gclient sync --no-history -r src@refs/tags/27.lts.13
build/install-build-deps.sh          # sudo が必要
cobalt/build/gn.py -p linux-x64x11 -c gold --no-rbe
# 新しい depot_tools は AI エージェント環境を検出すると siso に --heartbeat_period を付けるが、
# 27.lts が固定している siso はこのフラグを知らないため、該当する環境変数を外して実行する
env -u CLAUDECODE -u AI_AGENT autoninja -C out/linux-x64x11_gold cobalt
```

24 コアのローカルビルドで約 85 分でした。

### 2. strip 済みの実行ディレクトリ

```bash
O=~/chrobalt/src/out/linux-x64x11_gold; R=~/chrobalt/run-gold; mkdir -p $R
strip -o $R/cobalt $O/cobalt
strip -o $R/libstarboard.so.18 $O/starboard/libstarboard.so.18   # RPATH の $ORIGIN に置く
for f in $O/*.pak $O/locales $O/ssl $O/resources $O/hyphen-data; do ln -sfn $f $R/; done
```

### 3. VA-API パッチ（任意）

```bash
cd ~/chrobalt/src && git apply /path/to/patches/vaapi_experiment.patch
env -u CLAUDECODE -u AI_AGENT autoninja -C out/linux-x64x11_gold cobalt   # libstarboard.so のみ再ビルド
strip -o ~/chrobalt/run-gold/libstarboard.so.18 out/linux-x64x11_gold/starboard/libstarboard.so.18
```

| `COBALT_EXPERIMENTAL_VAAPI` | 動作 |
|---|---|
| 未設定 / `0` | 変更なし |
| `1` | AV1 と 8bit 以外を非対応と申告し、VP9 を FFmpeg + VA-API でデコード（結果は CPU 側にコピー） |
| `sw` | AV1 と 8bit 以外を非対応と申告し、VP9 を libvpx でデコード（比較用） |

### 4. ROM の内訳（任意、合計 8 時間程度）

```bash
cd ~/chrobalt/src
for v in "rom_O2:optimize_for_size = false" "rom_nocfi:is_cfi = false" "rom_nolto:use_thin_lto = false"; do
  d=out/${v%%:*}; mkdir -p $d; { cat out/linux-x64x11_gold/args.gn; echo "${v#*:}"; } > $d/args.gn
done
echo "is_cfi = false" >> out/rom_nolto/args.gn          # CFI requires ThinLTO
cobalt/build/gn.py -p chromium_linux-x64x11 -c gold --no-rbe
# 上流の chrome は Cobalt のヒストグラム定義 XML が原因でビルドできないため、ビルド中だけ退避する
mv tools/metrics/histograms/metadata/cobalt /tmp/parked_cobalt_histograms
env -u CLAUDECODE -u AI_AGENT autoninja -C out/chromium_linux-x64x11_gold chrome content_shell
mv /tmp/parked_cobalt_histograms tools/metrics/histograms/metadata/cobalt
ROOT=~/chrobalt scripts/build/rom_queue.sh     # cobalt の各構成（キューには上流 Chromium の手順も含む）
```

### 5. 計測

```bash
gcc -O2 -shared -fPIC -o ~/chrobalt/memshim/fake_physmem.so scripts/memshim/fake_physmem.c -ldl   # 偽装を使う場合
export ROOT=~/chrobalt FAST_FIRST=20 SMAPS_AT=120
V='--url=https://www.youtube.com/tv#/watch?v=aqz-KE-bpKQ'
scripts/measure/run_mem.sh startup 180                                  # ホーム画面
scripts/measure/run_mem.sh E0_base 180 "$V"                             # AV1 4K
FAKE_NPROC=4 scripts/measure/run_mem.sh E1_nproc4 180 "$V"              # CPU 数を 4 と申告
COBALT_EXPERIMENTAL_VAAPI=sw scripts/measure/run_mem.sh H0_vp9_sw 180 "$V"
COBALT_EXPERIMENTAL_VAAPI=1  scripts/measure/run_mem.sh H1_vp9_vaapi 180 "$V"
FAKE_PHYS_MB=1024 FAKE_NPROC=4 FAKE_MEMINFO=scripts/memshim/meminfo_1g.txt \
  WRAP="systemd-run --user --scope -q -p MemoryMax=600M -p MemorySwapMax=0 taskset -c 0-3" \
  scripts/measure/run_mem.sh E6_device1g_cg600 180 "$V"
python3 scripts/measure/mem_summary.py ~/chrobalt/mem/*/
```

`run_mem.sh` は Xvfb（`:99`、1920x1080）を起動し、gold の `cobalt` を動かして 1 秒ごとにプロセスツリーの RSS/PSS/USS と DRM fdinfo（GPU メモリ）を記録し、30 秒ごとにスクリーンショットを撮ります。
`--url` は起動 URL ではなく YouTube アプリへのディープリンクとして渡ります。

`cobalt.log` は通信内容を含みうるため公開していません。必要な行だけを `data/<run>/key_log_lines.txt` に抜き出しています。
