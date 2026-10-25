# Hardware

The machine as built in [../digital/Computer.dig](../digital/Computer.dig):
every part, every wire, what each does. The theory and how the parts work
together: [architecture.md](architecture.md). The control signals and
microcode: [microcode.md](microcode.md).

The authoritative sources are the circuit itself and Ben Eater's KiCad
netlist ([../kicad/8bit-computer.net](../kicad/8bit-computer.net)); this
document describes the machine as it stands. Re-derive the raw netlist any
time with `tools/dignetlist.py --dig digital/Computer.dig` (prints every
pin and the members of its net; also warns about T-junctions, which are
not connections in Digital) or compare against the KiCad reference with
`kicad/kicadnets.py` (see [tools.md](tools.md)).

Conventions: chips keep Ben's reference designators (U1..U53) so the two
netlists line up one to one. "X <- Y" means X latches Y on the clock edge
while X's enable is active.

## The parts

| module | chip | part | role |
|--------|------|------|------|
| clock | U1 | (Clock element) | clock source, standing in for Ben's 555s |
| clock | U4 | 7404 | clock gating (inverting) |
| clock | U5 | 7408 | clock gating (AND) |
| clock | U6 | 7432 | clock gating (OR) |
| program counter | U35 | 74161 | the PC: 4-bit counter |
| program counter | U36 | 74245 | PC onto the bus |
| A register | U7 | 74245 | A onto the bus |
| A register | U8, U9 | 74173 | A: low / high nibble latch |
| B register | U10 | 74245 | B onto the bus |
| B register | U11, U12 | 74173 | B: low / high nibble latch |
| instruction reg. | U13 | 74245 | bus into IR; operand nibble onto the bus |
| instruction reg. | U14, U15 | 74173 | IR: low / high nibble latch |
| ALU | U16, U18 | 7486 | XOR: invert B for subtract |
| ALU | U17 | 74245 | ALU sum onto the bus |
| ALU | U19 | 74173 | flag register: CF, ZF |
| ALU | U20, U21 | 74283 | 4-bit adders, low / high nibble |
| ALU | U22 | 7402 | NOR: zero detect |
| ALU | U23 | 7408 | AND: zero detect |
| MAR | U33 | 74157 | mux: panel address vs bus into the MAR |
| MAR | U34 | 74173 | the MAR: address latch |
| RAM | U24, U25 | 74189 | RAM: low / high nibble (16x4 each - the pair is the 16 bytes) |
| RAM | U26, U27 | 74157 | mux: panel data vs bus into the RAM |
| RAM | U28, U29 | 7404 | invert the RAM's inverted outputs back to true data |
| RAM | U30 | 74245 | RAM onto the bus |
| RAM | U31 | 7400 | NAND: write pulse with the clock |
| RAM | U32 | 74157 | mux: panel write vs microcode RI write-enable |
| output register | U37 | 7476 | display multiplex counter (2 bits) |
| output register | U38 | 74139 | decoder: which display digit is lit |
| output register | U44 | 74273 | the output register latch |
| output register | U45 | 28C16 | display ROM: seven-segment patterns |
| output register | U46 | 7408 | gate the output register's clock with OI |
| control unit | U47, U52 | 28C16 | control ROMs 1 and 2 (the microcode) |
| control unit | U48 | 74161 | microstep counter (T0..T7) |
| control unit | U49, U53 | 7404 | inverters: control-line enables |
| control unit | U50 | 74138 | decoder: step reset + T LEDs |
| control unit | U51 | 7400 | reset shaping + step-counter reset |

## The shared bus

Eight nets, BUS_0 (bit 0) .. BUS_7 (bit 7). One driver at a time - the
microcode guarantees it. Each bit's members:

- **drivers** (enabled by the control lines in parentheses):
  A register U7.B (AO), B register U10.B, instruction register U13.B
  (IO - drives only the operand nibble, bits 0-3), ALU U17.B (EO),
  RAM U30.B (RO), and the program-entry data muxes U26/U27.B (only in
  panel mode)
