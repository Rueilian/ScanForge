#!/usr/bin/env python3
"""Patch phase_d_fullscan_dataset.csv rows from existing FAN rpt files."""
from __future__ import annotations

import csv
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FAN = ROOT / "FAN_ATPG"
CSV = ROOT / "results/phase_d_fullscan_dataset.csv"
PARSER = ROOT / "scripts/parse_fan_scan_stats.py"


def row_from_rpt(circuit: str, group: str, rpt: Path, wall: str = "") -> list[str] | None:
    if not rpt.exists() or rpt.stat().st_size == 0:
        return None
    proc = subprocess.run(
        [sys.executable, str(PARSER), str(rpt), "--csv"],
        capture_output=True,
        text=True,
        check=True,
    )
    parts = proc.stdout.strip().split(",")
    if len(parts) < 12:
        return None
    fc_scan, fc_scan_coll, tc_scan, fc_raw, tc_raw, fu_c, fu_full, dt, au, ti_scan, ti, ud, pat, rt = parts[:14]
    return [circuit, group, fc_scan, fc_scan_coll, tc_scan, fu_c, dt, au, ti_scan, ud, pat, rt, wall or rt]


def main() -> int:
    patches = {
        "b05": ("itc99", FAN / "rpt/b05_scan_proto_fs.rpt"),
    }
    if not CSV.exists():
        print("CSV missing", file=CSV)
        return 1
    rows = list(csv.DictReader(CSV.open()))
    by_circuit = {r["circuit"]: r for r in rows}
    for c, (grp, rpt) in patches.items():
        new = row_from_rpt(c, grp, rpt)
        if new:
            by_circuit[c] = dict(
                zip(
                    [
                        "circuit",
                        "group",
                        "fc_scan",
                        "fc_scan_coll",
                        "test_cov_scan",
                        "fu_collapsed",
                        "dt",
                        "au",
                        "ti_scan",
                        "ud",
                        "patterns",
                        "runtime_s",
                        "wall_s",
                    ],
                    new,
                )
            )
            print(f"patched {c} fc_scan={new[2]}%")
    fieldnames = rows[0].keys() if rows else []
    with CSV.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            c = r["circuit"]
            w.writerow(by_circuit.get(c, r))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
