# digital/ - the circuit

The whole computer is one Digital (https://github.com/hneemann/Digital)
circuit: Computer.dig. It was wired from Ben Eater's schematics
(../schematics/) with the KiCad project (../kicad/) as the pin-exact
reference - every module was verified pin by pin against Ben's KiCad
netlist (kicad/8bit-computer.net) with the ../tools/ extractors before the
modules were merged together (the standalone per-module .dig files are
gone; git history has them).

## What Computer.dig contains

The ten modules (clock, A/B registers, instruction register, ALU, RAM, MAR,
program counter, output register, control logic) plus a front panel:

- **LEDs**: BUS\_0..7, PC\_0..3, A\_0..7, B\_0..7, SUM\_0..7, CF, ZF,
  IR\_0..7, RAM\_DATA\_0..7, the RAM address A0..A3, the microstep
  counter T0..T4, all 16 control signals (HLT MI RI RO IO II AI AO
  EO SU BI OI CE CO J FI), CLK, and PROG (lights in program mode).
- **Switches and buttons**: RESET; STEP\_MODE + STEP\_PULSE (manual
  clocking); DEC\_HEX (display mode); and the RAM program-entry group:
  PROG\_ADDR (the RUN/PROG mode switch - despite the name it selects the
  whole program-entry path: the RAM address, data and write-enable muxes
  switch together), the PROG\_ADDR\_A0..A3 address dipswitches, the
  PROG\_DATA\_0..7 data dipswitches, and PROG\_WRITE (the write pulse).
- **Clocks**: U1 (the master clock, a realtime Digital Clock element
  standing in for Ben's 555s; the 7404/7408/7432 gating around it matches
  the KiCad nets, including HLT gating the clock off) and MUX\_CLK (the
  display multiplex clock - set its Frequency to 500+ Hz for a steady
  display).
- **ROM (EEPROM) content** lives in the .dig as a circuit-level
  `romContent` attribute: U45 (display ROM), U47/U52 (control ROMs),
  verified to match the ../tools/digrom.py presets word for word.
  Archived in ../roms/; regenerate/re-inject with ../tools/digrom.py.

Conventions:

- Chips use Digital's DIL library parts with Ben's reference designators
  (U13, U24, U37, U45, ...) so netlist comparisons against the KiCad
  reference line up one to one.
- Digital stores underscores in labels with a backslash escape
  (BUS\_1, MUX\_CLK); keep names unique (a Clock element must not share a
  label with an In, or Digital's analyze/test features break).
- Unused gate inputs get NotConnected markers so simulation starts cleanly.
- The modules were developed with In/Out test elements at their
  boundaries; in Computer.dig those elements were removed and the
  boundary wires were joined directly.

## Verification history

Every module's wiring was verified pin-exact against the KiCad reference
(the intentional deviations below aside) as a standalone circuit before
the merge. Simulation results from that era: the Output Register, Control
Logic (every instruction, including JC/JZ flag behavior and the 6-cycle
step-counter wraparound), ALU (add/sub, carry, CF/ZF flags, output enable)
and Program Counter (count/hold, output enable) passed headless simulation;
the other modules were blocked by Digital 0.31 DIL-library model bugs
(below), not wiring faults - their register cores (74173 latch/hold logic)
were verified by simulating copies with the 74245 bus transceiver removed.

The integrated Computer.dig inherits the 74245 bug: the shared bus will
not simulate reliably in Digital 0.31 until the library is fixed.

## Known Digital 0.31 simulation bugs

Found while verifying the modules; all are bugs in Digital 0.31's bundled
DIL chip library (the model), not in the circuits here - the wiring matches
the KiCad reference pin for pin:

- 74173: the model's RES input is active-HIGH (it clears while 1); the real
  74LS173's MR is active LOW. In any simulation containing these chips
  (A/B registers, instruction register, MAR, ALU flags), hold the CLR input
  at 0 and pulse it to 1 to clear - inverted from the real machine, where
  CLR idles high. Use `digsim --nets` (see ../tools/README.md) to see the
  mis-evaluation directly.
- 74245: the two direction-enable And gates use input-inversion bubbles,
  and the model drops the inversions on one of the two gates (which one
  depends on the surrounding netlist). Net effect: a "disabled" 74245
  (~OE=1) wrongly drives one direction - A/B nets cross-couple through the
  chip - and an "enabled" one can end up dead. Modules whose bus-side nets
  had no other drivers (ALU, program counter: Out elements only) still
  simulated correctly; modules with bus-side In elements (A/B registers,
  instruction register, RAM) failed to load because the wrongly-enabled
  transceiver fought the test inputs. This is the bug that makes the
  shared bus of Computer.dig unreliable in simulation - check newer
  Digital releases, or patch a local copy of
  "DIL Chips/74xx/driver/74245.dig" (replace the inverted-input Ands with
  plain Ands plus explicit Not gates).
- 74157: the MAR's load path misbehaved in the headless model (the 74173 D
  inputs ended up with a mix of bus and dipswitch values regardless of
  MI\_hat); not yet root-caused.
- Switches and dipswitches (STEP\_MODE/STEP\_PULSE, the RAM program-entry
  dipswitches) are not model inputs, so `digsim --set` cannot drive them;
  test those paths in the GUI.

## Wiring notes (vs the KiCad reference)

- Clock: Digital's Clock element (labeled U1, realtime) stands in for
  Ben's 555s (U4/U5/U6 on his board); the 7404/7408/7432 gating (HLT etc.)
  matches the KiCad nets of those chips exactly.
- A register: the AO\_hat line drives the 74245 ~OE directly (Ben inverts
  his active-high AO control line on the control card instead; the
  active-low signal names line up at the module boundary).
- B register: adds a BO\_hat line on the 74245 ~OE (pin 19) where Ben ties
  it to VCC. Deliberate extension, mirroring the A register's AO\_hat, so
  the computer can gate the B register off the bus. Idles high (1) for
  Ben-compatible behavior.
- MAR and RAM: chip-enable/output pins tie to individual Ground symbols
  where Ben's board uses one shared GND rail - electrically identical.
- ALU: which physical XOR gate inside U16/U18 drives which 74283 B input
  is permuted relative to the KiCad placement, but every bit is paired
  correctly (A bit and B bit through one gate into the matching adder
  input).
- Control logic: both ROMs' A7 pins are tied to VDD here; Ben's board
  grounds U47's A7 (the "which ROM" bit). Harmless: the ROM images are
  replicated across A7.
- Control logic: Ben's KiCad 74LS00 symbol wires gates 3/4 as inputs
  9,10->8 and 12,13->11, which does not match a real 7400 (8,9->10 and
  11,12->13). The circuit is wired functionally:
  RESET -> inverter -> ~CLR -> inverter -> CLR.

## Running in the GUI (play button)

- Start/stop: the toolbar play button (Run menu -> Run) or the space bar.
  The master clock U1 runs in real time at its Frequency attribute
  (double-click the element in edit mode to change it). STEP\_MODE +
  STEP\_PULSE give manual clocking; the HLT control line gates the clock
  off when a program halts.
- Entering a program (full procedure in
  ../docs/assembly-language.md, "Loading a program into the machine"):
  flip PROG\_ADDR to program mode (the PROG LED lights); for each listing
  row set the address on the PROG\_ADDR\_A0..A3 dipswitches and the byte
  on the PROG\_DATA\_0..7 dipswitches, then click PROG\_WRITE; flip
  PROG\_ADDR back to run mode, pulse RESET, and start the clock.
- DEC\_HEX: 1 = decimal display, 0 = hex. MUX\_CLK drives the display
  multiplexing - at 1 Hz each digit lights one per second in rotation,
  500+ Hz looks steady.
- F6 opens a live value table; the graph tool plots signals over time; F7
  runs to a Break element; Run menu -> micro step (G) for gate-level
  stepping. Headless scripted equivalent: ../tools/digsim (where the 0.31
  library bugs allow it).
