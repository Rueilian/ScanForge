#!/usr/bin/env python3
"""Plot coverage–stress tradeoff from scanforge --sweep --summary-csv output."""

import argparse
import csv
import os
import sys

try:
    import matplotlib.pyplot as plt
except ImportError:
    print("matplotlib is required: pip install matplotlib", file=sys.stderr)
    sys.exit(1)


def load_rows(path):
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def to_float(row, key, default=0.0):
    try:
        return float(row.get(key, default))
    except (TypeError, ValueError):
        return default


def plot_pair(rows, xkey, ykey, title, outpath, label_key="ratio"):
    xs = [to_float(r, xkey) for r in rows]
    ys = [to_float(r, ykey) for r in rows]
    labels = [str(r.get(label_key, "")) for r in rows]
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.scatter(xs, ys, s=36, alpha=0.85)
    for x, y, lab in zip(xs, ys, labels):
        ax.annotate(lab, (x, y), textcoords="offset points", xytext=(4, 4), fontsize=8)
    ax.set_xlabel(xkey.replace("_", " "))
    ax.set_ylabel(ykey.replace("_", " "))
    ax.set_title(title)
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(outpath, dpi=150)
    plt.close(fig)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("csv", help="Summary CSV from scanforge --sweep --summary-csv")
    p.add_argument("-o", "--prefix", default="tradeoff", help="Output file prefix (PNG)")
    args = p.parse_args()

    rows = load_rows(args.csv)
    if not rows:
        print("Empty CSV", file=sys.stderr)
        sys.exit(1)

    mode = rows[0].get("mode", "mode")
    circuit = rows[0].get("circuit", "circuit")
    base = args.prefix
    plot_pair(
        rows,
        "coverage_proxy",
        "max_stress",
        f"{circuit} / {mode}: coverage proxy vs max stress",
        base + "_cov_vs_maxstress.png",
    )
    plot_pair(
        rows,
        "coverage_proxy",
        "activity",
        f"{circuit} / {mode}: coverage proxy vs activity",
        base + "_cov_vs_activity.png",
    )
    if "max_segment_stress" in rows[0]:
        plot_pair(
            rows,
            "coverage_proxy",
            "max_segment_stress",
            f"{circuit} / {mode}: coverage proxy vs max segment stress",
            base + "_cov_vs_maxsegment.png",
        )
        plot_pair(
            rows,
            "ratio",
            "hotspot_count",
            f"{circuit} / {mode}: partial ratio vs hotspot segment count",
            base + "_ratio_vs_hotspots.png",
            label_key="k",
        )
        print(
            "Also wrote",
            base + "_cov_vs_maxsegment.png",
            "and",
            base + "_ratio_vs_hotspots.png",
        )
    print("Wrote", base + "_cov_vs_maxstress.png", "and", base + "_cov_vs_activity.png")


if __name__ == "__main__":
    main()
