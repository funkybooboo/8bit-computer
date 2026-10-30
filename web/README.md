# web/ - the emulator, as a front panel

The machine emulated in a browser - the repo's emulator (there is no
separate one): the same machine as [digital/Computer.dig](../digital/Computer.dig),
running the same ROM images, presented as the front panel the hardware
has - LEDs, switches, a multiplexed display, keys - in pure HTML, CSS
and JavaScript, no build tools, no frameworks, no network dependencies -
a static directory any web server can host, so anyone can run the
computer in a browser.

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

## What makes it a close emulation

Everything below is modeled as the hardware does it (references:
[docs/microcode.md](../docs/microcode.md), [docs/hardware.md](../docs/hardware.md),
"Clock, reset, and power"):

- the **two-edge clock**: one cycle is `risingEdge()` + `fallingEdge()` -
  every register latches on the CLK edge, and only the microstep counter
  (U48) advances on the inverted edge, between register edges, which is why
  the control word is stable for the whole cycle
- **bus discipline**: at most one bus driver per cycle; more is an error
  (the emulator throws), not silent last-writer-wins
- **pre-edge latching**: every register latches from the state before the
  edge (which is what makes FI capture the flags of THIS result even as
  AI latches the same result into A); the ALU computes A + ~B + 1 for SUB
- **RESET as wired**: clears the PC, the step counter, the output register
  and every 74173 (A, B, IR, MAR, flags) - and does NOT clear RAM (the
  74189s are not on the reset net), so reset + rerun runs over whatever the
  last run left in memory, exactly like the hardware; the load button
  is the power cycle
- **the display** (U37/U38/U44/U45): the output register byte addresses
  the real [roms/output-display.hex](../roms/output-display.hex) through
  the mux-counter pages, so the four digits show decimal or hex exactly
  what the hardware shows - the DEC_HEX switch included
  (js/display.js decodes the ROM; the canvas draws all four digits, the
  persistence-of-vision view of the 500+ Hz multiplex, while the mux
  counter itself runs and shows on its panel LEDs)
- **the front panel** (docs/hardware.md, "The front panel"): every LED the
  hardware lists - BUS, PC, A, B, IR, SUM, CF/ZF, RAM address and data,
  the microstep T0..T6 and counter bits, all 16 control lines, CLK - plus
  the panel switches: RUN/PROG, the address and data dipswitches, WRITE,
  DEC_HEX. In PROGRAM mode the RAM address/data muxes (U33/U26/U27, the
  74157s) put the panel switches on, exactly as wired.

The control-word bits are the tables from [tools/genroms.py]
(../tools/genroms.py), the machine definition in code, and the cycle
model is the one documented in [docs/microcode.md](../docs/microcode.md).

## The app

- **the deck** (top): program picker + LOAD; RUN/PAUSE (the master
  clock), STEP (one clock pulse - the clock module's STEP_PULSE), TURBO
  (run to the halt/cap, no animation), RESET; the CLOCK speed slider
  (1 Hz to 2 kHz - slow enough to watch the control lines, fast enough
  to reach a halt in a second); TRACE (log every cycle while the clock
  runs); IMAGE FILE. Space = one clock cycle.
- **the panel**: the modules in the machine's own terms, each with its
  chip annotation (the OUT register and display, the clock, the bus, the
  control logic, the registers, the ALU, the RAM, the front-panel
  switches, the monitor). The control LEDs show the word for the cycle
  about to execute, steady between edges, like the hardware's.
- **your program**: paste .hl or .asm source (or a hex/logisim image),
  COMPILE + LOAD builds it in the browser with the repo's own toolchain
  (below) and puts it in RAM; the generated .asm is shown under the
  editor. IMAGE FILE accepts .hl, .asm, .bin, .hex and .lst files.
- **listing**: the program's entry table (the .lst web/build.py writes,
  or the one just assembled) with the current PC line highlighted - the
  same table used to enter a program through the dipswitches.
- **out log / cycle trace**: the OUT stream and, when stepping (or with
  TRACE on), every cycle's control lines and state.
