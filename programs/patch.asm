; patch.asm - self-modifying code: the program rewrites its own
; instruction
;
; A von Neumann machine: program and data share RAM, so nothing stops
; a program from writing over its own code. Lap 1: the ADD at address
; 01 reads x, so the display shows 7. Then the program builds the byte
; for "ADD y" (0x2A = 42 = 15 + 27) and stores it over address 01 -
; from lap 2 on, the SAME instruction means "add 9 instead" and the
; display shows 9 forever. Watch the IR operand LEDs change while the
; PC keeps returning to the same address.
;
; .ORG places y at exactly address 0x0A so the byte above is 0x2A.

loop:   LDI 0
        ADD x        ; lap 1: A = x; later laps: A = y (this line rewrites itself)
        OUT
        LDI 15
        ADD m27      ; 15 + 27 = 42 = 0x2A, the encoding of "ADD y"
        STA 1        ; write it over the instruction at address 01 (!)
        JMP loop
x:      .DB 7
m27:    .DB 27
        .ORG 10
y:      .DB 9        ; y sits at 0x0A -> "ADD y" encodes as 0x2A
