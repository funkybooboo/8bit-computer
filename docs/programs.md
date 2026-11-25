# Programs

The program gallery for the machine ([../programs/](../programs/)):
what each shows on the display, what it teaches, and what the machine
cannot do. The sources are `.hl` programs (the language:
[language.md](language.md)), compiled to the assembly language
([assembly-language.md](assembly-language.md) - the compiler's output is
kept beside each source for inspection); the instructions:
[instruction-set.md](instruction-set.md); running them without the
machine: the web build and its test ([tools.md](tools.md),
"Running programs").

Every program's expected output is frozen in
web/test/verify.py's expectations table - the contract every build
of the machine must reproduce. Each program compiles into the
machine's 16 bytes of RAM (code + data together); the byte counts
below are the compiler's output - div, gcd, half and mul use 15 of
the 16, countdown uses all of them.

The tables are the index; each program's header comment says what it
teaches.

## Foundations - sequences, state and flags

| program       | the display shows                                  | instructions exercised       | bytes |
|---------------|-----------------------------------------------------|------------------------------|-------|
| count.hl     | 0, 1, ..., 255, 0, ... forever (the 8-bit wrap)    | LDA OUT ADDI STA JMP         | 6     |
| step.hl      | 0, 3, 6, ..., every byte once per 256 laps         | the same shape as count.hl   | 6     |
| countdown.hl | 255, 254, ..., 0, then halt                         | LDA SUBI OUT NOP JZ JMP HLT STA | 16 |
| fib.hl       | Fibonacci mod 256, forever                           | LDA OUT ADD STA JMP          | 12    |
| overflow.hl  | 0, 60, 120, 180, 240, then halt on the wrap          | LDA OUT ADD SUB JC JMP HLT STA | 10 |
| larger.hl    | the larger of two data bytes                         | LDA SUB JNC JMP OUT HLT      | 11    |
| absdiff.hl   | the absolute difference |9 - 14| = 5                 | LDA SUB JNC JMP OUT HLT      | 11    |
| min.hl       | min(x, 10): the threshold guard (x=25 -> 10)        | LDA SUBI JNC LDI JMP OUT HLT | 10    |
| odometer.hl  | 0, 1, ..., 99, 0, ... a two-digit odometer          | LDA OUT ADDI SUB JNZ LDI JMP STA | 12 |

## Math - what arithmetic loops can build

| program    | the display shows                                        | the algorithm                    | bytes |
|------------|-----------------------------------------------------------|----------------------------------|-------|
| mul.hl    | the times table for x: 7, 14, ..., 42, halt              | repeated addition (r += x, y laps) | 15   |
| div.hl    | the long division of 100/9: 91, 82, ..., 1, then 11       | repeated subtraction + quotient  | 15    |
| mod.hl    | the remainder: 100 mod 9 = 1                             | repeated subtraction, stripped   | 10    |
| gcd.hl    | gcd(252, 105) = 21                                        | subtractive Euclid               | 15    |
| squares.hl| 1, 4, 9, ..., 225, then mod 256                            | sum of odd numbers               | 10    |
| powers.hl | 1, 2, 4, ..., 128, then halt exactly on the wrap          | doubling (DBL), self-stopping   | 10    |
| triple.hl | 3, 9, 27, 81, 243, ... the powers of three                  | shift-and-add (ADD + ADD)        | 7     |
| half.hl   | 22 / 2 = 11                                               | search for y with y + y = x      | 15    |
| lcg.hl    | a pseudorandom shuffle: every byte once per 256 steps    | x = 5x + 1 (mod 256)             | 10    |

## Machine tricks - shifts and flags

| program      | the display shows                                 | the trick                          | bytes |
|--------------|---------------------------------------------------|-------------------------------------|-------|
| rotate.hl   | a chasing light: 1, 2, 4, ..., 128, 1, ...        | rotate-left through the carry        | 11    |
| rol.hl      | a bit pattern circling a byte, 8 steps per lap    | the same idiom, wider seed            | 11    |
| bits.hl     | the byte itself as digits: 1, 0, 1, 1, ...       | the rotate, one bit displayed per lap | 14  |
| patch.hl    | 7 once, then 9 forever                            | the self-modification demo's OUT stream, rebuilt with ordinary code | 6 |
| bothflags.hl| 255, then 0                                       | one ADD setting CF and ZF together  | 10    |

## Limits - what does not fit, and why

The instruction set and the 16 bytes bound what is possible; these do
not fit, for structural reasons (not just for lack of bytes). What would
fix each one, and at what cost: [additions.md](additions.md);
the full path to C programs: [getting-to-c.md](getting-to-c.md).

- **Conway's Game of Life, even 1-D cellular automata (rule 90/110)** -
  the update rule XORs neighboring bits, and the ALU only adds and
  subtracts. Building XOR from arithmetic needs per-bit products (AND),
  and one cell's update alone would eat the whole RAM. rotate.hl is the
  one bit-op within reach: a rotate-left through the carry.
- **Arrays, lookup tables, indexed anything** - there is no indirect
  addressing: every LDA/STA operand is a 4-bit constant baked into the
  instruction, and an address cannot be computed at run time. The
  loophole is rewriting an operand's byte in RAM (STA to a code
  address) - but only one hand-patched instruction at a time, never a
  computed address; the .hl language forbids it by construction.
- **Interactive games, calculators you can feed numbers** - after PROG
  goes to run mode, the data dipswitches are muxed out of the datapath;
  the only run-time inputs are the clock, reset and mode switches.
  Nothing can respond to a player. All games here are self-running.
- **Exponentiation (x^y), prime testing, sorting, averaging N numbers** -
  these need nested loops (a loop counter inside another loop), plus
  their variables; two counters plus accumulators plus code does not fit
  16 bytes. div/gcd work because they are single-loop.
- **LFSR random numbers** - a linear feedback shift register needs the
  XOR of several tap bits; same problem as the cellular automata.
  lcg.hl is the arithmetic-only substitute.

Pushing the limit on purpose: countdown.hl uses exactly all 16 bytes; div,
gcd, half and mul use 15 of the 16.

## Building and loading any program

    python3 tools/compile.py programs/count.hl   # -> count.asm + count.lst + count.bin
    node web/js/run.mjs programs/count.bin       # run headless

Load it through the front panel (the procedure and the dipswitch
groups: [hardware.md](hardware.md), "Front panel"). The listing's bits
column is the dipswitch settings, in the three groups the switches
are: address | opcode | operand.

Note: programs that mutate their data bytes (fib.hl, the math group's
accumulators, triple.hl's running value) leave that state in RAM -
re-enter the image to restart them from their initial values.
