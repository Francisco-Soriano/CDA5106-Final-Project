#!/usr/bin/env python3
"""Generate comparison charts: baseline vs optimized icache proxy energy."""

import json, os
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import numpy as np

BASELINE = os.path.join(os.path.dirname(__file__), "..", "results", "test-baseline", "icache_proxy_coremark.json")
OPTIMIZED = os.path.join(os.path.dirname(__file__), "icache_proxy_coremark.json")
OUT_DIR = os.path.join(os.path.dirname(__file__), "scratch")

def load(path):
    with open(path) as f:
        return json.load(f)

def pct_change(old, new):
    if old == 0:
        return 0
    return (new - old) / old * 100

def save(fig, name):
    os.makedirs(OUT_DIR, exist_ok=True)
    path = os.path.join(OUT_DIR, name)
    fig.savefig(path, dpi=180, bbox_inches="tight", facecolor="white")
    print(f"  Saved {path}")
    plt.close(fig)


# ── Style ────────────────────────────────────────────────────────────────
COLORS = {
    "baseline": "#5B8DEF",
    "optimized": "#2ECC71",
    "delta_neg": "#2ECC71",
    "delta_pos": "#E74C3C",
    "tag_reads": "#5B8DEF",
    "data_reads": "#3498DB",
    "tag_writes": "#E67E22",
    "data_writes": "#E74C3C",
    "evictions": "#9B59B6",
    "inval_tag_writes": "#1ABC9C",
}

plt.rcParams.update({
    "font.family": "sans-serif",
    "font.size": 11,
    "axes.titlesize": 14,
    "axes.titleweight": "bold",
    "axes.labelsize": 12,
    "figure.facecolor": "white",
})


def fig1_proxy_energy_bar(base, opt):
    """Side-by-side proxy energy for RR and PLRU."""
    fig, ax = plt.subplots(figsize=(8, 5))

    policies = ["RR", "PLRU"]
    baseline_vals = [base["rr"]["metrics"]["proxy_energy"],
                     base["plru"]["metrics"]["proxy_energy"]]
    opt_vals = [opt["rr"]["metrics"]["proxy_energy"],
                opt["plru"]["metrics"]["proxy_energy"]]

    x = np.arange(len(policies))
    w = 0.32

    bars_b = ax.bar(x - w/2, baseline_vals, w, label="Baseline", color=COLORS["baseline"],
                    edgecolor="white", linewidth=0.8, zorder=3)
    bars_o = ax.bar(x + w/2, opt_vals, w, label="Optimized (FB_THRESHOLD=1)", color=COLORS["optimized"],
                    edgecolor="white", linewidth=0.8, zorder=3)

    for b_bar, o_bar, bv, ov in zip(bars_b, bars_o, baseline_vals, opt_vals):
        pct = pct_change(bv, ov)
        mid_x = (b_bar.get_x() + b_bar.get_width() + o_bar.get_x()) / 2
        ax.annotate(f"{pct:+.1f}%", xy=(mid_x, max(bv, ov)),
                    xytext=(0, 18), textcoords="offset points",
                    ha="center", va="bottom", fontsize=13, fontweight="bold",
                    color=COLORS["delta_neg"],
                    arrowprops=dict(arrowstyle="-", color="#aaa", lw=0.8))

    for bar_group in [bars_b, bars_o]:
        for bar in bar_group:
            h = bar.get_height()
            ax.text(bar.get_x() + bar.get_width()/2, h + 20000,
                    f"{h/1e6:.2f}M", ha="center", va="bottom", fontsize=9, color="#555")

    ax.set_xticks(x)
    ax.set_xticklabels(policies, fontsize=13)
    ax.set_ylabel("Proxy Energy (weighted SRAM events)")
    ax.set_title("Proxy Energy: Baseline vs Optimized")
    ax.legend(loc="upper right", framealpha=0.9)
    ax.set_ylim(0, max(baseline_vals) * 1.22)
    ax.yaxis.set_major_formatter(ticker.FuncFormatter(lambda v, _: f"{v/1e6:.1f}M"))
    ax.grid(axis="y", alpha=0.3, zorder=0)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    save(fig, "fig1_proxy_energy.png")


