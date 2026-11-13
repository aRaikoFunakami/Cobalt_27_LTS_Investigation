# Chrobalt (Cobalt 27.lts / Chromium M138) 調査・ビルドログ

Qiita 記事用の作業ログ。大きなステップごとに「まとめ」を追記していく。

> 記載ルール: 根拠はコマンドの出力、ファイルの行、URL で示す。
> 根拠が無いものは **推定** / **一般知識** / **未検証** と明記する（2026-11-12 に全体を再チェック済み）。

- 調査日: 2026-11-12
- 対象: https://github.com/youtube/cobalt
- 作業ディレクトリ: `~/chrobalt`

---

## Step 1. youtube/cobalt は最新 Chromium ベースの Chrobalt か

### 確認方法

```bash
# リポジトリ情報・リリース
gh api repos/youtube/cobalt --jq '{default_branch,pushed_at}'
gh api 'repos/youtube/cobalt/releases?per_page=10' --jq '.[]|"\(.tag_name) \(.published_at)"'

# 各ブランチの Chromium バージョン
for r in main 27.lts 26.android 26.eap chromium/m144 chromium/main autoroll-chromium/main-to-staging; do
  echo "== $r"
  gh api "repos/youtube/cobalt/contents/chrome/VERSION?ref=$r" --jq .content | base64 -d
done

# 現行 Chromium Stable
curl -s 'https://chromiumdash.appspot.com/fetch_releases?channel=Stable&platform=Linux&num=1'
```

### 結果

| ブランチ / 対象 | Chromium | 備考 |
|---|---|---|
| `main` / `27.lts`（最新リリース 27.lts.13, 2026-11-09） | **138.0.7204.311** | 現行リリース |
| `26.android` / `26.eap` | 114.0.5735.358 | 旧世代 |
| `autoroll-chromium/main-to-staging` | 150.0.7849.0 | 次期 rebase 作業中（PR #13935） |
| `chromium/m144`, `chromium/main`(152) | 144 / 152 | upstream ミラーのみ（`cobalt/` なし） |
| Chromium Stable（2026-11-12） | **157.0.8103.78** | |

- リポジトリは Chromium ツリー + `cobalt/` ディレクトリ構成 → **Chrobalt（Chromium ベース Cobalt）**。
- 旧 Cobalt（独自エンジン）は `25.lts` 以前。
  根拠: `25.lts.1+` ブランチには `chrome/VERSION` が無い（404）。一方で `cobalt/dom`、`cobalt/layout`、`cobalt/cssom`、`cobalt/script`、`cobalt/renderer`、`cobalt/loader` という独自エンジンのディレクトリがある。
- `chromium/m114`、`m120`、`m126`、`m132`、`m138` というブランチがある。
  ブランチ名から「約 6 マイルストーンごとに rebase している」と**推定**した。各ブランチの中身や rebase の日付は確認していない。

### まとめ

Chrobalt ではあるが最新 Chromium ではない。現行は **M138**（Stable より約 19 マイルストーン遅れ）。次は M150 への rebase が進行中。

---

## Step 2. 古い Chromium ベースで CVE 対応はどうしているか

### 確認方法

```bash
gh search commits --repo youtube/cobalt "CVE" --limit 15
gh api 'repos/youtube/cobalt/commits?sha=chromium/m138&per_page=8'
# upstream の M138 ブランチ（branch-heads/7204）
curl -s 'https://chromium.googlesource.com/chromium/src/+/refs/branch-heads/7204/chrome/VERSION?format=TEXT' | base64 -d
curl -s 'https://chromium.googlesource.com/chromium/src/+log/refs/branch-heads/7204?n=5&format=JSON'
# M138 sync 以降の upstream/backport コミット
gh api --paginate 'repos/youtube/cobalt/commits?since=2026-04-22T00:00:00Z&per_page=100' \
  --jq '.[].commit|"\(.author.date[:10]) \(.message|split("\n")[0])"' | grep -iE 'UPSTREAM|BACKPORT|security|cve'
```

### 結果

- Cobalt の `chrome/VERSION` 138.0.7204.311 = upstream `refs/branch-heads/7204` の HEAD と一致。
  7204 の最新コミットには `[M138-LTS][cc] Upgrade RTree allocation DCHECK to CHECK (cherry picked from ...)` や
  `Automated Commit: LKGM 16295.95.0 for chromeos` がある。このことから ChromeOS の LTS 用ブランチと判断した
  （コミットメッセージからの判断。LTS の公式スケジュールは確認していない）。
- Cobalt の `chromium/m138` ブランチには `Rebase refresh on YYYY-MM-DD for m138` というコミットがある。
  2026-04 は 4/4・4/8・4/9・4/11・4/12・4/15・4/16・4/17 と頻繁にあり、それより前は 2/10・2/19・3/26 などだった（main 側の PR 名で確認）。
  → **本家の LTS ブランチに入ったセキュリティ修正を取り込む方式**。
- upstream 7204 の最終コミットは **2026-04-16**。Cobalt の最終取り込みは 2026-04-21（#10181）。
  「M138 LTS が終了した」というのは、更新が止まっていることからの**推定**。
- 2026-04-22 以降、main には 1,740 コミットある。そのうち件名が `UPSTREAM:` / `BACKPORT:` で始まるのは 15 件で、多くは tvOS とビルド関連。
  件名に security / CVE / UAF / overflow を含むものは、eMudhra 証明書の失効（#13797 / #13862）と Cobalt 独自コードの UAF / overflow 修正だけだった。
  **件名のキーワード検索なので、件名にこれらの語を含まないセキュリティ修正は見落としている可能性がある。**
- 旧 Cobalt（25.lts 以前）は `Merge fix for CVE-2023-4863` のように CVE 単位で手動 cherry-pick していた。

### まとめ

公開リポジトリから見る限り、セキュリティ追従は「ChromeOS LTS ブランチ追従」→「数マイルストーン単位の大型 rebase」。
現在は M138 LTS 終了〜M150 rebase の間で、**約 7 か月 Chromium 側の修正が入っていない空白期間**とみられる。
（Google 内部での非公開パッチ有無は外からは不明）

---

## Step 3. 27.lts（M138）のリリースビルド（gold）を試す

### 参照した手順

- 公式: `cobalt/site/docs/development/setup-linux.md`（27.lts）
- CI: `.github/config/linux.json`, `.github/actions/build/action.yaml`
- build type 定義: `cobalt/build/gn.py`

| build type | 主な GN 引数 |
|---|---|
| debug | `symbol_level=2`, `cobalt_debugging_enabled=true` |
| devel | `symbol_level=1` |
| qa | `is_official_build=true`, `exclude_unwind_tables=false` |
| **gold（リリース）** | `is_official_build=true`, `cobalt_is_release_build=true` |

CI のターゲット: `cobalt:gn_all`, `cobalt/testing/browser_tests:cobalt_browsertests`, `chromedriver`, `dump_syms`, `minidump_stackwalk`

### 環境

- Ubuntu 24.04.3 LTS（公式検証は 22.04）、24 コア、メモリ 125GB、ディスク空き 3.2TB
- git 2.43.0、depot_tools（既存 `~/depot_tools`）、ccache あり
- sudo はパスワード必要（`install-build-deps.sh` は手動実行が必要）

### 実行コマンド

```bash
cd ~/chrobalt
export PATH="$HOME/depot_tools:$PATH"
git clone --depth 1 --branch 27.lts.13 https://github.com/youtube/cobalt.git src
gclient config --name=src https://github.com/youtube/cobalt.git
cd src
gclient sync --no-history -r src@refs/tags/27.lts.13 -j 16
# 以降予定
build/install-build-deps.sh --quick-check   # 不足パッケージ確認
gclient runhooks
cobalt/build/gn.py -p linux-x64x11 -c gold --no-rbe
autoninja -C out/linux-x64x11_gold cobalt
```

### 経過

#### 3-1. clone + gclient sync — 成功

- `git clone --depth 1`: 562,788 ファイル、約 22GB。
- `gclient sync --no-history -j 16`: EXIT 0、hooks 込みで完了。sync 後 `src` は 24GB。
- 出たメッセージ（いずれも無害）:
  - `ERROR:root:Failed to get version info: git log -1 --grep=^Change-Id: HEAD ...`
    → HEAD のコミットメッセージに `Change-Id:` が無い（`git log -1 --format=%B | grep -c Change-Id` → 0）うえに、
    shallow clone（`git rev-parse --is-shallow-repository` → true）なので、さかのぼって探すこともできない。
    その結果、`lastchange.py` が `0.0.0` にフォールバックした（ログに `Falling back to a version of 0.0.0` と出ている）。
    履歴付きで clone すれば解消するかは**未検証**。
  - `depot_tools recommends git 2.46.0 or later`（Ubuntu 24.04 標準は 2.43.0）

#### 3-2. 依存パッケージ確認

```bash
./build/install-build-deps.sh --quick-check
# WARNING: The following packages are not installed:
# libpcre3
```

不足は `libpcre3` のみ。Ubuntu 24.04 にもパッケージはある（`apt-cache policy libpcre3` → Candidate: 2:8.39-15build1）。
sudo が使えないので、入れずに進めた。

#### 3-3. GN gen（gold）— 成功

```bash
cobalt/build/gn.py -p linux-x64x11 -c gold --no-rbe
# Done. Made 27550 targets from 4119 files in 36866ms
```

`out/linux-x64x11_gold/args.gn`:

```gn
build_type = "gold"
symbol_level = 1
is_official_build = true
cobalt_is_release_build = true
import("//cobalt/build/configs/linux-x64x11/args.gn")
```

#### 3-4. ビルド 1 回目 — 即失敗（depot_tools と siso のバージョン不一致）

```
flag provided but not defined: -heartbeat_period
...
Detected AI agent env (CLAUDECODE, AI_AGENT). Prepending --quiet --batch=false --heartbeat_period=30s ...
```

- 最新の depot_tools の `autoninja` は、AI エージェント環境（`CLAUDECODE` / `AI_AGENT` 環境変数）を検出すると
  siso に `--heartbeat_period` を付ける。
  （ビルドログに `Detected AI agent env ... Prepending ... --heartbeat_period=30s` と出ている）
- 一方、siso は DEPS で `src/third_party/siso/cipd` に固定されている。
  DEPS には `'siso_version': 'git_revision:8863265a...'` とあり、Cobalt のコメントは「milestone 141.0.7390.0 の版に更新」。
  `third_party/siso/cipd/siso version` → `siso v1.4.2`。
  この版は `-heartbeat_period` を知らないので、`flag provided but not defined` で即終了した。
- つまり、**新しい depot_tools と、チェックアウトに固定された古い siso の組み合わせによるズレ**。
- 回避: 環境変数を外して実行。

```bash
env -u CLAUDECODE -u AI_AGENT autoninja -C out/linux-x64x11_gold cobalt
```

- ビルドは siso（ローカル実行）で、ステップ数は約 44,800。

#### 3-5. 監視

ネットワーク起因のエラーやハング、ほぼ進まない状態を検出するため、`watchdog.sh` で監視しながら実行している。

- 1 分ごとに、ログサイズ・ディスク使用量・ネットワーク受信量・プロセスツリーの CPU 時間をスナップショットする。
  すべて変化しない状態が 10 分続いたら `[STALL]`。
- ログに `fatal:` / `error:` / `HTTP 4xx/5xx` / `RESOURCE_EXHAUSTED` / `Killed` などが出たら `[ERROR]`。
- 15 分ごとに `[HEARTBEAT]`（進捗の行）。プロセスが終了したら `[EXIT]`。
- 途中で、トークン節約のため `QUIET=1` モードに切り替えた。heartbeat を出さず、ERROR / STALL を検出した時点で終了するので、通知は 1 回だけになる。

```bash
QUIET=1 ./watchdog.sh <autoninja の PID> build.log 10 0   # バックグラウンドで実行
```

#### 3-6. ビルド 2 回目 — 成功

```
1h25m19.85s Build Succeeded: 36538 steps - 7.14/s
real 85m20s / user 1912m45s / sys 98m16s
```

- 24 コア・ローカル実行（RBE なし、ccache なし）で **約 1 時間 25 分**。
- 監視では ERROR / STALL とも 0 件。
- 計画時のステップ数は約 44,800、実際に実行されたのは 36,538。
- 成果物 `out/linux-x64x11_gold/cobalt`:
  - ELF 64-bit PIE、x86-64、**667MB**（`symbol_level=1` のデバッグ情報込み。`.text` は 82.3MB。
    `size` コマンドの text 列 109MB は `.rodata` なども含んだ値）
  - `ldd` で未解決ライブラリは 0（`libpcre3` が無くても問題なし）
  - 出力ディレクトリ全体は 8.7GB
- `./cobalt --version` を実行すると、バージョン表示ではなくアプリが起動した。
  `cobalt/browser/switches.cc` に `"version"` というスイッチは無い。
  ログに `pulse_audio` という名前のスレッドの起動が出たところで、プロセスを終了させた。
  （`use_pulseaudio=false` なのにこの名前のスレッドがある理由は未調査）

### Step 3 まとめ

| 項目 | 結果 |
|---|---|
| ソース取得（27.lts.13, `--depth 1` + `gclient sync --no-history -j16`） | 成功（サーバー側のエラーなし、24GB） |
| 不足パッケージ | `libpcre3` のみ（ビルド・リンクには不要だった） |
| GN gen（gold） | 成功（27,550 targets） |
| ビルド | 1 回目: depot_tools の AI エージェント検出 × 古い siso で失敗 → 環境変数を外して **成功** |
| 所要時間 | 約 85 分（24 コア、ローカル） |

#### 3-7. なぜ gold なのに 667MB もあるのか

```bash
readelf -SW out/linux-x64x11_gold/cobalt     # セクションごとのサイズ
strip -o cobalt.stripped out/linux-x64x11_gold/cobalt
```

| セクション | サイズ |
|---|---|
| `.debug_info` | 183.7 MB |
| `.debug_str` | 105.2 MB |
| `.debug_line` | 93.4 MB |
| `.strtab` | 87.2 MB |
| `.text`（実際のコード） | 82.3 MB |
| `.debug_ranges` | 45.7 MB |
| `.debug_frame` | 23.8 MB |
| `.symtab` | 16.4 MB |
| **`.debug_*` の合計** | **454.9 MB / 667.8 MB** |

- `cobalt/build/gn.py` の `_BUILD_TYPES['gold']` に `symbol_level: 1` があるので、DWARF のデバッグ情報が入る。
- 配布するときに strip している根拠:
  - Chrome: `chrome/installer/linux/BUILD.gn` に `strip_binary("strip_chrome_binary")` がある。
  - Cobalt: 27.lts.13 の GitHub Release に、strip 済みの `lib/libcobalt.so` が入った `.crx`（`file` の結果が `stripped`、`.debug_*` セクション 0 個）と、
    `libcobalt_..._unstripped_x64_..._release_*.tar.gz`（241MB）が別々に置かれている。
- `strip` すると **108.8 MB** になる。
- 比較: 公式の `cobalt_evergreen_7.13.2_x64_sbversion-18_release.crx` に入っている `lib/libcobalt.so` は **90.7MB**（strip 済み）。
  ICU データは `content/icudtl.dat`（6.6MB）として別ファイルになっている。
  ただし公式のものは evergreen-x64 向けの共有ライブラリで、今回ビルドした linux-x64x11 の実行ファイルとは構成が違う。
- gold（`cobalt_is_release_build=true`）で実際に変わること（ソースで確認）:
  - `cobalt/BUILD.gn`: `//starboard/nplb` を依存から外す。
  - `cobalt/browser/BUILD.gn`: `heap_profiling` と `proxy_server_support` を外す。
  - `cobalt/build/configs/BUILD.gn`: `ENABLE_BUILDFLAG_COBALT_IS_RELEASE_BUILD` を define する（`cobalt/browser/cobalt_secure_navigation_throttle.cc` などで分岐に使われる）。
  - unwind テーブル: qa は `exclude_unwind_tables=false` を明示しているが、gold は指定していないので official build のデフォルトになる。
  - **デバッグ情報（`symbol_level`）は gold でも外れない。**
- `symbol_level = 0` を指定すれば DWARF が入らないはず（**未検証**）。

**ポイント**: M138 の Chrobalt は、Ubuntu 24.04 + 最新の depot_tools でも公式手順どおりにリリースビルド（gold）できる。
ハマりどころは「新しい depot_tools × 古いチェックアウトの siso」の組み合わせだけだった。

---

## Step 4. Chrobalt はどうやって strip 後 108MB に収めているのか（レビュー後の改訂版）

> 初版（`LOG.md.bak-step4` に保存）をシニアエンジニア視点でレビューし、調査が足りなかった部分を追加調査して書き直した。
> 初版で特に足りなかったのは、(1) 比較対象（ベースライン）が無いこと、(2) Blink の Web API 削除を見落としていたこと、
> (3) Starboard が別の .so であることを見落としていたこと、(4) 名前空間ベースのサイズ内訳が不正確だったこと。

### 4-0. ベースライン: 同じマイルストーン M138 の Chrome との比較

Chrome for Testing（CfT）138.0.7204.183 の linux64 版を入手して比べた。CfT は公式ビルドの Chrome だが、配布版の Chrome と完全に同じ構成かは未確認。

```bash
curl -s https://googlechromelabs.github.io/chrome-for-testing/known-good-versions-with-downloads.json  # 138 系の最新を選ぶ
curl -O https://storage.googleapis.com/chrome-for-testing-public/138.0.7204.183/linux64/chrome-linux64.zip
readelf -SW chrome-linux64/chrome
```

| | Chrome 138（CfT） | Cobalt 27.lts.13（gold, strip 後） |
|---|---|---|
| 本体 | `chrome` **254.5MB**（`file` の結果: stripped） | `cobalt` **108.8MB** |
| `.text` | 197.0MB | 82.3MB |
| `.rodata` | 20.1MB | 12.8MB（ICU データ 6.6MB を含む） |
| `.rela.dyn` | 22.1MB | 8.9MB |
| `.data.rel.ro` | 10.1MB | 3.9MB |
| `.eh_frame` | 3.2MB | 0.1MB |
| ICU データ | 別ファイル `icudtl.dat` 10.0MB | 埋め込み 6.6MB |
| その他の主な同梱物 | `resources.pak` 11.2MB、`libGLESv2.so` 6.3MB、`libvk_swiftshader.so` 4.5MB、Widevine 17.9MB | `starboard/libstarboard.so.18` **7.0MB**（strip 後）、`cobalt_shell.pak` 1.3MB |

- 実行コードの `.text` で比べると **Cobalt は Chrome の約 42%**（82.3 / 197.0）。
- 「108MB」と言うときは、**別ファイルの `libstarboard.so` 7.0MB が含まれていない**点に注意（4-4 を参照）。

### 4-1. サイズ内訳（DWARF のコンパイル単位で集計）

