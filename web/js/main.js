// main.js - the web app: the machine (js/machine.js) wired to the front
// panel (js/panel.js): the clock, the keys, the panel switches, the
// display, the toolchain (js/hlc.js + js/asm.js, so any .hl or .asm
// program can be built and run in the browser) and the docs reader
// (js/docs.js).
//
// The panel follows docs/hardware.md, "The front panel": which LEDs
// exist, which switches, and the program-entry procedure. The clock
// module's own switches (STEP_MODE / STEP_PULSE, the master clock) are
// the deck's STEP key and RUN/PAUSE key.

import { parseImage } from "./hex.js";
import {
  Machine, MEM_SIZE, controlNames, opcodeName, ROM1_BITS, ROM2_BITS,
} from "./machine.js";
import { makeDisplay } from "./display.js";
import { compileHl, HLError } from "./hlc.js";
import { assemble as assembleAsm, MNEMONICS, AsmError } from "./asm.js";
import { makeDocsViewer, renderMarkdown } from "./docs.js";
import {
  moduleCard, ledBank, namedLeds, dipRow, toggleSwitch, keycap,
  ramMonitor, listingPane, ledColumn,
} from "./panel.js";

// the programs this build serves: the tracked .hl sources in programs/,
// fetched and compiled in the browser by the same toolchain the repo
// uses (js/hlc.js + js/asm.js, byte-identical by test/test_tools.py) -
// so a statically hosted bare clone works with nothing prebuilt
const PROGRAMS = [
  "absdiff", "bits", "bothflags", "count", "countdown", "decrement",
  "div", "fib", "gcd", "half", "larger", "lcg", "memory", "min",
  "mod", "mul", "odometer", "overflow", "patch", "powers", "rol",
  "rotate", "squares", "step", "triple",
];

const MAX_CYCLES = 100000;  // the turbo cap (same as run.mjs)
const TRACE_MAX = 400;      // trace lines kept (oldest dropped)
const OUT_MAX = 300;        // OUT log lines kept
const MUX_HZ = 500;         // U37's MUX_CLK (docs/hardware.md: 500+ Hz)

const $ = (id) => document.getElementById(id);

// ---------------------------------------------------------------- state

let machine = null;    // the Machine, when a program is loaded
let programName = null;
let rom1 = null, rom2 = null, displayRom = null;
let lastCycle = null;  // { bus, driver } of the last executed cycle
let decHex = true;     // the DEC_HEX switch (U45.A10): 1 = decimal
let muxCnt = 0;        // the U37 display-mux counter, free-running

const prog = { mode: false, addr: 0, data: 0 };  // the panel switches
const clock = { auto: false, hz: 4, phase: false, acc: 0, lastT: 0 };
let traceOn = false;   // log cycles while the clock runs, not just steps
let traceLines = [];

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

async function loadProgram(name) {
  // the tracked source, compiled in the browser: the fetched file is
  // static, and the build is the repo's own (byte-identical, tested)
  const r = await fetch("../programs/" + name + ".hl");
  if (!r.ok) throw new Error("fetch " + name + ".hl: " + r.status);
  const { mem, listing: lst } = compileHl(await r.text());
  programName = name;
  listing.set(lst);
  startMachine(mem);
}

function startMachine(ram) {
  machine = new Machine(rom1, rom2, ram);
  lastCycle = null;
  clock.auto = false;
  runKey.textContent = "RUN";
  traceLines = [];
  traceDirty = true;
  outCount = -1;  // force the OUT log redraw
  render();
}

// ---------------------------------------------------------------- the panel

const panel = $("panel");
const out = {};

// what is on the machine vs what is this app's: hardware parts are
// unmarked; everything the machine does not have gets the dashed
// "web" treatment (css/style.css) and the legend above the panel
// explains it. The inventory of the real panel: docs/hardware.md,
// "The front panel".
function markWeb(el) {
  el.classList.add("web");
  return el;
}

