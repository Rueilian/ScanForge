#!/usr/bin/env python3
"""
Run remaining 5 circuits (b11,b13,s9234,s15850,s35932) for all 5 existing experiments.
Appends to existing CSV files. Logs stderr for debugging.
"""
import csv, os, subprocess, sys, time

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
FAN_DIR = os.path.join(REPO_ROOT, "FAN_ATPG")
RUNNER = os.path.join(REPO_ROOT, "scripts", "run_progressive_residual.py")
LOG = os.path.join(REPO_ROOT, "results", "sweep_remaining_log.txt")

PER_CIRCUIT_TIMEOUT = 600
CIRCUITS = ["b11", "b13", "s9234", "s15850", "s35932"]

EXPERIMENTS = [
    {"csv": "exp1_baseline.csv",        "env": {},              "t1tp": "off", "t2tp": "off", "t4tp": "off", "extra": ""},
    {"csv": "exp2_two_phase.csv",       "env": {},              "t1tp": "off", "t2tp": "on",  "t4tp": "on",  "extra": ""},
    {"csv": "exp3_uniform_T1.csv",      "env": {"ATPG_T1_BACKTRACK_LIMIT": "5000"}, "t1tp": "off", "t2tp": "off", "t4tp": "off", "extra": ""},
    {"csv": "exp4_enhanced_backtrace.csv", "env": {},           "t1tp": "off", "t2tp": "off", "t4tp": "off", "extra": "set_enhanced_backtrace on"},
    {"csv": "exp5_static_learning.csv", "env": {},              "t1tp": "off", "t2tp": "off", "t4tp": "off", "extra": "set_static_learning on"},
]

def log_msg(msg):
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG, "a") as f:
        f.write(f"[{ts}] {msg}\n")
    print(f"[{ts}] {msg}")

log_msg("=== Starting remaining 5 circuits × 5 experiments ===")

for exp in EXPERIMENTS:
    csv_path = os.path.join(REPO_ROOT, "results", exp["csv"])
    log_msg(f"--- {exp['csv']} ---")
    for circuit in CIRCUITS:
        mask_path = os.path.join(REPO_ROOT, "masks", f"{circuit}_x10.mask")
        if not os.path.exists(mask_path):
            log_msg(f"  {circuit}: SKIP (no mask)")
            continue
        with open(mask_path) as f:
            mask = " ".join(line.strip() for line in f if line.strip())
        log_msg(f"  {circuit}: {exp['csv']}")
        env = os.environ.copy()
        env.update(exp["env"])
        env["ATPG_SUMMARY_CSV"] = csv_path
        cmd = [
            sys.executable, RUNNER,
            "--circuit", circuit, "--ratio", "0.10",
            "--nonscan", mask,
            "--t1-two-phase", exp["t1tp"],
            "--t2-two-phase", exp["t2tp"],
            "--t4-two-phase", exp["t4tp"],
            "--timeout", "3600", "--per-target-timeout", "0",
        ]
        if exp["extra"]:
            cmd += ["--extra-flags", exp["extra"]]
        t0 = time.time()
        try:
            proc = subprocess.run(cmd, cwd=FAN_DIR, env=env, capture_output=True, text=True, timeout=PER_CIRCUIT_TIMEOUT)
            elapsed = time.time() - t0
            log_msg(f"    done ({elapsed:.1f}s) rc={proc.returncode}")
            if proc.returncode != 0:
                log_msg(f"    stderr: {proc.stderr[:500]}")
        except subprocess.TimeoutExpired:
            elapsed = time.time() - t0
            log_msg(f"    TIMEOUT after {elapsed:.1f}s")
        except Exception as e:
            log_msg(f"    ERROR: {e}")
        subprocess.run(["killall", "-9", "fan"], capture_output=True)

log_msg("=== Remaining circuits complete ===")