- **docs**: the repo's own documentation (docs/*.md) rendered in the
  page, cross-links working inside the reader - the machine's docs are
  one click from the machine.

### Entering a program by hand

The hardware's own procedure (docs/hardware.md, "The front panel"):
flip RUN/PROG to PROGRAM, set the address and data dipswitches, press
WRITE (a RAM row click loads that row's address and byte into the
switches), flip back to RUN, RESET, run. The listing pane's bits column
is the dipswitch table.

## The toolchain in the browser

`js/hlc.js` and `js/asm.js` are whole, faithful ports of
[tools/compile.py](../tools/compile.py) and [tools/asm.py](../tools/asm.py)
- same two-pass assembler, same lexer/parser/code generator, same
  emitted idioms - so a program built in the browser is byte-identical
  to what the repo's tools build. [test/test_tools.py](test/test_tools.py)
  is the proof: it compiles and assembles every program in the gallery
  with both toolchains and compares the .asm text and the .bin image
  byte for byte.

## Run it locally

The app fetches the ROM images from the repo and the program images
from ../programs/ (build artifacts - build them first). From the repo
root:

    python3 web/build.py        # writes programs/*.bin from the .hl sources
    python3 -m http.server

then open <http://localhost:8000/web/>. (An HTTP server, not `file://`.)
Hosting elsewhere is the same story: this directory plus `../roms/`,
`../docs/` and the built `../programs/` images is fully static. Open the
app with `?smoke=1` to run its built-in self-check (the machine, the
panel write path, the toolchain, the docs renderer - results in the
trace pane).

## Tests

    python3 web/test/verify.py      # every gallery program on js/machine.js
    python3 web/test/test_tools.py  # the JS ports vs the repo tools, byte for byte
    node web/test/test_display.mjs  # the display ROM decode vs known patterns

Correctness of the machine is defined by the expectations frozen in
[test/verify.py](test/verify.py)'s table - for every program, the halt
status, the OUT count, and the first 32 OUT values - and each build must
reproduce them exactly.

## What is here

| file            | what it is                                                    |
|-----------------|---------------------------------------------------------------|
| index.html      | the app's shell (the DOM is built by the JS)                   |
| css/style.css   | the looks - the faceplate, LEDs, keycaps, switches             |
| js/hex.js       | memory-image parsing: logisim .hex, Intel HEX, raw (the JS twin of the formats in tools/genroms.py) |
| js/machine.js   | the machine: control-word bits (tools/genroms.py) + the cycle-accurate core |
| js/hlc.js       | the .hl compiler, the JS twin of tools/compile.py              |
| js/asm.js       | the assembler, the JS twin of tools/asm.py                     |
| js/display.js   | the display: output-display.hex decode + the seven-segment canvas |
| js/panel.js     | the front panel's parts: LED banks, switches, the RAM monitor, the listing pane |
| js/docs.js      | the docs reader: a small markdown renderer + in-page navigation |
| js/main.js      | the app: the clock, the keys, the wiring, the render loop, the self-test |
| js/run.mjs      | headless CLI runner (node web/js/run.mjs programs/count.bin)    |
| build.py        | builds programs/*.bin from the .hl sources (gitignored artifacts; keeps the generated .asm and the .lst entry table next to each .hl) |
| test/verify.py  | runs every program on js/machine.js against the frozen expectations |
| test/test_tools.py + run_tools.mjs | the JS toolchain vs the repo toolchain, byte for byte |
| test/test_display.mjs | the display ROM decode against known patterns            |

## Phases

1. Core + minimal UI: runs the real ROM images, program picker,
   run/step/reset, register and OUT display. Done.
2. Front panel + visual machine (this): every LED and switch the
   hardware has, the multiplexed display, the real clock with speed
   control, dipswitch program entry, the RAM monitor, the listing.
   Done.
3. Compiler in the browser (this too): the .hl compiler and the
   assembler ported whole, byte-identical to the repo's tools, plus the
   docs reader. Done.
4. Hosting: publish so anyone can play with it.

The machine itself was finished at phase 1; phases 2 and 3 were
presentation and self-sufficiency.
