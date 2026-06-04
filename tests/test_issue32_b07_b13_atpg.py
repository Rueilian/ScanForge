#!/usr/bin/env python3
"""Regression smoke test for issue #32: b07/b13 ATPG must be reproducible."""
import subprocess
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
FAN_DIR = REPO_ROOT / "FAN_ATPG"
FAN_BIN = FAN_DIR / "bin" / "opt" / "fan"
SCRIPT_DIR = FAN_DIR / "script" / "fanScripts"


class Issue32B07B13AtpgSmokeTest(unittest.TestCase):
    maxDiff = None

    def require_fan_binary(self) -> None:
        if not FAN_BIN.exists():
            self.skipTest(f"FAN_ATPG binary not found; build FAN_ATPG first: {FAN_BIN}")

    def netlist_path(self, circuit: str) -> Path:
        netlist = FAN_DIR / "mod_netlist" / f"{circuit}.v"
        self.assertTrue(
            netlist.exists(),
            f"missing reproducible gate-level netlist for {circuit}: {netlist}",
        )
        return netlist

    def run_atpg(self, circuit: str, nonscan_ffs: list[str] | None = None) -> subprocess.CompletedProcess:
        self.require_fan_binary()
        self.netlist_path(circuit)
        nonscan_ffs = nonscan_ffs or []
        mode = "partial" if nonscan_ffs else "all_scan"
        script = SCRIPT_DIR / f"issue32_{circuit}_{mode}_smoke.script"
        lines = [
            "read_lib techlib/mod_nangate45.mdt",
            f"read_netlist mod_netlist/{circuit}.v",
        ]
        if nonscan_ffs:
            lines.append(f"set_nonscan_ff {' '.join(nonscan_ffs)}")
        lines.extend(
            [
                "build_circuit --frame 1",
                "set_fault_type saf",
                "add_fault --all",
                "set_static_compression off",
                "set_dynamic_compression off",
                "run_atpg",
                "exit",
            ]
        )
        script.write_text("\n".join(lines) + "\n")
        self.addCleanup(lambda: script.exists() and script.unlink())
        return subprocess.run(
            [str(FAN_BIN), "-f", str(script.relative_to(FAN_DIR))],
            cwd=FAN_DIR,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=30,
            check=False,
        )

    def assert_all_scan_atpg_passes(self, circuit: str) -> None:
        proc = self.run_atpg(circuit)
        self.assertEqual(
            proc.returncode,
            0,
            f"{circuit} ATPG exited with {proc.returncode}\nSTDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}",
        )
        self.assertNotIn("**ERROR", proc.stderr, proc.stdout + proc.stderr)
        self.assertIn("Finished reading netlist", proc.stdout)
        self.assertIn("Finished building circuit", proc.stdout)
        self.assertIn("Finished pattern generation", proc.stdout)

    def test_b07_all_scan_atpg_runs_without_crashing(self):
        self.assert_all_scan_atpg_passes("b07")

    def test_b13_all_scan_atpg_runs_without_crashing(self):
        self.assert_all_scan_atpg_passes("b13")

    def assert_x20_partial_scan_atpg_passes(self, circuit: str) -> None:
        mask_path = REPO_ROOT / "masks" / f"{circuit}_x20.mask"
        self.assertTrue(mask_path.exists(), f"missing non-scan mask: {mask_path}")
        nonscan = [line.strip() for line in mask_path.read_text().splitlines() if line.strip()]
        self.assertTrue(nonscan, f"empty mask: {mask_path}")
        proc = self.run_atpg(circuit, nonscan)
        self.assertEqual(
            proc.returncode,
            0,
            f"{circuit} partial-scan ATPG exited with {proc.returncode}\nSTDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}",
        )
        self.assertNotIn("**ERROR", proc.stderr, proc.stdout + proc.stderr)
        self.assertIn("Finished pattern generation", proc.stdout)

    def test_b07_x20_partial_scan_atpg_runs_without_crashing(self):
        self.assert_x20_partial_scan_atpg_passes("b07")

    def test_b13_x20_partial_scan_atpg_runs_without_crashing(self):
        self.assert_x20_partial_scan_atpg_passes("b13")


if __name__ == "__main__":
    unittest.main(verbosity=2)
