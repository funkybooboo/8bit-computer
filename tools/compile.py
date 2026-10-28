#!/usr/bin/env python3
"""
compile.py - the .hl language: a high-level language for the 8-bit
computer, compiled to the assembly language (asm.py's target).

The language maps onto what the hardware can do (full reference:
../docs/language.md). It is deliberately honest about the machine:

  - one 8-bit accumulator, 16 bytes of RAM shared by code and data
  - arithmetic is +, - and * by a constant (mod 256); the compiler uses
    DBL and ADD chains for multiplies, never a hidden loop
  - conditions never become values: they compile directly to SUB + a
    branch pair, so `and`/`or`/`not` are short-circuit and cost nothing
    but the branches
  - comparisons follow the machine's own rule (SUB sets CF=1 iff
    A >= B, ZF=1 iff A == B); `x >= 128` uses the DBL top-bit test
  - there are no boolean variables, no arrays, no functions, no
    recursion - the hardware has no storage for any of them, and the
    compiler rejects them instead of pretending
  - the compiler emits the hand-written idioms from the program corpus:
    it tracks the accumulator, so `out x` right after `x = ...` costs
    one byte, `x = x - y` right after `while x >= y` reuses the
    compare's subtraction, and `x = x * 2 + 1` after `if x >= 128`
    reuses the test's DBL

Statements:

    var x = 9         # data cell (initializer must be a constant)
    var y             # data cell, starts 0
    const limit = 10  # named constant
    x = expr
    out expr
    halt
    pass              # a NOP - pacing, like the countdown
    while cond:
        ...
        break
        continue
    if cond:
        ...
    elif cond:
        ...
    else:
        ...

Expressions: numbers (0-255, decimal/0x/0b), variables, constants,
parentheses, unary -, + - * and rol(e) - the rotate-left-through-carry
idiom (DBL + JNC + ADDI 1). e * k needs k constant; e * e is rejected
(the hardware has no multiply - write the shift-add loop, mul.asm).
Every value is a byte: arithmetic wraps mod 256 and comparisons are
unsigned byte comparisons.

Examples:
  compile.py programs/count.hl            # -> count.asm + count.bin
  compile.py programs/count.hl --stdout   # print the generated .asm only
"""

import argparse
import os
import re
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import asm            # the assembler the compiler targets
from asm import assemble as asm_assemble

# ---------------------------------------------------------------------------
# errors

class HLError(Exception):
    """An error at a .hl source position."""

    def __init__(self, lineno, msg):
        super().__init__(msg)
        self.lineno, self.msg = lineno, msg

    def __str__(self):
        return "%d: %s" % (self.lineno, self.msg)

# ---------------------------------------------------------------------------
# lexer: indentation blocks, # and ; comments, ; as a statement separator

KEYWORDS = {"var", "const", "out", "halt", "pass", "while", "if", "elif",
            "else", "break", "continue", "and", "or", "not"}
# statements allowed as a single `while c: stmt` body
INLINE_OK = {"out", "halt", "pass", "break", "continue", "if", "var", "const"}

NUM_RE = re.compile(r"0[xX][0-9a-fA-F]+\Z|0[bB][01]+\Z|\d+\Z")
NAME_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\Z")

class Tok:
    __slots__ = ("kind", "val", "lineno")

    def __init__(self, kind, val, lineno):
        self.kind, self.val, self.lineno = kind, val, lineno  # NUM NAME OP
        # KEY NEWLINE INDENT DEDENT EOF

def lex(path):
    try:
        with open(path, encoding="utf-8") as fh:
            lines = fh.read().splitlines()
    except OSError as e:
        raise SystemExit("compile: cannot read %s: %s" % (path, e))
    toks, stack = [], [0]
    for lineno, raw in enumerate(lines, 1):
        line = raw.split("#", 1)[0].split(";", 1)[0]
        stripped = line.strip()
        if not stripped:
            toks.append(Tok("NEWLINE", None, lineno))
            continue
        indent = len(line) - len(line.lstrip(" "))
        if indent % 4:
            raise HLError(lineno, "indentation must be a multiple of 4 spaces")
        while indent < stack[-1]:
            stack.pop()
            toks.append(Tok("DEDENT", None, lineno))
        if indent > stack[-1]:
            stack.append(indent)
            toks.append(Tok("INDENT", None, lineno))
        i, buf = 0, ""
        while i < len(stripped):
            c = stripped[i]
            if c in "()+-*<>=!:,":
                if buf:
                    _emit(toks, buf, lineno)
                    buf = ""
                two = stripped[i:i + 2]
                if two in ("==", "!=", "<=", ">="):
                    toks.append(Tok("OP", two, lineno))
                    i += 2
                    continue
                toks.append(Tok("OP", c, lineno))
                i += 1
                continue
            if c.isspace():
                if buf:
                    _emit(toks, buf, lineno)
                    buf = ""
                i += 1
                continue
            buf += c
            i += 1
        if buf:
            _emit(toks, buf, lineno)
        toks.append(Tok("NEWLINE", None, lineno))
    while stack[-1] != 0:
        stack.pop()
        toks.append(Tok("DEDENT", None, len(lines)))
    toks.append(Tok("EOF", None, len(lines)))
    return toks

