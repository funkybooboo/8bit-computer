#!/usr/bin/env python3
"""
test_tools.py - the browser toolchain against the repo's toolchain.

js/hlc.js and js/asm.js are ports of tools/compile.py and tools/asm.py;
this test is the port's proof of fidelity: every program in the gallery
is compiled and assembled by BOTH toolchains, and the generated .asm
text and the .bin image must match byte for byte. If they disagree, the
web app's "enter your own program" would build different machine code
than the repo's tools - a second opinion about the language, exactly
what the web build must not be.

Usage:
  python3 web/test/test_tools.py

Exit status: 0 iff every program matches on both axes.
"""

import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))  # the repo root
sys.path.insert(0, os.path.join(ROOT, "tools"))
import compile as hlc  # noqa: E402 - the .hl compiler (the reference)
import asm as asmpy   # noqa: E402 - the assembler (the reference)
from genroms import write_image  # noqa: E402 - image I/O


def main():
    src_dir = os.path.join(ROOT, "programs")
    names = sorted(f[:-3] for f in os.listdir(src_dir) if f.endswith(".hl"))
    print("test_tools: %d programs, the JS ports vs tools/ (asm text + image)"
          % len(names))
    failures = 0
    with tempfile.TemporaryDirectory() as js_dir, \
            tempfile.TemporaryDirectory() as py_dir:
        p = subprocess.run(
            ["node", os.path.join(HERE, "run_tools.mjs"), src_dir, js_dir],
            capture_output=True, text=True, check=False, cwd=ROOT,
        )
        if p.returncode != 0:
            print(p.stderr)
            sys.exit("test_tools: the JS toolchain failed on some program")

        for name in names:
            # the reference: what web/build.py serves and the repo builds
            expected_asm = hlc.compile_to_asm(
                os.path.join(src_dir, name + ".hl"), 16)
            asm_path = os.path.join(py_dir, name + ".asm")
            with open(asm_path, "w", encoding="utf-8") as fh:
                fh.write(expected_asm)
            mem, _rows = asmpy.assemble(asm_path, 16)
            write_image(os.path.join(py_dir, name + ".bin"), mem, "raw")

            ok = True
            for ext in (".asm", ".bin"):
                with open(os.path.join(py_dir, name + ext), "rb") as fh:
                    pyb = fh.read()
                with open(os.path.join(js_dir, name + ext), "rb") as fh:
                    jsb = fh.read()
                if pyb != jsb:
                    ok = False
                    print("  %-16s FAIL (%s differs: %d vs %d bytes)"
                          % (name, ext, len(pyb), len(jsb)))
            if ok:
                print("  %-16s PASS" % name)
            else:
                failures += 1

    if failures:
        print("test_tools: %d FAILURES" % failures)
        sys.exit(1)
    print("test_tools: the JS ports are byte-identical to the repo tools")


if __name__ == "__main__":
    main()
