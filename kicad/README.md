# kicad/ - Ben Eater's KiCad project (the reference design)

Ben Eater's KiCad project for the 8-bit computer, rev B (July/Aug 2018).
This is the pin-exact reference: wiring in the Digital circuits is verified
against its exported netlist.

| file                          | what it is                                                         |
|-------------------------------|--------------------------------------------------------------------|
| 8bit-computer.pro             | KiCad project file (root, rev B)                                  |
| 8bit-computer.sch             | Root schematic: hierarchy of the 10 module sheets below            |
| clock.sch                     | Clock module sheet                                                 |
| a-register.sch                | A register sheet                                                   |
| b-register.sch                | B register sheet                                                   |
| inst-register.sch             | Instruction register sheet                                         |
| alu.sch                       | ALU sheet                                                          |
| ram.sch                       | RAM module sheet                                                   |
| mar.sch                       | Memory address register sheet                                      |
| program-counter.sch           | Program counter sheet                                              |
| output.sch                    | Output register sheet (display + mux counter + mode switch)        |
| control.sch                   | Control logic sheet (instruction decoder, microcode EEPROMs)       |
| 8bit-computer.net             | Exported netlist of the whole board - the reference used by kicadnets.py in this directory |
| 8bit-computer.kicad_pcb       | The full PCB layout of the computer                                |
| 8bit-computer-cache.lib       | Cached schematic symbols for the sheets above                      |
| 8bit-computer.xml             | XML netlist export (intermediate for BOM tooling)                  |
| 8bit-computer.csv             | Bill of materials (~275 lines)                                     |
| fp-lib-table                  | Footprint library table (points at 8bit-custom-footprints.pretty)  |
| sym-lib-table                 | Symbol library table (sym-lib-table.bak is its backup)             |
| 8bit-custom-footprints.pretty/| Custom footprints, see its README                                  |

Chip pin maps (74LS273, 28C16, 74LS76, 74LS139, 74LS08) for reading the
netlist are in the header comment of kicadnets.py; the netlist of a
module is printed with e.g. (from the repo root):

    kicad/kicadnets.py --net kicad/8bit-computer.net --refs U44,U45,U46
