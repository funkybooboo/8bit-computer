// hlc.js - the .hl compiler, the JS twin of tools/compile.py.
//
// A whole, faithful port: same lexer, parser and code generator, the
// same accumulator/flags tracking and the same emitted idioms - so a
// .hl program compiled in the browser produces byte-identical .asm
// and .bin to the Python toolchain. Parity is enforced by
// web/test/test_tools.py over every program in the gallery.
//
// The language and its honesty about the machine: docs/language.md.
// The build chain this port mirrors: docs/tools.md, "The build chain".

import { assembleText, formatListing } from "./asm.js";

export class HLError extends Error {
  constructor(lineno, msg) {
    super(lineno + ": " + msg);
    this.lineno = lineno;
    this.msg = msg;
  }
}

// ---------------------------------------------------------------- lexer
// indentation blocks, # and ; comments, ; as a statement separator

const KEYWORDS = new Set(["var", "const", "out", "halt", "pass", "while",
  "if", "elif", "else", "break", "continue", "and", "or", "not"]);
// statements allowed as a single `while c: stmt` body
const INLINE_OK = new Set(["out", "halt", "pass", "break", "continue",
  "if", "var", "const"]);
const NUM_RE = /^(0[xX][0-9a-fA-F]+|0[bB][01]+|\d+)$/;
const NAME_RE = /^[A-Za-z_][A-Za-z0-9_]*$/;
const OPCHARS = "()+-*<>=!:,";

function lex(text) {
  const toks = [], stack = [0];
  // python's splitlines(): no phantom element after the final newline
  const lines = text.replace(/\r\n/g, "\n").split("\n");
  if (lines.length && lines[lines.length - 1] === "") lines.pop();
  const tok = (kind, val, lineno) => toks.push({ kind, val, lineno });
  for (let lineno = 1; lineno <= lines.length; lineno++) {
    const line = lines[lineno - 1].split("#", 1)[0].split(";", 1)[0];
    const stripped = line.trim();
    if (!stripped) {
      tok("NEWLINE", null, lineno);
      continue;
    }
    const indent = line.length - line.replace(/^ +/, "").length;
    if (indent % 4) throw new HLError(lineno, "indentation must be a multiple of 4 spaces");
    while (indent < stack[stack.length - 1]) {
      stack.pop();
      tok("DEDENT", null, lineno);
    }
    if (indent > stack[stack.length - 1]) {
      stack.push(indent);
      tok("INDENT", null, lineno);
    }
    let i = 0, buf = "";
    const emit = () => {
      if (!buf) return;
      if (KEYWORDS.has(buf)) tok("KEY", buf, lineno);
      else if (NUM_RE.test(buf)) tok("NUM", buf, lineno);
      else if (NAME_RE.test(buf)) tok("NAME", buf, lineno);
      else throw new HLError(lineno, "cannot lex '" + buf + "'");
      buf = "";
    };
    while (i < stripped.length) {
      const c = stripped[i];
      if (OPCHARS.includes(c)) {
        emit();
        const two = stripped.slice(i, i + 2);
        if (two === "==" || two === "!=" || two === "<=" || two === ">=") {
          tok("OP", two, lineno);
          i += 2;
          continue;
        }
        tok("OP", c, lineno);
        i += 1;
        continue;
      }
      if (/\s/.test(c)) {
        emit();
        i += 1;
        continue;
      }
      buf += c;
      i += 1;
    }
    emit();
    tok("NEWLINE", null, lineno);
  }
  while (stack[stack.length - 1] !== 0) {
    stack.pop();
    tok("DEDENT", null, lines.length);
  }
  tok("EOF", null, lines.length);
  return toks;
}

function numValue(s) {
  if (/^0x/i.test(s)) return parseInt(s.slice(2), 16);
  if (/^0b/i.test(s)) return parseInt(s.slice(2), 2);
  return parseInt(s, 10);
}

// ---------------------------------------------------------------- parser
// AST nodes are plain objects: { t: "num"|"name"|"bin"|"neg"|"rol"|
// "cmp"|"and"|"or"|"not"|"truthy"|"assign"|"out"|"simple"|"var"|
// "const"|"while"|"if", ..., lineno }