def _emit(toks, buf, lineno):
    if buf in KEYWORDS:
        toks.append(Tok("KEY", buf, lineno))
    elif NUM_RE.match(buf):
        toks.append(Tok("NUM", buf, lineno))
    elif NAME_RE.match(buf):
        toks.append(Tok("NAME", buf, lineno))
    else:
        raise HLError(lineno, "cannot lex %r" % buf)

def num_value(tok):
    low = tok.lower()
    if low.startswith("0x"):
        return int(low, 16)
    if low.startswith("0b"):
        return int(low, 2)
    return int(tok)

# ---------------------------------------------------------------------------
# AST

class Node:
    __slots__ = ("lineno",)

class Num(Node):
    __slots__ = ("v",)
    def __init__(self, v, lineno):
        self.v, self.lineno = v, lineno

class Name(Node):
    __slots__ = ("name",)
    def __init__(self, name, lineno):
        self.name, self.lineno = name, lineno

class Bin(Node):
    __slots__ = ("op", "l", "r")
    def __init__(self, op, l, r, lineno):
        self.op, self.l, self.r, self.lineno = op, l, r, lineno

class Neg(Node):
    __slots__ = ("e",)
    def __init__(self, e, lineno):
        self.e, self.lineno = e, lineno

class Rol(Node):
    __slots__ = ("e",)
    def __init__(self, e, lineno):
        self.e, self.lineno = e, lineno

class Cmp(Node):
    __slots__ = ("op", "l", "r")
    def __init__(self, op, l, r, lineno):
        self.op, self.l, self.r, self.lineno = op, l, r, lineno

class And(Node):
    __slots__ = ("l", "r")
    def __init__(self, l, r, lineno):
        self.l, self.r, self.lineno = l, r, lineno

class Or(Node):
    __slots__ = ("l", "r")
    def __init__(self, l, r, lineno):
        self.l, self.r, self.lineno = l, r, lineno

class Not(Node):
    __slots__ = ("e",)
    def __init__(self, e, lineno):
        self.e, self.lineno = e, lineno

class Truthy(Node):
    __slots__ = ("e",)
    def __init__(self, e, lineno):
        self.e, self.lineno = e, lineno

class Stmt(Node):
    __slots__ = ()

class Assign(Stmt):
    __slots__ = ("name", "e")
    def __init__(self, name, e, lineno):
        self.name, self.e, self.lineno = name, e, lineno

class Out(Stmt):
    __slots__ = ("e",)
    def __init__(self, e, lineno):
        self.e, self.lineno = e, lineno

class Simple(Stmt):
    __slots__ = ("which",)  # "halt" | "pass" | "break" | "continue"
    def __init__(self, which, lineno):
        self.which, self.lineno = which, lineno

class VarDecl(Stmt):
    __slots__ = ("name", "init")
    def __init__(self, name, init, lineno):
        self.name, self.init, self.lineno = name, init, lineno

class ConstDecl(Stmt):
    __slots__ = ("name", "v")
    def __init__(self, name, v, lineno):
        self.name, self.v, self.lineno = name, v, lineno

class While(Stmt):
    __slots__ = ("cond", "body")
    def __init__(self, cond, body, lineno):
        self.cond, self.body, self.lineno = cond, body, lineno

class If(Stmt):
    __slots__ = ("arms", "orelse")  # arms: [(cond, body), ...]
    def __init__(self, arms, orelse, lineno):
        self.arms, self.orelse, self.lineno = arms, orelse, lineno

# ---------------------------------------------------------------------------
# parser