- **loads**: A register U8/U9.D (AI), B register U11/U12.D (BI),
  IR U14/U15.D (II), MAR U34.D (MI), output register U44.D (OI),
  PC U35.A-D (J - parallel load inputs), program-entry data muxes
  U26/U27.B
- **front panel**: the BUS_0..7 LEDs (bit 0 also carries a wire-label
  marker)

Nibble chips are wired with D3..D0 / B4..B1 / A5..A8 mapping to the
low-to-high bits - see the raw netlist for the exact pin of each bit.

## The control lines

Sixteen nets, one per bit of the control word, each with a front-panel
LED. Source: the control ROMs (U47 = ROM1, U52 = ROM2) through the
U49/U53 inverters; the full timing story is
[microcode.md](microcode.md). All are active-high at the ROM output; the
inverters turn them into the active-low enables the chips want.

| line | ROM bit | inverted by | drives | meaning when high |
|------|---------|-------------|--------|-------------------|
| HLT | U47.7 | U4 (clock gating) | clock gate | stop the clock |
| MI  | U47.6 | U49.1 | U34.DE (MAR) | MAR <- bus |
| RI  | U47.5 | U31 (NAND with CLK) | RAM write pulse | write RAM[MAR] |
| RO  | U47.4 | U49.2 | U30.~OE (RAM out) | RAM drives the bus |
| IO  | U47.3 | U49.3 | U13.~OE (IR out) | IR drives the operand nibble onto the bus |
| II  | U47.2 | U49.6 | U14/U15.DE (IR) | IR <- bus |
| AI  | U47.1 | U49.5 | U8/U9.DE (A) | A <- bus |
| AO  | U47.0 | U49.4 | U7.~OE (A out) | A drives the bus |
| EO  | U52.7 | U53.1 | U17.~OE (ALU out) | ALU drives the bus |
| SU  | U52.6 | - (drives gates directly) | U16/U18 inverters + U21.C0 | subtract: A + ~B + 1 |
| BI  | U52.5 | U53.2 | U11/U12.DE (B) | B <- bus |
| OI  | U52.4 | U46.1 (AND with CLK) | U44.CP (output register) | output register <- bus |
| CE  | U52.3 | - (drives counter enables) | U35.ENP/ENT (PC) | PC <- PC + 1 |
| CO  | U52.2 | U53.6 | U36.~OE (PC out) | PC drives the bus |
| J   | U52.1 | U53.5 | U35.~LD (PC load) | PC <- bus |
| FI  | U52.0 | U53.3 | U19.DE (flags) | CF/ZF <- ALU flags |

## Clock, reset, and power

- **CLK** (LED CLK): the gated machine clock - U5.3Y. Sources: U1 (the
  master clock) through U4/U5/U6 gating, or the STEP_PULSE button when
  STEP_MODE is on. Loads: every register and the RAM write logic
  (U8/U9, U11/U12, U14/U15, U19, U34, U35, U44 via U46, U31). HLT gates
  it off (through U4.4). The microstep counter U48 clocks on the
  inverted edge (U4.6Y), so it advances between the register edges.
- **RESET** (switch, active while held): U51.3 input. U51.3Y (NOT RESET,
  the ~CLR net) clears the counters U35 (PC) and U48 (microsteps) and
  the output register U44; U51.4Y (the CLR net, double inversion)
  clears every 74173's RES pin - A, B, IR, MAR, flags.
- **VCC/GND**: every chip's power pins; the 74157 mux enables (~G pins)
  are grounded (always on); ROM output enables grounded (always
  reading); the 28C16 ~WE pins tied high (never writing). The bus
  transceivers' DIR pins: U7/U10/U13/U17/U30 fixed (A->B or B->A per
  module); U36 (PC) DIR grounded for its direction.
- **U13.A1..A4 grounded**: this is what makes IO drive the operand
  *nibble* - the IR transceiver's high four A inputs are hard-grounded,
  so the bus's high nibble reads 0 while the IR drives.

## Front panel

