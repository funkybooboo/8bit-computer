# programs/ - assembly programs

Programs for the machine in [../digital/Computer.dig](../digital/Computer.dig),
written in the assembly language ([../docs/assembly-language.md](../docs/assembly-language.md))
for the instruction set ([../docs/instruction-set.md](../docs/instruction-set.md)).

Only the `.asm` sources are tracked; assembled images and listings are
build artifacts and are gitignored (../.gitignore) - regenerate them with
the commands below (`tools/asm.py --dis` on the image verifies them).

| program   | what it does                                    |
|-----------|--------------------------------------------------|
| count.asm | count 0..255 forever, displaying each value     |

## count.asm

    tools/asm.py programs/count.asm --out programs/count.hex --lst programs/count.lst

Counts 0, 1, 2, ..., 255, 0, 1, ... forever on the output display. The 8-bit
ALU wraps naturally (255 + 1 = 0), so no conditional is needed; the +1 is a
data byte read by ADD (there is no increment instruction). 5 of the 16 RAM
bytes used.

## Building and loading any program

    tools/asm.py programs/count.asm --out prog.hex --lst prog.lst   # assemble
    tools/asm.py --dis prog.hex                                     # verify

Load it through the RAM module's program-entry dipswitches (`PROG`=1, set
`PROG_ADDR` + `PROG_DATA`, pulse `PROG_WRITE` per listing row; then `PROG`=0,
reset, run) - see "Loading a program into the machine" in
[../docs/assembly-language.md](../docs/assembly-language.md).
