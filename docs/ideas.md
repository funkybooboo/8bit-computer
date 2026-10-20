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

## Tier 1: free - the five unused opcode slots (microcode only)

Opcodes 1001-1101 (9-D) currently decode to nothing after fetch - five
wasted slots. All five can be filled with no wiring at all, because the
control ROMs are already addressed by the flags (CF = A8, ZF = A9) and the
operand path already reaches the bus (IO drives the operand nibble
zero-extended onto it):

| opcode | proposed  | microsteps                             | what it unlocks |
|--------|-----------|----------------------------------------|-----------------|
| 1001 9 | JNC addr  | T2 IO\|J, written into the CF=0 half   | jump if NOT carry - inverted conditionals |
| 1010 A | JNZ addr  | T2 IO\|J, written into the ZF=0 half   | jump if NOT zero |
| 1011 B | ADDI imm  | T2 IO\|BI, T3 EO\|AI\|FI               | immediate operands without a RAM cell |
| 1100 C | SUBI imm  | T2 IO\|BI, T3 EO\|SU\|AI\|FI           | - " - |
| 1101 D | TAB       | T2 AO\|BI                              | copy A to B - a second working register |

Why each is free:

- **JNC / JNZ**: JC's jump bytes exist only in the flag=1 half of the ROM
  image; the flag=0 half for the same step is empty. Writing the same
  T2 (IO|J) bytes into the *other* half is a jump on the inverted
  condition. (Both halves already exist in the image - the addressing
  sees to that.)
- **ADDI / SUBI**: the operand nibble is already drivable onto the bus
  (that is LDI's trick), and B loads from the bus - so an immediate can
  feed the ALU directly: IO|BI loads the zero-extended operand into B,
  then the normal ADD T3 runs. No `.DB` cell needed for constants.
- **TAB**: AO puts A on the bus and BI loads B from it. B finally becomes
  loadable from something other than RAM - a scratch register.

What they buy in practice: inverted conditionals (no more "burn 6 cycles
when the flag is the wrong polarity"), constants without spending RAM
bytes (countdown.asm and mul.asm lose their `one` cell), and two-operand
code (B as a temp). Cost: edit the microstep table in
[../tools/digrom.py](../tools/digrom.py), re-export the ROM images,
re-inject them, add the mnemonics to [../tools/asm.py](../tools/asm.py),
update the docs. Timing stays 6 cycles; nothing existing breaks (9-D are
NOPs today).

Free-adjacent (one wire): ROM address A10 is grounded and the images are
replicated across it. Wire A10 to a switch and the same two ROMs hold two
complete, switchable instruction sets - e.g. a normal set and a debug set
that OUTs different registers. The replication already exists.

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

- **tools/sim.py**: promote the ISA-level reference interpreter (the
  throwaway that verified all 16 gallery programs) into the toolkit.
  Runs any program in microseconds, handles self-modifying code, and is
  the test bench a compiler needs
  ([getting-to-c.md](getting-to-c.md)).
- **The Digital 0.31 74245 patch**: the known library bug that stops
  Computer.dig from simulating its shared bus - patching a local
  74245.dig means programs actually run in the GUI at all.
- **Assembler**: .EQU named constants, character literals, .DW / .FILL
  data directives, more listing options. All local to asm.py.
- **A microcode DSL**: the microstep table in digrom.py is the source of
  truth; a tiny "LDA: MI,IO / RO,AI" notation would make tier-1
  experiments painless.

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

1. Tier-1 opcodes + assembler update - days, zero wiring, immediately
   better programs.
2. tools/sim.py + the 74245 patch - the test bench.
3. The IN instruction (needs ROM3 + one 74245) - the machine becomes
   interactive.
4. Memory + addressing + stack - the big one; its plan is
   [getting-to-c.md](getting-to-c.md).