def fig2_energy_breakdown(base, opt):
    """Stacked bar showing energy contribution by component."""
    fig, axes = plt.subplots(1, 2, figsize=(12, 5), sharey=True)

    weights = base["weights"]
    components = ["tag_reads", "data_reads", "tag_writes", "data_writes", "evictions", "inval_tag_writes"]
    nice_names = ["Tag Reads (×1)", "Data Reads (×2)", "Tag Writes (×2)",
                  "Data Writes (×3)", "Evictions (×1)", "Inval Tag Wr (×1)"]

    for ax, policy, title in zip(axes, ["rr", "plru"], ["RR", "PLRU"]):
        labels = ["Baseline", "Optimized"]
        bottoms_b = 0
        bottoms_o = 0

        for comp, nice in zip(components, nice_names):
            w = weights[comp]
            bv = base[policy]["counters"][comp] * w
            ov = opt[policy]["counters"][comp] * w

            ax.barh(1, bv, left=bottoms_b, color=COLORS[comp], edgecolor="white",
                    linewidth=0.5, height=0.5, label=nice if ax == axes[0] else None, zorder=3)
            ax.barh(0, ov, left=bottoms_o, color=COLORS[comp], edgecolor="white",
                    linewidth=0.5, height=0.5, zorder=3)

            bottoms_b += bv
            bottoms_o += ov

        be = base[policy]["metrics"]["proxy_energy"]
        oe = opt[policy]["metrics"]["proxy_energy"]
        ax.text(bottoms_b + 30000, 1, f"{be/1e6:.2f}M", va="center", fontsize=10, color="#333")
        ax.text(bottoms_o + 30000, 0, f"{oe/1e6:.2f}M", va="center", fontsize=10, color="#333")

        pct = pct_change(be, oe)
        ax.text(bottoms_o + 30000, 0.5, f"{pct:+.1f}%", va="center", fontsize=12,
                fontweight="bold", color=COLORS["delta_neg"])

        ax.set_yticks([0, 1])
        ax.set_yticklabels(["Optimized", "Baseline"], fontsize=11)
        ax.set_title(f"{title} Policy")
        ax.xaxis.set_major_formatter(ticker.FuncFormatter(lambda v, _: f"{v/1e6:.1f}M"))
        ax.grid(axis="x", alpha=0.3, zorder=0)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.set_xlabel("Weighted Energy Contribution")

    axes[0].legend(loc="upper right", fontsize=8, framealpha=0.9)
    fig.suptitle("Energy Breakdown by Component", fontsize=15, fontweight="bold", y=1.02)
    fig.tight_layout()
    save(fig, "fig2_energy_breakdown.png")


def fig3_counter_deltas(base, opt):
    """Horizontal bar chart of percentage change for each counter."""
    fig, axes = plt.subplots(1, 2, figsize=(13, 5), sharey=True)

    counters = ["cycles", "instret", "fetch_wait", "tag_reads", "data_reads",
                "tag_writes", "data_writes"]
    nice = ["Cycles", "Instr. Retired", "Fetch Wait", "Tag Reads",
            "Data Reads", "Tag Writes", "Data Writes"]

    for ax, policy, title in zip(axes, ["rr", "plru"], ["RR", "PLRU"]):
        pcts = []
        for c in counters:
            bv = base[policy]["counters"][c]
            ov = opt[policy]["counters"][c]
            pcts.append(pct_change(bv, ov))

        colors = [COLORS["delta_neg"] if p <= 0 else COLORS["delta_pos"] for p in pcts]
        y = np.arange(len(counters))
        bars = ax.barh(y, pcts, color=colors, edgecolor="white", linewidth=0.5, height=0.6, zorder=3)

        for bar, p in zip(bars, pcts):
            xpos = bar.get_width()
            offset = 0.4 if p >= 0 else -0.4
            ha = "left" if p >= 0 else "right"
            ax.text(xpos + offset, bar.get_y() + bar.get_height()/2,
                    f"{p:+.1f}%", va="center", ha=ha, fontsize=10, fontweight="bold", color="#333")

        ax.set_yticks(y)
        ax.set_yticklabels(nice, fontsize=11)
        ax.axvline(0, color="#555", linewidth=0.8, zorder=2)
        ax.set_title(f"{title} Policy")
        ax.set_xlabel("% Change from Baseline")
        ax.grid(axis="x", alpha=0.3, zorder=0)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)

    fig.suptitle("Counter Changes: Baseline → Optimized", fontsize=15, fontweight="bold", y=1.02)
    fig.tight_layout()
    save(fig, "fig3_counter_deltas.png")


