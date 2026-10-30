#!/usr/bin/env python3
"""
build.py - write the gallery's build artifacts next to their sources.

For every programs/<name>.hl this writes <name>.asm, <name>.lst (the
front-panel entry table - the dipswitch bit groups for every address)
and <name>.bin (the bare machine image), all gitignored artifacts.
These are for local work: inspection, manual entry from the .lst (the
web app's only way to load a program - see web/README.md, "Entering a
program: the switches"), and the headless runner (js/run.mjs takes an
image path). Run it from anywhere; it is idempotent.

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