初版はシンボル名の名前空間で分類していたため、C 言語やアセンブリのコードを分類できなかった（16% が「不明」）。
改訂版では、`symbol_level=1` で残っている DWARF の compile unit（ソースファイルのパス）ごとにアドレス範囲を集計した。
`.text` 82.3MB のうち 79.1MB をソースに対応付けられた。

```bash
third_party/llvm-build/Release+Asserts/bin/llvm-dwarfdump --debug-info --recurse-depth=0 out/linux-x64x11_gold/cobalt \
  | python3 cu_attr.py    # CU の DW_AT_name ごとに、DW_AT_low_pc/high_pc・DW_AT_ranges の区間を重複なしで合計する
```

| ソースのディレクトリ | サイズ | 割合 |
|---|---|---|
| `v8` | 15.39MB | 19.5% |
| `third_party/blink/renderer/core` | 11.93MB | 15.1% |
| `gen/third_party/blink`（ビルド時に生成されるコード。中身は未分類） | 5.90MB | 7.5% |
| `content` | 5.74MB | 7.3% |
| `third_party/skia` | 4.35MB | 5.5% |
| `third_party/blink/renderer/modules` | 3.91MB | 4.9% |
| `net` | 2.98MB | 3.8% |
| `third_party/blink/renderer/platform` | 2.48MB | 3.1% |
| `ui` / `cc` / `third_party/icu` / `gpu` / `media` / `base` / `components/viz` | 各 1.0〜2.0MB | |
| `third_party/angle` | 0.61MB | 0.8% |
| `third_party/webrtc` | 0.19MB | 0.2% |
| `cobalt/*` の合計 | 約 0.35MB | 0.4% |

- 注意: ThinLTO でインライン化されたコードは、インライン先の compile unit に数えられる。ディレクトリごとの値は目安。
- Blink 全体（core、modules、platform、bindings、生成コード）で約 24.6MB、V8 が 15.4MB。**この 2 つで .text の約半分**。

### 4-2. 要因 A: `//chrome` を使わず、`//content` の上に専用の shell を作っている

- `gn desc out/linux-x64x11_gold //cobalt:cobalt deps --all` → 9,244 ターゲットのうち、**`//chrome/` は 0 個**。
- `cobalt/shell/browser/shell_content_browser_client.cc` や `cobalt/browser/cobalt_content_browser_client.cc` などで、Content API を直接実装している。
- `enable_extensions` / `enable_pdf` / `enable_glic` などは true のままだが、実際にリンクされるのは `//pdf:buildflags` ぐらい。
  ただし **`enable_printing` は効いていて**、`//printing:printing` など 26 ターゲットがリンクされる（`printing::` のシンボルは 8 個）。
- ベースラインとの `.text` の差 114.7MB のうち、どれだけがこの要因によるかは**未計測**。
  同じツリーで `//chrome` を含む構成をビルドして比べる必要がある。

### 4-3. 要因 B: Blink の Web API を、モジュール単位とバインディング単位で削っている（初版で見落としていた）

**1) Blink の sub_modules から除外**（`third_party/blink/renderer/modules/BUILD.gn:190` 付近、`:239` 付近）

```gn
if (is_cobalt) {
  sub_modules -= [
    ".../modules/mediarecorder", ".../modules/ml", ".../modules/webgpu", ".../modules/xr",
    ".../modules/bluetooth", ".../modules/hid", ".../modules/nfc", ".../modules/serial", ".../modules/webusb",
  ]
  ...
}
if (!use_webrtc_peer_connection) { sub_modules -= [ ".../modules/peerconnection" ] }   # = !is_cobalt
if (is_cobalt) { sub_modules -= [ ".../modules/ai" ] }
```

- `third_party/blink/public/public_features.gni:17`: `use_webrtc_peer_connection = !is_cobalt` → 実際の値は false（`gn args --list` で確認）。
- deps で確認すると、`modules/{xr,ml,webgpu,webusb,bluetooth,serial,hid,mediarecorder,peerconnection}` はどれも **0 ターゲット**。
- 除外したモジュールを参照している箇所のリンクを通すため、`modules/cobalt_modules_stubs.cc`（493 行）に `XRSystem`、`GPU*`、`DawnObjectBase` などのスタブがある。

**2) 生成される V8 バインディングをファイル名のパターンで除外**（`third_party/blink/renderer/bindings/bindings.gni:266` 以降）

- `cobalt_bindings_exclude_patterns`: `*_rtc_*`、`*peer_connection*`、`*v8_media_recorder.*` など。
  `enable_privacy_sandbox_apis = !is_cobalt`（`cobalt/build/cobalt.gni:29`）のため、`*ad_auction*`、`*browsing_topic*`、`*federated_credential*` なども除外される。
- `cobalt_hardware_exclude_patterns`: `*v8_bluetooth*`、`*v8_hid_*`、`*v8_serial_*`、`*v8_usb_*`、`*v8_ndef*`
- `cobalt_webgpu_exclude_patterns`: `*v8_gpu_*`、`*v8_ml_*`、`*v8_xr_*`
- `cobalt_ai_exclude_patterns`: `*v8_translator*`、`*v8_summarizer*`、`*v8_language_model*` など
- 適用している箇所: `bindings/BUILD.gn:278,416`、`bindings/core/v8/BUILD.gn:29,60`、`bindings/modules/v8/BUILD.gn:30,37`（`filter_exclude`）
- 削減量は**未計測**。

**3) Cobalt 独自のモジュールを追加**: `modules/cobalt/h5vcc_*`（13 個）、`cobalt/encryptedmedia`、`cobalt/mediasource`（`use_starboard_media` の場合）

### 4-4. 要因 C: メディアと描画はプラットフォーム層（Starboard）に任せ、Starboard は別の .so にする（初版で見落としていた）

- `ldd out/linux-x64x11_gold/cobalt` → `starboard/libstarboard.so.18` に依存している（strip 前 21.6MB、**strip 後 7.0MB**）。
- Chromium 側の設定は `media_use_ffmpeg=false`、`media_use_libvpx=false`、`enable_dav1d_decoder=false`。
  ただし deps には dav1d（7 ターゲット）と libvpx（11 ターゲット）が残っている。
  `gn path` で調べると、どちらも `//starboard/linux/x64x11/shared:starboard_platform(//starboard/linux/x64x11/toolchain:starboard)` 経由
  （`starboard/linux/x64x11/shared/BUILD.gn:23,25`）。
  → Linux 用のリファレンス実装である Starboard が、**`libstarboard.so` の中にソフトウェアデコーダとして持っている**
  （`nm` で dav1d / vpx / vp9 のシンボルが 11,049 個ある）。`cobalt` 本体には dav1d / libvpx の compile unit は無い。
- `libstarboard.so` に入っている文字列 `libavcodec.so`、`libde265.so`、`libopenh264.so`、`libpulse.so` と、
  `starboard/linux/shared/BUILD.gn:27` の `ffmpeg_dynamic_load` から、**システムの ffmpeg などを実行時に dlopen** していると判断した。
  ログに出た `pulse_audio` スレッドも、これで説明がつく（Chromium 側は `use_pulseaudio=false`）。
- つまり「デコードを SoC に任せる」は、**実機（TV など）で Starboard を移植した場合の話**。
  Linux のリファレンス実装では、Starboard がソフトウェアデコーダとシステムのライブラリを使う。
- 描画: `use_dawn=false`、`enable_vulkan=false`、`enable_swiftshader=false`、`use_static_angle=true`。
  ANGLE はスタティックリンクされていて、そのコードは 0.61MB（Chrome は `libGLESv2.so` 6.3MB と `libvk_swiftshader.so` 4.5MB を別ファイルで持つ）。
  Dawn はヘッダ系のターゲットだけが残っている（`//third_party/dawn/include/dawn:*`、`src/dawn/native:headers`）。

### 4-5. 要因 D: GN 引数での機能削減（`cobalt/build/configs/common.gn`、`linux_common.gn`）

| 分類 | 設定 | deps での確認結果 |
|---|---|---|
| XR | `enable_vr/openxr/arcore/cardboard=false` | `modules/xr` 0 |
| ML | `build_with_tflite_lib=false`、`webnn_use_tflite=false`、`build_tflite_with_xnnpack=false` | `//third_party/tflite` は `:buildflags` の 1 個だけ |
| キャプチャ / リモート | `enable_screen_capture=false`、`enable_remoting=false`、`enable_media_remoting(_rpc)=false` | 未確認 |
| Linux デスクトップ | `use_gtk/gio/glib/dbus/udev/cups/kerberos/pulseaudio/alsa/xkbcommon/qt5=false`、`ozone_platform="starboard"` | `ldd` に GTK / GLib / D-Bus は無い（X11 と ALSA は Starboard が使う） |
| 個別の削減（**Cobalt のコメントに書かれている値で、こちらでは未計測**） | HSTS プリロードリスト（-1.3MB）、ANGLE Vulkan（-1.2MB）、BackupRefPtr（-0.5MB）、WebRTC 内の dav1d（-533KB）、Rust PNG（-0.1MB）、V8 snapshot 圧縮（-167KB） | |
| unwind テーブル | gold は `exclude_unwind_tables` を指定しないので official build のデフォルト | `.eh_frame` は 0.1MB（Chrome は 3.2MB） |

### 4-6. 要因 E: ICU データを YouTube 向けに絞り込んでいる（初版で見落としていた）

- `third_party/icu/BUILD.gn:446` に `if (is_cobalt) { data_dir = "cobalt" }` がある。
- 使われるのは `third_party/icu/cobalt/icudtl.dat`（**6.62MB**）。Chrome は `common/icudtl.dat`（9.98MB）。
- バイナリの中では、`icudt74_dat` から `.rodata` の次のシンボル `v8_Default_embedded_blob_data_` までが 6.62MB で、ファイルサイズと一致する。
- `third_party/icu/cobalt/README.md` より: 「YouTube の UI 82 言語をサポートしつつ、`third_party/icu/filters/cobalt.json` でロケール、通貨、照合、タイムゾーンを絞り込む」。
  `scripts/make_data_assembly.py` でアセンブリにしてバイナリに埋め込んでいる。

### 4-7. 要因 F: コンパイラとリンカの設定

- `optimize_for_size=true` → Linux では `-Os`（`build/config/compiler/BUILD.gn` の `else if (optimize_for_size || is_chromeos)`。Fuchsia だけ `-Oz`）。
  Rust は `-Copt-level=s`。
- `use_thin_lto=true`、`use_icf=true`、`chrome_pgo_phase=0`、`is_cfi=true`（`gn args --list` で確認）。
- それぞれの効果量は未計測。

### 4-8. Chromium 本体へのパッチの規模

- `cobalt/` と `starboard/` 以外で、Cobalt 用の分岐があるファイルは 1,040 個。
  `BUILDFLAG(IS_COBALT)` 1,351 回、`BUILDFLAG(IS_STARBOARD)` 1,072 回、`BUILDFLAG(USE_STARBOARD_MEDIA)` 1,028 回。
- 内訳: blink 177、content 140、media 114、base 105 ...
- 「サイズ削減ではなく移植のための変更が中心」というのは**抜き取り確認による印象**で、全数は分類していない。

### 4-9. レビューで残った課題（未計測・未検証のもの）

1. 要因ごとの寄与度。`//chrome` の有無、Blink モジュールの除外、GN 引数のそれぞれを on/off してビルドし、差分を測る必要がある。
2. Cobalt のコメントに書かれている削減量（HSTS -1.3MB など）が本当か。
3. CfT と配布版の Google Chrome が同じ構成か。
4. `.rela.dyn` の差（8.9 vs 22.1MB）は、主にコード量とデータ量の違いによると考えている。RELR などの方式の違いは未確認。

### Step 4 まとめ（改訂版）

- 同じ M138 の Chrome（254.5MB）と比べると、Cobalt 本体は 108.8MB（**約 43%**）。`.text` で比べると約 42%。
  ただし Cobalt は、別ファイルの `libstarboard.so`（7.0MB）を含めて考えるべき。
- 根拠のある削減策:
  1. `//chrome` を使わず `//content` + 専用 shell にしている（`//chrome` ターゲット 0 個）。
  2. Blink の Web API を、モジュール単位と V8 バインディング単位で除外している（WebRTC、WebGPU、WebNN、WebXR、
     Bluetooth / HID / Serial / USB / NFC、MediaRecorder、built-in AI、Privacy Sandbox）。
  3. メディアとプラットフォームの処理を Starboard に分離している（Linux のリファレンス実装ではソフトウェアデコーダと dlopen）。
  4. ICU データを YouTube の 82 言語向けに絞り込んでいる（10.0MB → 6.6MB）。
  5. GN 引数で機能を切り、`-Os`、ThinLTO、ICF を使っている。
- 残っているコードの約半分は Blink と V8。Web プラットフォームの中核は残したうえで、周辺を削っている構成。

---

## Step 5. Web API を削る方法の詳細: Chromium 標準のビルドオプションか、Cobalt のパッチか

### 調べ方

上流 Chromium の同じ M138 ブランチ（`refs/branch-heads/7204`）と、Cobalt のファイルを比べた。

```bash
f=third_party/blink/renderer/modules/BUILD.gn
curl -s "https://chromium.googlesource.com/chromium/src/+/refs/branch-heads/7204/$f?format=TEXT" | base64 -d > upstream.gn
diff -u upstream.gn $f
```

| ファイル | 上流の行数 | Cobalt の行数 | 差分の行数 |
|---|---|---|---|
| `third_party/blink/renderer/modules/BUILD.gn` | 968 | 1125 | 159 |
| `third_party/blink/renderer/bindings/bindings.gni` | 264 | 363 | 99 |
| `third_party/blink/renderer/bindings/idl_in_modules.gni` | 1405 | 1537 | 132 |
| `third_party/blink/renderer/bindings/generated_in_modules.gni` | 3616 | 3736 | 120 |
| `third_party/blink/renderer/bindings/modules/v8/BUILD.gn` | 68 | 98 | 30 |
| `third_party/blink/renderer/bindings/BUILD.gn` | 521 | 535 | 14 |
| `third_party/blink/public/public_features.gni` | 13 | 19 | 6 |
| `third_party/blink/renderer/platform/runtime_enabled_features.json5` | 5740 | 5756 | 16（Cobalt 独自の機能を追加しているだけで、削除は無い） |

キーワードが上流に何回出てくるか（上流 / Cobalt）:

| キーワード | modules/BUILD.gn | bindings.gni | bindings/BUILD.gn | idl_in_modules.gni |
|---|---|---|---|---|
| `is_cobalt` | 0 / 8 | 0 / 1 | 0 / 0 | 0 / 4 |
| `use_webrtc_peer_connection` | 0 / 4 | 0 / 0 | 0 / 2 | 0 / 2 |
| `cobalt_*_exclude_patterns` | 0 / 0 | 0 / 5 | 0 / 2 | 0 / 0 |
| `enable_privacy_sandbox_apis` | 0 / 3 | 0 / 1 | 0 / 0 | 0 / 2 |
| `filter_exclude` | 0 / 3 | 0 / 0 | 0 / 2 | 0 / 4 |

- `modules/cobalt_modules_stubs.cc` は上流に無い（gitiles で HTTP 404）。
- 上流の `modules/BUILD.gn` で、標準のビルド引数によってモジュールを切り替えているのは `enable_compute_pressure` だけ。
  WebXR、WebGPU、WebUSB などを切る標準オプションは無い（`enable_vr=false` にしても `modules/xr` は外れない）。

### 結論: Compute Pressure 以外は、すべて Cobalt が独自に入れたパッチ

| 削除方法 | 対象 | 種類 | 根拠 |
|---|---|---|---|
| ① `sub_modules -= [...]` | mediarecorder、ml（WebNN）、webgpu、xr、bluetooth、hid、nfc、serial、webusb、ai | **Cobalt パッチ**（`if (is_cobalt)`） | `modules/BUILD.gn` の差分 |
| ② 新しい GN 引数 `use_webrtc_peer_connection = !is_cobalt` | peerconnection（WebRTC） | **Cobalt が追加した引数**（上流に無い） | `public/public_features.gni` の差分（+6 行） |
| ③ 新しい GN 引数 `enable_privacy_sandbox_apis = !is_cobalt` | browsing_topics、shared_storage、ad_auction、private_attribution、storage_access、credentialmanagement など | **Cobalt が追加した引数**（`cobalt/build/configs/cobalt.gni:29` で宣言） | `idl_in_modules.gni:1467` の `filter_exclude` |
| ④ IDL ファイルを外す | mediarecorder（`blob_event.idl`、`media_recorder.idl` など） | **Cobalt パッチ** | `idl_in_modules.gni:1347` の `static_idl_files_in_modules -= [...]` |
| ⑤ 生成された V8 バインディングをファイル名パターンで除外 | rtc / peer_connection、bluetooth / hid / serial / usb / ndef、gpu / ml / xr、AI（translator、summarizer など） | **Cobalt パッチ**（`bindings.gni:266` 以降でパターンを定義） | `bindings/modules/v8/BUILD.gn` の差分、`bindings/BUILD.gn:278,416`、`bindings/core/v8/BUILD.gn:29,60` |
| ⑥ スタブ | `GPU::gpu()`、`XRSystem::xr()`、`USB::usb()`、`HID::hid()`、`Serial::serial()`、`Bluetooth::bluetooth()`、`NavigatorML::ml()` などが `return nullptr` | **Cobalt が新しく追加したファイル**（493 行） | `modules/cobalt_modules_stubs.cc:265-300,420` |
| ⑦ GN 引数 `enable_compute_pressure=false` | Compute Pressure API | **Chromium 標準のオプション** | 上流の `modules/BUILD.gn:190,268,649` に `if (enable_compute_pressure)` がある |

### 仕組み: なぜスタブが必要なのか

1. ①で、モジュールの C++ 実装（`modules/webgpu` など）をリンク対象から外す。
2. ただし、WebGPU などの IDL は `idl_in_modules.gni` に残っている（④で外しているのは MediaRecorder だけ）。
   そのため、`partial interface Navigator` などから生成される **`v8_navigator.cc` には `navigator.gpu` などの属性が残る**。
   - 確認: `out/linux-x64x11_gold/gen/.../modules/v8/v8_navigator.cc` に `"usb"`、`"hid"`、`"serial"`、`"xr"`、`"gpu"`、`"bluetooth"`、`"ml"` がある。
   - 例: `v8_navigator.cc:2474` は `if (is_in_secure_context && ... && RuntimeEnabledFeatures::WebUSBEnabled())` の条件で `{"usb", UsbAttributeGetCallback, ...}` を登録する。
3. そのままでは getter が呼ぶ `USB::usb()` などがリンクできないので、⑥のスタブで `nullptr` を返すようにしてリンクを通している。
4. ⑤で、各 API 専用の型（`v8_gpu_*`、`v8_usb_*` など）のバインディングはコンパイル対象から外している。

**つまり、外しているのは「実装」と「API 専用の型のバインディング」で、Navigator などに生えている入口の属性は残っている。**