class Parser {
  constructor(toks) {
    this.toks = toks;
    this.i = 0;
  }
  peek(k = 0) {
    return this.toks[Math.min(this.i + k, this.toks.length - 1)];
  }
  next() {
    const t = this.toks[this.i];
    if (t.kind !== "EOF") this.i += 1;
    return t;
  }
  expectOp(op) {
    const t = this.next();
    if (t.kind !== "OP" || t.val !== op) {
      throw new HLError(t.lineno,
        "expected '" + op + "', got '" + (t.val || t.kind) + "'");
    }
  }
  skipNewlines() {
    while (this.peek().kind === "NEWLINE") this.next();
  }
  program() {
    const out = [];
    this.skipNewlines();
    while (this.peek().kind !== "EOF") {
      out.push(...this.statement());
      this.skipNewlines();
    }
    return out;
  }
  block() {
    this.skipNewlines();  // the rest of the ':' line
    const t = this.peek();
    if (t.kind === "KEY" && INLINE_OK.has(t.val)) return this.statement();
    if (t.kind !== "INDENT") {
      throw new HLError(t.lineno, "expected an indented block (or one" +
        " simple statement after the ':')");
    }
    this.next();
    this.skipNewlines();
    const body = [];
    while (this.peek().kind !== "DEDENT" && this.peek().kind !== "EOF") {
      body.push(...this.statement());
      this.skipNewlines();
    }
    if (this.peek().kind === "DEDENT") this.next();
    return body;
  }
  statement() {
    const t = this.peek();
    const ln = t.lineno;
    if (t.kind === "KEY") {
      if (t.val === "var") return [this.vardecl()];
      if (t.val === "const") return [this.constdecl()];
      if (t.val === "out") {
        this.next();
        const e = this.expr();
        this.endStmt();
        return [{ t: "out", e, lineno: ln }];
      }
      if (["halt", "pass", "break", "continue"].includes(t.val)) {
        this.next();
        this.endStmt();
        return [{ t: "simple", which: t.val, lineno: ln }];
      }
      if (t.val === "while") return [this.whilestmt()];
      if (t.val === "if") return [this.ifstmt()];
      throw new HLError(ln, "'" + t.val + "' cannot start a statement");
    }
    if (t.kind === "NAME") {
      const name = this.next().val;
      this.expectOp("=");
      const e = this.expr();
      this.endStmt();
      return [{ t: "assign", name, e, lineno: ln }];
    }
    throw new HLError(ln, "expected a statement, got '" + (t.val || t.kind) + "'");
  }
  endStmt() {
    const t = this.next();
    if (t.kind !== "NEWLINE" && t.kind !== "EOF") {
      throw new HLError(t.lineno,
        "expected end of statement, got '" + (t.val || t.kind) + "'");
    }
  }
  vardecl() {
    this.next();  // 'var'
    const t = this.next();
    const name = this.nameTok(t);
    let e = { t: "num", v: 0, lineno: t.lineno };  // no initializer: 0
    if (this.peek().kind === "OP" && this.peek().val === "=") {
      this.next();
      e = this.expr();
    }
    this.endStmt();
    return { t: "var", name, init: e, lineno: t.lineno };
  }
  constdecl() {
    this.next();  // 'const'
    const t = this.next();
    const name = this.nameTok(t);
    this.expectOp("=");
    const v = this.constValue();
    this.endStmt();
    return { t: "const", name, v, lineno: t.lineno };
  }
  nameTok(t) {
    if (t.kind !== "NAME") {
      throw new HLError(t.lineno, "expected a name, got '" + (t.val || t.kind) + "'");
    }
    if (KEYWORDS.has(t.val)) throw new HLError(t.lineno, "'" + t.val + "' is a keyword");
    return t.val;
  }
  constValue() {
    const t = this.next();
    if (t.kind === "OP" && t.val === "-") {
      return ((-this.constValue()) % 256 + 256) % 256;
    }
    if (t.kind !== "NUM") throw new HLError(t.lineno, "expected a constant");
    const v = numValue(t.val);
    if (v < 0 || v > 255) throw new HLError(t.lineno, "value must be 0-255");
    return v;
  }
  whilestmt() {
    const t = this.next();
    const cond = this.condition();
    this.expectOp(":");
    return { t: "while", cond, body: this.block(), lineno: t.lineno };
  }
  ifstmt() {
    let t = this.next();
    const arms = [];
    const cond = this.condition();
    this.expectOp(":");
    arms.push([cond, this.block()]);
    let orelse = [];
    for (;;) {
      const save = this.i;
      this.skipNewlines();
      // like compile.py, t is REASSIGNED here and its lineno is what
      // the If node carries (the last token the loop peeked - the
      // else keyword, or the token that ended the chain)
      t = this.peek();
      if (t.kind === "KEY" && t.val === "elif") {
        this.next();
        const c = this.condition();
        this.expectOp(":");
        arms.push([c, this.block()]);
        continue;
      }
      if (t.kind === "KEY" && t.val === "else") {
        this.next();
        this.expectOp(":");
        orelse = this.block();
        break;
      }
      this.i = save;
      break;
    }
    return { t: "if", arms, orelse, lineno: t.lineno };
  }
  // ---- conditions
  condition() {
    return this.orExpr();
  }
  orExpr() {
    let l = this.andExpr();
    while (this.peek().kind === "KEY" && this.peek().val === "or") {
      const ln = this.next().lineno;
      l = { t: "or", l, r: this.andExpr(), lineno: ln };
    }
    return l;
  }
  andExpr() {
    let l = this.notExpr();
    while (this.peek().kind === "KEY" && this.peek().val === "and") {
      const ln = this.next().lineno;
      l = { t: "and", l, r: this.notExpr(), lineno: ln };
    }
    return l;
  }
  notExpr() {
    if (this.peek().kind === "KEY" && this.peek().val === "not") {
      const ln = this.next().lineno;
      return { t: "not", e: this.notExpr(), lineno: ln };
    }
    return this.cmpExpr();
  }
  cmpExpr() {
    const l = this.expr();
    const t = this.peek();
    if (t.kind === "OP" && ["==", "!=", "<", "<=", ">", ">="].includes(t.val)) {
      this.next();
      return { t: "cmp", op: t.val, l, r: this.expr(), lineno: t.lineno };
    }
    return { t: "truthy", e: l, lineno: t.lineno };
  }
  // ---- expressions
  expr() {
    return this.addExpr();
  }
  addExpr() {
    let l = this.mulExpr();
    while (this.peek().kind === "OP" && ["+", "-"].includes(this.peek().val)) {
      const t = this.next();
      l = { t: "bin", op: t.val, l, r: this.mulExpr(), lineno: t.lineno };
    }
    return l;
  }
  mulExpr() {
    let l = this.unary();
    while (this.peek().kind === "OP" && this.peek().val === "*") {
      const t = this.next();
      l = { t: "bin", op: "*", l, r: this.unary(), lineno: t.lineno };
    }
    return l;
  }
  unary() {
    const t = this.peek();
    if (t.kind === "OP" && t.val === "-") {
      this.next();
      return { t: "neg", e: this.unary(), lineno: t.lineno };
    }
    return this.primary();
  }
  primary() {
    const t = this.next();
    if (t.kind === "NUM") {
      const v = numValue(t.val);
      if (v < 0 || v > 255) throw new HLError(t.lineno, "value must be 0-255");
      return { t: "num", v, lineno: t.lineno };
    }
    if (t.kind === "NAME") return { t: "name", name: t.val, lineno: t.lineno };
    if (t.kind === "OP" && t.val === "(") {
      const e = this.expr();
      this.expectOp(")");
      return e;
    }
    if (t.kind === "KEY" && t.val === "rol") {
      this.expectOp("(");
      const e = this.expr();
      this.expectOp(")");
      return { t: "rol", e, lineno: t.lineno };
    }
    throw new HLError(t.lineno, "expected a value, got '" + (t.val || t.kind) + "'");
  }
}

