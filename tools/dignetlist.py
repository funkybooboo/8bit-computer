#!/usr/bin/env python3
"""
dignetlist.py - extract the netlist from a Digital .dig circuit and sanity check it.

How pins are located (verified against Digital 0.31 source, DILShape.java /
SevenSegShape.java / GenericShape.java):
  - In, Out, Clock, Ground, VDD, NotConnected: a single pin at the element pos.
    In/Clock also carry a Label.
  - DIL chips (custom circuits such as 28c16.dig, 74139.dig, ...): pin pitch
    is 40 px. Left column holds pins 1..N/2 top-down at (x, y + 40*(p-1));
    right column holds pins N/2+1..N counted bottom-up, i.e. pin p sits at
    (x + 20*(Width+1), y + 40*(N-p)). N (pin count) and the pinNumber->name
    mapping come from the chip's own .dig file in Digital's library.
  - Seven-Seg: a-d on the top edge at rel (0,20,40,60 / 0); e,f,g,dp on the
    bottom edge at rel (0,20,40,60 / 140); cc (common cathode) or ca (common
    anode) at rel (80,140) when a common connection attribute is set.
    Common cathode enables a digit while cc is LOW; common anode enables
    while ca is HIGH (segments active low in that case).

Wires connect ONLY at shared endpoints (Digital's Net.tryMerge/Net.contains
logic). A wire endpoint touching the middle of another wire is NOT connected;
such T-junctions are reported as warnings because the GUI editor normally
splits them automatically when you draw them - a raw one is suspicious.

Multiple Ground / VDD symbols are separate nets electrically, but every one
drives the same constant; they are reported as GND/VDD sources.

Usage:
  dignetlist.py --dig "digital/Output Register.dig" [--lib LIBDIR] [--quiet]

The Digital library directory is found via --lib, $DIGITAL_LIB, the `digital`
executable's wrapper script (nix), or /nix/store/*digital*/share/java/lib.

Workflow used for this project: dump this netlist, extract the reference
netlist for the same module from Ben Eater's KiCad netlist (kicadnets.py),
and compare pin by pin - that verified the Output Register wiring exactly.
"""

import argparse
import glob
import os
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from collections import defaultdict

PITCH = 40          # px between DIL pins
SEG_H = 140         # Seven-Seg height to bottom pin row

_lib_cache = {}


def find_library(explicit=None):
    cands = []
    if explicit:
        cands.append(explicit)
    if os.environ.get("DIGITAL_LIB"):
        cands.append(os.environ["DIGITAL_LIB"])
    exe = shutil_which_digital()
    if exe:
        try:
            w = subprocess.run(["readlink", "-f", exe], capture_output=True, text=True).stdout.strip()
            m = re.search(r'([^ "\']*Digital\.jar)', open(w).read())
            if m:
                cands.append(os.path.join(os.path.dirname(m.group(1)), "lib"))
        except Exception:
            pass
    cands.extend(glob.glob("/nix/store/*digital*/share/java/lib"))
    for c in cands:
        if c and os.path.isdir(c):
            return c
    raise SystemExit(
        "dignetlist: Digital library dir not found; use --lib or $DIGITAL_LIB\n"
        "(it is the directory containing 'DIL Chips/', next to Digital.jar)"
    )


def shutil_which_digital():
    for d in os.environ.get("PATH", "").split(os.pathsep):
        p = os.path.join(d, "digital")
        if os.access(p, os.X_OK):
            return p
    return None


def load_lib_chip(libdir, name):
    """Parse a library .dig chip: return (pinCount, widthUnits, {pinNum: pinName})."""
    if name in _lib_cache:
        return _lib_cache[name]
    path = None
    for cand in glob.glob(os.path.join(libdir, "**", name), recursive=True):
        path = cand
        break
    if path is None:
        raise SystemExit("dignetlist: library chip %r not found under %s" % (name, libdir))
    root = ET.parse(path).getroot()
    width, pins = 5, {}
    for e in root.find("attributes"):
        if e.find("string").text == "Width":
            width = int(list(e)[1].text)
    for ve in root.find("visualElements"):
        if ve.find("elementName").text not in ("In", "Out"):
            continue
        attrs = {}
        ae = ve.find("elementAttributes")
        if ae is not None:
            for e in ae:
                attrs[e.find("string").text] = list(e)[1].text
        num = attrs.get("pinNumber")
        if num:
            pins[int(num)] = attrs.get("Label", "?")
    n = max(pins) if pins else 0
    if n % 2:
        n += 1
    _lib_cache[name] = (n, width, pins)
    return _lib_cache[name]


