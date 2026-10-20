# Tools

The toolchain in [../tools/](../tools/): verifying wiring, programming
EEPROMs, assembling programs, and running them without the machine. All
of it was built and used against the real circuits; nothing here is
speculative.

## The workflow

1. **Wire** a module in Digital from Ben's schematics ([../schematics/](../schematics/README.md)).
2. **Verify the wiring**: `dignetlist.py` extracts the netlist from the
   .dig; `kicadnets.py` prints the reference netlist from Ben's KiCad
   project; compare pin by pin.
3. **Program EEPROMs** with `digrom.py` (presets archived in
   [../roms/](../roms/README.md)).
4. **Run programs** with `asm.py` + `sim.py` - the machine itself is the
   last mile (load the image through the front panel,
   [hardware.md](hardware.md)).

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

The microcode presets are `control-rom1` / `control-rom2` (source of
truth for the microcode itself - the tables in
[microcode.md](microcode.md) describe what they encode); the display
preset is `output-display` (what it encodes:
[hardware.md](hardware.md), "The display"). Changing the microcode: edit
the preset, `export` to [../roms/](../roms/), `write` into
Computer.dig, then `sim.py --selftest` and run the gallery through
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
which are also the dipswitch groups for program entry. Image formats
reuse digrom.py's (logisim / intel / raw).

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
74LS139, 74LS08) are in the file's header comment - including Ben's
KiCad symbol quirks (e.g. the 74LS00 rescue symbol's non-standard gate
3/4 pin roles; compare the function, not the pin numbers, there).

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
- **74157**: the MAR's load path misbehaved in the headless model (D
  inputs ended up with a mix of bus and dipswitch values regardless of
  the select); not root-caused.
- **Switch/DipSwitch/Button** elements are not model inputs, so
  `digsim --set` cannot drive them; test those paths in the GUI.

Running Computer.dig in the Digital GUI: toolbar play button or space;
the master clock U1 runs at its Frequency attribute (double-click to
edit); F6 opens a live value table; Run menu -> micro step (G) for
gate-level stepping. Program entry through the front panel:
[hardware.md](hardware.md), "Front panel".
