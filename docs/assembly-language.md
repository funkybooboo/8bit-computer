# Assembly language

The assembly language for the machine's instruction set
([instruction-set.md](instruction-set.md)), and its assembler,
[../tools/asm.py](../tools/asm.py).

The language is deliberately minimal and honest about the hardware: every
instruction is one byte with a 4-bit operand field, and **every statement
assembles to exactly one byte** (a `.DB` with n values emits n bytes). There
are no pseudo-instructions that expand, no expressions, no macros - if the
hardware cannot encode it, the assembler rejects it instead of inventing
something.

## Grammar

One statement per line; free-form whitespace:

    line       := [ label ":" ] [ statement ] [ ";" comment ]
    statement  := instruction | directive
    instruction:= mnemonic [ operand ]
    directive  := ".DB" value { "," value }
               |  ".ORG" address
               |  name ":" ".EQU" value
    operand    := number | label | equ-name
    number     := decimal | "0x" hex | "0b" binary | "'" char "'"

- Mnemonics and directives are case-insensitive (`LDA`, `lda`); labels are
  case-sensitive identifiers: `[A-Za-z_][A-Za-z0-9_]*`.
- A label marks the RAM address of the next emitted byte and may be used as
  an operand anywhere a number may (it resolves to that address).
- Labels may not shadow instruction names (`LDI:`, `out:`, `db:`, `org:` are
  all rejected).
- Comments start with `;` and run to end of line. Blank lines are free.

What each mnemonic's operand means, and the allowed range, is part of
the instruction definition: [instruction-set.md](instruction-set.md).
Out-of-range operands are errors, not truncations: the operand field is one
nibble, and larger constants must be built with ADD (see the programming
rules there). Numeric literals are legal
anywhere a label is - an address is just a number 0-15 (patch.asm's
`STA 1` writes to address 1, which happens to be one of its own
instructions); labels exist so the number does not have to be maintained
by hand.

## Directives

- `.DB value [, value ...]` - emit raw data bytes (constants, variables,
  tables). Values may be numbers 0-255, char literals or labels (label =
  its RAM address). Any byte value is legal, including instruction
  encodings - a data byte that is never jumped onto is inert (patch.asm
  goes further and builds an instruction byte at run time with LDI +
  ADD).
- `.ORG address` - set the address of the next emitted byte. Forward-only;
  a label on an `.ORG` line lands at the moved-to address. The address must
  be a numeric literal (labels are not known yet when `.ORG` is processed).
  patch.asm uses it for a real need: placing a data byte at an exact
  address so a run-time-built instruction byte encodes correctly.
- `name: .EQU value` - define a named constant. Usable anywhere a number
  may appear (instruction operands, `.DB` values); the value must be a
  numeric or char literal resolved immediately (labels are addresses,
  `.EQU` names are values - they never occupy a RAM byte). min.asm and
  decrement.asm use `.EQU` for their thresholds; the alternative is a
  magic number in every instruction.

## Program model and limits

- The default memory is **16 bytes** (`--mem-size`), the machine's whole RAM;
  program and data share it.
- Unwritten bytes read as 0x00 = NOP; execution starts at address 0 and the
  PC wraps at 15. End every program with a loop or HLT (see
  [instruction-set.md](instruction-set.md), "Execution").
- Data is just bytes: nothing distinguishes it from code except that a jump
  never lands on it. Keep data at the end, after the code, and reference it
  by label.

## Example

[../programs/count.asm](../programs/count.asm) - count 0..255 forever:

        LDI 0        ; A = 0 (the counter)
loop:   OUT          ; display A
        ADD one      ; A = A + 1 (wraps 255 -> 0)
        JMP loop
one:    .DB 1        ; the constant +1

    ADDR  BYTE  ADDRESS    OPCODE     PARAM    SOURCE
    ----  ----  ----       ----       ----     --------
    00    50    0 0 0 0    0 1 0 1    0 0 0 0  LDI 0
    01    e0    0 0 0 1    1 1 1 0    0 0 0 0  loop: OUT
    02    24    0 0 1 0    0 0 1 0    0 1 0 0  ADD one
    03    61    0 0 1 1    0 1 1 0    0 0 0 1  JMP loop
    04    01    0 1 0 0    0 0 0 0    0 0 0 1  one: .DB 1

The listing's bits column is the instruction in straight ones and zeros,
in the three groups of four that matter to the hardware: the RAM address
of the byte, then the opcode nibble, then the operand nibble. These are
exactly the dipswitch groups for program entry (and the opcode table in
[instruction-set.md](instruction-set.md)). For `.DB` bytes the opcode and
operand groups are simply the byte's two nibbles - data has no opcode.

The full example gallery - every instruction, both flags, both wrap
directions, self-modifying code, and the machine's practical limits - is
[programs.md](programs.md).

Command-line usage (image formats, listings, the disassembler):
[tools.md](tools.md). Loading a program into the machine (the front
panel's program-entry dipswitches): [hardware.md](hardware.md),
"Front panel".

## Style conventions

- Labels flush at column 0, instructions indented (one tab or 8 spaces),
  one statement per line.
- Name every data constant and reference it by label (`ADD one`), never a
  bare address.
- Comments explain *why*, not *what* the mnemonic already says.
- Initialize: do not rely on power-up state; start programs with explicit
  `LDI`/`LDA` initialization of what they use.
