# Ben Eater's 8-bit computer - Digital edition

Building Ben Eater's 8-bit breadboard computer
(https://eater.net/8bit, his YouTube series) in the Digital logic
simulator (https://github.com/hneemann/Digital) first, module by module,
before reproducing it on real breadboards.

## Directory index

| directory     | contents                                                       |
|---------------|----------------------------------------------------------------|
| [digital/](digital/README.md)     | The circuits being built: one .dig file per computer module |
| [schematics/](schematics/README.md) | Ben Eater's original module schematics (PNG, from eater.net) |
| [kicad/](kicad/README.md)         | Ben Eater's KiCad project (rev B, 2018): the reference design |
| [roms/](roms/README.md)           | Archived EEPROM images (also stored inline in the .dig files) |
| [tools/](tools/README.md)         | Toolkit: netlist verification, EEPROM writer, headless simulator |

## Module status

| module             | digital/ circuit          | wired from                 | state                                        |
|--------------------|---------------------------|----------------------------|----------------------------------------------|
| Clock              | (pending)                 | schematics/clock.png       | not started in Digital                        |
| A register         | "A Register.dig"          | schematics/a-register.png  | wired, not yet verified                      |
| B register         | "B Register.dig"           | schematics/b-register.png   | wired, not yet verified                      |
| Instruction reg.   | "Instruction Register.dig"| schematics/ir.png          | wired, not yet verified                      |
| ALU                | "ALU.dig"                  | schematics/alu.png         | wired, not yet verified                      |
| RAM + MAR          | (pending)                 | schematics/ram.png, mar.png| not started in Digital                        |
| Program counter    | "Program Counter.dig"      | schematics/pc.png          | wired, not yet verified                      |
| Output register    | "Output Register.dig"      | schematics/output.png      | done: wiring verified vs KiCad, ROM programmed, simulation passing |
| Control logic      | (pending)                 | schematics/control.png     | not started (needs microcode EEPROMs)        |

## The workflow

Every module goes through the same loop (tooling in [tools/](tools/README.md)):

1. **Wire** the module in Digital from Ben's schematic (schematics/).
2. **Verify the wiring**: `tools/dignetlist.py` extracts the netlist from the
   .dig, `tools/kicadnets.py` prints the reference netlist from Ben's KiCad
   project (kicad/8bit-computer.net); compare pin by pin.
3. **Program EEPROMs** with `tools/digrom.py` (presets archived in roms/).
4. **Simulate headless** with `tools/digsim` - inputs, clocks, and rendered
   seven-segment displays, without opening the GUI.

The Output Register module was driven through all four steps: its wiring
turned out to be 100% correct and the only fault was an unprogrammed 28C16.

## Credits

All credit for the original circuit design, architecture, and schematics
belongs to Ben Eater. This repo is a personal reproduction and
re-implementation of his published work for study purposes.

- Website: <https://eater.net/>
- Schematics: <https://eater.net/8bit/schematics>
- Full video series: <https://eater.net/8bit/>
