// main.js - the web app: the machine, and only the machine.
//
// It powers on like the hardware does: clock running (STEP_MODE AUTO),
// RAM empty (16 NOPs), the display dark. A program gets in exactly one
// way - the panel switches, the way the hardware does it:
//
//   PROG_ADDR -> PROG (on the MAR), set PROG_ADDR_A + PROG_DATA from a
//   listing, PROG_WRITE per byte (on the RAM), PROG_ADDR -> RUN, RESET.
//
// Writing programs is the repo's job, not the app's: the footer links
// to the repo (the tools, the docs, the program sources), where a
// listing for hand entry is one command away.
//
// The machine itself is js/machine.js - cycle-accurate on the real
// control-ROM images. The display is js/display.js on the real
// output-display.hex. The parts and their placement follow
// docs/hardware.md, mirroring the Digital build.

import { parseImage } from "./hex.js";
import { Machine, ROM2_BITS } from "./machine.js";
import { makeDisplay } from "./display.js";
import {
  moduleCard, ledBank, namedLeds, dipRow, toggleSwitch, keycap,
} from "./panel.js";

const $ = (id) => document.getElementById(id);

// ---------------------------------------------------------------- state

let machine = null;
let rom1 = null, rom2 = null, displayRom = null;
let lastCycle = null;  // { bus } of the last executed cycle
let decHex = true;     // the DEC_HEX switch (U45.A10): 1 = decimal
let muxCnt = 0;        // the U37 display-mux counter, free-running

const prog = { mode: false, addr: 0, data: 0 };  // the panel switches
const clock = {
  stepMode: false,  // STEP_MODE: false = AUTO (the master clock runs),
  hz: 4,            //   true = MANUAL (STEP_PULSE single-steps)
  phase: false,
  acc: 0,
  lastT: 0,
};

const panel = $("panel");
const out = {};

// ---------------------------------------------------------------- loading

async function fetchImage(url, size) {
  const r = await fetch(url);
  if (!r.ok) throw new Error("fetch " + url + ": " + r.status);
  return parseImage(await r.arrayBuffer(), size);
}

async function loadRoms() {
  [rom1, rom2, displayRom] = await Promise.all([
    fetchImage("../roms/control-rom1.hex", 2048),
    fetchImage("../roms/control-rom2.hex", 2048),
    fetchImage("../roms/output-display.hex", 2048),
  ]);
}

// ---------------------------------------------------------------- the panel