// ---------------------------------------------------------------- codegen
//
// A-holds descriptors (compile.py's, as JS arrays):
//   ["var", name]     A == that variable's value
//   ["const", v]      A == the constant v
//   ["twice", name]   A == 2*name, CF == the bit DBL shifted out
//   ["diff", l, r]    A == l - r, flags still reflect the SUB
//   null              A is scratch
// l and r in "diff" are ["var", n] / ["imm", v] / ["cell", c] operands.

// deep equality for descriptors (python's tuple ==)
function deq(a, b) {
  if (a === b) return true;
  if (!Array.isArray(a) || !Array.isArray(b)) return false;
  if (a.length !== b.length) return false;
  return a.every((x, i) => deq(x, b[i]));
}

class Gen {
  constructor() {
    this.out = [];          // asm source lines being built
    this.varCells = new Set();  // declared hl variables
    this.consts = {};       // hl const name -> value
    this.constCells = {};   // value -> cell name
    this.dataRows = [];     // [cell, byte] in declaration order
    this.nlabel = 0;
    this.loops = [];        // [head, exit] stacks for break/continue
    this.a = null;
    this.jumpA = null;      // A descriptor on the edge of the last
    //                        emitted condition jump
    this.flags = null;      // ["cmp", ldesc, rdesc] if the flags still
    //                        reflect comparing l with r; null if stale
    this.broke = false;     // a break was emitted in the current loop
  }

  // ---- emission