class Parser:
    def __init__(self, toks):
        self.toks, self.i = toks, 0

    def peek(self, k=0):
        return self.toks[min(self.i + k, len(self.toks) - 1)]

    def next(self):
        t = self.toks[self.i]
        if t.kind != "EOF":
            self.i += 1
        return t

    def expect_op(self, op):
        t = self.next()
        if t.kind != "OP" or t.val != op:
            raise HLError(t.lineno, "expected %r, got %r" % (op, t.val or t.kind))

    def skip_newlines(self):
        while self.peek().kind == "NEWLINE":
            self.next()

    def program(self):
        out = []
        self.skip_newlines()
        while self.peek().kind != "EOF":
            out.extend(self.statement())
            self.skip_newlines()
        return out

    def block(self):
        self.skip_newlines()  # the rest of the ':' line
        t = self.peek()
        if t.kind == "KEY" and t.val in INLINE_OK:
            return self.statement()
        if t.kind != "INDENT":
            raise HLError(t.lineno, "expected an indented block (or one"
                                   " simple statement after the ':')")
        self.next()
        self.skip_newlines()
        body = []
        while self.peek().kind not in ("DEDENT", "EOF"):
            body.extend(self.statement())
            self.skip_newlines()
        if self.peek().kind == "DEDENT":
            self.next()
        return body

    def statement(self):
        t = self.peek()
        ln = t.lineno
        if t.kind == "KEY":
            if t.val == "var":
                return [self.vardecl()]
            if t.val == "const":
                return [self.constdecl()]
            if t.val == "out":
                self.next()
                e = self.expr()
                self.end_stmt()
                return [Out(e, ln)]
            if t.val in ("halt", "pass", "break", "continue"):
                self.next()
                self.end_stmt()
                return [Simple(t.val, ln)]
            if t.val == "while":
                return [self.whilestmt()]
            if t.val == "if":
                return [self.ifstmt()]
            raise HLError(ln, "%r cannot start a statement" % t.val)
        if t.kind == "NAME":
            name = self.next().val
            self.expect_op("=")
            e = self.expr()
            self.end_stmt()
            return [Assign(name, e, ln)]
        raise HLError(ln, "expected a statement, got %r" % (t.val or t.kind))

    def end_stmt(self):
        t = self.next()
        if t.kind not in ("NEWLINE", "EOF"):
            raise HLError(t.lineno, "expected end of statement, got %r"
                           % (t.val or t.kind))

    def vardecl(self):
        self.next()  # 'var'
        t = self.next()
        name = self.name_tok(t)
        if self.peek().kind == "OP" and self.peek().val == "=":
            self.next()
            e = self.expr()
        else:
            e = Num(0, t.lineno)  # no initializer: the cell starts 0
        self.end_stmt()
        return VarDecl(name, e, t.lineno)

    def constdecl(self):
        self.next()  # 'const'
        t = self.next()
        name = self.name_tok(t)
        self.expect_op("=")
        v = self.const_value()
        self.end_stmt()
        return ConstDecl(name, v, t.lineno)

    def name_tok(self, t):
        if t.kind != "NAME":
            raise HLError(t.lineno, "expected a name, got %r" % (t.val or t.kind))
        if t.val in KEYWORDS:
            raise HLError(t.lineno, "%r is a keyword" % t.val)
        return t.val

    def const_value(self):
        t = self.next()
        if t.kind == "OP" and t.val == "-":
            return (-self.const_value()) % 256
        if t.kind != "NUM":
            raise HLError(t.lineno, "expected a constant")
        v = num_value(t.val)
        if not 0 <= v <= 255:
            raise HLError(t.lineno, "value must be 0-255")
        return v

    def whilestmt(self):
        t = self.next()
        cond = self.condition()
        self.expect_op(":")
        return While(cond, self.block(), t.lineno)

    def ifstmt(self):
        t = self.next()
        arms = []
        cond = self.condition()
        self.expect_op(":")
        arms.append((cond, self.block()))
        orelse = []
        while True:
            save = self.i
            self.skip_newlines()
            t = self.peek()
            if t.kind == "KEY" and t.val == "elif":
                self.next()
                cond = self.condition()
                self.expect_op(":")
                arms.append((cond, self.block()))
                continue
            if t.kind == "KEY" and t.val == "else":
                self.next()
                self.expect_op(":")
                orelse = self.block()
                break
            self.i = save
            break
        return If(arms, orelse, t.lineno)

    # ---- conditions

    def condition(self):
        return self.or_expr()

    def or_expr(self):
        l = self.and_expr()
        while self.peek().kind == "KEY" and self.peek().val == "or":
            ln = self.next().lineno
            l = Or(l, self.and_expr(), ln)
        return l

    def and_expr(self):
        l = self.not_expr()
        while self.peek().kind == "KEY" and self.peek().val == "and":
            ln = self.next().lineno
            l = And(l, self.not_expr(), ln)
        return l

    def not_expr(self):
        if self.peek().kind == "KEY" and self.peek().val == "not":
            ln = self.next().lineno
            return Not(self.not_expr(), ln)
        return self.cmp_expr()

    def cmp_expr(self):
        l = self.expr()
        t = self.peek()
        if t.kind == "OP" and t.val in ("==", "!=", "<", "<=", ">", ">="):
            self.next()
            return Cmp(t.val, l, self.expr(), t.lineno)
        return Truthy(l, t.lineno)

    # ---- expressions

    def expr(self):
        return self.add_expr()

    def add_expr(self):
        l = self.mul_expr()
        while self.peek().kind == "OP" and self.peek().val in ("+", "-"):
            t = self.next()
            l = Bin(t.val, l, self.mul_expr(), t.lineno)
        return l

    def mul_expr(self):
        l = self.unary()
        while self.peek().kind == "OP" and self.peek().val == "*":
            t = self.next()
            l = Bin("*", l, self.unary(), t.lineno)
        return l

    def unary(self):
        t = self.peek()
        if t.kind == "OP" and t.val == "-":
            self.next()
            return Neg(self.unary(), t.lineno)
        return self.primary()

    def primary(self):
        t = self.next()
        if t.kind == "NUM":
            v = num_value(t.val)
            if not 0 <= v <= 255:
                raise HLError(t.lineno, "value must be 0-255")
            return Num(v, t.lineno)
        if t.kind == "NAME":
            return Name(t.val, t.lineno)
        if t.kind == "OP" and t.val == "(":
            e = self.expr()
            self.expect_op(")")
            return e
        if t.kind == "KEY" and t.val == "rol":
            self.expect_op("(")
            e = self.expr()
            self.expect_op(")")
            return Rol(e, t.lineno)
        raise HLError(t.lineno, "expected a value, got %r" % (t.val or t.kind))

