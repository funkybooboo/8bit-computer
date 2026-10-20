# Architecture

What this machine is, how its parts fit together, and why it is a real
computer. The parts and every wire: [hardware.md](hardware.md). The control
signals and microcode: [microcode.md](microcode.md). The instructions:
[instruction-set.md](instruction-set.md).

The machine is Ben Eater's 8-bit breadboard computer
(https://eater.net/8bit), built here in the Digital logic simulator
([../digital/Computer.dig](../digital/Computer.dig)) from 74xx-series
parts: an 8-bit von Neumann computer with 16 bytes of RAM, whose every
part is a chip you can buy, wired the way real 1970s computers were
wired.

## The block diagram

                     +---------+
                     |  clock  |  one edge at a time, gated by HLT
                     +----+----+
                          |
                          v
    +-----------------------------------------------------------+
    |                    control unit (U47-U53)                 |
    |  microstep counter -> ROM lookup -> 16 control lines       |
    +----+---------------+---------+--------------+------------+
         |               |         |              |
        MI|RO            AI|BI     CE|J           OI|HLT ... (16 lines)
         v               v         v              v
    +---------+     +---------+ +------+    +-----------+
    | MAR/PC  |     | A / B / | | PC   |    | output    |
    +----+----+     | IR /OUT | +------+    | register  |
         |          +----+----+             +-----+-----+
         v               |                        |
    +---------+           | 8-bit shared bus       |
    | RAM 16B |<==========+=========================+
    +---------+     (exactly one driver at a time)

Every part hangs off one 8-bit bus, and the control unit decides, every
clock cycle, which single part drives the bus and which single part
latches it. That is the whole machine.

## The theory

**The bus.** Eight wires, and a rule: at most one driver, at most one
latch, per cycle. Everything else - registers, RAM, ALU, display - is a
box with a connection to the bus and a "load me" or "drive me" signal.
The 74245 transceivers make the "drive me" possible (tri-state outputs,
or the bus could never be shared); the 74173 registers make the "load
me" possible (they latch on the clock edge only when enabled).

**Stored program (von Neumann).** The 16 bytes of RAM hold code *and*
data in one address space. Nothing distinguishes them: a byte is an
instruction only because the program counter points at it when it is
fetched. The flip side is self-modification - a program can write over
its own instructions ([programs.md](programs.md), patch.asm) - which is
legal because there is no protection, which is the same thing a 1970s CPU
gave you.

**Fetch, decode, execute.** Every 8 clock cycles the machine does the
same two-step opening: T0 puts the PC on the bus and latches it into the
MAR; T1 reads the RAM byte at the MAR into the instruction register and
increments the PC. From then on the instruction's opcode nibble (the top
4 bits now sitting in the IR) is the machine's *decision*: it selects a
row in the control ROMs, and that row is the instruction.

**Microcode.** The control unit is not magic: it is a counter and two
EEPROMs. The counter (a 74161) counts microsteps T0..T7; the ROMs are
addressed by (microstep, opcode, CF, ZF) and output the 16 control lines.
So "what ADD means" is literally: rows (2,ADD) through (4,ADD) of a ROM
image. This is how "an instruction" physically exists. Real CPUs work
this way too - microcode is not a metaphor here, it is two 2KB EEPROMs
you can read ([microcode.md](microcode.md)).

**Flags, and with them, decisions.** The ALU produces a sum and, on the
same instruction, two one-bit side effects: carry (CF) and zero (ZF),
latched into a flag register. The flags feed the control ROMs' address
lines, so the *next* instruction can be a different one depending on data
the machine computed earlier. Conditional jump = data-dependent ROM row =
branching. That is the hinge that makes it a computer and not a fixed
sequence: with conditional branching, arithmetic, and memory you have
everything needed to compute anything computable - bounded here only by
the 16 bytes of RAM.

**Timing.** Fixed-length: every instruction takes 8 cycles whether it
needs them or not (T0/T1 fetch, T2..T6 work, T7 resets the step counter).
Simplicity over speed - the classic microcoded trade.

## Why this is a real computer

Not "real" as in "a toy that resembles one": it has every essential part,
and each part works the way the corresponding part of a commercial CPU
works:

- a **stored program** it reads and obeys from memory, changing nothing
  but memory to change behavior;
