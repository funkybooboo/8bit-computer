// machine.js - the machine, cycle-accurate.
//
// The machine in code: it runs the REAL control-ROM images
// (roms/control-rom1.hex and roms/control-rom2.hex - the same images the
// Digital build carries and the hardware burns). Every clock cycle it
// looks up the 16-bit control word at (step, opcode, CF, ZF) and asserts
// the control signals against the registers, RAM and bus - fetch included.
// Nothing is special-cased per instruction: if the ROM images are wrong,
// programs fail here exactly the way they fail on the machine.
//
// Machine model (full reference: docs/microcode.md, docs/instruction-set.md):
//   - 8 cycles per instruction: steps T0-T6 stable, T7 the transient step
//     that resets the step counter (the ROM rows for T7 are all zero)
//   - fetch (all instructions): T0 MI|CO (MAR <- PC), T1 RO|II|CE
//   - bus drivers (exactly one may be active per cycle): CO (PC), RO
//     (RAM at MAR), IO (operand nibble, zero-extended), AO (A), EO (ALU)
//   - ALU: A + B, or A - B when SU (A + ~B + 1); FI latches CF and ZF
//   - registers latch on the CLK edge, all from the pre-edge state;
//     the microstep counter advances on the INVERTED edge, between
//     register edges; RI writes RAM[MAR]; PC wraps mod 16
//
// The control-word bits below come from tools/genroms.py (ROM1_BITS /
// ROM2_BITS, the machine definition in code) - one source of truth,
// kept in sync by web/test/verify.py's run against its frozen
// expectations table.

export const ROM1_BITS = {  // U47
  HLT: 0x80, MI: 0x40, RI: 0x20, RO: 0x10,
  IO: 0x08, II: 0x04, AI: 0x02, AO: 0x01,
};
export const ROM2_BITS = {  // U52
  EO: 0x80, SU: 0x40, BI: 0x20, OI: 0x10,
  CE: 0x08, CO: 0x04, J: 0x02, FI: 0x01,
};

export const OPCODES = {  // tools/genroms.py OPCODES, same table
  NOP: 0x0, LDA: 0x1, ADD: 0x2, SUB: 0x3, STA: 0x4, LDI: 0x5,
  JMP: 0x6, JC: 0x7, JZ: 0x8, JNC: 0x9, JNZ: 0xa, ADDI: 0xb,
  SUBI: 0xc, DBL: 0xd, OUT: 0xe, HLT: 0xf,
};
const MNEMONIC = new Map(Object.entries(OPCODES).map(([m, o]) => [o, m]));
export function opcodeName(opcode) {
  return MNEMONIC.get(opcode) || "?";
}

export const MEM_SIZE = 16;  // the MAR is 4 bits
export const STEPS = 8;      // step counter resets at T7 (docs/microcode.md)

export function controlNames(w1, w2) {
  const names = [];
  for (const [n, b] of Object.entries(ROM1_BITS)) if (w1 & b) names.push(n);
  for (const [n, b] of Object.entries(ROM2_BITS)) if (w2 & b) names.push(n);
  return names;
}

export class Machine {
  /** rom1, rom2: Uint8Array control-ROM images (2048 bytes each);
   *  ram: Uint8Array program image (16 bytes). */
  constructor(rom1, rom2, ram) {
    this.rom1 = rom1;
    this.rom2 = rom2;
    this.ram = new Uint8Array(ram ? ram : new Uint8Array(MEM_SIZE));
    this.pc = this.mar = 0;        // 4 bits, wrap mod 16
    this.ir = 0;                    // 8 bits: opcode nibble + operand
    this.a = this.b = this.out = 0; // 8 bits, wrap mod 256
    this.cf = this.zf = 0;
    this.step = 0;
    this.halted = false;
    this.cycles = 0;
    this.instructions = 0;
    this.outputs = [];
  }

  // -- the ALU, as the hardware computes it (A + ~B + 1 when SU) -------

  alu(su) {
    const t = this.a + (su ? (~this.b & 0xff) : this.b) + (su ? 1 : 0);
    return [t & 0xff, t > 0xff ? 1 : 0];
  }

