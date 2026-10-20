; rotate.asm - rotate a byte left through the carry - the shift
; instruction the machine does not have, faked with ADD
;
; A + A doubles the byte (a left shift) and the carry out is exactly
; the bit that fell off the top; JC + ADD one feed it back into bit
; 0. With s=1 the display (and the A-register LEDs) chase a single
; light: 1, 2, 4, 8, ... 128, 1, ... This is also the building block
; of serial links - shift registers before there were shift
; instructions.

loop:   LDA s
        ADD s        ; A = 2s; CF = old bit 7 (the bit shifted out)
        JC  wrap
        STA s
        OUT
        JMP loop
wrap:   ADD one      ; rotate the carry back into bit 0
        STA s
        OUT
        JMP loop
s:      .DB 1
one:    .DB 1