function buildPanel() {
  // the output module: the display (the machine's own OUT readout),
  // the DEC_HEX mode switch, and this app's extra readouts (marked)
  const mOut = moduleCard("OUTPUT", "U44 74273 / U45 28C16");
  out.reg = ledBank("OUT", 8, "r");  // not on the machine: OUT shows on the display only
  markWeb(out.reg.el);
  out.mux = namedLeds(["C1", "C0"], "a", false);  // U37's counter: internal, not on the panel
  markWeb(out.mux.el);
  out.decHex = toggleSwitch("DEC", "HEX", (on) => { decHex = !on; }, "DEC_HEX");
  const bezel = document.createElement("div");
  bezel.className = "segbezel";
  bezel.append($("display-canvas"));
  mOut.append(bezel, out.reg.el, out.mux.el, out.decHex.el);

  // the clock module, as the hardware has it: the CLK LED, the
  // STEP_MODE switch + STEP_PULSE key (manual clocking), RESET, and
  // the master clock's rate (U1 - the 555's pot on the breadboard)
  const mClock = moduleCard("CLOCK", "U1..U6 - clock + gating");
  out.clk = namedLeds(["CLK"], "g", true);
  out.halt = namedLeds(["HALT"], "r", true);  // the machine just stops; this lamp is the app's
  markWeb(out.halt.el);
  out.stepMode = toggleSwitch("AUTO", "MANUAL", (on) => {
    clock.stepMode = on;
    if (on) {  // U4.1: STEP_MODE disconnects the master clock
      clock.auto = false;
      runKey.textContent = "RUN";
    }
  }, "STEP_MODE");
  out.stepPulse = keycap("STEP_PULSE", step);
  out.resetKey = keycap("RESET", reset);
  const rateRow = document.createElement("div");
  rateRow.className = "bank";
  const rateNote = document.createElement("span");
  rateNote.className = "note";
  rateNote.textContent = "U1 RATE";
  rateNote.title = "the master clock's frequency - the 555's pot";
  mClock.append(out.clk.el, out.halt.el, out.stepMode.el,
    out.stepPulse, out.resetKey, rateRow);
  rateRow.append(rateNote, hzSlider, hzRead);
  const clockHint = document.createElement("p");
  clockHint.className = "hint";
  clockHint.textContent = "STEP_MODE MANUAL disconnects the master clock" +
    " (U4.1); each STEP_PULSE click is then one clock edge. HLT gates" +
    " the clock off entirely (U4.4). RESET clears PC/step/OUT/A/B/IR/" +
    "MAR/flags - not RAM.";
  mClock.append(clockHint);

  // the shared bus, as the rail it is: a vertical strip of the 8 BUS
  // lamps running down the middle between the module columns, every
  // module on either side tapping it (the driver note below the lamps
  // is this app's annotation)
  const mBus = moduleCard("BUS", "U30 U36 U13 U7 U17");
  mBus.classList.add("mid");
  out.bus = ledColumn(8, "r");
  const busFoot = document.createElement("div");
  busFoot.className = "bank";
  busFoot.append(out.bus.read, out.bus.note);
  markWeb(out.bus.note);
  mBus.append(out.bus.el, busFoot);

  // the control module: both ROM banks, the microstep LEDs
  const mCtrl = moduleCard("CONTROL", "U47 U52 28C16 / U48 74161");
  out.rom1 = namedLeds(["HLT", "MI", "RI", "RO", "IO", "II", "AI", "AO"], "a", false);
  out.rom2 = namedLeds(["EO", "SU", "BI", "OI", "CE", "CO", "J", "FI"], "a", false);
  out.t = namedLeds(["T0", "T1", "T2", "T3", "T4", "T5", "T6"], "a", true);
  out.q = namedLeds(["STEP_2", "STEP_1", "STEP_0"], "a", false);

  // the registers
  const mPc = moduleCard("PC", "U35 74161");
  out.pc = ledBank("PC", 4, "r");
  const mMar = moduleCard("MAR", "U34 74173");
  out.mar = ledBank("MAR", 4, "r");
  const mIr = moduleCard("INSTRUCTION", "U14 U15 74173");
  out.ir = ledBank("IR", 8, "r", true);
  if (out.ir.note) markWeb(out.ir.note);  // the mnemonic: the app's annotation
  const mA = moduleCard("A REGISTER", "U8 U9 74173");
  out.a = ledBank("A", 8, "r");
  const mB = moduleCard("B REGISTER", "U11 U12 74173");
  out.b = ledBank("B", 8, "r");
  const mAlu = moduleCard("ALU", "U20 U21 74283 / U19 74173");
  out.sum = ledBank("SUM", 8, "r");
  out.flags = namedLeds(["CF", "ZF"], "g", true);

  // the RAM: the addressed byte's LEDs + this app's monitor (marked)
  const mRam = moduleCard("RAM", "U24 U25 74189 / U30 74245");
  out.ramAddr = ledBank("ADDR", 4, "r");
  out.ramData = ledBank("DATA", 8, "r");
  out.ram = ramMonitor(decodeByte, (addr) => {
    // load the row into the panel dipswitches
    prog.addrDips.set(addr);
    prog.dataDips.set(machine ? machine.ram[addr] : 0);
  });
  markWeb(out.ram.el);

  // the front panel: program entry exactly as the hardware does it
  // (the switches carry the hardware's own net names)
  const mPanel = moduleCard("FRONT PANEL", "program entry (docs/hardware.md)");
  out.progMode = toggleSwitch("RUN", "PROG", (on) => { prog.mode = on; }, "PROG_ADDR");
  out.progLeds = namedLeds(["PROG", "PROG_hat"], "a", true);
  prog.addrDips = dipRow("PROG_ADDR_A", 4, (v) => { prog.addr = v; });
  prog.dataDips = dipRow("PROG_DATA", 8, (v) => { prog.data = v; });
  const writeKey = keycap("PROG_WRITE", () => {
    if (!machine) return;
    if (!prog.mode) {
      state("flip PROG_ADDR to PROG first - the write goes through U32");
      return;
    }
    machine.ram[prog.addr] = prog.data;  // the write pulse, as wired
    render();
  });
  out.writeKey = writeKey;
  const hint = document.createElement("p");
  hint.className = "hint";
  hint.textContent = "PROG mode: set PROG_ADDR_A + PROG_DATA, press" +
    " PROG_WRITE (a RAM row loads its address and byte into the" +
    " switches). RESET does not clear RAM - load the program again for" +
    " a power cycle.";

  mBus.append(out.bus.el);
  mCtrl.append(out.rom1.el, out.rom2.el, out.t.el, out.q.el);
  mPc.append(out.pc.el);
  mMar.append(out.mar.el);
  mIr.append(out.ir.el);
  mA.append(out.a.el);
  mB.append(out.b.el);
  mAlu.append(out.sum.el, out.flags.el);
  mRam.append(out.ramAddr.el, out.ramData.el, out.ram.el);
  mPanel.append(out.progMode.el, out.progLeds.el,
    prog.addrDips.el, prog.dataDips.el, writeKey, hint);

  // the arrangement echoes the Digital build (and Ben's breadboards):
  // left column top-to-bottom CLOCK, MAR, the front panel (the PROG
  // dipswitches sit by the memory muxes there too), RAM, IR, CONTROL;
  // right column PC (top), A, ALU, B, OUTPUT; the BUS rail runs down
  // the middle between them. Rows are placed explicitly (implicit-row
  // spanning is unreliable), so the pairing is stable. Nothing else
  // is on the panel - the app's own readouts live in the deck above.
  const ROWS = 6;
  const place = (m, col, row) => {
    m.classList.add(col);
    m.style.gridRow = String(row);
    panel.append(m);
  };
  mBus.style.gridRow = "1 / span " + ROWS;
  panel.append(mBus);  // the rail first: middle column, full height
  place(mClock, "l", 1);  place(mPc, "r", 1);
  place(mMar, "l", 2);   place(mA, "r", 2);
  place(mPanel, "l", 3); place(mAlu, "r", 3);
  place(mRam, "l", 4);   place(mB, "r", 4);
  place(mIr, "l", 5);    place(mOut, "r", 5);
  place(mCtrl, "l", 6);
}

