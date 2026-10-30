// asm.js - the assembler, the JS twin of tools/asm.py.
//
// A whole, faithful port (not a re-implementation): same two passes,
// same rules, same errors, same listing bytes - so anything assembled
// in the browser is identical to what tools/asm.py produces. Parity is
// enforced by web/test/test_tools.py, which compiles and assembles
// every program in the gallery with both toolchains and compares the
// .asm text and the .bin image byte for byte.
//
// Machine model and language reference: docs/instruction-set.md and
// docs/assembly-language.md. Opcode numbers come from js/machine.js
// (the same table genroms.py defines - one source of truth).

import { OPCODES } from "./machine.js";

const OPERAND_NONE = "none", OPERAND_ADDR = "addr", OPERAND_IMM = "imm";

const LANGUAGE = {  // mnemonic -> [operand kind, effect] (docs)
  NOP: [OPERAND_NONE, "no operation"],
  LDA: [OPERAND_ADDR, "A <- M[operand]"],
  ADD: [OPERAND_ADDR, "A <- A + M[operand]; CF/ZF updated"],
  SUB: [OPERAND_ADDR, "A <- A - M[operand]; CF/ZF updated"],
  STA: [OPERAND_ADDR, "M[operand] <- A"],
  LDI: [OPERAND_IMM, "A <- operand (0-15, zero-extended)"],
  JMP: [OPERAND_ADDR, "PC <- operand"],
  JC: [OPERAND_ADDR, "PC <- operand if CF = 1"],
  JZ: [OPERAND_ADDR, "PC <- operand if ZF = 1"],
  JNC: [OPERAND_ADDR, "PC <- operand if CF = 0"],
  JNZ: [OPERAND_ADDR, "PC <- operand if ZF = 0"],
  ADDI: [OPERAND_IMM, "A <- A + operand; CF/ZF updated"],
  SUBI: [OPERAND_IMM, "A <- A - operand; CF/ZF updated"],
  DBL: [OPERAND_NONE, "A <- 2*A (shift left; CF = bit shifted out)"],
  OUT: [OPERAND_NONE, "display <- A"],
  HLT: [OPERAND_NONE, "stop the clock"],
};
if (Object.keys(LANGUAGE).length !== Object.keys(OPCODES).length ||
    !Object.keys(LANGUAGE).every((k) => k in OPCODES)) {
  throw new Error("asm/machine opcode tables disagree");
}
export const MNEMONICS = {};  // name -> [opcode, kind, effect]
for (const [name, [kind, effect]] of Object.entries(LANGUAGE)) {
  MNEMONICS[name] = [OPCODES[name], kind, effect];
}

const ADDR_MAX = 15;  // MAR and PC are 4 bits -> RAM addresses 0-15
const IMM_MAX = 15;   // the operand field is one nibble

const SHADOWS = Object.keys(MNEMONICS).concat(["DB", "ORG", "EQU"]);
const IDENT_RE = /^[A-Za-z_][A-Za-z0-9_]*$/;
const LABEL_DEF_RE = /^([A-Za-z_][A-Za-z0-9_]*)\s*:\s*(.*)$/;

/** An error tied to a source position (asm.py's SourceError). */
export class SourceError extends Error {
  constructor(path, lineno, msg) {
    super(path + ":" + lineno + ": " + msg);
    this.path = path;
    this.lineno = lineno;
    this.msg = msg;
  }
}

/** An assembly failure: .errors is every parse error, or the one
 *  pass error (asm.py collects parse errors, fails passes singly). */
export class AsmError extends Error {
  constructor(errors) {
    super(errors.length === 1 ? errors[0]
      : "asm: " + errors.length + " error(s):\n" + errors.join("\n"));
    this.errors = errors;
  }
}

/** token -> int if it is a numeric literal, else null (asm.py's
 *  parse_number; strict forms, like int() rejecting bad digits). */
export function parseNumber(tok) {
  if (/^0x[0-9a-f]+$/i.test(tok)) return parseInt(tok.slice(2), 16);
  if (/^0b[01]+$/i.test(tok)) return parseInt(tok.slice(2), 2);
  if (/^[0-9]+$/.test(tok)) return parseInt(tok, 10);
  if (tok.length === 3 && tok[0] === "'" && tok[2] === "'") {
    const v = tok.charCodeAt(1);
    return v > 0 && v < 128 ? v : null;
  }
  return null;
}

// ---------------------------------------------------------------- parsing

/** One parsed source statement (label + instruction/directive), or null
 *  for a blank/comment-only line. */
