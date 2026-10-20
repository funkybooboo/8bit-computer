# schematics/ - Ben Eater's original module schematics

PNG schematics downloaded from https://eater.net/8bit - one per module page.
These are the human-readable wiring reference for the Digital build
(../digital/Computer.dig - all ten modules are built and integrated there;
the standalone per-module .dig files are gone, git history has them) and
correspond sheet-for-sheet to the KiCad project (../kicad/).

| file            | module                     | KiCad sheet             |
|-----------------|----------------------------|-------------------------|
| clock.png       | Clock module               | clock.sch               |
| a-register.png  | A register                 | a-register.sch          |
| b-register.png  | B register                 | b-register.sch          |
| ir.png          | Instruction reg.           | inst-register.sch       |
| alu.png         | ALU                        | alu.sch                 |
| ram.png         | RAM module                 | ram.sch                 |
| mar.png         | Memory address reg.        | mar.sch                 |
| pc.png          | Program counter            | program-counter.sch     |
| output.png      | Output register            | output.sch              |
| control.png     | Control logic              | control.sch             |
| high-level.png  | Whole-computer block diagram | -                    |
