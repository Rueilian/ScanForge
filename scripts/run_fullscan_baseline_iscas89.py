#!/usr/bin/env python3
"""
Run full-scan T=1 ATPG baseline on all ISCAS'89 circuits.

Full-scan = no set_nonscan_ff → all FFs are scan FFs.
This gives the ceiling fault coverage against which partial-scan results are compared.
Output: results/iscas89_fullscan_baseline.csv
"""
import os
import re
import subprocess
import sys
import time

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
FAN_DIR = os.path.join(REPO_ROOT, "FAN_ATPG")
FAN_BIN = os.path.join(FAN_DIR, "bin", "opt", "fan")
RPT_DIR = os.path.join(FAN_DIR, "rpt")
SCRIPT_DIR = os.path.join(FAN_DIR, "script", "fanScripts")
BASELINE_CSV = os.path.join(REPO_ROOT, "results", "iscas89_fullscan_baseline.csv")

# All ISCAS'89 circuits with TTU-converted SDFFR_X1 netlists
CIRCUITS = ["s27", "s510", "s953", "s1196", "s1238", "s5378",
            "s9234", "s15850", "s35932", "s38417", "s38584"]

WALL_TIMEOUT = int(os.environ.get("ATPG_WALL_TIMEOUT", "3600"))
PER_TARGET_TIMEOUT = float(os.environ.get("ATPG_PER_TARGET_TIMEOUT", "0"))


def run_fullscan(circuit: str) -> dict:
    label = f"{circuit}_fullscan_t1"
    script_path = os.path.join(SCRIPT_DIR, f"{label}.script")
    rpt_path = os.path.join(RPT_DIR, f"{label}.rpt")
    nl_path = os.path.join(FAN_DIR, "mod_netlist", f"{circuit}.v")
    if not os.path.exists(nl_path):
        return {"circuit": circuit, "status": "SKIP", "fc": None, "dt": None,
                "au": None, "ud": None, "total": None, "elapsed": 0.0, "ff_count": 0}

    with open(nl_path) as f:
        src = f.read()
    ff_count = len(re.findall(r'SDFFR_X1 ', src))

    ptt_line = [f"set_per_target_timeout {PER_TARGET_TIMEOUT:.1f}"] if PER_TARGET_TIMEOUT > 0 else []
    lines = [
        "read_lib techlib/mod_nangate45.mdt",
        f"read_netlist mod_netlist/{circuit}.v",
        "build_circuit --frame 1",
        "set_fault_type saf",
        "add_fault --all",
        *ptt_line,
        "set_static_compression off",
        "set_dynamic_compression off",
        "run_atpg",
        f"report_statistics > {rpt_path}",
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
        return {"circuit": circuit, "status": "TIMEOUT", "fc": None, "dt": None,
                "au": None, "ud": None, "total": None, "elapsed": WALL_TIMEOUT, "ff_count": ff_count}

    fc = dt = au = ab = ud = to_n = total = None
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
                if key == "dt":    dt = val
                elif key == "au":  au = val
                elif key == "ab":  ab = val
                elif key == "ud":  ud = val
                elif key == "to_n": to_n = val
        m_fc = re.search(r"fault coverage \(scan protocol\)\s+([\d.]+)%", text)
        if m_fc:
            fc = float(m_fc.group(1))
        total = (dt or 0) + (au or 0) + (ab or 0) + (ud or 0) + (to_n or 0)
    else:
        status = "FAILED"

    return {"circuit": circuit, "status": status, "fc": fc, "dt": dt,
            "au": au, "ud": ud, "total": total, "elapsed": elapsed, "ff_count": ff_count}


def main():
    os.makedirs(SCRIPT_DIR, exist_ok=True)
    os.makedirs(RPT_DIR, exist_ok=True)

    circuits = sys.argv[1:] if len(sys.argv) > 1 else CIRCUITS

    rows = []
    header = "circuit,ff_count,total_faults,DT,AU,UD,FC_fullscan_pct,elapsed_s,status"
    print(header)

    for c in circuits:
        r = run_fullscan(c)
        fc_str = f"{r['fc']:.2f}" if r['fc'] is not None else "N/A"
        row = (f"{r['circuit']},{r['ff_count']},{r['total'] or 'N/A'},"
               f"{r['dt'] or 'N/A'},{r['au'] or 'N/A'},{r['ud'] or 'N/A'},"
               f"{fc_str},{r['elapsed']:.1f},{r['status']}")
        print(row)
        rows.append(row)

    with open(BASELINE_CSV, "w") as f:
        f.write(header + "\n")
        f.write("\n".join(rows) + "\n")

    print(f"\nBaseline saved → {BASELINE_CSV}")


if __name__ == "__main__":
    main()