Switches and buttons (each has VDD/GND on its unmodeled second throw):

- **RESET** - hold to clear everything (above).
- **STEP_MODE** (U4.1A, U5.1B) + **STEP_PULSE** (U5.1A) - manual
  clocking: with STEP_MODE on, the machine clock is disconnected and
  each STEP_PULSE click is one clock edge (single-stepping).
- **PROG_ADDR** (the RUN/PROG mode switch; the PROG LED lights in
  program mode) - drives the S select of the four panel muxes (U26,
  U27, U32, U33) directly: in program mode the RAM's address, data and
  write-enable come from the panel dipswitches instead of the machine.
- **PROG_ADDR_A0..A3** (dipswitches -> U33.A) - the RAM address for
  program entry.
- **PROG_DATA_0..7** (dipswitches -> U26/U27.A) - the data byte for
  program entry.
- **PROG_WRITE** (U32.A4) - in program mode, pulsing this writes the
  byte (through U32 -> U24/U25 ~WE).
- **DEC_HEX** (U45.A10) - display mode: 1 decimal, 0 hexadecimal.

LEDs: BUS_0..7, PC_0..3, A_0..7, B_0..7, SUM_0..7, CF, ZF, IR_0..7,
RAM_DATA_0..7, RAM address A0..A3, microsteps T0..T6, STEP_0..2 (the
counter's raw bits), all 16 control lines, CLK, PROG, PROG_hat (lit in
run mode - the complement of PROG through the Not gate at -700,520).

Program-mode polarity (matches the KiCad reference): the panel muxes
are 74157s, which select their A inputs (the panel) when S is LOW. The
PROG_ADDR switch grounds the S net when closed (KiCad SW6), and the
R63/D48 path pulls it high when open - so PROG_ADDR closed = program
mode (PROG LED lit), open = run mode (PROG_hat lit).

**Entering a program**: flip PROG_ADDR to program mode; for each byte of
the listing (built with [tools.md](tools.md), asm.py) set PROG_ADDR_A0..3
and PROG_DATA_0..7 and click PROG_WRITE; flip PROG_ADDR back to run
mode, pulse RESET, start the clock (or single-step). The listing's
ADDR/BYTE columns are the dipswitch settings.

**The display**: the output register byte (U44.Q) addresses the display
ROM (U45.A0..7) together with the multiplex counter (U37 -> U45.A8/A9),
which U38 decodes into which of the four digits is lit; U37 is clocked
by MUX_CLK (a second clock element - set it 500+ Hz so the rotation
looks steady). ROM data drives the segment pins of all four displays;
ROM A10 is the DEC_HEX mode switch.

The display ROM's address and data encoding:

- address = A10*1024 + A9*512 + A8*256 + byte. A8/A9 are the mux
  counter, so ROM page p lights the digit whose cathode U38.~1Yp pulls
  low: page 0 = ones (rightmost display), 1 = tens, 2 = hundreds,
  3 = thousands (blank for 8-bit values). A10 = DEC_HEX: 1 -> decimal,
  0 -> hex; leading zeros blanked in both modes.
- data bit -> segment: 6=a 5=b 4=c 3=d 2=e 1=f 0=g 7=dp.

## Modules and their wires

### Clock module

Makes the one edge the machine steps on, and lets two things interrupt
it: a program (HLT) and the operator (STEP_MODE/STEP_PULSE).

| net | members | what it does |
|-----|---------|--------------|
| STEP_MODE | U4.1A, U5.1B | 1 = manual clocking |
| STEP_PULSE | U5.1A | one edge per click when STEP_MODE |
| U4.1Y -> U5.2A | | NOT STEP_MODE into the master-clock AND |
| U1.Clock -> U5.2B | | the master clock into the same AND |
| U5.1Y, U5.2Y -> U6.1A, U6.1B | | the two clock sources |
| U6.1Y -> U5.3A | | OR of them: the ungated clock |
| HLT -> U4.4A, U4.4Y -> U5.3B | | NOT HLT gates the clock |
| U5.3Y = CLK | | the machine clock (see above) |
| U4.6A <- CLK, U4.6Y -> U48.CLK | | inverted clock to the microstep counter |

