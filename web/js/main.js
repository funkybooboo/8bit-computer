// main.js - the UI: load a program, run / step / reset, display the
// machine state, the OUT stream and a cycle trace.

import { parseImage } from "./hex.js";
import {
  Machine, MEM_SIZE, controlNames, opcodeName, ROM1_BITS, ROM2_BITS,
} from "./machine.js";

// the programs this build serves: programs/<name>.hex images, built from
// the .asm sources by web/build.py (they are gitignored build artifacts -
// run it on a fresh clone before serving)
const PROGRAMS = [
  "absdiff", "bits", "bothflags", "count", "countdown", "decrement",
  "div", "fib", "gcd", "half", "larger", "lcg", "memory", "min",
  "mod", "mul", "odometer", "overflow", "patch", "powers", "rol",
  "rotate", "squares", "step", "triple",
];

const MAX_CYCLES = 100000;

const $ = (id) => document.getElementById(id);

let machine = null;   // the Machine, when a program is loaded
let programName = null;
let rom1 = null, rom2 = null;
let loadedRam = null; // the program image, for reset

// ---------------------------------------------------------------- loading

async function fetchImage(url, size) {
  const r = await fetch(url);
  if (!r.ok) throw new Error("fetch " + url + ": " + r.status);
  return parseImage(await r.arrayBuffer(), size);
}

async function loadRomImages() {
  [rom1, rom2] = await Promise.all([
    fetchImage("../roms/control-rom1.hex", 2048),
    fetchImage("../roms/control-rom2.hex", 2048),
  ]);
}

async function loadProgram(name) {
  const ram = await fetchImage("../programs/" + name + ".hex", MEM_SIZE);
  programName = name;
  startMachine(ram);
}

function startMachine(ram) {
  loadedRam = ram;
  machine = new Machine(rom1, rom2, ram);
  $("trace").textContent = "";
  render();
}

// ---------------------------------------------------------------- display

function hex2(v) { return v.toString(16).padStart(2, "0"); }

function render(cycleInfo) {
  const m = machine;
  if (!m) {
    $("state").textContent = "no program loaded";
    $("outs").textContent = "";
    return;
  }
  $("name").textContent = programName ? ("program: " + programName) : "program: (custom image)";
  $("a").textContent = hex2(m.a);
  $("b").textContent = hex2(m.b);
  $("ir").textContent = hex2(m.ir) + " (" + opcodeName(m.ir >> 4) + " " + (m.ir & 0xf) + ")";
  $("pc").textContent = m.pc.toString(16);
  $("mar").textContent = m.mar.toString(16);
  $("out").textContent = hex2(m.out);
  $("cf").textContent = m.cf;
  $("zf").textContent = m.zf;
  $("step").textContent = "T" + m.step;
  $("cycles").textContent = m.cycles;
  $("instructions").textContent = m.instructions;
  $("halted").textContent = m.halted ? "halted" : "running";

  $("outs").textContent = m.outputs
    .map((v) => String(v).padStart(3) + "  (0x" + hex2(v) + ")")
    .join("\n");

  if (cycleInfo) {
    const el = $("trace");
    el.textContent +=
      "cycle " + String(cycleInfo.cycle).padEnd(6) +
      " T" + cycleInfo.step + " " + cycleInfo.names.join(",").padEnd(10) +
      " bus=" + hex2(cycleInfo.bus) +
      " a=" + hex2(cycleInfo.pre.a) + " b=" + hex2(cycleInfo.pre.b) +
      " pc=" + cycleInfo.pre.pc.toString(16) + " out=" + hex2(cycleInfo.pre.out) +
      " cf=" + cycleInfo.pre.cf + " zf=" + cycleInfo.pre.zf + "\n";
  }
}

// the control word for the cycle about to execute (docs/microcode.md, "Timing")
function peekWord() {
  const opcode = machine.ir >> 4;
  const addr = machine.step | (opcode << 3) | (machine.cf << 8) | (machine.zf << 9);
  return [machine.rom1[addr], machine.rom2[addr]];
}

// ---------------------------------------------------------------- actions

function step() {
  if (!machine || machine.halted) return;
  const [w1, w2] = peekWord();
  const pre = {
    a: machine.a, b: machine.b, pc: machine.pc,
    out: machine.out, cf: machine.cf, zf: machine.zf,
  };
  const cycle = machine.cycles;
  const stepNo = machine.step;
  const bus = machine.cycle();
  render({ cycle, step: stepNo, names: controlNames(w1, w2), bus, pre });
}

function run() {
  if (!machine) return;
  if (machine.halted) return;
  machine.run(MAX_CYCLES);
  $("trace").textContent += "(run: " + machine.cycles + " cycles)\n";
  render();
}

function reset() {
  if (!machine) return;
  // the RESET switch, as wired: clears PC/step/OUT/A/B/IR/MAR/flags but
  // NOT RAM - a reset+rerun runs over whatever the last run left in
  // memory, exactly like the hardware. To start from the program image
  // again (a power cycle), use the load button.
  machine.reset();
  $("trace").textContent = "";
  render();
}

// ---------------------------------------------------------------- wiring

async function init() {
  const select = $("program");
  for (const p of PROGRAMS) {
    const opt = document.createElement("option");
    opt.value = p;
    opt.textContent = p;
    select.appendChild(opt);
  }
  try {
    await loadRomImages();
  } catch (e) {
    $("state").textContent = "could not load the ROM images: " + e +
      " - serve the repo root with an HTTP server (see web/README.md)";
    return;
  }
  select.addEventListener("change", () => loadProgram(select.value).catch(showError));
  $("load").addEventListener("click", () =>
    loadProgram(select.value).catch(showError));
  $("run").addEventListener("click", run);
  $("step").addEventListener("click", step);
  $("reset").addEventListener("click", reset);
  $("file").addEventListener("change", async () => {
    const f = $("file").files[0];
    if (!f) return;
    const ram = parseImage(await f.arrayBuffer(), MEM_SIZE);
    programName = null;
    startMachine(ram);
  });

  await loadProgram(select.value).catch(showError);
}

function showError(e) {
  $("state").textContent = "error: " + e;
}

init();
