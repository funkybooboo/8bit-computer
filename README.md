# Ben Eater's 8-bit computer - one machine, several builds

An 8-bit breadboard computer - [Ben Eater's](https://eater.net/8bit)
design, with a few additions of its own - defined once and built several
ways: the wiring verified pin-exact in [Digital](digital/), emulated in
a browser in [web/](web/) (the repo's emulator), Ben's KiCad project as
the reference in [kicad/](kicad/), and one day, real breadboards. Every
build runs the
same control-ROM images from [roms/](roms/README.md) (generated from one
place, [tools/genroms.py](tools/genroms.py)) and the same program
gallery from [programs/](programs/README.md), and each program's
expected output is frozen so every build can be checked against the same
answers.

## Run the machine in 30 seconds

    python3 -m http.server    # from this directory

then open <http://localhost:8000/web/>: the machine powers on with
empty RAM and the clock ticking. Build a listing to enter -
`python3 web/build.py` writes the .lst dipswitch tables for the whole
gallery, or `python3 tools/compile.py programs/count.hl` for one -
then enter it with the switches (the app's footer walks the
procedure) and press RESET. Or write your own program
([docs/language.md](docs/language.md)) and enter that.

## What is where

| directory | contents |
|-----------|----------|
| [docs/](docs/README.md) | The real documentation - one document per domain |
| [roms/](roms/README.md) | The machine's ROM images: what every build runs |
| [programs/](programs/README.md) | The program gallery (.hl sources, compiled by tools/compile.py) |
| [tools/](tools/README.md) | The .hl compiler, the assembler and the ROM generator |
| [digital/](digital/README.md) | The Digital build + its tools |
| [web/](web/README.md) | The web build + its build and test scripts |
| [kicad/](kicad/README.md) | Ben's KiCad project - the reference build |
| [crumb/](crumb/README.md) | The Crumb build (clock module in progress) |
| [schematics/](schematics/README.md) | Ben's original module schematics |

## The documentation

| document | domain |
|----------|--------|
| [docs/architecture.md](docs/architecture.md) | How the parts make a computer - the theory |
| [docs/hardware.md](docs/hardware.md) | Every part and every wire |
| [instruction-set.md](docs/instruction-set.md) | The machine language |
| [docs/language.md](docs/language.md) | The .hl high-level language |
| [docs/microcode.md](docs/microcode.md) | The control signals and ROMs |
| [docs/assembly-language.md](docs/assembly-language.md) | The assembly language and assembler |
| [docs/programs.md](docs/programs.md) | The program gallery and the machine's limits |
| [docs/tools.md](docs/tools.md) | The toolchain |
| [docs/additions.md](docs/additions.md) | Additions to Ben Eater's computer: made and possible |
| [docs/getting-to-c.md](docs/getting-to-c.md) | The staged path to running C |
| [docs/getting-to-os.md](docs/getting-to-os.md) | The staged path to running an OS |

## Credits

The computer itself - circuit design, architecture, schematics - is
Ben Eater's published work; this repo is a personal reproduction of it
for study. All credit for the machine belongs to him.

Other projects this one stands on or learned from, with credit due:

- [hneemann/Digital](https://github.com/hneemann/Digital) - the logic
  simulator the [digital/](digital/) build is wired and verified in.
- [ngdrascal/8bitsim](https://github.com/ngdrascal/8bitsim) - a Digital
  build of Ben's computer, a helpful reference while wiring this one;
  its microcode image was used to cross-check the control ROMs
  (docs/microcode.md).
- [kapilpokhrel/eater-8bitemu](https://github.com/kapilpokhrel/eater-8bitemu) -
  a terminal emulator of the stock machine with its own assembler - the
  proof that an emulator with a real front panel is worth building.
  Nothing in this repo is derived from its code.
