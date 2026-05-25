#!/usr/bin/env python3
"""Generate publication-quality figures for the ScanForge paper.

Usage:
    python scripts/plot_paper_figures.py results/all_experiments.csv -o figures/

Produces:
    F3_pareto_<circuit>.png      — coverage vs max_stress Pareto by mode
    F4_lambda_sensitivity.png   — lambda effect on s953
    F6_scalability.png          — selection runtime vs FF count
    F7_casestudy_<circuit>.png  — coverage-stress sweep for co vs co_wear_leveling
"""

import argparse
import csv
import os
import sys
from collections import defaultdict

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.ticker as mticker
    import numpy as np
except ImportError:
    print("matplotlib and numpy required: pip install matplotlib numpy", file=sys.stderr)
    sys.exit(1)

# ── Aesthetics ────────────────────────────────────────────────────────────────
MODES = ["random", "co", "combined", "co_wear", "combined_wear",
         "co_wear_leveling", "combined_wear_leveling"]

MODE_LABELS = {
    "random":                   "Random",
    "co":                       "SCOAP-CO",
    "combined":                 "SCOAP-Combined",
    "co_wear":                  "CO+Wear (global)",
    "combined_wear":            "Combined+Wear (global)",
    "co_wear_leveling":         "CO+Wear-Leveling (ours)",
    "combined_wear_leveling":   "Combined+Wear-Leveling (ours)",
}

MODE_COLORS = {
    "random":                   "#aaaaaa",
    "co":                       "#1f77b4",
    "combined":                 "#ff7f0e",
    "co_wear":                  "#d62728",
    "combined_wear":            "#e377c2",
    "co_wear_leveling":         "#2ca02c",
    "combined_wear_leveling":   "#17becf",
}

MODE_LS = {
    "random":                   ":",
    "co":                       "--",
    "combined":                 "-.",
    "co_wear":                  "--",
    "combined_wear":            "-.",
    "co_wear_leveling":         "-",
    "combined_wear_leveling":   "-",
}

MODE_MARKERS = {
    "random":                   "x",
    "co":                       "o",
    "combined":                 "s",
    "co_wear":                  "^",
    "combined_wear":            "v",
    "co_wear_leveling":         "D",
    "combined_wear_leveling":   "P",
}

FF_COUNTS = {
    "s27": 3, "s208": 8, "s510": 6, "s953": 29,
    "s1196": 18, "s1238": 18, "s5378": 179, "s9234": 211,
    "s15850": 534, "s35932": 1728, "s38417": 1636, "s38584": 1426,
}

# ── Data loading ──────────────────────────────────────────────────────────────

def flt(row, key, default=0.0):
    try:
        return float(row.get(key, default))
    except (TypeError, ValueError):
        return default


def load_csv(path):
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def index_rows(rows):
    """Returns dict: (circuit, mode, lambda, ratio) → row."""
    idx = {}
    for r in rows:
        key = (r["circuit"], r["mode"],
               round(flt(r, "lambda"), 4),
               round(flt(r, "ratio"), 4))
        idx[key] = r
    return idx


def rows_for(rows, circuit=None, mode=None, lam=None):
    out = rows
    if circuit:
        out = [r for r in out if r["circuit"] == circuit]
    if mode:
        out = [r for r in out if r["mode"] == mode]
    if lam is not None:
        out = [r for r in out if abs(flt(r, "lambda") - lam) < 1e-6]
    return out

# ── Figure helpers ────────────────────────────────────────────────────────────

def save(fig, path):
    fig.tight_layout()
    fig.savefig(path, dpi=200, bbox_inches="tight")
    plt.close(fig)
    print(f"  → {path}")

# ── F3: Coverage-Stress Pareto by mode ───────────────────────────────────────

