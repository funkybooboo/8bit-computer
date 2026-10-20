# Ben Eater's 8-bit computer - Digital edition

An 8-bit breadboard computer, built and verified in the
[Digital](https://github.com/hneemann/Digital) logic simulator before the
breadboards: [digital/Computer.dig](digital/Computer.dig) is the whole
machine - clock, registers, ALU, RAM, microcode control unit, front panel -
wired pin-exact against Ben Eater's [KiCad reference](kicad/), with its
own instruction set, assembler, and a cycle-accurate simulator, plus 21
example programs.

## Run a program in 30 seconds

    tools/asm.py programs/powers.asm --out /tmp/p.hex
    tools/sim.py programs/powers.asm

That assembles and runs "powers of two" on the same control-ROM images
the hardware burns - 1, 2, 4, ..., 128, halting on the wrap. No hardware
needed; everything works from this repo as cloned.

## What is where

| directory | contents |
|-----------|----------|
| [docs/](docs/README.md) | The real documentation - one document per domain |
| [digital/](digital/README.md) | The machine: Computer.dig |
| [programs/](programs/README.md) | Assembly programs (sources) |
| [tools/](tools/README.md) | Assembler, simulator, EEPROM writer, netlist verifiers |
| [roms/](roms/README.md) | Archived EEPROM images |
| [schematics/](schematics/README.md) | Ben Eater's original module schematics |
| [kicad/](kicad/README.md) | Ben Eater's KiCad project - the reference design |

## The documentation

| document | domain |
|----------|--------|
| [docs/architecture.md](docs/architecture.md) | How the parts make a computer - the theory |
| [docs/hardware.md](docs/hardware.md) | Every part and every wire |
| [docs/instruction-set.md](docs/instruction-set.md) | The machine language |
| [docs/microcode.md](docs/microcode.md) | The control signals and ROMs |
| [docs/assembly-language.md](docs/assembly-language.md) | The assembly language and assembler |
| [docs/programs.md](docs/programs.md) | The program gallery and the machine's limits |
| [docs/tools.md](docs/tools.md) | The toolchain |
| [docs/modifications.md](docs/modifications.md) | What can be changed, at what cost |
| [docs/getting-to-c.md](docs/getting-to-c.md) | The staged path to running C |

## Credits

The computer itself - circuit design, architecture, schematics - is
[Ben Eater's](https://eater.net/8bit) published work; this repo is a
personal reproduction of it for study. All credit for the machine
belongs to him.
