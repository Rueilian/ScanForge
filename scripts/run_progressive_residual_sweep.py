#!/usr/bin/env python3
"""
Run progressive residual sweep across all Tier A benchmarks and ratios.
"""
import os
import subprocess
import sys

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
MASK_DIR = os.path.join(REPO_ROOT, "masks")
RUNNER_PY = os.path.join(REPO_ROOT, "scripts", "run_progressive_residual.py")

CIRCUITS = ["b03", "b04", "b05", "b07", "b08", "b09", "b11", "b13"]
RATIOS = [0.05, 0.10, 0.15, 0.20]

import argparse

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--two-phase", action="store_true", help="Enable two-phase state justification optimization")
    args = ap.parse_args()
    two_phase = args.two_phase

    print(f"Starting progressive residual sweep for Tier A benchmarks{' (with Two-Phase Justification)' if two_phase else ''}...")
    
    total = len(CIRCUITS) * len(RATIOS)
    count = 0
    
    for c in CIRCUITS:
        for r in RATIOS:
            count += 1
            ratio_pct = int(round(r * 100))
            mask_file = os.path.join(MASK_DIR, f"{c}_x{ratio_pct}.mask")
            
            if not os.path.exists(mask_file):
                print(f"[{count}/{total}] SKIP {c} at {ratio_pct}%: Mask file {mask_file} not found.")
                continue
                
            with open(mask_file) as f:
                ff_names = [ln.strip() for ln in f if ln.strip()]
            
            ff_str = " ".join(ff_names)
            
            print(f"[{count}/{total}] Running {c} at {ratio_pct}% exclusion ({len(ff_names)} FFs)...")
            
            cmd = [
                sys.executable,
                RUNNER_PY,
                "--circuit", c,
                "--ratio", str(r),
                "--nonscan", ff_str
            ]
            if two_phase:
                cmd.append("--two-phase")
            
            try:
                subprocess.run(cmd, check=True)
            except subprocess.CalledProcessError as e:
                print(f"Error running progressive residual for {c} x={ratio_pct}%: {e}")
                
    print("Sweep completed successfully!")

if __name__ == "__main__":
    main()
