# tools/ - the toolchain

Verify wiring, program EEPROMs, assemble programs, run them - all from
this directory. Full usage and workflow: [../docs/tools.md](../docs/tools.md).

| file          | what it is                                                        |
|---------------|-------------------------------------------------------------------|
| asm.py        | Assembler / disassembler (see ../docs/assembly-language.md)       |
| sim.py        | Cycle-accurate simulator: runs the real microcode (see ../docs/programs.md) |
| digrom.py     | EEPROM writer/reader/exporter for .dig circuits                   |
| dignetlist.py | Netlist extraction from a .dig (see ../docs/hardware.md)          |
| kicadnets.py  | Reference netlist from Ben's KiCad project                        |
| DigSim.java + digsim | Headless Digital simulator wrapper                       |
