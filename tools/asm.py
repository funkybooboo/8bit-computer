#!/usr/bin/env python3
"""
asm.py - two-pass assembler and disassembler for the 8-bit computer's
machine language, plus the tiny assembly language defined for it.

Machine model (full reference: ../docs/instruction-set.md):

  - every instruction is ONE byte: [opcode:4][operand:4]
  - RAM is 16 x 8 bits (MAR and PC are 4 bits); program and data share it
  - the operand nibble is a RAM address (LDA/ADD/SUB/STA/JMP/JC/JZ/JNC/JNZ,
    range 0-15) or a 4-bit immediate loaded zero-extended (LDI/ADDI/SUBI,
    0-15); DBL ignores its operand nibble
  - opcode:   0     1    2    3    4    5    6    7    8    9    A    B    C    D    E    F
    mnemonic: NOP   LDA  ADD  SUB  STA  LDI  JMP  JC   JZ   JNC  JNZ  ADDI SUBI DBL  OUT  HLT
    (JNC/JNZ/ADDI/SUBI/DBL are this project's additions, see
    ../docs/additions.md, "Added: five opcodes"; the original
    Ben Eater set is the rest)

Assembly language (full reference: ../docs/assembly-language.md):

  - one statement per line:  [label:] mnemonic [operand] [; comment]
  - directives:  .DB val[,val...]   (emit raw data bytes)
                .ORG addr          (set the next address, forward only)
                name: .EQU val     (named constant, usable as any operand)
  - numbers: decimal, 0x1F, 0b1010, 'A' (ASCII char literal); labels are
    identifiers
  - mnemonics and directives are case-insensitive, labels are not
  - every instruction assembles to exactly one byte; the assembler rejects
    anything the hardware cannot encode (operand out of 0-15, program
    larger than RAM, ...)

Examples:
  asm.py programs/count.asm                       # listing to stdout
  asm.py programs/count.asm --out count.bin --lst count.lst
  asm.py --dis count.bin                          # disassemble an image
  asm.py --dis count.bin --all                    # ... including trailing NOPs
"""

import argparse
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from genroms import OPCODES, read_image, write_image  # tools/genroms.py:
# opcode numbers (the source of truth) + the image file formats

# ---------------------------------------------------------------------------
# instruction table: language-level facts about each mnemonic. The opcode
# NUMBERS come from genroms.py (the machine's definition, shared with the
# microcode); operand kinds and effects are language documentation.
# ---------------------------------------------------------------------------

OPERAND_NONE, OPERAND_ADDR, OPERAND_IMM = "none", "addr", "imm"

_LANGUAGE = {  # mnemonic -> (operand kind, effect)
    "NOP": (OPERAND_NONE, "no operation"),
    "LDA": (OPERAND_ADDR, "A <- M[operand]"),
    "ADD": (OPERAND_ADDR, "A <- A + M[operand]; CF/ZF updated"),
    "SUB": (OPERAND_ADDR, "A <- A - M[operand]; CF/ZF updated"),
    "STA": (OPERAND_ADDR, "M[operand] <- A"),
    "LDI": (OPERAND_IMM,  "A <- operand (0-15, zero-extended)"),
    "JMP": (OPERAND_ADDR, "PC <- operand"),
    "JC":  (OPERAND_ADDR, "PC <- operand if CF = 1"),
    "JZ":  (OPERAND_ADDR, "PC <- operand if ZF = 1"),
    "JNC": (OPERAND_ADDR, "PC <- operand if CF = 0"),
    "JNZ": (OPERAND_ADDR, "PC <- operand if ZF = 0"),
    "ADDI": (OPERAND_IMM, "A <- A + operand; CF/ZF updated"),
    "SUBI": (OPERAND_IMM, "A <- A - operand; CF/ZF updated"),
    "DBL": (OPERAND_NONE, "A <- 2*A (shift left; CF = bit shifted out)"),
    "OUT": (OPERAND_NONE, "display <- A"),
    "HLT": (OPERAND_NONE, "stop the clock"),
}
assert set(_LANGUAGE) == set(OPCODES), "asm/machine opcode tables disagree"
MNEMONICS = {name: (OPCODES[name], kind, effect)
             for name, (kind, effect) in _LANGUAGE.items()}

ADDR_MAX = 15  # MAR and PC are 4 bits -> RAM addresses 0-15
IMM_MAX = 15   # the operand field is one nibble

