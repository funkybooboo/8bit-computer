# Instruction set

The machine language executed by the computer in
[../digital/Computer.dig](../digital/Computer.dig). The wiring is pin-exact
against Ben Eater's reference design (his KiCad project, his schematics), and
the microcode that implements this instruction set is documented in
[microcode.md](microcode.md).

## Machine model

| unit      | width | notes                                                     |
|-----------|--------|-----------------------------------------------------------|
| data bus  | 8 bit  | exactly one driver at a time (tri-state)                  |
| A, B      | 8 bit  | general registers; the ALU reads both                     |
| ALU       | 8 bit  | add / subtract, with carry (CF) and zero (ZF) flags       |
| IR        | 8 bit  | instruction register: opcode nibble + operand nibble      |
| MAR       | 4 bit  | memory address register -> 2^4 = 16 RAM addresses         |
| PC        | 4 bit  | program counter                                           |
| RAM       | 16 x 8 | 2x 74189 (64x4) with only address lines A0-A3 wired       |
| output    | 8 bit  | register + multiplexed 7-segment display (decimal/hex)   |

Program and data share the same 16 bytes (von Neumann, one address space).
A "byte of RAM" can be an instruction, an operand constant, a variable, or
several of those at once if you arrange it.

## Encoding

Every instruction is exactly **one byte** and executes in exactly **6 clock
cycles**:

      bit:  7 6 5 4   3 2 1 0
            opcode    operand

The opcode nibble selects the instruction. The operand nibble is a RAM
address (0-15) for the memory and jump instructions, or a 4-bit immediate
for LDI. There is no second byte: the instruction register drives the
operand onto the bus's low four bits (with the high four bits driven as 0)
whenever a microstep needs it. That is why LDI can only load values 0-15
into A, and why larger constants must be built with ADD.

## Instructions

| opcode      | hex | mnemonic | operand | effect (RTL)                  | flags |
|-------------|-----|----------|---------|-------------------------------|-------|
| 0000        | 0   | NOP      | -       | (nothing; 6 idle cycles)      | -     |
| 0001        | 1   | LDA      | addr    | A <- M[addr]                  | -     |
| 0010        | 2   | ADD      | addr    | B <- M[addr]; A <- A + B      | CF,ZF |
| 0011        | 3   | SUB      | addr    | B <- M[addr]; A <- A - B      | CF,ZF |
| 0100        | 4   | STA      | addr    | M[addr] <- A                  | -     |
| 0101        | 5   | LDI      | imm     | A <- imm (0-15)               | -     |
| 0110        | 6   | JMP      | addr    | PC <- addr                    | -     |
| 0111        | 7   | JC       | addr    | if CF=1: PC <- addr           | -     |
| 1000        | 8   | JZ       | addr    | if ZF=1: PC <- addr           | -     |
| 1001 - 1101 | 9-D | (none)   | -       | unimplemented; act as NOP     | -     |
| 1110        | E   | OUT      | -       | display <- A                  | -     |
| 1111        | F   | HLT      | -       | stop the clock                | -     |

### Per-instruction notes

- **LDA / ADD / SUB / STA** - the operand is a RAM address, 0-15 (the MAR is
  4 bits; larger operand values would be truncated by the hardware, so the
  assembler rejects them).
- **ADD / SUB** - the only flag-setting instructions. Flags latch at the
  last microstep and persist until the next ADD or SUB.
- **SUB** - implemented as A + ~B + 1 through the adder (SU inverts B). The
  carry flag therefore means: CF=1 -> no borrow (A >= B); CF=0 -> a borrow
  happened (A < B). ZF=1 iff the result is 0 (A = B).
- **LDI** - loads the operand nibble, zero-extended, into A: A becomes
  0-15, top four bits 0.
- **JMP / JC / JZ** - the target is the operand nibble, 0-15 (the PC is 4
  bits). JC/JZ sample the flags at their second cycle; when the condition
  is false the instruction is an expensive NOP.
- **OUT** - displays **A**, not the operand. The output module's mode
  switch selects decimal or hex display.
- **HLT** - gates the clock off; the machine freezes in place until reset.
- **Opcodes 9-D** - decode to no control lines after fetch: they are safe
  but useless NOPs. There is no illegal-instruction trap on this machine.

## Execution

- Reset (or power-up): PC=0; execution starts at RAM address 0.
- Each instruction: 2 fetch cycles, up to 3 cycles of work, always padded
  to 6 (see [microcode.md](microcode.md)).
- The PC wraps 0-15: running off the end of RAM continues at address 0.
- Unwritten RAM bytes read as 0x00, which is NOP. A program that falls off
  its end will run through NOPs and wrap around to address 0 - so every
  program should end in a loop or HLT.

## Programming idioms and examples

Every instruction of the set is exercised by the example gallery,
[../programs/](../programs/README.md) - sixteen programs in three groups
(foundations, math, machine tricks), each with its expected display and
what to watch on the front panel. Which program shows what:

| idiom / instruction | shown by                                                  |
|---------------------|-------------------------------------------------------------|
| ADD on a `.DB` constant as an increment (no INC exists) | count.asm, memory.asm |
| SUB counts down; 0 - 1 = 255 (underflow builds big values) | countdown.asm |
| comparison without a compare instruction: SUB + JC as "jump if A >= B" | larger.asm |
| equality: ZF=1 after SUB (or ADD wrapping to 0) | countdown.asm |
| overflow detection: ADD sets CF on the wrap | overflow.asm |
| wrap-around counting with no conditional | count.asm |
| state kept in RAM (LDA/ADD/STA read-modify-write) | memory.asm, fib.asm |
| multiplication as a loop (r += x, y laps) | mul.asm |
| division / remainder as a loop (x -= y until x < y) | div.asm, mod.asm |
| Euclid's algorithm (greatest common divisor) | gcd.asm |
| search loops: "find y such that" with ZF as the hit test | half.asm |
| rotate-left through the carry (the shift the ISA lacks) | rotate.asm |
| self-modifying code (STA into the code region) | patch.asm |
| one operation setting both flags (255 + 1) | bothflags.asm |
| NOP as pacing filler (6 idle cycles) | countdown.asm |
| LDI's 0-15 limit worked around with `.DB` data + ADD/LDA | all of them |

What does not fit on this machine, and why (cellular automata, arrays,
interactive games, nested loops): [../programs/](../programs/README.md),
"Limits".

- Comparison: SUB sets ZF=1 iff equal, CF=1 iff A >= B (no borrow). Note
  SUB clobbers A - keep a copy in RAM first (STA) if you need it
  (larger.asm re-loads the winner from RAM instead).
- The ALU wraps modulo 256: 255 + 1 = 0, so counting loops need no
  end-of-range test; the wrap sets ZF at the same time if you do want it
  (count.asm runs on this).
- Since LDI can only load 0-15, larger constants are built with `.DB`
  data bytes plus ADD (or LDA), or - for values near 255 - by subtracting
  down from 0 (countdown.asm starts at 255 = 0 - 1).
- Flags change only on ADD and SUB - nothing else touches CF/ZF. A JZ
  three instructions after a SUB still reads that SUB's result (mul.asm
  leans on this); but a conditional reading a flag from before program
  start reads whatever the reset left there - put the SUB before the
  first test.
- **Self-modifying code is legal**: program and data share RAM, and STA
  can target a code address (patch.asm rewrites its own ADD's operand
  at run time). The machine has no memory protection - nothing stops a
  program from eating itself.