### JavaScript から見た動作（未検証）

- runtime feature の状態（`runtime_enabled_features.json5`）: WebXR `stable`、WebUSB `stable`、WebHID は `default: stable`、Serial は `default: stable`。
  Cobalt 側で `--disable-blink-features` を使ってこれらを無効にしている箇所は見つからなかった（`cobalt/app/cobalt_switch_defaults*.cc` を確認）。
- ここから、**secure context では `navigator.usb` などが `undefined` ではなく `null` になる可能性が高い**と推定している。
- 実機での確認は**できなかった**。Xvfb 上の gold ビルドで、プローブページ（`'usb' in navigator` などを報告するページ）を開こうとしたが、うまくいかなかった:
  - `--url=` は起動 URL ではなく **deep link** として扱われ、`https://www.youtube.com/tv` が開いた
    （ログ: `H5vccRuntime initial DeepLink: "http://127.0.0.1:8765/index.html"`、`Navigated to https://www.youtube.com/tv`）。
    `setup-linux.md` の「`--url` で起動 URL を指定する」という説明とは動作が違う。
  - 起動 URL は位置引数で渡す（`cobalt/shell/browser/shell_browser_main_parts.cc:103` の `GetStartupURL` が `args[0]` を使う）。
    実際に `Overriding initial URL with first argument` とログに出たが、90 秒待ってもページへのリクエストは来なかった。原因は未調査。
  - gold では HTTPS と CSP が強制される（`cobalt_secure_navigation_throttle.cc` の `#if BUILDFLAG(COBALT_IS_RELEASE_BUILD) return true;`）。
    `--https-enforcement=false --csp-enforcement=false` で無効にして試した。

### Step 5 まとめ

- Blink の Web API の削除は、**Compute Pressure を除いて、Chromium 標準のビルドオプションではなく Cobalt のパッチ**で実現されている。
  内容は、上流の GN ファイルへの `if (is_cobalt)` の追加、Cobalt 独自の GN 引数 2 個（`use_webrtc_peer_connection`、`enable_privacy_sandbox_apis`）、
  生成コードをパターンで除外する仕組み、スタブ用の新規ファイル 1 個。
- やり方は「IDL は残し、実装と専用の型のバインディングを外し、入口の getter はスタブで `nullptr` を返す」。
  IDL まで削っているのは MediaRecorder と Privacy Sandbox 系だけ。
- この方式だと、上流の rebase のたびに GN ファイルの差分とスタブを保守する必要がある
  （上流で新しい属性やメソッドが増えると、スタブの追加が必要になる）。保守コストが高い方式と言える（設計上の考察）。

---

## Step 6. 上流 Chromium M138 との全差分（Chrobalt のパッチの全体像）

### 調べ方

```bash
# 上流をそのまま写したブランチ（chromium/m138 = 138.0.7204.311、27.lts.13 と同じバージョン）を取得
git fetch --depth 1 origin refs/heads/chromium/m138:refs/remotes/origin/chromium/m138
git diff --name-status --no-renames origin/chromium/m138 HEAD     # HEAD = 27.lts.13
git ls-tree -r origin/chromium/m138 | awk '$1=="160000"'          # 上流で DEPS 管理（gitlink）になっているパス: 262 個

# Cobalt がリポジトリに取り込んだ依存（DEPS に "# Cobalt: imported" とあるもの）は、
# DEPS に書かれた上流コミットを個別に取得して tree 同士を比較した
git fetch --depth 1 https://chromium.googlesource.com/v8/v8.git <DEPS の sha>:refs/upstream-deps/v8
git diff --numstat refs/upstream-deps/v8^{tree} HEAD:v8
```

- 上流ブランチの取得は、手元にあるオブジェクトを再利用できたので数十秒で終わった。11 個の依存の取得も問題なく完了した（監視でエラーや停滞は無し）。

### 6-1. 全体像

| 区分 | 件数 | 内容 |
|---|---|---|
| 新しく追加したディレクトリ `cobalt/` | 1,671 ファイル | アプリ本体（shell、browser、h5vcc、updater など） |
| 新しく追加したディレクトリ `starboard/` | 2,340 ファイル | 移植レイヤ（Starboard API とプラットフォーム実装） |
| Chromium 本体の **変更** | **1,300 ファイル（+32,398 / −3,046 行）** | 6-2 を参照 |
| Chromium 本体の **追加** | 11,554 ファイル | 6-4 を参照 |
| Chromium 本体の **削除** | 660 ファイル | ほぼ全部 `third_party/google_input_tools`（653 個） |
| DEPS 管理からリポジトリに取り込んだ依存 | 11 個 / 262 個 | 6-5 を参照 |
| DEPS のリビジョンを変えた依存 | 2 個 | `native_client`、`fuzztest` |
| `DEPS` ファイル | +69 / −28 行 | siso を M141 の版に変更、取り込んだ依存のエントリを削除、`src/cobalt/internal` と `src/third_party/internal`（非公開。デフォルトでは checkout しない）を追加 |

**変更は追加が中心**（+32k / −3k）。上流のコードを書き換えるのではなく、`#if` で分岐を足していく方針と読める。

### 6-2. 変更 1,300 ファイルの分類

`git diff -U0` で各ファイルの追加行を見て、どのフラグや識別子で分岐しているかで分類した
（判定は上から順に当てはめる。キーワードによる機械的な分類）。

| 分類 | ファイル数 | 判定に使ったキーワード |
|---|---|---|
| Starboard への移植 | 386 | `STARBOARD`、`is_starboard`、`use_starboard`、`Sb*()` |
| Cobalt 固有の動作 | 376 | `IS_COBALT`、`is_cobalt`、`cobalt/` |
| テスト | 205 | パスに `_test`、`_unittest`、`/test/` などを含む |
| hermetic ビルド（musl など） | 128 | `HERMETIC`、`is_cobalt_hermetic_build`、`musl` |
| 上記の目印が無い | 202 | 下の表で内訳を確認 |
| Android | 3 | |

「目印が無い」202 ファイルの内訳:

| 内訳 | ファイル数 | 例 |
|---|---|---|
| Privacy Sandbox の無効化 | 55 | `content/browser/browser_context_impl.cc`、`client_hints.cc` |
| jni_zero / Android | 23 | `base/android/jni_android.cc` |
| tvOS / iOS への移植 | 22 | `base/message_loop/message_pump_io_ios.cc`、`content/shell/browser/shell_platform_delegate_ios.mm` |
| build / tools | 18 | `build/config/rust.gni` |
| crashpad | 11 | `crash_report_upload_thread.cc` |
| WebRTC / MediaRecorder の除外 | 7 | `v8_script_value_serializer_for_modules.cc` |
| その他 | 66 | 抜き取りで見ると、多くは Cobalt が独自に定義したフラグで分岐していた（例: `base/containers/flat_tree.h` は `BUILD_BASE_WITH_CPP17`、`components/crx_file/crx_verifier.cc` は `IN_MEMORY_UPDATES`、`net/socket/udp_socket_posix.cc` は `ENABLE_MULTI_PACKETS_PER_CALL_QUIC_OPTIMIZATIONS`） |

### 6-3. パッチで使われているフラグ（上流には無いもの）

変更ファイルの追加行に出てくる `BUILDFLAG(X)`、`defined(X)`、`#ifdef X` を数えた（全 83 種類）。
上位のうち、上流の `*.h`、`*.cc`、`*.gn`、`*.gni`、`*.py` に一度も出てこないもの:

| フラグ | 出現回数 | 意味 |
|---|---|---|
| `IS_COBALT` | 1,263 | Cobalt のビルド |
| `USE_STARBOARD_MEDIA` | 956 | メディア処理を Starboard 経由にする |
| `ENABLE_PRIVACY_SANDBOX_APIS` | 713 | Privacy Sandbox の有効 / 無効 |
| `IN_MEMORY_UPDATES` | 247 | updater（Evergreen）向け |
| `IS_COBALT_HERMETIC_BUILD` | 167 | musl などを使う hermetic ビルド |
| `USE_WEBRTC_PEER_CONNECTION` | 95 | WebRTC の有効 / 無効 |
| `ENABLE_DEVTOOLS_BACKEND` | 63 | DevTools |
| `IS_NATIVE_TOOLCHAIN` / `SB_IS_DEFAULT_TC` / `IS_STARBOARD_TOOLCHAIN` | 58 / 22 / 6 | 複数のツールチェーンの切り替え |
| `COBALT_DETAILED_MEMORY_METRICS` | 45 | |
| `ENABLE_COBALT_HERMETIC_HACKS` | 22 | |
| `BUILD_BASE_WITH_CPP17` | 20 | C++17 で base をビルドする（partner ツールチェーン用） |
| `IS_ANDROIDTV` | 15 | |

- `IS_STARBOARD`（694 回）も Cobalt が定義している（`build/build_config.h:296` の `BUILDFLAG_INTERNAL_IS_STARBOARD`）。
  上流にも `IS_STARBOARD` という文字列はあるが、`ui/ozone/platform/cast/BUILD.gn:36` の `defines += [ "IS_STARBOARD" ]` だけで、別物。

### 6-4. 本体に追加した主なディレクトリ（11,554 ファイル）

| ディレクトリ | ファイル数 | 用途（根拠） |
|---|---|---|
| `third_party/llvm-project` | 4,221 | `compiler-rt` と `libunwind` だけ（`ls` で確認）。hermetic ビルド用とみられる |
| `copied_base/base` | 3,370 | **//base のもう一つのコピー**。`base/BUILD.gn:188-193`: `is_cobalt && is_partner_toolchain` のときは `//copied_base/base` を使う。partner ツールチェーン = libstarboard.so をビルドする "starboard" / "native_target" ツールチェーン（`starboard/build/config/toolchain_variables.gni:30-36`）。中身は //base と同一 496、差分あり 2,210、コピー側にしかないもの 664。どの時点の //base をコピーしたかは未確認 |
| `third_party/musl` | 2,650 | musl libc（hermetic ビルド用） |
| `third_party/ffmpeg_includes` | 654 | ffmpeg / libav の複数バージョンのヘッダ（Starboard がシステムの ffmpeg を dlopen するため） |
| `third_party/blink` | 219 | Cobalt 独自の Blink モジュール（`modules/cobalt/*`）など |
| `media` | 89 | Starboard 向けのメディア実装 |
| `third_party/pulseaudio_includes` | 34 | PulseAudio のヘッダ（dlopen 用） |
| `third_party/lz4_lib` | 18 | |
| `.github`、`agents` | 66、45 | CI、AI コーディングエージェントのプロンプト（`agents/README.md`） |

### 6-5. 取り込んだ（vendor した）依存 11 個と上流との差分

| 依存 | 上流のコミット（DEPS） | M | A | D | +行 | −行 | 備考 |
|---|---|---|---|---|---|---|---|
| v8 | c6ef3038bf | 45 | 1 | 1 | 242 | 1006 | 上流 V8 の `src/base/platform/platform-starboard.cc`（506 行、旧 Cobalt 時代の Starboard 対応）を**削除**。`gni/v8.gni`、`BUILD.gn`、`src/base/cpu.cc` を変更 |
| third_party/webrtc | 7ad61a0a06 | 13 | 1 | 0 | 15949 | 15802 | ±15,789 行は CSV 1 ファイルの改行コードの違い（`--ignore-cr-at-eol` で差分が消える）。実質は `internal_encoder_factory_starboard_stub.cc` の追加など |
| third_party/skia | 9d9ac365fe | 12 | 1 | 0 | 991 | 694 | ±666 行は JSON の改行コードの違い。`SkStream.cpp` などを変更 |
| third_party/icu | b929596bae | 3 | 4 | 0 | 1890 | 2 | `filters/cobalt.json`（1,758 行）、`scripts/make_data_cobalt.sh`、`cobalt/` を追加 |
| net/third_party/quiche/src | 3b42119c3e | 12 | 0 | 0 | 111 | 2 | |
| third_party/angle | 4664989d81 | 9 | 0 | 0 | 65 | 1 | |
| third_party/googletest/src | 09ffd00153 | 3 | 0 | 0 | 70 | 3 | |
| third_party/boringssl/src | 9295969e1d | 5 | 0 | 0 | 11 | 2 | |
| third_party/perfetto | dd35b295cd | 5 | 0 | 0 | 10 | 5 | |
| third_party/cpuinfo/src | 39ea79a3c1 | 1 | 0 | 0 | 10 | 0 | |
| third_party/libc++/src | a01c02c9d4 | 1 | 0 | 0 | 1 | 1 | |

→ 依存側のパッチは改行コードの違いを除くと小さく、**中心は Chromium 本体の 1,300 ファイルと、新しく追加したディレクトリ**。

### Step 6 まとめ

Chrobalt の上流 M138 に対するパッチは、次の 5 層に分けられる。

1. **新しいコード**: `cobalt/`（1,671 ファイル）、`starboard/`（2,340 ファイル）
2. **Chromium 本体への `#if` 分岐の追加**: 1,300 ファイル、+32k 行。
   Cobalt が独自に定義したフラグ（`IS_COBALT`、`IS_STARBOARD`、`USE_STARBOARD_MEDIA`、`ENABLE_PRIVACY_SANDBOX_APIS`、`IS_COBALT_HERMETIC_BUILD` など）で分岐している。
   分類すると、Starboard への移植 386、Cobalt 固有の動作 376、テスト 205、hermetic ビルド 128、Privacy Sandbox の無効化 55、tvOS 22 など。
3. **hermetic ビルド用の環境**: `copied_base`（//base のフォーク）、`musl`、`llvm-project`（compiler-rt と libunwind）、ffmpeg / pulseaudio のヘッダ
4. **依存の取り込み**: 11 個をリポジトリに取り込み、パッチは小さい（V8 は上流の Starboard 対応を削除）
5. **DEPS / ツール**: siso の版を上げ、非公開の internal リポジトリを追加

別のバージョンへ rebase するときに一番大きな作業になるのは、2 の 1,300 ファイルの衝突解消と、`copied_base` を追従させるかどうかの判断になる（設計上の考察）。

### 残った課題（1 のうち未実施のもの）

- 分類はキーワードによる機械的なもの。各カテゴリの中身（どの機能をどう差し替えているか）は抜き取りでしか読んでいない。
- `copied_base` がどの時点の //base のコピーか（C++17 で使うための古い版なのか）は未確認。
- 1,300 ファイルのうち、上流の新しい版で既に取り込まれている「先取りの backport」がどれだけあるかは未確認。
- 非公開の `src/cobalt/internal`、`src/third_party/internal` の中身は見られない。

---

## Step 7. Step 6 の残課題の解決と、ROM 削減フラグは明示的か

### 7-1. 各カテゴリの中身（どのサブシステムに手を入れているか）

変更ファイルを Step 6 の分類ごとにディレクトリで集計し、追加行が多いファイルを挙げた（`backport.json` の追加行数）。

| 分類 | 主なディレクトリ（ファイル数） | 追加行の多いファイル |
|---|---|---|
| Starboard への移植（386） | blink/renderer 53、viz/service 10、media/mojo/mojom 10、media/mojo/services 10、crashpad 10、media/formats/webm 8、media/mojo/clients 7、base/task/sequence_manager 6、content/renderer/media 6 | `media/formats/mp4/mp4_stream_parser.cc` +287、`base/threading/hang_watcher.cc` +260、`media/formats/webm/webm_cluster_parser.cc` +247、`webm_stream_parser.cc` +233、`blink/.../mediasource/source_buffer.cc` +192、`components/update_client/url_fetcher_downloader.cc` +160 |
| Cobalt 固有の動作（376） | blink/renderer 81、content/browser/devtools 18、gpu/command_buffer/service 12、content/browser/renderer_host 10、content/public/browser 9、service_worker 7、resource_coordinator 7、cc/tiles 5 | `render_widget_host_view_tvos_uiview.mm` +448、`cc/paint/image_transfer_cache_entry.cc` +172、`gpu/.../raster_implementation.cc` +164、`blink/.../highest_pmf_reporter.cc` +133、`raster_decoder.cc` +126 |
| hermetic（128） | blink/renderer 8、partition_allocator 7、abseil 6、crashpad 5 | `os_metrics_linux.cc` +464、`allocator_shim_default_dispatch_to_partition_alloc.cc` +65、`ui/gl/gl_context_egl.cc` +51、`build/build_config.h` +39 |

- **Starboard への移植**の中心はメディア。MSE / MP4 / WebM のパーサ、Mojo のメディアサービス、SourceBuffer を Starboard の再生パイプラインにつないでいる。
- **Cobalt 固有の動作**の中心は、tvOS の描画、GPU のラスタ処理（コメントにある「in-process direct raster」の高速化）、DevTools、メモリの計測。
- **hermetic** は、musl 環境でのアロケータ、メモリ計測、EGL。
- 読み方の根拠になったコメントの例（追加行のうち Cobalt / Starboard に触れているコメントは 491 行、バグ ID は 74 種類）:
  - `media`: 「Cobalt uses the Starboard layer instead of AAudio. AAudio also breaks SDK 24 compatibility. See b/508072838.」
  - `content`: 「Starboard doesn't support video input.」、「bypass Chromium's a11y」（b/391708407）
  - `components/update_client`: 「On Starboard the download-stage free-space check is compiled out by design」
  - `gpu`: 「Fast path for Cobalt in-process direct raster.」
- 制約: ここで分かったのは「どのファイルにどれだけ手を入れたか」と「コメントが示す意図」まで。1,300 ファイルの hunk を全部読んだわけではない。

### 7-2. `copied_base` はどの版の //base か → **前の世代 Cobalt 26（Chromium M114）の base**

```bash
git ls-tree -r HEAD copied_base/base                                     # Cobalt 側の blob hash
gh api repos/youtube/cobalt/git/trees/<base の tree sha>?recursive=1     # 各ブランチの base/ の blob hash
```

| 比較先 | パスが一致 | **blob も同一** |
|---|---|---|
| 上流 `chromium/m114`（114.0.5735.359） | 3,344 | 3,127 |
| 上流 `chromium/m120` | 2,879 | 1,856 |
| 上流 `chromium/m126` | 2,773 | 1,028 |
| 上流 `chromium/m132` | 2,730 | 831 |
| 上流 `chromium/m138` | 2,687 | 488 |
| Cobalt `26.android` の base | 3,353 | 3,161 |
| **Cobalt `26.eap` の base** | **3,361** | **3,208**（3,370 ファイル中） |

→ `copied_base/base` は **Cobalt 26.eap（M114 版 Chrobalt）の `base/` をコピーし、その後に約 160 ファイルを変更したもの**。
libstarboard.so をビルドする partner ツールチェーンでは、M138 の //base ではなく、この **M114 時代の base** を使っている
（C++17 でビルドするための `BUILD_BASE_WITH_CPP17` フラグとも合う）。

### 7-3. 1,300 ファイルのうち、上流で既に取り込まれている「先取りの backport」はどれだけか

