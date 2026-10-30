// run_tools.mjs - the JS toolchain runner for test_tools.py: compile and
// assemble every .hl source in a directory with the browser ports
// (js/hlc.js + js/asm.js) and write <name>.asm and <name>.bin into the
// output directory, for byte-for-byte comparison against the Python
// toolchain (tools/compile.py + tools/asm.py).
//
//   node web/test/run_tools.mjs <source-dir> <output-dir>

import { readdirSync, readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { compileToAsm } from "../js/hlc.js";
import { assembleText } from "../js/asm.js";

const [srcDir, outDir] = process.argv.slice(2);
if (!srcDir || !outDir) {
  console.error("usage: node run_tools.mjs <source-dir> <output-dir>");
  process.exit(2);
}

let failures = 0;
for (const f of readdirSync(srcDir).filter((f) => f.endsWith(".hl")).sort()) {
  const name = f.slice(0, -3);
  const text = readFileSync(join(srcDir, f), "utf-8");
  try {
    const asmText = compileToAsm(text, 16);
    const { mem } = assembleText(asmText, 16, "(generated)");
    writeFileSync(join(outDir, name + ".asm"), asmText);
    writeFileSync(join(outDir, name + ".bin"), Buffer.from(mem));
  } catch (e) {
    failures++;
    console.error(name + ": FAIL - " + (e.lineno !== undefined
      ? "line " + e.lineno + ": " + e.msg : String(e)));
  }
}
if (failures) process.exit(1);
