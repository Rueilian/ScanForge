#!/usr/bin/env python3
"""
True Progressive Residual Multi-Frame ATPG Pipeline.
Runs T=1 → residual T=2 → residual T=4 and reports union coverage.
Outputs progressive_residual_summary.csv.
"""
import argparse, csv, os, re, subprocess, sys, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from atpg_timeouts import PER_TARGET_TIMEOUT_S, WALL_TIMEOUT_S

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
FAN_DIR = os.path.join(REPO_ROOT, "FAN_ATPG")
FAN_BIN = os.path.join(FAN_DIR, "bin", "opt", "fan")
RPT_DIR = os.path.join(FAN_DIR, "rpt")
SCRIPT_DIR = os.path.join(FAN_DIR, "script", "fanScripts")
RES_FAULT_DIR = os.path.join(REPO_ROOT, "results", "residual_faults")
RES_STATUS_DIR = os.path.join(REPO_ROOT, "results", "fault_status")
SUMMARY_CSV = os.path.join(REPO_ROOT, "results", "progressive_residual_summary.csv")

os.makedirs(RES_FAULT_DIR, exist_ok=True)
os.makedirs(RES_STATUS_DIR, exist_ok=True)

SUMMARY_FIELDS = [
    "circuit", "ratio", "excluded_ff", "total_ff", "denominator",
    "T1_DT", "T1_AU", "T1_AB", "T1_TO", "T1_FC",
    "R1_count", "T2_target", "T2_new_DT", "T2_AU", "T2_AB", "T2_TO",
    "R2_count", "T4_target", "T4_new_DT", "T4_AU", "T4_AB", "T4_TO",
    "final_DT", "FC_T1", "FC_T1_T2", "FC_T1_T2_T4",
    "gain_T2_pp", "gain_T4_pp", "total_gain_pp",
    "T1_rt", "T2_rt", "T4_rt", "total_rt",
    "recovered_per_sec_T2", "recovered_per_sec_T4",
    "per_target_timeout_sec", "status"
]

def run_fan(label, circuit, frame, nonscan_ffs, fault_file=None, timeout_s=None, per_target_timeout=None, two_phase=True):
    if timeout_s is None:
        timeout_s = WALL_TIMEOUT_S
    if per_target_timeout is None:
        per_target_timeout = PER_TARGET_TIMEOUT_S
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
    if per_target_timeout > 0:
        lines.append(f"set_per_target_timeout {per_target_timeout}")
    lines.append(f"set_two_phase_justification {'on' if two_phase else 'off'}")
    lines += [
        "set_static_compression off", "set_dynamic_compression off",
        "run_atpg",
        f"report_statistics > {rpt_path}",
        f"report_fault > {os.path.join(RPT_DIR, label + '_faults.txt')}",
        "exit",
    ]
    with open(script_path, "w") as f:
        f.write("\n".join(lines) + "\n")
    t0 = time.time()
    try:
        proc = subprocess.run(
            [FAN_BIN, "-f", os.path.relpath(script_path, FAN_DIR)],
            cwd=FAN_DIR, capture_output=True, text=True, timeout=timeout_s)
        elapsed = time.time() - t0
    except subprocess.TimeoutExpired:
        return {"label": label, "returncode": -1, "elapsed": timeout_s, "status": "TIMEOUT"}
    fc = dt = au = ab = ud = to_num = total = None
    status = "PASS"
    if os.path.exists(rpt_path):
        with open(rpt_path) as f:
            text = f.read()
        for key, pat in [
            ("dt", r"DT \(detected\)\s+([\d]+)"),
            ("au", r"AU \(atpg untestable\)\s+([\d]+)"),
            ("ab", r"AB \(atpg abort\)\s+([\d]+)"),
            ("ud", r"UD \(undetected\)\s+([\d]+)"),
            ("to_num", r"TO \(timeout\)\s+([\d]+)"),
        ]:
            m = re.search(pat, text)
            if m:
                if key == "dt": dt = int(m.group(1))
                elif key == "au": au = int(m.group(1))
                elif key == "ab": ab = int(m.group(1))
                elif key == "ud": ud = int(m.group(1))
                elif key == "to_num": to_num = int(m.group(1))

        # Parse fault coverage robustly
        m_fc = re.search(r"fault coverage \(scan protocol\)\s+([\d.]+)%", text)
        if not m_fc:
            m_fc = re.search(r"fault coverage\s+([\d.]+)%", text)
        if m_fc:
            fc = float(m_fc.group(1))
        total = (dt or 0) + (au or 0) + (ab or 0) + (ud or 0) + (to_num or 0)
    else:
        status = "FAILED"
        print(f"  ERROR: report {rpt_path} not found.")
        print(f"  FAN stdout:\n{proc.stdout}")
        print(f"  FAN stderr:\n{proc.stderr}")
    return {"label": label, "fc": fc, "dt": dt, "au": au, "ab": ab, "ud": ud, "to": to_num or 0, "total": total,
            "returncode": proc.returncode, "elapsed": elapsed, "status": status}

