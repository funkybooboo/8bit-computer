# tools/ - the machine-level tools

Three scripts, all runnable, all useful to every build of the machine.
Tools that serve only one build live beside it: ../digital/ has the
Digital tools, ../kicad/ has the netlist extractor, ../web/ has the
browser build's scripts. Full usage and workflow:
[../docs/tools.md](../docs/tools.md).

| file         | what it is                                                       |
|--------------|------------------------------------------------------------------|
| compile.py   | The .hl compiler ([language.md](../docs/language.md))           |
| asm.py       | Assembler / disassembler ([assembly-language.md](../docs/assembly-language.md)) |
| genroms.py   | The instruction set and microcode in code; generates and checks the ROM images every build runs ([microcode.md](../docs/microcode.md)) |