  ins(text, hlLn) {
    this.out.push("        " + text.padEnd(11) + "; " + hlLn);
    const sp = text.split(/\s+/);
    const head = sp[0].toUpperCase();
    if (head === "LDA") this.a = ["var", sp[1]];
    else if (head === "LDI") this.a = ["const", parseInt(sp[1], 10)];
    else if (head === "DBL") {
      this.a = this.a && this.a[0] === "var" ? ["twice", this.a[1]] : null;
      this.flags = null;
    } else if (head === "STA") this.a = ["var", sp[1]];
    else if (["ADD", "SUB", "ADDI", "SUBI"].includes(head)) {
      // SUBI 0 is the TEST idiom: the value in A does not change
      if (!(head === "SUBI" && sp[1] === "0")) this.a = null;
      this.flags = null;
    } else if (["OUT", "HLT", "NOP", "JMP", "JC", "JZ", "JNC", "JNZ"].includes(head)) {
      // A and the flags survive control flow and displays
    } else {
      this.a = null;
      this.flags = null;
    }
  }

  label(name, aHint = null, flagsHint = null) {
    this.out.push(name + ":");
    this.a = aHint;       // null: a merge point with unknown A
    this.flags = flagsHint;
  }

  newlabel(stem) {
    this.nlabel += 1;
    return "_" + stem + this.nlabel;
  }

  // ---- name resolution

  lookup(name, hlLn) {
    if (name in this.consts) return ["imm", this.consts[name]];
    if (this.varCells.has(name)) return ["var", name];
    throw new HLError(hlLn,
      "undefined variable '" + name + "' (declare it: var " + name + ")");
  }

  constCell(v) {
    if (!(v in this.constCells)) {
      const name = "c" + v;
      this.constCells[v] = name;
      this.dataRows.push([name, v]);
    }
    return this.constCells[v];
  }

  // ---- arithmetic operand classification

  operand(node, hlLn) {
    if (node.t === "num") {
      return node.v <= 15 ? ["imm", node.v] : ["cell", this.constCell(node.v)];
    }
    if (node.t === "name") {
      const [kind, v] = this.lookup(node.name, hlLn);
      if (kind === "imm") {
        return v <= 15 ? ["imm", v] : ["cell", this.constCell(v)];
      }
      return ["var", node.name];
    }
    return ["expr", node];
  }

  // ---- expressions -> A

  eval(node, hlLn) {
    if (node.t === "num") {
      if (node.v <= 15) {
        if (!deq(this.a, ["const", node.v])) this.ins("LDI " + node.v, hlLn);
      } else {
        const cell = this.constCell(node.v);
        if (!deq(this.a, ["const", node.v])) this.ins("LDA " + cell, hlLn);
      }
      return;
    }
    if (node.t === "name") {
      const [kind, v] = this.lookup(node.name, hlLn);
      if (kind === "imm") {
        this.eval({ t: "num", v, lineno: hlLn }, hlLn);
        return;
      }
      if (!deq(this.a, ["var", node.name])) this.ins("LDA " + node.name, hlLn);
      return;
    }
    if (node.t === "neg") {
      const f = this.fold(node);
      if (f !== null) {
        this.eval({ t: "num", v: f, lineno: hlLn }, hlLn);
        return;
      }
      // 0 - e
      const kind = this.operand(node.e, hlLn);
      if (kind[0] === "imm") {
        this.eval({ t: "num", v: ((-kind[1]) % 256 + 256) % 256, lineno: hlLn }, hlLn);
        return;
      }
      if (kind[0] === "cell") {
        this.ins("LDI 0", hlLn);
        this.ins("SUB " + kind[1], hlLn);
        return;
      }
      this.eval(node.e, hlLn);
      this.ins("STA _t0", hlLn);
      this.ins("LDI 0", hlLn);
      this.ins("SUB _t0", hlLn);
      return;
    }
    if (node.t === "rol") {
      const f = this.fold(node);
      if (f !== null) {
        this.eval({ t: "num", v: f, lineno: hlLn }, hlLn);
        return;
      }
      this.eval(node.e, hlLn);
      this.ins("DBL", hlLn);
      const l = this.newlabel("rl");
      this.ins("JNC " + l, hlLn);
      this.ins("ADDI 1", hlLn);
      this.label(l);
      return;
    }
    if (node.t === "bin") {
      if (node.op === "*") {
        this.evalMul(node, hlLn);
        return;
      }
      const v = this.fold(node);
      if (v !== null) {
        this.eval({ t: "num", v, lineno: hlLn }, hlLn);
        return;
      }
      // the compare-reuse idiom in expression position: the condition
      // left A == l - r and this is the same subtraction
      if (node.op === "-" && this.a && this.a[0] === "diff") {
        const [dL, dR] = [this.a[1], this.a[2]];
        if (this.sameOperand(node.l, dL) && this.sameOperand(node.r, dR)) {
          return;  // A already holds the difference
        }
      }
      this.eval(node.l, hlLn);
      const kind = this.operand(node.r, hlLn);
      if (kind[0] === "imm") {
        this.ins((node.op === "+" ? "ADDI " : "SUBI ") + kind[1], hlLn);
      } else if (kind[0] === "var" || kind[0] === "cell") {
        this.ins((node.op === "+" ? "ADD " : "SUB ") + kind[1], hlLn);
      } else {  // expression on the right: compute it, spill, add
        this.ins("STA _t0", hlLn);
        this.eval(node.r, hlLn);
        this.ins("STA _t1", hlLn);
        this.ins("LDA _t0", hlLn);
        this.ins((node.op === "+" ? "ADD " : "SUB ") + "_t1", hlLn);
      }
      return;
    }
    throw new HLError(hlLn, "a condition cannot be used as a value (booleans" +
      " exist only in if/while)");
  }

