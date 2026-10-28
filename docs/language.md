# The .hl language

`tools/compile.py` compiles `.hl` programs to the assembly language
([assembly-language.md](assembly-language.md)), which `tools/asm.py`
assembles to the `.lst` entry table and the `.bin` image the machine
runs - the full chain, with who produces what, is in
[tools.md](tools.md), "The build chain". One command does all of it:

    python3 tools/compile.py programs/count.hl
    # -> programs/count.asm (inspection) + programs/count.lst (the
    #    dipswitch entry table) + programs/count.bin (the machine image)

The language is a thin, honest layer over the machine
([instruction-set.md](instruction-set.md) is the ground truth). It
gives names, expressions and structured control; it refuses everything
the hardware cannot do, at compile time, with a reason.

## The machine the language assumes

- one 8-bit accumulator (A), 16 bytes of RAM shared by code and data,
  8-bit wrap-around arithmetic, unsigned comparisons
- variables are RAM cells entered together with the program (the `.DB`
  bytes in the generated assembly)
- every instruction is one byte: 4-bit opcode, 4-bit operand (a RAM
  address or a small immediate)

## Statements

```
var x = 9         # a data cell with an initial value (a constant; RAM
                  # is loaded before the program runs, so initializers
                  # cannot compute anything)
var y             # a data cell that starts 0
const limit = 10  # a named constant (assembled into instructions or
                  # folded - never a RAM cell)
x = expr          # assignment
out expr          # display a value
halt              # stop the clock
pass              # a NOP (pacing; the countdown uses it)
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
```

Comments run from `#` or `;` to the end of the line; `;` also separates
statements on one line. Blocks are indented (multiples of 4 spaces);
a single simple statement may follow the `:` (`while 1: out x`).

## Expressions

Numbers (`0`..`255`, decimal, `0x1F`, `0b1010`), variables, constants,
parentheses, unary `-`, and the operators `+`, `-`, `*`. Every value is
a byte: arithmetic wraps mod 256. `e * k` needs `k` constant - the
compiler emits the machine's multiply idioms (DBL for `* 2`, ADD chains
for small factors, shift-add for larger ones); `e * e` is rejected,
because the hardware has no multiply - write the counting loop
([mul.hl](../programs/mul.hl)).

`rol(e)` is the machine's rotate-left-through-carry idiom
(`DBL + JNC + ADDI 1`, [instruction-set.md](instruction-set.md)) as a
function: `rol(11)` is 22, `rol(176)` is 97.

## Conditions

Comparisons (`==`, `!=`, `<`, `<=`, `>`, `>=`) combined with `and`,
`or`, `not`, or a bare expression ("is nonzero"). Conditions never
become values - they compile straight to the machine's branch
structure, so short-circuit `and`/`or` cost only their branches.

Comparisons follow the machine's own rule: a subtraction sets CF=1 iff
there was no borrow (left >= right) and ZF=1 iff equal, so `x >= y` is
one SUB and one jump. `x >= 128` and `x < 128` use the DBL top-bit test
instead (one byte cheaper than a constant cell for 128).

## What compiles to what

| source | generated idiom |
|---|---|
| `x = 0` / `x = y` | `LDI 0, STA x` / `LDA y, STA x` |
| `x = x + 3` | `LDA x, ADDI 3, STA x` |
| `x = x + y` | `LDA x, ADD y, STA x` |
| `x = x * 2` | `LDA x, DBL, STA x` |
| `x = x * 3` | `LDA x, ADD x, ADD x, STA x` |
| `x = x * 13` | shift-add on a temp cell (`DBL/ADD` chain) |
| `out x` after `x = ...` | just `OUT` (the compiler tracks A) |
| `x = x - y` after `while x >= y` | just `STA x` (the condition's SUB already computed it) |
| `x = x * 2 + 1` after `if x >= 128` | `ADDI 1, STA x` (the test's DBL already doubled) |
| `while x >= y:` | `LDA x, SUB y, JNC exit` |
| `if x == y:` | `LDA x, SUB y, JNZ else` |
| `if x >= 128:` | `LDA x, DBL, JNC else` |
| `while n != 0:` | `LDA n, SUBI 0, JZ exit` (the free TEST instruction) |
| `rol(x)` | `DBL, JNC l, ADDI 1, l:` |
| `pass` | `NOP` |

Two consecutive comparisons of the same operands (as in
[gcd.hl](../programs/gcd.hl)) share one SUB, exactly like the hand
written assembly: the flags survive jumps and loads.

## What the compiler refuses (and why)

| rejected | reason |
|---|---|
| `b = x < y` | booleans are not storable - there is no boolean cell; use `if`/`while` |
| `x // y`, `x % y` | no divide; write the repeated-subtraction loop ([div.hl](../programs/div.hl), [mod.hl](../programs/mod.hl)) |
| `e * e` | no multiply instruction; write the counting loop ([mul.hl](../programs/mul.hl)) |
| functions, `call`, recursion | no stack, no return address - see [getting-to-os.md](getting-to-os.md) |
| arrays, pointers, indexing | no indirect addressing (the MAR cannot be loaded from RAM) |
| assigning to a `const`, using an undeclared name, non-constant `var` initializers | the language keeps names and data honest |
| programs whose code + data exceed 16 bytes | RAM is 16 bytes; nothing larger can be entered into the machine |
| numbers outside 0..255 | a byte is a byte |

Self-modifying code (rewriting your own instructions, like the
historical patch.asm) is not expressible: variables live in data cells,
the compiler owns the code addresses, and an accidental write over
your own code is exactly the kind of mistake the language exists to
prevent.

## The corpus

Every program in [../programs](../programs) is a `.hl` source; the
generated `.asm` (kept by `compile.py`, gitignored) shows exactly what
the machine will run, and the `.lst` beside it is the front-panel
entry table - the dipswitch bit groups, one line per address, and [web/test/verify.py](../web/test/verify.py)
runs each program on the machine against the frozen expected outputs.
