#!/usr/bin/env python3
"""
Master experiment sweep. Runs Exp 1, 3, 4, 5, 6 on 15 circuits.
Each experiment writes its own CSV to results/.
"""
import csv, os, subprocess, sys, time

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
FAN_DIR = os.path.join(REPO_ROOT, "FAN_ATPG")
RUNNER = os.path.join(REPO_ROOT, "scripts", "run_progressive_residual.py")
MASK_DIR = os.path.join(REPO_ROOT, "masks")
RES_DIR = os.path.join(REPO_ROOT, "results")
LOG = os.path.join(RES_DIR, "sweep_log.txt")

os.makedirs(RES_DIR, exist_ok=True)

CIRCUITS = ["b03","b04","b05","b07","b08","b09","b11","b13",
            "s953","s1196","s1238","s5378","s9234","s15850","s35932"]

def get_mask(circuit):
    mp = os.path.join(MASK_DIR, f"{circuit}_x10.mask")
    if os.path.exists(mp):
        with open(mp) as f:
            return " ".join(line.strip() for line in f if line.strip())
    return ""

EXPERIMENTS = [
    {
        "name": "exp1_baseline",
        "csv": os.path.join(RES_DIR, "exp1_baseline.csv"),
        "desc": "Baseline: T1=800, Two-Phase OFF",
        "env": {},
        "t1tp": "off", "t2tp": "off", "t4tp": "off",
        "extra": "",
    },
    {
        "name": "exp3_uniform_T1",
        "csv": os.path.join(RES_DIR, "exp3_uniform_T1.csv"),
        "desc": "Uniform T1=5000 (same as T>1)",
        "env": {"ATPG_T1_BACKTRACK_LIMIT": "5000"},
        "t1tp": "off", "t2tp": "off", "t4tp": "off",
        "extra": "",
    },
    {
        "name": "exp4_two_phase",
        "csv": os.path.join(RES_DIR, "exp4_two_phase.csv"),
        "desc": "Two-Phase ON at T=2, T=4",
        "env": {},
        "t1tp": "off", "t2tp": "on", "t4tp": "on",
        "extra": "",
    },
    {
        "name": "exp5_enhanced_backtrace",
        "csv": os.path.join(RES_DIR, "exp5_enhanced_backtrace.csv"),
        "desc": "Enhanced backtrace ON",
        "env": {},
        "t1tp": "off", "t2tp": "off", "t4tp": "off",
        "extra": "set_enhanced_backtrace on",
    },
    {
        "name": "exp6_static_learning",
        "csv": os.path.join(RES_DIR, "exp6_static_learning.csv"),
        "desc": "Static learning ON",
        "env": {},
        "t1tp": "off", "t2tp": "off", "t4tp": "off",
        "extra": "set_static_learning on",
    },
]

FIELD_NAMES = [
    "circuit","ratio","excluded_ff","total_ff","denominator",
    "T1_DT","T1_AU","T1_AB","T1_TO","T1_FC",
    "R1_count","T2_target","T2_new_DT","T2_AU","T2_AB","T2_TO",
    "R2_count","T4_target","T4_new_DT","T4_AU","T4_AB","T4_TO",
    "final_DT","FC_T1","FC_T1_T2","FC_T1_T2_T4",
    "gain_T2_pp","gain_T4_pp","total_gain_pp",
    "T1_rt","T2_rt","T4_rt","total_rt",
    "recovered_per_sec_T2","recovered_per_sec_T4",
    "per_target_timeout_sec","status",
]

def log_msg(msg):
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG, "a") as f:
        f.write(f"[{ts}] {msg}\n")
    print(f"[{ts}] {msg}")

for exp in EXPERIMENTS:
    log_msg(f"=== Starting {exp['name']}: {exp['desc']} ===")
    csv_path = exp["csv"]
    with open(csv_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELD_NAMES)
        w.writeheader()

    for circuit in CIRCUITS:
        mask = get_mask(circuit)
        log_msg(f"  {circuit}: {exp['name']}")
        env = os.environ.copy()
        env.update(exp["env"])
        env["ATPG_SUMMARY_CSV"] = csv_path
        cmd = [
            sys.executable, RUNNER,
            "--circuit", circuit,
            "--ratio", "0.10",
            "--nonscan", mask,
            "--t1-two-phase", exp["t1tp"],
            "--t2-two-phase", exp["t2tp"],
            "--t4-two-phase", exp["t4tp"],
            "--timeout", "3600",
            "--per-target-timeout", "0",
        ]
        if exp["extra"]:
            cmd += ["--extra-flags", exp["extra"]]
        t0 = time.time()
        try:
            proc = subprocess.run(cmd, cwd=FAN_DIR, env=env, capture_output=True, text=True, timeout=7200)
            elapsed = time.time() - t0
            log_msg(f"    done ({elapsed:.1f}s)  rc={proc.returncode}")
        except subprocess.TimeoutExpired:
            log_msg(f"    TIMEOUT after 7200s")
            continue
        except Exception as e:
            log_msg(f"    ERROR: {e}")
            continue

    log_msg(f"=== Finished {exp['name']} ===")

log_msg("ALL EXPERIMENTS COMPLETE")
