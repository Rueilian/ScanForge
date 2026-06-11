#!/usr/bin/env python3
"""Scatter coverage_proxy vs max_segment_stress from scanforge --summary-csv sweep output."""
import argparse
import csv
import sys


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("csv", help="Summary CSV from scanforge --sweep --summary-csv")
    p.add_argument("-o", "--output", default="leveling_pareto.png", help="Output PNG path")
    args = p.parse_args()

    try:
        import matplotlib.pyplot as plt
    except ImportError:
        print("matplotlib is required: pip install matplotlib", file=sys.stderr)
        return 1

    xs, ys, labels = [], [], []
    with open(args.csv, newline="") as f:
        r = csv.DictReader(f)
        for row in r:
            try:
                xs.append(float(row["coverage_proxy"]))
                ys.append(float(row["max_segment_stress"]))
            except (KeyError, ValueError):
                continue
            mode = row.get("mode", "")
            lam = row.get("lambda", "")
            rat = row.get("ratio", "")
            labels.append(f"{mode} r={rat} λ={lam}")

    if not xs:
        print("No rows with coverage_proxy and max_segment_stress", file=sys.stderr)
        return 1

    plt.figure(figsize=(8, 5))
    plt.scatter(xs, ys, alpha=0.7, s=36)
    plt.xlabel("coverage_proxy")
    plt.ylabel("max_segment_stress")
    plt.title("Coverage proxy vs max segment stress (sweep summary CSV)")
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(args.output, dpi=150)
    print("Wrote", args.output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
