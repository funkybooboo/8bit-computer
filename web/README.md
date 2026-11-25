# web/ - the machine in a browser

The machine emulated in a browser - the repo's only emulator: the
same machine as [digital/Computer.dig](../digital/Computer.dig),
running the same ROM images, drawn as the machine itself - its
modules, lamps and switches, laid out like the Digital build - in
pure HTML, CSS and JavaScript, no build tools, no frameworks,
no network dependencies. A static directory any web server can host.

The app is deliberately nothing more than the machine. It powers on
with empty RAM (16 NOPs) and the clock running, like the bench machine
with the power on - and a program is loaded exactly one way, the way
the hardware does it:

## Entering a program

The procedure - dipswitch groups, readback lamps, mode switch - is
the machine's: [../docs/hardware.md](../docs/hardware.md),
"Front panel"; the app's footer has the same steps. Writing programs
is the repo's job, not the app's: the sources are
[programs/](../programs/README.md) (the .hl language:
[docs/language.md](../docs/language.md)), and the listings are one
command away - `python3 tools/compile.py programs/count_up.hl` writes
`count_up.lst` (the entry table) next to the source, or
`python3 programs/build.py` does the whole gallery.

## What makes it a close emulation

The one rule: js/machine.js runs the actual control-ROM images
([roms/control-rom1.hex](../roms/control-rom1.hex) and
[roms/control-rom2.hex](../roms/control-rom2.hex)) - the same images
the Digital build carries and the hardware burns - asserting the
control word at (step, opcode, CF, ZF) every cycle. Nothing is
special-cased per instruction: if the microcode is wrong, programs
fail here exactly the way they fail on the machine. The rest of the
fidelity story - the two-edge clock, bus discipline, pre-edge
latching, RESET as wired, the display path, where every control
wires - is documented in
[../docs/microcode.md](../docs/microcode.md) and
[../docs/hardware.md](../docs/hardware.md), with design notes at
the top of js/machine.js and js/display.js.

The panel shows every lamp the hardware has and nothing else -
no readouts, no conveniences, nothing the machine does not have
([../docs/hardware.md](../docs/hardware.md), "Front panel"). The
arrangement mirrors the Digital build: left column CLOCK, MAR, RAM,
IR, CONTROL; right column PC (top), A, ALU, B, OUTPUT; the BUS runs
down the middle, the wire itself drawn running the panel's height.

## Run it locally

mise does both steps: `mise run web`. By hand, from the repo root:

    python3 -m http.server

then open <http://localhost:8000/web/>. (An HTTP server, not
`file://` - the app fetches the ROM images from ../roms/.) Any static
host works the same way; every file the app fetches is in the repo.
Open the app with `?smoke=1` to run its built-in self-check - the pure
way: a program entered through the switches, the gating, the clock
(results in the status line).

## Tests

    python3 programs/verify.py      # every gallery program on js/machine.js
    node web/test/test_display.mjs  # the display ROM decode vs known patterns

Correctness is defined by the frozen expectations in
[../programs/verify.py](../programs/verify.py) - the contract every
build must reproduce ([../docs/tools.md](../docs/tools.md), "Running programs").

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
| js/run.mjs      | headless CLI runner (node web/js/run.mjs programs/count_up.bin)    |
| test/test_display.mjs | the display ROM decode against known patterns            |
