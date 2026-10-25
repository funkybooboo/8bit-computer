#!/usr/bin/env python3
"""
kicadnets.py - extract nets from a KiCad schematic netlist (.net) file.

Used as the reference side of wiring verification: Ben Eater's KiCad project
(8bit-computer.net, this directory) contains the netlist of the real build.
Print the nets for the components of one module and compare pin by pin
against what ../digital/dignetlist.py extracts from the matching Digital
.dig circuit.

Example - the output module chips (run from this directory):
  kicadnets.py --net 8bit-computer.net --refs U37,U38,U44,U45,U46
  kicadnets.py --net 8bit-computer.net --refs U40,U41,U42,U43   # displays

Pin number maps for the chips used in this project (standard pinouts, also
what Digital's DIL library uses):
  74LS273: ~MR=1 Q0=2 D0=3 D1=4 Q1=5 Q2=6 D2=7 D3=8 Q3=9 GND=10 CP=11 Q4=12
           D4=13 D5=14 Q5=15 Q6=16 D6=17 D7=18 Q7=19 VCC=20
  28C16:   A7..A0=1..8 I/O0=9 I/O1=10 I/O2=11 GND=12 I/O3=13 I/O4=14 I/O5=15
           I/O6=16 I/O7=17 ~CE=18 A10=19 ~OE=20 ~WE=21 A9=22 A8=23 VCC=24
  74LS76:  1~CLK=1 1~PRE=2 1~CLR=3 1J=4 VCC=5 2~CLK=6 2~PRE=7 2~CLR=8 2J=9
           2~Q=10 2Q=11 2K=12 GND=13 1~Q=14 1Q=15 1K=16
  74LS139: ~1G=1 1A=2 1B=3 ~1Y0=4 ~1Y1=5 ~1Y2=6 ~1Y3=7 GND=8 ~2Y3=9 ~2Y2=10
           ~2Y1=11 ~2Y0=12 2B=13 2A=14 ~2G=15 VCC=16
  74LS08:  1A=1 1B=2 1Y=3 2A=4 2B=5 2Y=6 GND=7 3Y=8 3A=9 3B=10 4Y=11 4A=12
           4B=13 VCC=14
"""

import argparse
import re


def tokenize(text):
    return re.findall(r'\(|\)|"[^"]*"|[^\s()]+', text)


def parse(tokens):
    pos = 0

    def rd():
        nonlocal pos
        t = tokens[pos]
        pos += 1
        if t == "(":
            lst = []
            while tokens[pos] != ")":
                lst.append(rd())
            pos += 1
            return lst
        return t

    return rd()


def walk(x):
    if isinstance(x, list):
        if x and x[0] == "net":
            yield x
        for i in x:
            yield from walk(i)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--net", required=True, help="KiCad .net file")
    ap.add_argument("--refs", help="comma separated component refs to include (e.g. U44,U45)")
    args = ap.parse_args()

    want = set(args.refs.split(",")) if args.refs else None
    tree = parse(tokenize(open(args.net, encoding="utf-8", errors="replace").read()))
    for net in walk(tree):
        name, nodes = None, []
        for sub in net[1:]:
            if isinstance(sub, list) and sub and sub[0] == "name":
                name = sub[1].strip('"')
            elif isinstance(sub, list) and sub and sub[0] == "node":
                nodes.append((sub[1][1], sub[2][1]))
        if want is None or any(r in want for r, _p in nodes):
            print("%-38s %s" % (name, sorted(nodes)))


if __name__ == "__main__":
    main()
