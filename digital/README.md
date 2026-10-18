# digital/ - the circuits

One Digital (https://github.com/hneemann/Digital) circuit per module of the
computer, wired from Ben Eater's schematics (../schematics/) with the KiCad
project (../kicad/) as the pin-exact reference.

| file                         | module            | reference schematic | KiCad sheet      |
|------------------------------|-------------------|---------------------|------------------|
| Clock.dig                    | Clock             | clock.png           | clock.sch        |
| A Register.dig               | A register        | a-register.png      | a-register.sch   |
| B Register.dig               | B register        | b-register.png      | b-register.sch   |
| Instruction Register.dig     | Instruction reg.  | ir.png              | inst-register.sch|
| Arithmetic Logic Unit.dig    | ALU + flags       | alu.png             | alu.sch          |
| Program Counter.dig          | Program counter   | pc.png              | program-counter.sch |
| Memory Address Register.dig  | MAR               | mar.png             | mar.sch          |
| Random Access Memory.dig     | RAM               | ram.png             | ram.sch          |
| Output Register.dig          | Output register   | output.png          | output.sch       |
| Control Logic.dig            | Control logic     | control.png         | control.sch      |
| Computer.dig                 | whole computer    | (all of the above)  | (in progress)    |

Conventions:

- Inputs are In test elements labeled BUS\_0..BUS\_7 plus the module's control
  lines (e.g. OI, CLK, CLR\_hat). Digital stores underscores in labels with a
  backslash escape; keep names unique (a Clock element must not share a label
  with an In, or Digital's analyze/test features break).
- Chips use Digital's DIL library parts with Ben's reference designators
  (U37, U38, U44, U45, ...) so netlist comparisons against the KiCad
  reference line up one to one.
- Unused gate inputs get NotConnected markers so simulation starts cleanly.
- ROM (EEPROM) content lives inside the .dig as a circuit-level `romContent`
  attribute and is archived in ../roms/ - regenerate/re-inject with
  ../tools/digrom.py.

Status: every component circuit has been through steps 1-2 of the root
README's workflow - netlists verified pin by pin against the KiCad reference
(the intentional deviations above aside). "Output Register.dig" and
"Control Logic.dig" are fully done through the program/simulate steps.
"Arithmetic Logic Unit.dig" and "Program Counter.dig" are
simulation-verified headless (ADD/SUB/carry/CF-ZF flags/output enable;
count/hold/output enable). The remaining modules (A/B registers,
instruction register, MAR, RAM, Clock) currently cannot be simulated
headless because of Digital 0.31 DIL-library model bugs - see below. Their
register cores (74173 latch/hold logic) were verified by simulating copies
with the 74245 bus transceiver removed. "Computer.dig" is in progress.

## Known Digital 0.31 simulation bugs

Found while verifying these modules; all are bugs in Digital 0.31's bundled
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
  have no other drivers (ALU, program counter: Out elements only) still
  simulate correctly; modules with bus-side In elements (A/B registers,
  instruction register, RAM) fail to load because the wrongly-enabled
  transceiver fights the test inputs. This also means the shared bus of
  Computer.dig will not simulate reliably in Digital 0.31 until the library
  is fixed - check newer Digital releases, or patch a local copy of
  "DIL Chips/74xx/driver/74245.dig" (replace the inverted-input Ands with
  plain Ands plus explicit Not gates).
- 74157: the MAR's load path misbehaves in the headless model (the 74173 D
  inputs end up with a mix of bus and dipswitch values regardless of
  MI\_hat); not yet root-caused.
- Switches and dipswitches (Clock's STEP_MODE/STEP_PULSE, MAR/RAM program
  dipswitches) are not model inputs, so `digsim --set` cannot drive them;
  test those paths in the GUI.

Module wiring notes (vs the KiCad reference):

- Clock: Digital's Clock element (labeled U1, realtime) stands in for Ben's
  555s (U4/U5/U6); the 7404/7408/7432 gating (HLT etc.) matches the KiCad
  nets of those chips exactly.
- A register: the AO\_hat In drives the 74245 ~OE directly (Ben inverts his
  active-high AO control line on the control card instead; the active-low
  signal names line up at the module boundary).
- B register: adds a BO\_hat In on the 74245 ~OE (pin 19) where Ben ties it
  to VCC. Deliberate extension, mirroring the A register's AO\_hat, so the
  full computer can gate the B register off the bus. Keep it high (1) for
  Ben-compatible behavior.
- MAR and RAM: chip-enable/output pins tie to individual Ground symbols
  where Ben's board uses one shared GND rail - electrically identical.
- ALU: which physical XOR gate inside U16/U18 drives which 74283 B input is
  permuted relative to the KiCad placement, but every bit is paired correctly
  (A bit and B bit through one gate into the matching adder input).

Control logic notes (vs the KiCad reference):

- Both ROMs' A7 pins are tied to VDD here; Ben's board grounds U47's A7 (the
  "which ROM" bit). Harmless: the ROM images are replicated across A7.
- Ben's KiCad 74LS00 symbol wires gates 3/4 as inputs 9,10->8 and 12,13->11,
  which does not match a real 7400 (8,9->10 and 11,12->13). The circuit is
  wired functionally: RESET -> inverter -> ~CLR -> inverter -> CLR.

## Running in the GUI (play button)

- Start/stop: the toolbar play button (Run menu -> Run) or the space bar.
- While running, click a 1-bit In element to toggle it (all BUS bits, OI,
  CLK, CLR\_hat, SW\_7). Clicking the MUX\_CLK Clock element toggles it manually.
- Real-time clocks run by themselves once started: MUX\_CLK has
  runRealTime set, at its Frequency attribute (default 1 Hz). Set Frequency
  to 500+ Hz (double-click the element in edit mode) for a smooth
  multiplexed display; at 1 Hz the digits light one per second in rotation.
- Output Register cheat sheet: BUS\_0..7 = value bits (bit i = 2^i), OI = 1
  to let the latch capture the bus, then click CLK once (rising edge latches;
  click again to return low). SW\_7: 1 = decimal, 0 = hex. CLR\_hat: keep 1,
  pulse 0 to zero the latch.
- F6 opens a live value table; the graph tool plots signals over time; F7
  runs to a Break element; Run menu -> micro step (G) for gate-level
  stepping. Headless scripted equivalents: ../tools/digsim.
