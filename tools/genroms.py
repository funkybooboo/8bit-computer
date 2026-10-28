#!/usr/bin/env python3
"""
genroms.py - generate the machine's ROMs.

The machine's tables live here - the opcode numbers, the 16 control
lines (which bit of which control ROM drives each), and the MICROSTEPS
table, the source of truth for what every instruction does, cycle by
cycle - and this script turns them into the ROM images in ../roms/ that
every build of the machine runs (digital/Computer.dig, web/js/machine.js,
the breadboards). The ISA table in asm.py comes from here too, so tools
and builds can never disagree about an opcode or a microstep.

Run with no arguments to print the instruction/microstep table.
--generate regenerates the images in ../roms/ from these tables (the
logisim .hex every build loads plus the Intel HEX for EEPROM burners).
--check verifies that the images archived in ../roms/ are exactly these
tables, and that the fetch and bus rules hold in every ROM row.

The roms are shared by every build; each build uploads them its own way:
Digital via digital/rom.py (they are embedded in the .dig), the web
build by fetching them, the hardware by burning the Intel HEX files.

Full references: ../docs/instruction-set.md (the ISA),
../docs/microcode.md (the control unit and timing), ../docs/hardware.md
(what is wired where).
"""

import os
import re

# ---------------------------------------------------------------------------
# opcodes (canonical; docs/instruction-set.md documents them)
# ---------------------------------------------------------------------------

OPCODES = {
    "NOP": 0x0, "LDA": 0x1, "ADD": 0x2, "SUB": 0x3, "STA": 0x4, "LDI": 0x5,
    "JMP": 0x6, "JC": 0x7, "JZ": 0x8, "JNC": 0x9, "JNZ": 0xA, "ADDI": 0xB,
    "SUBI": 0xC, "DBL": 0xD, "OUT": 0xE, "HLT": 0xF,
}

# ---------------------------------------------------------------------------
# the control word: 16 lines, split across the two control ROMs
# (which ROM drives which line: ../docs/hardware.md, "The control lines")
# ---------------------------------------------------------------------------

ROM1_BITS = {  # U47
    "HLT": 0x80, "MI": 0x40, "RI": 0x20, "RO": 0x10,
    "IO": 0x08, "II": 0x04, "AI": 0x02, "AO": 0x01,
}
ROM2_BITS = {  # U52
    "EO": 0x80, "SU": 0x40, "BI": 0x20, "OI": 0x10,
    "CE": 0x08, "CO": 0x04, "J": 0x02, "FI": 0x01,
}

# ---------------------------------------------------------------------------
# the microcode - the source of truth for what each instruction does.
#
# One line per instruction; '/' separates microsteps, ',' separates control
# lines within a step. Steps number themselves from T2 (T0 and T1 are the
# fetch, identical for every instruction: T0 MI,CO / T1 RO,II,CE). A step
# may be conditional - 'if CF' / 'if not CF' / 'if ZF' / 'if not ZF' - it
# then exists only in the matching halves of the ROM images (the halves
# addressed by the flag; that is what JC/JZ/JNC/JNZ are). T7 is reserved:
# it is the transient step that resets the step counter, so usable steps
# are T2..T6 (see ../docs/microcode.md, "Timing").
# ---------------------------------------------------------------------------

MICROSTEPS = {
    "NOP":  "",
    "LDA":  "MI,IO / RO,AI",
    "ADD":  "MI,IO / RO,BI / EO,AI,FI",
    "SUB":  "MI,IO / RO,BI / EO,SU,AI,FI",
    "STA":  "MI,IO / AO,RI",
    "LDI":  "IO,AI",
    "JMP":  "IO,J",
    "JC":   "IO,J if CF",
    "JZ":   "IO,J if ZF",
    "JNC":  "IO,J if not CF",
    "JNZ":  "IO,J if not ZF",
    "ADDI": "IO,BI / EO,AI,FI",
    "SUBI": "IO,BI / EO,SU,AI,FI",
    "DBL":  "AO,BI / EO,AI,FI",
    "OUT":  "AO,OI",
    "HLT":  "HLT",
}

FETCH = [(0, None, frozenset({"MI", "CO"})), (1, None, frozenset({"RO", "II", "CE"}))]