方法: 各ファイルについて、Cobalt が追加した行（12 文字以上で、括弧やコメントだけの行は除く）のうち何割が、
上流の新しい版（`chromium/m144` = 144.0.7559.259、`chromium/main` = 152.0.7977.0）の同じファイルに既にあるかを数えた。
Cobalt 独自フラグなどの「目印」の有無と組み合わせた（`backport.py`。対象は追加行のある 1,281 ファイル）。

| main（M152）に既にある割合 | 目印あり | 目印なし |
|---|---|---|
| 80% 以上（ほぼ取り込み済み） | 1 | **65** |
| 30〜80% | 155 | 20 |
| 30% 未満（Cobalt にしか無い） | **934** | 76 |
| 上流でファイル自体が無くなった | 30 | 0 |

- **backport とみられるのは約 66 ファイル**（目印なしで 80% 以上が上流にある）。
  多いのは tvOS / iOS への移植（`shell_platform_delegate_ios.mm` 98 行、`keyboard_code_conversion_ios.mm` 63 行、`base/process/launch_mac.cc`、
  `message_pump_io_ios.cc`、`audio_session_manager_ios.mm`）と jni_zero。ほとんどは M144 の時点で既に上流にある。
  → Cobalt チームが **tvOS 対応を上流 Chromium に入れ、それを M138 に backport している**と読める
  （Step 2 で見た `BACKPORT: [tvOS] ...` というコミットとも合う）。
- **Cobalt にしか無い、恒久的なパッチは約 934 ファイル**。rebase のたびに持ち越す必要がある本体はここ。
- **30 ファイルは上流で削除されたか移動している**（例: `base/task/sequence_manager/thread_controller_impl.cc`、`base/base_switches.cc`）。
  rebase では、パッチの移し先を探す必要がある。
- 制約: 行単位の一致で数えているので、一般的な行（include など）は偶然一致することがある。30〜80% の 175 ファイルは個別に確認が必要。

### 7-4. 非公開の internal リポジトリ

- DEPS: `src/cobalt/internal`（`https://lbshell-internal.googlesource.com/cobalt/internal.git@0f7f447f...`）と
  `src/third_party/internal`（`@main`）。どちらも `condition: 'checkout_cobalt_internal'` で、デフォルトは `False`（DEPS:84）。
- 公開側から参照しているもの（中身は見られないので、参照のパスから判断）:
  - `//third_party/internal/ce_cdm/...`: Widevine CE CDM と OEMCrypto（`starboard/shared/widevine/BUILD.gn`）
  - `//cobalt/internal/starboard/shared/widevine/internal/wv_keybox.cc`: Widevine のキーボックス
  - `//cobalt/internal/third_party/platform_drm`、`cobalt/components/cdm/...`: プラットフォームの DRM
  - `//cobalt/internal/starboard/shared/tvos/tvos.gni`: tvOS の設定
- 公開ビルドでは `is_internal_build=false`（`COBALT_USE_INTERNAL_BUILD` 環境変数で切り替え。`initialize_variables.gni:24`）なので、
  `starboard/linux/shared/BUILD.gn:264` の分岐で **DRM はスタブ**（`starboard/shared/stub/drm_*.cc`）になる。
  → **公開ソースから作った Chrobalt では Widevine で保護されたコンテンツは再生できない**と判断した（実行しての確認はしていない）。

### 7-5. ROM 削減のフラグは明示的か、埋もれているか

結論: **明示的なのは一部だけ。大部分は上流ファイルへのパッチの中に埋もれている。** 3 段階に分けられる。

**(a) 明示的 — Cobalt の設定ファイル（`cobalt/build/configs/*.gn`）に書かれた引数**

- `common.gn` と `linux_common.gn` にある `enable_*`、`use_*`、`optimize_for_size` など。Step 4-5 の表のとおりで、
  一部には削減量のコメントも付いている（HSTS -1.3MB など）。
- `gn args out/... --list` に出てくるし、`args.gn` で上書きもできる。

**(b) 半分埋もれている — 上流の `declare_args` のデフォルト値を `is_cobalt` などで変えているもの（16 個）+ Cobalt 独自の引数**

```
third_party/blink/public/public_features.gni: use_webrtc_peer_connection = !is_cobalt
device/bluetooth/emulation/buildflags.gni:    enable_bluetooth_emulation = !is_cobalt && (...)
net/BUILD.gn:                                 enable_built_in_dns = use_blink && !is_starboard
net/BUILD.gn:                                 enable_unix_sockets = (is_posix && !is_starboard) && !is_ios
content/public/common/zygote/features.gni:    use_zygote = ... && !is_cobalt_hermetic_build
build_overrides/angle.gni:                    angle_enable_vulkan_validation_layers = !is_starboard
build_overrides/tint.gni:                     tint_build_benchmarks = !is_starboard
（ほか 9 個）
cobalt/build/configs/cobalt.gni:29:           enable_privacy_sandbox_apis = !is_cobalt
```

- 引数としては存在するので上書きはできる。ただし、**Cobalt の設定ファイルには書かれていない**ので、設定ファイルを読むだけでは気付けない。
- **注意（落とし穴）**: `gn args out/linux-x64x11_gold --list=enable_privacy_sandbox_apis` は
  `Current value (from the default) = true` と表示する。しかし実際のビルドでは無効になっている:
  - `obj/**/*.ninja` のどこにも `-DENABLE_BUILDFLAG_ENABLE_PRIVACY_SANDBOX_APIS` が無い（`cobalt/build/configs/shared/BUILD.gn:28-29` で、true のときだけ付ける）。
  - `blink/modules/{browsing_topics,shared_storage,ad_auction,private_attribution,storage_access,credentialmanagement}` の依存はどれも 0 ターゲット。
  - 原因は、同じファイルの別の `declare_args` で宣言した `is_cobalt` を参照するデフォルト値を、`gn args --list` が上書き前の値で評価しているためと**推定**（GN の仕様は未確認）。
  - → **`gn args --list` を見るだけでは、ROM 削減の状態を正しく把握できない場合がある。**

**(c) 完全に埋もれている — 引数では制御できない、ハードコードされた `if (...) { xxx -= [...] }`**

- 上流の GN ファイルへのパッチで追加された `-=` は **143 箇所**（`sources` 77、`deps` 49、`public_deps` 9、`sub_modules` 4 など、86 ファイル）。
  テスト以外で削られている依存のエントリは **87 個**。
- ガード条件ごとの件数（hunk の中で直前にある `if` で判定した近似値）:

| ガード条件 | 件数 | 引数で戻せるか |
|---|---|---|
| `if (is_cobalt)` | 45 | **戻せない**（Cobalt である限り常に有効） |
| `if (is_cobalt_hermetic_build)` | 17 | 戻せない |
| `if (!enable_privacy_sandbox_apis)` | 10 | 戻せる（Cobalt 独自の引数） |
| `if (is_starboard)` | 6 | 戻せない |
| `if (!enable_devtools_backend)` / `!enable_devtools_frontend` | 6 / 4 | 戻せる |
| `if (!use_webrtc_peer_connection)` | 4 | 戻せる（Cobalt 独自の引数） |
| その他（`use_dawn`、`is_linux` など） | 残り | |

- `if (is_cobalt)` で常に削られる主なもの:
  - Blink の WebGPU / WebNN / WebXR / Bluetooth / HID / NFC / Serial / USB / MediaRecorder / AI モジュール（Step 5）
  - `//components/language_detection/*`、`//third_party/cld_3`、`//third_party/ced`（言語検出、文字コード判定）
  - `//services/on_device_model/*`（オンデバイス AI）
  - `//device/bluetooth`、`//services/device/usb/mojo`
  - `//third_party/flac`（`media/audio/BUILD.gn`）
  - `//components/services/font`
  - `//services/metrics/public/cpp:ukm_builders`（resource_coordinator から）
- このほか、生成コードのパターン除外（Step 5 の `cobalt_*_exclude_patterns`）と、ICU データの切り替え（`third_party/icu/BUILD.gn:446` の `if (is_cobalt) { data_dir = "cobalt" }`）も、ハードコードされている。

### Step 7 まとめ

| 残課題 | 結果 |
|---|---|
| カテゴリの中身 | Starboard への移植はメディア（パーサ、MSE、Mojo）が中心。Cobalt 固有の動作は tvOS の描画、GPU のラスタ処理、DevTools、メモリ計測。hermetic はアロケータ、メモリ計測、EGL |
| `copied_base` の由来 | **Cobalt 26.eap（M114）の `base/`**（3,370 ファイル中 3,208 が blob 一致） |
| backport | 約 66 ファイル（主に tvOS / iOS と jni_zero。Cobalt が上流に入れたものを M138 に先取り）。恒久的なパッチは約 934 ファイル。30 ファイルは上流で消えている |
| internal リポジトリ | Widevine CE CDM、OEMCrypto、キーボックス、プラットフォーム DRM、tvOS の設定。公開ビルドでは DRM はスタブになる |
| ROM 削減フラグ | 明示的なのは Cobalt 設定ファイルの引数だけ。上流のデフォルトを変えたものが 16 個以上、ハードコードされた `-=` が 143 箇所（そのうち `is_cobalt` / `is_starboard` / `hermetic` のように引数で戻せないものが約 70 件）。`gn args --list` の表示と実際の設定が食い違う引数もある |

---

## Step 8. strip したリリース版（gold）の RAM 使用量（起動時 / 動画再生時）

### 8-0. DevTools を使わなかった理由

- `content/browser/devtools/features.gni`:
  `enable_devtools_backend = enable_devtools_frontend || !(is_cobalt && cobalt_is_release_build)`
  → gold では false。`declare_args` ではない普通の変数なので、GN 引数で上書きもできない。
  `obj/content/browser/browser.ninja` にも DevTools backend の define は無い。
- そこで、DevTools は使わずに次の方法で計測した:
  - 操作: 起動時の deep link（`--url=https://www.youtube.com/tv#/watch?v=<動画ID>`）で動画を直接開く。キー操作は不要だった。
  - 計測: `/proc/<pid>/smaps_rollup` をプロセスツリー全体について 1 秒ごとに集計（`mem_sample.py`）。
    内訳は `/proc/<pid>/smaps` をマッピングごとに分類して出した（`smaps_breakdown.py`）。
  - 表示: Xvfb（`:99`、1920x1080x24）。30 秒ごとにスクリーンショットを撮って、画面の状態を確認した（`run_mem.sh`）。

### 8-1. 実行環境

- `~/chrobalt/run-gold/` に strip した `cobalt`（108.8MB）と `libstarboard.so.18`（7.0MB）を置き、pak / ssl / resources / locales はビルド出力へのシンボリックリンクにした。
  - `cobalt` の RPATH は `$ORIGIN:<out>/starboard` なので、strip した `libstarboard.so.18` を `$ORIGIN` に置いて、そちらが使われるようにした（`ldd` で確認）。
- 注意: Xvfb には GPU が無いので、描画は Mesa のソフトウェアレンダラになる（`libEGL warning: DRI3 error` が出る）。
  動画も dav1d のソフトウェアデコード。**テレビなどの実機（ハードウェアデコード + GPU）とは、メモリの使われ方が大きく違う。**

```bash
~/chrobalt/run_mem.sh startup 180
~/chrobalt/run_mem.sh playback 240 --url='https://www.youtube.com/tv#/watch?v=aqz-KE-bpKQ'
```

### 8-2. 結果

**プロセス数は常に 1 個**（`nproc=1`）。レンダラと GPU の処理も同じプロセス内で動いている
（ログにも `Chrome_InProcRendererThread` が出る）。そのため、RSS ≒ プロセス全体のメモリ。

| 状態 | RSS | PSS | USS（そのプロセス専用） |
|---|---|---|---|
| 起動直後（0 秒） | 47.6MB | 41.6MB | 40.9MB |
| 起動中のピーク（37.6 秒） | — | **301.2MB** | — |
| ホーム画面で待機（60〜180 秒、安定） | **約 297MB** | **約 244MB** | 約 229MB |
| 動画再生中（40〜240 秒） | **約 900〜980MB** | **約 850〜930MB** | 約 840〜915MB |
| 動画再生中のピーク | 1009.5MB | 956.0MB | — |

- 画面確認: ホームは 60 秒の時点で「Recommended」が表示されていた。再生は 180 秒の時点で Big Buck Bunny のフレームが表示されていた。
- 再生した形式: `SbPlayerCreate() ... audio "audio/mp4; codecs="ec-3"", video "video/mp4; codecs="av01.0.13M.08""`
  → AV1、Main プロファイル、level 13（= 5.1。4K まで扱えるレベル）、8 bit。デコードは `dav1d_video_decoder` スレッド。
  **実際の解像度はログに出ていないので未確認。**

### 8-3. 内訳（smaps をマッピングごとに分類した PSS）

| 分類 | ホームで待機（90 秒） | 動画再生中（60 秒） |
|---|---|---|
| `[anon:partition_alloc]`（Chromium のヒープ） | 70.0MB（28%） | **674.4MB（78%）** |
| `cobalt` 本体のコードとデータ（ファイル） | 96.6MB（39%） | 94.8MB（11%） |
| Mesa / GL / LLVM（ソフトウェアレンダラ） | 33.6MB（14%） | 33.0MB（4%） |
| 名前なしの anon | 16.8MB | 19.1MB |
| `[anon:v8]` | 9.5MB | 7.9MB |
| `libstarboard` | 5.7MB | 5.5MB |
| 合計 | 247.0MB | 860.3MB |

- 待機中は **strip 後 108.8MB のバイナリのうち約 96MB が常にメモリに載っている**。つまり ROM サイズがそのまま RAM の常駐分になっている。
- 再生中に増えた約 600MB は、ほぼ全部 `partition_alloc`。
  `use_partition_alloc_as_malloc=true`（`gn args` で確認）なので、dav1d やシステムの Mesa が malloc したメモリもここに含まれると考えている（推定）。

### 8-4. 再生時のメモリは想定どおりか（ソースの設定値との比較）

- MSE のバッファ上限（Starboard の Linux 共通実装 `starboard/shared/starboard/media/media_get_video_buffer_budget.cc`）:
  1080p 以下は 30MB、4K で 8bit は 100MB、4K で 10bit 以上は 160MB。それより大きい解像度用の値もある。
  音声は 5MB（`media_get_audio_buffer_budget.cc`）。
  Finch の `kCobaltVideoBufferBudget*` で上書きできる（`media/base/starboard/demuxer_memory_limit_starboard.cc`）。
- **増えた約 600MB は、MSE のバッファ上限（最大 160MB）を大きく超えている。**
  残りは、ソフトウェアデコーダのフレームプール（dav1d のスレッドごとの参照フレーム）、デコード済みフレームのキュー、
  Mesa のソフトウェアレンダラのテクスチャやフレームバッファだと考えている。**ただし、この内訳は未計測**
  （partition_alloc の中身を分ける手段を今回は使っていない）。

### 8-5. 未確認のこと

- 再生した動画の実際の解像度（4K なのか 1080p なのか）。
- 再生中の約 600MB の内訳（MSE バッファ、デコーダ、レンダラの割合）。
- 実際の GPU やハードウェアデコーダがある環境での値。
- 起動時のキャッシュの有無による違い。今回は以前の起動で作られたキャッシュとストレージが残っている状態で計測した。

### Step 8 まとめ

- strip した gold を **単一プロセス**で動かした結果、**ホーム画面で待機中は PSS 約 244MB（RSS 約 297MB）、起動中のピークは PSS 301MB**。
- **AV1 の動画を再生中は PSS 約 850〜930MB（ピーク 956MB）**。増えた分はほぼ全部 Chromium のヒープ（partition_alloc）で、
  ソフトウェアデコードとソフトウェアレンダリングの影響を受けている可能性が高い。
- 待機中のメモリの 4 割はバイナリ本体（約 96MB）。ROM を削ると、そのまま常駐 RAM も減る構成になっている。

---

## Step 9. メモリが多い PC だから多く使っているのか（cgroup と物理メモリの偽装で検証）

### 9-1. 単一プロセスか、PSS と RSS がほぼ同じ理由

- `cobalt/app/cobalt_switch_defaults_starboard.cc:40-52` で、次のスイッチが**デフォルトで付く**:
  `--single-process`、`--no-zygote`、`--no-sandbox`、**`--enable-low-end-device-mode`**、`--disable-accelerated-video-decode` ほか。
  JS フラグとして `--no-decommit-pooled-pages --no-concurrent-marking` も付く。
- 計測でもプロセスは常に 1 個だった（Step 8）。
- ホーム画面で待機中の RSS − PSS = 52.6MB の内訳（smaps）: `libLLVM.so.20.1` 29.1MB、`libgallium` 7.1MB、`SYSV` 共有メモリ 4.0MB、libc 1.8MB など。
  **すべてシステムの共有ライブラリと X サーバとの共有メモリ**で、`cobalt` 本体は RSS = PSS。
  → PSS ≒ RSS になるのは、**single-process なので Chromium の子プロセスとページを共有していない**から。
  通常のマルチプロセス Chromium では、ブラウザ・レンダラ・GPU プロセスでバイナリのページを共有するので、プロセスごとの PSS は RSS よりかなり小さくなる。

### 9-2. Cobalt は物理メモリ量をどう知るか

- `starboard/shared/linux/system_get_total_cpu_memory.cc`: `SbSystemGetTotalCPUMemory()` = `sysconf(_SC_PHYS_PAGES) * page_size`。
- `base/system/sys_info_linux.cc`: `AmountOfPhysicalMemory()` も `sysconf(_SC_PHYS_PAGES)`。
- つまり、この PC では **125GB と認識している**。`cobalt` と `libstarboard.so.18` は glibc の `sysconf` を動的に import している（`nm -D` で確認）。

### 9-3. 実験方法

- 物理メモリの偽装: `memshim/fake_physmem.c`（LD_PRELOAD で `sysconf(_SC_PHYS_PAGES/_SC_AVPHYS_PAGES)` を差し替え）。
  python から 2048MB に見えることを確認した。ただし、`/proc/meminfo`（空きメモリ）は本物の値のまま。
- 実際のメモリ制限: `systemd-run --user --scope -p MemoryMax=<N> -p MemorySwapMax=0`。
  この PC には 8GB の swap があるので、swap に逃げないように 0 にした。cgroup の `memory.events` と `memory.peak` を 30 秒ごとに記録した。
- CPU 数の制限: `taskset -c 0-3`。
- コンテンツ: どれも同じ動画（deep link で `aqz-KE-bpKQ`、AV1 を dav1d でデコード）。240 秒間再生した。
  30 秒ごとのスクリーンショットが毎回変わっていることで、再生が進んでいることを確認した（`mem_summary.py`）。

### 9-4. 結果