def fig_pareto(rows, circuit, lam, outdir):
    """Coverage proxy vs max_stress across scan ratios, one line per mode."""
    fig, ax = plt.subplots(figsize=(6, 4.5))

    for mode in MODES:
        mrs = rows_for(rows, circuit=circuit, mode=mode, lam=lam)
        if not mrs:
            mrs = rows_for(rows, circuit=circuit, mode=mode)  # fallback any λ
        if not mrs:
            continue
        mrs = sorted(mrs, key=lambda r: flt(r, "ratio"))
        xs = [flt(r, "max_stress") for r in mrs]
        ys = [flt(r, "coverage_proxy") for r in mrs]
        ax.plot(xs, ys,
                label=MODE_LABELS.get(mode, mode),
                color=MODE_COLORS.get(mode, None),
                linestyle=MODE_LS.get(mode, "-"),
                marker=MODE_MARKERS.get(mode, "o"),
                markersize=4, linewidth=1.4, alpha=0.9)

    ax.set_xlabel("Max per-FF stress (toggle rate)", fontsize=11)
    ax.set_ylabel("Coverage proxy (SCOAP)", fontsize=11)
    n_ff = FF_COUNTS.get(circuit, "?")
    ax.set_title(f"{circuit} ({n_ff} FFs) — λ={lam}", fontsize=12)
    ax.legend(fontsize=7, loc="lower right", framealpha=0.8)
    ax.grid(True, alpha=0.25)
    ax.set_xlim(left=0)
    ax.set_ylim(bottom=0, top=1.05)

    fname = os.path.join(outdir, f"F3_pareto_{circuit}_l{lam}.png")
    save(fig, fname)

# ── F4: Lambda sensitivity ────────────────────────────────────────────────────

def fig_lambda_sensitivity(rows, circuit, ratio, outdir):
    """Coverage proxy and max_stress vs lambda for co_wear_leveling."""
    lambdas = sorted({round(flt(r, "lambda"), 4)
                      for r in rows_for(rows, circuit=circuit, mode="co_wear_leveling")})
    if not lambdas:
        print(f"  skip F4: no co_wear_leveling data for {circuit}")
        return

    cov, stress = [], []
    for lam in lambdas:
        rs = rows_for(rows, circuit=circuit, mode="co_wear_leveling", lam=lam)
        rs = [r for r in rs if abs(flt(r, "ratio") - ratio) < 0.02]
        if rs:
            cov.append(flt(rs[0], "coverage_proxy"))
            stress.append(flt(rs[0], "max_stress"))
        else:
            cov.append(None)
            stress.append(None)

    fig, ax1 = plt.subplots(figsize=(5, 3.5))
    ax2 = ax1.twinx()

    ax1.plot(lambdas, cov, "o-", color="#1f77b4", linewidth=1.8, label="Coverage proxy")
    ax2.plot(lambdas, stress, "s--", color="#d62728", linewidth=1.8, label="Max stress")

    ax1.set_xlabel("λ (stress penalty weight)", fontsize=11)
    ax1.set_ylabel("Coverage proxy", fontsize=11, color="#1f77b4")
    ax2.set_ylabel("Max per-FF stress", fontsize=11, color="#d62728")
    n_ff = FF_COUNTS.get(circuit, "?")
    ax1.set_title(f"λ sensitivity — {circuit} ({n_ff} FFs), ratio={ratio:.0%}", fontsize=11)
    ax1.set_ylim(0, 1.1)
    ax2.set_ylim(0, 1.0)
    ax1.tick_params(axis="y", colors="#1f77b4")
    ax2.tick_params(axis="y", colors="#d62728")

    lines1, labs1 = ax1.get_legend_handles_labels()
    lines2, labs2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labs1 + labs2, fontsize=9, loc="lower left")
    ax1.grid(True, alpha=0.25)

    fname = os.path.join(outdir, f"F4_lambda_{circuit}_r{int(ratio*100)}.png")
    save(fig, fname)

# ── F6: Scalability ───────────────────────────────────────────────────────────

