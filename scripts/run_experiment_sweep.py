#!/usr/bin/env python3
"""
Master experiment sweep. Runs Exp 1–5 on 10 report-ready circuits @10%.
Each experiment writes its own CSV to results/ (includes memory columns).

Usage:
  ATPG_WALL_TIMEOUT=3600 python3 scripts/run_experiment_sweep.py
  python3 scripts/run_experiment_sweep.py --exp 3        # single experiment
  python3 scripts/run_experiment_sweep.py --circuit b03  # single circuit, all exps
  python3 scripts/run_experiment_sweep.py --large        # include s15850, s35932
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
RES_DIR = os.path.join(REPO_ROOT, "results")
LOG = os.path.join(RES_DIR, "sweep_log.txt")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from run_progressive_residual import SUMMARY_FIELDS

CIRCUITS_10 = [
    "b03", "b04", "b05", "b07", "b08", "b09",
    "s953", "s1196", "s1238", "s5378",
]
LARGE_CIRCUITS = ["s15850", "s35932"]

EXPERIMENTS = [
    {
        "id": 1,
        "name": "exp1_baseline",
        "csv": os.path.join(RES_DIR, "exp1_baseline.csv"),
        "desc": "Baseline (Two-Phase OFF, T1=800)",
        "env": {},
        "t1tp": "off", "t2tp": "off", "t4tp": "off",
        "extra": "",
    },
    {
        "id": 2,
        "name": "exp2_two_phase",
        "csv": os.path.join(RES_DIR, "exp2_two_phase.csv"),
        "desc": "Two-Phase ON at T>1",
        "env": {},
        "t1tp": "off", "t2tp": "on", "t4tp": "on",
        "extra": "",
    },
    {
        "id": 3,
        "name": "exp3_uniform_T1",
        "csv": os.path.join(RES_DIR, "exp3_uniform_T1.csv"),
        "desc": "Uniform T1=5000",
        "env": {"ATPG_T1_BACKTRACK_LIMIT": "5000"},
        "t1tp": "off", "t2tp": "off", "t4tp": "off",
        "extra": "",
    },
    {
        "id": 4,
        "name": "exp4_enhanced_backtrace",
        "csv": os.path.join(RES_DIR, "exp4_enhanced_backtrace.csv"),
        "desc": "Enhanced backtrace ON",
        "env": {},
        "t1tp": "off", "t2tp": "off", "t4tp": "off",
        "extra": "set_enhanced_backtrace on",
    },
    {
        "id": 5,
        "name": "exp5_static_learning",
        "csv": os.path.join(RES_DIR, "exp5_static_learning.csv"),
        "desc": "Static learning ON",
        "env": {},
        "t1tp": "off", "t2tp": "off", "t4tp": "off",
        "extra": "set_static_learning on",
    },
]


def log_msg(msg):
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG, "a") as f:
        f.write(f"[{ts}] {msg}\n")
    print(f"[{ts}] {msg}", flush=True)


def load_mask(circuit):
    path = os.path.join(MASK_DIR, f"{circuit}_x10.mask")
    if not os.path.exists(path):
        return None
    with open(path) as f:
        return " ".join(line.strip() for line in f if line.strip())


def run_circuit(exp, circuit, timeout_s):
    mask = load_mask(circuit)
    if mask is None:
        log_msg(f"  {circuit}: SKIP (no mask)")
        return
    log_msg(f"  {circuit}: {exp['name']}")
    env = os.environ.copy()
    env.update(exp["env"])
    env["ATPG_SUMMARY_CSV"] = exp["csv"]
    cmd = [
        sys.executable, RUNNER,
        "--circuit", circuit,
        "--ratio", "0.10",
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
        proc = subprocess.run(cmd, cwd=FAN_DIR, env=env, capture_output=True, text=True, timeout=timeout_s)
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
    ap = argparse.ArgumentParser(description="Run Exp 1–5 ablation sweep with memory columns")
    ap.add_argument("--exp", type=int, choices=[1, 2, 3, 4, 5], help="Run a single experiment only")
    ap.add_argument("--circuit", help="Run a single circuit across selected experiments")
    ap.add_argument("--large", action="store_true", help="Include s15850 and s35932")
    ap.add_argument("--timeout", type=int, default=None,
                    help="Per-circuit wall timeout (default: ATPG_WALL_TIMEOUT or 3600)")
    args = ap.parse_args()

    timeout_s = args.timeout if args.timeout is not None else int(os.environ.get("ATPG_WALL_TIMEOUT", "3600"))
    if args.circuit:
        circuits = [args.circuit]
    else:
        circuits = list(CIRCUITS_10)
        if args.large:
            circuits.extend(LARGE_CIRCUITS)
    experiments = [e for e in EXPERIMENTS if args.exp is None or e["id"] == args.exp]

    os.makedirs(RES_DIR, exist_ok=True)
    log_msg(f"=== Experiment sweep: {len(circuits)} circuits × {len(experiments)} experiments ===")

    for exp in experiments:
        log_msg(f"--- {exp['name']}: {exp['desc']} ---")
        with open(exp["csv"], "w", newline="") as f:
            csv.DictWriter(f, fieldnames=SUMMARY_FIELDS).writeheader()
        for circuit in circuits:
            run_circuit(exp, circuit, timeout_s)
        log_msg(f"=== Finished {exp['name']} -> {exp['csv']} ===")

    log_msg("ALL EXPERIMENTS COMPLETE")


if __name__ == "__main__":
    main()