| 条件 | 定常の PSS | ピークの PSS | 結果 |
|---|---|---|---|
| 制限なし（物理メモリ 125GB、24 コア） | 891MB | 956MB | 再生できた |
| 物理メモリを 2GB に偽装 | 893MB | 952MB | 再生できた（**変化なし**） |
| 2GB に偽装 + cgroup 2GB | 891MB | 961MB | 再生できた（変化なし） |
| 1GB に偽装 + cgroup 1GB | 895MB | 956MB | 再生できた。`memory.events` で limit 到達も OOM も 0、cgroup のピークは 852MB（**変化なし**） |
| 600MB に偽装 + cgroup 600MB | — | — | **再生開始の約 2 秒後に OOM kill**（systemd: `Failed with result 'oom-kill'`、memory peak 600.0M） |
| 300MB に偽装 + cgroup 300MB | — | — | **再生開始の約 2 秒後に OOM kill**（memory peak 300.0M） |
| **4 コアに制限**（`taskset -c 0-3`） | **724MB** | 767MB | 再生できた（**−167MB**） |
| 4 コア + 600MB に偽装 + cgroup 600MB | — | 716MB | 16 秒で OOM kill |
| ホーム画面のみ（再生なし）、300MB に偽装 + cgroup 300MB | 243MB | 324MB | 120 秒間問題なく動いた（limit 到達も OOM も 0、cgroup のピークは 227MB）。制限なしの 244MB と同じ |

- 注意: PSS には、他の cgroup に計上されている共有ライブラリの分も含まれるので、cgroup の上限より大きな値になることがある（4 コア + 600MB の 716MB など）。

### 9-5. 考察

1. **「メモリがあるだけ使う」は、このコンテンツと範囲（1GB〜125GB）では確認できなかった。**
   物理メモリを偽装しても、cgroup で制限しても、使用量は同じだった。
   Cobalt は `--enable-low-end-device-mode` を常に付けていて、MSE のバッファも固定値（Step 8-4）。
   搭載メモリに応じて増える仕組みは、少なくともこの範囲では目立って効いていない。
2. **メモリが足りないとき、Cobalt は使用量を減らして適応するのではなく、OOM で落ちた**（600MB と 300MB）。
   動画再生を始めた直後の 1〜2 秒で必要量が急に増え、そこで kill された。
3. **実際に効いていたのは「メモリ量」ではなく「CPU のコア数」。**
   - `starboard/shared/libdav1d/dav1d_video_decoder.cc:163`: `dav1d_settings.n_threads = 0;  // Use all logic cores`
   - dav1d はコア数を `pthread_getaffinity_np` で数え（`third_party/dav1d/libdav1d/src/cpu.c`）、
     フレームスレッド数を `ceil(sqrt(n))` にする（`src/lib.c` の `get_num_threads`）。24 コアなら 5、4 コアなら 2。
   - 4 コアに制限すると、同じ動画で 167MB 減った。**この PC はコア数が多いので、ソフトウェアデコーダのメモリが増えている。**
     ただし、4 コアに制限したことで YouTube が選ぶ画質（ビットレート）が変わった可能性もあり、減った分がすべてフレームスレッドによるとは断定できない。
4. ホーム画面だけなら、300MB の制限でも動いた（PSS 243MB）。

### 9-6. 未確認のこと

- `/proc/meminfo`（空きメモリ）も偽装したときの挙動。Chromium のメモリ圧迫の検知が反応するかどうか。
- 再生した画質（解像度、ビットレート）が条件ごとに同じか。
- 600MB で OOM になった瞬間の内訳（どの確保で上限を超えたか）。
- 実機（ハードウェアデコーダ + GPU、2〜4 コア）での値。

---

## Step 10. CPU やメモリの量を見て、使うメモリの量を変えているか（ソースの追跡と実験）

### 10-1. ソースの追跡

**(1) CPU 数 → 再生する動画の最大解像度（今回一番効いていたもの）**
- `starboard/linux/shared/media_is_video_supported.cc`:
  ```cpp
  static const bool can_support_8k = SbSystemGetNumberOfProcessors() >= 16;
  const int max_width  = can_support_8k ? 7680 : 1920;
  const int max_height = can_support_8k ? 4320 : 1080;
  ```
- `starboard/shared/posix/system_get_number_of_processors.cc`: `sysconf(_SC_NPROCESSORS_ONLN)`。
  **CPU の affinity（`taskset`）は見ていない**ので、Step 9 の「4 コア制限」では 8K まで対応と申告したままだった。
- この PC（24 論理コア）では「8K まで再生できる」と YouTube に申告するので、1920x1080 のウィンドウでも **3840x2160 の動画が選ばれた**
  （`SbPlayerBridge::UpdateVideoConfig` のログ `natural size: [3840,2160]`。`--log-level=0 --v=0` を付けると出る）。

**(2) CPU 数 → dav1d のスレッド数とフレームスレッド数**
- `starboard/shared/libdav1d/dav1d_video_decoder.cc:163`: `n_threads = 0  // Use all logic cores`
- dav1d はコア数を `pthread_getaffinity_np` で数える（`third_party/dav1d/libdav1d/src/cpu.c`）。こちらは affinity の影響を受ける。
- フレームスレッド数は `ceil(sqrt(n))`（`src/lib.c` の `get_num_threads`）。
- Chromium のスレッドプールも CPU 数で大きさを決める（`content/common/thread_pool_util.cc:16`: `max(1, NumberOfProcessors() - 1)`）。

**(3) 物理メモリ量 → Cobalt 独自のメモリ圧迫判定（デフォルトでは無効）**
- `cobalt/memory/cobalt_system_memory_pressure_evaluator.cc`: 物理メモリ量に応じてプロセスのメモリ予算を決める。
  1GB 以下は 160MB、2GB 以下は 300MB、それより大きい場合は 500MB（`.h:63-65`）。
  これに MSE の容量（`GetMediaSourceCurrentMemoryCapacity`）を足した値と、プロセスの anon RSS + swap を比べる。
  85% を超えたら MODERATE、95% を超えたら CRITICAL を通知する。10 秒ごとに確認する。
- `cobalt/browser/features.cc:182`: `kEnableCobaltMemoryPressureEvaluator` は **`FEATURE_DISABLED_BY_DEFAULT`**。
  Finch か `--enable-features` で有効にしたときだけ動く（`cobalt_browser_main_parts.cc:643`）。

**(4) 物理メモリ量 → V8 のヒープ上限（上流 Chromium の仕組みがそのまま残っている）**
- `gin/isolate_holder.cc:191`: `ConfigureDefaults(AmountOfPhysicalMemory(), ...)`
- `v8/src/heap/heap.cc:226-302`: old generation の上限は「物理メモリ ÷ 4」で、2GB（物理メモリ 15GB 以上なら 4GB）が上限。
  これは GC の上限であって、実際に確保する量ではない。今回の計測では `[anon:v8]` は 8〜10MB しか無かった。

**(5) 上流で「メモリ量に応じて決める」設定を、Cobalt が固定値に置き換えている**
- `base/system/sys_info.cc:190` `DetectLowEndDevice()`: `--enable-low-end-device-mode` があれば常に true。
  Cobalt はこのスイッチを常に付けるので、**`IsLowEndDevice()` を見るコード（全 54 ファイル）は、メモリ量に関係なく常に低スペック向けの動作になる**。
- `cc/tiles/image_decode_cache_utils.cc`（Cobalt パッチ +90 行）: デコード済み画像の予算を **128MB に固定**（`--decoded-image-working-set-budget-bytes` で変更可）。
- `gpu/config/skia_limits.cc`（+10 / −4）: 低スペック時の Skia リソースキャッシュを、上流の 48MB から **2MB に固定**。
- `gpu/command_buffer/service/service_discardable_manager.cc`（+30 行）: GPU discardable キャッシュを Finch の値で決める（上限 256MB）。
- MSE のバッファ上限は解像度ごとの固定値（Step 8-4）。
- 物理メモリ量を見ているのに Cobalt が手を入れていないもの: `base/allocator/miracle_parameter.cc`、`components/viz/common/viz_utils.cc`、
  `components/viz/client/frame_eviction_manager.cc`（ただし single-process なので、viz の一部は影響しない可能性がある。未確認）。

**(6) Web アプリ（YouTube）に向けたメモリ情報の API**
- `third_party/blink/renderer/core/cobalt/performance/performance_extensions.idl` で、`performance.measureAvailableCpuMemory()`
  （`AmountOfAvailablePhysicalMemory`、つまり /proc/meminfo）や `measureTotalCpuMemory()` などを公開している（`cobalt/browser/performance/performance_impl.cc`）。
  YouTube のアプリがこれを見て動作を変えている可能性がある。アプリ側のコードは非公開。

### 10-2. 実験（同じ動画を 180 秒再生。最初の 20 秒は 0.1 秒ごとに計測）

偽装用の shim を拡張した（`memshim/fake_physmem.c`）:
`FAKE_PHYS_MB`（`_SC_PHYS_PAGES`）、`FAKE_NPROC`（`_SC_NPROCESSORS_ONLN/CONF`）、`FAKE_MEMINFO`（`/proc/meminfo` を開こうとしたら別のファイルを開く。
`open`、`open64`、`openat`、`openat64`、`fopen`、`fopen64` を差し替え）。
`cobalt` と `libstarboard.so.18` が import しているのは `fopen64`、`open64`、`openat64`、`sysconf`（`nm -D` で確認）。
偽の meminfo は MemTotal 1GB、MemAvailable 256MB。

| # | 条件 | 再生した解像度 | 定常の PSS | ピークの PSS | メモリ圧迫の通知 |
|---|---|---|---|---|---|
| E0 | 基準（24 コア、125GB） | **3840x2160** | **874MB** | 948MB | 評価器は無効 |
| E1 | CPU 数を 4 と申告（affinity は 24 のまま） | **1920x1080** | **416MB** | 436MB | 評価器は無効 |
| E2 | `taskset` で 4 コアに制限（8K 対応の申告はそのまま） | 3840x2160 | 714MB | 779MB | 評価器は無効 |
| E3 | CPU 数を 4 と申告 + `taskset` で 4 コア | 1920x1080 | **364MB** | 381MB | 評価器は無効 |
| E4 | 物理メモリを 1GB、MemAvailable を 256MB に偽装 | 3840x2160 | 878MB | 952MB | 評価器は無効 |
| E5 | E4 + `--enable-features=EnableCobaltMemoryPressureEvaluator` | 3840x2160 | 878MB | 961MB | **予算 160MB、CRITICAL（2）を 18 回** |
| E6 | 1GB・4 コアの端末を模擬（E3 + E5 + cgroup `MemoryMax=600M`、swap 0） | 1920x1080 | 364MB | 382MB | CRITICAL。**OOM にならずに再生できた**（cgroup のピーク 268MB） |

- どの条件でも、30 秒ごとのスクリーンショットが変化していて、再生が進んでいることを確認した。
- E5 のログ: `Resolved total physical RAM: 1024 MB` → `Derived process memory budget = 160 MB`。
  圧迫レベルは `MEMORY_PRESSURE_LEVEL_CRITICAL = 2`（`base/memory/memory_pressure_listener.h:67`）。

**再生開始直後の急増**（0.1 秒ごとの計測を 1 秒ごとに表示。PSS / スレッド数）:

```
E0 (4K, 24 コア): 0s 57MB/24 → 1s 235MB/85 → 2s 743MB/113 → ... 20s 854MB/113
E3 (1080p, 4 コア): 0s 47MB/22 → 1s 210MB/45 → 2s 320MB/54 → ... 20s 357MB/54
```

→ 4K では、プレーヤーを作ってから **1 秒で約 +500MB、スレッドが +28 本**。600MB で OOM になったのはこのタイミング（Step 9）。

### 10-3. 結論

1. **使用メモリを大きく左右していたのは「メモリ量」ではなく「CPU 数」で、主な経路は再生解像度。**
   - 申告する CPU 数が 16 以上だと 8K まで、それ未満だと 1080p までになる → 4K と 1080p で **874MB と 416MB（−458MB）**。
   - CPU の affinity による dav1d のスレッド数の違い: 4K で −160MB（874 → 714）、1080p で −52MB（416 → 364）。
2. **物理メモリ量や空きメモリ量を変えても、使用量も解像度も変わらなかった**（E4）。
   YouTube のアプリも、少なくともこの条件では、空きメモリを見て画質を下げてはいない。
3. **Cobalt 独自のメモリ圧迫判定を有効にしても（E5）、CRITICAL を出し続けるだけで、再生中のメモリは減らなかった。**
   キャッシュの解放などはしているはずだが、動画デコーダとバッファの分は、圧迫の通知では小さくならない。
4. 上流でメモリ量に応じて決めているキャッシュの多くを、Cobalt は固定値に置き換えている（low-end モードを常に有効、画像 128MB、Skia 2MB など）。
   **メモリ量に追従しないように作られている**と言える。メモリ量で変わるのは V8 の GC 上限くらいで、今回の負荷では影響は小さかった。
5. **1GB・4 コアの端末を模擬すると、600MB の cgroup でも 1080p で再生できた**（PSS 364MB）。
   Step 9 で 600MB の OOM になったのは、「24 コアの PC が 8K まで対応と申告して 4K を選んだ」ためだった。
   → **Step 9 の「cgroup で制限しても使用量が変わらない」という結果は、CPU 数で決まる解像度が支配的だったため**。

### 10-4. 注意と未確認のこと

- 「4 コア」は Linux リファレンス実装の判定（16 未満なら 1080p）を通しただけ。実機の Starboard 実装は、それぞれのハードウェアデコーダの能力で判定する。
- 今回の環境はソフトウェアデコードとソフトウェアレンダリング。ハードウェアデコーダ + GPU の実機とは内訳が違う。
- メモリ圧迫の通知を受けて、どのキャッシュがどれだけ解放されたかは計測していない（内訳を取る手段が gold には無い）。

---

## Step 11. ハードウェアデコーダの使用可否と、そのメモリを測る方法

### 11-1. この PC のハードウェアデコード対応状況

- GPU: `00:02.0 Intel Corporation Raptor Lake-S GT1 [UHD Graphics 770] [8086:a780]`。ドライバは `i915`（`xe` モジュールも読み込まれているが未使用）。カーネル 6.17.0-35-generic。
- `/dev/dri/renderD128` は `root:render 660`。ユーザーは render グループに入っていないが、ログイン中のセッションの ACL（`user:raiko:rw-`）で開ける（python の `os.open` で確認）。
- パッケージ: `libva2 2.20.0`、`intel-media-va-driver 24.1.0`（iHD）、`i965-va-driver 2.4.1`、`libvpl2`、`linux-firmware 20240318`。ffmpeg の hwaccels は `vdpau cuda vaapi qsv drm opencl vulkan`。
- `vainfo` は入っていない（sudo が使えない）ので、ctypes で同等のものを書いた（`hwdec/va_caps.py`。プロファイルの番号は `/usr/include/va/va.h` で確認）:
  ```
  VA-API 1.20  driver: Intel iHD driver for Intel(R) Gen Graphics - 24.1.0
  decode (VLD): MPEG2Simple, MPEG2Main, H264Main, H264High, JPEGBaseline, H264ConstrainedBaseline, HEVCMain, HEVCMain10,
                VP9Profile0-3, HEVCMain12, HEVCMain422_10/12, HEVCMain444/_10/_12, HEVCScc*, AV1Profile0
  ```
- 実際にデコードして確認した（ffmpeg で 4K・2 秒・60 フレームのテスト動画を作り、`-hwaccel vaapi -hwaccel_output_format vaapi` でデコード）:

| コーデック | ハードウェアデコード | 備考 |
|---|---|---|
| H.264 4K | **OK**（60 フレーム） | |
| HEVC 4K | **OK**（60 フレーム） | |
| VP9 4K | **OK**（60 フレーム） | CPU 時間 0.06 秒（ソフトウェアでは 0.98 秒） |
| AV1（4K / 1080p、SVT-AV1 / libaom） | **NG** | `Failed to end picture decode issue: 23 (internal decoding error)`。原因は未特定（カーネルのログが既に流れていて GuC / HuC の読み込み状況は確認できず、debugfs は root 専用） |

→ **H.264、HEVC、VP9 はハードウェアでデコードできる。AV1 は、ドライバは対応と言うが、実際には失敗する。**
YouTube が選んでいたのは AV1 なので、そのままではハードウェアデコードの対象にならない。

### 11-2. Cobalt（linux-x64x11）にはハードウェアデコードの経路が無い

- `starboard/linux/shared/player_components_factory.cc`: VP9 は `VpxVideoDecoder`（libvpx）、AV1 は `Dav1dVideoDecoder`、HEVC は `De265VideoDecoder`、
  H.264 は `OpenH264VideoDecoder` か `FfmpegVideoDecoder`（libavcodec を dlopen）。**すべてソフトウェア**。
- `starboard/` 全体（テストを除く）を `vaapi|libva|AV_HWDEVICE|hw_device_ctx|hwaccel|vdpau|v4l2` で検索しても、Android の `display_util.cc` しか出てこない。
- Chromium 側の VA-API も使わない: `use_vaapi=false`、`use_v4l2_codec=false`、`use_starboard_media=true`、
  `//media/gpu/vaapi` は 1 ターゲットもリンクされていない。さらに `--disable-accelerated-video-decode` を常に付けている（`cobalt_switch_defaults_starboard.cc`）。
- ほかのプラットフォーム設定も代わりにならない:
  - `chromium_linux-x64x11`: CI でビルドしているのは `content_shell` や `chromedriver` などで、Cobalt ではない（`.github/config/chromium_linux.json`）。
  - `linux-x64x11-no-starboard`: 設定ファイルに「Cobalt の Web API を web tests で試すための content_shell 用。cobalt ターゲットの動作は未定義」と書かれている。

### 11-3. ハードウェアデコーダのメモリは RSS には出ない → DRM の fdinfo で測る

ffmpeg で VP9 4K を VA-API デコードしているときに、`/proc/<pid>/fdinfo/<renderD128 の fd>` を読んだ:

```
drm-driver: i915  drm-total-system0: 401844 KiB  drm-resident-system0: 300420 KiB  drm-engine-video: 556093304 ns
VmRSS: 118404 kB  RssAnon: 74452 kB
```

- **プロセスの RSS は 118MB だが、GPU のバッファ（デコード面など）として 300MB（確保は 402MB）を別に持っている**。
  Intel の iGPU では、これも物理的にはシステムの RAM。
- `drm-engine-video` が増えているので、実際にハードウェアのビデオエンジンでデコードしている。
- → ハードウェアデコードの環境でメモリを比べるときは、**RSS / PSS に加えて DRM fdinfo（または dma-buf）の値を足さないと過小評価になる**。

### Step 11 まとめ

- この PC は H.264、HEVC、VP9 をハードウェアでデコードできる（AV1 は失敗）。
- ただし、**Cobalt の Linux リファレンス実装には、ハードウェアデコーダを使う経路がそもそも無い**（Starboard 側も Chromium 側も）。
  なので、何かの設定を「オン」にするだけでは試せない。
- ハードウェアデコーダのメモリは RSS に出ないので、DRM fdinfo で測る必要がある。