  // -- the clock, as the hardware shapes it -----------------------------
  //
  // One full cycle is two edges. The registers step on the CLK edge
  // (risingEdge); the microstep counter U48 clocks on the INVERTED edge
  // (fallingEdge), so it advances BETWEEN register edges - which is why
  // the control word selected by (step, opcode, CF, ZF) is stable for the
  // whole cycle. Nothing is special-cased per instruction: if the ROM
  // images are wrong, programs fail here exactly the way they fail on
  // the machine.

  /** The edge the registers step on. Latches every register from the
   *  pre-edge state, per the word selected by the current step.
   *  Returns the bus value; throws on bus contention in the microcode. */
  risingEdge() {
    const opcode = this.ir >> 4;
    const addr = this.step | (opcode << 3) | (this.cf << 8) | (this.zf << 9);
    const w1 = this.rom1[addr], w2 = this.rom2[addr];

    // capture the ALU result/carry from the PRE-edge state here, because
    // FI latches the flags of THIS result even after AI has latched it
    // into A
    let aluRes = null, aluCf = null;
    if (w2 & ROM2_BITS.EO) {
      [aluRes, aluCf] = this.alu(w2 & ROM2_BITS.SU);
    }

    // bus: exactly one driver asserted (the microcode guarantees it)
    const on = [];
    if (w2 & ROM2_BITS.CO) on.push(this.pc);
    if (w1 & ROM1_BITS.RO) on.push(this.ram[this.mar]);
    if (w1 & ROM1_BITS.IO) on.push(this.ir & 0xf);
    if (w1 & ROM1_BITS.AO) on.push(this.a);
    if (w2 & ROM2_BITS.EO) on.push(aluRes);
    if (on.length > 1) throw new Error("bus contention in the microcode");
    const bus = on.length ? on[0] : 0;

    // the edge: all latches from the pre-edge state
    if (w1 & ROM1_BITS.MI) this.mar = bus & 0xf;
    if (w1 & ROM1_BITS.II) this.ir = bus & 0xff;
    if (w2 & ROM2_BITS.BI) this.b = bus & 0xff;
    if (w1 & ROM1_BITS.AI) this.a = bus & 0xff;
    if (w1 & ROM1_BITS.RI) this.ram[this.mar] = bus & 0xff;
    if (w2 & ROM2_BITS.OI) {
      this.out = bus & 0xff;
      this.outputs.push(this.out);
    }
    if (w2 & ROM2_BITS.J) this.pc = bus & 0xf;
    if (w2 & ROM2_BITS.CE) this.pc = (this.pc + 1) & 0xf;
    if (w2 & ROM2_BITS.FI) {
      if (aluRes === null) {  // FI without EO: the current ALU output
        [aluRes, aluCf] = this.alu(w2 & ROM2_BITS.SU);
      }
      this.cf = aluCf;
      this.zf = aluRes === 0 ? 1 : 0;
    }
    if (w1 & ROM1_BITS.HLT) this.halted = true;  // the 7476 gates the clock off

    this.cycles++;
    return bus;
  }

  /** The inverted edge: only the microstep counter moves. */
  fallingEdge() {
    this.step = (this.step + 1) % STEPS;  // T7's word is zero and resets U48
    if (this.step === 0) this.instructions++;
  }

  /** One full clock cycle: both edges. Returns the bus value. */
  cycle() {
    const bus = this.risingEdge();
    this.fallingEdge();
    return bus;
  }

  /** The RESET switch, as wired: clears the PC (U35), the microstep
   *  counter (U48), the output register (U44) and every 74173's RES pin
   *  (A, B, IR, MAR, flags). RAM is NOT cleared - the 74189s are not on
   *  the reset net - so a reset+rerun re-runs over whatever the previous
   *  run left in memory, exactly like the hardware. The outputs log is
   *  an observation record, not machine state; reset does not touch it. */
  reset() {
    this.pc = this.mar = 0;
    this.ir = 0;
    this.a = this.b = this.out = 0;
    this.cf = this.zf = 0;
    this.step = 0;
    this.halted = false;
  }

  /** Run until halt or maxCycles; returns true iff halted. */
  run(maxCycles) {
    while (!this.halted && this.cycles < maxCycles) this.cycle();
    return this.halted;
  }
}