function kvRow(label) {
  const row = document.createElement("div");
  row.className = "bank";
  const name = document.createElement("span");
  name.className = "note";
  name.textContent = label;
  const read = document.createElement("span");
  read.className = "read wide";
  row.append(name, read);
  return { el: row, set: (t) => { read.textContent = t; } };
}

/** one RAM byte as a mnemonic (the monitor's OP column) */
function decodeByte(b) {
  const name = opcodeName(b >> 4);
  const [op, kind] = MNEMONICS[name] || [null, null];
  if (op === null) return ".DB";
  return kind === "none" ? name : name + " " + (b & 0xf);
}

// ---------------------------------------------------------------- deck

// the deck is this app's control room: none of it is on the machine
// (the machine's own controls are on the CLOCK and FRONT PANEL
// modules). The keys that touch the machine respect its gating: RUN
// only runs the master clock while STEP_MODE is AUTO.
const runKey = keycap("RUN", () => {
  if (!machine || machine.halted) return;
  if (clock.stepMode) {
    state("the master clock is disconnected while STEP_MODE is MANUAL (U4.1) - flip it to AUTO");
    return;
  }
  clock.auto = !clock.auto;
  clock.acc = 0;
  runKey.textContent = clock.auto ? "PAUSE" : "RUN";
}, "hot");