### 11-4. AV1 ハードウェアデコード失敗の切り分け（ユーザーが ssh から sudo で実行した結果）

| 確認項目 | 結果 | 判断 |
|---|---|---|
| HuC（`/sys/kernel/debug/dri/0/gt0/uc/huc_info`） | `i915/tgl_huc.bin`、**status: RUNNING**、version 7.9.3 | ファームウェアは正常 |
| GuC（`guc_info`） | `i915/tgl_guc_70.bin`、**status: RUNNING**、version 70.36.0、Submission API 1.17.0 | 正常 |
| カーネル引数（`/proc/cmdline`） | `BOOT_IMAGE=/vmlinuz-6.17.0-35-generic ... quiet splash`（i915 の特別な指定なし） | |
| `vainfo` | `VAProfileAV1Profile0 : VAEntrypointVLD`（iHD 24.1.0） | ドライバは AV1 デコードに対応と申告 |
| VA トレース（`LIBVA_TRACE`） | vaCreateConfig（AV1Profile0 / VLD）、vaCreateSurfaces、vaBeginPicture、vaRenderPicture（ピクチャ / スライスパラメータ / スライスデータ）はすべて `VA_STATUS_SUCCESS`。**最初のキーフレームの `vaEndPicture` で失敗**（`issue: 23` = 0x17 `VA_STATUS_ERROR_DECODING_ERROR`）。その後 ffmpeg 6.1.1 がエラー処理中に segfault | パラメータの受け渡しまでは成功し、**ドライバ内部で GPU にデコードを投げた段階で失敗**している |
| ストリームの特徴 | 8 bit（`bit_depth_idx = 0`）、`tile_cols = 1`、`tile_rows = 1`、`apply_grain = 0`、キーフレーム。640x360 の libaom（タイル 1、CDEF なし）でも同じエラー | 特定の符号化機能や解像度の問題ではない |
| QSV（`av1_qsv`） | `Error creating a MFX session: -9` | oneVPL の GPU ランタイム（`libmfx-gen1.2`）が未インストールのため。未検証 |
| GStreamer（`vaav1dec`） | `no element "av1parse"` | `gstreamer1.0-plugins-bad` が未インストールのため。未検証 |
| `intel_gpu_top` | デコードしていない時点の画面だけ | 未検証（デコード中に見る必要がある） |
| `intel-media-va-driver` の更新候補 `24.1.0+dfsg1-1ubuntu0.2` | changelog は「TWL（ADL-N Refresh）のデバイス ID 追加」だけ | **AV1 の修正は含まれない** |

**現時点の結論**: ファームウェア、プロファイル、ストリームに問題は無く、**iHD 24.1.0（2023 年 12 月の版）とカーネル 6.17 の i915 の組み合わせで、AV1 のデコードだけが GPU 側で失敗している**可能性が高い。
（H.264、HEVC、VP9 は同じ環境で成功するので、デバイスやアクセス権の問題ではない）。原因の確定はまだ。

### 11-5. AV1 の調査は中止

ユーザーの判断で、AV1 ハードウェアデコード失敗の調査はここで中止した（新しいドライバやカーネルを試すには再起動などシステムの変更が必要なため）。
原因は「iHD 24.1.0 と i915（カーネル 6.17）の組み合わせで、AV1 だけ `vaEndPicture` が失敗する」という推定のまま。

---

## Step 12. 物理メモリ量・低スペック判定・CPU 数で決まる設定の網羅調査

### 12-0. 方法

1. **バイナリに実際にリンクされたソース**を DWARF の compile unit から列挙した（18,081 ファイル。そのうち `gen/` は 3,752）。
   ```bash
   llvm-dwarfdump --debug-info --recurse-depth=0 out/linux-x64x11_gold/cobalt | grep DW_AT_name
   ```
2. その中で、次の API を使っているファイルを `git grep` で探した（テスト・ファジング・ベンチマークは除外）:
   `AmountOfPhysicalMemory`、`AmountOfAvailablePhysicalMemory|GetSystemMemoryInfo`、`IsLowEndDevice*`、`NumberOfProcessors|SbSystemGetNumberOfProcessors`、
   `MIRACLE_PARAMETER`、`SbSystemGet{Total,Used}CPUMemory`。
   → **98 ファイル**（物理メモリ 40、低スペック判定 38、CPU 数 25、空きメモリ 8、MiracleParameter 5、Starboard のメモリ API 2。重複あり）。
3. 各ファイルが上流 M138 と比べて Cobalt にパッチされているかを確認し、何の量を決めているのかをコードで読んだ。

### 12-1. 大前提: 低スペック判定は常に true

- `cobalt/app/cobalt_switch_defaults_starboard.cc` が `--enable-low-end-device-mode` を常に付ける。
  → `base/system/sys_info.cc:190` の `DetectLowEndDevice()` は常に true（メモリ量を見ない）。
- そのため、上流で `IsLowEndDevice()` によって分岐している箇所は、**メモリ量に関係なく常に低スペック側**になる。
  （上流のコードそのままで、Cobalt のパッチではない）:

| 場所 | 低スペック時の動作 |
|---|---|
| `third_party/leveldatabase/leveldb_chrome.cc:43` | LevelDB のブロックキャッシュが 8MB → **1MB** |
| `third_party/leveldatabase/env_chromium.cc:491` | ログを再利用しない |
| `third_party/blink/renderer/modules/storage/storage_controller.cc:47` | DOM Storage のキャッシュ上限を低スペック用の値に |
| `components/discardable_memory/client/...:59` | discardable の確保単位を低スペック用に |
| `third_party/blink/renderer/core/html/canvas/canvas_font_cache.cc:56` | Canvas のフォントキャッシュを低スペック用の上限に |
| `third_party/blink/renderer/platform/fonts/plain_text_painter.cc:285` | 共有キャッシュを使わない |
| `third_party/blink/renderer/bindings/core/v8/v8_gc_for_context_dispose.cc:76` | 低メモリ時にページ遷移で GC |
| `gpu/command_buffer/service/memory_program_cache.cc:258` | シェーダキャッシュを低スペック用に |
| `components/viz/service/display_embedder/skia_output_surface_impl.cc:489` | MSAA のサンプル数を変える |

### 12-2. Cobalt が「物理メモリ量に応じて決める」設定を固定値に置き換えている箇所（パッチ）

| 対象 | 上流（物理メモリ量に応じて決める） | Cobalt（Linux / Starboard の既定） | 根拠 |
|---|---|---|---|
| **V8 の old generation 上限** | 物理メモリ ÷ 4、上限 2GB（15GB 以上なら 4GB） | **常に 512MB、初期値 16MB** | 下の注を参照 |
| デコード済み画像の予算（cc） | 物理メモリから計算 | **128MB 固定**（`--decoded-image-working-set-budget-bytes` で変更可） | `cc/tiles/image_decode_cache_utils.cc`（+90 行） |
| Skia のリソースキャッシュ | 低スペック時 48MB（MiracleParameter） | **2MB 固定** | `gpu/config/skia_limits.cc` |
| GPU の discardable キャッシュ | プラットフォームごとの値 | **1MB**（`kCobaltGpuDiscardableCacheLimit` が Android 以外で既定で有効。上限 256MB） | `gpu/command_buffer/service/service_discardable_manager.cc`、`base/features.cc` |
| タイル（ラスタ）メモリの優先度 | `CUTOFF_ALLOW_NICE_TO_HAVE` | **`CUTOFF_ALLOW_REQUIRED_ONLY`**（表示に必要な分だけ） | `layer_tree_settings.cc`（+80 / −4） |
| タイルメモリの上限 | デスクトップ: 画面サイズに比例（512〜1152MB）、ただし物理メモリ ÷ 4 が上限 | 64bit は上流のまま。**32bit は 64MB に固定**。Finch の `kCobaltForceGpuMemAvailable` で固定値にもできる | 同上 |
| 先読みの描画（prepaint） | 上流の既定値 | **0%（先読みしない）**（`kCobaltMaxMemoryForPrepaint` が既定で有効） | `base/features.cc` |
| skewport（スクロール予測の範囲） | 上流の既定値 | **0 秒**（Android 以外で既定で有効） | `base/features.cc` |
| HTTP キャッシュ | 空きディスク容量に応じて決める | **プラットフォームの定数から決める**: `kSbMaxSystemPathCacheDirectorySize`（Linux は 24MiB）− 12MB = 12MB | `cobalt_content_browser_client.cc:433,549`、`starboard/linux/shared/configuration_constants.cc:57` |
| V8 の `--optimize-for-size` | `IsLowEndDevice()` なら付ける | 低スペック判定から切り離し、Finch の `kCobaltV8OptimizeForSize`（Android のみ既定で有効、Linux は無効）で決める | `content/renderer/render_process_impl.cc` |
| ICU データ | 共通の 10MB | YouTube 向けに絞った 6.6MB | Step 4-6 |
| MSE のバッファ | Chromium の既定値 | 解像度ごとの固定値（Starboard） | Step 8-4 |
| 動画デコーダのバッファ（MSE） | — | 1080p 以下 30MB、4K で 100 / 160MB | Step 8-4 |

**注（Step 10 の記述の訂正）: V8 のヒープ上限も固定値だった**
- `gin/v8_initializer.cc:398-407`（Cobalt パッチ）:
  ```cpp
  int max_old_space_mb = base::features::kCobaltV8MaxOldSpaceSizeMb.Get();     // 既定値 512
  if (max_old_space_mb > 0) SetV8FlagsFormatted("--max-old-space-size=%i", ...);
  int initial_old_space_mb = base::features::kCobaltV8InitialOldSpaceSizeMb.Get(); // 既定値 16
  if (initial_old_space_mb > 0) SetV8FlagsFormatted("--initial-old-space-size=%i", ...);
  ```
- `FeatureParam::Get()` は「feature が無効、またはパラメータが指定されていない場合はデフォルト値を返す」（`base/metrics/field_trial_params.h:93`）。
  このコードは feature が有効かどうかを見ていないので、**`kCobaltV8MaxOldSpaceSize` が無効（既定）でも常に 512 が設定される**。
- V8 側では `v8_flags.max_old_space_size > 0` の場合、物理メモリから計算した上限（`constraints`）より優先される（`v8/src/heap/heap.cc:5067`）。
- → Step 10 で書いた「メモリ量で変わるのは V8 の GC 上限くらい」は**誤り**。V8 の old generation 上限は**物理メモリに関係なく 512MB**。
  これはソースを読んだ結果で、実行時の確認はしていない（gold には DevTools も V8 のフラグを出力する経路も無い）。

### 12-3. Cobalt に追加された「既定で有効」な Finch 機能（`base/features.cc`）

| feature | Linux / Starboard の既定 | パラメータの既定値 |
|---|---|---|
| `kCobaltInProcessImageTransferCache` | **有効**（Android と tvOS は無効） | |
| `kCobaltGpuDiscardableCacheLimit` | **有効**（Android は無効） | `CobaltGpuDiscardableCacheLimit_mb = 1` |
| `kCobaltSkewportTargetTime` | **有効**（Android は無効） | 0.0 秒 |
| `kCobaltMaxMemoryForPrepaint` | **有効** | 0% |
| `kCobaltV8OptimizeForSize` | 無効（Android は有効） | |
| `kCobaltV8MaxOldSpaceSize` / `kCobaltV8InitialOldSpaceSize` | 無効（**ただしパラメータの既定値 512 / 16 は常に使われる**。12-2 の注） | 512 / 16MB |
| `kCobaltForceGpuMemAvailable` | 無効 | 64MB |
| `kCobaltCCImageCacheLimitItems` | 無効 | 0 個 / −1MB |
| `kCobaltEnableModerateMemoryPressure`、`kCobaltMemoryPressureCooldown`（60 秒）、`kCobaltStorageCleanup`、`kCobaltAndroidDisplayCriticalInProcessRenderer` | 無効 | |
| `kEnableCobaltMemoryPressureEvaluator`（`cobalt/browser/features.cc`） | 無効 | 予算は 160 / 300 / 500MB（Step 10） |

→ ROM / RAM 削減の設定は、GN の引数（Step 7-5）だけでなく、**Finch 機能の「コンパイル時の既定値」にも埋め込まれている**。
`gn args` でも Cobalt の設定ファイルでも見えないので、`base/features.cc` を読まないと分からない。

### 12-4. 上流のまま残っている「物理メモリ量に応じて決める」箇所（Cobalt はパッチしていない）

| 場所 | 内容 | Cobalt での影響 |
|---|---|---|
| `net/disk_cache/memory/mem_backend_impl.cc:79` | メモリ上の HTTP キャッシュ = 物理メモリの 2%（上限 50MB） | Cobalt はディスクキャッシュを使う（`in_memory=false` の経路で `http_cache_directory` を設定）ので、通常は使われない（推定） |
| `storage/browser/blob/blob_memory_controller.cc:86` | メモリ上の Blob の上限 = 物理メモリの 1% または 20% など | **物理メモリ量に応じて変わる** |
| `components/discardable_memory/service/discardable_shared_memory_manager.cc:207` | discardable 共有メモリの上限 = min(既定値, 物理メモリ ÷ 4) | **変わる**（小さい端末で上限が下がる） |
| `components/viz/client/frame_eviction_manager.cc:137` | 保持するフレーム数 = min(5, 2 + 物理メモリ MB ÷ 256) | **変わる**（512MB 以上で上限の 5） |
| `third_party/blink/common/device_memory/approximated_device_memory.cc:21` | JS の `navigator.deviceMemory` | **変わる**。YouTube アプリが参照できる値 |
| `base/allocator/miracle_parameter.cc:20` | 物理メモリの区分（<512MB、<1GB、<2GB、…）ごとに Finch パラメータの名前を切り替える仕組み | Finch で区分ごとの値が配られた場合だけ効く |
| `gin/isolate_holder.cc:191` | V8 の `ConfigureDefaults(物理メモリ)` | 12-2 の注のとおり `--max-old-space-size=512` で上書きされる |
| `blink_platform_impl.cc`、`gl_surface_egl.cc`、`viz_utils.cc` | 物理メモリに応じた分岐 | Android の場合だけなので、Linux には関係ない |
| `content_main_runner_impl.cc:431`、`gpu_main.cc:184`、`gpu_util.cc:988` | 値を事前に読んでおく、情報として報告する | 量は変わらない |

### 12-5. CPU 数で決まるもの

| 場所 | 内容 |
|---|---|
| `starboard/linux/shared/media_is_video_supported.cc` | 16 コア以上なら 8K、それ未満なら 1080p まで対応と申告（Step 10。**メモリへの影響が最も大きい**） |
| `starboard/shared/libdav1d/dav1d_video_decoder.cc:163` | dav1d が全コアを使う（Step 10） |
| `base/task/thread_pool/thread_pool_instance.cc`（Cobalt パッチ） | Starboard ではフォアグラウンドのスレッド数 = min(max(3, CPU 数 − 1), `kSbMaxThreads`)。Linux は `kSbMaxThreads = 90`（`starboard/linux/shared/configuration_constants.cc:54`） |
| `content/browser/gpu/compositor_util.cc` | レンダラのラスタスレッド数（Android TV を Android の分岐から外すパッチ） |
| `third_party/blink/renderer/core/frame/navigator_concurrent_hardware.cc` | JS の `navigator.hardwareConcurrency`。YouTube アプリが参照できる |

### Step 12 まとめ

1. **メモリ量による分岐は、3 つの方法でほぼ固定されている**:
   - (a) `--enable-low-end-device-mode` を常に付けて、上流の `IsLowEndDevice()` の分岐を常に低スペック側にする
   - (b) メモリ量に応じた計算を、固定値や Finch のパラメータに置き換えるパッチ（画像 128MB、Skia 2MB、GPU discardable 1MB、V8 512MB、prepaint 0%、HTTP キャッシュは Starboard の定数）
   - (c) Starboard の定数（`kSbMaxSystemPathCacheDirectorySize`、`kSbMaxThreads`、MSE の予算）
2. **V8 のヒープ上限も 512MB に固定されていた**（Step 10 の訂正）。ただしソースからの判断で、実行時には確認していない。
3. メモリ量に応じて変わるものとして残っているのは、Blob の上限、discardable 共有メモリの上限、保持フレーム数、`navigator.deviceMemory` くらい。どれも小さい端末で効く方向の調整。
4. 一方で **CPU 数に応じて決まるものは残っている**（申告する最大解像度、dav1d のスレッド数、スレッドプール）。この PC での計測値に一番効いていたのはこれだった（Step 10）。
5. 削減の設定の多くは **Finch 機能のコンパイル時の既定値**（`base/features.cc`）にもあり、`gn args` を見ても分からない。

---

## Step 13. Starboard に VA-API デコーダを追加し、ハードウェアデコード時のメモリを測る

### 13-1. 実装（簡易版: VA-API でデコードし、結果を CPU 側にコピーする）

パッチ: `~/chrobalt/vaapi_experiment.patch`（4 ファイル、+約 220 行。コミットはしていない）。
**環境変数 `COBALT_EXPERIMENTAL_VAAPI` を設定したときだけ動作が変わる**ので、通常の動作には影響しない。

| ファイル | 変更内容 |
|---|---|
| `starboard/shared/ffmpeg/ffmpeg_video_decoder_impl.{h,cc}` | ・`=1` のとき、`av_hwdevice_ctx_create(VAAPI, /dev/dri/renderD128)` で作ったデバイスを `codec_context->hw_device_ctx` に設定し、`get_format` で `AV_PIX_FMT_VAAPI` を選ぶ<br>・`get_buffer2` は ffmpeg の既定（ハードウェアのフレームプール）を使う<br>・デコード結果は `av_hwframe_transfer_data` で NV12 として CPU 側に取り出し、UV を分離して I420 にしてから `CpuVideoFrame::CreateYV12Frame` に渡す<br>・hwcontext 関連の関数は `FFMPEGDispatch` に無いので、`RTLD_GLOBAL` で読み込み済みの libavutil / libavcodec から `dlsym(RTLD_DEFAULT, ...)` で取得する<br>・FFmpeg 4.0 以上（`LIBAVCODEC_VERSION_MAJOR >= 58`）の場合だけ有効（同じ .cc が古い libav 用にもビルドされるため）<br>・VP9 → `AV_CODEC_ID_VP9` の対応を追加 |
| `starboard/linux/shared/player_components_factory.cc` | `=1` のとき、VP9 を `VpxVideoDecoder` ではなく `FfmpegVideoDecoder` に回す |
| `starboard/linux/shared/media_is_video_supported.cc` | `=1` または `=sw` のとき、AV1 と 8bit 以外を非対応と申告する（この PC では AV1 の VA-API デコードが失敗するので、YouTube に VP9 を選ばせる）。`=sw` は「VP9 を libvpx でデコードする」比較用 |