# ---------------------------------------------------------------------------
# code generation

# A-holds descriptors:
#   ("var", name)     A == that variable's value
#   ("const", v)      A == the constant v
#   ("twice", name)   A == 2*name, CF == the bit DBL shifted out
#   ("diff", l, r)    A == l - r, flags still reflect the SUB
#   None              A is scratch
# l and r in "diff" are ("var", n) / ("imm", v) / ("cell", c) operands.

class Gen:
    def __init__(self):
        self.out = []          # asm source lines being built
        self.var_cells = set() # declared hl variables
        self.consts = {}       # hl const name -> value
        self.const_cells = {}  # value -> cell name
        self.data_rows = []    # (cell, byte) in declaration order
        self.nlabel = 0
        self.loops = []        # (head, exit) stacks for break/continue
        self.a = None
        self.jump_a = None     # A descriptor on the edge of the last emitted
        #                        condition jump (what A holds where it lands)
        self.flags = None      # ("cmp", ldesc, rdesc) if the flags still
        #                        reflect comparing l with r; None if stale
        self.broke = False     # a break was emitted in the current loop

    # ---- emission

    def ins(self, text, hl_ln):
        """Emit one instruction, updating the A descriptor."""
        self.out.append("        %-11s; %d" % (text, hl_ln))
        head = text.split()[0].upper()
        if head == "LDA":
            self.a = ("var", text.split()[1])
        elif head == "LDI":
            self.a = ("const", int(text.split()[1]))
        elif head == "DBL":
            self.a = ("twice", self.a[1]) if self.a and self.a[0] == "var" else None
            self.flags = None
        elif head == "STA":
            self.a = ("var", text.split()[1])
        elif head in ("ADD", "SUB", "ADDI", "SUBI"):
            # SUBI 0 is the TEST idiom: the value in A does not change
            if head == "SUBI" and text.split()[1] == "0":
                pass
            else:
                self.a = None
            self.flags = None
        elif head in ("OUT", "HLT", "NOP", "JMP", "JC", "JZ", "JNC", "JNZ"):
            pass  # A and the flags survive control flow and displays
        else:
            self.a = None
            self.flags = None

    def label(self, name, a_hint=None, flags_hint=None):
        self.out.append("%s:" % name)
        self.a = a_hint       # None: a merge point with unknown A
        self.flags = flags_hint

    def newlabel(self, stem):
        self.nlabel += 1
        return "_%s%d" % (stem, self.nlabel)

    # ---- name resolution

    def lookup(self, name, hl_ln):
        if name in self.consts:
            return ("imm", self.consts[name])
        if name in self.var_cells:
            return ("var", name)
        raise HLError(hl_ln, "undefined variable %r (declare it: var %s)"
                     % (name, name))

    def const_cell(self, v):
        if v not in self.const_cells:
            name = "c%d" % v
            self.const_cells[v] = name
            self.data_rows.append((name, v))
        return self.const_cells[v]

    # ---- arithmetic operand classification

    def operand(self, node, hl_ln):
        """Right-hand operand of + - or a comparison ->
        ("imm", v) | ("var", name) | ("cell", name) | ("expr", node).
        "imm" fits an ADDI/SUBI nibble; "cell" is a constant pool cell
        for big constants; "var" is a variable's own cell; "expr" needs
        spilling."""
        if isinstance(node, Num):
            return ("imm", node.v) if node.v <= 15 else ("cell", self.const_cell(node.v))
        if isinstance(node, Name):
            kind, v = self.lookup(node.name, hl_ln)
            if kind == "imm":
                return ("imm", v) if v <= 15 else ("cell", self.const_cell(v))
            return ("var", node.name)
        return ("expr", node)

    # ---- expressions -> A

    def eval(self, node, hl_ln):
        """Leave the value in A. Never destroys a variable's cell."""
        if isinstance(node, Num):
            if node.v <= 15:
                if self.a != ("const", node.v):
                    self.ins("LDI %d" % node.v, hl_ln)
            else:
                cell = self.const_cell(node.v)
                if self.a != ("const", node.v):
                    self.ins("LDA %s" % cell, hl_ln)
            return
        if isinstance(node, Name):
            kind, v = self.lookup(node.name, hl_ln)
            if kind == "imm":
                self.eval(Num(v, hl_ln), hl_ln)
                return
            if self.a != ("var", node.name):
                self.ins("LDA %s" % node.name, hl_ln)
            return
        if isinstance(node, Neg):
            if self.fold(node) is not None:
                self.eval(Num(self.fold(node), hl_ln), hl_ln)
                return
            # 0 - e
            kind = self.operand(node.e, hl_ln)
            if kind[0] == "imm":
                self.eval(Num((-kind[1]) % 256, hl_ln), hl_ln)
                return
            if kind[0] == "cell":
                self.ins("LDI 0", hl_ln)
                self.ins("SUB %s" % kind[1], hl_ln)
                return
            self.eval(node.e, hl_ln)
            self.ins("STA _t0", hl_ln)
            self.ins("LDI 0", hl_ln)
            self.ins("SUB _t0", hl_ln)
            return
        if isinstance(node, Rol):
            if self.fold(node) is not None:
                self.eval(Num(self.fold(node), hl_ln), hl_ln)
                return
            self.eval(node.e, hl_ln)
            self.ins("DBL", hl_ln)
            l = self.newlabel("rl")
            self.ins("JNC %s" % l, hl_ln)
            self.ins("ADDI 1", hl_ln)
            self.label(l)
            return
        if isinstance(node, Bin):
            if node.op == "*":
                self.eval_mul(node, hl_ln)
                return
            v = self.fold(node)
            if v is not None:
                self.eval(Num(v, hl_ln), hl_ln)
                return
            # the compare-reuse idiom in expression position: the
            # condition left A == l - r and this is the same subtraction
            if node.op == "-" and self.a and self.a[0] == "diff":
                d_l, d_r = self.a[1], self.a[2]
                if self.same_operand(node.l, d_l) and self.same_operand(node.r, d_r):
                    return  # A already holds the difference
            # reuse: A already holds twice(x) and the product is x*2
            self.eval(node.l, hl_ln)
            kind = self.operand(node.r, hl_ln)
            if kind[0] == "imm":
                self.ins("%s %d" % ("ADDI" if node.op == "+" else "SUBI",
                                    kind[1]), hl_ln)
            elif kind[0] in ("var", "cell"):
                self.ins("%s %s" % ("ADD" if node.op == "+" else "SUB",
                                    kind[1]), hl_ln)
            else:  # expression on the right: compute it, spill, add
                self.ins("STA _t0", hl_ln)
                self.eval(node.r, hl_ln)
                self.ins("STA _t1", hl_ln)
                self.ins("LDA _t0", hl_ln)
                self.ins("%s _t1" % ("ADD" if node.op == "+" else "SUB"), hl_ln)
            return
        raise HLError(hl_ln, "a condition cannot be used as a value (booleans"
                             " exist only in if/while)")

    def fold(self, node):
        """compile-time value of node, or None (variables excluded)."""
        if isinstance(node, Num):
            return node.v
        if isinstance(node, Name):
            return self.consts.get(node.name)
        if isinstance(node, Neg):
            v = self.fold(node.e)
            return None if v is None else (-v) % 256
        if isinstance(node, Bin):
            lv, rv = self.fold(node.l), self.fold(node.r)
            if lv is None or rv is None:
                return None
            if node.op == "+":
                return (lv + rv) % 256
            if node.op == "-":
                return (lv - rv) % 256
            if node.op == "*":
                return (lv * rv) % 256
        return None

    def eval_mul(self, node, hl_ln):
        k = self.fold(node.r)
        x = node.l
        if k is None:
            k = self.fold(node.l)
            x = node.r
        if k is None:
            raise HLError(hl_ln, "e * e is not supported: the hardware has"
                                 " no multiply - write the counting loop"
                                 " instead (see mul.asm)")
        v = self.fold(x)
        if v is not None:
            self.eval(Num((v * k) % 256, hl_ln), hl_ln)
            return
        if k == 0:
            self.ins("LDI 0", hl_ln)
            return
        if k == 1:
            self.eval(x, hl_ln)
            return
        if not isinstance(x, Name):
            raise HLError(hl_ln, "in e * k the left side must be a variable"
                                 " (keeping a copy for the additions needs a"
                                 " RAM cell; use a variable)")
        kind, iv = self.lookup(x.name, hl_ln)
        if kind == "imm":
            self.eval(Num((iv * k) % 256, hl_ln), hl_ln)
            return
        # ADD chain for small k (lcg.asm's 5*s = ADD s four times), with
        # reuse when A already holds s or 2*s
        if 2 <= k <= 8:
            adds = k - 1
            if self.a == ("twice", x.name):
                adds = k - 2
            elif self.a != ("var", x.name):
                self.ins("LDA %s" % x.name, hl_ln)
            for _ in range(adds):
                self.ins("ADD %s" % x.name, hl_ln)
            return
        # general constant: shift-add on a temp copy of x, built from
        # the top set bit of k downward: result = result*2 (+ x if bit)
        h = k.bit_length() - 1
        self.ins("LDA %s" % x.name, hl_ln)
        self.ins("STA _t0", hl_ln)  # _t0 = x
        for i in range(h - 1, -1, -1):
            self.ins("DBL", hl_ln)
            if (k >> i) & 1:
                self.ins("ADD _t0", hl_ln)
        return

    # ---- conditions: SUB + a branch pair
    #
    # contract: cond(node, tlab, flab) -> "true" | "false" - the side that
    # FALLS THROUGH to the next emitted line (the other side always
    # jumps). Both labels are real; the caller lays out around the
    # returned fall side. Comparisons are unsigned byte comparisons.

    def cond(self, node, tlab, flab, hl_ln):
        """Emit the condition so control reaches tlab on true and flab
        on false; return "true"/"false" - the side that FALLS THROUGH to
        the next line (the other side always jumps)."""
        if isinstance(node, And):
            # l-true must fall so the r test is reached; l-false jumps to
            # flab. Normalize the left side if it falls on false.
            mid = self.newlabel("andt")
            got = self.cond(node.l, mid, flab, hl_ln)
            if got != "true":
                self.ins("JMP %s" % flab, hl_ln)
                self.label(mid, a_hint=self.jump_a)
            return self.cond(node.r, tlab, flab, hl_ln)
        if isinstance(node, Or):
            # l-true goes straight out; l-false must fall so the r test
            # is reached. Normalize the left side if it falls on true.
            mid = self.newlabel("orf")
            got = self.cond(node.l, tlab, mid, hl_ln)
            if got != "false":
                self.ins("JMP %s" % mid, hl_ln)
                self.label(mid, a_hint=self.jump_a)
            return self.cond(node.r, tlab, flab, hl_ln)
        if isinstance(node, Not):
            # e-true goes to flab, e-false to tlab
            got = self.cond(node.e, flab, tlab, hl_ln)
            if got == "true":
                # e-true fell here; it must reach flab, not fall into the
                # caller's true path
                self.ins("JMP %s" % flab, hl_ln)
                return "false"
            return "true"
        if isinstance(node, Truthy):
            v = self.fold(node.e)
            if v is not None:
                if v % 256 != 0:
                    return "true"  # constant true: falls through
                self.ins("JMP %s" % flab, hl_ln)
                return "false"
            # flags-reuse: a test of this expression against 0 is live
            d = self.desc_of(node.e)
            if self.flags == ("cmp", d, ("imm", 0)):
                self.a = None
                self.ins("JNZ %s" % tlab, hl_ln)
                return "false"
            self.eval(node.e, hl_ln)
            self.ins("SUBI 0", hl_ln)
            self.flags = ("cmp", d, ("imm", 0))
            self.jump_a = self.a
            self.ins("JNZ %s" % tlab, hl_ln)
            return "false"
        if isinstance(node, Cmp):
            return self.cmp(node, tlab, flab, hl_ln)
        raise HLError(hl_ln, "cannot use this as a condition")

    def cmp(self, node, tlab, flab, hl_ln):
        op, l, r = node.op, node.l, node.r
        lv, rv = self.fold(l), self.fold(r)
        if lv is not None and rv is not None:
            true = {"==": lv == rv, "!=": lv != rv, "<": lv < rv,
                    "<=": lv <= rv, ">": lv > rv, ">=": lv >= rv}[op]
            if true:
                return "true"
            self.ins("JMP %s" % flab, hl_ln)
            return "false"
        # flags-reuse: a comparison of these same operands is still live
        # (nothing arithmetic has run since) - emit only the branch.
        # This is the hand pattern in gcd.asm: JZ done then JC take test
        # the same SUB.
        ldesc, rdesc = self.desc_of(l), self.operand_desc(r, hl_ln)
        if self.flags == ("cmp", ldesc, rdesc):
            # the flags are live; A still holds the difference only if
            # nothing has loaded into it since the compare
            if self.a != ("diff", ldesc, rdesc):
                self.a = None
            self.emit_branch(op, tlab, flab, hl_ln)
            return self.falls(op)
        # the machine's own idiom for the top bit: DBL + JC/JNC
        if op in (">=", "<") and isinstance(l, Name) and l.name in self.var_cells \
                and isinstance(r, Num) and r.v == 128:
            if self.flags == ("twice", l.name):
                pass  # the DBL result is still live
            else:
                self.ins("LDA %s" % l.name, hl_ln)
                self.ins("DBL", hl_ln)
            self.jump_a = self.a
            self.flags = ("twice", l.name)
            self.emit_branch(op, tlab, flab, hl_ln)
            return self.falls(op)
        self.eval(l, hl_ln)
        kind = self.operand(r, hl_ln)
        if kind[0] == "imm":
            self.ins("SUBI %d" % kind[1], hl_ln)
            rdesc = ("imm", kind[1])
        elif kind[0] in ("var", "cell"):
            self.ins("SUB %s" % kind[1], hl_ln)
            rdesc = (kind[0], kind[1])
        else:
            self.ins("STA _t0", hl_ln)
            self.eval(r, hl_ln)
            self.ins("STA _t1", hl_ln)
            self.ins("LDA _t0", hl_ln)
            self.ins("SUB _t1", hl_ln)
            rdesc = ("expr",)
        # A == l - r now; conditions may clobber A, but record the diff
        # so a following `x = x - y` can reuse it, and the flags so a
        # second comparison of the same operands costs only its branch
        self.a = ("diff", self.desc_of(l), rdesc)
        self.jump_a = self.a
        self.flags = ("cmp", self.desc_of(l), rdesc)
        self.emit_branch(op, tlab, flab, hl_ln)
        return self.falls(op)

    def emit_branch(self, op, tlab, flab, hl_ln):
        """Emit the branch(es) for a comparison whose flags are live.
        CF=1 iff l >= r (no borrow), ZF=1 iff l == r."""
        if op == "==":
            self.ins("JNZ %s" % flab, hl_ln)
        elif op == "!=":
            self.ins("JZ %s" % flab, hl_ln)
        elif op == ">=":
            self.ins("JNC %s" % flab, hl_ln)
        elif op == "<":
            self.ins("JC %s" % flab, hl_ln)
        elif op == ">":
            # false iff l <= r: CF=1 or ZF=1
            self.ins("JC %s" % flab, hl_ln)
            self.ins("JZ %s" % flab, hl_ln)
        elif op == "<=":
            # true iff CF=1 or ZF=1: jumps on true, falls on false
            self.ins("JNC %s" % tlab, hl_ln)
            self.ins("JZ %s" % tlab, hl_ln)
        else:
            raise HLError(hl_ln, "unknown comparison %r" % op)

    @staticmethod
    def falls(op):
        """Which side falls through after emit_branch."""
        return "false" if op == "<=" else "true"

    def operand_desc(self, r, hl_ln):
        kind = self.operand(r, hl_ln)
        return (kind[0], kind[1]) if kind[0] != "expr" else ("expr",)

    def desc_of(self, node):
        if isinstance(node, Name):
            if node.name in self.var_cells:
                return ("var", node.name)
            if node.name in self.consts:
                v = self.consts[node.name]
                return ("imm", v) if v <= 15 else ("cell", self.const_cell(v))
        if isinstance(node, Num):
            return ("imm", node.v) if node.v <= 15 else ("cell", self.const_cell(node.v))
        return ("expr",)

    # ---- statements

    def gen_stmt(self, st):
        ln = st.lineno
        if isinstance(st, VarDecl):
            if st.name in self.var_cells or st.name in self.consts:
                raise HLError(ln, "%r is already declared" % st.name)
            v = self.fold(st.init)
            if v is None:
                raise HLError(ln, "the initializer must be a constant - RAM"
                                  " is loaded before the program runs")
            if not 0 <= v <= 255:
                raise HLError(ln, "initializer must be 0-255")
            self.var_cells.add(st.name)
            self.data_rows.append((st.name, v))
            return
        if isinstance(st, ConstDecl):
            if st.name in self.var_cells or st.name in self.consts:
                raise HLError(ln, "%r is already declared" % st.name)
            self.consts[st.name] = st.v
            return
        if isinstance(st, Assign):
            self.gen_assign(st)
            return
        if isinstance(st, Out):
            self.eval(st.e, ln)
            self.ins("OUT", ln)
            return
        if isinstance(st, Simple):
            if st.which == "halt":
                self.ins("HLT", ln)
            elif st.which == "pass":
                self.ins("NOP", ln)
            else:
                if not self.loops:
                    raise HLError(ln, "%r is only valid inside a while" % st.which)
                head, exit_ = self.loops[-1]
                if st.which == "break":
                    self.broke = True
                self.ins("JMP %s" % (head if st.which == "continue" else exit_), ln)
            return
        if isinstance(st, While):
            head = self.newlabel("loop")
            exit_ = self.newlabel("done")
            bodyl = self.newlabel("body")
            self.label(head)
            got = self.cond(st.cond, bodyl, exit_, ln)
            self.loops.append((head, exit_))
            self.broke = False
            if got == "true":
                # the condition's true side falls into the body
                for s in st.body:
                    self.gen_stmt(s)
            else:
                # the condition's true side jumps to bodyl; the false
                # side fell here - leave the loop
                self.ins("JMP %s" % exit_, ln)
                self.label(bodyl, a_hint=self.jump_a)
                for s in st.body:
                    self.gen_stmt(s)
            self.loops.pop()
            self.ins("JMP %s" % head, ln)
            # break edges may arrive with a different A than the
            # condition's false edge: only hint when no break was emitted
            hint = None if self.broke else self.jump_a
            self.label(exit_, a_hint=hint, flags_hint=None)
            return
        if isinstance(st, If):
            end = self.newlabel("endif")
            end_states = []
            for i, (c, body) in enumerate(st.arms):
                last_arm = i == len(st.arms) - 1 and not st.orelse
                els = end if last_arm else self.newlabel("else")
                thenl = self.newlabel("then")
                got = self.cond(c, thenl, els, ln)
                if got == "true":
                    # true falls into the body
                    for s in body:
                        self.gen_stmt(s)
                    if not terminates(body):
                        self.ins("JMP %s" % end, ln)
                        end_states.append(self.a)
                else:
                    # true jumps to thenl; false fell here - go to else
                    self.ins("JMP %s" % els, ln)
                    self.label(thenl, a_hint=self.jump_a)
                    for s in body:
                        self.gen_stmt(s)
                    if not terminates(body):
                        self.ins("JMP %s" % end, ln)
                        end_states.append(self.a)
                if els != end:
                    self.label(els, a_hint=self.jump_a)
            for s in st.orelse:
                self.gen_stmt(s)
            end_states.append(self.a)
            # if every path into end arrives with the same A value, the
            # join can keep that knowledge (out x after if/else: rol.asm)
            hint = end_states[0] if end_states and all(
                s == end_states[0] for s in end_states) and end_states[0] else None
            self.label(end, a_hint=hint)
            return
        raise HLError(ln, "internal: unknown statement")

    def gen_assign(self, st):
        ln = st.lineno
        name = st.name
        if name in self.consts:
            raise HLError(ln, "cannot assign to the constant %r" % name)
        if name not in self.var_cells:
            raise HLError(ln, "undefined variable %r (declare it: var %s)"
                          % (name, name))
        # the compare-reuse idiom: the condition left A == l - r and this
        # assignment recomputes that same subtraction into the left var
        if self.a and self.a[0] == "diff":
            d_l, d_r = self.a[1], self.a[2]
            if d_l == ("var", name) and isinstance(st.e, Bin) and st.e.op == "-" \
                    and self.same_operand(st.e.l, d_l) and self.same_operand(st.e.r, d_r):
                self.ins("STA %s" % name, ln)
                # the ALU's ZF tested exactly this new value
                self.flags = ("cmp", ("var", name), ("imm", 0))
                return
        pre = len(self.out)
        self.eval(st.e, ln)
        last = self.out[-1] if len(self.out) > pre else None
        self.ins("STA %s" % name, ln)
        # eval skips LDA/LDI/DBL when A already holds the needed value
        if last:
            head = last.split()[0].upper()
            if head in ("ADD", "SUB", "ADDI", "SUBI", "DBL"):
                # the last ALU operation computed the assigned value, so
                # its ZF tells whether the variable is now zero
                self.flags = ("cmp", ("var", name), ("imm", 0))

    def same_operand(self, node, desc):
        if desc[0] == "var":
            return isinstance(node, Name) and node.name == desc[1]
        if desc[0] == "imm":
            if isinstance(node, Num):
                return node.v == desc[1]
            return isinstance(node, Name) and self.consts.get(node.name) == desc[1]
        if desc[0] == "cell":
            v = node.v if isinstance(node, Num) else self.consts.get(node.name)
            return v is not None and self.const_cell(v) == desc[1]
        return False