  fold(node) {
    if (node.t === "num") return node.v;
    if (node.t === "name") return node.name in this.consts ? this.consts[node.name] : null;
    if (node.t === "neg") {
      const v = this.fold(node.e);
      return v === null ? null : ((-v) % 256 + 256) % 256;
    }
    if (node.t === "bin") {
      const lv = this.fold(node.l), rv = this.fold(node.r);
      if (lv === null || rv === null) return null;
      if (node.op === "+") return (lv + rv) % 256;
      if (node.op === "-") return ((lv - rv) % 256 + 256) % 256;
      if (node.op === "*") return (lv * rv) % 256;
    }
    return null;
  }

  evalMul(node, hlLn) {
    let k = this.fold(node.r), x = node.l;
    if (k === null) {
      k = this.fold(node.l);
      x = node.r;
    }
    if (k === null) {
      throw new HLError(hlLn, "e * e is not supported: the hardware has" +
        " no multiply - write the counting loop instead (see mul.asm)");
    }
    const v = this.fold(x);
    if (v !== null) {
      this.eval({ t: "num", v: (v * k) % 256, lineno: hlLn }, hlLn);
      return;
    }
    if (k === 0) {
      this.ins("LDI 0", hlLn);
      return;
    }
    if (k === 1) {
      this.eval(x, hlLn);
      return;
    }
    if (x.t !== "name") {
      throw new HLError(hlLn, "in e * k the left side must be a variable" +
        " (keeping a copy for the additions needs a RAM cell; use a variable)");
    }
    const [kind, iv] = this.lookup(x.name, hlLn);
    if (kind === "imm") {
      this.eval({ t: "num", v: (iv * k) % 256, lineno: hlLn }, hlLn);
      return;
    }
    // ADD chain for small k (lcg.asm's 5*s = ADD s four times), with
    // reuse when A already holds s or 2*s
    if (k >= 2 && k <= 8) {
      let adds = k - 1;
      if (deq(this.a, ["twice", x.name])) adds = k - 2;
      else if (!deq(this.a, ["var", x.name])) this.ins("LDA " + x.name, hlLn);
      for (let i = 0; i < adds; i++) this.ins("ADD " + x.name, hlLn);
      return;
    }
    // general constant: shift-add on a temp copy of x, built from
    // the top set bit of k downward: result = result*2 (+ x if bit)
    const h = (32 - Math.clz32(k)) - 1;  // k.bit_length() - 1
    this.ins("LDA " + x.name, hlLn);
    this.ins("STA _t0", hlLn);  // _t0 = x
    for (let i = h - 1; i >= 0; i--) {
      this.ins("DBL", hlLn);
      if ((k >> i) & 1) this.ins("ADD _t0", hlLn);
    }
  }

  // ---- conditions: SUB + a branch pair
  //
  // contract: cond(node, tlab, flab) -> "true" | "false" - the side that
  // FALLS THROUGH to the next emitted line (the other side always
  // jumps). Both labels are real; the caller lays out around the
  // returned fall side. Comparisons are unsigned byte comparisons.

