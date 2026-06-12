#!/usr/bin/env python3
"""Regression tests for reproducible synthesis/mask script preflight behavior."""
import os
import subprocess
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
BASH = Path("/usr/bin/bash")


class SynthesisScriptPreflightTest(unittest.TestCase):
    maxDiff = None

    def run_with_empty_path(self, script: str) -> subprocess.CompletedProcess:
        env = os.environ.copy()
        env["PATH"] = "/tmp/scanforge-no-tools"
        return subprocess.run(
            [str(BASH), str(REPO_ROOT / script)],
            cwd=Path("/tmp"),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
            timeout=10,
            check=False,
        )

    def assert_missing_tool_preflight(self, script: str, tool: str) -> None:
        proc = self.run_with_empty_path(script)
        combined = proc.stdout + proc.stderr
        self.assertNotEqual(proc.returncode, 0, combined)
        self.assertIn(f"ERROR: required tool '{tool}' not found in PATH", combined)
        self.assertIn("Install the missing tool or export PATH", combined)
        self.assertNotIn("command not found", combined)

    def test_synth_itc99_reports_missing_yosys_before_running(self):
        self.assert_missing_tool_preflight("scripts/synth_itc99.sh", "yosys")

    def test_gen_nonscan_masks_reports_missing_opensta_before_running(self):
        self.assert_missing_tool_preflight("scripts/gen_nonscan_masks.sh", "sta")


if __name__ == "__main__":
    unittest.main(verbosity=2)
