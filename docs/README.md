# docs/ - written documentation

The reference documentation for the machine as built in
[../digital/Computer.dig](../digital/Computer.dig).

| file                  | contents                                                       |
|-----------------------|----------------------------------------------------------------|
| instruction-set.md    | The machine model and every opcode, with semantics and idioms |
| microcode.md          | The 16 control signals, the two control ROMs, fetch + per-instruction microsteps |
| assembly-language.md  | The assembly language and its assembler (`tools/asm.py`)      |

The source of truth for the microcode itself is the
`control-rom1`/`control-rom2` presets in [../tools/digrom.py](../tools/digrom.py);
the ROM images are archived in [../roms/](../roms/README.md). Assembly
programs live in [../programs/](../programs/README.md).
