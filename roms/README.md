# ROM images

EEPROM contents used by the Digital (and eventually breadboard) build.
digital/Computer.dig also carries these inline (circuit attribute
`romContent`, chip Labels U45/U47/U52 - re-verified word for word after the
modules were merged into that one circuit), so this directory is the
browsable archive / source of truth.

| file                       | chip (in Computer.dig) | preset            |
|----------------------------|------------------------|-------------------|
| output-display.hex         | U45                    | output-display    |
| output-display-intel.hex   | U45                    | output-display    |
| control-rom1.hex           | U47                    | control-rom1      |
| control-rom1-intel.hex     | U47                    | control-rom1      |
| control-rom2.hex           | U52                    | control-rom2      |
| control-rom2-intel.hex     | U52                    | control-rom2      |

- `*.hex` are Logisim format ("v2.0 raw" + hex words), loadable by
  Digital's ROM editor; `-intel` variants are Intel HEX for EEPROM burners.
- Regenerate after editing a preset in tools/digrom.py:
  `tools/digrom.py export --preset output-display --out roms/output-display.hex`
- Re-inject into the circuit:
  `tools/digrom.py write --dig digital/Computer.dig --label U45 --preset output-display`
  (or `--hexfile roms/output-display.hex --size 2048`)

## output-display (U45 28C16 in Computer.dig, 2 KiB)

Address = A10*1024 + A9*512 + A8*256 + value. A8/A9 are the 7476 mux-counter
bits that also drive the 74139 select lines, so ROM page p lights the digit
whose cathode ~1Yp pulls low: page 0 = ones (rightmost display), 1 = tens,
2 = hundreds, 3 = thousands (blank for 8-bit values). A10 = mode switch:
1 -> decimal, 0 -> hex, leading zeros blanked in both modes.

Segment encoding (ROM bit -> segment): 6=a 5=b 4=c 3=d 2=e 1=f 0=g 7=dp.

## control-rom1 / control-rom2 (U47/U52 28C16 in Computer.dig, 2 KiB each)

The 16-bit control word of Ben's design, split across the two ROMs:

    U47: bit 7=HLT 6=MI 5=RI 4=RO 3=IO 2=II 1=AI 0=AO
    U52: bit 7=EO 6=SU 5=BI 4=OI 3=CE 2=CO 1=J  0=FI

Address (both ROMs): step counter (74161 Q0-Q2) -> A0-A2, opcode (IR4-IR7)
-> A3-A6, CF -> A8, ZF -> A9. A10 is grounded; A7 is the "which ROM" bit on
Ben's board (U47 A7=GND, U52 A7=VCC), so both images are replicated across
A7 and A10 and are correct regardless of how A7 is wired (the Digital build
ties both A7 pins to VDD).

Instruction set (opcode = instruction's high nibble) and microcode - all
instructions share the fetch T0: MI|CO, T1: RO|II|CE, and take 6 cycles (the
74138 T5 line asynchronously resets the step counter):

    0 NOP    1 LDA: T2 MI|IO, T3 RO|AI
    2 ADD: T2 MI|IO, T3 RO|BI, T4 EO|AI|FI
    3 SUB: T2 MI|IO, T3 RO|BI, T4 EO|AI|SU|FI
    4 STA: T2 MI|IO, T3 AO|RI      5 LDI: T2 IO|AI
    6 JMP: T2 IO|J     7 JC: T2 IO|J if CF     8 JZ: T2 IO|J if ZF
    9-D undefined (fetch only)
    E OUT: T2 AO|OI     F HLT: T2 HLT

The rom1 image matches the 8bitsim reference (ngdrascal/8bitsim,
memory-images/MicroInstructions.hex) instruction by instruction in its used
address half.
