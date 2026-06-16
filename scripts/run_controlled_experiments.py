#!/usr/bin/env python3
"""
Controlled experiments pipeline.
Experiments on 4 representative circuits to quantify:
  A) Does ptt=0 at T=1 eliminate T=2 gain? (structural vs TO mechanism)
  B) Does Two-Phase OFF at T=2 reduce T=2 gain? (Two-Phase contribution)

Usage:  ATPG_PER_TARGET_TIMEOUT=5 python3 scripts/run_controlled_experiments.py
Output: results/experiment_pipeline_comparison.csv
"""
import csv, os, re, subprocess, sys, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from atpg_timeouts import PER_TARGET_TIMEOUT_S, WALL_TIMEOUT_S

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
FAN_DIR = os.path.join(REPO_ROOT, "FAN_ATPG")
FAN_BIN = os.path.join(FAN_DIR, "bin", "opt", "fan")
RPT_DIR = os.path.join(FAN_DIR, "rpt")
SCRIPT_DIR = os.path.join(FAN_DIR, "script", "fanScripts")
RES_FAULT_DIR = os.path.join(REPO_ROOT, "results", "residual_faults")
os.makedirs(RES_FAULT_DIR, exist_ok=True)

MASKS = {
    "b05": "b05_x10.mask",
    "b13": "b13_x10.mask",
    "s5378": "s5378_x10.mask",
    "s38417": "s38417_x10.mask",
}

OUT_CSV = os.path.join(REPO_ROOT, "results", "experiment_pipeline_comparison.csv")
FIELDS = [
    "circuit", "experiment",
    "T1_ptt", "T1_two_phase", "T2_two_phase",
    "T1_DT", "T1_AU", "T1_TO", "T1_AB",
    "T2_new_DT", "T2_AU", "T2_AB", "T2_TO",
    "T4_new_DT",
    "FC_T1", "FC_T1_T2", "FC_T1_T2_T4",
    "gain_T2_pp", "gain_T4_pp",
    "T1_rt", "T2_rt", "T4_rt",
]


def run_fan(label, circuit, frame, nonscan_ffs, fault_file=None,
            timeout_s=None, per_target_timeout=None, two_phase=True):
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
        subprocess.run(
            [FAN_BIN, "-f", os.path.relpath(script_path, FAN_DIR)],
            cwd=FAN_DIR, capture_output=True, text=True, timeout=timeout_s)
        elapsed = time.time() - t0
    except subprocess.TimeoutExpired:
        return {"label": label, "elapsed": timeout_s, "status": "TIMEOUT"}
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
        m_fc = re.search(r"fault coverage \(scan protocol\)\s+([\d.]+)%", text)
        if not m_fc:
            m_fc = re.search(r"fault coverage\s+([\d.]+)%", text)
        if m_fc:
            fc = float(m_fc.group(1))
        total = (dt or 0) + (au or 0) + (ab or 0) + (ud or 0) + (to_num or 0)
    else:
        status = "FAILED"
    return {"label": label, "fc": fc, "dt": dt, "au": au, "ab": ab,
            "to": to_num or 0, "total": total, "elapsed": elapsed, "status": status}


def parse_faults(path):
    faults = {}
    if not os.path.exists(path):
        return faults
    with open(path) as f:
        for line in f:
            m = re.match(r'#\s+g=(\d+)\s+l=(-?\d+)\s+(SA[01])\s+(DT|AU|AB|UD|TI|RE|PT|TO)\s', line)
            if m:
                gid, fl, ft, st = int(m.group(1)), int(m.group(2)), m.group(3), m.group(4)
                faults[(gid, fl, ft)] = st
    return faults


def write_fault_list(faults, path):
    with open(path, "w") as f:
        for gid, fl, ft in sorted(faults):
            if fl < 0:
                continue
            f.write(f"{gid} {ft} {fl}\n")


