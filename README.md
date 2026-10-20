# Ben Eater's 8-bit computer - Digital edition

Building Ben Eater's 8-bit breadboard computer
(https://eater.net/8bit, his YouTube series) in the Digital logic
simulator (https://github.com/hneemann/Digital) first, module by module,
before reproducing it on real breadboards.

## Directory index

| directory     | contents                                                       |
|---------------|----------------------------------------------------------------|
| [digital/](digital/README.md)     | The whole computer in one Digital circuit: Computer.dig |
| [schematics/](schematics/README.md) | Ben Eater's original module schematics (PNG, from eater.net) |
| [kicad/](kicad/README.md)         | Ben Eater's KiCad project (rev B, 2018): the reference design |
| [roms/](roms/README.md)           | Archived EEPROM images (also stored inline in the .dig files) |
| [tools/](tools/README.md)         | Toolkit: netlist verification, EEPROM writer, headless simulator, assembler |
| [docs/](docs/README.md)           | Written documentation: instruction set, microcode, assembly language |
| [programs/](programs/README.md)   | Assembly programs (sources; assembled images/listings are gitignored build artifacts) |

Software index: the machine's instruction set and microcode are documented
in [docs/](docs/), and assembly programs for it live in
[programs/](programs/) (assembled with [tools/asm.py](tools/README.md)).

## Build status

All ten component circuits were wired and their wiring verified
pin by pin against Ben's KiCad netlist (kicad/8bit-computer.net) with the
tools/ netlist extractor, as standalone circuits first - and then merged
into a single circuit, digital/Computer.dig (the per-module .dig files are
gone; git history has them). The headless simulator cannot exercise the
full machine because of bugs in Digital 0.31's DIL chip library (details
and workarounds in digital/README.md, "Known Digital 0.31 simulation
bugs").

| module             | wired from                 | state (verified before the merge)                |
|--------------------|----------------------------|--------------------------------------------------|
| Clock              | schematics/clock.png       | wiring verified vs KiCad; realtime clock element verified; gated CLK output depends on the STEP_MODE switch (GUI test) |
| A register          | schematics/a-register.png  | wiring verified vs KiCad; load/hold verified (register core); full-module sim blocked by the 74245 library bug |
| B register          | schematics/b-register.png  | wiring verified vs KiCad (adds BO\_hat output-enable line); sim blocked by the 74245 library bug |
| Instruction reg.   | schematics/ir.png          | wiring verified vs KiCad; sim blocked by the 74245 library bug |
| ALU                | schematics/alu.png         | done: wiring verified vs KiCad; simulation verified (ADD/SUB, carry, CF/ZF flags, output enable) |
| RAM                | schematics/ram.png         | wiring verified vs KiCad; sim blocked by 74245/74157 library bugs |
| MAR                | schematics/mar.png         | wiring verified vs KiCad; sim blocked by a 74157 library bug |
| Program counter    | schematics/pc.png          | done: wiring verified vs KiCad; simulation verified (count/hold, output enable) |
| Output register    | schematics/output.png      | done: wiring verified vs KiCad, ROM programmed, simulation passing |
| Control logic      | schematics/control.png     | done: wiring verified vs KiCad, both ROMs programmed, simulation passing |
| Computer           | all of the above           | digital/Computer.dig: the integrated machine (all modules, front panel, program-entry dipswitches; ROMs re-verified in the merged circuit); shared-bus simulation blocked by the Digital 0.31 74245 library bug |

Wiring verification is pin-exact; the only intentional deviations from
Ben's board are listed in digital/README.md (BO\_hat on the B register,
separate Ground symbols on chip enables, equivalent XOR gate pairing in the
ALU, and the Clock element standing in for the 555s). The current activity
is step 5 of the workflow below: writing software for the integrated
machine ([docs/](docs/), [programs/](programs/)).

## The workflow

Every module goes through the same loop (tooling in [tools/](tools/README.md)):

1. **Wire** the module in Digital from Ben's schematic (schematics/).
2. **Verify the wiring**: `tools/dignetlist.py` extracts the netlist from the
   .dig, `tools/kicadnets.py` prints the reference netlist from Ben's KiCad
   project (kicad/8bit-computer.net); compare pin by pin.
3. **Program EEPROMs** with `tools/digrom.py` (presets archived in roms/).
4. **Simulate headless** with `tools/digsim` - inputs, clocks, and rendered
   seven-segment displays, without opening the GUI.
5. **Write software** in the assembly language (`tools/asm.py`, see
   [docs/](docs/)) and run it - see [programs/](programs/).

The Output Register module was driven through all four steps: its wiring
turned out to be 100% correct and the only fault was an unprogrammed 28C16.
The Control Logic module followed: wiring again correct (two benign A7/7400
symbol notes in digital/README.md), both microcode ROMs programmed, and all
instructions (incl. JC/JZ flag behavior and the 6-cycle step-counter
wraparound) verified by headless simulation. After that, the remaining eight
modules (Clock, A/B registers, instruction register, ALU, program counter,
MAR, RAM) were wired and their netlists verified the same way - all pin-
exact - and the ALU and program counter were simulation-verified end to end.
The other register/RAM modules are blocked in headless simulation by Digital
0.31 DIL-library model bugs (see digital/README.md), not by wiring faults:
their register cores were verified by simulating the latch logic with the
bus transceiver removed.

## Credits

All credit for the original circuit design, architecture, and schematics
belongs to Ben Eater. This repo is a personal reproduction and
re-implementation of his published work for study purposes.

- Website: <https://eater.net/>
- Schematics: <https://eater.net/8bit/schematics>
- Full video series: <https://eater.net/8bit/>