function buildPanel() {
  // the output module: the display (the machine's own OUT readout)
  // and its DEC_HEX mode switch
  const mOut = moduleCard("OUTPUT", "U44 74273 / U45 28C16");
  out.decHex = toggleSwitch("DEC", "HEX", (on) => { decHex = !on; }, "DEC_HEX");
  const bezel = document.createElement("div");
  bezel.className = "segbezel";
  bezel.append($("display-canvas"));
  mOut.append(bezel, out.decHex.el);

  // the clock module: the CLK lamp, the STEP_MODE switch + STEP_PULSE
  // key (manual clocking), and the master clock's rate (U1 - the 555's
  // pot on the breadboard)
  const mClock = moduleCard("CLOCK", "U1..U6 - clock + gating");
  out.clk = namedLeds(["CLK"], "g", true);
  out.stepMode = toggleSwitch("AUTO", "MANUAL", (on) => {
    clock.stepMode = on;
    clock.acc = 0;  // U4.1: MANUAL disconnects the master clock
  }, "STEP_MODE");
  out.stepPulse = keycap("STEP_PULSE", step);
  const rateRow = document.createElement("div");
  rateRow.className = "bank";
  const rateNote = document.createElement("span");
  rateNote.className = "note";
  rateNote.textContent = "U1 RATE";
  rateNote.title = "the master clock's frequency - the 555's pot";
  const hzSlider = document.createElement("input");
  hzSlider.type = "range";
  hzSlider.min = 0;
  hzSlider.max = 100;
  hzSlider.value = 18;  // ~4 Hz
  const hzRead = document.createElement("span");
  hzRead.className = "note";
  const hzText = (hz) =>
    (hz >= 10 ? Math.round(hz) : hz.toFixed(1)) + " Hz";
  hzRead.textContent = hzText(clock.hz);
  hzSlider.addEventListener("input", () => {
    // 0..100 -> 1..2048 Hz, logarithmic
    clock.hz = Math.pow(2, (hzSlider.value / 100) * 11);
    hzRead.textContent = hzText(clock.hz);
  });
  rateRow.append(rateNote, hzSlider, hzRead);
  mClock.append(out.clk.el, out.stepMode.el, out.stepPulse, rateRow);

  // the shared bus, as the rail it is: the 8 BUS lamps between the
  // module columns, the wire itself running the panel's height - every
  // module on either side taps it
  const mBus = moduleCard("BUS", "U30 U36 U13 U7 U17");
  mBus.classList.add("mid");
  out.bus = ledBank("", 8, "r");
  const rail = document.createElement("div");
  rail.className = "rail";  // the wire itself
  rail.title = "the shared bus - every module taps it";
  mBus.append(out.bus.el, rail);

  // the control unit: both ROM banks, the microstep lamps, and the
  // RESET key (it wires into U51 here - the reset shaping, which
  // clears every register's RES pin)
  const mCtrl = moduleCard("CONTROL", "U47 U52 28C16 / U48 74161 / U51 7400");
  out.rom1 = namedLeds(["HLT", "MI", "RI", "RO", "IO", "II", "AI", "AO"], "a", false);
  out.rom2 = namedLeds(["EO", "SU", "BI", "OI", "CE", "CO", "J", "FI"], "a", false);
  out.t = namedLeds(["T0", "T1", "T2", "T3", "T4", "T5", "T6"], "a", true);
  out.q = namedLeds(["STEP_2", "STEP_1", "STEP_0"], "a", false);
  out.resetKey = keycap("RESET", reset);
  mCtrl.append(out.rom1.el, out.rom2.el, out.t.el, out.q.el, out.resetKey);

  // the registers
  const mPc = moduleCard("PC", "U35 74161");
  out.pc = ledBank("PC", 4, "r");
  mPc.append(out.pc.el);

  // the MAR: the address latch, and the program-address side of
  // program entry - the PROG_ADDR mode switch (it selects the panel
  // side of all four muxes, U26 U27 U32 U33) and the address
  // dipswitches, which wire into U33 here
  const mMar = moduleCard("MAR", "U34 74173 / U33 74157");
  out.mar = ledBank("MAR", 4, "r");
  out.progMode = toggleSwitch("RUN", "PROG", (on) => { prog.mode = on; }, "PROG_ADDR");
  out.progLeds = namedLeds(["PROG", "PROG_hat"], "a", true);
  prog.addrDips = dipRow("PROG_ADDR_A", 4, (v) => { prog.addr = v; });
  mMar.append(out.mar.el, out.progMode.el, out.progLeds.el, prog.addrDips.el);

  const mIr = moduleCard("INSTRUCTION", "U14 U15 74173");
  out.ir = ledBank("IR", 8, "r");
  mIr.append(out.ir.el);
  const mA = moduleCard("A REGISTER", "U8 U9 74173");
  out.a = ledBank("A", 8, "r");
  mA.append(out.a.el);
  const mB = moduleCard("B REGISTER", "U11 U12 74173");
  out.b = ledBank("B", 8, "r");
  mB.append(out.b.el);
  const mAlu = moduleCard("ALU", "U20 U21 74283 / U19 74173");
  out.sum = ledBank("SUM", 8, "r");
  out.flags = namedLeds(["CF", "ZF"], "g", true);
  mAlu.append(out.sum.el, out.flags.el);

  // the RAM: the addressed byte's lamps (in PROG mode they show the
  // addressed dipswitch byte - the verification readback), and the
  // program-data side of entry (PROG_DATA through U26/U27, the write
  // through U32)
  const mRam = moduleCard("RAM", "U24 U25 74189 / U30 74245 / U26 U27 U32");
  out.ramAddr = ledBank("ADDR", 4, "r");
  out.ramData = ledBank("DATA", 8, "r");
  prog.dataDips = dipRow("PROG_DATA", 8, (v) => { prog.data = v; });
  out.writeKey = keycap("PROG_WRITE", () => {
    if (!machine) return;
    if (!prog.mode) {
      status("the write is disconnected while PROG_ADDR is RUN - flip it to PROG (the write goes through U32)");
      return;
    }
    machine.ram[prog.addr] = prog.data;  // the write pulse, as wired
    render();
  });
  mRam.append(out.ramAddr.el, out.ramData.el, prog.dataDips.el, out.writeKey);

  // the arrangement mirrors the Digital build (and Ben's breadboards):
  // left column CLOCK, MAR, RAM, IR, CONTROL; right column PC (top),
  // A, ALU, B, OUTPUT; the BUS rail down the middle. Rows are placed
  // explicitly (implicit-row spanning is unreliable), so the pairing
  // is stable.
  const ROWS = 5;
  const place = (m, col, row) => {
    m.classList.add(col);
    m.style.gridRow = String(row);
    panel.append(m);
  };
  mBus.style.gridRow = "1 / span " + ROWS;
  panel.append(mBus);  // the rail first: middle column, full height
  place(mClock, "l", 1);  place(mPc, "r", 1);
  place(mMar, "l", 2);   place(mA, "r", 2);
  place(mRam, "l", 3);   place(mAlu, "r", 3);
  place(mIr, "l", 4);    place(mB, "r", 4);
  place(mCtrl, "l", 5);  place(mOut, "r", 5);
}

