# programs/ - .hl programs

The program gallery's sources, one .hl file per program - the gallery
itself, with what each program shows and what it teaches, lives in
[../docs/programs.md](../docs/programs.md).

Only the sources are tracked. Everything else here is a build artifact
and is gitignored: `web/build.py` writes the .bin images the browser app
serves plus the compiled .asm and the .lst dipswitch entry table beside
each source, and `tools/compile.py` writes any of them on demand:

    python3 web/build.py                       # all program images, for the web app
    tools/compile.py programs/count.hl        # one program: .asm + .lst + .bin
    node web/js/run.mjs programs/count.bin    # or open http://localhost:8000/web/

Each program's expected output is frozen in
[web/test/verify.py](../web/test/verify.py) (halt status, OUT count,
first 32 OUT values) - every build of the machine must reproduce it.
