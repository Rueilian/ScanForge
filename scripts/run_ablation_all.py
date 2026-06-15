#!/usr/bin/env python3
"""
Ablation: A vs B vs C on 15 circuits (excl. s38417, s38584), all ptt=0.
  (A) Baseline: FAST=800, Two-Phase ON at T>1
  (B) No fast limit: FAST=5000 (same as T>1), Two-Phase ON at T>1
  (C) No Two-Phase at T=2: FAST=800, Two-Phase OFF at T=2 only

Output: results/ablation_{no_fast_limit,no_tp_T2}.csv
"""
import os, subprocess, sys, shutil, glob

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
RUNNER = os.path.join(REPO, "scripts", "run_progressive_residual.py")
MASK_DIR = os.path.join(REPO, "masks")
SUMMARY = os.path.join(REPO, "results", "progressive_residual_summary.csv")

CIRCUITS = ["b03","b04","b05","b07","b08","b09","b11","b13",
            "s953","s1196","s1238","s5378","s9234","s15850","s35932"]

def load_mask(circuit):
    with open(os.path.join(MASK_DIR, f"{circuit}_x10.mask")) as f:
        return " ".join(ln.strip() for ln in f if ln.strip())

def fresh_start():
    if os.path.exists(SUMMARY):
        os.makedirs(os.path.join(REPO, "results", "archive"), exist_ok=True)
        dst = os.path.join(REPO, "results", "archive", "progressive_residual_summary_before_ablation.csv")
        if not os.path.exists(dst):
            shutil.move(SUMMARY, dst)
            print(f"Archived existing summary -> {dst}")
    for d in ["results/residual_faults", "results/fault_status"]:
        dp = os.path.join(REPO, d)
        if os.path.isdir(dp):
            for f in glob.glob(os.path.join(dp, "*")):
                os.remove(f)

def run_one_condition(label, env_vars=None, extra_args=None):
    fresh_start()
    env = os.environ.copy()
    env["ATPG_PER_TARGET_TIMEOUT"] = "0"
    if env_vars:
        env.update(env_vars)
    for i, c in enumerate(CIRCUITS, 1):
        ns = load_mask(c)
        print(f"\n[{i}/{len(CIRCUITS)}] {c} -- {label}")
        sys.stdout.flush()
        cmd = [sys.executable, RUNNER, "--circuit", c, "--ratio", "0.10", "--nonscan", ns]
        if extra_args:
            cmd.extend(extra_args)
        try:
            r = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=7200)
            if r.returncode == 0:
                print("  OK")
            else:
                print(f"  FAILED exit={r.returncode}")
            for line in r.stdout.strip().split("\n")[-3:]:
                print(f"  {line}")
        except subprocess.TimeoutExpired:
            print(f"  TIMEOUT")
    out = os.path.join(REPO, "results", f"ablation_{label}.csv")
    if os.path.exists(SUMMARY):
        shutil.copy(SUMMARY, out)
        print(f"\n-> {out}")
    else:
        print(f"\n  WARNING: {SUMMARY} not found after run")

if __name__ == "__main__":
    print("=" * 60)
    print("Ablation: 15 circuits (excl s38417, s38584), ptt=0")
    print("=" * 60)

    print("\n>>> Condition B: no fast limit (FAST=5000) <<<")
    run_one_condition("no_fast_limit", env_vars={"ATPG_FAST_BACKTRACK_LIMIT": "5000"})

    print("\n>>> Condition C: no Two-Phase at T=2 <<<")
    run_one_condition("no_tp_T2", extra_args=["--t2-two-phase", "off"])

    archived = os.path.join(REPO, "results", "archive", "progressive_residual_summary_before_ablation.csv")
    if os.path.exists(archived):
        shutil.move(archived, SUMMARY)
        print(f"\nRestored original summary")
