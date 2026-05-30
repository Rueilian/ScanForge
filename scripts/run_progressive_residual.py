#!/usr/bin/env python3
"""
True Progressive Residual Multi-Frame ATPG Pipeline.

Phase 1: Run T=1 on all faults, extract DT set D1.
Phase 2: Build residual fault list R1 = All - D1, run T=2 on R1 only.
Phase 3: Build residual fault list R2 = R1 - DT(T=2), run T=4 on R2 only.
Phase 4: Report union coverage over original physical fault denominator.

Usage:
    python3 scripts/run_progressive_residual.py --circuit s27 --nonscan "U_G5 U_G6"
"""
import argparse, csv, os, re, subprocess, sys, tempfile, time
from collections import defaultdict

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
FAN_DIR = os.path.join(REPO_ROOT, "FAN_ATPG")
FAN_BIN = os.path.join(FAN_DIR, "bin", "opt", "fan")
RPT_DIR = os.path.join(FAN_DIR, "rpt")
SCRIPT_DIR = os.path.join(FAN_DIR, "script", "fanScripts")

def run_fan(label, circuit, frame, nonscan_ffs, fault_file=None, timeout_s=180):
    """Run FAN_ATPG. If fault_file is given, use add_fault -f; else add_fault --all."""
    script_path = os.path.join(SCRIPT_DIR, f"{label}.script")
    rpt_path = os.path.join(RPT_DIR, f"{label}.rpt")

    lines = [
        "read_lib techlib/mod_nangate45.mdt",
        f"read_netlist mod_netlist/{circuit}.v",
    ]
    if nonscan_ffs:
        lines.append(f"set_nonscan_ff {nonscan_ffs}")
    lines.append(f"build_circuit --frame {frame}")
    lines.append("set_fault_type saf")
    if fault_file:
        lines.append(f"add_fault -f {fault_file}")
    else:
        lines.append("add_fault --all")
    lines += [
        "set_static_compression off",
        "set_dynamic_compression off",
        "run_atpg",
        f"report_statistics > {rpt_path}",
        f"report_fault > {os.path.join(RPT_DIR, label + '_faults.txt')}",
        "exit",
    ]
    with open(script_path, "w") as f:
        f.write("\n".join(lines) + "\n")

    proc = subprocess.run(
        [FAN_BIN, "-f", os.path.relpath(script_path, FAN_DIR)],
        cwd=FAN_DIR, capture_output=True, text=True, timeout=timeout_s
    )

    # Parse results
    fc = dt = au = ab = ud = total = None
    if os.path.exists(rpt_path):
        with open(rpt_path) as f:
            text = f.read()
        for key, pat in [
            ("fc", r"fault coverage\s+([\d.]+)%"),
            ("dt", r"DT \(detected\)\s+([\d]+)"),
            ("au", r"AU \(atpg untestable\)\s+([\d]+)"),
            ("ab", r"AB \(atpg abort\)\s+([\d]+)"),
            ("ud", r"UD \(undetected\)\s+([\d]+)"),
        ]:
            m = re.search(pat, text)
            if m:
                if key == "fc": fc = float(m.group(1))
                elif key == "dt": dt = int(m.group(1))
                elif key == "au": au = int(m.group(1))
                elif key == "ab": ab = int(m.group(1))
                elif key == "ud": ud = int(m.group(1))
        total = dt + au + ab + ud if all(v is not None for v in [dt, au, ab, ud]) else None

    return {"label": label, "fc": fc, "dt": dt, "au": au, "ab": ab, "ud": ud, "total": total,
            "returncode": proc.returncode}


def parse_faults(path):
    """Parse report_fault output, return {fault_key: status} and list of (gid,line,type,status)."""
    faults = {}
    fault_list = []
    if not os.path.exists(path):
        return faults, fault_list
    with open(path) as f:
        for line in f:
            m = re.match(r'#\s+g=(\d+)\s+l=(-?\d+)\s+(SA[01])\s+(DT|AU|AB|UD|TI|RE|PT)\s', line)
            if m:
                gid = int(m.group(1)); fl = int(m.group(2))
                ft = m.group(3); st = m.group(4)
                key = (gid, fl, ft)
                faults[key] = st
                fault_list.append((gid, fl, ft, st))
    return faults, fault_list


