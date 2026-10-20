# Ideas - what the machine is missing, and what it would take

What to add to the hardware, microcode, instruction set and assembler to
make more interesting programs possible - organized by cost, from things
that cost zero (a new ROM image) to things that cost a redesign. Everything
in tier 1 is verified feasible against the actual wiring and microcode;
the higher tiers are estimates.

The current limits (details in [instruction-set.md](instruction-set.md) and
the "Limits" section of [../programs/README.md](../programs/README.md)):
16 bytes of RAM (the address path, not the chips), one-byte instructions
with a 4-bit operand, no indirect addressing, flags only from ADD/SUB, no
shifts or bitwise ops, no runtime input, no stack - and a control word
whose 16 bits are all allocated.

## Tier 1: free - the five unused opcode slots (microcode only) - DONE

Opcodes 1001-1101 (9-D) were fetch-only NOPs - five wasted slots. All five
are now filled with no wiring at all, because the control ROMs are already
addressed by the flags (CF = A8, ZF = A9) and the operand path already
reaches the bus (IO drives the operand nibble zero-extended onto it):

| opcode | insn      | microsteps                             | what it buys |
|--------|-----------|----------------------------------------|--------------|
| 1001 9 | JNC addr  | T2 IO\|J, written into the CF=0 half   | jump if NOT carry - "strictly less" after a SUB |
| 1010 A | JNZ addr  | T2 IO\|J, written into the ZF=0 half   | jump if NOT zero - loop exits without a spare jump |
| 1011 B | ADDI imm  | T2 IO\|BI, T3 EO\|AI\|FI               | add a constant without a RAM cell |
| 1100 C | SUBI imm  | T2 IO\|BI, T3 EO\|SU\|AI\|FI           | subtract / compare against a constant, no cell |
| 1101 D | DBL       | T2 AO\|BI, T3 EO\|AI\|FI              | double A = shift left 1, CF = bit shifted out |

Why each is free:

- **JNC / JNZ**: JC's jump bytes exist only in the flag=1 half of the ROM
  image; the flag=0 half for the same step was empty. Writing the same
  T2 (IO|J) bytes into the *other* half is a jump on the inverted
  condition. (Both halves already existed in the image - the addressing
  sees to that.)
