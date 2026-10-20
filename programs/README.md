# programs/ - assembly programs

The program gallery's sources, one .asm file per program - the gallery
itself, with what each program shows and what it teaches, lives in
[../docs/programs.md](../docs/programs.md).

Only sources are tracked; assembled images and listings are build
artifacts and are gitignored - build one with:

    tools/asm.py programs/count.asm --out prog.hex --lst prog.lst
    tools/sim.py programs/count.asm
