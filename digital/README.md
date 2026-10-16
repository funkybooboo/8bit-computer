# digital/ - the circuits

One Digital (https://github.com/hneemann/Digital) circuit per module of the
computer, wired from Ben Eater's schematics (../schematics/) with the KiCad
project (../kicad/) as the pin-exact reference.

| file                         | module            | reference schematic | KiCad sheet      |
|------------------------------|-------------------|---------------------|------------------|
| A Register.dig               | A register        | a-register.png      | a-register.sch   |
| B Register.dig               | B register        | b-register.png      | b-register.sch   |
| Instruction Register.dig     | Instruction reg.  | ir.png              | inst-register.sch|
| ALU.dig                      | ALU               | alu.png             | alu.sch         |
| Program Counter.dig          | Program counter   | pc.png              | program-counter.sch |
| Output Register.dig          | Output register   | output.png          | output.sch      |

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

Status: only "Output Register.dig" has been through the full
verify/program/simulate workflow (see the root README). The others are wired
but not yet verified or complete; run ../tools/dignetlist.py and compare
against ../tools/kicadnets.py output before debugging their behavior.

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
