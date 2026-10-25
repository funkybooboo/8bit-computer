# tools/ - the machine-level tools

Two scripts, both runnable, both useful to every build of the machine.
Tools that serve only one build live beside it: ../digital/ has the
Digital tools, ../kicad/ has the netlist extractor, ../web/ has the
browser build's scripts. Full usage and workflow:
[../docs/tools.md](../docs/tools.md).

| file         | what it is                                                       |
|--------------|------------------------------------------------------------------|
| asm.py       | Assembler / disassembler ([assembly-language.md](../docs/assembly-language.md)) |
| microcode.py | The instruction set and microcode in code; generates and checks the ROM images every build runs ([microcode.md](../docs/microcode.md)) |
