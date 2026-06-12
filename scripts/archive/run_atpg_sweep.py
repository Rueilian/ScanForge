#!/usr/bin/env python3
"""
run_atpg_sweep.py — Timing-driven partial-scan ATPG experiment runner.

For each (circuit, nonscan_ratio) combination:
  1. Read non-scan mask from masks/<circuit>_x<pct>.mask
  2. Write a FAN_ATPG script to FAN_ATPG/script/fanScripts/<circuit>_x<pct>.script
  3. Run FAN binary from FAN_ATPG/ with: ./bin/opt/fan -f <script>
  4. Parse FAN_ATPG/rpt/<circuit>_x<pct>.rpt
  5. Append one row to results/itc99_partial_scan.csv

Usage:
    python3 scripts/run_atpg_sweep.py [options]

Options:
    --circuits b03 b04 ...    circuits to include (default: Tier A active set, 8 ITC)
    --ratios 0.0 0.05 ...     nonscan ratios (default: 0.0 0.05 0.10 0.15 0.20)
    --out PATH                output CSV (default: results/itc99_partial_scan.csv)
    --dry-run                 generate scripts but do not run FAN
    --no-skip                 re-run even if row already exists in CSV
"""

import argparse
import csv
import math
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from atpg_timeouts import PER_TARGET_TIMEOUT_S, WALL_TIMEOUT_S, resolved_atpg_threads
from itc99_scope import ITC_ATPG

# ── Paths ──────────────────────────────────────────────────────────────────────

REPO_ROOT  = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
FAN_DIR    = os.path.join(REPO_ROOT, "FAN_ATPG")
FAN_BIN    = os.path.join(FAN_DIR, "bin", "opt", "fan")
MASK_DIR   = os.path.join(REPO_ROOT, "masks")
RPT_DIR    = os.path.join(FAN_DIR, "rpt")
SCRIPT_DIR = os.path.join(FAN_DIR, "script", "fanScripts")
OUT_CSV    = os.path.join(REPO_ROOT, "results", "archive", "itc99_partial_scan.csv")

DEFAULT_CIRCUITS = ITC_ATPG
DEFAULT_RATIOS = [0.0, 0.05, 0.10, 0.15, 0.20]

CSV_FIELDS = [
    "circuit", "nonscan_ratio",
    "fault_coverage", "test_coverage",
    "DT", "AU", "AB", "UD", "patterns", "runtime_s",
]

# ── Mask reading ───────────────────────────────────────────────────────────────

def read_mask(circuit, ratio_pct):
    """Return list of FF names. ratio_pct=0 → empty list (full scan)."""
    if ratio_pct == 0:
        return []
    mask_path = os.path.join(MASK_DIR, f"{circuit}_x{ratio_pct}.mask")
    if not os.path.exists(mask_path):
        raise FileNotFoundError(f"Mask not found: {mask_path}")
    with open(mask_path) as f:
        return [ln.strip() for ln in f if ln.strip()]

# ── Script generation ─────────────────────────────────────────────────────────

def make_script(circuit, ratio_pct, ff_names, script_path, rpt_rel):
    """Write a FAN_ATPG .script. Paths inside are relative to FAN_DIR."""
    frame = 1 if ratio_pct == 0 else 8
    lines = [
        "read_lib techlib/mod_nangate45.mdt",
        f"read_netlist mod_netlist/{circuit}.v",
    ]
    if ff_names:
        lines.append(f"set_nonscan_ff {' '.join(ff_names)}")
    lines += [
        f"build_circuit --frame {frame}",
        "set_fault_type saf",
        "add_fault --all",
    ]
    if PER_TARGET_TIMEOUT_S > 0:
        lines.append(f"set_per_target_timeout {PER_TARGET_TIMEOUT_S}")
    lines.append(f"set_atpg_threads {resolved_atpg_threads()}")
    lines += [
        "set_static_compression on",
        "set_dynamic_compression on",
        "run_atpg",
        f"report_statistics > {rpt_rel}",
        "exit",
    ]
    with open(script_path, "w") as f:
        f.write("\n".join(lines) + "\n")

# ── Report parsing ─────────────────────────────────────────────────────────────

INT_PATTERNS = {
    "DT":       r"DT \(detected\)\s+([\d]+)",
    "AU":       r"AU \(atpg untestable\)\s+([\d]+)",
    "AB":       r"AB \(atpg abort\)\s+([\d]+)",
    "UD":       r"UD \(undetected\)\s+([\d]+)",
    "patterns": r"#Patterns\s+([\d]+)",
}
FLOAT_PATTERNS = {
    "fault_coverage": r"fault coverage\s+([\d.]+)%",
    "test_coverage":  r"test coverage\s+([\d.]+)%",
    "runtime_s":      r"ATPG runtime\s+([\d.eE+\-]+)\s+s",
}

