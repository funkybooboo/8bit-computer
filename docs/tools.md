# Tools

The toolchain in [../tools/](../tools/). Digital is one way this machine
gets built, not the machine itself, so the tools split by level:

- **machine-level** - know nothing about Digital: `machine.py` (the
  machine's own definitions), `asm.py` (the assembler), `sim.py` (the
  cycle-accurate simulator). These work from any clone, no Digital, no
  JDK.
- **Digital-specific** - the bridge to the Digital build: `digrom.py`
  (ROM data inside .dig circuits), `dignetlist.py` (netlists out of .dig
  circuits), `DigSim.java`/`digsim` (headless Digital simulation).
- **reference** - `kicadnets.py`, the netlist out of Ben's KiCad project:
  the wiring reference for any build target, Digital or breadboard.

The image files are the bridge between levels and targets: the
assembler emits them (logisim hex / Intel HEX / raw), the simulator reads
them back, EEPROM burners and Digital's ROM editor load them, and
[../roms/](../roms/README.md) archives the machine's own ROM images.

## The workflow

1. **Wire** a module in Digital from Ben's schematics ([../schematics/](../schematics/README.md)).
2. **Verify the wiring**: `dignetlist.py` extracts the netlist from the
   .dig; `kicadnets.py` prints the reference netlist from Ben's KiCad
   project; compare pin by pin.
3. **Program EEPROMs** with `digrom.py` (images archived in
   [../roms/](../roms/README.md); contents defined in machine.py).
4. **Run programs** with `asm.py` + `sim.py` - the machine itself is the
   last mile (load the image through the front panel,
   [hardware.md](hardware.md)).

## machine.py - the machine itself, in code

    python3 tools/machine.py     # print the instruction/microstep table

Everything that is true of the machine no matter how it is built: the
opcode numbers, the 16-bit control word, the microcode (the MICROSTEPS
table - the source of truth for what each instruction does,
[microcode.md](microcode.md)), the ROM contents (control ROMs, display
ROM), and the image formats. The assembler, the simulator and the
Digital tools all import from here, so they can never disagree about an
opcode or a microstep. The microcode is written in a small notation, one
line per instruction:

    LDA:  "MI,IO / RO,AI"        # T2, T3 after the shared fetch
    JC:   "IO,J if CF"            # only in the CF=1 halves of the images
    ADDI: "IO,BI / EO,AI,FI"

`/` separates microsteps (numbered from T2 - T0/T1 are the shared fetch),
`,` separates control lines within a step, `if CF` / `if not ZF` make a
step conditional on a flag half. Run the file to see the resulting table.

## digrom.py - EEPROM data in .dig circuits

    tools/digrom.py presets
    tools/digrom.py dump  --dig digital/Computer.dig --label U45 --words
    tools/digrom.py write --dig digital/Computer.dig --label U47 --preset control-rom1
    tools/digrom.py write --dig c.dig --label U1 --hexfile myrom.hex --size 2048
    tools/digrom.py export --preset control-rom1 --out roms/control-rom1.hex