function parseLine(path, lineno, raw) {
  const text = raw.split(";", 1)[0].trim();
  if (!text) return null;
  let label = null, rest = text;
  if (text.includes(":")) {
    const m = LABEL_DEF_RE.exec(text);
    if (!m) {
      throw new SourceError(path, lineno,
        "cannot parse '" + text + "' (label syntax is 'name:')");
    }
    label = m[1];
    rest = m[2].trim();
  }
  if (label !== null && SHADOWS.includes(label.toUpperCase())) {
    throw new SourceError(path, lineno,
      "label '" + label + "' shadows an instruction name; pick another");
  }
  if (!rest) {
    return { lineno, label, kind: "labelonly", payload: null, text, addr: null };
  }
  const sp = rest.search(/\s/);
  const head = (sp < 0 ? rest : rest.slice(0, sp)).toUpperCase();
  const arg = sp < 0 ? "" : rest.slice(sp).trim();
  if (head in MNEMONICS) {
    const [_op, kind] = MNEMONICS[head];
    if (kind === OPERAND_NONE && arg) {
      throw new SourceError(path, lineno, head + " takes no operand");
    }
    if (kind !== OPERAND_NONE && !arg) {
      throw new SourceError(path, lineno,
        head + " requires an operand (0-15)");
    }
    return { lineno, label, kind: "insn", payload: [head, kind, arg], text, addr: null };
  }
  if (head === ".DB") {
    if (!arg) throw new SourceError(path, lineno, ".DB requires at least one value");
    return { lineno, label, kind: "db",
      payload: arg.split(",").map((v) => v.trim()), text, addr: null };
  }
  if (head === ".ORG") {
    if (!arg) throw new SourceError(path, lineno, ".ORG requires an address");
    return { lineno, label, kind: "org", payload: arg, text, addr: null };
  }
  if (head === ".EQU") {
    if (label === null) {
      throw new SourceError(path, lineno,
        ".EQU needs a name: use 'name: .EQU value'");
    }
    if (!arg) throw new SourceError(path, lineno, ".EQU requires a value");
    return { lineno, label, kind: "equ", payload: arg, text, addr: null };
  }
  throw new SourceError(path, lineno,
    "unknown instruction or directive '" + (sp < 0 ? rest : rest.slice(0, sp)) +
    "' (see docs/instruction-set.md)");
}

// ---------------------------------------------------------------- passes

function firstPass(path, stmts, memSize) {
  const labels = {}, equs = {};
  let addr = 0;
  for (const st of stmts) {
    if (st.kind === "equ") {
      const v = parseNumber(st.payload.trim());
      if (v === null) {
        throw new SourceError(path, st.lineno,
          ".EQU needs a numeric or char value (labels are not known yet)");
      }
      if (v < 0 || v > 255) {
        throw new SourceError(path, st.lineno,
          ".EQU value " + v + " is out of range 0-255");
      }
      if (st.label in labels || st.label in equs) {
        throw new SourceError(path, st.lineno, "duplicate name '" + st.label + "'");
      }
      equs[st.label] = v;
      st.addr = addr;
      continue;
    }
    if (st.kind === "org") {
      const v = parseNumber(st.payload.trim());
      if (v === null) {
        throw new SourceError(path, st.lineno,
          ".ORG needs a numeric address (labels are not known yet)");
      }
      if (v < addr) {
        throw new SourceError(path, st.lineno,
          ".ORG moves backwards (from " + addr + " to " + v + ")");
      }
      if (v > memSize) {
        throw new SourceError(path, st.lineno,
          ".ORG address " + v + " is beyond the " + memSize + " bytes of RAM");
      }
      addr = v;
    }
    if (st.label !== null) {
      if (st.label in labels) {
        throw new SourceError(path, st.lineno,
          "duplicate label '" + st.label + "' (first defined for address " +
          labels[st.label] + ")");
      }
      if (st.label in equs) {
        throw new SourceError(path, st.lineno,
          "name '" + st.label + "' is already a .EQU constant");
      }
      labels[st.label] = addr;
    }
    const size = st.kind === "insn" ? 1 : (st.kind === "db" ? st.payload.length : 0);
    if (addr + size > memSize) {
      throw new SourceError(path, st.lineno,
        "program does not fit in " + memSize + " bytes of RAM (statement would" +
        " end at " + (addr + size) + ")");
    }
    st.addr = addr;
    addr += size;
  }
  return { labels, equs };
}

function resolve(tok, labels, equs, path, lineno) {
  tok = tok.trim();
  if (!tok) throw new SourceError(path, lineno, "missing operand");
  const v = parseNumber(tok);
  if (v !== null) return v;
  if (IDENT_RE.test(tok)) {
    if (tok in equs) return equs[tok];
    if (tok in labels) return labels[tok];
    throw new SourceError(path, lineno,
      "undefined name '" + tok + "' (label or .EQU constant)");
  }
  throw new SourceError(path, lineno,
    "cannot parse operand '" + tok + "' (decimal, 0xNN, 0bNNNN, 'c' or a name)");
}