def parse_rpt(rpt_path):
    if not os.path.exists(rpt_path):
        return None
    with open(rpt_path) as f:
        text = f.read()
    result = {}
    for key, pat in INT_PATTERNS.items():
        m = re.search(pat, text)
        result[key] = int(m.group(1)) if m else None
    for key, pat in FLOAT_PATTERNS.items():
        m = re.search(pat, text)
        result[key] = float(m.group(1)) if m else None
    missing = [k for k, v in result.items() if v is None]
    if missing:
        print(f"  WARN: unparsed fields {missing} in {rpt_path}", file=sys.stderr)
    return result

# ── CSV helpers ───────────────────────────────────────────────────────────────

def init_csv(path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if not os.path.exists(path):
        with open(path, "w", newline="") as f:
            csv.DictWriter(f, fieldnames=CSV_FIELDS).writeheader()

def append_row(path, row):
    with open(path, "a", newline="") as f:
        csv.DictWriter(f, fieldnames=CSV_FIELDS).writerow(row)

def already_done(path, circuit, ratio):
    if not os.path.exists(path):
        return False
    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            if row["circuit"] == circuit and abs(float(row["nonscan_ratio"]) - ratio) < 1e-6:
                return True
    return False

# ── Single run ────────────────────────────────────────────────────────────────

def run_one(circuit, ratio, dry_run=False):
    ratio_pct = int(round(ratio * 100))
    label     = f"{circuit}_x{ratio_pct}"

    try:
        ff_names = read_mask(circuit, ratio_pct)
    except FileNotFoundError as e:
        print(f"  SKIP: {e}", file=sys.stderr)
        return None

    script_path = os.path.join(SCRIPT_DIR, f"{label}.script")
    rpt_path    = os.path.join(RPT_DIR,    f"{label}.rpt")
    rpt_rel     = os.path.relpath(rpt_path, FAN_DIR)
    script_rel  = os.path.relpath(script_path, FAN_DIR)

    os.makedirs(SCRIPT_DIR, exist_ok=True)
    os.makedirs(RPT_DIR,    exist_ok=True)

    make_script(circuit, ratio_pct, ff_names, script_path, rpt_rel)

    if dry_run:
        print(f"  [DRY RUN] {FAN_BIN} -f {script_rel}")
        return None

    if os.path.exists(rpt_path):
        os.remove(rpt_path)

    try:
        proc = subprocess.run(
            [FAN_BIN, "-f", script_rel],
            cwd=FAN_DIR,
            capture_output=True,
            text=True,
            timeout=WALL_TIMEOUT_S,
        )
    except subprocess.TimeoutExpired:
        print(f"  TIMEOUT ({label})", file=sys.stderr)
        return None
    except Exception as e:
        print(f"  ERROR ({label}): {e}", file=sys.stderr)
        return None

    parsed = parse_rpt(rpt_path)
    if parsed is None:
        print(f"  FAILED: no report produced for {label}", file=sys.stderr)
        print(f"  FAN stderr: {proc.stderr[-200:]}", file=sys.stderr)
        return None

    print(f"  FC={parsed['fault_coverage']}%  "
          f"DT={parsed['DT']}  AU={parsed['AU']}  AB={parsed['AB']}  "
          f"patterns={parsed['patterns']}  t={parsed['runtime_s']}s")
    return parsed

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--circuits", nargs="+", default=DEFAULT_CIRCUITS, metavar="C")
    ap.add_argument("--ratios",   nargs="+", type=float, default=DEFAULT_RATIOS, metavar="R")
    ap.add_argument("--out",      default=OUT_CSV)
    ap.add_argument("--dry-run",  action="store_true")
    ap.add_argument("--no-skip",  action="store_true",
                    help="Re-run even if row already in CSV")
    args = ap.parse_args()

    if not args.dry_run and not os.path.isfile(FAN_BIN):
        sys.exit(f"ERROR: FAN binary not found: {FAN_BIN}")

    init_csv(args.out)

    total = len(args.circuits) * len(args.ratios)
    done  = 0

    for circuit in args.circuits:
        for ratio in sorted(args.ratios):
            done += 1
            ratio_pct = int(round(ratio * 100))
            print(f"\n[{done}/{total}] {circuit} x={ratio_pct}%", flush=True)

            if not args.no_skip and already_done(args.out, circuit, ratio):
                print("  SKIP (already in CSV)")
                continue

            parsed = run_one(circuit, ratio, dry_run=args.dry_run)
            if parsed is None:
                continue

            row = {"circuit": circuit, "nonscan_ratio": ratio}
            row.update(parsed)
            append_row(args.out, row)

    print(f"\nDone. Results → {args.out}")


if __name__ == "__main__":
    main()