def fig_scalability(rows, ratio, outdir):
    """Selection time vs FF count for different modes at given ratio."""
    circuits = sorted(FF_COUNTS.keys(), key=lambda c: FF_COUNTS[c])
    highlight_modes = ["co", "co_wear", "co_wear_leveling"]

    fig, ax = plt.subplots(figsize=(6, 4))

    for mode in highlight_modes:
        xs, ys = [], []
        for c in circuits:
            rs = rows_for(rows, circuit=c, mode=mode)
            rs = [r for r in rs if abs(flt(r, "ratio") - ratio) < 0.02]
            if rs:
                sel_t = flt(rs[0], "selection_time_ms")
                if sel_t > 0:
                    xs.append(FF_COUNTS[c])
                    ys.append(sel_t)
        if xs:
            ax.plot(xs, ys,
                    label=MODE_LABELS.get(mode, mode),
                    color=MODE_COLORS.get(mode, None),
                    marker=MODE_MARKERS.get(mode, "o"),
                    linestyle=MODE_LS.get(mode, "-"),
                    linewidth=1.6, markersize=5)

    ax.set_xlabel("Number of flip-flops", fontsize=11)
    ax.set_ylabel("Selection time (ms)", fontsize=11)
    ax.set_title(f"Selection runtime vs FF count (ratio={ratio:.0%})", fontsize=12)
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.xaxis.set_major_formatter(mticker.ScalarFormatter())
    ax.yaxis.set_major_formatter(mticker.ScalarFormatter())
    ax.legend(fontsize=9)
    ax.grid(True, which="both", alpha=0.2)

    fname = os.path.join(outdir, f"F6_scalability_r{int(ratio*100)}.png")
    save(fig, fname)

# ── F7: Case study — co vs co_wear_leveling ──────────────────────────────────

def fig_casestudy(rows, circuit, lam, outdir):
    """Coverage proxy and max_stress vs ratio for co, co_wear, co_wear_leveling."""
    compare_modes = ["co", "co_wear", "co_wear_leveling"]
    fig, axes = plt.subplots(1, 2, figsize=(10, 4))

    for mode in compare_modes:
        mrs = rows_for(rows, circuit=circuit, mode=mode, lam=lam)
        if not mrs:
            mrs = rows_for(rows, circuit=circuit, mode=mode)
        if not mrs:
            continue
        mrs = sorted(mrs, key=lambda r: flt(r, "ratio"))
        ratios = [flt(r, "ratio") * 100 for r in mrs]
        covs   = [flt(r, "coverage_proxy") for r in mrs]
        maxs   = [flt(r, "max_stress") for r in mrs]

        axes[0].plot(ratios, covs,
                     label=MODE_LABELS.get(mode, mode),
                     color=MODE_COLORS.get(mode, None),
                     linestyle=MODE_LS.get(mode, "-"),
                     marker=MODE_MARKERS.get(mode, "o"),
                     markersize=4, linewidth=1.4)
        axes[1].plot(ratios, maxs,
                     label=MODE_LABELS.get(mode, mode),
                     color=MODE_COLORS.get(mode, None),
                     linestyle=MODE_LS.get(mode, "-"),
                     marker=MODE_MARKERS.get(mode, "o"),
                     markersize=4, linewidth=1.4)

    for ax, ylabel, title in [
        (axes[0], "Coverage proxy (SCOAP)", "Coverage vs scan ratio"),
        (axes[1], "Max per-FF stress",       "Stress vs scan ratio"),
    ]:
        ax.set_xlabel("Scan ratio (%)", fontsize=10)
        ax.set_ylabel(ylabel, fontsize=10)
        ax.set_title(title, fontsize=11)
        ax.legend(fontsize=7)
        ax.grid(True, alpha=0.25)
        ax.set_xlim(0, 105)
        ax.set_ylim(bottom=0)

    n_ff = FF_COUNTS.get(circuit, "?")
    fig.suptitle(f"Case study: {circuit} ({n_ff} FFs) — λ={lam}", fontsize=12)

    fname = os.path.join(outdir, f"F7_casestudy_{circuit}_l{lam}.png")
    save(fig, fname)

# ── F5: Window sensitivity ───────────────────────────────────────────────────