// ---------------------------------------------------------------- actions

/** The control word for the cycle about to execute (docs/microcode.md,
 *  "Timing") - the word the panel lamps show, steady between edges. */
function peekWord() {
  const opcode = machine.ir >> 4;
  const addr = machine.step | (opcode << 3) | (machine.cf << 8) | (machine.zf << 9);
  return [machine.rom1[addr], machine.rom2[addr]];
}

function doCycle() {
  const bus = machine.cycle();
  lastCycle = { bus };
  clock.phase = !clock.phase;
}

/** STEP_PULSE, as gated on the machine (U5.1): one clock edge per
 *  click, but only while STEP_MODE is MANUAL - in AUTO the button is
 *  disconnected. */
function step() {
  if (!machine || machine.halted) return;
  if (!clock.stepMode) {
    status("STEP_PULSE is disconnected while STEP_MODE is AUTO (U5.1) - flip STEP_MODE to MANUAL");
    return;
  }
  doCycle();
  render();
}

/** RESET, as wired through U51: clears the PC, the step counter, the
 *  output register and every 74173 (A, B, IR, MAR, flags) - and does
 *  NOT clear RAM, which is not on the reset net. */
function reset() {
  if (!machine) return;
  machine.reset();
  render();
}

// ---------------------------------------------------------------- render

let stickyStatus = null;  // a message that stays until cleared (?smoke=1)

function status(text) {
  $("status").textContent = text || "";
}

function render() {
  const m = machine;
  if (!m) return;
  const [w1, w2] = peekWord();

  out.bus.set(lastCycle ? lastCycle.bus : 0);
  out.pc.set(m.pc);
  out.mar.set(m.mar);
  out.ir.set(m.ir);
  out.a.set(m.a);
  out.b.set(m.b);
  const [sum] = m.alu(w2 & ROM2_BITS.SU);  // the adder's live output
  out.sum.set(sum);
  out.flags.set((m.cf << 1) | m.zf);

  out.rom1.set(w1);
  out.rom2.set(w2);
  out.t.set(1 << m.step);
  out.q.set(m.step);

  // RAM: the 74157 muxes put the panel switches on in program mode -
  // and the DATA lamps are the readback for hand entry
  const eff = prog.mode ? prog.addr : m.mar;
  out.ramAddr.set(eff);
  out.ramData.set(m.ram[eff]);

  out.clk.set(clock.phase ? 1 : 0);
  out.progLeds.set(prog.mode ? 1 : 2);  // PROG in program mode, PROG_hat in run

  // the keys tell their own gating story (dim while disconnected)
  out.stepPulse.classList.toggle("dim", !clock.stepMode || m.halted);
  out.writeKey.classList.toggle("dim", !prog.mode);

  // the display (all four digits: the persistence-of-vision view)
  if (out.display) out.display.draw(m.out, decHex);

  status(stickyStatus ||
    (m.halted ? "HLT - the clock is gated off (U4.4). RESET to run again." : ""));
}

