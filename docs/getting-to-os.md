# Getting to an OS - what it would take for this machine to run one

The honest answer first, same shape as the C answer
([getting-to-c.md](getting-to-c.md)): **an OS on this machine as it
stands is impossible, permanently** - an OS is by definition a program
that stays resident while another program runs, and 16 bytes cannot
hold both. But the punchline of this doc is that the machine does not
need a third upgrade program: the upgrades an OS demands are the same
upgrades C demands. L3 in the C ladder is also the OS threshold. One
hardware project, three payoffs: C, an OS, and the compiler that
justifies both.

## What "putting an OS on" actually is

An OS is not installed onto the silicon - it is the far end of a chain
of loaders, and every link in that chain is just a program whose one
special property is knowing how to load the next program:

```
power on -> hardware reset state -> firmware -> bootloader
        -> kernel -> init -> ... -> your program
```

On a modern x86 machine: the CPU forces the program counter to a fixed
reset vector; the firmware (BIOS/UEFI) in a ROM on the board brings up
memory and loads the bootloader from disk; the bootloader loads the
kernel; the kernel, from then on, never gives the machine back
voluntarily - every program ever run is loaded *by* it.

The "who loads the loader" paradox terminates in the chain's first two
links: **ROM and the reset state**. The first link is written to a
non-volatile chip while the machine is off, by another machine - the
"installer". That is the entire secret of installing an OS.

This machine today is the same chain with a human as its first link.
The dipswitch program entry ([hardware.md](hardware.md), "Front panel")
is the firmware; PROG_ADDR set to 0 and RESET held
([hardware.md](hardware.md), "Clock, reset, and power") is the reset
vector; asm.py assembling on the host is the installer. The chain is
one link long: once the program starts, nothing can ever get the
machine back - which is the next section's point.

## What an OS minimally is

Three requirements, and only three:

1. **It regains control when a program ends.** The essence - without a
   hand-back mechanism, whatever runs first is just "the program".
2. **It can load and start more than one program** - not necessarily
   from a disk; switches, tape, or a second ROM count, historically.
3. **It offers at least one service through a defined entry point** -
   print a byte, read a byte.

None of: disks, files, windows, memory protection, multiple users, or
preemption are required. This is not the bar lowered to fit - it is
what the earliest genuine OSes actually were. The KIM-1 (1975, 1KB
RAM) shipped with a 2KB ROM monitor: a loop that read a program and
address, jumped there, and printed its prompt again when the program
returned. CP/M - a full commercial OS that ran WordStar - is the same
three requirements elaborated to about 8KB: a hardware layer, a
service layer (its entire syscall interface is a jump table at fixed
address 0x0005), and a shell that reads a command line and loads the
program. It was single-tasking, cooperative, and had no protection.

## The three gaps (plus one optional)

| gap | why it is a gap | what closes it |
|-----|-----------------|---------------|
| coexistence | the OS must be resident while a program runs; 16 bytes cannot hold both, and the 64-byte tier does not either | 2KB SRAM and a memory map - OS low (in ROM at L3, so a buggy program cannot crash it), programs above ([additions.md](additions.md), "New chips", item 4) |
| hand-back | a program must jump somewhere and have the machine return - PC saved, then restored | SP + CALL/RET ([additions.md](additions.md), "New chips", item 3) - *the* primitive: "run a program" becomes CALL, "program ends" becomes RET, "syscall" becomes CALL to a fixed service table, CP/M-style |
| load path | dipswitch entry is the human-scale firmware, not something a resident program can drive | any one of: IN ([additions.md](additions.md), "New chips", item 2), the ROM bank switch ([additions.md](additions.md), "Microcode only"), or the host-side assembler, which already exists |
| preemption (optional) | nothing can interrupt a running program; cooperative OSes never needed this | an interrupt pin that hijacks the microstep counter and saves the PC - a third control ROM plus new wiring; furthest away, and CP/M, classic Mac OS through 9, and Windows through 3.x all shipped without it |

The hand-back gap is worth pausing on: it is the same gap C calls
"functions" ([getting-to-c.md](getting-to-c.md), "What C needs"). The
stack that lets a subroutine return is the stack that lets a program
return to the OS. That identity, up and down the list - functions are
hand-back, pointers are programs living above the OS, 2KB is
coexistence - is why C and the OS are one project.

## What the OS would literally be

The memory map at L3 (addresses are 16-bit there - none of this is
expressible in today's ISA):

```
0x0000-0x01FF   OS, in the code ROM - entered automatically at reset
0x0005          the syscall jump table (CP/M's convention)
0x0200-0x07FF   SRAM: user programs loaded here, plus their variables
```

"Installing the OS" then means exactly what it means on a real
machine: the OS is the thing already sitting at the reset vector. It
is burned into a 28C16 on the host with the tools this repo already
has.

The whole OS, in L3-shaped assembly:

```
start:  LDI '>' / OUT              ; a prompt, so a human knows it is alive
loop:   <read a program in>        ; IN bytes, or copy a ROM bank, to 0x0200
        CALL 0x0200                ; the OS instruction
        J loop                     ; the line that makes it an OS:
                                 ; control came BACK - next program
```

A "program" is anything ending in RET. The first service in the jump
table writes A to the display register - one syscall, `CALL 0x0005`
with a service number in A, and it is a genuine (single-user,
single-tasking, cooperative) operating system: the same shape as CP/M,
the way a paper plane is the same shape as a 747.

## Where OS capability lands on the ladder

The milestones map onto the same ladder as
[getting-to-c.md](getting-to-c.md), "The ladder - what each level
buys":

| the machine | OS status |
|-------------|-----------|
| L0-L2 + the 64-byte tier | impossible - the OS and a program still cannot coexist; the human is the firmware and the whole chain |
| L3 | writable: a ROM-resident monitor, programs loaded into SRAM, CALL/RET hand-back, the syscall table - a KIM-1-class OS on day one |
| L3 + IN | conversational: the OS reads at run time; a program can be typed in, run, replaced - CP/M-class usage |
| L3 + interrupts | preemptive: a timer can take the machine back mid-program; this is *beyond* L3 in the additions tiers, not part of it |

## Distances, honestly

- An OS on the current 16-byte machine: impossible, forever - same
  two orders of magnitude as C, because it is the same memory gap.
- The single unlock is the stack: SP + CALL/RET is the one primitive
  that separates an OS from a program; everything else on the list is
  elaboration of it.
- A KIM-1-class monitor at L3: a few hundred bytes of L3 assembly,
  once the L3 hardware exists - the hardware is the long pole, not the
  OS, exactly as with C.
- Preemption: the furthest milestone, and genuinely new hardware
  (interrupt pin, third ROM, saved PC) - cooperative first, as the
  8-bit era did.
- A modern OS: the same three requirements with fifty years stacked on
  the "regain control" line; nothing in kind, only in degree.