OPCODE_TO_MNEMONIC = {v[0]: (k, v[1]) for k, v in MNEMONICS.items()}

IDENT_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\Z")
LABEL_DEF_RE = re.compile(r"([A-Za-z_][A-Za-z0-9_]*)\s*:\s*(.*)\Z")


class SourceError(Exception):
    """An error tied to a source position."""

    def __init__(self, path, lineno, msg):
        super().__init__(msg)
        self.path, self.lineno, self.msg = path, lineno, msg

    def __str__(self):
        return "%s:%d: %s" % (self.path, self.lineno, self.msg)


def parse_number(tok):
    """token -> int if it is a numeric literal, else None."""
    low = tok.lower()
    if len(tok) > 2 and low.startswith("0x"):
        try:
            return int(low, 16)
        except ValueError:
            return None
    if len(tok) > 2 and low.startswith("0b"):
        try:
            return int(low, 2)
        except ValueError:
            return None
    if tok.isdigit():
        return int(tok, 10)
    if len(tok) == 3 and tok[0] == tok[2] == "'":  # 'A' char literal
        v = ord(tok[1])
        return v if 0 < v < 128 else None
    return None


# ---------------------------------------------------------------------------
# parsing
# ---------------------------------------------------------------------------

class Stmt:
    """One parsed source statement (label + instruction/directive)."""

    __slots__ = ("lineno", "label", "kind", "payload", "text", "addr")

    def __init__(self, lineno, label, kind, payload, text):
        self.lineno = lineno
        self.label = label
        self.kind = kind  # "insn" | "db" | "org" | "labelonly"
        self.payload = payload
        self.text = text  # comment-stripped source, for the listing
        self.addr = None


def parse_line(path, lineno, raw):
    """raw source line -> Stmt or None (blank/comment-only)."""
    text = raw.split(";", 1)[0].strip()
    if not text:
        return None
    label, rest = None, text
    if ":" in text:
        m = LABEL_DEF_RE.match(text)
        if not m:
            raise SourceError(path, lineno, "cannot parse %r (label syntax is 'name:')" % text)
        label, rest = m.group(1), m.group(2).strip()
    if label is not None and label.upper() in list(MNEMONICS) + ["DB", "ORG", "EQU"]:
        raise SourceError(path, lineno, "label %r shadows an instruction name; pick another" % label)
    if not rest:
        return Stmt(lineno, label, "labelonly", None, text)
    parts = rest.split(None, 1)
    head, arg = parts[0].upper(), (parts[1].strip() if len(parts) > 1 else "")
    if head in MNEMONICS:
        op, kind, _ = MNEMONICS[head]
        if kind is OPERAND_NONE and arg:
            raise SourceError(path, lineno, "%s takes no operand" % head)
        if kind is not OPERAND_NONE and not arg:
            raise SourceError(path, lineno, "%s requires an operand (0-15)" % head)
        return Stmt(lineno, label, "insn", (head, kind, arg), text)
    if head == ".DB":
        if not arg:
            raise SourceError(path, lineno, ".DB requires at least one value")
        return Stmt(lineno, label, "db", [v.strip() for v in arg.split(",")], text)
    if head == ".ORG":
        if not arg:
            raise SourceError(path, lineno, ".ORG requires an address")
        return Stmt(lineno, label, "org", arg, text)
    if head == ".EQU":
        if label is None:
            raise SourceError(path, lineno, ".EQU needs a name: use 'name: .EQU value'")
        if not arg:
            raise SourceError(path, lineno, ".EQU requires a value")
        return Stmt(lineno, label, "equ", arg, text)
    raise SourceError(
        path, lineno,
        "unknown instruction or directive %r (see docs/instruction-set.md)" % parts[0],
    )


# ---------------------------------------------------------------------------
# the two passes
# ---------------------------------------------------------------------------