- **ADDI / SUBI**: the operand nibble is already drivable onto the bus
  (that is LDI's trick), and B loads from the bus - so an immediate can
  feed the ALU directly: IO|BI loads the zero-extended operand into B,
  then the normal ADD/SUB T3 runs. No `.DB` cell needed for constants.
- **DBL**: AO puts A on the bus, BI loads B from it, then the ADD T3
  computes A + B = 2*A with CF catching the bit shifted out - a
  shift-left built from two existing micro-ops.

A correction to the first draft of this table (kept as a lesson): it
proposed TAB ("copy A to B, a second working register") as slot D. That
instruction is **inert**: ADD/SUB always reload B from RAM at their T3
(RO|BI), so nothing would ever read the stored B - a TAB would sit there
until the next ADD/SUB overwrote it. A real second working register needs
an instruction that reads B without the RAM reload ("A <- A + B" fits the
same two microstep budget) - that is the candidate if slot D is ever
re-purposed; DBL was chosen instead because a shift is a whole capability
class, not just a register move.

Applied: microstep table in digrom.py, images re-exported to
[../roms/](../roms/), injected into Computer.dig (verified == presets),
mnemonics in asm.py, docs updated, and five new gallery programs
(step, decrement, powers, min, rol) verified with tools/sim.py. Timing
unchanged (all five fit in T2/T3); nothing existing breaks.

Free-adjacent (one wire, still undone): ROM address A10 is grounded and
the images are replicated across it. Wire A10 to a switch and the same two
ROMs hold two complete, switchable instruction sets - e.g. a normal set
and a debug set that OUTs different registers. The replication already
exists.

## Tier 2: wiring only (no new chips)

- **8 microsteps instead of 6**: DONE - the step counter now resets at the
  74138's O7 output (count 7): 8 cycles per instruction, 7 stable steps,
  5 usable work steps (T2-T6). On hardware: move the reset wire from 74138
  ~Y5 (pin 10) to ~Y7 (pin 7) at the 7400 gate; T5/T6 panel LEDs wire from
  ~Y5/~Y6. The ROM images are unchanged (rows 5-7 were already zero), so
  existing programs run identically, just 2 cycles slower. Applied to
  Computer.dig and the timing docs.
- **64 bytes of RAM from the chips already on the board**: the 74189s are
  64 words deep and A4/A5 are simply not connected. The catch: the MAR is
  4 bits and the operand nibble only names 0-15, so the extra space needs
  a page latch (one 74173 - but gating it needs a 17th control line, see
  tier 3) or a wider instruction format. The RAM chips are not the limit;
  the address path is.

## Tier 3: new chips (the real unlocks, in value order)

1. **A third control ROM** - the gateway item. The 16-bit control word is
   FULL: HLT MI RI RO IO II AI AO / EO SU BI OI CE CO J FI - every bit
   allocated, zero spare. Every remaining idea below that needs a new
   control line (SP increment, SP-to-MAR, IN gate, ADC mode, output-2)
   needs an eighth-plus signal, and the natural source is a third 28C16 -
   a part this repo already programs.
2. **Runtime input (IN)** - kills the biggest limit. The PROG_DATA
   dipswitches are already wired into the RAM's data path through the
   program-entry muxes; in run mode they are muxed out. One 74245 bus
   driver from the dipswitches + an IN opcode + one control line makes
   the panel readable while running: interactive programs, a calculator
   you can feed, games with a player.
3. **A stack (SP + CALL/RET + push/pop)** - the biggest program-structure
   unlock: subroutines, recursion, expression evaluation. Needs an
   up/down counter (74193) as SP and microsteps to load/store through it.
   On 16 bytes of RAM the stack has no room to exist - this item and the
   memory growth below are one project.
4. **Memory + addressing** - 2KB of code in a 28C16 (the part this repo
   already burns for the control ROMs) + 2KB SRAM for data and stack, an
   at-least-11-bit (practically 16-bit) MAR and PC, and a two-byte
   instruction format with wide operands. This is the C threshold - see
   [getting-to-c.md](getting-to-c.md).
5. **Indirect addressing** - a way to load the MAR from a register pair
   instead of a constant operand (a mux into the MAR's inputs + control
   lines). With 16 bytes it is pointless (patch.asm's manual operand
   rewrite is the current loophole); with kilobytes it is what arrays,
   pointers and stacks actually need.
6. **ALU upgrades**:
   - **ADC/SBC** (add/subtract with carry): the adders' carry-in is
     verified to be driven by SU - that is how SUB gets its +1. Feeding
     it SU OR CF instead (one gate + a control line) enables 16-bit
     arithmetic as byte pairs chained through CF - exactly the idiom a
     compiler emits for int.
   - **Real shifts**: rotate-through-carry already exists as software
     (rotate.asm); hardware shifts want an ALU output mux.
   - **Bitwise AND/OR/XOR**: the 7486 XOR gates already exist in the ALU
     but are wired as SU's invert-B path, not a data path. Real bitwise
     ops want a second result source (74LS151-class muxes) + control
     lines - again, ROM3 territory.
   - **A sign flag** (result bit 7 into a latch) is one wire once ROM3
     exists - and makes comparisons read more naturally.
7. **A second output register** (display B, or the MAR) - cheap once ROM3
   exists; makes more state visible while stepping.

## Tier 4: software only (no hardware at all)

- **tools/sim.py**: DONE - the cycle-accurate simulator. It loads the
  control-ROM images from roms/ and runs the microcode itself (fetch
  included, self-modifying code included), so it verifies the microcode,
  the ROM files and every program without the machine. All 21 gallery
  programs pass it, cross-checked against an independent ISA-level
  reference. The compiler test bench of
  [getting-to-c.md](getting-to-c.md) exists.
- **The Digital 0.31 74245 patch**: still pending - the known library bug
  that stops Computer.dig from simulating its shared bus. sim.py covers
  the ISA-level truth; a GUI-level run needs this patch.
- **Assembler**: DONE - .EQU named constants and 'c' char literals added,
  along with the tier-1 mnemonics. More (.DW for 16-bit values, .FILL)
  can wait until 16-bit data exists.
- **A microcode DSL**: the microstep table in digrom.py stays the source
  of truth; a tiny "LDA: MI,IO / RO,AI" notation would make future
  experiments painless - not needed yet.

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

## Suggested order

1. DONE - tier-1 opcodes + assembler update (zero wiring, better
   programs, five new gallery programs).
2. PARTLY DONE - tools/sim.py exists (the test bench); the 74245 patch
   is still pending.
3. The IN instruction (needs ROM3 + one 74245) - the machine becomes
   interactive.
4. Memory + addressing + stack - the big one; its plan is
   [getting-to-c.md](getting-to-c.md).
