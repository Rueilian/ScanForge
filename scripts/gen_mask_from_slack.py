#!/usr/bin/env python3
"""
gen_mask_from_slack.py — Generate non-scan mask files from per-FF slack CSV.

Usage:
    python3 gen_mask_from_slack.py <slack_csv> <mask_dir> <circuit> <ratio1> [ratio2 ...]

    slack_csv  : CSV with columns ff_instance,min_slack (from OpenSTA)
    mask_dir   : directory to write mask files
    circuit    : circuit name (e.g. b03)
    ratio*     : nonscan fractions e.g. 0.05 0.10 0.15 0.20

Output (one FF name per line, most timing-critical first):
    <mask_dir>/<circuit>_x5.mask
    <mask_dir>/<circuit>_x10.mask
    <mask_dir>/<circuit>_x15.mask
    <mask_dir>/<circuit>_x20.mask
"""

import csv
import math
import os
import sys


def load_slack(slack_csv):
    rows = []
    with open(slack_csv, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            inst = row["ff_instance"].strip()
            slack = float(row["min_slack"])
            rows.append((inst, slack))
    # Ascending sort: most negative (tightest) slack = most timing-critical
    rows.sort(key=lambda r: r[1])
    return rows


def main():
    if len(sys.argv) < 5:
        print(__doc__)
        sys.exit(1)

    slack_csv = sys.argv[1]
    mask_dir  = sys.argv[2]
    circuit   = sys.argv[3]
    ratios    = [float(r) for r in sys.argv[4:]]

    rows = load_slack(slack_csv)
    n_total = len(rows)
    print(f"  {circuit}: {n_total} FFs in slack CSV")

    os.makedirs(mask_dir, exist_ok=True)

    for ratio in ratios:
        k = max(1, math.ceil(n_total * ratio))
        nonscan_ffs = [inst for inst, _ in rows[:k]]
        pct = int(round(ratio * 100))
        out_path = os.path.join(mask_dir, f"{circuit}_x{pct}.mask")
        with open(out_path, "w") as f:
            f.write("\n".join(nonscan_ffs) + "\n")
        print(f"  x={pct}%: {k}/{n_total} non-scan FFs → {out_path}")


if __name__ == "__main__":
    main()
