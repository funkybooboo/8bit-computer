#!/usr/bin/env python3
"""
verify.py - differential test: the web build against the golden model.

For every program in ../programs it runs the same control-ROM images on
both implementations - tools/sim.py (the golden model, Python) and
web/js/machine.js (the web build, via js/run.mjs under node) - and
requires identical OUT streams and identical halt status. The web build
is correct iff every program agrees; no other notion of correctness is
needed, because both sides run the real microcode.

Usage:
  python3 web/test/verify.py            # all programs
  python3 web/test/verify.py [--max-cycles N]

Exit status: 0 iff every program agrees.
"""

import argparse
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))   # the repo root
sys.path.insert(0, os.path.join(ROOT, "tools"))
import asm     # noqa: E402 - to build the image node runs
import machine # noqa: E402 - image I/O


def sim_reference(path, max_cycles):
    """Run tools/sim.py on the program; -> (stdout lines, halted)."""
    p = subprocess.run(
        [sys.executable, os.path.join(ROOT, "tools", "sim.py"), path,
         "--max-cycles", str(max_cycles)],
        capture_output=True, text=True, check=False,
    )
    return p.stdout.splitlines(), p.returncode == 0


def web_candidate(image_path, max_cycles):
    """Run js/machine.js on the program image via js/run.mjs; -> (stdout, halted)."""
    p = subprocess.run(
        ["node", os.path.join(HERE, "..", "js", "run.mjs"), image_path,
         "--rom1", os.path.join(ROOT, "roms", "control-rom1.hex"),
         "--rom2", os.path.join(ROOT, "roms", "control-rom2.hex"),
         "--max-cycles", str(max_cycles)],
        capture_output=True, text=True, check=False, cwd=ROOT,
    )
    return p.stdout.splitlines(), p.returncode == 0


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--max-cycles", type=int, default=100000)
    args = ap.parse_args()

    programs = sorted(
        f for f in os.listdir(os.path.join(ROOT, "programs")) if f.endswith(".asm")
    )
    failures = 0
    print("verify: %d programs, sim.py vs web/js/machine.js" % len(programs))
    for name in programs:
        path = os.path.join(ROOT, "programs", name)
        mem, _rows = asm.assemble(path, 16)  # the image node runs
        with tempfile.NamedTemporaryFile(
                "w", suffix=".hex", delete=False, encoding="utf-8") as fh:
            machine.write_image(fh.name, mem, "logisim")
            image_path = fh.name
        try:
            ref_lines, ref_halt = sim_reference(path, args.max_cycles)
            web_lines, web_halt = web_candidate(image_path, args.max_cycles)
        finally:
            os.unlink(image_path)

        ok = ref_lines == web_lines and ref_halt == web_halt
        status = "PASS" if ok else "FAIL"
        print("  %-16s %s (%d OUTs%s)"
              % (name, status, len(ref_lines),
                 "" if ref_halt else ", no halt"))
        if not ok:
            failures += 1
            print("    sim.py: %r" % (ref_lines[:8],))
            print("    web:    %r" % (web_lines[:8],))
            if ref_halt != web_halt:
                print("    halt differs: sim=%s web=%s" % (ref_halt, web_halt))

    if failures:
        print("verify: %d FAILURES" % failures)
        sys.exit(1)
    print("verify: web implementation agrees with sim.py on every program")


if __name__ == "__main__":
    main()