let hzSlider, hzRead;  // created here, mounted on the CLOCK module

function buildDeck() {
  const deck = $("deck");
  const select = document.createElement("select");
  for (const p of PROGRAMS) {
    const opt = document.createElement("option");
    opt.value = p;
    opt.textContent = p;
    select.append(opt);
  }
  select.addEventListener("change", () =>
    loadProgram(select.value).catch(showError));

  // the U1 rate control (built here, placed on the clock module by
  // buildPanel - it is on the machine, the 555's pot)
  hzSlider = document.createElement("input");
  hzSlider.type = "range";
  hzSlider.min = 0;
  hzSlider.max = 100;
  hzSlider.value = 18;  // ~4 Hz
  hzRead = document.createElement("span");
  hzRead.className = "read";
  hzRead.textContent = hzText(clock.hz);
  hzSlider.addEventListener("input", () => {
    // 0..100 -> 1..2048 Hz, logarithmic
    clock.hz = Math.pow(2, (hzSlider.value / 100) * 11);
    hzRead.textContent = hzText(clock.hz);
  });

  const traceTg = toggleSwitch("OFF", "TRACE", (on) => {
    traceOn = on;
  });

  const fileKey = document.createElement("label");
  fileKey.className = "key";
  fileKey.textContent = "IMAGE FILE";
  const fileInput = document.createElement("input");
  fileInput.type = "file";
  fileInput.accept = ".hl,.asm,.bin,.hex,.lst";
  fileInput.addEventListener("change", () => {
    const f = fileInput.files[0];
    if (f) loadFile(f);
    fileInput.value = "";
  });
  fileKey.append(fileInput);

  // the app's status readouts (what the MONITOR module used to be -
  // taken off the panel, where nothing but the machine belongs)
  out.monProgram = kvRow("program");
  out.monCycles = kvRow("cycles");
  out.monInsns = kvRow("instructions");

  const webtag = span("webtag", "THIS APP - NOT ON THE MACHINE");
  const spacer = span("spacer", "");
  deck.append(webtag, span("note", "PROGRAM"), select,
    keycap("LOAD", () => loadProgram(select.value).catch(showError)),
    runKey,
    keycap("TURBO", turbo),
    traceTg.el,
    fileKey,
    spacer,
    out.monProgram.el, out.monCycles.el, out.monInsns.el,
    span("state", "", "state"));
  out.stateEl = deck.lastChild;
}

function hzText(hz) {
  return (hz >= 10 ? Math.round(hz) : hz.toFixed(1)) + " Hz";
}

function span(cls, text, id) {
  const s = document.createElement("span");
  s.className = cls;
  if (id) s.id = id;
  s.textContent = text;
  return s;
}

// ---------------------------------------------------------------- actions

/** the control word for the cycle about to execute (docs/microcode.md,
 *  "Timing") - the word the panel LEDs show, steady between edges */
function peekWord() {
  const opcode = machine.ir >> 4;
  const addr = machine.step | (opcode << 3) | (machine.cf << 8) | (machine.zf << 9);
  return [machine.rom1[addr], machine.rom2[addr]];
}

function doCycle(trace) {
  const [w1, w2] = peekWord();
  const pre = {
    a: machine.a, b: machine.b, pc: machine.pc,
    out: machine.out, cf: machine.cf, zf: machine.zf,
  };
  const names = controlNames(w1, w2);
  const driver = ["CO", "RO", "IO", "AO", "EO"].find((n) => names.includes(n)) || null;
  const cycle = machine.cycles;
  const stepNo = machine.step;
  const bus = machine.cycle();
  lastCycle = { bus, driver };
  clock.phase = !clock.phase;
  if (trace) {
    traceLines.push(
      "cycle " + String(cycle).padEnd(6) +
      "T" + stepNo + " " + names.join(",").padEnd(10) +
      "bus=" + hex2(bus) +
      " a=" + hex2(pre.a) + " b=" + hex2(pre.b) +
      " pc=" + pre.pc.toString(16) + " out=" + hex2(pre.out) +
      " cf=" + pre.cf + " zf=" + pre.zf);
    while (traceLines.length > TRACE_MAX) traceLines.shift();
    traceDirty = true;
  }
}

