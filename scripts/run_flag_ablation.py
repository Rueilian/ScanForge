#!/usr/bin/env python3
"""
Quick flag ablation: test 3 ATPG flags individually + all-on.
Runs FAN directly (no T1/T2/T4 progressive pipeline) on all 15 circuits
with 5 flag conditions. Reports FC(scan), AB, TO, runtime per run.

Conditions:
  baseline, enhanced_only, backjump_only, dominator_only, all_on

Usage:
  python3 scripts/run_flag_ablation.py [--resume]

Output: results/flag_ablation.csv
"""
import argparse, csv, os, re, subprocess, sys, time

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
FAN_DIR = os.path.join(REPO, "FAN_ATPG")
FAN_BIN = os.path.join(FAN_DIR, "bin", "opt", "fan")
MASK_DIR = os.path.join(REPO, "masks")
OUT_CSV = os.path.join(REPO, "results", "flag_ablation.csv")

CIRCUITS = ["b03","b04","b05","b07","b08","b09","b11","b13",
            "s953","s1196","s1238","s5378","s9234","s15850","s35932"]

FLAGS = {
    "baseline":       [],
    "enhanced_only":  ["set_enhanced_backtrace on"],
    "backjump_only":  ["set_backjump on"],
    "dominator_only": ["set_dominator_check on"],
    "all_on":         ["set_enhanced_backtrace on",
                       "set_backjump on",
                       "set_dominator_check on"],
}

def load_mask(circuit):
    with open(os.path.join(MASK_DIR, f"{circuit}_x10.mask")) as f:
        return " ".join(ln.strip() for ln in f if ln.strip())

def build_script(circuit, flag_cmds):
    mask = load_mask(circuit)
    lines = [
        "read_lib techlib/mod_nangate45.mdt",
        f"read_netlist mod_netlist/{circuit}.v",
    ]
    if mask:
        # Strip trailing/leading; set_nonscan_ff expects space-separated
        ffs = mask.strip()
        if ffs:
            lines.append(f"set_nonscan_ff {ffs}")
    lines.append("build_circuit")
    lines.append("set_fault_type saf")
    lines.append("add_fault --all")
    lines.append("set_static_compression off")
    lines.append("set_dynamic_compression off")
    lines.extend(flag_cmds)
    lines.append("run_atpg")
    lines.append("report_statistics")
    lines.append("exit")
    return "\n".join(lines) + "\n"

def parse_rpt(text):
    """Parse FAN stdout for FC, AB, TO, runtime."""
    fc = ab = to = runtime = None
    for line in text.split("\n"):
        m = re.search(r'fault coverage \(raw, appendix\)\s+([\d.]+)%', line)
        if m: fc = float(m.group(1))
        m = re.search(r'AB \(atpg abort\)\s+(\d+)', line)
        if m: ab = int(m.group(1))
        m = re.search(r'TO \(timeout\)\s+(\d+)', line)
        if m: to = int(m.group(1))
        m = re.search(r'ATPG runtime\s+([\d.]+) s', line)
        if m: runtime = float(m.group(1))
    return fc, ab, to, runtime

def run_already_done():
    """Return set of (circuit, condition) already recorded."""
    done = set()
    if os.path.exists(OUT_CSV):
        with open(OUT_CSV) as f:
            reader = csv.DictReader(f)
            for row in reader:
                done.add((row["circuit"], row["condition"]))
    return done

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--resume", action="store_true",
                        help="Skip already-recorded (circuit,condition) pairs")
    args = parser.parse_args()

    done = run_already_done() if args.resume else set()

    os.makedirs(os.path.dirname(OUT_CSV), exist_ok=True)
    file_exists = os.path.exists(OUT_CSV)
    fout = open(OUT_CSV, "a" if args.resume else "w")
    writer = csv.writer(fout)
    if not file_exists or not args.resume:
        writer.writerow(["circuit", "condition", "FC_pct", "AB", "TO", "runtime_s"])

    total = len(CIRCUITS) * len(FLAGS)
    done_count = len(done)
    idx = 0
    for ckt in CIRCUITS:
        for cond, cmds in FLAGS.items():
            idx += 1
            key = (ckt, cond)
            if key in done:
                print(f"  [{idx}/{total}] SKIP {ckt}/{cond} (already done)")
                continue
            script = build_script(ckt, cmds)
            script_path = os.path.join(FAN_DIR, "script", f"flag_ablation_{ckt}_{cond}.script")
            with open(script_path, "w") as f:
                f.write(script)
            print(f"  [{idx}/{total}] {ckt}/{cond} ...", end=" ", flush=True)
            t0 = time.time()
            try:
                r = subprocess.run(
                    [FAN_BIN, "-f", os.path.relpath(script_path, FAN_DIR)],
                    cwd=FAN_DIR, capture_output=True, text=True, timeout=600)
                elapsed = time.time() - t0
                if r.returncode != 0:
                    print(f"FAILED(exit={r.returncode}) [{elapsed:.1f}s]")
                    writer.writerow([ckt, cond, "", "", "", round(elapsed, 3)])
                    fout.flush()
                    continue
                fc, ab, to, runtime = parse_rpt(r.stdout)
                if fc is None:
                    # try parsing report file
                    rpt_path = os.path.join(FAN_DIR, "rpt",
                                            f"flag_ablation_{ckt}_{cond}.rpt")
                    if os.path.exists(rpt_path):
                        with open(rpt_path) as f:
                            fc, ab, to, runtime = parse_rpt(f.read())
                print(f"FC={fc}% AB={ab} TO={to} {runtime}s [{elapsed:.1f}s]")
                writer.writerow([ckt, cond,
                                 f"{fc:.2f}" if fc else "",
                                 ab if ab is not None else "",
                                 to if to is not None else "",
                                 round(runtime, 6) if runtime else round(elapsed, 3)])
            except subprocess.TimeoutExpired:
                print(f"TIMEOUT")
                writer.writerow([ckt, cond, "", "", "1", "600.0"])
            fout.flush()
    fout.close()
    print(f"\nDone -> {OUT_CSV}")

if __name__ == "__main__":
    main()