def write_residual_file(residual_faults, path):
    """Write residual fault list: gateID SA0|SA1 faultyLine per line."""
    with open(path, "w") as f:
        for gid, fl, ft in sorted(residual_faults):
            f.write(f"{gid} {ft} {fl}\n")
    return path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--circuit", required=True)
    ap.add_argument("--nonscan", default="", help="space-separated non-scan FF names")
    ap.add_argument("--timeout", type=int, default=180)
    args = ap.parse_args()

    circuit = args.circuit
    nonscan = args.nonscan
    ns_tag = f"x{nonscan.count(' ')+1}" if nonscan else "x0"

    os.makedirs(RPT_DIR, exist_ok=True)
    os.makedirs(SCRIPT_DIR, exist_ok=True)

    print(f"{'='*60}")
    print(f"Progressive Residual ATPG: {circuit} {ns_tag}")
    print(f"{'='*60}")

    # ── Phase 1: T=1 all faults ──
    print("\nPhase 1: T=1 all faults")
    t1 = run_fan(f"{circuit}_{ns_tag}_t1_all", circuit, 1, nonscan)
    print(f"  FC={t1['fc']:.2f}% DT={t1['dt']} AU={t1['au']} AB={t1['ab']} TOTAL={t1['total']}")

    t1_faults, t1_list = parse_faults(os.path.join(RPT_DIR, f"{circuit}_{ns_tag}_t1_all_faults.txt"))
    if not t1_faults:
        print("  ERROR: no fault data from T=1 run")
        return

    D1 = {k for k, v in t1_faults.items() if v == 'DT'}
    denominator = len(t1_faults)
    print(f"  D1={len(D1)}/{denominator} detected")

    # ── Phase 2: T=2 residual ──
    R1 = {k for k, v in t1_faults.items() if v != 'DT'}
    print(f"\nPhase 2: T=2 on R1 ({len(R1)} residual faults)")
    r1_file = os.path.join(RPT_DIR, f"{circuit}_{ns_tag}_r1.txt")
    write_residual_file(R1, r1_file)

    t2 = run_fan(f"{circuit}_{ns_tag}_t2_res", circuit, 2, nonscan, fault_file=r1_file)
    print(f"  FC={t2['fc']:.2f}% DT={t2['dt']} AU={t2['au']} AB={t2['ab']} TOTAL={t2['total']}")

    t2_faults, _ = parse_faults(os.path.join(RPT_DIR, f"{circuit}_{ns_tag}_t2_res_faults.txt"))
    D2 = {k for k, v in t2_faults.items() if v == 'DT'}

    # ── Phase 3: T=4 residual ──
    R2 = R1 - D2
    print(f"\nPhase 3: T=4 on R2 ({len(R2)} remaining residual faults)")
    r2_file = os.path.join(RPT_DIR, f"{circuit}_{ns_tag}_r2.txt")
    write_residual_file(R2, r2_file)

    t4 = run_fan(f"{circuit}_{ns_tag}_t4_res", circuit, 4, nonscan, fault_file=r2_file)
    print(f"  FC={t4['fc']:.2f}% DT={t4['dt']} AU={t4['au']} AB={t4['ab']} TOTAL={t4['total']}")

    t4_faults, _ = parse_faults(os.path.join(RPT_DIR, f"{circuit}_{ns_tag}_t4_res_faults.txt"))
    D4 = {k for k, v in t4_faults.items() if v == 'DT'}

    # ── Union coverage ──
    print(f"\n{'='*60}")
    print(f"Union Coverage (denominator={denominator})")
    D_union = D1 | D2 | D4
    fc_t1 = len(D1) / denominator * 100
    fc_t1_t2 = len(D1 | D2) / denominator * 100
    fc_full = len(D_union) / denominator * 100
    print(f"  FC_T1              = {fc_t1:.2f}%")
    print(f"  FC_T1∪T2           = {fc_t1_t2:.2f}% (+{len(D2 - D1)} from T=2)")
    print(f"  FC_T1∪T2∪T4        = {fc_full:.2f}% (+{len(D4 - D1 - D2)} from T=4)")
    print(f"  Total new recovered = {len(D_union - D1)}")


if __name__ == '__main__':
    main()
