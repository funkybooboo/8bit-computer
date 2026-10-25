# Ben Eater's 8-bit computer - one machine, several builds

An 8-bit breadboard computer - [Ben Eater's](https://eater.net/8bit)
design, with a few additions of its own - defined once and built several
ways: the wiring verified pin-exact in [Digital](digital/), playable in
a browser in [web/](web/), Ben's KiCad project as the reference in
[kicad/](kicad/), and one day, real breadboards. Every build runs the
same control-ROM images from [roms/](roms/README.md) (generated from one
place, [tools/genroms.py](tools/genroms.py)) and the same program
gallery from [programs/](programs/README.md), and each program's
expected output is frozen so every build can be checked against the same
answers.

## Run a program in 30 seconds

    python3 web/build.py      # build the program images the app serves
    python3 -m http.server    # from this directory

then open <http://localhost:8000/web/>, pick "powers", and hit run:
1, 2, 4, ..., 128, halting on the wrap. No hardware needed; everything
works from this repo as cloned.

## What is where

| directory | contents |
|-----------|----------|
| [docs/](docs/README.md) | The real documentation - one document per domain |
| [roms/](roms/README.md) | The machine's ROM images: what every build runs |
| [programs/](programs/README.md) | The program gallery (.asm sources) |
| [tools/](tools/README.md) | The assembler + the ROM generator (genroms.py) |
| [digital/](digital/README.md) | The Digital build + its tools |
| [web/](web/README.md) | The browser build + its build and test scripts |
| [kicad/](kicad/README.md) | Ben's KiCad project - the reference build |
| [crumb/](crumb/README.md) | The Crumb build (empty for now) |
| [schematics/](schematics/README.md) | Ben's original module schematics |

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
| [docs/additions.md](docs/additions.md) | Additions to Ben Eater's computer: made and possible |
| [docs/getting-to-c.md](docs/getting-to-c.md) | The staged path to running C |
| [docs/getting-to-os.md](docs/getting-to-os.md) | The staged path to running an OS |

## Credits

The computer itself - circuit design, architecture, schematics - is
Ben Eater's published work; this repo is a personal reproduction of it
for study. All credit for the machine belongs to him.
