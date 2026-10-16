# Tools

Helpers for building Ben Eater's 8-bit computer (https://eater.net/8bit) in
Digital (https://github.com/hneemann/Digital) before building it on
breadboards. Everything here was developed and verified while building the
Output Register module; the same workflow applies to the next modules.

| file          | what it is                                                        |
|---------------|-------------------------------------------------------------------|
| digrom.py     | EEPROM writer/reader/exporter for .dig circuits (presets, hex/bin) |
| dignetlist.py | Netlist extraction from a .dig with real Digital pin geometry     |
| kicadnets.py  | Reference netlist extraction from Ben's KiCad .net (pin maps in header) |
| DigSim.java   | Headless simulator source (set/edge/toggle/steps/watch/dump/render) |
| digsim        | Wrapper: locates Digital.jar + JDK, compiles and runs DigSim       |
| README.md     | This file: workflow and usage                                     |

## The workflow

1. Wire the module in Digital from Ben's schematic (schematics/*.png,
   kicad/*.sch).
2. **Verify the wiring** before debugging behavior:
   - `dignetlist.py` extracts the netlist from your .dig (real Digital pin
     geometry, auto-loaded from Digital's installed library).
   - `kicadnets.py` prints the reference netlist from Ben's KiCad project
     (kicad/8bit-computer.net).
   - Compare pin by pin. This caught nothing in the Output Register (wiring
     was perfect) but found the actual bug: an unprogrammed EEPROM.
3. **Program EEPROMs** with `digrom.py` (presets or hex/binary files, stored
   in the .dig and archived in ../roms/).
4. **Simulate headless** with `digsim` - set inputs, clock, mux-toggle and
   render the seven-segment display without opening the GUI:
   `tools/digsim --dig "digital/Output Register.dig" --list`

## digrom.py - EEPROM data in .dig circuits

    tools/digrom.py presets
    tools/digrom.py dump  --dig "digital/Output Register.dig" --label U45 --words
    tools/digrom.py write --dig "digital/Output Register.dig" --label U45 --preset output-display
    tools/digrom.py write --dig c.dig --label U1 --hexfile myrom.hex --size 2048
    tools/digrom.py export --preset output-display --out rom.hex --format logisim

ROM data for embedded DIL chips is stored at the circuit level under the
`romContent` attribute, keyed by chip instance Label (Digital 0.31 format;
Digital round-trips it on re-save - verified). `write` does a surgical text
edit (keeps your file formatting), then re-reads and round-trip checks the
result before atomically replacing the file.

New ROMs (e.g. the control-logic microcode when that module gets built) go
into the `PRESETS` dict in digrom.py - each preset is a function returning
bytes - and get archived to ../roms/ via `export`.

Segment encoding used by Ben's display ROMs (verified against his KiCad
netlist):

    ROM bit:  7    6   5   4   3   2   1   0
    segment: dp    a   b   c   d   e   f   g

    digits 0-9: 7e 30 6d 79 33 5b 5f 70 7f 7b
    hex A-F:    77 1f 4e 3d 4f 47   (A b C d E F)
    blank:      00

## dignetlist.py - netlist extraction and wiring check

    tools/dignetlist.py --dig "digital/Output Register.dig"

Prints every element, every pin, and the members of the net each pin is on
(e.g. `A8 -> ['U37.1~Q', 'U37.2~CLK', 'U38.1A', 'U45.A8']`). Also warns about
wire endpoints touching the middle of another wire (T-junctions are NOT
connections in Digital) and about unconnected chip pins.

Pin geometry (verified against Digital 0.31 source):
- In/Out/Clock/Ground/VDD/NotConnected: one pin at the element pos.
- DIL chips: 40 px pitch; left column pins 1..N/2 top-down at
  (x, y + 40*(p-1)); right column pin p at (x + 20*(Width+1), y + 40*(N-p)).
  N and pin names come from the chip's .dig in Digital's library
  (auto-located; override with --lib or $DIGITAL_LIB).
- Seven-Seg: a-d on top at rel (0..60, 0); e,f,g,dp on the bottom at
  rel (0..60, 140); cc/ca at rel (80, 140) with a common connection
  attribute. Common cathode enables a digit while cc is LOW.

## kicadnets.py - reference netlist from Ben's KiCad

    tools/kicadnets.py --net kicad/8bit-computer.net --refs U44,U45,U46

Prints every net containing the given component refs, as (ref, pin) pairs.
The header comment in the file lists the pin maps for the chips used in this
project.

## digsim - headless simulator

    tools/digsim --dig "digital/Output Register.dig" --list
    tools/digsim --dig "digital/Output Register.dig" \
        --set 'CLR\_hat=1' --set 'OI=1' --set 'BUS\_1=1' --set 'BUS\_5=1' \
        --set 'SW\_7=1' --edge CLK --toggle 'MUX\_CLK:8'

Options (executed in command line order): `--set NAME=VALUE` (0x/0b/decimal;
auto-steps), `--edge NAME` (0->1->0 pulse), `--toggle NAME:N` (N half-cycles
with a step after each), `--steps N`, `--render` (print the Seven-Seg display
state during toggles; '.' = disabled display), `--watch LABEL.pin` or
`--watch x,y` (print a pin value), `--dump [FILTER]` (print all pin values).
`--toggle` also prints a `display(mux full cycle)` summary merging what each
display showed across a full multiplex cycle.

Digital stores labels containing underscores with a backslash escape
(e.g. `BUS\_1`); --set accepts both the escaped and plain forms.

Needs Digital.jar and a JDK (found via DIGITAL_JAR / JAVA_HOME, or
auto-detected from the `digital` executable / nix store). Compiles DigSim.java
into ~/.cache/digsim on first use. Reflection-based (ModelCreator.netList),
so it is Digital-version specific (tested on 0.31).
