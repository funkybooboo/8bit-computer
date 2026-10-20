# Microcode

How the machine turns a step counter, an opcode and two flags into the 16
control lines that make every instruction work.

The **source of truth** is the generator: the MICROSTEPS table in
[../tools/machine.py](../tools/machine.py), one line per instruction in
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

| signal | drives          | effect while 1                                      |
|--------|-----------------|------------------------------------------------------|
| HLT    | clock gating    | stop the clock                                       |
| MI     | MAR             | load MAR from the bus (low nibble)                   |
| RI     | RAM             | write the bus into RAM at MAR                        |
| RO     | RAM             | drive RAM[MAR] onto the bus                          |
| IO     | IR              | drive the operand nibble onto the bus (high bits 0)  |
| II     | IR              | load IR from the bus                                |
| AI     | A register      | load A from the bus                                  |
| AO     | A register      | drive A onto the bus                                 |
| EO     | ALU             | drive the ALU sum onto the bus                       |
| SU     | ALU             | invert B into the adder (subtract)                   |
| BI     | B register      | load B from the bus                                  |
| OI     | output register | load the display register from the bus               |
| CE     | PC              | increment PC                                         |
| CO     | PC              | drive PC onto the bus                                |
| J      | PC              | load PC from the bus (low nibble)                    |
| FI     | flag registers  | latch CF/ZF from the ALU                              |

(The ROM bits are active-high; inverters between the control logic and the
chips adapt them to the active-low chip inputs.)

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

Every instruction continues after the fetch like this (unused steps output
no control lines):

| insn | step | ROM1 (U47) | ROM2 (U52) | meaning                        |
|-------|------|------------|-------------|--------------------------------|
| NOP   | -    | -          | -           | (fetch only)                   |
| LDA   | T2   | MI, IO     | -           | MAR <- operand                 |
|       | T3   | RO, AI     | -           | A <- RAM                       |
| ADD   | T2   | MI, IO     | -           | MAR <- operand                 |
|       | T3   | RO, BI     | -           | B <- RAM                       |
|       | T4   | AI         | EO, FI      | A <- A + B, flags              |
| SUB   | T2   | MI, IO     | -           | MAR <- operand                 |
|       | T3   | RO, BI     | -           | B <- RAM                       |
|       | T4   | AI         | EO, SU, FI  | A <- A - B, flags              |
| STA   | T2   | MI, IO     | -           | MAR <- operand                 |
|       | T3   | RI, AO     | -           | RAM <- A                       |
| LDI   | T2   | IO, AI     | -           | A <- operand (zero-extended)  |
| JMP   | T2   | IO         | J           | PC <- operand                  |
| JC    | T2   | IO         | J           | PC <- operand, only where CF=1 |
| JZ    | T2   | IO         | J           | PC <- operand, only where ZF=1 |
| JNC   | T2   | IO         | J           | PC <- operand, only where CF=0 |
| JNZ   | T2   | IO         | J           | PC <- operand, only where ZF=0 |
| ADDI  | T2   | IO         | BI          | B <- operand (zero-extended)  |
|       | T3   | AI         | EO, FI      | A <- A + B, flags              |
| SUBI  | T2   | IO         | BI          | B <- operand (zero-extended)  |
|       | T3   | AI         | EO, SU, FI  | A <- A - B, flags              |
| DBL   | T2   | AO         | BI          | B <- A                         |
|       | T3   | AI         | EO, FI      | A <- A + B = 2*A, flags        |
| OUT   | T2   | AO, OI     | -           | display <- A                   |
| HLT   | T2   | HLT        | -           | stop the clock                  |

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

You can watch this table run on the machine: single-step a program
(STEP_MODE + STEP_PULSE, see [hardware.md](hardware.md)
"Front panel") and the T0..T6 and control-line LEDs light up exactly
the rows above, one per microstep. Example programs:
[programs.md](programs.md).

## Regenerating and injecting the ROMs

The workflow (export to ../roms/, write into Computer.dig, re-verify):
[tools.md](tools.md).