def first_pass(path, stmts, mem_size):
    """Assign an address to every statement; collect labels and .EQU constants."""
    labels, equs = {}, {}
    addr = 0
    for st in stmts:
        if st.kind == "equ":
            v = parse_number(st.payload.strip())
            if v is None:
                raise SourceError(path, st.lineno, ".EQU needs a numeric or char value (labels are not known yet)")
            if not 0 <= v <= 255:
                raise SourceError(path, st.lineno, ".EQU value %d is out of range 0-255" % v)
            if st.label in labels or st.label in equs:
                raise SourceError(path, st.lineno, "duplicate name %r" % st.label)
            equs[st.label] = v
            st.addr = addr
            continue
        if st.kind == "org":
            v = parse_number(st.payload.strip())
            if v is None:
                raise SourceError(path, st.lineno, ".ORG needs a numeric address (labels are not known yet)")
            if v < addr:
                raise SourceError(path, st.lineno, ".ORG moves backwards (from %d to %d)" % (addr, v))
            if v > mem_size:
                raise SourceError(path, st.lineno, ".ORG address %d is beyond the %d bytes of RAM" % (v, mem_size))
            addr = v
        if st.label is not None:
            if st.label in labels:
                raise SourceError(path, st.lineno, "duplicate label %r (first defined for address %d)" % (st.label, labels[st.label]))
            if st.label in equs:
                raise SourceError(path, st.lineno, "name %r is already a .EQU constant" % st.label)
            labels[st.label] = addr
        size = 1 if st.kind == "insn" else (len(st.payload) if st.kind == "db" else 0)
        if addr + size > mem_size:
            raise SourceError(path, st.lineno, "program does not fit in %d bytes of RAM (statement would end at %d)" % (mem_size, addr + size))
        st.addr = addr
        addr += size
    return labels, equs


def resolve(tok, labels, equs, path, lineno):
    """operand token -> int (numeric literal, .EQU constant or label address)."""
    tok = tok.strip()
    if not tok:
        raise SourceError(path, lineno, "missing operand")
    v = parse_number(tok)
    if v is not None:
        return v
    if IDENT_RE.match(tok):
        if tok in equs:
            return equs[tok]
        if tok in labels:
            return labels[tok]
        raise SourceError(path, lineno, "undefined name %r (label or .EQU constant)" % tok)
    raise SourceError(path, lineno, "cannot parse operand %r (decimal, 0xNN, 0bNNNN, 'c' or a name)" % tok)


def second_pass(path, stmts, labels, equs, mem_size):
    """Resolve operands, encode, return (memory image, listing rows)."""
    mem = bytearray(mem_size)
    rows = []  # (addr, byte-or-None, text)
    for st in stmts:
        if st.kind == "insn":
            head, kind, arg = st.payload
            opcode, _, _ = MNEMONICS[head]
            if kind is OPERAND_NONE:
                mem[st.addr] = opcode << 4
                rows.append((st.addr, mem[st.addr], st.text))
                continue
            val = resolve(arg, labels, equs, path, st.lineno)
            limit = ADDR_MAX if kind is OPERAND_ADDR else IMM_MAX
            if val > limit:
                kindword = "RAM address" if kind is OPERAND_ADDR else "immediate"
                raise SourceError(
                    path, st.lineno,
                    "%s operand %d is out of range 0-%d (the operand field is one"
                    " nibble; build larger constants with ADD)"
                    % (kindword, val, limit),
                )
            mem[st.addr] = (opcode << 4) | val
            rows.append((st.addr, mem[st.addr], st.text))
        elif st.kind == "db":
            for i, tok in enumerate(st.payload):
                v = resolve(tok, labels, equs, path, st.lineno)
                if not 0 <= v <= 255:
                    raise SourceError(path, st.lineno, ".DB value %d is out of range 0-255" % v)
                mem[st.addr + i] = v
                rows.append((st.addr + i, v, st.text if i == 0 else ""))
        else:  # "org" / "labelonly" / "equ": no byte emitted
            rows.append((st.addr, None, st.text))
    return mem, rows


def assemble(path, mem_size):
    """Assemble a source file -> (mem, rows) or exit with all parse errors."""
    try:
        with open(path, encoding="utf-8") as fh:
            lines = fh.read().splitlines()
    except OSError as e:
        raise SystemExit("asm: cannot read %s: %s" % (path, e))
    stmts, errors = [], []
    for lineno, raw in enumerate(lines, 1):
        try:
            st = parse_line(path, lineno, raw)
        except SourceError as e:
            errors.append(str(e))
            continue
        if st is not None:
            stmts.append(st)
    if errors:
        for e in errors:
            print(e, file=sys.stderr)
        raise SystemExit("asm: %d parse error(s)" % len(errors))
    try:
        labels, equs = first_pass(path, stmts, mem_size)
        return second_pass(path, stmts, labels, equs, mem_size)
    except SourceError as e:
        raise SystemExit("asm: %s" % e)


