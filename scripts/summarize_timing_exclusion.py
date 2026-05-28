#!/usr/bin/env python3

import csv
import sys
from collections import defaultdict
from pathlib import Path


EXPECTED_RATIOS = ["0.05", "0.1", "0.15", "0.2"]


def read_rows(path: Path):
    with path.open(newline="") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        raise ValueError("master CSV is empty")
    return rows


def summarize(rows):
    grouped = defaultdict(dict)
    for row in rows:
        grouped[row["circuit"]][row["ratio"]] = row

    summary = []
    for circuit in sorted(grouped):
        ratios = grouped[circuit]
        missing = [r for r in EXPECTED_RATIOS if r not in ratios]
        if missing:
            raise ValueError(f"{circuit} missing ratio rows: {', '.join(missing)}")

        r05 = ratios["0.05"]
        r20 = ratios["0.2"]

        cov05 = float(r05["coverage_proxy_combined"])
        cov20 = float(r20["coverage_proxy_combined"])
        act05 = float(r05["switching_activity"])
        act20 = float(r20["switching_activity"])

        summary.append(
            {
                "circuit": circuit,
                "ff_count_scan_5": r05["scan_ff"],
                "ff_count_scan_20": r20["scan_ff"],
                "coverage_combined_5": f"{cov05:.6f}",
                "coverage_combined_20": f"{cov20:.6f}",
                "coverage_drop_abs": f"{(cov05 - cov20):.6f}",
                "coverage_drop_pct_of_5": f"{((cov05 - cov20) / cov05 * 100.0) if cov05 else 0.0:.4f}",
                "activity_5": f"{act05:.6f}",
                "activity_20": f"{act20:.6f}",
                "activity_delta": f"{(act20 - act05):.6f}",
            }
        )
    return summary


def write_rows(path: Path, rows):
    fieldnames = [
        "circuit",
        "ff_count_scan_5",
        "ff_count_scan_20",
        "coverage_combined_5",
        "coverage_combined_20",
        "coverage_drop_abs",
        "coverage_drop_pct_of_5",
        "activity_5",
        "activity_20",
        "activity_delta",
    ]
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main(argv):
    if len(argv) != 3:
        print(
            "Usage: summarize_timing_exclusion.py <master_csv> <summary_csv>",
            file=sys.stderr,
        )
        return 1

    master_csv = Path(argv[1])
    summary_csv = Path(argv[2])
    rows = read_rows(master_csv)
    summary = summarize(rows)
    write_rows(summary_csv, summary)
    print(f"Wrote {len(summary)} circuit summaries to {summary_csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
