# tools/ - the toolchain

Verify wiring, program EEPROMs, assemble programs, run them - all from
this directory. Full usage and workflow: [../docs/tools.md](../docs/tools.md).

| file          | what it is                                                        |
|---------------|-------------------------------------------------------------------|
| machine.py    | The machine in code: opcodes, microcode DSL, ROM contents, image formats (machine-level) |
| asm.py        | Assembler / disassembler (machine-level; see ../docs/assembly-language.md) |
| sim.py        | Cycle-accurate simulator: runs the real microcode (machine-level; see ../docs/programs.md) |
| digrom.py     | ROM data in .dig circuits - the Digital bridge (see ../docs/tools.md) |
| dignetlist.py | Netlist extraction from a .dig (Digital-specific; see ../docs/hardware.md) |
| kicadnets.py  | Reference netlist from Ben's KiCad project (build-target neutral) |
| DigSim.java + digsim | Headless Digital simulator (Digital-specific)            |

Machine-level tools work from any clone, no Digital needed; the
Digital-specific ones bridge to the Digital build. Details:
[../docs/tools.md](../docs/tools.md).