  cond(node, tlab, flab, hlLn) {
    if (node.t === "and") {
      // l-true must fall so the r test is reached; l-false jumps to
      // flab. Normalize the left side if it falls on false.
      const mid = this.newlabel("andt");
      const got = this.cond(node.l, mid, flab, hlLn);
      if (got !== "true") {
        this.ins("JMP " + flab, hlLn);
        this.label(mid, this.jumpA);
      }
      return this.cond(node.r, tlab, flab, hlLn);
    }
    if (node.t === "or") {
      // l-true goes straight out; l-false must fall so the r test is
      // reached. Normalize the left side if it falls on true.
      const mid = this.newlabel("orf");
      const got = this.cond(node.l, tlab, mid, hlLn);
      if (got !== "false") {
        this.ins("JMP " + mid, hlLn);
        this.label(mid, this.jumpA);
      }
      return this.cond(node.r, tlab, flab, hlLn);
    }
    if (node.t === "not") {
      // e-true goes to flab, e-false to tlab
      const got = this.cond(node.e, flab, tlab, hlLn);
      if (got === "true") {
        // e-true fell here; it must reach flab, not fall into the
        // caller's true path
        this.ins("JMP " + flab, hlLn);
        return "false";
      }
      return "true";
    }
    if (node.t === "truthy") {
      const v = this.fold(node.e);
      if (v !== null) {
        if (v % 256 !== 0) return "true";  // constant true: falls through
        this.ins("JMP " + flab, hlLn);
        return "false";
      }
      // flags-reuse: a test of this expression against 0 is live
      const d = this.descOf(node.e);
      if (deq(this.flags, ["cmp", d, ["imm", 0]])) {
        this.a = null;
        this.ins("JNZ " + tlab, hlLn);
        return "false";
      }
      this.eval(node.e, hlLn);
      this.ins("SUBI 0", hlLn);
      this.flags = ["cmp", d, ["imm", 0]];
      this.jumpA = this.a;
      this.ins("JNZ " + tlab, hlLn);
      return "false";
    }
    if (node.t === "cmp") return this.cmp(node, tlab, flab, hlLn);
    throw new HLError(hlLn, "cannot use this as a condition");
  }

  cmp(node, tlab, flab, hlLn) {
    const { op, l, r } = node;
    const lv = this.fold(l), rv = this.fold(r);
    if (lv !== null && rv !== null) {
      const truth = { "==": lv === rv, "!=": lv !== rv, "<": lv < rv,
        "<=": lv <= rv, ">": lv > rv, ">=": lv >= rv }[op];
      if (truth) return "true";
      this.ins("JMP " + flab, hlLn);
      return "false";
    }
    // flags-reuse: a comparison of these same operands is still live
    // (nothing arithmetic has run since) - emit only the branch.
    // This is the hand pattern in gcd.asm: JZ done then JC take test
    // the same SUB.
    const ldesc = this.descOf(l);
    let rdesc = this.operandDesc(r, hlLn);
    if (deq(this.flags, ["cmp", ldesc, rdesc])) {
      // the flags are live; A still holds the difference only if
      // nothing has loaded into it since the compare
      if (!deq(this.a, ["diff", ldesc, rdesc])) this.a = null;
      this.emitBranch(op, tlab, flab, hlLn);
      return this.falls(op);
    }
    // the machine's own idiom for the top bit: DBL + JC/JNC
    if ((op === ">=" || op === "<") && l.t === "name" &&
        this.varCells.has(l.name) && r.t === "num" && r.v === 128) {
      if (deq(this.flags, ["twice", l.name])) {
        // the DBL result is still live
      } else {
        this.ins("LDA " + l.name, hlLn);
        this.ins("DBL", hlLn);
      }
      this.jumpA = this.a;
      this.flags = ["twice", l.name];
      this.emitBranch(op, tlab, flab, hlLn);
      return this.falls(op);
    }
    this.eval(l, hlLn);
    const kind = this.operand(r, hlLn);
    if (kind[0] === "imm") {
      this.ins("SUBI " + kind[1], hlLn);
      rdesc = ["imm", kind[1]];
    } else if (kind[0] === "var" || kind[0] === "cell") {
      this.ins("SUB " + kind[1], hlLn);
      rdesc = [kind[0], kind[1]];
    } else {
      this.ins("STA _t0", hlLn);
      this.eval(r, hlLn);
      this.ins("STA _t1", hlLn);
      this.ins("LDA _t0", hlLn);
      this.ins("SUB _t1", hlLn);
      rdesc = ["expr"];
    }
    // A == l - r now; conditions may clobber A, but record the diff
    // so a following `x = x - y` can reuse it, and the flags so a
    // second comparison of the same operands costs only its branch
    this.a = ["diff", this.descOf(l), rdesc];
    this.jumpA = this.a;
    this.flags = ["cmp", this.descOf(l), rdesc];
    this.emitBranch(op, tlab, flab, hlLn);
    return this.falls(op);
  }

