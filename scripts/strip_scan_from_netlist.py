#!/usr/bin/env python3
"""Remove scan insertion from a fixup --scan netlist (SDFFR -> DFFR)."""
import re
import sys

def strip(src: str) -> str:
    src = src.replace(', test_si, test_so, test_se', '')
    src = re.sub(r'^  input test_si;\n  input test_se;\n  output test_so;\n', '', src, flags=re.M)
    src = re.sub(r'^  input test_si;\n  wire test_si;\n  input test_se;\n  wire test_se;\n  output test_so;\n  wire test_so;\n', '', src, flags=re.M)
    src = re.sub(r'^  assign test_so = [^;]+;\n', '', src, flags=re.M)
    src = src.replace('SDFFR_X1', 'DFFR_X1').replace('SDFFS_X1', 'DFFS_X1').replace('SDFFRS_X1', 'DFFRS_X1')
    src = re.sub(r',\s*\n\s*\.SE\(test_se\),\s*\n\s*\.SI\([^)]+\)\s*\n', '\n', src)
    return src

if __name__ == '__main__':
    inp, outp = sys.argv[1], sys.argv[2]
    with open(inp) as f:
        out = strip(f.read())
    with open(outp, 'w') as f:
        f.write(out)
