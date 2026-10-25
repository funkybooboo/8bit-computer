#!/usr/bin/env python3
"""
netlist.py - extract the netlist from a Digital .dig circuit and sanity check it.

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
  netlist.py --dig digital/Computer.dig [--lib LIBDIR] [--quiet]

The Digital library directory is found via --lib, $DIGITAL_LIB, the `digital`
executable's wrapper script (nix), or /nix/store/*digital*/share/java/lib.

Workflow: dump this netlist, extract the reference netlist from Ben Eater's
KiCad netlist (../kicad/netlist.py), and compare pin by pin - that is the
wiring verification of Computer.dig against 8bit-computer.net.
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
        "netlist: Digital library dir not found; use --lib or $DIGITAL_LIB\n"
        "(it is the directory containing 'DIL Chips/', next to Digital.jar)"
    )


def shutil_which_digital():
    for d in os.environ.get("PATH", "").split(os.pathsep):
        p = os.path.join(d, "digital")
        if os.access(p, os.X_OK):
            return p
    return None


def rotation_of(ve, idx, rots, root_vis):
    """Rotation value of visual element `idx`, resolving XStream references
    (<rotation reference="..."/>) which point at another element's entry."""
    if idx in rots:
        return rots[idx]
    ae = ve.find("elementAttributes")
    val = 0
    if ae is not None:
        for e in ae:
            if e.find("string").text == "rotation":
                v = list(e)[1]
                ref = v.get("reference")
                if ref is not None:
                    m = re.search(r"visualElement\[(\d+)\]", ref)
                    if m:
                        target = int(m.group(1)) - 1
                        val = rotation_of(root_vis[target], target, rots, root_vis)
                elif v.get("rotation") is not None:
                    val = int(v.get("rotation"))
                break
    rots[idx] = val
    return val


def load_lib_chip(libdir, name):
    """Parse a library .dig chip: return (pinCount, widthUnits, {pinNum: pinName})."""
    if name in _lib_cache:
        return _lib_cache[name]
    path = None
    for cand in glob.glob(os.path.join(libdir, "**", name), recursive=True):
        path = cand
        break
    if path is None:
        raise SystemExit("netlist: library chip %r not found under %s" % (name, libdir))
    root = ET.parse(path).getroot()
    width, pins = 5, {}
    for e in root.find("attributes"):
        if e.find("string").text == "Width":
            width = int(list(e)[1].text)
    for ve in root.find("visualElements"):
        # "Clock" elements inside a chip definition are its clock input pin
        # (e.g. 74161.dig: Label "CLK", pinNumber 2) - they carry a pinNumber
        # like In/Out elements do.
        if ve.find("elementName").text not in ("In", "Out", "Clock"):
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
    """Unrotated position of DIL pin `pinnum` on a chip placed at (x, y)."""
    if pinnum <= npins // 2:
        return (x, y + PITCH * (pinnum - 1))
    return (x + 20 * (width_units + 1), y + PITCH * (npins - pinnum))


def rot_pos(x, y, dx, dy, r):
    """Apply Digital's element rotation (r quarter turns) to an unrotated
    offset (dx, dy) relative to an element at (x, y).

    Matches Digital's VisualElement.getTransform() -> TransformRotate(pos, r):
    rot=1: (x+dy, y-dx)   rot=2: (x-dx, y-dy)   rot=3: (x-dy, y+dx)
    """
    if r == 1:
        return (x + dy, y - dx)
    if r == 2:
        return (x - dx, y - dy)
    if r == 3:
        return (x - dy, y + dx)
    return (x + dx, y + dy)


def element_pins(el, libdir):
    """Yield (pinName, absPos, direction) for one visual element."""
    name, x, y, attrs = el["name"], el["x"], el["y"], el["attrs"]
    r = int(attrs.get("rotation", 0))
    if name.endswith(".dig"):
        npins, width, pins = load_lib_chip(libdir, name)
        for num, label in sorted(pins.items()):
            dx, dy = dil_pin_pos(0, 0, npins, width, num)
            yield label, rot_pos(x, y, dx, dy, r), "io"
        return
    if name == "Seven-Seg":
        common = "cc" if attrs.get("commonCathode") == "true" else ("ca" if attrs.get("commonAnode") == "true" else None)
        top = ["a", "b", "c", "d"]
        bottom = ["e", "f", "g", "dp"]
        offs = [(20 * i, 0) for i in range(4)] + [(20 * i, SEG_H) for i in range(4)]
        names = top + bottom
        for (dx, dy), s in zip(offs, names):
            yield s, rot_pos(x, y, dx, dy, r), "in"
        if common:
            yield common, rot_pos(x, y, 80, SEG_H, r), "in"
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
    root_vis = root.find("visualElements")
    rots = {}
    els = []
    for i, ve in enumerate(root.find("visualElements")):
        name = ve.find("elementName").text
        attrs = {}
        ae = ve.find("elementAttributes")
        if ae is not None:
            for e in ae:
                v = list(e)[1]
                # non-string values (e.g. <rotation rotation="1"/>) carry no text
                attrs[e.find("string").text] = v.get("rotation") if v.get("rotation") is not None else v.text
        attrs["rotation"] = rotation_of(ve, i, rots, root_vis)
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