def parse_microsteps(spec):
    """'MI,IO / RO,AI' -> [(2, None, {'MI','IO'}), (3, None, {'RO','AI'})].

    Conditional steps: 'IO,J if CF' -> [(2, ('CF', True), {'IO','J'})],
    'IO,J if not ZF' -> [(2, ('ZF', False), {'IO','J'})].
    Returns [] for an empty spec (a fetch-only instruction).
    """
    if not spec.strip():
        return []
    steps = []
    for i, chunk in enumerate(spec.split("/")):
        chunk = chunk.strip()
        cond = None
        if " if " in chunk:
            chunk, c = chunk.split(" if ", 1)
            c = c.strip()
            if c.startswith("not "):
                cond = (c[4:].strip(), False)
            else:
                cond = (c, True)
            if cond[0] not in ("CF", "ZF"):
                raise ValueError("microstep condition must be CF or ZF, not %r" % cond[0])
            chunk = chunk.strip()
        lines = frozenset(t.strip() for t in chunk.split(",") if t.strip())
        bad = lines - set(ROM1_BITS) - set(ROM2_BITS)
        if bad:
            raise ValueError("unknown control line(s) %s in %r" % (sorted(bad), spec))
        steps.append((2 + i, cond, lines))
    if steps and steps[-1][0] > 6:
        raise ValueError("microstep past T6 (T7 is the reset transient): %r" % spec)
    return steps


def control_images():
    """The two control-ROM images (2048 bytes each) from MICROSTEPS.

    Address (both ROMs): step A0-A2, opcode A3-A6, CF A8, ZF A9; the images
    are replicated across A7 (the which-ROM bit) and A10 (grounded) so they
    are correct for any A7/A10 wiring.
    """
    r1, r2 = bytearray(2048), bytearray(2048)
    for name, opcode in OPCODES.items():
        for cf in (0, 1):
            for zf in (0, 1):
                flags = {"CF": cf, "ZF": zf}
                for step, cond, lines in FETCH + parse_microsteps(MICROSTEPS[name]):
                    if cond is not None and flags[cond[0]] != cond[1]:
                        continue  # this half of the ROM gets no such step
                    w1 = sum(ROM1_BITS[l] for l in lines if l in ROM1_BITS)
                    w2 = sum(ROM2_BITS[l] for l in lines if l in ROM2_BITS)
                    for a7 in (0, 1):
                        for a10 in (0, 1):
                            a = (step | (opcode << 3) | (a7 << 7)
                                 | (cf << 8) | (zf << 9) | (a10 << 10))
                            r1[a] = w1
                            r2[a] = w2
    return bytes(r1), bytes(r2)


def control_rom1(**_kw):
    """U47: HLT/MI/RI/RO/IO/II/AI/AO half of the control word."""
    return control_images()[0]


def control_rom2(**_kw):
    """U52: EO/SU/BI/OI/CE/CO/J/FI half of the control word."""
    return control_images()[1]


# ---------------------------------------------------------------------------
# the display ROM (the output module's digit patterns; the encoding is
# documented in ../docs/hardware.md, "The display")
# ---------------------------------------------------------------------------

SEG_DIGITS = [0x7e, 0x30, 0x6d, 0x79, 0x33, 0x5b, 0x5f, 0x70, 0x7f, 0x7b]
SEG_HEX = SEG_DIGITS + [0x77, 0x1f, 0x4e, 0x3d, 0x4f, 0x47]  # A b C d E F
SEG_BLANK = 0x00


def output_display(swap_banks=False):
    """U45: 4-digit multiplexed decimal/hex display ROM (28C16, 2 KiB).

    Address = A10*1024 + A9*512 + A8*256 + value, where A8/A9 are the 7476
    mux-counter outputs that also drive the 74139 select inputs, so ROM page
    p lights the digit whose common cathode ~1Yp pulls low: page 0 = ones
    digit (rightmost display), 1 = tens, 2 = hundreds, 3 = thousands (always
    blank for 8-bit values). A10 is the front-panel mode switch: by default
    A10=1 -> decimal, A10=0 -> hexadecimal; leading zeros blanked in both
    modes. Pass swap_banks=True to swap which switch position gives which
    mode. ROM bit -> segment: 6=a 5=b 4=c 3=d 2=e 1=f 0=g 7=dp.
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


PRESETS = {
    "output-display": output_display,
    "control-rom1": control_rom1,
    "control-rom2": control_rom2,
}


# ---------------------------------------------------------------------------
# memory image formats (how these ROM contents and the assembler's output
# travel between tools and build targets: Digital's ROM editor loads the
# logisim form, EEPROM burners take the Intel form)
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


def write_image(path, mem, fmt):
    """Write a memory image: 'raw' (bare binary - the .bin) or, for the
    machine's own ROM contents, 'logisim' and 'intel'."""
    if fmt == "raw":
        with open(path, "wb") as fh:
            fh.write(bytes(mem))
    else:
        text = export_logisim(mem) if fmt == "logisim" else export_intel(mem)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)