  emitBranch(op, tlab, flab, hlLn) {
    // CF=1 iff l >= r (no borrow), ZF=1 iff l == r
    if (op === "==") this.ins("JNZ " + flab, hlLn);
    else if (op === "!=") this.ins("JZ " + flab, hlLn);
    else if (op === ">=") this.ins("JNC " + flab, hlLn);
    else if (op === "<") this.ins("JC " + flab, hlLn);
    else if (op === ">") {
      // false iff l <= r: CF=1 or ZF=1
      this.ins("JC " + flab, hlLn);
      this.ins("JZ " + flab, hlLn);
    } else if (op === "<=") {
      // true iff CF=1 or ZF=1: jumps on true, falls on false
      this.ins("JNC " + tlab, hlLn);
      this.ins("JZ " + tlab, hlLn);
    } else {
      throw new HLError(hlLn, "unknown comparison '" + op + "'");
    }
  }

  falls(op) {
    // which side falls through after emitBranch
    return op === "<=" ? "false" : "true";
  }

  operandDesc(r, hlLn) {
    const kind = this.operand(r, hlLn);
    return kind[0] !== "expr" ? [kind[0], kind[1]] : ["expr"];
  }

  descOf(node) {
    if (node.t === "name") {
      if (this.varCells.has(node.name)) return ["var", node.name];
      if (node.name in this.consts) {
        const v = this.consts[node.name];
        return v <= 15 ? ["imm", v] : ["cell", this.constCell(v)];
      }
    }
    if (node.t === "num") {
      return node.v <= 15 ? ["imm", node.v] : ["cell", this.constCell(node.v)];
    }
    return ["expr"];
  }

  // ---- statements

  genStmt(st) {
    const ln = st.lineno;
    if (st.t === "var") {
      if (this.varCells.has(st.name) || st.name in this.consts) {
        throw new HLError(ln, "'" + st.name + "' is already declared");
      }
      const v = this.fold(st.init);
      if (v === null) {
        throw new HLError(ln, "the initializer must be a constant - RAM" +
          " is loaded before the program runs");
      }
      if (v < 0 || v > 255) throw new HLError(ln, "initializer must be 0-255");
      this.varCells.add(st.name);
      this.dataRows.push([st.name, v]);
      return;
    }
    if (st.t === "const") {
      if (this.varCells.has(st.name) || st.name in this.consts) {
        throw new HLError(ln, "'" + st.name + "' is already declared");
      }
      this.consts[st.name] = st.v;
      return;
    }
    if (st.t === "assign") {
      this.genAssign(st);
      return;
    }
    if (st.t === "out") {
      this.eval(st.e, ln);
      this.ins("OUT", ln);
      return;
    }
    if (st.t === "simple") {
      if (st.which === "halt") this.ins("HLT", ln);
      else if (st.which === "pass") this.ins("NOP", ln);
      else {
        if (!this.loops.length) {
          throw new HLError(ln, "'" + st.which + "' is only valid inside a while");
        }
        const [head, exit] = this.loops[this.loops.length - 1];
        if (st.which === "break") this.broke = true;
        this.ins("JMP " + (st.which === "continue" ? head : exit), ln);
      }
      return;
    }
    if (st.t === "while") {
      const head = this.newlabel("loop");
      const exit = this.newlabel("done");
      const bodyl = this.newlabel("body");
      this.label(head);
      const got = this.cond(st.cond, bodyl, exit, ln);
      this.loops.push([head, exit]);
      this.broke = false;
      if (got === "true") {
        // the condition's true side falls into the body
        for (const s of st.body) this.genStmt(s);
      } else {
        // the condition's true side jumps to bodyl; the false
        // side fell here - leave the loop
        this.ins("JMP " + exit, ln);
        this.label(bodyl, this.jumpA);
        for (const s of st.body) this.genStmt(s);
      }
      this.loops.pop();
      this.ins("JMP " + head, ln);
      // break edges may arrive with a different A than the
      // condition's false edge: only hint when no break was emitted
      const hint = this.broke ? null : this.jumpA;
      this.label(exit, hint, null);
      return;
    }
    if (st.t === "if") {
      const end = this.newlabel("endif");
      const endStates = [];
      for (let i = 0; i < st.arms.length; i++) {
        const [c, body] = st.arms[i];
        const lastArm = i === st.arms.length - 1 && !st.orelse.length;
        const els = lastArm ? end : this.newlabel("else");
        const thenl = this.newlabel("then");
        const got = this.cond(c, thenl, els, ln);
        if (got === "true") {
          // true falls into the body
          for (const s of body) this.genStmt(s);
          if (!terminates(body)) {
            this.ins("JMP " + end, ln);
            endStates.push(this.a);
          }
        } else {
          // true jumps to thenl; false fell here - go to else
          this.ins("JMP " + els, ln);
          this.label(thenl, this.jumpA);
          for (const s of body) this.genStmt(s);
          if (!terminates(body)) {
            this.ins("JMP " + end, ln);
            endStates.push(this.a);
          }
        }
        if (els !== end) this.label(els, this.jumpA);
      }
      for (const s of st.orelse) this.genStmt(s);
      endStates.push(this.a);
      // if every path into end arrives with the same A value, the
      // join can keep that knowledge (out x after if/else: rol.asm)
      const hint = endStates.length && endStates[0] &&
        endStates.every((s) => deq(s, endStates[0])) ? endStates[0] : null;
      this.label(end, hint);
      return;
    }
    throw new HLError(ln, "internal: unknown statement");
  }

