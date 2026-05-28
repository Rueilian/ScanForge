#!/usr/bin/env python3
"""
run_stage1_fan_cases.py — emit full_scan and partial_scan_no_recovery rows
using real FAN_ATPG reports and the evaluation-case CSV schema.

Stage 1 scope:
  - full_scan: no non-scan FFs, frame=1
  - partial_scan_no_recovery: non-scan FFs selected from timing ranking, frame=1
"""

import argparse
import csv
import math
import os
import re
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
FAN_DIR = REPO_ROOT / "FAN_ATPG"
FAN_BIN = FAN_DIR / "bin" / "opt" / "fan"
SCRIPT_DIR = FAN_DIR / "script" / "fanScripts"
RPT_DIR = FAN_DIR / "rpt"
NETLIST_DIR = FAN_DIR / "mod_netlist"
TECHLIB = "techlib/mod_nangate45.mdt"

CSV_FIELDS = [
    "circuit",
    "case",
    "ratio",
    "depth",
    "coverage",
    "pattern_count",
    "runtime_sec",
    "test_coverage",
    "DT",
    "AU",
    "AB",
    "UD",
    "non_scan_ff",
]

INT_PATTERNS = {
    "DT": r"DT \(detected\)\s+([\d]+)",
    "AU": r"AU \(atpg untestable\)\s+([\d]+)",
    "AB": r"AB \(atpg abort\)\s+([\d]+)",
    "UD": r"UD \(undetected\)\s+([\d]+)",
    "pattern_count": r"#Patterns\s+([\d]+)",
    "non_scan_ff": None,
}

FLOAT_PATTERNS = {
    "coverage": r"fault coverage\s+([\d.]+)%",
    "test_coverage": r"test coverage\s+([\d.]+)%",
    "runtime_sec": r"ATPG runtime\s+([\d.eE+\-]+)\s+s",
}


def load_timing_rows(path: Path):
    rows = []
    with path.open(newline="") as f:
        for row in csv.DictReader(f):
            rows.append(
                {
                    "ff_name": row["ff_name"].strip(),
                    "timing_score": float(row["timing_score"]),
                }
            )
    if not rows:
        raise ValueError(f"timing ranking CSV is empty: {path}")
    rows.sort(key=lambda row: (-row["timing_score"], row["ff_name"]))
    return rows


def select_non_scan_ff_names(rows, ratio):
    k = int(round(ratio * len(rows)))
    if k <= 0:
        k = 1
    k = min(k, len(rows))
    chosen = [row["ff_name"] for row in rows[:k]]
    chosen.sort()
    return chosen


def make_script(case_name, circuit, frame, non_scan_names, script_path, rpt_rel):
    lines = [
        f"read_lib {TECHLIB}",
        f"read_netlist mod_netlist/{circuit}.v",
    ]
    if non_scan_names:
        lines.append(f"set_nonscan_ff {' '.join(non_scan_names)}")
    lines += [
        f"build_circuit --frame {frame}",
        "set_fault_type saf",
        "add_fault --all",
        "set_static_compression on",
        "set_dynamic_compression on",
        "run_atpg",
        f"report_statistics > {rpt_rel}",
        "exit",
    ]
    script_path.write_text("\n".join(lines) + "\n")


def parse_report(path: Path, non_scan_ff_count: int):
    if not path.exists():
        raise FileNotFoundError(f"report not found: {path}")
    text = path.read_text()
    out = {"non_scan_ff": non_scan_ff_count}
    for key, pat in INT_PATTERNS.items():
        if pat is None:
            continue
        match = re.search(pat, text)
        if not match:
            raise ValueError(f"could not parse {key} from {path}")
        out[key] = int(match.group(1))
    for key, pat in FLOAT_PATTERNS.items():
        match = re.search(pat, text)
        if not match:
            raise ValueError(f"could not parse {key} from {path}")
        out[key] = float(match.group(1))
    return out


def run_fan(script_path: Path):
    proc = subprocess.run(
        [str(FAN_BIN), "-f", os.path.relpath(script_path, FAN_DIR)],
        cwd=FAN_DIR,
        capture_output=True,
        text=True,
        timeout=600,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"FAN_ATPG failed for {script_path.name}\nSTDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"
        )


def emit_row(out_csv: Path, row):
    if not out_csv.exists():
        out_csv.parent.mkdir(parents=True, exist_ok=True)
        with out_csv.open("w", newline="") as f:
            csv.DictWriter(f, fieldnames=CSV_FIELDS).writeheader()
    with out_csv.open("a", newline="") as f:
        csv.DictWriter(f, fieldnames=CSV_FIELDS).writerow(row)


def build_case_row(circuit, case_name, ratio, depth, parsed):
    return {
        "circuit": circuit,
        "case": case_name,
        "ratio": f"{ratio:.2f}",
        "depth": depth,
        "coverage": f"{parsed['coverage']:.2f}",
        "pattern_count": parsed["pattern_count"],
        "runtime_sec": f"{parsed['runtime_sec']:.6f}",
        "test_coverage": f"{parsed['test_coverage']:.2f}",
        "DT": parsed["DT"],
        "AU": parsed["AU"],
        "AB": parsed["AB"],
        "UD": parsed["UD"],
        "non_scan_ff": parsed["non_scan_ff"],
    }


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--circuit", required=True)
    ap.add_argument("--ratio", type=float, required=True)
    ap.add_argument("--timing-csv", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args(argv[1:])

    if not FAN_BIN.exists():
        raise SystemExit(f"FAN binary not found: {FAN_BIN}")
    netlist_path = NETLIST_DIR / f"{args.circuit}.v"
    if not netlist_path.exists():
        raise SystemExit(f"netlist not found: {netlist_path}")

    timing_rows = load_timing_rows(Path(args.timing_csv))
    non_scan_names = select_non_scan_ff_names(timing_rows, args.ratio)

    cases = [
        ("full_scan", 0.0, 1, []),
        ("partial_scan_no_recovery", args.ratio, 0, non_scan_names),
    ]

    for case_name, ratio, depth, non_scan_ff_names in cases:
        label = f"{args.circuit}_{case_name}_x{int(round(args.ratio * 100))}"
        script_path = SCRIPT_DIR / f"{label}.script"
        rpt_path = RPT_DIR / f"{label}.rpt"
        rpt_rel = os.path.relpath(rpt_path, FAN_DIR)
        if rpt_path.exists():
            rpt_path.unlink()
        make_script(case_name, args.circuit, 1, non_scan_ff_names, script_path, rpt_rel)
        run_fan(script_path)
        parsed = parse_report(rpt_path, len(non_scan_ff_names))
        row = build_case_row(args.circuit, case_name, ratio, depth, parsed)
        emit_row(Path(args.out), row)
        print(
            f"{case_name}: coverage={row['coverage']} pattern_count={row['pattern_count']} runtime_sec={row['runtime_sec']}"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
