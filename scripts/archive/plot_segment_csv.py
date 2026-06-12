#!/usr/bin/env python3
"""Plot segment_avg_stress vs segment start index from scanforge --segment-csv output."""
import argparse
import csv
import sys


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("csv", help="CSV from scanforge --segment-csv")
    p.add_argument("-o", "--output", default="segment_profile.png", help="Output PNG path")
    args = p.parse_args()

    try:
        import matplotlib.pyplot as plt
    except ImportError:
        print("matplotlib is required: pip install matplotlib", file=sys.stderr)
        return 1

    xs, ys, hot = [], [], []
    with open(args.csv, newline="") as f:
        r = csv.DictReader(f)
        for row in r:
            xs.append(int(row["start_idx"]))
            ys.append(float(row["avg_stress"]))
            hot.append(int(row.get("hotspot", 0)))

    colors = ["coral" if h else "steelblue" for h in hot]
    plt.figure(figsize=(10, 4))
    plt.bar(xs, ys, color=colors, width=0.9)
    plt.xlabel("Segment start index (chain order)")
    plt.ylabel("avg_stress")
    plt.title("Segment-level scan stress (hotspots in coral)")
    plt.tight_layout()
    plt.savefig(args.output, dpi=150)
    print("Wrote", args.output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