def terminates(body):
    return body and isinstance(body[-1], Simple) and body[-1].which == "halt"

# ---------------------------------------------------------------------------
# top level

def compile_program(path):
    toks = lex(path)
    stmts = Parser(toks).program()
    g = Gen()
    for st in stmts:
        g.gen_stmt(st)
    out = list(g.out)
    if g.data_rows:
        out.append("")
        for cell, v in g.data_rows:
            out.append("%-8s .DB %d" % (cell + ":", v))
    return "\n".join(out) + "\n"

def compile_to_asm(path, mem_size):
    """Full pipeline: .hl -> asm text, validated by assembling it."""
    text = compile_program(path)
    with tempfile.NamedTemporaryFile("w", suffix=".asm", delete=False,
                                     encoding="utf-8") as fh:
        fh.write(text)
        tmp = fh.name
    try:
        asm_assemble(tmp, mem_size)
    except SystemExit as e:
        raise HLError(0, "the program does not fit the hardware: %s" % e)
    finally:
        os.unlink(tmp)
    return text

# ---------------------------------------------------------------------------
# CLI

def main():
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("input", help=".hl source file")
    p.add_argument("--stdout", action="store_true",
                   help="print the generated .asm and write nothing")
    p.add_argument("--no-asm", action="store_true",
                   help="do not keep the generated .asm file")
    p.add_argument("--mem-size", type=int, default=16,
                   help="RAM size in bytes (default: 16)")
    args = p.parse_args()

    base = args.input[:-3] if args.input.endswith(".hl") else args.input
    try:
        text = compile_to_asm(args.input, args.mem_size)
    except HLError as e:
        raise SystemExit("compile: %s:%s" % (args.input, e))

    if args.stdout:
        sys.stdout.write(text)
        return

    with open(base + ".asm", "w", encoding="utf-8") as fh:
        fh.write(text)
    print("compile: wrote %s.asm" % base)
    mem, rows = asm_assemble(base + ".asm", args.mem_size)
    used = sum(1 for _a, b, _t in rows if b is not None)
    sys.stdout.write(asm.format_listing(rows, used, args.mem_size))
    asm.write_image(base + ".bin", mem, "bin")
    print("compile: wrote %d-byte image to %s.bin" % (len(mem), base))

if __name__ == "__main__":
    main()
