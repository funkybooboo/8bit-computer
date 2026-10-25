#!/usr/bin/env python3
"""
build.py - build the program images the web app serves.

The browser app's program picker fetches ../programs/<name>.hex; those
images are build artifacts (assembled from the .asm sources with the
repo's assembler) and are gitignored, so a fresh clone has none of them.
This script builds all of them. Run it from anywhere; it is idempotent.

    python3 web/build.py

(the control ROM images are different: roms/*.hex are the machine's own
contents and are tracked - nothing to build there)
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "tools"))
import asm      # the assembler
from microcode import write_image  # image I/O


def main():
    out_dir = os.path.join(ROOT, "programs")
    names = sorted(f[:-4] for f in os.listdir(out_dir) if f.endswith(".asm"))
    for name in names:
        src = os.path.join(out_dir, name + ".asm")
        mem, _rows = asm.assemble(src, 16)
        dst = os.path.join(out_dir, name + ".hex")
        write_image(dst, mem, "logisim")
    print("build: %d program images written to programs/*.hex" % len(names))


if __name__ == "__main__":
    main()
