# web/ - the emulator, as the machine itself

The machine emulated in a browser - the repo's emulator (there is no
separate one): the same machine as [digital/Computer.dig](../digital/Computer.dig),
running the same ROM images, presented as the machine itself - its
modules, lamps and switches, laid out as the Digital build lays them
out - in pure HTML, CSS and JavaScript, no build tools, no frameworks,
no network dependencies - a static directory any web server can host,
so anyone can run the computer in a browser.

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
- **the machine's controls** (docs/hardware.md, "The front panel" -
  the wiring of the switches and lamps): every LED the hardware
  lists - BUS, PC, A, B, IR, SUM, CF/ZF, RAM address and data, the
  microstep T0..T6 and STEP counter bits, all 16 control lines, CLK,
  PROG/PROG_hat - plus the switches with the hardware's own names,
  homes and gating: RESET on the CONTROL (U51's reset shaping),
  STEP_MODE + STEP_PULSE on the CLOCK (in AUTO the pulse button is
  disconnected, U5.1; in MANUAL the master clock is, U4.1), PROG_ADDR
  and the PROG_ADDR_A dipswitches on the MAR (U33), PROG_DATA and
  PROG_WRITE on the RAM (U26/U27, U32), DEC_HEX on the OUTPUT. In
  PROGRAM mode the RAM address/data muxes (U33/U26/U27, the 74157s)
  put the panel switches on, exactly as wired.

The control-word bits are the tables from [tools/genroms.py]
(../tools/genroms.py), the machine definition in code, and the cycle
model is the one documented in [docs/microcode.md](../docs/microcode.md).

## The app

- **the deck** (the dashed bar above the panel): this app's control
  room - nothing in it is on the machine. The program picker + LOAD,
  RUN/PAUSE (the app's time control - the hardware has no pause),
  TURBO (run to the halt/cap without animation), TRACE, IMAGE FILE,
  and the app's status readouts (program, cycles, instructions).
  Space = one clock pulse (as STEP_PULSE, so it respects STEP_MODE).
- **the panel**: the machine and only the machine, arranged as in the
  Digital build and Ben's breadboards - left column CLOCK, MAR, RAM,
  IR, CONTROL; right column PC (top), A, ALU, B, OUTPUT; the BUS runs
  down the middle between the module columns, its lamps reading left
  to right and the wire itself drawn running the panel's height -
  every module taps it. Each module carries its chip annotation, and
  the control LEDs show the word for the cycle about to execute,
  steady between edges, like the hardware's. The switches sit where
  they wire: STEP_MODE + STEP_PULSE and the U1 rate (1 Hz to 2 kHz,
  the 555's pot) on the CLOCK (the gating is real - in AUTO the
  pulse button is disconnected, U5.1; in MANUAL the master clock is,
  U4.1); RESET on the CONTROL (it is U51's reset shaping there);
  PROG_ADDR and the PROG_ADDR_A dipswitches on the MAR (U33);
  PROG_DATA and PROG_WRITE on the RAM (U26/U27, U32); DEC_HEX on the
  OUTPUT. A legend above the panel states the marking convention:
  unmarked = on the machine; dashed = this app's (the hex readouts,
  the OUT LED bank - on the hardware OUT shows on the display only -
  the mux counter LEDs, the halt lamp, the RAM monitor, the
  driver/mnemonic annotations).
- **your program**: paste .hl or .asm source (or a hex/logisim image),
  COMPILE + LOAD builds it in the browser with the repo's own toolchain
  (below) and puts it in RAM; the generated .asm is shown under the
  editor. IMAGE FILE accepts .hl, .asm, .bin, .hex and .lst files.
- **listing**: the program's entry table - one line per address with
  the three dipswitch groups - as compiled in the browser, the current
  PC line highlighted. A line that carries a byte is clickable: it
  puts that address and byte straight onto the PROG switches, because
  the table IS the hand-entry procedure. The same table web/build.py
  writes next to each source.
- **out log / cycle trace**: the OUT stream and, when stepping (or with
  TRACE on), every cycle's control lines and state.
- **docs**: the repo's own documentation (docs/*.md) rendered in the
  page, cross-links working inside the reader - the machine's docs are
  one click from the machine.

### Loading a program: three ways, one destination

All three end with the same bytes in RAM - the gallery and the
compiler are conveniences that do what the switches do byte by byte:

1. **by hand, the hardware's way** - flip PROG_ADDR (on the MAR) to
   PROG, set PROG_ADDR_A and PROG_DATA from the listing (clicking a
   listing line or a RAM row loads its bits onto the switches), press
   PROG_WRITE per byte; flip back to RUN, RESET, run.
2. **from the gallery** - pick a prewritten program in the deck and
   LOAD: it is fetched as .hl source and compiled in the browser with
   the repo's own toolchain, byte-identical to the repo's build.
3. **your own** - paste .hl or .asm (or an image) in the pane below
   and COMPILE + LOAD.

Whichever way, the listing pane then shows the bytes - and way 1 can
reproduce way 2 or 3 by hand, line by line.

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

A bare clone is enough - nothing is prebuilt and no backend is needed:
every file the app fetches is in the repo (the ROM images, the docs,
the .hl sources), and the programs are compiled in the browser. From
the repo root:

    python3 -m http.server

then open <http://localhost:8000/web/>. (An HTTP server, not
`file://` - the app fetches its files.) Any static host works the same
way; GitHub Pages serving the repo as-is does too, since every fetch
is a relative path into the repo. Open the app with `?smoke=1` to run
its built-in self-check (the machine, the panel write path, the
toolchain, the docs renderer - results in the trace pane).

web/build.py remains for local work: it writes the .bin images and the
.lst entry tables next to the .hl sources (gitignored artifacts) for
inspection, manual entry and the headless runner - the web app does
not need them.

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
| js/panel.js     | the panel's parts: LED banks, switches, the RAM monitor, the listing pane |
| js/docs.js      | the docs reader: a small markdown renderer + in-page navigation |
| js/main.js      | the app: the clock, the keys, the wiring, the render loop, the self-test |
| js/run.mjs      | headless CLI runner (node web/js/run.mjs programs/count.bin)    |
| build.py        | optional: writes programs/*.bin + .lst artifacts next to the .hl sources for inspection, manual entry and the headless runner (the web app does not need them) |
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

One constraint throughout: the app is fully static - no backend, no
build step, no network dependencies beyond the repo's own files - so
any web server (or GitHub Pages) can host it straight from a clone.
