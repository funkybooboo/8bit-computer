# web/ - the browser implementation

The same machine as [digital/Computer.dig](../digital/Computer.dig), the
same spec, one more way to run it: pure HTML, CSS and JavaScript, no build
tools, no frameworks, no network dependencies - a static directory any web
server can host, so anyone can play with the computer in a browser.

## The one rule: real ROM images, not an ISA re-implementation

`js/machine.js` runs the actual control-ROM images
([roms/control-rom1.hex](../roms/control-rom1.hex) and
[roms/control-rom2.hex](../roms/control-rom2.hex)) - the same images the
Digital build carries and the hardware burns. Every clock cycle it looks up
the 16-bit control word at (step, opcode, CF, ZF) and asserts the control
signals against the registers, RAM and bus. Nothing is special-cased per
instruction. If the microcode is wrong, programs fail here exactly the way
they fail on the machine. That is what makes this an implementation of the
spec rather than a second opinion about it.

The control-word bits are the tables from [tools/microcode.py]
(../tools/microcode.py), the machine definition in code, and the cycle
model is the one documented in [docs/microcode.md](../docs/microcode.md).
Correctness is defined by the expectations frozen in
[test/verify.py](test/verify.py)'s table - for every program, the halt
status, the OUT count, and the first 32 OUT values - and each build must
reproduce them exactly:

    python3 web/test/verify.py

runs every program in [programs/](../programs/) on this build's
`js/machine.js` and checks them against that table.

## Run it locally

The app fetches the ROM images from the repo and the program images
from ../programs/ (build artifacts - build them first). From the repo
root:

    python3 web/build.py        # writes programs/*.hex from the .asm sources
    python3 -m http.server

then open <http://localhost:8000/web/>. (An HTTP server, not `file://`.)
Hosting elsewhere is the same story: this directory plus `../roms/` and
the built `../programs/` images is fully static.

## What is here

| file            | what it is                                                    |
|-----------------|---------------------------------------------------------------|
| index.html      | the app                                                        |
| css/style.css   | the looks                                                      |
| js/hex.js       | memory-image parsing: logisim .hex, Intel HEX, raw (the JS twin of the formats in tools/microcode.py) |
| js/machine.js   | the machine: control-word bits (tools/microcode.py) + the cycle-accurate core |
| js/main.js      | the UI: load, run, step, reset, register and OUT display        |
| js/run.mjs      | headless CLI runner (node web/js/run.mjs programs/count.hex)    |
| build.py        | builds programs/*.hex from the .asm sources (gitignored artifacts) |
| test/verify.py  | runs every program on js/machine.js against the frozen expectations |

## Phases

1. Core + minimal UI (this): runs the real ROM images, program picker for
   the programs that ship .hex images, run/step/reset, register, control
   signal and OUT display.
2. Front panel + visual datapath: the fun part - LEDs, bus and register
   boxes, clock animation, single-stepping with the control lines lighting
   up, the programming dipswitches from the hardware.
3. Assembler in the browser: port asm.py so any .asm source can be pasted
   and run (removes the dependency on the .hex images existing).
4. Hosting: publish so anyone can play with it.

Phase 1 is the whole machine, done correctly; everything after it is
presentation.
