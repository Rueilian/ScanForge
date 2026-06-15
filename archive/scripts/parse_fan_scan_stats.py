#!/usr/bin/env python3
"""Parse FAN report_statistics output for scan-protocol (primary) metrics."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


def parse_report(text: str) -> dict[str, str]:
    patterns = {
        "fc_scan": r"fault coverage \(scan protocol\)\s+([\d.]+)%",
        "fc_scan_coll": r"fault coverage \(scan, collapsed\)\s+([\d.]+)%",
        "test_cov_scan": r"test coverage \(scan protocol\)\s+([\d.]+)%",
        "fc_raw": r"fault coverage \(raw, appendix\)\s+([\d.]+)%",
        "test_cov_raw": r"test coverage \(raw, appendix\)\s+([\d.]+)%",
        "fu_collapsed": r"FU \(collapsed\)\s+(\d+)",
        "fu_full": r"FU \(full\)\s+(\d+)",
        "dt": r"DT \(detected\)\s+(\d+)",
        "au": r"AU \(atpg untestable\)\s+(\d+)",
        "ti_scan": r"TI \(scan async control\)\s+(\d+)",
        "ti": r"TI \(tied\)\s+(\d+)",
        "ud": r"UD \(undetected\)\s+(\d+)",
        "patterns": r"#Patterns\s+(\d+)",
        "runtime_s": r"ATPG runtime\s+([\d.eE+-]+)\s+s",
    }
    out: dict[str, str] = {}
    for key, pat in patterns.items():
        m = re.search(pat, text)
        if m:
            out[key] = m.group(1)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("report", nargs="?", help="FAN statistics report path")
    ap.add_argument("--csv", action="store_true", help="print one CSV row (header if --header)")
    ap.add_argument("--header", action="store_true", help="with --csv, print header row")
    args = ap.parse_args()

    if not args.report:
        ap.print_help()
        return 1

    text = Path(args.report).read_text()
    stats = parse_report(text)

    if args.csv:
        cols = [
            "fc_scan",
            "fc_scan_coll",
            "test_cov_scan",
            "fc_raw",
            "test_cov_raw",
            "fu_collapsed",
            "fu_full",
            "dt",
            "au",
            "ti_scan",
            "ti",
            "ud",
            "patterns",
            "runtime_s",
        ]
        if args.header:
            print(",".join(cols))
        print(",".join(stats.get(c, "") for c in cols))
        return 0

    for key in (
        "fc_scan",
        "test_cov_scan",
        "fc_raw",
        "test_cov_raw",
        "fu_collapsed",
        "dt",
        "au",
        "ti_scan",
    ):
        if key in stats:
            print(f"{key}={stats[key]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