/** STEP_PULSE, as gated on the machine (U5.1): one clock edge per
 *  click, but only while STEP_MODE is MANUAL - in AUTO the button is
 *  disconnected. */
function step() {
  if (!machine || machine.halted) return;
  if (!clock.stepMode) {
    state("STEP_PULSE is disconnected while STEP_MODE is AUTO (U5.1) - flip STEP_MODE to MANUAL on the clock module");
    return;
  }
  doCycle(true);
  render();
}

function turbo() {
  if (!machine || machine.halted) return;
  const before = machine.cycles;
  machine.run(MAX_CYCLES);
  lastCycle = null;
  traceLines.push("(turbo: " + (machine.cycles - before) + " cycles)");
  while (traceLines.length > TRACE_MAX) traceLines.shift();
  traceDirty = true;
  clock.auto = false;
  runKey.textContent = "RUN";
  render();
}

function reset() {
  if (!machine) return;
  // the RESET switch, as wired: clears PC/step/OUT/A/B/IR/MAR/flags but
  // NOT RAM - a reset+rerun runs over whatever the last run left in
  // memory, exactly like the hardware. To start from the program image
  // again (a power cycle), use the load button.
  machine.reset();
  traceLines = [];
  traceDirty = true;
  render();
}

// ---------------------------------------------------------------- your program

const editor = {};  // built in buildYourProgram

function buildYourProgram() {
  const box = $("your");
  const area = document.createElement("textarea");
  area.spellcheck = false;
  area.value = EXAMPLE;
  const modeSel = document.createElement("select");
  for (const [v, t] of [["auto", "auto-detect"], ["hl", ".hl source"],
    ["asm", ".asm source"], ["image", "image (hex / logisim text)"]]) {
    const opt = document.createElement("option");
    opt.value = v;
    opt.textContent = t;
    modeSel.append(opt);
  }
  const status = span("note", "");
  const asmPre = document.createElement("pre");
  asmPre.className = "genasm";

  const go = () => {
    status.textContent = "";
    asmPre.textContent = "";
    const text = area.value;
    try {
      const kind = modeSel.value === "auto" ? detect(text) : modeSel.value;
      if (kind === "image") {
        const ram = parseImage(new TextEncoder().encode(text), MEM_SIZE);
        programName = "(pasted image)";
        listing.set(null);
        startMachine(ram);
      } else if (kind === "hl") {
        const r = compileHl(text);
        programName = "(your .hl)";
        listing.set(r.listing);
        asmPre.textContent = r.asmText;
        startMachine(r.mem);
      } else {
        const r = assembleAsm(text, "(your .asm)");
        programName = "(your .asm)";
        listing.set(r.listing);
        startMachine(r.mem);
      }
      state("loaded - STEP or RUN");
    } catch (e) {
      status.textContent = errorText(e);
      status.classList.add("err");
    }
  };

  box.append(area, modeSel, keycap("COMPILE + LOAD", go), status, asmPre);
  editor.area = area;
  editor.load = go;
}

/** shape detection: .hl keywords/assignments vs mnemonics/labels */
function detect(text) {
  let hl = 0, asm = 0;
  for (const line of text.split("\n")) {
    if (/^\s*(var|const|while|if|elif|else|out|halt|pass|break|continue|and|or|not|rol)\b/.test(line)) hl++;
    else if (/^\s*[A-Za-z_]\w*\s*=(?!=)/.test(line)) hl++;
    if (/^\s*([A-Za-z_]\w*:)?\s*(NOP|LDA|ADD|SUB|STA|LDI|JMP|JC|JZ|JNC|JNZ|ADDI|SUBI|DBL|OUT|HLT|\.DB|\.ORG|\.EQU)\b/i.test(line)) asm++;
  }
  if (hl === 0 && asm === 0) return "image";
  return hl >= asm ? "hl" : "asm";
}

function errorText(e) {
  if (e instanceof HLError) return "line " + e.lineno + ": " + e.msg;
  if (e instanceof AsmError) return e.errors.join("  ");
  return String(e);
}

