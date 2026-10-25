# programs/ - assembly programs

The program gallery's sources, one .asm file per program - the gallery
itself, with what each program shows and what it teaches, lives in
[../docs/programs.md](../docs/programs.md).

Only the sources are tracked. Everything else here is a build artifact
and is gitignored: `web/build.py` writes the .hex images the browser app
serves, and `tools/asm.py` writes any image or listing on demand:

    python3 web/build.py                       # all program images, for the web app
    tools/asm.py programs/count.asm --out prog.hex --lst prog.lst
    node web/js/run.mjs prog.hex               # or open http://localhost:8000/web/

Each program's expected output is frozen in
[web/test/verify.py](../web/test/verify.py) (halt status, OUT count,
first 32 OUT values) - every build of the machine must reproduce it.