// ---------------------------------------------------------------- the loop

function frame(t) {
  if (machine && !clock.stepMode && !machine.halted) {
    if (clock.lastT) clock.acc += ((t - clock.lastT) / 1000) * clock.hz;
    const whole = Math.floor(clock.acc);
    clock.acc -= whole;  // a background tab's backlog is dropped
    const n = Math.min(whole, 20000);
    for (let i = 0; i < n && !machine.halted; i++) doCycle();
  }
  clock.lastT = t;
  // the display mux counter (U37) free-runs at MUX_CLK speed
  muxCnt += ((t - (frame.lastT || t)) / 1000) * 500;
  frame.lastT = t;
  render();
  requestAnimationFrame(frame);
}

// ---------------------------------------------------------------- self-test

/** ?smoke=1: the served app checks itself the pure way - a program
 *  entered through the panel switches, the gating, the clock. Results
 *  land in the status line, so a headless run (or a user) can see
 *  them. */
async function runSmoke() {
  const results = [];
  const check = (name, ok) => results.push((ok ? "PASS " : "FAIL ") + name);
  // a counting program, entered by hand: LDI 0, OUT, ADDI 1, JMP 1
  out.progMode.set(true);  // fires the switch's onChange
  const image = [[0, 0x50], [1, 0xe0], [2, 0xb1], [3, 0x61]];
  for (const [a, b] of image) {
    prog.addrDips.set(a);
    prog.dataDips.set(b);
    out.writeKey.click();
  }
  check("hand entry -> RAM",
    image.every(([a, b]) => machine.ram[a] === b));
  out.progMode.set(false);
  // STEP_PULSE is disconnected in AUTO
  const before = machine.step;
  step();
  check("STEP_MODE gates STEP_PULSE", machine.step === before);
  // MANUAL: single-steps; then the clock runs the program
  out.stepMode.set(true);
  reset();
  step();
  step();
  check("STEP_PULSE steps", machine.step === 2);
  out.stepMode.set(false);
  machine.run(400);
  check("the program counts 0,1,2,...",
    machine.outputs.length > 10 &&
    machine.outputs.slice(0, 10).every((v, i) => v === i));
  out.display.draw(255, true);
  out.display.draw(0xaf, false);
  check("display draws", true);
  stickyStatus = "SMOKE: " + (results.some((r) => r.startsWith("FAIL"))
    ? results.join(" | ") : "all checks passed (" + results.length + ")");
  status(stickyStatus);
}

// ---------------------------------------------------------------- wiring

async function init() {
  buildPanel();
  try {
    await loadRoms();
  } catch (e) {
    status("could not load the ROM images: " + e +
      " - serve the repo root with an HTTP server (see web/README.md)");
    return;
  }
  out.display = makeDisplay($("display-canvas"), displayRom);

  // power on: the clock runs (STEP_MODE AUTO) over empty RAM - 16 NOPs
  machine = new Machine(rom1, rom2, null);
  render();

  document.addEventListener("keydown", (ev) => {
    if (ev.key !== " ") return;
    if (!(ev.target instanceof Element)) return;
    if (ev.target.closest("input, select, textarea, button, label")) return;
    ev.preventDefault();
    step();
  });

  if (new URLSearchParams(location.search).get("smoke")) {
    runSmoke();
  }
  requestAnimationFrame(frame);
}

init();
