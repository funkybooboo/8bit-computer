# Instruction set

The machine language the machine executes in
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
| RAM       | 16 x 8 | 2x 74189 (16x4 each) - the chips, not the wiring, cap it  |
| output    | 8 bit  | register + multiplexed 7-segment display (decimal/hex)   |

Program and data share the same 16 bytes (von Neumann, one address space).
A "byte of RAM" can be an instruction, an operand constant, a variable, or
several of those at once if you arrange it.

## Encoding

Every instruction is exactly **one byte** and executes in exactly **8 clock
cycles** (fixed-length timing; see
[microcode.md](microcode.md) for the step-by-step breakdown):

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
| 0000        | 0   | NOP      | -       | (nothing; 8 idle cycles)      | -     |
| 0001        | 1   | LDA      | addr    | A <- M[addr]                  | -     |
| 0010        | 2   | ADD      | addr    | B <- M[addr]; A <- A + B      | CF,ZF |
| 0011        | 3   | SUB      | addr    | B <- M[addr]; A <- A - B      | CF,ZF |
| 0100        | 4   | STA      | addr    | M[addr] <- A                  | -     |
| 0101        | 5   | LDI      | imm     | A <- imm (0-15)               | -     |
| 0110        | 6   | JMP      | addr    | PC <- addr                    | -     |
| 0111        | 7   | JC       | addr    | if CF=1: PC <- addr           | -     |
| 1000        | 8   | JZ       | addr    | if ZF=1: PC <- addr           | -     |
| 1001        | 9   | JNC      | addr    | if CF=0: PC <- addr           | -     |
| 1010        | A   | JNZ      | addr    | if ZF=0: PC <- addr           | -     |
| 1011        | B   | ADDI     | imm     | B <- imm; A <- A + B          | CF,ZF |
| 1100        | C   | SUBI     | imm     | B <- imm; A <- A - B          | CF,ZF |
| 1101        | D   | DBL      | -       | B <- A; A <- A + B (= 2*A)    | CF,ZF |
| 1110        | E   | OUT      | -       | display <- A                  | -     |
| 1111        | F   | HLT      | -       | stop the clock                | -     |

Opcodes 9-D are **this project's additions** (see [additions.md](additions.md),
"Added: five opcodes" - filled with microcode only, no wiring changes; the original Ben
Eater set is 0-8, E, F). An older ROM image burns those opcodes as NOPs.

### Per-instruction notes

- **LDA / ADD / SUB / STA** - the operand is a RAM address, 0-15 (the MAR is
  4 bits; larger operand values would be truncated by the hardware, so the
  assembler rejects them).
- **ADD / SUB / ADDI / SUBI / DBL** - the flag-setting instructions. Flags
  latch at the last microstep and persist until the next one of them.
- **SUB** - implemented as A + ~B + 1 through the adder (SU inverts B). The
  carry flag therefore means: CF=1 -> no borrow (A >= B); CF=0 -> a borrow
  happened (A < B). ZF=1 iff the result is 0 (A = B).
- **LDI** - loads the operand nibble, zero-extended, into A: A becomes
  0-15, top four bits 0.
- **JMP / JC / JZ / JNC / JNZ** - the target is the operand nibble, 0-15
  (the PC is 4 bits). The conditional jumps sample the flags at their
  second cycle; when the condition is false the instruction is an
  expensive NOP. JNC/JNZ are the inverted forms: after a SUB, JNC means
  "strictly less" and JNZ means "not equal" - loop idioms no longer need
  a spare jump around a jump.
- **ADDI / SUBI** - immediate forms of ADD/SUB: the operand nibble (0-15,
  zero-extended) feeds the ALU directly instead of a RAM cell, so loops can
  step and compare against constants without spending a byte of RAM on
  them (decrement.hl, min.hl, step.hl).
- **DBL** - doubles A through the ALU (B <- A, then A <- A + B): a
  shift-left-1 instruction, with CF catching the bit shifted out. DBL +
  JNC + ADDI 1 is a rotate-left-through-carry in three instructions
  (rol.hl, and bits.hl streams a byte's bits through the display with
  it), and a doubling loop ends itself on the wrap (powers.hl). The
  operand nibble is ignored (the assembler emits 0).
- **OUT** - displays **A**, not the operand. The output module's mode
  switch selects decimal or hex display.
- **HLT** - gates the clock off; the machine freezes in place until reset.

## Execution

- Reset (or power-up): PC=0; execution starts at RAM address 0.
- Each instruction: 2 fetch cycles, up to 5 cycles of work, always padded
  to 8 (see [microcode.md](microcode.md)).
- The PC wraps 0-15: running off the end of RAM continues at address 0.
- Unwritten RAM bytes read as 0x00, which is NOP. A program that falls off
  its end will run through NOPs and wrap around to address 0 - so every
  program should end in a loop or HLT.

## Programming rules of the road

Every instruction is exercised by the example gallery - twenty-five
programs in three groups, each with its expected display:
[programs.md](programs.md). What that does not fit on this machine, and
why (cellular automata, arrays, interactive games, nested loops): the
same document, "Limits".

- Comparison: SUB sets ZF=1 iff equal, CF=1 iff A >= B (no borrow). Note
  SUB clobbers A - keep a copy in RAM first (STA) if you need it
  (larger.hl re-loads the winner from RAM instead), or let the wrapped
  subtraction restore itself when the compare value is a .DB constant
  (SUB k, test the flags, ADD k - odometer.hl).
- The ALU wraps modulo 256: 255 + 1 = 0, so counting loops need no
  end-of-range test; the wrap sets ZF at the same time if you do want it
  (count.hl runs on this).
- Since LDI can only load 0-15, larger constants are built with `.DB`
  data bytes plus ADD (or LDA), or - for values near 255 - by subtracting
  down from 0 (countdown.hl starts at 255 = 0 - 1).
- Flags change only on ADD, SUB, ADDI, SUBI and DBL - nothing else touches
  CF/ZF. A JZ three instructions after a SUB still reads that SUB's result
  (mul.hl leans on this); but a conditional reading a flag from before
  program start reads whatever the reset left there - put the SUB before
  the first test.
- **Self-modifying code is legal**: program and data share RAM, and STA
  can target a code address (patch.hl rewrites its own ADD's operand
  at run time). The machine has no memory protection - nothing stops a
  program from eating itself.
