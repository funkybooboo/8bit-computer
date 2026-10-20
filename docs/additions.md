# Additions to Ben Eater's computer

This machine is Ben Eater's 8-bit breadboard computer
(https://eater.net/8bit) - his circuit design, built here in Digital from
his schematics and verified pin-exact against his KiCad project
([hardware.md](hardware.md)). This document is the delta: what this
build adds on top of his design - the additions already made, and every
avenue still available, organized by cost, from a new ROM image (zero
wiring) to a redesign.

The machine's current limits are documented where they belong:
[instruction-set.md](instruction-set.md) (what the ISA can express),
[programs.md](programs.md) "Limits" (what fits in 16 bytes),
[hardware.md](hardware.md) (what is wired where).

Two structural facts bound everything below:

- The 16-bit control word is fully allocated (HLT MI RI RO IO II AI AO /
  EO SU BI OI CE CO J FI) - every new control line needs a third control
  ROM ([microcode.md](microcode.md)).
- The RAM is 16 bytes of silicon (two 74189s, 16 words x 4 bits each -
  there are no A4/A5 pins), and the instruction operand is a 4-bit
  nibble - so more memory means new chips *and* a page scheme, not just
  wires ([hardware.md](hardware.md), RAM module).

## Added: 8-cycle instructions

Ben's control unit resets the microstep counter at step 5: every
instruction runs 6 cycles, of which 3 are work steps. This build resets
at step 7: every instruction runs 8 cycles, of which 5 are work steps
(T2-T6) - room for longer instructions without a redesign. The
mechanism and the timing story: [microcode.md](microcode.md), "Timing".
On hardware it is one wire (74138 ~Y5 pin 10 -> ~Y7 pin 7).

## Added: five opcodes

Ben's instruction set defines opcodes 0-8, E, F and leaves slots 9-D
undefined - a machine burning his original ROM images executes them as
NOPs. This build fills all five (full definitions and per-instruction
notes: [instruction-set.md](instruction-set.md)):

- **JNC / JNZ** (9 / A) - the inverted conditional jumps: after a SUB,
  JNC means "strictly less" and JNZ means "not equal", so loop idioms no
  longer need a spare jump around a jump. They live in the flag=0
  halves of the ROM images - halves his microcode leaves empty.
- **ADDI / SUBI** (B / C) - immediate ADD/SUB: the operand nibble feeds
  the ALU directly instead of a RAM cell, so loops can step and
  compare against constants without spending a byte of RAM on them.
- **DBL** (D) - shift A left one bit through CF (B <- A, then
  A <- A + B): a rotate-left-through-carry in three instructions, and a
  doubling loop that ends itself on the wrap.

None of them needed wiring: the control ROMs are already addressed by
the flags, and the operand nibble and the A register already reach the
bus ([microcode.md](microcode.md), "ROM addressing" and
"Per-instruction microsteps").

One slot-D constraint worth knowing before re-purposing it: an
instruction that only copies A into B is inert - ADD/SUB always reload B
from RAM at their T3 (RO|BI), so nothing reads the stored B. A real
second working register needs "A <- A + B" (reads B without the RAM
reload, same microstep budget).

## Added: the software

The design is hardware: it ships as schematics and EEPROM data. This
repo adds the machine's whole software side - the machine's own
definitions, an assembler and disassembler, a cycle-accurate simulator
that runs the real control-ROM images, the EEPROM tooling with archived
images, and a gallery of 25 verified programs exercising every
instruction ([tools.md](tools.md), [programs.md](programs.md)).

## Microcode only

What a new ROM image alone can still buy (no wiring):

- **Two switchable instruction sets**: control-ROM address A10 is
  grounded and the images are replicated across it. Wire A10 to a
  switch (one wire) and the same two ROMs hold two complete
  instruction sets - e.g. a normal set and a debug set.

## Wiring + RAM chips (no new control lines)

**64 bytes of RAM, four pages of 16** - the plan, researched against
the circuit (every "unused" pin claim verified in Computer.dig):

- The RAM needs new silicon: the 74189s are 16 words x 4 bits each
  (64 *bits* per chip - there are no A4/A5 pins to wire), so the
  same-chips path is four banks of 16 bytes: six more 74189s plus one
  74139 decoding RAM bits 4-5 onto the four banks' ~CS. The data,
  write and bus paths (U26/U27 entry muxes, U31/U32 write pulse,
  U28/U29 inverters, U30 transceiver) are shared by all banks as-is.
  The one-chip path is a 2KB SRAM (6116) - the direction of "New
  chips" item 4, which merges the data-in and data-out paths (the
  6116's I/O pins are bidirectional) and reworks the module's plumbing.
- The address path widens with no 17th control line: one more 74161 as
  the PC's bits 4-5, chained off U35's unused RCO and never loaded
  (jumps stay in their own page); one more 74173 as the MAR's bits 4-5
  on the existing MI gate, latching from the bus (fetch addresses reach
  all 64); CO extended onto bus bits 4-5 through the PC transceiver's
  unused pins; program entry through U32's spare mux sections plus two
  more PROG_ADDR dipswitch bits.
- The 4-bit operand nibble already decides the semantics: **zero-page
  data, in-page jumps, linear code**. The IR grounds the bus's high
  nibble while driving the operand (the same wiring that zero-extends
  immediates), so LDA/ADD/SUB/STA address page 0 forever; J loads only
  PC bits 0-3, so a jump reaches its own 16-byte page; execution flows
  linearly through all 64 bytes and wraps at 63. The classic
  zero-page architecture - and every existing program (all <= 16
  bytes, page 0) keeps its exact behavior.
- What it buys: 48-60 bytes of code with 16 bytes of zero-page data -
  nested loops fit, so the size-locked family (popcount, sqrt, sum 1..n,
  exponentiation - [programs.md](programs.md) "Limits") becomes
  writable. No microcode change: MI, CO, J, CE, RO, RI just drive
  wider registers.
- One silicon detail to check at build time: the banks share the Q
  nets, so the 74189 variant must tri-state on ~CS (74LS189 does; a
  plain 7489 is open-collector and wants pull-ups).

## New chips (in value order)

1. **A third control ROM** - the gateway item: every remaining idea
   that needs a new control line needs this first.
2. **Runtime input (IN)** - kills the biggest limit. The PROG_DATA
   dipswitches are already wired into the RAM's data path through the
   program-entry muxes; in run mode they are muxed out. One 74245 bus
   driver from the dipswitches + an IN opcode + one control line makes
   the panel readable while running: interactive programs, a calculator
   you can feed, games with a player.
3. **A stack (SP + CALL/RET + push/pop)** - subroutines, recursion,
   expression evaluation. Needs an up/down counter (74193) as SP and
   microsteps to load/store through it. On 16 bytes of RAM the stack
   has no room - this and the memory growth below are one project.
4. **Memory + addressing** - 2KB of code in a 28C16 (the part this repo
   already burns) + 2KB SRAM for data and stack, a 16-bit MAR and PC, a
   two-byte instruction format with wide operands. This is the C
   threshold: [getting-to-c.md](getting-to-c.md).
5. **Indirect addressing** - load the MAR from a register pair instead
   of a constant operand (a mux into the MAR's inputs + control lines).
   With 16 bytes it is pointless (patch.asm's manual operand rewrite is
   the loophole); with kilobytes it is what arrays, pointers and stacks
   need.
6. **ALU upgrades**:
   - **ADC/SBC**: the adders' carry-in is driven by SU (that is how SUB
     gets its +1 - [hardware.md](hardware.md), ALU). Feeding it SU OR CF
     instead (one gate + a control line) enables 16-bit arithmetic as
     byte pairs chained through CF.
   - **Real shifts**: rotate-through-carry exists as software
     (rotate.asm); hardware shifts want an ALU output mux.
   - **Bitwise AND/OR/XOR**: the 7486 XOR gates already exist in the ALU
     but are wired as SU's invert-B path, not a data path. Real bitwise
     ops want a second result source + control lines - ROM3 territory.
   - **A sign flag** (result bit 7 into a latch): one wire once ROM3
     exists.
7. **A second output register** (display B, or the MAR): cheap once
   ROM3 exists.

## Software only

- The assembler could grow `.DW` (16-bit data) and `.FILL` - pointless
  until 16-bit data exists ([assembly-language.md](assembly-language.md)).
- The microcode's source of truth is MICROSTEPS in tools/machine.py,
  written in the "LDA: MI,IO / RO,AI" notation ([tools.md](tools.md)) -
  experiments there are painless already.

## Not worth it (honest)

- Interrupts/DMA: no devices to interrupt, nothing that needs the
  latency.
- Floating point: soft-float is thousands of bytes; this is an integer
  machine (fixed point is the idiom).
- Rebuilding the datapath at 16 bits: do 16-bit work as byte pairs
  chained through CF - what every 8-bit CPU actually did.
- Self-hosting tools (assembler or compiler running on the machine):
  needs tens of kilobytes; cross-compile forever
  ([getting-to-c.md](getting-to-c.md)).

## Highest value next

1. The IN instruction (needs ROM3 + one 74245) - the machine becomes
   interactive.
2. Memory + addressing + stack - the big one; its plan is
   [getting-to-c.md](getting-to-c.md).
