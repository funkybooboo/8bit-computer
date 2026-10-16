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