- an **ALU** doing real arithmetic (the same adder-with-invert-B trick
  real CPUs use for subtraction, carry included);
- **registers** and a **flag** word whose meanings a programmer depends on;
- **conditional control flow** - the if, from which while and for follow;
- **I/O**: a display register driven by a program (and a front panel for
  entering programs into memory by hand, exactly how real machines were
  loaded);
- a **control unit** built as microcode ROM - same idea as the x86's
  decode unit, small enough to hold in your head.

The only joke it makes is the memory: 16 bytes - exactly what two
16-word chips make, and the 4-bit operand only names 16 addresses
anyway (what more memory really costs: [additions.md](additions.md)). Inside its memory it computes
real things: multiplication, division, gcd, pseudorandom sequences,
self-modifying code ([programs.md](programs.md)). Give the same design
a wider address path and it stops being a toy without changing its soul.

## The parts

Each in one paragraph; pins and wires in [hardware.md](hardware.md).

- **Clock module** - a clock source and gating logic. It produces the
  one edge everything steps on, and respects two masters: HLT (a program
  saying "stop") and the manual STEP_MODE/STEP_PULSE front panel
  controls. Everything is synchronous to this one edge.
- **Program counter (PC)** - a 4-bit counter (74161). It always holds the
  address of the *next* instruction byte; CE increments it at fetch T1,
  J loads it when a jump is taken. It wraps 0..15.
- **Memory address register (MAR) + RAM** - the MAR latches an address
  from the bus (MI); the RAM (two 74189s) is 16 addressable bytes whose
  data pins reach the bus through a transceiver (RO to read out; RI plus
  a write pulse to store). Program entry from the front panel muxes its
  way into the same address/data/write paths, which is why the panel can
  load RAM without being part of the datapath.
- **Instruction register (IR)** - the byte currently executing. Its top
  nibble addresses the control ROMs (it *is* the opcode); its bottom
  nibble can be driven onto the bus low-four-bits (IO) so an instruction
  can carry its own operand or immediate.
- **A and B registers** - the working registers. A is the accumulator
  (what OUT displays, what the ALU reads and writes); B is the ALU's
  second input, loaded from RAM/immediately per instruction. Both latch
  from the bus and drive the bus through transceivers (AO; B drives only
  the ALU).
- **ALU** - two 4-bit adders (74283) chained into 8 bits, with XOR gates
  that invert B and a carry-in +1 when SU (subtract) - so SUB is
  literally A + ~B + 1, and CF is the carry-out (which after a SUB
  reads as "no borrow", the flag every comparison on this machine is
  built on). A NOR/AND tree watches the sum for zero (ZF). The flag
  register (74173) latches CF/ZF when FI.
- **Output register** - an 8-bit latch (OI) plus a ROM-driven
  multiplexed 4-digit seven-segment display: the ROM converts the byte
  into digit patterns (decimal or hex, front-panel switch), a 2-bit
  counter rotates through the digits fast enough to look steady. This is
  the machine's stdout.
- **Control unit** - the counter + decoder + two EEPROMs + inverters of
  [microcode.md](microcode.md): it turns (microstep, opcode, flags) into
  the 16 control lines, and resets itself after T7.

## One instruction, cycle by cycle

ADD 5 ("A <- A + M[5]") as the bus sees it (microcode rows in
[microcode.md](microcode.md); control-line meanings in
[hardware.md](hardware.md)):

| step | control lines on | bus carries | what latches |
|------|------------------|-------------|---------------|
| T0 | MI, CO | the PC | MAR <- PC (the address of ADD 5) |
| T1 | RO, II, CE | RAM[MAR] = the ADD 5 byte | IR <- ADD 5; PC <- PC+1 |
| T2 | MI, IO | the operand nibble, 5 | MAR <- 5 |
| T3 | RO, BI | RAM[5] | B <- M[5] |
| T4 | EO, AI, FI | A + B (the ALU output) | A <- A + B; CF/ZF <- result |
| T5 | - | - | idle |
| T6 | - | - | idle |
| T7 | - | - | transient: resets the step counter |

Then T0 of the next instruction, with the PC already pointing at it.
Multiply that by any program in [programs.md](programs.md) and that is
the machine running: a fixed 8-cycle heartbeat, ROM rows steering one
bus transfer at a time, forever - until a HLT row gates the clock off.