- ビルド: `autoninja -C out/linux-x64x11_gold cobalt` で **16 ステップ、3 秒**（変更は `libstarboard.so` だけで、`cobalt` 本体は再リンクされない）。
  最初は、古い libav 用のビルドで新しいメンバを使っていないため `-Wunused-private-field`（`-Werror`）で失敗したので、使っていないことを明示して修正した。
- strip した `libstarboard.so.18` を `run-gold/` に入れた（7.04MB。変更前は 7.03MB で、変更前のものは `.sw-only` として残してある）。

### 13-2. 計測方法の追加

`mem_sample.py` に、DRM の fdinfo（`/proc/<pid>/fdinfo/<fd>` の `drm-total-system0`、`drm-resident-system0`、`drm-engine-video`）を
`drm-client-id` ごとに 1 回だけ数える処理を追加した。**GPU のバッファ（デコード面など）は RSS / PSS に含まれない**ので、別に足す必要がある。

### 13-3. 結果（同じ動画 `aqz-KE-bpKQ` を 180 秒再生）

| 条件 | YouTube が選んだ形式 | デコーダ | 定常の PSS | ピークの PSS | GPU 常駐（定常） | GPU 確保（ピーク） | ビデオエンジンの使用時間 |
|---|---|---|---|---|---|---|---|
| E0（Step 10） | AV1 4K | dav1d（ソフトウェア、24 スレッド） | 874MB | 948MB | 0 | 0 | 0 秒 |
| **H0** `=sw` | VP9 4K（`vp09.00.51.08`、3840x2160） | libvpx（ソフトウェア） | **573MB** | 630MB | 0 | 0 | 0 秒 |
| **H1** `=1` | VP9 4K（同じ） | **VA-API（ハードウェア）** | **411MB** | 474MB | **89MB** | 176MB | **21.2 秒** |

- 確認したこと:
  - ログ `FfmpegVideoDecoder: VA-API hardware decoding enabled for codec 8`（8 = `kSbMediaVideoCodecVp9`）、`Playing video using ffmpeg::VideoDecoder`、`natural size: [3840,2160]`
  - ビデオエンジンの使用時間が 21.2 秒増えた → 実際に GPU のハードウェアでデコードしている
  - 30 秒ごとのスクリーンショットが毎回変化。180 秒時点の場面は H0 と H1 でほぼ同じ → どちらも通常の速度で再生できている
  - 色が正しい（草、空、岩が自然な色）→ NV12 → I420 の変換は正しい（`mem/H_compare_60s.jpg`、`mem/H_compare_180s.jpg`）
- 比較:
  - **VP9 のソフトウェア → ハードウェア**: プロセスの PSS は **−162MB**（573 → 411）。代わりに GPU 側に **+89MB**（常駐）。**合計で約 −73MB**。
  - AV1（dav1d） → VP9（libvpx）: −301MB。dav1d は 24 スレッドでフレームスレッドが多いことが効いている（Step 10）。

### 13-4. 注意（この数字の限界）

- **CPU 側へのコピーがある簡易版**なので、デコード済みフレームを CPU 側（`CpuVideoFrame`）にも持っている。
  コピーせずに GPU 上のまま描画に渡す本来の実装なら、プロセス側はさらに小さくなるはず（未実装・未計測）。
- 描画は Xvfb 上のソフトウェアレンダリング（Mesa）なので、実機とは描画側の内訳が違う。
- GPU の 89MB は、4K の NV12 デコード面（1 枚あたり約 12MB）、参照フレーム、ffmpeg のフレームプールの合計と考えられる（内訳は未計測）。
- AV1 はこの PC の VA-API で失敗するので測れていない（Step 11-4、11-5）。AV1 のハードウェアデコードは VP9 と同程度と推測されるが、未確認。
- 単一の動画を 1 回ずつ計測しただけで、ばらつきは評価していない。

### Step 13 まとめ

- **Starboard の ffmpeg デコーダに VA-API を追加し、Cobalt（gold、strip 済み）で YouTube の 4K VP9 をハードウェアでデコードできた。**
  変更は約 220 行、差分ビルドは 3 秒。
- **同じ VP9 4K で比べると、ハードウェアデコードではプロセスのメモリが 573MB → 411MB（−162MB）になり、GPU 側に 89MB 増えた。合計で約 −73MB。**
- 最初の AV1 ソフトウェアデコード（874MB）と比べると、合計で 500MB（411 + 89）まで下がった。
- メモリを比べるときは、RSS / PSS だけでなく、**DRM fdinfo の GPU メモリを足さないと、ハードウェアデコードの方が実際より小さく見える**。

---

## Step 14. ハードウェアデコードとソフトウェアデコードのメモリの違い（3 回計測、内訳、理由）

### 14-1. 方法

- 条件: VP9 4K（`aqz-KE-bpKQ`、3840x2160）、gold（strip 済み）、Xvfb 1920x1080、180 秒再生、最初の 20 秒は 0.1 秒ごとにサンプリング。
  ソフトウェア（`COBALT_EXPERIMENTAL_VAAPI=sw` → libvpx）とハードウェア（`=1` → VA-API）を **各 3 回**（1 回目は Step 13。2・3 回目は交互に実行）。
- 2・3 回目は 120 秒時点で `/proc/<pid>/smaps` を保存（`SMAPS_AT=120`）。
- VA-API のサーフェスプールの構成を 1 回だけログに出すコードを追加した（`AVHWFramesContext` の `initial_pool_size`、`width`、`height`、`sw_format`）。
- 集計の修正: ビデオエンジンの使用時間に「終了直前の行」を使っていたので、GPU の fd が閉じた後の値（0.5 秒）が出ていた。**最大値を使うように直した**（実際には 166 秒時点で 19.6 秒と正常に増えていた）。

### 14-2. ばらつき（3 回）

| | 1 回目 | 2 回目 | 3 回目 | **平均 ± 標準偏差** |
|---|---|---|---|---|
| ソフトウェア（libvpx）定常の PSS | 573.0 | 571.4 | 574.2 | **572.9 ± 1.4MB** |
| ハードウェア（VA-API）定常の PSS | 411.0 | 410.0 | 412.3 | **411.1 ± 1.2MB** |
| ソフトウェア ピークの PSS | 630.3 | 631.3 | 630.2 | 630.6 ± 0.6MB |
| ハードウェア ピークの PSS | 474.3 | 459.7 | 462.2 | 465.4 ± 7.8MB |
| ハードウェア GPU 常駐（定常） / GPU 確保（ピーク） | 89.0 / 176.0 | 89.0 / 176.0 | 89.0 / 176.0 | 89.0 / 176.0MB（ばらつき 0） |

- どの回も、解像度は 3840x2160、30 秒ごとのスクリーンショットは毎回変化、ハードウェアではビデオエンジンの使用時間が増加（約 20 秒）。
- **差（−161.8MB）は標準偏差（1MB 台）より 2 桁大きく、再現性は高い。**
- ハードウェアの合計（プロセス + GPU 常駐）= 411.1 + 89.0 = **500.1MB**。ソフトウェアの 572.9MB と比べて **−72.8MB（−12.7%）**。

### 14-3. 内訳

**プロセス側（120 秒時点の smaps。2・3 回目の平均）**

| 項目 | ソフトウェア | ハードウェア | 差 | 根拠・対応するもの |
|---|---|---|---|---|
| `[anon:partition_alloc]` | 382.3 / 371.7（平均 377.0） | 212.5 / 246.8（平均 229.7） | **−147.3MB** | libvpx の内部フレームバッファ（下の計算） |
| スレッド数 | 98 | 90 | **−8** | `vpx_video_decoder.cc:130` `vpx_config.threads = 8` に対し、VA-API 側は `thread_count = 1` |
| GPU ドライバのライブラリ | — | `iHD_drv_video.so` 4.7MB、`libigdgmm.so` 0.5MB | +5.2MB | smaps の該当マッピング |
| 名前なしの anon | 15.2 | 21.5 / 22.7 | +約 7MB | ドライバや libva のヒープ（推定） |
| `cobalt` 本体、Mesa | 約 95 / 33 | 約 95 / 33 | 0 | 共通 |

- **libvpx のフレームバッファ**（ソースから計算）:
  `vp9_onyxc_int.h:41` `FRAME_BUFFERS = REF_FRAMES(8) + 1 + REFS_PER_FRAME(3) = 12`、
  `yv12config.h:27` `VP9_DEC_BORDER_IN_PIXELS = 32`
  → 1 枚 (3840+64)×(2160+64)×1.5 = **12.42MiB**、12 枚で **149.0MiB**。
  `partition_alloc` の差 147.3MB とほぼ一致する（4K の再生中は 12 枚すべてが使われていると考えられる）。

**GPU 側（DRM fdinfo とプールのログ）**

- ログ: `VA-API surface pool: initial_pool_size=12 size=3840x2160 sw_format=23 (NV12=23)`
  → ffmpeg の VA-API デコーダも **12 枚**のサーフェスを確保している（libvpx と同じ枚数）。
- 1 枚の大きさの見積もり: NV12 で高さを 2176 にアラインすると仮定して 3840×2176×1.5 = 11.95MiB、12 枚で約 143MiB（**推定**。実際のアライメントやタイリングは確認していない）。
- `drm-total-system0` のピーク 176MB = サーフェス約 143MB + その他のドライバのバッファ（ビットストリーム、動きベクトル、確率テーブル、バッチバッファなど）約 33MB（**推定**）。
- `drm-resident-system0` は **89MB**。確保した 176MB のうち実際にページが割り当てられているのは約半分（サーフェス約 7 枚分）。
  i915 の GEM オブジェクトは使われたときに初めてページが割り当てられるため、と考えている（**推定**。確認には root の debugfs が必要）。

### 14-4. なぜメモリが減ったのか / なぜ大きくは減らないのが正常なのか

1. **参照フレームは、ハードウェアでもソフトウェアでも必ず必要**
   - VP9 は参照フレームを 8 枠持つ（`REF_FRAMES = 8`）。デコーダの実装方法に関係なく、規格上必要なメモリ。
   - ハードウェアデコードでは、これが **CPU 側のヒープから GPU 側のサーフェスに移るだけ**。どちらも 12 枚。
   - Intel の内蔵 GPU やテレビの SoC のような**ユニファイドメモリ（UMA）では、GPU のメモリも物理的には同じ DRAM**。
     → 「ハードウェアデコードにすれば、デコーダのメモリが消える」わけではない。**移るだけなのが正常**。
2. **今回減った 72.8MB の内訳**（ソフトウェア → ハードウェア）
   - フレームバッファ: プロセス側 −147MB に対して GPU 側 +89MB（常駐）→ **−58MB**。
     理由は、libvpx のバッファは 32px の余白付きで 12 枚すべて常駐しているのに対し、GPU 側は余白なしで、常駐しているのは約半分だから（後者は推定）。
   - デコードスレッド 8 本分（スタックとスレッドごとの作業領域）が減った。
   - VA-API ドライバの分（約 +12MB）が増えた。
3. **ハードウェアデコードで本当に大きく減らせるのは「CPU 側へのコピー」**
   - 今回の簡易版では、ソフトウェアとハードウェアの両方で、デコード済みフレームを `CpuVideoFrame` として**最大 12 枚**持っている
     （`GetMaxNumberOfCachedFrames() = 12`。`vpx_video_decoder.h:54` と `ffmpeg_video_decoder_impl.h:72`）。4K で 1 枚 11.87MiB、**最大 142.4MiB**。
   - 実機の Starboard 移植では、デコード済みフレームをアプリのプロセスに渡さない **punch-out 出力**が使われる
     （`starboard/player.h:89-95`: 映像を最背面に描画し、プラットフォームがグラフィックスを上に重ねる。android 4、tvos 2、contrib/rdk 3 ファイルで使われている）。
     この方式なら、CPU 側のフレームキャッシュ（最大約 142MiB）と、描画用のテクスチャへの転送が不要になる。
     → **実機でのハードウェアデコードのメモリ削減は、主にこの「コピーが無くなる」ことから来る**と考えられる（**未実装・未計測の推定**）。
4. まとめると:
   - 参照フレーム（DPB）の分は、ハードウェアでもソフトウェアでも**減らないのが正常**（GPU 側に移るだけ）。
   - 減るのは、ソフトウェアデコーダ特有のもの（余白、スレッド、作業バッファ）と、コピーなしの出力経路にしたときの CPU 側フレームキャッシュ。
   - 今回の簡易版は前者だけを反映しているので −72.8MB（−12.7%）にとどまった。

### 14-5. 未確認・推定のもの

- GPU サーフェス 1 枚の実際の大きさ（タイリング、アライメント）と、確保 176MB / 常駐 89MB の差の正確な理由（i915 の GEM オブジェクトの一覧は root が必要）。
- コピーなしの経路（punch-out または dma-buf を直接テクスチャにする）での実測値。
- AV1 のハードウェアデコード（この PC では動作しない）。
- 実機（テレビの SoC）での値。安全なメモリ領域や CMA にあるデコーダのメモリは、プロセスの PSS にも DRM fdinfo にも出ない場合がある。

### Step 14 まとめ

- 3 回の計測で、**ソフトウェア 572.9 ± 1.4MB、ハードウェア 411.1 ± 1.2MB（+ GPU 89.0MB）**。再現性は高い。
- プロセス側の差（−147MB）は、**libvpx のフレームバッファ 12 枚（ソースから計算すると 149MiB）**で説明できる。
  ハードウェア側では、同じ 12 枚のサーフェスが GPU 側（ユニファイドメモリなら同じ DRAM）に移っている。
- **参照フレームのメモリは、ハードウェアデコードでも減らないのが正常。** 今回の正味の削減（−72.8MB）は、余白、スレッド、常駐ページの差によるもの。
- 実機で大きく減るとすれば、それは **CPU 側にコピーしない出力経路（punch-out など）で、CPU 側のフレームキャッシュ（最大約 142MiB）が無くなること**による、というのがソースに基づく見立て（未計測）。


> 訂正（記事作成時）: cgroup の `memory.peak`（バイト）を 10 進の MB で書いていた箇所を、他の値と同じ 2^20 換算に統一した（281→268、894→852、238→227）。

---

## Step 15. ROM の未計測部分の計測（コンパイル設定と //chrome 層）

### 15-1. 方法

- gold の `args.gn` に 1 行足した出力ディレクトリを作り、`cobalt` をビルドして strip 後のサイズを比較した（キュー: `~/chrobalt/rom_queue.sh`、結果: `~/chrobalt/rom_sizes.tsv`）。
  - `rom_O2`: `optimize_for_size = false`
  - `rom_nocfi`: `is_cfi = false`
  - `rom_nolto`: `use_thin_lto = false` + `is_cfi = false`（`build/config/compiler/compiler.gni:164` の `assert(!is_cfi || use_thin_lto, "CFI requires ThinLTO")` のため、CFI も外す必要がある）
  - ICF: gold のディレクトリで一時的に `use_icf = false` にしてリンクし直し、測った後に元に戻して再リンクした（戻した後のサイズが元の 114,060,408 バイトと一致することを確認）。
- `//chrome` 層: 同じソースツリーで `cobalt/build/gn.py -p chromium_linux-x64x11 -c gold --no-rbe`（`is_cobalt=false`、`is_official_build=true`、`optimize_for_size=false`、ThinLTO・CFI・ICF は有効、`chrome_pgo_phase=0`）を生成し、`chrome` と `content_shell` をビルドした。
- 所要時間: `rom_O2` 1h26m、`rom_nocfi` 1h24m、`rom_nolto` 約 1h24m、ICF の切り替えと戻しが各 49m、上流 Chromium 2h28m（51,088 ステップ）。

### 15-2. 上流 Chromium のビルドで起きたこと

1. 1 回目は 20 秒で失敗した: `//chrome/browser/metrics:expired_histograms_array` の生成スクリプトが、
   `The --inputs is not in sync with the most updated list of xmls ... add: tools/metrics/histograms/metadata/cobalt/histograms.xml, .../cobalt/enums.xml` で停止。
   Cobalt のパッチ（`components/metrics/generate_expired_histograms_array.gni`、+4 行）は `if (is_cobalt)` のときだけ Cobalt の XML を入力に加えるが、スクリプトはディスク上の全 XML を対象に整合性を確認するため、`is_cobalt=false` では食い違う。
2. 2 回目: gni で 2 つの XML を条件なしで入力に加えたところ、`Duplicate enum Android.MemoryPressureNotification`、`Duplicate enum BooleanHung`、`Duplicate histogram definition Android.MemoryPressureNotification{AndroidProcessType}` で失敗した（Cobalt の XML が上流の定義と重複している）。gni は元に戻した。
3. 3 回目: ビルド中だけ `tools/metrics/histograms/metadata/cobalt` をツリーの外へ退避し、終了時に戻した（`trap`）。ビルドは成功し、XML も戻ったことを確認した（`git status` に差分なし）。
   → **このソースツリーのままでは、上流の `chrome` はビルドできない**。CI（`.github/config/chromium_linux.json`）でビルドしているのは `content_shell`、`chromedriver` などで、`chrome` は含まれていない。
- キューの不具合: 上流 Chromium 用の 2 本目のキュー（`rom_queue2.sh`）は、1 本目から関数を切り出して読み込む作りにしたため、`chrome` のサイズが記録されず `content_shell` が 2 行記録された。2 つのバイナリは手で strip して測り直した（下の表の値）。

### 15-3. 結果（strip 後、1 MB = 2^20 バイト）

| 構成 | strip 後 | `.text` | `.rodata` | `.rela.dyn` | `.data.rel.ro` |
|---|---|---|---|---|---|
| gold（基準） | 108.8 MB（114,060,408） | 82.3 | 12.8 | 8.9 | 3.9 |
| `-Os` を外す | 123.0 MB（129,014,904） | 96.4 | 13.0 | 8.9 | 3.9 |
| ICF を外す | 119.3 MB（125,119,608） | 91.9 | 13.6 | 9.0 | 4.0 |
| CFI を外す | 103.4 MB（108,448,888） | 77.9 | 12.6 | 8.5 | 3.6 |
| ThinLTO と CFI を外す | 103.7 MB（108,686,456） | 78.3 | 12.6 | 8.5 | 3.6 |
| 上流 `chrome`（`-O2`） | 283.4 MB（297,151,608） | 228.0 | 19.5 | 22.2 | 10.1 |
| 上流 `content_shell`（`-O2`） | 168.8 MB（176,954,568） | 139.3 | 11.5 | 11.5 | 5.5 |

- `-Os`: −14.3 MB。ICF: −10.5 MB。CFI: +5.4 MB（セキュリティ機能のための増加）。ThinLTO 単独（CFI を外した構成との差）: −0.2 MB。
- 分解（同じソースツリー）: `chrome` 283.4 → `//chrome` 層 −114.6 → `content_shell` 168.8 → Cobalt 独自の機能削減 −45.8 → `cobalt`（`-O2`）123.0 → `-Os` −14.3 → gold 108.8。
- `content_shell` は ICU データと V8 の起動用データを別ファイルにしており、`cobalt` は本体に埋め込んでいるので、Cobalt 独自の機能削減は 45.8 MB より大きい。
- 同じソースからビルドした `chrome`（283.4 MB）は Chrome for Testing（254.5 MB）より大きい。今回のビルドは `chrome_pgo_phase=0`（PGO なし）、`is_chrome_branded=false`。Chrome for Testing のビルド条件は確認していない。

