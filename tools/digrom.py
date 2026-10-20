#!/usr/bin/env python3
"""
digrom.py - read, write and export EEPROM (ROM) data of Digital .dig circuits.

Digital (https://github.com/hneemann/Digital) stores the ROM content of an
embedded DIL chip (e.g. 28c16.dig) at the CIRCUIT level, in <attributes> under
the key "romContent", keyed by the chip instance's Label:

    <attributes>
      <entry>
        <string>romContent</string>
        <romList>
          <roms>
            <entry>
              <string>U45</string>
              <romData>
                <dataField>7e,30,6d,16*0</dataField>
              </romData>
            </entry>
          </roms>
        </romList>
      </entry>
    </attributes>

The dataField value is a comma separated list of tokens: a single hex byte
("7e") or a run length ("16*0" = 16 times 0x00). Addresses past the last token
read as 0x00. This is Digital's own DataFieldConverter format; Digital 0.31
round-trips it unchanged (verified: write via this tool, open + re-save in the
Digital GUI, data survives).

The old pre-0.31 "storedRoms" format is understood when reading but is written
as romList, because current Digital fails to build a model from the old format.

Commands:
  dump      Read and print ROM data stored in a .dig circuit.
  write     Write ROM data into a .dig circuit (preset, hex/binary file, or
            literal dataField tokens). Surgical text edit + round-trip check,
            atomic replace.
  export    Write a preset's (or a .dig's) ROM image to a file: logisim .hex,
            Intel HEX, or raw binary - for the Digital ROM editor's "load from
            file" option or for burning real EEPROMs.
  presets   List the built-in data presets.

Examples:
  digrom.py dump --dig "digital/Output Register.dig" --label U45 --words
  digrom.py write --dig "digital/Output Register.dig" --label U45 --preset output-display
  digrom.py write --dig c.dig --label U1 --hex myrom.hex --size 2048
  digrom.py export --preset output-display --out display.hex --format logisim

Preset notes live in the PRESETS dict below - add new presets there (e.g. the
control-logic microcode ROMs when that module gets built).
"""

import argparse
import os
import re
import sys
import tempfile
import xml.etree.ElementTree as ET

# ---------------------------------------------------------------------------
# Segment encoding used by Ben Eater's display EEPROMs (verified against his
# KiCad netlist: ROM I/O0->g, I/O1->f, I/O2->e, I/O3->d, I/O4->c, I/O5->b,
# I/O6->a, I/O7->dp):
#
#   ROM bit:  7    6   5   4   3   2   1   0
#   segment: dp    a   b   c   d   e   f   g
# ---------------------------------------------------------------------------
SEG_DIGITS = [0x7e, 0x30, 0x6d, 0x79, 0x33, 0x5b, 0x5f, 0x70, 0x7f, 0x7b]
SEG_HEX = SEG_DIGITS + [0x77, 0x1f, 0x4e, 0x3d, 0x4f, 0x47]  # A b C d E F
SEG_BLANK = 0x00