  genAssign(st) {
    const ln = st.lineno;
    const name = st.name;
    if (name in this.consts) {
      throw new HLError(ln, "cannot assign to the constant '" + name + "'");
    }
    if (!this.varCells.has(name)) {
      throw new HLError(ln,
        "undefined variable '" + name + "' (declare it: var " + name + ")");
    }
    // the compare-reuse idiom: the condition left A == l - r and this
    // assignment recomputes that same subtraction into the left var
    if (this.a && this.a[0] === "diff") {
      const [dL, dR] = [this.a[1], this.a[2]];
      if (deq(dL, ["var", name]) && st.e.t === "bin" && st.e.op === "-" &&
          this.sameOperand(st.e.l, dL) && this.sameOperand(st.e.r, dR)) {
        this.ins("STA " + name, ln);
        // the ALU's ZF tested exactly this new value
        this.flags = ["cmp", ["var", name], ["imm", 0]];
        return;
      }
    }
    const pre = this.out.length;
    this.eval(st.e, ln);
    const last = this.out.length > pre ? this.out[this.out.length - 1] : null;
    this.ins("STA " + name, ln);
    // eval skips LDA/LDI/DBL when A already holds the needed value
    if (last) {
      const head = last.trim().split(/\s+/)[0].toUpperCase();
      if (["ADD", "SUB", "ADDI", "SUBI", "DBL"].includes(head)) {
        // the last ALU operation computed the assigned value, so
        // its ZF tells whether the variable is now zero
        this.flags = ["cmp", ["var", name], ["imm", 0]];
      }
    }
  }

  sameOperand(node, desc) {
    if (desc[0] === "var") {
      return node.t === "name" && node.name === desc[1];
    }
    if (desc[0] === "imm") {
      if (node.t === "num") return node.v === desc[1];
      return node.t === "name" && this.consts[node.name] === desc[1];
    }
    if (desc[0] === "cell") {
      // (compile.py dereferences node.name here and crashes on a Bin
      // right side; the port guards it - a compound expression is
      // simply not the same operand)
      const v = node.t === "num" ? node.v
        : node.t === "name" && node.name in this.consts ? this.consts[node.name] : null;
      return v !== null && this.constCell(v) === desc[1];
    }
    return false;
  }
}

function terminates(body) {
  return body.length && body[body.length - 1].t === "simple" &&
    body[body.length - 1].which === "halt";
}

// ---------------------------------------------------------------- public

/** .hl source text -> assembly source text (compile.py's
 *  compile_program). Throws HLError on a bad program. */
export function compileProgram(text) {
  const toks = lex(text);
  const stmts = new Parser(toks).program();
  const g = new Gen();
  for (const st of stmts) g.genStmt(st);
  const out = [...g.out];
  if (g.dataRows.length) {
    out.push("");
    for (const [cell, v] of g.dataRows) {
      out.push((cell + ":").padEnd(8) + " .DB " + v);
    }
  }
  return out.join("\n") + "\n";
}

/** Full pipeline: .hl text -> asm text, validated by assembling it
 *  (compile.py's compile_to_asm - the fits-the-hardware guard). */
export function compileToAsm(text, memSize) {
  const asmText = compileProgram(text);
  try {
    assembleText(asmText, memSize, "(generated)");
  } catch (e) {
    const msg = e.errors ? "asm: " + e.errors.join("; ") : String(e);
    throw new HLError(0, "the program does not fit the hardware: " + msg);
  }
  return asmText;
}

/** .hl text -> { asmText, mem, listing } (compile.py + asm.py, the
 *  whole build chain from docs/tools.md). */
export function compileHl(text) {
  const asmText = compileToAsm(text, 16);
  const { mem, rows } = assembleText(asmText, 16, "(generated)");
  const used = rows.reduce((n, [_a, b]) => n + (b !== null ? 1 : 0), 0);
  const listing = formatListing(rows, used, 16);
  return { asmText, mem, listing };
}
