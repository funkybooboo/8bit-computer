# Getting to C - how far this machine is from running C programs

The honest answer first: **C on this machine as it stands is impossible,
permanently** - a single C call frame plus the code for one statement is
more than this machine's entire 16 bytes. That is not a tuning problem;
the ISA and memory are the problem. But there is a credible, staged path:
a subset C compiler running on the host, emitting this repo's assembly
language, targeting an upgraded machine whose upgrades are exactly the
ones listed in [ideas.md](ideas.md) tier 3. The compiler itself needs no
new hardware at all and can be started now.

## What C needs, checked against what we have

| C needs | the standard's requirement | this machine | the gap |
|---------|---------------------------|--------------|---------|
| char    | 8 bits                    | 8 bits       | none |
| int     | at least 16 bits          | 8-bit ALU    | doable as byte pairs - needs ADC (carry-in chaining; see ideas.md tier 3) |
| pointers| addresses that can be computed | operands are 4-bit constants baked into instructions | indirect addressing - the structural gap |
| memory  | code + globals + stack; the smallest real programs are hundreds of bytes | 16 bytes, shared | 2 orders of magnitude |
| stack   | every call, every local   | none - no SP, no CALL/RET, no push/pop | SP + CALL/RET (ideas.md tier 3) |
| arithmetic | + - * / % all exist | + - in hardware, * / % as loops (mul/div/mod already written) | none, just slow |
| bitwise | & \| ^ ~ << >>           | none          | software emulation (rotate + carry + conditional); correct, ~100s of cycles per byte-op |
| control flow | if / while / for / functions | JMP JC JZ (+ JNC JNZ free, ideas.md tier 1) | functions = stack |
| output  | putchar                   | OUT           | none |
| input   | getchar                   | none at run time | the IN instruction (ideas.md tier 3) |

The compiler itself runs on the host - cross-compilation, like every
8-bit microcomputer of the era. This machine will never self-host a
compiler (a compiler needs tens of kilobytes); that is normal and fine.

## What "C" we mean: subset C (the Small-C class)

Full standard C is not the goal. The realistic target is the classic
Small-C dialect (the 1980 compiler that made C practical on 8080-class
8-bit machines):

- char and int (16-bit, built from byte pairs + ADC), pointers,
  one-dimensional arrays;
- functions with arguments, return values, recursion (the stack makes
  this natural);
- if / else, while, for, assignments, arithmetic, comparisons;
- bitwise ops and shifts as software routines;
- no floats, no structs, no typedef, no stdio - output is OUT
  (putchar-style), input is IN once it exists.

This is not a coincidence: an 8080 is 8-bit data with 16-bit addresses
and a hardware stack pointer - and the machine in
[ideas.md](ideas.md) tier 3 is exactly that shape. The upgrades C
demands are the upgrades an 8080 has. History already ran this
experiment: Small-C on 8080s is the proven minimum.

Why not just use gcc/LLVM/SDCC: their 8-bit backends assume
AVR/8080-class register sets and 16-bit addressing, and porting any of
them to a custom ISA is far more work than a small subset compiler whose
backend is this repo's own assembler - which already exists and already
has the listings, bits columns and disassembler a compiler needs for
debugging.

## The ladder - what each level buys

| level | what it is | C status |
|-------|-----------|----------|
| L0 (today) | 16 bytes, 11 instructions, assembler + 16 verified programs | impossible |
| L1 (free microcode, days) | ideas.md tier 1: JNC/JNZ/ADDI/SUBI/TAB | still impossible - 16 bytes is 16 bytes |
| L2 (wiring) | 64 bytes, 8 microsteps | still impossible |
| L3 (the C threshold - hardware project) | 2KB code ROM (a 28C16 - this repo already burns them) + 2KB SRAM; 16-bit MAR and PC; two-byte instructions; the third control ROM; SP + CALL/RET + push/pop; indirect load/store (MAR from a register pair); ADC | the machine can now express C's abstract machine |
| L4 (software, weeks) | the subset-C cross compiler on the host, emitting this repo's assembly; asm.py as the backend, sim.py as the test bench | C programs compile, run, and can be hand-checked against the gallery |
| L5 (polish) | IN (getchar), hardware shifts/bitwise, structs | comfort, not capability |

L3 is the long pole: it reworks the machine's spine - every address path,
the instruction format, the step budget, the control word. Practically
it is "build a second machine using everything learned from the first",
which is also what Ben Eater's own community builds after the 8-bit
computer. L4 does not need L3 to *start* (next section).

## What can start now, with zero new hardware

1. **tools/sim.py** - promote the ISA-level reference interpreter that
   already verified all 16 gallery programs into the toolkit. It runs
   any program in microseconds, handles self-modifying code, and is the
   compiler's test bench. Days.
2. **The ideas.md tier-1 opcodes + assembler update** - a better compiler
   target the same day, for free.
3. **The Digital 0.31 74245 patch** - otherwise even hand-written
   programs cannot run in the GUI (the known library bug).
4. **Write the compiler against sim.py + asm.py, with the L3 ISA defined
   on paper first.** The compiler is the biggest software piece of the
   project and needs no hardware; doing it first also produces, as a
   side effect, the exact demand list the hardware must satisfy
   (data-driven hardware design: the compiler tells you what L3 must
   provide).

## What the first C program will look like

    int gcd(int a, int b) {
        while (a != b)
            if (a > b) a = a - b;
            else b = b - a;
        return a;
    }
    void main() { out(gcd(252, 105)); }

This is exactly today's programs/gcd.asm (15 bytes), written by hand.
Compiled with a calling convention, it will be roughly 10x that - the
price of C. That price is the point: C exists for the thousand-line
program no one will hand-assemble into 16 bytes, and that program is
what forces L3 in the first place.

## Distances, honestly

- C on the current 16-byte machine: impossible, forever.
- Subset C compiling and running in the simulator: weeks, zero
  hardware (sim.py + tier-1 opcodes + the compiler).
- Subset C running on real (upgraded) hardware: the compiler plus the
  L3 rebuild - the hardware is the long pole, measured in a real
  electronics project, not an afternoon.
- Full standard C (floats, stdio, structs): not the goal on this
  architecture; its I/O is OUT and, someday, IN.
- Self-hosted C (the compiler running on the machine): never - tens of
  kilobytes; cross-compile forever, as the 8-bit era did.