def parse_faults(path):
    faults = {}; fault_list = []
    if not os.path.exists(path): return faults, fault_list
    with open(path) as f:
        for line in f:
            m = re.match(r'#\s+g=(\d+)\s+l=(-?\d+)\s+(SA[01])\s+(DT|AU|AB|UD|TI|RE|PT|TO)\s', line)
            if m:
                gid, fl, ft, st = int(m.group(1)), int(m.group(2)), m.group(3), m.group(4)
                faults[(gid, fl, ft)] = st
                fault_list.append((gid, fl, ft, st))
    return faults, fault_list

def write_fault_list(faults, path):
    with open(path, "w") as f:
        for gid, fl, ft in sorted(faults):
            if fl < 0:  # skip QN-pin faults (faultyLine=-4): FAN always leaves them UD
                continue
            f.write(f"{gid} {ft} {fl}\n")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--circuit", required=True)
    ap.add_argument("--ratio", type=float, required=True)
    ap.add_argument("--nonscan", default="")
    ap.add_argument("--timeout", type=int, default=WALL_TIMEOUT_S,
                    help=f"Wall-clock timeout per FAN run (default {WALL_TIMEOUT_S}s)")
    ap.add_argument("--per-target-timeout", type=float, default=PER_TARGET_TIMEOUT_S,
                    help=f"Per-target-fault timeout in seconds (0=disabled, default {PER_TARGET_TIMEOUT_S})")
    ap.add_argument("--t1-two-phase", choices=["on","off"], default="on",
                    help="Two-Phase setting for T=1 stage (default on)")
    ap.add_argument("--t2-two-phase", choices=["on","off"], default="on",
                    help="Two-Phase setting for T=2 stage (default on)")
    ap.add_argument("--t4-two-phase", choices=["on","off"], default="on",
                    help="Two-Phase setting for T=4 stage (default on)")
    args = ap.parse_args()

    c = args.circuit; ratio = args.ratio; ns_ffs = args.nonscan
    ptt = args.per_target_timeout
    excl = len(ns_ffs.split()) if ns_ffs else 0
    total_ff = None
    nl_path = os.path.join(FAN_DIR, "mod_netlist", f"{c}.v")
    if os.path.exists(nl_path):
        with open(nl_path) as f:
            total_ff = len(re.findall(r'DFF[RS]_X1 ', f.read()))
    pct = int(ratio * 100); tag = f"{c}_x{pct}"

    print(f"\n{'='*60}")
    print(f"Progressive Residual: {tag}  excl={excl}/{total_ff or '?'}")
    print(f"{'='*60}")

    # ── Phase 1: T=1 all faults ──
    print("Phase 1: T=1 all faults")
    t1 = run_fan(f"{tag}_t1_all", c, 1, ns_ffs, per_target_timeout=ptt, two_phase=args.t1_two_phase=="on")
    if t1["status"] != "PASS":
        print(f"  {t1['status']}")
        return
    if t1.get("fc") is None:
        print("  ERROR: T=1 report missing fault coverage")
        return
    t1_elapsed = t1.get("elapsed") or 0.0
    print(f"  FC={t1['fc']:.2f}% DT={t1['dt']} AU={t1['au']} ({t1_elapsed:.1f}s)")

    t1_faults, _ = parse_faults(os.path.join(RPT_DIR, f"{tag}_t1_all_faults.txt"))
    if not t1_faults:
        print("  ERROR: no T=1 fault data"); return
    D1 = {k for k, v in t1_faults.items() if v == 'DT'}
    denom = len(t1_faults)

    # ── Phase 2: T=2 residual ──
    R1 = {k for k, v in t1_faults.items() if v != 'DT'}
    r1_file = os.path.join(RES_FAULT_DIR, f"{tag}_after_T1.faults")
    write_fault_list(R1, r1_file)
    print(f"Phase 2: T=2 on {len(R1)} residual faults")
    t2 = run_fan(f"{tag}_t2_res", c, 2, ns_ffs, fault_file=r1_file, per_target_timeout=ptt, two_phase=args.t2_two_phase=="on")
    t2_new = D2_au = D2_ab = D2_to = 0
    if t2["status"] == "PASS":
        t2_faults, _ = parse_faults(os.path.join(RPT_DIR, f"{tag}_t2_res_faults.txt"))
        D2 = {k for k, v in t2_faults.items() if v == 'DT'}
        D2_au = sum(1 for k, v in t2_faults.items() if v == 'AU')
        D2_ab = sum(1 for k, v in t2_faults.items() if v == 'AB')
        D2_to = sum(1 for k, v in t2_faults.items() if v == 'TO')
        t2_new = len(D2 - D1)
        print(f"  new_DT={t2_new} AU={D2_au} ({t2['elapsed']:.1f}s)")
    else:
        print(f"  {t2['status']}")
        D2 = set()

    # ── Phase 3: T=4 residual ──
    R2 = R1 - D2
    r2_file = os.path.join(RES_FAULT_DIR, f"{tag}_after_T1_T2.faults")
    write_fault_list(R2, r2_file)
    print(f"Phase 3: T=4 on {len(R2)} remaining residual faults")
    t4 = run_fan(f"{tag}_t4_res", c, 4, ns_ffs, fault_file=r2_file, per_target_timeout=ptt, two_phase=args.t4_two_phase=="on")
    t4_new = D4_au = D4_ab = D4_to = 0
    if t4["status"] == "PASS":
        t4_faults, _ = parse_faults(os.path.join(RPT_DIR, f"{tag}_t4_res_faults.txt"))
        D4 = {k for k, v in t4_faults.items() if v == 'DT'}
        D4_au = sum(1 for k, v in t4_faults.items() if v == 'AU')
        D4_ab = sum(1 for k, v in t4_faults.items() if v == 'AB')
        D4_to = sum(1 for k, v in t4_faults.items() if v == 'TO')
        t4_new = len(D4 - D1 - D2)
        print(f"  new_DT={t4_new} AU={D4_au} ({t4['elapsed']:.1f}s)")
    else:
        print(f"  {t4['status']}")
        D4 = set()

    # ── Union ──
    Du = D1 | D2 | D4
    fc1 = len(D1)/denom*100; fc12 = len(D1|D2)/denom*100; fc124 = len(Du)/denom*100
    gain2 = fc12 - fc1; gain4 = fc124 - fc12; total_gain = fc124 - fc1
    trt = (t1.get("elapsed",0) + t2.get("elapsed",0) + t4.get("elapsed",0))
    rps2 = t2_new / t2["elapsed"] if t2.get("elapsed") and t2_new else 0
    rps4 = t4_new / t4["elapsed"] if t4.get("elapsed") and t4_new else 0
    status = "PASS" if all(r["status"] == "PASS" for r in [t1, t2, t4]) else "PARTIAL"

    print(f"\nUnion: FC_T1={fc1:.2f}%  T1∪T2={fc12:.2f}%  T1∪T2∪T4={fc124:.2f}%")
    print(f"  +{t2_new} from T=2, +{t4_new} from T=4, total +{t2_new+t4_new}")

    # CSV row
    row = {
        "circuit": c, "ratio": ratio, "excluded_ff": excl, "total_ff": total_ff, "denominator": denom,
        "T1_DT": len(D1), "T1_AU": sum(1 for v in t1_faults.values() if v == 'AU'),
        "T1_AB": sum(1 for v in t1_faults.values() if v == 'AB'),
        "T1_TO": sum(1 for v in t1_faults.values() if v == 'TO'),
        "T1_FC": round(fc1, 2),
        "R1_count": len(R1), "T2_target": len(R1), "T2_new_DT": t2_new,
        "T2_AU": D2_au, "T2_AB": D2_ab, "T2_TO": D2_to,
        "R2_count": len(R2), "T4_target": len(R2), "T4_new_DT": t4_new,
        "T4_AU": D4_au, "T4_AB": D4_ab, "T4_TO": D4_to,
        "final_DT": len(Du), "FC_T1": round(fc1, 2), "FC_T1_T2": round(fc12, 2),
        "FC_T1_T2_T4": round(fc124, 2),
        "gain_T2_pp": round(gain2, 2), "gain_T4_pp": round(gain4, 2),
        "total_gain_pp": round(total_gain, 2),
        "T1_rt": round(t1.get("elapsed", 0), 2), "T2_rt": round(t2.get("elapsed", 0), 2),
        "T4_rt": round(t4.get("elapsed", 0), 2), "total_rt": round(trt, 2),
        "recovered_per_sec_T2": round(rps2, 2), "recovered_per_sec_T4": round(rps4, 2),
        "per_target_timeout_sec": ptt, "status": status,
    }

    # Append CSV
    existed = os.path.exists(SUMMARY_CSV)
    with open(SUMMARY_CSV, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=SUMMARY_FIELDS)
        if not existed: w.writeheader()
        w.writerow(row)

if __name__ == '__main__':
    main()