def dil_pin_pos(x, y, npins, width_units, pinnum):
    """Absolute position of DIL pin `pinnum` on a chip placed at (x, y)."""
    if pinnum <= npins // 2:
        return (x, y + PITCH * (pinnum - 1))
    return (x + 20 * (width_units + 1), y + PITCH * (npins - pinnum))


def element_pins(el, libdir):
    """Yield (pinName, absPos, direction) for one visual element."""
    name, x, y, attrs = el["name"], el["x"], el["y"], el["attrs"]
    if name.endswith(".dig"):
        npins, width, pins = load_lib_chip(libdir, name)
        for num, label in sorted(pins.items()):
            yield label, dil_pin_pos(x, y, npins, width, num), "io"
        return
    if name == "Seven-Seg":
        common = "cc" if attrs.get("commonCathode") == "true" else ("ca" if attrs.get("commonAnode") == "true" else None)
        top = ["a", "b", "c", "d"]
        bottom = ["e", "f", "g", "dp"]
        for i, s in enumerate(top):
            yield s, (x + 20 * i, y), "in"
        for i, s in enumerate(bottom):
            yield s, (x + 20 * i, y + SEG_H), "in"
        if common:
            yield common, (x + 80, y + SEG_H), "in"
        return
    if name in ("In", "Out", "Clock", "Ground", "VDD", "NotConnected", "Tunnel"):
        yield name, (x, y), "io"
        return
    # Unknown element: assume a pin at pos so it still shows up in the report.
    yield "?", (x, y), "io"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dig", required=True)
    ap.add_argument("--lib")
    ap.add_argument("--quiet", action="store_true", help="hide warnings")
    args = ap.parse_args()
    libdir = find_library(args.lib)

    root = ET.parse(args.dig).getroot()
    els = []
    for i, ve in enumerate(root.find("visualElements")):
        name = ve.find("elementName").text
        attrs = {}
        ae = ve.find("elementAttributes")
        if ae is not None:
            for e in ae:
                attrs[e.find("string").text] = list(e)[1].text
        p = ve.find("pos")
        els.append({"idx": i, "name": name, "x": int(p.get("x")), "y": int(p.get("y")), "attrs": attrs})
    wires = []
    for w in root.find("wires"):
        wires.append(
            (
                (int(w[0].get("x")), int(w[0].get("y"))),
                (int(w[1].get("x")), int(w[1].get("y"))),
            )
        )

    # ---- connectivity: shared endpoints only (Digital semantics)
    parent = {}

    def find(a):
        parent.setdefault(a, a)
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    for a, b in wires:
        union(a, b)

    # ---- T-junction warnings (NOT connections in Digital)
    def on_interior(p, a, b):
        (x, y), (x1, y1), (x2, y2) = p, a, b
        if p in (a, b):
            return False
        if x1 == x2:
            return x == x1 and min(y1, y2) < y < max(y1, y2)
        if y1 == y2:
            return y == y1 and min(x1, x2) < x < max(x1, x2)
        return False

    if not args.quiet:
        for a, b in wires:
            for p in (a, b):
                for a2, b2 in wires:
                    if (a2, b2) == (a, b):
                        continue
                    if on_interior(p, a2, b2):
                        print(
                            "WARNING: T-junction at %s: wire %s-%s ends on the middle of %s-%s "
                            "(NOT connected in Digital - check in the GUI)" % (p, a, b, a2, b2),
                            file=sys.stderr,
                        )

    # ---- pin -> net membership
    members = defaultdict(list)  # net-root -> [(elementLabel, pinName)]
    label_of = {}
    for el in els:
        lbl = el["attrs"].get("Label") or el["name"]
        if el["name"] == "Seven-Seg":
            lbl = "SEG@%d" % el["x"]
        if el["name"] in ("Ground", "VDD", "NotConnected"):
            lbl = el["name"]
        label_of[el["idx"]] = lbl
        for pinname, pos, _d in element_pins(el, libdir):
            members[find(pos) if pos in parent else pos].append((el["idx"], lbl, pinname))

    # element index for stable ordering
    for el in els:
        print("=== %s (%s) at (%d,%d)" % (label_of[el["idx"]], el["name"], el["x"], el["y"]))
        for pinname, pos, _d in element_pins(el, libdir):
            r = find(pos) if pos in parent else pos
            mem = ["%s.%s" % (l, pn) for i, l, pn in members.get(r, [])]
            uniq = sorted(set(mem))
            if len(uniq) == 1 and uniq[0] == "%s.%s" % (label_of[el["idx"]], pinname):
                note = "  <-- UNCONNECTED" if el["name"].endswith(".dig") else ""
                print("   %-8s -> (alone)%s" % (pinname, note))
            else:
                print("   %-8s -> %s" % (pinname, uniq))


if __name__ == "__main__":
    main()