def fig_window_sensitivity(rows, circuit, lam, outdir):
    """Coverage proxy and max_segment_stress vs ratio for W=8 vs W=16 (co_wear_leveling)."""
    windows = [8, 16]
    win_colors = {8: "#e377c2", 16: "#2ca02c"}
    win_ls = {8: "--", 16: "-"}

    fig, axes = plt.subplots(1, 2, figsize=(10, 4))

    for w in windows:
        mrs = [r for r in rows
               if r["circuit"] == circuit
               and r["mode"] == "co_wear_leveling"
               and abs(flt(r, "lambda") - lam) < 1e-6
               and int(r.get("segment_window", 0)) == w]
        if not mrs:
            print(f"  skip F5 W={w}: no data for {circuit}")
            continue
        mrs = sorted(mrs, key=lambda r: flt(r, "ratio"))
        ratios = [flt(r, "ratio") * 100 for r in mrs]
        covs   = [flt(r, "coverage_proxy") for r in mrs]
        segs   = [flt(r, "max_segment_stress") for r in mrs]

        label = f"W={w}"
        axes[0].plot(ratios, covs, label=label,
                     color=win_colors[w], linestyle=win_ls[w],
                     marker="o", markersize=4, linewidth=1.4)
        axes[1].plot(ratios, segs, label=label,
                     color=win_colors[w], linestyle=win_ls[w],
                     marker="o", markersize=4, linewidth=1.4)

    for ax, ylabel, title in [
        (axes[0], "Coverage proxy (SCOAP)", "Coverage vs scan ratio"),
        (axes[1], "Max segment stress",     "Segment stress vs scan ratio"),
    ]:
        ax.set_xlabel("Scan ratio (%)", fontsize=10)
        ax.set_ylabel(ylabel, fontsize=10)
        ax.set_title(title, fontsize=11)
        ax.legend(fontsize=9)
        ax.grid(True, alpha=0.25)
        ax.set_xlim(0, 105)
        ax.set_ylim(bottom=0)

    n_ff = FF_COUNTS.get(circuit, "?")
    fig.suptitle(f"Window sensitivity: {circuit} ({n_ff} FFs) — co_wear_leveling, λ={lam}", fontsize=11)
    fname = os.path.join(outdir, f"F5_window_{circuit}_l{lam}.png")
    save(fig, fname)


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("csv", help="results/all_experiments.csv")
    ap.add_argument("-o", "--outdir", default="figures", help="Output directory")
    args = ap.parse_args()

    os.makedirs(args.outdir, exist_ok=True)

    print(f"Loading {args.csv}...")
    rows = load_csv(args.csv)
    print(f"  {len(rows)} rows loaded.")

    # F3: Pareto plots for representative circuits
    print("\n[F3] Coverage-Stress Pareto plots")
    for circuit in ["s953", "s1238", "s5378", "s9234", "s15850"]:
        fig_pareto(rows, circuit, lam=0.5, outdir=args.outdir)

    # F4: Lambda sensitivity
    print("\n[F4] Lambda sensitivity")
    fig_lambda_sensitivity(rows, circuit="s953", ratio=0.5, outdir=args.outdir)
    fig_lambda_sensitivity(rows, circuit="s5378", ratio=0.5, outdir=args.outdir)

    # F6: Scalability
    print("\n[F6] Scalability")
    fig_scalability(rows, ratio=0.5, outdir=args.outdir)
    fig_scalability(rows, ratio=0.25, outdir=args.outdir)

    # F5: Window sensitivity
    print("\n[F5] Window sensitivity")
    for circuit in ["s953", "s1238", "s5378"]:
        fig_window_sensitivity(rows, circuit, lam=0.5, outdir=args.outdir)

    # F7: Case studies
    print("\n[F7] Case studies")
    fig_casestudy(rows, circuit="s953",  lam=0.5, outdir=args.outdir)
    fig_casestudy(rows, circuit="s5378", lam=0.5, outdir=args.outdir)
    fig_casestudy(rows, circuit="s9234", lam=0.5, outdir=args.outdir)

    print(f"\nAll figures written to {args.outdir}/")


if __name__ == "__main__":
    main()