def run_pipeline(circuit, ratio, nonscan_ffs, ptt, t1_two_phase, t2_two_phase, exp_name):
    """Run T=1→T=2→T=4 and return result dict."""
    pct = int(ratio * 100)
    tag = f"exp_{circuit}_x{pct}_{exp_name}"

    # T=1
    t1 = run_fan(f"{tag}_t1", circuit, 1, nonscan_ffs,
                 per_target_timeout=ptt, two_phase=t1_two_phase)
    if t1["status"] != "PASS" or t1.get("fc") is None:
        print(f"  {circuit} T=1 FAILED: {t1.get('status')}")
        return None

    t1_faults = parse_faults(os.path.join(RPT_DIR, f"{tag}_t1_faults.txt"))
    if not t1_faults:
        print(f"  {circuit} T=1 no fault data")
        return None
    D1 = {k for k, v in t1_faults.items() if v == 'DT'}
    denom = len(t1_faults)

    # T=2 residual
    R1 = {k for k, v in t1_faults.items() if v != 'DT'}
    r1_file = os.path.join(RES_FAULT_DIR, f"{tag}_after_T1.faults")
    write_fault_list(R1, r1_file)

    t2 = run_fan(f"{tag}_t2", circuit, 2, nonscan_ffs, fault_file=r1_file,
                 per_target_timeout=ptt, two_phase=t2_two_phase)
    t2_new = D2_au = D2_ab = D2_to = 0
    D2 = set()
    if t2["status"] == "PASS":
        t2_faults = parse_faults(os.path.join(RPT_DIR, f"{tag}_t2_faults.txt"))
        D2 = {k for k, v in t2_faults.items() if v == 'DT'}
        D2_au = sum(1 for k, v in t2_faults.items() if v == 'AU')
        D2_ab = sum(1 for k, v in t2_faults.items() if v == 'AB')
        D2_to = sum(1 for k, v in t2_faults.items() if v == 'TO')
        t2_new = len(D2 - D1)

    # T=4 residual
    R2 = R1 - D2
    r2_file = os.path.join(RES_FAULT_DIR, f"{tag}_after_T1_T2.faults")
    write_fault_list(R2, r2_file)
    t4 = run_fan(f"{tag}_t4", circuit, 4, nonscan_ffs, fault_file=r2_file,
                 per_target_timeout=ptt, two_phase=True)
    t4_new = 0
    D4 = set()
    if t4["status"] == "PASS":
        t4_faults = parse_faults(os.path.join(RPT_DIR, f"{tag}_t4_faults.txt"))
        D4 = {k for k, v in t4_faults.items() if v == 'DT'}
        t4_new = len(D4 - D1 - D2)

    Du = D1 | D2 | D4
    fc1 = len(D1)/denom*100
    fc12 = len(D1|D2)/denom*100
    fc124 = len(Du)/denom*100
    gain2 = fc12 - fc1
    gain4 = fc124 - fc12

    return {
        "circuit": circuit, "experiment": exp_name,
        "T1_ptt": ptt, "T1_two_phase": t1_two_phase, "T2_two_phase": t2_two_phase,
        "T1_DT": len(D1),
        "T1_AU": sum(1 for v in t1_faults.values() if v == 'AU'),
        "T1_TO": sum(1 for v in t1_faults.values() if v == 'TO'),
        "T1_AB": sum(1 for v in t1_faults.values() if v == 'AB'),
        "T2_new_DT": t2_new, "T2_AU": D2_au, "T2_AB": D2_ab, "T2_TO": D2_to,
        "T4_new_DT": t4_new,
        "FC_T1": round(fc1, 2), "FC_T1_T2": round(fc12, 2),
        "FC_T1_T2_T4": round(fc124, 2),
        "gain_T2_pp": round(gain2, 2), "gain_T4_pp": round(gain4, 2),
        "T1_rt": round(t1.get("elapsed", 0), 2),
        "T2_rt": round(t2.get("elapsed", 0), 2),
        "T4_rt": round(t4.get("elapsed", 0), 2),
    }


def main():
    print("=" * 70)
    print("Controlled Experiments: ptt & Two-Phase effect on T=2 recovery")
    print("=" * 70)

    # Circuit configs: (circuit, ratio, mask_file)
    circuits = [
        ("b05", 0.10, "b05_x10.mask"),
        ("b13", 0.10, "b13_x10.mask"),
        ("s5378", 0.10, "s5378_x10.mask"),
        ("s38417", 0.10, "s38417_x10.mask"),
    ]

    # Experiment configurations:
    # (name, T1_ptt, T1_two_phase, T2_two_phase)
    experiments = [
        # Baseline (matches current CSV)
        ("baseline", 5, True, True),
        # A: ptt=0 at T=1, rest same
        ("no_ptt_T1", 0, True, True),
        # B: Two-Phase OFF at T=2, rest same
        ("no_tp_T2", 5, True, False),
    ]

    results = []
    for circuit, ratio, mask_name in circuits:
        mask_path = os.path.join(REPO_ROOT, "masks", mask_name)
        if os.path.exists(mask_path):
            with open(mask_path) as f:
                ns_ffs = f.read().strip()
        else:
            print(f"  WARNING: mask {mask_path} not found, skipping {circuit}")
            continue

        for exp_name, ptt, t1_tp, t2_tp in experiments:
            print(f"\n{'─' * 60}")
            print(f"Circuit: {circuit}  Experiment: {exp_name}")
            print(f"  T1: ptt={ptt}s, Two-Phase={'ON' if t1_tp else 'OFF'}")
            print(f"  T2: Two-Phase={'ON' if t2_tp else 'OFF'}")
            sys.stdout.flush()
            row = run_pipeline(circuit, ratio, ns_ffs, ptt, t1_tp, t2_tp, exp_name)
            if row:
                results.append(row)
                print(f"  FC_T1={row['FC_T1']}%  FC_T1_T2={row['FC_T1_T2']}%  Gain={row['gain_T2_pp']}pp  T=2+DT={row['T2_new_DT']}")
            else:
                print(f"  FAILED (skipped)")
            sys.stdout.flush()

    # Write CSV
    with open(OUT_CSV, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(results)

    print(f"\n{'=' * 70}")
    print(f"Results written to {OUT_CSV}")
    print(f"{'=' * 70}")

    # Print comparison table
    print(f"\n{'circuit':>8} {'exp':>12} {'T1_ptt':>8} {'T1_FC':>8} {'T2_gain':>8} {'T2_+DT':>8}")
    print("-" * 56)
    for r in results:
        print(f"{r['circuit']:>8} {r['experiment']:>12} {r['T1_ptt']:>8} {r['FC_T1']:>7.1f}% {r['gain_T2_pp']:>7.2f} {r['T2_new_DT']:>8}")


if __name__ == "__main__":
    main()
