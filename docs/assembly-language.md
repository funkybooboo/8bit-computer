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
    directive  := ".DB" value { "," value }  |  ".ORG" address
    operand    := number | label
    number     := decimal | "0x" hex | "0b" binary

- Mnemonics and directives are case-insensitive (`LDA`, `lda`); labels are
  case-sensitive identifiers: `[A-Za-z_][A-Za-z0-9_]*`.
- A label marks the RAM address of the next emitted byte and may be used as
  an operand anywhere a number may (it resolves to that address).
- Labels may not shadow instruction names (`LDI:`, `out:`, `db:`, `org:` are
  all rejected).
- Comments start with `;` and run to end of line. Blank lines are free.

## Operand rules (mirror the hardware)

| mnemonics               | operand means   | allowed range | why                     |
|-------------------------|-----------------|---------------|--------------------------|
| LDA, ADD, SUB, STA      | RAM address     | 0-15          | the MAR is 4 bits        |
| LDI                     | immediate       | 0-15          | the operand is one nibble, loaded zero-extended into A |
| JMP, JC, JZ             | target address  | 0-15          | the PC is 4 bits         |
| NOP, OUT, HLT           | (none)          | -             | -                        |

Out-of-range operands are errors, not truncations: the operand field is one
nibble, and larger constants must be built with ADD (see idioms in
[instruction-set.md](instruction-set.md)). Numeric literals are legal
anywhere a label is - an address is just a number 0-15 (patch.asm's
`STA 1` writes to address 1, which happens to be one of its own
instructions); labels exist so the number does not have to be maintained
by hand.

## Directives

- `.DB value [, value ...]` - emit raw data bytes (constants, variables,
  tables). Values may be numbers 0-255 or labels (label = its RAM address).
  Any byte value is legal, including instruction encodings - the
  undefined opcodes 9-D execute as NOPs, so `.DB 0x9F` is a legal, if
  unusual, no-op byte (patch.asm goes further and builds an instruction
  byte at run time with LDI + ADD).
- `.ORG address` - set the address of the next emitted byte. Forward-only;
  a label on an `.ORG` line lands at the moved-to address. The address must
  be a numeric literal (labels are not known yet when `.ORG` is processed).
  patch.asm uses it for a real need: placing a data byte at an exact
  address so a run-time-built instruction byte encodes correctly.

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

The full example gallery - sixteen programs in three groups (foundations,
math, machine tricks) that together exercise every instruction, both
flags, both wrap directions, self-modifying code and the practical limits
of the machine, each with its expected display - is
[../programs/](../programs/README.md).

## Usage

    tools/asm.py programs/count.asm                       # listing to stdout
    tools/asm.py programs/count.asm --out prog.hex --lst prog.lst
    tools/asm.py programs/count.asm --out prog.bin --format raw
    tools/asm.py --dis prog.hex                           # disassemble an image
    tools/asm.py --dis prog.hex --all                     # ... including trailing NOPs

- `--out` writes the assembled image; `--format` selects `logisim`
  (default; the "v2.0 raw" format Digital's ROM editor loads), `intel`
  (Intel HEX) or `raw` binary. Formats are shared with digrom.py.
- `--lst FILE` writes the listing to a file instead of stdout. The
  listing shows hex and the address|opcode|operand bits column (see
  the example above).
- `--dis` disassembles an image (format sniffed); undefined opcodes and data
  print as `.DB 0xNN`. A disassembler cannot know which bytes are data - it
  decodes every byte linearly.

## Loading a program into the machine

The RAM has no stored content, so programs are entered through the RAM
module's program-entry dipswitches (as wired from Ben's ram.png/mar.png
schematics; verified against the netlist):

1. Set `PROG` = 1 (program mode).
2. For each listing row: set the address on the `PROG_ADDR` nibble
   dipswitches and the byte on the `PROG_DATA` dipswitches, then pulse
   `PROG_WRITE`.
3. Set `PROG` = 0, press reset, and start the clock.

The listing's ADDR/BYTE columns are exactly the dipswitch settings.

## Style conventions

- Labels flush at column 0, instructions indented (one tab or 8 spaces),
  one statement per line.
- Name every data constant and reference it by label (`ADD one`), never a
  bare address.
- Comments explain *why*, not *what* the mnemonic already says.
- Initialize: do not rely on power-up state; start programs with explicit
  `LDI`/`LDA` initialization of what they use.