async function loadFile(f) {
  const ext = f.name.split(".").pop().toLowerCase();
  const text = await f.text();
  if (ext === "hl" || ext === "asm") {
    editor.area.value = text;
    editor.load();
    return;
  }
  if (ext === "lst") {  // the entry table: show it, load nothing
    listing.set(text);
    return;
  }
  // .bin / .hex: a machine image
  try {
    const ram = parseImage(await f.arrayBuffer(), MEM_SIZE);
    programName = "(" + f.name + ")";
    listing.set(null);
    startMachine(ram);
  } catch (e) {
    showError(e);
  }
}

const EXAMPLE = "; your program - .hl, .asm, or a pasted image.\n" +
  "; docs/language.md is in the docs pane; COMPILE + LOAD builds it\n" +
  "; with the same tools as the repo (byte-identical, tested).\n" +
  "var n = 3\n" +
  "while 1:\n" +
  "    out n\n" +
  "    n = n * 3\n" +
  "halt\n";

// ---------------------------------------------------------------- render

let outCount = -1;

function hex2(v) { return v.toString(16).padStart(2, "0"); }

function state(text) {
  if (out.stateEl) out.stateEl.textContent = text;
}

function render() {
  const m = machine;
  if (!m) {
    state("no program loaded");
    return;
  }
  const [w1, w2] = peekWord();

  // data registers and the bus
  out.bus.set(lastCycle ? lastCycle.bus : 0);
  if (out.bus.note) out.bus.note.textContent = lastCycle ? (lastCycle.driver || "-") : "-";
  out.pc.set(m.pc);
  out.mar.set(m.mar);
  out.ir.set(m.ir);
  if (out.ir.note) {
    out.ir.note.textContent = opcodeName(m.ir >> 4) + " " + (m.ir & 0xf);
  }
  out.a.set(m.a);
  out.b.set(m.b);
  const [sum] = m.alu(w2 & ROM2_BITS.SU);  // the adder's live output
  out.sum.set(sum);
  out.reg.set(m.out);
  out.flags.set((m.cf << 1) | m.zf);

  // control: the word for the cycle about to run, then the counter
  out.rom1.set(w1);
  out.rom2.set(w2);
  out.t.set(1 << m.step);
  out.q.set(m.step);

  // RAM: the 74157 muxes put the panel switches on in program mode
  const eff = prog.mode ? prog.addr : m.mar;
  out.ramAddr.set(eff);
  out.ramData.set(m.ram[eff]);
  out.ram.update(m.ram, m.pc, eff);

  // clock + panel lamps
  out.clk.set(clock.phase ? 1 : 0);
  out.halt.set(m.halted ? 1 : 0);
  out.progLeds.set(prog.mode ? 1 : 2);  // PROG lights in program mode, PROG_hat in run

  // the display (all four digits: the persistence-of-vision view)
  if (out.display) out.display.draw(m.out, decHex);

  // the panes
  listing.mark(m.pc);
  if (m.outputs.length !== outCount) {
    outCount = m.outputs.length;
    const shown = m.outputs.slice(-OUT_MAX);
    $("outlog").textContent =
      (m.outputs.length > OUT_MAX ? "(last " + OUT_MAX + " of " : "(") +
      m.outputs.length + " OUTs)\n" +
      shown.map((v) => String(v).padStart(3) + "  (0x" + hex2(v) + ")").join("\n");
  }
  if (traceDirty) {
    traceDirty = false;
    $("trace").textContent = traceLines.join("\n") +
      (traceLines.length ? "\n" : "");
  }

  // the app's status readouts (the deck) + the state line
  out.monProgram.set(programName || "-");
  out.monCycles.set(String(m.cycles));
  out.monInsns.set(String(m.instructions));
  state(smokeStatus ||
    (m.halted ? "HALTED after " + m.cycles + " cycles - RESET to run again"
    : prog.mode ? "PROGRAM mode - the RAM is on the panel switches"
    : clock.auto ? "running at " + hzText(clock.hz)
    : clock.stepMode ? "MANUAL - STEP_PULSE (or space) is one clock edge"
    : "AUTO - RUN starts the master clock, or flip STEP_MODE to MANUAL"));
}

// ---------------------------------------------------------------- the loop

