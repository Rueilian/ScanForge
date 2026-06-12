#!/usr/bin/env python3
"""Generate report figures from progressive_residual_summary.csv.

Primary chart: T=1 / T1∪T2 / T1∪T2∪T4 at the canonical 20% partial-scan setting.
"""
import csv
import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
FIG_DIR = os.path.join(REPO, "docs", "figures")
os.makedirs(FIG_DIR, exist_ok=True)

CSV = os.path.join(REPO, "results", "progressive_residual_summary.csv")
CANONICAL_RATIO = "0.2"
CIRCUITS = ["b03", "b04", "b05", "b07", "b08", "b09", "b11", "b13"]


def load_first_rows():
    first = {}
    with open(CSV, newline="") as f:
        for row in csv.DictReader(f):
            key = (row["circuit"], row["ratio"])
            if key not in first:
                first[key] = row
    return first


def rows_at_ratio(first, ratio):
    out = []
    for c in CIRCUITS:
        key = (c, ratio)
        if key in first:
            out.append(first[key])
    return out


def plot_t_stage_bars(rows, out_name, title):
    labels = [r["circuit"] for r in rows]
    t1 = [float(r["FC_T1"]) for r in rows]
    t12 = [float(r["FC_T1_T2"]) for r in rows]
    t124 = [float(r["FC_T1_T2_T4"]) for r in rows]
    gain = [float(r["total_gain_pp"]) for r in rows]

    fig, ax = plt.subplots(figsize=(9, 4.5))
    x = np.arange(len(labels))
    w = 0.25
    ax.bar(x - w, t1, w, label="T=1", color="#4472C4")
    ax.bar(x, t12, w, label="T1∪T2", color="#ED7D31")
    ax.bar(x + w, t124, w, label="T1∪T2∪T4", color="#70AD47")
    ax.set_ylabel("Fault coverage (%)")
    ax.set_title(title)
    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.legend(loc="lower right")
    ax.set_ylim(80, 100)
    for i, (g, v) in enumerate(zip(gain, t124)):
        if g > 0:
            ax.annotate(f"+{g:.2f}pp", (x[i] + w, v + 0.15), ha="center", fontsize=8)
    fig.tight_layout()
    fig.savefig(os.path.join(FIG_DIR, out_name), dpi=150)
    plt.close(fig)


def plot_new_dt(rows, out_name):
    labels = [r["circuit"] for r in rows]
    t2new = [int(r["T2_new_DT"]) for r in rows]
    t4new = [int(r["T4_new_DT"]) for r in rows]

    fig, ax = plt.subplots(figsize=(9, 4))
    x = np.arange(len(labels))
    w = 0.35
    ax.bar(x - w / 2, t2new, w, label="New DT at T=2", color="#ED7D31")
    ax.bar(x + w / 2, t4new, w, label="New DT at T=4", color="#70AD47")
    ax.set_ylabel("Newly detected faults")
    ax.set_title("Residual recovery at T=2 and T=4 (20% non-scan)")
    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.legend()
    fig.tight_layout()
    fig.savefig(os.path.join(FIG_DIR, out_name), dpi=150)
    plt.close(fig)


def main():
    first = load_first_rows()
    rows20 = rows_at_ratio(first, CANONICAL_RATIO)
    if not rows20:
        raise SystemExit("No 20% rows found in progressive_residual_summary.csv")

    plot_t_stage_bars(
        rows20,
        "coverage_bar_chart.png",
        "Progressive residual pipeline: T-stage union coverage (20% non-scan)",
    )
    plot_new_dt(rows20, "recovered_faults_chart.png")

    # Retire stale two-phase comparison figure; keep filename for backward links.
    fig, ax = plt.subplots(figsize=(6, 3))
    ax.axis("off")
    ax.text(
        0.5,
        0.5,
        "Two-phase vs standard TFE comparison removed.\n"
        "Report focus: T=1→T2→T4 pipeline gain (see Section 7).",
        ha="center",
        va="center",
        fontsize=11,
    )
    fig.tight_layout()
    fig.savefig(os.path.join(FIG_DIR, "two_phase_comparison.png"), dpi=150)
    plt.close(fig)

    print(f"Wrote figures to {FIG_DIR}/")


if __name__ == "__main__":
    main()
