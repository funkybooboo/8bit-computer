# digital/ - the Digital build

The whole computer as one Digital circuit: Computer.dig - all ten
modules plus the front panel, with the EEPROM contents stored in the
circuit file itself.

- What the parts are and how they make a computer:
  [../docs/architecture.md](../docs/architecture.md)
- Every part and every wire: [../docs/hardware.md](../docs/hardware.md)
- The EEPROM images and how to change them:
  [../roms/README.md](../roms/README.md), [../docs/tools.md](../docs/tools.md)
- Headless simulation: `digsim` (drives Digital's own model, see its
  `--help`); netlist cross-checks: `netlist.py`.
- GUI with the Driver high-Z fix: `gui` - builds a patched Digital.jar
  on demand and launches it (why: [../docs/tools.md](../docs/tools.md),
  "Digital 0.31 notes"). Use the same jar headless with
  `DIGITAL_JAR=~/.cache/digital-patched/Digital.jar digsim ...`.
