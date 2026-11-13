#!/usr/bin/env python3
"""Charts for the article. Values come from data/SUMMARY.txt, data/*/smaps_120s_breakdown.txt
and docs/investigation-log.md (Step 4-0, 8, 10, 14). usage: make_charts.py <out_dir>"""
import sys
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager

out = sys.argv[1] if len(sys.argv) > 1 else "."
for f in ("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",):
    font_manager.fontManager.addfont(f)
plt.rcParams.update({
    "font.family": "Noto Sans CJK JP", "font.size": 11,
    "axes.edgecolor": "#52514e", "axes.labelcolor": "#0b0b0b",
    "xtick.color": "#52514e", "ytick.color": "#0b0b0b",
    "figure.facecolor": "#fcfcfb", "axes.facecolor": "#fcfcfb",
})
BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"  # validated: dataviz validate_palette.js (light)


def finish(ax, title, xlabel):
    ax.set_title(title, loc="left", fontsize=13, color="#0b0b0b", pad=12)
    ax.set_xlabel(xlabel, color="#52514e")
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="x", color="#e4e3df", linewidth=0.8)
    ax.set_axisbelow(True)


def label(ax, bar, text):
    ax.text(bar.get_x() + bar.get_width() + 4, bar.get_y() + bar.get_height() / 2, text,
            va="center", ha="left", fontsize=10, color="#0b0b0b")


# 1. ROM: stripped binary size (Step 4-0, 3-7)
fig, ax = plt.subplots(figsize=(9, 2.8), dpi=150)
names = ["Chrome 138 (chrome)", "Chrobalt 27.lts.13\n(cobalt + libstarboard)"]
main = [254.5, 108.8]
sb = [0, 7.0]
b1 = ax.barh(names, main, color=BLUE, height=0.5, label="本体バイナリ")
b2 = ax.barh(names, sb, left=main, color=ORANGE, height=0.5, label="libstarboard.so", edgecolor="#fcfcfb", linewidth=2)
label(ax, b1[0], "254.5 MB")
label(ax, b2[1], "108.8 + 7.0 = 115.8 MB")
ax.invert_yaxis()
ax.set_xlim(0, 300)
ax.legend(loc="lower right", frameon=False)
finish(ax, "strip 後のバイナリサイズ（Linux x64）", "MB")
fig.tight_layout(); fig.savefig(f"{out}/rom_binary_size.png"); plt.close(fig)

# 2. RAM by condition (steady PSS + GPU resident), Step 8 / 10 / 14
fig, ax = plt.subplots(figsize=(9, 4.6), dpi=150)
rows = [
    ("ホーム画面で待機", 244.0, 0),
    ("AV1 4K 再生（24コア申告、dav1d）", 873.5, 0),
    ("AV1 1080p 再生（4コア申告）", 416.1, 0),
    ("AV1 1080p 再生（4コア申告＋4コア実行）", 364.3, 0),
    ("VP9 4K 再生 ソフトウェア（libvpx）", 572.9, 0),
    ("VP9 4K 再生 ハードウェア（VA-API）", 411.1, 89.0),
]
n = [r[0] for r in rows]
p = [r[1] for r in rows]
g = [r[2] for r in rows]
bp = ax.barh(n, p, color=BLUE, height=0.55, label="プロセスの PSS")
bg = ax.barh(n, g, left=p, color=ORANGE, height=0.55, label="GPU 常駐メモリ（DRM fdinfo）", edgecolor="#fcfcfb", linewidth=2)
for i, (pp, gg) in enumerate(zip(p, g)):
    bar = bg[i] if gg else bp[i]
    label(ax, bar, f"{pp:.0f} + {gg:.0f} = {pp + gg:.0f} MB" if gg else f"{pp:.0f} MB")
ax.invert_yaxis()
ax.set_xlim(0, 1050)
ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.14), ncol=2, frameon=False, fontsize=9)
finish(ax, "RAM 使用量（定常時、gold・strip 済み・単一プロセス）", "MB")
fig.tight_layout(); fig.savefig(f"{out}/ram_by_condition.png"); plt.close(fig)

# 3. VP9 4K SW vs HW breakdown (Step 14: smaps @120s mean of r2/r3, DRM fdinfo)
fig, ax = plt.subplots(figsize=(9, 2.9), dpi=150)
names = ["ソフトウェア（libvpx）", "ハードウェア（VA-API）"]
heap = [377.0, 229.7]
other = [572.9 - 377.0, 411.1 - 229.7]
gpu = [0, 89.0]
a = ax.barh(names, heap, color=BLUE, height=0.5, label="Chromium ヒープ（partition_alloc）")
b = ax.barh(names, other, left=heap, color=AQUA, height=0.5, label="その他のプロセスメモリ", edgecolor="#fcfcfb", linewidth=2)
c = ax.barh(names, gpu, left=[h + o for h, o in zip(heap, other)], color=ORANGE, height=0.5,
            label="GPU 常駐メモリ", edgecolor="#fcfcfb", linewidth=2)
for i in range(2):
    ax.text(heap[i] / 2, i, f"{heap[i]:.0f}", ha="center", va="center", color="#ffffff", fontsize=10)
    label(ax, c[i] if gpu[i] else b[i], f"合計 {heap[i] + other[i] + gpu[i]:.0f} MB")
ax.invert_yaxis()
ax.set_xlim(0, 700)
ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.32), ncol=3, frameon=False, fontsize=9)
finish(ax, "VP9 4K 再生時の内訳（3 回平均）", "MB")
fig.tight_layout(); fig.savefig(f"{out}/hw_vs_sw_breakdown.png"); plt.close(fig)
print("ok")

# 4. ROM waterfall: same-tree builds (data/rom_sizes.tsv; investigation log Step 15)
fig, ax = plt.subplots(figsize=(9, 3.6), dpi=150)
steps = [("chrome\n（上流構成、-O2）", 283.4, None), ("//chrome 層", -114.6, None),
         ("content_shell\n（上流構成、-O2）", 168.8, None), ("Cobalt 独自の\n機能削減", -45.8, None),
         ("cobalt\n（-O2）", 123.0, None), ("-Os", -14.3, None), ("cobalt\n（gold）", 108.8, None)]
x = range(len(steps)); level = 0
for i, (name, v, _) in enumerate(steps):
    if v > 0:
        bar = ax.bar(i, v, color=BLUE, width=0.6)
        ax.text(i, v + 5, f"{v:.1f}", ha="center", va="bottom", fontsize=10, color="#0b0b0b")
        level = v
    else:
        ax.bar(i, -v, bottom=level + v, color=ORANGE, width=0.6)
        ax.text(i, level + 5, f"{v:.1f}", ha="center", va="bottom", fontsize=10, color="#0b0b0b")
        level = level + v
ax.set_xticks(list(x)); ax.set_xticklabels([s[0] for s in steps], fontsize=9)
ax.set_ylim(0, 320); ax.set_ylabel("MB", color="#52514e")
ax.set_title("strip 後のサイズの分解（同じソースツリーでビルド）", loc="left", fontsize=13, color="#0b0b0b", pad=12)
ax.spines[["top", "right"]].set_visible(False); ax.grid(axis="y", color="#e4e3df", linewidth=0.8); ax.set_axisbelow(True)
fig.tight_layout(); fig.savefig(f"{out}/rom_waterfall.png"); plt.close(fig)
print("waterfall ok")