# ---------------------------------------------------------------------------
# listing / images
# ---------------------------------------------------------------------------

def bits_field(addr, b, addr_width):
    """'0 0 0 0    0 1 0 1    0 0 0 0' = address | opcode | operand."""
    def group(val, width):
        return " ".join(str((val >> i) & 1) for i in range(width - 1, -1, -1))
    return "%s    %s    %s" % (group(addr, addr_width), group(b >> 4, 4), group(b & 0xF, 4))


def format_listing(rows, used, mem_size):
    addr_width = 4
    while (1 << addr_width) < mem_size:
        addr_width += 4
    gw = 2 * addr_width - 1  # chars taken by one space-separated bit group
    pad = lambda s: s.ljust(gw)
    out = [
        "ADDR  BYTE  %s    %s    %s  SOURCE" % (pad("ADDRESS"), pad("OPCODE"), pad("PARAM")),
        "----  ----  %s    %s    %s  --------" % (pad("----"), pad("----"), pad("----")),
    ]
    for addr, b, text in rows:
        a = ("%02x" % addr) if addr is not None else "--"
        v = ("%02x" % b) if b is not None else "--"
        bits = bits_field(addr, b, addr_width) if (b is not None and addr is not None) else ""
        out.append(("%-4s  %-4s  %s  %s" % (a, v, bits, text)).rstrip())
    out.append("")
    out.append("; bits column: address | opcode | operand (the dipswitch groups for program entry)")
    out.append("; %d of %d RAM bytes used; unused bytes read as 0x00 (NOP)" % (used, mem_size))
    return "\n".join(out) + "\n"


def disassemble(mem, path, decode_all):
    if not any(mem):
        print("; %s: image is all zero (empty RAM)" % path)
        return
    last = max(i for i, b in enumerate(mem) if b)
    end = len(mem) if decode_all else last + 1
    print("ADDR  BYTE  SOURCE")
    print("----  ----  ----------------------------------------")
    for i in range(end):
        op, val = mem[i] >> 4, mem[i] & 0xF
        if op in OPCODE_TO_MNEMONIC:
            mn, kind = OPCODE_TO_MNEMONIC[op]
            text = mn if kind is OPERAND_NONE else "%s %d" % (mn, val)
        else:
            text = ".DB 0x%02x" % mem[i]
        print("%-4s  %-4s  %s" % ("%02x" % i, "%02x" % mem[i], text))
    if not decode_all and last + 1 < len(mem):
        print("; %d trailing zero byte(s) not shown (use --all)" % (len(mem) - last - 1))


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("input", help="assembly source (.asm), or with --dis: a memory image")
    p.add_argument("--dis", action="store_true",
                   help="disassemble a memory image instead of assembling")
    p.add_argument("--out", help="write the assembled memory image to this file")
    p.add_argument("--format", choices=["bin", "raw", "logisim", "intel"], default="bin",
                   help="image file format for --out (default: bin - one hex"
                        " byte per line, address = line number)")
    p.add_argument("--lst", "--listing", dest="lst",
                   help="write the listing to this file instead of stdout")
    p.add_argument("--mem-size", type=int, default=16,
                   help="RAM size in bytes (default: 16; the MAR is 4 bits)")
    p.add_argument("--all", action="store_true",
                   help="with --dis: decode the whole image, not just up to the last nonzero byte")
    args = p.parse_args()

    if args.mem_size < 1:
        raise SystemExit("asm: --mem-size must be positive")

    if args.dis:
        try:
            mem = read_image(args.input, args.mem_size)
        except ValueError as e:
            raise SystemExit("asm: %s" % e)
        disassemble(mem, args.input, args.all)
        return

    mem, rows = assemble(args.input, args.mem_size)
    used = sum(1 for _a, b, _t in rows if b is not None)
    listing = format_listing(rows, used, args.mem_size)
    if args.lst:
        with open(args.lst, "w", encoding="utf-8") as fh:
            fh.write(listing)
        print("asm: wrote listing to %s" % args.lst)
    else:
        sys.stdout.write(listing)
    if args.out:
        write_image(args.out, mem, args.format)
        print("asm: wrote %d-byte image to %s (%s)" % (len(mem), args.out, args.format))


if __name__ == "__main__":
    main()
