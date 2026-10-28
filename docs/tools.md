# Tools

The software that serves the machine. [../tools/](../tools/) holds the
machine-level tools (they work from any clone - no Digital, no JDK, no
node needed); each build directory holds the tools that belong to it:

- **tools/** - `asm.py` (the assembler) and `genroms.py` (the
  instruction set and microcode in code, and the script that generates
  the ROM images every build runs).
- **digital/** - the Digital build's own tools: `rom.py` (ROM data
  inside .dig circuits), `netlist.py` (netlists out of .dig
  circuits), `DigSim.java`/`digsim` (headless Digital simulation).
- **kicad/** - `netlist.py`: the netlist out of Ben's KiCad project,
  the wiring reference for any build target, Digital or breadboard.
- **web/** - the browser build, plus its test against the expected
  outputs (below).

The image files are the bridge between tools and targets: the assembler
emits them (logisim hex / Intel HEX / raw), EEPROM burners and Digital's
ROM editor load them, and [../roms/](../roms/README.md) archives the
machine's own ROM images.

## The workflow

1. **Wire** a module in Digital from Ben's schematics ([../schematics/](../schematics/README.md)).
2. **Verify the wiring**: `netlist.py` extracts the netlist from the
   .dig; `netlist.py` prints the reference netlist from Ben's KiCad
   project; compare pin by pin.
3. **Program EEPROMs** with `rom.py` (images archived in
   [../roms/](../roms/README.md); contents defined in `genroms.py`).
4. **Run programs** in the browser build - the machine itself is the
   last mile (load the image through the front panel,
   [hardware.md](hardware.md)).

## genroms.py - the ROM generator (the machine's tables in code)

    tools/genroms.py             # print the instruction/microstep table
    tools/genroms.py --generate  # regenerate the ../roms/ images
    tools/genroms.py --check     # verify the ../roms/ images match it

The machine's definition, independent of how it is built: the opcode
numbers, the 16 control lines, and the MICROSTEPS table - the source of
truth for what every instruction does, step by step
([microcode.md](microcode.md)). The control-ROM images in
[../roms/](../roms/README.md) are generated from this table, and every
build of the machine runs those images: digital/Computer.dig,
web/js/machine.js, the breadboards. The assembler imports the opcode
numbers from here, so tools and builds can never disagree about an
opcode or a microstep. The microcode is written in a small notation,
one line per instruction:

    LDA:  "MI,IO / RO,AI"        # T2, T3 after the shared fetch
    JC:   "IO,J if CF"            # only in the CF=1 halves of the images
    ADDI: "IO,BI / EO,AI,FI"

`/` separates microsteps (numbered from T2 - T0/T1 are the shared fetch),
`,` separates control lines within a step, `if CF` / `if not ZF` make a
step conditional on a flag half. Run the file to see the resulting table.
`--generate` (re)writes the images in [../roms/](../roms/README.md) -
logisim .hex plus Intel HEX for EEPROM burners; the roms are shared by
every build, and each build uploads them its own way (Digital via
`rom.py`, the web build by fetching them, the hardware by burning the
Intel files). `--check` verifies the archived images are exactly these
tables. The image formats themselves (raw binary / logisim / Intel HEX) are
also defined in this file; the web build's twin is web/js/hex.js.

## compile.py - the .hl compiler

    tools/compile.py programs/count.hl        # -> count.asm + count.lst + count.bin
    tools/compile.py programs/count.hl --stdout    # the generated .asm only

Compiles [language.md](language.md) - the high-level language - to the
assembly language, validates the result by assembling it, and writes
three files beside the source: the .asm (for inspection, gitignored),
the .lst - the front-panel entry table, the dipswitch bit groups for
every address - and the .bin, the bare 16-byte machine image. The language covers the whole machine (every opcode is reachable
from some construct) and refuses at compile time what the hardware
cannot do: e * e, division, boolean values, functions, arrays,
programs that do not fit the 16 bytes. The compiler emits the corpus's
hand-written idioms - accumulator tracking makes `out x` after
`x = ...` one byte, `x = x - y` after `while x >= y` reuse the
compare's subtraction, `x >= 128` is the DBL top-bit test - so the
generated assembly reads like the hand-written programs did.

## asm.py - assembler / disassembler

    tools/asm.py programs/count.asm                       # listing to stdout
    tools/asm.py programs/count.asm --out p.bin --lst p.lst   # image + listing
    tools/asm.py --dis p.bin                              # disassemble an image

Two-pass assembler for the one-byte instruction format
([opcode:4][operand:4]); language reference:
[assembly-language.md](assembly-language.md). Rejects anything the
hardware cannot encode. The listing shows each byte in hex and in ones
and zeros as the three hardware groups - RAM address | opcode | operand -
which are also the dipswitch groups for program entry. The default image
format is `raw` - bare binary, the .bin. Image formats are
`genroms.py`'s (raw / logisim / intel; the last two exist for the
machine's own ROM contents).

## Running programs: the web build and the expected outputs

    python3 web/build.py     # compile + assemble the programs the app serves
    python3 -m http.server   # from the repo root; open http://localhost:8000/web/
    node web/js/run.mjs programs/count.bin    # headless CLI on the same machine model
    python3 web/test/verify.py  # every program vs its frozen expectations

The web build runs the same control-ROM images the hardware burns, so a
program behaves there exactly the way it behaves on the machine. What
"correct" means is defined by the expectations frozen in
web/test/verify.py's table: for every program, the halt status, the
OUT count within 20,000 cycles, and the first 32 OUT values - and every
build of the machine must reproduce them exactly. Changing a program's
intended behavior means updating that table deliberately.

## rom.py - EEPROM data in .dig circuits

    digital/rom.py presets
    digital/rom.py dump  --dig digital/Computer.dig --label U45 --words
    digital/rom.py write --dig digital/Computer.dig --label U47 --preset control-rom1
    digital/rom.py write --dig c.dig --label U1 --hexfile myrom.hex --size 2048
    digital/rom.py export --preset control-rom1 --out roms/control-rom1.hex

ROM data for embedded DIL chips is stored at the circuit level under the
`romContent` attribute, keyed by chip instance Label (Digital 0.31
format; Digital round-trips it on re-save). `write` does a surgical text
edit (keeps the file's formatting), then re-reads and round-trip checks
before atomically replacing the file.

The data itself is machine-level: presets and images come from
`genroms.py` and [../roms/](../roms/README.md). Changing the
microcode: edit MICROSTEPS in `tools/genroms.py`, `--generate` into
[../roms/](../roms/README.md), `write` into Computer.dig with `rom.py`,
then `tools/genroms.py --check` and `web/test/verify.py` before touching
hardware.

## digital/netlist.py - netlist extraction

    digital/netlist.py --dig digital/Computer.dig

Prints every element, every pin, and the members of the net each pin is
on. Warns about wire endpoints touching the middle of another wire
(T-junctions are NOT connections in Digital) and about unconnected chip
pins. Pin geometry is real Digital geometry (In/Out/LED at element pos;
DIL chips 40 px pitch, left column pins 1..N/2 top-down, right column
bottom-up; Seven-Seg segment pins on the top/bottom edges) - verified
against the Digital 0.31 source.

## kicad/netlist.py - the reference netlist

    kicad/netlist.py --net kicad/8bit-computer.net --refs U44,U45,U46

Prints every net containing the given component refs, as (ref, pin)
pairs, from Ben's KiCad netlist. Chip pin maps (74LS273, 28C16, 74LS76,
74LS139, 74LS08) are in the file's header comment. One KiCad symbol
quirk to know when comparing: Ben's 74LS00 rescue symbol has
non-standard gate 3/4 pin roles (documented, with the rest of the
wiring notes, in [hardware.md](hardware.md)).

## digsim - headless Digital simulator

    digital/digsim --dig digital/Computer.dig --list
    digital/digsim --dig digital/Computer.dig --toggle 'MUX\_CLK:8' --render

Runs any .dig headless through Digital's own model (compiles DigSim.java
against Digital.jar; needs a JDK and Digital.jar, auto-located or set via
DIGITAL_JAR / JAVA_HOME). Options in command-line order: `--set NAME=VALUE`,
`--edge NAME`, `--toggle NAME:N`, `--steps N`, `--render` (seven-segment
display state during toggles), `--watch LABEL.pin` or `--watch x,y`,
`--dump [FILTER]`, `--pins [FILTER]` (element pins with real positions),
`--nets` (Digital's own flattened nets - the view that exposed the
library bugs below), `--setpos X,Y=VALUE` (drive a DipSwitch or Button
output by element position - switches are not model inputs, so --set
cannot reach them; e.g. `--setpos -220,3020=1`), `--switch NAME=0|1`
(open/close a SwitchDT by Label; closed connects the common pin to the
B1 throw - this is how PROG_ADDR/RESET/PROG_WRITE are driven headless).
Labels with underscores are stored backslash-escaped
(`BUS\_1`); --set accepts both forms.

Reflection-based (ModelCreator.netList), so it is Digital-version
specific (tested on 0.31).

## Digital 0.31 notes

Bugs in Digital 0.31's bundled DIL chip library - they affect
*simulating* this circuit, not the circuit's correctness (the wiring
matches the KiCad reference pin for pin; the facts below were observed
with digsim --nets):

- **74173**: the model's RES input is active-HIGH; the real chip's MR is
  active LOW. In simulations hold the clear input at 0 and pulse 1.
- **74245**: the direction-enable And gates use input-inversion bubbles,
  and the model drops the inversions on one of the two gates (which one
  varies with the surrounding netlist). Net effect: a "disabled" 74245
  wrongly drives one direction, so A/B nets cross-couple. Modules whose
  bus side had no other drivers simulated correctly; modules with
  bus-side loads fought the wrongly-enabled transceiver. This makes the
  shared bus of Computer.dig unreliable in Digital 0.31 simulation -
  a newer Digital release is the fix (patching a local 74245.dig copy
  was investigated and dropped; program behavior is verified against
  the frozen expected outputs instead, via web/test/verify.py). The
  display path (MUX_CLK multiplexing) does simulate.
- **Driver (core, FIXED HERE)**: the tri-state Driver element - the
  buffer inside the 74245/74189 models and the multiplexer output path
  - converted a high-Z input into a random-noise *driven* output
  (`getValue()` returns random bits for high-Z). At model init, with
  all inputs at 0, the B->A transceivers started enabled, read the
  floating side, and drove noise onto nets that were also driven by
  real sources: a bus burn, and Digital swallows the BurnException and
  closes the *entire model* (every later input change is silently
  ignored - the machine shows frozen mid-init garbage, different every
  run). This was the root cause of the "74157 mixes bus and dipswitch"
  observation above and of all panel-entry corruption; the 74157 and
  74245 chip models themselves are correct. The fix is
  [Driver.java](../digital/Driver.java): propagate the input's high-Z
  to the output. `digital/gui` builds a patched Digital.jar on demand
  (cache: ~/.cache/digital-patched/Digital.jar) and launches the GUI;
  point digsim at the same jar with
  `DIGITAL_JAR=~/.cache/digital-patched/Digital.jar`. With the fix,
  front-panel entry writes and reads back every byte deterministically.
- **Burn-on-transition (core, unfixed)**: on some model builds a
  transient two-driver overlap during clock-edge settling still trips
  the burn check and closes the model mid-run (order-dependent, about
  half of headless runs). If the machine freezes at garbage in the
  GUI, stop and restart the simulation - the next build usually runs
  clean through the whole program.
- **Switch/DipSwitch/Button** elements are not model inputs, so
  `digsim --set` cannot drive them; test those paths in the GUI.

Running Computer.dig in the Digital GUI: toolbar play button or space;
the master clock U1 runs at its Frequency attribute (double-click to
edit); F6 opens a live value table; Run menu -> micro step (G) for
gate-level stepping. Program entry through the front panel:
[hardware.md](hardware.md), "Front panel".
