# programs/ - assembly programs

Programs for the machine in [../digital/Computer.dig](../digital/Computer.dig),
written in the assembly language ([../docs/assembly-language.md](../docs/assembly-language.md))
for the instruction set ([../docs/instruction-set.md](../docs/instruction-set.md)).

Together the six programs exercise every instruction of the set, both flags,
taken and not-taken branches, and the adder's wrap in both directions. Each
fits in the machine's 16 bytes of RAM (program + data together):

| program       | the display shows                                   | instructions exercised         | bytes |
|---------------|------------------------------------------------------|--------------------------------|-------|
| count.asm     | 0, 1, ..., 255, 0, ... forever (the 8-bit wrap)     | LDI OUT ADD JMP                | 5     |
| countdown.asm | 255, 254, ..., 0, then halt                          | LDI SUB OUT NOP JZ JMP HLT     | 10    |
| memory.asm    | 0..255 forever, the counter kept in RAM              | LDI STA LDA OUT ADD JMP        | 9     |
| fib.asm       | Fibonacci mod 256, forever                           | LDA OUT ADD STA JMP           | 12    |
| overflow.asm  | 0, 60, 120, 180, 240, then halt on the carry          | LDI OUT ADD JC JMP HLT        | 7     |
| larger.asm    | the larger of two data bytes                         | LDA SUB JC OUT HLT            | 11    |

Only the `.asm` sources are tracked; assembled images and listings are
build artifacts and are gitignored (../.gitignore) - regenerate them with
the commands below (`tools/asm.py --dis` on the image verifies them).

## count.asm

Counts up forever, wrapping 255 -> 0 with no conditional at all: the
8-bit ALU wraps by itself. The +1 is a `.DB` constant read by ADD (there
is no increment instruction). Watch the ZF LED light when 255 + 1 = 0.

## countdown.asm

Counts down from 255 to 0 and halts. The 255 comes from an underflow:
`LDI 0` then `SUB one` is 0 - 1 = 255 through the adder (SUB computes
A + ~B + 1). ZF=1 on the final 0 is the exit test (JZ taken; on every
other round it is not taken). The NOP is pacing filler - 6 idle
microsteps that slow the countdown.

## memory.asm

The same count-up as count.asm, but the counter lives in RAM instead of
the A register: LDA loads it, ADD bumps it, STA stores it back - the
read-modify-write pattern, the machine's only way to keep state outside
its registers.

## fib.asm

Ben Eater's classic demo: Fibonacci numbers mod 256, forever. Each
round: x, y = y, x + y, displaying x. The three `.DB` bytes are the
initial pair (0, 1) plus a scratch byte - entered into RAM together
with the code. The sequence wraps mod 256 after 233 + 144 = 121.
12 of the 16 RAM bytes used - the tightest program here.

## overflow.asm

Counts by 60 and halts when the adder carries: ADD sets CF=1 whenever
the sum overflows the byte, so JC doubles as an overflow detector
(240 + 60 = 44, carry). The last displayed value is 240; watch the CF
LED light on the wrap.

## larger.asm

Displays the larger of two data bytes. SUB sets CF=1 when there is no
borrow - when A >= B - so JC acts as "jump if greater or equal", a
comparison without a compare instruction. SUB clobbers A, so the winner
is re-loaded from RAM. With the shipped data (x=9, y=14) it takes the
not-taken path; change the two data bytes (they are the last two
listing rows) and re-enter to watch JC taken, or equal (x=y shows x).

## Watching them on the machine

Set STEP_MODE and click STEP_PULSE once per clock edge to single-step:
the T0..T4 LEDs are the microstep counter, and the 16 control-line LEDs
show exactly the rows of [../docs/microcode.md](../docs/microcode.md) -
every instruction starts with the fetch (MI+CO, then RO+II+CE), ADD adds
RO+BI then EO+AI+FI at T3/T4, and so on. The CF and ZF LEDs tell you
which way JC/JZ will go. At speed, flip DEC_HEX for decimal/hex display
and set MUX_CLK's frequency high for a steady display.

Note: programs that mutate their data bytes (memory.asm, fib.asm) leave
that state in RAM - re-enter the image to restart them from their
initial values.

## Building and loading any program

    tools/asm.py programs/count.asm --out prog.hex --lst prog.lst   # assemble
    tools/asm.py --dis prog.hex                                     # verify

Load it through the RAM module's program-entry dipswitches (`PROG`=1, set
`PROG_ADDR` + `PROG_DATA`, pulse `PROG_WRITE` per listing row; then `PROG`=0,
reset, run) - see "Loading a program into the machine" in
[../docs/assembly-language.md](../docs/assembly-language.md). The listing's
ADDR/BYTE columns are the dipswitch settings; its bits column is the same
thing in ones and zeros.
