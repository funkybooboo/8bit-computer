#!/usr/bin/env python3
"""
sim.py - cycle-accurate simulator for the 8-bit computer.

Runs programs the way the hardware does: it loads the two control-ROM
images (the same images archived in ../roms/ and injected into
../digital/Computer.dig), and every clock cycle it looks up the 16-bit
control word at (step, opcode, CF, ZF) and asserts the control signals
against the registers, RAM and bus - fetch included. Nothing is
special-cased per instruction, so sim.py verifies the microcode itself:
if the ROM images are wrong, the programs fail here exactly the way they
would fail on the machine.

Machine model (full reference: ../docs/microcode.md and
../docs/instruction-set.md):

  - 8 cycles per instruction: steps T0-T6 stable, T7 the transient step
    that resets the step counter (the ROM rows for T7 are all zero)
  - fetch (all instructions): T0 MI|CO (MAR <- PC), T1 RO|II|CE
    (IR <- RAM, PC <- PC + 1)
  - bus drivers (exactly one may be active per cycle): CO (PC), RO
    (RAM at MAR), IO (operand nibble, zero-extended), AO (A), EO (ALU)
  - ALU: A + B, or A - B when SU (implemented as A + ~B + 1, the
    adder's carry-in driven by SU); FI latches CF (carry out) and ZF
    (result zero)
  - registers latch on the clock edge at the end of each cycle, all
    from the pre-edge state; RI writes RAM[MAR]; PC wraps mod 16

Usage:
  sim.py programs/powers.asm                     # run: OUT stream + summary
  sim.py programs/rotate.asm --max-cycles 5000    # safety cap for loops
  sim.py programs/count.asm --trace 40            # per-cycle trace
  sim.py --selftest                               # verify the ROM images

Inputs: .asm sources (assembled with asm.py) or memory images (.hex
logisim/Intel, .bin raw). Output: one line per OUT (decimal and hex) on
stdout; the run summary goes to stderr. --trace prints every cycle
(step, control lines, bus, registers) to stderr.

Exit status: 0 if the program halted, 1 if it hit --max-cycles first.
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import asm  # the assembler, for .asm inputs
import digrom  # the control-ROM presets, for --selftest

# control word bits, split across the two ROMs (matches digrom.py)
ROM1_BITS = {
    "HLT": 0x80, "MI": 0x40, "RI": 0x20, "RO": 0x10,
    "IO": 0x08, "II": 0x04, "AI": 0x02, "AO": 0x01,
}
ROM2_BITS = {
    "EO": 0x80, "SU": 0x40, "BI": 0x20, "OI": 0x10,
    "CE": 0x08, "CO": 0x04, "J": 0x02, "FI": 0x01,
}
MEM_SIZE = 16   # the MAR is 4 bits
STEPS = 8       # step counter resets at T7 (see ../docs/microcode.md)


def load_control_roms(rom1_path, rom2_path):
    """Read the two control-ROM images (logisim .hex format)."""
    def read(path):
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
        body = text.split("\n", 1)[1] if text.lstrip().startswith("v2.0") else text
        vals = [int(t, 16) for t in body.replace(",", " ").split() if t]
        return (vals + [0] * 2048)[:2048]
    return read(rom1_path), read(rom2_path)


class Machine:
    """Cycle-accurate model: ROM images in, control signals per cycle."""

    def __init__(self, rom1, rom2, ram=None):
        self.rom1, self.rom2 = rom1, rom2
        self.ram = bytearray(ram if ram is not None else b"\x00" * MEM_SIZE)
        self.pc = self.mar = 0            # 4 bits, wrap mod 16
        self.ir = 0                        # 8 bits: opcode nibble + operand
        self.a = self.b = self.out = 0     # 8 bits, wrap mod 256
        self.cf = self.zf = 0
        self.step = 0
        self.halted = False
        self.cycles = 0
        self.instructions = 0
        self.outputs = []

    # -- the ALU, as the hardware computes it (A + ~B + 1 when SU) ------

    def alu(self, su):
        t = self.a + ((~self.b & 0xFF) if su else self.b) + (1 if su else 0)
        return t & 0xFF, 1 if t > 0xFF else 0

    # -- one clock cycle ------------------------------------------------

    def cycle(self):
        opcode = self.ir >> 4
        addr = self.step | (opcode << 3) | (self.cf << 8) | (self.zf << 9)
        w1, w2 = self.rom1[addr], self.rom2[addr]
        assert not (w1 & (ROM1_BITS["AO"] | ROM1_BITS["RO"] | ROM1_BITS["IO"])
                   and w2 & ROM2_BITS["EO"]), "bus contention in the microcode"

        # bus: exactly one driver asserted (the microcode guarantees it);
        # capture the ALU result/carry from the PRE-edge state here, because
        # FI latches the flags of THIS result even after AI has latched it
        # into A
        alu_res = alu_cf = None
        if w2 & ROM2_BITS["EO"]:
            alu_res, alu_cf = self.alu(w2 & ROM2_BITS["SU"])
        drivers = (
            (w2 & ROM2_BITS["CO"], lambda: self.pc),
            (w1 & ROM1_BITS["RO"], lambda: self.ram[self.mar]),
            (w1 & ROM1_BITS["IO"], lambda: self.ir & 0xF),
            (w1 & ROM1_BITS["AO"], lambda: self.a),
            (w2 & ROM2_BITS["EO"], lambda: alu_res),
        )
        on = [d for d in drivers if d[0]]
        assert len(on) <= 1, "bus contention in the microcode"
        bus = on[0][1]() if on else 0

        # edge: all latches from the pre-edge state
        if w1 & ROM1_BITS["MI"]:
            self.mar = bus & 0xF
        if w1 & ROM1_BITS["II"]:
            self.ir = bus & 0xFF
        if w2 & ROM2_BITS["BI"]:
            self.b = bus & 0xFF
        if w1 & ROM1_BITS["AI"]:
            self.a = bus & 0xFF
        if w1 & ROM1_BITS["RI"]:
            self.ram[self.mar] = bus & 0xFF
        if w2 & ROM2_BITS["OI"]:
            self.out = bus & 0xFF
            self.outputs.append(self.out)
        if w2 & ROM2_BITS["J"]:
            self.pc = bus & 0xF
        if w2 & ROM2_BITS["CE"]:
            self.pc = (self.pc + 1) & 0xF
        if w2 & ROM2_BITS["FI"]:
            if alu_res is None:  # FI without EO: the current ALU output
                alu_res, alu_cf = self.alu(w2 & ROM2_BITS["SU"])
            self.cf = alu_cf
            self.zf = 1 if alu_res == 0 else 0
        if w1 & ROM1_BITS["HLT"]:
            self.halted = True

        self.cycles += 1
        self.step = (self.step + 1) % STEPS
        if self.step == 0:
            self.instructions += 1
        return bus

    def run(self, max_cycles):
        while not self.halted and self.cycles < max_cycles:
            self.cycle()
        return self.halted


# ---------------------------------------------------------------------------
# input loading
# ---------------------------------------------------------------------------

def load_program(path, mem_size):
    """-> RAM image: assemble .asm, or read .hex/.bin memory image."""
    if path.endswith(".asm"):
        mem, _rows = asm.assemble(path, mem_size)
        return mem
    return asm.read_image(path, mem_size)


# ---------------------------------------------------------------------------
# output helpers
# ---------------------------------------------------------------------------

def control_names(w1, w2):
    names = [n for n, b in ROM1_BITS.items() if w1 & b]
    names += [n for n, b in ROM2_BITS.items() if w2 & b]
    return names


def run_one(path, rom1, rom2, max_cycles, trace, mem_size):
    ram = load_program(path, mem_size)
    m = Machine(rom1, rom2, ram)
    tcount = 0
    while not m.halted and m.cycles < max_cycles:
        pre = m  # trace BEFORE the cycle, with the cycle's own word
        if trace and tcount < trace:
            opcode = m.ir >> 4
            addr = m.step | (opcode << 3) | (m.cf << 8) | (m.zf << 9)
            w1, w2 = rom1[addr], rom2[addr]
            print(
                "cycle %-6d T%d ir=%02x(%s) bus=%02x a=%02x b=%02x pc=%x mar=%x"
                " out=%02x cf=%d zf=%d | %s"
                % (m.cycles, m.step, m.ir, asm.OPCODE_TO_MNEMONIC.get(opcode, ("?",))[0],
                   0, m.a, m.b, m.pc, m.mar, m.out, m.cf, m.zf,
                   ",".join(control_names(w1, w2))),
                file=sys.stderr,
            )
        m.cycle()
        tcount += 1
    return m


# ---------------------------------------------------------------------------
# selftest: the ROM images must match the digrom presets, and the fetch
# rows / bus-drive rules must hold everywhere
# ---------------------------------------------------------------------------

def selftest(rom1_path, rom2_path):
    rom1, rom2 = load_control_roms(rom1_path, rom2_path)
    p1, p2 = digrom._control_images()
    assert bytes(rom1) == p1, "roms/control-rom1.hex does not match the digrom preset"
    assert bytes(rom2) == p2, "roms/control-rom2.hex does not match the digrom preset"
    for step in range(STEPS):
        for opcode in range(16):
            for cf in (0, 1):
                for zf in (0, 1):
                    a = step | (opcode << 3) | (cf << 8) | (zf << 9)
                    w1, w2 = rom1[a], rom2[a]
                    drivers = sum(bool(x) for x in (
                        w2 & ROM2_BITS["CO"], w1 & ROM1_BITS["RO"], w1 & ROM1_BITS["IO"],
                        w1 & ROM1_BITS["AO"], w2 & ROM2_BITS["EO"],
                    ))
                    assert drivers <= 1, "bus contention at step %d opcode %x" % (step, opcode)
                    if step == 7:
                        assert (w1, w2) == (0, 0), "T7 rows must be zero (reset transient)"
                    if step in (0, 1):  # fetch is identical for all opcodes/flags
                        assert (w1, w2) == (
                            (ROM1_BITS["MI"], ROM2_BITS["CO"]) if step == 0
                            else (ROM1_BITS["RO"] | ROM1_BITS["II"], ROM2_BITS["CE"])
                        ), "fetch rows differ at opcode %x" % opcode
    print("sim: ROM images match the digrom presets; fetch and bus rules hold")
    print("sim: selftest OK")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    here = os.path.dirname(os.path.abspath(__file__))
    root = os.path.dirname(here)
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("input", nargs="?", help=".asm source or .hex/.bin memory image")
    p.add_argument("--rom1", default=os.path.join(root, "roms", "control-rom1.hex"))
    p.add_argument("--rom2", default=os.path.join(root, "roms", "control-rom2.hex"))
    p.add_argument("--max-cycles", type=int, default=100000,
                   help="safety cap (default 100000; exit 1 if reached)")
    p.add_argument("--trace", type=int, metavar="N", default=0,
                   help="print the first N cycles to stderr")
    p.add_argument("--selftest", action="store_true",
                   help="verify the ROM images and exit")
    args = p.parse_args()

    if args.selftest:
        selftest(args.rom1, args.rom2)
        return
    if not args.input:
        p.error("give a program (.asm/.hex/.bin) or --selftest")

    rom1, rom2 = load_control_roms(args.rom1, args.rom2)
    m = run_one(args.input, rom1, rom2, args.max_cycles, args.trace, MEM_SIZE)
    for v in m.outputs:
        print("%3d  (0x%02x)" % (v, v))
    status = "halted" if m.halted else "did NOT halt (hit --max-cycles)"
    print(
        "sim: %s | %d cycles, %d instructions (%.1f cycles/insn), %d OUTs"
        % (status, m.cycles, m.instructions,
           m.cycles / max(1, m.instructions), len(m.outputs)),
        file=sys.stderr,
    )
    sys.exit(0 if m.halted else 1)


if __name__ == "__main__":
    main()
