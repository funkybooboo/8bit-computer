#!/usr/bin/env node
// run.mjs - headless entry point, used only by web/test/verify.py.
//
//   node web/js/run.mjs <program-image> [--rom1 FILE] [--rom2 FILE]
//                       [--max-cycles N]
//
// Runs the program on js/machine.js (the same cycle model as the browser
// app) and prints one line per OUT on stdout, the summary on stderr, exit
// 0 iff the program halted - the contract web/test/verify.py compares
// against the frozen expected outputs in programs/*.out.

import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

import { parseImage } from "./hex.js";
import { Machine } from "./machine.js";

const here = dirname(fileURLToPath(import.meta.url));
const root = join(here, "..", "..");

const args = process.argv.slice(2);
let program = null;
let rom1Path = join(root, "roms", "control-rom1.hex");
let rom2Path = join(root, "roms", "control-rom2.hex");
let maxCycles = 100000;
for (let i = 0; i < args.length; i++) {
  if (args[i] === "--rom1") rom1Path = args[++i];
  else if (args[i] === "--rom2") rom2Path = args[++i];
  else if (args[i] === "--max-cycles") maxCycles = parseInt(args[++i], 10);
  else if (args[i].startsWith("--")) usage("unknown option " + args[i]);
  else if (program === null) program = args[i];
  else usage("give exactly one program image");
}
if (program === null) usage("no program image given");

function usage(msg) {
  if (msg) console.error("run.mjs: " + msg);
  console.error(
    "usage: node web/js/run.mjs <program-image> " +
    "[--rom1 FILE] [--rom2 FILE] [--max-cycles N]"
  );
  process.exit(2);
}

const rom1 = parseImage(readFileSync(rom1Path), 2048);
const rom2 = parseImage(readFileSync(rom2Path), 2048);
const ram = parseImage(readFileSync(program), 16);

const m = new Machine(rom1, rom2, ram);
m.run(maxCycles);
for (const v of m.outputs) {
  console.log(String(v).padStart(3) + "  (0x" + v.toString(16).padStart(2, "0") + ")");
}
const status = m.halted ? "halted" : "did NOT halt (hit --max-cycles)";
console.error(
  "web: " + status + " | " + m.cycles + " cycles, " + m.instructions +
  " instructions (" + (m.cycles / Math.max(1, m.instructions)).toFixed(1) +
  " cycles/insn), " + m.outputs.length + " OUTs"
);
process.exit(m.halted ? 0 : 1);