function frame(t) {
  if (machine && clock.auto && !machine.halted) {
    if (clock.lastT) clock.acc += ((t - clock.lastT) / 1000) * clock.hz;
    const whole = Math.floor(clock.acc);
    clock.acc -= whole;  // a background tab's backlog is dropped
    const n = Math.min(whole, 20000);
    for (let i = 0; i < n && !machine.halted; i++) doCycle(traceOn);
    if (machine.halted) {
      clock.auto = false;
      runKey.textContent = "RUN";
    }
  }
  clock.lastT = t;
  // the display mux counter (U37) free-runs at MUX_CLK speed
  muxCnt += ((t - (frame.lastT || t)) / 1000) * MUX_HZ;
  frame.lastT = t;
  if (out.mux) out.mux.set(muxCnt & 3);
  render();
  requestAnimationFrame(frame);
}

// ---------------------------------------------------------------- self-test

/** ?smoke=1: the served app checks itself - the machine runs the count
 *  program to the right OUT sequence, the panel write path changes RAM,
 *  the in-browser toolchain builds a program, the docs renderer renders.
 *  Results land in the trace pane and the deck state line, so a headless
 *  run (or a user) can see them. */
async function runSmoke() {
  let failed = 0;
  const check = (name, ok) => {
    traceLines.push((ok ? "PASS " : "FAIL ") + name);
    if (!ok) failed++;
  };
  await loadProgram("count");  // the program the checks below assume
  // single-stepping first (reset clears the trace): STEP_MODE must be
  // MANUAL - in AUTO the STEP_PULSE button is disconnected (U5.1)
  out.stepMode.set(true);  // fires the switch's onChange
  reset();
  step();
  step();
  check("step trace + T counter",
    traceLines.length === 2 && machine.step === 2);
  // the gating itself: back in AUTO, STEP_PULSE does nothing
  const gatedAt = traceLines.length;  // (each check adds a line itself)
  out.stepMode.set(false);
  step();
  check("STEP_MODE gates STEP_PULSE",
    traceLines.length === gatedAt && machine.step === 2);
  out.stepMode.set(true);
  // the machine: count runs to the cap and counts 0,1,2,... (checked
  // before the panel write, which deliberately corrupts a data cell)
  turbo();
  const okCount = machine.outputs.length > 100 &&
    machine.outputs.slice(0, 16).every((v, i) => v === i);
  // the panel write path: PROGRAM mode, dips, the WRITE key
  prog.mode = true;
  out.progMode.set(true);
  prog.addrDips.set(5);
  prog.dataDips.set(0xab);
  out.writeKey.click();
  check("panel write -> RAM[5]", machine.ram[5] === 0xab);
  prog.mode = false;
  out.progMode.set(false);
  check("count OUT sequence 0..15", okCount);
  // the toolchain: the example compiles and assembles
  try {
    const r = compileHl(EXAMPLE);
    check("compileHl builds the example", r.mem.length === MEM_SIZE);
  } catch (e) {
    check("compileHl builds the example (" + e + ")", false);
  }
  // the display and the docs renderer
  out.display.draw(255, true);
  out.display.draw(0xaf, false);
  check("display draws", true);
  const html = renderMarkdown("# t\n\n| a | b |\n|---|---|\n| 1 | `x` |\n");
  check("markdown table + code", html.includes("<table>") && html.includes("<code>x</code>"));
  traceDirty = true;
  smokeStatus = "SMOKE: " + (failed ? failed + " FAILURES (see the trace pane)"
    : "all checks passed");
  state(smokeStatus);
  render();
}

// ---------------------------------------------------------------- wiring

function showError(e) {
  state("error: " + e);
}

async function init() {
  buildDeck();
  buildPanel();
  buildYourProgram();
  listing = listingPane();
  $("listing").append(listing.el);
  makeDocsViewer($("docs"), "../docs/");
  listing.set(null);

  try {
    await loadRoms();
  } catch (e) {
    state("could not load the ROM images: " + e +
      " - serve the repo root with an HTTP server (see web/README.md)");
    return;
  }
  out.display = makeDisplay($("display-canvas"), displayRom);

  document.addEventListener("keydown", (ev) => {
    if (ev.key !== " ") return;
    if (!(ev.target instanceof Element)) return;
    if (ev.target.closest("input, select, textarea, button, label")) return;
    ev.preventDefault();
    step();
  });

  await loadProgram(PROGRAMS[0]).catch(showError);  // absdiff (the picker's default)
  if (new URLSearchParams(location.search).get("smoke")) {
    await runSmoke();
  }
  requestAnimationFrame(frame);
}

let listing = null;   // the listing pane (listingPane())
let traceDirty = false;
let smokeStatus = null;  // the sticky self-test banner (?smoke=1)

init();
