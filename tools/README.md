# Tools

Helpers for building Ben Eater's 8-bit computer (https://eater.net/8bit) in
Digital (https://github.com/hneemann/Digital) before building it on
breadboards. Everything here was developed and verified while building the
modules; all circuits now live in one file, digital/Computer.dig (the
per-module .dig files are gone - git history has them).

| file          | what it is                                                        |
|---------------|-------------------------------------------------------------------|
| digrom.py     | EEPROM writer/reader/exporter for .dig circuits (presets, hex/bin) |
| asm.py        | Assembler/disassembler (labels, .DB/.ORG/.EQU, char literals, bits listing) |
| sim.py        | Cycle-accurate simulator: runs the real control-ROM microcode |
| dignetlist.py | Netlist extraction from a .dig with real Digital pin geometry     |
| kicadnets.py  | Reference netlist extraction from Ben's KiCad .net (pin maps in header) |
| DigSim.java   | Headless simulator source (set/edge/toggle/steps/watch/dump/render) |
| digsim        | Wrapper: locates Digital.jar + JDK, compiles and runs DigSim       |
| README.md     | This file: workflow and usage                                     |

## The workflow (how every module was built and verified)

1. Wire the module in Digital from Ben's schematic (schematics/*.png,
   kicad/*.sch).
2. **Verify the wiring** before debugging behavior:
   - `dignetlist.py` extracts the netlist from the .dig (real Digital pin
     geometry, auto-loaded from Digital's installed library).
   - `kicadnets.py` prints the reference netlist from Ben's KiCad project
     (kicad/8bit-computer.net).
   - Compare pin by pin. This caught nothing in the Output Register (wiring
     was perfect) but found the actual bug: an unprogrammed EEPROM.
3. **Program EEPROMs** with `digrom.py` (presets or hex/binary files, stored
   in the .dig and archived in ../roms/).
4. **Simulate headless** with `digsim` - set inputs, clock, mux-toggle and
   render the seven-segment display without opening the GUI:
   `tools/digsim --dig digital/Computer.dig --list`
   (the shared bus of the merged circuit is not reliable in Digital 0.31 -
   see ../digital/README.md, "Known Digital 0.31 simulation bugs" - but the
   ROM/netlist tooling works on it as-is).

## digrom.py - EEPROM data in .dig circuits

    tools/digrom.py presets
    tools/digrom.py dump  --dig digital/Computer.dig --label U45 --words
    tools/digrom.py write --dig digital/Computer.dig --label U45 --preset output-display
    tools/digrom.py write --dig c.dig --label U1 --hexfile myrom.hex --size 2048
    tools/digrom.py export --preset output-display --out rom.hex --format logisim

ROM data for embedded DIL chips is stored at the circuit level under the
`romContent` attribute, keyed by chip instance Label (Digital 0.31 format;
Digital round-trips it on re-save - verified). `write` does a surgical text
edit (keeps your file formatting), then re-reads and round-trip checks the
result before atomically replacing the file.

New ROMs go into the `PRESETS` dict in digrom.py - each preset is a function
returning bytes - and get archived to ../roms/ via `export`. Existing presets:
`output-display`, `control-rom1`, `control-rom2` (the control-logic
microcode; see ../roms/README.md for the address/data encoding).

## asm.py - assembler / disassembler

    tools/asm.py programs/count.asm                                  # listing to stdout
    tools/asm.py programs/count.asm --out p.hex --lst p.lst           # image + listing file
    tools/asm.py programs/count.asm --out p.bin --format raw
    tools/asm.py --dis p.hex                                         # disassemble an image

Two-pass assembler for the machine's one-byte instruction format
([opcode:4][operand:4]): labels, `.DB`/`.ORG`/`.EQU` directives, `;`
comments, literals (decimal / 0x / 0b / 'c' char). Rejects everything the
hardware cannot encode: operands outside 0-15 (the operand field is one
nibble), programs larger than the 16-byte RAM, duplicate/undefined/
shadowing names. Mnemonics cover the full 16-opcode set including this
project's additions (JNC/JNZ/ADDI/SUBI/DBL - see
../docs/instruction-set.md).

## sim.py - cycle-accurate simulator

    tools/sim.py programs/powers.asm            # run: OUT stream + summary
    tools/sim.py programs/rotate.asm --max-cycles 5000
    tools/sim.py programs/count.asm --trace 40  # per-cycle trace (stderr)
    tools/sim.py --selftest                     # verify the ROM images

Loads the control-ROM images from ../roms/ (the same images the hardware
burns and Computer.dig carries) and executes the microcode itself: fetch,
flags, bus drivers, register latches - no per-instruction special cases.
So it verifies the microcode and the ROM files, not just programs:
run it after any preset change in digrom.py (and re-inject into the .dig
before running anything on the machine). Accepts .asm sources or
.hex/.bin images; stdout carries the OUT stream, the summary and any
trace go to stderr; exit status tells halt vs. cycle cap.

The listing shows each byte in hex and in straight ones and zeros as the
three hardware groups - RAM address | opcode | operand - which are also the
dipswitch groups for program entry. Image formats reuse digrom.py's
(logisim / intel / raw). The disassembler decodes linearly; data and
undefined opcodes print as `.DB 0xNN`.

Language reference: ../docs/assembly-language.md; instruction set:
../docs/instruction-set.md; programs: ../programs/.

Segment encoding used by Ben's display ROMs (verified against his KiCad
netlist):

    ROM bit:  7    6   5   4   3   2   1   0
    segment: dp    a   b   c   d   e   f   g

    digits 0-9: 7e 30 6d 79 33 5b 5f 70 7f 7b
    hex A-F:    77 1f 4e 3d 4f 47   (A b C d E F)
    blank:      00

## dignetlist.py - netlist extraction and wiring check

    tools/dignetlist.py --dig digital/Computer.dig

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

    tools/digsim --dig digital/Computer.dig --list
    tools/digsim --dig digital/Computer.dig --toggle 'MUX\_CLK:8' --render

(The second example multiplexes the front-panel display, which does not
touch the shared bus; the merged circuit's In test elements are gone - use
`--list` to see what is settable. From the standalone-module era, a module
example looked like: `--set 'CLR\_hat=1' --set 'OI=1' --set 'BUS\_1=1' --edge
CLK --toggle 'MUX\_CLK:8'`.)

Options (executed in command line order): `--set NAME=VALUE` (0x/0b/decimal;
auto-steps), `--edge NAME` (0->1->0 pulse), `--toggle NAME:N` (N half-cycles
with a step after each), `--steps N`, `--render` (print the Seven-Seg display
state during toggles; '.' = disabled display), `--watch LABEL.pin` or
`--watch x,y` (print a pin value), `--dump [FILTER]` (print all pin values),
`--pins [FILTER]` (print every element's pins with their real positions -
useful when a wire endpoint looks unconnected; wire-connected input pins of
embedded DIL chips show no value there, use --watch on In/Out/LED pins
instead), `--nets` (print Digital's own nets from ModelCreator.netList -
every pin of every net with name, position, direction and value, including
the flattened internals of embedded DIL chips; the tool that exposed the
Digital 0.31 74173/74245/74157 library bugs listed in ../digital/README.md).
`--toggle` also prints a `display(mux full cycle)` summary merging what each
display showed across a full multiplex cycle.

Digital stores labels containing underscores with a backslash escape
(e.g. `BUS\_1`); --set accepts both the escaped and plain forms.

Needs Digital.jar and a JDK (found via DIGITAL_JAR / JAVA_HOME, or
auto-detected from the `digital` executable / nix store). Compiles DigSim.java
into ~/.cache/digsim on first use. Reflection-based (ModelCreator.netList),
so it is Digital-version specific (tested on 0.31).