U4/U5/U6 spare gates are parked on NotConnected markers.

### Program counter (U35 74161, U36 74245)

Holds the address of the next instruction byte. U35 counts up when CE
(U35.ENP/ENT), loads from the bus when J (U53.5Y -> U35.~LD; the load
inputs U35.A..D are bus bits 0..3), clears with ~CLR. U36 puts the PC
on the bus while CO (U53.6Y -> U36.~OE); PC_0..3 are the Q outputs on
their way to U36 and the LEDs. U35.QD and RCO are unused.

### A register (U7 74245, U8/U9 74173)

The accumulator. U8/U9 latch the bus nibbles when AI (U49.5Y -> DE);
they clear with the reset net; outputs are the A_0..7 nets, which feed
the U7 transceiver (drives the bus while AO: U49.4Y -> U7.~OE), the
high adder U20.A (A bits 4..7) / low adder U21.A (A bits 0..3), and the
A LEDs. U7.DIR is tied to VDD (fixed A->bus direction).

### B register (U10 74245, U11/U12 74173)

The ALU's second input. Same shape as the A register (BI via
U53.2Y -> DE; outputs B_0..7), except the B bits feed only the ALU's
XOR inverters (U16 for bits 4..7, U18 for bits 0..3), not the bus.
U10.DIR is tied to VDD; U10.~OE is tied to a NotConnected marker - a
deliberate unwired extension point (a future BO control line would
land there; until then the transceiver is simply always enabled, which
is what Ben's board does by tying the pin to VCC).

### Instruction register (U13 74245, U14/U15 74173)

The byte being executed. U14/U15 latch the bus when II (U49.6Y); the
high nibble outputs (IR_4..7) address the control ROMs (U47/U52.A3..6)
and drive the IR_4..7 LEDs - the opcode; the low nibble (IR_0..3,
U15.Q) feeds U13.A5..A8 - the operand. U13 drives the bus *low nibble
only* while IO (U49.3Y -> U13.~OE): its A1..A4 are grounded, so bits
4..7 of the bus read 0. That is how LDI/ADDI/SUBI carry immediates and
how jumps carry their target address.

### ALU (U16/U18 7486, U20/U21 74283, U22 7402, U23 7408, U19 74173, U17 74245)

Adds or subtracts, and watches its own result.

| net | members | what it does |
|-----|---------|--------------|
| SU | U16/U18 B inputs, U21.C0 | invert every B bit and add 1: SUB = A + ~B + 1 |
| U16.y -> U20.B, U18.y -> U21.B | | inverted B into the adders |
| U20.C4 -> U21.C0 | | nibble carry chain |
| U21.C0 also <- SU | | the subtract's +1 rides the carry-in |
| SUM_0..7 | adder S outputs, U17.A, U22 inputs | the sum, on its way to the bus (EO: U53.1Y -> U17.~OE) |
| U22/U23 | NOR+AND tree over SUM | ZF term: all bits zero |
| U19.D0 <- U20/U21 carry chain | | CF term |
| U19.D1 <- U23.2Y (the zero tree) | | ZF term |
| U19.DE <- U53.3Y (FI) | | latch CF/ZF on the clock edge |
| CF -> U19.Q0, U47/U52.A8 | | carry flag, and control-ROM address bit A8 |
| ZF -> U19.Q1, U47/U52.A9 | | zero flag, and control-ROM address bit A9 |

### MAR (U33 74157, U34 74173)

The RAM address register. U34 latches the bus when MI (U49.1Y); its
outputs Q0..3 go back through U33 (B inputs) and out to the RAM address
nets A0..A3. In program mode U33 selects the PROG_ADDR_A0..3
dipswitches (A inputs) instead - the panel writes the MAR directly.
U34's output enables are grounded.

### RAM (U24/U25 74189, U26/U27/U32 74157, U28/U29 7404, U30 74245, U31 7400, U32 74157)

16 bytes: each 74189 is 16 words x 4 bits (64 bits per chip - there
are no A4/A5 pins), and the pair makes one 16-byte RAM, addressed by
the A0..A3 nets, shared with the MAR. More memory means new silicon,
not wiring ([additions.md](additions.md)). Their outputs
are inverted, so U28/U29 invert them back onto the RAM_DATA_0..7 nets
(RAM LEDs + U30.A); U30 drives the bus while RO (U49.2Y). Data in: the
U26/U27 muxes pick bus (B) or PROG_DATA dipswitches (A) into the RAM D
pins. Write: U31 NANDs CLK and RI into a low pulse, U32 (program mode)
selects it or the PROG_WRITE switch, and the result drives both chips'
~WE. ~CS is grounded (always selected).

### Output register (U44 74273, U45 28C16, U37 7476, U38 74139, U46 7408)

The display. U44 is a 74273 (no data-enable pins), so its clock itself
is gated: U46 ANDs CLK with OI (U52.I/O4 -> U46.1A) into U44.CP. Its
outputs U44.Q0..7 address the display ROM (U45.A0..7). U37 (7476) is a
2-bit counter clocked by MUX_CLK; its outputs feed U38 (74139), which
pulls one display's common cathode low at a time, and U45.A8/A9 (the
digit page). The ROM's address/segment encoding is in "The display"
above; the image is archived in [../roms/](../roms/README.md).

