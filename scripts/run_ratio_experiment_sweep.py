#!/usr/bin/env python3
"""
Multi-ratio experiment sweep: Exp 1–5 at each non-scan exclusion ratio.

Default grid: 5%, 10%, 15%, 20% (5% steps) × 5 experiments × 10 circuits.

Outputs per ratio under results/ratio_sweep/x{pct}/exp{N}_{name}.csv

Usage:
  ATPG_WALL_TIMEOUT=3600 python3 scripts/run_ratio_experiment_sweep.py
  python3 scripts/run_ratio_experiment_sweep.py --ratio 0.15
  python3 scripts/run_ratio_experiment_sweep.py --exp 2 --circuit s5378
"""
import argparse
import csv
import os
import subprocess
import sys
import time

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
FAN_DIR = os.path.join(REPO_ROOT, "FAN_ATPG")
RUNNER = os.path.join(REPO_ROOT, "scripts", "run_progressive_residual.py")
MASK_DIR = os.path.join(REPO_ROOT, "masks")
RES_ROOT = os.path.join(REPO_ROOT, "results", "ratio_sweep")
LOG = os.path.join(REPO_ROOT, "results", "ratio_sweep_log.txt")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from run_experiment_sweep import CIRCUITS_10, EXPERIMENTS
from run_progressive_residual import SUMMARY_FIELDS

RATIOS = [0.05, 0.10, 0.15, 0.20]


def log_msg(msg):
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG, "a") as f:
        f.write(f"[{ts}] {msg}\n")
    print(f"[{ts}] {msg}", flush=True)


def ratio_pct(ratio):
    return int(round(ratio * 100))


def load_mask(circuit, ratio):
    pct = ratio_pct(ratio)
    path = os.path.join(MASK_DIR, f"{circuit}_x{pct}.mask")
    if not os.path.exists(path):
        return None
    with open(path) as f:
        return " ".join(line.strip() for line in f if line.strip())


def exp_csv_path(exp, ratio):
    pct = ratio_pct(ratio)
    out_dir = os.path.join(RES_ROOT, f"x{pct}")
    os.makedirs(out_dir, exist_ok=True)
    return os.path.join(out_dir, f"{exp['name']}.csv")


def run_circuit(exp, circuit, ratio, timeout_s):
    mask = load_mask(circuit, ratio)
    pct = ratio_pct(ratio)
    if mask is None:
        log_msg(f"  {circuit} @ x{pct}%: SKIP (no mask)")
        return
    log_msg(f"  {circuit} @ x{pct}%: {exp['name']}")
    env = os.environ.copy()
    env.update(exp["env"])
    env["ATPG_SUMMARY_CSV"] = exp_csv_path(exp, ratio)
    cmd = [
        sys.executable, RUNNER,
        "--circuit", circuit,
        "--ratio", str(ratio),
        "--nonscan", mask,
        "--t1-two-phase", exp["t1tp"],
        "--t2-two-phase", exp["t2tp"],
        "--t4-two-phase", exp["t4tp"],
        "--timeout", str(timeout_s),
        "--per-target-timeout", "0",
    ]
    if exp["extra"]:
        cmd += ["--extra-flags", exp["extra"]]
    t0 = time.time()
    try:
        proc = subprocess.run(
            cmd, cwd=FAN_DIR, env=env, capture_output=True, text=True, timeout=timeout_s,
        )
        elapsed = time.time() - t0
        log_msg(f"    done ({elapsed:.1f}s) rc={proc.returncode}")
        for line in proc.stdout.strip().split("\n"):
            if "Memory peak:" in line or "peak=" in line:
                log_msg(f"    {line.strip()}")
        if proc.returncode != 0:
            log_msg(f"    stderr: {proc.stderr[:500]}")
    except subprocess.TimeoutExpired:
        elapsed = time.time() - t0
        log_msg(f"    TIMEOUT after {elapsed:.1f}s")
    except Exception as e:
        log_msg(f"    ERROR: {e}")
    subprocess.run(["killall", "-9", "fan"], capture_output=True)


def main():
    ap = argparse.ArgumentParser(description="Run Exp 1–5 across non-scan ratio grid")
    ap.add_argument("--ratio", type=float, choices=RATIOS, help="Single ratio only")
    ap.add_argument("--exp", type=int, choices=[1, 2, 3, 4, 5], help="Single experiment only")
    ap.add_argument("--circuit", help="Single circuit only")
    ap.add_argument(
        "--timeout", type=int, default=None,
        help="Per-circuit wall timeout (default: ATPG_WALL_TIMEOUT or 3600)",
    )
    args = ap.parse_args()

    timeout_s = args.timeout if args.timeout is not None else int(
        os.environ.get("ATPG_WALL_TIMEOUT", "3600")
    )
    circuits = [args.circuit] if args.circuit else list(CIRCUITS_10)
    ratios = [args.ratio] if args.ratio is not None else list(RATIOS)
    experiments = [e for e in EXPERIMENTS if args.exp is None or e["id"] == args.exp]

    os.makedirs(RES_ROOT, exist_ok=True)
    total = len(ratios) * len(experiments) * len(circuits)
    log_msg(
        f"=== Ratio sweep: {len(ratios)} ratios × {len(experiments)} exps "
        f"× {len(circuits)} circuits = {total} runs ==="
    )

    for ratio in ratios:
        pct = ratio_pct(ratio)
        log_msg(f"--- Ratio x{pct}% ---")
        for exp in experiments:
            csv_path = exp_csv_path(exp, ratio)
            log_msg(f"  {exp['name']}: {exp['desc']}")
            with open(csv_path, "w", newline="") as f:
                csv.DictWriter(f, fieldnames=SUMMARY_FIELDS).writeheader()
            for circuit in circuits:
                run_circuit(exp, circuit, ratio, timeout_s)
            log_msg(f"  === Finished {exp['name']} -> {csv_path} ===")

    log_msg("ALL RATIO SWEEPS COMPLETE")


if __name__ == "__main__":
    main()