### Step 15 まとめ

- Chrome から Cobalt までの差（同じソースツリーで 283.4 → 108.8 MB）は、**`//chrome` 層 114.6 MB、Cobalt 独自の機能削減 45.8 MB 以上、`-Os` 14.3 MB** に分解できた。
- 両方の構成に入っている ICF は 10.5 MB 減らしており、ThinLTO 単独の効果は 0.2 MB だった。
- Cobalt 独自の機能削減の内訳（Web API の除外、ビルド設定による機能の除外、Starboard の分離など）は個別には測っていない。

---

## Step 16. Cobalt shell と CEF（Chromium Embedded Framework）の比較

### 16-1. 対象

| | ソース / バイナリ |
|---|---|
| CEF | `https://github.com/chromiumembedded/cef` ブランチ `7204`（commit `6981a09edb2b`、「Update to Chromium version 138.0.7204.310」）を `~/chrobalt/cef` に `--depth 1` で clone。`CHROMIUM_BUILD_COMPATIBILITY.txt` は `refs/tags/138.0.7204.310` |
| CEF のバイナリ | 公式ビルド（cef-builds.spotifycdn.com）の `cef_binary_138.0.62+g6981a09+chromium-138.0.7204.310_linux64_minimal.tar.bz2`（366.2 MB、clone したコミットと同じ `g6981a09`） |
| Cobalt | 27.lts.13（Chromium 138.0.7204.311） |

### 16-2. CEF は `//chrome` をまるごと含む

- `cef/BUILD.gn` の `source_set("libcef_static")`（482 行目〜）の依存に `"//chrome:dependencies"`（916 行目）があり、`//chrome/app/chrome_main_delegate.cc` などの Chrome のソースも直接取り込んでいる（`"//chrome/...` の参照は 36 箇所）。
- 上流 `chromium/m138` の `chrome/BUILD.gn` の `group("dependencies")` は `//chrome/browser`、`//chrome/child`、`//chrome/common`、`//chrome/gpu`、`//chrome/renderer`、`//chrome/utility`、`//components/sync` などを含む。
- → CEF は Chrome のブラウザ層の上に組み込み用の API を足したもの。Cobalt は `//chrome` のターゲットを 1 つも含まない（Step 4）。

### 16-3. サイズ（strip 後、1 MB = 2^20 バイト）

| バイナリ | strip 後 | `.text` | `.rodata` | `.rela.dyn` | `.data.rel.ro` |
|---|---|---|---|---|---|
| CEF `libcef.so`（138.0.62、配布物は strip 前 1,381 MB） | **226.2 MB**（237,235,328） | 175.0 | 17.7 | 22.3 | 9.8 |
| Chrome for Testing 138.0.7204.183 `chrome` | 254.5 MB | 197.0 | 20.1 | 22.1 | 10.1 |
| 同じソースの上流 `chrome`（`-O2`、PGO なし） | 283.4 MB | 228.0 | 19.5 | 22.2 | 10.1 |
| 同じソースの上流 `content_shell`（`-O2`） | 168.8 MB | 139.3 | 11.5 | 11.5 | 5.5 |
| Cobalt `cobalt`（gold） | 108.8 MB（+ `libstarboard.so` 7.0 MB） | 82.3 | 12.8 | 8.9 | 3.9 |

- CEF の公式ビルドの GN 引数（PGO や `-Os` の有無など）は確認していないので、Chrome for Testing との差（−28.3 MB）の理由は不明。
- CEF は Chrome とほぼ同じ規模で、Cobalt の約 2.1 倍。

### 16-4. Cobalt shell の正体: `content_shell` の改造版

| ファイル（`cobalt/shell/browser/` と `content/shell/browser/`） | `content_shell` | Cobalt | 共通行（Cobalt に対する割合） |
|---|---|---|---|
| `shell.cc` | 825 行 | 1,468 行 | 554（38%） |
| `shell_content_browser_client.cc` | 1,039 行 | 771 行 | 618（80%） |
| `shell_browser_main_parts.cc` | 235 行 | 264 行 | 152（58%） |
| `shell_platform_delegate_views.cc` | 463 行 | 483 行 | 238（49%） |
| `shell_javascript_dialog_manager.cc` | 141 行 | 95 行 | 70（74%） |
| `shell_devtools_frontend.cc` | 84 行 | 94 行 | 75（80%） |

（`difflib.SequenceMatcher` で一致した行数。`shell.cc` の著作権表記は「Copyright 2025 The Cobalt Authors」）

### 16-5. 機能の対比

| 機能 | CEF（`include/cef_*.h` 85 ファイル + `include/views/` 21 ファイル） | Cobalt shell / Cobalt |
|---|---|---|
| 想定用途 | 任意のアプリにブラウザを組み込む汎用の API（`cef_browser.h`、`cef_client.h`、`cef_app.h`） | YouTube のテレビ向けアプリ専用（起動 URL は `https://www.youtube.com/tv`） |
| プロセス構成 | マルチプロセス（`cef_process_message.h`、`cef_render_process_handler.h`） | 単一プロセス（`--single-process` を常に付ける） |
| JavaScript との連携 | V8 を直接操作する API（`cef_v8.h`、36 KB） | Blink の Web IDL として独自 API を追加（`H5vcc*`、16 の IDL: accessibility、experiments、memory、metrics、native_stability、platform_service、runtime、settings、storage、system、updater など） |
| ダウンロード | `cef_download_handler.h`、`cef_download_item.h` | なし（`ShellBrowserContext::GetDownloadManagerDelegate()` が `nullptr`） |
| 印刷 | `cef_print_handler.h`、`cef_print_settings.h` | なし（`printing/` は 3 ファイル、`.text` 0.00 MB） |
| ファイル選択ダイアログ | `cef_dialog_handler.h` | なし（`RunFileChooser` を実装していない。`content_shell` は実装） |
| カメラ・マイクの許可 | `cef_permission_handler.h` | 音声以外は `PERMISSION_DENIED`（`shell.cc` の `RequestMediaAccessPermission`） |
| 画面外への描画（OSR） | `cef_render_handler.h` | なし（Starboard の画面に直接描画） |
| UI 部品 | `include/views/`（ボタン、テキスト欄、ウィンドウなど 21 ファイル）、`cef_menu_model.h`、`cef_context_menu_handler.h` | YouTube の Web アプリ自身が UI を描く。ネイティブの UI 部品はスプラッシュ画面程度（`splash_screen_*`） |
| 通信への介入 | `cef_resource_request_handler.h`、`cef_request_handler.h`、`cef_response_filter.h`、`cef_cookie.h`、`cef_scheme.h` | `h5vcc-embedded://` スキームの読み込み（`h5vcc_scheme_url_loader_factory.cc`）、Client Hints ヘッダ、HTTPS / CSP の強制（`cobalt_secure_navigation_throttle.cc`） |
| Chrome の設定・コマンド | `cef_preference.h`、`cef_command_handler.h`、`cef_task_manager.h` | なし |
| メディアの送信先（Cast） | `cef_media_router.h` | なし（`components/media_router` のリンク済みコード 0） |
| Chrome 由来の機能（パスワード管理、自動入力、Safe Browsing、同期、翻訳、履歴、ブックマーク、PDF ビューア、拡張機能） | `//chrome:dependencies` 経由で含む（例: `//chrome/browser/resources/pdf:resources` を直接参照） | 機能としては無い。`//content` が参照する共通部分だけがリンクされている（`.text`: password_manager 0.01 MB、download 0.15 MB、translate・history・bookmarks・pdf・extensions は 0） |
| テレビ向けの機能 | なし | Starboard（動画再生、DRM、音声、入力、画面）、DIAL（`cobalt/browser/dial`）、画面上のキーボード（`on_screen_keyboard`）、ライフサイクル管理（`lifecycle`）、Evergreen の更新（`h5vcc_updater`、`cobalt/updater`）、ディープリンク（`h5vcc_runtime`）、メトリクス・クラッシュ注記（`metrics`、`crash_annotator`） |
| 開発者ツール | `cef_devtools_message_observer.h` | 非リリースビルドのみ（gold では `enable_devtools_backend=false`） |

### Step 16 まとめ

- **CEF は `//chrome` をまるごと取り込む**（`libcef_static` → `//chrome:dependencies`）。そのため `libcef.so` は strip 後 226.2 MB で、Chrome と同じ規模。CEF を使っても `//chrome` 層（−114.6 MB）は減らせない。
- **Cobalt shell は `content_shell` を元にした YouTube 専用の shell** で、汎用の組み込み API（ダウンロード、印刷、ファイル選択、画面外への描画、V8 の直接操作、ネイティブ UI 部品）を持たない代わりに、Starboard とテレビ向けの機能、`H5vcc` という Web API を持つ。
- Cobalt が −114.6 MB を実現できているのは、「YouTube の Web アプリ 1 つだけを動かす」と用途を絞り、汎用ブラウザに必要な Chrome 層を丸ごと持たない構成にしているため。

### Step 16 追補: CEF と Google サインイン、Cobalt のサインイン
- Google Security Blog 2019-04「Better protection against Man in the Middle phishing attacks」: CEF など埋め込みブラウザ経由の Google サインインをブロック。開発者向けの解決策は「browser-based OAuth authentication」（CEF に //chrome を入れることではない）。
- CEF の Alloy→Chrome ランタイム一本化: cef issue #3681（2024-04-11）の理由は「Chrome runtime は Chrome の UI と機能を全部サポート」「ランタイムを起動時に 1 つ選ぶ必要がある問題の解消」「最終的に Alloy bootstrap を削除」。サインインは理由に書かれていない（他の issue は未確認）。
- Cobalt: ソース（cobalt/, starboard/）に accounts.google.com・OAuth・device code の実装なし。cobalt/shell/common/device_authentication.cc は起動 URL に端末証明書の鍵（SbSystemSignWithCertificationSecretKey, kSbSystemPropertyCertificationScope）で署名を付けるだけ＝端末の認証であってユーザーのサインインではない。
- ユーザーのサインインは YouTube の Web アプリ側（一般知識・未検証: OAuth 2.0 for TV and Limited-Input Devices、スマホで yt.be/activate にコード入力）。ブラウザ内でパスワードを入力しないので埋め込みブラウザのブロック対象にならない。
- 追補（ユーザー確認）: Cobalt で Sign in を選ぶと「Scan QR code or go to yt.be/activate / Enter the code XXX-XXX-XXXX」画面（Sign in with your phone）。端末外でサインインする方式であることを画面で確認。もう 1 つの「Sign in with your remote」の中身は未確認。

## Step 17. content_shell と cobalt shell の差（ファイル構成・依存・DWARF でのコード量）
- ファイル: content/shell 143 / cobalt/shell 98（.cc/.h/.mm/.gn/.java）、同名 56。
  - cobalt/shell のみ: splash_screen*、h5vcc_scheme_url_loader_factory、migrate_storage_record、picture_in_picture、on_screen_keyboard(tvOS)、device_authentication、url_constants、Android の StartupGuard。
  - content/shell のみ: browser/bluetooth(13)、shell_permission_manager、shell_origin_trial_policy、color_chooser、protocol(DevTools 拡張)、gpu/utility/render_frame_observer、web test 用ヘルパー。
- クラス構成: cobalt/shell は namespace content の content_shell 派生。cobalt/ 層が継承（CobaltMainDelegate : ShellMainDelegate、CobaltContentBrowserClient : ShellContentBrowserClient、CobaltBrowserMainParts : ShellBrowserMainParts）。Renderer/GPU/Utility client は Cobalt 独自（Shell 版を継承しない）。
- ShellContentBrowserClient の override: content_shell 44 / cobalt shell 40。cobalt で削除: AreIsolatedWebAppsEnabled、BindBrowserControlInterface、ExposeInterfacesToChild、Cookie Deprecation Label 2 個、IsFencedStorageReadAllowed、OnNetworkServiceCreated 等。追加: 非ネットワーク URLLoaderFactory 登録 4 個（h5vcc-embedded スキーム用）、GetCacheStoragePath。CobaltContentBrowserClient がさらに 20 個 override（UA、ナビゲーションスロットル、キャッシュ quota、PiP など）。
- BUILD.gn の依存: content_shell のみ = //content/web_test:*、//device/bluetooth、//components/permissions、//components/origin_trials、crashpad/breakpad、//sandbox、//ppapi テストプラグイン、//ui/shell_dialogs、//tools/v8_context_snapshot 等。cobalt shell のみ = //cobalt/browser/*（h5vcc_runtime、lifecycle、on_screen_keyboard）、//cobalt/updater、//ui/ozone/platform/starboard、//starboard/common、//components/js_injection/browser。
- DWARF CU のコード量（.text 範囲、llvm-dwarfdump + cu_attr.py を 2 階層に細分化）: content_shell 131.7MB → cobalt(rom_O2、-Os なし) 91.6MB、差 40.2MB。
  | 区分 | content_shell | cobalt | 差 |
  |---|---|---|---|
  | Blink（core/modules/生成バインディング/platform） | 36.86 | 30.31 | 6.55 |
  | ブラウザ内の動画・画像デコーダ（libaom, libvpx, ffmpeg, dav1d, crabbyavif, media/gpu） | 5.19 | 0.01 | 5.18 |
  | WebGPU（Dawn, SPIR-V Tools） | 4.64 | 0.00 | 4.64 |
  | content/browser, content/services | 10.68 | 6.43 | 4.25 |
  | WebRTC | 4.25 | 0.22 | 4.03 |
  | ML（TFLite, XNNPACK, WebNN） | 3.55 | 0.02 | 3.53 |
  | device（Bluetooth/HID/USB 等） | 2.56 | 0.75 | 1.81 |
  | Rust | 1.83 | 0.60 | 1.23 |
  | web_test | 1.11 | 0.00 | 1.11 |
  | shell 本体（content/shell vs cobalt/shell） | 0.10 | 0.10 | 0.00 |
  | その他（skia 0.82, harfbuzz 0.65, v8 0.64, ozone 0.52 など） | | | 7.83 |
  cobalt/・starboard/・media/starboard の追加分は 0.5MB。
- 主な GN 引数の差（gn args --list）: use_dawn/skia_use_dawn true→false、use_webrtc_peer_connection true→false、build_with_tflite_lib/webnn_use_tflite true→false、media_use_ffmpeg/media_use_libvpx/enable_libaom/enable_ffmpeg_video_decoders true→false、use_starboard_media false→true、use_vaapi true→false、enable_vulkan true→false。
- 結論: shell の実装コード自体はどちらも約 0.1MB で差はない。差の 40MB は shell の置き換えではなく、cobalt のビルド構成（is_cobalt 用の GN 引数、Blink の sub_modules 除外パッチ、Step 4）によるもの。デコーダはブラウザから外れて libstarboard.so（7.0MB）側に移る（削除ではなく移動）。

## Step 18. テレビ向け Shell としての cobalt shell（機能面）
ここでの「cobalt shell」は cobalt/shell（content_shell 派生）＋ cobalt/app ＋ cobalt/browser（Shell を継承する Cobalt 層）＋ ui/ozone/platform/starboard。
- 起動: スプラッシュ画面を別 WebContents で表示（shell.h:97 LoadSplashScreenWebContents、:99 h5vcc.system.hideSplashScreen() で閉じる、最小表示時間・動画の preroll 待ち :308-334）。splash.html などは h5vcc-embedded スキームでメモリ内リソースから配信（h5vcc_scheme_url_loader_factory.h:46-49、キャッシュ版と組み込み版）。起動 URL に端末署名（device_authentication.cc）。旧 Cobalt（Starboard storage record）から Chromium のストレージへの移行（migrate_storage_record/migration_manager.h）。
- 画面: views ウィンドウは 1 枚。content_shell の views 実装にある URL 入力欄（Textfield 6）と戻る/進むボタンが cobalt 版には 0。ウィンドウサイズは SbWindowGetSize に合わせる（shell_platform_delegate_views.cc:302-312）。JavaScript の alert/confirm/prompt は表示せず抑止（shell_javascript_dialog_manager.cc:51 did_suppress_message=true、TODO コメントあり）。
- 入力: Ozone の Starboard プラットフォーム（platform_event_source_starboard.cc）が kSbEventTypeInput を ui のキー/マウスイベントに変換。画面キーボード API（on_screen_keyboard.idl、window_on_screen_keyboard.idl）。
- ライフサイクル: cobalt/app/app_event_delegate.cc が kSbEventType Start/Stop/Blur/Focus/Conceal/Reveal/Freeze/Unfreeze/Link/Input を処理。cobalt_lifecycle_manager.h: Conceal は 2 段階（Blink の visibilitychange/pagehide の完了 → ウィンドウの unmap と GPU（EGL）の後始末、:78-87）。Reveal の ACK 待ちでフォーカスを遅らせる（:72-75）。
- メディア: Starboard のプレーヤー（SbPlayer）を使う。Blink への追加 API: MediaKeys.getMetrics()、SourceBuffer.writeHead / appendTransferredBuffer（third_party/blink/renderer/modules/cobalt/）。Android TV のピクチャー・イン・ピクチャー（picture_in_picture_window_manager.h）。
- 外部連携: DIAL サーバー（cobalt/browser/dial: UDP と HTTP サーバー、JS 側 DialServer IDL で onGet/onPost/onDelete）。ディープリンク（kSbEventTypeLink → h5vcc_runtime/deep_link_manager）。
- 端末情報: User-Agent に Starboard のシステムプロパティ（ファームウェア版、端末種別、補助欄。user_agent_platform_info.cc:205,294,296）。client_hint_headers でヘッダーにも付与。
- 運用: Evergreen 更新（h5vcc.updater、//cobalt/updater）、ハング監視（hang_watcher_delegate_impl: H5vcc 設定 > Finch > 既定値の 3 段）、クラッシュ注記、メトリクス、メモリ ablation 実験（memory_ablation.h、上限 256MB）、HTTPS/CSP の強制はコマンドラインで（cobalt_secure_navigation_throttle.h）。
- Blink 側の Cobalt IDL: 25 個（h_5_vcc*.idl 13、dial 3、on_screen_keyboard 2、crash_log、deep_link_event、metrics_event、text_to_speech_change_event 2、media_keys_extensions、source_buffer_extensions）。
- gold で外れるもの: DevTools のバックエンド（content/browser/devtools/features.gni: enable_devtools_backend = enable_devtools_frontend || !(is_cobalt && cobalt_is_release_build)。gold の cobalt_shell_lib.ninja には shell_devtools_manager_delegate_stub.o のみ）。content_shell にある Bluetooth、権限管理、オリジントライアル、色選択、Web テストは cobalt shell にない。
