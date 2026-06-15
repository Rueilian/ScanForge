#!/usr/bin/env python3
"""
Full-scan oracle diagnostic for R2 residual faults.

For each circuit, takes the R2 residual fault list (faults not detected at T=2)
and runs them through full-scan T=1 ATPG.  This answers:

  DT at full-scan → partial-scan-BLOCKED: the non-scan FF is preventing detection;
                    changing non-scan FF selection could recover these faults.
  AU at full-scan → circuit-STRUCTURAL: genuinely redundant; no ATPG can detect them.
  AB at full-scan → hard, need more search; ambiguous.

Output: results/fullscan_oracle_summary.csv
"""
import csv
import os
import re
import subprocess
import sys
import time

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
FAN_DIR   = os.path.join(REPO_ROOT, "FAN_ATPG")
FAN_BIN   = os.path.join(FAN_DIR, "bin", "opt", "fan")
RPT_DIR   = os.path.join(FAN_DIR, "rpt")
SCRIPT_DIR = os.path.join(FAN_DIR, "script", "fanScripts")
RES_FAULT_DIR = os.path.join(REPO_ROOT, "results", "residual_faults")
OUT_CSV   = os.path.join(REPO_ROOT, "results", "fullscan_oracle_summary.csv")

WALL_TIMEOUT = int(os.environ.get("ATPG_WALL_TIMEOUT", "3600"))

CIRCUITS = [
    "b03","b04","b05","b07","b08","b09","b11","b13",
    "s953","s1196","s1238","s5378","s9234","s15850","s35932","s38417","s38584",
]


def run_oracle(circuit: str, r2_file: str) -> dict:
    label = f"{circuit}_x10_oracle_fs"
    script_path = os.path.join(SCRIPT_DIR, f"{label}.script")
    rpt_path    = os.path.join(RPT_DIR,    f"{label}.rpt")
    fault_path  = os.path.join(RPT_DIR,    f"{label}_faults.txt")

    nl_path = os.path.join(FAN_DIR, "mod_netlist", f"{circuit}.v")
    if not os.path.exists(nl_path):
        return {"circuit": circuit, "status": "SKIP"}

    r2_count = sum(1 for _ in open(r2_file)) if os.path.exists(r2_file) else 0
    if r2_count == 0:
        return {"circuit": circuit, "status": "EMPTY", "r2_count": 0}

    lines = [
        "read_lib techlib/mod_nangate45.mdt",
        f"read_netlist mod_netlist/{circuit}.v",
        # NO set_nonscan_ff → full-scan
        "build_circuit --frame 1",
        "set_fault_type saf",
        f"add_fault -f {r2_file}",
        "set_static_compression off",
        "set_dynamic_compression off",
        "run_atpg",
        f"report_statistics > {rpt_path}",
        f"report_fault > {fault_path}",
        "exit",
    ]
    with open(script_path, "w") as f:
        f.write("\n".join(lines) + "\n")

    t0 = time.time()
    try:
        proc = subprocess.run(
            [FAN_BIN, "-f", os.path.relpath(script_path, FAN_DIR)],
            cwd=FAN_DIR, capture_output=True, text=True, timeout=WALL_TIMEOUT)
        elapsed = time.time() - t0
    except subprocess.TimeoutExpired:
        return {"circuit": circuit, "status": "TIMEOUT", "r2_count": r2_count,
                "elapsed": WALL_TIMEOUT}

    dt = au = ab = ud = to_n = 0
    status = "PASS"
    if os.path.exists(rpt_path):
        text = open(rpt_path).read()
        for key, pat in [
            ("dt",   r"DT \(detected\)\s+([\d]+)"),
            ("au",   r"AU \(atpg untestable\)\s+([\d]+)"),
            ("ab",   r"AB \(atpg abort\)\s+([\d]+)"),
            ("ud",   r"UD \(undetected\)\s+([\d]+)"),
            ("to_n", r"TO \(timeout\)\s+([\d]+)"),
        ]:
            m = re.search(pat, text)
            if m:
                val = int(m.group(1))
                if key == "dt":    dt   = val
                elif key == "au":  au   = val
                elif key == "ab":  ab   = val
                elif key == "ud":  ud   = val
                elif key == "to_n": to_n = val
    else:
        status = "FAILED"

    return {
        "circuit": circuit, "status": status, "r2_count": r2_count,
        "fs_DT": dt, "fs_AU": au, "fs_AB": ab, "fs_UD": ud, "fs_TO": to_n,
        "partial_scan_blocked_pct": round(100*dt/r2_count, 2) if r2_count else 0,
        "circuit_structural_pct":   round(100*au/r2_count, 2) if r2_count else 0,
        "elapsed": round(time.time() - t0 + elapsed - elapsed, 2),
    }


def main():
    os.makedirs(SCRIPT_DIR, exist_ok=True)
    os.makedirs(RPT_DIR, exist_ok=True)

    circuits = sys.argv[1:] if len(sys.argv) > 1 else CIRCUITS

    header = ("circuit,r2_count,fs_DT,fs_AU,fs_AB,fs_UD,fs_TO,"
              "partial_scan_blocked_pct,circuit_structural_pct,elapsed_s,status")
    print(header)
    rows = []

    for c in circuits:
        r2_file = os.path.join(RES_FAULT_DIR, f"{c}_x10_after_T1_T2.faults")
        if not os.path.exists(r2_file):
            print(f"{c},,,,,,,,,, SKIP (no R2 file)")
            continue
        r = run_oracle(c, r2_file)
        row = (f"{r.get('circuit',c)},{r.get('r2_count','')},{r.get('fs_DT','')},"
               f"{r.get('fs_AU','')},{r.get('fs_AB','')},{r.get('fs_UD','')},"
               f"{r.get('fs_TO','')},{r.get('partial_scan_blocked_pct','')},"
               f"{r.get('circuit_structural_pct','')},{r.get('elapsed','')},{r.get('status','')}")
        print(row)
        rows.append(row)

    with open(OUT_CSV, "w") as f:
        f.write(header + "\n")
        f.write("\n".join(rows) + "\n")
    print(f"\nOracle saved → {OUT_CSV}")


if __name__ == "__main__":
    main()
