#!/usr/bin/env python3
"""
Run progressive residual T=1→T=2→T=4 pipeline on ISCAS'89 benchmarks.

4 circuits × 1 ratio (10%) = 4 runs → results/iscas89_progressive_residual_summary.csv

Purpose: verify whether the 0-gain result from ITC'99 is dataset-specific
or a fundamental limitation of timing-driven partial-scan partial observability.
"""
import argparse
import glob
import os
import shutil
import subprocess
import sys
from datetime import datetime

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
MASK_DIR = os.path.join(REPO_ROOT, "masks")
RUNNER_PY = os.path.join(REPO_ROOT, "scripts", "run_progressive_residual.py")
SUMMARY_CSV = os.path.join(REPO_ROOT, "results", "iscas89_progressive_residual_summary.csv")
ARCHIVE_DIR = os.path.join(REPO_ROOT, "results", "archive")

# s27/s510 have <10 FFs; floor(n*0.1)=0 non-scan → full-scan baseline only, not in this sweep
CIRCUITS = ["s953", "s1196", "s1238", "s5378", "s9234", "s15850", "s35932", "s38417", "s38584"]
NONSCAN_RATIO = 0.10
RATIO_PCT = 10


def archive_existing_summary():
    if not os.path.exists(SUMMARY_CSV):
        return None
    os.makedirs(ARCHIVE_DIR, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest = os.path.join(ARCHIVE_DIR, f"iscas89_progressive_residual_summary_{stamp}.csv")
    shutil.move(SUMMARY_CSV, dest)
    print(f"Archived previous summary → {dest}")
    return dest


def clear_residual_artifacts():
    for pattern in (
        os.path.join(REPO_ROOT, "results", "residual_faults", "s*"),
        os.path.join(REPO_ROOT, "results", "fault_status", "s*"),
    ):
        for path in glob.glob(pattern):
            if os.path.isfile(path):
                os.remove(path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fresh", action="store_true",
                    help="Archive existing summary and start a clean sweep")
    ap.add_argument("--circuits", nargs="+", default=CIRCUITS, choices=CIRCUITS,
                    help="Subset of ISCAS'89 circuits (default: all 4)")
    args = ap.parse_args()

    os.environ.setdefault("ATPG_WALL_TIMEOUT", "3600")

    if args.fresh:
        archive_existing_summary()
        clear_residual_artifacts()

    circuits = args.circuits
    total = len(circuits)
    failed = []

    print("Progressive residual sweep — ISCAS'89 @ 10% non-scan")
    print(f"Circuits: {' '.join(circuits)}")
    print(f"Output: {SUMMARY_CSV}")
    print(f"ATPG_WALL_TIMEOUT={os.environ.get('ATPG_WALL_TIMEOUT')}s\n")

    for i, c in enumerate(circuits, 1):
        mask_file = os.path.join(MASK_DIR, f"{c}_x{RATIO_PCT}.mask")
        if not os.path.exists(mask_file):
            print(f"[{i}/{total}] SKIP {c}: mask not found ({mask_file})")
            failed.append((c, "missing mask"))
            continue

        with open(mask_file) as f:
            ff_names = [ln.strip() for ln in f if ln.strip()]

        print(f"[{i}/{total}] {c} @ {RATIO_PCT}% ({len(ff_names)} non-scan FFs)")
        cmd = [
            sys.executable,
            RUNNER_PY,
            "--circuit", c,
            "--ratio", str(NONSCAN_RATIO),
            "--nonscan", " ".join(ff_names),
        ]
        try:
            # Override summary CSV so ISCAS'89 results go to a separate file
            env = os.environ.copy()
            env["ISCAS89_SUMMARY_CSV"] = SUMMARY_CSV
            subprocess.run(cmd, check=True, env=env)
        except subprocess.CalledProcessError as e:
            print(f"  FAILED: {e}")
            failed.append((c, str(e)))

    if failed:
        print(f"\nSweep finished with {len(failed)} failure(s): {failed}")
        sys.exit(1)

    print("\nSweep completed successfully!")
    if os.path.exists(SUMMARY_CSV):
        print(f"Results: {SUMMARY_CSV}")


if __name__ == "__main__":
    main()