def output_display(swap_banks=False):
    """Ben Eater output module: 4-digit multiplexed decimal/hex display ROM.

    28C16 (2 KiB). Address = A10*1024 + A9*512 + A8*256 + value, where A8/A9
    are the 7476 mux-counter outputs that also drive the 74139 select inputs,
    so ROM page p lights the digit whose common cathode ~1Yp pulls low:
      page 0 = ones digit (rightmost display), 1 = tens, 2 = hundreds,
      3 = thousands (always blank for 8-bit values).
    A10 is the front-panel mode switch: by default A10=1 -> decimal,
    A10=0 -> hexadecimal; leading zeros blanked in both modes.
    Pass swap_banks=True to swap which switch position gives which mode.
    """
    rom = [0] * 2048
    dec_bank, hex_bank = (1024, 0) if not swap_banks else (0, 1024)
    for v in range(256):
        rom[dec_bank + 0 * 256 + v] = SEG_DIGITS[v % 10]
        rom[dec_bank + 1 * 256 + v] = SEG_DIGITS[(v // 10) % 10] if v >= 10 else SEG_BLANK
        rom[dec_bank + 2 * 256 + v] = SEG_DIGITS[(v // 100) % 10] if v >= 100 else SEG_BLANK
        rom[dec_bank + 3 * 256 + v] = SEG_BLANK
        rom[hex_bank + 0 * 256 + v] = SEG_HEX[v & 0xf]
        rom[hex_bank + 1 * 256 + v] = SEG_HEX[v >> 4] if v >= 16 else SEG_BLANK
        rom[hex_bank + 2 * 256 + v] = SEG_BLANK
        rom[hex_bank + 3 * 256 + v] = SEG_BLANK
    return bytes(rom)


# ---------------------------------------------------------------------------
# Control-logic microcode (Ben Eater's 16-bit control word split across two
# 28C16s, U47 + U52). Bit weights verified against the KiCad netlist (ROM
# data pins -> U49/U53 inverter gates -> control nets):
#
#   ROM1 U47: bit 7=HLT 6=MI 5=RI 4=RO 3=IO 2=II 1=AI 0=AO
#   ROM2 U52: bit 7=EO 6=SU 5=BI 4=OI 3=CE 2=CO 1=J  0=FI
#
# Address, both ROMs: step counter (74161 Q0/Q1/Q2) -> A0-A2, IR4..IR7
# (opcode) -> A3-A6, CF -> A8, ZF -> A9. A10 is grounded. A7 is the
# "which ROM" bit on Ben's board (U47 A7=GND, U52 A7=VCC), so the images
# are replicated across A7 and A10 and are correct for any A7 wiring
# (the Digital build ties both A7 pins to VDD).
#
# Instruction set (opcode = IR nibble):
#   0 NOP   1 LDA   2 ADD   3 SUB   4 STA   5 LDI   6 JMP   7 JC
#   8 JZ    9 JNC   A JNZ   B ADDI  C SUBI  D DBL   E OUT   F HLT
#
# Microcode (T0/T1 fetch identical for all instructions; every instruction
# takes 8 cycles because the 74138 O7/T7 line resets the step counter):
#   T0: MI|CO          T1: RO|II|CE
#   LDA : T2 MI|IO            T3 RO|AI
#   ADD : T2 MI|IO            T3 RO|BI          T4 EO|AI|FI
#   SUB : T2 MI|IO            T3 RO|BI          T4 EO|AI|SU|FI
#   STA : T2 MI|IO            T3 AO|RI
#   LDI : T2 IO|AI
#   JMP : T2 IO|J
#   JC  : T2 IO|J (only if CF=1)
#   JZ  : T2 IO|J (only if ZF=1)
#   JNC : T2 IO|J (only if CF=0)
#   JNZ : T2 IO|J (only if ZF=0)
#   ADDI: T2 IO|BI            T3 EO|AI|FI       (immediate operand)
#   SUBI: T2 IO|BI            T3 EO|AI|SU|FI   (immediate operand)
#   DBL : T2 AO|BI            T3 EO|AI|FI       (A <- 2*A: shift left, CF = bit out)
#   OUT : T2 AO|OI
#   HLT : T2 HLT
# The ROM1 image was verified instruction by instruction against the
# 8bitsim reference (ngdrascal/8bitsim memory-images/MicroInstructions.hex);
# opcodes 9-D are this project's additions (see ../docs/ideas.md tier 1) and
# are verified by tools/sim.py against the program gallery.
# ---------------------------------------------------------------------------

# ROM1 (U47) signal bits
HLT, MI, RI, RO, IO, II, AI, AO = 0x80, 0x40, 0x20, 0x10, 0x08, 0x04, 0x02, 0x01
# ROM2 (U52) signal bits
EO, SU, BI, OI, CE, CO, J, FI = 0x80, 0x40, 0x20, 0x10, 0x08, 0x04, 0x02, 0x01

# opcode -> list of (step, rom1 signals, rom2 signals); the T0/T1 fetch is
# added by _control_images() for every opcode. JNC/JNZ are appended there
# too (like JC/JZ) because they depend on the flag state.
_OPCODE_MICROCODE = {
    0x1: [(2, MI | IO, 0), (3, RO | AI, 0)],                                # LDA
    0x2: [(2, MI | IO, 0), (3, RO, BI), (4, AI, EO | FI)],                  # ADD
    0x3: [(2, MI | IO, 0), (3, RO, BI), (4, AI, EO | SU | FI)],            # SUB
    0x4: [(2, MI | IO, 0), (3, RI | AO, 0)],                                # STA
    0x5: [(2, IO | AI, 0)],                                                 # LDI
    0x6: [(2, IO, J)],                                                      # JMP
    0xB: [(2, IO, BI), (3, AI, EO | FI)],                                  # ADDI imm
    0xC: [(2, IO, BI), (3, AI, EO | SU | FI)],                             # SUBI imm
    0xD: [(2, AO, BI), (3, AI, EO | FI)],                                   # DBL
    0xE: [(2, AO, OI)],                                                     # OUT
    0xF: [(2, HLT, 0)],                                                     # HLT
}


def _control_images():
    """Returns (rom1, rom2) as 2048-byte images for U47/U52."""
    r1 = bytearray(2048)
    r2 = bytearray(2048)
    for opcode in range(16):
        for cf in (0, 1):
            for zf in (0, 1):
                microsteps = [(0, MI, CO), (1, RO | II, CE)]
                microsteps += _OPCODE_MICROCODE.get(opcode, [])
                if opcode == 0x7 and cf:  # JC: jump only when CF (A8) set
                    microsteps.append((2, IO, J))
                if opcode == 0x8 and zf:  # JZ: jump only when ZF (A9) set
                    microsteps.append((2, IO, J))
                if opcode == 0x9 and not cf:   # JNC: jump only when CF (A8) clear
                    microsteps.append((2, IO, J))
                if opcode == 0xA and not zf:   # JNZ: jump only when ZF (A9) clear
                    microsteps.append((2, IO, J))
                for st, w1, w2 in microsteps:
                    # replicate across A7 (the which-ROM bit) and A10 (grounded)
                    for a7 in (0, 1):
                        for a10 in (0, 1):
                            a = (st | (opcode << 3) | (a7 << 7)
                                 | (cf << 8) | (zf << 9) | (a10 << 10))
                            r1[a] = w1
                            r2[a] = w2
    return bytes(r1), bytes(r2)


def control_rom1(**_kw):
    """U47: HLT/MI/RI/RO/IO/II/AI/AO half of the control word."""
    return _control_images()[0]


def control_rom2(**_kw):
    """U52: EO/SU/BI/OI/CE/CO/J/FI half of the control word."""
    return _control_images()[1]


PRESETS = {
    "output-display": output_display,
    "control-rom1": control_rom1,
    "control-rom2": control_rom2,
}


# ---------------------------------------------------------------------------
# dataField token format (Digital's DataFieldConverter)
# ---------------------------------------------------------------------------

def encode_tokens(data):
    """bytes -> dataField token string with run-length compression."""
    toks = []
    i = 0
    while i < len(data):
        j = i
        while j < len(data) and data[j] == data[i]:
            j += 1
        count = j - i
        if count < 4:
            toks.extend(["%x" % data[i]] * count)
        else:
            toks.append("%d*%x" % (count, data[i]))
        i = j
    return ",".join(toks)


def decode_tokens(text):
    """dataField token string -> list of ints (padded/truncated by caller)."""
    out = []
    for tok in text.split(","):
        tok = tok.strip()
        if not tok:
            continue
        if "*" in tok:
            count, val = tok.split("*", 1)
            out.extend([int(val, 16)] * int(count))
        else:
            out.append(int(tok, 16))
    return out


# ---------------------------------------------------------------------------
# reading ROM data from a .dig
# ---------------------------------------------------------------------------

def read_roms(path):
    """Return {label: dataField-text} for all ROMs stored in a .dig circuit."""
    root = ET.parse(path).getroot()
    att = root.find("attributes")
    roms = {}
    if att is None:
        return roms
    for entry in att:
        if entry.find("string") is None or entry.find("string").text != "romContent":
            continue
        for sub in entry:
            tag = sub.tag
            if tag == "romList":  # current format
                for e in sub.iter("entry"):
                    label = e.find("string")
                    df = e.find(".//dataField")
                    if label is not None and df is not None:
                        roms[label.text] = df.text or ""
            elif tag == "storedRoms":  # pre-0.31 format (read-only support)
                for e in sub.iter("entry"):
                    label = e.find("string")
                    data = e.find("data")
                    if label is not None and data is not None:
                        roms[label.text] = data.text or ""
    return roms


def check_label_exists(path, label):
    """Warn helper: does the circuit contain an element with this Label?"""
    root = ET.parse(path).getroot()
    for ve in root.find("visualElements"):
        ae = ve.find("elementAttributes")
        if ae is None:
            continue
        for e in ae:
            if e.find("string").text == "Label" and list(e)[1].text == label:
                return True
    return False


# ---------------------------------------------------------------------------
# writing ROM data into a .dig (surgical text edit, keeps user formatting)
# ---------------------------------------------------------------------------

def entry_xml(label, tokens):
    return (
        "<entry>\n"
        "          <string>%s</string>\n"
        "          <romData>\n"
        "            <dataField>%s</dataField>\n"
        "          </romData>\n"
        "        </entry>" % (label, tokens)
    )


def write_rom(path, label, data):
    src = open(path, encoding="utf-8").read()
    tokens = encode_tokens(data)

    def sub_once(pattern, repl, s, what):
        new, n = re.subn(pattern, repl, s, count=1, flags=re.S)
        if n != 1:
            raise SystemExit("digrom: failed to %s (pattern not found)" % what)
        return new

    entry_re = re.compile(
        r"<entry>\s*<string>%s</string>\s*<romData>\s*<dataField>[^<]*</dataField>\s*</romData>\s*</entry>"
        % re.escape(label)
    )
    romcontent_re = re.compile(
        r"<entry>\s*<string>romContent</string>\s*<romList>\s*<roms>\s*(.*?)\s*</roms>\s*</romList>\s*</entry>",
        re.S,
    )
    oldfmt_re = re.compile(
        r"<entry>\s*<string>romContent</string>\s*<storedRoms>.*?</storedRoms>\s*</entry>",
        re.S,
    )

    if entry_re.search(src):
        # same-label ROM already stored: replace its data
        out = entry_re.sub(
            lambda m: entry_xml(label, tokens).strip(), src, count=1
        )
    elif romcontent_re.search(src):
        # romContent exists, but not for this label: insert a new entry
        out = sub_once(
            r"(</\s*roms\s*>)",
            lambda m: entry_xml(label, tokens) + "\n        " + m.group(1),
            src,
            "insert entry into <roms>",
        )
    elif oldfmt_re.search(src):
        # old storedRoms format: replace whole romContent entry with romList
        out = oldfmt_re.sub(
            lambda m: (
                "<entry>\n"
                "        <string>romContent</string>\n"
                "        <romList>\n"
                "          <roms>\n"
                + entry_xml(label, tokens)
                + "\n          </roms>\n"
                "        </romList>\n"
                "      </entry>"
            ),
            src,
            count=1,
        )
    elif "<attributes/>" in src:
        out = src.replace(
            "<attributes/>",
            "<attributes>\n    <entry>\n      <string>romContent</string>\n"
            "      <romList>\n        <roms>\n"
            + entry_xml(label, tokens)
            + "\n        </roms>\n      </romList>\n    </entry>\n  </attributes>",
            1,
        )
    elif re.search(r"<attributes>\s*</attributes>", src):
        out = sub_once(
            r"<attributes>\s*</attributes>",
            "<attributes>\n    <entry>\n      <string>romContent</string>\n"
            "      <romList>\n        <roms>\n"
            + entry_xml(label, tokens)
            + "\n        </roms>\n      </romList>\n    </entry>\n  </attributes>",
            src,
            "fill empty <attributes>",
        )
    elif "<attributes>" in src:
        out = sub_once(
            r"(</\s*attributes\s*>)",
            lambda m: (
                "  <entry>\n    <string>romContent</string>\n"
                "    <romList>\n      <roms>\n"
                + entry_xml(label, tokens).replace("          ", "    ")
                + "\n      </roms>\n    </romList>\n  </entry>\n"
                + m.group(1)
            ),
            src,
            "append entry to <attributes>",
        )
    else:
        out = sub_once(
            r"(<version>\d+</version>)",
            lambda m: m.group(1)
            + "\n  <attributes>\n    <entry>\n      <string>romContent</string>\n"
            "      <romList>\n        <roms>\n"
            + entry_xml(label, tokens)
            + "\n        </roms>\n      </romList>\n    </entry>\n  </attributes>",
            src,
            "insert <attributes> after <version>",
        )

    # round-trip check before touching the file
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(os.path.abspath(path)) or ".")
    os.close(fd)
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write(out)
    try:
        got = read_roms(tmp).get(label)
        if got is None:
            raise SystemExit("digrom: internal error - written file lost the ROM entry")
        back = decode_tokens(got)
        want = list(data)
        if back[: len(want)] != want:
            raise SystemExit("digrom: internal error - round-trip mismatch")
    except Exception:
        os.unlink(tmp)
        raise
    os.replace(tmp, path)


# ---------------------------------------------------------------------------
# data sources for `write` / `export`
# ---------------------------------------------------------------------------

def load_data(args):
    n = args.size
    if args.preset:
        if args.preset not in PRESETS:
            raise SystemExit(
                "digrom: unknown preset %r (have: %s)" % (args.preset, ", ".join(sorted(PRESETS)))
            )
        data = PRESETS[args.preset](swap_banks=getattr(args, "swap_banks", False))
        return data[:n] if n else data
    if args.data:
        vals = decode_tokens(args.data)
        return (vals + [0] * n)[:n] if n else vals
    if args.hexfile:
        text = open(args.hexfile, encoding="utf-8", errors="replace").read()
        if "v2.0 raw" in text:  # logisim format
            text = text.split("\n", 1)[1]
        vals = [int(t, 16) for t in re.split(r"[,\s]+", text.strip()) if t and not t.startswith(":")]
        return (vals + [0] * n)[:n] if n else vals
    if args.binfile:
        vals = list(open(args.binfile, "rb").read())
        return (vals + [0] * n)[:n] if n else vals
    raise SystemExit("digrom: no data source given (use --preset, --data, --hex or --bin)")


# ---------------------------------------------------------------------------
# export formats
# ---------------------------------------------------------------------------

def export_logisim(data):
    lines = ["v2.0 raw"]
    for i in range(0, len(data), 8):
        lines.append(" ".join("%x" % b for b in data[i : i + 8]))
    return "\n".join(lines) + "\n"


def export_intel(data):
    out = []
    for i in range(0, len(data), 16):
        chunk = data[i : i + 16]
        rec = [len(chunk), (i >> 8) & 0xFF, i & 0xFF, 0x00] + list(chunk)
        ck = (-sum(rec)) & 0xFF
        out.append(":" + "".join("%02X" % b for b in rec + [ck]))
    out.append(":00000001FF")
    return "\n".join(out) + "\n"


def cmd_dump(args):
    roms = read_roms(args.dig)
    if not roms:
        raise SystemExit("digrom: no romContent found in %s" % args.dig)
    labels = [args.label] if args.label else sorted(roms)
    for label in labels:
        if label not in roms:
            raise SystemExit("digrom: no ROM for label %r (have: %s)" % (label, ", ".join(sorted(roms))))
        vals = decode_tokens(roms[label])
        last = max((i for i, v in enumerate(vals) if v), default=-1)
        print("label %s: %d words listed, last nonzero address 0x%03x (%d)" % (label, len(vals), last, last))
        if args.words:
            size = args.size or (last + 16) & ~15 or 16
            for i in range(0, size, 16):
                row = vals[i : i + 16]
                print("  %04x: %s" % (i, " ".join("%02x" % v for v in row)))


def cmd_write(args):
    if not args.label:
        raise SystemExit("digrom: --label is required for write (the chip instance's Label)")
    if not check_label_exists(args.dig, args.label):
        print("digrom: WARNING: no element with Label %r in %s" % (args.label, args.dig), file=sys.stderr)
    data = load_data(args)
    write_rom(args.dig, args.label, data)
    print("digrom: wrote %d bytes to %s (label %s)" % (len(data), args.dig, args.label))


def cmd_export(args):
    data = None
    if args.preset or args.data or args.hexfile or args.binfile:
        data = load_data(args)
    elif args.dig and args.label:
        roms = read_roms(args.dig)
        if args.label not in roms:
            raise SystemExit("digrom: no ROM for label %r in %s" % (args.label, args.dig))
        data = decode_tokens(roms[args.label])
    else:
        raise SystemExit("digrom: export needs a --preset/--hex/--bin/--data source, or --dig + --label")
    if args.size:
        data = (list(data) + [0] * args.size)[: args.size]
    if args.format == "raw":
        with open(args.out, "wb") as fh:
            fh.write(bytes(data))
    else:
        text = {"logisim": export_logisim, "intel": export_intel}[args.format](data)
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(text)
    print("digrom: exported %d bytes to %s (%s)" % (len(data), args.out, args.format))


def cmd_presets(_args):
    for name, fn in sorted(PRESETS.items()):
        print("%s\n  %s\n" % (name, " ".join((fn.__doc__ or "").split())))


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    d = sub.add_parser("dump", help="read ROM data from a .dig")
    d.add_argument("--dig", required=True)
    d.add_argument("--label")
    d.add_argument("--words", action="store_true", help="print 16 words per line with addresses")
    d.add_argument("--size", type=int, help="with --words: total size to print (default: up to last nonzero)")
    d.set_defaults(fn=cmd_dump)

    w = sub.add_parser("write", help="write ROM data into a .dig")
    w.add_argument("--dig", required=True)
    w.add_argument("--label", help="chip instance Label (e.g. U45)")
    w.add_argument("--preset")
    w.add_argument("--data", help="literal dataField tokens, e.g. '7e,30,16*0'")
    w.add_argument("--hexfile", "--hex", dest="hexfile", help="text file of hex bytes (logisim or plain)")
    w.add_argument("--binfile", "--bin", dest="binfile", help="binary file")
    w.add_argument("--size", type=int, help="force image size (pad/truncate), e.g. 2048")
    w.add_argument("--swap-banks", action="store_true", help="preset option: swap mode banks")
    w.set_defaults(fn=cmd_write)

    e = sub.add_parser("export", help="write a ROM image to logisim/intel/raw")
    e.add_argument("--preset")
    e.add_argument("--data")
    e.add_argument("--hexfile", "--hex", dest="hexfile")
    e.add_argument("--binfile", "--bin", dest="binfile")
    e.add_argument("--dig")
    e.add_argument("--label")
    e.add_argument("--size", type=int, default=2048)
    e.add_argument("--swap-banks", action="store_true", help="preset option: swap mode banks")
    e.add_argument("--out", required=True)
    e.add_argument("--format", choices=["logisim", "intel", "raw"], default="logisim")
    e.set_defaults(fn=cmd_export)

    l = sub.add_parser("presets", help="list built-in presets")
    l.set_defaults(fn=cmd_presets)

    args = p.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