def read_image(path, size=None):
    """Read a memory image: logisim .hex, Intel HEX or raw binary (sniffed).
    Pads (or truncates) to `size` bytes; without a size, returns exactly
    the file's own content length."""
    with open(path, "rb") as fh:
        blob = fh.read()
    if blob.lstrip()[:1] == b":":  # Intel HEX
        vals = []
        for line in blob.decode("ascii", "replace").splitlines():
            line = line.strip()
            if not line:
                continue
            rec = bytes.fromhex(line[1:])
            count, addr, rectype = rec[0], (rec[1] << 8) | rec[2], rec[3]
            if rectype == 0x00:
                for i in range(count):
                    vals.append((addr + i, rec[4 + i]))
            elif rectype == 0x01:
                break
            else:
                raise ValueError("unsupported Intel HEX record type %d in %s" % (rectype, path))
        if not vals:
            raise ValueError("no data records in %s" % path)
        mem = bytearray(vals[-1][0] + 1 if not size else size)
        for a, v in vals:
            if a < len(mem):
                mem[a] = v
        return mem
    text = blob.decode("utf-8", "replace")
    stripped = text.lstrip()
    if stripped.startswith("v2.0"):  # logisim/Digital format
        body = text.split("\n", 1)[1] if "\n" in text else ""
        vals = [int(t, 16) for t in body.replace(",", " ").split() if t]
        return bytearray((vals + [0] * size)[:size] if size else vals)
    vals = list(blob)
    return bytearray((vals + [0] * size)[:size] if size else vals)  # raw binary


# ---------------------------------------------------------------------------
# running this file: show the table, regenerate the roms, or check them
# ---------------------------------------------------------------------------

def _dump():
    print("fetch (every instruction): T0 MI,CO / T1 RO,II,CE")
    print()
    print("opcode  mnemonic  microsteps")
    print("------  --------  ------------------------------")
    for name, opcode in sorted(OPCODES.items(), key=lambda kv: kv[1]):
        spec = MICROSTEPS[name]
        row = " / ".join(
            "%s %s%s" % ("T%d" % step, ",".join(sorted(lines)),
                         "" if cond is None else
                         (" if %s" % cond[0] if cond[1] else " if not %s" % cond[0]))
            for step, cond, lines in parse_microsteps(spec)
        ) or "-"
        print("0x%x     %-8s  %s" % (opcode, name, row))


def _generate():
    """Regenerate the images in ../roms/ from these tables: the logisim
    .hex every build loads plus the Intel HEX for EEPROM burners."""
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    for name, preset in PRESETS.items():
        img = preset()
        for suffix, fmt in ((".hex", "logisim"), ("-intel.hex", "intel")):
            path = os.path.join(root, "roms", name + suffix)
            write_image(path, img, fmt)
            print("genroms: wrote roms/%s%s" % (name, suffix))


def _check():
    """Verify the images archived in ../roms/ are exactly these tables,
    and that the fetch and bus rules hold in every control-ROM row
    (the rules are documented in ../docs/microcode.md)."""
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    for name, preset in PRESETS.items():
        img = preset()
        archived = bytes(read_image(os.path.join(root, "roms", name + ".hex"),
                                    len(img)))
        assert archived == img, \
            "roms/%s.hex does not match the tables in genroms.py" % name

    # rules every control-ROM row must satisfy: fetch is identical for all
    # opcodes/flags (T0 MI|CO, T1 RO|II|CE), at most one bus driver per
    # cycle, and T7 - the transient step that resets the step counter -
    # reads zero in both ROMs
    rom1 = PRESETS["control-rom1"]()
    rom2 = PRESETS["control-rom2"]()
    for step in range(8):
        for opcode in range(16):
            for cf in (0, 1):
                for zf in (0, 1):
                    a = step | (opcode << 3) | (cf << 8) | (zf << 9)
                    w1, w2 = rom1[a], rom2[a]
                    drivers = sum(bool(x) for x in (
                        w2 & ROM2_BITS["CO"], w1 & ROM1_BITS["RO"], w1 & ROM1_BITS["IO"],
                        w1 & ROM1_BITS["AO"], w2 & ROM2_BITS["EO"],
                    ))
                    assert drivers <= 1, \
                        "bus contention at step %d opcode %x" % (step, opcode)
                    if step == 7:
                        assert (w1, w2) == (0, 0), "T7 rows must be zero (reset transient)"
                    if step in (0, 1):
                        assert (w1, w2) == (
                            (ROM1_BITS["MI"], ROM2_BITS["CO"]) if step == 0
                            else (ROM1_BITS["RO"] | ROM1_BITS["II"], ROM2_BITS["CE"])
                        ), "fetch rows differ at opcode %x" % opcode
    print("genroms: roms/ images match these tables; fetch and bus rules hold")
    print("genroms: check OK")


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true",
                    help="verify the ../roms/ images are exactly these tables")
    ap.add_argument("--generate", action="store_true",
                    help="regenerate the ../roms/ images from these tables")
    args = ap.parse_args()
    if args.generate:
        _generate()
    elif args.check:
        _check()
    else:
        _dump()
