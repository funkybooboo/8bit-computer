# programs/ - assembly programs

Programs for the machine in [../digital/Computer.dig](../digital/Computer.dig),
written in the assembly language ([../docs/assembly-language.md](../docs/assembly-language.md))
for the instruction set ([../docs/instruction-set.md](../docs/instruction-set.md)).

Twenty-one programs in three groups - foundations, math, and machine
tricks. Together they exercise every instruction (including the opcode
additions JNC/JNZ/ADDI/SUBI/DBL), both flags, taken and not-taken
branches, the adder's wrap in both directions, and the von Neumann trick of
a program rewriting itself. Every program's behavior was verified before
being documented: [../tools/sim.py](../tools/sim.py) runs it cycle by
cycle off the same control-ROM images the hardware burns, cross-checked
against an independent ISA-level reference. Each fits in the machine's 16
bytes of RAM (program + data together); the tightest use all 16.

Only the `.asm` sources are tracked; assembled images and listings are
build artifacts and are gitignored (../.gitignore) - regenerate them with
the commands at the bottom (`tools/asm.py --dis` on the image verifies
them). To RUN a program without the machine:
`tools/sim.py programs/fib.asm`.

## Foundations - sequences, state and flags

| program       | the display shows                                  | instructions exercised    | bytes |
|---------------|-----------------------------------------------------|---------------------------|-------|
| count.asm     | 0, 1, ..., 255, 0, ... forever (the 8-bit wrap)    | LDI OUT ADD JMP           | 5     |
| step.asm      | 0, 3, 6, ..., every byte once per 256 laps         | OUT ADDI JMP              | 3     |
| countdown.asm | 255, 254, ..., 0, then halt                         | LDI SUB OUT NOP JZ JMP HLT | 10    |
| decrement.asm | 10, 9, ..., 0, then halt (no data cell)            | LDI OUT SUBI JZ JMP HLT   | 7     |
| memory.asm    | 0..255 forever, the counter kept in RAM             | LDI STA LDA OUT ADD JMP   | 9     |
| fib.asm       | Fibonacci mod 256, forever                           | LDA OUT ADD STA JMP       | 12    |
| overflow.asm  | 0, 60, 120, 180, 240, then halt on the carry          | LDI OUT ADD JC JMP HLT    | 7     |
| larger.asm    | the larger of two data bytes                         | LDA SUB JC OUT HLT        | 11    |
| min.asm       | min(x, 10): the threshold guard (x=25 -> 10)        | LDA SUBI JNC LDI OUT HLT  | 10    |

- **count.asm** - counts up forever, wrapping 255 -> 0 with no conditional:
  the 8-bit ALU wraps by itself. The +1 is a `.DB` constant read by ADD.
- **step.asm** - count.asm with the constant taken out of RAM: ADDI adds
  the step straight from the instruction, so the whole program is 3
  bytes. Any odd step (3, 5, ... 15) is coprime with 256, so the display
  visits all 256 byte values before repeating; change one nibble and the
  step changes.
- **countdown.asm** - counts down from 255 to 0 and halts. The 255 comes
  from an underflow (`LDI 0` then `SUB one` = 0 - 1 = 255). ZF=1 on the
  final 0 is the exit test; the NOP is pacing filler.
- **decrement.asm** - the same countdown with SUBI: the 1 comes from the
  instruction, so no data cell and no underflow trick are needed - just
  the classic decrement-and-test loop. 7 bytes vs countdown's 10.
- **memory.asm** - the same count-up, but the counter lives in RAM: the
  LDA / ADD / STA read-modify-write pattern for state outside the registers.
- **fib.asm** - Ben Eater's classic: Fibonacci mod 256, forever. x, y =
  y, x + y each round, displaying x. The three `.DB` bytes are the
  initial state; wraps after 233 + 144 = 121.
- **overflow.asm** - counts by 60 and halts when the adder carries: ADD
  sets CF=1 on the wrap (240 + 60 = 44), so JC doubles as an overflow
  detector.
- **larger.asm** - the larger of two data bytes: SUB sets CF=1 when there
  is no borrow (A >= B), so JC acts as "jump if greater or equal". Change
  the two data bytes and re-enter to take the other branch (x=y shows x).
- **min.asm** - the guard pattern: compare against a threshold that exists
  only in the instruction. SUBI limit sets CF=1 iff A >= limit, so JNC
  means "strictly below" - the first comparison on this machine that
  needs no RAM cell for its constant. The compare clobbers A, so both
  branches re-load it.

