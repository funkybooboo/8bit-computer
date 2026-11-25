# programs/ - .hl programs

The program gallery's sources, one .hl file per program - the gallery
itself, with what each program shows and what it teaches, lives in
[../docs/programs.md](../docs/programs.md).

Only the sources are tracked. Everything else here is a build artifact
and is gitignored: `build.py` writes the compiled .asm, the .lst
dipswitch entry table and the .bin image beside each source, and
`tools/compile.py` writes any of them on demand:

    python3 programs/build.py                  # all program images + entry tables
    tools/compile.py programs/count_up.hl     # one program: .asm + .lst + .bin
    node web/js/run.mjs programs/count_up.bin  # or open http://localhost:8000/web/

Each program's expected output is frozen in
[verify.py](verify.py) - the contract every build of the machine must
reproduce ([../docs/tools.md](../docs/tools.md), "Running programs").
