# Microcode

How the machine turns a step counter, an opcode and two flags into the 16
control lines that make every instruction work.

The **source of truth** is the generator: the MICROSTEPS table in
[../tools/genroms.py](../tools/genroms.py), one line per instruction in
a small notation ("/" separates microsteps, "," separates control lines,
"if CF" makes a step conditional on a flag half). The images are archived
in [../roms/](../roms/README.md) (logisim + Intel HEX) and injected into the
circuits under the chip Labels U47/U52 (circuit-level `romContent`). The
microcode was verified instruction by instruction against Ben Eater's
programmed EEPROM data, the 8bitsim reference image
(ngdrascal/8bitsim, memory-images/MicroInstructions.hex), and headless
simulation of every instruction including JC/JZ flag behavior and the
8-cycle step-counter wraparound.

## Control word

16 control lines, active high, split across two 28C16 ROMs:

    ROM1 U47, bit:   7    6   5   4   3   2   1   0
    signal:         HLT   MI  RI  RO  IO  II  AI  AO

    ROM2 U52, bit:   7   6   5   4   3   2   1   0
    signal:         EO  SU  BI  OI  CE  CO  J   FI

What each line drives, and what it means while high (including the
inverters that adapt them to the chips' active-low inputs):
[hardware.md](hardware.md), "The control lines".

## ROM addressing

Both ROMs share the same address word:

    A0-A2   step counter (a 74161 counting the microsteps)
    A3-A6   opcode (IR4-7, the instruction's high nibble)
    A7      which-ROM bit (U47 A7=GND, U52 A7=VCC on Ben's board; this build
            ties both to VDD - the images are replicated across A7)
    A8      CF (carry flag)
    A9      ZF (zero flag)
    A10     grounded (images replicated)

The images are A7- and A10-invariant: 2 KiB each, the same 512-byte
opcode/flag/step pattern four times over.

**Conditional jumps are implemented in the ROM addressing, not in extra
logic.** The T2 microstep of JC (IO|J) exists only in the half of the image
where A8 (CF) is 1; JZ's exists only where A9 (ZF) is 1. Same opcode, same
step - the flag bits of the ROM address select whether the jump lines are
there at all.

## Fetch (identical for every instruction)

    T0: MI | CO           MAR <- PC (put the instruction address on MAR)
    T1: RO | II | CE      bus <- RAM[MAR]; IR <- bus; PC <- PC + 1

## Per-instruction microsteps

The generator prints the whole table - every instruction's work
steps after the fetch, control line by control line (unused steps
output none):

    tools/genroms.py

NOP is fetch only. Opcodes 9-D (JNC/JNZ/ADDI/SUBI/DBL) are this project's
additions - the jump rows live in the "other half" of the ROM images (the
halves addressed by CF=0/ZF=0, which the original microcode leaves empty),
and the immediate/shift rows reuse the existing datapath (IO already drives
the operand nibble onto the bus, AO already drives A). No wiring changed; a
pre-addition ROM burn makes those opcodes NOPs. See [additions.md](additions.md),
"Added: five opcodes".

## Timing

Every instruction takes exactly 8 clock cycles. The step counter (a 74161)
counts steps 0..6; at step 7 the 74138 decoder's O7 line goes active, a
7400 NAND pair shapes it into a reset pulse for the counter's asynchronous
~MR, and counting restarts at 0. So the ROMs are addressed with steps 0-6
plus one transient step 7, and instructions that finish early simply idle
through the remaining cycles.

The reset fires at T7 rather than T5, paying two idle cycles per
instruction to leave T5/T6 usable as work steps (the addition and its
rationale: [additions.md](additions.md), "Added: 8-cycle
instructions"). ROM rows for steps 5-7 are all zero. The T5/T6 panel LEDs wire from ~Y5/~Y6; T7 is transient
and gets no LED.

You can watch the microcode run on the machine: single-step a program
(STEP_MODE + STEP_PULSE, see [hardware.md](hardware.md)
"Front panel") and the T0..T6 and control-line LEDs light up exactly
the generator's rows, one per microstep. Example programs:
[programs.md](programs.md).

## Regenerating and injecting the ROMs

The workflow (export to ../roms/, write into Computer.dig, re-verify):
[tools.md](tools.md).