function secondPass(path, stmts, labels, equs, memSize) {
  const mem = new Uint8Array(memSize);
  const rows = [];  // [addr, byte-or-null, text]
  for (const st of stmts) {
    if (st.kind === "insn") {
      const [head, kind, arg] = st.payload;
      const [opcode] = MNEMONICS[head];
      if (kind === OPERAND_NONE) {
        mem[st.addr] = opcode << 4;
        rows.push([st.addr, mem[st.addr], st.text]);
        continue;
      }
      const val = resolve(arg, labels, equs, path, st.lineno);
      const limit = kind === OPERAND_ADDR ? ADDR_MAX : IMM_MAX;
      if (val > limit) {
        throw new SourceError(path, st.lineno,
          (kind === OPERAND_ADDR ? "RAM address" : "immediate") +
          " operand " + val + " is out of range 0-" + limit +
          " (the operand field is one nibble; build larger constants with ADD)");
      }
      mem[st.addr] = (opcode << 4) | val;
      rows.push([st.addr, mem[st.addr], st.text]);
    } else if (st.kind === "db") {
      for (let i = 0; i < st.payload.length; i++) {
        const v = resolve(st.payload[i], labels, equs, path, st.lineno);
        if (v < 0 || v > 255) {
          throw new SourceError(path, st.lineno,
            ".DB value " + v + " is out of range 0-255");
        }
        mem[st.addr + i] = v;
        rows.push([st.addr + i, v, i === 0 ? st.text : ""]);
      }
    } else {  // "org" / "labelonly" / "equ": no byte emitted
      rows.push([st.addr, null, st.text]);
    }
  }
  return { mem, rows };
}

// ---------------------------------------------------------------- public

/** Assemble source text -> { mem, rows, used } or throw AsmError with
 *  every parse error (asm.py's assemble, over a string instead of a
 *  file; `path` names the source in error messages). */
export function assembleText(text, memSize, path) {
  const stmts = [], errors = [];
  // python's splitlines(): no phantom element after the final newline
  const lines = text.replace(/\r\n/g, "\n").split("\n");
  if (lines.length && lines[lines.length - 1] === "") lines.pop();
  for (let lineno = 1; lineno <= lines.length; lineno++) {
    try {
      const st = parseLine(path, lineno, lines[lineno - 1]);
      if (st !== null) stmts.push(st);
    } catch (e) {
      if (e instanceof SourceError) errors.push(String(e));
      else throw e;
    }
  }
  if (errors.length) throw new AsmError(errors);
  try {
    const { labels, equs } = firstPass(path, stmts, memSize);
    return { ...secondPass(path, stmts, labels, equs, memSize) };
  } catch (e) {
    if (e instanceof SourceError) throw new AsmError([String(e)]);
    throw e;
  }
}

/** '0 0 0 0    0 1 0 1    0 0 0 0' = address | opcode | operand - the
 *  three dipswitch groups (asm.py's bits_field). */
export function bitsField(addr, b, addrWidth) {
  const group = (val, width) => {
    let s = "";
    for (let i = width - 1; i >= 0; i--) s += (i < width - 1 ? " " : "") + ((val >> i) & 1);
    return s;
  };
  return group(addr, addrWidth) + "    " + group(b >> 4, 4) + "    " + group(b & 0xf, 4);
}

/** The listing: the front-panel entry table (asm.py's format_listing,
 *  byte for byte). */
export function formatListing(rows, used, memSize) {
  let addrWidth = 4;
  while ((1 << addrWidth) < memSize) addrWidth += 4;
  const gw = 2 * addrWidth - 1;
  const pad = (s) => s.padEnd(gw);
  const out = [
    "ADDR  BYTE  " + pad("ADDRESS") + "    " + pad("OPCODE") + "    " + pad("PARAM") + "  SOURCE",
    "----  ----  " + pad("----") + "    " + pad("----") + "    " + pad("----") + "  --------",
  ];
  for (const [addr, b, text] of rows) {
    const a = addr !== null ? addr.toString(16).padStart(2, "0") : "--";
    const v = b !== null ? b.toString(16).padStart(2, "0") : "--";
    const bits = b !== null && addr !== null ? bitsField(addr, b, addrWidth) : "";
    out.push((a.padEnd(4) + "  " + v.padEnd(4) + "  " + bits + "  " + text).trimEnd());
  }
  out.push("");
  out.push("; bits column: address | opcode | operand (the dipswitch groups for program entry)");
  out.push("; " + used + " of " + memSize + " RAM bytes used; unused bytes read as 0x00 (NOP)");
  return out.join("\n") + "\n";
}

/** Convenience: source text -> { mem, listing } in one call. */
export function assemble(text, path) {
  const { mem, rows } = assembleText(text, 16, path || "(source)");
  const used = rows.reduce((n, [_a, b]) => n + (b !== null ? 1 : 0), 0);
  return { mem, listing: formatListing(rows, used, 16) };
}
