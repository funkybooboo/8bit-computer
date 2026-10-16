# ROM images

EEPROM contents used by the Digital (and eventually breadboard) build.
The .dig circuits also carry these inline (circuit attribute `romContent`),
so this directory is the browsable archive / source of truth.

| file                       | module          | chip | preset            |
|----------------------------|-----------------|------|-------------------|
| output-display.hex         | Output Register | U45  | output-display    |
| output-display-intel.hex   | Output Register | U45  | output-display    |

- `output-display.hex` is Logisim format ("v2.0 raw" + hex words), loadable by
  Digital's ROM editor; `-intel` variants are Intel HEX for EEPROM burners.
- Regenerate after editing a preset in tools/digrom.py:
  `tools/digrom.py export --preset output-display --out roms/output-display.hex`
- Re-inject into a .dig:
  `tools/digrom.py write --dig "digital/Output Register.dig" --label U45 --preset output-display`
  (or `--hexfile roms/output-display.hex --size 2048`)

## output-display (Output Register, U45 28C16, 2 KiB)

Address = A10*1024 + A9*512 + A8*256 + value. A8/A9 are the 7476 mux-counter
bits that also drive the 74139 select lines, so ROM page p lights the digit
whose cathode ~1Yp pulls low: page 0 = ones (rightmost display), 1 = tens,
2 = hundreds, 3 = thousands (blank for 8-bit values). A10 = mode switch:
1 -> decimal, 0 -> hex, leading zeros blanked in both modes.

Segment encoding (ROM bit -> segment): 6=a 5=b 4=c 3=d 2=e 1=f 0=g 7=dp.
