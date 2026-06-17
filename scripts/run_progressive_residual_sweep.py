#!/usr/bin/env python3
"""
Run progressive residual sweep for Tier A @ the fixed 10% non-scan ratio.

Each run: T=1 baseline (FC_T1) → residual T=2 → residual T=4 (workflow union).
8 circuits × 1 ratio = 8 runs → results/progressive_residual_summary.csv

Use --fresh to archive the previous summary and start clean.
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
SUMMARY_CSV = os.path.join(REPO_ROOT, "results", "progressive_residual_summary.csv")
ARCHIVE_DIR = os.path.join(REPO_ROOT, "results", "archive")

CIRCUITS = ["b03", "b04", "b05", "b07", "b08", "b09", "b11", "b13"]
NONSCAN_RATIO = 0.10
RATIO_PCT = 10


def archive_existing_summary():
    if not os.path.exists(SUMMARY_CSV):
        return None
    os.makedirs(ARCHIVE_DIR, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest = os.path.join(ARCHIVE_DIR, f"progressive_residual_summary_{stamp}.csv")
    shutil.move(SUMMARY_CSV, dest)
    print(f"Archived previous summary → {dest}")
    return dest


def clear_residual_artifacts():
    for pattern in (
        os.path.join(REPO_ROOT, "results", "residual_faults", "*"),
        os.path.join(REPO_ROOT, "results", "fault_status", "*"),
    ):
        for path in glob.glob(pattern):
            if os.path.isfile(path):
                os.remove(path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--fresh",
        action="store_true",
        help="Archive existing summary CSV and start a clean 8-run sweep",
    )
    ap.add_argument(
        "--circuits",
        nargs="+",
        default=CIRCUITS,
        choices=CIRCUITS,
        help="Subset of Tier A circuits (default: all 8)",
    )
    ap.add_argument(
        "--two-phase",
        action="store_true",
        help="(deprecated, no-op) state justification is always enabled in FAN_ATPG",
    )
    args = ap.parse_args()
    if args.two_phase:
        print("Note: --two-phase is deprecated; FAN_ATPG enables state justification by default.")

    os.environ.setdefault("ATPG_WALL_TIMEOUT", "7200")

    if args.fresh:
        archive_existing_summary()
        clear_residual_artifacts()

    circuits = args.circuits
    total = len(circuits)
    failed = []

    print("Progressive residual sweep — Tier A @ 10% non-scan only")
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
            subprocess.run(cmd, check=True)
        except subprocess.CalledProcessError as e:
            print(f"  FAILED: {e}")
            failed.append((c, str(e)))

    if failed:
        print(f"\nSweep finished with {len(failed)} failure(s): {failed}")
        sys.exit(1)

    print("\nSweep completed successfully!")


if __name__ == "__main__":
    main()
