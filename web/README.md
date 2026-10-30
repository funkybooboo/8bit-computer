# web/ - the machine in a browser

The machine emulated in a browser - the repo's emulator (there is no
separate one): the same machine as [digital/Computer.dig](../digital/Computer.dig),
running the same ROM images, presented as the machine itself - its
modules, lamps and switches, laid out as the Digital build lays them
out - in pure HTML, CSS and JavaScript, no build tools, no frameworks,
no network dependencies. A static directory any web server can host.

The app is deliberately nothing more than the machine. It powers on
with empty RAM (16 NOPs) and the clock running, like the bench machine
with the power on - and a program gets in exactly one way, the way the
hardware does it:

## Entering a program: the switches

1. Build a listing for the program you want (see below) - its bits
   column is the dipswitch table.
2. PROG_ADDR (on the MAR) to PROG. In program mode the panel muxes put
   the switches on: the RAM DATA lamps now read back the byte at the
   PROG_ADDR_A address - how you verify what you entered.
3. For each line: set PROG_ADDR_A and PROG_DATA, press PROG_WRITE (on
   the RAM).
4. PROG_ADDR back to RUN, RESET (on the CONTROL), and STEP_MODE (on
   the CLOCK) to AUTO - or MANUAL and single-step with STEP_PULSE
   (the space bar works too).

Writing programs is the repo's job, not the app's: the program sources
are [programs/](../programs/README.md) (the .hl language:
[docs/language.md](../docs/language.md)), and the listings are one
command away - `python3 tools/compile.py programs/count.hl` writes
`count.lst` (the entry table) next to the source, or
`python3 web/build.py` does the whole gallery. The footer of the app
links to all of this.

## What makes it a close emulation

Everything below is modeled as the hardware does it (references:
[docs/microcode.md](../docs/microcode.md), [docs/hardware.md](../docs/hardware.md)):

- the **one rule**: js/machine.js runs the actual control-ROM images
  ([roms/control-rom1.hex](../roms/control-rom1.hex) and
  [roms/control-rom2.hex](../roms/control-rom2.hex)) - the same images
  the Digital build carries and the hardware burns. Every clock cycle
  it looks up the 16-bit control word at (step, opcode, CF, ZF) and
  asserts the control signals. Nothing is special-cased per
  instruction; if the microcode is wrong, programs fail here exactly
  the way they fail on the machine.
- the **two-edge clock**: one cycle is `risingEdge()` +
  `fallingEdge()` - every register latches on the CLK edge, and only
  the microstep counter (U48) advances on the inverted edge, which is
  why the control word is stable for the whole cycle
- **bus discipline**: at most one bus driver per cycle; more is an
  error (the emulator throws), not silent last-writer-wins
- **pre-edge latching**: every register latches from the state before
  the edge; the ALU computes A + ~B + 1 for SUB
- **RESET as wired** through U51: clears the PC, the step counter, the
  output register and every 74173 (A, B, IR, MAR, flags) - and does
  NOT clear RAM, which is not on the reset net
- **the display** (U37/U38/U44/U45): the output register byte
  addresses the real [roms/output-display.hex](../roms/output-display.hex)
  through the mux-counter pages, so the four digits show decimal or
  hex exactly what the hardware shows - the DEC_HEX switch included
  (js/display.js decodes the ROM; the canvas draws all four digits,
  the persistence-of-vision view of the 500+ Hz multiplex)
- **the controls, where they wire** (docs/hardware.md, "The front
  panel"): STEP_MODE + STEP_PULSE and the U1 rate (the 555's pot) on
  the CLOCK; RESET on the CONTROL (U51's reset shaping); PROG_ADDR and
  the PROG_ADDR_A dipswitches on the MAR (U33); PROG_DATA and
  PROG_WRITE on the RAM (U26/U27, U32); DEC_HEX on the OUTPUT. The
  gating is real: in AUTO the STEP_PULSE button is disconnected
  (U5.1); in MANUAL the master clock is (U4.1); HLT gates the clock
  off entirely (U4.4). In PROGRAM mode the RAM address/data muxes
  (U33/U26/U27, the 74157s) put the panel switches on, exactly as
  wired.

The panel carries every lamp the hardware lists - BUS, PC, A, B, IR,
SUM, CF/ZF, the RAM data (the RAM_DATA nets; the address lamps live
on the MAR - they are the RAM address nets A0..A3, driven by the MAR
in run mode and by the switches in program mode), the microsteps
T0..T6 and STEP
counter bits, all 16 control lines, CLK, PROG/PROG_hat - and nothing
else: no readouts, no conveniences, nothing the machine does not have.
The arrangement mirrors the Digital build: left column CLOCK, MAR, RAM,
IR, CONTROL; right column PC (top), A, ALU, B, OUTPUT; the BUS runs
down the middle between them, the wire itself drawn running the
panel's height.

## Run it locally

From the repo root:

    python3 -m http.server

then open <http://localhost:8000/web/>. (An HTTP server, not
`file://` - the app fetches the ROM images from ../roms/.) Any static
host works the same way; every file the app fetches is in the repo.
Open the app with `?smoke=1` to run its built-in self-check - the pure
way: a program entered through the switches, the gating, the clock
(results in the status line).

## Tests

    python3 web/test/verify.py      # every gallery program on js/machine.js
    node web/test/test_display.mjs  # the display ROM decode vs known patterns

Correctness of the machine is defined by the expectations frozen in
[test/verify.py](test/verify.py)'s table - for every program, the halt
status, the OUT count, and the first 32 OUT values - and each build
must reproduce them exactly.

## What is here

| file            | what it is                                                    |
|-----------------|---------------------------------------------------------------|
| index.html      | the page: a header, the panel, the footer                      |
| css/style.css   | the looks - the faceplate, lamps, keycaps, switches            |
| js/hex.js       | memory-image parsing: logisim .hex, Intel HEX, raw (the JS twin of the formats in tools/genroms.py) |
| js/machine.js   | the machine: control-word bits (tools/genroms.py) + the cycle-accurate core |
| js/display.js   | the display: output-display.hex decode + the seven-segment canvas |
| js/panel.js     | the parts as DOM: modules, lamp banks, switches, keys           |
| js/main.js      | the wiring: the clock, the panel, the render loop, the self-test |
| js/run.mjs      | headless CLI runner (node web/js/run.mjs programs/count.bin)    |
| build.py        | writes programs/*.bin + .lst artifacts next to the .hl sources for inspection, manual entry and the headless runner (the web app does not need them) |
| test/verify.py  | runs every program on js/machine.js against the frozen expectations |
| test/test_display.mjs | the display ROM decode against known patterns            |