def fig4_reads_scatter(base, opt):
    """Scatter: tag_reads vs proxy_energy for all four data points."""
    fig, ax = plt.subplots(figsize=(7, 5))

    points = [
        ("Baseline RR",   base["rr"]["counters"]["tag_reads"],   base["rr"]["metrics"]["proxy_energy"],   COLORS["baseline"], "o"),
        ("Baseline PLRU", base["plru"]["counters"]["tag_reads"],  base["plru"]["metrics"]["proxy_energy"],  COLORS["baseline"], "s"),
        ("Opt RR",        opt["rr"]["counters"]["tag_reads"],     opt["rr"]["metrics"]["proxy_energy"],     COLORS["optimized"], "o"),
        ("Opt PLRU",      opt["plru"]["counters"]["tag_reads"],   opt["plru"]["metrics"]["proxy_energy"],   COLORS["optimized"], "s"),
    ]

    for label, reads, energy, color, marker in points:
        ax.scatter(reads, energy, s=160, c=color, marker=marker, edgecolors="white",
                   linewidths=1.5, zorder=5, label=label)
        ax.annotate(label, (reads, energy), textcoords="offset points",
                    xytext=(10, 8), fontsize=9, color="#333")

    ax.arrow(base["plru"]["counters"]["tag_reads"], base["plru"]["metrics"]["proxy_energy"],
             opt["plru"]["counters"]["tag_reads"] - base["plru"]["counters"]["tag_reads"],
             opt["plru"]["metrics"]["proxy_energy"] - base["plru"]["metrics"]["proxy_energy"],
             head_width=12000, head_length=8000, fc="#aaa", ec="#aaa", zorder=2, alpha=0.5)

    ax.set_xlabel("Tag/Data Reads (per run)")
    ax.set_ylabel("Proxy Energy")
    ax.set_title("SRAM Reads vs Proxy Energy")
    ax.xaxis.set_major_formatter(ticker.FuncFormatter(lambda v, _: f"{v/1e6:.2f}M"))
    ax.yaxis.set_major_formatter(ticker.FuncFormatter(lambda v, _: f"{v/1e6:.2f}M"))
    ax.grid(alpha=0.3, zorder=0)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.legend(fontsize=9, framealpha=0.9)

    save(fig, "fig4_reads_vs_energy.png")


def fig5_summary_table(base, opt):
    """Summary table as a figure."""
    fig, ax = plt.subplots(figsize=(10, 4))
    ax.axis("off")

    headers = ["", "Baseline", "Optimized", "Change"]
    rows = []
    for policy in ["rr", "plru"]:
        pname = policy.upper()
        be = base[policy]["metrics"]["proxy_energy"]
        oe = opt[policy]["metrics"]["proxy_energy"]
        br = base[policy]["counters"]["tag_reads"]
        ore = opt[policy]["counters"]["tag_reads"]
        bc = base[policy]["counters"]["cycles"]
        oc = opt[policy]["counters"]["cycles"]

        rows.append([f"{pname} Proxy Energy", f"{be:,.0f}", f"{oe:,.0f}", f"{pct_change(be,oe):+.2f}%"])
        rows.append([f"{pname} SRAM Reads",   f"{br:,}",    f"{ore:,}",   f"{pct_change(br,ore):+.2f}%"])
        rows.append([f"{pname} Cycles",        f"{bc:,}",    f"{oc:,}",    f"{pct_change(bc,oc):+.2f}%"])
        if policy == "rr":
            rows.append(["", "", "", ""])

    table = ax.table(cellText=rows, colLabels=headers, loc="center", cellLoc="center")
    table.auto_set_font_size(False)
    table.set_fontsize(11)
    table.scale(1.0, 1.6)

    for (r, c), cell in table.get_celld().items():
        cell.set_edgecolor("#ddd")
        if r == 0:
            cell.set_facecolor("#34495E")
            cell.set_text_props(color="white", fontweight="bold")
        elif rows[r-1][0] == "":
            cell.set_facecolor("white")
            cell.set_edgecolor("white")
        elif c == 3:
            txt = rows[r-1][3]
            if txt.startswith("-"):
                cell.set_text_props(color=COLORS["delta_neg"], fontweight="bold")
            elif txt.startswith("+"):
                cell.set_text_props(color=COLORS["delta_pos"], fontweight="bold")

    ax.set_title("Optimization Summary: FB_THRESHOLD = NUM_FB−3",
                 fontsize=14, fontweight="bold", pad=20)
    save(fig, "fig5_summary_table.png")


def main():
    base = load(BASELINE)
    opt = load(OPTIMIZED)

    print("Generating comparison charts...\n")
    fig1_proxy_energy_bar(base, opt)
    fig2_energy_breakdown(base, opt)
    fig3_counter_deltas(base, opt)
    fig4_reads_scatter(base, opt)
    fig5_summary_table(base, opt)
    print(f"\nAll charts saved to {os.path.abspath(OUT_DIR)}/")

if __name__ == "__main__":
    main()
