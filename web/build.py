#!/usr/bin/env python3
"""
build.py - build the program images the web app serves.

The browser app's program picker fetches ../programs/<name>.bin; those
images are build artifacts (compiled from the .hl sources with the repo's
compiler, then assembled) and are gitignored, so a fresh clone has none
of them. This script builds all of them. Run it from anywhere; it is
idempotent. The generated .asm and .lst files are kept next to the .hl
sources (also gitignored): the .lst is the front-panel entry table -
the dipswitch bit groups for every address.

    python3 web/build.py

(the control ROM images are different: roms/*.hex are the machine's own
contents and are tracked - nothing to build there)
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "tools"))
import asm       # the assembler
import compile as hlc  # the .hl compiler


def main():
    out_dir = os.path.join(ROOT, "programs")
    names = sorted(f[:-3] for f in os.listdir(out_dir) if f.endswith(".hl"))
    for name in names:
        src = os.path.join(out_dir, name + ".hl")
        text = hlc.compile_to_asm(src, 16)
        asm_path = os.path.join(out_dir, name + ".asm")
        with open(asm_path, "w", encoding="utf-8") as fh:
            fh.write(text)
        mem, rows = asm.assemble(asm_path, 16)
        asm.write_image(os.path.join(out_dir, name + ".bin"), mem, "raw")
        used = sum(1 for _a, byte, _t in rows if byte is not None)
        with open(os.path.join(out_dir, name + ".lst"), "w", encoding="utf-8") as fh:
            fh.write(asm.format_listing(rows, used, 16))
    print("build: %d program images written to programs/*.bin (+ .lst entry tables)" % len(names))


if __name__ == "__main__":
    main()
