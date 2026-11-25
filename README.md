# Ben Eater's 8-bit computer

One machine, built several ways. This is Ben Eater's 8-bit breadboard
computer ([eater.net/8bit](https://eater.net/8bit)) - his circuit
design, plus a few additions ([docs/additions.md](docs/additions.md)) - wired and verified in a
logic simulator, emulated in a browser, checked against the original
schematics, and one day built for real:

- **[digital/](digital/)** - the wiring, drawn and verified pin-exact
  in the [Digital](https://github.com/hneemann/Digital) logic
  simulator
- **[web/](web/)** - the machine in a browser: every module, lamp and
  switch, laid out like the Digital build
- **[kicad/](kicad/)** - Ben's KiCad project, the pin-exact reference
  the wiring is checked against
- **[crumb/](crumb/)** - the same machine in
  [Crumb](https://crumb.breadboard.cc/), the breadboard simulator
  (clock module so far)
- real breadboards, one day

Every build runs the same control-ROM images ([roms/](roms/README.md),
generated from one place: [tools/genroms.py](tools/genroms.py)) and
the same program gallery ([programs/](programs/README.md)). Each
program's expected output is frozen in
[programs/verify.py](programs/verify.py) - the contract every build
is checked against ([docs/tools.md](docs/tools.md), "Running
programs").

## Quick start

The web build runs the machine in a browser - pure HTML, CSS and
JavaScript, no build step, no backend. From the repo root:

```bash
python3 -m http.server
```

Open <http://localhost:8000/web/>. It powers on like the real machine:
empty RAM (16 NOPs), clock ticking.

There is exactly one way to load a program, the same way the
hardware does it: the dipswitches. First build the program's entry
listing:

```bash
python3 tools/compile.py programs/count_up.hl   # writes programs/count_up.lst
python3 programs/build.py                   # ...or the whole gallery
```

Enter it on the panel (the procedure: [docs/hardware.md](docs/hardware.md),
"Front panel"; the app's footer has the same steps), press RESET, and
watch the display count. Pick any program from the
[gallery](programs/README.md), or write your own in the repo's small
language, [.hl](docs/language.md).

(Append `?smoke=1` to the URL to run the app's built-in self-check.)

## What's in the repo

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

## Documentation

[docs/](docs/README.md) - one document per domain: the architecture,
the hardware, the instruction set, both languages, the microcode, the
program gallery, the tools, the additions, and the staged paths to C
and an OS.

## Credits

The computer itself - the circuit design, the architecture, the
schematics - is Ben Eater's published work. This repo is a personal
reproduction of it for study; the credit for the machine is his.

Other projects this one stands on or learned from:

- [hneemann/Digital](https://github.com/hneemann/Digital) - the logic
  simulator the [digital/](digital/) build is wired and verified in.
- [ngdrascal/8bitsim](https://github.com/ngdrascal/8bitsim) - a
  Digital build of Ben's computer, a helpful reference while wiring
  this one; its microcode image was used to cross-check the control
  ROMs ([docs/microcode.md](docs/microcode.md)).
- [kapilpokhrel/eater-8bitemu](https://github.com/kapilpokhrel/eater-8bitemu) -
  a terminal emulator of the stock machine, proof that an emulator
  with a real front panel is worth building. Nothing in this repo is
  derived from its code.
- [Mike Bushell](https://www.youtube.com/watch?v=KYTkgplXpXE) - the
  creator of CRUMB. His complete build of Ben's computer in CRUMB
  ("Building Ben Eater's 8-bit computer... in a breadboard simulator";
  the .cru save is linked in the video's description) is committed at
  [crumb/Computer-Mike-Bushell.cru](crumb/Computer-Mike-Bushell.cru)
  and used as the authoritative in-game reference for the
  [crumb/](crumb/) build, including his verified 555 timing values.