## Math - what arithmetic loops can build

| program    | the display shows                                        | the algorithm                    | bytes |
|------------|-----------------------------------------------------------|----------------------------------|-------|
| mul.asm    | the times table for x: 7, 14, ..., 42, halt              | repeated addition (r += x, y laps) | 14   |
| div.asm    | the long division of 100/9: 91, 82, ..., 1, then 11       | repeated subtraction + quotient  | 16    |
| mod.asm    | the remainder: 100 mod 9 = 1                             | repeated subtraction, stripped   | 10    |
| gcd.asm    | gcd(252, 105) = 21                                        | subtractive Euclid               | 15    |
| squares.asm| 1, 4, 9, ..., 225, then mod 256                            | sum of odd numbers               | 11    |
| powers.asm | 1, 2, 4, ..., 128, then halt exactly on the wrap          | doubling (DBL), self-stopping    | 5     |
| half.asm   | 22 / 2 = 11                                               | search for y with y + y = x      | 16    |
| lcg.asm    | a pseudorandom shuffle: every byte once per 256 steps    | x = 5x + 1 (mod 256)             | 11    |

- **mul.asm** - multiplication as a loop (the machine has none): each lap
  adds x to a running product and shows it, so the display walks the
  times-table row for x. The exit test sits right after the SUB that sets
  ZF - flags only change on ADD/SUB/ADDI/SUBI/DBL, so every JZ reads a
  fresh result.
  Edge case: y=0 runs 256 laps and still ends on the right answer, because
  x*0 and x*256 are the same byte (mod 256) - the wrap fixes the accident.
- **div.asm** - long division, visible: every lap subtracts y and shows
  the running remainder (91, 82, ...), counts the laps in q, and the
  final display is the quotient (100/9 = 11, remainder 1 left in x).
  Exactly 16 bytes - every byte of RAM is working.
- **mod.asm** - the stripped core of div.asm: subtract until x < y; what
  is left in x IS the remainder. 10 bytes, the smallest arithmetic loop here.
- **gcd.asm** - the oldest algorithm still in daily use (it reduces
  fractions: 252/105 = 12/5 after dividing out 21). One SUB does triple
  duty: A = x - y, ZF tests x == y, CF tests x >= y.
- **squares.asm** - 1 + 3 + 5 + ... = n^2: adding successive odd numbers
  generates the squares; wraps mod 256 at 16^2 = 0.
- **powers.asm** - doubling as a self-stopping loop: DBL doubles A with
  CF catching the bit shifted out, and 128 * 2 wraps to exactly 0, so
  ZF ends the run on the wrap - no counter, no comparison. 5 bytes:
  the flag does the bookkeeping.
- **half.asm** - halving without a shift: search upward for the y whose
  double equals x (the SUB sets ZF on the hit). A search loop - a
  different algorithm class from the counting loops. Edge case: x must
  be even, or the search runs forever (2y mod 256 is always even).
- **lcg.asm** - a full-period pseudorandom sequence: x = 5x + 1 (mod 256)
  built from four ADDs. By the Hull-Dobell theorem (a = 5 is 1 mod 4,
  c = 1 is odd, m = 256) its period is exactly 256: the outputs are a
  permutation of every byte 0..255. The closest thing to randomness this
  machine can make - no XOR, so no LFSR (see "Limits" below).

## Machine tricks - shifts and self-modification

| program      | the display shows                                 | the trick                          | bytes |
|--------------|---------------------------------------------------|-------------------------------------|-------|
| rotate.asm   | a chasing light: 1, 2, 4, ..., 128, 1, ...        | rotate-left through the carry        | 12    |
| rol.asm      | a bit pattern circling a byte, 8 steps per lap    | the same, with DBL + JNC + ADDI 1    | 6     |
| patch.asm    | 7 once, then 9 forever                            | the program rewrites its own ADD    | 10    |
| bothflags.asm| 255, then 0                                       | one ADD setting CF and ZF together  | 10    |

- **rotate.asm** - the shift built from primitives, before DBL existed:
  A + A doubles the byte (a left shift) and the carry out is exactly the
  bit that fell off the top; JC + ADD one feed it back into bit 0. With
  s=1 the display (and the A-register LEDs) chase a single
  light - also the building block of serial links.
