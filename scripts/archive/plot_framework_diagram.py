#!/usr/bin/env python3
"""Generate F1 — ScanForge overall framework diagram.

Usage:
    python scripts/plot_framework_diagram.py -o figures/
"""
import argparse
import os

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches
    from matplotlib.patches import FancyArrowPatch, FancyBboxPatch
except ImportError:
    print("matplotlib required: pip install matplotlib")
    raise


def box(ax, x, y, w, h, text, color, fontsize=10, text_color="white", style="round,pad=0.05"):
    fancy = FancyBboxPatch((x - w/2, y - h/2), w, h,
                           boxstyle=style,
                           facecolor=color, edgecolor="white", linewidth=1.5,
                           zorder=3)
    ax.add_patch(fancy)
    ax.text(x, y, text, ha="center", va="center",
            fontsize=fontsize, color=text_color, fontweight="bold",
            zorder=4, wrap=True,
            multialignment="center")


def arrow(ax, x0, y0, x1, y1, label="", color="#555555"):
    ax.annotate("", xy=(x1, y1), xytext=(x0, y0),
                arrowprops=dict(arrowstyle="-|>", color=color, lw=1.5),
                zorder=2)
    if label:
        mx, my = (x0 + x1) / 2, (y0 + y1) / 2
        ax.text(mx + 0.02, my + 0.02, label, fontsize=7.5, color="#444444",
                ha="left", va="bottom", zorder=5)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("-o", "--outdir", default="figures")
    args = ap.parse_args()
    os.makedirs(args.outdir, exist_ok=True)

    fig, ax = plt.subplots(figsize=(11, 5))
    ax.set_xlim(0, 11)
    ax.set_ylim(0, 5)
    ax.axis("off")

    C_BLUE   = "#1f77b4"
    C_GREEN  = "#2ca02c"
    C_ORANGE = "#ff7f0e"
    C_PURPLE = "#9467bd"
    C_GRAY   = "#7f7f7f"
    C_RED    = "#d62728"

    # ── Row 1: input pipeline ────────────────────────────────────────────────
    box(ax, 1.1, 3.8, 1.7, 0.9, "ISCAS'89\nBenchmark\n(.bench)", C_GRAY, fontsize=9)
    arrow(ax, 1.95, 3.8, 2.65, 3.8, ".bench")
    box(ax, 3.2, 3.8, 1.0, 0.9, "FAN ATPG\n(NTU)", C_GRAY, fontsize=9)
    arrow(ax, 3.7, 3.8, 4.4, 3.8, ".sf")
    box(ax, 5.0, 3.8, 1.1, 0.9, "ScanForge\nParser", C_BLUE, fontsize=9)

    # ── Row 1 → Row 2: SCOAP + Stress ───────────────────────────────────────
    arrow(ax, 5.0, 3.35, 5.0, 2.65, "SCOAP (CC0,CC1,CO)\nper-FF chain order")

    # ── Row 2: selection core ────────────────────────────────────────────────
    box(ax, 5.0, 2.25, 1.8, 0.8, "Selection Algorithm\n(7 modes)", C_GREEN, fontsize=9)

    # Modes annotations below selection box
    modes_txt = "random | co | combined\nco_wear | combined_wear\nco_wear_leveling | combined_wear_leveling"
    ax.text(5.0, 1.67, modes_txt, ha="center", va="top", fontsize=7,
            color=C_GREEN, style="italic")

    # lambda input
    box(ax, 2.5, 2.25, 1.3, 0.8, "Hyperparams\nλ, W", C_ORANGE, fontsize=9)
    arrow(ax, 3.15, 2.25, 4.1, 2.25, "λ, segment\nwindow W")

    # ── Row 2 → Row 3: simulation ────────────────────────────────────────────
    arrow(ax, 5.0, 1.85, 5.0, 1.15, "K selected FFs\nchain order")

    # ── Row 3: simulation ────────────────────────────────────────────────────
    box(ax, 5.0, 0.75, 1.8, 0.8, "Scan Shift\nSimulation\n(ATPG patterns)", C_PURPLE, fontsize=9)

    # Outputs (right column)
    box(ax, 8.5, 3.0, 2.1, 0.75, "Coverage Proxy\n(SCOAP-derived)", C_BLUE, fontsize=9)
    box(ax, 8.5, 2.0, 2.1, 0.75, "Max/Avg Per-FF Stress\n(toggle rate)", C_RED, fontsize=9)
    box(ax, 8.5, 1.0, 2.1, 0.75, "Segment Stress\n(hotspot detection)", C_RED, fontsize=9)

    # ── Row 3 → Outputs ──────────────────────────────────────────────────────
    arrow(ax, 5.9, 0.75, 7.44, 3.0, "")
    arrow(ax, 5.9, 0.75, 7.44, 2.0, "")
    arrow(ax, 5.9, 0.75, 7.44, 1.0, "")

    # ── Stress feedback loop ──────────────────────────────────────────────────
    ax.annotate("", xy=(5.0, 2.85), xytext=(8.5, 2.35),
                arrowprops=dict(arrowstyle="-|>", color=C_RED, lw=1.2,
                                connectionstyle="arc3,rad=-0.3"),
                zorder=2)
    ax.text(7.0, 3.3, "stress prior\n(full-scan)", fontsize=7, color=C_RED,
            ha="center", va="bottom")

    ax.set_title("ScanForge: Stress-Aware Partial Scan Selection Framework",
                 fontsize=13, fontweight="bold", pad=10)

    fname = os.path.join(args.outdir, "F1_framework.png")
    fig.tight_layout()
    fig.savefig(fname, dpi=200, bbox_inches="tight")
    plt.close(fig)
    print(f"  → {fname}")


if __name__ == "__main__":
    main()
