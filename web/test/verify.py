#!/usr/bin/env python3
"""
verify.py - run every program on the web build and check it against the
expected outputs.

Correctness of an implementation is defined by the corpus: the table
below records, for every program in ../../programs/, the halt status, the
total OUT count within the cap, and the first 32 OUT values. Any build of
the machine that deviates in any of these fails. The OUT sequences were
frozen from the 2026-10-24 simulator/web agreement; the counts were
re-frozen at the 2026-10-27 .hl migration (the compiler's loops cost a
different number of cycles per OUT than the hand-written ones - same
values, same order - so the cap admits a different number of them; the
sequences themselves are byte-for-byte unchanged, verified by comparing
every .hl against its .asm predecessor before the .asm sources were
retired). Update the table only deliberately, when a program's intended
behavior changes.

Usage:
  python3 web/test/verify.py

Exit status: 0 iff every program matches.
"""

import os
import re
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))  # the repo root
sys.path.insert(0, os.path.join(ROOT, "tools"))
import asm      # noqa: E402 - to build the image node runs
import compile as hlc  # noqa: E402 - the .hl compiler
from genroms import write_image  # noqa: E402 - image I/O

CAP = 20000  # the cycle cap the expectations were frozen with

# program -> (halted, total OUTs within CAP, first 32 OUT values)
EXPECTED = {
    "absdiff": (True, 1, [5]),
    "bits": (False, 303, [1, 0, 1, 1, 0, 1, 0, 1, 1, 0, 1, 1, 0, 1, 0, 1, 1, 0, 1, 1, 0, 1, 0, 1, 1, 0, 1, 1, 0, 1, 0, 1]),
    "bothflags": (True, 2, [255, 0]),
    "count": (False, 500, [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31]),
    "countdown": (True, 256, [255, 254, 253, 252, 251, 250, 249, 248, 247, 246, 245, 244, 243, 242, 241, 240, 239, 238, 237, 236, 235, 234, 233, 232, 231, 230, 229, 228, 227, 226, 225, 224]),
    "decrement": (True, 11, [10, 9, 8, 7, 6, 5, 4, 3, 2, 1, 0]),
    "div": (True, 12, [91, 82, 73, 64, 55, 46, 37, 28, 19, 10, 1, 11]),
    "fib": (False, 278, [0, 1, 1, 2, 3, 5, 8, 13, 21, 34, 55, 89, 144, 233, 121, 98, 219, 61, 24, 85, 109, 194, 47, 241, 32, 17, 49, 66, 115, 181, 40, 221]),
    "gcd": (True, 1, [21]),
    "half": (True, 1, [11]),
    "larger": (True, 1, [14]),
    "lcg": (False, 277, [6, 31, 156, 13, 66, 75, 120, 89, 190, 183, 148, 229, 122, 99, 240, 177, 118, 79, 140, 189, 178, 123, 104, 9, 46, 231, 132, 149, 234, 147, 224, 97]),
    "memory": (False, 500, [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31]),
    "min": (True, 1, [10]),
    "mod": (True, 1, [1]),
    "mul": (True, 6, [7, 14, 21, 28, 35, 42]),
    "odometer": (False, 356, [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31]),
    "overflow": (True, 5, [0, 60, 120, 180, 240]),
    "patch": (False, 834, [7, 9, 9, 9, 9, 9, 9, 9, 9, 9, 9, 9, 9, 9, 9, 9, 9, 9, 9, 9, 9, 9, 9, 9, 9, 9, 9, 9, 9, 9, 9, 9]),
    "powers": (True, 8, [1, 2, 4, 8, 16, 32, 64, 128]),
    "rol": (False, 370, [22, 44, 88, 176, 97, 194, 133, 11, 22, 44, 88, 176, 97, 194, 133, 11, 22, 44, 88, 176, 97, 194, 133, 11, 22, 44, 88, 176, 97, 194, 133, 11]),
    "rotate": (False, 400, [2, 4, 8, 16, 32, 64, 128, 1, 2, 4, 8, 16, 32, 64, 128, 1, 2, 4, 8, 16, 32, 64, 128, 1, 2, 4, 8, 16, 32, 64, 128, 1]),
    "squares": (False, 313, [1, 4, 9, 16, 25, 36, 49, 64, 81, 100, 121, 144, 169, 196, 225, 0, 33, 68, 105, 144, 185, 228, 17, 64, 113, 164, 217, 16, 73, 132, 193, 0]),
    "step": (False, 500, [0, 3, 6, 9, 12, 15, 18, 21, 24, 27, 30, 33, 36, 39, 42, 45, 48, 51, 54, 57, 60, 63, 66, 69, 72, 75, 78, 81, 84, 87, 90, 93]),
    "triple": (False, 416, [3, 9, 27, 81, 243, 217, 139, 161, 227, 169, 251, 241, 211, 121, 107, 65, 195, 73, 219, 145, 179, 25, 75, 225, 163, 233, 187, 49, 147, 185, 43, 129]),
}


def run_web(image_path):
    """Run js/machine.js on the program image via js/run.mjs."""
    p = subprocess.run(
        ["node", os.path.join(HERE, "..", "js", "run.mjs"), image_path,
         "--rom1", os.path.join(ROOT, "roms", "control-rom1.hex"),
         "--rom2", os.path.join(ROOT, "roms", "control-rom2.hex"),
         "--max-cycles", str(CAP)],
        capture_output=True, text=True, check=False, cwd=ROOT,
    )
    values = [int(m) for m in re.findall(r"^\s*(\d+)\s", p.stdout, re.M)]
    return p.returncode == 0, values


def main():
    failures = 0
    print("verify: %d programs, web/js/machine.js vs the expected outputs" % len(EXPECTED))
    for name in sorted(EXPECTED):
        exp_halt, exp_count, exp_head = EXPECTED[name]
        text = hlc.compile_to_asm(os.path.join(ROOT, "programs", name + ".hl"), 16)
        with tempfile.NamedTemporaryFile(
                "w", suffix=".asm", delete=False, encoding="utf-8") as fh:
            fh.write(text)
            asm_path = fh.name
        try:
            mem, _rows = asm.assemble(asm_path, 16)
        finally:
            os.unlink(asm_path)
        with tempfile.NamedTemporaryFile(
                "w", suffix=".bin", delete=False, encoding="utf-8") as fh:
            write_image(fh.name, mem, "bin")
            image_path = fh.name
        try:
            got_halt, got_values = run_web(image_path)
        finally:
            os.unlink(image_path)

        ok = (exp_halt == got_halt and exp_count == len(got_values)
              and exp_head == got_values[:len(exp_head)])
        print("  %-16s %s (%d OUTs, %s)"
              % (name, "PASS" if ok else "FAIL", exp_count,
                 "halts" if exp_halt else "cap"))
        if not ok:
            failures += 1
            print("    expected: halt=%s count=%d head=%r"
                  % (exp_halt, exp_count, exp_head[:8]))
            print("    got:      halt=%s count=%d head=%r"
                  % (got_halt, len(got_values), got_values[:8]))

    if failures:
        print("verify: %d FAILURES" % failures)
        sys.exit(1)
    print("verify: the web build reproduces every expected output")


if __name__ == "__main__":
    main()
