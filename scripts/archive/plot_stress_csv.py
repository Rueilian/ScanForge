#!/usr/bin/env python3
"""Plot stress_score vs FF index from scanforge --stress-csv output."""
import argparse
import csv
import sys


def main():
    p = argparse.ArgumentParser(description="Plot per-FF stress_score from stress CSV")
    p.add_argument("csv", help="CSV from scanforge --stress-csv")
    p.add_argument("-o", "--output", default="stress_profile.png", help="Output PNG path")
    args = p.parse_args()

    try:
        import matplotlib.pyplot as plt
    except ImportError:
        print("matplotlib is required: pip install matplotlib", file=sys.stderr)
        return 1

    xs, ys, names = [], [], []
    with open(args.csv, newline="") as f:
        r = csv.DictReader(f)
        for row in r:
            xs.append(int(row["index"]))
            ys.append(float(row["stress_score"]))
            names.append(row["ff_name"])

    plt.figure(figsize=(10, 4))
    plt.bar(xs, ys, color="steelblue", width=0.8)
    plt.xlabel("FF index (scan chain order)")
    plt.ylabel("stress_score")
    plt.title("Per-FF scan shift stress (prototype heat map)")
    plt.tight_layout()
    plt.savefig(args.output, dpi=150)
    print("Wrote", args.output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