- **rol.asm** - the same rotate with the new opcodes, twice as short and
  with no data cell: DBL is the shift (CF = bit out), JNC skips the fixup,
  ADDI 1 wraps the carried bit into bit 0. The seed never has to sit in
  RAM, and every byte value passes through A once per 8 laps.
- **patch.asm** - self-modifying code: program and data share RAM, so
  nothing stops a program from writing over its own instructions. Lap 1:
  the ADD at address 01 reads x (7); then the program builds the byte for
  "ADD y" (0x2A = 42 = 15 + 27) and stores it over address 01 - from lap 2
  the same instruction means "add 9 instead". Watch the IR operand LEDs
  change while the PC keeps returning to the same address. `.ORG` places
  y at exactly 0x0A so the built byte is 0x2A.
- **bothflags.asm** - 255 + 1 is the only byte whose successor is exactly
  0 with a carry: CF and ZF set in the same instruction. Both conditional
  jumps are shown testing it (JC takes it; so would JZ).

## Watching them on the machine

Set STEP_MODE and click STEP_PULSE once per clock edge to single-step:
the T0..T6 LEDs are the microstep counter, and the 16 control-line LEDs
show exactly the rows of [../docs/microcode.md](../docs/microcode.md) -
every instruction starts with the fetch (MI+CO, then RO+II+CE), ADD adds
RO+BI then EO+AI+FI at T3/T4, and so on. The CF and ZF LEDs tell you
which way JC/JZ will go. At speed, flip DEC_HEX for decimal/hex display
and set MUX_CLK's frequency high for a steady display.

Note: programs that mutate their data bytes (memory.asm, fib.asm, and
the math group's accumulators) leave that state in RAM - re-enter the
image to restart them from their initial values.

## The practical set - what a no-input machine is good for

There is no run-time input (see Limits below), so "practical" means: a
pocket calculator whose operands you set as `.DB` bytes when entering the
program, then watch it work. That still covers real jobs on a display-only
machine:

- **times tables** (mul.asm) - any row, any length;
- **integer division and remainders** (div.asm, mod.asm) - the running
  remainder even shows the long-division work;
- **fraction reduction** (gcd.asm) - divide numerator and denominator by
  the displayed gcd;
- **halving** (half.asm) - and any "find y such that" search on small sets;
- **clamps and thresholds** (min.asm) - compare against a constant the
  machine does not have to store;
- **sequence generation** (lcg.asm, squares.asm, powers.asm, fib.asm) -
  permutations, squares, powers, Fibonacci: lookup-table content generated
  rather than stored;
- **bit shipping** (rotate.asm, rol.asm) - shift a byte out one bit per
  lap, carry first: serial output.

## Limits - what does not fit, and why

The instruction set and the 16 bytes bound what is possible; these do not
fit, for structural reasons (not just for lack of bytes). What would fix
each one, and at what cost: [../docs/ideas.md](../docs/ideas.md) (the
former empty opcode slots are now filled - JNC/JNZ/ADDI/SUBI/DBL); the
full path to C programs: [../docs/getting-to-c.md](../docs/getting-to-c.md).

- **Conway's Game of Life, even 1-D cellular automata (rule 90/110)** -
  the update rule XORs neighboring bits, and the ALU only adds and
  subtracts. Building XOR from arithmetic needs per-bit products (AND),
  and one cell's update alone would eat the whole RAM. rotate.asm is the
  one bit-op within reach: a rotate-left through the carry.
- **Arrays, lookup tables, indexed anything** - there is no indirect
  addressing: every LDA/STA operand is a 4-bit constant baked into the
  instruction, and an address cannot be computed at run time. patch.asm
  shows the loophole - rewrite an operand's byte in RAM - but one patched
  instruction at a time, never a computed one.
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
  lcg.asm is the arithmetic-only substitute.

On purpose at the limit: div.asm and half.asm use exactly all 16 bytes.

## Building and loading any program

    tools/asm.py programs/count.asm --out prog.hex --lst prog.lst   # assemble
    tools/asm.py --dis prog.hex                                     # verify

Load it through the RAM module's program-entry dipswitches (`PROG`=1, set
`PROG_ADDR` + `PROG_DATA`, pulse `PROG_WRITE` per listing row; then `PROG`=0,
reset, run) - see "Loading a program into the machine" in
[../docs/assembly-language.md](../docs/assembly-language.md). The listing's
ADDR/BYTE columns are the dipswitch settings; its bits column is the same
thing in ones and zeros.