ROM data for embedded DIL chips is stored at the circuit level under the
`romContent` attribute, keyed by chip instance Label (Digital 0.31
format; Digital round-trips it on re-save). `write` does a surgical text
edit (keeps the file's formatting), then re-reads and round-trip checks
before atomically replacing the file.

The data itself is machine-level: presets and images come from
machine.py and [../roms/](../roms/README.md). Changing the microcode:
edit MICROSTEPS in machine.py, `export` to [../roms/](../roms/), `write`
into Computer.dig, then `sim.py --selftest` and run the gallery through
`sim.py` before touching hardware.

## asm.py - assembler / disassembler

    tools/asm.py programs/count.asm                                  # listing to stdout
    tools/asm.py programs/count.asm --out p.hex --lst p.lst         # image + listing
    tools/asm.py programs/count.asm --out p.bin --format raw
    tools/asm.py --dis p.hex                                        # disassemble an image

Two-pass assembler for the one-byte instruction format
([opcode:4][operand:4]); language reference:
[assembly-language.md](assembly-language.md). Rejects anything the
hardware cannot encode. The listing shows each byte in hex and in ones
and zeros as the three hardware groups - RAM address | opcode | operand -
which are also the dipswitch groups for program entry. Image formats are
machine.py's (logisim / intel / raw).

## sim.py - cycle-accurate simulator

    tools/sim.py programs/powers.asm            # run: OUT stream + summary
    tools/sim.py programs/rotate.asm --max-cycles 5000
    tools/sim.py programs/count.asm --trace 40 # per-cycle trace (stderr)
    tools/sim.py --selftest                     # verify the ROM images

Loads the control-ROM images from [../roms/](../roms/) (the same images
the hardware burns and Computer.dig carries) and executes the microcode
itself: fetch, flags, bus drivers, register latches - no per-instruction
special cases. So it verifies the microcode and the ROM files, not just
programs. Accepts .asm sources or .hex/.bin images; stdout carries the
OUT stream, summary and trace go to stderr; exit status tells halt vs.
cycle cap. Every program in the gallery passes it
([programs.md](programs.md)).

## dignetlist.py - netlist extraction

    tools/dignetlist.py --dig digital/Computer.dig

Prints every element, every pin, and the members of the net each pin is
on. Warns about wire endpoints touching the middle of another wire
(T-junctions are NOT connections in Digital) and about unconnected chip
pins. Pin geometry is real Digital geometry (In/Out/LED at element pos;
DIL chips 40 px pitch, left column pins 1..N/2 top-down, right column
bottom-up; Seven-Seg segment pins on the top/bottom edges) - verified
against the Digital 0.31 source.

## kicadnets.py - the reference netlist

    tools/kicadnets.py --net kicad/8bit-computer.net --refs U44,U45,U46

Prints every net containing the given component refs, as (ref, pin)
pairs, from Ben's KiCad netlist. Chip pin maps (74LS273, 28C16, 74LS76,
74LS139, 74LS08) are in the file's header comment. One KiCad symbol
quirk to know when comparing: Ben's 74LS00 rescue symbol has
non-standard gate 3/4 pin roles (documented, with the rest of the
wiring notes, in [hardware.md](hardware.md)).

## digsim - headless Digital simulator

    tools/digsim --dig digital/Computer.dig --list
    tools/digsim --dig digital/Computer.dig --toggle 'MUX\_CLK:8' --render

Runs any .dig headless through Digital's own model (compiles DigSim.java
against Digital.jar; needs a JDK and Digital.jar, auto-located or set via
DIGITAL_JAR / JAVA_HOME). Options in command-line order: `--set NAME=VALUE`,
`--edge NAME`, `--toggle NAME:N`, `--steps N`, `--render` (seven-segment
display state during toggles), `--watch LABEL.pin` or `--watch x,y`,
`--dump [FILTER]`, `--pins [FILTER]` (element pins with real positions),
`--nets` (Digital's own flattened nets - the view that exposed the
library bugs below). Labels with underscores are stored backslash-escaped
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
  was investigated and dropped; program behavior is verified headless
  with sim.py). The display path (MUX_CLK multiplexing) does simulate.
- **74157**: with a 74245 pin on any of its B-input nets, the mux
  outputs zeros on the *selected* A path (reproduced in isolation:
  clean A inputs, B inputs grounded except one on a 74245 - with or
  without the 74245 enabled, at either rotation; the same mux with a
  plain Driver or In on the B net is correct). This is the concrete
  mechanism behind the earlier "mix of bus and dipswitch values"
  observation, and it is why the front-panel program entry writes
  garbage under Digital 0.31 even in program mode: the RAM data muxes
  (U26/U27) have their B inputs on the shared bus, which is built from
  74245 pins. Test panel entry only on a newer Digital release.
- **Switch/DipSwitch/Button** elements are not model inputs, so
  `digsim --set` cannot drive them; test those paths in the GUI.

Running Computer.dig in the Digital GUI: toolbar play button or space;
the master clock U1 runs at its Frequency attribute (double-click to
edit); F6 opens a live value table; Run menu -> micro step (G) for
gate-level stepping. Program entry through the front panel:
[hardware.md](hardware.md), "Front panel".