### Control unit (U47/U52 28C16, U48 74161, U50 74138, U49/U53 7404, U51 7400)

The microcode engine - fully documented in [microcode.md](microcode.md).
Its wires in brief:

| net | members | what it does |
|-----|---------|--------------|
| STEP_0..2 | U48.Q, U47/U52.A0..2, U50.A/B/C | microstep counter value |
| IR_4..7 | U14.Q, U47/U52.A3..6 | opcode addresses the ROMs |
| CF, ZF | U19.Q, U47/U52.A8/A9 | flags address the ROMs (conditional rows) |
| U47/U52.A7 -> VDD, A10 -> GND | | both ROMs read their replicated image; A7 is Ben's "which ROM" bit, replicated across |
| U47/U52 I/O0..7 | the control lines above | the 16-bit control word |
| T0..T6 | U50.~Y0..~Y6, LEDs | microstep indicators |
| U50.~Y7 -> U51.2B | | T7 (transient) resets the microstep counter |
| U51 gates 1/2 | ~CLR + ~Y7 -> U48.~CLR | reset OR end-of-instruction: restart at T0 |
| U51 gate 3 | RESET -> ~CLR | NOT RESET (the active-low clear net) |
| U51 gate 4 | ~CLR -> CLR | RESET again (active-high clear for the 74173s) |

## Wiring notes (vs Ben's KiCad reference)

The circuit matches the KiCad netlist pin for pin except for these
deliberate or benign points:

- Clock: Digital's realtime Clock element (U1) stands in for the 555s;
  the gating around it (U4/U5/U6) matches the KiCad nets.
- A register: the AO control line drives U7's ~OE directly (Ben inverts
  AO on his control card instead; same polarity at the module boundary).
- B register: U10's ~OE is a NotConnected marker (see above) where Ben
  ties it to VCC.
- MAR/RAM: chip enables tie to individual Ground symbols where Ben's
  board uses one shared GND rail - electrically identical.
- ALU: which XOR gate inside U16/U18 drives which adder B input is
  permuted vs the KiCad placement, but every bit is paired correctly.
- Control: both ROMs' A7 pins are tied to VDD (Ben grounds U47's A7) -
  harmless, the images are replicated across A7.
- Control: Ben's KiCad 74LS00 symbol has non-standard gate 3/4 pin
  roles; the circuit is wired to the *function* of the real 7400.

The simulator quirks of Digital 0.31's DIL chip library (which affect
simulating this circuit, not its correctness): [tools.md](tools.md),
"Digital 0.31 notes".
